"""Notas posteriores sobre sucesos ya registrados (proceso/incidentes.py, mismo_suceso_posterior):
una nota que vuelve meses después sobre un suceso con su día escrito se une sola al incidente
que ya está, si es el único de ese país, tipo y día; nunca une dos sucesos distintos."""

from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import incidentes
from tests import ejemplos

AHORA = datetime(2026, 10, 8, 15, 17, tzinfo=UTC)
MODELOS: frozenset[str] = frozenset()


def _incidente(
    id_: str,
    inicio: str,
    publicada: str,
    pais: str = "PL",
    tipo: str = "incursion",
    origen: str = "explicita",
    precision: str = "dia",
    punto: tuple[float, float] | None = None,
    region: str | None = None,
    fuentes: int = 1,
    cierre: bool = False,
) -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["id"] = id_
    documento["tipo"] = tipo
    documento["titulo"] = {"es": f"Suceso {id_}", "en": f"Event {id_}"}
    lugar: dict[str, Any] = {"pais": pais, "nivel": "pais"}
    if punto is not None:
        lugar.update(punto={"lat": punto[0], "lon": punto[1]}, radio_km=2.0, nivel="localidad")
    if region is not None:
        lugar["region"] = region
        if punto is None:
            lugar["nivel"] = "region"
    documento["lugar"] = lugar
    documento["tiempo"] = {
        "inicio": ejemplos.instante(inicio, precision),
        "origen_inicio": {"tipo": origen, "fuente_id": f"{id_}-0", "motivo": "prueba"},
    }
    documento["fuentes"] = []
    for n in range(fuentes):
        fuente = ejemplos.fuente(f"{id_}-{n}", "B")
        fuente["fecha"] = ejemplos.instante(publicada)
        fuente["enlace"] = f"https://ejemplo.pl/{id_}/{n}"
        documento["fuentes"].append(fuente)
    documento["estado"]["historial"][0]["fuente_id"] = f"{id_}-0"
    documento["estado"]["historial"][0]["fecha"] = ejemplos.instante(publicada)
    documento["control"]["alta"] = ejemplos.instante(publicada)
    if cierre:
        documento["consecuencias"] = {"cierre": {"valor": "si"}}
    return documento


# Los drones de Polonia de la noche del 9 al 10 de septiembre de 2025 (EODI-2025-00295) y la nota
# de un año después sobre el archivo de la investigación (EODI-2025-00442), con solo el país.
POLONIA = _incidente(
    "EODI-2025-00295",
    "2025-09-09T00:00Z",
    "2025-09-10T09:00Z",
    punto=(50.705, 23.44111),
    region="Lubelskie",
    fuentes=5,
)
ARCHIVO = _incidente("EODI-2025-00442", "2025-09-09T22:00Z", "2026-10-08T14:15Z")


def test_la_nota_del_archivo_de_la_investigacion_se_une_al_suceso() -> None:
    assert incidentes.nota_posterior(ARCHIVO)
    assert not incidentes.nota_posterior(POLONIA)
    assert incidentes.mismo_suceso_posterior(POLONIA, ARCHIVO)
    # La regla de siempre no la une: el suceso tiene punto y la nota solo el país.
    assert not incidentes.encajan(POLONIA, ARCHIVO)


def test_con_la_base_se_une_y_queda_anotada() -> None:
    # Como sobrevuelos: una incursión guardada pide la prueba de su origen, que aquí no hace falta.
    almacen = Almacen.abrir()
    almacen.guardar_incidente({**POLONIA, "tipo": "sobrevuelo"}, AHORA, MODELOS)
    almacen.guardar_incidente({**ARCHIVO, "tipo": "sobrevuelo"}, AHORA, MODELOS)
    assert incidentes.fusionar(almacen, AHORA, MODELOS, frozenset({POLONIA["id"]})) == 1
    unido = almacen.incidente(ARCHIVO["id"])
    assert unido is not None and unido["fusionado_en"] == POLONIA["id"]
    [fusion] = almacen.fusiones()
    assert fusion["motivo"] == incidentes.MOTIVO_NOTA_POSTERIOR
    # Revisar las fusiones no la deshace.
    assert incidentes.revisar_fusiones(almacen, AHORA, MODELOS) == []


