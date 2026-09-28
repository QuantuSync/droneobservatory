"""Incidentes europeos a partir de candidatos y fichas validadas; fusión y episodios.

Reglas del diseño:
- Fusión: mismo objetivo o puntos a menos de la suma de radios más 10 km; con
  precisión de hora, inicios a menos de 6 horas; con precisión de día, el
  mismo día o el siguiente; más de 12 horas sin actividad es otro incidente.
  Una fusión dudosa (el incidente encaja con dos) no se hace. Toda fusión es
  reversible: el absorbido queda en la base con `fusionado_en` y la tabla de
  fusiones anota qué fuentes aportó; el historial guarda cada cambio.
- Episodio: varios objetivos distintos del mismo país en una misma noche.
- Estado: las noticias notifican; confirmar corresponde a una autoridad.
- presencia_dron: la que da la ficha, independiente del estado.
"""

import copy
import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso.credibilidad import Declaracion, Fiabilidad, Postura, credibilidad
from proceso.estados import nuevo_estado
from proceso.noticias import Lugar
from proceso.validacion_ficha import Validada, leer_fecha

MAX_PALABRAS_FRASE = 25
DECIMALES = 5
MARGEN_FUSION_KM = 10.0
INICIOS_HORA = timedelta(hours=6)
SIN_ACTIVIDAD = timedelta(hours=12)
RADIO_TIERRA_KM = 6371.0
# La noche de un episodio: de las 16:00 a las 06:00 UTC (17:00 a 07:00 en Europa central
# en invierno, 18:00 a 08:00 en verano), cuando se producen casi todos los avistamientos.
HORA_INICIO_NOCHE = 16
HORA_FIN_NOCHE = 6
MEDIODIA = 12
PRECISIONES_HORA = frozenset({"minuto", "hora"})
CATEGORIA_LUGAR = {
    "aeropuerto": "aeropuerto", "base": "base_militar", "nuclear": "energia",
    "energia": "energia", "subestacion": "energia", "presa": "presa", "puerto": "puerto",
    "estadio": "estadio",
}  # fmt: skip
FIABILIDAD_NOTICIAS = "C"
LONGITUD_OACI = 4
# «Varios objetivos»: dos o más.
MIN_OBJETIVOS_EPISODIO = 2


def _instante(momento: datetime, precision: str) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


