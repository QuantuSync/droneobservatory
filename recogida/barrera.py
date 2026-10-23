"""La barrera de titulares en la recogida horaria: que nada quede retenido sin salida.

La barrera (proceso/cita_titular.py, exportacion/geojson.publicables) no publica un incidente
cuyas citas no respaldan su titular. Este paso, justo antes de publicar, hace tres cosas:

1. **Respaldo por el titular del artículo.** Si la cita no nombra el lugar ni el país, pero sí el
   titular de uno de sus propios artículos tal como está guardado en la base (tabla `articulos`),
   ese titular se guarda como cita del incidente (una fuente más del mismo artículo, con el
   prefijo `titular-`) y el incidente se publica con la frase que lo respalda.
2. **Hora de retención.** Lo que sigue retenido queda anotado con la hora en que se vio retenido
   por primera vez (cursor `barrera_titulares` de la base).
3. **Resolución a las 6 horas**, sin esperar a ninguna revisión a mano:
   a) si algún texto de sus fuentes (citas o titulares de sus artículos) nombra el país o una de
      sus regiones, se publica a nivel de país, sin punto (la web lo dibuja con el marcador de
      lugar aproximado), sin el nombre de la instalación y con un titular que no nombra el lugar
      concreto;
   b) si ninguno nombra ni el país, se retira como no verificable, con el motivo. El cursor guarda
      cada resolución: es el registro interno de los descartes.

Todo es idempotente: una resolución se vuelve a aplicar si una extracción nueva rehace el
incidente y sigue sin respaldo; si la extracción nueva lo respalda, se publica tal cual. El estado
para la vigilancia (retenidos con su hora, resoluciones de los últimos 7 días y la última vez que
cambió incidentes.geojson) va a un fichero aparte con identificadores, en los secretos del
servidor (recogida/vigilancia.py lo lee y solo publica recuentos).
"""

import copy
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from exportacion import geojson
from proceso import cita_titular, decidir, incidentes
from proceso.presencia import TABLA_MOTIVOS

registro = logging.getLogger(__name__)

CURSOR = "barrera_titulares"
ESPERA = timedelta(hours=6)
CONSERVAR_RESOLUCIONES = timedelta(days=7)
PREFIJO_TITULAR = "titular-"
PAIS, DESCARTADO = "pais", "descartado"
FICHERO_MAPA = "incidentes.geojson"
AVISOS = Path(__file__).resolve().parent.parent / "configuracion" / "avisos.json"
MOTIVO_TITULAR = (
    "titular del artículo fuente guardado como cita: nombra el lugar o el país del titular "
    "(recogida/barrera.py)"
)
MOTIVO_PAIS = (
    "retenido 6 horas por la barrera de titulares: ningún texto de sus fuentes nombra el lugar "
    "concreto, pero sí el país; se publica a nivel de país con ubicación aproximada "
    "(recogida/barrera.py)"
)
MOTIVO_DESCARTE = (
    "No verificable: retenido 6 horas por la barrera de titulares y ningún texto de sus fuentes "
    "(cita ni titular del artículo) nombra el país ni el lugar del suceso."
)
MOTIVO_DESCARTE_EN = (
    "Not verifiable: held for 6 hours by the headline check and no text from its sources (quote "
    "or article headline) names the country or the place of the event."
)
# Titular a nivel de país según el tipo del incidente: sin lugar concreto.
TITULO_PAIS = {
    "incursion": ("{dron} en el espacio aéreo de {es}", "{drone} in {en} airspace"),
    "interrupcion_aeroportuaria": (
        "{dron} interrumpen la actividad de un aeropuerto de {es}",
        "{drone} disrupt operations at an airport in {en}",
    ),
    "sobrevuelo": ("{dron} avistado en {es}", "{drone} sighted in {en}"),
}
PLURAL_ES = {"Drones avistado ": "Drones avistados "}


