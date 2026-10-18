"""Cliente HTTP del servicio secundario de modelos, con la biblioteca estándar.

Lo usa la segunda lectura (docs/segunda_lectura.md).

Un servicio gratuito, experimental y prescindible: si no responde o desaparece, el observatorio
sigue exactamente igual. Todo lo que lo identifica llega en variables de entorno (en local, del
mismo fichero que las del extractor, fuera de cualquier repositorio):

- EODI_SECUNDARIO_URL: la dirección base del servicio (formato de chat compatible: /models y
  /chat/completions).
- EODI_SECUNDARIO_CLAVE: la clave.
- EODI_SECUNDARIO_MODELO: el modelo.

Si falta alguna, `configuracion()` devuelve None y la capa no hace nada.

El modelo razona antes de contestar y devuelve el razonamiento aparte («reasoning»): se ignora y
solo vale el contenido. La respuesta se pide en JSON con su esquema (`json_schema`); si el
servicio no lo admite, con `json_object`, y el código la valida igual. Ritmo: como mucho
`por_minuto` peticiones por minuto, un tiempo de espera por petición y, ante un 429 o un error
del servidor, espera exponencial. Los errores nunca llevan la clave.
"""

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VARIABLES = ("EODI_SECUNDARIO_URL", "EODI_SECUNDARIO_CLAVE", "EODI_SECUNDARIO_MODELO")
RUTA_LOCAL = Path.home() / ".eodi" / "extractor.env"
HTTP_OK = 200
HTTP_PETICION_INVALIDA = 400
HTTP_ERROR_SERVIDOR = 500
CODIGOS_TEMPORALES = frozenset({408, 409, 425, 429})
MAX_LETRAS_MENSAJE = 300
CLAVE_OCULTA = "***"
_BLOQUE_JSON = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)

Respuesta = tuple[int, dict[str, str], bytes]
Transporte = Callable[[str, str, dict[str, str], bytes | None, float], Respuesta]


class ServicioCaido(RuntimeError):
    """El servicio no responde o falla también tras los reintentos (o su clave no vale)."""


class SinTiempo(ServicioCaido):
    """La petición (o su reintento) ya no cabe antes del final de la pasada."""


class RespuestaInvalida(ValueError):
    """La respuesta llegó, pero no trae un objeto JSON entero."""


@dataclass(frozen=True)
class Ritmo:
    """Cuánto se pide y cuánto se insiste."""

    por_minuto: int = 8
    limite_s: float = 120.0
    reintentos: int = 3
    espera_inicial_s: float = 5.0
    espera_maxima_s: float = 60.0

    @classmethod
    def de(cls, datos: dict[str, Any]) -> "Ritmo":
        campos = {k: datos[k] for k in cls.__dataclass_fields__ if k in datos}
        return cls(**campos)


@dataclass(frozen=True)
class Configuracion:
    url: str
    clave: str
    modelo: str


def cargar_local(ruta: Path | None = None) -> None:
    """Para ejecuciones en local: lleva el fichero a las variables que falten."""
    ruta = ruta or RUTA_LOCAL
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        nombre, _, valor = linea.partition("=")
        if nombre in VARIABLES and not os.environ.get(nombre):
            os.environ[nombre] = valor.strip()


def configuracion() -> Configuracion | None:
    """La configuración del servicio, o None si falta alguna variable (la capa no hace nada)."""
    valores = [os.environ.get(v, "").strip() for v in VARIABLES]
    if not all(valores):
        return None
    url, clave, modelo = valores
    return Configuracion(url.rstrip("/"), clave, modelo)


def transporte_urllib(
    metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None, limite_s: float
) -> Respuesta:
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=limite_s) as respuesta:
            return respuesta.status, dict(respuesta.headers), respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read() or b""


def es_temporal(codigo: int) -> bool:
    return codigo in CODIGOS_TEMPORALES or codigo >= HTTP_ERROR_SERVIDOR


