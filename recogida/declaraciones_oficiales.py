"""Declaraciones de autoridades leídas en su página oficial, y titulares de acuerdo con el estado.

Las declaraciones que atribuyen un incidente casi nunca llegan por las noticias con las palabras
de la autoridad: la prensa cuenta que el Gobierno «acusa» o «señala», y eso no basta
(proceso/atribucion.py). Las de configuracion/declaraciones_oficiales.json se han buscado en la
web de la autoridad y se ha guardado una copia fechada de su texto
(configuracion/declaraciones_oficiales/). En cada recogida horaria, este lector:

- comprueba que la frase está literalmente en la copia (proceso/declaraciones.validas, como la
  frase que da el extractor tiene que estar en la noticia enviada); si no está, no la aplica;
- hace con ella una fuente del incidente: oficial, de fiabilidad A, con el enlace a la página,
  su fecha, su idioma y la frase (si solo la cita una noticia, «declaración oficial citada», de
  fiabilidad B, con el enlace a la noticia);
- la pasa por las reglas de siempre (proceso/declaraciones.aplicar_fuentes): confirma, atribuye
  solo si la regla de atribución lo sostiene, y lo que la autoridad investiga va a la ficha como
  investigación en curso;
- guarda el incidente con la validación de siempre: lo que no valida no entra.

Una fuente que el incidente ya tiene no se vuelve a aplicar: después de la primera recogida no
cambia nada. Si una reconstrucción rehiciera el incidente sin ella, la siguiente recogida la
vuelve a aplicar.

Además, todos los titulares quedan de acuerdo con el estado (atribucion.titulo_segun_atribucion):
el de un incidente que no está atribuido no dice la nacionalidad del dron ni señala a un autor.
"""

import copy
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import atribucion, declaraciones, incidentes
from proceso.credibilidad import Credibilidad
from proceso.presencia import TABLA_MOTIVOS

registro = logging.getLogger(__name__)

CONFIGURACION = Path(__file__).resolve().parent.parent / "configuracion"
RUTA = CONFIGURACION / "declaraciones_oficiales.json"
COPIAS = CONFIGURACION / "declaraciones_oficiales"
PREFIJO = "oficial-"
# Como en las fuentes de las declaraciones que encuentra el extractor: la exportación reconoce
# por esta marca una declaración citada por un medio (exportacion/procedencia.py).
MARCA_CITADA = "-declaracion-1"
MOTIVO = (
    "declaración de la autoridad leída en su página oficial (recogida/declaraciones_oficiales.py)"
)
MOTIVO_TITULAR = (
    "titular sin la nacionalidad del dron ni el autor: el incidente no está atribuido "
    "(proceso/atribucion.py)"
)
_CAMPOS = ("estado", "atribucion", "investigacion", "presencia_dron", "titulo", "tipo")


@dataclass
class Resumen:
    aplicadas: list[str] = field(default_factory=list)
    atribuidos: list[str] = field(default_factory=list)
    sin_frase: list[str] = field(default_factory=list)
    sin_incidente: list[str] = field(default_factory=list)
    sin_guardar: list[str] = field(default_factory=list)


@cache
def cargar(ruta: Path = RUTA) -> tuple[Documento, ...]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(datos["declaraciones"])


@cache
def copia(nombre: str, carpeta: Path = COPIAS) -> Documento:
    """La copia fechada de la página: su enlace, su editor, sus fechas y su texto."""
    datos: Documento = json.loads((carpeta / f"{nombre}.json").read_text(encoding="utf-8"))
    return datos


def texto(nombre: str, carpeta: Path = COPIAS) -> str:
    return "\n".join(copia(nombre, carpeta)["texto"])


def literal(entrada: Documento, carpeta: Path = COPIAS) -> bool:
    """Si la frase está, palabra por palabra, en la copia de la página."""
    declaracion = {**entrada, "fuente": 1}
    validas = declaraciones.validas([declaracion], [texto(entrada["copia"], carpeta)])
    return bool(validas) and validas[0]["frase"] == entrada["frase"]


def fuente(entrada: Documento, carpeta: Path = COPIAS) -> Documento:
    """La fuente del incidente: la página oficial, o la noticia que cita a la autoridad."""
    citada = entrada.get("citada_en")
    resultado: Documento = {
        "id": PREFIJO + entrada["id"] + (MARCA_CITADA if citada else ""),
        "enlace": copia(entrada["copia"], carpeta)["enlace"],
        "medio": (
            f"{entrada['autoridad']} (declaración oficial citada en {citada})"
            if citada else entrada["autoridad"]
        ),
        "fecha": {"valor": entrada["fecha"], "precision": entrada["precision"]},
        "idioma": entrada["idioma"],
        "fiabilidad": declaraciones.FIABILIDAD if citada else "A",
        "credibilidad": int(Credibilidad.CONFIRMADO),
        "frase_origen": entrada["frase"],
        "replicas": 0,
        "campos_respaldados": ["estado", "presencia_dron"],
        "es_autoridad": True,
        "interna_fuera_de_ucrania": False,
        "publica": True,
        # La frase la comprueba el código en la copia de la página, sin extractor.
        "metodo": "parser",
    }  # fmt: skip
    return resultado


