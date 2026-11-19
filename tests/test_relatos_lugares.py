"""Relatos de sucesos anteriores, lugares de otro país en el titular y fichas retenidas (19 de
noviembre de 2026), con fichas reales de la base (tests/fixtures/relatos_lugares_2026-11-19.json).

- EODI-2026-00888 (b92.net del 18/11, «tokom noći»), EODI-2026-00818 (13/11, «last week») y
  EODI-2026-00815 (12/11, «in der Nacht») volvían a contar la noche del 10 al 11 de noviembre en
  Lituania (EODI-2026-00792) y salían como sucesos nuevos con la fecha de su publicación.
- EODI-2026-00862 (Byala, Bulgaria) salía «frente a Bielsko-Biała»: la web cambiaba la forma
  ajena «Byala» de la ciudad polaca sin mirar el país de la ficha.
- EODI-2026-00844 (RO-Alert del domingo 15/11 «la ora 15.02.») tomó el 15 de febrero y quedó
  retenida 87 horas.
"""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from proceso import correccion, fechas, nombres_lugar, suceso
from proceso.noticias import filtro

DATOS = json.loads(
    (Path(__file__).parent / "fixtures" / "relatos_lugares_2026-11-19.json").read_text(
        encoding="utf-8"
    )
)
DESTINO = "EODI-2026-00792"


def _relatos() -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in DATOS["relato"]["relatos"]}


def _activas(sin: str) -> list[dict[str, Any]]:
    """Las fichas activas de Lituania en esos días, sin `sin` (la que se compara)."""
    otras = [DATOS["relato"]["destino"], *DATOS["lituania"], *_relatos().values()]
    return [copy.deepcopy(o) for o in otras if o["id"] != sin]


@pytest.mark.parametrize("id_", ["EODI-2026-00888", "EODI-2026-00818", "EODI-2026-00815"])
def test_el_relato_se_une_a_la_ficha_del_suceso(id_: str) -> None:
    ficha = _relatos()[id_]
    assert suceso.fecha_de_su_publicacion(ficha)
    mismas = suceso.del_mismo_suceso(ficha, _activas(id_))
    assert [o["id"] for o, _ in mismas] == [DESTINO]
    assert mismas[0][1].regla in {suceso.REGLA_RELATO, *(v.regla for _, v in mismas)}


def test_00888_cuenta_birzai_y_el_derribo_repetido() -> None:
    ficha = _relatos()["EODI-2026-00888"]
    hechos = suceso.hechos(ficha)
    assert "derribo:dos_veces" in hechos
    assert any(clave.startswith("lugar:birz") for clave in hechos)
    [(otra, dicho)] = suceso.relato_de(ficha, _activas(ficha["id"]))
    assert otra["id"] == DESTINO
    assert dicho.regla == suceso.REGLA_RELATO and dicho.relacion == suceso.MISMO


def test_al_unirse_queda_la_fecha_de_la_ficha_anterior() -> None:
    destino = DATOS["relato"]["destino"]
    ficha = _relatos()["EODI-2026-00888"]
    conserva, une = suceso.queda(destino, ficha)
    assert (conserva["id"], une["id"]) == (DESTINO, ficha["id"])
    assert destino["tiempo"]["inicio"]["valor"].startswith("2026-11-10")


def test_un_hecho_que_cuentan_dos_fichas_no_distingue() -> None:
    """Si otra ficha de su país en esos días cuenta el mismo hecho, no se une a ninguna."""
    ficha = _relatos()["EODI-2026-00818"]
    gemela = copy.deepcopy(DATOS["relato"]["destino"])
    gemela["id"] = "EODI-2026-09999"
    gemela["tiempo"]["inicio"]["valor"] = "2026-11-05T00:00Z"
    assert suceso.relato_de(ficha, [*_activas(ficha["id"]), gemela]) == []


def test_una_fecha_con_su_dia_no_es_de_publicacion() -> None:
    ficha = copy.deepcopy(_relatos()["EODI-2026-00888"])
    ficha["tiempo"]["origen_inicio"] = {
        "tipo": "explicita", "motivo": "«10 noiembrie»", "fuente_id": ficha["fuentes"][0]["id"]
    }  # fmt: skip
    assert not suceso.fecha_de_su_publicacion(ficha)
    assert suceso.relato_de(ficha, _activas(ficha["id"])) == []


def test_una_instalacion_no_distingue_un_suceso() -> None:
    """El cierre de pistas de Múnich del 6 de septiembre (00303) y los drones de aficionados de
    octubre (00261) son dos sucesos aunque los dos sean en el aeropuerto."""
    nueva, anterior = DATOS["munich"]
    assert suceso.relato_de(nueva, [anterior]) == []


@pytest.mark.parametrize(
    ("motivo", "sin_dia"),
    [
        ("«tokom noći» en una nota publicada el 2026-11-18 09:00", True),
        ("«ayer» en una nota", True),
        ("«in der Nacht zum Montag» en una nota", False),
        ("«sonntag» en una nota", False),
        ("«10 noiembrie»", False),
    ],
)
def test_relativa_sin_dia(motivo: str, sin_dia: bool) -> None:
    assert fechas.relativa_sin_dia(motivo) is sin_dia


# --- B: lugares de otro país en el titular -----------------------------------------------------


def test_byala_no_pasa_a_bielsko_biala_en_una_ficha_de_bulgaria() -> None:
    ficha = DATOS["byala"]
    titulo = nombres_lugar.titulo_corregido(ficha)
    assert "Byala" in titulo["es"] and "Byala" in titulo["en"]
    assert "Bielsko" not in titulo["es"] + titulo["en"]