def leer_contenido(respuesta: dict[str, Any]) -> dict[str, Any]:
    """El objeto JSON del contenido de la respuesta (nunca del razonamiento). Lanza
    RespuestaInvalida si no lo trae entero."""
    try:
        eleccion = respuesta["choices"][0]
        contenido = eleccion["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise RespuestaInvalida("respuesta sin contenido") from error
    if eleccion.get("finish_reason") not in (None, "stop"):
        raise RespuestaInvalida(f"parada: {eleccion.get('finish_reason')}")
    texto = str(contenido).strip()
    bloque = _BLOQUE_JSON.match(texto)
    if bloque:
        texto = bloque[1]
    try:
        datos = json.loads(texto)
    except ValueError as error:
        raise RespuestaInvalida("el contenido no es JSON") from error
    if not isinstance(datos, dict):
        raise RespuestaInvalida("el contenido no es un objeto")
    return datos


class Cliente:
    def __init__(
        self,
        config: Configuracion,
        ritmo: Ritmo | None = None,
        transporte: Transporte = transporte_urllib,
        dormir: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.ritmo = ritmo or Ritmo()
        self._transporte = transporte
        self._dormir = dormir
        self._reloj = reloj
        self._ultima: float | None = None
        # Si el servicio no admite json_schema, se pasa a json_object para el resto de la pasada.
        self.formato = "json_schema"
        self.peticiones = 0
        # Final de la pasada (reloj monótono): ninguna petición ni espera pasa de ahí.
        self.hasta: float | None = None

    def _limpio(self, texto: str) -> str:
        return " ".join(texto.replace(self.config.clave, CLAVE_OCULTA).split())[:MAX_LETRAS_MENSAJE]

    def _cabeceras(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.config.clave}", "content-type": "application/json"}

    def _esperar_turno(self) -> None:
        """Como mucho `por_minuto` peticiones por minuto: un hueco fijo entre una y la siguiente."""
        hueco = 60.0 / max(1, self.ritmo.por_minuto)
        if self._ultima is not None:
            falta = self._ultima + hueco - self._reloj()
            if falta > 0:
                self._dormir(falta)
        self._ultima = self._reloj()

    def _pedir(self, metodo: str, ruta: str, cuerpo: Any = None) -> tuple[int, bytes]:
        """El código y el cuerpo de la respuesta; los errores temporales se reintentan con espera
        exponencial y, si siguen, salen como ServicioCaido."""
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        motivo = ""
        for intento in range(self.ritmo.reintentos + 1):
            pedida = ""
            if self.hasta is not None and self._reloj() + self.ritmo.limite_s > self.hasta:
                raise SinTiempo(f"sin tiempo para otra petición; antes: {motivo or 'nada'}")
            self._esperar_turno()
            self.peticiones += 1
            try:
                codigo, cabeceras, respuesta = self._transporte(
                    metodo, self.config.url + ruta, self._cabeceras(), datos, self.ritmo.limite_s
                )
            except (OSError, http.client.HTTPException) as error:
                motivo = f"corte de conexión ({type(error).__name__}: {self._limpio(str(error))})"
            else:
                if codigo == HTTP_OK or not es_temporal(codigo):
                    return codigo, respuesta
                motivo = f"código {codigo} ({self._limpio(respuesta.decode('utf-8', 'replace'))})"
                pedida = {k.lower(): v for k, v in cabeceras.items()}.get("retry-after", "")
            if intento < self.ritmo.reintentos:
                espera = self.ritmo.espera_inicial_s * 2**intento
                if pedida.strip().isdigit():
                    espera = max(espera, float(pedida))
                self._dormir(min(espera, self.ritmo.espera_maxima_s))
        raise ServicioCaido(f"{motivo}; reintentos: {self.ritmo.reintentos}")

    def modelos(self) -> list[str]:
        """Los modelos que ofrece el servicio (para comprobar que responde)."""
        codigo, cuerpo = self._pedir("GET", "/models")
        if codigo != HTTP_OK:
            raise ServicioCaido(f"código {codigo}")
        try:
            return [str(m["id"]) for m in json.loads(cuerpo)["data"]]
        except (ValueError, KeyError, TypeError) as error:
            raise ServicioCaido("lista de modelos ilegible") from error

    def _formato(self, nombre: str, esquema: dict[str, Any]) -> dict[str, Any]:
        if self.formato == "json_schema":
            return {"type": "json_schema",
                    "json_schema": {"name": nombre, "schema": esquema, "strict": True}}  # fmt: skip
        return {"type": "json_object"}

    def json(
        self, instrucciones: str, contenido: str, nombre: str, esquema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:  # fmt: skip
        """Una pregunta con su respuesta en JSON, leída (sin validar contra el esquema: eso lo
        hace quien llama). Lanza ServicioCaido o RespuestaInvalida."""
        for _ in range(2):
            cuerpo = {
                "model": self.config.modelo,
                "max_tokens": max_tokens,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": instrucciones},
                    {"role": "user", "content": contenido},
                ],
                "response_format": self._formato(nombre, esquema),
            }
            codigo, respuesta = self._pedir("POST", "/chat/completions", cuerpo)
            if codigo == HTTP_OK:
                try:
                    return leer_contenido(json.loads(respuesta))
                except ValueError as error:
                    raise RespuestaInvalida(str(error)[:200]) from error
            texto = respuesta.decode("utf-8", "replace")
            if (
                codigo == HTTP_PETICION_INVALIDA
                and self.formato == "json_schema"
                and ("response_format" in texto or "json_schema" in texto)
            ):
                self.formato = "json_object"
                continue
            # Clave inválida, modelo que ya no existe, petición rechazada: no se arregla
            # reintentando en esta pasada.
            raise ServicioCaido(f"código {codigo} ({self._limpio(texto)})")
        raise ServicioCaido("el servicio rechaza el formato JSON")
