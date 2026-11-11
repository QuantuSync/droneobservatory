"""La puerta de la publicación (exportacion/puerta.py, docs/ciclo_de_vida.md): cerrada por
defecto. Una versión entra en lo publicado solo con el pase del control en esta pasada, sin marca
de la auditoría de protección y sin romper una invariante; si no, queda la última versión buena y
la que nunca salió no sale. Una ficha unida o retirada conserva su dirección."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from exportacion import geojson, publicar, puerta
from proceso import auditoria_fichas, invariantes, protegido
from recogida import vigilancia, visitas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import ficha, version_mala

AHORA = datetime(2026, 10, 13, 14, 17, tzinfo=UTC)
ID = "EODI-2026-09600"
OTRA = "EODI-2026-09601"

# El cierre publicado: 30 minutos en la versión buena, 45 en la que no pasa.
BUENO, MALO = 30, 45


def _con_cierre(documento: Documento, minutos: int) -> Documento:
    documento = copy.deepcopy(documento)
    documento["consecuencias"] = {
        "cierre": {"valor": "si", "minutos": {"min": minutos, "max": minutos}}
    }
    return documento


def _minima(id_: str = ID) -> Documento:
    """Una ficha mínima que se publica (sin punto, en su región)."""
    documento = ejemplos.incidente_minimo()
    documento["id"] = id_
    documento["lugar"] = {"pais": "BE", "nivel": "region", "region": "Limburg"}
    return documento


def _base(minutos: int, pase: bool = True) -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_con_cierre(_minima(), minutos), AHORA, VOCABULARIO_MODELOS)
    if pase:
        puerta.dar_pase(almacen, AHORA, [ID])
    return almacen


def _cambiar(almacen: Almacen, minutos: int) -> None:
    documento = almacen.incidente(ID)
    assert documento is not None
    almacen.guardar_incidente(_con_cierre(documento, minutos), AHORA, VOCABULARIO_MODELOS)


def _publicadas(directorio: Path) -> dict[str, Documento]:
    salida: dict[str, Documento] = {}
    for nombre, lista in puerta.LISTAS.items():
        datos = json.loads((directorio / nombre).read_text(encoding="utf-8"))
        salida.update({puerta._id(e): dict(e) for e in datos[lista]})
    return salida


def _mapa(directorio: Path) -> Documento:
    return dict(json.loads((directorio / publicar.INCIDENTES).read_text(encoding="utf-8")))


def _minutos(entrada: Documento | None) -> Any:
    assert entrada is not None
    return (entrada.get("properties") or entrada)["consecuencias"]["cierre"]["minutos"]["max"]


@pytest.fixture
def sin_marcas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {})


# --- Cerrado por defecto ------------------------------------------------------------------


def test_sin_pase_del_control_la_ficha_nueva_no_sale(tmp_path: Path, sin_marcas: None) -> None:
    # El fallo de fondo: lo que el control no llegaba a retener se publicaba. Ahora, al revés:
    # sin pase no hay fila.
    almacen = _base(BUENO, pase=False)
    puerta.dar_pase(almacen, AHORA)  # el control terminó, pero esta ficha no lo ha pasado
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _publicadas(tmp_path) == {}
    assert almacen.publicado() == {}
    cursor = almacen.cursor(puerta.CURSOR) or {}
    # Es la retención normal de una ficha nueva: no es una ficha en su versión anterior.
    assert cursor["sin_pase"] == [ID] and cursor["sustituidas"] == []


def test_si_el_control_no_corre_nada_nuevo_se_publica(tmp_path: Path, sin_marcas: None) -> None:
    # Una base en la que el control no ha corrido nunca: ninguna ficha sale.
    almacen = _base(BUENO, pase=False)
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _publicadas(tmp_path) == {}


def test_si_el_control_no_termina_en_esta_pasada_lo_publicado_no_cambia(
    tmp_path: Path, sin_marcas: None
) -> None:
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _minutos(_publicadas(tmp_path)[ID]) == BUENO
    # Una hora después la ficha cambia y llega otra nueva, pero el control falla antes de acabar:
    # su cursor sigue con la pasada anterior.
    despues = AHORA + timedelta(hours=1)
    _cambiar(almacen, MALO)
    almacen.guardar_incidente(_con_cierre(_minima(OTRA), BUENO), despues, VOCABULARIO_MODELOS)
    publicar.publicar(almacen, despues, tmp_path)
    assert set(_publicadas(tmp_path)) == {ID}
    assert _minutos(_publicadas(tmp_path)[ID]) == BUENO
    cursor = almacen.cursor(puerta.CURSOR) or {}
    assert cursor["terminado"] is False
    # Con el control terminado, la versión nueva y la ficha nueva (ya con pase) entran.
    puerta.dar_pase(almacen, despues, [OTRA])
    publicar.publicar(almacen, despues, tmp_path)
    assert set(_publicadas(tmp_path)) == {ID, OTRA}
    assert _minutos(_publicadas(tmp_path)[ID]) == MALO


def test_sin_auditoria_ninguna_version_nueva_pasa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def falla(*_: Any) -> dict[str, list[str]]:
        raise RuntimeError("auditoría rota")

    almacen = _base(BUENO)
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {})
    publicar.publicar(almacen, AHORA, tmp_path)
    _cambiar(almacen, MALO)
    monkeypatch.setattr(puerta, "marcadas", falla)
    publicar.publicar(almacen, AHORA, tmp_path)
    # Antes, si la auditoría fallaba salía lo de la base; ahora queda lo publicado.
    assert _minutos(_publicadas(tmp_path)[ID]) == BUENO
    (retenida,) = (almacen.cursor(puerta.CURSOR) or {})["sustituidas"]
    assert retenida["comprobaciones"] == [puerta.SIN_AUDITORIA]


def test_si_la_puerta_falla_entera_los_incidentes_quedan_como_estaban(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sin_marcas: None
) -> None:
    def falla(*_: Any, **__: Any) -> puerta.Resultado:
        raise RuntimeError("puerta rota")

    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    antes = (tmp_path / publicar.SIN_UBICACION).read_bytes()
    _cambiar(almacen, MALO)
    monkeypatch.setattr(puerta, "pasar", falla)
    fallidos: list[str] = []
    publicar.publicar(almacen, AHORA, tmp_path, fallidos=fallidos)
    assert (tmp_path / publicar.SIN_UBICACION).read_bytes() == antes
    assert any("puerta" in f for f in fallidos)


# --- La última versión buena --------------------------------------------------------------


@pytest.mark.parametrize("comprobacion", protegido.AUDITORIA)
def test_la_ficha_marcada_sale_en_su_ultima_version_buena(
    comprobacion: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = _base(BUENO)
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {})
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _minutos(_publicadas(tmp_path)[ID]) == BUENO
    # La base cambia y la auditoría la marca: sale lo de antes.
    _cambiar(almacen, MALO)
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {ID: [comprobacion]})
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _minutos(_publicadas(tmp_path)[ID]) == BUENO
    (sustituida,) = (almacen.cursor(puerta.CURSOR) or {})["sustituidas"]
    assert sustituida["id"] == ID and sustituida["comprobaciones"] == [comprobacion]
    assert sustituida["origen"] == puerta.BUENA
    assert "consecuencias" in sustituida["diferencias"]
    # Sin marca vuelve a salir lo de la base, y esa pasa a ser la versión buena.
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {})
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _minutos(_publicadas(tmp_path)[ID]) == MALO
    assert (almacen.cursor(puerta.CURSOR) or {})["sustituidas"] == []


def test_la_marcada_que_nunca_se_publico_no_sale_y_se_apunta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = _base(BUENO)
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {ID: ["W"]})
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _publicadas(tmp_path) == {}
    (retenida,) = (almacen.cursor(puerta.CURSOR) or {})["sustituidas"]
    assert retenida["origen"] == puerta.NINGUNA
    assert puerta.linea(retenida)[0] == f"{ID} no publicada"


def test_una_ficha_que_no_valida_no_para_a_las_demas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sin_marcas: None
) -> None:
    # Antes, una ficha que no validaba al exportar dejaba sin generar el fichero entero.
    almacen = _base(BUENO)
    almacen.guardar_incidente(_con_cierre(_minima(OTRA), BUENO), AHORA, VOCABULARIO_MODELOS)
    puerta.dar_pase(almacen, AHORA, [OTRA])
    publicar.publicar(almacen, AHORA, tmp_path)
    assert set(_publicadas(tmp_path)) == {ID, OTRA}
    _cambiar(almacen, MALO)
    normal = geojson._no_publicable

    def una_no_valida(incidente: Documento, *resto: Any) -> str | None:
        if incidente["id"] == OTRA:
            return f"{geojson.NO_VALIDA}la ficha de prueba"
        return normal(incidente, *resto)

    monkeypatch.setattr(geojson, "_no_publicable", una_no_valida)
    fallidos: list[str] = []
    publicar.publicar(almacen, AHORA, tmp_path, fallidos=fallidos)
    assert fallidos == []
    # La que no valida sigue en la web como estaba; la otra sale con su versión nueva.
    assert set(_publicadas(tmp_path)) == {ID, OTRA}
    assert _minutos(_publicadas(tmp_path)[ID]) == MALO
    (retenida,) = (almacen.cursor(puerta.CURSOR) or {})["sustituidas"]
    assert retenida["id"] == OTRA and retenida["comprobaciones"] == [puerta.SIN_ENTRADA]
    assert "no valida" in retenida["diferencias"]["motivo"][1]


def test_dos_publicaciones_seguidas_sin_cambios_no_escriben_nada(
    tmp_path: Path, sin_marcas: None
) -> None:
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    filas = almacen.publicado()
    cursor = almacen.cursor(puerta.CURSOR)
    cambios = almacen.conexion.total_changes
    despues = AHORA + timedelta(hours=1)
    puerta.dar_pase(almacen, despues)
    del_pase = almacen.conexion.total_changes - cambios
    cambiados = publicar.publicar(almacen, despues, tmp_path)
    assert cambiados == []
    assert almacen.publicado() == filas
    assert almacen.cursor(puerta.CURSOR) == cursor
    # Lo único que cambia en la base es el pase de la pasada.
    assert almacen.conexion.total_changes - cambios == del_pase


# --- Ninguna dirección en 404 -------------------------------------------------------------


def _unir(almacen: Almacen, absorbida: str, destino: str) -> None:
    """La ficha, fundida en la otra, escrita tal cual: aquí se prueba la puerta, no el cerrojo
    (que con las fichas de ejemplo retendría la unión por la fecha de su fuente)."""
    documento = almacen.incidente(absorbida)
    assert documento is not None
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = ? WHERE id = ?",
        (json.dumps({**documento, "fusionado_en": destino}), absorbida),
    )


def test_la_unida_a_una_ficha_sin_publicar_sigue_saliendo_como_estaba(
    tmp_path: Path, sin_marcas: None
) -> None:
    # EODI-2026-00746, 6/11/2026: publicada, quedó fundida en la 00760, recién dada de alta.
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    almacen.guardar_incidente(_con_cierre(_minima(OTRA), MALO), AHORA, VOCABULARIO_MODELOS)
    _unir(almacen, ID, OTRA)
    publicar.publicar(almacen, AHORA, tmp_path)
    # La nueva no tiene pase: no sale, y la publicada no desaparece ni redirige a una 404.
    assert set(_publicadas(tmp_path)) == {ID}
    assert "unidos" not in _mapa(tmp_path)
    (retenida,) = (almacen.cursor(puerta.CURSOR) or {})["sustituidas"]
    assert retenida["comprobaciones"] == [puerta.UNIDA_A_NO_PUBLICADA]
    # Cuando la que queda pasa el control, la unida redirige a ella.
    puerta.dar_pase(almacen, AHORA, [OTRA])
    publicar.publicar(almacen, AHORA, tmp_path)
    assert set(_publicadas(tmp_path)) == {OTRA}
    assert _mapa(tmp_path)["unidos"] == {ID: OTRA}
    assert almacen.estados_publicados() == {ID: puerta.UNIDA, OTRA: puerta.PUBLICADA}
    assert invariantes.rotas(invariantes.comprobar(almacen, AHORA)) == {}


def test_la_retirada_explica_su_retirada(tmp_path: Path, sin_marcas: None) -> None:
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    documento = almacen.incidente(ID)
    assert documento is not None
    retirado = {
        "fecha": ejemplos.instante("2026-10-13T14:17Z"),
        "motivo": "No es un suceso: la nota cuenta un simulacro.",
        "motivo_en": "Not an event: the article reports a drill.",
    }
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = ? WHERE id = ?",
        (json.dumps({**documento, "retirado": retirado}), ID),
    )
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _publicadas(tmp_path) == {}
    assert _mapa(tmp_path)["retirados"] == {
        ID: {
            "fecha": "2026-10-13T14:17Z",
            "motivo": {
                "es": "No es un suceso: la nota cuenta un simulacro.",
                "en": "Not an event: the article reports a drill.",
            },
        }
    }
    assert almacen.estados_publicados() == {ID: puerta.RETIRADA}
    assert invariantes.rotas(invariantes.comprobar(almacen, AHORA)) == {}


def test_el_motivo_de_una_regla_interna_no_se_publica() -> None:
    # Solo en español y con los pasos del proceso: sale el motivo general, en los dos idiomas.
    interna = {"fecha": ejemplos.instante("2026-10-13T14:17Z"), "motivo": "copia numerada de más"}
    detalle = puerta.detalle_de_retirada(interna, "2026-10-13T15:00:00Z")
    assert detalle == {"fecha": "2026-10-13T14:17Z", "motivo": puerta.MOTIVO_SIN_MOTIVO}
    # La nota del paso interno que la decidió no es parte de la explicación pública.
    repaso = {
        "fecha": ejemplos.instante("2026-10-28T18:53Z"),
        "motivo": "Fecha del suceso desconocida: la noticia cuenta un suceso anterior sin decir "
        "cuándo fue (repaso de entrada con el experto).",
        "motivo_en": "Unknown event date: the report tells of an earlier event without saying "
        "when it happened (entry review by the expert model).",
    }
    assert puerta.detalle_de_retirada(repaso, "x")["motivo"] == {
        "es": "Fecha del suceso desconocida: la noticia cuenta un suceso anterior sin decir "
        "cuándo fue.",
        "en": "Unknown event date: the report tells of an earlier event without saying when it "
        "happened.",
    }
    # Sin fecha en la retirada (las más antiguas la guardan de otra forma), la de la publicación.
    sin_fecha = puerta.detalle_de_retirada({"fecha": "x", "motivo": "m"}, "2026-10-13T15:00:00Z")
    assert sin_fecha["fecha"] == "2026-10-13T15:00:00Z"


def test_la_retirada_que_nunca_salio_no_tiene_direccion(tmp_path: Path, sin_marcas: None) -> None:
    almacen = _base(BUENO, pase=False)
    puerta.dar_pase(almacen, AHORA)
    documento = almacen.incidente(ID)
    assert documento is not None
    retirado = {"fecha": ejemplos.instante("2026-10-13T14:17Z"), "motivo": "No verificable."}
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = ? WHERE id = ?",
        (json.dumps({**documento, "retirado": retirado}), ID),
    )
    publicar.publicar(almacen, AHORA, tmp_path)
    assert "retirados" not in _mapa(tmp_path) and almacen.publicado() == {}


def test_el_enlace_a_un_relacionado_sin_publicar_no_sale(tmp_path: Path, sin_marcas: None) -> None:
    # EODI-2025-00066 enlazaba a la 00444, retenida (20 de octubre de 2026).
    filas: dict[str, Documento] = {
        ID: {"id": ID, "estado": puerta.PUBLICADA, "fichero": publicar.SIN_UBICACION,
             "entrada": {"id": ID, "relacionados": [{"id": OTRA}, {"id": "EODI-2026-09602"}]},
             "detalle": {}},
        "EODI-2026-09602": {"id": "EODI-2026-09602", "estado": puerta.PUBLICADA,
                            "fichero": publicar.SIN_UBICACION,
                            "entrada": {"id": "EODI-2026-09602"}, "detalle": {}},
    }  # fmt: skip
    generados: dict[str, Documento] = {publicar.SIN_UBICACION: {"incidentes": []}}
    (primera, _) = puerta.ficheros(generados, filas, {})[publicar.SIN_UBICACION]["incidentes"]
    assert primera["relacionados"] == [{"id": "EODI-2026-09602"}]
    # La fila guarda la entrada entera: el enlace vuelve solo cuando la otra se publica.
    assert len(filas[ID]["entrada"]["relacionados"]) == 2


def test_la_siembra_pone_lo_ya_publicado_una_sola_vez(tmp_path: Path, sin_marcas: None) -> None:
    # La migración: la tabla vacía se llena con los ficheros que ya están publicados.
    origen = _base(BUENO)
    publicar.publicar(origen, AHORA, tmp_path)
    almacen = _base(MALO, pase=False)
    assert puerta.sembrar(almacen, AHORA, tmp_path) == 1
    assert _minutos(almacen.publicado()[ID]["entrada"]) == BUENO
    assert puerta.sembrar(almacen, AHORA, tmp_path) == 0
    # Sin ficheros no siembra nada.
    assert puerta.sembrar(_base(MALO), AHORA, tmp_path / "vacia") == 0


def test_la_siembra_va_antes_de_guardar_nada(tmp_path: Path, sin_marcas: None) -> None:
    # Reproducción del 10 de noviembre de 2026: con la tabla aún vacía, una ficha publicada que el
    # control no cuenta entre las vistas (una unida de hace tiempo) parecía nueva en el filtro y
    # el cerrojo no le guardaba lo «con cita». Sembrada, ya no está en el filtro.
    origen = _base(BUENO)
    publicar.publicar(origen, AHORA, tmp_path)
    almacen = _base(MALO, pase=False)
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    assert almacen.en_el_filtro(ID) is True
    assert puerta.sembrar(almacen, AHORA, tmp_path) == 1
    assert almacen.en_el_filtro(ID) is False
    # Y la recogida horaria la hace lo primero, antes del primer paso que guarda fichas.
    import inspect

    from recogida import horaria

    codigo = inspect.getsource(horaria.principal)
    assert 0 < codigo.index("puerta.sembrar") < codigo.index("suelo_europeo.paso_horario")


# --- La auditoría de protección -----------------------------------------------------------


@pytest.mark.parametrize(
    ("comprobacion", "entrada"),
    [
        ("P", ID),
        ("R", f"{ID} presencia_dron: confirmada ≠ no_confirmada"),
        ("V", f"EODI-2026-09601→{ID}"),
        ("W", f"{ID} inicio"),
        ("X", f"{ID} lugar"),
    ],
)  # fmt: skip
def test_cada_comprobacion_marca_la_ficha_publicada(
    comprobacion: str, entrada: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    resultado: dict[str, list[str]] = {c: [] for c in auditoria_fichas.COMPROBACIONES}
    resultado[comprobacion] = [entrada]
    monkeypatch.setattr(auditoria_fichas, "auditar", lambda *_a, **_k: resultado)
    monkeypatch.setattr(puerta, "x_vigentes", lambda *_: resultado["X"])
    assert puerta.marcadas(Almacen.abrir(), AHORA) == {ID: [comprobacion]}


def _revision(monkeypatch: pytest.MonkeyPatch, dato: str, valor: Any, pais: str = "DE") -> None:
    """Una revisión a mano de `dato` de la ficha (incidentes_revisados.json, «datos»)."""
    from proceso import decidir

    revision = {
        "incidente": ID,
        "campo": dato,
        "valor": valor,
        "cita": "la frase",
        "enlace": ficha()["fuentes"][0]["enlace"],
        "pais": pais,
        "motivo": "revisado",
    }
    monkeypatch.setattr(decidir, "_revisiones_de_datos", lambda: {ID: {dato: revision}})


def _x(almacen: Almacen) -> tuple[list[str], list[str]]:
    """La X de la auditoría y la de la puerta, con lo que tiene ahora la base."""
    cambios = almacen.cambios_desde("2000-01-01")
    permitidos = protegido.permitidos(almacen.controles(protegido.PREFIJO_PERMITIDO))
    auditoria = auditoria_fichas.auditar(almacen.incidentes(), cambios, permitidos=permitidos)
    actuales = {str(d["id"]): d for d in almacen.incidentes()}
    return auditoria["X"], puerta.x_vigentes(cambios, permitidos, actuales)


@pytest.fixture
def en_observar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Para guardar un cambio sin permiso y ver que la auditoría lo marca: en «aplicar» el
    cerrojo no lo deja llegar a la base."""
    monkeypatch.setattr(protegido, "modo", lambda *_: protegido.OBSERVAR)


