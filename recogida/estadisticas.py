"""Estadísticas oficiales de drones: avistamientos, afectaciones y encuentros por periodo.

Dos lectores, registrados en recogida/detalle.py:

- **ukab_meses**: la tabla mensual oficial del Excel histórico de la UK Airprox Board (hoja
  «By Month» del «UA and Other Airprox Count»: Airprox con drones, globos, aeromodelos y
  objetos desconocidos por año y mes, con el total del año). Se lee con código: cada celda con
  número es una cifra, con su año y su mes como periodo. Una celda vacía no es un cero: no se
  guarda. Usa el Excel que deja el lector de la UKAB (recogida/airprox.py).
- **publicaciones**: las publicaciones de gestores de navegación aérea y autoridades de
  aviación con cifras de drones (configuracion/publicaciones_oficiales.json). Cada una se
  descarga una vez, se extrae su texto y se localizan sus pasajes sobre drones; las cifras las
  saca el extractor con su frase literal (proceso/extraccion_oficial.py). Lo que solo está en un
  gráfico no se lee.
"""

import html
import io
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from esquema import Documento
from proceso.pasajes import localizar
from recogida import airprox, detalle, oficiales, paginas_oficiales
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida

registro = logging.getLogger(__name__)

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
FIABILIDAD = "A"
CREDIBILIDAD = 2
HOJA_MESES = "By Month"
MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_FECHA_PDF = re.compile(r"D:(\d{4})(\d{2})(\d{2})")


def publicaciones(ruta: Path = DIRECTORIO / "publicaciones_oficiales.json") -> list[Documento]:
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return list(datos["publicaciones"])


# --- Tabla mensual de la UKAB ---------------------------------------------------------


def _ultimo_dia(anio: int, mes: int) -> str:
    siguiente = date(anio + (mes == 12), mes % 12 + 1, 1)
    return (siguiente - timedelta(days=1)).isoformat()


def cifras_meses(filas: list[list[Any]], corte: str) -> list[Documento]:
    """Cada celda con número de la tabla: un mes de un año, o el total del año. Ningún periodo
    pasa de `corte` (el día del Excel): el total del año en curso es hasta ese día."""
    if not filas:
        return []
    cabecera = [str(c).strip() if c is not None else "" for c in filas[0]]
    resultado = []
    for fila in filas[1:]:
        if not fila or not isinstance(fila[0], float) or not 2000 <= fila[0] <= 2100:
            continue
        anio = int(fila[0])
        for columna, valor in enumerate(fila[1:], 1):
            if not isinstance(valor, float) or columna >= len(cabecera):
                continue
            nombre = cabecera[columna]
            if nombre in MESES:
                mes = MESES.index(nombre) + 1
                inicio, fin = f"{anio}-{mes:02d}-01", _ultimo_dia(anio, mes)
            elif nombre == "Total":
                inicio, fin = f"{anio}-01-01", f"{anio}-12-31"
            else:
                continue
            fin = min(fin, corte)
            if inicio > fin:
                continue
            resultado.append({
                "metrica": "encuentros", "valor": {"min": int(valor), "max": int(valor)},
                "periodo_inicio": inicio, "periodo_fin": fin, "pais": "GB", "categoria": "",
                "instalacion": "",
                # La celda tal como está en la tabla: fila, columna y valor.
                "frase": f"{HOJA_MESES}: {anio} {nombre} {int(valor)}",
            })  # fmt: skip
    return resultado


def recolector_ukab_meses(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    """Las cifras de la hoja mensual del Excel histórico que dejó el lector de la UKAB."""
    datos = airprox.Datos(raiz / "airprox")
    if not datos.historico_ruta.exists():
        raise FileNotFoundError("falta el Excel histórico de la UKAB: se lee con el lector ukab")
    contenido = datos.historico_ruta.read_bytes()
    enlace = datos.indice().get("historico") or airprox.DRONES
    fecha = airprox.fecha_xlsx(contenido) or ahora.strftime("%Y-%m-%d")
    cifras = cifras_meses(airprox.filas_xlsx(contenido, HOJA_MESES), fecha)
    documento = {
        "id": f"{fuente['id']}:ua_other_by_month", "fuente_detalle": fuente["id"],
        "tipo": "estadistica", "autoridad": airprox.AUTORIDAD, "pais": "GB", "idioma": "en",
        "titulo": "UA and Other Airprox Count, By Month", "enlace": enlace, "fecha": fecha,
        "fiabilidad": FIABILIDAD, "credibilidad": CREDIBILIDAD,
    }  # fmt: skip
    _escribir_tabla(raiz, fuente["id"], [{"documento": documento, "cifras": cifras}])
    return len(cifras)


def _escribir_tabla(raiz: Path, fuente_id: str, tablas: list[Documento]) -> None:
    ruta = raiz / "estadisticas" / f"{fuente_id}.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(tablas, ensure_ascii=False, sort_keys=True, indent=1),
                    encoding="utf-8", newline="\n")  # fmt: skip


# --- Publicaciones ----------------------------------------------------------------------


