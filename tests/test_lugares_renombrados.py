"""Un candidato anterior a un cambio del nomenclátor conserva el identificador viejo de su lugar:
el de EODI-2025-00397 (aeropuerto:way/384875110, hoy GCFV) no se podía preparar y se apartaba
en cada recogida con KeyError (configuracion/lugares_renombrados.json)."""

from typing import Any

from proceso import extraccion
from proceso.noticias import id_actual, nomenclator, renombrados


def test_cada_renombrado_va_a_un_lugar_que_existe_y_el_viejo_ya_no_esta() -> None:
    nom = nomenclator()
    tabla = renombrados()
    assert tabla["aeropuerto:way/384875110"] == "GCFV"
    for viejo, nuevo in tabla.items():
        assert viejo not in nom.lugares, viejo
        assert nuevo in nom.lugares, nuevo
        assert nom.lugares[nuevo].tipo == viejo.split(":", 1)[0]


def test_el_objetivo_del_candidato_viejo_es_el_aeropuerto_de_fuerteventura() -> None:
    candidato = {"id": "CAND-20251019T1715-aeropuerto:way/384875110-aeropuerto",
                 "lugar": "aeropuerto:way/384875110"}  # fmt: skip
    almacen: Any = None  # con el lugar en el nomenclátor no se lee el vocabulario
    objetivo = extraccion.objetivo_de(almacen, candidato, nomenclator())
    assert objetivo.id == "GCFV"
    assert objetivo.oaci == "GCFV"
    assert objetivo.pais == "ES"
    assert "Fuerteventura" in objetivo.nombre
    assert extraccion.palabras_objetivo("aeropuerto:way/384875110")
    assert "Fuerteventura" in " ".join(
        extraccion.nombres_objetivo("aeropuerto:way/384875110", objetivo)
    )


def test_un_identificador_vigente_no_cambia() -> None:
    assert id_actual("GCFV") == "GCFV"
    assert id_actual("EPWA") == "EPWA"