def test_la_forma_ajena_si_cambia_en_su_pais() -> None:
    assert "Bielsko-Biała" in nombres_lugar.corregir_texto("dron nad Byala", {}, "es", "PL")


def test_la_coherencia_caza_un_lugar_de_otro_pais_sin_frase() -> None:
    ficha = copy.deepcopy(DATOS["byala"])
    assert correccion.localidad_de_otro_pais(ficha) is None
    ficha["titulo"] = {
        "es": "Hunde el buque GAS HUSKY frente a Bielsko-Biała, posible ataque con drones",
        "en": "Tanker GAS HUSKY sinks off Bielsko-Biała, possible drone strike",
    }
    assert correccion.localidad_de_otro_pais(ficha) == "Bielsko-Biala"
    assert correccion.titulo_ajeno(ficha) == "Bielsko-Biala"
    letras = {h.comprobacion for h in correccion.hallazgos(ficha)}
    assert correccion.TITULAR in letras


# --- C: fechas que son horas y fichas retenidas ------------------------------------------------


@pytest.mark.parametrize(
    ("frase", "fecha"),
    [
        ("O nouă alertă aeriană a fost declanșată în România, duminică, la ora 15.02.", None),
        ("um 15.02 Uhr startete die Drohne", None),
        ("kl. 21.15 i går", None),
        ("Am 15.02. gab es einen Vorfall", date(2026, 2, 15)),
        ("w dniu 15.02. godz. 3", date(2026, 2, 15)),
        ("El 15.02.2026 hubo un dron", date(2026, 2, 15)),
    ],
)
def test_una_hora_no_es_una_fecha(frase: str, fecha: date | None) -> None:
    halladas = fechas._explicitas(frase, list(fechas.lexicos().values()), date(2026, 11, 15))
    assert [f for f, _ in halladas] == ([] if fecha is None else [fecha])


def test_00844_el_dia_de_su_noticia_no_queda_lejos() -> None:
    """Con la fecha mala de febrero, el 15 de noviembre (el de la nota) no es «lejano»: el filtro
    de entrada lo aplica en vez de retenerla; un día lejano de la noticia sigue reteniéndose."""
    ficha = DATOS["ro_alert_15"]
    assert ficha["tiempo"]["inicio"]["valor"].startswith("2026-02-15")
    assert not suceso.otro_dia_lejano(ficha, "2026-11-15")
    assert suceso.otro_dia_lejano(ficha, "2026-11-01")


def test_las_tintas_aereas_rumanas_son_de_dron() -> None:
    dron = filtro().dron
    assert dron.search("RO Alert la TULCEA: 11 ținte aeriene detectate în apropierea frontierei")
    assert dron.search("MApN: Alertă RO-ALERT în Tulcea, după detectarea unor ţinte aeriene")
    assert dron.search("Țintă aeriană detectată la sud-est de Insula Șerpilor")
    assert not dron.search("Ținta a fost atinsă")
    # Dejan entrar la noticia, pero no nombran un dron: la presencia sigue «no confirmada»
    # (EODI-2026-00650 perdía el «posible» en el ensayo del 19 de noviembre de 2026).
    from proceso import declaraciones, pasajes

    frase = (
        "Sistemul de supraveghere radar al Ministerului Apărării Naţionale a detectat un grup de "
        "ţinte aeriene la nord-est de localitatea Vâlcove, în spaţiul aerian al Ucrainei."
    )
    assert not declaraciones.atribuye_dron(frase)
    assert not declaraciones.habla_de_drones(frase)
    # El extractor sí recibe ese pasaje: es lo que cuenta la alerta.
    assert pasajes.habla_de_drones(frase)
    assert declaraciones.habla_de_drones("a fost detectată o dronă")


def test_la_alerta_del_16_al_17_entra_como_articulo_dirigido() -> None:
    from proceso.noticias import nomenclator
    from recogida import articulos_dirigidos

    [articulo] = [a for a in articulos_dirigidos.cargar() if "11-tinte-aeriene" in a["url"]]
    assert all(articulo.get(c) for c in articulos_dirigidos.CAMPOS)
    assert articulo["lugar"] in nomenclator().lugares
    publicada = datetime.fromisoformat(articulo["fecha"].replace("Z", "+00:00"))
    assert publicada >= datetime(2026, 11, 16, 22, 7, tzinfo=UTC)  # tras el fin de la alerta


def test_la_nota_sin_dron_no_se_enlaza_solo_por_el_dia() -> None:
    """La nota del MApN del 17/11 (11 objetivos aéreos junto a Vâlcove e Ismail) iba, en el ensayo,
    a la ficha rumana sin punto del día anterior (EODI-2026-00849, drones a la deriva): una nota que
    no nombra un dron solo se enlaza si nombra la localidad de la ficha o encaja con su sitio."""
    from almacen.base import Almacen
    from recogida import oficiales
    from tests.test_extraccion import extraer_ejemplo
    from tests.test_oficiales import FUENTE, NOTA_PAIS, _sin_punto

    almacen = Almacen.abrir()
    id_ = _sin_punto(almacen, str(extraer_ejemplo(almacen)))
    (nota, _) = oficiales.leer_rss(NOTA_PAIS, FUENTE)
    radar = oficiales.Nota(
        nota.fuente, nota.id, "Informație de presă", nota.enlace, nota.fecha,
        "Sistemul de supraveghere radar a detectat 11 ținte aeriene în spațiul aerian al Ucrainei.",
    )  # fmt: skip
    assert id_ in [i["id"] for i in oficiales.posibles(almacen, nota)]
    assert oficiales.posibles(almacen, radar) == []
    assert oficiales.suceso(radar)
