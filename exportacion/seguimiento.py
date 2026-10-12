"""Lo que el observatorio guarda fuera de la base y sirve a AEGIS, para la exportación semanal
(formato 1.9.0): el seguimiento en directo de la guerra sobre Ucrania, las rutas reconstruidas de
todas las noches, las interrupciones medidas de los aeropuertos y las comprobaciones de la
previsión, del tipo de dron y de la barrera de titulares.

- fuerza_aerea_seguimiento.jsonl: los mensajes de seguimiento de la Fuerza Aérea de Ucrania
  (t.me/kpszsu) de cada noche del archivo, con sus avisos (tipo, grupo, número, zona con su
  radio, rumbo y destino), leídos por código (proceso/rutas/mensajes.py). Lo que dice el mensaje
  es oficial; el punto y el radio de cada zona salen del nomenclátor (deducido).
- neptun_pistas.jsonl: las pistas archivadas de NEPTUN (neptun.in.ua) de los tipos de dron (uav,
  fpv, recon), punto a punto, con rumbo, velocidad, número, confianza, radio de incertidumbre y
  calidad de la posición tal como las da NEPTUN. Son estimaciones de un agregador de informes, no
  un radar; cada pista lleva la atribución que exigen sus condiciones.
- rutas_reconstruidas.jsonl: la reconstrucción de cada noche con los mensajes de la Fuerza Aérea
  (proceso/rutas/reconstruccion.py), también las que no se publican, con la precisión de cada
  tramo y el error medido contra NEPTUN (comprobacion.json). Deducido.
- cierres_medidos.jsonl: todas las interrupciones de aeropuertos medidas con el tráfico de
  adsb.lol (tabla anomalias_trafico), casadas o no con un incidente. Medido.
- prevision_validacion.json, tipo_dron_validacion.json y barrera_titulares.json: la previsión
  publicada con su comprobación y su registro puntuado (Rumanía, Moldavia y los demás países), la
  calibración del tipo de dron y el estado de la barrera de titulares con el titular y la cita que
  respaldan cada incidente.

Las alertas de alerts.in.ua no entran: sus condiciones piden no usar su API para infraestructura
crítica (docs/licencias_terceros.md) y AEGIS protege puertos.

Las carpetas se leen de donde las deja cada servicio del servidor (las mismas variables de
servidor/configuracion.sh); sin ellas, los ficheros salen vacíos.
"""

import gzip
import json
import os
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento

VARIABLE_PUBLICACION = "EODI_PUBLICACION_DATOS"
TIPOS_DRON_NEPTUN = ("uav", "fpv", "recon")
ENLACE_KPSZSU = "https://t.me/kpszsu/"
AVISO_NEPTUN = (
    "NEPTUN es un agregador de informes, no un sistema oficial de alerta ni un radar: sus "
    "posiciones son estimaciones que pueden ser inexactas o llegar tarde. Para la seguridad de "
    "las personas mandan las alertas oficiales."
)
INCERTIDUMBRE_RUTAS = (
    "Cada tramo une dos zonas de los mensajes; precision_km es el radio mayor de las dos. El "
    "error medido contra las pistas de NEPTUN está en validacion: la reconstrucción no mejora a "
    "la línea recta y por eso no se publica en la web."
)
ATRIBUCION_ALERTAS_EXCLUIDA = {
    "fuente": "alerts.in.ua",
    "motivo": "Sus condiciones («Не використовуйте API для критичної інфраструктури»: no usar la "
    "API para infraestructura crítica) no permiten llevar sus alertas a AEGIS, que protege "
    "infraestructura crítica. Se archivan solo en el servidor del observatorio.",
    "condiciones": "https://devs.alerts.in.ua/",
}


def datos_publicacion() -> Path:
    return Path(os.environ.get(VARIABLE_PUBLICACION) or Path.home() / "datos" / "publicacion")


def _noches(rutas: Path) -> Iterator[dict[str, Any]]:
    for ruta in sorted((rutas / "noches").glob("*.json.gz")):
        documento: dict[str, Any] = json.loads(gzip.decompress(ruta.read_bytes()))
        yield documento


# --- Fuerza Aérea de Ucrania -------------------------------------------------------------------


def fuerza_aerea(rutas: Path) -> list[Documento]:
    """Cada mensaje de seguimiento con sus avisos, de todas las noches estructuradas."""
    salida: list[Documento] = []
    for noche in _noches(rutas):
        version = str(noche.get("version_kpszsu", ""))
        for mensaje in noche.get("kpszsu", []):
            fuentes = [f"kpszsu:{mensaje['id']}"]
            salida.append({
                "id": mensaje["id"],
                "fecha": mensaje["fecha"],
                "noche": noche["noche"],
                "enlace": f"{ENLACE_KPSZSU}{mensaje['id']}",
                "avisos": mensaje["avisos"],
                "procedencia": {
                    "avisos": {"origen": "oficial", "metodo": "parser", "regla": version,
                               "fuentes": fuentes},
                    "zonas": {"origen": "deducido", "metodo": "regla", "regla": version,
                              "fuentes": fuentes,
                              "nota": "punto y radio de la zona que nombra el mensaje, del "
                                      "nomenclátor; el mensaje no da coordenadas"},
                },
            })  # fmt: skip
    return sorted(salida, key=lambda m: (m["fecha"], m["id"]))


