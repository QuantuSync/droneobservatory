"""El ciclo de vida de una ficha al escribirla (docs/ciclo_de_vida.md), con el cerrojo en
«aplicar», como producción: el guardado no deja versiones que solo cambian la fecha; el cerrojo
«con cita» no pisa al filtro de entrada; una unión se deshace dejando todo como estaba; una
ficha retirada no vuelve sola."""

import copy
import json
from datetime import timedelta

import pytest

from almacen.base import Almacen
from esquema import Documento
from exportacion import puerta
from modelo import coste
from proceso import incidentes, invariantes, protegido
from proceso.presencia import TABLA_MOTIVOS
from recogida import control_fichas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import _afirmacion, base, ficha, guardar, version_mala
from tests.test_control_fichas import AHORA, _fuente

ID = "EODI-2026-09600"
OTRA = "EODI-2026-09601"


def _historial(almacen: Almacen, id_: str = ID) -> int:
    fila = almacen.conexion.execute(
        "SELECT count(*) FROM historial WHERE tabla = 'incidentes' AND entidad_id = ?", (id_,)
    ).fetchone()
    return int(fila[0])


def _con_fecha(documento: Documento, minutos: int) -> Documento:
    nuevo = copy.deepcopy(documento)
    cuando = (AHORA - timedelta(minutes=minutos)).strftime("%Y-%m-%dT%H:%MZ")
    nuevo["control"]["ultima_actualizacion"] = ejemplos.instante(cuando)
    return nuevo


# --- Escritura idempotente ----------------------------------------------------------------


def test_una_version_que_solo_cambia_la_fecha_no_se_escribe() -> None:
    almacen = base(ficha())
    guardado = almacen.incidente(ID)
    assert guardado is not None
    versiones = _historial(almacen)
    # Lo que hacía cada hora el control con el cierre de EODI-2026-00773: proponer lo mismo con
    # otra fecha.
    assert almacen.guardar_incidente(_con_fecha(guardado, 30), AHORA, VOCABULARIO_MODELOS) is False
    assert almacen.incidente(ID) == guardado and _historial(almacen) == versiones
    # Un cambio de verdad sí se escribe, con su fecha.
    otro = _con_fecha(guardado, 30)
    otro["titulo"] = {"es": "Un dron cierra el aeropuerto", "en": "A drone closes the airport"}
    assert almacen.guardar_incidente(otro, AHORA, VOCABULARIO_MODELOS) is True
    assert _historial(almacen) == versiones + 1
    assert invariantes.versiones_iguales(almacen.cambios_desde("2000-01-01")) == []


def test_lo_que_el_cerrojo_retiene_cada_hora_no_deja_version_ni_motivo() -> None:
    almacen = base(ficha())
    guardado = almacen.incidente(ID)
    assert guardado is not None
    versiones = _historial(almacen)
    ctx = _contexto(almacen)
    for hora in (1, 2, 3):
        # El control propone quitar el número de drones sin ninguna fuente nueva: retenido.
        malo = _con_fecha(version_mala(guardado, "drones"), 10 * hora)
        assert control_fichas._guardar(ctx, guardado, malo, "drones sin dato") is False
    assert almacen.incidente(ID) == guardado
    assert _historial(almacen) == versiones
    assert ctx.resultado.corregidos == {}
    # Queda apuntado una sola vez, no una por hora.
    retenidos = [c for c in almacen.controles(protegido.PREFIJO_RETENIDO) if ":drones:" in c]
    assert len(retenidos) == 1
    motivos = almacen.conexion.execute(
        "SELECT count(*) FROM historial WHERE tabla = ?", (TABLA_MOTIVOS,)
    ).fetchone()
    assert motivos[0] == 0


def _contexto(almacen: Almacen) -> control_fichas.Contexto:
    resultado = control_fichas.Resultado()
    llamador = control_fichas.Llamador(almacen, None, coste.Modo.CONTROL, AHORA, None, resultado)
    return control_fichas.Contexto(
        almacen, AHORA, VOCABULARIO_MODELOS, llamador, resultado, None, None, {}
    )


