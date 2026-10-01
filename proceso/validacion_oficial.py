"""Validación por código de la ficha de un documento oficial (modelo/ficha_oficial.py).

La misma que la de las noticias (proceso/validacion_ficha.validar): frase literal en el texto
enviado, confianza de 0,5 o más, valores con su formato y dentro de sus topes, lugar del suceso
nombrado en su frase. Cambia lo que depende de la fecha: un documento oficial cita sucesos de
meses atrás, así que el inicio vale si no es posterior al documento ni anterior a
FECHA_MINIMA. Y se añaden los campos de detalle (altura, velocidad, detección, resultado de
las contramedidas) y las cifras, cuyo número tiene que estar escrito en su frase.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from proceso.fronteras import paises
from proceso.noticias import normalizar
from proceso.validacion_ficha import (
    MAX_PALABRAS_FRASE,
    UMBRAL_CONFIANZA,
    Contexto,
    Validada,
    leer_fecha,
    validar,
)

# Ningún suceso que cite un documento de la recogida es anterior: el observatorio empieza en
# 2024 y los informes de investigación con drones, en 2014.
FECHA_MINIMA = datetime(2014, 1, 1, tzinfo=UTC)
MAX_ALTURA_M = 10_000.0
MAX_VELOCIDAD_MS = 200.0
MAX_CIFRA = 1_000_000
MAX_LETRAS_INSTALACION = 120
CATEGORIAS = frozenset({
    "aeropuerto", "base_militar", "puerto", "energia", "presa", "estadio", "industrial",
    "gubernamental", "otra",
})  # fmt: skip
# Un día del mes escrito con cifras, suelto («23», «3.»), no dentro de un año ni de una hora.
_DIA = re.compile(r"(?<![\d:])(\d{1,2})(?![\d:])")
_NUMERO = re.compile(r"\d[\d.,'   ]*")


@dataclass
class Suceso:
    validada: Validada
    datos: dict[str, dict[str, Any]] = field(default_factory=dict)


def _frase_en(frase: Any, texto: str) -> str | None:
    if not isinstance(frase, str) or not frase.strip():
        return "sin frase de origen"
    frase = " ".join(frase.split()[:MAX_PALABRAS_FRASE])
    return None if normalizar(frase) in normalizar(texto) else "la frase no está en el texto"


def _confianza(dato: dict[str, Any]) -> str | None:
    confianza = dato.get("confianza")
    if not isinstance(confianza, int | float) or not 0 <= confianza <= 1:
        return "confianza fuera de 0 a 1"
    return "confianza baja" if confianza < UMBRAL_CONFIANZA else None


def dia_en_frase(valor: str, frase: str) -> bool:
    """El día del mes de la fecha está escrito en su frase («op 23 december», «am 3.
    März»): una frase que solo da el año o el mes («aus dem Jahr 2024») no da un día, y la
    fecha no se completa con el primero del mes."""
    dia = int(valor[8:10])
    return any(int(n) == dia for n in _DIA.findall(frase))


def _fecha_valida(valor: Any, documento: date, frase: str = "") -> str | None:
    momento = leer_fecha(valor) if isinstance(valor, str) else None
    if momento is None:
        return "fecha imposible"
    if momento.date() > documento:
        return "posterior al documento"
    if momento < FECHA_MINIMA:
        return "anterior a 2014"
    if not dia_en_frase(str(valor), frase):
        return "el día no está en su frase"
    return None


def validar_suceso(
    suceso: dict[str, Any], texto: str, pais_documento: str, fecha_documento: date, ahora: datetime
) -> tuple[Suceso, list[str]]:
    """Los datos válidos del suceso y los motivos de lo que no pasa."""
    motivos: list[str] = []
    datos = dict(suceso.get("datos", {}))
    propios: dict[str, dict[str, Any]] = {}
    for nombre in ("inicio", "fin", "altura_m", "velocidad_ms", "deteccion",
                   "resultado_contramedidas"):  # fmt: skip
        if nombre not in datos:
            continue
        dato = datos.pop(nombre)
        motivo = _confianza(dato) or _frase_en(dato.get("frase"), texto)
        valor = dato.get("valor")
        if motivo is None and nombre in {"inicio", "fin"}:
            motivo = _fecha_valida(valor, fecha_documento, str(dato.get("frase") or ""))
        if motivo is None and nombre in {"altura_m", "velocidad_ms"}:
            tope = MAX_ALTURA_M if nombre == "altura_m" else MAX_VELOCIDAD_MS
            if not isinstance(valor, dict) or not 0 <= valor["min"] <= valor["max"] <= tope:
                motivo = f"fuera de 0 a {tope:g}"
        if motivo:
            motivos.append(f"{nombre}: {motivo}")
            continue
        propios[nombre] = {
            **dato,
            "frase": " ".join(str(dato["frase"]).split()[:MAX_PALABRAS_FRASE]),
        }
    if "inicio" not in propios:
        datos.pop("inicio_precision", None)
    if (
        "fin" in propios
        and "inicio" in propios
        and propios["fin"]["valor"] < propios["inicio"]["valor"]
    ):
        propios.pop("fin")
        motivos.append("fin: anterior al inicio")
    # El resto, con la validación de la ficha de noticias: el documento es la fuente 1.
    ficha = {
        **{n: {**d, "fuente": 1} for n, d in datos.items()},
        "titulo_es": suceso.get("titulo_es", ""),
        "titulo_en": suceso.get("titulo_en", ""),
    }
    contexto = Contexto(
        textos=(texto,), pais_objetivo=pais_documento,
        primer_articulo=datetime.combine(fecha_documento, datetime.min.time(), UTC)
        + timedelta(days=1),
        ahora=ahora,
    )  # fmt: skip
    validada = validar(ficha, contexto)
    motivos += [m for m in validada.motivos if not m.startswith("sin título")]
    for nombre, dato in propios.items():
        validada.campos[nombre] = {**dato, "fuente": 1}
    resultado = Suceso(validada)
    resultado.datos = {
        nombre: {
            "valor": c["valor"],
            "frase": " ".join(str(c.get("frase") or "").split()[:MAX_PALABRAS_FRASE]),
            "confianza": float(c["confianza"]),
        }
        for nombre, c in sorted(validada.campos.items())
        if c.get("frase")
    }  # fmt: skip
    return resultado, motivos


def _numero_en_frase(valor: dict[str, int], frase: str) -> bool:
    """El mínimo (y el máximo) de la cifra están escritos en la frase, con o sin separador
    de miles («1.234», «1 234»)."""
    escritos = {int(re.sub(r"\D", "", m)) for m in _NUMERO.findall(frase) if re.sub(r"\D", "", m)}
    return valor["min"] in escritos and valor["max"] in escritos


def _dia(texto: Any) -> date | None:
    if not isinstance(texto, str):
        return None
    try:
        return date.fromisoformat(texto.strip())
    except ValueError:
        return None


def validar_cifra(cifra: dict[str, Any], texto: str, fecha_documento: date) -> str | None:
    """Motivo por el que la cifra no vale, o None."""
    motivo = _confianza(cifra) or _frase_en(cifra.get("frase"), texto)
    if motivo:
        return motivo
    valor = cifra.get("valor")
    if not isinstance(valor, dict) or not 0 <= valor["min"] <= valor["max"] <= MAX_CIFRA:
        return "cifra fuera de rango"
    if not _numero_en_frase(valor, str(cifra["frase"])):
        return "la cifra no está escrita en su frase"
    inicio, fin = _dia(cifra.get("periodo_inicio")), _dia(cifra.get("periodo_fin"))
    if inicio is None or fin is None:
        return "periodo sin fechas"
    if fin < inicio:
        return "periodo con fin anterior al inicio"
    if inicio > fecha_documento or inicio < FECHA_MINIMA.date():
        return "periodo fuera de lo posible"
    if cifra.get("pais") not in paises():
        return "país fuera de la recogida"
    categoria = str(cifra.get("categoria") or "")
    if categoria and categoria not in CATEGORIAS:
        return "categoría fuera de la lista"
    if len(str(cifra.get("instalacion") or "")) > MAX_LETRAS_INSTALACION:
        return "instalación demasiado larga"
    return None