def test_la_auditoria_real_marca_un_cambio_sin_permiso(en_observar: None) -> None:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ficha(ID), AHORA, VOCABULARIO_MODELOS)
    documento = almacen.incidente(ID)
    assert documento is not None
    # La ficha ya ha salido en la web: de una que sigue en el filtro, X no cuenta lo «con cita».
    almacen.guardar_publicado(ID, puerta.PUBLICADA, "incidentes.geojson", {"id": ID}, {}, {}, "x")
    almacen.guardar_incidente(version_mala(documento, "drones"), AHORA, VOCABULARIO_MODELOS)
    assert "X" in puerta.marcadas(almacen, datetime.now(UTC)).get(ID, [])
    # Deshecho el cambio (una revisión, el control), ya no deja la ficha en su versión anterior.
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    assert "X" not in puerta.marcadas(almacen, datetime.now(UTC)).get(ID, [])


def test_x_no_cuenta_un_cambio_malo_que_una_revision_ya_deshizo(
    monkeypatch: pytest.MonkeyPatch, en_observar: None
) -> None:
    # EODI-2026-00719 y 00022, 3/11/2026: el cambio malo del 2/11 (el inicio sin su hora) lo
    # deshizo una revisión con cita; X lo seguía contando 48 horas y la ficha quedaba en su
    # versión anterior, tapando la corrección.
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ficha(ID), AHORA, VOCABULARIO_MODELOS)
    bueno = almacen.incidente(ID)
    assert bueno is not None
    almacen.guardar_incidente(version_mala(bueno, "inicio"), AHORA, VOCABULARIO_MODELOS)
    assert _x(almacen) == ([f"{ID} inicio"], [f"{ID} inicio"])
    _revision(monkeypatch, "inicio", bueno["tiempo"]["inicio"])
    almacen.guardar_incidente(bueno, AHORA, VOCABULARIO_MODELOS)
    assert _x(almacen) == ([], [])
    cambios = almacen.cambios_desde("2000-01-01")
    assert protegido.cambios_sin_permiso(cambios, frozenset()) == [f"{ID} inicio"]
    assert "X" not in puerta.marcadas(almacen, datetime.now(UTC)).get(ID, [])


