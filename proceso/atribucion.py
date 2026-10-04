"""A quién atribuye una autoridad un incidente: un Estado o una persona, y su país.

Atribuir un incidente es lo más grave que publica el observatorio. Un incidente está
«atribuido» solo si una autoridad competente afirma expresamente, en una declaración que se
puede citar con sus propias palabras, quién es el responsable. La atribución la hace una
autoridad en una declaración citada (proceso/declaraciones.py): el extractor da el autor, su
tipo y su país, la frase, si la frase son palabras literales de la autoridad y, si es una
persona, si la autoridad la ha detenido, acusado o condenado. Aquí se decide si eso se sostiene:

- **Autoridad competente.** Gobierno, ministerio, fuerzas armadas, fiscalía o policía.
- **Palabras literales.** La frase tiene que ser de la propia autoridad (una cita o su texto
  oficial). Una noticia que cuenta que la autoridad atribuye, sin sus palabras, no basta.
- **Sin duda ni investigación.** Una frase que investiga, examina, sospecha, no descarta, ve
  posible o da por probable (configuracion/expresiones_duda.json, en los idiomas de las fuentes)
  nunca atribuye. Lo que la autoridad investiga va a la ficha como investigación en curso.
- **Nunca quien declara.** El autor no puede ser la propia autoridad que habla ni un nombre que
  coincida con ella.
- **Estado.** El país es el que nombra el autor («Rusia», «Russland») o, si el autor no es un
  país de la tabla, el que da el extractor. La frase tiene que nombrar a ese Estado: su
  nombre, su capital o su gentilicio. Si no lo nombra, no hay atribución.
- **Persona.** Solo si la autoridad la ha detenido, acusado o condenado. Su nombre se publica
  solo si la frase de la autoridad la nombra; si no, «una persona» (ACTOR_SIN_NOMBRE). Su
  nacionalidad, solo si la frase la dice con un gentilicio; nunca sale del nombre, del lugar ni
  del idioma.

Las fichas guardadas antes de esta regla no dicen si la frase es literal: sus atribuciones no se
sostienen y se retiran (recogida/tipo_atribucion.py), con su motivo en el historial.

La tabla de países (configuracion/paises_atribucion.json) es también la de las banderas de la
web: un país fuera de ella no se puede comprobar en la frase.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso.noticias import normalizar

CONFIGURACION = Path(__file__).parents[1] / "configuracion"
RUTA_PAISES = CONFIGURACION / "paises_atribucion.json"
RUTA_DUDA = CONFIGURACION / "expresiones_duda.json"
TIPOS = ("estado", "persona")
# Autoridades que pueden atribuir: las que gobiernan, defienden, acusan o detienen.
CATEGORIAS = frozenset({"gobierno", "ministerio", "fuerzas_armadas", "fiscalia", "policia"})
# Lo que la autoridad tiene que haber hecho con una persona para que se le atribuya.
SITUACIONES = ("detenida", "acusada", "condenada")
# Actor de una atribución a una persona que la autoridad no nombra: la web escribe «una
# persona» en su idioma.
ACTOR_SIN_NOMBRE = "persona sin nombre publicado"
ESTADO_ATRIBUIDO = "atribuido"
_ISO = re.compile(r"^[A-Z]{2}$")
# Las palabras de un nombre que bastan para reconocerlo: sin iniciales ni partículas.
_LETRAS_NOMBRE = 3
# Palabras de un nombre propio que se comparan con la autoridad que declara.
_LETRAS_DECLARANTE = 4
# «X (declaración oficial citada en medio)»: el nombre de la fuente de una declaración.
_DECLARACION = re.compile(r"^(?P<autoridad>.+) \(declaración oficial citada en (?P<medio>.+)\)$")


class Motivo(StrEnum):
    """Por qué una atribución no se sostiene."""

    INVESTIGACION = "investigacion"
    DUDA = "duda"
    DECLARANTE = "declarante"
    NO_LITERAL = "no_literal"
    NO_NOMBRA = "no_nombra"
    CATEGORIA = "categoria"
    TIPO = "tipo"
    PERSONA = "persona"


@dataclass(frozen=True)
class Decision:
    """Una atribución que se sostiene (`clase`: tipo, país y, de una persona, su actor) o el
    motivo por el que no (`motivo`, con la expresión que lo provoca si la hay)."""

    clase: Documento | None
    motivo: Motivo | None = None
    expresion: str | None = None


def _patron(termino: str) -> str:
    entero = termino.endswith("$")
    normal = normalizar(termino.rstrip("$"))
    return rf"(?<!\w){re.escape(normal)}" + (r"(?!\w)" if entero else "")


def _compilar(lista: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(_patron(t) for t in lista))


@cache
def _tabla() -> dict[str, dict[str, re.Pattern[str]]]:
    datos = json.loads(RUTA_PAISES.read_text(encoding="utf-8"))
    return {
        pais: {clase: _compilar(lista) for clase, lista in terminos.items()}
        for pais, terminos in datos["paises"].items()
    }


@cache
def _dudas() -> dict[Motivo, re.Pattern[str]]:
    datos = json.loads(RUTA_DUDA.read_text(encoding="utf-8"))
    return {
        Motivo.INVESTIGACION: _compilar(
            [t for lista in datos["investigacion"].values() for t in lista]
        ),
        Motivo.DUDA: _compilar([t for lista in datos["duda"].values() for t in lista]),
    }


def paises() -> frozenset[str]:
    """Los países que se pueden comprobar en una frase (y que tienen bandera en la web)."""
    return frozenset(_tabla())


def expresion_de_duda(frase: str) -> tuple[Motivo, str] | None:
    """La primera expresión de investigación o de duda de la frase, con su clase, o None."""
    normal = normalizar(frase)
    for motivo, patron in _dudas().items():
        if encontrada := patron.search(normal):
            return motivo, encontrada.group(0)
    return None


def es_investigacion(frase: str) -> bool:
    """Si la frase dice que una autoridad investiga, examina o comprueba algo."""
    return bool(_dudas()[Motivo.INVESTIGACION].search(normalizar(frase)))


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


def _palabras(texto: str, letras: int) -> set[str]:
    return {p for p in normalizar(texto).split() if len(p) >= letras}


def _nombra_persona(autor: str, frase: str) -> bool:
    return bool(_palabras(autor, _LETRAS_NOMBRE) & set(normalizar(frase).split()))


def es_declarante(autor: str, declarantes: list[str] | tuple[str, ...]) -> bool:
    """Si el autor coincide con quien declara: comparten una palabra de su nombre."""
    nombre = _palabras(autor, _LETRAS_DECLARANTE)
    return any(nombre & _palabras(d, _LETRAS_DECLARANTE) for d in declarantes)


def _iso(valor: object) -> str | None:
    codigo = str(valor or "").strip().upper()
    return codigo if _ISO.match(codigo) else None


def evaluar(
    autor: str,
    frase: str,
    tipo: str | None = None,
    pais: str | None = None,
    *,
    literal: bool | None = None,
    situacion: str | None = None,
    declarantes: list[str] | tuple[str, ...] = (),
) -> Decision:
    """Si una autoría se sostiene con la regla y, si se sostiene, su tipo, su país y su actor.
    `tipo`, `pais`, `literal` y `situacion` son los que da el extractor (None, una ficha
    anterior que no los traía); `declarantes`, los nombres de quien declara."""
    autor = autor.strip()
    if tipo is not None and tipo not in TIPOS:
        return Decision(None, Motivo.TIPO)
    if hallada := expresion_de_duda(frase):
        return Decision(None, hallada[0], hallada[1])
    if autor and es_declarante(autor, declarantes):
        return Decision(None, Motivo.DECLARANTE)
    if literal is not True:
        return Decision(None, Motivo.NO_LITERAL)
    nombrado = estado_nombrado(autor) if autor else None
    dado = _iso(pais)
    if tipo == "estado" or (tipo is None and nombrado is not None):
        elegido = nombrado or dado
        if elegido is not None and elegido in paises():
            if not menciona(frase, elegido):
                return Decision(None, Motivo.NO_NOMBRA)
            return Decision({"tipo": "estado", "pais": elegido})
        if not autor or not _nombra_persona(autor, frase):
            return Decision(None, Motivo.NO_NOMBRA)
        return Decision({"tipo": "estado", "pais": elegido} if elegido else {"tipo": "estado"})
    # Una persona: solo si la autoridad la ha detenido, acusado o condenado.
    if situacion not in SITUACIONES:
        return Decision(None, Motivo.PERSONA)
    clase: Documento = {"tipo": "persona"}
    if not autor or not _nombra_persona(autor, frase):
        clase["actor"] = ACTOR_SIN_NOMBRE
    if dado is not None and menciona(frase, dado, solo_gentilicio=True):
        clase["pais"] = dado
    return Decision(clase)


def clasificar(
    autor: str,
    frase: str,
    tipo: str | None = None,
    pais: str | None = None,
    **resto: Any,
) -> Documento | None:
    """El tipo y el país de una atribución que se sostiene, o None."""
    return evaluar(autor, frase, tipo, pais, **resto).clase


def autoridad_de_fuente(fuente: Documento) -> str:
    """El nombre de la autoridad de una fuente «declaración oficial citada»."""
    medio = str(fuente.get("medio", ""))
    encontrada = _DECLARACION.match(medio)
    return encontrada.group("autoridad") if encontrada else medio


def fuente_de_atribucion(incidente: Documento) -> Documento | None:
    """La fuente (la declaración citada) del último paso a atribuido del historial."""
    pasos = [p for p in incidente["estado"]["historial"] if p["estado"] == ESTADO_ATRIBUIDO]
    if not pasos:
        return None
    por_id = {f["id"]: f for f in incidente.get("fuentes", [])}
    fuente: Documento | None = por_id.get(pasos[-1]["fuente_id"])
    return fuente


def investigaciones(incidente: Documento) -> list[Documento]:
    """Lo que las autoridades dicen que investigan del incidente: cada declaración oficial
    citada cuya frase investiga, examina o comprueba, con su autoridad, su cita y su fuente."""
    resultado: list[Documento] = []
    for fuente in incidente.get("fuentes", []):
        frase = str(fuente.get("frase_origen", ""))
        if not fuente.get("es_autoridad") or not frase or not es_investigacion(frase):
            continue
        entrada = {
            "autoridad": autoridad_de_fuente(fuente),
            "cita": frase,
            "fuente_id": fuente["id"],
            "fecha": fuente["fecha"],
        }
        if entrada not in resultado:
            resultado.append(entrada)
    return resultado


def errores(incidente: Documento) -> list[str]:
    """Lo que no cuadra en la atribución de un incidente: sin tipo; una frase de la autoridad
    con duda o investigación; un autor que coincide con quien declara; un tipo o un país que no
    salen de la frase."""
    atribucion: dict[str, Any] | None = incidente.get("atribucion")
    if atribucion is None:
        return []
    tipo = atribucion.get("tipo")
    if tipo not in TIPOS:
        return ["atribución sin tipo de actor (estado o persona)"]
    fuente = fuente_de_atribucion(incidente)
    if fuente is None or not fuente.get("es_autoridad"):
        return []
    frase = str(fuente.get("frase_origen", ""))
    if hallada := expresion_de_duda(frase):
        return [f"la frase de la autoridad no afirma: {hallada[0].value} («{hallada[1]}»)"]
    actor = str(atribucion["actor"])
    declarantes = [str(atribucion["autoridad"]), autoridad_de_fuente(fuente)]
    if actor != ACTOR_SIN_NOMBRE and es_declarante(actor, declarantes):
        return [f"el autor ({actor}) coincide con la autoridad que declara"]
    # El tipo y el país, coherentes con la frase (que la validación da por literal: lo comprueba
    # la extracción, que es quien lo sabe).
    esperado = evaluar(
        "" if actor == ACTOR_SIN_NOMBRE else actor, frase, tipo, atribucion.get("pais"),
        literal=True, situacion=SITUACIONES[0],
    )  # fmt: skip
    if esperado.clase is None:
        return [f"la frase de la autoridad no nombra a quien se atribuye ({actor})"]
    if esperado.clase.get("pais") != atribucion.get("pais"):
        return [
            f"país de la atribución {atribucion.get('pais')!r} distinto del que dice la frase "
            f"de la autoridad ({esperado.clase.get('pais')!r})"
        ]
    return []


# --- Retirar una atribución que no se sostiene ------------------------------------------

# Lo que un titular no puede decir de un incidente sin atribuir: la nacionalidad de los drones
# (es de quien atribuye) y, si ninguna autoridad lo dice, que llevaban explosivos.
_NACIONALIDAD = {
    "es": re.compile(
        r"\s+(?:rus[oa]s?|bielorrus[oa]s?|ucranian[oa]s?|iran[ií]es|iran[ií])(?=\W|$)",
        re.IGNORECASE,
    ),
    "en": re.compile(r"(?<!\w)(?:Russian|Belarusian|Ukrainian|Iranian)\s+", re.IGNORECASE),
}
_EXPLOSIVOS = {
    "es": re.compile(
        r"\s+(?:con|cargad[oa]s? (?:de|con)|armad[oa]s? con) explosivos", re.IGNORECASE
    ),
    "en": re.compile(
        r"\s+(?:with|carrying|armed with|laden with) explosives|(?<!\w)explosive-laden\s+",
        re.IGNORECASE,
    ),
}
_AUTORIDAD_EXPLOSIVOS = re.compile(
    r"explos|sprengstoff|sprengsatz|exploz|wybuch|sprang|взрыв|вибух|robban", re.IGNORECASE
)


def _mayuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def titulo_sin_atribucion(incidente: Documento) -> dict[str, str]:
    """El titular de un incidente sin atribuir: sin la nacionalidad de los drones y sin
    explosivos que ninguna autoridad dice."""
    autoridad_dice_explosivos = any(
        f.get("es_autoridad") and _AUTORIDAD_EXPLOSIVOS.search(str(f.get("frase_origen", "")))
        for f in incidente.get("fuentes", [])
    )
    titulo: dict[str, str] = dict(incidente["titulo"])
    for idioma, patron in _NACIONALIDAD.items():
        texto = patron.sub(" " if idioma == "en" else "", titulo[idioma])
        if not autoridad_dice_explosivos:
            texto = _EXPLOSIVOS[idioma].sub(" " if idioma == "en" else "", texto)
        titulo[idioma] = _mayuscula(" ".join(texto.split()))
    return titulo


def retirar(incidente: Documento, motivo: dict[str, str], instante: Documento) -> Documento:
    """El incidente sin su atribución: un paso nuevo en el historial que vuelve al estado
    anterior a la atribución, con el motivo; lo que las autoridades investigan, como
    investigación en curso; y el titular sin lo que solo decía la atribución. Lo anterior del
    historial no se toca: la ficha enseña que estuvo atribuido y por qué dejó de estarlo."""
    historial = incidente["estado"]["historial"]
    anterior = next(p for p in reversed(historial) if p["estado"] != ESTADO_ATRIBUIDO)
    fuente = fuente_de_atribucion(incidente)
    paso = {
        "estado": anterior["estado"],
        "fecha": instante,
        "fuente_id": fuente["id"] if fuente is not None else historial[-1]["fuente_id"],
        "motivo": motivo,
    }
    resultado = {k: v for k, v in incidente.items() if k != "atribucion"}
    resultado["estado"] = {"actual": anterior["estado"], "historial": [*historial, paso]}
    if encontradas := investigaciones(incidente):
        resultado["investigacion"] = encontradas
    resultado["titulo"] = titulo_sin_atribucion(incidente)
    return resultado