# --- El cerrojo y el filtro de entrada ----------------------------------------------------


def test_una_ficha_esta_en_el_filtro_solo_si_el_control_no_la_ha_pasado() -> None:
    almacen = base(ficha())
    # Sin cursor del control (una base que no ha pasado por él) ninguna está en el filtro.
    assert almacen.en_el_filtro(ID) is False
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    assert almacen.en_el_filtro(ID) is True
    puerta.dar_pase(almacen, AHORA, [ID])
    assert almacen.en_el_filtro(ID) is False
    # Y una que ya salió en la web no vuelve al filtro aunque pierda el pase.
    almacen.guardar_publicado(ID, puerta.PUBLICADA, "incidentes.geojson", {"id": ID}, {}, {}, "x")
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    assert almacen.en_el_filtro(ID) is False


def test_el_cerrojo_no_devuelve_lo_que_el_filtro_corrige_en_una_ficha_nueva() -> None:
    # EODI-2026-00728 y 00765: el filtro de entrada corregía el día o el lugar de una ficha que
    # aún no había salido y el cerrojo le devolvía el valor «decidido con cita».
    almacen = base(ficha())
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    guardado = almacen.incidente(ID)
    assert guardado is not None
    corregida = version_mala(guardado, "inicio")
    assert almacen.guardar_incidente(corregida, AHORA, VOCABULARIO_MODELOS) is True
    queda = almacen.incidente(ID)
    assert queda is not None and queda["tiempo"]["inicio"] == corregida["tiempo"]["inicio"]
    assert almacen.controles(protegido.PREFIJO_RETENIDO) == {}


def test_el_cerrojo_si_protege_lo_decidido_con_cita_de_una_ficha_publicada() -> None:
    almacen = base(ficha())
    puerta.dar_pase(almacen, AHORA, [ID])
    guardado = almacen.incidente(ID)
    assert guardado is not None
    assert (
        almacen.guardar_incidente(version_mala(guardado, "inicio"), AHORA, VOCABULARIO_MODELOS)
        is False
    )
    assert almacen.incidente(ID) == guardado
    assert any(":inicio:" in c for c in almacen.controles(protegido.PREFIJO_RETENIDO))


def test_en_el_filtro_solo_se_protege_lo_que_fija_una_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Una ficha del nivel manual que sigue en el filtro (EODI-2026-00728): lo que fija una
    # revisión no cambia; lo que solo «dice una frase» es lo que el filtro comprueba, y cambia.
    from proceso import decidir

    monkeypatch.setattr(protegido, "fichas_manuales", lambda: frozenset({ID}))
    almacen = base(ficha())
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    guardado = almacen.incidente(ID)
    assert guardado is not None
    revision = {
        "incidente": ID, "campo": "drones", "valor": {"min": 1, "max": 1}, "cita": "la frase",
        "enlace": guardado["fuentes"][0]["enlace"], "pais": "DE", "motivo": "revisado",
    }  # fmt: skip
    monkeypatch.setattr(decidir, "_revisiones_de_datos", lambda: {ID: {"drones": revision}})
    nueva = version_mala(version_mala(guardado, "drones"), "inicio")
    almacen.guardar_incidente(nueva, AHORA, VOCABULARIO_MODELOS)
    queda = almacen.incidente(ID)
    assert queda is not None and queda["drones"]["numero"] == {"min": 1, "max": 1}
    assert queda["tiempo"]["inicio"] == nueva["tiempo"]["inicio"]


