"""Alias y ciudades del nomenclátor que son solo palabras corrientes: «Norden» («en el norte») llevó
el aeropuerto de Bremen al aeródromo de Norden-Norddeich (EODI-2025-00174) y «Base navale», una
base de La Reunión, se quedó con la base naval de Toulon (EODI-2026-00649). Solos no casan nada
(proceso/noticias.generico); la auditoría lo vigila con la comprobación I."""

from proceso import auditoria_fichas, noticias

# La frase de kreiszeitung.de de EODI-2025-00174.
FRASE_BREMEN = (
    "Drohnen-Alarm im Norden: Flugverkehr am Bremer Airport für fast eine Stunde lahmgelegt"
)
# La de nicematin.com de EODI-2026-00649.
FRASE_TOULON = (
    "La base navale de Toulon survolée par des drones non autorisés, une enquête judiciaire ouverte"
)
REUNION = "base:way/662378236"
TOULON = "base:wikidata/Q1564994"


def test_palabras_corrientes_no_nombran_nada() -> None:
    assert noticias.generico("norden")
    assert noticias.generico("base navale")
    assert noticias.generico("stadion miejski nr 1")
    assert noticias.generico("military base 01602")
    # Un nombre propio basta; y las de tipo cuentan enteras, no por prefijo («Bazaly»).
    assert not noticias.generico("base navale de toulon")
    assert not noticias.generico("stadion bazaly")
    # Las que son también un lugar no están en la lista.
    assert not noticias.generico("aeroporto do porto")
    assert not noticias.generico("halle")


def test_bremen_no_va_a_norden() -> None:
    nom = noticias.nomenclator()
    assert noticias.lugares_en(FRASE_BREMEN, nom) == ("EDDW",)
    assert noticias.lugares_en("Drohnensichtung an Airport im Norden", nom) == ()
    # El nombre propio del aeródromo sigue casando.
    assert noticias.lugares_en("Drohne über dem Flugplatz Norden-Norddeich", nom) == ("EDWS",)


def test_toulon_en_su_base_y_no_en_la_reunion() -> None:
    nom = noticias.nomenclator()
    assert REUNION in nom.lugares
    assert noticias.lugares_en(FRASE_TOULON, nom) == (TOULON,)
    assert noticias.lugares_en("Drones over Toulon naval base", nom) == (TOULON,)
    assert noticias.lugares_en("Des drones survolent une base navale", nom) == ()
    # El aeropuerto de Toulon-Hyères sigue siendo el aeropuerto.
    assert noticias.lugares_en("Drone à l'aéroport de Toulon", nom) == ("LFTH",)


def _ficha(objetivo: dict[str, str], frase: str) -> dict[str, object]:
    return {
        "id": "EODI-2025-00174",
        "tipo": "interrupcion_aeroportuaria",
        "titulo": {"es": "Dron sobre el aeropuerto de Bremen"},
        "objetivo": objetivo,
        "lugar": {"pais": "DE", "localidad": "Bremen", "nivel": "instalacion"},
        "fuentes": [{"id": "f", "frase_origen": frase}],
    }


def test_auditoria_i() -> None:
    norden = {"categoria": "aeropuerto", "nombre": "Flugplatz Norden-Norddeich", "oaci": "EDWS"}
    assert auditoria_fichas._i(_ficha(norden, FRASE_BREMEN))
    bremen = {"categoria": "aeropuerto", "nombre": "Flughafen Bremen", "oaci": "EDDW"}
    assert not auditoria_fichas._i(_ficha(bremen, FRASE_BREMEN))
    # Si una fuente lo nombra por su nombre propio, no es un alias genérico.
    assert not auditoria_fichas._i(_ficha(norden, "Drohne am Flugplatz Norden-Norddeich"))
    reunion = {"categoria": "base_militar", "nombre": "Base navale"}
    assert auditoria_fichas._i(_ficha(reunion, FRASE_TOULON))
