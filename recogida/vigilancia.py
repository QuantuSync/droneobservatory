"""Salud del servidor para la vigilancia externa: salud.json en el almacén público.

Cada 5 minutos (eodi-vigilancia.timer) se compone, con lo que hay en el propio servidor, un
resumen sin contenido de lo que hace falta para saber si todo va bien, y se sube al almacén
público como `salud.json`. Lo lee el workflow vigia-recogida cada 10 minutos
(recogida/salud.py): si el fichero deja de llegar, es que el servidor no está; si llega con un
problema, el workflow falla y el dueño recibe el correo de GitHub.

Problemas (cada uno con su frase):

- **publicación**: la última recogida que publicó (código 0 o 2) terminó hace más de 2 horas;
- **recogida**: la última recogida terminó con un código distinto de 0 y 2;
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
- **versiones**: la versión citable del mes de los datos abiertos no se ha generado el día 1
  (pasadas las 06:00 UTC), una versión publicada ha cambiado o falta, o no se comprueban desde
  hace 2 días (recogida/versiones.py).

Avisos (se ven, no son fallo): la última recogida terminó con avisos (código 2) y por qué (las
líneas de aviso de su diario: fuentes sin leer, tope de tiempo agotado), y cuántos incidentes
retiene la barrera de titulares (proceso/cita_titular.py). El fichero es público: no lleva
identificadores de incidentes sin publicar ni ningún contenido, solo horas, recuentos y frases
genéricas. El detalle queda en el diario de esta unidad.

El registro `/home/eodi/.eodi/vigilancia.json` guarda la hora de la última publicación vista
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
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen import reserva
from almacen.sitio import casa
from recogida import almacen_publico, versiones

registro = logging.getLogger("vigilancia")

VERSION = 1
OBJETO = "salud.json"
CACHE = "public, max-age=60"
UNIDAD_RECOGIDA = "eodi-recogida.service"
UNIDAD_SEGUIMIENTO = "eodi-seguimiento.service"
UNIDAD_ALERTAS = "eodi-alertas.service"
SALIDAS_QUE_PUBLICAN = frozenset({0, 2})
MAX_SIN_PUBLICAR = timedelta(hours=2)
MAX_SIN_RECIBIR = timedelta(minutes=10)
# Las activas se consultan cada minuto: 15 minutos sin respuesta correcta son 15 consultas.
MAX_SIN_ALERTAS = timedelta(minutes=15)
MAX_SIN_COPIA = timedelta(hours=2)
MAX_SIN_COPIA_ARCHIVO = timedelta(hours=2)
MAX_SIN_REPLICA = timedelta(hours=3)
DISCO_AVISO_PCT = 75.0
# Líneas del diario de la recogida que explican un código 2 y las de la barrera de titulares.
AVISO_TOPE = re.compile(r"tope de \d+ s agotado|no se lee|sin leer: \d+|en rojo", re.I)
RETENIDO = re.compile(r"(EODI-\d{4}-\d{5}) no se publica: su cita no respalda el titular")

Ejecutar = Callable[[Sequence[str]], str]


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


# --- Composición --------------------------------------------------------------------------
def componer(
    ahora: datetime,
    secretos: Path,
    datos_seguimiento: Path,
    disco: Path,
    ejecutar: Ejecutar = _ejecutar,
    copia_base: Callable[[], datetime | None] = ultima_copia_base,
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
    en_marcha = recogida["activa"] in ("activating", "active", "deactivating")
    retenidos: list[str] = []
    if recogida["inicio"] is not None and recogida["fin"] is not None and not en_marcha:
        lineas = diario_recogida(recogida["inicio"], ejecutar)
        frases, retenidos = avisos_del_diario(lineas)
        if codigo == 2:
            avisos.append({
                "id": "recogida_con_avisos",
                "frase": "La última recogida terminó con avisos (código 2): "
                + ("; ".join(frases) if frases else "ver su diario") + ".",
            })  # fmt: skip
        elif codigo not in (0, None):
            problemas.append({
                "id": "recogida",
                "frase": f"La última recogida falló con el código {codigo} y no publicó.",
            })  # fmt: skip
    if retenidos:
        avisos.append({
            "id": "titulares_retenidos",
            "frase": f"La barrera de titulares retiene {len(retenidos)} incidentes: sus citas no "
            "respaldan el titular (detalle en el diario de eodi-vigilancia).",
        })  # fmt: skip
        detalle.append("retenidos por la barrera de titulares: " + ", ".join(retenidos))

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

    memoria["ultima_publicacion"] = _iso(ultima_publicacion)
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
    salud, detalle = componer(datetime.now(UTC), secretos, datos, casa())
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