def _leer_instante(instante: Documento) -> datetime:
    return datetime.strptime(instante["valor"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def _frase(texto: str) -> str:
    return " ".join(texto.split()[:MAX_PALABRAS_FRASE])


def id_fuente(url: str) -> str:
    return "gdelt-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def huella(urls: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(urls)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Objetivo:
    """El sitio del incidente: del nomenclátor, del vocabulario o nuevo de la ficha."""

    id: str
    categoria: str
    nombre: str
    pais: str
    lat: float
    lon: float
    radio_km: float
    oaci: str | None = None

    @classmethod
    def de_lugar(cls, lugar: Lugar) -> "Objetivo":
        oaci = lugar.id if lugar.tipo == "aeropuerto" and len(lugar.id) == LONGITUD_OACI else None
        return cls(
            id=lugar.id,
            # Helipuertos, localidades y lugares del GKG: «otra».
            categoria=CATEGORIA_LUGAR.get(lugar.tipo, "otra"),
            nombre=lugar.nombre,
            pais=lugar.pais,
            lat=lugar.lat,
            lon=lugar.lon,
            radio_km=lugar.radio_km,
            oaci=oaci,
        )


def credibilidad_noticias(n: int) -> int:
    """Varias noticias de fiabilidad C sin contradicción: 3 por la regla."""
    declaraciones = [
        Declaracion(f"nota-{i}", Fiabilidad(FIABILIDAD_NOTICIAS), False, Postura.RESPALDA)
        for i in range(n)
    ]
    return int(credibilidad(declaraciones))


def fuentes_incidente(
    articulos: list[Documento], enviadas: list[str], ficha: Validada
) -> list[Documento]:
    """Una fuente por artículo con idioma conocido; las enviadas llevan sus campos y frase."""
    por_fuente: dict[str, list[str]] = defaultdict(list)
    frases: dict[str, str] = {}
    for nombre, campo in ficha.campos.items():
        url = enviadas[campo["fuente"] - 1]
        por_fuente[url].append(nombre)
        frases.setdefault(url, campo["frase"])
    utiles = [a for a in articulos if a.get("idioma")]
    nivel = credibilidad_noticias(len(utiles))
    resultado = []
    for articulo in sorted(utiles, key=lambda a: (a["fecha"], a["url"])):
        url = articulo["url"]
        fuente: Documento = {
            "id": id_fuente(url),
            "enlace": url,
            "medio": articulo["medio"],
            "fecha": _instante(datetime.fromisoformat(articulo["fecha"]), "aproximada"),
            "idioma": articulo["idioma"],
            "fiabilidad": FIABILIDAD_NOTICIAS,
            "credibilidad": nivel,
            "frase_origen": _frase(frases.get(url) or str(articulo["titular"])),
            "replicas": articulo.get("replicas", 0),
            "es_autoridad": False,
            "interna_fuera_de_ucrania": False,
            "publica": True,
        }
        if por_fuente.get(url):
            fuente["campos_respaldados"] = sorted(por_fuente[url])
        resultado.append(fuente)
    return resultado


def _rango(valor: Any) -> Documento | str:
    return {"min": valor["min"], "max": valor["max"]} if isinstance(valor, dict) else "desconocido"


def _hay_interrupcion(documento: Documento) -> bool:
    consecuencias = documento.get("consecuencias", {})
    cierre = consecuencias.get("cierre", {}).get("valor") == "si"
    vuelos = any(
        isinstance(consecuencias.get(c), dict) and consecuencias[c]["min"] > 0
        for c in ("vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados")
    )
    return (cierre and documento["objetivo"]["categoria"] == "aeropuerto") or vuelos


def construir(
    id_: str,
    objetivo: Objetivo,
    candidato: Documento,
    articulos: list[Documento],
    enviadas: list[str],
    ficha: Validada,
    ahora: datetime,
    version: str,
    modelos_validos: frozenset[str],
) -> Documento:
    """Documento del incidente a partir del candidato y la ficha ya validada."""
    fuentes = fuentes_incidente(articulos, enviadas, ficha)
    primera = fuentes[0]
    inicio_ficha = leer_fecha(ficha.valor("inicio") or "")
    if inicio_ficha is not None:
        precision = ficha.valor("inicio_precision") or "dia"
        if "T" not in ficha.valor("inicio"):
            precision = "dia"
        inicio = _instante(inicio_ficha, precision)
    else:
        inicio = _instante(datetime.fromisoformat(candidato["inicio"]), "dia")
    tiempo: Documento = {"inicio": inicio}
    fin_ficha = leer_fecha(ficha.valor("fin") or "")
    if fin_ficha is not None and "T" in ficha.valor("fin"):
        tiempo["fin"] = _instante(fin_ficha, "minuto")
        tiempo["duracion_min"] = int((fin_ficha - _leer_instante(inicio)).total_seconds()) // 60
    lugar: Documento = {
        "punto": {"lat": round(objetivo.lat, DECIMALES), "lon": round(objetivo.lon, DECIMALES)},
        "radio_km": objetivo.radio_km,
        "pais": objetivo.pais,
    }
    if ficha.valor("localidad"):
        lugar["localidad"] = ficha.valor("localidad")
    datos_objetivo: Documento = {"categoria": objetivo.categoria, "nombre": objetivo.nombre}
    if objetivo.oaci and objetivo.categoria == "aeropuerto":
        datos_objetivo["oaci"] = objetivo.oaci
    drones: Documento = {"numero": _rango(ficha.valor("drones"))}
    if ficha.valor("modelo_dron") in modelos_validos:
        drones["modelo"] = ficha.valor("modelo_dron")
    consecuencias: Documento = {"cierre": {"valor": ficha.valor("cierre") or "desconocido"}}
    if ficha.valor("cierre_minutos"):
        consecuencias["cierre"]["minutos"] = _rango(ficha.valor("cierre_minutos"))
    for campo in ("vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados"):
        if ficha.valor(campo):
            consecuencias[campo] = _rango(ficha.valor(campo))
    documento: Documento = {
        "id": id_,
        "tipo": "sobrevuelo",
        "estado": nuevo_estado(primera["fecha"], primera["id"]),
        "titulo": {
            "es": ficha.titulo_es or f"Drones en {objetivo.nombre}",
            "en": ficha.titulo_en or f"Drones at {objetivo.nombre}",
        },
        "presencia_dron": ficha.valor("presencia_dron") or "no_confirmada",
        "tiempo": tiempo,
        "lugar": lugar,
        "objetivo": datos_objetivo,
        "drones": drones,
        "consecuencias": consecuencias,
        "fuentes": fuentes,
        "afirmaciones": [
            {
                "campo": nombre,
                "valor": campo["valor"],
                "fuente_id": id_fuente(enviadas[campo["fuente"] - 1]),
                "confianza_extraccion": float(campo["confianza"]),
            }
            for nombre, campo in sorted(ficha.campos.items())
            if any(f["id"] == id_fuente(enviadas[campo["fuente"] - 1]) for f in fuentes)
        ],
        "control": {
            "alta": _instante(ahora, "minuto"),
            "ultima_actualizacion": _instante(ahora, "minuto"),
            "version_extractor": version,
            "huella_fuentes": huella([f["enlace"] for f in fuentes]),
        },
    }
    medidas = ficha.valor("medidas")
    if medidas:
        documento["respuesta"] = {"medidas": sorted(set(medidas))}
    origen = ficha.valor("origen_demostrado")
    if origen:
        documento["origen_demostrado_por"] = sorted(set(origen))
    # El tipo sigue las reglas del esquema, no solo lo que diga la ficha.
    if _hay_interrupcion(documento):
        documento["tipo"] = "interrupcion_aeroportuaria"
    elif ficha.valor("tipo") == "incursion" and origen:
        documento["tipo"] = "incursion"
    return documento


# --- Fusión -------------------------------------------------------------------------


def _distancia_km(a: Documento, b: Documento) -> float:
    pa, pb = a["lugar"]["punto"], b["lugar"]["punto"]
    f1, f2 = math.radians(pa["lat"]), math.radians(pb["lat"])
    df, dl = f2 - f1, math.radians(pb["lon"] - pa["lon"])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def mismo_sitio(a: Documento, b: Documento) -> bool:
    if a["lugar"]["pais"] != b["lugar"]["pais"]:
        return False
    oa, ob = a.get("objetivo", {}), b.get("objetivo", {})
    if oa.get("nombre") and oa.get("nombre") == ob.get("nombre"):
        return True
    radios = float(a["lugar"]["radio_km"]) + float(b["lugar"]["radio_km"])
    return _distancia_km(a, b) < radios + MARGEN_FUSION_KM


def ultima_actividad(documento: Documento) -> datetime:
    momentos = [_leer_instante(documento["tiempo"]["inicio"])]
    if "fin" in documento["tiempo"]:
        momentos.append(_leer_instante(documento["tiempo"]["fin"]))
    momentos += [_leer_instante(f["fecha"]) for f in documento["fuentes"]]
    return max(momentos)


def misma_ventana(a: Documento, b: Documento) -> bool:
    """`a` empezó antes o a la vez que `b`."""
    inicio_a, inicio_b = a["tiempo"]["inicio"], b["tiempo"]["inicio"]
    ta, tb = _leer_instante(inicio_a), _leer_instante(inicio_b)
    if inicio_b["precision"] in PRECISIONES_HORA and tb - ultima_actividad(a) > SIN_ACTIVIDAD:
        return False
    if inicio_a["precision"] in PRECISIONES_HORA and inicio_b["precision"] in PRECISIONES_HORA:
        return abs(tb - ta) < INICIOS_HORA
    return tb.date() in {ta.date(), ta.date() + timedelta(days=1)}


def encajan(a: Documento, b: Documento) -> bool:
    primero, segundo = sorted((a, b), key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]))
    return mismo_sitio(a, b) and misma_ventana(primero, segundo)


