"""La coherencia de la puerta corrige en vez de retener (recogida/correccion.py, desde el 14 de
noviembre de 2026): el lugar que no nombra ninguna frase baja a lo que sí nombran, el número de
drones sin fuente queda «sin dato», el día lo da una frase, la ficha de dos jornadas se separa
con una revisión automática y el titular que nombra otro país se rehace. Con el experto falso de
tests/test_entrada.py: aquí no se llama a ningún modelo."""

import copy
import json
from datetime import timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import correccion as comprobaciones
from proceso import suceso
from recogida import control_fichas, correccion, revisados
from recogida.plazo import Plazo
from tests.test_entrada import AHORA, Cliente, _base, _contexto, _ficha

KRETINGA = (55.89, 21.24)


@pytest.fixture(autouse=True)
def _sin_descargas_ni_automaticas(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})
    suceso.fijar_automaticas(None)
    yield
    suceso.fijar_automaticas(None)


def _lituana(id_: str = "EODI-2026-09901", frase: str = "", **lugar: Any) -> dict[str, Any]:
    ficha = _ficha(id_, "LT", "2026-10-26T00:00Z", punto=KRETINGA, nivel="localidad",
                   frase=frase or "Drones were seen over the Lithuanian coast")  # fmt: skip
    ficha["lugar"] = {**ficha["lugar"], "suceso": "Kretinga", "localidad": "Kretinga", **lugar}
    ficha["titulo"] = {"es": "Dron avistado en Kretinga", "en": "Drone sighted in Kretinga"}
    return ficha


def _respuesta(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "lugar": {"sostenido": False, "nivel": "pais", "region": "", "frase": "", "fuente": 1},
        "drones": {"valor": "", "frase": "", "fuente": 1},
        "dia": {"valor": "", "frase": "", "fuente": 1},
        "dias": [],
    }
    return {**base, **cambios}


def _corregir(almacen: Almacen, cliente: Cliente | None) -> tuple[correccion.Resumen, Any]:
    ctx = _contexto(almacen, cliente)
    return correccion.corregir(ctx, Plazo(60)), ctx


# --- Las comprobaciones -----------------------------------------------------------------------


def test_un_lugar_que_nombra_una_frase_no_es_un_hallazgo() -> None:
    ficha = _lituana(frase="A drone was seen over Kretinga on Monday night")
    assert comprobaciones.hallazgos(ficha) == []
    sin_frase = _lituana()
    assert [h.comprobacion for h in comprobaciones.hallazgos(sin_frase)] == [comprobaciones.LUGAR]


def test_un_titular_con_otro_pais_y_el_suyo_no() -> None:
    ficha = _lituana(frase="A drone was seen over Kretinga")
    ficha["titulo"] = {"es": "Dron de Polonia avistado en Kretinga", "en": "x"}
    otro = comprobaciones.titulo_de_otro_pais(ficha)
    assert otro == "PL"
    ficha["titulo"] = {"es": "Dron avistado en Kretinga (Lituania) desde Polonia", "en": "x"}
    assert comprobaciones.titulo_de_otro_pais(ficha) is None
    # «España» no es «espacio».
    ficha["titulo"] = {"es": "Dron en el espacio aéreo de Lituania", "en": "x"}
    assert comprobaciones.titulo_de_otro_pais(ficha) is None


# --- La corrección con la relectura -----------------------------------------------------------


def test_sin_frase_del_sitio_baja_a_la_region_que_nombra_una_frase() -> None:
    frase = "Drones were seen over the Lithuanian coast"
    almacen = _base(_lituana(frase=frase))
    cliente = Cliente([_respuesta(lugar={"sostenido": False, "nivel": "region",
                                         "region": "Lithuanian coast", "frase": frase,
                                         "fuente": 1})])  # fmt: skip
    resumen, ctx = _corregir(almacen, cliente)
    assert resumen.corregidas == ["EODI-2026-09901"] and resumen.releidas == 1
    ficha = almacen.incidente("EODI-2026-09901")
    assert ficha is not None
    assert ficha["lugar"]["nivel"] == "region" and ficha["lugar"]["region"] == "Lithuanian coast"
    assert "punto" not in ficha["lugar"] and "Kretinga" not in str(ficha["titulo"])
    decision = ctx.nuevas[correccion.CLAVE + "EODI-2026-09901"]
    assert decision["relectura"] and decision["cambios"]
    # Lo que ya se decidió con la misma ficha no se relee.
    resumen, _ = _corregir(almacen, Cliente([]))
    assert resumen.releidas == 0


