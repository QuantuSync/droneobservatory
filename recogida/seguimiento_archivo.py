"""Archivo del seguimiento en directo: compresión, índice diario y copia de seguridad privada.

Lo que deja `recogida/seguimiento.py` en `<datos>/<fuente>/<AAAA>/<MM>/<fuente>-<día>T<HH>.jsonl`:

- **Compresión.** Cada fichero de una hora ya cerrada (la hora acabó hace más de 2 minutos) se
  comprime a `.jsonl.gz` junto a él; se comprueba que el comprimido devuelve exactamente los mismos
  bytes y solo entonces se quita el `.jsonl`. Si ya hay un `.jsonl.gz` de esa hora (líneas que
  llegaron tarde), el nuevo se llama `.parte2.jsonl.gz`, `.parte3…`: nunca se reescribe nada.
- **Índice diario** (`<datos>/indices/<AAAA-MM-DD>.json`), una vez terminado el día y comprimidas
  todas sus horas: mensajes recibidos por tipo y por vía, amenazas distintas, huecos de conexión,
  publicaciones de la Fuerza Aérea, y nombre, líneas, tamaño y huella SHA-256 de cada fichero. Una
  vez escrito no se rehace.
- **Copia de seguridad** en un bucket privado de Hetzner Object Storage
  (`configuracion/archivo_seguimiento.json`; sin política pública: solo se lee con credenciales),
  una vez al día, con los ficheros del día anterior y su índice. Cada objeto lleva su huella en
  `x-amz-meta-sha256`; antes de subir se mira si ya está: con la misma huella no se sube, con otra
  se avisa y no se sobrescribe. Lo copiado queda anotado en `<datos>/copias/<AAAA-MM-DD>.json`.

Este trabajo no corre nunca entre los minutos 15 y 40 de la hora ni mientras la recogida horaria
esté en marcha (se mira la unidad, sin tocar su cerrojo), y solo hay uno a la vez (su propio
cerrojo, que toma servidor/seguimiento_archivo.sh). Lo lanza el temporizador
eodi-seguimiento-archivo.

Uso: python -m recogida.seguimiento_archivo ciclo
     python -m recogida.seguimiento_archivo copiar --dia AAAA-MM-DD   (también el día en curso:
         sube las horas ya comprimidas)
     python -m recogida.seguimiento_archivo restaurar --objeto <clave> --destino <fichero>
     python -m recogida.seguimiento_archivo preparar | resumen
"""

import argparse
import gzip
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida.almacen_publico import VARIABLE_ID, VARIABLE_SECRETO, firmar
from recogida.seguimiento import KPSZSU, NEPTUN, directorio_datos

registro = logging.getLogger("seguimiento_archivo")

RAIZ = Path(__file__).resolve().parent.parent
CONFIGURACION = RAIZ / "configuracion" / "archivo_seguimiento.json"
FUENTES = (NEPTUN, KPSZSU)
MARGEN_CIERRE = timedelta(minutes=2)
MINUTOS_PROHIBIDOS = range(15, 40)
UNIDAD_RECOGIDA = "eodi-recogida.service"
TOPE_PETICION_S = 120.0
LEEME = (
    "Copia de seguridad privada del archivo del seguimiento en directo del European Observatory\n"
    "of Drone Incidents (recogida/seguimiento_archivo.py). Ficheros por hora en JSON por lineas,\n"
    "comprimidos, con su SHA-256 en x-amz-meta-sha256, e indices diarios. Nada se sobrescribe.\n"
)


