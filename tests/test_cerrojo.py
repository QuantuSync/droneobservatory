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
    principal = _fuente(
        "gdelt-base", ENLACE, "ejemplo.eu", "de",
        "Um 08:30 Uhr sah die Polizei eine Drohne und der Flughafen schloss 30 Minuten.", "08:00",
    )  # fmt: skip
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
    if not protegido._hay_revision(mala, "inicio" if dato == "fin" else dato):
        monkeypatch.setattr(decidir, "aplicar", lambda incidente, *_: incidente)
    guardar(almacen, mala)
    actual = almacen.incidente(str(uno["id"]))
    assert actual is not None
    dato = "inicio" if dato == "fin" else dato
    return bool(protegido.valor(actual, dato) == protegido.valor(guardado, dato))


def _esperado(error: Documento) -> bool:
    if error["dato"] in NO_PROTEGIDOS:
        return False
    if error["dato"] == "titulo":
        # Sin frase propia: solo si lo fija una revisión; si no, sigue a lo retenido.
        return protegido._respaldado(ficha(str(error["ficha"])), "titulo")
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


def test_la_configuracion_tiene_un_modo_valido() -> None:
    # Las pruebas van en «observar» (tests/conftest.py); el fichero dice el modo de verdad.
    assert protegido.modo() == protegido.OBSERVAR
    modo = json.loads(protegido.CONFIGURACION.read_text(encoding="utf-8"))["modo"]
    assert modo in (protegido.OBSERVAR, protegido.APLICAR)
    assert protegido.modo(protegido.CONFIGURACION) == modo


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
        "  Fichas publicadas en su versión anterior: 0",
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


# --- La regla ajustada ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dato", "frase", "dicho", "esperado"),
    [
        ("drones", "reports of multiple drones near Jersey Airport", {"min": 2, "max": 4}, False),
        ("drones", "Două aparate de zbor fără pilot au survolat", {"min": 2, "max": 2}, True),
        ("drones", "12 Drohnen über dem Hafen", {"min": 12, "max": 12}, True),
        ("drones", "Dronas yra pakeltas Servečės gatvėje", {"min": 1, "max": 1}, True),
        ("drones", "Dronas yra pakeltas", "desconocido", False),
        ("inicio", "am Mittwochabend plötzlich gestoppt", {"precision": "hora"}, False),
        ("inicio", "la ora 10:26, de către un aparat", {"precision": "minuto"}, True),
        ("inicio", "gegen 22 Uhr über dem Flughafen", {"precision": "hora"}, True),
        ("inicio", "am 11.03.2026 über dem Flughafen", {"precision": "hora"}, False),
        ("inicio", "el 18 de septiembre", {"precision": "dia"}, True),
        ("lugar", "", {}, False),
    ],
)
def test_una_frase_respalda_el_dato_solo_si_lo_dice(
    dato: str, frase: str, dicho: Any, esperado: bool
) -> None:
    assert protegido.dice_el_dato(dato, frase, dicho) is esperado


def _sin_frase_que_lo_diga(documento: Documento) -> Documento:
    documento = copy.deepcopy(documento)
    documento["fuentes"][0]["frase_origen"] = "Es gab mehrere Drohnen am Flughafen."
    documento["drones"] = {"numero": {"min": 2, "max": 4}}
    for afirmacion in documento["afirmaciones"]:
        if afirmacion["campo"] == "drones":
            afirmacion["valor"] = {"min": 2, "max": 4}
    return documento


def test_lo_que_ninguna_frase_dice_se_puede_corregir() -> None:
    # EODI-2026-00714 («multiple drones», 2 a 4) y EODI-2026-00013 (una hora que nadie da).
    guardado = _sin_frase_que_lo_diga(ficha())
    nuevo = copy.deepcopy(guardado)
    nuevo["drones"] = {"numero": "desconocido"}
    nuevo["tiempo"]["inicio"] = ejemplos.instante("2026-10-13T00:00Z", "dia")
    nuevo["tiempo"]["origen_inicio"] = {"tipo": "publicacion", "motivo": "sin frase"}
    assert protegido.candidatos(guardado, nuevo) == []


