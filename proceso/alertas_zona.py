"""Alertas aéreas que una autoridad da por zonas (las Fuerzas Armadas de Letonia, por municipios).

Cada nota es de una zona y de una hora. La noche del 10 al 11 de noviembre de 2026 las Fuerzas
Armadas letonas avisaron en Ludza (23.25), en Augšdaugava y Krāslava (00.23) y en Balvi (01.25),
lo anularon a las 02.16, y hacia las 03.00 avisaron en Cēsis y, a las 03.18, en Smiltene y
Gulbene; a la mañana siguiente contaron la noche entera en una nota («Naktī uz 11. novembri
Latvijas gaisa telpā ielidoja trīs bezpilota lidaparāti»), alerta por alerta.

Este módulo solo lee esas notas: las zonas que nombra un texto y las horas que escribe, con el
patrón de la fuente (`alertas_por_zona` en configuracion/fuentes_oficiales.json). Qué es el mismo
suceso lo dice la definición (proceso/suceso.py): la nota de la noche y sus alertas lo son
(`suceso.resumen_de_la_misma_noche`). Hasta el 11 de noviembre de 2026 hubo aquí una regla
propia («otra zona y otra hora es otra alerta») que partió esa noche en dos fichas; se quitó."""

import re

from proceso.noticias import localidades_declinadas, lugares_en, nomenclator


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
