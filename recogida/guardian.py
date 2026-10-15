"""Guardián del sistema: comprueba y repara solo lo básico del servidor cada 5 minutos.

El 13 de octubre de 2026 una sesión borró /dev/null en el servidor: sshd dejó de aceptar
conexiones, systemd no pudo lanzar ningún servicio («Failed to set up standard input») y dos
recogidas no llegaron a arrancar. El servidor no se reparó solo. Desde entonces lo hace este
guardián, que lanza eodi-guardian.timer cada 5 minutos, como root (interno: servidor, «Guardián
del sistema»):

- /dev/null, /dev/zero, /dev/random y /dev/urandom existen y son dispositivos de caracteres con
  sus números (1,3; 1,5; 1,8; 1,9), dueño root y permisos 666. Si no, los recrea con mknod (en un
  nombre temporal y renombrándolo encima, de una vez). La unidad toma su entrada de un dato
  (StandardInput=data) y no de /dev/null: así systemd la puede lanzar aunque falte;
- /tmp existe, es una carpeta de root con permisos 1777;
- sshd está activo y acepta conexiones locales (saluda con «SSH-» en el puerto 22); si no,
  reinicia ssh.socket y ssh.service;
- el disco no pasa del 90 %: si pasa, limpia las cachés y los temporales propios del observatorio
  (caché de pip, temporales del usuario del observatorio de más de un día, paquetes descargados
  de apt y el diario por encima de 500 MB). Nunca toca datos.

Último recurso: si las dos últimas recogidas terminadas fallaron por un error del sistema (no de
una fuente: no pudo arrancar, sin memoria, disco lleno, sin /dev/null...) y no ha habido después
ninguna buena, el guardián primero relanza la recogida si acaba de reparar algo; si no ha reparado
nada o la relanzada vuelve a fallar por el sistema, reinicia el servidor, como mucho una vez cada 6
horas. Tras cualquier arranque (este, el que viene de fuera por la API de Hetzner o uno a mano),
si la última publicación tiene más de 65 minutos, lanza la recogida pendiente.

Cada reparación queda en el diario de la unidad y en el registro /var/lib/eodi-guardian/estado.json
(lectura para todos): lo leen la vigilancia (recogida/vigilancia.py: lo que no se arregla pasa a
problema) y el resumen diario (recogida/visitas.py, sección SISTEMA).

Solo usa la biblioteca estándar y se lanza con el Python del sistema (`python3 -I`): funciona
aunque el entorno del observatorio esté roto. Ninguna orden necesita /dev/null.

Uso: python3 -I recogida/guardian.py              (una pasada, como root)
     python3 -I recogida/guardian.py --simulacro-reinicio
         (una pasada con dos recogidas fallidas por el sistema inventadas: hace todo menos
          reiniciar, y lo cuenta)
"""

import argparse
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

VERSION = 1
ESTADO = Path(os.environ.get("EODI_GUARDIAN_ESTADO", "/var/lib/eodi-guardian/estado.json"))


def _dueno(ruta: Path) -> str:
    try:
        return ruta.owner()
    except (OSError, KeyError, NotImplementedError):
        return ""


# La unidad del guardián pasa la casa y el usuario del observatorio. Sin ellos: la carpeta que
# contiene el clon (el guardián se ejecuta desde él) y su dueño.
CASA = Path(os.environ.get("EODI_GUARDIAN_CASA") or Path(__file__).resolve().parent.parent.parent)
USUARIO = os.environ.get("EODI_GUARDIAN_USUARIO") or _dueno(CASA)
UNIDAD_RECOGIDA = os.environ.get("EODI_GUARDIAN_RECOGIDA", "eodi-recogida.service")

# Dispositivo: (mayor, menor). Todos de root, con permisos 666 (lo de serie del núcleo).
DISPOSITIVOS = {
    "/dev/null": (1, 3),
    "/dev/zero": (1, 5),
    "/dev/random": (1, 8),
    "/dev/urandom": (1, 9),
}
MODO_DISPOSITIVO = 0o666
TMP = Path("/tmp")
MODO_TMP = 0o1777

UNIDADES_SSH = ("ssh.socket", "ssh.service")
PUERTO_SSH = 22
ESPERA_SSH_S = 10.0

DISCO = Path("/")
DISCO_LIMPIEZA_PCT = 90.0
DIARIO_TOPE = "500M"
TEMPORALES = (Path("/tmp"), Path("/var/tmp"))
TEMPORAL_ANTIGUEDAD = timedelta(days=1)

