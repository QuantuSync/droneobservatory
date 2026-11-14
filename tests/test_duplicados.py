"""El mismo suceso publicado dos veces (13 de noviembre de 2026), con las fichas reales
(tests/fixtures/duplicados_2026-11-14.json):

- EODI-2026-00817, la entrada de un dron en Estonia el 11 de noviembre, repetía EODI-2026-00814.
  El experto la dio por distinta leyendo «la madrugada del miércoles 12» (el miércoles era el 11)
  cuando la ficha aún tenía la fecha de publicación; ese «distinto» la sacó de la lista del filtro
  de entrada, que la publicó.
- EODI-2026-00818 contaba, como «last week» en una nota del viernes 13, la noche del 10 al 11 en
  Lituania (los cazas que intentaron derribar el dron dos veces) que ya era EODI-2026-00792; la
  semana natural anterior la fechó el 8 y no casó con su suceso.

La definición (proceso/suceso.py) las da por el mismo suceso que su ficha y manda sobre el experto;
el candado de la publicación (exportacion/puerta.candado, invariante I8) no deja dos fichas
publicadas de un suceso. Los casos de la batería de la definición siguen en
tests/test_definicion_suceso.py."""

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from almacen.base import Almacen
from exportacion import puerta
from proceso import fechas, invariantes, suceso
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

CASO = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "duplicados_2026-11-14.json").read_text(
        encoding="utf-8"
    )
)
AHORA = datetime(2026, 11, 14, 10, 17, tzinfo=UTC)
ESTONIA, ESTONIA_BIS = "EODI-2026-00814", "EODI-2026-00817"
LITUANIA, LITUANIA_BIS, LETONIA = "EODI-2026-00792", "EODI-2026-00818", "EODI-2026-00777"
# Lo que el experto dio por distinto (escalado) el 13 de noviembre.
DEL_EXPERTO = suceso.distintos_en(CASO["pares"])
NOTA_LRT = (
    "Last week, NATO fighter jets tried twice to shoot down a stray drone that entered "
    "Lithuanian airspace, unsuccessfully."
)


def f(id_: str, otro_id: str | None = None) -> dict[str, Any]:
    """La ficha real; con `otro_id`, con otro número (las revisiones a mano van por el número)."""
    ficha: dict[str, Any] = copy.deepcopy(CASO["fichas"][id_])
    return {**ficha, "id": otro_id} if otro_id else ficha


def con_la_semana_de_ahora(ficha: dict[str, Any]) -> dict[str, Any]:
    """EODI-2026-00818 con la fecha que le da hoy «last week» (proceso/fechas.pasado_de)."""
    publicada = datetime(2026, 11, 13, 15, 30, tzinfo=UTC)
    vilna = ZoneInfo("Europe/Vilnius")
    resolucion = fechas.resolver(publicada, "dia", [NOTA_LRT], publicada, vilna, vilna, "en")
    tiempo = {
        "inicio": {"valor": resolucion.valor.strftime("%Y-%m-%dT%H:%MZ"),
                   "precision": resolucion.precision},
        "origen_inicio": {"tipo": resolucion.origen, "motivo": resolucion.motivo},
    }  # fmt: skip
    return {**ficha, "tiempo": tiempo}


# --- Lo que pasó: el «distinto» del experto mandaba ------------------------------------------


def test_el_experto_las_dio_por_distintas() -> None:
    assert frozenset({ESTONIA, ESTONIA_BIS}) in DEL_EXPERTO
    # El par de Lituania lo decidió el modelo base sin escalar: no cuenta como del experto.
    assert frozenset({LITUANIA, LITUANIA_BIS}) not in DEL_EXPERTO
    # Las dos se publicaron.
    assert CASO["entrada"][ESTONIA_BIS]["decision"] == "publicar"
    assert CASO["entrada"][LITUANIA_BIS]["decision"] == "publicar"
    assert CASO["entrada"][LITUANIA_BIS]["dudosas"] == [LITUANIA]


# --- Estonia: la misma incursión del país en la misma jornada --------------------------------