def absorber(
    destino: Documento, absorbido: Documento, ahora: datetime
) -> tuple[Documento, list[str]]:
    """El destino con las fuentes y afirmaciones del absorbido; y las fuentes aportadas."""
    resultado = copy.deepcopy(destino)
    ids = {f["id"] for f in resultado["fuentes"]}
    aportadas = [f for f in absorbido["fuentes"] if f["id"] not in ids]
    resultado["fuentes"] = sorted(
        resultado["fuentes"] + copy.deepcopy(aportadas),
        key=lambda f: (f["fecha"]["valor"], f["id"]),
    )
    nivel = credibilidad_noticias(len(resultado["fuentes"]))
    for fuente in resultado["fuentes"]:
        fuente["credibilidad"] = nivel
    aportadas_ids = {f["id"] for f in aportadas}
    resultado["afirmaciones"] = resultado.get("afirmaciones", []) + [
        a for a in absorbido.get("afirmaciones", []) if a["fuente_id"] in aportadas_ids
    ]
    # Lo que al destino le faltaba y el absorbido sabe.
    if "fin" not in resultado["tiempo"] and "fin" in absorbido["tiempo"]:
        fin = absorbido["tiempo"]["fin"]
        if fin["valor"] >= resultado["tiempo"]["inicio"]["valor"]:
            resultado["tiempo"]["fin"] = fin
            inicio = _leer_instante(resultado["tiempo"]["inicio"])
            resultado["tiempo"]["duracion_min"] = (
                int((_leer_instante(fin) - inicio).total_seconds()) // 60
            )
    for campo in ("respuesta", "origen_demostrado_por"):
        if campo not in resultado and campo in absorbido:
            resultado[campo] = copy.deepcopy(absorbido[campo])
    if resultado.get("presencia_dron") == "no_confirmada" and absorbido.get("presencia_dron"):
        resultado["presencia_dron"] = absorbido["presencia_dron"]
    resultado["control"]["huella_fuentes"] = huella([f["enlace"] for f in resultado["fuentes"]])
    resultado["control"]["ultima_actualizacion"] = _instante(ahora, "minuto")
    return resultado, sorted(aportadas_ids)