# Último recurso.
REINICIO_CADA = timedelta(hours=6)
DIARIO_RECOGIDA = timedelta(hours=6)
FALLOS_SISTEMA_SEGUIDOS = 2
# Tras un arranque, la recogida se lanza si la última publicación tiene más de esto (la recogida
# es horaria; 5 minutos de margen).
MAX_SIN_PUBLICAR_ARRANQUE = timedelta(minutes=65)
# Lo que se guarda en el registro.
DIAS_REGISTRO = timedelta(days=30)
TOPE_ORDEN_S = 120

# Una recogida que falla por esto ha fallado por el sistema, no por una fuente: systemd no pudo
# lanzarla (códigos 200 a 249), la cortó por memoria o se quedó sin disco, sin /dev/null, sin
# ficheros abiertos o con el disco de solo lectura.
PATRONES_SISTEMA = re.compile(
    r"Failed at step \w+|Failed to set up standard|Failed to spawn|status=2(?:[0-4]\d)/"
    r"|result '(?:resources|oom-kill|core-dump)'|No space left on device"
    r"|Couldn't open /dev/null|/dev/null: No such file|Read-only file system"
    r"|Cannot allocate memory|Input/output error|Too many open files|Out of memory"
)
FIN_BIEN = "Deactivated successfully"
FIN_MAL = re.compile(r"Failed with result '([\w-]+)'")

Ejecutar = Callable[[Sequence[str]], tuple[int, str]]


