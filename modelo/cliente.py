"""Cliente HTTP del servicio del extractor, con la biblioteca estándar.

Todo lo que identifica al proveedor (direcciones, modelo, cabeceras y su
versión) llega en variables de entorno, que en GitHub Actions son secretos:

- EODI_EXTRACTOR_CLAVE: la clave.
- EODI_EXTRACTOR_URL: el servicio de mensajes.
- EODI_EXTRACTOR_URL_LOTES: el servicio de lotes.
- EODI_EXTRACTOR_MODELO: el modelo.
- EODI_EXTRACTOR_CABECERAS: JSON con las cabeceras propias del servicio; el
  texto «{clave}» en un valor se sustituye por la clave.

En local se cargan de un fichero fuera de cualquier repositorio. Los errores
nunca llevan la clave ni la respuesta completa.
"""

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VARIABLES = (
    "EODI_EXTRACTOR_CLAVE",
    "EODI_EXTRACTOR_URL",
    "EODI_EXTRACTOR_URL_LOTES",
    "EODI_EXTRACTOR_MODELO",
    "EODI_EXTRACTOR_CABECERAS",
)
RUTA_LOCAL = Path.home() / ".eodi" / "extractor.env"
MARCA_CLAVE = "{clave}"
# Una respuesta de unos cientos de tokens tarda segundos; 120 s cubren un servicio lento.
TIEMPO_LIMITE_S = 120.0
# 429 y 5xx se reintentan 4 veces con espera doble desde 10 s (150 s en total), o lo que
# pida el servicio en retry-after con tope de 300 s.
REINTENTOS = 4
ESPERA_INICIAL_S = 10.0
ESPERA_MAXIMA_S = 300.0
CODIGOS_REINTENTABLES = frozenset({408, 409, 429, 500, 502, 503, 504, 529})
HTTP_OK = 200

Respuesta = tuple[int, dict[str, str], bytes]
Transporte = Callable[[str, str, dict[str, str], bytes | None, float], Respuesta]


class ClienteNoConfigurado(RuntimeError):
    pass


class LlamadaFallida(RuntimeError):
    pass


@dataclass(frozen=True)
class Configuracion:
    clave: str
    url: str
    url_lotes: str
    modelo: str
    cabeceras: dict[str, str]

    def cabeceras_http(self) -> dict[str, str]:
        cabeceras = {k: v.replace(MARCA_CLAVE, self.clave) for k, v in self.cabeceras.items()}
        cabeceras["content-type"] = "application/json"
        return cabeceras


def cargar_local(ruta: Path = RUTA_LOCAL) -> None:
    """Para ejecuciones en local: lleva el fichero a las variables que falten."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        nombre, _, valor = linea.partition("=")
        if nombre in VARIABLES and not os.environ.get(nombre):
            os.environ[nombre] = valor


def configuracion() -> Configuracion:
    faltan = [v for v in VARIABLES if not os.environ.get(v)]
    if faltan:
        raise ClienteNoConfigurado(f"faltan variables: {', '.join(faltan)}")
    cabeceras = json.loads(os.environ["EODI_EXTRACTOR_CABECERAS"])
    if not any(MARCA_CLAVE in str(v) for v in cabeceras.values()):
        raise ClienteNoConfigurado("las cabeceras no dicen dónde va la clave")
    return Configuracion(
        clave=os.environ["EODI_EXTRACTOR_CLAVE"],
        url=os.environ["EODI_EXTRACTOR_URL"],
        url_lotes=os.environ["EODI_EXTRACTOR_URL_LOTES"],
        modelo=os.environ["EODI_EXTRACTOR_MODELO"],
        cabeceras={str(k): str(v) for k, v in cabeceras.items()},
    )


def transporte_urllib(
    metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None, limite_s: float
) -> Respuesta:
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=limite_s) as respuesta:
            return respuesta.status, dict(respuesta.headers), respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read() or b""


def _tipo_error(cuerpo: bytes) -> str:
    """Solo el tipo de error del servicio: nunca el texto completo."""
    try:
        return str(json.loads(cuerpo).get("error", {}).get("type", "desconocido"))
    except (ValueError, AttributeError):
        return "desconocido"


class Cliente:
    def __init__(
        self,
        config: Configuracion,
        transporte: Transporte = transporte_urllib,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._transporte = transporte
        self._dormir = dormir

    def _pedir(self, metodo: str, url: str, cuerpo: Any = None) -> bytes:
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        motivo = ""
        for intento in range(REINTENTOS + 1):
            pedida = ""
            try:
                codigo, cabeceras, respuesta = self._transporte(
                    metodo, url, self.config.cabeceras_http(), datos, TIEMPO_LIMITE_S
                )
            except (OSError, TimeoutError) as error:
                motivo = f"error de red: {type(error).__name__}"
            else:
                if codigo == HTTP_OK:
                    return respuesta
                motivo = f"código {codigo} ({_tipo_error(respuesta)})"
                if codigo not in CODIGOS_REINTENTABLES:
                    raise LlamadaFallida(motivo)
                pedida = {k.lower(): v for k, v in cabeceras.items()}.get("retry-after", "")
            if intento < REINTENTOS:
                espera = ESPERA_INICIAL_S * 2**intento
                if pedida.strip().isdigit():
                    espera = max(espera, min(float(pedida), ESPERA_MAXIMA_S))
                self._dormir(espera)
        raise LlamadaFallida(f"{motivo} tras {REINTENTOS} reintentos")

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        """Una llamada al servicio de mensajes con el modelo configurado."""
        respuesta: dict[str, Any] = json.loads(
            self._pedir("POST", self.config.url, {"model": self.config.modelo, **cuerpo})
        )
        return respuesta

    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]:
        """Peticiones [{"custom_id": ..., "params": {...}}]; el modelo se añade a cada una."""
        cuerpo = {
            "requests": [
                {
                    "custom_id": p["custom_id"],
                    "params": {"model": self.config.modelo, **p["params"]},
                }
                for p in peticiones
            ]
        }
        respuesta: dict[str, Any] = json.loads(self._pedir("POST", self.config.url_lotes, cuerpo))
        return respuesta

    def lote(self, id_: str) -> dict[str, Any]:
        respuesta: dict[str, Any] = json.loads(self._pedir("GET", f"{self.config.url_lotes}/{id_}"))
        return respuesta

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]:
        """Resultados de un lote terminado, una línea JSON por petición."""
        texto = self._pedir("GET", lote["results_url"]).decode("utf-8")
        return [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
