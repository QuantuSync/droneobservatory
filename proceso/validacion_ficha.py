"""Validación con código de la ficha que devuelve el extractor.

Nada de lo que devuelve el modelo se usa sin pasar por aquí. Un campo que no
valida se descarta y su motivo queda en el registro interno de la extracción;
si no valida lo esencial (que es un incidente, su país y su fecha), la ficha
entera no se publica.

Comprobaciones:
- la frase de origen tiene 25 palabras como máximo y está, tal cual, en el
  texto de la fuente que cita (así no se cuela una frase inventada);
- la confianza está entre 0 y 1 y llega al umbral;
- el país existe en la lista de países europeos y las coordenadas de un lugar
  nuevo caen dentro de su caja;
- los rangos son coherentes y caben en los topes;
- las fechas son posibles: no futuras, no posteriores al primer artículo y no
  más de una semana anteriores;
- el objetivo existe: el conocido del nomenclátor o un lugar nuevo válido.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from proceso.noticias import normalizar

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
MAX_PALABRAS_FRASE = 25
# Por debajo de 0,5 el modelo declara que supone: el campo no se usa.
UMBRAL_CONFIANZA = 0.5
# Topes de plausibilidad. Los avistamientos europeos más grandes de 2025 hablan de
# decenas de drones (19 a 23 en Polonia en septiembre): 100 deja margen.
MAX_DRONES = 100
# Un gran aeropuerto europeo mueve unos 1500 vuelos al día: más afectados es un error.
MAX_VUELOS = 2000
# Un cierre por drones dura horas; más de dos días es un error de unidades.
MAX_CIERRE_MIN = 2 * 24 * 60
# La noticia sale el mismo día o pocos días después: más de una semana antes es un error.
MAX_ANTELACION = timedelta(days=7)
# El artículo lleva la hora de su franja de GDELT, que puede ir hasta una hora por detrás
# de la publicación.
MARGEN_ARTICULO = timedelta(hours=1)
MAX_LETRAS_NOMBRE = 80
RANGOS = ("drones", "cierre_minutos", "vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados")
TOPES = {
    "drones": MAX_DRONES,
    "cierre_minutos": MAX_CIERRE_MIN,
    "vuelos_desviados": MAX_VUELOS,
    "vuelos_cancelados": MAX_VUELOS,
    "vuelos_retrasados": MAX_VUELOS,
}
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?$")


@cache
def cajas_paises(ruta: Path = DIRECTORIO / "paises_europa.json") -> dict[str, list[float]]:
    datos: dict[str, list[float]] = json.loads(ruta.read_text(encoding="utf-8"))["cajas"]
    return datos


def dentro(pais: str, lat: float, lon: float) -> bool:
    caja = cajas_paises().get(pais)
    if caja is None:
        return False
    lat_min, lat_max, lon_min, lon_max = caja
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


@dataclass(frozen=True)
class Contexto:
    """Lo que el extractor recibió: textos de las fuentes, objetivo y primer artículo."""

    textos: tuple[str, ...]
    pais_objetivo: str
    primer_articulo: datetime
    ahora: datetime


@dataclass
class Validada:
    """Campos que pasan, con su valor, fuente (índice desde 1), frase y confianza."""

    campos: dict[str, dict[str, Any]] = field(default_factory=dict)
    motivos: list[str] = field(default_factory=list)
    titulo_es: str = ""
    titulo_en: str = ""

    @property
    def publicable(self) -> bool:
        """Es un incidente. El país y la fecha, si la ficha no los da o no validan, salen
        del objetivo y del candidato (con precisión de día)."""
        otro_sitio = self.valor("objetivo_conocido") is False and "lugar_nuevo" not in self.campos
        return (
            "es_incidente" in self.campos
            and bool(self.campos["es_incidente"]["valor"])
            and not otro_sitio
        )

    def valor(self, campo: str) -> Any:
        return self.campos[campo]["valor"] if campo in self.campos else None


def leer_fecha(texto: str) -> datetime | None:
    if not _FECHA.match(texto):
        return None
    formato = "%Y-%m-%dT%H:%M" if "T" in texto else "%Y-%m-%d"
    try:
        return datetime.strptime(texto, formato).replace(tzinfo=UTC)
    except ValueError:
        return None


def _frase_valida(campo: dict[str, Any], textos: tuple[str, ...]) -> str | None:
    """Motivo por el que la frase o la fuente no valen, o None."""
    fuente, frase = campo.get("fuente"), campo.get("frase")
    if not isinstance(fuente, int) or not 1 <= fuente <= len(textos):
        return "fuente inexistente"
    if not isinstance(frase, str) or not frase.strip():
        return "sin frase de origen"
    if normalizar(frase) not in normalizar(textos[fuente - 1]):
        return "la frase no está en la fuente"
    return None


def _rango_valido(nombre: str, valor: Any) -> str | None:
    if not isinstance(valor, dict) or set(valor) != {"min", "max"}:
        return "rango mal formado"
    minimo, maximo = valor["min"], valor["max"]
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (minimo, maximo)):
        return "rango no entero"
    if minimo < 0 or minimo > maximo:
        return "rango incoherente"
    if maximo > TOPES[nombre]:
        return f"por encima del tope de {TOPES[nombre]}"
    return None


def _lugar_valido(valor: Any) -> str | None:
    if not isinstance(valor, dict):
        return "lugar mal formado"
    nombre, pais = valor.get("nombre"), valor.get("pais")
    if not isinstance(nombre, str) or not 0 < len(nombre.strip()) <= MAX_LETRAS_NOMBRE:
        return "lugar sin nombre"
    lat, lon = valor.get("lat"), valor.get("lon")
    if (
        not isinstance(pais, str)
        or not isinstance(lat, int | float)
        or not isinstance(lon, int | float)
    ):
        return "lugar sin país o coordenadas"
    if not dentro(pais, float(lat), float(lon)):
        return "coordenadas fuera del país citado"
    return None


def _valor_valido(nombre: str, valor: Any, contexto: Contexto) -> str | None:
    """Motivo por el que el valor no vale, o None."""
    if nombre in RANGOS:
        return _rango_valido(nombre, valor)
    if nombre == "pais":
        return None if isinstance(valor, str) and valor in cajas_paises() else "país desconocido"
    if nombre == "lugar_nuevo":
        return _lugar_valido(valor)
    if nombre in {"inicio", "fin"}:
        momento = leer_fecha(valor) if isinstance(valor, str) else None
        if momento is None:
            return "fecha imposible"
        if momento > contexto.ahora:
            return "fecha futura"
        if nombre == "inicio" and momento > contexto.primer_articulo + MARGEN_ARTICULO:
            return "inicio posterior al primer artículo"
        if nombre == "inicio" and momento < contexto.primer_articulo - MAX_ANTELACION:
            return "inicio más de una semana antes del primer artículo"
        return None
    if nombre in {"localidad", "objetivo_nombre", "modelo_dron"}:
        texto_ok = isinstance(valor, str) and 0 < len(valor.strip()) <= MAX_LETRAS_NOMBRE
        return None if texto_ok else "texto vacío o demasiado largo"
    return None


def validar(ficha: dict[str, Any], contexto: Contexto) -> Validada:
    resultado = Validada(
        titulo_es=str(ficha.get("titulo_es", "")).strip(),
        titulo_en=str(ficha.get("titulo_en", "")).strip(),
        motivos=list(ficha.get("ilegibles", [])),
    )
    for nombre, campo in ficha.items():
        if not isinstance(campo, dict) or campo.get("valor") is None:
            continue
        confianza = campo.get("confianza")
        if not isinstance(confianza, int | float) or not 0 <= confianza <= 1:
            resultado.motivos.append(f"{nombre}: confianza fuera de 0 a 1")
            continue
        if confianza < UMBRAL_CONFIANZA:
            resultado.motivos.append(f"{nombre}: confianza baja")
            continue
        if isinstance(campo.get("frase"), str) and len(campo["frase"].split()) > MAX_PALABRAS_FRASE:
            # Una frase más larga se recorta a sus primeras 25 palabras: sigue siendo cita literal.
            campo = {**campo, "frase": " ".join(campo["frase"].split()[:MAX_PALABRAS_FRASE])}
        motivo = _frase_valida(campo, contexto.textos) or _valor_valido(
            nombre, campo["valor"], contexto
        )
        if motivo:
            resultado.motivos.append(f"{nombre}: {motivo}")
            continue
        resultado.campos[nombre] = campo
    # Coherencias entre campos.
    fin, inicio = resultado.valor("fin"), resultado.valor("inicio")
    if (
        fin
        and inicio
        and (leer_fecha(fin) or contexto.ahora) < (leer_fecha(inicio) or contexto.ahora)
    ):
        resultado.campos.pop("fin")
        resultado.motivos.append("fin: anterior al inicio")
    if "cierre_minutos" in resultado.campos and resultado.valor("cierre") != "si":
        resultado.campos.pop("cierre_minutos")
        resultado.motivos.append("cierre_minutos: minutos sin cierre")
    conocido = resultado.valor("objetivo_conocido")
    if conocido is not False and resultado.valor("pais") not in {None, contexto.pais_objetivo}:
        resultado.campos.pop("pais")
        resultado.motivos.append("pais: distinto del país del objetivo conocido")
    nuevo = resultado.valor("lugar_nuevo")
    if conocido is False and nuevo and nuevo["pais"] != resultado.valor("pais"):
        resultado.campos.pop("lugar_nuevo")
        resultado.motivos.append("lugar_nuevo: país distinto del del incidente")
    if conocido is False and "lugar_nuevo" not in resultado.campos:
        resultado.campos.pop("pais", None)
        resultado.motivos.append("objetivo: ni el conocido ni un lugar nuevo válido")
    if not resultado.titulo_es or not resultado.titulo_en:
        resultado.motivos.append("sin título")
    return resultado
