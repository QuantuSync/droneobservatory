"""Barrera de titulares sin espera a mano (recogida/barrera.py, proceso/cita_titular.py): el
titular del propio artículo fuente respalda el titular y queda como cita; lo retenido 6 horas se
publica a nivel de país o se descarta como no verificable; el extractor elige una cita con el
lugar; y la vigilancia avisa solo cuando algo va mal."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from exportacion import geojson
from proceso import cita_titular, incidentes
from proceso.validacion_ficha import Validada
from recogida import barrera, vigilancia
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_vigilancia import Sistema, preparar

ALTA = datetime(2026, 10, 9, 19, 17, tzinfo=UTC)
ID = "EODI-2026-00507"
NRK = "https://nrk.no/nordland/tok-fem-ulovlige-droner-ved-leknes-lufthavn-1.18050915"
OTRO = "https://nrk.no/nordland/annen-sak-1.1"
SIN_LUGAR = "Rundt klokken 14.00 fikk politiet melding om ulovlig droneflyging"
TITULAR = "Tok fem ulovlige droner ved Leknes lufthavn – avslørte ulovlige sjåfører"


def _leknes(frase: str = SIN_LUGAR, region: bool = True) -> dict[str, Any]:
    """Como EODI-2026-00507: el titular nombra Leknes y la cita no."""
    documento = ejemplos.incidente_minimo()
    documento["id"] = ID
    documento["titulo"] = {
        "es": "Cinco drones ilegales capturados cerca del aeropuerto de Leknes",
        "en": "Five illegal drones seized near Leknes airport",
    }
    documento["lugar"] = {
        "pais": "NO", "nivel": "instalacion", "suceso": "Leknes lufthavn",
        "punto": {"lat": 68.15287, "lon": 13.60939}, "radio_km": 5.0,
        "geocodificacion": "nomenclator",
    }  # fmt: skip
    if region:
        documento["lugar"]["region"] = "Nordland"
    documento["objetivo"] = {"categoria": "aeropuerto", "nombre": "Leknes lufthavn"}
    documento["fuentes"][0].update(enlace=NRK, medio="nrk.no", idioma="no", fiabilidad="C",
                                   frase_origen=frase)  # fmt: skip
    documento["tiempo"] = {"inicio": ejemplos.instante("2026-10-09T12:00Z", "hora")}
    documento["estado"]["historial"][0]["fecha"] = ejemplos.instante("2026-10-09T18:45Z")
    alta = ejemplos.instante("2026-10-09T19:17Z")
    documento["control"] = {"alta": alta, "ultima_actualizacion": alta}
    return documento


def _articulo(url: str, titular: str) -> dict[str, Any]:
    return {"url": url, "medio": "nrk.no", "fecha": "2026-10-09T18:45:00Z", "idioma": "no",
            "pais": "NO", "titular": titular, "titular_normalizado": titular.lower()}  # fmt: skip


def _base(documento: dict[str, Any], *articulos: tuple[str, str]) -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(documento, ALTA, VOCABULARIO_MODELOS)
    for url, titular in articulos:
        almacen.guardar_articulo(_articulo(url, titular))
    return almacen


def _publicable(almacen: Almacen) -> bool:
    documento = almacen.incidente(ID)
    assert documento is not None
    return bool(geojson.publicables([documento], ALTA + timedelta(days=1), VOCABULARIO_MODELOS))


# --- La barrera ampliada ----------------------------------------------------------------------
def test_cita_sin_lugar_y_titular_del_articulo_que_lo_nombra_publica() -> None:
    almacen = _base(_leknes(), (NRK, TITULAR + " ᐉ Nyheter fra NRK"))
    assert not _publicable(almacen)
    hecho = barrera.revisar(almacen, ALTA, VOCABULARIO_MODELOS)
    assert hecho.con_titular == [ID] and hecho.retenidos == {}
    despues = almacen.incidente(ID)
    assert despues is not None and _publicable(almacen)
    # El titular queda como cita del incidente, literal y sin el nombre del medio.
    nueva = despues["fuentes"][-1]
    assert nueva["id"].startswith(barrera.PREFIJO_TITULAR) and nueva["enlace"] == NRK
    assert nueva["frase_origen"] == TITULAR and nueva["medio"] == "nrk.no"
    assert any(h["nuevo"].get("motivo") == barrera.MOTIVO_TITULAR for h in almacen.historial(ID))
    # La recogida siguiente no cambia nada.
    assert (
        barrera.revisar(almacen, ALTA + timedelta(hours=1), VOCABULARIO_MODELOS).con_titular == []
    )
    assert almacen.incidente(ID) == despues


def test_ningun_texto_de_la_fuente_nombra_el_lugar_retiene() -> None:
    almacen = _base(_leknes(), (NRK, "Tok fem ulovlige droner – avslørte ulovlige sjåfører"))
    hecho = barrera.revisar(almacen, ALTA, VOCABULARIO_MODELOS)
    assert hecho.retenidos == {ID: "2026-10-09T19:17:00Z"} and not hecho.con_titular
    assert not _publicable(almacen)
    # Cinco horas después sigue retenido, con la hora de la primera vez.
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=5), VOCABULARIO_MODELOS)
    assert hecho.retenidos == {ID: "2026-10-09T19:17:00Z"}


def test_el_titular_de_otro_articulo_no_cuenta() -> None:
    # El artículo que nombra Leknes no es fuente del incidente.
    almacen = _base(_leknes(), (NRK, "Tok fem ulovlige droner"), (OTRO, TITULAR))
    hecho = barrera.revisar(almacen, ALTA, VOCABULARIO_MODELOS)
    assert hecho.retenidos and not hecho.con_titular and not _publicable(almacen)
    publico = geojson.vista_publica(_leknes())
    assert publico is not None
    assert cita_titular.titular_que_respalda(publico, {OTRO: TITULAR}) is None
    assert cita_titular.titular_que_respalda(publico, {NRK: TITULAR}) == (NRK, TITULAR)


def test_una_region_cuenta_con_la_palabra_entera() -> None:
    # «Ruse» (provincia de Bulgaria) no casa con «руски»; «Troms» sí casa con «Troms».
    ruso = "дронът може да е както руски, така е украински"
    assert not cita_titular.nombra_region([ruso], "BG")
    assert cita_titular.nombra_region(["Droner tatt i Troms i dag"], "NO")
    assert not cita_titular.nombra_region(["Droner tatt i Tromsø"], "NO")


def test_titular_limpio() -> None:
    assert cita_titular.titular_limpio("A  b ᐉ Новини от Fakti.bg - България") == "A b"
    assert cita_titular.titular_limpio("Drones over Leknes | NRK") == "Drones over Leknes"
    assert (
        cita_titular.titular_limpio("Drones over Leknes - NRK Nordland", "nrk.no")
        == "Drones over Leknes"
    )
    # Tras un guion, lo que no nombra al medio es parte del titular.
    assert cita_titular.titular_limpio(TITULAR, "nrk.no") == TITULAR


# --- Resolución a las 6 horas -----------------------------------------------------------------
def test_a_solo_respalda_el_pais_se_publica_a_nivel_de_pais() -> None:
    # Sin región en el lugar: «Troms» sitúa en Noruega, no en el aeropuerto de Leknes.
    almacen = _base(_leknes(region=False), (NRK, "Fem ulovlige droner tatt i Troms"))
    barrera.revisar(almacen, ALTA, VOCABULARIO_MODELOS)
    assert not _publicable(almacen)
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=6), VOCABULARIO_MODELOS)
    assert hecho.a_pais == [ID] and hecho.retenidos == {} and not hecho.sin_guardar
    assert hecho.resoluciones == [
        {"id": ID, "fecha": "2026-10-10T01:17:00Z", "resultado": barrera.PAIS}
    ]
    despues = almacen.incidente(ID)
    assert despues is not None and _publicable(almacen)
    # Sin punto ni lugar concreto: la web lo dibuja con el marcador de lugar aproximado.
    assert despues["lugar"] == {"pais": "NO", "nivel": "pais"}
    assert despues["objetivo"] == {"categoria": "aeropuerto"}
    assert "Leknes" not in json.dumps(despues["titulo"]) and "Noruega" in despues["titulo"]["es"]
    assert "Norway" in despues["titulo"]["en"]
    assert despues["fuentes"][-1]["frase_origen"] == "Fem ulovlige droner tatt i Troms"
    sin_ubicacion = geojson.exportar_sin_ubicacion(
        [despues], ALTA + timedelta(days=1), VOCABULARIO_MODELOS
    )
    assert [i["id"] for i in sin_ubicacion["incidentes"]] == [ID]
    # Idempotente: la recogida siguiente no cambia nada ni cuenta otra resolución.
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=7), VOCABULARIO_MODELOS)
    assert hecho.a_pais == [] and len(hecho.resoluciones) == 1
    assert almacen.incidente(ID) == despues


def test_a_vuelve_a_aplicarse_si_una_extraccion_nueva_lo_rehace() -> None:
    almacen = _base(_leknes(region=False), (NRK, "Fem ulovlige droner tatt i Troms"))
    barrera.revisar(almacen, ALTA, VOCABULARIO_MODELOS)
    barrera.revisar(almacen, ALTA + timedelta(hours=6), VOCABULARIO_MODELOS)
    almacen.guardar_incidente(_leknes(region=False), ALTA + timedelta(hours=8), VOCABULARIO_MODELOS)
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=8), VOCABULARIO_MODELOS)
    assert hecho.a_pais == [ID] and len(hecho.resoluciones) == 1 and _publicable(almacen)


def test_b_ningun_texto_respalda_el_pais_se_descarta_con_el_motivo() -> None:
    almacen = _base(_leknes(), (NRK, "Tok fem ulovlige droner"))
    barrera.revisar(almacen, ALTA, VOCABULARIO_MODELOS)
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=6, minutes=1), VOCABULARIO_MODELOS)
    assert hecho.descartados == [ID] and hecho.retenidos == {}
    despues = almacen.incidente(ID)
    assert despues is not None and not incidentes.activo(despues)
    assert despues["retirado"]["motivo"] == barrera.MOTIVO_DESCARTE
    assert despues["retirado"]["motivo_en"] == barrera.MOTIVO_DESCARTE_EN
    # El registro interno de descartes: el cursor de la barrera, con el motivo.
    cursor = almacen.cursor(barrera.CURSOR)
    assert cursor is not None
    assert cursor["resueltos"][ID]["resultado"] == barrera.DESCARTADO
    assert cursor["resueltos"][ID]["motivo"] == barrera.MOTIVO_DESCARTE
    assert cursor["resueltos"][ID]["desde"] == "2026-10-09T19:17:00Z"
    # Ya descartado, la recogida siguiente no lo toca.
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=7), VOCABULARIO_MODELOS)
    assert hecho.descartados == [] and almacen.incidente(ID) == despues


def test_lo_que_la_cita_ya_respalda_no_se_toca() -> None:
    almacen = _base(_leknes(frase="Fem droner ved Leknes lufthavn"), (NRK, TITULAR))
    antes = almacen.incidente(ID)
    hecho = barrera.revisar(almacen, ALTA + timedelta(hours=9), VOCABULARIO_MODELOS)
    assert hecho.texto().startswith("con titular 0, retenidos 0")
    assert almacen.incidente(ID) == antes


def test_titulo_de_pais_segun_el_tipo() -> None:
    documento = _leknes()
    assert barrera.titulo_de_pais(documento)["es"] == "Dron avistado en Noruega"
    documento["drones"] = {"numero": {"min": 5, "max": 5}}
    assert barrera.titulo_de_pais(documento)["es"] == "Drones avistados en Noruega"
    documento["tipo"] = "interrupcion_aeroportuaria"
    assert barrera.titulo_de_pais(documento) == {
        "es": "Drones interrumpen la actividad de un aeropuerto de Noruega",
        "en": "Drones disrupt operations at an airport in Norway",
    }
    documento["tipo"] = "incursion"
    documento.pop("drones")
    assert barrera.titulo_de_pais(documento)["en"] == "Drone in Norway airspace"


# --- La cita que elige el extractor ------------------------------------------------------------
def _ficha(frase: str, otra: str = "") -> Validada:
    campos: dict[str, dict[str, Any]] = {
        "es_incidente": {"valor": True, "fuente": 1, "frase": frase, "confianza": 0.95},
        "pais": {"valor": "MD", "fuente": 1, "frase": frase, "confianza": 0.95},
        "lugar_suceso": {
            "valor": {"nombre": "Anenii Noi", "nivel": "localidad", "pais": "MD",
                      "region": "Anenii Noi"},
            "fuente": 1, "frase": otra or frase, "confianza": 0.85,
        },
    }  # fmt: skip
    return Validada(campos=campos)


MOLDPRES = "https://moldpres.md/rom/o-drona-a-explodat-in-raionul-anenii-noi"
SIN_MOLDAVIA = "Incidentul s-a produs noaptea trecută, în contextul atacurilor masive."
TITULAR_MD = (
    "O dronă a survolat neautorizat spațiul aerian național și a explodat în raionul Anenii Noi"
)


def _articulo_md(titular: str = TITULAR_MD) -> dict[str, Any]:
    return {"url": MOLDPRES, "medio": "moldpres.md", "fecha": "2026-10-11T09:45:00+00:00",
            "idioma": "ro", "titular": titular, "replicas": 0}  # fmt: skip


def test_el_extractor_usa_el_titular_si_la_cita_no_nombra_el_lugar() -> None:
    fuentes = incidentes.fuentes_incidente([_articulo_md()], [MOLDPRES], _ficha(SIN_MOLDAVIA))
    assert fuentes[0]["frase_origen"] == TITULAR_MD


def test_el_extractor_prefiere_la_frase_que_nombra_el_lugar() -> None:
    con_lugar = "O dronă a căzut lângă satul Geamăna, raionul Anenii Noi."
    fuentes = incidentes.fuentes_incidente(
        [_articulo_md()], [MOLDPRES], _ficha(SIN_MOLDAVIA, con_lugar)
    )
    assert fuentes[0]["frase_origen"] == con_lugar


def test_sin_lugar_en_ningun_texto_queda_la_primera_frase() -> None:
    fuentes = incidentes.fuentes_incidente(
        [_articulo_md("Explozie noaptea trecută")], [MOLDPRES], _ficha(SIN_MOLDAVIA)
    )
    assert fuentes[0]["frase_origen"] == SIN_MOLDAVIA
    assert incidentes.cita_con_lugar([], "Titular", ["Moldova"]) == "Titular"


# --- Vigilancia ---------------------------------------------------------------------------------
AHORA_V = datetime(2026, 10, 11, 20, 50, tzinfo=UTC)


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _estado(**cambios: Any) -> dict[str, Any]:
    estado: dict[str, Any] = {
        "generado": _iso(AHORA_V - timedelta(minutes=30)),
        "mapa_cambiado": _iso(AHORA_V - timedelta(hours=2)),
        "ultima_alta_con_punto": "2026-10-11T10:17Z",
        "retenidos": {"EODI-2026-00510": _iso(AHORA_V - timedelta(hours=2))},
        "resoluciones": [
            {"id": f"EODI-2026-0049{i}", "fecha": _iso(AHORA_V - timedelta(hours=i)),
             "resultado": "pais"} for i in range(3)
        ],
    }  # fmt: skip
    estado.update(cambios)
    return estado


def test_vigilancia_en_el_estado_normal_no_avisa() -> None:
    assert vigilancia.problemas_de_la_barrera(_estado(), AHORA_V) == []
    assert vigilancia.problemas_de_la_barrera({}, AHORA_V) == []


def test_vigilancia_mas_de_3_resoluciones_en_un_dia() -> None:
    resoluciones = [
        {"id": f"EODI-2026-0049{i}", "fecha": _iso(AHORA_V - timedelta(hours=i * 5)),
         "resultado": "pais" if i % 2 else "descartado"} for i in range(5)
    ]  # fmt: skip
    problemas = vigilancia.problemas_de_la_barrera(_estado(resoluciones=resoluciones), AHORA_V)
    assert [p["id"] for p in problemas] == ["barrera_resoluciones"]
    assert "5 incidentes en 24 horas (2 a nivel de país, 3 descartados" in problemas[0]["frase"]
    assert "EODI" not in json.dumps(problemas)


def test_vigilancia_retenido_que_la_resolucion_no_despacha() -> None:
    retenidos = {"EODI-2026-00510": _iso(AHORA_V - timedelta(hours=9))}
    problemas = vigilancia.problemas_de_la_barrera(_estado(retenidos=retenidos), AHORA_V)
    assert [p["id"] for p in problemas] == ["barrera_atascada"]
    assert "EODI" not in json.dumps(problemas)


def test_vigilancia_mapa_parado_con_incidentes_nuevos() -> None:
    parado = _estado(mapa_cambiado=_iso(AHORA_V - timedelta(hours=25)))
    assert [p["id"] for p in vigilancia.problemas_de_la_barrera(parado, AHORA_V)] == ["mapa_parado"]
    # Sin incidentes nuevos desde el último cambio, que el mapa no cambie no es un problema.
    quieto = _estado(
        mapa_cambiado=_iso(AHORA_V - timedelta(hours=25)), ultima_alta_con_punto="2026-10-10T08:17Z"
    )
    assert vigilancia.problemas_de_la_barrera(quieto, AHORA_V) == []


def test_vigilancia_lo_pone_en_salud_json_como_problema(tmp_path: Path) -> None:
    """El problema llega a salud.json: el workflow vigia-recogida abre su incidencia."""
    from tests import test_vigilancia as tv

    hace = tv.AHORA - timedelta(seconds=20)
    secretos, datos = preparar(tmp_path, hace, tv.AHORA - timedelta(minutes=47))
    estado = _estado(mapa_cambiado=_iso(tv.AHORA - timedelta(hours=30)),
                     ultima_alta_con_punto=_iso(tv.AHORA - timedelta(hours=3)),
                     retenidos={"EODI-2026-00510": _iso(tv.AHORA - timedelta(hours=10))},
                     resoluciones=[])  # fmt: skip
    (secretos / vigilancia.BARRERA).write_text(json.dumps(estado), encoding="utf-8")
    sistema = Sistema(0, tv.AHORA - timedelta(minutes=17), [])
    salud, detalle = vigilancia.componer(
        tv.AHORA, secretos, datos, tmp_path, sistema, lambda: tv.AHORA - timedelta(minutes=18)
    )
    assert [p["id"] for p in salud["problemas"]] == ["barrera_atascada", "mapa_parado"]
    assert "EODI-2026-00510" not in json.dumps(salud)
    assert any("EODI-2026-00510" in linea for linea in detalle)


def test_estado_de_la_barrera_para_la_vigilancia(tmp_path: Path) -> None:
    ruta = tmp_path / "barrera.json"
    publicacion = tmp_path / "publicacion"
    publicacion.mkdir()
    revision = barrera.Revision(retenidos={ID: "2026-10-09T19:17:00Z"},
                                ultima_alta_con_punto="2026-10-09T19:17Z")  # fmt: skip
    barrera.escribir_estado(ruta, revision, [publicacion / "incidentes.geojson"], publicacion, ALTA)
    estado = json.loads(ruta.read_text(encoding="utf-8"))
    assert estado["mapa_cambiado"] == "2026-10-09T19:17:00Z" and estado["retenidos"] == {
        ID: "2026-10-09T19:17:00Z"
    }
    # Sin cambio en el mapa se conserva la hora anterior; con la revisión fallida, lo anterior.
    barrera.escribir_estado(ruta, None, [], publicacion, ALTA + timedelta(hours=1))
    estado = json.loads(ruta.read_text(encoding="utf-8"))
    assert estado["mapa_cambiado"] == "2026-10-09T19:17:00Z" and estado["revision_fallida"]
    assert estado["retenidos"] == {ID: "2026-10-09T19:17:00Z"}


def test_todos_los_paises_tienen_nombre_para_el_titular() -> None:
    cajas = json.loads(
        (Path(barrera.AVISOS).parent / "paises_europa.json").read_text(encoding="utf-8")
    )["cajas"]
    faltan = sorted(set(cajas) - set(barrera.nombres_de_paises()))
    assert faltan == [] or set(faltan) <= {"UA", "RU", "BY"}, faltan


def test_copia_del_documento_no_cambia() -> None:
    documento = _leknes()
    antes = copy.deepcopy(documento)
    barrera.a_nivel_de_pais(documento)
    assert documento == antes
