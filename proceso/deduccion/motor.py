"""Motor de deducción: para cada incidente europeo, cada impacto con lugar y cada ataque de la
capa de guerra, qué clases de dron son compatibles, cuáles quedan descartadas y por qué, y desde
dónde pudo despegar. Solo reglas de código (proceso/deduccion/reglas.py) sobre el catálogo de
prestaciones (configuracion/catalogo_drones.json) y los datos medidos de la base.

Combinación por clase, sin votar por mayoría:

- descartada: alguna regla física la descarta y ninguna evidencia la apoya;
- indeterminada con conflicto: una regla la descarta y la descripción de testigos o pilotos (o el
  modelo que da la fuente) la apoya; se guardan las reglas enfrentadas;
- compatible: alguna regla física pudo evaluarla y ninguna la descarta, con sus condiciones
  (relevos, despegue dentro del país, varios equipos...) e indicios;
- indeterminada: ninguna regla física tenía datos para ella.

Si todas las clases evaluadas quedan descartadas, las pruebas no encajan entre sí: todas pasan a
indeterminadas con el conflicto declarado. Lo deducido lleva siempre origen «deducido», método
«regla», la versión de cada regla y la del catálogo, y nunca se mezcla con lo medido ni con lo
oficial (va en su propio bloque `deduccion`, interno).
"""

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from proceso import textos_dron
from proceso.deduccion import deriva, direccion, geo, reglas, viento, zona_despegue
from proceso.deduccion.catalogo import Catalogo
from proceso.deduccion.reglas import Caso, Evidencia, Origen, Sitio

VERSION = "1.1.0"
COMPATIBLE = "compatible"
DESCARTADA = "descartada"
INDETERMINADA = "indeterminada"
# Ventana que se da a un inicio con precisión de hora (o a un inicio sin fin).
DURACION_HORA = timedelta(hours=1)
PRECISIONES_HORA = frozenset({"minuto", "hora"})
ORIGENES_OFICIALES = frozenset({"oficial", "oficial_citado", "medido"})
CLASE_DERIVA = "senuelo_largo_alcance"


def _segundos(instante: dict[str, Any] | None) -> float | None:
    if not instante or not instante.get("valor"):
        return None
    texto = str(instante["valor"]).replace("Z", "+00:00")
    return datetime.fromisoformat(texto).timestamp()


def _rango(valor: Any) -> tuple[float, float] | None:
    if isinstance(valor, dict) and "min" in valor and "max" in valor:
        return float(valor["min"]), float(valor["max"])
    return None


def instante(momento: datetime) -> dict[str, str]:
    return {"precision": "minuto", "valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")}


# --- Casos -------------------------------------------------------------------------


def entrada_confirmada(incidente: dict[str, Any]) -> bool:
    """Una autoridad (o algo medido) dice que el dron entró desde fuera del país."""
    from exportacion.procedencia import origen_de_fuente

    fuentes = {f["id"]: f for f in incidente.get("fuentes", [])}
    for afirmacion in incidente.get("afirmaciones", []):
        if afirmacion.get("campo") != "entrada_exterior" or afirmacion.get("valor") is not True:
            continue
        fuente = fuentes.get(afirmacion.get("fuente_id", ""))
        if fuente and origen_de_fuente(fuente) in ORIGENES_OFICIALES:
            return True
    return False