def test_lo_que_una_frase_dice_sigue_protegido() -> None:
    guardado = ficha()
    guardado["drones"] = {"numero": {"min": 30, "max": 30}}
    guardado["afirmaciones"] = [
        {**a, "valor": {"min": 30, "max": 30}} if a["campo"] == "drones" else a
        for a in guardado["afirmaciones"]
    ]
    nuevo = copy.deepcopy(guardado)
    nuevo["drones"] = {"numero": "desconocido"}
    assert [c.dato for c in protegido.candidatos(guardado, nuevo)] == ["drones"]


def _presencia_mala(documento: Documento) -> Documento:
    nuevo = copy.deepcopy(documento)
    nuevo["presencia_dron"] = "no_confirmada"
    nuevo["afirmaciones"] = [a for a in nuevo["afirmaciones"] if a["campo"] != "presencia_dron"]
    nuevo["titulo"] = {"es": "Posible dron en Núremberg", "en": "Possible drone in Nuremberg"}
    fecha = nuevo["estado"]["historial"][-1]["fecha"]
    nuevo["estado"]["actual"] = "notificado"
    nuevo["estado"]["historial"].append(
        {"estado": "notificado", "fecha": fecha, "fuente_id": "gdelt-base"}
    )
    return nuevo


def test_el_titular_y_el_estado_siguen_a_lo_retenido() -> None:
    # EODI-2025-00178, 00472 y EODI-2026-00694: con la presencia retenida pasaba «Posible dron…».
    guardado = ficha()
    veredicto = protegido.juzgar(guardado, _presencia_mala(guardado), [], lambda _: "")
    assert {c.dato for c in veredicto.retenidos} == {"presencia_dron", "estado", "titulo"}
    assert veredicto.permitidos == []


def test_lo_retenido_por_seguir_se_conserva() -> None:
    guardado = ficha()
    malo = _presencia_mala(guardado)
    veredicto = protegido.juzgar(guardado, malo, [], lambda _: "")
    resultado = protegido.conservar(malo, guardado, veredicto.retenidos)
    assert resultado["titulo"] == guardado["titulo"]
    assert resultado["estado"] == guardado["estado"]
    assert resultado["presencia_dron"] == "confirmada"


def test_sin_nada_retenido_el_titular_no_se_retiene() -> None:
    guardado = ficha()
    nuevo = copy.deepcopy(guardado)
    nuevo["titulo"] = {"es": "Dron en Núremberg", "en": "Drone in Nuremberg"}
    veredicto = protegido.juzgar(guardado, nuevo, [], lambda _: "")
    assert veredicto.retenidos == []


def _otra_fuente(documento: Documento, frase: str) -> Documento:
    nuevo = copy.deepcopy(documento)
    fuente = _fuente("gdelt-nueva", ENLACE_NUEVO, "otro.eu", "de", frase, "09:00")
    nuevo["fuentes"].append(fuente)
    return nuevo


def test_la_fuente_nueva_tiene_que_decir_el_valor_nuevo() -> None:
    # EODI-2026-00694: fuentes nuevas literales que no decían el valor al que cambiaba.
    guardado = ficha()
    frase = "Am Flughafen gab es mehrere Drohnen."
    nuevo = _otra_fuente(guardado, frase)
    nuevo["drones"] = {"numero": {"min": 30, "max": 30}}
    nuevo["afirmaciones"] = [a for a in nuevo["afirmaciones"] if a["campo"] != "drones"]
    nuevo["afirmaciones"].append(_afirmacion("drones", {"min": 30, "max": 30}, "gdelt-nueva"))
    assert not protegido.fuente_nueva_con_frase("drones", guardado, nuevo, lambda _: frase)
    bien = _otra_fuente(guardado, "Am Flughafen gab es 30 Drohnen.")
    bien["drones"] = nuevo["drones"]
    bien["afirmaciones"] = nuevo["afirmaciones"]
    assert protegido.fuente_nueva_con_frase(
        "drones", guardado, bien, lambda _: "Am Flughafen gab es 30 Drohnen."
    )


def test_la_fuente_nueva_de_la_presencia_tiene_que_afirmar_ese_valor() -> None:
    guardado = ficha()
    frase = "Die Polizei hat keine Drohne bestätigt."
    nuevo = _otra_fuente(_presencia_mala(guardado), frase)
    nuevo["afirmaciones"].append(_afirmacion("presencia_dron", "confirmada", "gdelt-nueva"))
    assert not protegido.fuente_nueva_con_frase("presencia_dron", guardado, nuevo, lambda _: frase)
    nuevo["afirmaciones"][-1]["valor"] = "no_confirmada"
    assert protegido.fuente_nueva_con_frase("presencia_dron", guardado, nuevo, lambda _: frase)