def test_estonia_es_el_mismo_suceso_aunque_el_experto_dijera_otra_cosa() -> None:
    dicho = suceso.veredicto(f(ESTONIA), f(ESTONIA_BIS), DEL_EXPERTO)
    assert dicho.relacion == suceso.MISMO
    # Sin la revisión que las une (otro número), la que habla es la incursión del país.
    otra = f(ESTONIA_BIS, "EODI-2026-09817")
    dicho = suceso.veredicto(f(ESTONIA), otra, DEL_EXPERTO | {frozenset({ESTONIA, otra["id"]})})
    assert (dicho.relacion, dicho.regla) == (suceso.MISMO, suceso.REGLA_INCURSION)


def test_el_filtro_ve_la_ficha_de_su_suceso() -> None:
    """El conjunto del filtro ya no saca lo que el experto dio por distinto si la definición dice
    que es el mismo suceso."""
    otra = f(ESTONIA_BIS, "EODI-2026-09817")
    distintos = frozenset({frozenset({ESTONIA, otra["id"]})})
    assert ESTONIA in [c["id"] for c in suceso.conjunto(otra, [f(ESTONIA)], distintos)]


def test_el_distinto_decidido_con_otra_fecha_no_vale() -> None:
    """El experto decidió con la fecha de publicación (el 13); el filtro le puso el 11."""
    clave = f"par:{ESTONIA}|{ESTONIA_BIS}"
    al_decidir = {ESTONIA: "2026-11-11T00:00Z", ESTONIA_BIS: "2026-11-13T08:15Z"}
    decision = {**CASO["pares"][clave], "inicios": al_decidir}
    ahora = {ESTONIA: "2026-11-11T00:00Z", ESTONIA_BIS: "2026-11-11T00:00Z"}
    assert suceso.distintos_en({clave: decision}, ahora.get) == frozenset()
    con_las_mismas = {**decision, "inicios": ahora}
    assert suceso.distintos_en({clave: con_las_mismas}, ahora.get) == {
        frozenset({ESTONIA, ESTONIA_BIS})
    }


def test_otro_pais_de_la_misma_noche_no_es_el_mismo_suceso() -> None:
    """Lituania, Letonia y Estonia: tres sucesos, un episodio."""
    for otra in (LITUANIA, LETONIA):
        assert suceso.veredicto(f(ESTONIA_BIS), f(otra), DEL_EXPERTO).relacion != suceso.MISMO


# --- Lituania: «last week» es también esta semana --------------------------------------------


def test_la_semana_pasada_llega_hasta_la_vispera() -> None:
    publicada = datetime(2026, 11, 13, 15, 30, tzinfo=UTC)
    vilna = ZoneInfo("Europe/Vilnius")
    assert fechas.pasado_de(NOTA_LRT, publicada, vilna) == (
        date(2026, 11, 1), date(2026, 11, 12), "last week",
    )  # fmt: skip


def test_lituania_es_la_noche_del_10_al_11() -> None:
    lrt = con_la_semana_de_ahora(f(LITUANIA_BIS, "EODI-2026-09818"))
    # Con la semana natural (la ficha publicada, fechada el 8) no casaba con su suceso.
    assert suceso.veredicto(f(LITUANIA), f(LITUANIA_BIS, "EODI-2026-09818")).relacion != (
        suceso.MISMO
    )
    dicho = suceso.veredicto(f(LITUANIA), lrt, DEL_EXPERTO)
    assert (dicho.relacion, dicho.regla) == (suceso.MISMO, suceso.REGLA_INCURSION)
    candidatas = [f(LITUANIA), f(ESTONIA), f(LETONIA), f(ESTONIA_BIS)]
    assert [o["id"] for o, _ in suceso.del_mismo_suceso(lrt, candidatas, DEL_EXPERTO)] == [LITUANIA]