def test_x_no_cuenta_el_valor_que_fija_una_revision_aunque_sea_el_del_cambio_malo(
    monkeypatch: pytest.MonkeyPatch, en_observar: None
) -> None:
    # EODI-2026-00079, 3/11/2026: el valor actual es el correcto y coincide con el del cambio malo.
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ficha(ID), AHORA, VOCABULARIO_MODELOS)
    bueno = almacen.incidente(ID)
    assert bueno is not None
    almacen.guardar_incidente(version_mala(bueno, "drones"), AHORA, VOCABULARIO_MODELOS)
    assert _x(almacen) == ([f"{ID} drones"], [f"{ID} drones"])
    _revision(monkeypatch, "drones", "desconocido")
    assert _x(almacen) == ([], [])
    assert puerta.marcadas(almacen, datetime.now(UTC)).get(ID) is None


def test_x_no_cuenta_lo_que_vuelve_al_valor_de_antes(en_observar: None) -> None:
    # EODI-2026-00322, 1/11/2026: la ficha acabó como empezó y ese guardado no es un cambio.
    almacen = Almacen.abrir()
    almacen.guardar_incidente(ficha(ID), AHORA, VOCABULARIO_MODELOS)
    bueno = almacen.incidente(ID)
    assert bueno is not None
    almacen.guardar_incidente(version_mala(bueno, "drones"), AHORA, VOCABULARIO_MODELOS)
    malo = almacen.incidente(ID)
    assert malo is not None
    almacen.guardar_incidente({**malo, "drones": bueno["drones"]}, AHORA, VOCABULARIO_MODELOS)
    assert _x(almacen) == ([], [])


