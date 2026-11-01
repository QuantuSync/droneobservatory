"""El cerrojo de lo decidido (proceso/protegido.py, docs/cerrojo.md).

`tests/cerrojo/errores_reales.json` es la lista de los errores reales de datos desde el 20 de
octubre de 2026 (una entrada por ficha y dato). Cada uno intenta guardar por
`Almacen.guardar_incidente`, en modo «aplicar», una versión que cambia ese dato de esa ficha, y
comprueba que se retiene.
"""

import copy
import json
import random
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from proceso import auditoria_fichas, decidir, incidentes, protegido
from recogida import control_fichas, vigilancia, visitas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_control_fichas import AHORA, _fuente, _nuremberg_griega

ERRORES = json.loads(
    (Path(__file__).parent / "cerrojo" / "errores_reales.json").read_text(encoding="utf-8")
)
ENLACE = "https://ejemplo.eu/noticia"
ENLACE_NUEVO = "https://otro.eu/noticia"
# Los errores que no son un dato protegido, por diseño: una fuente de más no es un dato decidido
# (la cubren `quitar_fuentes` y la auditoría C) y en una ficha sin revisión a mano ni el titular,
# ni el tipo, ni la instalación son del nivel con cita.
NO_PROTEGIDOS = {"fuentes"}
FUERA_DEL_NIVEL_CON_CITA = {"titulo", "tipo", "objetivo"}


@pytest.fixture
def aplicar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protegido, "modo", lambda: protegido.APLICAR)


def _afirmacion(campo: str, valor: Any, fuente: str) -> Documento:
    return {"campo": campo, "valor": valor, "fuente_id": fuente, "confianza_extraccion": 0.9}


def ficha(id_: str = "EODI-2026-09600") -> Documento:
    """Una ficha publicada con sus datos decididos con la frase de una fuente."""
    d = _nuremberg_griega()
    d["id"] = id_
    principal = _fuente("gdelt-base", ENLACE, "ejemplo.eu", "de", "Frase de la noticia.", "08:00")
    oficial = _fuente(
        "gdelt-base-declaracion-1", ENLACE, "Polizei Nürnberg (declaración oficial citada en "
        "ejemplo.eu)", "de", "Die Polizei bestätigte die Drohne über dem Flughafen.", "08:00",
    )  # fmt: skip
    oficial["es_autoridad"] = True
    d["fuentes"] = [principal, oficial]
    d["presencia_dron"] = "confirmada"
    d["estado"] = {
        "actual": "confirmado",
        "historial": [
            {"estado": "notificado", "fecha": principal["fecha"], "fuente_id": principal["id"]},
            {"estado": "confirmado", "fecha": oficial["fecha"], "fuente_id": oficial["id"]},
        ],
    }
    d["tiempo"] = {
        "inicio": ejemplos.instante("2026-10-13T08:30Z", "minuto"),
        "origen_inicio": {"tipo": "explicita", "fuente_id": principal["id"], "motivo": "la frase"},
    }
    d["drones"] = {"numero": {"min": 1, "max": 1}}
    d["consecuencias"] = {"cierre": {"valor": "si", "minutos": {"min": 30, "max": 30}}}
    d["afirmaciones"] = [
        _afirmacion("presencia_dron", "confirmada", oficial["id"]),
        _afirmacion("drones", {"min": 1, "max": 1}, principal["id"]),
        _afirmacion("cierre", "si", principal["id"]),
        _afirmacion("cierre_minutos", {"min": 30, "max": 30}, principal["id"]),
        _afirmacion("lugar_suceso", {"nombre": "Núremberg"}, principal["id"]),
    ]
    return d


def base(*documentos: Documento) -> Almacen:
    almacen = Almacen.abrir()
    for documento in documentos:
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    return almacen


def guardar(almacen: Almacen, documento: Documento) -> None:
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)


def distinto_del_experto(almacen: Almacen, a: str, b: str) -> None:
    uno, otro = sorted((a, b))
    almacen.guardar_controles(
        {f"par:{uno}|{otro}": {"decision": "distinto", "escalado": ["dudoso"], "huella": "x"}},
        "2026-10-13T05:00:00Z",
    )