def test_un_sin_dato_no_lo_dice_ninguna_fuente_nueva() -> None:
    guardado = ficha()
    frase = "Am Flughafen gab es mehrere Drohnen."
    nuevo = _otra_fuente(guardado, frase)
    nuevo["drones"] = {"numero": "desconocido"}
    nuevo["afirmaciones"].append(_afirmacion("drones", "desconocido", "gdelt-nueva"))
    assert not protegido.fuente_nueva_con_frase("drones", guardado, nuevo, lambda _: frase)


# --- rehacer ----------------------------------------------------------------------------------


def _fundida_en_manual(monkeypatch: pytest.MonkeyPatch) -> tuple[Almacen, str, str]:
    destino, fundida = ficha(MANUAL), ficha(OTRA)
    fundida["fuentes"] = [{**f, "id": f"otra-{f['id']}", "enlace": ENLACE_NUEVO}
                          for f in fundida["fuentes"]]  # fmt: skip
    fundida["estado"]["historial"][0]["fuente_id"] = "otra-gdelt-base"
    fundida["estado"]["historial"][1]["fuente_id"] = "otra-gdelt-base-declaracion-1"
    fundida["tiempo"]["origen_inicio"]["fuente_id"] = "otra-gdelt-base"
    for afirmacion in fundida["afirmaciones"]:
        afirmacion["fuente_id"] = f"otra-{afirmacion['fuente_id']}"
    almacen = base(destino, fundida)
    monkeypatch.setattr(almacen, "enlaces_de_fusion", lambda: {})
    guardado = almacen.incidente(OTRA)
    assert guardado is not None
    almacen.guardar_incidente({**guardado, "fusionado_en": MANUAL}, AHORA, VOCABULARIO_MODELOS)
    almacen.registrar_fusion("2026-10-13T14:17Z", OTRA, MANUAL, "prueba", [])
    return almacen, OTRA, MANUAL