def test_lo_que_el_cerrojo_protege_no_se_corrige_a_medias(monkeypatch: pytest.MonkeyPatch) -> None:
    # EODI-2026-00747 en el ensayo del 14/11: el cerrojo retuvo el lugar con su cita y el
    # titular bajó solo al país. Ahora, la corrección entera o nada.
    monkeypatch.setattr(correccion, "protegidos_por_el_cerrojo", lambda *a: ["lugar"])
    almacen = _base(_lituana())
    ficha = almacen.incidente("EODI-2026-09901")
    assert ficha is not None
    resumen, ctx = _corregir(almacen, Cliente([_respuesta()]))
    assert resumen.protegidas == ["EODI-2026-09901"] and resumen.corregidas == []
    guardada = almacen.incidente("EODI-2026-09901")
    assert guardada is not None and guardada["titulo"] == ficha["titulo"]
    assert guardada["lugar"]["nivel"] == "localidad"
    assert ctx.nuevas[correccion.CLAVE + "EODI-2026-09901"]["protegidos"] == ["lugar"]


def test_con_los_drones_protegidos_el_lugar_se_corrige(monkeypatch: pytest.MonkeyPatch) -> None:
    # EODI-2026-00725 en el ensayo: el número de drones tiene su cita; el lugar baja a la región
    # que nombra la frase, con su titular.
    def protegidos(almacen: Any, antes: dict[str, Any], nuevo: dict[str, Any]) -> list[str]:
        return ["drones"] if antes.get("drones") != nuevo.get("drones") else []

    monkeypatch.setattr(correccion, "protegidos_por_el_cerrojo", protegidos)
    frase = "Drones were seen over the Lithuanian coast"
    ficha = _lituana(frase=frase)
    ficha["drones"] = {"numero": {"min": 1, "max": 1}}
    almacen = _base(ficha)
    cliente = Cliente([_respuesta(lugar={"sostenido": False, "nivel": "region",
                                         "region": "Lithuanian coast", "frase": frase,
                                         "fuente": 1})])  # fmt: skip
    resumen, _ = _corregir(almacen, cliente)
    assert resumen.protegidas == resumen.corregidas == ["EODI-2026-09901"]
    guardada = almacen.incidente("EODI-2026-09901")
    assert guardada is not None and guardada["drones"]["numero"] == {"min": 1, "max": 1}
    assert guardada["lugar"]["region"] == "Lithuanian coast"
    assert "Lithuanian coast" in guardada["titulo"]["es"]


def test_una_region_sin_frase_literal_baja_al_pais() -> None:
    almacen = _base(_lituana())
    # La frase no está en la fuente: no cuenta.
    cliente = Cliente([_respuesta(lugar={"sostenido": True, "nivel": "igual", "region": "",
                                         "frase": "Over Kretinga", "fuente": 1})])  # fmt: skip
    _corregir(almacen, cliente)
    ficha = almacen.incidente("EODI-2026-09901")
    assert ficha is not None and ficha["lugar"]["nivel"] == "pais"
    assert "Lituania" in ficha["titulo"]["es"]


def test_los_drones_los_da_una_frase_con_la_palabra_dron_o_quedan_sin_dato() -> None:
    frase = "Two drones were seen over Kretinga on Monday"
    con_numero = _lituana(frase=frase)
    con_numero["drones"] = {"numero": {"min": 5, "max": 5}}
    almacen = _base(con_numero)
    cliente = Cliente([_respuesta(drones={"valor": "2", "frase": frase, "fuente": 1})])
    _corregir(almacen, cliente)
    ficha = almacen.incidente("EODI-2026-09901")
    assert ficha is not None and ficha["drones"]["numero"] == {"min": 2, "max": 2}
    assert any(a["campo"] == "drones" for a in ficha["afirmaciones"])
    # Sin frase: «sin dato».
    otra = _lituana("EODI-2026-09902", frase="A drone was seen over Kretinga on Monday")
    otra["drones"] = {"numero": {"min": 5, "max": 5}}
    almacen = _base(otra)
    _corregir(almacen, Cliente([_respuesta()]))
    ficha = almacen.incidente("EODI-2026-09902")
    assert ficha is not None and ficha["drones"]["numero"] == comprobaciones.SIN_DATO


def test_sin_relectura_espera_una_recogida_y_despues_corrige_lo_seguro() -> None:
    sin_frase = _lituana()
    sin_frase["drones"] = {"numero": {"min": 3, "max": 3}}
    almacen = _base(sin_frase)
    resumen, _ = _corregir(almacen, None)
    # La primera vez, tal como está: espera la relectura.
    assert resumen.sin_relectura == resumen.pendientes == ["EODI-2026-09901"]
    ficha = almacen.incidente("EODI-2026-09901")
    assert ficha is not None and ficha["lugar"]["nivel"] == "localidad"
    # Una recogida después, sin relectura todavía: lo seguro.
    ctx = _contexto(almacen, None)
    ctx.ahora = AHORA + timedelta(hours=1)
    correccion.corregir(ctx, Plazo(60))
    ficha = almacen.incidente("EODI-2026-09901")
    assert ficha is not None and ficha["lugar"]["nivel"] == "pais"
    assert ficha["drones"]["numero"] == comprobaciones.SIN_DATO
    # Corregida, ya no espera nada.
    ctx.ahora = AHORA + timedelta(hours=2)
    assert correccion.corregir(ctx, Plazo(60)).pendientes == []


