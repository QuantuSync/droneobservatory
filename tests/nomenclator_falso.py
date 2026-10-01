"""Nomenclátor de la capa de guerra para los tests: unas pocas localidades e instalaciones
reales (coordenadas redondeadas), con los casos difíciles: homónimos en el mismo óblast, una
palabra corriente («Мирне»), un distrito urbano y lo ocupado con código de Ucrania."""

from typing import Any

from proceso.lugares_guerra import Nomenclator


def _loc(
    id_: str, nombre: str, pais: str, region: str, lat: float, lon: float, **extra: Any
) -> dict[str, Any]:
    nombres = extra.pop("nombres", {"uk" if pais == "UA" else "ru": [nombre]})
    return {
        "id": id_, "nombre": nombre, "pais": pais, "region": region,
        "categoria": extra.pop("categoria", "aldea"), "lat": lat, "lon": lon,
        "radio_km": extra.pop("radio_km", 1.5), "nombres": nombres, "origen_punto": "prueba",
        **extra,
    }  # fmt: skip


LOCALIDADES = [
    _loc(
        "katotth:UA63120270010096107",
        "Харків",
        "UA",
        "UA-63",
        49.99,
        36.23,
        categoria="ciudad",
        radio_km=15.0,
        nombres={"uk": ["Харків"], "ru": ["Харьков"], "la": ["Kharkiv"]},
    ),
    _loc(
        "katotth:UA63140170010036104",
        "Чугуїв",
        "UA",
        "UA-63",
        49.84,
        36.69,
        categoria="ciudad",
        radio_km=4.0,
        raion="Чугуївський",
        hromada="Чугуївська",
        nombres={"uk": ["Чугуїв"], "ru": ["Чугуев"], "la": ["Chuhuiv"]},
    ),
    # Dos Малинівка en el mismo óblast, en distritos distintos.
    _loc(
        "katotth:UA63140050010015082",
        "Малинівка",
        "UA",
        "UA-63",
        49.81,
        36.71,
        categoria="asentamiento",
        radio_km=2.5,
        raion="Чугуївський",
        hromada="Малинівська",
    ),
    _loc(
        "katotth:UA63080010020091234",
        "Малинівка",
        "UA",
        "UA-63",
        49.30,
        35.80,
        raion="Красноградський",
        hromada="Зачепилівська",
    ),
    # Una palabra corriente: «мирне населення».
    _loc("katotth:UA12020150190068810", "Мирне", "UA", "UA-12", 48.10, 35.10),
    _loc(
        "katotth:UA12080050010010114",
        "Нікополь",
        "UA",
        "UA-12",
        47.57,
        34.40,
        categoria="ciudad",
        radio_km=7.0,
        nombres={"uk": ["Нікополь"], "ru": ["Никополь"]},
    ),
    _loc(
        "katotth:UA12080070010012345",
        "Марганець",
        "UA",
        "UA-12",
        47.65,
        34.62,
        categoria="ciudad",
        radio_km=4.0,
    ),
    _loc(
        "katotth:UA51080030010072039",
        "Ізмаїл",
        "UA",
        "UA-51",
        45.35,
        28.84,
        categoria="ciudad",
        radio_km=5.0,
    ),
    # Lo ocupado: Crimea con su código ucraniano.
    _loc(
        "katotth:UA01160330010074014",
        "Феодосія",
        "UA",
        "UA-43",
        45.03,
        35.38,
        categoria="ciudad",
        radio_km=5.0,
        nombres={"uk": ["Феодосія"], "ru": ["Феодосия"]},
    ),
    # Una aldea que se llama como un país: nunca sale.
    _loc("katotth:UA12000000000000001", "Україна", "UA", "UA-12", 48.0, 35.0),
    _loc(
        "geonames:578072",
        "Белгород",
        "RU",
        "RU-BEL",
        50.61,
        36.58,
        categoria="ciudad",
        radio_km=10.0,
        raion="Belgorodskiy Rayon",
        nombres={"ru": ["Белгород"], "la": ["Belgorod"]},
    ),
    _loc(
        "geonames:495112",
        "Шебекино",
        "RU",
        "RU-BEL",
        50.41,
        36.90,
        categoria="ciudad",
        radio_km=4.0,
        raion="Shebekinskiy Rayon",
    ),
    _loc(
        "geonames:500096",
        "Рязань",
        "RU",
        "RU-RYA",
        54.63,
        39.74,
        categoria="ciudad",
        radio_km=10.0,
        nombres={"ru": ["Рязань"], "la": ["Ryazan"]},
    ),
    _loc(
        "geonames:518255",
        "Новокуйбышевск",
        "RU",
        "RU-SAM",
        53.10,
        49.95,
        categoria="ciudad",
        radio_km=5.0,
        nombres={"ru": ["Новокуйбышевск"], "uk": ["Новокуйбишевськ"]},
    ),
    _loc(
        "geonames:548393",
        "Кириши",
        "RU",
        "RU-LEN",
        59.45,
        32.02,
        categoria="ciudad",
        radio_km=4.0,
        nombres={"ru": ["Кириши"], "la": ["Kirishi"]},
    ),
]

INSTALACIONES = [
    {"osm": "way/1", "categoria": "refineria", "pais": "RU", "region": "RU-RYA",
     "lat": 54.59, "lon": 39.80, "radio_km": 3.0,
     "nombres": {"ru": ["Рязанская нефтеперерабатывающая компания"]}},
    {"osm": "way/2", "categoria": "refineria", "pais": "RU", "region": "RU-SAM",
     "lat": 53.12, "lon": 49.93, "radio_km": 3.0,
     "nombres": {"ru": ["Новокуйбышевский НПЗ"], "uk": ["Новокуйбишевський НПЗ"]}},
    {"osm": "way/3", "categoria": "refineria", "pais": "RU", "region": "RU-LEN",
     "lat": 59.46, "lon": 32.05, "radio_km": 3.0, "nombres": {"ru": ["КИНЕФ"]}},
    {"osm": "way/4", "categoria": "deposito_combustible", "pais": "UA", "region": "UA-43",
     "lat": 45.04, "lon": 35.36, "radio_km": 1.5, "nombres": {"ru": ["Феодосийская нефтебаза"]}},
    {"osm": "way/5", "categoria": "aerodromo", "pais": "RU", "region": "RU-KLU", "oaci": "UUBC",
     "lat": 54.55, "lon": 36.37, "radio_km": 4.0, "nombres": {"ru": ["Аэропорт Калуга"]}},
]  # fmt: skip

DISTRITOS = [
    {"nombre": "Київський", "ciudad": "katotth:UA63120270010096107", "region": "UA-63"},
    {"nombre": "Шевченківський", "ciudad": "katotth:UA63120270010096107", "region": "UA-63"},
]


def nomenclator(comunes: tuple[str, ...] = ("мирне",)) -> Nomenclator:
    return Nomenclator.desde_datos(
        {
            "localidades": LOCALIDADES,
            "instalaciones": INSTALACIONES,
            "distritos_urbanos": DISTRITOS,
        },
        comunes,
    )
