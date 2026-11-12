"""Medios públicos nacionales que se leen directamente, además de GDELT.

La noche del 10 al 11 de noviembre de 2026 hubo alertas aéreas en media Lituania, con los
aeropuertos de Vilna y Kaunas cerrados y cazas de la OTAN en el aire, y el observatorio no publicó
nada: GDELT trajo dos notas de la prensa británica que hablaban de «Letonia y Lituania», y las
páginas de las autoridades lituanas (el Centro Nacional de Gestión de Crisis, las Fuerzas Armadas,
los Aeropuertos de Lituania) no dejan entrar al servidor. LRT, la radiotelevisión pública, lo
contó desde las 23.00 con las citas de esas autoridades.

Cada medio de `configuracion/medios_publicos.json` se lee como una página de noticias de las
fuentes oficiales (`recogida/paginas_oficiales.py`: los enlaces de la lista, y de ellos los que
hablan de drones o llevan un título de alerta), con su robots.txt y la identificación del
observatorio. Una nota que habla de drones y cuenta un suceso (`oficiales.suceso`) entra una sola
vez como artículo de su lugar en un candidato, igual que un artículo dirigido: el extractor lo
lleva delante y la ficha pasa por el control y el filtro de entrada de siempre. **No es una fuente
oficial**: nunca se enlaza a una ficha como autoridad ni confirma nada; lo que una autoridad diga
dentro de la nota lo saca el extractor como declaración citada.

Cada nota se abre una vez: la que entra y la que se descarta quedan en el cursor
`medios_publicos` con su motivo. Un medio que no responde se apunta en el registro y se pasa al
siguiente; no es un fallo de la recogida. Desde cuándo falla cada uno queda en el cursor
`medios_publicos_fallos` (como el de las fuentes oficiales, recogida/oficiales.py) y de ahí pasa
a la vigilancia (`fuentes.json`, recogida/vigilancia.py): donde se lee un medio público es porque
no hay otra fuente del país, y si deja de leerse el país se queda sin ninguna."""

import json
import logging
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso.noticias import filtro, titular_normalizado
from recogida import oficiales, paginas_oficiales
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida, NoEncontrado
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger(__name__)

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "medios_publicos.json"
CURSOR = "medios_publicos"
# Los medios que vienen fallando: {medio: {fallos_seguidos, primer_fallo, ultimo_fallo, motivo}}.
CURSOR_FALLOS = "medios_publicos_fallos"
MOTIVO = (
    "nota de un medio público leído directamente: entra como artículo de su lugar para que el "
    "extractor y el filtro de entrada decidan si es un suceso nuevo o el de una ficha existente"
)
# Dos medios, con su lista y como mucho MAX_NOTAS notas nuevas cada uno, a 3 s por petición.
TOPE_S = 90.0
MAX_NOTAS = 4
# Lo anterior ya lo trajeron las noticias; las listas guardan notas de varios días.
DIAS_ENTRADA = 3
# Las notas descartadas se olvidan pasado este tiempo: ya no están en la lista.
DIAS_CURSOR = 30


@cache
def medios(ruta: Path = RUTA) -> tuple[Documento, ...]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return tuple(datos["medios"])


def candidatos(almacen: Almacen) -> set[str]:
    """Los candidatos donde entraron notas de los medios públicos (el extractor los lleva
    delante)."""
    cursor = almacen.cursor(CURSOR) or {}
    return {c for entrada in cursor.values() if isinstance(entrada, dict)
            for c in entrada.get("candidatos", [])}  # fmt: skip


def interesa(nota: oficiales.Nota, ahora: datetime) -> str | None:
    """Por qué la nota no entra, o None si entra: habla de drones, cuenta un suceso y es
    reciente."""
    if not filtro().dron.search(f"{nota.titulo} {nota.texto}"):
        return "no habla de drones"
    if not oficiales.suceso(nota):
        return "no cuenta un suceso"
    fecha = nota.fecha if nota.fecha.tzinfo else nota.fecha.replace(tzinfo=UTC)
    if fecha < ahora - timedelta(days=DIAS_ENTRADA):
        return f"de hace más de {DIAS_ENTRADA} días"
    if fecha > ahora + timedelta(hours=1):
        return "fecha futura"
    return None


def entrar(almacen: Almacen, nota: oficiales.Nota) -> list[str]:
    """La nota, como artículo de su lugar, en un candidato. Devuelve los candidatos tocados."""
    from recogida.calidad import situar_en_candidatos

    sitio = oficiales.lugar_de_candidato(nota)
    if sitio is None:
        return []
    fecha = nota.fecha if nota.fecha.tzinfo else nota.fecha.replace(tzinfo=UTC)
    documento: Documento = {
        "url": nota.enlace, "medio": nota.fuente["medio"],
        "fecha": fecha.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "idioma": nota.fuente["idioma"], "pais": nota.fuente["pais"], "titular": nota.titulo,
        "titular_normalizado": titular_normalizado(nota.titulo), "temas": [], "lugares": [sitio],
    }  # fmt: skip
    if not almacen.guardar_articulo(documento):
        existente = almacen.articulos_de([nota.enlace])
        if existente:
            documento = {**existente[0], "lugares": [sitio]}
    return situar_en_candidatos(almacen, [(documento, [sitio])], MOTIVO)


