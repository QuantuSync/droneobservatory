"""A quién atribuye una autoridad un incidente: un Estado o una persona, y su país.

La atribución la hace una autoridad en una declaración citada (proceso/declaraciones.py): el
extractor da el autor («Rusia», un nombre y apellidos), su tipo y su país, y la frase literal.
Aquí se decide si eso se sostiene con la propia frase, sin deducir nada:

- **Estado.** El país es el que nombra el autor («Rusia», «Russland») o, si el autor no es un
  país de la tabla, el que da el extractor. La frase tiene que nombrar a ese Estado: su
  nombre, su capital («oskarżyła Moskwę») o su gentilicio («einem russischen
  Anschlagsversuch»). Si no lo nombra, no hay atribución.
- **Persona.** La frase tiene que nombrar a la persona (alguna de las palabras de su nombre).
  Su país (la nacionalidad) solo se rellena si la frase la dice con un gentilicio de ese país
  («un cetățean rus»); nunca sale del nombre, del lugar del incidente ni del idioma. Sin
  gentilicio, la persona queda sin país.

Las fichas guardadas antes de que el extractor diera el tipo (sin `autor_tipo`) se leen igual:
un autor que nombra un Estado de la tabla es un Estado; otro, una persona, sin país. Un tipo
vacío (el extractor dice que no es ni un Estado ni una persona) no da atribución.

La tabla de países (configuracion/paises_atribucion.json) es también la de las banderas de la
web: un país fuera de ella no se puede comprobar en la frase.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso.noticias import normalizar

RUTA_PAISES = Path(__file__).parents[1] / "configuracion" / "paises_atribucion.json"
TIPOS = ("estado", "persona")
ESTADO_ATRIBUIDO = "atribuido"
_ISO = re.compile(r"^[A-Z]{2}$")
# Las palabras de un nombre que bastan para reconocerlo en la frase: sin iniciales ni
# partículas («de», «van»).
_LETRAS_NOMBRE = 3


def _patron(termino: str) -> str:
    entero = termino.endswith("$")
    normal = normalizar(termino.rstrip("$"))
    return rf"(?<!\w){re.escape(normal)}" + (r"(?!\w)" if entero else "")


@cache
def _tabla() -> dict[str, dict[str, re.Pattern[str]]]:
    datos = json.loads(RUTA_PAISES.read_text(encoding="utf-8"))
    tabla: dict[str, dict[str, re.Pattern[str]]] = {}
    for pais, terminos in datos["paises"].items():
        tabla[pais] = {
            clase: re.compile("|".join(_patron(t) for t in lista))
            for clase, lista in terminos.items()
        }
    return tabla


def paises() -> frozenset[str]:
    """Los países que se pueden comprobar en una frase (y que tienen bandera en la web)."""
    return frozenset(_tabla())


def menciona(texto: str, pais: str, *, solo_gentilicio: bool = False) -> bool:
    """Si el texto nombra al país: su nombre, su capital o su gentilicio; con
    `solo_gentilicio`, solo el gentilicio (la nacionalidad de una persona)."""
    patrones = _tabla().get(pais)
    if patrones is None:
        return False
    normal = normalizar(texto)
    if patrones["gentilicio"].search(normal):
        return True
    return not solo_gentilicio and bool(patrones["estado"].search(normal))


def estado_nombrado(autor: str) -> str | None:
    """El Estado que nombra el autor («Rusia», «Kremlin», «las autoridades rusas»), o None.
    Si nombra varios, el del término más largo."""
    normal = normalizar(autor)
    mejor: tuple[int, str] | None = None
    for pais, patrones in _tabla().items():
        for patron in patrones.values():
            for encontrado in patron.finditer(normal):
                largo = len(encontrado.group(0))
                if mejor is None or largo > mejor[0]:
                    mejor = (largo, pais)
    return None if mejor is None else mejor[1]


def _nombra_persona(autor: str, frase: str) -> bool:
    palabras = {p for p in normalizar(autor).split() if len(p) >= _LETRAS_NOMBRE}
    texto = set(normalizar(frase).split())
    return bool(palabras & texto)


def _iso(valor: object) -> str | None:
    codigo = str(valor or "").strip().upper()
    return codigo if _ISO.match(codigo) else None


def clasificar(
    autor: str, frase: str, tipo: str | None = None, pais: str | None = None
) -> Documento | None:
    """El tipo y el país de una atribución ({"tipo": …, "pais": …}, el país solo si se sabe),
    o None si la frase no la sostiene. `tipo` y `pais` son los que da el extractor; `tipo`
    None es una ficha anterior que no lo traía."""
    autor = autor.strip()
    if not autor or (tipo is not None and tipo not in TIPOS):
        return None
    nombrado = estado_nombrado(autor)
    dado = _iso(pais)
    if tipo == "estado" or (tipo is None and nombrado is not None):
        elegido = nombrado or dado
        if elegido is not None and elegido in paises():
            return {"tipo": "estado", "pais": elegido} if menciona(frase, elegido) else None
        # Un Estado fuera de la tabla: la frase tiene que nombrar al autor tal cual.
        if not _nombra_persona(autor, frase):
            return None
        return {"tipo": "estado", "pais": elegido} if elegido else {"tipo": "estado"}
    if not _nombra_persona(autor, frase):
        return None
    if tipo == "persona" and dado is not None and menciona(frase, dado, solo_gentilicio=True):
        return {"tipo": "persona", "pais": dado}
    return {"tipo": "persona"}


def fuente_de_atribucion(incidente: Documento) -> Documento | None:
    """La fuente (la declaración citada) del último paso a atribuido del historial."""
    pasos = [p for p in incidente["estado"]["historial"] if p["estado"] == ESTADO_ATRIBUIDO]
    if not pasos:
        return None
    por_id = {f["id"]: f for f in incidente.get("fuentes", [])}
    fuente: Documento | None = por_id.get(pasos[-1]["fuente_id"])
    return fuente


def errores(incidente: Documento) -> list[str]:
    """Lo que no cuadra en la atribución de un incidente: sin tipo, o un tipo o un país que no
    salen de la frase de la autoridad que lo atribuye."""
    atribucion: dict[str, Any] | None = incidente.get("atribucion")
    if atribucion is None:
        return []
    tipo = atribucion.get("tipo")
    if tipo not in TIPOS:
        return ["atribución sin tipo de actor (estado o persona)"]
    fuente = fuente_de_atribucion(incidente)
    if fuente is None or not fuente.get("es_autoridad"):
        return []
    esperado = clasificar(
        atribucion["actor"], str(fuente.get("frase_origen", "")), tipo, atribucion.get("pais")
    )
    if esperado is None:
        return [f"la frase de la autoridad no nombra a quien se atribuye ({atribucion['actor']})"]
    if esperado.get("pais") != atribucion.get("pais"):
        return [
            f"país de la atribución {atribucion.get('pais')!r} distinto del que dice la frase "
            f"de la autoridad ({esperado.get('pais')!r})"
        ]
    return []


def corregir(incidente: Documento) -> Documento:
    """El incidente con su atribución clasificada desde la frase guardada de la autoridad. Si
    la frase no la sostiene, el incidente vuelve al estado anterior a la atribución (sin el
    paso a atribuido ni la atribución). Devuelve el mismo objeto si no cambia nada."""
    atribucion = incidente.get("atribucion")
    fuente = fuente_de_atribucion(incidente)
    if atribucion is None or fuente is None:
        return incidente
    clase = clasificar(
        atribucion["actor"],
        str(fuente.get("frase_origen", "")),
        atribucion.get("tipo"),
        atribucion.get("pais"),
    )
    if clase is not None:
        nueva = {k: v for k, v in atribucion.items() if k not in ("tipo", "pais")} | clase
        return incidente if nueva == atribucion else {**incidente, "atribucion": nueva}
    historial = [p for p in incidente["estado"]["historial"] if p["estado"] != ESTADO_ATRIBUIDO]
    resultado = {k: v for k, v in incidente.items() if k != "atribucion"}
    resultado["estado"] = {
        **incidente["estado"],
        "actual": historial[-1]["estado"],
        "historial": historial,
    }
    return resultado
