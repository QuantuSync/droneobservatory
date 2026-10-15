"""Lo que no es un suceso no es ficha.

La EODI-2026-00539 se publicó a partir de un reportaje de contenido de socio de delfi.lt sobre
cómo actúa la defensa aérea de la OTAN, sin ningún suceso concreto (retirada en el PR #242).
Antes de crear o mantener una ficha se mira cada fuente: las marcas de su página
(modelo/paginas.marcas: tipo y sección del artículo, etiquetas, datos estructurados), su
dirección y la cabeza de su titular, con las señales de configuracion/no_es_suceso.json:

- contenido patrocinado o de socio y publicidad (categoría «segura»): si todas las fuentes lo
  son, la ficha nueva no se crea, aunque el modelo la dé por suceso, y sin gastar en el
  experto;
- opinión, análisis, explicativos, entrevistas y resúmenes generales: si todas las fuentes lo
  son y el modelo base la da por suceso, la duda la decide el experto.

Nada publicado se retira sin el experto (docs/modelos.md): una ficha publicada cuyas fuentes son
todas de estas se repite con él (proceso/extraccion.py y recogida/control_fichas.py), y si la
retira lo hace con su motivo en español y en inglés.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from modelo.ficha import FuenteTexto
from proceso.noticias import normalizar

RUTA = Path(__file__).resolve().parent.parent / "configuracion" / "no_es_suceso.json"
PREFIJO_MOTIVO = "no_es_suceso"
_CABEZA = re.compile(r"\s*(?::|\||\s[-–—]\s)")
PALABRAS_CABEZA = 3


@dataclass(frozen=True)
class Categoria:
    nombre: str
    segura: bool
    es: str
    en: str
    marcas: re.Pattern[str] | None
    titular: re.Pattern[str] | None
    titular_entero: re.Pattern[str] | None
    direcciones: tuple[str, ...]


@dataclass(frozen=True)
class Veredicto:
    """Por qué una fuente (o todas las de una ficha) no cuentan un suceso."""

    categoria: str
    segura: bool
    senal: str
    medio: str
    es: str
    en: str

    def motivo_escalado(self) -> str:
        return f"{PREFIJO_MOTIVO}: {self.categoria} ({self.medio}: «{self.senal}»)"

    def motivo(self) -> str:
        return (
            f"No es un suceso: la fuente es {self.es} ({self.medio}, «{self.senal}») y no cuenta "
            "un suceso concreto con su fecha y su lugar."
        )

    def motivo_en(self) -> str:
        return (
            f"Not an event: the source is {self.en} ({self.medio}, «{self.senal}») and does not "
            "report a specific event with its date and place."
        )

    def documento(self) -> dict[str, Any]:
        return {"categoria": self.categoria, "segura": self.segura, "senal": self.senal,
                "medio": self.medio}  # fmt: skip


def _expresion(texto: str) -> str:
    """Como en configuracion/senales_escalado.json: «*» casa con lo que empieza por la palabra y
    «..» deja hasta tres palabras en medio."""
    partes = []
    for palabra in texto.split():
        if palabra == "..":
            partes.append(r"(?:\w+\s+){0,3}")
            continue
        raiz = r"\s+".join(map(re.escape, normalizar(palabra.rstrip("*")).split()))
        if raiz:
            partes.append((raiz + r"\w*" if palabra.endswith("*") else raiz) + r"\s+")
    return "".join(partes).removesuffix(r"\s+")


def _patron(expresiones: list[str]) -> re.Pattern[str] | None:
    validas = [e for e in (_expresion(x) for x in expresiones) if e]
    return re.compile(r"\b(?:" + "|".join(validas) + r")\b") if validas else None


@cache
def categorias() -> tuple[Categoria, ...]:
    datos = json.loads(RUTA.read_text(encoding="utf-8"))["categorias"]
    return tuple(
        Categoria(
            nombre=nombre,
            segura=bool(d["segura"]),
            es=d["es"],
            en=d["en"],
            marcas=_patron(d.get("expresiones", [])),
            titular=_patron(d.get("titular", [])),
            titular_entero=_patron(d.get("titular_entero", [])),
            direcciones=tuple(x.lower() for x in d.get("direcciones", [])),
        )
        for nombre, d in datos.items()
    )


def _direccion(url: str) -> str:
    partes = urlsplit(url)
    servidor = (partes.hostname or "").lower().removeprefix("www.")
    return f"{servidor}{partes.path.lower() or '/'}"


def _cabeza(titular: str) -> str:
    """Lo que va antes de «:», «|» o « - » en los primeros caracteres, o las tres primeras
    palabras: donde los medios ponen «Opinión:», «Kommentar |» o «Sponsored -»."""
    corte = _CABEZA.search(titular)
    if corte is not None and corte.start() <= 40:
        return titular[: corte.start()]
    return " ".join(titular.split()[:PALABRAS_CABEZA])


def _busca(patron: re.Pattern[str] | None, texto: str) -> str | None:
    if patron is None or not texto:
        return None
    hallado = patron.search(texto)
    return hallado.group(0) if hallado else None


def de_fuente(titular: str, url: str, marcas: Iterable[str], medio: str = "") -> Veredicto | None:
    """La categoría de la fuente si no cuenta un suceso; None si nada lo indica. Las seguras
    primero."""
    texto_marcas = normalizar(" ".join(marcas).replace("=", " ").replace(":", " "))
    direccion = _direccion(url) if url else ""
    texto_direccion = normalizar(re.sub(r"[/_.\-]+", " ", direccion))
    cabeza, entero = normalizar(_cabeza(titular)), normalizar(titular)
    medio = medio or direccion.split("/", 1)[0]
    for categoria in sorted(categorias(), key=lambda c: not c.segura):
        senal = next(
            (s for s in (
                next((d for d in categoria.direcciones if d in f"/{direccion}" or
                      direccion.startswith(d)), None),
                _busca(categoria.marcas, texto_marcas),
                _busca(categoria.marcas, texto_direccion) if categoria.segura else None,
                _busca(categoria.titular, cabeza),
                _busca(categoria.titular_entero, entero),
            ) if s),
            None,
        )  # fmt: skip
        if senal:
            return Veredicto(categoria.nombre, categoria.segura, senal, medio, categoria.es,
                             categoria.en)  # fmt: skip
    return None


def de_fuentes(fuentes: Iterable[FuenteTexto]) -> Veredicto | None:
    """Si ninguna de las fuentes cuenta un suceso, el veredicto (el de la primera; seguro solo
    si todas lo son). None si alguna puede contarlo o no hay fuentes."""
    veredictos = [de_fuente(f.titular, f.url, f.marcas, f.medio) for f in fuentes]
    if not veredictos or any(v is None for v in veredictos):
        return None
    primero = veredictos[0]
    assert primero is not None
    segura = all(v is not None and v.segura for v in veredictos)
    return Veredicto(primero.categoria, segura, primero.senal, primero.medio, primero.es,
                     primero.en)  # fmt: skip


def con_aviso(fuente: FuenteTexto) -> FuenteTexto:
    """La fuente con lo que su página dice de ella, para el modelo («contenido patrocinado o de
    socio»)."""
    veredicto = de_fuente(fuente.titular, fuente.url, fuente.marcas, fuente.medio)
    if veredicto is None:
        return fuente
    return FuenteTexto(fuente.medio, fuente.fecha, fuente.idioma, fuente.titular, fuente.texto,
                       fuente.url, fuente.marcas, veredicto.es)  # fmt: skip
