"""Archivo diario de adsb.lol: localización de cada día, descarga en flujo y lectura de trazas.

adsb.lol publica cada día en GitHub, en un repositorio por año (`adsblol/globe_history_AAAA`),
una copia de `/var/globe_history` de readsb: una traza por aeronave
(`traces/xx/trace_full_<icao>.json`, JSON comprimido con gzip) más el mapa de calor y ACAS.
Licencia ODbL 1.0 (© adsb.lol contributors); los receptores ceden sus datos con CC0.

Cada día tiene varias publicaciones (`v2025.09.22-planes-readsb-prod-0`, `...-staging-0`, y
algunos días de 2025 `...-prod-0tmp`); el tar va partido en trozos de 2 GB (`.tar.aa`,
`.tar.ab`) o entero (`.tar`). Se usa prod-0 salvo que staging-0 sea más de un 10 % mayor
(adsb.lol pide usar la que no sea mucho menor), y prod-0tmp donde no hay prod-0. Comprobado
el 1 de octubre de 2026 con la lista de publicaciones: un día pesa de 2 a 4,3 GB (mediana
3,3 GB), se publica hacia las 03:25 UTC del día siguiente (la mitad antes de las 03:26 y nueve
de cada diez antes de las 00:40 del día después) y faltan el 6 de mayo de 2026 y, en prod-0,
del 28 de mayo al 10 de junio de 2025 (están en prod-0tmp). El 5 de mayo de 2026 (0,24 GB) y
el 11 de junio de 2025 (0,73 GB) están incompletos: su cobertura sale insuficiente sola.

Los trozos se leen en flujo, uno detrás de otro, sin guardar el día en disco.

Formato de una traza (readsb, README-json.md, «trace jsons»): `icao`, `r` (matrícula), `t`
(tipo OACI), `dbFlags` (1 militar, 2 interesante, 4 PIA, 8 LADD), `desc`, `ownOp`, `year`,
`timestamp` (inicio del día, segundos desde 1970) y `trace`, una lista de puntos de 14
campos: segundos desde `timestamp`, latitud, longitud, altitud barométrica en pies (o
"ground", o null), velocidad sobre el suelo en nudos, rumbo, marcas (1 posición antigua, 2
inicio de tramo, 4 velocidad vertical geométrica, 8 altitud geométrica), velocidad vertical
en pies por minuto, datos de la aeronave (null salvo cuando cambian; con `nic`, `nac_p`, `sil`,
`version`, `flight`, `category`, `squawk`...), fuente de la posición (`adsb_icao`, `mlat`,
`tisb_icao`...), altitud geométrica, velocidad vertical geométrica, velocidad indicada y
alabeo. Hay puntos repetidos con el mismo instante (uno con los datos de la aeronave).
"""

import gzip
import http.client
import io
import json
import tarfile
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any, BinaryIO

from proceso.vuelos import Traza
from recogida.descarga import AGENTE_EODI

REPOSITORIO = "https://github.com/adsblol/globe_history_{anio}"
DESCARGA = REPOSITORIO + "/releases/download/{etiqueta}/{fichero}"
PAGINA = REPOSITORIO + "/releases/tag/{etiqueta}"
PROD, PROD_TMP, STAGING = "prod-0", "prod-0tmp", "staging-0"
# staging-0 solo se prefiere si es claramente mayor que prod-0.
MARGEN_STAGING = 1.10
SUFIJOS_TROZO = tuple(f"a{c}" for c in "abcdefghij")
TIEMPO_LIMITE_S = 120.0
BLOQUE = 1 << 20

# Abre una URL con un método («HEAD» o «GET») desde un byte (petición Range si no es 0).
Abridor = Callable[..., Any]
# Una conexión que se corta antes de tiempo se reanuda desde donde iba, como mucho tantas veces,
# con espera creciente entre una y otra (2, 4, 8, 16 y 32 s): antes se reanudaba en el acto.
REANUDACIONES = 5
ESPERA_REANUDACION_S = 2.0


class SinPublicar(LookupError):
    """adsb.lol aún no ha publicado el día (o no lo publicará)."""


class LecturaIncompleta(OSError):
    """La descarga del día no llegó entera: el día no se da por procesado y se repite."""


@dataclass(frozen=True)
class Publicacion:
    dia: date
    anio_repositorio: int
    etiqueta: str
    ficheros: tuple[str, ...]
    bytes: int
    tamanos: tuple[int, ...] = ()

    @property
    def urls(self) -> list[str]:
        return [
            DESCARGA.format(anio=self.anio_repositorio, etiqueta=self.etiqueta, fichero=f)
            for f in self.ficheros
        ]

    @property
    def pagina(self) -> str:
        return PAGINA.format(anio=self.anio_repositorio, etiqueta=self.etiqueta)