# --- Invariantes --------------------------------------------------------------------------


def test_i1_una_fila_publicada_sin_pase_se_ve(tmp_path: Path, sin_marcas: None) -> None:
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    assert invariantes.comprobar(almacen, AHORA)[invariantes.I1] == []
    # Algo quita el pase por fuera del control (no debería poder pasar): se ve.
    almacen.guardar_cursor(puerta.CURSOR_CONTROL, {"vistos": {}, "pasada": puerta._iso(AHORA)})
    assert invariantes.comprobar(almacen, AHORA)[invariantes.I1] == [ID]


def test_i2_una_fila_unida_a_nada_se_ve() -> None:
    filas = {ID: {"id": ID, "estado": puerta.UNIDA, "fichero": publicar.INCIDENTES,
                  "entrada": {"id": ID}, "detalle": {"destino": OTRA}}}  # fmt: skip
    assert invariantes.sin_direccion(filas, {}) == [ID]
    filas[OTRA] = {"id": OTRA, "estado": puerta.PUBLICADA, "fichero": publicar.INCIDENTES,
                   "entrada": {"id": OTRA}, "detalle": {}}  # fmt: skip
    assert invariantes.sin_direccion(filas, {}) == []
    # Una retirada sin motivo no explica nada.
    filas[OTRA] = {**filas[OTRA], "estado": puerta.RETIRADA, "detalle": {"motivo": {"es": ""}}}
    assert invariantes.sin_direccion(filas, {}) == [ID, OTRA]


