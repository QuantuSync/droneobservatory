"""EODI-2025-00106 repetía EODI-2025-00049: el dron que la tripulación de un avión vio el domingo
28 de septiembre de 2025 al acercarse a Otopeni. Eran dos noticias del expediente penal, fechadas
por su publicación (30 de septiembre); una de ellas dice «acum două zile». Estuvo publicada como
otro suceso, con otro día, hasta el 10 de noviembre de 2026."""

from recogida import revisados

DOMINGO, REPETIDA = "EODI-2025-00049", "EODI-2025-00106"


def test_la_ficha_repetida_de_otopeni_se_une_a_la_del_domingo() -> None:
    grupos = [g for g in revisados.cargar()["unir"] if REPETIDA in g["registros"]]
    assert len(grupos) == 1
    (grupo,) = grupos
    assert set(grupo["registros"]) == {DOMINGO, REPETIDA}
    # Queda la del domingo: es la que tiene la fecha del suceso y su dirección.
    assert grupo["conserva"] == DOMINGO
    assert "acum două zile" in grupo["motivo"]


def test_ninguna_revision_la_separa_ni_la_da_por_distinta() -> None:
    datos = revisados.cargar()
    assert not [s for s in datos["separar"] if s["incidente"] in (DOMINGO, REPETIDA)]
    assert not [d for d in datos["distintos"] if REPETIDA in d["incidentes"]]
