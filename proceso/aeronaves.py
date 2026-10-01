"""Clases de aeronave por su designador de tipo OACI y la marca militar de adsb.lol.

La base de adsb.lol marca cada aeronave con `dbFlags`, un campo de bits: 1 militar, 2
interesante, 4 PIA (dirección privada en EE. UU.) y 8 LADD (pide no ser mostrada). Una
aeronave es militar si lleva la marca 1 o si su tipo solo existe en versión militar (cazas,
aviones radar, cisternas, patrulla marítima, drones y helicópteros de combate). Un tipo que
también vuelan las aerolíneas o la aviación general (A332 de un MRTT, C295, King Air, NH90
de rescate) solo cuenta como militar con la marca.

Las listas de partida son las de skylight y gods-eye-view, ampliadas aquí con los aviones
radar, las cisternas, la patrulla marítima, los transportes militares y más cazas, drones
y helicópteros:

    ICAO type-designator sets (HELI, UAV, FASTJET) adapted from skylight,
    https://github.com/cpaczek/skylight (web/src/display/aircraftGlyph.ts),
    Copyright (c) 2026 cpaczek. MIT License.
    Further sets (UAV, FASTJET) adapted from gods-eye-view,
    https://github.com/bilawalsidhu/gods-eye-view (src/data/aircraftClass.js),
    Copyright (c) 2026 Bilawal Sidhu. MIT License.

El texto completo de esas licencias está en docs/licencias_terceros.md.
"""

from enum import StrEnum

MARCA_MILITAR = 1


class Clase(StrEnum):
    CAZA = "caza"
    RADAR = "radar"
    CISTERNA = "cisterna"
    PATRULLA_MARITIMA = "patrulla_maritima"
    HELICOPTERO = "helicoptero"
    DRON = "dron"
    TRANSPORTE = "transporte"
    OTRA = "otra"


# Cazas y entrenadores a reacción: el conjunto FASTJET de gods-eye-view y los designadores
# OACI de los cazas europeos y rusos que faltaban (Gripen, Mirage, Alpha Jet, Su-24/25...).
CAZAS = frozenset(
    [
        "F16",
        "F15",
        "F18",
        "FA18",
        "F18H",
        "F18S",
        "F14",
        "F22",
        "F35",
        "F4",
        "F5",
        "A10",
        "AV8B",
        "TYPH",
        "EUFI",
        "RFAL",
        "RAFL",
        "GRIP",
        "GRIF",
        "JS39",
        "JAS39",
        "TOR",
        "MIR2",
        "M2000",
        "SU27",
        "SU30",
        "SU33",
        "SU34",
        "SU35",
        "SU57",
        "SU24",
        "SU25",
        "MG29",
        "MIG29",
        "MG31",
        "J20",
        "T38",
        "HAWK",
        "L39",
        "L159",
        "M346",
        "T7A",
        "AJET",
        "M339",
        "K8",
        "T6",
        "PC21",
        "PC9",
    ]
)
# Aviones radar, de alerta temprana y de inteligencia electrónica: E-3 (E3TF, E3CF), E-7
# (E737), E-767, E-2, E-6, E-8, RC-135, U-2, A-50 y los Saab de alerta temprana.
RADAR = frozenset(
    [
        "E3TF",
        "E3CF",
        "E767",
        "E737",
        "E7",
        "E2",
        "E2C",
        "E2D",
        "E6",
        "E8",
        "R135",
        "RC35",
        "U2",
        "A50",
        "SB34",
        "S100",
    ]
)
# Cisternas: KC-135 (K35R, K35E), KC-46 (K46), KC-10, KC-767, KC-130J e Il-78. El A330 MRTT y
# el KC-30 vuelan como A332: solo con la marca militar.
CISTERNAS = frozenset(
    ["K35R", "K35E", "K35T", "K46", "KC46", "KC10", "K767", "C30J", "KC30", "IL78", "MRTT"]
)
# Patrulla marítima y antisubmarina: P-8, P-3, Atlantique 2, P-1 y Kawasaki.
PATRULLA_MARITIMA = frozenset(["P8", "P3", "ATL2", "ATLA", "BR1", "P1", "KP1"])
# Drones: el conjunto UAV de gods-eye-view y los designadores OACI de Global Hawk y Triton.
DRONES = frozenset(
    [
        "Q1",
        "Q4",
        "Q9",
        "MQ1",
        "MQ4",
        "MQ9",
        "RQ4",
        "GLHK",
        "TRIT",
        "TB2",
        "TB3",
        "SHDW",
        "HERN",
        "HRN",
        "HERM",
        "AKNC",
    ]
)
# Helicópteros de combate y transporte militar pesado (los demás, solo con la marca).
HELICOPTEROS_MILITARES = frozenset(
    ["H64", "TIGR", "A129", "H47", "H53", "H53S", "EH10", "MI24", "MI28", "KA52", "MI8", "LYNX"]
)
# Helicópteros de cualquier uso: el conjunto HELI de skylight y los militares.
HELICOPTEROS = (
    frozenset(
        [
            "EC20",
            "EC25",
            "EC30",
            "EC35",
            "EC45",
            "EC55",
            "AS50",
            "AS55",
            "AS65",
            "AS32",
            "A109",
            "A119",
            "A139",
            "A169",
            "A189",
            "B06",
            "B06T",
            "B407",
            "B412",
            "B427",
            "B429",
            "B430",
            "B505",
            "S76",
            "S92",
            "S61",
            "S64",
            "H60",
            "H500",
            "MD52",
            "MD60",
            "R22",
            "R44",
            "R66",
            "EXEC",
            "EXPL",
            "GAZL",
            "LYNX",
            "NH90",
            "PUMA",
            "SCAV",
            "UH1",
            "B105",
            "B212",
            "B214",
            "B222",
            "AC",
            "H47",
            "H64",
            "H160",
            "H145",
            "H135",
        ]
    )
    | HELICOPTEROS_MILITARES
)
# Transportes militares (y los que tienen también versión civil, que necesitan la marca).
TRANSPORTES_MILITARES = frozenset(
    ["C17", "C5M", "A400", "C130", "C27J", "C160", "IL76", "AN12", "AN124", "KC39", "C2"]
)
TRANSPORTES = TRANSPORTES_MILITARES | frozenset(
    ["C30J", "C295", "CN35", "A332", "B762", "B752", "B737"]
)