def caso_de_incidente(
    incidente: dict[str, Any],
    condiciones: dict[str, Any] | None,
    trafico: dict[str, Any] | None,
    encuentros: list[dict[str, Any]] = (),  # type: ignore[assignment]
    mejor: dict[str, Any] | None = None,
    frases: Sequence[tuple[str, str, str, str | None]] = (),
) -> Caso:
    """`mejor`: el tiempo de mejor origen (exportacion/mejor_origen.momento): la hora de un
    cierre medido, de un registro oficial o de una autoridad, con su duración. `frases`: lo que
    escriben las fuentes del incidente ((origen, fuente, frase, idioma)), para la descripción y
    para el país desde el que una autoridad dice que entró."""
    lugar = incidente.get("lugar", {})
    detalle = incidente.get("detalle_oficial", {})
    punto = detalle.get("punto") or lugar.get("punto")
    radio = detalle.get("radio_km") or lugar.get("radio_km") or 0.0
    tiempo = incidente.get("tiempo", {})
    inicio_doc = detalle.get("inicio") or tiempo.get("inicio")
    origen_inicio = None
    if mejor and mejor.get("origen"):
        tiempo = mejor["tiempo"]
        inicio_doc = tiempo.get("inicio")
        origen_inicio = mejor["origen"]
    drones = incidente.get("drones", {})
    respuesta = incidente.get("respuesta", {})
    textos = [str(drones.get("modelo") or "")]
    for encuentro in encuentros:
        textos.append(str(encuentro.get("objeto", {}).get("descripcion") or ""))
    textos += [frase for _, _, frase, _ in frases]
    entrada_desde = None
    for origen, fuente, frase, _ in frases:
        if origen not in ORIGENES_OFICIALES:
            continue
        pais = textos_dron.pais_de_entrada(frase, lugar.get("pais"))
        if pais is not None:
            entrada_desde = {"pais": pais, "origen": origen, "fuente": fuente, "frase": frase}
            break
    gnss = (trafico or {}).get("interferencia_gnss") or {}
    nivel_gnss = None
    for clave in ("propia", "vecinas"):
        nivel = (gnss.get(clave) or {}).get("nivel")
        if nivel in {"media", "alta"} and nivel_gnss != "alta":
            nivel_gnss = nivel
    if nivel_gnss is None and gnss.get("resultado") == "medida":
        nivel_gnss = "sin_interferencia"
    deteccion = respuesta.get("deteccion") or []
    velocidad = _rango(drones.get("velocidad_ms"))
    return Caso(
        id=incidente["id"],
        tipo="incidente",
        pais=lugar.get("pais"),
        lat=punto["lat"] if punto else None,
        lon=punto["lon"] if punto else None,
        radio_km=float(radio),
        inicio=_segundos(inicio_doc),
        fin=_segundos(tiempo.get("fin")),
        precision=(inicio_doc or {}).get("precision"),
        duracion_min=tiempo.get("duracion_min"),
        entrada_exterior=bool(incidente.get("pruebas", {}).get("entrada_exterior"))
        or entrada_desde is not None,
        entrada_confirmada=entrada_confirmada(incidente) or entrada_desde is not None,
        condiciones=condiciones,
        gnss=nivel_gnss,
        textos=[t for t in textos if t],
        luces=drones.get("luces"),
        clase_declarada=drones.get("clase"),
        velocidad_ms=velocidad,
        # La velocidad la escriben solo las fuentes oficiales de detalle (detalle_oficial).
        velocidad_oficial=velocidad is not None,
        deteccion_radar=any("radar" in str(d) for d in deteccion),
        altura_m=_rango(drones.get("altura_m")) or altura_de_encuentros(encuentros),
        # La altura solo la escriben las fuentes oficiales de detalle o la UKAB.
        altura_oficial=_rango(drones.get("altura_m")) is not None
        or altura_de_encuentros(encuentros) is not None,
        origen_inicio=origen_inicio,
        entrada_desde=entrada_desde,
    )


PIE_M = 0.3048


def altura_de_encuentro(encuentro: dict[str, Any]) -> tuple[float, float] | None:
    """La altura de un encuentro de la UK Airprox Board en metros: la del informe (sobre el
    terreno, sobre el mar o nivel de vuelo, en pies), o None si no la da."""
    pies = (encuentro.get("altitud") or {}).get("pies")
    if not isinstance(pies, (int, float)) or pies <= 0:
        return None
    metros = round(float(pies) * PIE_M, 1)
    return (metros, metros)


