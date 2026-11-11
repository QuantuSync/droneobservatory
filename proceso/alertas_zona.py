"""Alertas aéreas que una autoridad da por zonas (las Fuerzas Armadas de Letonia, por municipios).

Cada nota es de una zona y de una hora. La noche del 10 al 11 de noviembre de 2026 las Fuerzas
Armadas letonas avisaron en Ludza (23.25), en Augšdaugava y Krāslava (00.23) y en Balvi (01.25),
lo anularon a las 02.16, y hacia las 03.00 avisaron en Cēsis y, a las 03.18, en Smiltene y
Gulbene: otro objeto, en el centro y el norte del país. Dos alertas de la misma autoridad en zonas
distintas y a horas distintas no son el mismo suceso: la nota de la segunda no se enlaza a la
ficha de la primera (recogida/oficiales.posibles) ni el filtro de entrada une sus fichas
(recogida/entrada.nunca_el_mismo).

La regla solo vale para las fuentes que la piden (`alertas_por_zona` en
configuracion/fuentes_oficiales.json, con el patrón de la hora de sus títulos) y solo dice
«otra alerta» cuando sabe las dos cosas de las dos partes: zonas del nomenclátor sin ninguna en
común y horas a más de MARGEN_MIN. Si falta algo (la nota que anula no escribe la hora, el
municipio no está en el nomenclátor), no dice nada y decide lo de siempre."""

import re
from collections.abc import Iterable

from proceso.noticias import localidades_declinadas, lugares_en, nomenclator

# Dos avisos a menos de una hora son la misma alerta que se amplía a los municipios vecinos.
MARGEN_MIN = 60
_DIA_MIN = 24 * 60


def zonas(texto: str, pais: str) -> frozenset[str]:
    """Los lugares del país que nombra el texto (también declinados: «Smiltenes un Gulbenes»)."""
    nom = nomenclator()
    hallados = [*lugares_en(texto, nom), *localidades_declinadas(texto, nom)]
    return frozenset(h for h in hallados if h in nom.lugares and nom.lugares[h].pais == pais)


def horas(texto: str, patron: str) -> frozenset[int]:
    """Las horas que escribe el texto, en minutos del día, con el patrón de la fuente (dos
    grupos: la hora y los minutos)."""
    minutos = set()
    for m in re.finditer(patron, texto):
        hora, minuto = int(m[1]), int(m[2])
        if hora < 24 and minuto < 60:
            minutos.add(hora * 60 + minuto)
    return frozenset(minutos)


def _separadas(a: frozenset[int], b: frozenset[int]) -> bool:
    """Todas las horas de un lado están a más de MARGEN_MIN de todas las del otro (el reloj da la
    vuelta a medianoche: las 23.25 y las 00.23 están a 58 minutos)."""

    def distancia(x: int, y: int) -> int:
        return min(abs(x - y), _DIA_MIN - abs(x - y))

    return all(distancia(x, y) > MARGEN_MIN for x in a for y in b)


def otra_alerta(de_la_ficha: Iterable[str], de_la_nota: Iterable[str], pais: str,
                patron_hora: str) -> bool:  # fmt: skip
    """Los títulos de las notas de una ficha y los de otra nota (u otra ficha) de la misma
    autoridad son de alertas distintas: zonas sin ninguna en común y horas separadas."""
    textos_a, textos_b = " . ".join(de_la_ficha), " . ".join(de_la_nota)
    zonas_a, zonas_b = zonas(textos_a, pais), zonas(textos_b, pais)
    if not zonas_a or not zonas_b or zonas_a & zonas_b:
        return False
    horas_a, horas_b = horas(textos_a, patron_hora), horas(textos_b, patron_hora)
    return bool(horas_a and horas_b) and _separadas(horas_a, horas_b)