def fusionar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Funde los incidentes que encajan con uno solo anterior. Devuelve cuántas fusiones hace."""
    activos = sorted(
        (i for i in almacen.incidentes() if "fusionado_en" not in i),
        key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]),
    )
    vivos = {i["id"]: i for i in activos}
    hechas = 0
    for incidente in activos:
        if incidente["id"] not in vivos:
            continue
        anteriores = [
            otro
            for otro in vivos.values()
            if otro["id"] != incidente["id"]
            and (otro["tiempo"]["inicio"]["valor"], otro["id"])
            < (incidente["tiempo"]["inicio"]["valor"], incidente["id"])
            and encajan(otro, incidente)
        ]
        # Dudosa si encaja con dos: no se hace.
        if len(anteriores) != 1:
            continue
        destino = anteriores[0]
        nuevo, aportadas = absorber(destino, incidente, ahora)
        fundido = {**copy.deepcopy(incidente), "fusionado_en": destino["id"]}
        almacen.guardar_incidente(nuevo, ahora, modelos)
        almacen.guardar_incidente(fundido, ahora, modelos)
        almacen.registrar_fusion(
            _instante(ahora, "minuto")["valor"], incidente["id"], destino["id"],
            "mismo sitio y misma ventana", aportadas,
        )  # fmt: skip
        vivos[destino["id"]] = nuevo
        del vivos[incidente["id"]]
        hechas += 1
    return hechas


def revertir(almacen: Almacen, absorbido_id: str, ahora: datetime, modelos: frozenset[str]) -> None:
    """Deshace la fusión: el absorbido vuelve a publicarse y el destino pierde lo aportado."""
    fusion = next(
        f
        for f in reversed(almacen.fusiones())
        if f["absorbido"] == absorbido_id and not f["revertida"]
    )
    absorbido = almacen.incidente(absorbido_id)
    destino = almacen.incidente(fusion["destino"])
    if absorbido is None or destino is None:
        raise KeyError(absorbido_id)
    aportadas = set(fusion["fuentes"])
    destino["fuentes"] = [f for f in destino["fuentes"] if f["id"] not in aportadas]
    destino["afirmaciones"] = [
        a for a in destino.get("afirmaciones", []) if a["fuente_id"] not in aportadas
    ]
    nivel = credibilidad_noticias(len(destino["fuentes"]))
    for fuente in destino["fuentes"]:
        fuente["credibilidad"] = nivel
    destino["control"]["huella_fuentes"] = huella([f["enlace"] for f in destino["fuentes"]])
    destino["control"]["ultima_actualizacion"] = _instante(ahora, "minuto")
    absorbido.pop("fusionado_en")
    almacen.guardar_incidente(destino, ahora, modelos)
    almacen.guardar_incidente(absorbido, ahora, modelos)
    almacen.revertir_fusion(absorbido_id)


# --- Episodios ----------------------------------------------------------------------


def noche(documento: Documento) -> str | None:
    """Fecha de la tarde de la noche del incidente, o None si no fue de noche o no se sabe."""
    inicio = documento["tiempo"]["inicio"]
    if inicio["precision"] not in PRECISIONES_HORA:
        return None
    momento = _leer_instante(inicio)
    if HORA_FIN_NOCHE <= momento.hour < HORA_INICIO_NOCHE:
        return None
    return (momento - timedelta(hours=MEDIODIA)).date().isoformat()


def agrupar_episodios(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Varios objetivos distintos del mismo país en una noche forman un episodio."""
    grupos: dict[tuple[str, str], list[Documento]] = defaultdict(list)
    for incidente in almacen.incidentes():
        clave = noche(incidente)
        if "fusionado_en" not in incidente and clave is not None:
            grupos[(incidente["lugar"]["pais"], clave)].append(incidente)
    cambios = 0
    for (_, fecha), miembros in sorted(grupos.items()):
        objetivos = {m.get("objetivo", {}).get("nombre") for m in miembros}
        if len(objetivos) < MIN_OBJETIVOS_EPISODIO:
            continue
        existentes = sorted({m["episodio"] for m in miembros if "episodio" in m})
        id_ = existentes[0] if existentes else almacen.siguiente_id_episodio(int(fecha[:4]))
        almacen.guardar_episodio(
            {"id": id_, "noche": fecha, "incidentes": sorted(m["id"] for m in miembros)}, ahora
        )
        for miembro in miembros:
            if miembro.get("episodio") != id_:
                almacen.guardar_incidente({**miembro, "episodio": id_}, ahora, modelos)
                cambios += 1
    return cambios