def altura_de_encuentros(encuentros: list[dict[str, Any]] | None) -> tuple[float, float] | None:
    alturas = [a for e in encuentros or [] if (a := altura_de_encuentro(e)) is not None]
    if not alturas:
        return None
    return (min(a[0] for a in alturas), max(a[1] for a in alturas))


def caso_de_encuentro(encuentro: dict[str, Any]) -> Caso | None:
    """Un encuentro de la UK Airprox Board con un dron o un objeto, como caso del motor: su punto,
    su hora y su altura (oficial). None sin altura o sin punto."""
    altura = altura_de_encuentro(encuentro)
    punto = (encuentro.get("posicion") or {}).get("punto")
    if altura is None or not punto:
        return None
    objeto = encuentro.get("objeto") or {}
    textos = [str(objeto.get(c)) for c in ("descripcion", "tipo_catalogo") if objeto.get(c)]
    return Caso(
        id=encuentro["id"],
        tipo="encuentro",
        pais=encuentro.get("pais"),
        lat=punto["lat"],
        lon=punto["lon"],
        radio_km=5.0,
        inicio=_segundos(encuentro.get("instante")),
        precision=(encuentro.get("instante") or {}).get("precision"),
        textos=textos,
        altura_m=altura,
        altura_oficial=True,
    )


def evaluar_encuentro(catalogo: Catalogo, caso: Caso) -> dict[str, Any]:
    """Las reglas que dicen algo de un encuentro sin condiciones medidas: la altura y la
    descripción."""
    evidencias = reglas.r9_altura(catalogo, caso) + reglas.r7_descripcion(catalogo, caso)
    resultado = {**_base(catalogo), **combinar(catalogo, evidencias)}
    resultado["conclusiones"] = []
    return resultado


def _lugar_cercano(lista: list[dict[str, Any]], lat: float, lon: float, km: float) -> Any:
    mejor, distancia = None, km
    for lugar in lista:
        d = geo.distancia_km(lugar["lat"], lugar["lon"], lat, lon)
        if d <= distancia:
            mejor, distancia = lugar, d
    return mejor


def caso_de_impacto(
    catalogo: Catalogo,
    impacto: dict[str, Any],
    ataque: dict[str, Any] | None,
    condiciones_ataque: dict[str, Any] | None,
) -> Caso:
    lugar = impacto["lugar"]
    lat, lon = lugar["punto"]["lat"], lugar["punto"]["lon"]
    caso = Caso(
        id=impacto["id"],
        tipo="impacto",
        pais=None,
        lat=lat,
        lon=lon,
        radio_km=float(lugar.get("radio_km") or 0.0),
        inicio=_segundos(impacto.get("fecha")),
    )
    if impacto["sentido"] == "UA_RU":
        # Los drones de Ucrania salen del territorio que controla, dentro de sus fronteras
        # reconocidas: la distancia a ellas es una cota inferior de lo que volaron.
        distancia = geo.distancia_a_pais_km("UA", lat, lon)
        caso.origenes = [Origen("territorio_ucrania", max(0.0, distancia - caso.radio_km))]
    elif ataque:
        zonas = [
            z for nombre in ataque.get("zonas_lanzamiento", []) for z in catalogo.zonas_de(nombre)
        ]
        caso.origenes = reglas.origenes_de_zonas(caso, list({z.id: z for z in zonas}.values()))
    if ataque:
        caso.lanzados = ataque.get("lanzados", {})
        caso.textos = [
            k
            for k, v in caso.lanzados.items()
            if v not in (None, "desconocido") and k in {"shahed_geran", "gerbera_senuelos"}
        ]
        caso.textos = [
            {"shahed_geran": "Shahed Geran", "gerbera_senuelos": "Gerbera"}[t] for t in caso.textos
        ]
    if condiciones_ataque:
        cercano = _lugar_cercano(condiciones_ataque.get("impacto") or [], lat, lon, 150.0)
        if cercano:
            caso.condiciones = {"lugar": cercano}
    return caso


