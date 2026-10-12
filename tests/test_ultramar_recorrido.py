"""Un incidente en el suelo europeo de fuera del continente entra de verdad: del artículo al
candidato, de la ficha del extractor al incidente validado con el país padre, al GeoJSON del
mapa y a los canales de avisos de su país y de Europa. Ningún filtro pensado para el continente
lo tira."""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from exportacion.geojson import exportar
from modelo import coste, ficha
from proceso import extraccion
from proceso.noticias import Articulo
from proceso.validaciones import validar_incidente
from recogida import avisos, gdelt
from tests.test_extraccion import AHORA, MODELOS, campo, ficha_ejemplo, respuesta, suceso


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


CASOS = [
    # (lugar, medio, idioma, país del medio, titular, texto, país de la ficha, lugar del suceso,
    #  país esperado)
    (
        "GEML",
        "elfarodemelilla.es",
        "es",
        "ES",
        "Un dron obliga a retrasar el aterrizaje de un vuelo en el aeropuerto de Melilla",
        "Un dron voló sobre el aeropuerto de Melilla y obligó a retrasar el aterrizaje de un "
        "vuelo de Iberia el martes por la noche.",
        "ES",
        suceso("aeropuerto de Melilla", "instalacion", "ES", "Melilla"),
        "ES",
    ),
    (
        "LCRA",
        "cyprus-mail.com",
        "en",
        "CY",
        "Drone hits hangar at RAF Akrotiri air base",
        "A drone hit a hangar at RAF Akrotiri air base on Sunday night, causing minor damage.",
        "CY",
        suceso("RAF Akrotiri", "instalacion", "CY", ""),
        "GB",
    ),
    (
        "FMEE",
        "clicanoo.re",
        "fr",
        "FR",
        "Un drone survole l'aéroport Roland-Garros de La Réunion",
        "Un drone a survolé l'aéroport Roland-Garros de La Réunion samedi soir, le trafic a été "
        "suspendu.",
        "RE",
        suceso("aéroport Roland-Garros", "instalacion", "RE", "La Réunion"),
        "FR",
    ),
    (
        "ENSB",
        "svalbardposten.no",
        "no",
        "NO",
        "Drone over Svalbard lufthavn Longyear",
        "En drone ble observert over Svalbard lufthavn Longyear lørdag kveld.",
        "SJ",
        suceso("Svalbard lufthavn Longyear", "instalacion", "SJ", "Svalbard"),
        "NO",
    ),
]


def _ficha(texto: str, titular: str, pais: str, lugar: dict[str, str]) -> dict[str, Any]:
    frase = texto.split(",")[0]
    return ficha_ejemplo(
        es_incidente=campo(True, frase),
        tipo=campo("avistamiento", frase),
        inicio=campo(None),
        inicio_precision=campo(None),
        pais=campo(pais, frase),
        lugar_suceso=campo(lugar, frase),
        localidad=campo(None),
        objetivo_conocido=campo(True, frase),
        drones=campo({"min": 1, "max": 1}, frase),
        presencia_dron=campo("no_confirmada", frase),
        cierre=campo(None),
        vuelos_desviados=campo(None),
        titulo_es=titular,
        titulo_en=titular,
    )


@pytest.mark.parametrize("caso", CASOS, ids=[c[0] for c in CASOS])
def test_un_incidente_de_ultramar_llega_al_mapa_y_a_los_avisos(
    almacen: Almacen, caso: tuple[Any, ...]
) -> None:
    lugar, medio, idioma, pais_medio, titular, texto, pais, suceso_, esperado = caso
    articulo = Articulo(
        url=f"https://{medio}/noticia", medio=medio, fecha=AHORA - timedelta(hours=3),
        titular=titular, idioma=idioma, pais=pais_medio, lugares=(lugar,),
    )  # fmt: skip
    gdelt.incorporar(almacen, [articulo])
    (candidato,) = almacen.candidatos()
    peticion = extraccion.preparar(almacen, candidato, None)
    peticion = extraccion.Peticion(
        **{**peticion.__dict__, "fuentes": [
            ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, texto)
            for f in peticion.fuentes
        ]}
    )  # fmt: skip
    id_ = extraccion.procesar_respuesta(
        almacen, peticion, respuesta(_ficha(texto, titular, pais, suceso_)), AHORA,
        coste.Modo.HORARIO, False, MODELOS,
    )  # fmt: skip
    assert id_ is not None, almacen.extracciones(candidato["id"])[-1]["documento"]["motivos"]
    incidente = almacen.incidente(id_)
    assert incidente is not None
    assert incidente["lugar"]["pais"] == esperado
    assert "punto" in incidente["lugar"]
    assert validar_incidente(incidente, AHORA, MODELOS) == []
    mapa = exportar([incidente], AHORA, MODELOS)
    assert [f["id"] for f in mapa["features"]] == [id_]
    config = avisos.configuracion()
    assert esperado in config["paises"]


def test_los_incidentes_guardados_con_el_pais_de_antes_pasan_al_suyo(almacen: Almacen) -> None:
    from recogida import suelo_europeo

    ids = {}
    for caso in (CASOS[0], CASOS[1]):
        lugar, medio, idioma, pais_medio, titular, texto, pais, suceso_, _ = caso
        articulo = Articulo(
            url=f"https://{medio}/antes", medio=medio, fecha=AHORA - timedelta(hours=3),
            titular=titular, idioma=idioma, pais=pais_medio, lugares=(lugar,),
        )  # fmt: skip
        gdelt.incorporar(almacen, [articulo])
        candidato = next(c for c in almacen.candidatos() if articulo.url in c["articulos"])
        peticion = extraccion.preparar(almacen, candidato, None)
        peticion = extraccion.Peticion(
            **{**peticion.__dict__, "fuentes": [
                ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, texto)
                for f in peticion.fuentes
            ]}
        )  # fmt: skip
        id_ = extraccion.procesar_respuesta(
            almacen, peticion, respuesta(_ficha(texto, titular, pais, suceso_)), AHORA,
            coste.Modo.HORARIO, False, MODELOS,
        )  # fmt: skip
        assert id_ is not None
        ids[lugar] = id_
    # Como estaban antes del 12 de octubre: Melilla bien (ES), Akrotiri en Chipre.
    # (la validación de hoy ya no lo deja guardar así: se pone directamente en la base).
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = json_set(documento, '$.lugar.pais', 'CY') WHERE id = ?",
        (ids["LCRA"],),
    )
    almacen.conexion.commit()
    assert suelo_europeo.paso_horario(almacen, AHORA, MODELOS) == 1
    corregido = almacen.incidente(ids["LCRA"])
    assert corregido is not None and corregido["lugar"]["pais"] == "GB"
    assert suelo_europeo.paso_horario(almacen, AHORA, MODELOS) == 0
    assert suelo_europeo.pais_corregido({"pais": "GI"}) == "GB"
    assert suelo_europeo.pais_corregido({"pais": "ES"}) is None