def test_i3_un_dato_revisado_distinto_de_su_revision_no_pasa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sin_marcas: None
) -> None:
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    bueno = _publicadas(tmp_path)[ID]
    # La revisión dice un dron y la base tiene siete (escrito por fuera del guardado).
    _revision(monkeypatch, "drones", {"min": 1, "max": 1}, pais="BE")
    documento = almacen.incidente(ID)
    assert documento is not None
    otro = copy.deepcopy(documento)
    otro["drones"] = {**otro.get("drones", {}), "numero": {"min": 7, "max": 7}}
    assert invariantes.de_ficha(otro) == [invariantes.I3]
    almacen.conexion.execute(
        "UPDATE incidentes SET documento = ? WHERE id = ?", (json.dumps(otro), ID)
    )
    publicar.publicar(almacen, AHORA, tmp_path)
    assert _publicadas(tmp_path)[ID] == bueno
    (retenida,) = (almacen.cursor(puerta.CURSOR) or {})["sustituidas"]
    assert retenida["comprobaciones"] == [invariantes.I3]
    # Guardada por el camino normal, la revisión se aplica y la ficha pasa.
    almacen.guardar_incidente(otro, AHORA, VOCABULARIO_MODELOS)
    guardado = almacen.incidente(ID)
    assert guardado is not None and invariantes.de_ficha(guardado) == []
    assert guardado["drones"]["numero"] == {"min": 1, "max": 1}