# --- Combinación -------------------------------------------------------------------


def combinar(catalogo: Catalogo, evidencias: Iterable[Evidencia]) -> dict[str, Any]:
    por_clase: dict[str, list[Evidencia]] = defaultdict(list)
    for e in evidencias:
        por_clase[e.clase].append(e)
    compatibles: list[dict[str, Any]] = []
    descartadas: list[dict[str, Any]] = []
    indeterminadas: list[dict[str, Any]] = []
    conflictos: list[dict[str, Any]] = []
    for clase in catalogo.clases:
        lista = por_clase.get(clase, [])
        descartes = [e for e in lista if e.efecto == reglas.DESCARTA]
        a_favor = [e for e in lista if e.efecto == reglas.A_FAVOR]
        fisicas = [e for e in lista if e.regla in reglas.FISICAS]
        condiciones = [e.documento() for e in lista if e.efecto == reglas.CONDICION]
        indicios = [e.documento() for e in lista if e.efecto in {reglas.A_FAVOR, reglas.EN_CONTRA}]
        anotaciones = [e.documento() for e in lista if e.efecto == reglas.ANOTACION]
        if descartes and a_favor:
            conflicto = {
                "clase": clase,
                "descartan": [e.documento() for e in descartes],
                "apoyan": [e.documento() for e in a_favor],
            }
            conflictos.append(conflicto)
            indeterminadas.append({"clase": clase, "motivo": "conflicto"})
        elif descartes:
            descartadas.append({"clase": clase, "por": [e.documento() for e in descartes]})
        elif fisicas:
            entrada: dict[str, Any] = {"clase": clase}
            if condiciones:
                entrada["condiciones"] = condiciones
            if indicios:
                entrada["indicios"] = indicios
            if anotaciones:
                entrada["anotaciones"] = anotaciones
            entrada["reglas"] = sorted({e.regla for e in fisicas})
            compatibles.append(entrada)
        else:
            entrada = {"clase": clase, "motivo": "sin_datos"}
            if indicios:
                entrada["indicios"] = indicios
            if anotaciones:
                entrada["anotaciones"] = anotaciones
            indeterminadas.append(entrada)
    if descartadas and not compatibles and not conflictos:
        # Ninguna clase encaja: las pruebas se contradicen entre sí.
        conflictos.append(
            {
                "clase": None,
                "motivo": "ninguna_clase_compatible",
                "descartan": [d for x in descartadas for d in x["por"]],
            }
        )
        indeterminadas += [{"clase": x["clase"], "motivo": "conflicto"} for x in descartadas]
        descartadas = []
    return {
        "compatibles": compatibles,
        "descartadas": descartadas,
        "indeterminadas": sorted(indeterminadas, key=lambda x: str(x["clase"])),
        "conflictos": conflictos,
    }


def _base(catalogo: Catalogo) -> dict[str, Any]:
    return {
        "origen": "deducido",
        "metodo": "regla",
        "version_motor": VERSION,
        "version_catalogo": catalogo.version,
        "version_zonas": catalogo.version_zonas,
        "reglas": [{"nombre": n, "version": v} for n, v in reglas.REGLAS],
    }