# --- Turno ----------------------------------------------------------------------------------
def recogida_en_marcha() -> bool:
    try:
        salida = subprocess.run(
            ["systemctl", "is-active", UNIDAD_RECOGIDA], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return salida.stdout.strip() in ("active", "activating", "deactivating")


def esperar_turno(
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
    en_marcha: Callable[[], bool] = recogida_en_marcha,
    dormir: Callable[[float], None] = time.sleep,
) -> None:
    """Espera fuera de los minutos 15 a 40 y a que la recogida horaria no esté en marcha."""
    avisado = False
    while ahora().minute in MINUTOS_PROHIBIDOS or en_marcha():
        if not avisado:
            registro.info("en pausa: es la hora de la recogida horaria")
            avisado = True
        dormir(30)


# --- Compresión -----------------------------------------------------------------------------
def hora_del_fichero(ruta: Path) -> datetime | None:
    """La hora UTC de un fichero `<fuente>-AAAA-MM-DDTHH.jsonl[.gz]`."""
    nombre = ruta.name.split(".", 1)[0]
    try:
        return datetime.strptime(nombre[-13:], "%Y-%m-%dT%H")
    except ValueError:
        return None


def _hora(ruta: Path) -> datetime | None:
    hora = hora_del_fichero(ruta)
    return hora.replace(tzinfo=UTC) if hora else None


def destino_comprimido(ruta: Path) -> Path:
    base = ruta.with_suffix("")  # sin .jsonl
    destino = base.with_name(base.name + ".jsonl.gz")
    parte = 2
    while destino.exists():
        destino = base.with_name(f"{base.name}.parte{parte}.jsonl.gz")
        parte += 1
    return destino


def comprimir(ruta: Path) -> Path:
    """Comprime un fichero de hora cerrada y quita el original solo si el comprimido devuelve
    exactamente lo mismo."""
    datos = ruta.read_bytes()
    estado = ruta.stat()
    destino = destino_comprimido(ruta)
    temporal = destino.with_name(destino.name + ".tmp")
    temporal.write_bytes(gzip.compress(datos, compresslevel=9, mtime=0))
    if gzip.decompress(temporal.read_bytes()) != datos:
        temporal.unlink()
        raise OSError(f"{ruta.name}: el comprimido no coincide")
    despues = ruta.stat()
    if (despues.st_size, despues.st_mtime_ns) != (estado.st_size, estado.st_mtime_ns):
        temporal.unlink()
        raise OSError(f"{ruta.name}: ha cambiado mientras se comprimía")
    os.replace(temporal, destino)
    ruta.unlink()
    return destino


def comprimir_cerrados(datos: Path, ahora: datetime) -> list[Path]:
    hechos: list[Path] = []
    for fuente in FUENTES:
        for ruta in sorted((datos / fuente).glob("*/*/*.jsonl")):
            hora = _hora(ruta)
            if hora is None or hora + timedelta(hours=1) + MARGEN_CIERRE > ahora:
                continue
            try:
                hechos.append(comprimir(ruta))
            except OSError as error:
                registro.warning("no se comprime %s: %s", ruta.name, error)
    return hechos


# --- Índice diario --------------------------------------------------------------------------
def ficheros_dia(datos: Path, fuente: str, dia: date) -> list[Path]:
    carpeta = datos / fuente / f"{dia:%Y}" / f"{dia:%m}"
    return sorted(carpeta.glob(f"{fuente}-{dia:%Y-%m-%d}T*.jsonl*"))


def _lineas(ruta: Path) -> Iterator[dict[str, Any]]:
    abrir = gzip.open if ruta.name.endswith(".gz") else open
    with abrir(ruta, "rt", encoding="utf-8") as fichero:
        for linea in fichero:
            if linea.strip():
                yield json.loads(linea)


def _huella(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fichero:
        for trozo in iter(lambda: fichero.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def _amenazas(crudo: str, ids: set[str]) -> str | None:
    """Anota los ids de amenaza de un mensaje del flujo o de un cuerpo REST; devuelve el tipo."""
    try:
        datos = json.loads(crudo)
    except ValueError:
        return None
    if not isinstance(datos, dict):
        return None
    tipo = datos.get("type")
    cuerpo = datos.get("data", datos)
    candidatos: list[Any] = []
    if isinstance(cuerpo, dict):
        if isinstance(cuerpo.get("threats"), list):
            candidatos = cuerpo["threats"]
        elif "id" in cuerpo:
            candidatos = [cuerpo]
    for amenaza in candidatos:
        if isinstance(amenaza, dict) and isinstance(amenaza.get("id"), str):
            ids.add(amenaza["id"])
    return tipo if isinstance(tipo, str) else None


def componer_indice(datos: Path, dia: date) -> dict[str, Any]:
    por_tipo: Counter[str] = Counter()
    por_via: Counter[str] = Counter()
    eventos: Counter[str] = Counter()
    ids: set[str] = set()
    huecos: list[dict[str, Any]] = []
    ficheros: list[dict[str, Any]] = []
    kpszsu_ids: set[int] = set()
    kpszsu_versiones = 0
    for fuente in FUENTES:
        for ruta in ficheros_dia(datos, fuente, dia):
            lineas = 0
            for linea in _lineas(ruta):
                lineas += 1
                if "evento" in linea:
                    eventos[f"{fuente}:{linea['evento']}"] += 1
                    if linea["evento"] == "hueco":
                        huecos.append({"fuente": fuente, **{
                            k: linea.get(k) for k in ("desde", "hasta", "segundos", "motivo")
                        }})  # fmt: skip
                    continue
                via = str(linea.get("via"))
                por_via[f"{fuente}:{via}"] += 1
                if fuente == KPSZSU:
                    kpszsu_ids.add(int(linea["id"]))
                    kpszsu_versiones += 1 if int(linea.get("version", 0)) > 0 else 0
                    continue
                if linea.get("binario"):
                    por_tipo["binario"] += 1
                    continue
                tipo = _amenazas(str(linea.get("crudo", "")), ids)
                if via == "ws":
                    por_tipo[tipo or "sin_tipo"] += 1
            ficheros.append({
                "nombre": str(ruta.relative_to(datos)).replace(os.sep, "/"),
                "lineas": lineas,
                "bytes": ruta.stat().st_size,
                "sha256": _huella(ruta),
            })  # fmt: skip
    return {
        "dia": dia.isoformat(),
        "generado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "neptun": {
            "mensajes_por_tipo": dict(sorted(por_tipo.items())),
            "amenazas_distintas": len(ids),
        },
        "mensajes_por_via": dict(sorted(por_via.items())),
        "eventos": dict(sorted(eventos.items())),
        "huecos": huecos,
        "kpszsu": {"publicaciones_distintas": len(kpszsu_ids), "ediciones": kpszsu_versiones},
        "bytes": sum(f["bytes"] for f in ficheros),
        "ficheros": ficheros,
    }


def ruta_indice(datos: Path, dia: date) -> Path:
    return datos / "indices" / f"{dia.isoformat()}.json"


def escribir_indice(datos: Path, dia: date) -> Path | None:
    """El índice de un día terminado, si todas sus horas están comprimidas y aún no existe."""
    ruta = ruta_indice(datos, dia)
    if ruta.exists():
        return None
    for fuente in FUENTES:
        if any(not r.name.endswith(".gz") for r in ficheros_dia(datos, fuente, dia)):
            return None
    indice = componer_indice(datos, dia)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(
        json.dumps(indice, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(temporal, ruta)
    return ruta


def dias_con_datos(datos: Path) -> list[date]:
    dias: set[date] = set()
    for fuente in FUENTES:
        for ruta in (datos / fuente).glob("*/*/*.jsonl*"):
            hora = _hora(ruta)
            if hora is not None:
                dias.add(hora.date())
    return sorted(dias)


# --- Copia de seguridad privada -----------------------------------------------------------
@dataclass(frozen=True)
class Destino:
    ubicacion: str
    punto_s3: str
    bucket: str
    prefijo: str

    def url(self, objeto: str = "") -> str:
        base = f"{self.punto_s3.rstrip('/')}/{self.bucket}"
        return f"{base}/{urllib.parse.quote(objeto)}" if objeto else base

    def url_anonima(self, objeto: str) -> str:
        """Dirección sin firma: tiene que responder que no (el bucket no es público)."""
        servidor = urllib.parse.urlsplit(self.punto_s3).netloc
        return f"https://{self.bucket}.{servidor}/{urllib.parse.quote(objeto)}"


def cargar_destino(ruta: Path = CONFIGURACION) -> Destino:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return Destino(datos["ubicacion"], datos["punto_s3"], datos["bucket"], datos["prefijo"])


@dataclass(frozen=True)
class Credenciales:
    clave_id: str
    secreto: str

    @classmethod
    def del_entorno(cls) -> "Credenciales | None":
        clave_id = os.environ.get(VARIABLE_ID, "")
        secreto = os.environ.get(VARIABLE_SECRETO, "")
        return cls(clave_id, secreto) if clave_id and secreto else None


@dataclass(frozen=True)
class RespuestaS3:
    estado: int
    cabeceras: dict[str, str]
    cuerpo: bytes


Enviar = Callable[[urllib.request.Request], RespuestaS3]


def enviar_http(peticion: urllib.request.Request) -> RespuestaS3:
    try:
        with urllib.request.urlopen(peticion, timeout=TOPE_PETICION_S) as respuesta:
            cabeceras = {k.lower(): v for k, v in respuesta.headers.items()}
            return RespuestaS3(respuesta.status, cabeceras, respuesta.read())
    except urllib.error.HTTPError as error:
        cabeceras = {k.lower(): v for k, v in error.headers.items()}
        return RespuestaS3(error.code, cabeceras, error.read())


class Copia:
    def __init__(
        self, destino: Destino, credenciales: Credenciales, enviar: Enviar = enviar_http
    ) -> None:
        self.destino = destino
        self.credenciales = credenciales
        self._enviar = enviar

    def _peticion(
        self,
        metodo: str,
        objeto: str,
        cuerpo: bytes = b"",
        cabeceras: dict[str, str] | None = None,
    ) -> RespuestaS3:
        url = self.destino.url(objeto)
        firmadas = firmar(
            metodo, url, cabeceras or {}, hashlib.sha256(cuerpo).hexdigest(),
            self.destino.ubicacion, self.credenciales.clave_id, self.credenciales.secreto,
            datetime.now(UTC),
        )  # fmt: skip
        firmadas.pop("host")
        peticion = urllib.request.Request(
            url, data=cuerpo if metodo == "PUT" else None, method=metodo, headers=firmadas
        )
        return self._enviar(peticion)

    def preparar(self) -> str:
        respuesta = self._peticion("HEAD", "")
        if respuesta.estado == 200:
            return "el bucket ya existe"
        cuerpo = (
            '<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"<LocationConstraint>{self.destino.ubicacion}</LocationConstraint>"
            "</CreateBucketConfiguration>"
        ).encode()
        respuesta = self._peticion("PUT", "", cuerpo, {"Content-Type": "application/xml"})
        if respuesta.estado in (200, 409):
            return f"bucket creado ({respuesta.estado})"
        raise OSError(f"no se pudo crear el bucket: HTTP {respuesta.estado} {respuesta.cuerpo!r}")

    def subir(self, objeto: str, cuerpo: bytes, tipo: str) -> str:
        """Sube si no está; nunca sobrescribe. Devuelve subido, ya_estaba o distinto."""
        huella = hashlib.sha256(cuerpo).hexdigest()
        previo = self._peticion("HEAD", objeto)
        if previo.estado == 200:
            return (
                "ya_estaba" if previo.cabeceras.get("x-amz-meta-sha256") == huella else "distinto"
            )
        if previo.estado != 404:
            raise OSError(f"{objeto}: HEAD {previo.estado}")
        respuesta = self._peticion(
            "PUT", objeto, cuerpo, {"Content-Type": tipo, "x-amz-meta-sha256": huella}
        )
        if not 200 <= respuesta.estado < 300:
            raise OSError(f"{objeto}: PUT {respuesta.estado}")
        return "subido"

    def bajar(self, objeto: str) -> tuple[bytes, str | None]:
        respuesta = self._peticion("GET", objeto)
        if respuesta.estado != 200:
            raise OSError(f"{objeto}: GET {respuesta.estado}")
        return respuesta.cuerpo, respuesta.cabeceras.get("x-amz-meta-sha256")


def ruta_copias(datos: Path, dia: date) -> Path:
    return datos / "copias" / f"{dia.isoformat()}.json"


def copiar_dia(datos: Path, dia: date, copia: Copia) -> dict[str, Any]:
    """Sube los ficheros comprimidos del día (y su índice, si ya está) que no se hayan subido."""
    anotado_ruta = ruta_copias(datos, dia)
    anotado: dict[str, Any] = {"dia": dia.isoformat(), "objetos": {}}
    if anotado_ruta.exists():
        anotado = json.loads(anotado_ruta.read_text(encoding="utf-8"))
    objetos: dict[str, Any] = anotado["objetos"]
    candidatos = [r for f in FUENTES for r in ficheros_dia(datos, f, dia) if r.name.endswith(".gz")]
    indice = ruta_indice(datos, dia)
    if indice.exists():
        candidatos.append(indice)
    resultado: Counter[str] = Counter()
    for ruta in candidatos:
        relativa = str(ruta.relative_to(datos)).replace(os.sep, "/")
        if relativa in objetos:
            resultado["anotado"] += 1
            continue
        cuerpo = ruta.read_bytes()
        tipo = "application/gzip" if ruta.name.endswith(".gz") else "application/json"
        estado = copia.subir(copia.destino.prefijo + relativa, cuerpo, tipo)
        resultado[estado] += 1
        if estado == "distinto":
            registro.warning("%s ya está en la copia con otra huella: no se sobrescribe", relativa)
            continue
        objetos[relativa] = {
            "sha256": hashlib.sha256(cuerpo).hexdigest(),
            "bytes": len(cuerpo),
            "copiado": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    anotado_ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = anotado_ruta.with_name(anotado_ruta.name + ".tmp")
    temporal.write_text(json.dumps(anotado, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporal, anotado_ruta)
    return dict(resultado)


def dia_copiado(datos: Path, dia: date) -> bool:
    """Copiado del todo: con su índice y todos sus ficheros anotados."""
    ruta = ruta_copias(datos, dia)
    if not ruta.exists() or not ruta_indice(datos, dia).exists():
        return False
    objetos = json.loads(ruta.read_text(encoding="utf-8")).get("objetos", {})
    relativos = [
        str(r.relative_to(datos)).replace(os.sep, "/")
        for f in FUENTES
        for r in ficheros_dia(datos, f, dia)
    ]
    return f"indices/{dia.isoformat()}.json" in objetos and all(r in objetos for r in relativos)


# --- Órdenes ----------------------------------------------------------------------------------
def ciclo(datos: Path, ahora: datetime, copia: Copia | None) -> dict[str, Any]:
    comprimidos = comprimir_cerrados(datos, ahora)
    indices: list[str] = []
    copias: dict[str, Any] = {}
    for dia in dias_con_datos(datos):
        if dia >= ahora.date():
            continue
        hecho = escribir_indice(datos, dia)
        if hecho:
            indices.append(dia.isoformat())
        if copia is not None and ruta_indice(datos, dia).exists() and not dia_copiado(datos, dia):
            copias[dia.isoformat()] = copiar_dia(datos, dia, copia)
    return {
        "comprimidos": len(comprimidos),
        "indices": indices,
        "copias": copias,
    }


def resumen(datos: Path) -> dict[str, Any]:
    dias = []
    for ruta in sorted((datos / "indices").glob("*.json")):
        indice = json.loads(ruta.read_text(encoding="utf-8"))
        dias.append({
            "dia": indice["dia"],
            "bytes": indice["bytes"],
            "tipos": indice["neptun"]["mensajes_por_tipo"],
            "amenazas": indice["neptun"]["amenazas_distintas"],
            "huecos": len(indice["huecos"]),
            "kpszsu": indice["kpszsu"]["publicaciones_distintas"],
            "copiado": dia_copiado(datos, date.fromisoformat(indice["dia"])),
        })  # fmt: skip
    abiertos = sorted(
        str(r.relative_to(datos)) for f in FUENTES for r in (datos / f).glob("*/*/*.jsonl")
    )
    return {"dias": dias, "sin_comprimir": abiertos}


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument("--datos", type=Path)
    sub = opciones.add_subparsers(dest="orden", required=True)
    sub.add_parser("ciclo")
    c = sub.add_parser("copiar")
    c.add_argument("--dia", type=date.fromisoformat, required=True)
    r = sub.add_parser("restaurar")
    r.add_argument("--objeto", required=True)
    r.add_argument("--destino", type=Path, required=True)
    sub.add_parser("preparar")
    sub.add_parser("resumen")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos: Path = args.datos or directorio_datos()
    if args.orden == "resumen":
        print(json.dumps(resumen(datos), ensure_ascii=False, indent=1))
        return 0
    credenciales = Credenciales.del_entorno()
    copia = Copia(cargar_destino(), credenciales) if credenciales else None
    if args.orden in ("preparar", "restaurar") and copia is None:
        print("faltan las credenciales del almacén", file=sys.stderr)
        return 1
    if args.orden == "preparar":
        assert copia is not None
        print(copia.preparar())
        leeme = copia.destino.prefijo + "LEEME.txt"
        print(f"{leeme}: {copia.subir(leeme, LEEME.encode(), 'text/plain; charset=utf-8')}")
        # Sin credenciales, ni el objeto ni el listado: el bucket no es público.
        codigos = [
            enviar_http(urllib.request.Request(url, method="GET")).estado
            for url in (copia.destino.url_anonima(leeme), copia.destino.url_anonima(""))
        ]
        print(f"lectura sin credenciales: objeto HTTP {codigos[0]}, listado HTTP {codigos[1]}")
        return 0 if all(c in (401, 403) for c in codigos) else 1
    if args.orden == "restaurar":
        assert copia is not None
        cuerpo, huella = copia.bajar(args.objeto)
        calculada = hashlib.sha256(cuerpo).hexdigest()
        args.destino.write_bytes(cuerpo)
        print(f"{len(cuerpo)} bytes, sha256 {calculada}, anotada {huella}")
        return 0 if huella == calculada else 1
    esperar_turno()
    if copia is None:
        registro.warning("sin credenciales del almacén: no se hace la copia de seguridad")
    if args.orden == "copiar":
        comprimir_cerrados(datos, datetime.now(UTC))
        if args.dia < datetime.now(UTC).date():
            escribir_indice(datos, args.dia)
        if copia is None:
            return 1
        print(json.dumps(copiar_dia(datos, args.dia, copia)))
        return 0
    print(json.dumps(ciclo(datos, datetime.now(UTC), copia), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