def test_i4_una_version_que_solo_cambia_la_fecha_se_ve() -> None:
    antes = {"id": ID, "titulo": {"es": "a"}, "control": {"ultima_actualizacion": {"valor": "1"}}}
    igual = {"id": ID, "titulo": {"es": "a"}, "control": {"ultima_actualizacion": {"valor": "2"}}}
    otra = {"id": ID, "titulo": {"es": "b"}, "control": {"ultima_actualizacion": {"valor": "2"}}}
    cambios = [
        {"entidad_id": ID, "tabla": "incidentes", "anterior": antes, "nuevo": igual},
        {"entidad_id": OTRA, "tabla": "incidentes", "anterior": antes, "nuevo": otra},
        {"entidad_id": OTRA, "tabla": "incidentes_motivos", "anterior": antes, "nuevo": igual},
    ]
    assert invariantes.versiones_iguales(cambios) == [ID]


def test_i5_el_aviso_lleva_los_datos_de_lo_publicado(tmp_path: Path, sin_marcas: None) -> None:
    almacen = _base(BUENO)
    publicar.publicar(almacen, AHORA, tmp_path)
    interno = almacen.publicado_interno([ID])[ID]
    entrada = _publicadas(tmp_path)[ID]
    assert invariantes.aviso_distinto(interno, entrada) == []
    otro = copy.deepcopy(interno)
    otro["tiempo"]["inicio"]["valor"] = "2026-10-12T08:00Z"
    assert invariantes.aviso_distinto(otro, entrada) == ["inicio"]
    assert invariantes.comprobar(almacen, AHORA)[invariantes.I5] == []