@pytest.mark.parametrize(
    ("nota", "porque"),
    [
        (
            _incidente(
                "N",
                "2025-09-09T00:00Z",
                "2026-10-08T14:00Z",
                origen="publicacion",
                precision="aproximada",
            ),
            "día de la publicación, no escrito",
        ),
        (_incidente("N", "2025-09-09T00:00Z", "2025-09-10T10:00Z"), "no es posterior"),
        (_incidente("N", "2025-09-09T00:00Z", "2026-10-08T14:00Z", pais="LT"), "otro país"),
        (_incidente("N", "2025-09-09T00:00Z", "2026-10-08T14:00Z", tipo="sobrevuelo"), "otro tipo"),
        (_incidente("N", "2025-09-12T00:00Z", "2026-10-08T14:00Z"), "otro día"),
        (
            _incidente("N", "2025-09-09T00:00Z", "2026-10-08T14:00Z", region="Mazowieckie"),
            "otra región",
        ),
        (
            _incidente("N", "2025-09-09T00:00Z", "2026-10-08T14:00Z", punto=(52.23, 21.01)),
            "otro sitio (Varsovia)",
        ),
    ],
)
def test_no_une_lo_que_no_es_el_mismo_suceso(nota: dict[str, Any], porque: str) -> None:
    assert not incidentes.mismo_suceso_posterior(POLONIA, nota), porque


def test_dos_sucesos_del_mismo_dia_y_pais_la_nota_no_se_une_a_ninguno() -> None:
    # Moldavia, 7 de octubre de 2026: un dron por la mañana y otro por la tarde (EODI-2026-00492 y
    # EODI-2026-00496). Una nota de semanas después con solo el país y el día no sabe de cuál es.
    manana = _incidente(
        "EODI-2026-00492",
        "2026-10-07T07:00Z",
        "2026-10-07T09:00Z",
        pais="MD",
        precision="hora",
        tipo="sobrevuelo",
    )
    tarde = _incidente(
        "EODI-2026-00496",
        "2026-10-07T16:00Z",
        "2026-10-07T18:00Z",
        pais="MD",
        precision="hora",
        tipo="sobrevuelo",
    )
    nota = _incidente(
        "EODI-2026-00600", "2026-10-07T00:00Z", "2026-11-02T10:00Z", pais="MD", tipo="sobrevuelo"
    )
    almacen = Almacen.abrir()
    ahora = datetime(2026, 11, 3, 10, 17, tzinfo=UTC)
    for documento in (manana, tarde, nota):
        almacen.guardar_incidente(documento, ahora, MODELOS)
    publicados = frozenset({manana["id"], tarde["id"]})
    assert incidentes.mismo_suceso_posterior(manana, nota)
    assert incidentes.mismo_suceso_posterior(tarde, nota)
    assert incidentes.fusionar(almacen, ahora, MODELOS, publicados) == 0
    # Y los dos sucesos del día, que no son notas posteriores, siguen separados.
    assert not incidentes.mismo_suceso_posterior(manana, tarde)
    assert not incidentes.mismo_suceso_posterior(tarde, manana)


def test_dos_aeropuertos_cerrados_la_misma_noche_siguen_separados() -> None:
    # Lublin y Rzeszów (EODI-2026-00497 y EODI-2026-00498): una nota posterior que nombra uno de
    # los dos aeropuertos con su punto va solo con ese.
    lublin = _incidente(
        "EODI-2026-00497",
        "2026-10-07T00:00Z",
        "2026-10-07T08:00Z",
        tipo="interrupcion_aeroportuaria",
        punto=(51.24, 22.71),
        cierre=True,
    )
    rzeszow = _incidente(
        "EODI-2026-00498",
        "2026-10-07T00:00Z",
        "2026-10-07T08:00Z",
        tipo="interrupcion_aeroportuaria",
        punto=(50.11, 22.02),
        cierre=True,
    )
    nota = _incidente(
        "EODI-2026-00601",
        "2026-10-07T00:00Z",
        "2026-10-20T10:00Z",
        tipo="interrupcion_aeroportuaria",
        punto=(51.24, 22.71),
        cierre=True,
    )
    assert incidentes.mismo_suceso_posterior(lublin, nota)
    assert not incidentes.mismo_suceso_posterior(rzeszow, nota)
    assert not incidentes.mismo_suceso_posterior(lublin, rzeszow)


def test_dos_cierres_de_noches_distintas_no_se_juntan() -> None:
    # Lieja, 8 y 9 de noviembre de 2025: una nota posterior del cierre del 9 no va al del 8.
    ocho = _incidente(
        "EODI-2025-00230",
        "2025-11-08T00:00Z",
        "2025-11-08T22:00Z",
        pais="BE",
        tipo="interrupcion_aeroportuaria",
        cierre=True,
    )
    nota = _incidente(
        "EODI-2025-00399",
        "2025-11-09T00:00Z",
        "2025-12-01T10:00Z",
        pais="BE",
        tipo="interrupcion_aeroportuaria",
        cierre=True,
    )
    assert not incidentes.mismo_suceso_posterior(ocho, nota)