def test_una_ficha_sin_sitio_no_se_une_sola_a_dos_de_su_pais() -> None:
    """Si casa con varias de su país, no se sabe con cuál: `del_mismo_suceso` las da todas y
    quien llama no une (el candado la para y avisa)."""
    otra_noche = {**f(LITUANIA, "EODI-2026-09792"), "relacionados": []}
    otra_noche["tiempo"] = {"inicio": {"valor": "2026-11-04T00:00Z", "precision": "dia"}}
    lrt = con_la_semana_de_ahora(f(LITUANIA_BIS, "EODI-2026-09818"))
    mismos = suceso.del_mismo_suceso(lrt, [f(LITUANIA), otra_noche])
    assert len(mismos) == 2


# --- El candado de la publicación (I8) --------------------------------------------------------


def _completa(ficha: dict[str, Any]) -> dict[str, Any]:
    """La ficha recortada con lo que pide el esquema para guardarla."""
    base = ejemplos.incidente_minimo()
    nueva = {**base, **{k: v for k, v in ficha.items() if k != "fuentes_en_la_base"}}
    for fuente in nueva["fuentes"]:
        for clave, valor in base["fuentes"][0].items():
            fuente.setdefault(clave, valor)
    primera = nueva["fuentes"][0]
    nueva["control"] = {**base["control"], **ficha["control"]}
    nueva["afirmaciones"] = []
    nueva["estado"] = {
        "actual": "notificado",
        "historial": [
            {"estado": "notificado", "fecha": primera["fecha"], "fuente_id": primera["id"]}
        ],
    }
    for clave in ("respuesta", "drones", "atribucion", "presencia_dron", "relacionados", "zona"):
        nueva.pop(clave, None)
    origen = (nueva["tiempo"].get("origen_inicio") or {}).get("fuente_id")
    if origen and origen not in {n["id"] for n in nueva["fuentes"]}:
        nueva["tiempo"]["origen_inicio"].pop("fuente_id")
    return nueva


def _publicadas(*fichas: dict[str, Any]) -> Almacen:
    almacen = Almacen.abrir()
    for ficha in fichas:
        almacen.guardar_incidente(ficha, AHORA, VOCABULARIO_MODELOS)
        almacen.guardar_publicado(
            ficha["id"], puerta.PUBLICADA, puerta.MAPA, {"id": ficha["id"]}, ficha, {},
            "2026-11-13T13:17:02Z",
        )  # fmt: skip
    return almacen


