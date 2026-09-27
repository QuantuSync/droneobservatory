import itertools

import pytest

from proceso.credibilidad import (
    Credibilidad,
    Declaracion,
    Fiabilidad,
    Postura,
    credibilidad,
)

A, B, C, D, E, F = (Fiabilidad(x) for x in "ABCDEF")


def respalda(nota: str, fiabilidad: Fiabilidad, autoridad: bool = False) -> Declaracion:
    return Declaracion(nota, fiabilidad, autoridad, Postura.RESPALDA)


def contradice(nota: str, fiabilidad: Fiabilidad, autoridad: bool = False) -> Declaracion:
    return Declaracion(nota, fiabilidad, autoridad, Postura.CONTRADICE)


CASOS = [
    ("dos A o B independientes", [respalda("n1", A), respalda("n2", B)], 1),
    ("confirma una autoridad", [respalda("n1", C, autoridad=True)], 1),
    ("autoridad y una C", [respalda("n1", B, autoridad=True), respalda("n2", C)], 1),
    ("una A sola", [respalda("n1", A)], 2),
    ("una B con una C que coincide", [respalda("n1", B), respalda("n2", C)], 2),
    ("réplicas de una misma nota B", [respalda("n1", B), respalda("n1", B)], 2),
    ("réplicas A de una misma nota", [respalda("n1", A), respalda("n1", A)], 2),
    ("una C sola", [respalda("n1", C)], 3),
    ("dos C independientes", [respalda("n1", C), respalda("n2", C)], 3),
    ("B contradicha por una C", [respalda("n1", B), contradice("n2", C)], 3),
    ("B contradicha por otra B", [respalda("n1", B), contradice("n2", B)], 4),
    ("C contradicha por una A", [respalda("n1", C), contradice("n2", A)], 4),
    (
        "dos A contradichas por una A",
        [respalda("n1", A), respalda("n2", A), contradice("n3", A)],
        4,
    ),
    ("la contradice una autoridad", [respalda("n1", A), contradice("n2", D, autoridad=True)], 5),
    (
        "autoridad frente a autoridad",
        [respalda("n1", A, autoridad=True), contradice("n2", A, autoridad=True)],
        5,
    ),
    ("sin declaraciones", [], 6),
    ("una D sola", [respalda("n1", D)], 3),
    ("una D con una E que coincide", [respalda("n1", D), respalda("n2", E)], 3),
    ("C contradicha por una D", [respalda("n1", C), contradice("n2", D)], 3),
    ("D contradicha por una E", [respalda("n1", D), contradice("n2", E)], 6),
    ("solo una E", [respalda("n1", E)], 6),
    ("solo E y F", [respalda("n1", E), respalda("n2", F)], 6),
    ("solo contradicciones", [contradice("n1", A)], 6),
]


@pytest.mark.parametrize(
    ("declaraciones", "esperado"),
    [(t, e) for _, t, e in CASOS],
    ids=[n for n, _, _ in CASOS],
)
def test_regla(declaraciones: list[Declaracion], esperado: int) -> None:
    assert credibilidad(declaraciones) == Credibilidad(esperado)


@pytest.mark.parametrize(
    "declaraciones",
    [t for _, t, _ in CASOS if len(t) > 1],
    ids=[n for n, t, _ in CASOS if len(t) > 1],
)
def test_no_depende_del_orden(declaraciones: list[Declaracion]) -> None:
    resultados = {credibilidad(p) for p in itertools.permutations(declaraciones)}
    assert len(resultados) == 1


def test_acepta_cualquier_iterable() -> None:
    assert credibilidad(iter([respalda("n1", A)])) is Credibilidad.PROBABLE


def test_fiabilidad_ordenada() -> None:
    assert [f.rango for f in Fiabilidad] == sorted(f.rango for f in Fiabilidad)
    assert A.rango < F.rango
