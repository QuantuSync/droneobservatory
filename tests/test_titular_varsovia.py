"""El titular revisado de EODI-2025-00233 (el cierre del aeropuerto de Varsovia por los drones rusos
del 10 de septiembre de 2025) decía en español solo «Aeropuerto de Varsovia-Frédéric Chopin»: el
nombre del sitio, no lo que pasó. En inglés estaba bien. Publicado así hasta el 10 de noviembre de
2026."""

from recogida import revisados


def _titulos_revisados() -> list[tuple[str, dict[str, str]]]:
    datos = revisados.cargar()
    return [
        (str(d["incidente"]), d["valor"])
        for d in datos["datos"]
        if d["campo"] == "titulo" and isinstance(d["valor"], dict)
    ]


def test_el_titular_de_varsovia_cuenta_el_suceso_en_los_dos_idiomas() -> None:
    (titulo,) = [valor for id_, valor in _titulos_revisados() if id_ == "EODI-2025-00233"]
    assert titulo["es"] == (
        "Los drones rusos que entraron en Polonia obligan a cerrar el aeropuerto de Varsovia"
    )
    assert titulo["en"] == "Russian drones that entered Poland force the closure of Warsaw airport"


def test_ningun_titular_revisado_se_queda_en_el_nombre_del_sitio() -> None:
    """Un titular de cuatro palabras o menos frente a otro de siete o más en el otro idioma no
    cuenta lo mismo."""
    desparejados = [
        id_
        for id_, valor in _titulos_revisados()
        for corto, largo in ((valor["es"], valor["en"]), (valor["en"], valor["es"]))
        if len(corto.split()) <= 4 and len(largo.split()) >= 7
    ]
    assert desparejados == []