def test_el_candado_une_las_dos_fichas_publicadas_de_estonia() -> None:
    queda = _completa(f(ESTONIA, "EODI-2026-09814"))
    repetida = _completa(f(ESTONIA_BIS, "EODI-2026-09817"))
    almacen = _publicadas(queda, repetida)
    filas = almacen.publicado()
    antes = invariantes.mismo_suceso_en_dos_fichas(almacen, filas, set())
    assert antes == ["EODI-2026-09814=EODI-2026-09817 (misma_incursion_del_pais)"]
    hecho = puerta.candado(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hecho.unidas == ["EODI-2026-09817→EODI-2026-09814"] and not hecho.sin_unir
    unida = almacen.incidente("EODI-2026-09817")
    assert unida is not None and unida["fusionado_en"] == "EODI-2026-09814"
    # La unión lleva su cita: la frase de la ficha que se une.
    (fusion,) = [u for u in almacen.fusiones() if u["absorbido"] == "EODI-2026-09817"]
    assert "candado de la publicación (I8)" in fusion["motivo"] and "«" in fusion["motivo"]
    assert invariantes.mismo_suceso_en_dos_fichas(almacen, almacen.publicado(), set()) == []
    # La dirección de la unida lleva a la que queda (I7).
    base = {str(d["id"]): d for d in almacen.incidentes()}
    resultado = puerta.Resultado()
    filas = almacen.publicado()
    pase = puerta.Pase(frozenset({"EODI-2026-09814"}), True)
    puerta._sin_candidata(almacen, resultado, filas, {}, base, {}, pase, "2026-11-14T10:17:00Z")
    assert resultado.unidas == ["EODI-2026-09817→EODI-2026-09814"]
    assert puerta.direcciones(almacen.publicado(), base)[0] == {
        "EODI-2026-09817": "EODI-2026-09814"
    }


def test_la_puerta_no_publica_una_ficha_nueva_de_un_suceso_ya_publicado() -> None:
    """Independiente del candado de antes: la versión de una ficha sin publicar del mismo
    suceso que una publicada no entra (I8) y la invariante lo cuenta para avisar."""
    queda = _completa(f(LITUANIA, "EODI-2026-09792"))
    almacen = _publicadas(queda)
    nueva = _completa(con_la_semana_de_ahora(f(LITUANIA_BIS, "EODI-2026-09818")))
    almacen.guardar_incidente(nueva, AHORA, VOCABULARIO_MODELOS)
    puerta.dar_pase(almacen, AHORA, ["EODI-2026-09792", "EODI-2026-09818"])
    base = {str(d["id"]): d for d in almacen.incidentes()}
    generados = {puerta.MAPA: {"features": [{"id": i, "properties": {"id": i}} for i in base]}}
    resultado = puerta.pasar(almacen, AHORA, generados, base)
    paradas = {r["id"]: r["comprobaciones"] for r in resultado.retenidas}
    assert puerta.MISMO_SUCESO in paradas["EODI-2026-09818"]
    assert "EODI-2026-09818" not in {
        i for i, fila in almacen.publicado().items() if fila["estado"] == puerta.PUBLICADA
    }
    rotas = invariantes.mismo_suceso_en_dos_fichas(
        almacen, almacen.publicado(), {"EODI-2026-09818"}
    )
    assert rotas == ["EODI-2026-09818 parada: el mismo suceso que EODI-2026-09792"]


def test_el_aeropuerto_chopin_de_varsovia_se_reconoce_en_ruso() -> None:
    # La letra B de la auditoría del 14 de noviembre: «В варшавском аэропорту имени Шопена» no
    # casaba con ningún nombre del aeropuerto (solo «Шопена» declinado lo nombra) y «Warsaw
    # airport» casa con Modlin, a más de su radio de la ficha.
    from proceso import objetivo_del_titular

    nombrado = objetivo_del_titular.objetivo_nombrado(f("EODI-2026-00819"))
    assert nombrado == {"categoria": "aeropuerto", "nombre": "Lotnisko Chopina", "oaci": "EPWA"}


def _nota_sin_ficha(almacen: Almacen, entrado: str) -> str:
    from recogida import oficiales

    enlace = "https://www.mil.lv/lv/zinas/nota-de-prueba"
    almacen.guardar_cursor(
        oficiales.CURSOR_SIN_FICHA,
        {enlace: {"entrado": entrado, "fuente": "mil_lv", "candidatos": ["cand-prueba"]}},
    )
    return enlace


def test_una_nota_oficial_sin_salida_en_dos_horas_avisa_una_vez() -> None:
    from proceso import escalado, extraccion
    from recogida import oficiales

    almacen = Almacen.abrir()
    almacen.guardar_candidato({"id": "cand-prueba", "articulos": []})
    enlace = _nota_sin_ficha(almacen, "2026-11-14T07:50Z")
    avisos: list[str] = []
    # A las 2 horas sin salida: sus candidatos se repiten con el experto (crítico, con revisión,
    # ya vencida para la extracción de la hora siguiente) y aún no se avisa.
    assert oficiales.avisar_sin_salida(almacen, AHORA, lambda titulo: avisos.append) == []
    assert avisos == []
    espera = extraccion.esperan_experto(almacen)["cand-prueba"]
    assert espera["revision"] and espera["critico"]
    assert espera["motivos"][0].startswith(escalado.MOTIVO_NOTA_OFICIAL)
    assert escalado.es_critico(espera["motivos"]) and escalado.escala(espera["motivos"])
    assert extraccion.en_revision(almacen) == {"cand-prueba"}
    assert not extraccion.espera_experto(almacen, "cand-prueba", AHORA)
    pedido = (almacen.cursor(oficiales.CURSOR_SIN_FICHA) or {})[enlace]["experto_pedido"]
    assert pedido == "2026-11-14T10:17Z"
    # Pedido una sola vez: la recogida siguiente dentro de la hora no escribe nada.
    antes = (almacen.cursor(oficiales.CURSOR_SIN_FICHA), extraccion.esperan_experto(almacen))
    media_hora = datetime(2026, 11, 14, 10, 47, tzinfo=UTC)
    assert oficiales.avisar_sin_salida(almacen, media_hora, lambda titulo: avisos.append) == []
    assert (
        almacen.cursor(oficiales.CURSOR_SIN_FICHA),
        extraccion.esperan_experto(almacen),
    ) == antes
    # Una hora después, sin salida tras el experto: un aviso, una sola vez.
    hora = datetime(2026, 11, 14, 11, 17, tzinfo=UTC)
    assert oficiales.avisar_sin_salida(almacen, hora, lambda titulo: avisos.append) == [enlace]
    assert len(avisos) == 1 and enlace in avisos[0]
    assert oficiales.avisar_sin_salida(almacen, hora, lambda titulo: avisos.append) == [enlace]
    assert len(avisos) == 1
    assert (almacen.cursor(oficiales.CURSOR_SIN_FICHA) or {})[enlace]["experto_pedido"] == pedido


def test_una_nota_oficial_en_ensayo_pide_el_experto_y_no_avisa() -> None:
    from proceso import extraccion
    from recogida import oficiales

    almacen = Almacen.abrir()
    almacen.guardar_candidato({"id": "cand-prueba", "articulos": []})
    enlace = _nota_sin_ficha(almacen, "2026-11-14T07:50Z")
    assert oficiales.avisar_sin_salida(almacen, AHORA, None) == []
    assert extraccion.en_revision(almacen) == {"cand-prueba"}
    hora = datetime(2026, 11, 14, 11, 17, tzinfo=UTC)
    assert oficiales.avisar_sin_salida(almacen, hora, None) == [enlace]
    # Sin quien avise, nada se marca como avisado y las recogidas siguientes no cambian nada.
    cursor = almacen.cursor(oficiales.CURSOR_SIN_FICHA) or {}
    assert "avisada" not in cursor[enlace]
    assert oficiales.avisar_sin_salida(almacen, hora, None) == [enlace]
    assert almacen.cursor(oficiales.CURSOR_SIN_FICHA) == cursor


def test_una_extraccion_escalada_sin_salida_da_ya_su_oportunidad_al_experto() -> None:
    from recogida import oficiales

    almacen = Almacen.abrir()
    almacen.guardar_candidato({"id": "cand-prueba", "articulos": []})
    enlace = _nota_sin_ficha(almacen, "2026-11-14T07:50Z")
    assert oficiales.avisar_sin_salida(almacen, AHORA, None) == []
    # El experto la extrajo a los 20 minutos sin ficha ni descarte con motivo: no hay que
    # esperar a que pase la hora.
    almacen.guardar_extraccion(
        "cand-prueba", "2026-11-14T10:37Z", "v", "h", False,
        {"motivos": [], "campos": {}, "incidente": None, "escalado": ["nota_oficial_sin_salida"]},
    )  # fmt: skip
    avisos: list[str] = []
    despues = datetime(2026, 11, 14, 10, 40, tzinfo=UTC)
    assert oficiales.avisar_sin_salida(almacen, despues, lambda titulo: avisos.append) == [enlace]
    assert len(avisos) == 1


def test_un_descarte_con_motivo_o_una_ficha_es_la_salida_de_la_nota() -> None:
    from proceso import extraccion
    from recogida import oficiales

    almacen = Almacen.abrir()
    almacen.guardar_candidato({"id": "cand-prueba", "articulos": []})
    enlace = _nota_sin_ficha(almacen, "2026-11-14T07:50Z")
    # Una extracción de antes de que la nota entrara no cuenta.
    almacen.guardar_extraccion(
        "cand-prueba", "2026-11-14T07:00Z", "v", "h", False,
        {"motivos": ["no es un incidente"], "campos": {}, "incidente": None},
    )  # fmt: skip
    # Ni una de después sin ficha y sin motivo.
    almacen.guardar_extraccion(
        "cand-prueba", "2026-11-14T08:00Z", "v", "h", False,
        {"motivos": [], "campos": {}, "incidente": None},
    )  # fmt: skip
    assert oficiales.sin_salida(almacen, AHORA) == [enlace]
    # El descarte del base con su motivo (o la ficha que dice que no es un incidente) es salida.
    almacen.guardar_extraccion(
        "cand-prueba", "2026-11-14T09:00Z", "v", "h", False,
        {"motivos": [], "campos": {}, "incidente": None,
         "ficha": {"es_incidente": {"valor": False}}},
    )  # fmt: skip
    assert oficiales.sin_salida(almacen, AHORA) == []
    avisos: list[str] = []
    hora = datetime(2026, 11, 14, 11, 17, tzinfo=UTC)
    assert oficiales.avisar_sin_salida(almacen, hora, lambda titulo: avisos.append) == []
    assert avisos == [] and extraccion.esperan_experto(almacen) == {}


def test_un_descarte_con_motivos_tras_la_entrada_es_salida() -> None:
    from proceso import extraccion
    from recogida import oficiales

    almacen = Almacen.abrir()
    almacen.guardar_candidato({"id": "cand-prueba", "articulos": []})
    _nota_sin_ficha(almacen, "2026-11-14T07:50Z")
    almacen.guardar_extraccion(
        "cand-prueba", "2026-11-14T08:50Z", "v", "h", False,
        {"motivos": ["no_es_suceso: comunicado de ejercicios"], "campos": {}, "incidente": None},
    )  # fmt: skip
    assert oficiales.avisar_sin_salida(almacen, AHORA, None) == []
    assert extraccion.esperan_experto(almacen) == {}


def test_una_nota_oficial_reciente_o_con_ficha_no_avisa() -> None:
    from recogida import oficiales

    almacen = Almacen.abrir()
    _nota_sin_ficha(almacen, "2026-11-14T09:00Z")  # 1 h 17 min: aún dentro del plazo
    assert oficiales.sin_salida(almacen, AHORA) == []
    enlace = _nota_sin_ficha(almacen, "2026-11-14T07:50Z")
    ficha = _completa(f(ESTONIA, "EODI-2026-09814"))
    ficha["fuentes"][0]["enlace"] = enlace
    almacen.guardar_incidente(ficha, AHORA, VOCABULARIO_MODELOS)
    assert oficiales.sin_salida(almacen, AHORA) == []


def test_con_un_sitio_en_una_de_las_dos_no_es_la_misma_incursion() -> None:
    # Ensayo del 14 de noviembre de 2026: con «una de las dos sin sitio» la regla unía la segunda
    # dron de Moldavia del 31 de octubre (Viișoara, EODI-2026-00728) con la de Plopi (00716). Con
    # un sitio en una de las dos, decide el experto.
    con_sitio = f(ESTONIA_BIS, "EODI-2026-09817")
    con_sitio["lugar"] = {**con_sitio["lugar"], "nivel": "localidad", "localidad": "Narva"}
    assert not suceso.misma_incursion(f(ESTONIA), con_sitio)
    assert suceso.misma_incursion(f(ESTONIA), f(ESTONIA_BIS, "EODI-2026-09817"))


def test_los_dos_cierres_de_munich_son_distintos_por_revision() -> None:
    # El candado los unía por el mismo sitio y la misma jornada; una revisión los separa.
    assert frozenset({"EODI-2025-00055", "EODI-2025-00083"}) in suceso.pares_distintos()


def test_la_revision_pone_el_objetivo_aunque_nada_mas_cambie() -> None:
    from recogida import revisados

    ficha = {**ejemplos.incidente_minimo(), "id": "EODI-2026-00819"}
    ficha["objetivo"] = {"categoria": "otra", "nombre": "Warsaw"}
    revision = next(
        r for r in revisados.cargar()["titulares"] if r["incidente"] == "EODI-2026-00819"
    )
    instante = {"valor": "2026-11-14T10:17Z", "precision": "minuto"}
    nueva = revisados.con_titular(ficha, revision, instante)
    assert nueva["objetivo"] == {
        "categoria": "aeropuerto",
        "nombre": "Lotnisko Chopina",
        "oaci": "EPWA",
    }