def test_la_correccion_del_filtro_no_es_un_cambio_sin_permiso() -> None:
    # EODI-2026-00778 (11 de noviembre de 2026): el filtro de entrada corrigió una ficha nueva, el
    # cerrojo no retuvo nada (no estaba publicada) y la auditoría X lo contaba como cambio sin
    # permiso: la puerta no la habría dejado salir en 48 horas.
    almacen = base(ficha())
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    guardado = almacen.incidente(ID)
    assert guardado is not None and almacen.en_el_filtro(ID)
    almacen.guardar_incidente(version_mala(guardado, "inicio"), AHORA, VOCABULARIO_MODELOS)
    cambios = almacen.cambios_desde("2000-01-01T00:00:00Z")
    permitidos = protegido.permitidos(almacen.controles(protegido.PREFIJO_PERMITIDO))
    assert almacen.primeras_publicaciones() == {}
    # Como se miraba antes (siempre como publicada), era una X; mirado como el cerrojo, no.
    assert protegido.cambios_sin_permiso(cambios, permitidos) == [f"{ID} inicio"]
    assert protegido.cambios_sin_permiso(cambios, permitidos, None, {}) == []
    assert puerta.marcadas(almacen, AHORA) == {}
    # Publicada después de ese cambio, sigue sin contar; publicada desde antes, sí.
    despues = {ID: "2999-01-01T00:00:00Z"}
    assert protegido.cambios_sin_permiso(cambios, permitidos, None, despues) == []
    assert protegido.cambios_sin_permiso(cambios, permitidos, None, {ID: ""}) == [f"{ID} inicio"]


def test_las_publicadas_al_sembrar_cuentan_desde_siempre() -> None:
    almacen = base(ficha())
    almacen.guardar_publicado(ID, puerta.PUBLICADA, "incidentes.geojson", {"id": ID}, {}, {}, "a")
    almacen.guardar_publicado(
        OTRA, puerta.PUBLICADA, "incidentes.geojson", {"id": OTRA}, {}, {}, "b"
    )
    assert almacen.primeras_publicaciones() == {ID: "", OTRA: "b"}


# --- Unir y deshacer ----------------------------------------------------------------------