def test_el_titular_con_otro_pais_se_rehace() -> None:
    ficha = _lituana(frase="A drone was seen over Kretinga on Monday")
    ficha["titulo"] = {"es": "Dron de Polonia avistado en Kretinga", "en": "x"}
    almacen = _base(ficha)
    resumen, _ = _corregir(almacen, Cliente([]))
    assert resumen.corregidas == ["EODI-2026-09901"] and resumen.releidas == 0
    guardada = almacen.incidente("EODI-2026-09901")
    assert guardada is not None
    assert comprobaciones.titulo_de_otro_pais(guardada) is None
    assert "Lituania" in guardada["titulo"]["es"]


# --- a) Dos jornadas: se separan, no se retienen ---------------------------------------------

DOS_DIAS = "W łotewską przestrzeń powietrzną wkroczyły w niedzielę i wtorek dwa drony."


def _letona() -> dict[str, Any]:
    ficha = _ficha("EODI-2026-09756", "LV", "2026-10-18T00:00Z", nivel="pais",
                   frase=DOS_DIAS, publicada="2026-10-22T08:15Z")  # fmt: skip
    ficha["lugar"] = {"pais": "LV", "nivel": "pais"}
    segunda = copy.deepcopy(ficha["fuentes"][0])
    segunda.update(id="EODI-2026-09756-F2", enlace="https://example.lv/otra",
                   frase_origen="Otrdien Latvijas gaisa telpā ielidoja drons")  # fmt: skip
    ficha["fuentes"][0]["idioma"] = "pl"
    ficha["fuentes"].append(segunda)
    return ficha


def test_dos_jornadas_se_separan_con_una_revision_automatica() -> None:
    almacen = _base(_letona())
    assert suceso.dos_dias_sin_revisar(almacen.incidente("EODI-2026-09756") or {})
    cliente = Cliente([_respuesta(dias=[
        {"dia": "2026-10-18", "fuentes": [1], "frase": DOS_DIAS, "fuente": 1},
        {"dia": "2026-10-20", "fuentes": [1, 2], "frase": DOS_DIAS, "fuente": 1},
    ])])  # fmt: skip
    resumen, _ = _corregir(almacen, cliente)
    assert resumen.separar == ["EODI-2026-09756"]
    guardadas = almacen.cursor(suceso.CURSOR_AUTOMATICAS) or {}
    (revision,) = guardadas["separar"]
    assert revision["automatica"] and [p["fecha"] for p in revision["partes"]] == [
        "2026-10-18", "2026-10-20"
    ]  # fmt: skip
    # En la pasada, todavía retenida; en la siguiente, la separación es una revisión más (la
    # hace recogida/revisados.separar) y la ficha ya no se retiene por sus dos días.
    assert suceso.dos_dias_sin_revisar(almacen.incidente("EODI-2026-09756") or {})
    suceso.cargar_automaticas(almacen)

    assert "EODI-2026-09756" in {r["incidente"] for r in revisados.cargar()["separar"]}
    assert not suceso.dos_dias_sin_revisar(almacen.incidente("EODI-2026-09756") or {})
    # El archivo de las revisiones no cambia: la automática vive en la base.
    archivo = json.loads(revisados.RUTA.read_text(encoding="utf-8"))
    assert "EODI-2026-09756" not in {r["incidente"] for r in archivo["separar"]}


def test_una_sola_jornada_tras_la_relectura_ya_no_retiene() -> None:
    almacen = _base(_letona())
    _corregir(almacen, Cliente([_respuesta()]))
    assert (almacen.cursor(suceso.CURSOR_AUTOMATICAS) or {}).get("una_jornada")
    suceso.cargar_automaticas(almacen)
    assert not suceso.dos_dias_sin_revisar(almacen.incidente("EODI-2026-09756") or {})


def test_sin_relectura_espera_una_recogida_y_luego_avisa_una_vez() -> None:
    almacen = _base(_letona())
    resumen, _ = _corregir(almacen, None)
    assert resumen.pendientes == ["EODI-2026-09756"]
    enviados: list[str] = []

    def avisador(titulo: str) -> Any:
        return enviados.append

    assert correccion.avisar_pendientes(almacen, AHORA, avisador) == []
    despues = AHORA + timedelta(hours=1)
    assert correccion.avisar_pendientes(almacen, despues, avisador) == ["EODI-2026-09756"]
    assert correccion.avisar_pendientes(almacen, despues, avisador) == []
    assert len(enviados) == 1 and "EODI-2026-09756" in enviados[0]
    # En un ensayo (sin avisador) no se avisa.
    assert correccion.avisar_pendientes(almacen, despues, None) == []