@dataclass
class Revision:
    con_titular: list[str] = field(default_factory=list)
    retenidos: dict[str, str] = field(default_factory=dict)
    a_pais: list[str] = field(default_factory=list)
    descartados: list[str] = field(default_factory=list)
    sin_guardar: list[str] = field(default_factory=list)
    resoluciones: list[Documento] = field(default_factory=list)
    ultima_alta_con_punto: str | None = None

    def texto(self) -> str:
        return (
            f"con titular {len(self.con_titular)}, retenidos {len(self.retenidos)}, a nivel de "
            f"país {self.a_pais}, descartados {self.descartados}, sin guardar {self.sin_guardar}"
        )


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)


def _instante(ahora: datetime) -> Documento:
    return {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


@cache
def nombres_de_paises(ruta: Path = AVISOS) -> dict[str, tuple[str, str]]:
    """El nombre en español y en inglés de cada país cubierto (configuracion/avisos.json)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {codigo: (p["es"], p["en"]) for codigo, p in datos["paises"].items()}


# --- Respaldo por el titular del artículo ------------------------------------------------------
def fuente_de_titular(incidente: Documento, enlace: str, titular: str) -> Documento:
    """La fuente que lleva como cita el titular de uno de sus artículos: el mismo artículo, el
    mismo medio y la misma fiabilidad; sin datos que respalde aparte del titular."""
    mismas = [f for f in incidente["fuentes"] if f.get("enlace") == enlace]
    original = next((f for f in mismas if "-declaracion" not in f["id"]), mismas[0])
    clave = hashlib.sha256(f"{enlace}\n{titular}".encode()).hexdigest()[:16]
    fuente: Documento = {
        "id": PREFIJO_TITULAR + clave,
        "enlace": enlace,
        "medio": original["medio"],
        "fecha": copy.deepcopy(original["fecha"]),
        "idioma": original["idioma"],
        "fiabilidad": original["fiabilidad"],
        "credibilidad": original.get("credibilidad", 3),
        "frase_origen": incidentes._frase(titular),
        "replicas": 0,
        "campos_respaldados": [],
        "es_autoridad": False,
        "interna_fuera_de_ucrania": False,
        "publica": True,
    }
    return fuente


def con_titular(incidente: Documento, enlace: str, titular: str) -> Documento:
    """El incidente con el titular de su artículo como cita (si aún no la tiene)."""
    fuente = fuente_de_titular(incidente, enlace, titular)
    if any(f["id"] == fuente["id"] for f in incidente["fuentes"]):
        return incidente
    resultado = copy.deepcopy(incidente)
    resultado["fuentes"] = [*resultado["fuentes"], fuente]
    return resultado


def _titulares(almacen: Almacen, incidente: Documento) -> dict[str, str]:
    """Enlace -> titular guardado en la base de los artículos fuente del incidente."""
    enlaces = [f["enlace"] for f in incidente.get("fuentes", []) if f.get("enlace")]
    return {a["url"]: str(a["titular"]) for a in almacen.articulos_de(enlaces)}


def _limpios(incidente: Documento, titulares_: dict[str, str]) -> dict[str, str]:
    """Los titulares sin el nombre del medio de su fuente."""
    medios = {f["enlace"]: f.get("medio", "") for f in incidente.get("fuentes", [])}
    return {e: cita_titular.titular_limpio(t, medios.get(e, "")) for e, t in titulares_.items()}


# --- Resolución a las 6 horas -------------------------------------------------------------------
def titulo_de_pais(incidente: Documento) -> dict[str, str]:
    """Un titular que no afirma más que el país: el hecho según el tipo, sin el lugar."""
    es, en = nombres_de_paises()[incidente["lugar"]["pais"]]
    plantilla_es, plantilla_en = TITULO_PAIS.get(
        incidente.get("tipo", ""), TITULO_PAIS["sobrevuelo"]
    )
    numero = (incidente.get("drones") or {}).get("numero")
    varios = isinstance(numero, dict) and int(numero.get("min", 1)) >= 2
    if incidente.get("tipo") == "interrupcion_aeroportuaria" or varios:
        titulo_es = plantilla_es.format(dron="Drones", es=es)
        titulo_en = plantilla_en.format(drone="Drones", en=en)
        for singular, plural in PLURAL_ES.items():
            titulo_es = titulo_es.replace(singular, plural)
    else:
        titulo_es = plantilla_es.format(dron="Dron", es=es)
        titulo_en = plantilla_en.format(drone="Drone", en=en)
    return {"es": titulo_es, "en": titulo_en}


def a_nivel_de_pais(incidente: Documento) -> Documento:
    """El incidente situado solo en su país: sin punto, sin el nombre del lugar ni de la
    instalación, y con el titular a nivel de país (coherente con la presencia y la atribución)."""
    resultado = copy.deepcopy(incidente)
    resultado["lugar"] = {"pais": incidente["lugar"]["pais"], "nivel": "pais"}
    objetivo = resultado.get("objetivo")
    if isinstance(objetivo, dict):
        resultado["objetivo"] = {k: v for k, v in objetivo.items() if k in ("categoria", "uso")}
    resultado["titulo"] = titulo_de_pais(resultado)
    # Coherente con la presencia y la atribución: lo decide proceso/decidir.py.
    resultado["titulo"] = decidir.decidir_titulo(resultado)
    return resultado


def descartado(incidente: Documento, ahora: datetime) -> Documento:
    resultado = {k: v for k, v in incidente.items() if k != "episodio"}
    resultado["retirado"] = {
        "fecha": _instante(ahora),
        "motivo": MOTIVO_DESCARTE,
        "motivo_en": MOTIVO_DESCARTE_EN,
    }
    return resultado


def _guardar(
    almacen: Almacen,
    antes: Documento,
    despues: Documento,
    ahora: datetime,
    modelos: frozenset[str],
    motivo: str,
    hecho: Revision,
) -> bool:
    if despues == antes:
        return True
    control = {**despues["control"], "ultima_actualizacion": _instante(ahora)}
    despues = {**despues, "control": control}
    try:
        almacen.guardar_incidente(despues, ahora, modelos)
    except DocumentoInvalido as error:
        registro.warning("barrera: %s sin guardar: %s", antes["id"], str(error)[:300])
        hecho.sin_guardar.append(antes["id"])
        return False
    campos = ("titulo", "lugar", "objetivo", "fuentes", "retirado")
    cambios = {c: antes.get(c) for c in campos if antes.get(c) != despues.get(c)}
    if cambios:
        nuevos = {c: despues.get(c) for c in cambios}
        almacen.anotar_motivo(TABLA_MOTIVOS, antes["id"], cambios, nuevos, motivo)
    return True


def revisar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Revision:
    """Respaldo por el titular, hora de retención y resolución de lo retenido 6 horas."""
    hecho = Revision()
    cursor: Documento = almacen.cursor(CURSOR) or {}
    anteriores: dict[str, str] = dict(cursor.get("retenidos", {}))
    resueltos: dict[str, Documento] = dict(cursor.get("resueltos", {}))
    for incidente in almacen.incidentes():
        if not incidentes.activo(incidente):
            continue
        id_ = str(incidente["id"])
        alta = incidente["control"]["alta"]["valor"]
        if "punto" in incidente["lugar"] and (
            hecho.ultima_alta_con_punto is None or alta > hecho.ultima_alta_con_punto
        ):
            hecho.ultima_alta_con_punto = alta
        publico = geojson.vista_publica(incidente)
        if publico is None or cita_titular.publicable(publico):
            continue
        titulares_ = _titulares(almacen, publico)
        apoyo = cita_titular.titular_que_respalda(publico, titulares_)
        if apoyo is not None:
            nuevo = con_titular(incidente, *apoyo)
            if _guardar(almacen, incidente, nuevo, ahora, modelos, MOTIVO_TITULAR, hecho):
                hecho.con_titular.append(id_)
                registro.info("%s respaldado por el titular de %s", id_, apoyo[0])
            continue
        desde = anteriores.get(id_, _iso(ahora))
        ya = resueltos.get(id_)
        if ya is None and ahora - _momento(desde) < ESPERA:
            hecho.retenidos[id_] = desde
            continue
        limpios = _limpios(publico, titulares_)
        otros = list(limpios.values())
        pais_conocido = incidente["lugar"].get("pais") in nombres_de_paises()
        if pais_conocido and cita_titular.respalda_el_pais(publico, otros):
            nuevo, resultado, motivo = a_nivel_de_pais(incidente), PAIS, MOTIVO_PAIS
            # La cita que respalda el país, si es el titular de un artículo, queda guardada.
            if not cita_titular.respalda(geojson.vista_publica(nuevo) or nuevo):
                for enlace, limpio in limpios.items():
                    if cita_titular.nombra_el_pais([limpio], nuevo["lugar"]["pais"]):
                        nuevo = con_titular(nuevo, enlace, limpio)
                        break
        else:
            nuevo, resultado, motivo = descartado(incidente, ahora), DESCARTADO, MOTIVO_DESCARTE
        if not _guardar(almacen, incidente, nuevo, ahora, modelos, motivo, hecho):
            hecho.retenidos[id_] = desde
            continue
        (hecho.a_pais if resultado == PAIS else hecho.descartados).append(id_)
        if ya is None or ya["resultado"] != resultado:
            resueltos[id_] = {"resultado": resultado, "fecha": _iso(ahora), "desde": desde,
                              "motivo": motivo}  # fmt: skip
            hecho.resoluciones.append({"id": id_, "fecha": _iso(ahora), "resultado": resultado})
            registro.warning("barrera: %s resuelto (%s) tras 6 horas retenido", id_, resultado)
    recientes = [
        r for r in [*cursor.get("resoluciones", []), *hecho.resoluciones]
        if ahora - _momento(r["fecha"]) <= CONSERVAR_RESOLUCIONES
    ]  # fmt: skip
    hecho.resoluciones = recientes
    almacen.guardar_cursor(
        CURSOR,
        {"retenidos": dict(sorted(hecho.retenidos.items())), "resueltos": resueltos,
         "resoluciones": recientes},
    )  # fmt: skip
    registro.info("barrera de titulares: %s", hecho.texto())
    return hecho


def paso_horario(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Revision | None:
    """La revisión de la barrera; un fallo no cambia el código de salida (y la vigilancia ve
    que el estado no se actualiza)."""
    try:
        return revisar(almacen, ahora, modelos)
    except Exception as error:
        registro.warning("barrera de titulares sin revisar: %s", str(error)[:300])
        return None


# --- Estado para la vigilancia -----------------------------------------------------------------
def escribir_estado(
    ruta: Path,
    revision: Revision | None,
    cambiados: list[Path],
    directorio: Path,
    ahora: datetime,
) -> None:
    """barrera.json: retenidos con su hora, resoluciones recientes y última vez que cambió el
    mapa publicado, con la última alta de un incidente con punto."""
    anterior: dict[str, Any] = {}
    if ruta.exists():
        try:
            anterior = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            anterior = {}
    mapa = directorio / FICHERO_MAPA
    if any(Path(c).name == FICHERO_MAPA for c in cambiados):
        cambio = _iso(ahora)
    elif anterior.get("mapa_cambiado"):
        cambio = anterior["mapa_cambiado"]
    elif mapa.exists():
        cambio = _iso(datetime.fromtimestamp(mapa.stat().st_mtime, UTC))
    else:
        cambio = _iso(ahora)
    estado: dict[str, Any] = {
        "generado": _iso(ahora),
        "mapa_cambiado": cambio,
        "ultima_alta_con_punto": None,
        "retenidos": {},
        "resoluciones": [],
    }
    if revision is not None:
        estado["ultima_alta_con_punto"] = revision.ultima_alta_con_punto
        estado["retenidos"] = revision.retenidos
        estado["resoluciones"] = revision.resoluciones
    else:
        estado["revision_fallida"] = True
        for clave in ("ultima_alta_con_punto", "retenidos", "resoluciones"):
            estado[clave] = anterior.get(clave, estado[clave])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)