# --- NEPTUN ------------------------------------------------------------------------------------


def _punto_neptun(amenaza: dict[str, Any]) -> dict[str, Any] | None:
    from proceso.rutas import neptun

    velocidad = amenaza.get("velocity")
    extra = {
        k: v
        for k, v in {
            "rumbo": amenaza.get("heading"),
            "kmh": velocidad.get("speedKmh") if isinstance(velocidad, dict) else None,
            "numero": amenaza.get("count"),
            "incertidumbre_km": amenaza.get("uncertaintyKm"),
            "confianza": amenaza.get("confidenceLevel"),
            "calidad_posicion": amenaza.get("positionQuality"),
            "confirmaciones": amenaza.get("sourceCount"),
            "region": amenaza.get("region") or None,
            "localidad": amenaza.get("locality") or None,
        }.items()
        if v is not None
    }
    return neptun._punto(amenaza.get("updatedAt"), amenaza.get("lat"), amenaza.get("lon"), extra)


def neptun_pistas(seguimiento: Path) -> list[Documento]:
    """Las pistas de dron de todo el archivo de NEPTUN, una por amenaza, con sus puntos en orden."""
    from proceso.rutas import neptun

    rutas = sorted((seguimiento / "neptun").glob("*/*/neptun-*.jsonl*"))
    puntos: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    datos: dict[str, dict[str, Any]] = {}
    for mensaje in neptun.mensajes(rutas):
        for amenaza in neptun._amenazas(mensaje):
            if amenaza.get("type") not in TIPOS_DRON_NEPTUN or not amenaza.get("id"):
                continue
            id_ = str(amenaza["id"])
            punto = _punto_neptun(amenaza)
            if punto is not None:
                puntos[id_][punto["t"]] = punto
            for paso in amenaza.get("trail") or []:
                if isinstance(paso, dict):
                    previo = neptun._punto(paso.get("t"), paso.get("lat"), paso.get("lon"), {})
                    if previo is not None and previo["t"] not in puntos[id_]:
                        puntos[id_][previo["t"]] = previo
            datos[id_] = {"id": id_, "tipo": amenaza["type"], "titulo": amenaza.get("title")}
    salida = []
    for id_, por_t in puntos.items():
        lista = [por_t[t] for t in sorted(por_t)]
        salida.append({
            **datos[id_],
            "puntos": lista,
            "procedencia": {
                "origen": "deducido", "metodo": "estimacion_neptun", "regla": neptun.VERSION,
                "fuentes": ["neptun.in.ua"], "estimacion": True, "radar": False,
                "nota": "posición estimada por NEPTUN a partir de informes; deducido por NEPTUN, "
                        "no por el observatorio",
            },
            "atribucion": dict(neptun.ATRIBUCION),
            "aviso": AVISO_NEPTUN,
        })  # fmt: skip
    return sorted(salida, key=lambda p: (p["puntos"][0]["t"], p["id"]))


# --- Rutas reconstruidas -----------------------------------------------------------------------


def _validacion(rutas: Path) -> Documento:
    ruta = rutas / "comprobacion.json"
    if not ruta.exists():
        return {"disponible": False}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    claves = ("pasa", "criterio", "mediana_reconstruccion_km", "mediana_recta_km",
              "mejor_en_cada_noche", "puntos", "calculado", "version")  # fmt: skip
    resumen: Documento = {"disponible": True, **{k: datos[k] for k in claves if k in datos}}
    resumen["noches"] = [
        {k: n[k] for k in n if k not in ("distancias", "distancias_recta")}
        for n in datos.get("noches", [])
    ]
    return resumen


