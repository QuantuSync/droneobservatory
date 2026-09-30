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
llevan el código y el mensaje del servicio tal como los da, nunca la clave.

Un error temporal (el servicio no responde, está saturado o falla por dentro) se
reintenta según la insistencia del cliente y, si sigue, sale como ErrorTemporal.
Los demás errores (petición inválida, clave inválida, saldo agotado) no se
arreglan reintentando y salen enseguida como ErrorDefinitivo.
"""

import http.client
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
HTTP_OK = 200
# Errores temporales: tiempo agotado (408), demasiadas peticiones (429) y cualquier fallo
# del lado del servidor (500, 502, 503, 504, 529...). Los cortes de conexión también lo son.
CODIGOS_TEMPORALES = frozenset({408, 429})
HTTP_ERROR_SERVIDOR = 500
TIPO_DESCONOCIDO = "desconocido"
# El mensaje de error va al registro en una línea y con este tope: cabe una frase larga
# y no una página de error entera.
MAX_LETRAS_MENSAJE = 300
CLAVE_OCULTA = "***"

Respuesta = tuple[int, dict[str, str], bytes]
Transporte = Callable[[str, str, dict[str, str], bytes | None, float], Respuesta]


class ClienteNoConfigurado(RuntimeError):
    pass


class LlamadaFallida(RuntimeError):
    pass


class ErrorTemporal(LlamadaFallida):
    """El servicio no responde o falla por dentro, también tras reintentar."""


class ErrorDefinitivo(LlamadaFallida):
    """Error que no se arregla reintentando: petición o clave inválidas, saldo agotado."""


@dataclass(frozen=True)
class Insistencia:
    """Cuánto se insiste ante un error temporal y cuánto se espera cada respuesta."""

    reintentos: int
    # Espera antes del primer reintento; se dobla en cada uno de los siguientes.
    espera_inicial_s: float
    # Tope a lo que pida el servicio en retry-after.
    espera_maxima_s: float
    limite_s: float


# Ejecución horaria. Una respuesta de unos cientos de tokens tarda segundos (del 28 al 30
# de septiembre de 2026, de 5 a 10 s por candidato con la descarga de sus páginas): 60 s
# cubren un servicio lento. Tras un error temporal, un único reintento a los 5 s, o a lo
# que pida el servicio con tope de 20 s; si vuelve a fallar, el servicio está caído y no
# tiene sentido insistir candidato a candidato: la siguiente ejecución lo intenta de nuevo.
HORARIA = Insistencia(reintentos=1, espera_inicial_s=5.0, espera_maxima_s=20.0, limite_s=60.0)
# Órdenes del histórico, que se lanzan a mano y pueden esperar: 4 reintentos con espera
# doble desde 10 s (150 s en total), o lo que pida el servicio con tope de 300 s, y 120 s
# por respuesta.
HISTORICO = Insistencia(reintentos=4, espera_inicial_s=10.0, espera_maxima_s=300.0, limite_s=120.0)


def es_temporal(codigo: int) -> bool:
    return codigo in CODIGOS_TEMPORALES or codigo >= HTTP_ERROR_SERVIDOR


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


class Cliente:
    def __init__(
        self,
        config: Configuracion,
        transporte: Transporte = transporte_urllib,
        dormir: Callable[[float], None] = time.sleep,
        insistencia: Insistencia = HORARIA,
    ) -> None:
        self.config = config
        self._transporte = transporte
        self._dormir = dormir
        self._insistencia = insistencia

    def _limpio(self, texto: str) -> str:
        """El texto en una línea, sin la clave y con tope de letras."""
        return " ".join(texto.replace(self.config.clave, CLAVE_OCULTA).split())[:MAX_LETRAS_MENSAJE]

    def _detalle(self, cuerpo: bytes) -> str:
        """Tipo y mensaje del error tal como los da el servicio."""
        texto = cuerpo.decode("utf-8", errors="replace")
        try:
            error = json.loads(texto)["error"]
            tipo, mensaje = str(error["type"]), str(error.get("message", ""))
        except (ValueError, KeyError, TypeError, AttributeError):
            # Una pasarela caída responde con una página, no con el JSON del servicio.
            tipo, mensaje = TIPO_DESCONOCIDO, texto
        mensaje = self._limpio(mensaje)
        return f"{tipo}: {mensaje}" if mensaje else tipo

    def _pedir(self, metodo: str, url: str, cuerpo: Any = None) -> bytes:
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        insistencia = self._insistencia
        motivo = ""
        for intento in range(insistencia.reintentos + 1):
            pedida = ""
            try:
                codigo, cabeceras, respuesta = self._transporte(
                    metodo, url, self.config.cabeceras_http(), datos, insistencia.limite_s
                )
            except (OSError, http.client.HTTPException) as error:
                detalle = self._limpio(str(error))
                motivo = f"corte de conexión ({type(error).__name__}: {detalle})"
            else:
                if codigo == HTTP_OK:
                    return respuesta
                motivo = f"código {codigo} ({self._detalle(respuesta)})"
                if not es_temporal(codigo):
                    raise ErrorDefinitivo(motivo)
                pedida = {k.lower(): v for k, v in cabeceras.items()}.get("retry-after", "")
            if intento < insistencia.reintentos:
                espera = insistencia.espera_inicial_s * 2**intento
                if pedida.strip().isdigit():
                    espera = min(max(espera, float(pedida)), insistencia.espera_maxima_s)
                self._dormir(espera)
        raise ErrorTemporal(f"{motivo}; reintentos: {insistencia.reintentos}")

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
