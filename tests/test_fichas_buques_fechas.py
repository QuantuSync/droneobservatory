"""Fichas mal publicadas del 20 de octubre de 2026: un buque como lugar, un buque alcanzado como
sobrevuelo, «interior» en el mar, la fecha de publicación de una nota que dice «la semana pasada»
y un nombre de instalación traducido (proceso/buques.py, proceso/fechas.py, proceso/zona.py,
proceso/control_fichas.fallos_de_ficha, proceso/nombres_lugar.traduccion_inventada)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from proceso import buques, fechas, incidentes, nombres_lugar, titulares, zona
from proceso import control_fichas as reglas
from recogida import segunda_busqueda

TITULAR = "Debris Found on Drone-Struck Chelsea 3 as Bulgaria Opens Investigation"
FRASE = (
    "Bulgarian authorities have found debris aboard the drone-struck merchant vessel Chelsea 3 "
    "and will analyze it to establish details of the attack"
)
FRASE_MAR = "the Chelsea 3, hit by drones in the Black Sea in Bulgaria's exclusive economic zone"
NOTA_NUREMBERG = (
    "Erst letzte Woche meldeten mehrere Piloten unabhängig voneinander mutmaßliche "
    "Drohnensichtungen am Flughafen Nürnberg."
)


def chelsea() -> dict[str, Any]:
    return {
        "id": "EODI-2026-00639",
        "tipo": "sobrevuelo",
        "titulo": {
            "es": "Hallan restos en el buque Chelsea 3 alcanzado por un dron",
            "en": "Debris found on drone-struck vessel Chelsea 3",
        },
        "estado": {"actual": "confirmado", "historial": []},
        "presencia_dron": "confirmada",
        "pruebas": {"dron_estatal": False, "entrada_exterior": False, "evidencia": ["restos"]},
        "consecuencias": {"cierre": {"valor": "desconocido"}},
        "lugar": {
            "pais": "BG",
            "nivel": "localidad",
            "suceso": "Chelsea 3",
            "localidad": "Chelsea 3",
        },
        "zona": {"grupo": "interior", "motivo": "sin_lugar"},
        "tiempo": {
            "inicio": {"valor": "2026-10-20T11:45Z", "precision": "aproximada"},
            "origen_inicio": {"tipo": "publicacion", "motivo": "fecha de publicación"},
        },
        "fuentes": [
            {
                "id": "f1",
                "fecha": {"valor": "2026-10-20T11:45Z", "precision": "minuto"},
                "frase_origen": FRASE,
                "titular": TITULAR,
            },
            {
                "id": "f2",
                "fecha": {"valor": "2026-10-20T12:00Z", "precision": "minuto"},
                "frase_origen": FRASE_MAR,
            },
        ],
    }


def test_el_nombre_del_buque_no_es_un_lugar() -> None:
    textos = [TITULAR, FRASE]
    assert buques.nombres_de_buques(textos) == {"chelsea 3"}
    assert buques.es_nombre_de_buque("Chelsea 3, Bulgaria", textos)
    assert not buques.es_nombre_de_buque("Varna", textos)
    assert buques.nombres_de_buques(["La policía, a cargo de la investigación"]) == set()


def test_en_el_mar_el_lugar_es_la_zona_maritima() -> None:
    documento = chelsea()
    lugar = incidentes.lugar_sin_buque(documento["lugar"], buques.textos_de(documento))
    assert lugar == {"pais": "BG", "nivel": "region",
                     "suceso": "mar Negro, zona económica exclusiva de Bulgaria"}  # fmt: skip
    # Sin zona marítima en las fuentes, el mar; con un lugar de verdad, nada cambia.
    solo = incidentes.lugar_sin_buque(documento["lugar"], [TITULAR, FRASE])
    assert solo["suceso"] == "mar" and "punto" not in solo
    varna = {"pais": "BG", "nivel": "localidad", "suceso": "Varna"}
    assert incidentes.lugar_sin_buque(varna, [TITULAR, FRASE]) is varna


def test_un_buque_alcanzado_en_el_mar_no_es_un_sobrevuelo() -> None:
    resultado = incidentes.aplicar_reglas(chelsea())
    assert resultado["tipo"] == "incursion"
    assert resultado["origen_demostrado_por"] == ["restos"]
    # Un avistamiento sobre un aeropuerto sigue siendo sobrevuelo.
    otro = chelsea()
    otro["titulo"] = {"es": "Drones sobre el aeropuerto de Varna", "en": "Drones over Varna"}
    otro["fuentes"] = [{"id": "f1", "frase_origen": "Drones were seen over Varna airport"}]
    assert incidentes.aplicar_reglas(otro)["tipo"] == "sobrevuelo"


def test_un_suceso_en_el_mar_negro_no_es_del_interior() -> None:
    documento = chelsea()
    documento.pop("zona")
    assert zona.clasificar(documento) == {"grupo": "frontera", "motivo": "costa_mar_negro"}


def test_la_semana_pasada_no_es_la_fecha_de_publicacion() -> None:
    berlin = ZoneInfo("Europe/Berlin")
    publicada = datetime(2026, 10, 19, 21, 15, tzinfo=UTC)
    assert fechas.pasado_de(NOTA_NUREMBERG, publicada, berlin) == (
        date(2026, 10, 11),
        date(2026, 10, 18),
        "letzte woche",
    )
    resolucion = fechas.resolver(publicada, "hora", [NOTA_NUREMBERG], publicada, berlin, berlin,
                                 "de")  # fmt: skip
    assert resolucion.precision == "aproximada" and resolucion.valor.date() == date(2026, 10, 18)
    assert fechas.ventana_de_motivo(resolucion.motivo) == (date(2026, 10, 11), date(2026, 10, 18))
    hace = fechas.pasado_de("il y a quelques jours, un drone", publicada, berlin)
    assert hace is not None and hace[:2] == (date(2026, 10, 9), date(2026, 10, 18))
    assert fechas.pasado_de("Am Montag meldeten Piloten Drohnen", publicada, berlin) is None


def _aeropuerto(id_: str, inicio: dict[str, str], origen: dict[str, str]) -> dict[str, Any]:
    return {
        "id": id_, "tiempo": {"inicio": inicio, "origen_inicio": origen},
        "lugar": {"pais": "DE", "punto": {"lat": 49.4987, "lon": 11.0781}, "radio_km": 2},
    }  # fmt: skip


def test_la_nota_de_la_semana_pasada_cae_en_la_ventana_del_suceso_registrado() -> None:
    registrado = _aeropuerto(
        "EODI-2026-00515", {"valor": "2026-10-13T00:00Z", "precision": "dia"},
        {"tipo": "explicita", "motivo": "«13 oktober»"},
    )  # fmt: skip
    motivo = f"«letzte woche» en una nota: {fechas.MARCA_PASADO}2026-10-11 y el 2026-10-18"
    nota = _aeropuerto(
        "EODI-2026-00632", {"valor": "2026-10-18T00:00Z", "precision": "aproximada"},
        {"tipo": "publicacion", "motivo": motivo},
    )  # fmt: skip
    assert incidentes.misma_ventana(registrado, nota)
    sin_ventana = _aeropuerto(
        "EODI-2026-00632", {"valor": "2026-10-19T21:15Z", "precision": "aproximada"},
        {"tipo": "publicacion", "motivo": "fecha de publicación"},
    )  # fmt: skip
    assert not incidentes.misma_ventana(registrado, sin_ventana)


def test_el_control_encuentra_los_cuatro_fallos() -> None:
    documento = chelsea()
    assert reglas.fallos_de_ficha(documento) == [
        reglas.BUQUE_COMO_LUGAR, reglas.ALCANZADO_COMO_SOBREVUELO, reglas.INTERIOR_EN_EL_MAR,
    ]  # fmt: skip
    nota = _aeropuerto(
        "EODI-2026-00632", {"valor": "2026-10-19T21:15Z", "precision": "aproximada"},
        {"tipo": "publicacion", "motivo": "fecha de publicación"},
    )  # fmt: skip
    fecha = {"valor": "2026-10-19T21:15Z", "precision": "minuto"}
    nota["titulo"] = {"es": "Drones en Núremberg", "en": "Drones at Nuremberg"}
    nota["tipo"] = "sobrevuelo"
    nota["fuentes"] = [{"id": "f1", "fecha": fecha, "frase_origen": NOTA_NUREMBERG}]
    assert reglas.fallos_de_ficha(nota) == [reglas.PUBLICACION_CON_PASADO]


def test_los_nombres_de_instalaciones_no_se_traducen() -> None:
    assert nombres_lugar.traduccion_inventada(
        "Eemshaven", {"es": "Puerto de Ems", "en": "Puerto de Ems"}
    )
    assert not nombres_lugar.traduccion_inventada(
        "Rotterdam", {"es": "Puerto de Rotterdam", "en": "Port of Rotterdam"}
    )
    assert not nombres_lugar.traduccion_inventada(
        "Nürnberg", {"es": "Núremberg", "en": "Nuremberg"}
    )


class _Almacen:
    def __init__(self, extraccion: dict[str, Any]) -> None:
        self._extraccion = extraccion

    def candidatos(self) -> list[dict[str, Any]]:
        return [{"id": "CAND-1", "articulos": ["https://a", "https://b"]}]

    def extracciones(self, candidato: str) -> list[dict[str, Any]]:
        return [self._extraccion]


def test_el_experto_no_repite_el_mismo_candidato_la_misma_noche() -> None:
    ahora = datetime(2026, 10, 20, 3, 17, tzinfo=UTC)
    hecha = {
        "fecha": "2026-10-20T00:17:03Z", "escalado": ["critico: cierre de aeropuerto"],
        "huella": incidentes.huella(["https://a", "https://b"]),
    }  # fmt: skip
    almacen: Any = _Almacen(hecha)
    assert segunda_busqueda.ya_con_experto(almacen, "CAND-1", ahora)
    assert not segunda_busqueda.ya_con_experto(almacen, "CAND-1", ahora + timedelta(hours=10))
    almacen = _Almacen({**hecha, "huella": "otra"})
    assert not segunda_busqueda.ya_con_experto(almacen, "CAND-1", ahora)
    almacen = _Almacen({**hecha, "escalado": []})
    assert not segunda_busqueda.ya_con_experto(almacen, "CAND-1", ahora)


def test_posible_va_delante_del_grupo_del_dron_en_ingles() -> None:
    assert titulares.ajustar("Mystery drones spotted over Eemshaven", "no_confirmada", "en") == (
        "Possible mystery drones spotted over Eemshaven"
    )
    assert titulares.ajustar("Narco-drones over a prison", "no_confirmada", "en") == (
        "Possible narco-drones over a prison"
    )
    assert titulares.ajustar("Russian drones over Poland", "no_confirmada", "en") == (
        "Possible Russian drones over Poland"
    )
    assert titulares.ajustar("Two drones near Schiphol", "no_confirmada", "en") == (
        "Two possible drones near Schiphol"
    )


def test_posible_no_se_mete_tras_un_verbo_ni_una_preposicion() -> None:
    casos = {
        "Belgian airspace closed following drone sightings": (
            "Belgian airspace closed following possible drone sightings"
        ),
        "Paphos Airport evacuated due to drone threat": (
            "Paphos Airport evacuated due to possible drone threat"
        ),
        "Pilot reports drone collision near JFK": "Pilot reports possible drone collision near JFK",
        "Nine drone incidents at Leipzig/Halle": "Nine possible drone incidents at Leipzig/Halle",
        "Explosive drone found on the runway": "Possible explosive drone found on the runway",
    }
    for antes, despues in casos.items():
        assert titulares.ajustar(antes, "no_confirmada", "en") == despues


def test_buques_en_plural_y_ataque() -> None:
    textos = ["Drones strike two ships off the Bulgarian coast in the Black Sea"]
    assert buques.en_el_mar(textos)
    assert buques.alcanzado(textos)