def etiqueta(dia: date, sufijo: str) -> str:
    return f"v{dia:%Y.%m.%d}-planes-readsb-{sufijo}"


def abrir_urllib(url: str, metodo: str, desde: int = 0) -> Any:
    cabeceras = {"User-Agent": AGENTE_EODI}
    if desde:
        cabeceras["Range"] = f"bytes={desde}-"
    peticion = urllib.request.Request(url, method=metodo, headers=cabeceras)
    return urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE_S)


def _tamano(url: str, abrir: Abridor) -> int | None:
    """Bytes del fichero (HEAD, siguiendo la redirección), o None si no existe."""
    try:
        with abrir(url, "HEAD") as respuesta:
            return int(respuesta.headers.get("Content-Length") or 0)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def _publicacion(dia: date, anio: int, sufijo: str, abrir: Abridor) -> Publicacion | None:
    nombre = etiqueta(dia, sufijo)

    def url(fichero: str) -> str:
        return DESCARGA.format(anio=anio, etiqueta=nombre, fichero=fichero)

    entero = _tamano(url(f"{nombre}.tar"), abrir)
    if entero is not None:
        return Publicacion(dia, anio, nombre, (f"{nombre}.tar",), entero, (entero,))
    ficheros, total, tamanos = [], 0, []
    for sufijo_trozo in SUFIJOS_TROZO:
        tamano = _tamano(url(f"{nombre}.tar.{sufijo_trozo}"), abrir)
        if tamano is None:
            break
        ficheros.append(f"{nombre}.tar.{sufijo_trozo}")
        tamanos.append(tamano)
        total += tamano
    if not ficheros:
        return None
    return Publicacion(dia, anio, nombre, tuple(ficheros), total, tuple(tamanos))


def publicaciones(dia: date, abrir: Abridor = abrir_urllib) -> list[Publicacion]:
    """Las publicaciones del día en el orden en que se prueban: prod-0 (o prod-0tmp) y después
    staging-0, salvo que staging-0 sea más de un 10 % mayor. Si una no se puede leer entera
    (el prod-0 del 15 de octubre de 2025 se corta siempre en el mismo byte), se usa la otra.
    SinPublicar si aún no hay ninguna."""
    for anio in (dia.year, dia.year + 1):
        prod = _publicacion(dia, anio, PROD, abrir) or _publicacion(dia, anio, PROD_TMP, abrir)
        staging = _publicacion(dia, anio, STAGING, abrir)
        orden = [p for p in (prod, staging) if p is not None]
        if prod and staging and staging.bytes > prod.bytes * MARGEN_STAGING:
            orden.reverse()
        if orden:
            return orden
    raise SinPublicar(f"adsb.lol no tiene publicado el {dia.isoformat()}")


def localizar(dia: date, abrir: Abridor = abrir_urllib) -> Publicacion:
    """La publicación que se usa primero para el día."""
    return publicaciones(dia, abrir)[0]