def version_mala(documento: Documento, dato: str) -> Documento:
    """La ficha con ese dato cambiado sin ninguna fuente nueva."""
    nuevo = copy.deepcopy(documento)
    if dato == "fin":
        nuevo["tiempo"]["fin"] = ejemplos.instante("2026-10-13T11:00Z", "minuto")
    elif dato == "inicio":
        nuevo["tiempo"] = {
            "inicio": ejemplos.instante("2026-10-01T00:00Z", "dia"),
            "origen_inicio": {"tipo": "publicacion", "motivo": "fecha de la noticia"},
        }
    elif dato == "drones":
        nuevo["drones"] = {"numero": "desconocido"}
    elif dato == "cierre":
        nuevo["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    elif dato == "lugar":
        nuevo["lugar"] = {"pais": nuevo["lugar"]["pais"], "nivel": "pais"}
    elif dato == "estado":
        fecha = nuevo["estado"]["historial"][-1]["fecha"]
        nuevo["estado"]["historial"].append(
            {"estado": "desmentido", "fecha": fecha, "fuente_id": "gdelt-base"}
        )
        nuevo["estado"]["actual"] = "desmentido"
        nuevo["control"]["motivo_desmentido"] = "Otra lectura."
    elif dato == "presencia_dron":
        nuevo["presencia_dron"] = "descartada"
        nuevo["afirmaciones"] = [
            a for a in nuevo["afirmaciones"] if a["campo"] != "presencia_dron"
        ] + [_afirmacion("presencia_dron", "descartada", "gdelt-base")]
    elif dato == "tipo":
        nuevo["tipo"] = "incursion" if nuevo.get("tipo") != "incursion" else "sobrevuelo"
    elif dato == "objetivo":
        nuevo["objetivo"] = {"categoria": "puerto", "nombre": "Otro puerto"}
    elif dato == "titulo":
        nuevo["titulo"] = {"es": "Otro titular cualquiera del suceso", "en": "Some other headline"}
    elif dato == "retirado":
        nuevo["retirado"] = {
            "fecha": ejemplos.instante("2026-10-13T14:17Z", "minuto"),
            "motivo": "No se sabe la fecha.",
        }
    return nuevo


def retenido(error: Documento, monkeypatch: pytest.MonkeyPatch) -> bool:
    """Guarda la versión mala del error en modo «aplicar»; True si el dato no cambió. Sin
    `decidir.aplicar`, que arregla parte de estos por su cuenta (lo que se prueba es la última
    barrera), salvo en un dato con revisión a mano: ese lo fija `decidir` y el cerrojo lo deja
    pasar."""
    dato = str(error["dato"])
    uno = ficha(str(error["ficha"]))
    if dato == "fusionado_en":
        # La unión equivocada, con la marca que dejó su corrección. Si el error fue una ficha
        # duplicada en el alta, la unión de esa ficha con otra cualquiera marcada como distinta.
        malo = str(error.get("malo"))
        otro_id = malo if malo.startswith("EODI-") else "EODI-2026-09601"
        otro = ficha(otro_id)
        otro["fuentes"] = [{**f, "id": f"otra-{f['id']}", "enlace": ENLACE_NUEVO}
                           for f in otro["fuentes"]]  # fmt: skip
        otro["estado"]["historial"][0]["fuente_id"] = "otra-gdelt-base"
        otro["estado"]["historial"][1]["fuente_id"] = "otra-gdelt-base-declaracion-1"
        otro["tiempo"]["origen_inicio"]["fuente_id"] = "otra-gdelt-base"
        for afirmacion in otro["afirmaciones"]:
            afirmacion["fuente_id"] = f"otra-{afirmacion['fuente_id']}"
        almacen = base(uno, otro)
        distinto_del_experto(almacen, str(uno["id"]), otro_id)
        guardar(almacen, {**(almacen.incidente(str(uno["id"])) or {}), "fusionado_en": otro_id})
        return "fusionado_en" not in (almacen.incidente(str(uno["id"])) or {})
    almacen = base(uno)
    guardado = almacen.incidente(str(uno["id"]))
    assert guardado is not None
    mala = version_mala(guardado, dato)
    if not protegido._revisado(mala, "inicio" if dato == "fin" else dato):
        monkeypatch.setattr(decidir, "aplicar", lambda incidente, *_: incidente)
    guardar(almacen, mala)
    actual = almacen.incidente(str(uno["id"]))
    assert actual is not None
    dato = "inicio" if dato == "fin" else dato
    return bool(protegido.valor(actual, dato) == protegido.valor(guardado, dato))


def _esperado(error: Documento) -> bool:
    if error["dato"] in NO_PROTEGIDOS:
        return False
    return not (
        error["dato"] in FUERA_DEL_NIVEL_CON_CITA
        and error["ficha"] not in protegido.fichas_manuales()
    )


@pytest.mark.parametrize(
    "error", ERRORES, ids=[f"{e['ficha'][5:]}-{e['dato']}-{e['n']}" for e in ERRORES]
)
def test_cada_error_real_se_retiene(
    error: Documento, aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if error["dato"] in NO_PROTEGIDOS:
        pytest.skip("no es un dato protegido: lo cubren quitar_fuentes y la auditoría")
    assert retenido(error, monkeypatch) is _esperado(error)


def test_la_lista_de_errores_trae_los_del_encargo() -> None:
    claves = {(e["ficha"], e["dato"]) for e in ERRORES}
    assert ("EODI-2026-00066", "inicio") in claves
    assert ("EODI-2025-00043", "presencia_dron") in claves
    assert ("EODI-2025-00043", "drones") in claves
    assert ("EODI-2026-00648", "titulo") in claves


# --- El caso de hoy: R ------------------------------------------------------------------------


def test_otra_declaracion_del_mismo_articulo_no_justifica(aplicar: None) -> None:
    # EODI-2025-00043: una reextracción sacó una declaración más del mismo artículo.
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    nuevo = version_mala(guardado, "drones")
    copia = {**guardado["fuentes"][0], "id": "gdelt-base-declaracion-2"}
    nuevo["fuentes"].append(copia)
    guardar(almacen, nuevo)
    actual = almacen.incidente("EODI-2026-09600")
    assert actual is not None
    assert actual["drones"]["numero"] == {"min": 1, "max": 1}
    # Las fuentes nuevas sí se quedan: solo se conserva el dato.
    assert "gdelt-base-declaracion-2" in {f["id"] for f in actual["fuentes"]}
    assert any(c.startswith("retenido:EODI-2026-09600:drones:") for c in almacen.controles())


def test_el_cerrojo_apunta_quien_lo_intento(aplicar: None) -> None:
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(almacen, version_mala(guardado, "drones"))
    ((clave, apunte),) = almacen.controles(protegido.PREFIJO_RETENIDO).items()
    assert apunte["ficha"] == "EODI-2026-09600" and apunte["dato"] == "drones"
    assert apunte["antes"] == {"min": 1, "max": 1} and apunte["despues"] == "desconocido"
    assert apunte["quien"] == f"{__name__}.guardar" and apunte["fecha"] == "2026-10-13T14:17:00Z"
    assert clave.count(":") == 3


def test_el_tipo_sigue_al_cierre_retenido(aplicar: None) -> None:
    # Sobre la base real, 15 fichas: con el cierre conservado y el tipo que dejó `decidir`, lo
    # retenido no validaba («hay interrupción de aeropuerto: manda ese tipo») y la escritura pasaba.
    uno = ficha()
    uno["tipo"] = "interrupcion_aeroportuaria"
    almacen = base(uno)
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    tipo = guardado["tipo"]
    guardar(almacen, version_mala(guardado, "cierre"))
    actual = almacen.incidente("EODI-2026-09600")
    assert actual is not None
    assert actual["consecuencias"]["cierre"]["valor"] == "si" and actual["tipo"] == tipo
    assert not almacen.controles(protegido.PREFIJO_FALLO)


# --- Cambios legítimos ------------------------------------------------------------------------


def _con_fuente_nueva(documento: Documento, frase: str) -> Documento:
    nuevo = copy.deepcopy(documento)
    nuevo["drones"] = {"numero": {"min": 3, "max": 3}}
    fuente = _fuente("gdelt-nueva", ENLACE_NUEVO, "otro.eu", "de", frase, "09:00")
    nuevo["fuentes"].append(fuente)
    nuevo["afirmaciones"] = [a for a in nuevo["afirmaciones"] if a["campo"] != "drones"]
    nuevo["afirmaciones"].append(_afirmacion("drones", {"min": 3, "max": 3}, "gdelt-nueva"))
    return nuevo


def _articulo_guardado(almacen: Almacen, frase: str) -> None:
    almacen.conexion.execute(
        "INSERT INTO articulos (url, medio, fecha, idioma, pais, titular, titular_normalizado, "
        "temas, lugares, replicas, candidato) VALUES (?, 'otro.eu', '2026-10-13', 'de', 'DE', ?, "
        "?, '[]', '[]', 0, 'CAND-1')",
        (ENLACE_NUEVO, frase, frase.lower()),
    )


def test_una_fuente_nueva_con_su_frase_literal_si_cambia_el_dato(aplicar: None) -> None:
    frase = "Drei Drohnen über dem Flughafen"
    almacen = base(ficha())
    _articulo_guardado(almacen, frase)
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(almacen, _con_fuente_nueva(guardado, frase))
    actual = almacen.incidente("EODI-2026-09600")
    assert actual is not None and actual["drones"]["numero"] == {"min": 3, "max": 3}
    assert not almacen.controles(protegido.PREFIJO_RETENIDO)
    assert any(c.startswith("permitido:EODI-2026-09600:drones:") for c in almacen.controles())


def test_una_fuente_nueva_sin_frase_en_su_articulo_no_cambia_el_dato(aplicar: None) -> None:
    almacen = base(ficha())
    _articulo_guardado(almacen, "Ein anderer Titel")
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(almacen, _con_fuente_nueva(guardado, "Drei Drohnen über dem Flughafen"))
    actual = almacen.incidente("EODI-2026-09600")
    assert actual is not None and actual["drones"]["numero"] == {"min": 1, "max": 1}


def test_una_rectificacion_oficial_nueva_si_pasa(aplicar: None) -> None:
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    nuevo = copy.deepcopy(guardado)
    nuevo["presencia_historial"] = [
        {"valor": "confirmada", "fuente_id": "gdelt-base-declaracion-1",
         "fecha": ejemplos.instante("2026-10-13T08:00Z", "minuto")},
        {"valor": "no_acreditada", "fuente_id": "gdelt-base-declaracion-1",
         "fecha": ejemplos.instante("2026-10-13T12:00Z", "minuto")},
    ]  # fmt: skip
    guardar(almacen, nuevo)
    actual = almacen.incidente("EODI-2026-09600")
    assert actual is not None and actual["presencia_dron"] == "no_acreditada"
    assert not almacen.controles(protegido.PREFIJO_RETENIDO)


def test_una_revision_a_mano_si_pasa(aplicar: None) -> None:
    assert protegido.por_revision(["recogida.revisados._guardar", "recogida.revisados.corregir"])
    assert not protegido.por_revision(
        ["proceso.extraccion._alta", "recogida.revisados._extraer_parte"]
    )
    assert not protegido.por_revision(["recogida.control_fichas.unir"])


def test_el_alta_no_esta_protegida(aplicar: None) -> None:
    almacen = base(ficha())
    assert not almacen.controles(protegido.PREFIJO_RETENIDO)


# --- Observar ---------------------------------------------------------------------------------


def _estado(almacen: Almacen) -> tuple[Any, ...]:
    tablas = ("incidentes", "fuentes", "afirmaciones", "fusiones")
    return tuple(
        almacen.conexion.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall() for t in tablas
    )


def _pasada(almacen: Almacen) -> None:
    for dato in ("inicio", "drones", "cierre", "lugar", "presencia_dron", "retirado"):
        guardado = almacen.incidente("EODI-2026-09600")
        assert guardado is not None
        if "retirado" not in guardado:
            guardar(almacen, version_mala(guardado, dato))
    otra = almacen.incidente("EODI-2026-09601")
    assert otra is not None
    almacen.guardar_incidente(
        {**otra, "fusionado_en": "EODI-2026-09600"}, AHORA, VOCABULARIO_MODELOS
    )
    almacen.registrar_fusion("2026-10-13T14:17Z", "EODI-2026-09601", "EODI-2026-09600", "x", [])


def test_en_observar_la_base_queda_como_sin_cerrojo(monkeypatch: pytest.MonkeyPatch) -> None:
    def montar() -> Almacen:
        almacen = base(ficha(), ficha("EODI-2026-09601"))
        distinto_del_experto(almacen, "EODI-2026-09600", "EODI-2026-09601")
        return almacen

    con = montar()
    _pasada(con)
    sin = montar()
    monkeypatch.setattr(protegido, "juzgar", lambda *a: protegido.Veredicto())
    monkeypatch.setattr(protegido, "union_prohibida", lambda *a: None)
    _pasada(sin)
    assert _estado(con) == _estado(sin)
    assert con.controles(protegido.PREFIJO_RETENIDO)
    assert not sin.controles(protegido.PREFIJO_RETENIDO)


def test_la_configuracion_se_fusiona_en_observar() -> None:
    assert protegido.modo() == protegido.OBSERVAR
    assert json.loads(protegido.CONFIGURACION.read_text(encoding="utf-8"))["modo"] == "observar"


def test_un_modo_desconocido_es_observar(tmp_path: Path) -> None:
    ruta = tmp_path / "cerrojo.json"
    ruta.write_text('{"modo": "otro"}', encoding="utf-8")
    assert protegido.modo(ruta) == protegido.OBSERVAR
    assert protegido.modo(tmp_path / "no.json") == protegido.OBSERVAR


# --- Uniones ----------------------------------------------------------------------------------


def test_un_grupo_entero_no_salta_el_par_prohibido(aplicar: None) -> None:
    # La cadena 00712→00708→00694: 00712 cuelga de 00708 y 00708 se une a 00694, y el prohibido es
    # 00712 con 00694.
    a, b, c = "EODI-2026-00694", "EODI-2026-00708", "EODI-2026-00712"
    almacen = base(ficha(a), ficha(b), ficha(c))
    distinto_del_experto(almacen, a, c)
    colgada = almacen.incidente(c)
    assert colgada is not None
    guardar(almacen, {**colgada, "fusionado_en": b})
    media = almacen.incidente(b)
    assert media is not None
    guardar(almacen, {**media, "fusionado_en": a})
    assert "fusionado_en" not in (almacen.incidente(b) or {})
    apunte = almacen.controles(f"retenido:{b}:fusionado_en:")
    assert [(d["uno"], d["otro"]) for d in apunte.values()] == [(c, a)]


def test_la_v_de_hoy_una_union_a_mano_manda_sobre_la_marca(aplicar: None) -> None:
    uno, otro = ficha("EODI-2026-09600"), ficha("EODI-2026-09601")
    almacen = base(uno, otro)
    distinto_del_experto(almacen, "EODI-2026-09600", "EODI-2026-09601")
    almacen.registrar_fusion(
        "2026-10-20T10:17Z", "EODI-2026-09600", "EODI-2026-09601", "revisión: el mismo", []
    )
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(almacen, {**guardado, "fusionado_en": "EODI-2026-09601"})
    assert (almacen.incidente("EODI-2026-09600") or {}).get("fusionado_en") == "EODI-2026-09601"


def test_una_union_retenida_no_deja_la_destinataria_a_medias(aplicar: None) -> None:
    uno, otro = ficha("EODI-2026-09600"), _nuremberg_griega()
    otro["id"] = "EODI-2026-09601"
    almacen = base(uno, otro)
    distinto_del_experto(almacen, "EODI-2026-09600", "EODI-2026-09601")
    conserva, une = almacen.incidente(uno["id"]), almacen.incidente(otro["id"])
    assert conserva is not None and une is not None
    # Como incidentes.fusionar, sin su comprobación: la destinataria recibe las fuentes y después
    # se marca la absorbida.
    nuevo, aportadas = incidentes.absorber(conserva, une, AHORA)
    guardar(almacen, nuevo)
    guardar(almacen, {**une, "fusionado_en": conserva["id"]})
    almacen.registrar_fusion("2026-10-13T14:17Z", une["id"], conserva["id"], "regla", aportadas)
    assert almacen.incidente(uno["id"]) == conserva
    assert "fusionado_en" not in (almacen.incidente(otro["id"]) or {})
    assert almacen.fusiones() == []


def test_renumerar_no_abre_un_duplicado(aplicar: None, monkeypatch: pytest.MonkeyPatch) -> None:
    # recogida/control_fichas.conservar_la_mas_antigua: la más antigua colgaba de la más nueva y
    # pasa a quedarse; la más nueva se marca fundida en ella y las demás cuelgan de la antigua.
    viejo, nuevo, otro = "EODI-2026-09600", "EODI-2026-09601", "EODI-2026-09602"
    almacen = base(ficha(viejo), ficha(nuevo), ficha(otro))
    distinto_del_experto(almacen, viejo, otro)
    guardar(almacen, {**(almacen.incidente(viejo) or {}), "fusionado_en": nuevo})
    guardar(almacen, {**(almacen.incidente(otro) or {}), "fusionado_en": nuevo})
    assert "fusionado_en" not in (almacen.incidente(otro) or {})  # el par prohibido, retenido
    conserva = almacen.incidente(nuevo)
    assert conserva is not None
    queda = {**copy.deepcopy(conserva), "id": viejo}
    monkeypatch.setattr(protegido, "pila", lambda: [protegido.PASO_RENUMERAR])
    guardar(almacen, queda)
    guardar(almacen, {**conserva, "fusionado_en": viejo})
    assert (almacen.incidente(nuevo) or {}).get("fusionado_en") == viejo
    assert "fusionado_en" not in (almacen.incidente(viejo) or {})


MANUAL, OTRA = "EODI-2026-09600", "EODI-2026-09601"


def _manual(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protegido, "fichas_manuales", lambda: frozenset({MANUAL}))


def _unir_por_regla(almacen: Almacen, absorbida: str, queda: str) -> None:
    """Como incidentes.fusionar: la que queda recibe las fuentes y luego se marca la absorbida."""
    conserva, une = almacen.incidente(queda), almacen.incidente(absorbida)
    assert conserva is not None and une is not None
    nuevo, aportadas = incidentes.absorber(conserva, une, AHORA)
    guardar(almacen, nuevo)
    guardar(almacen, {**une, "fusionado_en": queda})
    almacen.registrar_fusion("2026-10-13T14:17Z", absorbida, queda, "regla", aportadas)


def _dos_fichas() -> Almacen:
    otra = _nuremberg_griega()
    otra["id"] = OTRA
    return base(ficha(MANUAL), otra)


def test_una_regla_no_funde_una_ficha_manual(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manual(monkeypatch)
    almacen = _dos_fichas()
    antes = almacen.incidente(OTRA)
    _unir_por_regla(almacen, MANUAL, OTRA)
    assert "fusionado_en" not in (almacen.incidente(MANUAL) or {})
    assert almacen.incidente(OTRA) == antes
    assert almacen.fusiones() == []
    apunte = almacen.controles(f"retenido:{MANUAL}:fusionado_en:{OTRA}")
    assert [d["motivo"] for d in apunte.values()] == ["manual"]


def test_en_observar_la_union_de_una_manual_se_apunta_y_no_cambia_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _manual(monkeypatch)
    almacen = _dos_fichas()
    _unir_por_regla(almacen, MANUAL, OTRA)
    assert (almacen.incidente(MANUAL) or {}).get("fusionado_en") == OTRA
    assert len(almacen.fusiones()) == 1
    assert almacen.controles(f"retenido:{MANUAL}:fusionado_en:{OTRA}")


def test_una_revision_a_mano_si_funde_una_ficha_manual(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manual(monkeypatch)
    monkeypatch.setattr(protegido, "pila", lambda: ["recogida.revisados.unir"])
    almacen = _dos_fichas()
    _unir_por_regla(almacen, MANUAL, OTRA)
    assert (almacen.incidente(MANUAL) or {}).get("fusionado_en") == OTRA
    assert not almacen.controles("retenido:")


def test_una_union_a_mano_anterior_manda_en_la_ficha_manual(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manual(monkeypatch)
    almacen = _dos_fichas()
    almacen.registrar_fusion("2026-10-20T10:17Z", MANUAL, OTRA, "revisión: el mismo", [])
    _unir_por_regla(almacen, MANUAL, OTRA)
    assert (almacen.incidente(MANUAL) or {}).get("fusionado_en") == OTRA


def test_la_ficha_manual_si_recibe_un_duplicado(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _manual(monkeypatch)
    almacen = _dos_fichas()
    _unir_por_regla(almacen, OTRA, MANUAL)
    assert (almacen.incidente(OTRA) or {}).get("fusionado_en") == MANUAL
    assert not almacen.controles(f"retenido:{OTRA}:fusionado_en:")


def _fundida() -> Almacen:
    almacen = _dos_fichas()
    _unir_por_regla(almacen, OTRA, MANUAL)
    return almacen


def test_una_regla_no_reabre_una_ficha_fundida(aplicar: None) -> None:
    almacen = _fundida()
    destino = almacen.incidente(MANUAL)
    incidentes.revertir(almacen, OTRA, AHORA, VOCABULARIO_MODELOS)
    assert (almacen.incidente(OTRA) or {}).get("fusionado_en") == MANUAL
    assert almacen.incidente(MANUAL) == destino
    assert [f["revertida"] for f in almacen.fusiones()] == [False]
    apunte = almacen.controles(f"retenido:{OTRA}:reapertura:{MANUAL}")
    assert [d["dato"] for d in apunte.values()] == ["reapertura"]


def test_en_observar_la_reapertura_se_apunta_y_no_cambia_nada() -> None:
    almacen = _fundida()
    incidentes.revertir(almacen, OTRA, AHORA, VOCABULARIO_MODELOS)
    assert "fusionado_en" not in (almacen.incidente(OTRA) or {})
    assert [f["revertida"] for f in almacen.fusiones()] == [True]
    assert almacen.controles(f"retenido:{OTRA}:reapertura:{MANUAL}")


def test_una_revision_a_mano_si_reabre(aplicar: None, monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = _fundida()
    monkeypatch.setattr(protegido, "pila", lambda: ["recogida.revisados.separar"])
    incidentes.revertir(almacen, OTRA, AHORA, VOCABULARIO_MODELOS)
    assert "fusionado_en" not in (almacen.incidente(OTRA) or {})
    assert not almacen.controles("retenido:")


def test_una_extraccion_lanzada_desde_una_revision_no_reabre(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = _fundida()
    monkeypatch.setattr(
        protegido, "pila", lambda: ["proceso.extraccion._alta", "recogida.revisados.separar"]
    )
    fundida = almacen.incidente(OTRA)
    assert fundida is not None
    guardar(almacen, {k: v for k, v in fundida.items() if k != "fusionado_en"})
    assert (almacen.incidente(OTRA) or {}).get("fusionado_en") == MANUAL


def test_una_separacion_si_reabre(aplicar: None) -> None:
    # incidentes.revisar_fusiones deshace una unión de un par que no se une.
    almacen = _fundida()
    distinto_del_experto(almacen, MANUAL, OTRA)
    incidentes.revertir(almacen, OTRA, AHORA, VOCABULARIO_MODELOS)
    assert "fusionado_en" not in (almacen.incidente(OTRA) or {})
    assert not almacen.controles(f"retenido:{OTRA}:reapertura:")


def test_cadenas_y_renumeraciones_al_azar_nunca_juntan_un_par_prohibido(aplicar: None) -> None:
    azar = random.Random(20261101)
    for _ in range(25):
        ids = [f"EODI-2026-09{n:03d}" for n in range(600, 612)]
        almacen = base(*(ficha(i) for i in ids))
        prohibidos = set()
        for _ in range(8):
            a, b = azar.sample(ids, 2)
            prohibidos.add(frozenset((a, b)))
            distinto_del_experto(almacen, a, b)
        for _ in range(40):
            a, b = azar.sample(ids, 2)
            documento = almacen.incidente(a)
            assert documento is not None
            enlaces = almacen.enlaces_de_fusion()
            if protegido.raiz_de(b, enlaces) == protegido.raiz_de(a, enlaces):
                continue
            if azar.random() < 0.3 and a in enlaces:
                # Una renumeración: la ficha cuelga ahora de la destinataria de su destinataria.
                siguiente = enlaces.get(enlaces[a])
                if siguiente is None:
                    continue
                b = siguiente
            guardar(almacen, {**documento, "fusionado_en": b})
            if azar.random() < 0.2:
                guardar(almacen, {k: v for k, v in documento.items() if k != "fusionado_en"})
        enlaces = almacen.enlaces_de_fusion()
        por_raiz: dict[str, set[str]] = {}
        for id_ in ids:
            por_raiz.setdefault(protegido.raiz_de(id_, enlaces), set()).add(id_)
        for grupo in por_raiz.values():
            assert not any(par <= grupo for par in prohibidos)


# --- Nunca para la recogida -------------------------------------------------------------------


def test_si_el_cerrojo_falla_la_escritura_pasa_y_se_cuenta(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None

    def rota(*_: Any) -> protegido.Veredicto:
        raise RuntimeError("roto")

    monkeypatch.setattr(protegido, "juzgar", rota)
    guardar(almacen, version_mala(guardado, "drones"))
    actual = almacen.incidente("EODI-2026-09600")
    assert actual is not None and actual["drones"]["numero"] == "desconocido"
    assert len(almacen.controles(protegido.PREFIJO_FALLO)) == 1


def test_si_ni_apuntar_el_fallo_se_puede_tampoco_para(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None

    def rota(*_: Any) -> None:
        raise sqlite3.OperationalError("sin disco")

    monkeypatch.setattr(almacen, "_apuntar_control", rota)
    guardar(almacen, version_mala(guardado, "drones"))


def test_lo_retenido_que_no_valida_deja_pasar_y_se_cuenta(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    monkeypatch.setattr(protegido, "conservar", lambda *_: {**guardado, "tipo": "no vale"})
    guardar(almacen, version_mala(guardado, "drones"))
    assert len(almacen.controles(protegido.PREFIJO_FALLO)) == 1


# --- Auditoría X, resumen y vigilancia --------------------------------------------------------


def _cambios(almacen: Almacen) -> list[Documento]:
    return almacen.cambios_desde("2000-01-01")


def test_x_cuenta_lo_guardado_sin_permiso_y_vale_0_en_aplicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observado = base(ficha())
    guardado = observado.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(observado, version_mala(guardado, "drones"))
    assert protegido.cambios_sin_permiso(_cambios(observado), frozenset()) == [
        "EODI-2026-09600 drones"
    ]
    monkeypatch.setattr(protegido, "modo", lambda: protegido.APLICAR)
    aplicado = base(ficha())
    guardar(aplicado, version_mala(guardado, "drones"))
    assert protegido.cambios_sin_permiso(_cambios(aplicado), frozenset()) == []


def test_x_no_cuenta_lo_permitido(aplicar: None) -> None:
    frase = "Drei Drohnen über dem Flughafen"
    almacen = base(ficha())
    _articulo_guardado(almacen, frase)
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(almacen, _con_fuente_nueva(guardado, frase))
    permitidos = protegido.permitidos(almacen.controles(protegido.PREFIJO_PERMITIDO))
    assert protegido.cambios_sin_permiso(_cambios(almacen), permitidos) == []
    resultado = auditoria_fichas.auditar(
        almacen.incidentes(), _cambios(almacen), permitidos=permitidos
    )
    assert resultado["X"] == [] and "X" in auditoria_fichas.NOMBRES


def test_el_estado_del_control_lleva_el_cerrojo() -> None:
    almacen = base(ficha())
    guardado = almacen.incidente("EODI-2026-09600")
    assert guardado is not None
    guardar(almacen, version_mala(guardado, "drones"))
    estado = control_fichas.cerrojo_del_dia(almacen, AHORA, {"ids": {"X": ["a"], "A": ["b"]}})
    assert estado["modo"] == "observar" and estado["proteccion"] == {"X": ["a"]}
    assert estado["dias"] == {"2026-10-13": ["EODI-2026-09600 drones"]}
    assert estado["fallos_24h"] == 0


def test_el_resumen_lleva_los_cambios_retenidos() -> None:
    lineas = visitas.lineas_cerrojo({"modo": "observar", "retenidos": ["EODI-2026-09600 drones"]})
    assert lineas[0] == "  Cambios retenidos: 1 (en observación)"
    assert lineas[1] == "  - EODI-2026-09600 drones"
    assert visitas.lineas_cerrojo({"modo": "aplicar", "retenidos": []}) == [
        "  Cambios retenidos: 0",
        "  Guardados fallidos de fichas publicadas: 0",
    ]
    assert visitas.lineas_cerrojo(None) == []


def test_la_vigilancia_solo_avisa_de_la_proteccion_en_aplicar() -> None:
    estado: Documento = {"cerrojo": {"modo": "observar", "proteccion": {"R": ["x"]}}}
    assert vigilancia.problemas_del_cerrojo(estado) == []
    estado["cerrojo"]["modo"] = "aplicar"
    assert [p["id"] for p in vigilancia.problemas_del_cerrojo(estado)] == ["cerrojo_proteccion"]
    estado = {"cerrojo": {"modo": "observar", "fallos_24h": 2}}
    assert [p["id"] for p in vigilancia.problemas_del_cerrojo(estado)] == ["cerrojo_fallos"]
    assert vigilancia.problemas_del_cerrojo({}) == []
