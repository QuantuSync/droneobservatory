"""Auditoría de cobertura de una fuente de partes, por año.

Para cada día sin parte detectado se buscan publicaciones de esa mañana que
mencionen drones junto a cifras. Cada una se explica (nota de un mando
regional, solo reconocimiento, reportaje...) o queda como «sin explicación»:
es la señal de un formato que el detector aún no reconoce.
"""

import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from recogida.telegram import Publicacion

# "Esa mañana": los partes de la noche salen entre las 4:00 y las 13:00 hora local.
HORA_INICIO_MANANA = 4
HORA_FIN_MANANA = 13
CIFRA = re.compile(r"\d")
EJEMPLOS_SIN_EXPLICAR = 5


@dataclass
class Anio:
    dias: int = 0
    partes: int = 0
    fallidos: int = 0
    dias_con_parte: int = 0
    dias_sin_parte: int = 0
    # Días sin parte con alguna publicación candidata, por explicación.
    explicados: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    sin_explicar: list[str] = field(default_factory=list)


def por_dia(publicaciones: Iterable[Publicacion], zona: ZoneInfo) -> dict[date, list[Publicacion]]:
    dias: dict[date, list[Publicacion]] = defaultdict(list)
    for publicacion in publicaciones:
        dias[publicacion.fecha.astimezone(zona).date()].append(publicacion)
    return dias


def auditar(
    publicaciones: Iterable[Publicacion],
    zona: ZoneInfo,
    desde: date,
    hasta: date,
    es_parte: Callable[[str], bool],
    legible: Callable[[Publicacion], bool],
    palabras_dron: re.Pattern[str],
    explicar: Callable[[str], str | None],
) -> dict[int, Anio]:
    """Cobertura por año de `desde` a `hasta`, ambos incluidos, en la hora local de la fuente."""
    dias = por_dia(publicaciones, zona)
    resultado: dict[int, Anio] = defaultdict(Anio)
    dia = desde
    while dia <= hasta:
        anio = resultado[dia.year]
        anio.dias += 1
        partes = [p for p in dias.get(dia, []) if es_parte(p.texto)]
        anio.partes += len(partes)
        anio.fallidos += sum(not legible(p) for p in partes)
        if partes:
            anio.dias_con_parte += 1
        else:
            anio.dias_sin_parte += 1
            _explicar_dia(anio, dias.get(dia, []), zona, palabras_dron, explicar)
        dia += timedelta(days=1)
    return dict(resultado)


def _explicar_dia(
    anio: Anio,
    publicaciones: list[Publicacion],
    zona: ZoneInfo,
    palabras_dron: re.Pattern[str],
    explicar: Callable[[str], str | None],
) -> None:
    candidatas = [
        p
        for p in publicaciones
        if HORA_INICIO_MANANA <= p.fecha.astimezone(zona).hour < HORA_FIN_MANANA
        and palabras_dron.search(p.texto)
        and CIFRA.search(p.texto)
    ]
    if not candidatas:
        anio.explicados["sin publicaciones de drones con cifras esa mañana"] += 1
        return
    motivos = [explicar(p.texto) for p in candidatas]
    sin_motivo = [p for p, m in zip(candidatas, motivos, strict=True) if m is None]
    if sin_motivo:
        anio.sin_explicar.append(sin_motivo[0].enlace)
    else:
        # El motivo de la primera candidata basta para clasificar el día.
        anio.explicados[str(motivos[0])] += 1


def tabla(por_anio: dict[int, Anio], antes: dict[int, int] | None = None) -> str:
    """Tabla en Markdown. `antes` son los partes detectados por la versión anterior."""
    columnas = ["Año", "Días", *(["Partes antes"] if antes is not None else [])]
    columnas += ["Partes", "Fallidos", "Días sin parte", "Sin explicar"]
    lineas = ["| " + " | ".join(columnas) + " |", "| --- |" + " ---: |" * (len(columnas) - 1)]
    for anio, a in sorted(por_anio.items()):
        previo = [str(antes.get(anio, 0))] if antes is not None else []
        celdas = [str(anio), str(a.dias), *previo, str(a.partes), str(a.fallidos)]
        celdas += [str(a.dias_sin_parte), str(len(a.sin_explicar))]
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


def explicaciones(por_anio: dict[int, Anio]) -> str:
    """Días sin parte por explicación y hasta cinco enlaces sin explicar por año."""
    lineas: list[str] = []
    for anio, a in sorted(por_anio.items()):
        partes = ", ".join(f"{motivo}: {n}" for motivo, n in sorted(a.explicados.items()))
        lineas.append(f"- **{anio}**: {partes or '—'}.")
        if a.sin_explicar:
            ejemplos = ", ".join(a.sin_explicar[:EJEMPLOS_SIN_EXPLICAR])
            lineas.append(f"  Sin explicar ({len(a.sin_explicar)}): {ejemplos}")
    return "\n".join(lineas) + "\n"