def leer(
    almacen: Almacen, descargador: Descargador, medio: Documento, ahora: datetime,
    cursor: dict[str, Any],
) -> int:  # fmt: skip
    """Lee la lista de un medio y hace entrar sus notas nuevas de interés. Devuelve cuántas
    entran."""
    lector = oficiales.robots(descargador, medio["url"])
    if not lector.can_fetch(AGENTE_EODI, medio["url"]):
        raise NoSeLee("su robots.txt no deja leerlo")
    lista = descargador.texto(medio["url"], lambda t: "<" in t)
    nuevas = [
        (direccion, titulo)
        for direccion, titulo in paginas_oficiales.enlaces(lista, medio)
        if direccion not in cursor
        and paginas_oficiales.interesa(titulo, medio, filtro().dron)
        and lector.can_fetch(AGENTE_EODI, direccion)
    ][:MAX_NOTAS]
    entraron = 0
    for direccion, titulo in nuevas:
        marca: dict[str, Any] = {"visto": ahora.strftime("%Y-%m-%dT%H:%MZ"), "medio": medio["id"]}
        try:
            pagina = descargador.texto(direccion, lambda t: "<" in t)
        except NoEncontrado:
            cursor[direccion] = {**marca, "descartada": "no existe"}
            continue
        except (DescargaFallida, ValueError):
            # Un corte: se vuelve a probar en la recogida siguiente.
            continue
        leido = paginas_oficiales.contenido(pagina, medio, titulo)
        if leido is None:
            cursor[direccion] = {**marca, "descartada": "sin fecha"}
            continue
        fecha, precision, texto = leido
        id_ = paginas_oficiales.identificador(medio, direccion)
        nota = oficiales.Nota(medio, id_, titulo, direccion, fecha, texto, precision)
        motivo = interesa(nota, ahora)
        if motivo is not None:
            cursor[direccion] = {**marca, "descartada": motivo}
            continue
        tocados = entrar(almacen, nota)
        if not tocados:
            cursor[direccion] = {**marca, "descartada": "sin lugar"}
            continue
        cursor[direccion] = {**marca, "candidatos": tocados}
        entraron += 1
        registro.info("medios públicos: %s entra en %s", direccion, ", ".join(tocados))
    return entraron


def fallos(almacen: Almacen) -> dict[str, dict[str, Any]]:
    """El estado de cada medio que viene fallando (vacío si todos se leen)."""
    guardado = almacen.cursor(CURSOR_FALLOS) or {}
    return {k: dict(v) for k, v in guardado.items() if isinstance(v, dict)}


def paso_horario(
    almacen: Almacen, ahora: datetime, descargador: Descargador | None = None,
    plazo: Plazo | None = None, avisar: oficiales.Avisar | None = None,
) -> int:  # fmt: skip
    """Lee los medios públicos. Devuelve cuántas notas entraron. `avisar` manda al responsable
    el aviso de un medio que lleva `oficiales.AVISO_SIN_LEER` sin leerse (no se pasa en los
    ensayos ni en las pruebas)."""
    descargador = descargador or Descargador(agente=AGENTE_EODI)
    # Como las fuentes oficiales: una petición colgada no agota el tope del paso.
    descargador = descargador.con_limites(
        min(descargador.reintentos, oficiales.REINTENTOS_PETICION),
        min(descargador.limite_s, oficiales.LIMITE_PETICION_S),
    )
    descargador.plazo = plazo or Plazo(TOPE_S)
    ids = {m["id"] for m in medios()}
    estados = {k: v for k, v in fallos(almacen).items() if k in ids}
    estados_antes = json.dumps(estados, sort_keys=True)
    limite = (ahora - timedelta(days=DIAS_CURSOR)).strftime("%Y-%m-%dT%H:%MZ")
    cursor: dict[str, Any] = {
        url: e for url, e in (almacen.cursor(CURSOR) or {}).items()
        if isinstance(e, dict) and (e.get("candidatos") or str(e.get("visto", "")) >= limite)
    }  # fmt: skip
    antes = json.dumps(cursor, sort_keys=True)
    entraron = 0
    pendientes = [m["id"] for m in medios()]
    try:
        for medio in medios():
            motivo: str | None = None
            try:
                entraron += leer(almacen, descargador, medio, ahora, cursor)
            except (DescargaFallida, ValueError, NoSeLee) as error:
                motivo = str(error)[:200]
            pendientes.remove(medio["id"])
            _anotar(estados, medio["id"], motivo, ahora)
    except TiempoAgotado as error:
        registro.warning("medios públicos: %s; lo que falta, en la recogida siguiente", error)
        # El que se estaba leyendo y los que quedaban no se han leído en esta recogida.
        detalle = f" (último intento: {descargador.ultimo_fallo[:160]})" * bool(
            descargador.ultimo_fallo
        )
        for id_ in pendientes:
            _anotar(estados, id_, f"cortado al agotar el tope del paso{detalle}", ahora)
    finally:
        descargador.plazo = None
        if json.dumps(cursor, sort_keys=True) != antes:
            almacen.guardar_cursor(CURSOR, cursor)
        nombres = {str(m["id"]): f"{m['medio']} ({m['pais']})" for m in medios()}
        oficiales.avisar_sin_leer(estados, ahora, avisar, nombres, "El medio público")
        if json.dumps(estados, sort_keys=True) != estados_antes:
            almacen.guardar_cursor(CURSOR_FALLOS, estados)
    return entraron


class NoSeLee(RuntimeError):
    """El medio no se puede leer por algo que no es una descarga fallida (su robots.txt)."""


def _anotar(
    estados: dict[str, dict[str, Any]], id_: str, motivo: str | None, ahora: datetime
) -> None:
    """El resultado de un medio en esta recogida: leído (deja de tener estado) o con su fallo."""
    if motivo is None:
        estados.pop(id_, None)
        return
    oficiales.anotar_fallo(estados.setdefault(id_, {}), motivo, ahora)
    registro.warning(
        "medios públicos: %s no se pudo leer: %s (%d recogidas seguidas)", id_, motivo,
        estados[id_]["fallos_seguidos"],
    )  # fmt: skip
