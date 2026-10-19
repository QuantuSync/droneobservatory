"""Aeropuertos del tráfico medido desde OurAirports (recogida/aeropuertos_ourairports.py)."""

import json
from pathlib import Path

from recogida import aeropuertos_ourairports as ourairports

CABECERA = (
    "id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,continent,iso_country,"
    "scheduled_service,icao_code"
)
AEROPUERTOS = "\n".join([
    CABECERA,
    "1,LEMG,large_airport,Malaga Airport,36.6749,-4.4991,53,EU,ES,yes,LEMG",
    # Melilla: España, pero en África para OurAirports, dentro de la caja del tráfico.
    "2,GEML,medium_airport,Melilla Airport,35.2798,-2.9563,156,AF,ES,yes,GEML",
    # Gran Canaria: España, en África y fuera de la caja.
    "3,GCLP,large_airport,Gran Canaria Airport,27.9319,-15.3866,78,AF,ES,yes,GCLP",
    # Nador: dentro de la caja, pero Marruecos no es un país del observatorio.
    "4,GMMW,medium_airport,Nador Airport,34.9888,-3.0282,574,AF,MA,yes,GMMW",
])  # fmt: skip
PISTAS = (
    "id,airport_ref,closed,le_ident,le_latitude_deg,le_longitude_deg,le_elevation_ft,"
    "he_ident,he_latitude_deg,he_longitude_deg,he_elevation_ft\n"
    "10,2,0,15,35.2860,-2.9600,150,33,35.2740,-2.9530,160\n"
)


def test_entran_los_de_un_pais_del_observatorio_en_otro_continente_dentro_de_la_caja() -> None:
    generados = {a["oaci"]: a for a in ourairports.generar(AEROPUERTOS, PISTAS)}
    assert set(generados) == {"LEMG", "GEML"}
    melilla = generados["GEML"]
    assert melilla["pais"] == "ES" and melilla["regular"] and len(melilla["pistas"]) == 2


def test_el_fichero_tiene_melilla_rodas_y_cos() -> None:
    ruta = Path(ourairports.DESTINO)
    oaci = {a["oaci"] for a in json.loads(ruta.read_text(encoding="utf-8"))["aeropuertos"]}
    assert {"GEML", "LGRP", "LGKO"} <= oaci