SOLO_MILITARES = (
    CAZAS
    | RADAR
    | CISTERNAS
    | PATRULLA_MARITIMA
    | DRONES
    | HELICOPTEROS_MILITARES
    | TRANSPORTES_MILITARES
)


def es_militar(tipo: str | None, marcas: int | None) -> bool:
    return bool((marcas or 0) & MARCA_MILITAR) or (tipo or "").upper() in SOLO_MILITARES


def clase(tipo: str | None, categoria: str | None = None) -> Clase:
    """La clase de una aeronave militar por su tipo; si el tipo no la dice, por la categoría
    de emisor ADS-B (A7 helicóptero, B6 dron)."""
    t = (tipo or "").upper()
    for conjunto, resultado in (
        (CAZAS, Clase.CAZA),
        (RADAR, Clase.RADAR),
        (CISTERNAS, Clase.CISTERNA),
        (PATRULLA_MARITIMA, Clase.PATRULLA_MARITIMA),
        (DRONES, Clase.DRON),
        (HELICOPTEROS, Clase.HELICOPTERO),
        (TRANSPORTES, Clase.TRANSPORTE),
    ):
        if t in conjunto:
            return resultado
    if categoria == "A7":
        return Clase.HELICOPTERO
    if categoria == "B6":
        return Clase.DRON
    return Clase.OTRA


# Categorías de emisor ADS-B de aviones de transporte y de negocios (A2 a A6): las que vuelan
# en IFR y cuentan en los movimientos de referencia de EUROCONTROL. A1 (ligeros), A7
# (helicópteros) y B (planeadores, globos, ultraligeros, drones) no cuentan.
CATEGORIAS_IFR = frozenset({"A2", "A3", "A4", "A5", "A6"})
LIGEROS = frozenset(
    [
        "C150",
        "C152",
        "C162",
        "C172",
        "C72R",
        "C175",
        "C177",
        "C180",
        "C182",
        "C185",
        "C188",
        "C206",
        "C207",
        "C210",
        "SR20",
        "SR22",
        "S22T",
        "PA18",
        "PA24",
        "PA28",
        "P28A",
        "P28B",
        "P28R",
        "PA32",
        "P32R",
        "PA38",
        "PA44",
        "DA20",
        "DA40",
        "DA42",
        "BE33",
        "BE35",
        "BE36",
        "BE76",
        "M20P",
        "M20T",
        "AA1",
        "AA5",
        "RV4",
        "RV6",
        "RV7",
        "RV8",
        "RV9",
        "RV10",
        "RV14",
        "G115",
        "BL8",
        "CH7",
    ]
)


def es_ifr(tipo: str | None, categoria: str | None, marcas: int | None) -> bool:
    """Si la aeronave cuenta como movimiento IFR comparable con la referencia: transporte o
    negocios, no ligera, no helicóptero ni militar."""
    t = (tipo or "").upper()
    if es_militar(t, marcas) or t in HELICOPTEROS or t in LIGEROS:
        return False
    if categoria:
        return categoria in CATEGORIAS_IFR
    return bool(t)
