"""Salud del servidor para la vigilancia externa: salud.json en el almacén público.

Cada 5 minutos (eodi-vigilancia.timer) se compone, con lo que hay en el propio servidor, un
resumen sin contenido de lo que hace falta para saber si todo va bien, y se sube al almacén
público como `salud.json`. Lo lee el workflow vigia-recogida cada 10 minutos
(recogida/salud.py): si el fichero deja de llegar, es que el servidor no está; si llega con un
problema, el workflow falla y el dueño recibe el correo de GitHub.

El observatorio se cura solo: cada servicio se reintenta (servidor/reintentos.sh) y la recogida
se repite a los 10 y a los 25 minutos si falla. Por eso un problema solo pasa a `problemas` (y el
vigía abre su incidencia, que llega por correo) cuando no se ha arreglado solo:

- la recogida, cuando las 3 últimas recogidas terminadas (cada una tras sus reintentos) han
  fallado; mientras una recogida está en marcha (o esperando su reintento) no se juzga: vale lo
  que dijeron las terminadas;
- la publicación, con más de 3 horas sin publicar;
- los demás, cuando siguen igual tras GRACIA (30 minutos, varios reintentos de su unidad), salvo
  los que no se arreglan solos por mucho que se espere (SIN_GRACIA).

Mientras tanto van en `avisos` como «en observación». Lo que estuvo y se fue queda en el registro
(`resueltos`, 8 días) para la sección SISTEMA del resumen diario privado (recogida/visitas.py), sin
correo.

Problemas (cada uno con su frase):

- **publicación**: la última recogida que publicó (código 0 o 2) terminó hace más de 3 horas;
- **recogida**: las 3 últimas recogidas terminadas (tras sus reintentos) fallaron con un código
  distinto de 0 y 2;
- **seguimiento**: la captura del seguimiento no ha recibido nada en 10 minutos o su unidad no
  está en marcha;
- **alertas**: el archivo de alertas de alerts.in.ua (recogida/alertas.py) no ha tenido una
  respuesta correcta de la API (200, o 304 sin cambios) en 15 minutos, o su unidad no está en
  marcha;
- **alertas_autorizacion**: la API de alerts.in.ua responde 401 o 403 (token no válido o IP
  bloqueada);
- **copia de la base**: la última copia cifrada de la base en el almacén privado tiene más de 2
  horas (solo con la base en el disco: modos `doble` y `disco`);
- **copia del archivo**: la última copia del archivo del seguimiento tiene más de 2 horas (se
  copia cada hora);
- **réplica**: la última pasada correcta de la segunda copia en otra ubicación (almacen/replica.py)
  tiene más de 3 horas;
- **reserva**: la copia pública de reserva del almacén de la web, en Helsinki (almacen/reserva.py),
  lleva más de 30 minutos sin estar al día;
- **disco**: el disco pasa del 75 % (el aviso llega antes del 80 %);
- **prueba de restauración**: la prueba semanal de restauración de la base falló o no hay una
  correcta en 8 días;
- **paso a solo disco**: el paso de la base a solo disco (almacen/solo_disco.py) no se hizo porque
  falló una de sus comprobaciones;
- **ntfy**: el servidor de los avisos públicos (https://ntfy.droneobservatory.eu) no responde a
  /v1/health (dos intentos), en el servidor que los tiene (con el token de «observatorio»);
- **avisos**: el envío de los avisos de ntfy (recogida/avisos.py) ha fallado dos recogidas
  seguidas;
- **certificados**: el certificado de https://ntfy.droneobservatory.eu o de
  https://stats.droneobservatory.eu caduca en menos de 14 días (Caddy los renueva solo a los 30:
  si llega a 14, la renovación está fallando), en el servidor que los tiene;
- **goatcounter**: el contador de visitas (https://stats.droneobservatory.eu) no responde a /status
  (dos intentos), en el servidor que lo tiene;
- **resumen**: el resumen diario privado del día anterior (recogida/visitas.py) no ha salido a las
  09:00 de Madrid;
- **copia_visitas**: la última copia de la base de visitas tiene más de 3 horas;
- **visitas_privadas**: el panel de visitas, su API o el tema privado del resumen responden sin
  usuario;
- **versiones**: la versión citable del mes de los datos abiertos no se ha generado el día 1
  (pasadas las 06:00 UTC), una versión publicada ha cambiado o falta, o no se comprueban desde
  hace 2 días (recogida/versiones.py);
- **barrera_resoluciones**: la barrera de titulares ha resuelto sola (a nivel de país o descartado
  como no verificable, recogida/barrera.py) más de 3 incidentes en 24 horas: señal de que el
  extractor elige mal las citas. Cada resolución por separado no es un problema;
- **barrera_atascada**: un incidente sigue retenido por la barrera más de 8 horas (la resolución
  automática tenía que haberlo despachado a las 6): la revisión de la barrera está fallando;
- **guardian**: el guardián del sistema (recogida/guardian.py) no ha podido arreglar algo (un
  dispositivo de /dev, /tmp, sshd, el disco por encima del 90 % tras limpiar, o dos recogidas
  seguidas que fallan por el sistema con el reinicio de último recurso ya gastado en 6 horas);
- **guardian_parado**: el guardián no ha pasado en 20 minutos (pasa cada 5);
- **experto_critico**: un caso crítico (docs/modelos.md) lleva más de 6 horas esperando al modelo
  experto (su tope y la reserva crítica agotados, o el experto fallando): se reintenta en cada
  recogida y, mientras no pasen 6 horas, solo sale en el resumen diario;
- **mapa_parado**: hay incidentes de Europa con punto dados de alta después del último cambio de
  incidentes.geojson y ese cambio tiene más de 24 horas: lo nuevo no llega al mapa.

Avisos (se ven, no son fallo): los problemas en observación, la última recogida falló pero aún no
van 3 seguidas, la última recogida terminó con avisos (código 2) y por qué (las
líneas de aviso de su diario: fuentes sin leer, tope de tiempo agotado), y cuántos incidentes
retiene la barrera de titulares (proceso/cita_titular.py). El fichero es público: no lleva
identificadores de incidentes sin publicar ni ningún contenido, solo horas, recuentos y frases
genéricas. El detalle queda en el diario de esta unidad.

El registro `~/.eodi/vigilancia.json` guarda la hora de la última publicación vista
(la recogida es horaria y esta unidad pasa cada 5 minutos: ve todas).

Uso: python -m recogida.vigilancia [--sin-subir] [--salida <fichero>]
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen import reserva
from almacen.sitio import casa
from recogida import almacen_publico, versiones, visitas
from recogida import avisos as avisos_ntfy

registro = logging.getLogger("vigilancia")

VERSION = 1
OBJETO = "salud.json"
CACHE = "public, max-age=60"
UNIDAD_RECOGIDA = "eodi-recogida.service"
UNIDAD_SEGUIMIENTO = "eodi-seguimiento.service"
UNIDAD_ALERTAS = "eodi-alertas.service"
SALIDAS_QUE_PUBLICAN = frozenset({0, 2})
MAX_SIN_PUBLICAR = timedelta(hours=3)
# Recogidas terminadas (cada una tras sus reintentos) que tienen que fallar seguidas.
MAX_RECOGIDAS_FALLIDAS = 3
RECOGIDAS_ANOTADAS = 24
# Memoria propia de la recogida (sin la caché de ficheros, que llega al tope sin ser un problema),
# medida por servidor/recogida.sh en memoria_recogida.json: problema desde este tanto del tope.
UMBRAL_MEMORIA = 0.8
# Tiempo que un problema tiene que seguir igual para no ser un fallo suelto que se arregla solo.
GRACIA = timedelta(minutes=30)
# Los que no se arreglan solos esperando, o que ya llevan su propia espera (publicación, recogida).
SIN_GRACIA = frozenset({
    "publicacion", "recogida", "visitas_privadas", "prueba_restauracion", "base_solo_disco",
    "versiones", "barrera_resoluciones", "barrera_atascada", "mapa_parado", "control_fichas",
})  # fmt: skip
DIAS_RESUELTOS = timedelta(days=8)
MAX_SIN_RECIBIR = timedelta(minutes=10)
# Las activas se consultan cada minuto: 15 minutos sin respuesta correcta son 15 consultas.
MAX_SIN_ALERTAS = timedelta(minutes=15)
MAX_SIN_COPIA = timedelta(hours=2)
MAX_SIN_COPIA_ARCHIVO = timedelta(hours=2)
MAX_SIN_REPLICA = timedelta(hours=3)
# Barrera de titulares (recogida/barrera.py): resoluciones automáticas en un día, retención que
# la resolución tenía que haber despachado y mapa sin cambiar con incidentes nuevos.
MAX_RESOLUCIONES_DIA = 3
MAX_RETENIDO = timedelta(hours=8)
MAX_MAPA_SIN_CAMBIAR = timedelta(hours=24)
BARRERA = "barrera.json"
# Control de calidad de las fichas (recogida/control_fichas.py): incidencia solo si el propio
# control falla varias pasadas seguidas (lo que corrige o retiene va al resumen diario).
CONTROL = "control.json"
MAX_FALLOS_CONTROL = 3
# Un caso crítico que espera al experto más de esto abre incidencia (antes, solo el resumen).
MAX_CRITICO_ESPERANDO = timedelta(hours=6)
DISCO_AVISO_PCT = 75.0
# Guardián del sistema (recogida/guardian.py): su registro y cuánto puede pasar sin una pasada.
GUARDIAN = Path(os.environ.get("EODI_GUARDIAN_ESTADO", "/var/lib/eodi-guardian/estado.json"))
MAX_SIN_GUARDIAN = timedelta(minutes=20)
# Líneas del diario de la recogida que explican un código 2 y las de la barrera de titulares.
AVISO_TOPE = re.compile(
    r"tope de \d+ s agotado|no se lee|sin leer: \d+|en rojo|paso fallido|apartado|retirado", re.I
)
RETENIDO = re.compile(r"(EODI-\d{4}-\d{5}) no se publica: su cita no respalda el titular")

URL_SALUD_NTFY = "https://ntfy.droneobservatory.eu/v1/health"
# Certificados que renueva Caddy en este servidor y días que tienen que quedar como mínimo.
CERTIFICADOS = ("ntfy.droneobservatory.eu", "stats.droneobservatory.eu")
MIN_DIAS_CERTIFICADO = 14
TOKEN_NTFY = "ntfy_observatorio"

Ejecutar = Callable[[Sequence[str]], str]


def ntfy_responde(intentos: int = 2, espera_s: float = 5) -> bool:
    """Si el servidor ntfy de los avisos dice que está sano; un fallo suelto no cuenta."""
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(URL_SALUD_NTFY, timeout=10) as respuesta:
                if json.loads(respuesta.read().decode("utf-8")).get("healthy") is True:
                    return True
        except (OSError, ValueError):
            pass
        if intento + 1 < intentos:
            time.sleep(espera_s)
    return False


def dias_de_certificado(host: str) -> float | None:
    """Días que le quedan al certificado del servidor, o None si no responde."""
    import socket
    import ssl

    try:
        contexto = ssl.create_default_context()
        with (
            socket.create_connection((host, 443), timeout=10) as conexion,
            contexto.wrap_socket(conexion, server_hostname=host) as segura,
        ):
            caduca = (segura.getpeercert() or {})["notAfter"]
    except (OSError, ssl.SSLError, KeyError):
        return None
    return (ssl.cert_time_to_seconds(str(caduca)) - time.time()) / 86400


def certificados_que_caducan(
    dias: Callable[[str], float | None] = dias_de_certificado,
) -> list[str]:
    """Los certificados de CERTIFICADOS a menos de MIN_DIAS_CERTIFICADO días (o caducados)."""
    fallos = []
    for host in CERTIFICADOS:
        quedan = dias(host)
        if quedan is not None and quedan < MIN_DIAS_CERTIFICADO:
            fallos.append(f"{host} ({quedan:.0f} días)")
    return fallos


def _ejecutar(orden: Sequence[str]) -> str:
    salida = subprocess.run(list(orden), capture_output=True, text=True, timeout=60, check=False)
    return salida.stdout


def _iso(momento: datetime | None) -> str | None:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ") if momento else None


def _instante(texto: Any) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _leer_json(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


# --- Lo que se mira -----------------------------------------------------------------------
def unidad(nombre: str, ejecutar: Ejecutar = _ejecutar) -> dict[str, Any]:
    """Estado de una unidad de systemd: activa, código de la última salida, inicio y fin."""
    texto = ejecutar(
        [
            "systemctl", "show", nombre, "--timestamp=unix", "-p", "ActiveState",
            "-p", "ExecMainStatus", "-p", "ExecMainStartTimestamp", "-p", "ExecMainExitTimestamp",
        ]
    )  # fmt: skip
    valores = dict(linea.split("=", 1) for linea in texto.splitlines() if "=" in linea)

    def momento(clave: str) -> datetime | None:
        valor = valores.get(clave, "").lstrip("@")
        return datetime.fromtimestamp(int(valor), UTC) if valor.isdigit() else None

    estado = valores.get("ExecMainStatus", "")
    return {
        "activa": valores.get("ActiveState", ""),
        "codigo": int(estado) if estado.isdigit() else None,
        "inicio": momento("ExecMainStartTimestamp"),
        "fin": momento("ExecMainExitTimestamp"),
    }


def diario_recogida(desde: datetime, ejecutar: Ejecutar = _ejecutar) -> list[str]:
    return ejecutar(
        [
            "journalctl", "-u", UNIDAD_RECOGIDA, "--since", f"@{int(desde.timestamp())}",
            "-o", "cat", "--no-pager",
        ]
    ).splitlines()  # fmt: skip


def avisos_del_diario(lineas: Sequence[str]) -> tuple[list[str], list[str]]:
    """Las frases de aviso de una recogida (sin repetir) y los incidentes retenidos."""
    avisos: list[str] = []
    retenidos: list[str] = []
    for linea in lineas:
        if m := RETENIDO.search(linea):
            if m[1] not in retenidos:
                retenidos.append(m[1])
            continue
        if AVISO_TOPE.search(linea):
            frase = re.sub(r"^(WARNING|INFO|ERROR) [\w.]+: ", "", linea.strip())
            frase = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:]+Z", "<hora>", frase)
            if frase not in avisos:
                avisos.append(frase[:200])
    return avisos, retenidos


def problemas_del_guardian(estado: dict[str, Any], ahora: datetime) -> list[dict[str, str]]:
    """Lo que el guardián del sistema no ha podido arreglar, y si ha dejado de pasar."""
    ultima = _instante(estado.get("ultima_pasada"))
    if ultima is None or ahora - ultima > MAX_SIN_GUARDIAN:
        cuando = "nunca" if ultima is None else f"el {ultima:%Y-%m-%d %H:%M} UTC"
        return [{
            "id": "guardian_parado",
            "frase": "El guardián del sistema no pasa desde hace más de 20 minutos (última "
            f"pasada: {cuando}).",
        }]  # fmt: skip
    frases = [str(p.get("frase")) for p in estado.get("sin_arreglar", []) if isinstance(p, dict)]
    if not frases:
        return []
    return [{"id": "guardian", "frase": "El guardián del sistema no lo ha arreglado: "
             + "; ".join(frases)[:400]}]  # fmt: skip


def problemas_del_control(estado: dict[str, Any]) -> list[dict[str, str]]:
    """El control de las fichas falla varias pasadas seguidas (control.json)."""
    fallos = int(estado.get("fallos_seguidos") or 0) if estado else 0
    if fallos < MAX_FALLOS_CONTROL:
        return []
    return [{
        "id": "control_fichas",
        "frase": f"El control de calidad de las fichas ha fallado {fallos} pasadas seguidas: lo "
        "nuevo se publica sin comprobar duplicados ni respaldo de los datos.",
    }]  # fmt: skip


def problemas_del_experto(estado: dict[str, Any], ahora: datetime) -> list[dict[str, str]]:
    """Casos críticos que llevan más de 6 horas esperando al experto (control.json), sin
    identificadores (salud.json es público)."""
    viejos = [
        c for c in (estado or {}).get("criticos_esperando") or []
        if (desde := _instante(c.get("desde"))) is not None
        and ahora - desde > MAX_CRITICO_ESPERANDO
    ]  # fmt: skip
    if not viejos:
        return []
    return [{
        "id": "experto_critico",
        "frase": f"{len(viejos)} casos críticos llevan más de 6 horas esperando al modelo experto "
        "(su tope y la reserva crítica agotados, o el experto fallando).",
    }]  # fmt: skip


def problemas_de_la_barrera(estado: dict[str, Any], ahora: datetime) -> list[dict[str, str]]:
    """Los problemas de la barrera de titulares en su estado (barrera.json), sin identificadores
    (salud.json es público)."""
    problemas: list[dict[str, str]] = []
    if not estado:
        return problemas
    dia = [
        r for r in estado.get("resoluciones", [])
        if (cuando := _instante(r.get("fecha"))) is not None and ahora - cuando <= timedelta(days=1)
    ]  # fmt: skip
    if len(dia) > MAX_RESOLUCIONES_DIA:
        a_pais = sum(1 for r in dia if r.get("resultado") == "pais")
        problemas.append({
            "id": "barrera_resoluciones",
            "frase": f"La barrera de titulares ha resuelto sola {len(dia)} incidentes en 24 horas "
            f"({a_pais} a nivel de país, {len(dia) - a_pais} descartados como no verificables): "
            "el extractor puede estar eligiendo mal las citas.",
        })  # fmt: skip
    atascados = [
        desde for desde in estado.get("retenidos", {}).values()
        if (momento := _instante(desde)) is not None and ahora - momento > MAX_RETENIDO
    ]  # fmt: skip
    if atascados:
        problemas.append({
            "id": "barrera_atascada",
            "frase": f"{len(atascados)} incidentes siguen retenidos por la barrera de titulares "
            f"desde hace más de 8 horas (el más antiguo, desde el {min(atascados)}): la "
            "resolución automática no se está aplicando.",
        })  # fmt: skip
    cambio = _instante(estado.get("mapa_cambiado"))
    alta = _instante(estado.get("ultima_alta_con_punto"))
    if (
        cambio is not None
        and alta is not None
        and alta > cambio
        and ahora - cambio > MAX_MAPA_SIN_CAMBIAR
    ):
        problemas.append({
            "id": "mapa_parado",
            "frase": f"incidentes.geojson no cambia desde el {cambio:%Y-%m-%d %H:%M} UTC y hay "
            f"incidentes nuevos con punto en la base (el último, del {alta:%Y-%m-%d %H:%M} "
            "UTC): lo nuevo no llega al mapa.",
        })  # fmt: skip
    return problemas


def ultima_copia_base() -> datetime | None:
    """La hora de la copia cifrada más reciente de la base en el almacén privado."""
    from almacen import copias

    todas = copias.cliente().copias()
    return max((cuando for nivel, cuando, _ in todas if nivel == copias.HORARIA), default=None)


def ultima_copia_archivo(datos: Path) -> datetime | None:
    """La hora de la última subida del archivo del seguimiento, de sus anotaciones."""
    ultima: datetime | None = None
    for ruta in sorted((datos / "copias").glob("*.json"))[-3:]:
        for objeto in _leer_json(ruta).get("objetos", {}).values():
            cuando = _instante(objeto.get("copiado")) if isinstance(objeto, dict) else None
            if cuando and (ultima is None or cuando > ultima):
                ultima = cuando
    return ultima


def modo_base(secretos: Path) -> str:
    try:
        return (secretos / "base_modo").read_text(encoding="utf-8").strip() or "github"
    except OSError:
        return "github"


def problemas_de_memoria(medida: dict[str, Any]) -> list[dict[str, str]]:
    """La memoria propia de la última recogida cerca de su tope. Solo la propia: el pico de
    systemd cuenta la caché de ficheros, que el núcleo suelta al llegar al tope."""
    pico, tope = medida.get("pico_bytes"), medida.get("tope_bytes")
    if not isinstance(pico, int) or not isinstance(tope, int) or tope <= 0:
        return []
    if pico < UMBRAL_MEMORIA * tope:
        return []
    gb = 1024**3
    return [{
        "id": "memoria_recogida",
        "frase": f"La recogida usó {pico / gb:.1f} GB de memoria propia, sin contar la caché de "
        f"ficheros: el {100 * pico / tope:.0f} % de su tope de {tope / gb:.1f} GB.",
    }]  # fmt: skip


# --- Composición --------------------------------------------------------------------------
def componer(
    ahora: datetime,
    secretos: Path,
    datos_seguimiento: Path,
    disco: Path,
    ejecutar: Ejecutar = _ejecutar,
    copia_base: Callable[[], datetime | None] = ultima_copia_base,
    salud_ntfy: Callable[[], bool] = ntfy_responde,
    salud_goatcounter: Callable[[], bool] = visitas.goatcounter_responde,
    privacidad: Callable[[], list[str]] = visitas.fallos_de_privacidad,
    certificados: Callable[[], list[str]] = certificados_que_caducan,
    guardian: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """salud.json y las líneas de detalle para el diario (con los identificadores)."""
    detalle: list[str] = []
    problemas: list[dict[str, str]] = []
    avisos: list[dict[str, str]] = []
    registro_ruta = secretos / "vigilancia.json"
    memoria = _leer_json(registro_ruta)

    # Recogida y publicación.
    recogida = unidad(UNIDAD_RECOGIDA, ejecutar)
    ultima_publicacion = _instante(memoria.get("ultima_publicacion"))
    fin = recogida["fin"]
    publico = recogida["codigo"] in SALIDAS_QUE_PUBLICAN and fin is not None
    if publico and (ultima_publicacion is None or fin > ultima_publicacion):
        ultima_publicacion = fin
    if ultima_publicacion is None:
        # Sin registro todavía: lo que dice estado.json de la última correcta.
        ultima_publicacion = _instante(_leer_json(secretos / "estado.json").get("ultima_correcta"))
    if ultima_publicacion is None or ahora - ultima_publicacion > MAX_SIN_PUBLICAR:
        problemas.append({
            "id": "publicacion",
            "frase": "La última recogida que publicó terminó "
            + (
                f"el {ultima_publicacion:%Y-%m-%d %H:%M} UTC"
                if ultima_publicacion
                else "sin constar"
            )
            + ": más de 2 horas sin publicar.",
        })  # fmt: skip
    codigo = recogida["codigo"]
    # En marcha o esperando su reintento («activating»): no se juzga, vale lo de las terminadas.
    en_marcha = recogida["activa"] in ("activating", "active", "deactivating", "reloading")
    retenidos: list[str] = []
    terminadas = [r for r in memoria.get("recogidas", []) if isinstance(r, dict)]
    if recogida["inicio"] is not None and recogida["fin"] is not None and not en_marcha:
        if not terminadas or terminadas[-1].get("fin") != _iso(recogida["fin"]):
            terminadas.append({"fin": _iso(recogida["fin"]), "codigo": codigo})
        lineas = diario_recogida(recogida["inicio"], ejecutar)
        frases, retenidos = avisos_del_diario(lineas)
        if codigo == 2:
            avisos.append({
                "id": "recogida_con_avisos",
                "frase": "La última recogida terminó con avisos (código 2): "
                + ("; ".join(frases) if frases else "ver su diario") + ".",
            })  # fmt: skip
    terminadas = terminadas[-RECOGIDAS_ANOTADAS:]
    memoria["recogidas"] = terminadas
    fallidas = 0
    for anotada in reversed(terminadas):
        if anotada.get("codigo") in SALIDAS_QUE_PUBLICAN:
            break
        fallidas += 1
    if fallidas >= MAX_RECOGIDAS_FALLIDAS:
        problemas.append({
            "id": "recogida",
            "frase": f"Las últimas {fallidas} recogidas fallaron, cada una tras sus reintentos "
            f"(la última con el código {terminadas[-1].get('codigo')}), y no publicaron.",
        })  # fmt: skip
    elif fallidas:
        avisos.append({
            "id": "recogida_fallida",
            "frase": f"La última recogida falló con el código {terminadas[-1].get('codigo')} tras "
            f"sus reintentos ({fallidas} seguidas; incidencia a partir de "
            f"{MAX_RECOGIDAS_FALLIDAS}).",
        })  # fmt: skip
    problemas += problemas_de_memoria(_leer_json(secretos / "memoria_recogida.json"))
    if retenidos:
        avisos.append({
            "id": "titulares_retenidos",
            "frase": f"La barrera de titulares retiene {len(retenidos)} incidentes: sus citas no "
            "respaldan el titular (detalle en el diario de eodi-vigilancia).",
        })  # fmt: skip
        detalle.append("retenidos por la barrera de titulares: " + ", ".join(retenidos))
    estado_barrera = _leer_json(secretos / BARRERA)
    problemas += problemas_de_la_barrera(estado_barrera, ahora)
    for id_, desde in estado_barrera.get("retenidos", {}).items():
        detalle.append(f"barrera: {id_} retenido desde {desde}")
    estado_control = _leer_json(secretos / CONTROL)
    problemas += problemas_del_control(estado_control)
    problemas += problemas_del_experto(estado_control, ahora)

    # Captura del seguimiento.
    seguimiento = _leer_json(secretos / "seguimiento.json")
    recepcion = _instante(seguimiento.get("ultima_recepcion"))
    activa = unidad(UNIDAD_SEGUIMIENTO, ejecutar)["activa"]
    if activa != "active" or recepcion is None or ahora - recepcion > MAX_SIN_RECIBIR:
        problemas.append({
            "id": "seguimiento",
            "frase": f"La captura del seguimiento está «{activa or 'desconocida'}» y recibió por "
            "última vez "
            + (f"el {recepcion:%Y-%m-%d %H:%M} UTC" if recepcion else "sin constar")
            + ": más de 10 minutos sin datos.",
        })  # fmt: skip

    # Archivo de alertas de alerts.in.ua.
    alertas = _leer_json(secretos / "alertas.json")
    respuesta = _instante(alertas.get("ultima_respuesta"))
    activa_alertas = unidad(UNIDAD_ALERTAS, ejecutar)["activa"]
    if activa_alertas != "active" or respuesta is None or ahora - respuesta > MAX_SIN_ALERTAS:
        problemas.append({
            "id": "alertas",
            "frase": "El archivo de alertas de alerts.in.ua está "
            f"«{activa_alertas or 'desconocida'}» y tuvo respuesta de la API por última vez "
            + (f"el {respuesta:%Y-%m-%d %H:%M} UTC" if respuesta else "sin constar")
            + ": más de 15 minutos sin datos nuevos.",
        })  # fmt: skip
    autorizacion = alertas.get("error_autorizacion")
    if isinstance(autorizacion, dict):
        problemas.append({
            "id": "alertas_autorizacion",
            "frase": f"La API de alerts.in.ua respondió {autorizacion.get('http')} el "
            f"{autorizacion.get('momento')}: el token no vale o la IP está bloqueada.",
        })  # fmt: skip

    # Copias de seguridad.
    modo = modo_base(secretos)
    base: datetime | None = None
    if modo in ("doble", "disco"):
        try:
            base = copia_base()
        except (OSError, ValueError) as error:
            detalle.append(f"copias de la base sin listar: {error}")
        if base is None or ahora - base > MAX_SIN_COPIA:
            problemas.append({
                "id": "copia_base",
                "frase": "La última copia cifrada de la base en el almacén es "
                + (f"del {base:%Y-%m-%d %H:%M} UTC" if base else "desconocida")
                + ": más de 2 horas sin copia.",
            })  # fmt: skip
    archivo = ultima_copia_archivo(datos_seguimiento)
    if archivo is None or ahora - archivo > MAX_SIN_COPIA_ARCHIVO:
        horas = MAX_SIN_COPIA_ARCHIVO / timedelta(hours=1)
        problemas.append({
            "id": "copia_archivo",
            "frase": "La última copia del archivo del seguimiento es "
            + (f"del {archivo:%Y-%m-%d %H:%M} UTC" if archivo else "desconocida")
            + f": más de {horas:.0f} horas sin copia.",
        })  # fmt: skip

    replica = _instante(_leer_json(secretos / "replica.json").get("ultima"))
    if replica is None or ahora - replica > MAX_SIN_REPLICA:
        problemas.append({
            "id": "replica",
            "frase": "La última segunda copia en otra ubicación es "
            + (f"del {replica:%Y-%m-%d %H:%M} UTC" if replica else "desconocida")
            + ": más de 3 horas sin réplica.",
        })  # fmt: skip

    # Copia pública de reserva del almacén de la web, en Helsinki (almacen/reserva.py).
    estado_reserva = _leer_json(secretos / reserva.ESTADO)
    frase_reserva = reserva.problema_para_vigilancia(estado_reserva, ahora)
    if frase_reserva is not None:
        problemas.append({"id": "reserva", "frase": frase_reserva})

    # Avisos públicos de ntfy (recogida/avisos.py), solo en el servidor que los envía.
    if (secretos / TOKEN_NTFY).exists():
        if not salud_ntfy():
            problemas.append({
                "id": "ntfy",
                "frase": "El servidor de avisos ntfy no responde (/v1/health).",
            })  # fmt: skip
        frase_avisos = avisos_ntfy.problema_para_vigilancia(
            _leer_json(secretos / avisos_ntfy.ESTADO)
        )
        if frase_avisos is not None:
            problemas.append({"id": "avisos", "frase": frase_avisos})
        # Contador de visitas y resumen diario (recogida/visitas.py), en el mismo servidor.
        if not salud_goatcounter():
            problemas.append({
                "id": "goatcounter",
                "frase": "El contador de visitas (GoatCounter) no responde (/status).",
            })  # fmt: skip
        problemas += visitas.problemas_para_vigilancia(_leer_json(secretos / visitas.ESTADO), ahora)
        caducan = certificados()
        if caducan:
            problemas.append({
                "id": "certificados",
                "frase": "Certificados que Caddy no ha renovado y caducan pronto: "
                + ", ".join(caducan) + ".",
            })  # fmt: skip
        abiertos = privacidad()
        if abiertos:
            problemas.append({
                "id": "visitas_privadas",
                "frase": "Lo privado ha quedado abierto: " + "; ".join(abiertos) + ".",
            })  # fmt: skip

    prueba = _leer_json(secretos / "prueba_restauracion.json")
    hecha = _instante(prueba.get("fecha"))
    if prueba and (not prueba.get("correcto") or (hecha and ahora - hecha > timedelta(days=8))):
        problemas.append({
            "id": "prueba_restauracion",
            "frase": f"La prueba de restauración de la base del {prueba.get('fecha')} "
            + ("falló" if not prueba.get("correcto") else "tiene más de 8 días") + ".",
        })  # fmt: skip
    # Versiones citables de los datos abiertos (recogida/versiones.py).
    for frase in versiones.problemas_para_vigilancia(
        _leer_json(secretos / "versiones.json"), ahora
    ):
        problemas.append({"id": "versiones", "frase": frase})
    solo_disco = _leer_json(secretos / "base_solo_disco.json")
    if solo_disco and not solo_disco.get("correcto"):
        motivos = solo_disco.get("comprobaciones") or ["sin comprobaciones"]
        problemas.append({
            "id": "base_solo_disco",
            "frase": f"El paso de la base a solo disco del {solo_disco.get('fecha')} no se hizo: "
            f"{motivos[-1]}. La copia secundaria en GitHub sigue.",
        })  # fmt: skip

    # Disco.
    uso = shutil.disk_usage(disco)
    porcentaje = round(100 * uso.used / uso.total, 1)
    if porcentaje >= DISCO_AVISO_PCT:
        problemas.append({
            "id": "disco",
            "frase": f"El disco está al {porcentaje} % (aviso desde el {DISCO_AVISO_PCT:.0f} %, "
            f"quedan {uso.free / 1e9:.1f} GB).",
        })  # fmt: skip

    if guardian is not None:
        problemas += problemas_del_guardian(_leer_json(guardian), ahora)

    memoria["ultima_publicacion"] = _iso(ultima_publicacion)
    problemas, observacion = persistentes(problemas, memoria, ahora)
    avisos = observacion + avisos
    salud: dict[str, Any] = {
        "version": VERSION,
        "generado": _iso(ahora),
        "recogida": {
            "en_marcha": en_marcha,
            "ultimo_codigo": codigo,
            "ultimo_fin": _iso(recogida["fin"]),
            "ultima_publicacion": _iso(ultima_publicacion),
        },
        "seguimiento": {"unidad": activa, "ultima_recepcion": _iso(recepcion)},
        "alertas": {"unidad": activa_alertas, "ultima_respuesta": _iso(respuesta)},
        "copias": {
            "modo_base": modo,
            "base": _iso(base),
            "archivo": _iso(archivo),
            "replica": _iso(replica),
            "reserva_web": estado_reserva.get("ultima_al_dia"),
        },
        "disco": {"usado_pct": porcentaje, "libre_gb": round(uso.free / 1e9, 1)},
        "problemas": problemas,
        "avisos": avisos,
    }
    _escribir(registro_ruta, memoria)
    return salud, detalle


def persistentes(
    problemas: list[dict[str, str]], memoria: dict[str, Any], ahora: datetime
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Los problemas que no se han arreglado solos y los que siguen en observación (avisos).

    Anota en `memoria` desde cuándo está abierto cada uno y, al irse, lo pasa a `resueltos` (con
    si llegó a ser incidencia), para el resumen diario.
    """
    abiertos: dict[str, Any] = {
        k: v for k, v in (memoria.get("abiertos") or {}).items() if isinstance(v, dict)
    }
    resueltos = [
        r for r in memoria.get("resueltos", [])
        if isinstance(r, dict)
        and (hasta := _instante(r.get("hasta"))) is not None and ahora - hasta <= DIAS_RESUELTOS
    ]  # fmt: skip
    vistos: set[str] = set()
    firmes: list[dict[str, str]] = []
    observacion: list[dict[str, str]] = []
    for problema in problemas:
        id_ = problema["id"]
        vistos.add(id_)
        entrada = abiertos.setdefault(id_, {"desde": _iso(ahora), "incidencia": False})
        entrada["frase"] = problema["frase"]
        desde = _instante(entrada.get("desde")) or ahora
        if id_ in SIN_GRACIA or ahora - desde >= GRACIA:
            entrada["incidencia"] = True
            firmes.append(problema)
        else:
            observacion.append({
                "id": f"observacion_{id_}",
                "frase": "En observación, se reintenta solo: " + problema["frase"],
            })  # fmt: skip
    for id_ in [i for i in abiertos if i not in vistos]:
        entrada = abiertos.pop(id_)
        resueltos.append({
            "id": id_, "frase": entrada.get("frase", ""), "desde": entrada.get("desde"),
            "hasta": _iso(ahora), "incidencia": bool(entrada.get("incidencia")),
        })  # fmt: skip
    memoria["abiertos"] = abiertos
    memoria["resueltos"] = resueltos
    return firmes, observacion