class Encadenado(io.RawIOBase):
    """Los trozos del tar leídos uno detrás de otro como un solo flujo. Con los tamaños de los
    trozos, una conexión que se corta antes de tiempo se reanuda desde ese byte (petición
    Range) hasta REANUDACIONES veces; si aun así un trozo no llega entero, LecturaIncompleta."""

    def __init__(
        self,
        urls: list[str],
        abrir: Abridor = abrir_urllib,
        tamanos: tuple[int, ...] = (),
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._dormir = dormir
        self._pendientes = list(urls)
        self._tamanos = list(tamanos)
        self._abrir = abrir
        self._actual: Any = None
        self._url = ""
        self._esperado: int | None = None
        self._leidos_trozo = 0
        self._reanudaciones = 0
        self.bytes = 0

    def readable(self) -> bool:
        return True

    def readinto(self, destino: Any) -> int:
        while True:
            if self._actual is None:
                if not self._pendientes:
                    return 0
                self._url = self._pendientes.pop(0)
                self._esperado = self._tamanos.pop(0) if self._tamanos else None
                self._leidos_trozo = 0
                self._actual = self._abrir(self._url, "GET")
            try:
                leidos = self._actual.readinto(destino)
            except (OSError, http.client.HTTPException):
                leidos = 0
            if leidos:
                self.bytes += leidos
                self._leidos_trozo += leidos
                return int(leidos)
            self._actual.close()
            self._actual = None
            if self._esperado is not None and self._leidos_trozo < self._esperado:
                if self._reanudaciones >= REANUDACIONES:
                    raise LecturaIncompleta(
                        f"{self._url}: {self._leidos_trozo} de {self._esperado} bytes"
                    )
                self._dormir(ESPERA_REANUDACION_S * 2**self._reanudaciones)
                self._reanudaciones += 1
                self._actual = self._abrir(self._url, "GET", self._leidos_trozo)

    def close(self) -> None:
        if self._actual is not None:
            self._actual.close()
            self._actual = None
        super().close()


def documentos(flujo: BinaryIO, ilegibles: list[str] | None = None) -> Iterator[dict[str, Any]]:
    """Cada traza del tar como el documento JSON de readsb. Una traza que no se puede leer
    (gzip o JSON dañado: pasó con una del 15 de octubre de 2025) se salta y se anota su nombre
    en `ilegibles`: no tumba el día entero."""
    with tarfile.open(fileobj=flujo, mode="r|") as tar:
        for miembro in tar:
            if not miembro.isfile() or "/traces/" not in f"/{miembro.name.lstrip('./')}":
                continue
            fichero = tar.extractfile(miembro)
            if fichero is None:
                continue
            crudo = fichero.read()
            try:
                if crudo[:2] == b"\x1f\x8b":
                    crudo = gzip.decompress(crudo)
                documento = json.loads(crudo)
            except (OSError, EOFError, ValueError, zlib.error):
                if ilegibles is not None:
                    ilegibles.append(miembro.name)
                continue
            yield documento


def toca_caja(
    documento: dict[str, Any], oeste: float, sur: float, este: float, norte: float
) -> bool:
    return any(sur <= p[1] <= norte and oeste <= p[2] <= este for p in documento.get("trace", ()))


def _numero(valor: Any) -> float | None:
    return float(valor) if isinstance(valor, int | float) and not isinstance(valor, bool) else None


def leer_traza(
    documento: dict[str, Any], caja: tuple[float, float, float, float] | None = None
) -> Traza:
    """La traza de readsb ordenada por tiempo, sin repetidos y con los datos de la aeronave
    (NIC, NACp, versión, indicativo, categoría) arrastrados de su último valor. Con `caja`
    (oeste, sur, este, norte), solo los puntos dentro."""
    base = float(documento.get("timestamp") or 0.0)
    traza = Traza(
        icao=str(documento.get("icao", "")).lower(),
        matricula=documento.get("r"),
        tipo=documento.get("t"),
        marcas=int(documento.get("dbFlags") or 0),
        descripcion=documento.get("desc"),
        operador=documento.get("ownOp"),
    )
    nic = nacp = version = None
    indicativo: str | None = None
    categorias: dict[str, int] = {}
    ultimo: float | None = None
    for punto in sorted(documento.get("trace", ()), key=lambda p: p[0]):
        datos = punto[8] if len(punto) > 8 and isinstance(punto[8], dict) else None
        if datos:
            nic = datos.get("nic", nic)
            nacp = datos.get("nac_p", nacp)
            version = datos.get("version", version)
            # readsb rellena con «@» un indicativo que no se ha recibido.
            vuelo = (datos.get("flight") or "").strip().strip("@").strip()
            indicativo = vuelo or indicativo
            if datos.get("category"):
                categorias[datos["category"]] = categorias.get(datos["category"], 0) + 1
        t = base + float(punto[0])
        if ultimo is not None and t == ultimo:
            continue
        lat, lon = float(punto[1]), float(punto[2])
        if caja is not None and not (caja[1] <= lat <= caja[3] and caja[0] <= lon <= caja[2]):
            continue
        ultimo = t
        alt = punto[3]
        suelo = alt == "ground"
        geometrica = _numero(punto[10]) if len(punto) > 10 else None
        altitud = 0.0 if suelo else (_numero(alt) if _numero(alt) is not None else geometrica)
        marcas = int(punto[6] or 0)
        fuente = punto[9] if len(punto) > 9 and isinstance(punto[9], str) else ""
        traza.t.append(t)
        traza.lat.append(lat)
        traza.lon.append(lon)
        traza.alt.append(None if altitud is None else altitud)
        traza.suelo.append(suelo)
        traza.gs.append(_numero(punto[4]))
        traza.rumbo.append(_numero(punto[5]))
        traza.vz.append(_numero(punto[7]))
        traza.tramo_nuevo.append(bool(marcas & 2))
        traza.nic.append(nic)
        traza.nacp.append(nacp)
        traza.version.append(version)
        traza.adsb.append(fuente.startswith("adsb"))
        traza.indicativo.append(indicativo)
    if categorias:
        traza.categoria = max(categorias, key=lambda c: categorias[c])
    return traza