def declaracion(entrada: Documento) -> dict[str, Any]:
    """La declaración con los mismos campos que da el extractor (modelo/ficha.py)."""
    campos = (
        "autoridad", "pais", "categoria", "afirma", "autor", "autor_tipo", "autor_pais",
        "autor_situacion", "cita_literal", "frase",
    )  # fmt: skip
    return {c: entrada[c] for c in campos if c in entrada}


def vivo(almacen: Almacen, id_: str) -> Documento | None:
    """El incidente, o aquel en que está fundido; None si no existe o está retirado."""
    vistos: set[str] = set()
    documento = almacen.incidente(id_)
    while documento is not None and "fusionado_en" in documento and id_ not in vistos:
        vistos.add(id_)
        id_ = documento["fusionado_en"]
        documento = almacen.incidente(id_)
    if documento is None or not incidentes.activo(documento):
        return None
    return documento


def _instante(ahora: datetime) -> Documento:
    return {"valor": ahora.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": "minuto"}


def _anotar(almacen: Almacen, antes: Documento, despues: Documento, motivo: str) -> None:
    cambios = {c: antes.get(c) for c in _CAMPOS if antes.get(c) != despues.get(c)}
    if cambios:
        nuevos = {c: despues.get(c) for c in cambios}
        almacen.anotar_motivo(TABLA_MOTIVOS, despues["id"], cambios, nuevos, motivo)


def aplicar(
    almacen: Almacen,
    ahora: datetime,
    modelos: frozenset[str],
    entradas: tuple[Documento, ...] | None = None,
    carpeta: Path = COPIAS,
) -> Resumen:
    """Aplica cada declaración a su incidente, si aún no la tiene. Devuelve lo hecho."""
    resumen = Resumen()
    por_incidente: dict[str, list[tuple[dict[str, Any], Documento]]] = {}
    for entrada in cargar() if entradas is None else entradas:
        if not literal(entrada, carpeta):
            registro.warning("declaración %s: la frase no está en su copia", entrada["id"])
            resumen.sin_frase.append(entrada["id"])
            continue
        documento = vivo(almacen, entrada["incidente"])
        if documento is None:
            resumen.sin_incidente.append(entrada["id"])
            continue
        por_incidente.setdefault(documento["id"], []).append(
            (declaracion(entrada), fuente(entrada, carpeta))
        )
    for id_, pares in por_incidente.items():
        guardado = almacen.incidente(id_)
        assert guardado is not None
        nuevo = declaraciones.aplicar_fuentes(guardado, pares)
        if nuevo == guardado:
            continue
        nuevo = incidentes.aplicar_reglas(nuevo)
        nuevo["control"] = {
            **copy.deepcopy(nuevo["control"]),
            "ultima_actualizacion": _instante(ahora),
        }
        try:
            almacen.guardar_incidente(nuevo, ahora, modelos)
        except DocumentoInvalido as error:
            registro.warning("declaraciones oficiales sin guardar en %s: %s", id_, error)
            resumen.sin_guardar.append(id_)
            continue
        _anotar(almacen, guardado, nuevo, MOTIVO)
        resumen.aplicadas += [
            f["id"] for _, f in pares if f["id"] in {x["id"] for x in nuevo["fuentes"]}
        ]
        if nuevo["estado"]["actual"] == atribucion.ESTADO_ATRIBUIDO != guardado["estado"]["actual"]:
            resumen.atribuidos.append(id_)
    registro.info(
        "declaraciones oficiales: %d aplicadas; atribuidos: %s; frase que no está en la copia: "
        "%d; sin incidente: %d; sin guardar: %d",
        len(resumen.aplicadas), resumen.atribuidos or "ninguno", len(resumen.sin_frase),
        len(resumen.sin_incidente), len(resumen.sin_guardar),
    )  # fmt: skip
    return resumen


def titulares(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> tuple[int, list[str]]:
    """Deja cada titular de acuerdo con el estado de su incidente. Devuelve cuántos cambia y los
    incidentes que no se pudieron guardar."""
    cambiados, fallidos = 0, []
    for incidente in almacen.incidentes():
        if not incidentes.activo(incidente):
            continue
        titulo = atribucion.titulo_segun_atribucion(incidente)
        if titulo == incidente["titulo"]:
            continue
        documento = {
            **incidente, "titulo": titulo,
            "control": {**incidente["control"], "ultima_actualizacion": _instante(ahora)},
        }  # fmt: skip
        try:
            almacen.guardar_incidente(documento, ahora, modelos)
        except DocumentoInvalido:
            fallidos.append(incidente["id"])
            continue
        _anotar(almacen, incidente, documento, MOTIVO_TITULAR)
        cambiados += 1
    registro.info("titulares sin nacionalidad ni autor sin atribución: %d", cambiados)
    return cambiados, fallidos
