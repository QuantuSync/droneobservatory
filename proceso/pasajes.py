"""Localización de los párrafos y tablas que interesan de un documento oficial.

El extractor nunca recibe un documento entero: solo los pasajes que nombran drones (el filtro
de palabras de dron de las noticias, en todos los idiomas, más «UAS», «RPAS» y «Drohnen-»
compuestos) y, para no perder la cifra o el lugar que da la frase siguiente, el párrafo de
después. Una tabla es un pasaje: sus filas van juntas. Un tope de letras por documento
limita el gasto: los pasajes van en el orden del documento hasta llenarlo.
"""

import hashlib
import re
from dataclasses import dataclass

from proceso.noticias import filtro

# 12 000 letras son unas 3000 palabras: varias respuestas a preguntas con sus tablas. Un
# documento más largo (un informe de investigación entero) se corta en los primeros pasajes.
MAX_LETRAS = 12_000
MIN_LETRAS_PARRAFO = 20
MAX_LETRAS_PARRAFO = 3_000
# Trozo de un párrafo largo: unas 150 palabras, lo que ocupa un párrafo normal.
LETRAS_TROZO = 1_000
# Palabras de dron que el filtro de noticias no tiene: siglas técnicas y compuestos alemanes,
# neerlandeses y escandinavos («Drohnenüberflüge», «droneobservationer»).
_TECNICAS = re.compile(
    r"\b(UAS|RPAS|UAV|sUAS|C-UAS|drohnen\w*|\w*drohne\w*|drone\w+|\w+drone[rns]?\b|"
    r"multicopter\w*|quadcopter\w*|onbemand\w*|ubemann\w*|ubemand\w*|unbemannt\w*|"
    r"obemannad\w*|bezza[łl]ogow\w*|miehittämät\w*)",
    re.IGNORECASE,
)
_FILA_TABLA = re.compile(r"(\S+\s{2,}){2,}\S+|(\S+\s*\|\s*){2,}\S+|(\S+\t){2,}\S+")


@dataclass(frozen=True)
class Pasajes:
    textos: tuple[str, ...]
    letras: int
    huella: str

    @property
    def texto(self) -> str:
        return "\n\n".join(self.textos)


def parrafos(texto: str) -> list[str]:
    """Párrafos de un texto plano (de PDF, HTML o API): separados por líneas en blanco; las
    líneas seguidas de un párrafo se unen, salvo las filas de una tabla, que se conservan."""
    bloques = re.split(r"\n\s*\n", texto.replace("\r\n", "\n"))
    resultado = []
    for bloque in bloques:
        lineas = [x.rstrip() for x in bloque.splitlines() if x.strip()]
        if not lineas:
            continue
        tabla = sum(bool(_FILA_TABLA.search(x)) for x in lineas) >= max(2, len(lineas) // 2)
        if tabla and sum(len(x) + 1 for x in lineas) <= MAX_LETRAS_PARRAFO:
            parrafo = "\n".join(lineas)
        else:
            # Un bloque grande (una página de PDF sin líneas en blanco) es texto aunque tenga
            # columnas: se trocea por frases.
            parrafo = " ".join(" ".join(lineas).split())
            # Las palabras cortadas por guion al final de línea se vuelven a unir.
            parrafo = re.sub(r"(\w)- (\w)", r"\1\2", parrafo)
        if len(parrafo) >= MIN_LETRAS_PARRAFO:
            resultado += _trozos(parrafo)
    return resultado


def _trozos(parrafo: str) -> list[str]:
    """Un párrafo largo (una página entera sin saltos) en trozos de frases enteras de hasta
    LETRAS_TROZO letras: así se localiza la parte que habla de drones y no se corta el final."""
    if len(parrafo) <= LETRAS_TROZO or "\n" in parrafo:
        return [parrafo[:MAX_LETRAS_PARRAFO]]
    trozos, actual = [], ""
    for frase in re.split(r"(?<=[.!?])\s+", parrafo):
        if len(frase) > LETRAS_TROZO:
            # Una «frase» sin puntos (listas, índices) se corta por palabras.
            palabras = frase.split()
            frase = ""
            for palabra in palabras:
                if frase and len(frase) + len(palabra) + 1 > LETRAS_TROZO:
                    trozos += [actual] if actual else []
                    actual = ""
                    trozos.append(frase)
                    frase = ""
                frase = f"{frase} {palabra}".strip()
        if actual and len(actual) + len(frase) + 1 > LETRAS_TROZO:
            trozos.append(actual)
            actual = ""
        actual = f"{actual} {frase}".strip()
    if actual:
        trozos.append(actual)
    return [t[:MAX_LETRAS_PARRAFO] for t in trozos]


def habla_de_drones(texto: str) -> bool:
    return bool(filtro().dron.search(texto) or _TECNICAS.search(texto))


def localizar(texto: str, max_letras: int = MAX_LETRAS) -> Pasajes:
    """Los pasajes que nombran drones, con el párrafo siguiente, sin repetir y en orden."""
    lista = parrafos(texto)
    elegidos: list[int] = []
    for i, parrafo in enumerate(lista):
        if habla_de_drones(parrafo):
            elegidos += [j for j in (i, i + 1) if j < len(lista) and j not in elegidos]
    textos: list[str] = []
    letras = 0
    for j in sorted(elegidos):
        if letras + len(lista[j]) > max_letras:
            break
        textos.append(lista[j])
        letras += len(lista[j])
    huella = hashlib.sha256("\n\n".join(textos).encode("utf-8")).hexdigest()
    return Pasajes(tuple(textos), letras, huella)
