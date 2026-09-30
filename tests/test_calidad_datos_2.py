"""Nomenclátor más completo, país deducido del lugar del suceso y episodios sin numerar de más."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import extraccion, incidentes
from proceso.noticias import lugar_del_suceso, lugares_en, nomenclator
from proceso.ubicacion import (
    Pistas,
    localidad_pequena,
    localidades_pequenas,
    pais_del_suceso,
    ubicar,
)
from proceso.validacion_ficha import Validada
from proceso.variantes import variantes
from recogida import revision
from tests import ejemplos
from tests.test_calidad_datos import de_noche
from tests.test_extraccion import extraer_ejemplo

AHORA = datetime(2026, 10, 1, 12, tzinfo=UTC)
MODELOS = frozenset({"shahed_geran", "gerbera_senuelos", "otros"})
GENERICOS = ("aeropuert", "airport", "flughafen", "lotnisk", "lufthavn", "oro", "uost")


# --- Variantes de las instalaciones, por idioma -------------------------------------------


@pytest.mark.parametrize(
    ("titular", "instalacion"),
    [
        ("Drohne über Düsseldorfer Flughafen", "EDDL"),  # alemán: adjetivo en -er
        ("Münchner Flughafen wegen Drohnen gesperrt", "EDDM"),
        ("Dron nad lotniskiem w Rzeszowie", "EPRZ"),  # polaco: locativo
        ("Drony nad lotniskiem w Lublinie", "EPLB"),
        ("Dronas virš Palangos oro uosto", "EYPA"),  # lituano: genitivo
        ("Drons virs Liepājas lidostas", "EVLA"),  # letón: genitivo
        ("Droon Tallinna lennujaama kohal", "EETN"),  # estonio: genitivo
        ("Drooni Rovaniemen lentoasemalla", "EFRO"),  # finés: genitivo
        ("Drooni Turun lentoasemalla", "EFTU"),
        ("Drönare vid Visbys flygplats", "ESSV"),  # sueco: genitivo en -s
        ("Drone over Aalborgs lufthavn", "EKYT"),  # danés
        ("Drone ved Trondheims lufthavn", "ENVA"),  # noruego
    ],
)
def test_forma_declinada_de_la_ciudad_de_una_instalacion(titular: str, instalacion: str) -> None:
    assert lugares_en(titular, nomenclator()) == (instalacion,)


@pytest.mark.parametrize(
    ("ciudad", "pais", "forma"),
    [
        ("dusseldorf", "DE", "dusseldorfer"),
        ("bremen", "DE", "bremer"),
        ("rzeszow", "PL", "rzeszowie"),
        ("warszawa", "PL", "warszawie"),
        ("kaunas", "LT", "kauno"),
        ("vilnius", "LT", "vilniaus"),
        ("riga", "LV", "rigas"),
        ("tallinn", "EE", "tallinna"),
        ("helsinki", "FI", "helsingin"),
        ("oulu", "FI", "oulun"),
        ("goteborg", "SE", "goteborgs"),
        ("aalborg", "DK", "aalborgs"),
        ("trondheim", "NO", "trondheims"),
    ],
)
def test_reglas_de_declinacion(ciudad: str, pais: str, forma: str) -> None:
    assert forma in variantes(ciudad, pais)


def test_sin_regla_para_el_idioma_no_hay_variantes() -> None:
    assert variantes("madrid", "ES") == set()


def test_la_ciudad_compartida_va_a_la_instalacion_que_solo_lleva_su_nombre() -> None:
    # «Düsseldorf» es también del aeropuerto de Düsseldorf Mönchengladbach.
    assert lugares_en("Flughafen Düsseldorf gesperrt", nomenclator()) == ("EDDL",)


# --- Localidades pequeñas ----------------------------------------------------------------


def ficha(**valores: Any) -> Validada:
    return Validada(campos={k: {"valor": v, "fuente": 1, "frase": "", "confianza": 0.9}
                            for k, v in valores.items()})  # fmt: skip


def pistas(lugar: str = "loc:0") -> Pistas:
    return Pistas(lugar, None, (), {}, GENERICOS)


def suceso(nombre: str, nivel: str, pais: str, region: str = "") -> dict[str, str]:
    return {"nombre": nombre, "nivel": nivel, "pais": pais, "region": region}


def test_una_aldea_que_no_estaba_se_situa() -> None:
    ubicacion = ubicar(
        ficha(es_incidente=True, lugar_suceso=suceso("Hîrbovăț", "localidad", "MD")),
        pistas(), nomenclator(),
    )  # fmt: skip
    assert ubicacion.sitio is not None
    assert (ubicacion.origen, ubicacion.sitio.pais) == ("localidad_pequena", "MD")


def test_un_homonimo_se_resuelve_con_la_region_y_sin_ella_no() -> None:
    # Grindu (Tulcea) pierde su nombre en el nomenclátor grande ante Grindu (Ialomița).
    tulcea = localidad_pequena("Grindu", "RO", "Tulcea")
    assert tulcea is not None and tulcea.lat == pytest.approx(45.4)
    ubicacion = ubicar(
        ficha(es_incidente=True, lugar_suceso=suceso("Grindu", "localidad", "RO", "Tulcea")),
        pistas(), nomenclator(),
    )  # fmt: skip
    assert ubicacion.sitio is not None and ubicacion.sitio.lat == pytest.approx(45.4)


def test_las_palabras_corrientes_no_son_aldeas() -> None:
    indice, _filas = localidades_pequenas()
    assert "para" not in indice and "guerra" not in indice


@pytest.mark.parametrize(
    ("nombre", "pais", "instalacion"),
    [
        # Aeródromos con el nombre de una aldea del mismo país, que está en otro sitio.
        ("Zborov", "SK", "aeropuerto:node/1236392751"),
        ("Weremień", "PL", "aeropuerto:node/1042054967"),
    ],
)
def test_una_localidad_no_desplaza_a_la_instalacion(
    nombre: str, pais: str, instalacion: str
) -> None:
    assert localidad_pequena(nombre, pais, None) is not None
    ubicacion = ubicar(
        ficha(es_incidente=True, lugar_suceso=suceso(nombre, "instalacion", pais)),
        pistas(), nomenclator(),
    )  # fmt: skip
    assert ubicacion.sitio is not None
    assert (ubicacion.origen, ubicacion.sitio.id) == ("nomenclator", instalacion)


def test_en_un_titular_manda_la_instalacion_sobre_la_localidad() -> None:
    assert lugar_del_suceso("Drones over Kastrup airport", "", nomenclator()) == "EKCH"


# --- País deducido del lugar del suceso ----------------------------------------------------


def bruta(campo: str, valor: Any, frase: str) -> dict[str, Any]:
    return {campo: {"valor": valor, "fuente": 1, "frase": frase, "confianza": 0.9}}


def test_el_pais_se_deduce_de_una_instalacion_de_un_solo_pais() -> None:
    frase = "drone near Shannon Airport"
    deducido = pais_del_suceso(
        bruta("lugar_suceso", suceso("Shannon Airport", "instalacion", ""), frase), (),
        GENERICOS, nomenclator(),
    )  # fmt: skip
    assert deducido is not None and deducido[0] == "IE"


def test_el_pais_se_deduce_del_nombre_del_pais() -> None:
    frase = "NATO-Jets schießen Drohne über Estland ab"
    deducido = pais_del_suceso(
        bruta("lugar_suceso", suceso("Estland", "pais", ""), frase), (), GENERICOS,
        nomenclator(),
    )  # fmt: skip
    assert deducido is not None and deducido[0] == "EE"


def test_un_nombre_de_varios_paises_no_deduce_nada() -> None:
    # Hay aldeas llamadas «Neudorf» en Alemania, Austria y Chequia (o en varios de ellos).
    frase = "Drohne über Neudorf gesichtet"
    assert pais_del_suceso(
        bruta("localidad", "Neudorf", frase), (), GENERICOS, nomenclator()
    ) is None  # fmt: skip


def test_un_suceso_que_la_ficha_situa_fuera_no_toma_un_pais_europeo() -> None:
    # Hay una localidad canaria llamada El Paso; el aeropuerto de la noticia es el de Texas.
    frase = "drones force closure of El Paso International Airport"
    bruta_ = {
        **bruta("lugar_suceso", suceso("El Paso", "localidad", "US"), frase),
        **bruta("pais", "US", frase),
    }
    assert pais_del_suceso(bruta_, (), GENERICOS, nomenclator()) is None


def test_un_nombre_que_la_frase_no_cita_no_deduce_nada() -> None:
    assert pais_del_suceso(
        bruta("localidad", "Shannon", "drone sighted over the river"), (), GENERICOS,
        nomenclator(),
    ) is None  # fmt: skip


# --- Episodios ----------------------------------------------------------------------------


def test_los_episodios_deshechos_se_purgan_y_su_numero_no_se_reutiliza() -> None:
    almacen = Almacen.abrir()
    base = ejemplos.incidente_minimo()
    uno, otro = (de_noche(base, f"EODI-2025-0001{n}", 45.18 + n, 26.0) for n in (0, 1))
    for documento in (uno, otro):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    incidentes.agrupar_episodios(almacen, AHORA, MODELOS)
    (publicado,) = almacen.episodios()
    # Deja de ser episodio: uno de los dos pierde el punto.
    otro["lugar"] = {"pais": "RO", "nivel": "pais"}
    almacen.guardar_incidente(otro, AHORA, MODELOS)
    incidentes.agrupar_episodios(almacen, AHORA, MODELOS)
    assert almacen.purgar_episodios_deshechos(AHORA) == [publicado["id"]]
    assert almacen.episodios() == []
    historial = almacen.historial(publicado["id"])
    assert historial[-1]["nuevo"] == {"purgado": "2026-10-01T12:00Z"}
    # El número purgado no vuelve a usarse.
    assert almacen.siguiente_id_episodio(2025) == "EODI-EP-2025-0002"
    # Y la base sigue sin admitir borrados.
    almacen.guardar_episodio(
        {"id": "EODI-EP-2025-0002", "noche": "2025-11-04", "incidentes": ["EODI-2025-00010"]},
        AHORA,
    )
    with pytest.raises(Exception, match="nada se borra"):
        almacen.conexion.execute("DELETE FROM episodios")


def test_rehacer_dos_veces_no_numera_de_mas(monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = Almacen.abrir()
    base = ejemplos.incidente_minimo()
    for n in (0, 1):
        documento = de_noche(base, f"EODI-2025-0001{n}", 45.18 + n, 26.0)
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    monkeypatch.setattr(extraccion, "reconstruir", lambda *_a, **_k: 0)
    monkeypatch.setattr(revision, "modelos_base", lambda: MODELOS)
    revision.rehacer(almacen, AHORA, MODELOS)
    primero = [e["id"] for e in almacen.episodios()]
    for _ in range(2):
        revision.rehacer(almacen, AHORA, MODELOS)
    assert [e["id"] for e in almacen.episodios()] == primero == ["EODI-EP-2025-0001"]
    assert json.dumps(almacen.episodios()).count("deshecho") == 0


# --- Identificadores estables al reconstruir -------------------------------------------------


def test_reconstruir_conserva_el_identificador_y_retira_las_copias() -> None:
    almacen = Almacen.abrir()
    id_ = extraer_ejemplo(almacen)
    assert id_ is not None
    original = almacen.incidente(id_)
    assert original is not None
    # Una copia numerada de más por una reconstrucción anterior, sin candidato anotado.
    copia = json.loads(json.dumps(original))
    copia["id"] = "EODI-2025-00099"
    copia["control"].pop("candidato")
    almacen.guardar_incidente(copia, AHORA, MODELOS)
    antes = len(almacen.incidentes())
    for _ in range(2):
        extraccion.reconstruir(almacen, AHORA, MODELOS, rehacer=True)
    assert len(almacen.incidentes()) == antes
    rehecho, retirada = almacen.incidente(id_), almacen.incidente("EODI-2025-00099")
    assert rehecho is not None and "retirado" not in rehecho
    assert rehecho["control"]["candidato"] == almacen.candidatos()[0]["id"]
    assert retirada is not None
    assert retirada["retirado"]["motivo"].startswith(f"copia de {id_}")