def test_rehacer_no_deja_filas_revertidas_con_fichas_fundidas(
    aplicar: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recogida import revision

    almacen, fundida, destino = _fundida_en_manual(monkeypatch)
    revision.abrir_fundidas(almacen, AHORA, VOCABULARIO_MODELOS)
    # La reapertura se retiene: la ficha sigue fundida y su fila no se revierte.
    actual = almacen.incidente(fundida)
    assert actual is not None
    assert actual["fusionado_en"] == destino
    (fila,) = [f for f in almacen.fusiones() if f["absorbido"] == fundida]
    assert fila["revertida"] is False
    assert almacen.controles(f"retenido:{fundida}:reapertura:{destino}")


def test_rehacer_en_observar_abre_y_revierte(monkeypatch: pytest.MonkeyPatch) -> None:
    from recogida import revision

    almacen, fundida, _ = _fundida_en_manual(monkeypatch)
    revision.abrir_fundidas(almacen, AHORA, VOCABULARIO_MODELOS)
    actual = almacen.incidente(fundida)
    assert actual is not None
    assert "fusionado_en" not in actual
    (fila,) = [f for f in almacen.fusiones() if f["absorbido"] == fundida]
    assert fila["revertida"] is True


def test_un_cambio_contra_la_revision_no_cuenta_como_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # EODI-2025-00472: el control bajó la presencia que hoy fija una revisión a mano.
    guardado = ficha()
    monkeypatch.setattr(decidir, "presencias_revisadas",
                        lambda: {guardado["id"]: "confirmada"})  # fmt: skip
    malo = _presencia_mala(guardado)
    assert protegido._hay_revision(malo, "presencia_dron")
    assert not protegido._revisado(malo, "presencia_dron")
    assert protegido._revisado(guardado, "presencia_dron")


def test_un_sin_dato_de_la_referencia_esta_fijado(monkeypatch: pytest.MonkeyPatch) -> None:
    # EODI-2026-00515: un dron que nadie encontró; ninguna frase dice «sin dato».
    guardado = ficha()
    guardado["drones"] = {"numero": "desconocido"}
    monkeypatch.setattr(protegido, "valores_de_referencia",
                        lambda: {guardado["id"]: {"drones": "desconocido"}})  # fmt: skip
    assert protegido._fijado_en_referencia(guardado, "drones")
    guardado["drones"] = {"numero": {"min": 1, "max": 1}}
    assert not protegido._fijado_en_referencia(guardado, "drones")


# --- 3 de noviembre de 2026: intervalos, modelo, cierre, fuentes anteriores y retiradas -------


@pytest.mark.parametrize(
    ("frase", "dicho", "esperado"),
    [
        # EODI-2026-00744/00745: «19 încălcări» no dice un intervalo de 9 a 19 drones.
        ("în octombrie au fost înregistrate 19 încălcări ale spațiului aerian",
         {"min": 9, "max": 19}, False),
        ("între 9 și 19 drone au survolat", {"min": 9, "max": 19}, True),
    ],
)  # fmt: skip
def test_un_intervalo_de_drones_lo_dicen_sus_dos_extremos(
    frase: str, dicho: Any, esperado: bool
) -> None:
    assert protegido.dice_el_dato("drones", frase, dicho) is esperado


def _con_modelo(documento: Documento, modelo: str, frase: str) -> Documento:
    documento = copy.deepcopy(documento)
    documento["fuentes"][0]["frase_origen"] = frase
    documento["drones"] = {**documento["drones"], "modelo": modelo}
    documento["afirmaciones"].append(_afirmacion("modelo_dron", modelo, "gdelt-base"))
    return documento


def test_el_modelo_que_dice_la_frase_esta_protegido() -> None:
    # EODI-2025-00261 volvía a Shahed tras su revisión (1/11/2026).
    guardado = _con_modelo(ficha(), "Gerbera", "Ein Gerbera-Drohne flog über den Flughafen.")
    assert protegido.dice_el_dato("modelo", "Ein Gerbera-Drohne", "Gerbera")
    nuevo = copy.deepcopy(guardado)
    nuevo["drones"]["modelo"] = "Shahed-136"
    veredicto = protegido.juzgar(guardado, nuevo, [], lambda _: "")
    assert "modelo" in {c.dato for c in veredicto.retenidos}
    resultado = protegido.conservar(nuevo, guardado, veredicto.retenidos)
    assert resultado["drones"]["modelo"] == "Gerbera"


def test_otra_redaccion_del_mismo_modelo_no_es_un_cambio() -> None:
    # EODI-2025-00068: «витлов самолет» y «безпилотен летателен апарат тип "витлов самолет"».
    guardado = _con_modelo(ficha(), "витлов самолет", "Това е витлов самолет.")
    nuevo = copy.deepcopy(guardado)
    nuevo["drones"]["modelo"] = 'безпилотен летателен апарат тип "витлов самолет"'
    assert "modelo" not in {c.dato for c in protegido.candidatos(guardado, nuevo)}


def _cierre_nuevo(frase: str) -> tuple[Documento, Documento]:
    guardado = ficha()
    guardado["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    guardado["afirmaciones"] = [
        a for a in guardado["afirmaciones"] if not a["campo"].startswith("cierre")
    ]
    nuevo = _otra_fuente(guardado, frase)
    nuevo["consecuencias"] = {"cierre": {"valor": "si"}}
    nuevo["afirmaciones"].append(_afirmacion("cierre", "si", "gdelt-nueva"))
    return guardado, nuevo


def test_un_cierre_que_ninguna_frase_nombra_se_retiene() -> None:
    # EODI-2026-00725: en Suceava solo hubo una alerta RO-Alert; el cierre fue en Iasi.
    guardado, nuevo = _cierre_nuevo(
        "O avertizare RO-Alert a fost transmisă pentru județul Suceava."
    )
    assert "cierre" in {c.dato for c in protegido.candidatos(guardado, nuevo)}
    guardado, nuevo = _cierre_nuevo("Der Flughafen wurde für 20 Minuten gesperrt.")
    assert "cierre" not in {c.dato for c in protegido.candidatos(guardado, nuevo)}


def _con_nota_anterior(documento: Documento) -> Documento:
    nuevo = _otra_fuente(documento, "Keine Landungen nach Drohnensichtung möglich")
    nuevo["fuentes"][-1]["fecha"] = ejemplos.instante("2026-02-17T11:00Z", "aproximada")
    return nuevo


def test_una_fuente_anterior_al_suceso_junta_dos_sucesos() -> None:
    # EODI-2026-00079: la nota del 17 de febrero de 2026 en la ficha del 11 de agosto.
    guardado = ficha()
    assert protegido.fuentes_anteriores(guardado) == []
    nuevo = _con_nota_anterior(guardado)
    assert protegido.fuentes_anteriores(nuevo) == ["gdelt-nueva"]
    veredicto = protegido.juzgar(guardado, nuevo, [], lambda _: "")
    assert protegido.COHERENCIA in {c.dato for c in veredicto.retenidos}
    assert protegido.conservar(nuevo, guardado, veredicto.retenidos) == guardado
    # Una revisión a mano sí la deja; un día antes (zona horaria) no cuenta.
    revisado = protegido.juzgar(guardado, nuevo, ["recogida.revisados._guardar"], lambda _: "")
    assert revisado.retenidos == []
    cerca = _otra_fuente(guardado, "Drohne am Flughafen")
    cerca["fuentes"][-1]["fecha"] = ejemplos.instante("2026-10-12T20:00Z", "aproximada")
    assert protegido.fuentes_anteriores(cerca) == []


def test_la_auditoria_z_ve_la_fuente_anterior() -> None:
    assert "Z" in auditoria_fichas.COMPROBACIONES
    resultado = auditoria_fichas.auditar([_con_nota_anterior(ficha())])
    assert resultado["Z"] == ["EODI-2026-09600"]


@pytest.mark.parametrize(
    ("pasos", "esperado"),
    [
        (["proceso.extraccion.retirar", "proceso.incursiones.retirar"], True),
        (["proceso.extraccion.retirar", "proceso.extraccion_oficial.revalidar_altas"], True),
        (["proceso.extraccion.retirar", "proceso.extraccion.reconstruir"], True),
        # Un fallo dentro de una reconstrucción no es la decisión de retirar.
        (["proceso.extraccion.retirar", "proceso.extraccion.guardar",
          "proceso.extraccion.reconstruir"], False),
        (["recogida.control_fichas._guardar", "recogida.control_fichas.resolver_sin_fecha"], True),
        (["proceso.extraccion.conservar_publicada"], False),
    ],
)  # fmt: skip
def test_los_caminos_de_retirada(pasos: list[str], esperado: bool) -> None:
    assert protegido.por_decision(pasos) is esperado


def _retirada(documento: Documento) -> Documento:
    nuevo = copy.deepcopy(documento)
    nuevo["retirado"] = {"fecha": ejemplos.instante("2026-10-13T14:17Z", "minuto"),
                         "motivo": "regla", "motivo_en": "rule"}  # fmt: skip
    return nuevo


def test_una_regla_explicita_no_retira_lo_que_cuenta_una_autoridad() -> None:
    # EODI-2024-00002: la alta oficial cuyo día no estaba en su frase.
    pasos = ["proceso.extraccion.retirar", "proceso.extraccion_oficial.revalidar_altas"]
    con_autoridad = ficha()
    veredicto = protegido.juzgar(con_autoridad, _retirada(con_autoridad), pasos, lambda _: "")
    assert "retirado" in {c.dato for c in veredicto.retenidos}
    sin_autoridad = ficha()
    sin_autoridad["fuentes"] = sin_autoridad["fuentes"][:1]
    veredicto = protegido.juzgar(sin_autoridad, _retirada(sin_autoridad), pasos, lambda _: "")
    assert "retirado" not in {c.dato for c in veredicto.retenidos}
    revision = protegido.juzgar(con_autoridad, _retirada(con_autoridad),
                                ["recogida.revisados._guardar"], lambda _: "")  # fmt: skip
    assert revision.retenidos == []


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("Oficialii Aeroportului I\u0061\u0219i anunță că, în urma mesajului RO-Alert referitor "
         "la posibilă incursiune a unei drone, spațiul aerian a fost închis", True),
        ("Nach einer Warnung der Behörden wurde der Flughafen geschlossen", True),
        ("Eine Drohne flog über den Flughafen Hannover", False),
    ],
)  # fmt: skip
def test_el_aeropuerto_que_reacciona_a_una_alerta_no_es_el_lugar(
    frase: str, esperado: bool
) -> None:
    # EODI-2026-00719: la alerta era para el distrito de Iasi; el aeropuerto solo cerró.
    from proceso import control_fichas as reglas

    assert reglas.reacciona_a_una_alerta(frase) is esperado