def _ejecutar(orden: Sequence[str]) -> tuple[int, str]:
    """Código y salida de una orden. La entrada es vacía y no /dev/null: funciona aunque falte."""
    try:
        r = subprocess.run(
            list(orden), input=b"", capture_output=True, timeout=TOPE_ORDEN_S, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        return 127, str(error)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instante(texto: Any) -> datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


@dataclass
class Pasada:
    """Lo que hizo una pasada: reparaciones (hechas o fallidas) y lo que no se pudo arreglar."""

    ahora: datetime
    reparaciones: list[dict[str, Any]] = field(default_factory=list)
    sin_arreglar: list[dict[str, str]] = field(default_factory=list)

    def reparado(self, id_: str, frase: str, correcto: bool = True) -> None:
        print(("reparado" if correcto else "sin reparar") + f" {id_}: {frase}", flush=True)
        self.reparaciones.append(
            {"hora": _iso(self.ahora), "id": id_, "frase": frase, "correcto": correcto}
        )
        if not correcto:
            self.sin_arreglar.append({"id": id_, "frase": frase})


# --- Dispositivos y /tmp -------------------------------------------------------------------


def dispositivo_correcto(estado: os.stat_result | None, mayor: int, menor: int) -> bool:
    return (
        estado is not None
        and stat.S_ISCHR(estado.st_mode)
        and os.major(estado.st_rdev) == mayor
        and os.minor(estado.st_rdev) == menor
        and stat.S_IMODE(estado.st_mode) == MODO_DISPOSITIVO
        and estado.st_uid == 0
        and estado.st_gid == 0
    )


def _lstat(ruta: str) -> os.stat_result | None:
    try:
        return os.lstat(ruta)
    except FileNotFoundError:
        return None


def reparar_dispositivo(ruta: str, mayor: int, menor: int, pasada: Pasada) -> None:
    antes = _lstat(ruta)
    if dispositivo_correcto(antes, mayor, menor):
        return
    if antes is None:
        que = "no existía"
    elif not stat.S_ISCHR(antes.st_mode):
        que = "no era un dispositivo de caracteres"
    elif (os.major(antes.st_rdev), os.minor(antes.st_rdev)) != (mayor, menor):
        que = "tenía otros números"
    else:
        que = "tenía otros permisos o dueño"
    temporal = f"{ruta}.eodi-guardian"
    try:
        if _lstat(temporal) is not None:
            os.unlink(temporal)
        os.mknod(temporal, stat.S_IFCHR | MODO_DISPOSITIVO, os.makedev(mayor, menor))
        os.chown(temporal, 0, 0)
        os.chmod(temporal, MODO_DISPOSITIVO)
        if antes is not None and stat.S_ISDIR(antes.st_mode):
            os.rename(ruta, f"{ruta}.apartado-{int(time.time())}")
        os.replace(temporal, ruta)
    except OSError as error:
        pasada.reparado(ruta, f"{ruta} {que} y no se pudo recrear: {error}", correcto=False)
        return
    correcto = dispositivo_correcto(_lstat(ruta), mayor, menor)
    pasada.reparado(
        ruta,
        f"{ruta} {que}: recreado con mknod ({mayor},{menor}, 666)"
        + ("" if correcto else ", pero sigue mal"),
        correcto,
    )


def reparar_tmp(pasada: Pasada, ruta: Path = TMP) -> None:
    estado = _lstat(str(ruta))
    if (
        estado is not None
        and stat.S_ISDIR(estado.st_mode)
        and stat.S_IMODE(estado.st_mode) == MODO_TMP
        and estado.st_uid == 0
    ):
        return
    try:
        if estado is None:
            que = "no existía"
        elif not stat.S_ISDIR(estado.st_mode):
            que = "no era una carpeta"
            os.rename(ruta, f"{ruta}.apartado-{int(time.time())}")
        else:
            que = f"tenía permisos {stat.S_IMODE(estado.st_mode):o}"
        ruta.mkdir(exist_ok=True)
        os.chown(ruta, 0, 0)
        os.chmod(ruta, MODO_TMP)
    except OSError as error:
        pasada.reparado(str(ruta), f"{ruta} {que} y no se pudo arreglar: {error}", correcto=False)
        return
    pasada.reparado(str(ruta), f"{ruta} {que}: carpeta de root con permisos 1777")


# --- sshd --------------------------------------------------------------------------------


def ssh_responde(puerto: int = PUERTO_SSH, espera_s: float = ESPERA_SSH_S) -> bool:
    """Si sshd saluda en el puerto local (el saludo lo da después de abrir /dev/null)."""
    try:
        with socket.create_connection(("127.0.0.1", puerto), timeout=espera_s) as conexion:
            return conexion.recv(64).startswith(b"SSH-")
    except OSError:
        return False


def reparar_ssh(
    pasada: Pasada,
    ejecutar: Ejecutar = _ejecutar,
    responde: Callable[[], bool] = ssh_responde,
    dormir: Callable[[float], None] = time.sleep,
) -> None:
    activas = [u for u in UNIDADES_SSH if ejecutar(["systemctl", "is-active", u])[0] == 0]
    if len(activas) == len(UNIDADES_SSH) and responde():
        return
    # Con activación por socket, ssh.service puede no estar en marcha y sshd responde igual.
    if responde():
        return
    que = "no aceptaba conexiones locales" + (
        "" if activas else " y sus unidades no estaban activas"
    )
    codigo, salida = ejecutar(["sshd", "-t"])
    if codigo:
        pasada.reparado(
            "sshd", f"sshd {que} y su configuración no es válida: {salida.strip()[:200]}", False
        )
        return
    ejecutar(["systemctl", "reset-failed", *UNIDADES_SSH])
    ejecutar(["systemctl", "restart", *UNIDADES_SSH])
    for _ in range(6):
        if responde():
            pasada.reparado("sshd", f"sshd {que}: reiniciado, vuelve a aceptar conexiones")
            return
        dormir(5)
    pasada.reparado("sshd", f"sshd {que} y sigue igual tras reiniciarlo", correcto=False)


# --- Disco -------------------------------------------------------------------------------


def uso_disco(ruta: Path = DISCO) -> float:
    uso = shutil.disk_usage(ruta)
    return 100 * uso.used / uso.total


def _borrar_arbol(ruta: Path) -> int:
    """Borra el contenido de una carpeta de caché (no la carpeta) y devuelve los bytes."""
    liberado = 0
    if not ruta.is_dir() or ruta.is_symlink():
        return 0
    for hijo in ruta.iterdir():
        try:
            if hijo.is_dir() and not hijo.is_symlink():
                liberado += sum(f.stat().st_size for f in hijo.rglob("*") if f.is_file())
                shutil.rmtree(hijo)
            else:
                liberado += hijo.lstat().st_size
                hijo.unlink()
        except OSError:
            continue
    return liberado


def temporales_viejos(
    carpetas: Sequence[Path], uid: int, ahora: float, antiguedad: timedelta
) -> list[Path]:
    """Ficheros del usuario del observatorio en las carpetas temporales sin tocar desde hace más
    de `antiguedad` (solo ficheros normales, sin seguir enlaces)."""
    viejos = []
    limite = ahora - antiguedad.total_seconds()
    for carpeta in carpetas:
        if not carpeta.is_dir():
            continue
        for raiz, _dirs, ficheros in os.walk(carpeta, followlinks=False):
            for nombre in ficheros:
                ruta = Path(raiz) / nombre
                try:
                    e = ruta.lstat()
                except OSError:
                    continue
                if stat.S_ISREG(e.st_mode) and e.st_uid == uid and e.st_mtime < limite:
                    viejos.append(ruta)
    return viejos


def limpiar_disco(
    pasada: Pasada,
    ejecutar: Ejecutar = _ejecutar,
    uso: Callable[[], float] = uso_disco,
    casa: Path = CASA,
    usuario: str = USUARIO,
) -> None:
    antes = uso()
    if antes <= DISCO_LIMPIEZA_PCT:
        return
    hecho = []
    liberado = _borrar_arbol(casa / ".cache" / "pip")
    hecho.append(f"caché de pip ({liberado / 1e6:.0f} MB)")
    try:
        import pwd

        uid = pwd.getpwnam(usuario).pw_uid
    except (ImportError, KeyError):
        uid = -1
    viejos = temporales_viejos(TEMPORALES, uid, time.time(), TEMPORAL_ANTIGUEDAD)
    for ruta in viejos:
        try:
            ruta.unlink()
        except OSError:
            continue
    hecho.append(f"{len(viejos)} temporales del observatorio de más de un día")
    if ejecutar(["apt-get", "clean"])[0] == 0:
        hecho.append("paquetes descargados de apt")
    if ejecutar(["journalctl", f"--vacuum-size={DIARIO_TOPE}"])[0] == 0:
        hecho.append(f"diario recortado a {DIARIO_TOPE}")
    despues = uso()
    correcto = despues <= DISCO_LIMPIEZA_PCT
    pasada.reparado(
        "disco",
        f"disco al {antes:.1f} %: limpiado ({', '.join(hecho)}), queda al {despues:.1f} %"
        + ("" if correcto else "; sigue por encima del 90 %: hay que liberar datos a mano"),
        correcto,
    )


# --- Recogidas y último recurso ----------------------------------------------------------


@dataclass
class Recogida:
    fin: datetime
    correcta: bool
    sistema: bool
    motivo: str


def recogidas(entradas: Sequence[dict[str, Any]]) -> list[Recogida]:
    """Las recogidas terminadas, en orden, a partir del diario de su unidad (journalctl -o json):
    cada una acaba en «Deactivated successfully» o en «Failed with result»."""
    terminadas = []
    mensajes: list[str] = []
    for entrada in entradas:
        mensaje = entrada.get("MESSAGE")
        if not isinstance(mensaje, str):
            continue
        mensajes.append(mensaje)
        malo = FIN_MAL.search(mensaje)
        if FIN_BIEN not in mensaje and not malo:
            continue
        try:
            fin = datetime.fromtimestamp(int(entrada["__REALTIME_TIMESTAMP"]) / 1e6, UTC)
        except (KeyError, TypeError, ValueError):
            fin = datetime.now(UTC)
        motivo = "correcta"
        sistema = False
        if malo:
            motivo = malo.group(0)
            for m in mensajes:
                if encontrado := PATRONES_SISTEMA.search(m):
                    motivo, sistema = encontrado.group(0), True
                    break
        terminadas.append(Recogida(fin=fin, correcta=not malo, sistema=sistema, motivo=motivo))
        mensajes = []
    return terminadas


def diario_recogida(ahora: datetime, ejecutar: Ejecutar = _ejecutar) -> list[dict[str, Any]]:
    desde = (ahora - DIARIO_RECOGIDA).strftime("%Y-%m-%d %H:%M:%S")
    codigo, salida = ejecutar([
        "journalctl", "-u", UNIDAD_RECOGIDA, "--since", desde, "--utc", "-o", "json",
        "--output-fields=MESSAGE,__REALTIME_TIMESTAMP", "--no-pager",
    ])  # fmt: skip
    entradas = []
    for linea in salida.splitlines() if codigo == 0 else []:
        try:
            entrada = json.loads(linea)
        except ValueError:
            continue
        if isinstance(entrada, dict):
            entradas.append(entrada)
    return entradas


def fallos_de_sistema(lista: Sequence[Recogida]) -> list[Recogida]:
    """Las últimas recogidas terminadas, si las FALLOS_SISTEMA_SEGUIDOS últimas fallaron por el
    sistema (y por tanto no hay ninguna buena después); si no, vacío."""
    ultimas = list(lista[-FALLOS_SISTEMA_SEGUIDOS:])
    if len(ultimas) == FALLOS_SISTEMA_SEGUIDOS and all(r.sistema for r in ultimas):
        return ultimas
    return []


def puede_reiniciar(estado: dict[str, Any], ahora: datetime) -> bool:
    for texto in estado.get("reinicios", []):
        hora = _instante(texto.get("hora") if isinstance(texto, dict) else None)
        if hora is not None and ahora - hora < REINICIO_CADA:
            return False
    return True


def reiniciar(ejecutar: Ejecutar = _ejecutar) -> bool:
    """Reinicia: con systemd si puede; si no, forzado; y, si tampoco, por el núcleo."""
    for orden in (["systemctl", "reboot"], ["systemctl", "reboot", "--force"]):
        if ejecutar(orden)[0] == 0:
            return True
    try:
        with open("/proc/sysrq-trigger", "w") as disparador:
            for letra in "sub":
                disparador.write(letra)
                disparador.flush()
                time.sleep(2)
    except OSError:
        return False
    return True


def lanzar_recogida(ejecutar: Ejecutar = _ejecutar) -> bool:
    ejecutar(["systemctl", "reset-failed", UNIDAD_RECOGIDA])
    return ejecutar(["systemctl", "start", "--no-block", UNIDAD_RECOGIDA])[0] == 0


def ultima_publicacion(casa: Path = CASA) -> datetime | None:
    momentos = []
    for nombre in ("vigilancia.json", "estado.json"):
        try:
            datos = json.loads((casa / ".eodi" / nombre).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(datos, dict) and (m := _instante(datos.get("ultima_publicacion"))):
            momentos.append(m)
    return max(momentos) if momentos else None


def hora_de_arranque(ahora: datetime) -> datetime | None:
    try:
        segundos = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return ahora - timedelta(seconds=segundos)


def arranque_actual() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def ultimo_recurso(
    pasada: Pasada,
    estado: dict[str, Any],
    entradas: Sequence[dict[str, Any]],
    ejecutar: Ejecutar = _ejecutar,
    simulacro: bool = False,
    desde: datetime | None = None,
) -> None:
    """Relanza la recogida o reinicia el servidor si las dos últimas fallaron por el sistema."""
    # Solo cuentan las de este arranque: tras un reinicio, las de antes ya no dicen nada.
    fallos = fallos_de_sistema([r for r in recogidas(entradas) if desde is None or r.fin >= desde])
    if not fallos:
        estado.pop("relanzada_tras", None)
        return
    ultimo = fallos[-1]
    motivo = f"las {len(fallos)} últimas recogidas fallaron por el sistema ({ultimo.motivo})"
    reparo_ahora = any(r["correcto"] for r in pasada.reparaciones)
    ya_relanzada = _instante(estado.get("relanzada_tras")) == ultimo.fin
    if reparo_ahora and not ya_relanzada:
        correcto = lanzar_recogida(ejecutar) if not simulacro else True
        estado["relanzada_tras"] = _iso(ultimo.fin)
        pasada.reparado(
            "recogida", f"{motivo}; reparado lo anterior, se relanza la recogida", correcto
        )
        return
    if ya_relanzada and not reparo_ahora:
        # La relanzada aún no ha terminado: su resultado será el nuevo último fallo o una buena.
        print(f"{motivo}; se espera a la recogida relanzada", flush=True)
        return
    if not puede_reiniciar(estado, pasada.ahora):
        pasada.reparado(
            "reinicio",
            f"{motivo} y ya hubo un reinicio de último recurso hace menos de 6 horas",
            correcto=False,
        )
        return
    estado.setdefault("reinicios", []).append({"hora": _iso(pasada.ahora), "motivo": motivo})
    estado["recogida_pendiente"] = True
    estado["simulacro" if simulacro else "reinicio_pedido"] = _iso(pasada.ahora)
    if simulacro:
        estado["reinicios"].pop()
        pasada.reparado("reinicio", f"SIMULACRO: {motivo}: aquí se reiniciaría el servidor")
        return
    pasada.reparado("reinicio", f"{motivo}: se reinicia el servidor (último recurso)")
    escribir_estado(estado, pasada)
    if not reiniciar(ejecutar):
        pasada.reparado("reinicio", "el reinicio de último recurso no se pudo pedir", False)


def tras_arranque(
    pasada: Pasada,
    estado: dict[str, Any],
    arranque: str,
    publicada: datetime | None,
    ejecutar: Ejecutar = _ejecutar,
    hora: datetime | None = None,
) -> None:
    """Una vez por arranque: lo anota con su hora (`hora`, la del arranque) y lanza la recogida
    pendiente si la última publicación es vieja."""
    if not arranque or estado.get("arranque") == arranque:
        return
    estado["arranque"] = arranque
    estado.setdefault("arranques", []).append(_iso(hora or pasada.ahora))
    pendiente = bool(estado.pop("recogida_pendiente", False))
    vieja = publicada is None or pasada.ahora - publicada > MAX_SIN_PUBLICAR_ARRANQUE
    if not (pendiente or vieja):
        return
    activa = ejecutar(["systemctl", "is-active", UNIDAD_RECOGIDA])[1].strip()
    if activa in ("active", "activating"):
        return
    hace = (
        "sin publicación anterior"
        if publicada is None
        else (f"la última publicó el {publicada:%Y-%m-%d %H:%M} UTC")
    )
    pasada.reparado(
        "recogida_tras_arranque",
        f"tras el arranque se lanza la recogida pendiente ({hace})",
        lanzar_recogida(ejecutar),
    )


# --- Registro ----------------------------------------------------------------------------


def leer_estado(ruta: Path | None = None) -> dict[str, Any]:
    ruta = ruta or ESTADO
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def escribir_estado(estado: dict[str, Any], pasada: Pasada, ruta: Path | None = None) -> None:
    ruta = ruta or ESTADO
    limite = pasada.ahora - DIAS_REGISTRO
    anteriores = [
        r for r in estado.get("reparaciones", [])
        if isinstance(r, dict) and (h := _instante(r.get("hora"))) and h >= limite
        and r not in pasada.reparaciones
    ]  # fmt: skip
    estado["version"] = VERSION
    estado["ultima_pasada"] = _iso(pasada.ahora)
    estado["reparaciones"] = anteriores + pasada.reparaciones
    estado["sin_arreglar"] = pasada.sin_arreglar
    estado["arranques"] = [
        a for a in estado.get("arranques", []) if (h := _instante(a)) and h >= limite
    ]
    estado["reinicios"] = [
        r for r in estado.get("reinicios", [])
        if isinstance(r, dict) and (h := _instante(r.get("hora"))) and h >= limite
    ]  # fmt: skip
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.chmod(temporal, 0o644)
    os.replace(temporal, ruta)


def simulacro_entradas(ahora: datetime) -> list[dict[str, Any]]:
    """Dos recogidas inventadas que no pudieron arrancar por falta de /dev/null."""
    entradas = []
    for minutos in (35, 10):
        marca = str(int((ahora - timedelta(minutes=minutos)).timestamp() * 1e6))
        for mensaje in (
            "eodi-recogida.service: Failed to set up standard input: No such file or directory",
            "eodi-recogida.service: Failed at step STDIN spawning /usr/bin/env: No such file",
            "eodi-recogida.service: Failed with result 'exit-code'.",
        ):
            entradas.append({"MESSAGE": mensaje, "__REALTIME_TIMESTAMP": marca})
    return entradas


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    opciones.add_argument("--simulacro-reinicio", action="store_true")
    args = opciones.parse_args(argumentos)
    pasada = Pasada(ahora=datetime.now(UTC))
    # Primero lo que necesita todo lo demás.
    for ruta, (mayor, menor) in DISPOSITIVOS.items():
        reparar_dispositivo(ruta, mayor, menor, pasada)
    reparar_tmp(pasada)
    limpiar_disco(pasada)
    reparar_ssh(pasada)
    estado = leer_estado()
    tras_arranque(
        pasada, estado, arranque_actual(), ultima_publicacion(),
        hora=hora_de_arranque(pasada.ahora),
    )  # fmt: skip
    if args.simulacro_reinicio:
        simulado = {k: v for k, v in estado.items() if k != "reinicios"}
        ultimo_recurso(pasada, simulado, simulacro_entradas(pasada.ahora), simulacro=True)
        estado["simulacro"] = simulado.get("simulacro")
    else:
        ultimo_recurso(
            pasada, estado, diario_recogida(pasada.ahora), desde=hora_de_arranque(pasada.ahora)
        )
    escribir_estado(estado, pasada)
    if not pasada.reparaciones:
        print("todo en orden", flush=True)
    return 1 if pasada.sin_arreglar else 0


if __name__ == "__main__":
    sys.exit(principal())