def test_i5_cuenta_con_el_inicio_que_ajusta_la_exportacion(tmp_path: Path) -> None:
    # EODI-2026-00777 (11 de noviembre de 2026): la base tenía el día 11 (la hora local de la
    # nota) y el primer aviso era del 10; la exportación publica el 10 (coherencia). No es un
    # aviso distinto, y el mensaje sale con el día publicado.
    from proceso import coherencia
    from recogida import avisos

    interno: Documento = {
        "id": ID,
        "tipo": "sobrevuelo",
        "lugar": {"pais": "LV"},
        "estado": {"actual": "notificado", "historial": [
            {"estado": "notificado", "fecha": {"valor": "2026-11-10T00:00Z", "precision": "dia"},
             "fuente_id": "f"},
        ]},
        "tiempo": {"inicio": {"valor": "2026-11-11T00:00Z", "precision": "dia"}},
    }  # fmt: skip
    entrada = coherencia.coherente(interno)
    assert entrada["tiempo"]["inicio"]["valor"] == "2026-11-10T00:00Z"
    assert invariantes.aviso_distinto(interno, entrada) == []
    (tmp_path / "incidentes_sin_ubicacion.json").write_text(
        json.dumps({"incidentes": [entrada]}), encoding="utf-8"
    )
    del_aviso = avisos.con_lo_publicado({ID: interno}, tmp_path)[ID]
    assert del_aviso["tiempo"]["inicio"]["valor"] == "2026-11-10T00:00Z"
    assert interno["tiempo"]["inicio"]["valor"] == "2026-11-11T00:00Z"


