"""La red de seguridad de la publicación (docs/cerrojo.md): una ficha que la auditoría marca en una
comprobación de protección (P, R, V, W o X: `proceso/protegido.AUDITORIA`) no sale con lo que
tiene ahora en la base, sino con su última versión buena, la última que se publicó sin marca.

- Sin versión buena, sale como en la publicación anterior (lo que había en el fichero).
- Si nunca se publicó, no sale, y queda apuntado.
- Nada de esto para la publicación: si la auditoría o la sustitución fallan, se publica lo de la
  base, como antes, y el fallo queda en el registro.

Las versiones buenas son las entradas publicadas (el «feature» del mapa o la entrada de los
incidentes sin punto, ya con sus citas), una por ficha, en `versiones_buenas.json`, en una carpeta
al lado de la publicación (`<publicación>_buena`), que no se sube. Lo que se sustituyó en cada
publicación, con la comprobación y la diferencia, queda en el cursor `publicacion_buena`: lo leen el
estado del control (control.json), la vigilancia, que abre la incidencia, y el resumen diario
(«Fichas publicadas en su versión anterior: N»)."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import coste

registro = logging.getLogger(__name__)

CURSOR = "publicacion_buena"
VARIABLE_DIRECTORIO = "EODI_PUBLICACION_BUENA"
FICHERO = "versiones_buenas.json"
# La clave de las entradas de cada fichero publicado.
LISTAS = {"incidentes.geojson": "features", "incidentes_sin_ubicacion.json": "incidentes"}
# Lo que dicen las diferencias: unos pocos campos y valores cortos (salud.json es público).
MAX_DIFERENCIAS = 6
MAX_VALOR = 80
DIAS = 8
BUENA, ANTERIOR, NINGUNA = "buena", "anterior", "ninguna"


def directorio(publicacion: Path) -> Path:
    """Al lado de la carpeta de la publicación, fuera de ella (no se sube)."""
    return Path(
        os.environ.get(VARIABLE_DIRECTORIO) or publicacion.parent / f"{publicacion.name}_buena"
    )


def marcadas(almacen: Almacen, ahora: datetime) -> dict[str, list[str]]:
    """{ficha: [comprobaciones]} de las fichas vigentes en P, R, V, W o X ahora, con los mismos
    datos que la auditoría del control (recogida/control_fichas.auditoria_del_dia). En V cuenta la
    ficha que queda publicada (la de destino)."""
    from proceso import auditoria_fichas, incidentes, protegido
    from recogida import revisados

    desde = (ahora - timedelta(hours=auditoria_fichas.HORAS_OSCILA)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resultado = auditoria_fichas.auditar(
        almacen.incidentes(),
        almacen.cambios_desde(desde),
        None,
        incidentes.distintos_del_experto(almacen) | revisados.pares_de_partes(almacen),
        incidentes.uniones_a_mano(almacen),
        almacen.fechas_extraccion(desde),
        protegido.permitidos(almacen.controles(protegido.PREFIJO_PERMITIDO)),
    )
    salida: dict[str, list[str]] = {}
    for comprobacion in protegido.AUDITORIA:
        for entrada in resultado.get(comprobacion, []):
            texto = str(entrada)
            id_ = texto.split("→")[-1] if "→" in texto else texto.split(" ")[0]
            if id_.startswith("EODI-") and comprobacion not in salida.get(id_, []):
                salida.setdefault(id_, []).append(comprobacion)
    return salida


def _id(entrada: Documento) -> str:
    return str(entrada.get("id") or (entrada.get("properties") or {}).get("id") or "")


def _entradas(documento: Documento | None, nombre: str) -> list[Documento]:
    lista = (documento or {}).get(LISTAS[nombre])
    return lista if isinstance(lista, list) else []


def _corto(valor: Any) -> str:
    texto = json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return texto if len(texto) <= MAX_VALOR else texto[: MAX_VALOR - 1] + "…"


def diferencias(publicada: Documento | None, actual: Documento | None) -> dict[str, list[str]]:
    """Los campos que cambian entre lo que se publica y lo que tiene ahora la base, con los dos
    valores recortados."""
    uno = {**(publicada or {}), **((publicada or {}).get("properties") or {})}
    otro = {**(actual or {}), **((actual or {}).get("properties") or {})}
    salida: dict[str, list[str]] = {}
    for campo in sorted(set(uno) | set(otro)):
        if campo in ("properties", "citas", "fuentes", "afirmaciones_publicas"):
            continue
        if uno.get(campo) != otro.get(campo):
            salida[campo] = [_corto(uno.get(campo)), _corto(otro.get(campo))]
        if len(salida) >= MAX_DIFERENCIAS:
            break
    return salida


def cargar(ruta: Path) -> dict[str, Documento]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _guardar(ruta: Path, datos: dict[str, Documento]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temporal, ruta)


def sustituir(
    generados: dict[str, Documento],
    anteriores: dict[str, Documento | None],
    marcas: dict[str, list[str]],
    buenas: dict[str, Documento],
) -> tuple[dict[str, Documento], dict[str, Documento], list[Documento]]:
    """Los ficheros con cada ficha marcada en su versión buena, o en la anterior, o fuera; las
    versiones buenas al día (las fichas publicadas sin marca, tal como salen) y lo sustituido.

    `generados` y `anteriores` van por nombre de fichero (los de `LISTAS`); `buenas`, por ficha:
    {"fichero", "entrada"}."""
    salida = {n: {**d, LISTAS[n]: list(_entradas(d, n))} for n, d in generados.items()}
    donde = {_id(e): n for n, d in salida.items() for e in _entradas(d, n)}
    previas = {
        _id(e): {"fichero": n, "entrada": e}
        for n, d in anteriores.items() if n in LISTAS
        for e in _entradas(d, n)
    }  # fmt: skip
    sustituidas: list[Documento] = []
    for id_ in sorted(set(marcas) & set(donde)):
        nombre = donde[id_]
        lista = salida[nombre][LISTAS[nombre]]
        actual = next(e for e in lista if _id(e) == id_)
        lista.remove(actual)
        origen, version = NINGUNA, None
        if id_ in buenas and buenas[id_].get("fichero") in salida:
            origen, version = BUENA, buenas[id_]
        elif id_ in previas and previas[id_]["fichero"] in salida:
            origen, version = ANTERIOR, previas[id_]
        if version is not None:
            otra = salida[str(version["fichero"])][LISTAS[str(version["fichero"])]]
            otra.append(version["entrada"])
            otra.sort(key=_id)
        sustituidas.append({
            "id": id_, "comprobaciones": marcas[id_], "origen": origen,
            "diferencias": diferencias(version["entrada"] if version else None, actual),
        })  # fmt: skip
    nuevas = dict(buenas)
    for nombre, documento in salida.items():
        for entrada in _entradas(documento, nombre):
            if (id_ := _id(entrada)) and id_ not in marcas:
                nuevas[id_] = {"fichero": nombre, "entrada": entrada}
    return salida, nuevas, sustituidas


def aplicar(
    almacen: Almacen,
    ahora: datetime,
    generados: dict[str, Documento],
    publicacion: Path,
    carpeta: Path | None = None,
) -> dict[str, Documento]:
    """`generados` con la red de seguridad, o tal cual si algo falla: nunca para la publicación.
    Apunta lo sustituido en el cursor y guarda las versiones buenas."""
    try:
        marcas = marcadas(almacen, ahora)
    except Exception as error:
        registro.warning("red de la publicación sin auditoría: %s", str(error)[:200])
        return generados
    try:
        ruta = (carpeta or directorio(publicacion)) / FICHERO
        anteriores: dict[str, Documento | None] = {}
        for nombre in generados:
            fichero = publicacion / nombre
            anteriores[nombre] = (
                json.loads(fichero.read_text(encoding="utf-8")) if fichero.exists() else None
            )
        salida, buenas, sustituidas = sustituir(generados, anteriores, marcas, cargar(ruta))
        _guardar(ruta, buenas)
        anotar(almacen, ahora, sustituidas)
    except Exception:
        registro.exception("red de la publicación sin aplicar: se publica lo de la base")
        return generados
    for s in sustituidas:
        registro.warning(
            "%s publicada en su versión %s (%s): %s", s["id"], s["origen"],
            ", ".join(s["comprobaciones"]), ", ".join(s["diferencias"]) or "sin diferencias",
        )  # fmt: skip
    return salida


def anotar(almacen: Almacen, ahora: datetime, sustituidas: list[Documento]) -> None:
    """El cursor: lo de la última publicación y, por día UTC, las fichas sustituidas."""
    anterior = almacen.cursor(CURSOR) or {}
    limite = coste.dia(ahora - timedelta(days=DIAS))
    dias = {d: v for d, v in (anterior.get("dias") or {}).items() if d >= limite}
    hoy = coste.dia(ahora)
    dias[hoy] = sorted(set(dias.get(hoy, [])) | {str(s["id"]) for s in sustituidas})
    almacen.guardar_cursor(CURSOR, {
        "fecha": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "sustituidas": sustituidas,
        "dias": dict(sorted(dias.items())),
    })  # fmt: skip