def huella(*partes: Any) -> str:
    texto = json.dumps(partes, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_caso(catalogo: Catalogo, caso: Caso, extra: Any = None) -> str:
    return huella(
        VERSION,
        catalogo.version,
        catalogo.version_zonas,
        catalogo.version_fuentes,
        reglas.REGLAS,
        asdict(caso),
        extra,
    )


# --- Evaluación --------------------------------------------------------------------


def _viento_medio(caso: Caso) -> tuple[float, float] | None:
    lista = viento.lecturas((caso.condiciones or {}).get("lugar"))
    return viento.medio(viento.en_banda(lista, 0.0, 150.0))


def evaluar_incidente(
    catalogo: Catalogo,
    caso: Caso,
    sitios: list[Sitio],
    horizonte_de: Callable[[float, float], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    evidencias: list[Evidencia] = []
    r1, conclusiones, exterior = reglas.r1_distancia_europa(catalogo, caso)
    evidencias += r1
    evidencias += reglas.r2_meteorologia(catalogo, caso)
    evidencias += reglas.r3_autonomia(catalogo, caso)
    evidencias += reglas.r4_velocidad(catalogo, caso)
    evidencias += reglas.r5_radar(catalogo, caso)
    simultaneos = reglas.r6_simultaneidad(catalogo, caso, sitios)
    evidencias += simultaneos
    evidencias += reglas.r7_descripcion(catalogo, caso)
    evidencias += reglas.r8_gnss(catalogo, caso)
    evidencias += reglas.r9_altura(catalogo, caso)
    resultado = {**_base(catalogo), **combinar(catalogo, evidencias)}
    if simultaneos:
        otros = sorted({x["otro"] for e in simultaneos for x in e.datos["sitios"]})
        conclusiones.append(
            {
                "regla": reglas.R6[0],
                "version": reglas.R6[1],
                "conclusion": "varios_equipos_para_algunas_clases",
                "datos": {"sitios": otros},
            }
        )
    resultado["conclusiones"] = conclusiones
    if exterior is not None:
        resultado["exterior"] = exterior
    if caso.gnss is not None:
        resultado["gnss"] = caso.gnss
    # Zona de despegue de cada clase compatible, con el viento medido en su lugar.
    medio = _viento_medio(caso)
    if caso.con_punto and caso.pais and caso.lat is not None and caso.lon is not None:
        zonas: list[dict[str, Any]] = []
        for entrada in resultado["compatibles"]:
            zona = zona_despegue.calcular(
                catalogo, entrada["clase"], caso.pais, caso.lat, caso.lon, medio or (0.0, 0.0)
            )
            if zona is None:
                continue
            documento = zona.documento() if isinstance(zona, zona_despegue.Zona) else zona
            documento["viento_medido"] = medio is not None
            zonas.append(documento)
        if zonas:
            resultado["zona_despegue"] = {
                "regla": zona_despegue.VERSION[0],
                "version": zona_despegue.VERSION[1],
                "clases": zonas,
            }
        # Deriva en los cruces a países de la OTAN de drones que entran desde fuera.
        if caso.pais in deriva.OTAN and caso.entrada_exterior and CLASE_DERIVA in catalogo.clases:
            cruce = deriva.evaluar(
                catalogo, CLASE_DERIVA, caso.lat, caso.lon, (caso.condiciones or {}).get("lugar")
            )
            # Con solo el día, el viento de cada hora del día: decide si todas dan lo mismo.
            if (
                cruce is not None
                and cruce.resultado == deriva.INDETERMINADO
                and "viento_ms" not in cruce.datos
                and caso.lugares_horas
            ):
                cruce = (
                    deriva.evaluar_horas(
                        catalogo, CLASE_DERIVA, caso.lat, caso.lon, caso.lugares_horas
                    )
                    or cruce
                )
            if cruce is not None:
                resultado["deriva"] = cruce.documento()
        # Dirección de entrada: la que declara una autoridad o la deducida de la zona de despegue.
        sentido: dict[str, Any] | None = None
        if caso.entrada_desde is not None:
            sentido = direccion.declarada(
                caso.lat,
                caso.lon,
                caso.entrada_desde["pais"],
                caso.entrada_desde["origen"],
                caso.entrada_desde["fuente"],
                caso.entrada_desde["frase"],
            )
        if sentido is None and zonas:
            sentido = direccion.deducida(catalogo, caso.lat, caso.lon, zonas)
        if sentido is not None:
            resultado["direccion_entrada"] = sentido
        if horizonte_de is not None:
            calculado = horizonte_de(caso.lat, caso.lon)
            if calculado is not None:
                resultado["horizonte_radar"] = calculado
    return resultado


def evaluar_impacto(catalogo: Catalogo, caso: Caso) -> dict[str, Any]:
    evidencias: list[Evidencia] = []
    evidencias += reglas.r1_distancia_guerra(catalogo, caso)
    evidencias += reglas.r2_meteorologia(catalogo, caso)
    evidencias += reglas.r7_descripcion(catalogo, caso)
    resultado = {**_base(catalogo), **combinar(catalogo, evidencias)}
    if caso.origenes:
        resultado["origenes"] = [
            {"zona": o.nombre, "distancia_km": round(o.distancia_km, 1)}
            for o in sorted(caso.origenes, key=lambda o: o.distancia_km)
        ]
    return resultado


def evaluar_ataque(
    catalogo: Catalogo, ataque: dict[str, Any], de_impactos: list[dict[str, Any]]
) -> dict[str, Any]:
    """Un ataque reúne drones de varias clases: una clase es compatible si llega a alguno de sus
    impactos con lugar y descartada si no llega a ninguno. `alcance_exigido_km` es la distancia
    al impacto más lejano: algún dron del ataque tuvo que recorrerla."""
    resultado = _base(catalogo)
    if not de_impactos:
        resultado.update(
            {
                "compatibles": [],
                "descartadas": [],
                "conflictos": [],
                "indeterminadas": [
                    {"clase": c, "motivo": "sin_impactos_con_lugar"} for c in catalogo.clases
                ],
            }
        )
    else:
        compatibles, descartadas, indeterminadas = [], [], []
        for clase in catalogo.clases:
            estados = []
            for d in de_impactos:
                if any(x["clase"] == clase for x in d.get("compatibles", [])):
                    estados.append(COMPATIBLE)
                elif any(x["clase"] == clase for x in d.get("descartadas", [])):
                    estados.append(DESCARTADA)
                else:
                    estados.append(INDETERMINADA)
            if COMPATIBLE in estados:
                compatibles.append({"clase": clase, "impactos": estados.count(COMPATIBLE)})
            elif estados and all(e == DESCARTADA for e in estados):
                descartadas.append(
                    {
                        "clase": clase,
                        "por": [
                            {
                                "regla": reglas.R1[0],
                                "version": reglas.R1[1],
                                "efecto": reglas.DESCARTA,
                                "motivo": "no llega a ninguno de los impactos del ataque",
                                "datos": {"impactos": len(estados)},
                            }
                        ],
                    }
                )
            else:
                indeterminadas.append({"clase": clase, "motivo": "sin_datos"})
        resultado.update(
            {
                "compatibles": compatibles,
                "descartadas": descartadas,
                "indeterminadas": indeterminadas,
                "conflictos": [],
            }
        )
        distancias = [
            min(o["distancia_km"] for o in d["origenes"]) for d in de_impactos if d.get("origenes")
        ]
        if distancias:
            resultado["alcance_exigido_km"] = max(distancias)
    cruces = ataque.get("cruces") or []
    if cruces:
        resultado["deriva"] = {
            "regla": deriva.VERSION[0],
            "version": deriva.VERSION[1],
            "resultado": deriva.INDETERMINADO,
            "motivo": "el parte da el país del cruce, no el punto de caída",
            "datos": {"paises": sorted({c["pais"] for c in cruces})},
        }
    return resultado


def sitios_de(casos: Iterable[Caso]) -> list[Sitio]:
    """Los incidentes con punto y hora (al menos con precisión de hora) para la simultaneidad."""
    resultado = []
    for caso in casos:
        if not caso.con_punto or caso.inicio is None or caso.precision not in PRECISIONES_HORA:
            continue
        assert caso.lat is not None and caso.lon is not None
        fin = caso.fin if caso.fin is not None else caso.inicio + DURACION_HORA.total_seconds()
        resultado.append(Sitio(caso.id, caso.lat, caso.lon, caso.radio_km, caso.inicio, fin))
    return resultado