def texto_html(pagina: str) -> str:
    """El texto de la página con un párrafo por bloque (líneas en blanco entre párrafos) y las
    celdas de cada fila de una tabla en la misma línea, separadas por dos espacios."""
    sin_ruido = re.sub(
        r"<(script|style|noscript|nav|footer|header)\b.*?</\1>", " ", pagina, flags=re.S | re.I
    )
    con_saltos = re.sub(
        r"</(p|div|li|tr|h\d|table|section|article)>|<br\s*/?>", "\n\n", sin_ruido, flags=re.I
    )
    con_celdas = re.sub(r"</t[dh]>", "  ", con_saltos, flags=re.I)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", con_celdas))
    return "\n".join(re.sub(r"[ \t]{3,}", "  ", linea).strip() for linea in texto.splitlines())


def _fecha_pdf(datos: bytes) -> str | None:
    metadatos: dict[str, Any] = dict(PdfReader(io.BytesIO(datos)).metadata or {})
    for clave in ("/CreationDate", "/ModDate"):
        valor = str(metadatos.get(clave) or "")
        if m := _FECHA_PDF.match(valor):
            return f"{m[1]}-{m[2]}-{m[3]}"
    return None


def _fecha_html(html: str) -> str | None:
    pagina = paginas_oficiales.leer(html)
    candidatos = [
        pagina.meta.get("article:published_time"), pagina.meta.get("datepublished"),
        pagina.meta.get("dcterms.date"), pagina.meta.get("date"), *pagina.tiempos,
    ]  # fmt: skip
    for valor in candidatos:
        if valor and (m := re.match(r"(\d{4}-\d{2}-\d{2})", valor.strip())):
            return m[1]
    return None


def _fecha_del_texto(publicacion: Documento, texto: str) -> str | None:
    patron = publicacion.get("fecha_patron")
    m = re.search(patron, texto, re.S) if patron else None
    dia = paginas_oficiales.dia_de_texto(m[1]) if m else None
    return dia.strftime("%Y-%m-%d") if dia else None


def documento_publicacion(publicacion: Documento, contenido: bytes) -> Documento:
    """El documento recogido de una publicación: texto, pasajes sobre drones y fecha."""
    if publicacion["formato"] == "pdf":
        if contenido[:5] != b"%PDF-":
            raise DescargaFallida(f"{publicacion['url']}: no es un PDF")
        texto = airprox.texto_pdf(contenido)
        metadatos = _fecha_pdf(contenido)
    else:
        pagina = contenido.decode("utf-8", errors="replace")
        texto = texto_html(pagina)
        metadatos = _fecha_html(pagina)
    fecha = publicacion.get("fecha") or _fecha_del_texto(publicacion, texto)
    # Un PDF que se genera al pedirlo lleva la fecha de hoy en sus metadatos: si el texto dice
    # cuándo se publicó, manda el texto.
    fecha = fecha or (None if publicacion.get("fecha_patron") else metadatos)
    if not fecha:
        raise ValueError(f"{publicacion['id']}: sin fecha de publicación")
    pasajes = localizar(texto)
    return {
        "id": f"publicaciones:{publicacion['id']}", "fuente_detalle": "publicaciones",
        "tipo": "estadistica", "autoridad": publicacion["autoridad"], "pais": publicacion["pais"],
        "idioma": publicacion["idioma"], "titulo": publicacion["titulo"],
        "enlace": publicacion["url"],
        "fecha": fecha, "fiabilidad": FIABILIDAD, "credibilidad": CREDIBILIDAD,
        "pasajes": list(pasajes.textos), "huella": pasajes.huella,
    }  # fmt: skip


def recolector_publicaciones(
    fuente: Documento, raiz: Path, descargador: Descargador, ahora: datetime, historico: bool
) -> int:
    """Descarga las publicaciones que aún no se tienen (todas, con el histórico)."""
    ruta = detalle.ruta_documentos(raiz, fuente["id"])
    ya = {d["id"] for d in json.loads(ruta.read_text(encoding="utf-8"))} if ruta.exists() else set()
    nuevos, errores = [], []
    for publicacion in publicaciones():
        id_ = f"publicaciones:{publicacion['id']}"
        if id_ in ya and not historico:
            continue
        lector = oficiales.robots(descargador, publicacion["url"])
        if not lector.can_fetch(AGENTE_EODI, publicacion["url"]):
            errores.append(f"{publicacion['id']}: robots.txt no lo permite")
            continue
        try:
            contenido = descargador.contenido(publicacion["url"], lambda c: len(c) > 0)
            nuevos.append(documento_publicacion(publicacion, contenido))
        except (DescargaFallida, ValueError) as error:
            errores.append(f"{publicacion['id']}: {str(error)[:150]}")
    for aviso in errores:
        registro.warning("publicaciones: %s", aviso)
    detalle.guardar_documentos(raiz, fuente["id"], nuevos)
    if errores and not nuevos and not ya:
        raise DescargaFallida("; ".join(errores))
    return len(nuevos)


detalle.registrar_recolector("ukab_meses", recolector_ukab_meses)
detalle.registrar_recolector("publicaciones", recolector_publicaciones)