def rutas_reconstruidas(rutas: Path, corte: datetime) -> list[Documento]:
    """La reconstrucción con la Fuerza Aérea de cada noche cerrada en `corte`, publicada o no."""
    from proceso.rutas import calculo, reconstruccion, recorridos
    from recogida.rutas import frontera_km

    ataques: dict[str, Any] = (
        json.loads((rutas / "ataques.json").read_text(encoding="utf-8"))
        if (rutas / "ataques.json").exists()
        else {}
    )
    publicadas = {p.stem for p in (rutas / "publicar" / "noches").glob("*.json")}
    validacion = _validacion(rutas)
    salida: list[Documento] = []
    for noche in _noches(rutas):
        if not calculo.cerrada(noche, corte):
            continue
        ataque = ataques.get(noche["noche"], {})
        tramos = calculo.unir_repetidos(
            reconstruccion.tramos_fuerza_aerea(noche, ataque.get("zonas", []), frontera_km)
        )
        if not tramos:
            continue
        lista, grupos = recorridos.recorridos(recorridos.trozos_fuerza_aerea(tramos))
        siguiente = max([0, *grupos]) + 1
        for i, g in enumerate(grupos):
            if g == 0:
                grupos[i], siguiente = siguiente, siguiente + 1
        salida.append({
            "noche": noche["noche"],
            "fuente": "fuerza_aerea",
            "publicada": noche["noche"] in publicadas,
            "ataques": ataque.get("ataques", []),
            "tramos": [calculo._publico(t, g, "fuerza_aerea")
                       for t, g in zip(tramos, grupos, strict=True)],
            "recorridos": [{k: v for k, v in r.items() if k not in ("franjas", "flechas")}
                           for r in lista],
            "grupos": calculo.estadisticas(tramos, grupos, "fuerza_aerea"),
            "incertidumbre": INCERTIDUMBRE_RUTAS,
            "procedencia": {
                "origen": "deducido", "metodo": "regla",
                "regla": f"{reconstruccion.VERSION}+{recorridos.VERSION}",
                "fuentes": sorted({f"kpszsu:{m}" for t in tramos for m in t.get("mensajes", [])}),
            },
        })  # fmt: skip
    por_noche = {n["noche"]: n for n in validacion.get("noches", [])}
    resumen = {k: v for k, v in validacion.items() if k != "noches"}
    return [
        {**r, "validacion": {**resumen, **({"noche": por_noche[r["noche"]]}
                                            if r["noche"] in por_noche else {})}}
        for r in salida
    ]  # fmt: skip


# --- Tráfico aéreo -----------------------------------------------------------------------------


def cierres_medidos(almacen: Almacen) -> list[Documento]:
    """Cada interrupción medida de un aeropuerto, con su regla y su fuente."""
    return [
        {
            "id": f"{a['oaci']}/{a['inicio']}",
            "anomalia": a,
            "procedencia": {"origen": "medido", "metodo": "regla",
                            "regla": f"{a['regla']['nombre']}-{a['regla']['version']}",
                            "fuentes": ["adsb.lol"]},
            "licencia": "ODbL 1.0 (adsb.lol)",
        }
        for a in almacen.anomalias()
    ]  # fmt: skip


# --- Comprobaciones ----------------------------------------------------------------------------


def prevision_validacion(publicacion: Path) -> Documento:
    """La previsión publicada (prevision.json): cada país con su comprobación y el registro de lo
    que se previó, puntuado con lo que pasó."""
    ruta = publicacion / "prevision.json"
    if not ruta.exists():
        return {"disponible": False, "documento": None, "procedencia": None}
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    return {
        "disponible": True,
        "documento": documento,
        "procedencia": {"origen": "deducido", "metodo": "regla",
                        "regla": str(documento.get("version", "")),
                        "fecha": str(documento.get("calculado", ""))},
    }  # fmt: skip


def tipo_dron_validacion(almacen: Almacen) -> Documento:
    cursor = almacen.cursor("tipo_dron")
    return {
        "disponible": cursor is not None,
        "comprobacion": cursor,
        "procedencia": {"origen": "deducido", "metodo": "regla", "regla": "tipo_dron"},
    }


def barrera_titulares(almacen: Almacen, incidentes: list[Documento]) -> Documento:
    """El estado de la barrera (retenidos, resueltos a país o retirados), por incidente si su
    cita respalda el titular (proceso/cita_titular.py) y el titular que lo respalda."""
    from proceso import cita_titular
    from proceso import incidentes as reglas

    justificados = cita_titular.justificados()
    veredictos = [
        {"incidente": i["id"], "respalda": cita_titular.respalda(i),
         "justificado_a_mano": i["id"] in justificados}
        for i in incidentes
        if reglas.activo(i)
    ]  # fmt: skip
    respaldos = [
        {
            "incidente": i["id"], "fuente_id": f["id"], "medio": f["medio"],
            "enlace": f["enlace"], "publica": bool(f["publica"]),
            **({"frase_origen": f["frase_origen"]} if "frase_origen" in f else {}),
        }
        for i in incidentes
        for f in i.get("fuentes", [])
        if str(f.get("id", "")).startswith("titular-")
    ]  # fmt: skip
    return {
        "estado": almacen.cursor("barrera_titulares") or {},
        "respaldos": sorted(respaldos, key=lambda r: (r["incidente"], r["fuente_id"])),
        "veredictos": sorted(veredictos, key=lambda v: v["incidente"]),
        "procedencia": {
            "veredictos": {"origen": "deducido", "metodo": "regla", "regla": "cita_titular"},
            "respaldos": {"origen": "prensa", "metodo": "transcripcion"},
            "estado": {"origen": "deducido", "metodo": "regla", "regla": "barrera_titulares"},
        },
    }
