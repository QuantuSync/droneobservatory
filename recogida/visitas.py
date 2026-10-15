"""Visitas de la web y resumen diario privado por ntfy (interno: visitas).

La web cuenta sus visitas en un GoatCounter propio (https://stats.droneobservatory.eu, en este
servidor: servidor/visitas.sh). Esta unidad (eodi-visitas.timer, cada 5 minutos) hace tres cosas,
cada una por su cuenta (un fallo de una no para las otras):

1. **Muestra de los suscriptores de ntfy.** ntfy no da suscriptores por canal: sus métricas
   internas (solo en local, configuracion/ntfy/server.yml) dan los suscriptores conectados en ese
   momento en total (`ntfy_subscribers_total`). Por canal solo se sabe cuántos navegadores tienen
   activadas las notificaciones (tabla `subscription_topic` de webpush.db, que lee como root
   servidor/ntfy_suscriptores.py antes de esta unidad y deja en `ntfy_navegador.json`). Cada
   muestra va a `muestras_ntfy.jsonl` (40 días).
2. **Copia de la base de visitas**, una vez por hora: copia coherente de la base de GoatCounter
   (API de copia de SQLite, solo lectura), comprimida, al bucket privado del archivo
   (`visitas/ultima.sqlite.gz`, sustituida cuando cambia, y la primera de cada día en
   `visitas/diaria/AAAA-MM-DD.sqlite.gz`, que no se sobrescribe). La segunda copia de Helsinki
   (almacen/replica.py) la lleva cifrada como el resto del archivo.
3. **Resumen diario**, a partir de las 08:00 de Madrid: el del día anterior (00:00 a 24:00 de
   Madrid) al tema privado `lucas-resumen`, una sola vez. Si el envío falla, la pasada siguiente
   (5 minutos después) lo repite; si a las 09:00 de Madrid no ha salido, la vigilancia lo da como
   problema (`resumen`).

Qué cuenta GoatCounter: cada página vista con su sesión, un número aleatorio que dura 8 horas y no
lleva la dirección IP (servidor/goatcounter_ajustes.py). Visitas = páginas vistas; visitantes
únicos = sesiones distintas del día (una persona que vuelve pasadas 8 horas cuenta dos veces).

Lo que se anota queda en `$SECRETOS/visitas.json`, que lee la vigilancia.

Uso: python -m recogida.visitas pasada
     python -m recogida.visitas comprobar
     python -m recogida.visitas resumen --dia AAAA-MM-DD [--tema <tema de pruebas>] [--ensayo]
     python -m recogida.visitas restaurar --destino <fichero> [--objeto <clave>]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as hora
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from almacen.sitio import casa
from proceso import autoridades
from recogida import avisos as avisos_ntfy

registro = logging.getLogger("visitas")

Documento = dict[str, Any]
Enviar = Callable[[Documento], None]
Ejecutar = Callable[[Sequence[str]], str]

RAIZ = Path(__file__).resolve().parent.parent
MADRID = ZoneInfo("Europe/Madrid")
HORA_RESUMEN = hora(8, 0)
# Pasada esta hora de Madrid sin el resumen del día anterior, la vigilancia lo da como problema.
HORA_LIMITE_RESUMEN = hora(9, 0)
TEMA_RESUMEN = "lucas-resumen"
TITULO = "EODI · Resumen diario"
PANEL = "https://stats.droneobservatory.eu/"
URL_ESTADO_GOATCOUNTER = "https://stats.droneobservatory.eu/status"
URL_METRICAS = "http://127.0.0.1:9095/metrics"
URL_SALUD = "https://droneobservatory-almacen.nbg1.your-objectstorage.com/salud.json"
UNIDAD_RECOGIDA = "eodi-recogida.service"
# Registro de la vigilancia (recogida/vigilancia.py): lo que se arregló solo.
VIGILANCIA = "vigilancia.json"
CONTROL = "control.json"
# Registro del guardián del sistema (recogida/guardian.py), de lectura para todos.
GUARDIAN = Path(os.environ.get("EODI_GUARDIAN_ESTADO", "/var/lib/eodi-guardian/estado.json"))
ESTADO = "visitas.json"
MUESTRAS = "muestras_ntfy.jsonl"
NAVEGADOR = "ntfy_navegador.json"
PUBLICADOS = "publicados.json"
DIAS_MUESTRAS = 40
CADA_COPIA = timedelta(minutes=55)
COPIA_ULTIMA = "visitas/ultima.sqlite.gz"
COPIA_DIARIA = "visitas/diaria/{dia}.sqlite.gz"
INTENTOS_ENVIO = 3
TIEMPO_ESPERA_S = 15
LIMITE = 5

# Procedencias por dominio del referente (sin «www.»): el nombre que sale en el resumen.
PROCEDENCIAS = (
    (r"(^|\.)(linkedin\.com|lnkd\.in)$", "LinkedIn"),
    (r"(^|\.)google\.[a-z.]+$", "Google"),
    (r"(^|\.)bing\.com$", "Bing"),
    (r"(^|\.)duckduckgo\.com$", "DuckDuckGo"),
    (r"(^|\.)(yahoo\.com|search\.yahoo\.com)$", "Yahoo"),
    (r"(^|\.)(ecosia\.org)$", "Ecosia"),
    (r"(^|\.)(t\.co|x\.com|twitter\.com)$", "X"),
    (r"(^|\.)(facebook\.com|fb\.com|m\.facebook\.com|l\.facebook\.com)$", "Facebook"),
    (r"(^|\.)(instagram\.com)$", "Instagram"),
    (r"(^|\.)(reddit\.com)$", "Reddit"),
    (r"(^|\.)(bsky\.app)$", "Bluesky"),
    (r"(^|\.)(t\.me|telegram\.org)$", "Telegram"),
    (r"(^|\.)(whatsapp\.com|wa\.me)$", "WhatsApp"),
    (r"(^|\.)(github\.com)$", "GitHub"),
    (r"(^|\.)droneobservatory\.eu$", "La propia web"),
)
# Países que no son de configuracion/avisos.json (que trae los de Europa en español).
PAISES_FUERA = {
    "US": "Estados Unidos",
    "CA": "Canadá",
    "MX": "México",
    "AR": "Argentina",
    "BR": "Brasil",
    "CL": "Chile",
    "CO": "Colombia",
    "PE": "Perú",
    "VE": "Venezuela",
    "UY": "Uruguay",
    "CN": "China",
    "JP": "Japón",
    "KR": "Corea del Sur",
    "IN": "India",
    "PK": "Pakistán",
    "ID": "Indonesia",
    "SG": "Singapur",
    "TH": "Tailandia",
    "VN": "Vietnam",
    "PH": "Filipinas",
    "AU": "Australia",
    "NZ": "Nueva Zelanda",
    "IL": "Israel",
    "SA": "Arabia Saudí",
    "AE": "Emiratos Árabes Unidos",
    "QA": "Catar",
    "IR": "Irán",
    "IQ": "Irak",
    "EG": "Egipto",
    "MA": "Marruecos",
    "DZ": "Argelia",
    "TN": "Túnez",
    "ZA": "Sudáfrica",
    "NG": "Nigeria",
    "KE": "Kenia",
    "KZ": "Kazajistán",
    "RU": "Rusia",
    "BY": "Bielorrusia",
    "TW": "Taiwán",
    "HK": "Hong Kong",
}
MOVILES = frozenset({"Android", "iOS", "iPadOS"})
ANCHO_MOVIL = 768


# --- Utilidades -------------------------------------------------------------------------------
def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instante(texto: Any) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def _leer_json(ruta: Path) -> Documento:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _escribir_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def limites_del_dia(dia: date) -> tuple[datetime, datetime]:
    """Inicio y fin (UTC) del día de Madrid, con el cambio de hora incluido."""
    inicio = datetime.combine(dia, hora(0), MADRID)
    fin = datetime.combine(dia + timedelta(days=1), hora(0), MADRID)
    return inicio.astimezone(UTC), fin.astimezone(UTC)


def _sql_utc(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def numero(n: float) -> str:
    """Número con el punto de los miles, como se escribe en español."""
    return f"{n:,.0f}".replace(",", ".")


def comparacion(nombre: str, actual: float, referencia: float | None) -> str:
    """«día anterior 100, +20 %»: la cifra de referencia y el cambio (sin cambio si era 0)."""
    if referencia is None:
        return f"{nombre} sin datos"
    cifra = (
        numero(referencia)
        if referencia == int(referencia)
        else f"{referencia:.1f}".replace(".", ",")
    )
    texto = f"{nombre} {cifra}"
    if referencia == 0:
        return texto
    pct = round(100 * (actual - referencia) / referencia)
    return f"{texto}, {'+' if pct > 0 else ''}{pct} %"


# --- Visitas (base de GoatCounter, solo lectura) ----------------------------------------------
@dataclass
class Visitas:
    visitas: int = 0
    visitantes: int = 0
    paginas: list[tuple[str, int]] = field(default_factory=list)
    procedencias: list[tuple[str, int]] = field(default_factory=list)
    paises: list[tuple[str, int]] = field(default_factory=list)
    movil: int = 0
    ordenador: int = 0


def abrir_goatcounter(ruta: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)


def totales(conexion: sqlite3.Connection, dia: date) -> tuple[int, int]:
    inicio, fin = limites_del_dia(dia)
    fila = conexion.execute(
        "select count(*), count(distinct session) from hits"
        " where created_at >= ? and created_at < ?",
        (_sql_utc(inicio), _sql_utc(fin)),
    ).fetchone()
    return int(fila[0]), int(fila[1])


def procedencia(ref: str, esquema: str) -> str:
    """El nombre de la procedencia de un referente de GoatCounter (`ref` sin esquema; esquema «g» =
    agrupado por GoatCounter, «c» = campaña)."""
    if not ref:
        return "Directo"
    if esquema == "c":
        return f"Campaña {ref}"
    if esquema == "g":
        # GoatCounter ya agrupa los conocidos con su nombre («Google», «LinkedIn»…).
        return ref
    servidor = ref.split("/", 1)[0].lower().removeprefix("www.")
    for patron, nombre in PROCEDENCIAS:
        if re.search(patron, servidor):
            return nombre
    return servidor


def nombre_pais(codigo: str, nombres: dict[str, str], ingles: str) -> str:
    if not codigo:
        return "Desconocido"
    return nombres.get(codigo) or PAISES_FUERA.get(codigo) or ingles or codigo


def nombres_paises() -> dict[str, str]:
    config = avisos_ntfy.configuracion()
    return {codigo: datos["es"] for codigo, datos in config["paises"].items()}


def visitas_del_dia(conexion: sqlite3.Connection, dia: date) -> Visitas:
    inicio, fin = limites_del_dia(dia)
    rango = (_sql_utc(inicio), _sql_utc(fin))
    resultado = Visitas()
    resultado.visitas, resultado.visitantes = totales(conexion, dia)
    resultado.paginas = [
        (str(p), int(n))
        for p, n in conexion.execute(
            "select p.path, count(*) from hits h join paths p using (path_id)"
            " where h.created_at >= ? and h.created_at < ? and p.event = 0"
            " group by p.path order by 2 desc, 1 limit ?",
            (*rango, LIMITE),
        )
    ]
    # Procedencia y país de cada visitante: los de su primera página del día.
    primeras = conexion.execute(
        "select h.session, r.ref, r.ref_scheme, h.location, coalesce(s.name, ''), h.width"
        " from hits h join refs r using (ref_id) left join systems s using (system_id)"
        " where h.hit_id in (select min(hit_id) from hits"
        "   where created_at >= ? and created_at < ? group by session)",
        rango,
    ).fetchall()
    ingles = dict(conexion.execute("select country, country_name from locations where region = ''"))
    nombres = nombres_paises()
    origenes: Counter[str] = Counter()
    paises: Counter[str] = Counter()
    for _sesion, ref, esquema, lugar, sistema, ancho in primeras:
        origenes[procedencia(str(ref or ""), str(esquema or ""))] += 1
        codigo = str(lugar or "").split("-", 1)[0]
        paises[nombre_pais(codigo, nombres, str(ingles.get(codigo, "")))] += 1
        if sistema in MOVILES or (ancho is not None and 0 < int(ancho) < ANCHO_MOVIL):
            resultado.movil += 1
        else:
            resultado.ordenador += 1
    resultado.procedencias = origenes.most_common(LIMITE)
    resultado.paises = paises.most_common(LIMITE)
    return resultado


# --- Suscriptores de ntfy ---------------------------------------------------------------------
def leer_metricas(url: str = URL_METRICAS) -> dict[str, float]:
    with urllib.request.urlopen(url, timeout=10) as respuesta:
        texto = respuesta.read().decode("utf-8")
    valores: dict[str, float] = {}
    for linea in texto.splitlines():
        if linea.startswith("#") or " " not in linea:
            continue
        nombre, _, valor = linea.rpartition(" ")
        try:
            valores[nombre] = float(valor)
        except ValueError:
            continue
    return valores


def muestrear(datos: Path, ahora: datetime, metricas: Callable[[], dict[str, float]]) -> Documento:
    """Una muestra: suscriptores conectados y navegadores por canal; poda lo de más de 40 días."""
    valores = metricas()
    navegador = _leer_json(datos / NAVEGADOR).get("temas", {})
    muestra: Documento = {
        "momento": _iso(ahora),
        "suscriptores": int(valores.get("ntfy_subscribers_total", 0)),
        "temas": int(valores.get("ntfy_topics_total", 0)),
        "navegador": navegador if isinstance(navegador, dict) else {},
    }
    ruta = datos / MUESTRAS
    limite = ahora - timedelta(days=DIAS_MUESTRAS)
    lineas = []
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            try:
                anterior = json.loads(linea)
            except ValueError:
                continue
            momento = _instante(anterior.get("momento"))
            if momento is not None and momento >= limite:
                lineas.append(json.dumps(anterior, ensure_ascii=False))
    lineas.append(json.dumps(muestra, ensure_ascii=False))
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)
    return muestra


def muestras(datos: Path) -> list[Documento]:
    ruta = datos / MUESTRAS
    if not ruta.exists():
        return []
    lista = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        try:
            lista.append(json.loads(linea))
        except ValueError:
            continue
    return lista


@dataclass
class Suscriptores:
    conectados: int | None = None
    maximo: int | None = None
    anterior: int | None = None
    navegador_total: int = 0
    navegador_temas: list[tuple[str, int]] = field(default_factory=list)


def suscriptores_del_dia(lista: Iterable[Documento], dia: date) -> Suscriptores:
    """Al cierre del día (última muestra), el máximo del día y el cierre del día anterior."""
    inicio, fin = limites_del_dia(dia)
    inicio_antes, _ = limites_del_dia(dia - timedelta(days=1))
    del_dia, del_anterior = [], []
    for m in lista:
        momento = _instante(m.get("momento"))
        if momento is None:
            continue
        if inicio <= momento < fin:
            del_dia.append(m)
        elif inicio_antes <= momento < inicio:
            del_anterior.append(m)
    resultado = Suscriptores()
    if del_dia:
        ultima = max(del_dia, key=lambda m: str(m["momento"]))
        resultado.conectados = int(ultima.get("suscriptores", 0))
        resultado.maximo = max(int(m.get("suscriptores", 0)) for m in del_dia)
        temas = {str(k): int(v) for k, v in (ultima.get("navegador") or {}).items()}
        resultado.navegador_total = sum(temas.values())
        resultado.navegador_temas = sorted(temas.items(), key=lambda t: (-t[1], t[0]))[:LIMITE]
    if del_anterior:
        ultima = max(del_anterior, key=lambda m: str(m["momento"]))
        resultado.anterior = int(ultima.get("suscriptores", 0))
    return resultado


# --- Incidentes nuevos y avisos enviados ------------------------------------------------------
def _titulo_es(datos: Documento, id_: str) -> str:
    """El titular en español con las autoridades escritas como en la web y en los avisos (la
    tabla, la traducción que viaja con la ficha o «una autoridad»: proceso/autoridades.py)."""
    titulo = str((datos.get("titulo") or {}).get("es") or id_)
    return autoridades.en_texto(titulo, "es", datos.get("autoridades"))


def titulos_publicados(carpeta: Path) -> dict[str, str]:
    """Los incidentes en la web con su titular en español."""
    titulos: dict[str, str] = {}
    mapa = carpeta / avisos_ntfy.FICHEROS_PUBLICADOS[0]
    if mapa.exists():
        for rasgo in json.loads(mapa.read_text(encoding="utf-8")).get("features", []):
            props = rasgo.get("properties") or {}
            id_ = str(rasgo.get("id") or props.get("id"))
            titulos[id_] = _titulo_es(props, id_)
    sin_punto = carpeta / avisos_ntfy.FICHEROS_PUBLICADOS[1]
    if sin_punto.exists():
        for inc in json.loads(sin_punto.read_text(encoding="utf-8")).get("incidentes", []):
            titulos[str(inc["id"])] = _titulo_es(inc, str(inc["id"]))
    return titulos


def anotar_publicados(
    datos: Path,
    titulos: dict[str, str],
    ahora: datetime,
    altas: Callable[[set[str]], dict[str, str]],
) -> Documento:
    """Cuándo apareció cada incidente en la web por primera vez. La primera vez, los que ya están
    toman la hora de su alta en la base (lo más parecido que hay)."""
    ruta = datos / PUBLICADOS
    anotados: Documento = _leer_json(ruta)
    nuevos = set(titulos) - set(anotados)
    if not anotados and nuevos:
        iniciales = altas(nuevos)
        for id_ in nuevos:
            anotados[id_] = {"desde": iniciales.get(id_), "titulo": titulos[id_]}
    else:
        for id_ in nuevos:
            anotados[id_] = {"desde": _iso(ahora), "titulo": titulos[id_]}
    for id_, titulo in titulos.items():
        anotados[id_]["titulo"] = titulo
    if nuevos or not ruta.exists():
        _escribir_json(ruta, anotados)
    return anotados


def altas_en_la_base(base: Path) -> Callable[[set[str]], dict[str, str]]:
    def altas(ids: set[str]) -> dict[str, str]:
        if not base.exists():
            return {}
        documentos = avisos_ntfy.documentos(base, ids)
        return {
            id_: str(((doc.get("control") or {}).get("alta") or {}).get("valor") or "")
            for id_, doc in documentos.items()
        }

    return altas


def rectificaciones_del_dia(base: Path, dia: date) -> list[tuple[str, str]]:
    """Las rectificaciones oficiales de la presencia del dron que decidió ese día el experto
    (recogida/rectificaciones.py), con su tipo: (incidente, no_acreditada | descartada |
    parcial). Leídas sin escribir en la base; vacío si no se puede leer."""
    if not base.exists():
        return []
    inicio, fin = limites_del_dia(dia)
    try:
        conexion = sqlite3.connect(f"{base.resolve().as_uri()}?mode=ro", uri=True)
        try:
            filas = conexion.execute(
                "SELECT documento FROM control_fichas WHERE clave LIKE 'rectificacion:%' "
                "AND fecha >= ? AND fecha < ? ORDER BY id",
                (_iso(inicio), _iso(fin)),
            ).fetchall()
        finally:
            conexion.close()
    except sqlite3.Error as error:
        registro.warning("rectificaciones sin leer: %s", error)
        return []
    resultado = []
    for (documento,) in filas:
        decision = json.loads(documento)
        if decision.get("tipo"):
            resultado.append((str(decision.get("incidente")), str(decision["tipo"])))
    return resultado


def nuevos_del_dia(anotados: Documento, dia: date) -> list[tuple[str, str]]:
    inicio, fin = limites_del_dia(dia)
    lista = []
    for id_, dato in anotados.items():
        momento = _instante((dato or {}).get("desde"))
        if momento is not None and inicio <= momento < fin:
            lista.append((momento, id_, str(dato.get("titulo"))))
    return [(id_, titulo) for _, id_, titulo in sorted(lista)]


def avisos_del_dia(ruta: Path, dia: date) -> tuple[int, int]:
    """Mensajes de aviso enviados ese día (uno por canal) y a cuántos incidentes."""
    if not ruta.exists():
        return 0, 0
    inicio, fin = limites_del_dia(dia)
    conexion = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)
    try:
        fila = conexion.execute(
            "select count(*), count(distinct id) from avisos"
            " where inicial = 0 and momento >= ? and momento < ?",
            (_iso(inicio), _iso(fin)),
        ).fetchone()
    finally:
        conexion.close()
    return int(fila[0]), int(fila[1])


# --- Estado del sistema -----------------------------------------------------------------------
def _ejecutar(orden: Sequence[str]) -> str:
    """La salida de la orden; si no se puede ejecutar (o tarda), vacía: el resumen sale igual."""
    try:
        salida = subprocess.run(
            list(orden), capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        registro.warning("%s sin ejecutar: %s", orden[0], error)
        return ""
    return salida.stdout


def recogidas_del_dia(dia: date, ejecutar: Ejecutar = _ejecutar) -> tuple[int, int, int]:
    """Recogidas del día: correctas (código 0), con avisos (2, publican igual) y fallidas."""
    inicio, fin = limites_del_dia(dia)
    texto = ejecutar(
        [
            "journalctl", "-u", UNIDAD_RECOGIDA, "--since", f"@{int(inicio.timestamp())}",
            "--until", f"@{int(fin.timestamp())}", "-o", "cat", "--no-pager",
        ]
    )  # fmt: skip
    return contar_recogidas(texto.splitlines())


def diario_del_dia(dia: date, ejecutar: Ejecutar = _ejecutar) -> list[str]:
    inicio, fin = limites_del_dia(dia)
    return ejecutar(
        [
            "journalctl", "-u", UNIDAD_RECOGIDA, "--since", f"@{int(inicio.timestamp())}",
            "--until", f"@{int(fin.timestamp())}", "-o", "cat", "--no-pager",
        ]
    ).splitlines()  # fmt: skip


def contar_recogidas(lineas: Iterable[str]) -> tuple[int, int, int]:
    correctas = con_avisos = fallidas = 0
    for linea in lineas:
        if f"{UNIDAD_RECOGIDA}: Deactivated successfully" in linea:
            correctas += 1
        elif m := re.search(
            rf"{re.escape(UNIDAD_RECOGIDA)}: Main process exited, .*status=(\d+)", linea
        ):
            if m[1] == "2":
                con_avisos += 1
            elif m[1] != "0":
                fallidas += 1
        elif f"{UNIDAD_RECOGIDA}: Failed with result 'timeout'" in linea:
            fallidas += 1
    return correctas, con_avisos, fallidas


def reintentos_del_dia(dia: date, ejecutar: Ejecutar = _ejecutar) -> dict[str, int]:
    """Reintentos que systemd hizo solo ese día, por unidad (servidor/reintentos.sh)."""
    inicio, fin = limites_del_dia(dia)
    texto = ejecutar(
        [
            "journalctl", "-u", "eodi-*", "-u", "goatcounter.service", "-u", "ntfy.service",
            "-u", "caddy.service", "--since", f"@{int(inicio.timestamp())}",
            "--until", f"@{int(fin.timestamp())}", "-o", "cat", "--no-pager",
        ]
    )  # fmt: skip
    return contar_reintentos(texto.splitlines())


def contar_reintentos(lineas: Iterable[str]) -> dict[str, int]:
    cuenta: dict[str, int] = {}
    for linea in lineas:
        if m := re.search(r"([\w.@-]+)\.service: Scheduled restart job", linea):
            cuenta[m[1]] = cuenta.get(m[1], 0) + 1
    return dict(sorted(cuenta.items()))


def candidatos_del_dia(lineas: Iterable[str]) -> tuple[int, int]:
    """Candidatos que el extractor apartó por un fallo propio y los que retiró, en el diario."""
    apartados = retirados = 0
    for linea in lineas:
        if re.search(r"candidato \S+ apartado en esta recogida", linea):
            apartados += 1
        elif re.search(r"candidato \S+ retirado:", linea):
            retirados += 1
    return apartados, retirados


def resueltos_del_dia(vigilancia_json: Path, dia: date) -> list[tuple[str, bool]]:
    """Lo que la vigilancia vio y se fue ese día (recogida/vigilancia.py, `resueltos`): la frase y
    si llegó a abrir incidencia."""
    inicio, fin = limites_del_dia(dia)
    resueltos = []
    for r in _leer_json(vigilancia_json).get("resueltos", []):
        hasta = _instante(r.get("hasta")) if isinstance(r, dict) else None
        if hasta is not None and inicio <= hasta < fin:
            resueltos.append((str(r.get("frase") or r.get("id")), bool(r.get("incidencia"))))
    return resueltos


# Clase de cada corrección del control de las fichas, por cómo empieza su motivo.
CLASES_CONTROL = (
    ("lugar", "lugar"), ("drones", "drones"), ("presencia", "presencia"),
    ("cierre", "cierre"), ("duración", "duración del cierre"), ("hora", "hora"),
    ("día", "día"), ("estado", "estado"),
)  # fmt: skip


def control_del_dia(control_json: Path, dia: date) -> Documento | None:
    """Lo que hizo ese día el control de las fichas (recogida/control_fichas.py): las fichas que
    corrigió y por qué, los duplicados que unió, las que retuvo y lo que gastó. None si no hay
    registro."""
    datos = _leer_json(control_json)
    if not datos:
        return None
    inicio, fin = limites_del_dia(dia)
    corregidas: dict[str, list[str]] = {}
    unidos: list[str] = []
    retenidas: set[str] = set()
    liberadas: set[str] = set()
    gasto = 0.0
    pasadas = errores = 0
    for pasada in datos.get("pasadas", []):
        momento = _instante(pasada.get("fecha"))
        if momento is None or not inicio <= momento < fin:
            continue
        pasadas += 1
        for id_, motivos in (pasada.get("corregidos") or {}).items():
            corregidas.setdefault(id_, []).extend(str(m) for m in motivos)
        unidos += [str(u) for u in pasada.get("unidos") or []]
        retenidas |= set(pasada.get("retenidos") or {})
        liberadas |= set(pasada.get("liberados") or {})
        gasto += float(pasada.get("gasto") or 0)
        errores += 1 if pasada.get("parada") == "error" else 0
    clases: dict[str, int] = {}
    for motivos in corregidas.values():
        partes = {p.strip() for m in motivos for p in m.split(";")}
        for nombre, prefijo in CLASES_CONTROL:
            if any(p.startswith(prefijo) for p in partes):
                clases[nombre] = clases.get(nombre, 0) + 1
    return {
        "pasadas": pasadas, "corregidas": corregidas, "clases": clases, "unidos": unidos,
        "retenidas": sorted(retenidas), "liberadas": sorted(liberadas), "gasto": gasto,
        "errores": errores, "fallos_seguidos": int(datos.get("fallos_seguidos") or 0),
        "modelos": (datos.get("modelos") or {}).get(dia.isoformat()),
        "experto": (datos.get("experto") or {}).get(dia.isoformat()),
        "criticos_esperando": list(datos.get("criticos_esperando") or []),
    }  # fmt: skip


def lineas_control(control: Documento | None) -> list[str]:
    """Las líneas del control de las fichas en la sección SISTEMA."""
    if control is None:
        return ["  Control de fichas: sin registro"]
    if not control["pasadas"]:
        return ["  Control de fichas: no pasó ese día"]
    clases = ", ".join(f"{k} {v}" for k, v in control["clases"].items())
    lineas = [
        f"  Control de fichas: {len(control['corregidas'])} fichas corregidas"
        + (f" ({clases})" if clases else "")
        + f", {len(control['unidos'])} duplicados unidos, {len(control['retenidas'])} retenidas"
        + f", gasto {control['gasto']:.4f} USD".replace(".", ",")
    ]
    lineas += [f"  - unido {u}" for u in control["unidos"][:LIMITE]]
    for id_, motivos in list(control["corregidas"].items())[:LIMITE]:
        lineas.append(f"  - {id_}: {'; '.join(dict.fromkeys(motivos))[:160]}")
    if control["retenidas"]:
        lineas.append(f"  Retenidas por el control: {', '.join(control['retenidas'][:LIMITE])}")
    if control["errores"]:
        lineas.append(f"  El control falló en {control['errores']} pasadas")
    return lineas + lineas_modelos(control.get("modelos")) + lineas_experto(control)


def lineas_experto(control: Documento) -> list[str]:
    """El gasto del experto ese día (UTC) en su tope normal y en la reserva crítica, y los casos
    críticos que esperan ahora al experto (se reintentan en cada recogida)."""
    lineas = []
    experto = control.get("experto")
    if experto:
        lineas.append(
            "  Experto: tope normal "
            + f"{float(experto['normal']):.4f} de {float(experto['limite']):.2f} USD; reserva "
            f"crítica {float(experto['reserva']):.4f} de {float(experto['reserva_limite']):.2f} "
            "USD".replace(".", ",")
        )
    esperando = control.get("criticos_esperando") or []
    if esperando:
        lineas.append(
            f"  Casos críticos esperando al experto: {len(esperando)} (se reintentan en cada "
            "recogida)"
        )
        lineas += [f"  - {c['clave'][:120]} desde {c['desde']}" for c in esperando[:LIMITE]]
    return lineas


# Los papeles de los modelos (docs/modelos.md), en el orden en que se cuentan.
PAPELES = (("base", "modelo base"), ("experto", "modelo experto"), ("anterior", "modelo anterior"))


def lineas_modelos(modelos: Documento | None) -> list[str]:
    """Las llamadas de cada modelo ese día, cuántas se escalaron al experto y lo que costó cada
    uno (todas las llamadas del observatorio, no solo las del control)."""
    if modelos is None:
        return ["  Modelos: sin registro"]
    if not modelos:
        return ["  Modelos: ninguna llamada"]
    partes = []
    for clave, nombre in PAPELES:
        cuenta = modelos.get(clave)
        if not cuenta:
            continue
        texto = f"{nombre} {numero(int(cuenta['llamadas']))} llamadas"
        if clave == "experto":
            texto += f" ({numero(int(cuenta['escaladas']))} escaladas)"
        texto += f", {cuenta['coste']:.4f} USD".replace(".", ",")
        partes.append(texto)
    total = sum(float(c.get("coste") or 0) for c in modelos.values())
    return [f"  Modelos: {'; '.join(partes)}; total " + f"{total:.4f} USD".replace(".", ",")]


def guardian_del_dia(ruta: Path, dia: date) -> Documento:
    """Lo que hizo ese día el guardián del sistema: reparaciones (hora, frase, si salió bien) y
    arranques del servidor (los suyos de último recurso, los de fuera y los manuales)."""
    estado = _leer_json(ruta)
    if not estado:
        return {"sin_registro": True, "reparaciones": [], "arranques": []}
    inicio, fin = limites_del_dia(dia)

    def del_dia(texto: Any) -> datetime | None:
        momento = _instante(texto)
        return momento if momento is not None and inicio <= momento < fin else None

    reparaciones = [
        (m, str(r.get("frase")), bool(r.get("correcto")))
        for r in estado.get("reparaciones", [])
        if isinstance(r, dict) and (m := del_dia(r.get("hora")))
    ]
    arranques = [m for a in estado.get("arranques", []) if (m := del_dia(a))]
    return {"sin_registro": False, "reparaciones": reparaciones, "arranques": arranques}


def lineas_guardian(guardian: Documento | None) -> list[str]:
    """Las líneas del guardián del sistema en la sección SISTEMA (horas de Madrid)."""
    if guardian is None:
        return []
    if guardian["sin_registro"]:
        return ["  Guardián del sistema: sin registro"]
    reparaciones, arranques = guardian["reparaciones"], guardian["arranques"]
    malas = sum(1 for _, _, correcto in reparaciones if not correcto)
    lineas = [
        f"  Guardián del sistema: {len(reparaciones)} reparaciones"
        + (f" ({malas} sin conseguirlo)" if malas else "")
    ]
    for momento, frase, correcto in reparaciones[:LIMITE]:
        hora = momento.astimezone(MADRID).strftime("%H:%M")
        lineas.append(f"  - {hora} {'' if correcto else 'SIN ARREGLAR: '}{frase[:160]}")
    if arranques:
        horas = ", ".join(m.astimezone(MADRID).strftime("%H:%M") for m in arranques)
        lineas.append(f"  Arranques del servidor: {len(arranques)} ({horas})")
    return lineas


def problemas_abiertos(url: str = URL_SALUD) -> list[str] | None:
    """Los problemas abiertos de la vigilancia (salud.json), o None si no se puede leer."""
    try:
        with urllib.request.urlopen(url, timeout=15) as respuesta:
            salud = json.loads(respuesta.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return [str(p.get("frase") or p.get("id")) for p in salud.get("problemas", [])]


# --- El resumen -------------------------------------------------------------------------------
@dataclass
class Datos:
    dia: date
    visitas: Visitas | None
    anterior: tuple[int, int] | None
    media7: tuple[float, float] | None
    suscriptores: Suscriptores
    nuevos: list[tuple[str, str]]
    avisos: tuple[int, int]
    recogidas: tuple[int, int, int]
    problemas: list[str] | None
    # Lo que se arregló solo ese día: reintentos de systemd por unidad, lo que la vigilancia vio y
    # se fue (frase, si abrió incidencia) y los candidatos apartados y retirados por el extractor.
    reintentos: dict[str, int] = field(default_factory=dict)
    resueltos: list[tuple[str, bool]] = field(default_factory=list)
    candidatos: tuple[int, int] = (0, 0)
    # Lo que hizo el control de las fichas ese día (control_del_dia).
    control: Documento | None = None
    # Lo que hizo ese día el guardián del sistema (guardian_del_dia).
    guardian: Documento | None = None
    # Las rectificaciones oficiales de la presencia decididas ese día (rectificaciones_del_dia).
    rectificaciones: list[tuple[str, str]] = field(default_factory=list)


DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
    "octubre", "noviembre", "diciembre",
)  # fmt: skip


def fecha_larga(dia: date) -> str:
    return f"{DIAS_SEMANA[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def _lista(elementos: Sequence[tuple[str, int]], vacia: str) -> list[str]:
    if not elementos:
        return [f"  {vacia}"]
    return [f"  {i}. {nombre}: {numero(n)}" for i, (nombre, n) in enumerate(elementos, 1)]


def texto_resumen(d: Datos) -> str:
    """El cuerpo del aviso, en texto plano (sin emoticonos ni Markdown)."""
    lineas = [f"Datos del {fecha_larga(d.dia)} (hora de Madrid).", ""]
    v = d.visitas
    if v is None:
        lineas += ["VISITAS", "  No se pudo leer el contador de visitas.", ""]
    else:
        antes, media = d.anterior, d.media7
        lineas += [
            "VISITAS",
            f"  Visitas: {numero(v.visitas)} ("
            + comparacion("día anterior", v.visitas, antes[0] if antes else None)
            + "; "
            + comparacion("media de 7 días", v.visitas, media[0] if media else None)
            + ")",
            f"  Visitantes únicos: {numero(v.visitantes)} ("
            + comparacion("día anterior", v.visitantes, antes[1] if antes else None)
            + "; "
            + comparacion("media de 7 días", v.visitantes, media[1] if media else None)
            + ")",
            "",
            "Páginas más vistas",
            *_lista(v.paginas, "ninguna"),
            "",
            "Procedencias",
            *_lista(v.procedencias, "ninguna"),
            "",
            "Países",
            *_lista(v.paises, "ninguno"),
            "",
        ]
        total = v.movil + v.ordenador
        if total:
            pct = round(100 * v.movil / total)
            lineas += [
                f"Dispositivos: móvil {pct} % ({numero(v.movil)}), ordenador {100 - pct} % "
                f"({numero(v.ordenador)})",
                "",
            ]
        else:
            lineas += ["Dispositivos: sin visitantes", ""]
    s = d.suscriptores
    lineas.append("AVISOS (ntfy)")
    if s.conectados is None:
        lineas.append("  Suscriptores: sin muestras ese día")
    else:
        diferencia = "sin dato del día anterior"
        if s.anterior is not None:
            delta = s.conectados - s.anterior
            diferencia = f"{'+' if delta > 0 else ''}{delta} respecto al día anterior"
        lineas.append(
            f"  Suscriptores conectados al cierre: {numero(s.conectados)} ({diferencia}; "
            f"máximo del día {numero(s.maximo or 0)})"
        )
        if s.navegador_temas:
            canales = ", ".join(f"{t} {n}" for t, n in s.navegador_temas)
            lineas.append(f"  Con notificaciones en el navegador: {s.navegador_total} ({canales})")
        else:
            lineas.append("  Con notificaciones en el navegador: ninguno")
    mensajes, incidentes = d.avisos
    lineas += [
        f"  Avisos enviados: {numero(mensajes)} mensajes de {numero(incidentes)} incidentes",
        "",
        f"INCIDENTES NUEVOS PUBLICADOS: {len(d.nuevos)}",
    ]
    lineas += [f"  {id_}: {titulo}" for id_, titulo in d.nuevos[:LIMITE]]
    if len(d.nuevos) > LIMITE:
        lineas.append(f"  y {len(d.nuevos) - LIMITE} más")
    if d.rectificaciones:
        nombres = {"no_acreditada": "no acreditada", "descartada": "descartada",
                   "parcial": "corrección parcial"}  # fmt: skip
        lineas += ["", f"RECTIFICACIONES OFICIALES DE LA PRESENCIA: {len(d.rectificaciones)}"]
        lineas += [f"  {id_}: {nombres.get(t, t)}" for id_, t in d.rectificaciones[:LIMITE]]
    correctas, con_avisos, fallidas = d.recogidas
    lineas += [
        "",
        "SISTEMA",
        f"  Recogidas: {correctas + con_avisos} correctas ({con_avisos} con avisos), "
        f"{fallidas} fallidas",
    ]
    if d.reintentos:
        total = sum(d.reintentos.values())
        detalle = ", ".join(f"{u.removeprefix('eodi-')} {n}" for u, n in d.reintentos.items())
        lineas.append(f"  Reintentos automáticos: {total} ({detalle})")
    else:
        lineas.append("  Reintentos automáticos: ninguno")
    apartados, retirados = d.candidatos
    if apartados or retirados:
        lineas.append(
            f"  Candidatos apartados por un fallo propio: {apartados}; retirados tras 3 fallos: "
            f"{retirados}"
        )
    if d.resueltos:
        solos = [f for f, incidencia in d.resueltos if not incidencia]
        cerradas = [f for f, incidencia in d.resueltos if incidencia]
        lineas.append(f"  Se arreglaron solos, sin incidencia: {len(solos)}")
        lineas += [f"  - {f[:160]}" for f in solos[:LIMITE]]
        if cerradas:
            lineas.append(f"  Con incidencia, ya cerrada: {len(cerradas)}")
            lineas += [f"  - {f[:160]}" for f in cerradas[:LIMITE]]
    lineas += lineas_control(d.control)
    lineas += lineas_guardian(d.guardian)
    if d.problemas is None:
        lineas.append("  Vigilancia: no se pudo leer salud.json")
    elif d.problemas:
        lineas.append(f"  Vigilancia: {len(d.problemas)} problemas abiertos")
        lineas += [f"  - {p[:160]}" for p in d.problemas[:LIMITE]]
    else:
        lineas.append("  Vigilancia: ningún problema abierto")
    return "\n".join(lineas)


def mensaje(d: Datos, tema: str) -> Documento:
    return {
        "topic": tema,
        "title": TITULO,
        "message": texto_resumen(d),
        "priority": 3,
        "click": PANEL,
        "icon": avisos_ntfy.configuracion()["icono"],
    }


def reunir(
    dia: date,
    goatcounter: Path,
    datos: Path,
    publicacion: Path,
    base: Path,
    avisos: Path,
    ahora: datetime,
    ejecutar: Ejecutar = _ejecutar,
    salud: Callable[[], list[str] | None] = problemas_abiertos,
    secretos: Path | None = None,
    guardian: Path | None = None,
) -> Datos:
    """Todo lo que lleva el resumen del día; lo que no se puede leer sale como «no se pudo»."""
    visitas = anterior = media7 = None
    try:
        conexion = abrir_goatcounter(goatcounter)
        try:
            visitas = visitas_del_dia(conexion, dia)
            anterior = totales(conexion, dia - timedelta(days=1))
            semana = [totales(conexion, dia - timedelta(days=n)) for n in range(1, 8)]
            media7 = (
                sum(s[0] for s in semana) / 7,
                sum(s[1] for s in semana) / 7,
            )
        finally:
            conexion.close()
    except sqlite3.Error as error:
        registro.warning("visitas sin leer: %s", error)
    try:
        anotados = anotar_publicados(
            datos, titulos_publicados(publicacion), ahora, altas_en_la_base(base)
        )
    except (OSError, ValueError, sqlite3.Error) as error:
        registro.warning("incidentes publicados sin leer: %s", error)
        anotados = _leer_json(datos / PUBLICADOS)
    try:
        enviados = avisos_del_dia(avisos, dia)
    except sqlite3.Error as error:
        registro.warning("avisos enviados sin leer: %s", error)
        enviados = (0, 0)
    return Datos(
        dia=dia,
        visitas=visitas,
        anterior=anterior,
        media7=media7,
        suscriptores=suscriptores_del_dia(muestras(datos), dia),
        nuevos=nuevos_del_dia(anotados, dia),
        avisos=enviados,
        recogidas=recogidas_del_dia(dia, ejecutar),
        problemas=salud(),
        reintentos=reintentos_del_dia(dia, ejecutar),
        resueltos=resueltos_del_dia(secretos / VIGILANCIA, dia) if secretos else [],
        candidatos=candidatos_del_dia(diario_del_dia(dia, ejecutar)),
        control=control_del_dia(secretos / CONTROL, dia) if secretos else None,
        guardian=guardian_del_dia(guardian, dia) if guardian else None,
        rectificaciones=rectificaciones_del_dia(base, dia),
    )


def enviar_con_reintentos(
    enviar: Enviar, cuerpo: Documento, dormir: Callable[[float], None] | None = None
) -> None:
    dormir = dormir or time.sleep
    espera = 2.0
    for intento in range(1, INTENTOS_ENVIO + 1):
        try:
            enviar(cuerpo)
            return
        except (urllib.error.URLError, OSError, ValueError):
            if intento == INTENTOS_ENVIO:
                raise
            dormir(espera)
            espera *= 2


# --- Copia de la base de visitas --------------------------------------------------------------
def instantanea(goatcounter: Path) -> bytes:
    """Copia coherente de la base de GoatCounter (API de copia de SQLite), comprimida."""
    with tempfile.TemporaryDirectory() as carpeta:
        destino = Path(carpeta) / "copia.sqlite3"
        origen = abrir_goatcounter(goatcounter)
        copia = sqlite3.connect(destino)
        try:
            origen.backup(copia)
        finally:
            copia.close()
            origen.close()
        return gzip.compress(destino.read_bytes(), compresslevel=9, mtime=0)


def destino_copia() -> Any:
    from almacen import copias, replica

    destino = replica.destino_archivo()
    return copias.Copias(destino, copias.Credenciales.cargar())


def copiar(goatcounter: Path, estado: Documento, ahora: datetime, cliente: Any) -> str:
    """Sube la copia si ha cambiado, y la primera de cada día; anota en `estado['copia']`."""
    anotado: Documento = estado.setdefault("copia", {})
    cuerpo = instantanea(goatcounter)
    huella = hashlib.sha256(cuerpo).hexdigest()
    hechos = []
    if anotado.get("sha256") != huella:
        cliente.subir(COPIA_ULTIMA, cuerpo)
        anotado["sha256"] = huella
        hechos.append("ultima")
    dia = ahora.date().isoformat()
    if anotado.get("diaria") != dia:
        clave = COPIA_DIARIA.format(dia=dia)
        if not cliente.existe(clave):
            cliente.subir(clave, cuerpo)
            hechos.append(f"diaria {dia}")
        anotado["diaria"] = dia
    anotado["ultima"] = _iso(ahora)
    anotado["tamano"] = len(cuerpo)
    return ", ".join(hechos) or "sin cambios"


def restaurar(cliente: Any, destino: Path, objeto: str = COPIA_ULTIMA) -> Documento:
    """Baja una copia (comprueba su huella), la descomprime en `destino` y comprueba la base."""
    cuerpo = cliente.bajar(objeto)
    destino.write_bytes(gzip.decompress(cuerpo))
    conexion = sqlite3.connect(destino)
    try:
        integra = conexion.execute("pragma integrity_check").fetchone()[0] == "ok"
        paginas = int(conexion.execute("select count(*) from hits").fetchone()[0])
    finally:
        conexion.close()
    if not integra:
        raise OSError(f"{objeto}: la base restaurada no pasa la comprobación de integridad")
    return {"objeto": objeto, "bytes": destino.stat().st_size, "paginas_vistas": paginas}


# --- La pasada de cada 5 minutos -------------------------------------------------------------
@dataclass
class Rutas:
    secretos: Path
    datos: Path
    goatcounter: Path
    publicacion: Path
    base: Path
    avisos: Path


def dia_pendiente(estado: Documento, ahora: datetime) -> date | None:
    """El día cuyo resumen toca enviar ahora (el anterior en Madrid), o None."""
    local = ahora.astimezone(MADRID)
    if local.time() < HORA_RESUMEN:
        return None
    dia = local.date() - timedelta(days=1)
    if (estado.get("resumen") or {}).get("dia") == dia.isoformat():
        return None
    return dia


def pasada(
    rutas: Rutas,
    ahora: datetime,
    enviar: Enviar | None,
    metricas: Callable[[], dict[str, float]] = leer_metricas,
    cliente_copia: Callable[[], Any] = destino_copia,
    ejecutar: Ejecutar = _ejecutar,
    salud: Callable[[], list[str] | None] = problemas_abiertos,
) -> Documento:
    ruta_estado = rutas.secretos / ESTADO
    estado = _leer_json(ruta_estado)
    rutas.datos.mkdir(parents=True, exist_ok=True)

    try:
        m = muestrear(rutas.datos, ahora, metricas)
        estado["muestra"] = {"momento": m["momento"], "suscriptores": m["suscriptores"]}
    except (OSError, ValueError) as error:
        registro.warning("suscriptores de ntfy sin muestra: %s", error)

    copia = estado.get("copia") or {}
    ultima = _instante(copia.get("ultima"))
    if ultima is None or ahora - ultima >= CADA_COPIA:
        try:
            registro.info(
                "copia de las visitas: %s",
                copiar(rutas.goatcounter, estado, ahora, cliente_copia()),
            )
            estado["copia"].pop("error", None)
        except (OSError, ValueError, sqlite3.Error) as error:
            estado.setdefault("copia", {})["error"] = f"{type(error).__name__}: {error}"[:200]
            registro.warning("copia de las visitas sin hacer: %s", error)

    dia = dia_pendiente(estado, ahora)
    if dia is not None and enviar is not None:
        resumen: Documento = dict(estado.get("resumen") or {})
        try:
            datos = reunir(
                dia, rutas.goatcounter, rutas.datos, rutas.publicacion, rutas.base,
                rutas.avisos, ahora, ejecutar, salud, rutas.secretos, GUARDIAN,
            )  # fmt: skip
            enviar_con_reintentos(enviar, mensaje(datos, TEMA_RESUMEN))
        except (urllib.error.URLError, OSError, ValueError, sqlite3.Error) as error:
            resumen["fallos_seguidos"] = int(resumen.get("fallos_seguidos", 0)) + 1
            resumen["error"] = f"{type(error).__name__}: {error}"[:200]
            resumen["ultimo_intento"] = _iso(ahora)
            registro.warning("resumen del %s sin enviar: %s", dia, resumen["error"])
        else:
            resumen = {"dia": dia.isoformat(), "enviado": _iso(ahora), "fallos_seguidos": 0}
            registro.info("resumen del %s enviado a %s", dia, TEMA_RESUMEN)
        estado["resumen"] = resumen
    elif rutas.publicacion.exists():
        # Sin resumen que enviar, se anota igual lo publicado para saber qué es nuevo cada día.
        try:
            anotar_publicados(
                rutas.datos, titulos_publicados(rutas.publicacion), ahora,
                altas_en_la_base(rutas.base),
            )  # fmt: skip
        except (OSError, ValueError, sqlite3.Error) as error:
            registro.warning("incidentes publicados sin anotar: %s", error)

    _escribir_json(ruta_estado, estado)
    return estado


# --- Vigilancia -------------------------------------------------------------------------------
def problemas_para_vigilancia(estado: Documento, ahora: datetime) -> list[dict[str, str]]:
    """El resumen del día anterior no ha salido a las 09:00 de Madrid, o la copia de la base de
    visitas tiene más de 3 horas."""
    problemas: list[dict[str, str]] = []
    local = ahora.astimezone(MADRID)
    resumen = estado.get("resumen") or {}
    esperado = (local.date() - timedelta(days=1)).isoformat()
    if local.time() >= HORA_LIMITE_RESUMEN and resumen.get("dia") != esperado:
        problemas.append({
            "id": "resumen",
            "frase": f"El resumen diario del {esperado} no se ha enviado a las "
            f"{HORA_LIMITE_RESUMEN:%H:%M} de Madrid"
            + (f" ({resumen['error']})" if resumen.get("error") else "")
            + ": se reintenta cada 5 minutos.",
        })  # fmt: skip
    copia = _instante((estado.get("copia") or {}).get("ultima"))
    if copia is None or ahora - copia > timedelta(hours=3):
        problemas.append({
            "id": "copia_visitas",
            "frase": "La última copia de la base de visitas es "
            + (f"del {copia:%Y-%m-%d %H:%M} UTC" if copia else "desconocida")
            + ": más de 3 horas sin copia.",
        })  # fmt: skip
    return problemas


def goatcounter_responde(intentos: int = 2, espera_s: float = 5) -> bool:
    """Si el contador de visitas responde a /status por su dirección pública."""
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(URL_ESTADO_GOATCOUNTER, timeout=10) as respuesta:
                if "version" in json.loads(respuesta.read().decode("utf-8")):
                    return True
        except (OSError, ValueError):
            pass
        if intento + 1 < intentos:
            time.sleep(espera_s)
    return False


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _codigo(url: str) -> int:
    """El código HTTP de una petición anónima, sin seguir redirecciones (0 si no responde)."""
    abridor = urllib.request.build_opener(_SinRedirecciones())
    try:
        with abridor.open(url, timeout=10) as respuesta:
            return int(respuesta.status)
    except urllib.error.HTTPError as error:
        return int(error.code)
    except OSError:
        return 0


PRIVADOS = (
    # (dirección, códigos que valen, qué quiere decir si no)
    (PANEL, {302, 303}, "el panel de visitas se abre sin usuario"),
    (
        PANEL.rstrip("/") + "/api/v0/stats/total",
        {401, 403},
        "la API de visitas responde sin usuario",
    ),
    (
        f"https://ntfy.droneobservatory.eu/{TEMA_RESUMEN}/json?poll=1",
        {401, 403},
        f"el tema {TEMA_RESUMEN} se lee sin el usuario «lucas»",
    ),
)


def fallos_de_privacidad(codigo: Callable[[str], int] = _codigo) -> list[str]:
    """Lo que debería ser privado y no lo es; una dirección que no responde no cuenta aquí (eso
    lo dicen los problemas «goatcounter» y «ntfy»)."""
    fallos = []
    for url, validos, frase in PRIVADOS:
        obtenido = codigo(url)
        if obtenido and obtenido not in validos:
            fallos.append(f"{frase} (HTTP {obtenido})")
    return fallos


# --- Órdenes ----------------------------------------------------------------------------------
def rutas_del_entorno() -> Rutas:
    secretos = Path(os.environ.get("EODI_SECRETOS") or casa() / ".eodi")
    return Rutas(
        secretos=secretos,
        datos=Path(os.environ.get("EODI_VISITAS_DATOS") or casa() / "datos" / "visitas"),
        goatcounter=Path(
            os.environ.get("EODI_GOATCOUNTER_BASE") or "/var/lib/goatcounter/goatcounter.sqlite3"
        ),
        publicacion=Path(
            os.environ.get("EODI_PUBLICACION_DIRECTORIO") or casa() / "datos" / "publicacion"
        ),
        base=Path(os.environ.get("EODI_BASE") or casa() / "base" / "eodi.sqlite"),
        avisos=Path(os.environ.get("EODI_AVISOS_DATOS") or casa() / "datos" / "avisos")
        / avisos_ntfy.BASE_AVISOS,
    )


def _enviador(secretos: Path) -> Enviar:
    token = (secretos / "ntfy_observatorio").read_text(encoding="utf-8").strip()
    return avisos_ntfy.enviador(avisos_ntfy.configuracion()["servidor"], token)


def principal(argumentos: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    analizador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = analizador.add_subparsers(dest="orden", required=True)
    sub.add_parser("pasada")
    sub.add_parser("comprobar", help="panel y tema privado cerrados sin usuario")
    r = sub.add_parser("resumen")
    r.add_argument("--dia", type=date.fromisoformat, required=True)
    r.add_argument("--tema", help="tema de pruebas (nunca el privado ni uno público)")
    r.add_argument("--ensayo", action="store_true", help="solo escribe el texto")
    rs = sub.add_parser("restaurar")
    rs.add_argument("--destino", type=Path, required=True)
    rs.add_argument("--objeto", default=COPIA_ULTIMA)
    args = analizador.parse_args(argumentos)
    rutas = rutas_del_entorno()
    ahora = datetime.now(UTC)

    if args.orden == "comprobar":
        fallos = fallos_de_privacidad()
        for url, validos, _frase in PRIVADOS:
            sys.stdout.write(f"{_codigo(url)} {url} (vale: {sorted(validos)})\n")
        sys.stdout.write("privado: " + ("; ".join(fallos) if fallos else "sí") + "\n")
        return 1 if fallos else 0
    if args.orden == "pasada":
        pasada(rutas, ahora, _enviador(rutas.secretos))
        return 0
    if args.orden == "restaurar":
        if args.destino.exists():
            registro.error("%s ya existe: no se sobrescribe", args.destino)
            return 1
        resultado = restaurar(destino_copia(), args.destino, args.objeto)
        sys.stdout.write(json.dumps(resultado, ensure_ascii=False) + "\n")
        return 0
    datos = reunir(
        args.dia, rutas.goatcounter, rutas.datos, rutas.publicacion, rutas.base, rutas.avisos,
        ahora, secretos=rutas.secretos, guardian=GUARDIAN,
    )  # fmt: skip
    if args.ensayo:
        sys.stdout.write(f"{TITULO}\n\n{texto_resumen(datos)}\n")
        return 0
    publicos = set(avisos_ntfy.temas_publicos(avisos_ntfy.configuracion()))
    if not args.tema or args.tema == TEMA_RESUMEN or args.tema in publicos:
        registro.error("el resumen de prueba solo va a un tema de pruebas")
        return 1
    enviar_con_reintentos(_enviador(rutas.secretos), mensaje(datos, args.tema))
    registro.info("resumen del %s enviado a %s", args.dia, args.tema)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