def _de_publicacion(id_: str) -> Documento:
    """Una ficha del mismo sitio que solo sabe la fecha de publicación de su noticia."""
    documento = ficha(id_)
    fuente = _fuente(
        "gdelt-tarde", "https://ejemplo.eu/tarde", "ejemplo.eu", "de",
        "Eine Drohne wurde am Flughafen gesehen.", "12:00",
    )  # fmt: skip
    documento["fuentes"] = [fuente]
    documento["presencia_dron"] = "no_confirmada"
    documento["estado"] = {
        "actual": "notificado",
        "historial": [
            {"estado": "notificado", "fecha": fuente["fecha"], "fuente_id": fuente["id"]}
        ],
    }
    documento["tiempo"] = {
        "inicio": ejemplos.instante("2026-10-13T12:00Z", "minuto"),
        "origen_inicio": {"tipo": "publicacion", "motivo": "fecha de la noticia"},
    }
    documento["drones"] = {"numero": "desconocido"}
    documento["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    documento["afirmaciones"] = [_afirmacion("lugar_suceso", {"nombre": "Núremberg"}, fuente["id"])]
    return documento


def _unir(almacen: Almacen, absorbida: str, queda: str, con_instantanea: bool = True) -> None:
    conserva, une = almacen.incidente(queda), almacen.incidente(absorbida)
    assert conserva is not None and une is not None
    nuevo, aportadas = incidentes.absorber(conserva, une, AHORA)
    guardar(almacen, nuevo)
    guardar(almacen, {**une, "fusionado_en": queda})
    almacen.registrar_fusion(
        "2026-10-13T14:17Z", absorbida, queda, "regla", aportadas,
        incidentes.instantanea(almacen, conserva, une) if con_instantanea else None,
    )  # fmt: skip


@pytest.fixture
def separables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deshacer una unión es cosa de una revisión o de una separación: aquí, una separación."""
    monkeypatch.setattr(protegido, "es_separacion", lambda *_: True)


@pytest.mark.parametrize("con_instantanea", [True, False])
def test_deshacer_una_union_devuelve_el_dia_que_la_union_copio(
    con_instantanea: bool, separables: None
) -> None:
    # Fallo 5 del repaso del 10/11/2026: `revertir` quitaba las fuentes del absorbido pero dejaba
    # en la que queda el día que la unión le había copiado: el del otro suceso. Sin instantánea
    # (las uniones de antes), se saca del historial de la ficha.
    almacen = base(_de_publicacion(ID), ficha(OTRA))
    antes = almacen.incidente(ID)
    absorbida_antes = almacen.incidente(OTRA)
    assert antes is not None and absorbida_antes is not None
    _unir(almacen, OTRA, ID, con_instantanea)
    unida = almacen.incidente(ID)
    assert unida is not None
    # La unión le copió el día escrito por la fuente del otro, su cierre... y sus fuentes.
    assert unida["tiempo"]["inicio"] == absorbida_antes["tiempo"]["inicio"]
    assert len(unida["fuentes"]) == 3
    incidentes.revertir(almacen, OTRA, AHORA + timedelta(hours=1), VOCABULARIO_MODELOS)
    queda, vuelve = almacen.incidente(ID), almacen.incidente(OTRA)
    assert queda is not None and vuelve is not None
    assert "fusionado_en" not in vuelve
    for dato in ("tiempo", "presencia_dron", "estado", "drones", "consecuencias", "fuentes"):
        assert queda.get(dato) == antes.get(dato), dato
        assert vuelve.get(dato) == absorbida_antes.get(dato), dato
    assert [f["revertida"] for f in almacen.fusiones()] == [True]


def test_deshacer_una_union_respeta_lo_que_cambio_despues(separables: None) -> None:
    almacen = base(_de_publicacion(ID), ficha(OTRA))
    _unir(almacen, OTRA, ID)
    unida = almacen.incidente(ID)
    assert unida is not None
    # Después de la unión, otra vía (una fuente nueva, una revisión) le pone otro día.
    despues = copy.deepcopy(unida)
    despues["tiempo"] = {
        "inicio": ejemplos.instante("2026-10-12T00:00Z", "dia"),
        "origen_inicio": {"tipo": "explicita", "motivo": "revisado"},
    }
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = ? WHERE id = ?", (json.dumps(despues), ID)
    )
    incidentes.revertir(almacen, OTRA, AHORA + timedelta(hours=1), VOCABULARIO_MODELOS)
    queda = almacen.incidente(ID)
    assert queda is not None and queda["tiempo"]["inicio"] == despues["tiempo"]["inicio"]


def test_la_union_que_el_cerrojo_retendria_no_se_intenta(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fallo 4 del repaso: `control_fichas.unir` guardaba la que queda con las fuentes de la otra
    # y el cerrojo la devolvía, en cada pasada (como la regla de fusión con 00747 en 00743).
    monkeypatch.setattr(protegido, "fichas_manuales", lambda: frozenset({OTRA}))
    almacen = base(_de_publicacion(ID), ficha(OTRA))
    conserva, une = almacen.incidente(ID), almacen.incidente(OTRA)
    assert conserva is not None and une is not None
    versiones = _historial(almacen) + _historial(almacen, OTRA)
    assert (
        control_fichas.unir(almacen, conserva, une, "el mismo", AHORA, VOCABULARIO_MODELOS) is None
    )
    assert _historial(almacen) + _historial(almacen, OTRA) == versiones
    assert almacen.fusiones() == []


def test_un_cierre_retenido_en_una_ficha_sin_cierre_no_rompe_el_guardado() -> None:
    # Al pasar las pruebas a «aplicar» (10/11/2026): un cierre nuevo retenido en una ficha que no
    # tenía cierre dejaba un cierre vacío, lo retenido no validaba y el cerrojo se quedaba con la
    # versión guardada entera, con lo que la que queda en una unión perdía las fuentes de la otra.
    sin_cierre = ficha()
    del sin_cierre["consecuencias"]
    sin_cierre["afirmaciones"] = [
        a for a in sin_cierre["afirmaciones"] if not a["campo"].startswith("cierre")
    ]
    sin_cierre["fuentes"][0]["frase_origen"] = "Um 08:30 Uhr sah die Polizei eine Drohne."
    almacen = base(sin_cierre)
    guardado = almacen.incidente(ID)
    assert guardado is not None
    nuevo = copy.deepcopy(guardado)
    nuevo["consecuencias"] = {"cierre": {"valor": "si"}}
    nuevo["titulo"] = {"es": "Un dron sobre el aeropuerto", "en": "A drone over the airport"}
    almacen.guardar_incidente(nuevo, AHORA, VOCABULARIO_MODELOS)
    queda = almacen.incidente(ID)
    assert queda is not None
    # El cierre que ninguna frase nombra se retiene (la ficha sigue sin cierre, y el titular con
    # ella), y el cerrojo no falla: lo retenido valida.
    assert "cierre" not in (queda.get("consecuencias") or {})
    assert any(":cierre:" in c for c in almacen.controles(protegido.PREFIJO_RETENIDO))
    assert almacen.controles(protegido.PREFIJO_FALLO) == {}


# --- Retirada firme -----------------------------------------------------------------------


def _retirar(almacen: Almacen, id_: str = ID) -> Documento:
    documento = almacen.incidente(id_)
    assert documento is not None
    retirada = {
        **documento,
        "retirado": {"fecha": ejemplos.instante("2026-10-13T14:17Z"), "motivo": "No es un suceso."},
    }
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = ? WHERE id = ?", (json.dumps(retirada), id_)
    )
    return documento


def test_una_ficha_retirada_no_vuelve_al_rehacerla() -> None:
    # Fallo 9 del repaso: la versión que rehace una extracción sale sin `retirado` y la ficha
    # retirada volvía a la web.
    almacen = base(ficha())
    almacen.guardar_publicado(ID, puerta.PUBLICADA, "incidentes.geojson", {"id": ID}, {}, {}, "x")
    viva = _retirar(almacen)
    rehecha = copy.deepcopy(viva)
    rehecha["titulo"] = {"es": "Un dron cierra el aeropuerto", "en": "A drone closes the airport"}
    almacen.guardar_incidente(rehecha, AHORA, VOCABULARIO_MODELOS)
    queda = almacen.incidente(ID)
    assert queda is not None and queda["retirado"]["motivo"] == "No es un suceso."
    assert [c.split(":")[2] for c in almacen.controles(f"retenido:{ID}:vuelta")] == ["vuelta"]


def test_la_que_nunca_salio_vuelve_si_llega_un_articulo_nuevo() -> None:
    # La nota oficial que llega después de que el filtro retirase la ficha por falta de fecha.
    almacen = base(ficha())
    viva = _retirar(almacen)
    # Rehecha con las mismas fuentes: sigue retirada.
    almacen.guardar_incidente(copy.deepcopy(viva), AHORA, VOCABULARIO_MODELOS)
    assert "retirado" in (almacen.incidente(ID) or {})
    # Con un artículo que la retirada no tenía: vuelve, y pasará otra vez por el filtro.
    con_nota = copy.deepcopy(viva)
    con_nota["fuentes"].append(
        _fuente(
            "gdelt-nota",
            "https://ejemplo.eu/nota",
            "ejemplo.eu",
            "de",
            "Die Polizei bestätigte am Mittag den Vorfall.",
            "12:00",
        )
    )
    almacen.guardar_incidente(con_nota, AHORA, VOCABULARIO_MODELOS)
    assert "retirado" not in (almacen.incidente(ID) or {})


def test_una_revision_a_mano_si_vuelve_a_publicar_la_retirada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    almacen = base(ficha())
    almacen.guardar_publicado(ID, puerta.PUBLICADA, "incidentes.geojson", {"id": ID}, {}, {}, "x")
    viva = _retirar(almacen)
    monkeypatch.setattr(protegido, "pila", lambda: ["recogida.revisados._reponer"])
    almacen.guardar_incidente(copy.deepcopy(viva), AHORA, VOCABULARIO_MODELOS)
    assert "retirado" not in (almacen.incidente(ID) or {})