def test_una_invariante_rota_se_avisa_una_vez() -> None:
    almacen = Almacen.abrir()
    enviados: list[str] = []
    resultado = {invariantes.I3: [f"{ID} drones"], invariantes.I1: []}

    def avisador(titulo: str) -> Any:
        assert titulo == invariantes.TITULO_AVISO
        return enviados.append

    assert invariantes.avisar(almacen, AHORA, resultado, avisador) == [f"I3:{ID} drones"]
    assert invariantes.avisar(almacen, AHORA + timedelta(hours=1), resultado, avisador) == []
    assert len(enviados) == 1 and ID in enviados[0] and "I3" in enviados[0]
    assert (almacen.cursor(invariantes.CURSOR) or {})["rotas"] == {invariantes.I3: [f"{ID} drones"]}
    # Sin quien avise (ensayo) queda apuntada y se avisa cuando lo haya.
    otra = {invariantes.I2: [OTRA]}
    assert invariantes.avisar(almacen, AHORA, otra, None) == []
    assert invariantes.avisar(almacen, AHORA, otra, avisador) == [f"I2:{OTRA}"]


# --- Lo que leen la vigilancia y el resumen -----------------------------------------------


def test_el_registro_dice_no_publicada() -> None:
    nunca = {"id": ID, "comprobaciones": ["X"], "origen": puerta.NINGUNA, "diferencias": {}}
    assert puerta.linea(nunca) == (f"{ID} no publicada", "X", "sin diferencias")
    antes = {**nunca, "origen": puerta.BUENA, "diferencias": {"titulo": ["a", "b"]}}
    assert puerta.linea(antes) == (f"{ID} publicada en su versión buena", "X", "titulo")


def test_la_vigilancia_abre_la_incidencia_con_la_ficha_la_comprobacion_y_la_diferencia() -> None:
    estado = {"cerrojo": {"modo": "observar", "version_anterior": [{
        "id": ID, "comprobaciones": ["X"], "origen": "buena",
        "diferencias": {"titulo": ['{"es": "Dron"}', '{"es": "Posible dron"}']},
    }]}}  # fmt: skip
    (problema,) = vigilancia.problemas_del_cerrojo(estado)
    assert problema["id"] == "version_anterior" and "version_anterior" in vigilancia.SIN_GRACIA
    assert ID in problema["frase"] and "(X;" in problema["frase"]
    assert "titulo" in problema["frase"] and "Posible dron" in problema["frase"]


def test_el_resumen_cuenta_las_fichas_en_su_version_anterior() -> None:
    lineas = visitas.lineas_cerrojo(
        {"modo": "aplicar", "retenidos": [], "guardados_fallidos": [], "version_anterior": [ID]}
    )
    assert "  Fichas publicadas en su versión anterior: 1" in lineas
    assert f"  - {ID}" in lineas
