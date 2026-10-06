"""Entradas del cálculo para cada incidente y casos de respuesta conocida para comprobarlo.

Casos de respuesta conocida (la autoridad dijo qué dron era), de tres sitios:

1. los incidentes de la base en que una frase oficial nombra el modelo o la familia
   (proceso/tipo_dron/identificacion.py);
2. los casos de configuracion/validacion_deduccion.json (restos y declaraciones oficiales, con su
   fuente), sin los que ya son un incidente de la base;
3. los encuentros de la UK Airprox Board cuyo catálogo clasifica el objeto: «Fixed-wing RPAS»
   (ala fija), «Rotary-wing RPAS» o «Rotorcraft» (multirrotor), o un modelo nombrado (DJI…).

Al comprobar, cada caso se calcula con los nombres de modelo tapados en todas sus frases y con la
frecuencia de partida sacada de los demás casos.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import zona as zona_
from proceso.deduccion import geo
from proceso.tipo_dron import identificacion, modelo, rasgos
from proceso.tipo_dron.rasgos import Frase

VALIDACION = (
    Path(__file__).resolve().parent.parent.parent / "configuracion" / "validacion_deduccion.json"
)
# Reglas del motor de deducción que cuentan: los descartes de cualquier regla física y la
# condición de la meteorología («solo con el viento a favor»). «Solo con despegue dentro del
# país» es lo normal para un dron comercial y no resta.
CONDICIONES_QUE_PESAN = ("meteorologia",)

# Categorías del catálogo de la UK Airprox Board.
UKAB_ALA_FIJA = ("Fixed-wing RPAS", "Fixed-Wing")
UKAB_MULTIRROTOR = ("Rotary-wing RPAS", "Rotorcraft")
UKAB_ALA_FIJA_DESDE = 2017
CLASES_ALA_FIJA_UKAB = ("aeromodelo_ala_fija_pequeno", "ala_fija_tactica_electrica")
CLASES_MULTIRROTOR = (
    "multirrotor_consumo_sub250",
    "multirrotor_consumo",
    "multirrotor_profesional",
    "multirrotor_pesado_carga",
    "fpv",
)


@dataclass
class Conocido:
    id: str
    fuente_respuesta: str  # base | validacion | ukab
    respuesta: tuple[str, ...]  # clases del catálogo
    entrada: modelo.Entrada
    pais: str | None = None
    fecha: str | None = None
    detalle: dict[str, Any] = field(default_factory=dict)

    @property
    def grupos(self) -> set[str]:
        return {modelo.grupo_de_clase()[c] for c in self.respuesta}


def a_documento(conocido: Conocido) -> Documento:
    """El caso tal como entra en el cálculo, para la copia fija de la comprobación (CI)."""
    e = conocido.entrada
    return {
        "id": conocido.id,
        "fuente_respuesta": conocido.fuente_respuesta,
        "respuesta": list(conocido.respuesta),
        "pais": conocido.pais,
        "fecha": conocido.fecha,
        "detalle": conocido.detalle,
        "entrada": {
            "zona": e.zona,
            "d_partes_km": e.d_partes_km,
            "d_costa_km": e.d_costa_km,
            "con_punto": e.con_punto,
            "entrada_exterior": e.entrada_exterior,
            "rasgos": e.rasgos,
            "motor": {c: [list(x) for x in v] for c, v in e.motor.items()},
        },
    }


def de_documento(documento: Documento) -> Conocido:
    e = documento["entrada"]
    return Conocido(
        documento["id"],
        documento["fuente_respuesta"],
        tuple(documento["respuesta"]),
        modelo.Entrada(
            zona=e["zona"],
            d_partes_km=e["d_partes_km"],
            d_costa_km=e["d_costa_km"],
            con_punto=e["con_punto"],
            entrada_exterior=e["entrada_exterior"],
            rasgos=e["rasgos"],
            motor={c: [(x[0], x[1]) for x in v] for c, v in e["motor"].items()},
        ),
        documento.get("pais"),
        documento.get("fecha"),
        documento.get("detalle") or {},
    )


def motor_de(deduccion: Documento | None) -> dict[str, list[tuple[str, str]]]:
    if not deduccion:
        return {}
    efectos: dict[str, list[tuple[str, str]]] = {}
    for d in deduccion.get("descartadas", []):
        for por in d.get("por", []):
            efectos.setdefault(d["clase"], []).append(("descarta", str(por.get("regla"))))
    for c in deduccion.get("compatibles", []):
        for condicion in c.get("condiciones", []):
            if condicion.get("regla") in CONDICIONES_QUE_PESAN:
                efectos.setdefault(c["clase"], []).append(("condicion", condicion["regla"]))
    return efectos


def distancias(pais: str | None, lat: float, lon: float) -> tuple[float | None, float | None]:
    """A Ucrania, Rusia o Bielorrusia y a la costa del país (cotas inferiores, km)."""
    partes = zona_.distancia_frontera_km(lat, lon)
    costa = geo.exterior(pais, lat, lon).costa_km if pais else None
    return partes, costa


def frases_de(
    lista: Iterable[tuple[str, str, str, str | None]], tapar: bool = False
) -> list[Frase]:
    """Las frases del incidente (origen, fuente, texto, idioma), con los modelos tapados si se
    pide."""
    return [Frase(identificacion.tapar_modelos(t) if tapar else t, f, o, i) for o, f, t, i in lista]


def entrada_de_incidente(
    documento: Documento, frases: list[Frase], deduccion: Documento | None
) -> modelo.Entrada:
    lugar = documento.get("lugar") or {}
    punto = lugar.get("punto")
    partes = costa = None
    if punto:
        partes, costa = distancias(lugar.get("pais"), punto["lat"], punto["lon"])
    pruebas = documento.get("pruebas") or {}
    return modelo.Entrada(
        zona=(documento.get("zona") or {}).get("grupo"),
        d_partes_km=partes,
        d_costa_km=costa,
        con_punto=bool(punto),
        entrada_exterior=documento.get("tipo") == "incursion"
        or pruebas.get("entrada_exterior") is True,
        rasgos=rasgos.de_frases(frases),
        motor=motor_de(deduccion),
    )


# --- Casos de respuesta conocida ---------------------------------------------------------------


def de_la_base(
    incidentes: Iterable[
        tuple[Documento, list[tuple[str, str, str, str | None]], Documento | None]
    ],
) -> list[Conocido]:
    conocidos = []
    for documento, lista, deduccion in incidentes:
        hallado = identificacion.identificado(frases_de(lista))
        if hallado is None:
            continue
        entrada = entrada_de_incidente(documento, frases_de(lista, tapar=True), deduccion)
        conocidos.append(
            Conocido(
                documento["id"],
                "base",
                tuple(hallado["clases"]),
                entrada,
                (documento.get("lugar") or {}).get("pais"),
                ((documento.get("tiempo") or {}).get("inicio") or {}).get("valor", "")[:10],
                {"modelo": hallado["modelo"], "cita": hallado["cita"]},
            )
        )
    return conocidos


def de_validacion(ya: list[Conocido], ruta: Path = VALIDACION) -> list[Conocido]:
    """Los casos del fichero de validación que no son ya un incidente de la base (por su enlace
    o por el mismo país, el mismo grupo y un día de diferencia como mucho)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    conocidos = []
    for caso in datos["casos"]:
        respuesta = tuple(c for c in caso["clases_reales"] if c in modelo.grupo_de_clase())
        if not respuesta:
            continue
        grupos = {modelo.grupo_de_clase()[c] for c in respuesta}
        if caso.get("incidente") and any(k.id == caso["incidente"] for k in ya):
            continue
        if any(
            k.pais == caso["pais"]
            and k.fecha
            and abs(_dias(k.fecha) - _dias(caso["fecha"])) <= 1
            and k.grupos & grupos
            for k in ya
        ):
            continue
        lat, lon = caso["punto"]["lat"], caso["punto"]["lon"]
        partes, costa = distancias(caso["pais"], lat, lon)
        grupo_zona = zona_._por_punto(lat, lon)[0]
        frases = [
            Frase(identificacion.tapar_modelos(f["cita"]), f["url"], "oficial_citado")
            for f in caso.get("fuentes", [])
            if f.get("cita")
        ]
        entrada = modelo.Entrada(
            zona=grupo_zona,
            d_partes_km=partes,
            d_costa_km=costa,
            con_punto=True,
            entrada_exterior=bool(caso.get("entrada_exterior")) or grupo_zona == "frontera",
            rasgos=rasgos.de_frases(frases),
        )
        conocidos.append(
            Conocido(
                caso["id"],
                "validacion",
                respuesta,
                entrada,
                caso["pais"],
                caso["fecha"],
                {"modelo": caso["modelo"]},
            )
        )
    return conocidos


