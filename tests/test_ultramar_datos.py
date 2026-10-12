"""Suelo europeo fuera del continente: cada territorio cae dentro del país del que depende
(fronteras), el nomenclátor sitúa un titular en cada uno con el país padre, y GDELT cuenta
sus lugares y sus medios como de ese país."""

import pytest

from proceso.fronteras import dentro_del_pais, es_nombre_de_pais, paises
from proceso.noticias import lugar_del_suceso, nomenclator
from proceso.prevision.datos import cajas_de_paises
from proceso.ubicacion import regiones_con_nombre
from recogida.gdelt import medios

PUNTOS = [
    ("Nuuk", 64.18, -51.72, "DK"),
    ("Marigot", 18.07, -63.08, "FR"),
    ("RAF Akrotiri", 34.59, 32.99, "GB"),
    ("Dhekelia", 35.0, 33.75, "GB"),
    ("Gibraltar", 36.14, -5.35, "GB"),
    ("Las Palmas de Gran Canaria", 28.1, -15.42, "ES"),
    ("Melilla", 35.29, -2.94, "ES"),
    ("Islas Chafarinas", 35.18, -2.43, "ES"),
    ("Ponta Delgada", 37.74, -25.67, "PT"),
    ("Funchal", 32.65, -16.91, "PT"),
    ("Kourou", 5.16, -52.65, "FR"),
    ("Saint-Denis de La Réunion", -20.88, 55.45, "FR"),
    ("Mamoudzou", -12.78, 45.23, "FR"),
    ("Pointe-à-Pitre", 16.24, -61.53, "FR"),
    ("Fort-de-France", 14.6, -61.07, "FR"),
    ("Longyearbyen", 78.22, 15.65, "NO"),
    ("Pafos", 34.77, 32.42, "CY"),
    ("Lárnaca", 34.92, 33.62, "CY"),
]


@pytest.mark.parametrize(("nombre", "lat", "lon", "pais"), PUNTOS)
def test_cada_territorio_cae_en_su_pais(nombre: str, lat: float, lon: float, pais: str) -> None:
    assert dentro_del_pais(pais, lat, lon), nombre


def test_las_bases_de_chipre_son_britanicas_y_no_chipriotas() -> None:
    assert not dentro_del_pais("CY", 34.59, 32.99)
    assert "GI" not in paises() and "GL" not in paises()


def test_los_territorios_que_son_un_sitio_no_se_bloquean_como_paises() -> None:
    for nombre in ("gibraltar", "akrotiri", "dhekelia"):
        assert not es_nombre_de_pais(nombre)
    # Un territorio entero, como un país, no sitúa nada.
    assert es_nombre_de_pais("greenland")


TITULARES = [
    ("Drone sighted over Gran Canaria airport", "GCLP", "ES"),
    ("Drone near RAF Akrotiri", "LCRA", "GB"),
    ("Drone at Nuuk Airport", "BGGH", "DK"),
    ("Drohne über dem Flughafen Longyearbyen", "ENSB", "NO"),
    ("drone à l'aéroport Roland-Garros de La Réunion", "FMEE", "FR"),
    ("dron sobre el aeropuerto de Melilla", "GEML", "ES"),
    ("drone sobre o aeroporto de Ponta Delgada", "LPPD", "PT"),
    ("Drone over Gibraltar Airport", "LXGB", "GB"),
    ("drone au-dessus de l'aéroport de Pointe-à-Pitre", "TFFR", "FR"),
    ("Drone over Thule Air Base", "BGTL", "DK"),
    ("Drone spotted near the Guiana Space Centre", "base:relation/8090912", "FR"),
]


@pytest.mark.parametrize(("titular", "lugar", "pais"), TITULARES)
def test_el_nomenclator_situa_un_titular_en_cada_territorio(
    titular: str, lugar: str, pais: str
) -> None:
    nom = nomenclator()
    hallado = lugar_del_suceso(titular, "", nom)
    assert hallado == lugar
    sitio = nom.lugares[hallado]
    assert sitio.pais == pais
    assert dentro_del_pais(pais, sitio.lat, sitio.lon)


def test_kourou_es_la_localidad_de_la_guayana() -> None:
    nom = nomenclator()
    hallado = lugar_del_suceso("drone au-dessus de Kourou", "", nom)
    assert hallado is not None
    sitio = nom.lugares[hallado]
    assert sitio.pais == "FR" and abs(sitio.lat - 5.16) < 0.1 and abs(sitio.lon + 52.65) < 0.1


def test_un_nombre_compartido_es_de_la_localidad_del_continente() -> None:
    nom = nomenclator()
    sitio = nom.lugares[lugar_del_suceso("Drone über Saint-Denis gesichtet", "", nom) or ""]
    assert sitio.lat > 40  # Saint-Denis (Seine-Saint-Denis), no la de La Reunión


def test_las_localidades_de_cada_territorio_tienen_su_region() -> None:
    for pais, region in (("FR", "Guadeloupe"), ("FR", "La Réunion"), ("FR", "Mayotte"),
                         ("FR", "Guyane"), ("FR", "Martinique"), ("FR", "Saint-Martin"),
                         ("DK", "Greenland"), ("NO", "Svalbard"), ("GB", "Gibraltar"),
                         ("GB", "Akrotiri"), ("GB", "Dhekelia")):  # fmt: skip
        assert regiones_con_nombre(pais, region), region


def test_gdelt_cuenta_los_territorios_como_su_pais() -> None:
    tabla = medios()
    for fips, iso in (("GI", "GB"), ("AX", "GB"), ("DX", "GB"), ("GL", "DK"), ("SV", "NO"),
                      ("RE", "FR"), ("MF", "FR"), ("GP", "FR"), ("MB", "FR"), ("FG", "FR"),
                      ("RN", "FR"), ("SP", "ES"), ("PO", "PT")):  # fmt: skip
        assert tabla.fips[fips] == iso
    assert tabla.pais("www.clicanoo.re") == "FR"
    assert tabla.pais("sermitsiaq.ag") == "DK"
    assert tabla.pais("gbc.gi") == "GB"
    assert tabla.pais("guadeloupe.franceantilles.fr") == "FR"


def test_la_caja_de_dinamarca_en_la_prevision_no_es_groenlandia() -> None:
    lon_min, _lat_min, _lon_max, lat_max = cajas_de_paises(["DK"])["DK"]
    assert lon_min > 0 and lat_max < 60
