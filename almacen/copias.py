"""Copias de seguridad de la base en un bucket privado de Hetzner Object Storage.

Cada copia es la base cifrada con age (comprimida con xz), el mismo formato de la rama estado.
Configuración en configuracion/copias_base.json. Tres niveles, con su retención:

- horaria/AAAA-MM-DDTHHMMSSZ.db.age: una por cada vez que se guarda la base, 48 horas;
- diaria/AAAA-MM-DD.db.age: la primera de cada día (UTC), 30 días;
- semanal/AAAA-Wss.db.age: la primera de cada semana ISO, un año.

Cada objeto lleva su SHA-256 en x-amz-meta-sha256, que se comprueba al restaurar. La poda nunca
borra la copia más reciente de un nivel. Credenciales S3: ALMACEN_ID y ALMACEN_SECRETO del
entorno o, si no están, del fichero ~/.eodi/almacen.env (o el de EODI_ALMACEN_CREDENCIALES).

Uso: python -m almacen.copias preparar | listar | guardar --fichero db.age |
     restaurar --destino base.sqlite [--objeto clave] [--huella] | podar
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from almacen.sitio import casa
from recogida.almacen_publico import firmar

registro = logging.getLogger("copias")

RAIZ = Path(__file__).resolve().parent.parent
# Otra configuración (por ejemplo, otro prefijo para un ensayo) con EODI_COPIAS_CONFIGURACION.
VARIABLE_CONFIGURACION = "EODI_COPIAS_CONFIGURACION"
CONFIGURACION = RAIZ / "configuracion" / "copias_base.json"
VARIABLE_ID = "ALMACEN_ID"
VARIABLE_SECRETO = "ALMACEN_SECRETO"
VARIABLE_CREDENCIALES = "EODI_ALMACEN_CREDENCIALES"
CREDENCIALES = casa() / ".eodi" / "almacen.env"
HORARIA, DIARIA, SEMANAL = "horaria", "diaria", "semanal"
SUFIJO = ".db.age"
TOPE_PETICION_S = 300.0
INTENTOS = 3
ESPERA_INICIAL_S = 2.0
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


@dataclass(frozen=True)
class Destino:
    ubicacion: str
    punto_s3: str
    bucket: str
    prefijo: str
    retencion: dict[str, timedelta]

    def url(self, objeto: str = "", consulta: str = "") -> str:
        url = f"{self.punto_s3.rstrip('/')}/{self.bucket}"
        if objeto:
            url += f"/{urllib.parse.quote(objeto)}"
        return f"{url}?{consulta}" if consulta else url

    def url_anonima(self, objeto: str) -> str:
        servidor = urllib.parse.urlsplit(self.punto_s3).netloc
        return f"https://{self.bucket}.{servidor}/{urllib.parse.quote(objeto)}"


def cargar_destino(ruta: Path = CONFIGURACION) -> Destino:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    r = datos["retencion"]
    retencion = {
        HORARIA: timedelta(hours=r["horaria_horas"]),
        DIARIA: timedelta(days=r["diaria_dias"]),
        SEMANAL: timedelta(days=r["semanal_dias"]),
    }
    return Destino(
        datos["ubicacion"], datos["punto_s3"], datos["bucket"], datos["prefijo"], retencion
    )


@dataclass(frozen=True)
class Credenciales:
    clave_id: str
    secreto: str

    @classmethod
    def cargar(cls) -> "Credenciales":
        clave_id = os.environ.get(VARIABLE_ID, "")
        secreto = os.environ.get(VARIABLE_SECRETO, "")
        if not (clave_id and secreto):
            ruta = Path(os.environ.get(VARIABLE_CREDENCIALES) or CREDENCIALES)
            valores: dict[str, str] = {}
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                nombre, igual, valor = linea.strip().partition("=")
                if igual and not nombre.startswith("#"):
                    valores[nombre.strip()] = valor.strip().strip("'\"")
            clave_id, secreto = valores.get(VARIABLE_ID, ""), valores.get(VARIABLE_SECRETO, "")
        if not (clave_id and secreto):
            raise OSError("faltan las credenciales S3 del almacén")
        return cls(clave_id, secreto)


@dataclass(frozen=True)
class Respuesta:
    estado: int
    cabeceras: dict[str, str]
    cuerpo: bytes


Enviar = Callable[[urllib.request.Request], Respuesta]


def enviar_http(peticion: urllib.request.Request) -> Respuesta:
    try:
        with urllib.request.urlopen(peticion, timeout=TOPE_PETICION_S) as respuesta:
            cabeceras = {k.lower(): v for k, v in respuesta.headers.items()}
            return Respuesta(respuesta.status, cabeceras, respuesta.read())
    except urllib.error.HTTPError as error:
        cabeceras = {k.lower(): v for k, v in error.headers.items()}
        return Respuesta(error.code, cabeceras, error.read())


@dataclass(frozen=True)
class Objeto:
    clave: str
    tamano: int


def nivel_y_momento(clave: str, prefijo: str) -> tuple[str, datetime] | None:
    """El nivel de una copia y el momento que dice su nombre (el inicio del día o la semana)."""
    nombre = clave.removeprefix(prefijo)
    if m := re.fullmatch(r"horaria/(\d{4}-\d{2}-\d{2}T\d{6}Z)\.db\.age", nombre):
        return HORARIA, datetime.strptime(m[1], "%Y-%m-%dT%H%M%SZ").replace(tzinfo=UTC)
    if m := re.fullmatch(r"diaria/(\d{4}-\d{2}-\d{2})\.db\.age", nombre):
        return DIARIA, datetime.strptime(m[1], "%Y-%m-%d").replace(tzinfo=UTC)
    if m := re.fullmatch(r"semanal/(\d{4})-W(\d{2})\.db\.age", nombre):
        lunes = datetime.fromisocalendar(int(m[1]), int(m[2]), 1)
        return SEMANAL, lunes.replace(tzinfo=UTC)
    return None


def claves(destino: Destino, momento: datetime) -> dict[str, str]:
    anio, semana, _ = momento.isocalendar()
    p = destino.prefijo
    return {
        HORARIA: f"{p}{HORARIA}/{momento:%Y-%m-%dT%H%M%SZ}{SUFIJO}",
        DIARIA: f"{p}{DIARIA}/{momento:%Y-%m-%d}{SUFIJO}",
        SEMANAL: f"{p}{SEMANAL}/{anio:04d}-W{semana:02d}{SUFIJO}",
    }


class Copias:
    def __init__(
        self,
        destino: Destino,
        credenciales: Credenciales,
        enviar: Enviar = enviar_http,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.destino = destino
        self.credenciales = credenciales
        self._enviar = enviar
        self._dormir = dormir

    def _peticion(
        self,
        metodo: str,
        objeto: str = "",
        cuerpo: bytes = b"",
        cabeceras: dict[str, str] | None = None,
        consulta: str = "",
    ) -> Respuesta:
        url = self.destino.url(objeto, consulta)
        espera = ESPERA_INICIAL_S
        for intento in range(1, INTENTOS + 1):
            firmadas = firmar(
                metodo, url, cabeceras or {}, hashlib.sha256(cuerpo).hexdigest(),
                self.destino.ubicacion, self.credenciales.clave_id, self.credenciales.secreto,
                datetime.now(UTC),
            )  # fmt: skip
            firmadas.pop("host")
            peticion = urllib.request.Request(
                url, data=cuerpo if metodo == "PUT" else None, method=metodo, headers=firmadas
            )
            try:
                respuesta = self._enviar(peticion)
            except OSError as error:
                if intento == INTENTOS:
                    raise
                registro.info("%s %s: %s; se repite", metodo, objeto or "bucket", error)
            else:
                if respuesta.estado < 500 or intento == INTENTOS:
                    return respuesta
            self._dormir(espera)
            espera *= 2
        raise OSError("sin intentos")

    def preparar(self) -> str:
        """Crea el bucket privado si no existe (sin política pública)."""
        if self._peticion("HEAD").estado == 200:
            return "el bucket ya existe"
        cuerpo = (
            '<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"<LocationConstraint>{self.destino.ubicacion}</LocationConstraint>"
            "</CreateBucketConfiguration>"
        ).encode()
        respuesta = self._peticion("PUT", "", cuerpo, {"Content-Type": "application/xml"})
        if respuesta.estado in (200, 409):
            return f"bucket creado ({respuesta.estado})"
        raise OSError(f"no se pudo crear el bucket: HTTP {respuesta.estado}")

    def existe(self, objeto: str) -> bool:
        respuesta = self._peticion("HEAD", objeto)
        if respuesta.estado in (200, 404):
            return respuesta.estado == 200
        raise OSError(f"{objeto}: HEAD {respuesta.estado}")

    def subir(self, objeto: str, cuerpo: bytes, metadatos: dict[str, str] | None = None) -> None:
        huella = hashlib.sha256(cuerpo).hexdigest()
        cabeceras = {"Content-Type": "application/octet-stream", "x-amz-meta-sha256": huella}
        cabeceras.update(metadatos or {})
        respuesta = self._peticion("PUT", objeto, cuerpo, cabeceras)
        if not 200 <= respuesta.estado < 300:
            raise OSError(f"{objeto}: PUT {respuesta.estado}")

    def metadato(self, objeto: str, nombre: str) -> str | None:
        """Una cabecera del objeto (HEAD), o None si no está."""
        respuesta = self._peticion("HEAD", objeto)
        if respuesta.estado == 404:
            return None
        if respuesta.estado != 200:
            raise OSError(f"{objeto}: HEAD {respuesta.estado}")
        return respuesta.cabeceras.get(nombre.lower())

    def bajar(self, objeto: str) -> bytes:
        respuesta = self._peticion("GET", objeto)
        if respuesta.estado != 200:
            raise OSError(f"{objeto}: GET {respuesta.estado}")
        esperada = respuesta.cabeceras.get("x-amz-meta-sha256")
        if esperada and hashlib.sha256(respuesta.cuerpo).hexdigest() != esperada:
            raise OSError(f"{objeto}: la huella no coincide con la guardada")
        return respuesta.cuerpo

    def borrar(self, objeto: str) -> None:
        respuesta = self._peticion("DELETE", objeto)
        if respuesta.estado not in (200, 204, 404):
            raise OSError(f"{objeto}: DELETE {respuesta.estado}")

    def listar(self, prefijo: str) -> Iterator[Objeto]:
        continuacion = ""
        while True:
            parametros = {"list-type": "2", "prefix": prefijo}
            if continuacion:
                parametros["continuation-token"] = continuacion
            consulta = "&".join(
                f"{k}={urllib.parse.quote(v, safe='-_.~')}" for k, v in sorted(parametros.items())
            )
            respuesta = self._peticion("GET", consulta=consulta)
            if respuesta.estado != 200:
                raise OSError(f"listado {prefijo}: GET {respuesta.estado}")
            raiz = ET.fromstring(respuesta.cuerpo)
            for contenido in raiz.iter(f"{NS}Contents"):
                yield Objeto(
                    contenido.findtext(f"{NS}Key", ""), int(contenido.findtext(f"{NS}Size", "0"))
                )
            if raiz.findtext(f"{NS}IsTruncated", "false") != "true":
                return
            continuacion = raiz.findtext(f"{NS}NextContinuationToken", "")

    def copias(self) -> list[tuple[str, datetime, Objeto]]:
        """Todas las copias reconocibles, con su nivel y su momento, de la más antigua a la
        más reciente."""
        encontradas = []
        for objeto in self.listar(self.destino.prefijo):
            leido = nivel_y_momento(objeto.clave, self.destino.prefijo)
            if leido is not None:
                encontradas.append((leido[0], leido[1], objeto))
        return sorted(encontradas, key=lambda c: (c[1], c[2].clave))

    def guardar(self, cifrada: Path, momento: datetime) -> dict[str, object]:
        """Sube la copia de este momento y, si es la primera del día o de la semana, también a
        esos niveles; después poda lo caducado."""
        cuerpo = cifrada.read_bytes()
        hechas = []
        for nivel, clave in claves(self.destino, momento).items():
            if nivel != HORARIA and self.existe(clave):
                continue
            self.subir(clave, cuerpo)
            hechas.append(clave)
        return {"subidas": hechas, "tamano": len(cuerpo), "borradas": self.podar(momento)}

    def podar(self, momento: datetime) -> list[str]:
        """Borra las copias que han pasado su retención; nunca la más reciente de un nivel."""
        por_nivel: dict[str, list[tuple[datetime, str]]] = {}
        for nivel, cuando, objeto in self.copias():
            por_nivel.setdefault(nivel, []).append((cuando, objeto.clave))
        borradas = []
        for nivel, lista in por_nivel.items():
            for cuando, clave in lista[:-1]:
                if momento - cuando > self.destino.retencion[nivel]:
                    self.borrar(clave)
                    borradas.append(clave)
        return borradas

    def ultima(self) -> str | None:
        horarias = [c for c in self.copias() if c[0] == HORARIA]
        todas = horarias or self.copias()
        return todas[-1][2].clave if todas else None

    def restaurar(self, destino: Path, objeto: str | None = None) -> dict[str, object]:
        """Baja una copia (la última si no se dice cuál), comprueba su huella, la descifra en
        `destino` y comprueba su integridad."""
        from almacen import sitio

        clave = objeto or self.ultima()
        if clave is None:
            raise OSError("no hay ninguna copia")
        cuerpo = self.bajar(clave)
        sitio.descifrar_a_fichero(cuerpo, destino)
        if not sitio.integra(destino):
            raise OSError(f"{clave}: la base restaurada no pasa la comprobación de integridad")
        return {"objeto": clave, "tamano_cifrado": len(cuerpo), "tamano": destino.stat().st_size}

    def anonimo_rechazado(self, objeto: str) -> bool:
        """Sin firma, el objeto no se puede leer (el bucket no es público)."""
        peticion = urllib.request.Request(self.destino.url_anonima(objeto), method="GET")
        return self._enviar(peticion).estado in (401, 403)


def cliente() -> Copias:
    configuracion = os.environ.get(VARIABLE_CONFIGURACION)
    destino = cargar_destino(Path(configuracion)) if configuracion else cargar_destino()
    return Copias(destino, Credenciales.cargar())


def guardar(cifrada: Path, momento: datetime) -> dict[str, object]:
    return cliente().guardar(cifrada, momento)


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ordenes = opciones.add_subparsers(dest="orden", required=True)
    ordenes.add_parser("preparar", help="crea el bucket privado y comprueba que no es público")
    ordenes.add_parser("listar")
    ordenes.add_parser("podar")
    subir = ordenes.add_parser("guardar", help="sube una base cifrada como copia de ahora")
    subir.add_argument("--fichero", type=Path, required=True)
    restaurar = ordenes.add_parser("restaurar")
    restaurar.add_argument("--destino", type=Path, required=True)
    restaurar.add_argument("--objeto", help="clave de la copia; por defecto, la última")
    restaurar.add_argument("--huella", action="store_true", help="calcula la huella del contenido")
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    copias = cliente()
    ahora = datetime.now(UTC)
    if args.orden == "preparar":
        registro.info("%s", copias.preparar())
        prueba = f"{copias.destino.prefijo}prueba-privada.txt"
        copias.subir(prueba, b"privado")
        rechazado = copias.anonimo_rechazado(prueba)
        copias.borrar(prueba)
        registro.info("sin credenciales: %s", "rechazado" if rechazado else "SE PUEDE LEER")
        return 0 if rechazado else 1
    if args.orden == "listar":
        for nivel, cuando, objeto in copias.copias():
            sys.stdout.write(f"{nivel}\t{cuando.isoformat()}\t{objeto.tamano}\t{objeto.clave}\n")
        return 0
    if args.orden == "podar":
        sys.stdout.write(json.dumps(copias.podar(ahora), indent=1) + "\n")
        return 0
    if args.orden == "guardar":
        sys.stdout.write(json.dumps(copias.guardar(args.fichero, ahora), indent=1) + "\n")
        return 0
    from almacen import cifrado, sitio

    cifrado.cargar_clave_local()
    destino: Path = args.destino
    if destino.exists():
        registro.error("%s ya existe: no se sobrescribe", destino)
        return 1
    with TemporaryDirectory(dir=destino.parent) as temporal:
        parcial = Path(temporal) / destino.name
        resultado = copias.restaurar(parcial, args.objeto)
        os.replace(parcial, destino)
    if args.huella:
        resultado["huella"] = sitio.huella_fichero(destino)
    sys.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