def _dias(fecha: str) -> int:
    from datetime import date

    return date.fromisoformat(fecha[:10]).toordinal()


def respuesta_ukab(objeto: Documento, anio: int | None = None) -> tuple[str, ...] | None:
    """La clase que da el catálogo de la UKAB (no la que sale de la descripción). Hasta 2016 el
    catálogo pone «RPAS - Fixed-wing RPAS» a casi todos los drones: de los de 2014 a 2016 con
    forma descrita, 11 son «quadcopter» y 4 ala fija. Esa categoría solo cuenta desde 2017, cuando
    el catálogo separa «Rotary-wing RPAS»."""
    categoria = str(objeto.get("categoria_catalogo") or "")
    tipo = str(objeto.get("tipo_catalogo") or "")
    nombrados = identificacion.familias_en(tipo)
    if nombrados:
        return identificacion.clases_de(nombrados[0][1])
    if any(c in categoria for c in UKAB_ALA_FIJA) and (anio or 0) >= UKAB_ALA_FIJA_DESDE:
        return CLASES_ALA_FIJA_UKAB
    if any(c in categoria for c in UKAB_MULTIRROTOR):
        return CLASES_MULTIRROTOR
    return None


def de_ukab(encuentros: Iterable[Documento]) -> list[Conocido]:
    conocidos = []
    for encuentro in encuentros:
        objeto = encuentro.get("objeto") or {}
        instante = str((encuentro.get("instante") or {}).get("valor") or "")
        respuesta = respuesta_ukab(objeto, int(instante[:4]) if instante[:4].isdigit() else None)
        if respuesta is None:
            continue
        frases = []
        if objeto.get("descripcion"):
            frases.append(
                Frase(
                    identificacion.tapar_modelos(objeto["descripcion"]),
                    encuentro["id"],
                    "oficial",
                    "en",
                )
            )
        lista = rasgos.de_frases(frases)
        altura = objeto.get("altura_m")
        if isinstance(altura, dict) and altura.get("max") is not None:
            lista.append(
                {
                    "rasgo": rasgos.ALTURA,
                    "valor": {"metros": float(altura["max"])},
                    "cita": (encuentro.get("altitud") or {}).get("texto"),
                    "fuente": encuentro["id"],
                    "origen": "oficial",
                }
            )
        punto = (encuentro.get("posicion") or {}).get("punto")
        partes = costa = None
        if punto:
            partes, costa = distancias(encuentro.get("pais"), punto["lat"], punto["lon"])
        entrada = modelo.Entrada(
            zona="interior",
            d_partes_km=partes,
            d_costa_km=costa,
            con_punto=bool(punto),
            rasgos=lista,
        )
        conocidos.append(
            Conocido(
                encuentro["id"],
                "ukab",
                respuesta,
                entrada,
                encuentro.get("pais"),
                ((encuentro.get("instante") or {}).get("valor") or "")[:10],
                {
                    "categoria": objeto.get("categoria_catalogo"),
                    "tipo": objeto.get("tipo_catalogo"),
                },
            )
        )
    return conocidos
