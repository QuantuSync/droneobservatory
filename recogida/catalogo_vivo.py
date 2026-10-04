"""Barrido periódico del catálogo de prestaciones (catálogo vivo).

Lo lanza `servidor/catalogo.sh` una vez al día con su propio cerrojo (nunca el de la recogida
horaria) y deja lo que encuentra en `<datos>/` (`EODI_CATALOGO_DATOS`, en el servidor
/home/eodi/datos/catalogo); la recogida horaria lo incorpora a la base (tabla `catalogo_vivo`).
Fuentes y ritmo en `configuracion/barrido_catalogo.json`: diario para War&Sanctions y para los
datos propios, semanal para el resto. Lógica sin red en `proceso/catalogo_vivo.py`.

Ficheros:

- `novedades.jsonl`: cada hallazgo (modelo nuevo, cifra nueva de un modelo conocido, táctica o
  nombre de modelo nuevo en los datos propios) con su fecha, su semana, su fuente y su estado
  (admitida o candidata). Solo se añade: una candidata que confirma otra fuente se reescribe como
  admitida en una línea nueva con el mismo id.
- `catalogo_vivo.json`: lo admitido que se aplica al catálogo de la configuración (fuentes,
  modelos nuevos, cifras nuevas y modelos sin clase), con su versión.
- `historial.jsonl`: cada versión del catálogo vivo, con su fecha y las novedades que aplica.
- `tacticas.json`: las tácticas observadas, con su primera y última vez, cuántas veces y hasta
  tres frases de ejemplo con su fuente.
- `apariciones.json`: qué modelos nombran los datos propios (incidentes en Europa, partes de la
  capa de guerra y encuentros de la UK Airprox Board), por país y por mes.
- `control.json`: la última lectura de cada fuente, su estado y lo ya visto.
- `gasto.json`: lo gastado en el extractor por día y en la primera pasada.

Uso:
    python -m recogida.catalogo_vivo barrer [--base db.age] [--primera] [--solo FUENTE]
    python -m recogida.catalogo_vivo resumen
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urljoin

from almacen.base import Almacen
from proceso import catalogo_vivo as cv
from proceso.deduccion import catalogo as catalogo_
from proceso.noticias import filtro as filtro_noticias
from recogida import canales_guerra
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida

registro = logging.getLogger("recogida.catalogo_vivo")

VARIABLE_DATOS = "EODI_CATALOGO_DATOS"
DATOS = Path.home() / "datos" / "catalogo"
CONFIGURACION = catalogo_.CONFIGURACION / "barrido_catalogo.json"
NOVEDADES, CATALOGO, HISTORIAL = "novedades.jsonl", "catalogo_vivo.json", "historial.jsonl"
TACTICAS, APARICIONES = "tacticas.json", "apariciones.json"
CONTROL, GASTO = "control.json", "gasto.json"
# Presupuesto del extractor: 0,10 USD al día y, una sola vez, 3 USD para la primera pasada.
LIMITE_DIARIO_USD = 0.10
LIMITE_PRIMERA_USD = 3.00
# Ritmo moderado: una petición cada 5 s por sitio (el descargador espera también entre
# reintentos, 5, 10, 20 y 40 s, y respeta el tope diario de reintentos por sitio).
PAUSA_S = 5.0
# War&Sanctions: cuántas páginas de la lista como mucho y qué parte de las fichas conocidas se
# vuelve a leer cada día para ver cambios (un séptimo: todas en una semana).
PAGINAS_LISTA = 30
ROTACION_DIAS = 7
# Tope de tiempo de una ejecución.
TOPE_S = 50 * 60
EJEMPLOS_TACTICA = 3
CLASE_FIBRA = "fpv_fibra"
CLASE_FPV_RADIO = "fpv_militar_rf"
TIPO_AERONAVE = {
    "fpv": "multirrotor",
    "senuelo_largo_alcance": "ala_fija",
    "municion_merodeadora": "ala_fija",
    "ataque_largo_alcance_piston": "ala_fija",
    "ataque_reaccion": "reaccion",
    "multirrotor_consumo_sub250": "multirrotor",
    "multirrotor_consumo": "multirrotor",
    "multirrotor_profesional": "multirrotor",
}

Documento = dict[str, Any]


def directorio_datos() -> Path:
    return Path(os.environ.get(VARIABLE_DATOS) or DATOS)


def _leer(ruta: Path, defecto: Any) -> Any:
    if not ruta.exists():
        return defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def _escribir(ruta: Path, contenido: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with open(temporal, "w", encoding="utf-8", newline="\n") as fichero:
        fichero.write(json.dumps(contenido, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    temporal.replace(ruta)


def leer_novedades(datos: Path) -> list[Documento]:
    """Las novedades, la última línea de cada id (una candidata confirmada se reescribe)."""
    ruta = datos / NOVEDADES
    if not ruta.exists():
        return []
    por_id: dict[str, Documento] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip():
            novedad = json.loads(linea)
            por_id[novedad["id"]] = novedad
    return list(por_id.values())


def _anadir(datos: Path, nombre: str, documentos: list[Documento]) -> None:
    if not documentos:
        return
    datos.mkdir(parents=True, exist_ok=True)
    with open(datos / nombre, "a", encoding="utf-8", newline="\n") as fichero:
        for documento in documentos:
            fichero.write(json.dumps(documento, ensure_ascii=False, sort_keys=True) + "\n")


def semana(dia: date) -> str:
    anio, numero, _ = dia.isocalendar()
    return f"{anio}-W{numero:02d}"


def configuracion(ruta: Path = CONFIGURACION) -> Documento:
    contenido: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return contenido


def toca(fuente: Documento, control: Documento, hoy: date) -> bool:
    """Diario: si no se leyó hoy; semanal: si hace 7 días o más."""
    ultima = control.get("fuentes", {}).get(fuente["id"], {}).get("ultima_lectura")
    if not ultima:
        return True
    dia = date.fromisoformat(ultima[:10])
    return dia < hoy if fuente["ritmo"] == "diario" else (hoy - dia).days >= 7


# --- Lectores ----------------------------------------------------------------------------


@dataclass
class Entrada:
    url: str
    titulo: str
    fecha: str | None = None
    resumen: str = ""


def _es_html(texto: str) -> bool:
    return "<" in texto


def leer_rss(descargar: Callable[[str], str], fuente: Documento) -> list[Entrada]:
    texto = descargar(fuente["url"])
    entradas = []
    for item in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", texto, re.S | re.I):
        enlace = re.search(r"<link[^>]*?(?:href=\"([^\"]+)\"[^>]*/?>|>([^<]+)</link>)", item, re.I)
        titulo = re.search(r"<title[^>]*>(.*?)</title>", item, re.S | re.I)
        fecha = re.search(r"<(?:pubDate|published|updated|dc:date)[^>]*>(.*?)</", item, re.S | re.I)
        resumen = re.search(
            r"<(?:description|summary|content:encoded)[^>]*>(.*?)</", item, re.S | re.I
        )
        if not enlace:
            continue
        url = (enlace.group(1) or enlace.group(2) or "").strip()
        entradas.append(
            Entrada(
                url,
                cv._texto(re.sub(r"<!\[CDATA\[|\]\]>", "", titulo.group(1))) if titulo else url,
                fecha.group(1).strip()[:40] if fecha else None,
                cv._texto(re.sub(r"<!\[CDATA\[|\]\]>", "", resumen.group(1))) if resumen else "",
            )
        )
    return entradas


def leer_enlaces(descargar: Callable[[str], str], fuente: Documento) -> list[Entrada]:
    """Los enlaces de una página de lista que cumplen el patrón de la fuente."""
    texto = descargar(fuente["url"])
    patron = re.compile(fuente["patron"])
    entradas: dict[str, Entrada] = {}
    for m in re.finditer(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", texto, re.S | re.I):
        url = urljoin(fuente["url"], m.group(1).strip())
        if patron.search(url) and url not in entradas:
            entradas[url] = Entrada(url, cv._texto(m.group(2))[:300] or url)
    return list(entradas.values())


def leer_sitemap(descargar: Callable[[str], str], fuente: Documento) -> list[Entrada]:
    texto = descargar(fuente["url"])
    patron = re.compile(fuente["patron"])
    entradas = []
    for bloque in re.findall(r"<url>.*?</url>", texto, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", bloque)
        fecha = re.search(r"<lastmod>(.*?)</lastmod>", bloque)
        if loc and patron.search(loc.group(1)):
            entradas.append(
                Entrada(
                    loc.group(1).strip(),
                    loc.group(1).strip(),
                    fecha.group(1)[:10] if fecha else None,
                )
            )
    return entradas


def leer_war_sanctions(
    descargar: Callable[[str], str], fuente: Documento
) -> list[tuple[str, str, str]]:
    vistos: dict[str, tuple[str, str, str]] = {}
    for pagina in range(1, int(fuente.get("paginas_max", PAGINAS_LISTA)) + 1):
        texto = descargar(f"{fuente['url']}?page={pagina}&per-page=12")
        nuevos = [x for x in cv.lista_war_sanctions(texto) if x[0] not in vistos]
        if not nuevos:
            break
        vistos.update({x[0]: x for x in nuevos})
    return list(vistos.values())


# --- Estado de una ejecución -----------------------------------------------------------


@dataclass
class Barrido:
    datos: Path
    ahora: datetime
    catalogo: Documento  # el de la configuración con lo ya admitido (vivo)
    fuentes_catalogo: Documento
    descargador: Descargador
    extractor: Any | None = None
    primera: bool = False
    hallazgos: list[Documento] = field(default_factory=list)
    gasto: Documento = field(default_factory=dict)
    cuentas: Counter[str] = field(default_factory=Counter)
    robots: dict[str, Any] = field(default_factory=dict)
    # Las tácticas de los partes se leen desde la última pasada (o desde el principio).
    desde_partes: str = ""

    @property
    def hoy(self) -> date:
        return self.ahora.date()

    def descargar(self, url: str) -> str:
        """La página, si el robots.txt de su sitio lo permite a la identificación del
        observatorio (se lee una vez por sitio y ejecución)."""
        from urllib.parse import urlsplit

        from recogida.oficiales import robots

        sitio_ = urlsplit(url).netloc
        if sitio_ not in self.robots:
            self.robots[sitio_] = robots(self.descargador, url)
        if not self.robots[sitio_].can_fetch(AGENTE_EODI, url):
            self.cuentas["robots_no_permite"] += 1
            raise DescargaFallida(f"{url}: el robots.txt no lo permite")
        return self.descargador.texto(url, lambda t: bool(t.strip()))

    def nombres(self) -> dict[str, str]:
        return cv.nombres_de(self.catalogo)

    def por_url(self) -> dict[str, str]:
        return {
            re.sub(r"^https?://(www\.)?", "", f["url"]).rstrip("/").lower(): id_
            for id_, f in self.fuentes_catalogo["fuentes"].items()
        }


def _fuente_doc(fuente: Documento, url: str, titulo: str, fecha: str | None) -> Documento:
    return {
        "id": fuente["id"],
        "tipo": fuente["tipo"],
        "url": url,
        "titulo": titulo[:300],
        "fecha": fecha,
    }


def unidad_del_campo(catalogo: Documento, campo: str, dato: Documento) -> bool:
    """Si la unidad de una cifra cabe en el campo: «autonomía 10 km» no es una autonomía."""
    canonica = catalogo["campos"].get(campo, {}).get("unidad")
    unidad = dato.get("unidad")
    if canonica is None or unidad is None:
        return True
    return unidad in catalogo_.CONVERSION and catalogo_.convertible(unidad, canonica)


def _hallazgo(barrido: Barrido, tipo: str, fuente: Documento, url: str, titulo: str,
              fecha: str | None, **datos: Any) -> None:  # fmt: skip
    if tipo == cv.CIFRA_NUEVA and not unidad_del_campo(
        barrido.catalogo, datos.get("campo", ""), datos.get("dato", {})
    ):
        barrido.cuentas["cifras_con_unidad_ajena"] += 1
        return
    barrido.hallazgos.append(
        {"tipo": tipo, "fuente": _fuente_doc(fuente, url, titulo, fecha), **datos}
    )


def _ya_tiene(modelo: Documento, campo: str, cifra: Documento) -> bool:
    for dato in modelo.get("campos", {}).get(campo, {}).get("datos", []):
        if all(dato.get(k) == cifra.get(k) for k in ("valor", "min", "max", "unidad")):
            return True
    return False


def _modelos(barrido: Barrido) -> dict[str, Documento]:
    return {m["id"]: m for m in barrido.catalogo["modelos"]}


def analizar_ficha_ws(barrido: Barrido, fuente: Documento, ficha: cv.Ficha) -> None:
    """Hallazgos de una ficha de War&Sanctions."""
    modelos = _modelos(barrido)
    conocido = cv.modelo_de(ficha.nombre, barrido.nombres())
    clase, motivo = cv.clase_por_proposito(ficha)
    if conocido is None and clase == cv.FPV:
        conocido = CLASE_FIBRA if cv.fibra(ficha) else CLASE_FPV_RADIO
    if conocido is not None:
        for campo, cifras in ficha.cifras.items():
            for cifra in cifras:
                if _ya_tiene(modelos[conocido], campo, cifra):
                    continue
                _hallazgo(
                    barrido,
                    cv.CIFRA_NUEVA,
                    fuente,
                    ficha.url,
                    ficha.nombre,
                    ficha.fecha,
                    modelo=conocido,
                    nombre=ficha.nombre,
                    campo=campo,
                    dato=cifra,
                    clave=cv.clave_cifra(conocido, campo, cifra),
                )
        return
    _hallazgo(
        barrido,
        cv.MODELO_NUEVO,
        fuente,
        ficha.url,
        ficha.nombre,
        ficha.fecha,
        nombre=ficha.nombre,
        clase=clase,
        motivo=motivo,
        proposito=ficha.proposito,
        cifras=ficha.cifras,
        clave=cv.clave_modelo(ficha.nombre),
    )


def barrer_war_sanctions(barrido: Barrido, fuente: Documento, control: Documento) -> int:
    lista = leer_war_sanctions(barrido.descargar, fuente)
    vistos: dict[str, str] = control.setdefault("vistos", {})
    conocidas = barrido.por_url()
    leidas = 0
    for url, _nombre, _ in lista:
        clave = re.sub(r"^https?://(www\.)?", "", url).rstrip("/").lower()
        nueva = url not in vistos and clave not in conocidas
        rota = int(cv.huella(url), 16) % ROTACION_DIAS == barrido.hoy.toordinal() % ROTACION_DIAS
        if not (nueva or rota or barrido.primera):
            continue
        try:
            pagina = barrido.descargar(url)
        except DescargaFallida as error:
            registro.warning("War&Sanctions %s: %s", url, error)
            continue
        leidas += 1
        ficha = cv.ficha_war_sanctions(url, pagina)
        if ficha is None:
            continue
        huella = cv.huella(json.dumps(ficha.cifras, sort_keys=True), ficha.proposito)
        if vistos.get(url) != huella:
            analizar_ficha_ws(barrido, fuente, ficha)
            vistos[url] = huella
    barrido.cuentas[f"{fuente['id']}:fichas_leidas"] += leidas
    barrido.cuentas[f"{fuente['id']}:en_lista"] += len(lista)
    return len(lista)


PESO_PROFESIONAL_KG = 2.0


def _clase_fabricante(fuente: Documento, ficha: cv.Ficha) -> str | None:
    from proceso.deduccion.catalogo import convertir

    pesos = [
        convertir(cv._mayor(c), c["unidad"], "kg")
        for c in ficha.cifras.get("mtow", [])
        if c["unidad"] in {"g", "kg", "lb"}
    ]
    if pesos and max(pesos) < 0.25 and fuente.get("clase", "").startswith("multirrotor_consumo"):
        return "multirrotor_consumo_sub250"
    # Un multirrotor de más de PESO_PROFESIONAL_KG en la lista de consumo de un fabricante
    # (Inspire 3, 4,3 kg) es de la clase profesional.
    if pesos and max(pesos) > PESO_PROFESIONAL_KG and fuente.get("clase") == "multirrotor_consumo":
        return "multirrotor_profesional"
    clase: str | None = fuente.get("clase")
    return clase


def barrer_fabricante(barrido: Barrido, fuente: Documento, control: Documento) -> int:
    lector = {"rss": leer_rss, "enlaces": leer_enlaces, "sitemap": leer_sitemap}[fuente["lector"]]
    entradas = lector(barrido.descargar, fuente)
    vistos: dict[str, str] = control.setdefault("vistos", {})
    nombres = barrido.nombres()
    modelos = _modelos(barrido)
    for entrada in entradas:
        if entrada.url in vistos and not barrido.primera:
            continue
        vistos[entrada.url] = barrido.hoy.isoformat()
        if not fuente.get("ficha"):
            analizar_texto(barrido, fuente, entrada, entrada.titulo + " " + entrada.resumen)
            continue
        base = entrada.url.split("?")[0].split("#")[0].rstrip("/")
        url_ficha = fuente["ficha"].format(url=entrada.url.rstrip("/"), base=base)
        try:
            pagina = barrido.descargar(url_ficha)
        except DescargaFallida as error:
            registro.warning("%s %s: %s", fuente["id"], url_ficha, error)
            continue
        nombre = cv.nombre_de_titulo(entrada.titulo, base)
        if not nombre or nombre.startswith("http"):
            titulo = re.search(r"<title[^>]*>(.*?)</title>", pagina, re.S | re.I)
            nombre = cv.nombre_de_titulo(cv._texto(titulo.group(1)), base) if titulo else base
        if fuente.get("excluir") and re.search(fuente["excluir"], nombre, re.I):
            continue
        ficha = cv.ficha_fabricante(url_ficha, nombre, pagina)
        if not ficha.cifras:
            continue
        conocido = cv.modelo_de(nombre, nombres)
        if conocido is not None:
            for campo, cifras in ficha.cifras.items():
                for cifra in cifras:
                    if not _ya_tiene(modelos[conocido], campo, cifra):
                        _hallazgo(
                            barrido,
                            cv.CIFRA_NUEVA,
                            fuente,
                            url_ficha,
                            nombre,
                            entrada.fecha,
                            modelo=conocido,
                            nombre=nombre,
                            campo=campo,
                            dato=cifra,
                            clave=cv.clave_cifra(conocido, campo, cifra),
                        )
        else:
            clase = _clase_fabricante(fuente, ficha)
            _hallazgo(
                barrido,
                cv.MODELO_NUEVO,
                fuente,
                url_ficha,
                nombre,
                entrada.fecha,
                nombre=nombre,
                clase=clase,
                motivo=f"modelo nuevo del fabricante (clase {clase or 'sin decidir'})",
                cifras=ficha.cifras,
                clave=cv.clave_modelo(nombre),
            )
    return len(entradas)


_CLASE_UE = re.compile(r"\b(C[0-6])\b")


def clase_ue(barrido: Barrido, fuente: Documento, entrada: Entrada) -> None:
    """Una entrada de una lista oficial de marcado de clase de la UE: la clase (C0 a C6) de un
    modelo conocido es una cifra nueva de texto; un modelo desconocido queda registrado sin
    clase del motor (no trae prestaciones)."""
    clase = _CLASE_UE.search(entrada.titulo)
    nombre = _CLASE_UE.sub("", entrada.titulo).strip(" -–|:")
    if not nombre:
        return
    conocido = cv.modelo_de(nombre, barrido.nombres())
    if conocido is not None and clase:
        dato = {"texto": clase.group(1), "cita": entrada.titulo[:300]}
        if any(
            d.get("texto") == dato["texto"]
            for d in _modelos(barrido)[conocido]["campos"].get("clase_ue", {}).get("datos", [])
        ):
            return
        _hallazgo(
            barrido,
            cv.CIFRA_NUEVA,
            fuente,
            entrada.url,
            entrada.titulo,
            entrada.fecha,
            modelo=conocido,
            nombre=nombre,
            campo="clase_ue",
            dato=dato,
            clave=f"clase_ue|{conocido}|{clase.group(1)}",
        )
    elif conocido is None:
        _hallazgo(
            barrido,
            cv.MODELO_NUEVO,
            fuente,
            entrada.url,
            nombre,
            entrada.fecha,
            nombre=nombre,
            clase=None,
            cifras={},
            motivo="en la lista oficial de marcado de clase"
            + (f" ({clase.group(1)})" if clase else ""),
            clave=cv.clave_modelo(nombre),
        )


_FILA_CLASE = re.compile(r"\| ([^|]{3,80}?) \| ([^|]{2,120}?) \| (C[0-6](?:, ?C[0-6])*) \|")


def barrer_tabla_clases(barrido: Barrido, fuente: Documento) -> None:
    """Una tabla «modelo | fabricante | clase» de una lista de productos con marcado de clase."""
    texto = cv._texto(barrido.descargar(fuente["url"]))
    for m in _FILA_CLASE.finditer(texto):
        modelo, fabricante, clases = (x.strip() for x in m.groups())
        entrada = Entrada(fuente["url"], f"{modelo} {clases.split(',')[0]}", resumen=fabricante)
        clase_ue(barrido, fuente, entrada)


_NUMERO_UNIDAD = re.compile(
    r"\d+(?:[.,]\d+)?\s?(?:km/h|km|kg|m/s|mph|kn|min|hours?|h\b|m\b|ft\b|g\b)", re.I
)


def analizar_texto(barrido: Barrido, fuente: Documento, entrada: Entrada, texto: str) -> None:
    """Tácticas, modelos nombrados y, si el extractor tiene presupuesto, cifras en un texto."""
    nombres = barrido.nombres()
    for tipo, frase, paises in cv.tacticas(texto):
        modelos = sorted(cv.menciones(frase, nombres))
        _hallazgo(
            barrido,
            cv.TACTICA,
            fuente,
            entrada.url,
            entrada.titulo,
            entrada.fecha,
            tactica=tipo,
            frase=frase[:600],
            paises=paises,
            modelos=modelos,
            clave=cv.clave_tactica(tipo, modelos, paises),
        )
    if barrido.extractor is None:
        return
    candidatas = [
        f for f in cv.frases(texto) if cv.menciones(f, nombres) and _NUMERO_UNIDAD.search(f)
    ][:6]
    if candidatas:
        for cifra in extraer_cifras(barrido, candidatas, nombres):
            _hallazgo(
                barrido, cv.CIFRA_NUEVA, fuente, entrada.url, entrada.titulo, entrada.fecha, **cifra
            )


# --- Extractor -------------------------------------------------------------------------


def limite(barrido: Barrido) -> tuple[str, float, float]:
    """(modo, gastado, límite) del presupuesto que toca."""
    if barrido.primera:
        return "primera", float(barrido.gasto.get("primera", 0.0)), LIMITE_PRIMERA_USD
    dia = barrido.hoy.isoformat()
    return "diario", float(barrido.gasto.get("dias", {}).get(dia, 0.0)), LIMITE_DIARIO_USD


def extraer_cifras(barrido: Barrido, frases: list[str], nombres: dict[str, str]) -> list[Documento]:
    """Cifras validadas por código de lo que lee el extractor."""
    from modelo import catalogo as ficha_catalogo
    from modelo import coste

    modelos_nombrados = sorted(
        {
            n
            for f in frases
            for n in nombres
            if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", f.lower())
        }
    )
    modo, gastado, tope = limite(barrido)
    previsto = coste.peor_caso(
        sum(len(f) for f in frases) + len(ficha_catalogo.INSTRUCCIONES),
        ficha_catalogo.MAX_TOKENS_SALIDA,
    )
    if gastado + previsto > tope:
        barrido.cuentas["extractor_sin_presupuesto"] += 1
        return []
    if barrido.extractor is None:
        return []
    try:
        respuesta = barrido.extractor.mensaje(ficha_catalogo.cuerpo(frases, modelos_nombrados))
    except Exception as error:  # el servicio caído no para el barrido
        registro.warning("extractor: %s", str(error)[:200])
        barrido.extractor = None
        return []
    gastado_ahora = coste.Uso.de_respuesta(respuesta.get("usage", {})).coste()
    if modo == "primera":
        barrido.gasto["primera"] = round(gastado + gastado_ahora, 6)
    else:
        dias = barrido.gasto.setdefault("dias", {})
        dias[barrido.hoy.isoformat()] = round(gastado + gastado_ahora, 6)
    barrido.cuentas["extractor_llamadas"] += 1
    try:
        cifras = ficha_catalogo.leer_respuesta(respuesta)
    except ficha_catalogo.RespuestaInvalida:
        return []
    validas = []
    texto = " ".join(frases)
    for cifra in cifras:
        frase = str(cifra.get("frase", ""))
        modelo = cv.modelo_de(str(cifra.get("modelo", "")), nombres)
        numeros = [cifra.get(k) for k in ("valor", "min", "max") if cifra.get(k) is not None]
        if (
            not frase
            or frase not in texto
            or modelo is None
            or not numeros
            or not all(_en_frase(n, frase) for n in numeros)
            or str(cifra.get("modelo", "")).lower() not in frase.lower()
        ):
            barrido.cuentas["extractor_cifras_rechazadas"] += 1
            continue
        dato = {k: cifra[k] for k in ("valor", "min", "max") if cifra.get(k) is not None}
        dato.update({"unidad": cifra["unidad"], "cita": frase})
        validas.append(
            {
                "modelo": modelo,
                "nombre": cifra["modelo"],
                "campo": cifra["campo"],
                "dato": dato,
                "metodo": "extractor",
                "clave": f"cifra|{modelo}|{cifra['campo']}|{cv.huella(*numeros, cifra['unidad'])}",
            }
        )
    return validas


def _en_frase(numero: Any, frase: str) -> bool:
    entero = float(numero)
    formas = {f"{entero:g}", f"{entero:,.0f}", f"{entero:.0f}", str(numero)}
    plano = frase.replace(" ", " ").replace(" ", "")
    return any(f.replace(" ", "") in plano or f.replace(".", ",") in plano for f in formas)


# --- Datos propios ---------------------------------------------------------------------

_NOMBRE_SERIE = re.compile(
    r"(?<!\w)(geran|герань|shahed|шахед|gerbera|гербера|lancet|ланцет|molniya|молния)"
    r"[- ]?(\d{1,3})(?!\d)",
    re.I,
)


def barrer_propios(barrido: Barrido, fuente: Documento, almacen: Almacen) -> Documento:
    """Qué modelos nombran los datos propios y con qué frecuencia; tácticas de los canales
    oficiales de la capa de guerra; nombres de modelo que el catálogo no tiene."""
    nombres = barrido.nombres()
    apariciones: dict[str, Documento] = {}

    def contar(textos: list[str], pais: str | None, mes: str, origen: str) -> None:
        cuentas: Counter[str] = Counter()
        for texto in textos:
            cuentas.update(cv.menciones(texto, nombres))
        for modelo in cuentas:
            entrada = apariciones.setdefault(
                modelo, {"total": 0, "por_pais": {}, "por_mes": {}, "por_origen": {}}
            )
            entrada["total"] += 1
            if pais:
                entrada["por_pais"][pais] = entrada["por_pais"].get(pais, 0) + 1
            entrada["por_mes"][mes] = entrada["por_mes"].get(mes, 0) + 1
            entrada["por_origen"][origen] = entrada["por_origen"].get(origen, 0) + 1

    desconocidos: Counter[str] = Counter()
    for incidente in almacen.incidentes():
        if "fusionado_en" in incidente or "retirado" in incidente:
            continue
        textos = [str((incidente.get("drones") or {}).get("modelo") or "")]
        textos += [str(f.get("frase_origen") or "") for f in incidente.get("fuentes", [])]
        mes = str(incidente.get("tiempo", {}).get("inicio", {}).get("valor", ""))[:7]
        contar(textos, (incidente.get("lugar") or {}).get("pais"), mes, "incidentes_europa")
        for texto in textos:
            desconocidos.update(m.group(0) for m in _NOMBRE_SERIE.finditer(texto))
    for encuentro in almacen.encuentros():
        texto = str((encuentro.get("objeto") or {}).get("descripcion") or "")
        mes = str((encuentro.get("instante") or {}).get("valor", ""))[:7]
        contar([texto], encuentro.get("pais") or "GB", mes, "uk_airprox")
    # Los partes de la capa de guerra: los textos guarda el lector de canales en su carpeta.
    canales = {c.id: c for c in canales_guerra.cargar_canales()}
    guerra = canales_guerra.Datos(canales_guerra.directorio_datos())
    for canal_id, canal in sorted(canales.items()):
        oficial = canal.origen == "oficial"
        for mensaje in guerra.ultimas(canal_id).values():
            texto = str(mensaje.get("texto") or "")
            if not texto:
                continue
            mes = str(mensaje.get("fecha") or "")[:7]
            contar([texto], canal.pais, mes, "partes_guerra")
            desconocidos.update(m.group(0) for m in _NOMBRE_SERIE.finditer(texto))
            if str(mensaje.get("fecha") or "") < barrido.desde_partes:
                continue
            for tipo, frase, paises in cv.tacticas(texto)[:2]:
                nombrados = sorted(cv.menciones(frase, nombres))
                origen = {**fuente, "tipo": "autoridad" if oficial else "prensa"}
                donde = paises or [canal.pais]
                _hallazgo(
                    barrido,
                    cv.TACTICA,
                    origen,
                    f"https://t.me/{canal.canal}/{mensaje['id']}",
                    canal.canal,
                    str(mensaje.get("fecha") or "")[:10] or None,
                    tactica=tipo,
                    frase=frase[:600],
                    paises=donde,
                    modelos=nombrados,
                    clave=cv.clave_tactica(tipo, nombrados, donde),
                )
    for nombre, veces in sorted(desconocidos.items()):
        if cv.modelo_de(nombre, nombres) is None:
            _hallazgo(
                barrido,
                cv.MODELO_NUEVO,
                {**fuente, "tipo": "propios"},
                "datos_propios",
                nombre,
                barrido.hoy.isoformat(),
                nombre=nombre,
                clase=None,
                motivo=f"nombrado {veces} veces en los datos propios; sin ficha",
                cifras={},
                clave=cv.clave_modelo(nombre),
            )
    return {
        "fecha": barrido.hoy.isoformat(),
        "modelos": dict(sorted(apariciones.items(), key=lambda x: -x[1]["total"])),
    }


# --- Reglas de entrada y catálogo vivo -------------------------------------------------


def a_novedades(barrido: Barrido, previas: list[Documento]) -> list[Documento]:
    """Novedades de los hallazgos de esta ejecución (sin repetir lo que ya dijo la misma
    fuente). Las de datos propios nunca son cifras: quedan como candidatas."""
    existentes = {n["id"] for n in previas}
    nuevas = []
    for hallazgo in barrido.hallazgos:
        id_ = cv.huella(hallazgo["clave"], hallazgo["fuente"]["url"])
        if id_ in existentes:
            continue
        existentes.add(id_)
        tipo_fuente = hallazgo["fuente"]["tipo"]
        estado = cv.CANDIDATA if tipo_fuente == cv.PROPIOS else cv.estado_de(tipo_fuente)
        nuevas.append(
            {
                "id": id_,
                "fecha": barrido.hoy.isoformat(),
                "semana": semana(barrido.hoy),
                "estado": estado,
                **hallazgo,
            }
        )
    return nuevas


def _slug(nombre: str) -> str:
    return (
        re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", nombre.lower())).strip("_")[:60] or "modelo"
    )


def aplicar(vivo: Documento, base: Documento, fuentes_base: Documento,
            novedades: list[Documento], hoy: date) -> list[str]:  # fmt: skip
    """Aplica al catálogo vivo las novedades admitidas que aún no están. Devuelve sus ids."""
    aplicadas = set(vivo.get("aplicadas", []))
    por_url = {
        re.sub(r"^https?://(www\.)?", "", f["url"]).rstrip("/").lower(): id_
        for id_, f in {**fuentes_base["fuentes"], **vivo.get("fuentes", {})}.items()
    }
    numero = 1 + max(
        [int(i[1:]) for i in vivo.get("fuentes", {}) if re.fullmatch(r"V\d+", i)] or [0]
    )
    modelos_base = {m["id"] for m in base["modelos"]}
    nuevos_ids = {m["id"] for m in vivo.get("modelos", [])}
    hechas = []

    def fuente_de(novedad: Documento) -> str:
        nonlocal numero
        url = novedad["fuente"]["url"]
        clave = re.sub(r"^https?://(www\.)?", "", url).rstrip("/").lower()
        if clave not in por_url:
            id_ = f"V{numero}"
            numero += 1
            vivo.setdefault("fuentes", {})[id_] = {
                "titulo": novedad["fuente"]["titulo"] or url,
                "url": url,
                "fecha": novedad["fuente"].get("fecha")
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(novedad["fuente"].get("fecha")))
                else None,
                "consultada": hoy.isoformat(),
                "tipo": novedad["fuente"]["tipo"],
                "prioridad": "normal",
                "notas": "Admitida por el barrido periódico del catálogo vivo.",
            }
            por_url[clave] = id_
        return str(por_url[clave])

    for novedad in sorted(novedades, key=lambda n: (n["fecha"], n["id"])):
        if (
            novedad["estado"] != cv.ADMITIDA
            or novedad["id"] in aplicadas
            or novedad["tipo"] not in {cv.CIFRA_NUEVA, cv.MODELO_NUEVO}
        ):
            continue
        if novedad["tipo"] == cv.CIFRA_NUEVA and novedad.get("modelo"):
            if novedad["modelo"] not in modelos_base | nuevos_ids:
                continue
            dato = {"fuente": fuente_de(novedad), **novedad["dato"]}
            if novedad.get("nombre") and novedad["modelo"] in {CLASE_FIBRA, CLASE_FPV_RADIO}:
                dato["nota"] = f"Modelo de la fuente: {novedad['nombre']}."
            vivo.setdefault("datos", []).append(
                {
                    "modelo": novedad["modelo"],
                    "campo": novedad["campo"],
                    "dato": dato,
                    "alta": novedad["fecha"],
                    "novedad": novedad["id"],
                }
            )
        elif novedad["tipo"] == cv.MODELO_NUEVO:
            cifras = novedad.get("cifras") or {}
            if novedad.get("clase") and cifras:
                id_ = _slug(novedad["nombre"])
                if id_ in modelos_base | nuevos_ids:
                    id_ = f"{id_}_{novedad['id'][:6]}"
                fuente = fuente_de(novedad)
                vivo.setdefault("modelos", []).append(
                    {
                        "id": id_,
                        "nombre": novedad["nombre"],
                        "otros_nombres": [],
                        "pais": "no consta en la fuente",
                        "fabricante": "no consta en la fuente",
                        "tipo_aeronave": TIPO_AERONAVE.get(novedad["clase"], "ala_fija"),
                        "clase": novedad["clase"],
                        "campos": {
                            c: {
                                "datos": [{"fuente": fuente, **d} for d in lista],
                                "sin_fuente": False,
                            }
                            for c, lista in cifras.items()
                        },
                        "vivo": {"alta": novedad["fecha"], "fuentes": [fuente]},
                        "nota": f"Alta del barrido del catálogo vivo: {novedad.get('motivo', '')}"[
                            :500
                        ],
                    }
                )
                nuevos_ids.add(id_)
            else:
                vivo.setdefault("sin_clase", []).append(
                    {
                        "nombre": novedad["nombre"],
                        "motivo": novedad.get("motivo"),
                        "fuente": novedad["fuente"]["url"],
                        "cifras": cifras,
                        "alta": novedad["fecha"],
                        "novedad": novedad["id"],
                    }
                )
        aplicadas.add(novedad["id"])
        hechas.append(novedad["id"])
    if hechas:
        vivo["version"] = int(vivo.get("version", 0)) + 1
        vivo["aplicadas"] = sorted(aplicadas)
    return hechas


def actualizar_tacticas(tacticas: Documento, novedades: list[Documento]) -> None:
    """Registro de tácticas: por clave, primera y última vez, veces y ejemplos."""
    for novedad in novedades:
        if novedad["tipo"] != cv.TACTICA:
            continue
        entrada = tacticas.setdefault(
            novedad["clave"],
            {
                "tactica": novedad["tactica"],
                "modelos": novedad.get("modelos", []),
                "paises": novedad.get("paises", []),
                "primera": novedad["fecha"],
                "veces": 0,
                "ejemplos": [],
            },
        )
        entrada["ultima"] = novedad["fecha"]
        entrada["veces"] += 1
        entrada["estado"] = (
            cv.ADMITIDA if novedad["estado"] == cv.ADMITIDA else entrada.get("estado", cv.CANDIDATA)
        )
        if len(entrada["ejemplos"]) < EJEMPLOS_TACTICA:
            entrada["ejemplos"].append(
                {
                    "frase": novedad["frase"],
                    "fuente": novedad["fuente"]["url"],
                    "tipo_fuente": novedad["fuente"]["tipo"],
                    "fecha": novedad["fuente"].get("fecha"),
                }
            )


# --- Ejecución -------------------------------------------------------------------------


def barrer(
    datos: Path,
    ahora: datetime,
    descargador: Descargador,
    almacen: Almacen | None = None,
    extractor: Any | None = None,
    primera: bool = False,
    solo: str | None = None,
    configuracion_: Documento | None = None,
) -> Documento:
    """Una ejecución del barrido. Devuelve el resumen."""
    configuracion_ = configuracion_ or configuracion()
    control = _leer(datos / CONTROL, {"fuentes": {}})
    vivo = _leer(datos / CATALOGO, {"version": 0})
    base = json.loads(catalogo_.CATALOGO.read_text(encoding="utf-8"))
    fuentes_base = json.loads(catalogo_.FUENTES.read_text(encoding="utf-8"))
    catalogo, fuentes = catalogo_.aplicar_vivo(base, fuentes_base, vivo)
    primera = primera or not control.get("primera_hecha")
    barrido = Barrido(
        datos,
        ahora,
        catalogo,
        fuentes,
        descargador,
        extractor,
        primera,
        gasto=_leer(datos / GASTO, {"dias": {}, "primera": 0.0}),
    )
    if not barrido.primera:
        barrido.desde_partes = str(
            control["fuentes"].get("propios", {}).get("ultima_lectura") or ""
        )[:10]
    apariciones = None
    for fuente in configuracion_["fuentes"]:
        if solo and fuente["id"] != solo:
            continue
        estado = control["fuentes"].setdefault(fuente["id"], {})
        if not (toca(fuente, control, barrido.hoy) or barrido.primera or solo):
            continue
        try:
            if fuente["lector"] == "war_sanctions":
                barrer_war_sanctions(barrido, fuente, estado)
            elif fuente["lector"] == "propios":
                if almacen is None:
                    continue
                apariciones = barrer_propios(barrido, fuente, almacen)
            elif fuente["tipo"] == "fabricante" and fuente.get("ficha"):
                barrer_fabricante(barrido, fuente, estado)
            elif fuente["lector"] == "tabla_clases":
                barrer_tabla_clases(barrido, fuente)
            else:
                lector = {"rss": leer_rss, "enlaces": leer_enlaces, "sitemap": leer_sitemap}
                entradas = lector[fuente["lector"]](barrido.descargar, fuente)
                vistos: dict[str, str] = estado.setdefault("vistos", {})
                dron = filtro_noticias().dron
                for entrada in entradas:
                    if entrada.url in vistos:
                        continue
                    vistos[entrada.url] = barrido.hoy.isoformat()
                    if fuente.get("clase_ue"):
                        clase_ue(barrido, fuente, entrada)
                        continue
                    # Las fuentes que no son de drones: solo las notas que hablan de ellos.
                    if fuente.get("solo_dron") and not dron.search(
                        f"{entrada.titulo} {entrada.resumen}"
                    ):
                        continue
                    texto = entrada.titulo + ". " + entrada.resumen
                    if fuente.get("leer_pagina"):
                        try:
                            texto += " " + cv._texto(barrido.descargar(entrada.url))
                        except DescargaFallida as error:
                            registro.warning("%s %s: %s", fuente["id"], entrada.url, error)
                    analizar_texto(barrido, fuente, entrada, texto)
            estado.update({"ultima_lectura": ahora.strftime("%Y-%m-%dT%H:%MZ"), "estado": "leida"})
            estado.pop("error", None)
        except Exception as error:  # una fuente que falla no para las demás
            estado.update({"estado": "no_leida", "error": str(error)[:300]})
            registro.warning("fuente %s: %s", fuente["id"], str(error)[:300])
    previas = leer_novedades(datos)
    nuevas = a_novedades(barrido, previas)
    todas = previas + nuevas
    confirmadas = cv.confirmar_candidatos(todas)
    _anadir(datos, NOVEDADES, nuevas + [n for n in confirmadas if n not in nuevas])
    hechas = aplicar(vivo, base, fuentes_base, todas, barrido.hoy)
    if hechas:
        _escribir(datos / CATALOGO, vivo)
        _anadir(
            datos,
            HISTORIAL,
            [{"version": vivo["version"], "fecha": barrido.hoy.isoformat(), "novedades": hechas}],
        )
    tacticas = _leer(datos / TACTICAS, {})
    actualizar_tacticas(tacticas, nuevas)
    _escribir(datos / TACTICAS, tacticas)
    if apariciones is not None:
        _escribir(datos / APARICIONES, apariciones)
    if barrido.primera and not solo:
        control["primera_hecha"] = barrido.hoy.isoformat()
    _escribir(datos / CONTROL, control)
    _escribir(datos / GASTO, barrido.gasto)
    resumen = {
        "fecha": ahora.strftime("%Y-%m-%dT%H:%MZ"),
        "primera": barrido.primera,
        "hallazgos": len(barrido.hallazgos),
        "novedades_nuevas": dict(Counter(f"{n['tipo']}:{n['estado']}" for n in nuevas)),
        "confirmadas": len(confirmadas),
        "aplicadas": len(hechas),
        "version_vivo": vivo.get("version", 0),
        "gasto": barrido.gasto,
        "cuentas": dict(barrido.cuentas),
        "fuentes": {k: v.get("estado") for k, v in control["fuentes"].items()},
    }
    registro.info("catálogo vivo: %s", json.dumps(resumen, ensure_ascii=False))
    return resumen


# --- Incorporación en la recogida horaria ------------------------------------------------


def incorporar(almacen: Almacen, datos: Path | None = None) -> dict[str, int]:
    """Guarda en la base (tabla catalogo_vivo) lo que ha cambiado: el catálogo vivo, las
    novedades, las tácticas y las apariciones."""
    datos = datos or directorio_datos()
    cambiados: Counter[str] = Counter()
    vivo = _leer(datos / CATALOGO, None)
    if vivo is not None and almacen.guardar_catalogo_vivo("catalogo", "catalogo", vivo):
        cambiados["catalogo"] += 1
    for novedad in leer_novedades(datos):
        if almacen.guardar_catalogo_vivo(f"novedad:{novedad['id']}", "novedad", novedad):
            cambiados["novedades"] += 1
    tacticas = _leer(datos / TACTICAS, None)
    if tacticas is not None and almacen.guardar_catalogo_vivo("tacticas", "tacticas", tacticas):
        cambiados["tacticas"] += 1
    apariciones = _leer(datos / APARICIONES, None)
    if apariciones is not None and almacen.guardar_catalogo_vivo(
        "apariciones", "apariciones", apariciones
    ):
        cambiados["apariciones"] += 1
    return dict(cambiados)


def paso_horario(almacen: Almacen) -> None:
    """En la recogida horaria: nada de lo que falle aquí sale de esta función."""
    try:
        cambiados = incorporar(almacen)
        registro.info("catálogo vivo incorporado: %s", cambiados or "sin cambios")
    except Exception as error:
        registro.warning("catálogo vivo no incorporado: %s", str(error)[:300])


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    orden = opciones.add_subparsers(dest="orden", required=True)
    barrida = orden.add_parser("barrer", help="lee las fuentes que tocan hoy")
    barrida.add_argument("--repositorio", default=None)
    barrida.add_argument("--base", type=Path, help="base cifrada local")
    barrida.add_argument("--primera", action="store_true", help="primera pasada (todo)")
    barrida.add_argument("--solo", help="solo esta fuente")
    barrida.add_argument("--sin-extractor", action="store_true")
    orden.add_parser("resumen", help="estado del catálogo vivo")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos = directorio_datos()
    if args.orden == "resumen":
        novedades = leer_novedades(datos)
        print(
            json.dumps(
                {
                    "novedades": dict(Counter(f"{n['tipo']}:{n['estado']}" for n in novedades)),
                    "version_vivo": _leer(datos / CATALOGO, {}).get("version", 0),
                    "control": {
                        k: v.get("estado")
                        for k, v in _leer(datos / CONTROL, {"fuentes": {}})["fuentes"].items()
                    },
                    "gasto": _leer(datos / GASTO, {}),
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 0
    from almacen import remoto, sitio
    from almacen.cifrado import abrir_cifrada
    from modelo import cliente as servicio
    from recogida.plazo import Plazo

    extractor = None
    if not args.sin_extractor:
        try:
            extractor = servicio.Cliente(servicio.configuracion())
        except servicio.ClienteNoConfigurado as error:
            registro.warning("extractor sin configurar: %s", error)
    descargador = Descargador(agente=AGENTE_EODI, pausa_minima_s=PAUSA_S, plazo=Plazo(TOPE_S))
    ahora = datetime.now(UTC)
    with TemporaryDirectory() as temporal:
        abierta = (
            Almacen(abrir_cifrada(args.base))
            if args.base is not None
            else sitio.abrir_base(Path(temporal), args.repositorio or remoto.REPOSITORIO)
        )
        if abierta is None:
            registro.error("no hay base en la rama %s", remoto.RAMA)
            return 1
        almacen = abierta
        barrer(datos, ahora, descargador, almacen, extractor, args.primera, args.solo)
        almacen.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(principal())