def _escribir(ruta: Path, datos: dict[str, Any]) -> None:
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--sin-subir", action="store_true")
    opciones.add_argument("--salida", type=Path)
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    secretos = Path(os.environ.get("EODI_SECRETOS") or casa() / ".eodi")
    datos = Path(os.environ.get("EODI_SEGUIMIENTO_DATOS") or casa() / "datos" / "seguimiento")
    salud, detalle = componer(datetime.now(UTC), secretos, datos, casa(), guardian=GUARDIAN)
    for linea in detalle:
        registro.info("%s", linea)
    for problema in salud["problemas"]:
        registro.warning("problema %s: %s", problema["id"], problema["frase"])
    for aviso in salud["avisos"]:
        registro.info("aviso %s: %s", aviso["id"], aviso["frase"])
    cuerpo = (json.dumps(salud, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    if args.salida:
        args.salida.write_bytes(cuerpo)
    if args.sin_subir:
        return 0
    clave_id = os.environ.get(almacen_publico.VARIABLE_ID, "")
    secreto = os.environ.get(almacen_publico.VARIABLE_SECRETO, "")
    if not (clave_id and secreto):
        registro.error("sin credenciales del almacén: salud.json no se sube")
        return 1
    correcto, motivo = almacen_publico.subir(
        almacen_publico.cargar(), OBJETO, cuerpo, clave_id, secreto,
        "application/json", CACHE,
    )  # fmt: skip
    registro.info("%s: %s", OBJETO, motivo)
    return 0 if correcto else 1


if __name__ == "__main__":
    sys.exit(principal())
