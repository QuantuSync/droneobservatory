"""Incidentes que juntaban sucesos distintos (docs/sucesos_mezclados.md): la regla que los juntó
(nombres que no nombran un lugar) y la separación revisada (recogida/revisados.separar), con el
caso de Vilna, EODI-2026-00072."""

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import incidentes, noticias
from proceso.noticias import Articulo
from recogida import revisados
from tests import ejemplos

AHORA = datetime(2026, 10, 13, 19, 17, tzinfo=UTC)
MODELOS: frozenset[str] = frozenset()

# Los cuatro titulares del candidato de EODI-2026-00072: dos del cierre del domingo 13 de
# septiembre de 2026 (publicados el 14) y dos del derribo de la noche del 14 al 15.
VILNA = [
    ("https://sot.com.al/dron", "2026-09-14T08:30:00Z",
     "Dron mbi Lituani, mbyllet aeroporti i Vilniusit, NATO ngre avionin luftarak, Kievi "
     "paralajmëron për rrezikun rus në Europë"),
    ("https://humanevents.com/aeropuerto", "2026-09-14T19:15:00Z",
     "Lithuanian authorities close airport, scramble NATO jet when mistaking birds for drones in "
     "real life '99 Red Balloons' incident | Human Events"),
    ("https://delo.si/derribo", "2026-09-15T07:15:00Z",
     "Nato minulo noč sestrelil dron, ki je vdrl v litovski zračni prostor"),
    ("https://klix.ba/derribo", "2026-09-15T08:45:00Z",
     "NATO avioni srušili dron u Litvaniji: Zbog upada u zračni prostor bio zatvoren i aerodrom u "
     "Vilniusu"),
]  # fmt: skip


# --- La regla ------------------------------------------------------------------------


def test_nato_no_es_la_base_de_geilenkirchen() -> None:
    nom, filtro = noticias.nomenclator(), noticias.filtro()
    for _, _, titular in VILNA:
        assert "ETNG" not in noticias.lugares_articulo(titular, nom, filtro), titular
    # La base sigue saliendo cuando se la nombra.
    assert noticias.lugares_articulo(
        "Alerta de posible dron en la base aérea de Geilenkirchen", nom, filtro
    ) == ("ETNG",)


def test_los_titulares_de_vilna_no_acaban_en_un_mismo_candidato() -> None:
    nom, filtro = noticias.nomenclator(), noticias.filtro()
    articulos = [
        Articulo(url, url.split("/")[2], datetime.fromisoformat(fecha.replace("Z", "+00:00")),
                 titular, lugares=noticias.lugares_articulo(titular, nom, filtro))
        for url, fecha, titular in VILNA
    ]  # fmt: skip
    agrupacion = noticias.agrupar(articulos, filtro, nom)
    # Con «NATO» como ciudad de Geilenkirchen, los cuatro iban a un mismo candidato.
    assert agrupacion.candidatos or agrupacion.sin_lugar == len(VILNA)
    for candidato in agrupacion.candidatos:
        urls = set(candidato.articulos)
        assert not (urls & {VILNA[0][0], VILNA[1][0]} and urls & {VILNA[2][0], VILNA[3][0]})


@pytest.mark.parametrize("palabra", sorted(noticias.no_son_lugares()))
def test_ninguna_palabra_de_la_lista_nombra_un_lugar(palabra: str) -> None:
    nom = noticias.nomenclator()
    assert palabra not in nom.alias
    assert palabra not in nom.ciudades
    assert palabra not in nom.localidades


@pytest.mark.parametrize(
    "titular",
    [
        "Caccia Nato in volo sul Baltico: abbattuto un drone in territorio lettone",
        "Cazas OTAN derriban un dron sobre Letonia",
        "Încă o dronă a fost doborâtă în spațiul aerian românesc",
        "NATO Downs Russian Drone Over Latvia",
        "Drama na Baltiku: NATO srušio dron iz Rusije iznad Latvije",
    ],
)
def test_palabras_comunes_no_situan_un_titular(titular: str) -> None:
    lugares = noticias.lugares_articulo(titular, noticias.nomenclator(), noticias.filtro())
    pais = {noticias.lugar(i, noticias.nomenclator()).pais for i in lugares}
    assert pais <= {"LV", "RO"}, (titular, lugares)


def test_las_uniones_correctas_siguen() -> None:
    """El mismo cierre del 7 de octubre de 2026 en Lublin y Rzeszów: un titular, dos aeropuertos
    del mismo país, dos candidatos, unidos a mano en uno."""
    titular = (
        "Συναγερμός στην Πολωνία - Έκλεισαν τα νατοϊκά αεροδρόμια Lublin και Rzeszów μετά από "
        "εκτόξευση ρωσικού drone"
    )
    assert noticias.lugares_articulo(titular, noticias.nomenclator(), noticias.filtro()) == (
        "EPLB",
        "EPRZ",
    )
    grupos = [g["registros"] for g in revisados.cargar()["unir"]]
    assert any({"EODI-2026-00497", "EODI-2026-00498"} <= set(g) for g in grupos)


# --- La separación ---------------------------------------------------------------------


def _fuente(id_: str, url: str, fecha: str, frase: str, **mas: Any) -> dict[str, Any]:
    fuente = ejemplos.fuente(id_, "C")
    fuente.update(enlace=url, fecha=ejemplos.instante(fecha.replace(":00Z", "Z")),
                  frase_origen=frase, **mas)  # fmt: skip
    return fuente


def _incidente(id_: str, fuentes: list[dict[str, Any]], inicio: str) -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento.update(
        id=id_,
        titulo={"es": "Dron sobre Lituania", "en": "Drone over Lithuania"},
        tiempo={"inicio": ejemplos.instante(inicio, "dia")},
        lugar={"punto": {"lat": 54.63488, "lon": 25.28759}, "radio_km": 5.0, "pais": "LT"},
        fuentes=fuentes,
    )
    documento["estado"]["historial"][0].update(fuente_id=fuentes[0]["id"],
                                               fecha=fuentes[0]["fecha"])  # fmt: skip
    documento["control"]["alta"] = fuentes[0]["fecha"]
    return documento


@pytest.fixture
def vilna(monkeypatch: pytest.MonkeyPatch) -> Almacen:
    almacen = Almacen.abrir()
    for url, fecha, titular in VILNA:
        almacen.guardar_articulo({
            "url": url, "medio": url.split("/")[2], "fecha": fecha, "idioma": "en",
            "titular": titular, "titular_normalizado": noticias.normalizar(titular),
            "lugares": ["ETNG"],
        })  # fmt: skip
    candidato: dict[str, Any] = {
        "id": "CAND-20260914T0830-ETNG-aeropuerto", "tipo": "aeropuerto", "lugar": "ETNG",
        "inicio": "2026-09-14T08:30:00Z", "ultimo": "2026-09-15T08:45:00Z", "precision": "dia",
        "articulos": [u for u, _, _ in VILNA],
    }  # fmt: skip
    almacen.corregir_candidatos([candidato], "prueba")
    s1, s2, s3, s4 = (
        _fuente(f"s{n}", url, fecha, titular) for n, (url, fecha, titular) in enumerate(VILNA, 1)
    )
    declaracion = _fuente("s3-declaracion-1", VILNA[2][0], VILNA[2][1],
                          "Piloti lovcev zveze Nato so to noč sestrelili dron",
                          fiabilidad="B", es_autoridad=True)  # fmt: skip
    mezclado = _incidente("EODI-2026-00072", [s1, s2, s3, declaracion, s4], "2026-09-14T00:00Z")
    mezclado["estado"] = {"actual": "confirmado", "historial": [
        mezclado["estado"]["historial"][0],
        {"estado": "confirmado", "fecha": declaracion["fecha"], "fuente_id": declaracion["id"]},
    ]}  # fmt: skip
    mezclado["presencia_dron"] = "confirmada"
    mezclado["afirmaciones"] = [{"campo": "presencia_dron", "valor": "confirmada",
                                 "fuente_id": "s3", "confianza_extraccion": 0.95}]  # fmt: skip
    mezclado["control"]["candidato"] = candidato["id"]
    almacen.guardar_incidente(mezclado, AHORA, MODELOS)
    almacen.guardar_extraccion(candidato["id"], "2026-09-30T18:46Z", "ficha/5", "h", True,
                               {"incidente": "EODI-2026-00072",
                                "enviadas": [u for u, _, _ in VILNA[:3]]})  # fmt: skip
    # Las fichas que ya tenían cada suceso.
    cierre = _incidente("EODI-2026-00007", [
        _fuente("c1", "https://bt.dk/cierre", "2026-09-13T11:15:00Z", "Lufthavn lukket"),
        _fuente("c2", "https://vg.no/cierre", "2026-09-13T15:00:00Z", "Flyplass stengt"),
    ], "2026-09-13T00:00Z")  # fmt: skip
    derribo = _incidente("EODI-2026-00179", [
        _fuente("d1", "https://ansa.it/derribo", "2026-09-15T01:00:00Z", "Caccia abbattono drone"),
        _fuente("d2", "https://lrt.lt/derribo", "2026-09-16T12:45:00Z", "Gerbera shot down"),
        _fuente("d3", "https://lrt.lt/otra", "2026-09-16T13:45:00Z", "Drone over Lithuania"),
    ], "2026-09-15T00:00Z")  # fmt: skip
    for documento in (cierre, derribo):
        almacen.guardar_incidente(documento, AHORA - timedelta(days=20), MODELOS)
    revision = {
        "incidente": "EODI-2026-00072",
        "motivo": {"es": "juntaba el cierre y el derribo", "en": "merged closure and shoot-down"},
        "partes": [
            {"es_suceso": True, "fecha": "2026-09-13", "pais": "LT", "descripcion": "cierre",
             "coincide_con": "EODI-2026-00007", "lugar": "EYVI", "fuentes": ["s1", "s2"]},
            {"es_suceso": True, "fecha": "2026-09-14", "pais": "LT", "descripcion": "derribo",
             "coincide_con": "EODI-2026-00179",
             "fuentes": ["s3", "s3-declaracion-1", "s4"]},
        ],
    }  # fmt: skip
    monkeypatch.setattr(revisados, "cargar", lambda: {"unir": [], "separar": [revision]})
    return almacen


def _extractor_falso(llamadas: list[str]) -> Any:
    """Da de alta el incidente del candidato como lo haría el extractor: con el número siguiente
    y sus artículos como fuentes."""

    def extraer(almacen: Almacen, cliente: Any, candidato: Any, ahora: datetime) -> int:
        llamadas.append(candidato["id"])
        anterior = [
            e["incidente"] for e in almacen.extracciones(candidato["id"]) if e.get("incidente")
        ]
        id_ = anterior[-1] if anterior else almacen.siguiente_id_incidente(2026)
        previo = almacen.incidente(id_)
        articulos = almacen.articulos_de(candidato["articulos"])
        fuentes = [_fuente(incidentes.id_fuente(a["url"]), a["url"], a["fecha"], a["titular"])
                   for a in articulos]  # fmt: skip
        documento = _incidente(id_, fuentes, articulos[0]["fecha"][:10] + "T00:00Z")
        documento["control"]["candidato"] = candidato["id"]
        if previo is not None and "fusionado_en" in previo:
            documento["fusionado_en"] = previo["fusionado_en"]
        almacen.guardar_incidente(documento, ahora, MODELOS)
        almacen.guardar_extraccion(candidato["id"], "2026-10-13T19:17Z", "ficha/5",
                                   incidentes.huella(candidato["articulos"]), True,
                                   {"incidente": id_,
                                    "enviadas": candidato["articulos"]})  # fmt: skip
        return 1

    return extraer


def test_vilna_se_separa_en_sus_dos_sucesos(
    vilna: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[str] = []
    monkeypatch.setattr(revisados, "_extraer", _extractor_falso(llamadas))
    hechos = revisados.separar(vilna, AHORA, MODELOS, cliente=object())
    assert hechos.repartidos == ["EODI-2026-00072"]
    # El candidato del cierre conserva sus artículos; el derribo, en uno nuevo separado de él.
    candidatos = {c["id"]: c for c in vilna.candidatos()}
    propio = candidatos["CAND-20260914T0830-ETNG-aeropuerto"]
    assert propio["articulos"] == [VILNA[0][0], VILNA[1][0]]
    (nuevo,) = [c for c in candidatos.values() if c.get("separado_de") == propio["id"]]
    assert nuevo["articulos"] == [VILNA[2][0], VILNA[3][0]]
    assert nuevo["id"] == "CAND-20260915T0715-ETNG-aeropuerto"
    # Las dos partes pasan por el extractor; el derribo recibe el número siguiente.
    assert sorted(llamadas) == sorted([propio["id"], nuevo["id"]])
    derribo_nuevo = vilna.incidente("EODI-2026-00180")
    assert derribo_nuevo is not None
    assert {f["enlace"] for f in derribo_nuevo["fuentes"]} == {VILNA[2][0], VILNA[3][0]}
    # Cada parte, unida a la ficha que ya tenía su suceso (la de más fuentes queda).
    cierre = vilna.incidente("EODI-2026-00072")
    assert cierre is not None and cierre["fusionado_en"] == "EODI-2026-00007"
    assert derribo_nuevo.get("fusionado_en") == "EODI-2026-00179"
    unido = vilna.incidente("EODI-2026-00007")
    assert unido is not None
    assert {VILNA[0][0], VILNA[1][0]} <= {f["enlace"] for f in unido["fuentes"]}
    assert not {VILNA[2][0], VILNA[3][0]} & {f["enlace"] for f in unido["fuentes"]}
    # Las dos fichas se enlazan entre sí, con la nota en los dos idiomas.
    derribo = vilna.incidente("EODI-2026-00179")
    assert derribo is not None
    assert [r["id"] for r in unido["relacionados"]] == ["EODI-2026-00179"]
    assert [r["id"] for r in derribo["relacionados"]] == ["EODI-2026-00007"]
    assert derribo["relacionados"][0]["separado_de"] == "EODI-2026-00072"
    assert derribo["relacionados"][0]["nota"]["en"] == "merged closure and shoot-down"
    # Una segunda pasada no cambia nada ni vuelve a llamar.
    antes = {i["id"]: i for i in vilna.incidentes()}
    otra = revisados.separar(vilna, AHORA + timedelta(hours=1), MODELOS, cliente=object())
    assert otra.repartidos == [] and otra.relacionados == [] and otra.unidos == 0
    assert {i["id"]: i for i in vilna.incidentes()} == antes
    assert len(llamadas) == 2


def test_sin_extractor_el_que_se_queda_pierde_lo_del_otro_suceso(vilna: Almacen) -> None:
    hechos = revisados.separar(vilna, AHORA, MODELOS, cliente=None)
    assert hechos.repartidos == ["EODI-2026-00072"]
    assert len(hechos.pendientes) == 2
    # Sin el extractor (un ensayo), el que se queda ya no tiene las fuentes del derribo ni la
    # confirmación de su declaración, y se une a la ficha del cierre.
    cierre = vilna.incidente("EODI-2026-00072")
    assert cierre is not None and cierre["fusionado_en"] == "EODI-2026-00007"
    assert {f["id"] for f in cierre["fuentes"]} == {"s1", "s2"}
    assert cierre["estado"]["actual"] == "notificado"
    assert cierre["presencia_dron"] == "no_confirmada"
    assert cierre["afirmaciones"] == []


def test_el_fundido_por_una_regla_se_separa_igual(vilna: Almacen) -> None:
    # EODI-2025-00199 recibió las fuentes de otro suceso y una regla lo fundió en EODI-2026-00094
    # (25 de octubre de 2026): la separación deshace esa fusión antes de repartir.
    mezclado = vilna.incidente("EODI-2026-00072")
    destino = vilna.incidente("EODI-2026-00179")
    assert mezclado is not None and destino is not None
    nuevo, aportadas = incidentes.absorber(destino, mezclado, AHORA)
    vilna.guardar_incidente(nuevo, AHORA, MODELOS)
    vilna.guardar_incidente({**mezclado, "fusionado_en": destino["id"]}, AHORA, MODELOS)
    vilna.registrar_fusion("2026-10-25T05:17Z", mezclado["id"], destino["id"],
                           "mismo sitio y misma ventana", aportadas)  # fmt: skip
    hechos = revisados.separar(vilna, AHORA, MODELOS, cliente=None)
    assert hechos.repartidos == ["EODI-2026-00072"]
    assert all(f["revertida"] for f in vilna.fusiones() if f["absorbido"] == "EODI-2026-00072"
               and f["destino"] == "EODI-2026-00179")  # fmt: skip


def test_lo_que_no_es_un_suceso_sale_sin_formar_otro(
    vilna: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = copy.deepcopy(revisados.cargar()["separar"][0])
    revision["partes"][1].update(es_suceso=False, coincide_con=None)
    monkeypatch.setattr(revisados, "cargar", lambda: {"unir": [], "separar": [revision]})
    llamadas: list[str] = []
    monkeypatch.setattr(revisados, "_extraer", _extractor_falso(llamadas))
    revisados.separar(vilna, AHORA, MODELOS, cliente=object())
    (fuera,) = [c for c in vilna.candidatos() if c.get("separado_de")]
    assert fuera["id"] not in llamadas
    (extraccion,) = vilna.extracciones(fuera["id"])
    assert not extraccion["valida"] and extraccion["incidente"] is None
    assert vilna.incidente("EODI-2026-00180") is None


def test_un_suceso_antiguo_no_se_avisa() -> None:
    """Los avisos de ntfy solo salen para sucesos de las últimas 72 horas: las partes de una
    separación son sucesos de hace semanas."""
    from recogida import avisos

    documento = _incidente("EODI-2026-00180", [
        _fuente("s3", VILNA[2][0], VILNA[2][1], "Nato sestrelil dron nad Litvo",
                fiabilidad="A", es_autoridad=True),
    ], "2026-09-14T00:00Z")  # fmt: skip
    documento["estado"]["actual"] = "confirmado"
    documento["estado"]["historial"][0]["estado"] = "confirmado"
    config = avisos.configuracion()
    assert avisos.clasificar(documento, config, datetime(2026, 9, 14, 6, tzinfo=UTC)) is not None
    assert avisos.clasificar(documento, config, AHORA) is None


def test_la_configuracion_de_vilna() -> None:
    revision = next(r for r in revisados.cargar()["separar"] if r["incidente"] == "EODI-2026-00072")
    cierre, derribo = revision["partes"]
    assert revisados.conservada(revision) == 0
    assert cierre["coincide_con"] == "EODI-2026-00007"
    assert derribo["coincide_con"] == "EODI-2026-00179"
    assert set(cierre["fuentes"]) == {"gdelt-6c91f3d8c07ad7fa", "gdelt-cafe5ba5a861a635"}
    assert "gdelt-c2e4d410a67ab90c" in derribo["fuentes"]
    # Toda separación tiene al menos dos partes, una de ellas un suceso, y su motivo en los dos
    # idiomas.
    for revision in revisados.cargar()["separar"]:
        assert len(revision["partes"]) >= 2
        assert any(p["es_suceso"] for p in revision["partes"])
        assert revision["motivo"]["es"] and revision["motivo"]["en"]


def test_un_articulo_de_los_dos_sucesos_va_a_los_dos(
    vilna: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = copy.deepcopy(revisados.cargar()["separar"][0])
    # klix.ba cuenta el derribo y que el aeropuerto estuvo cerrado.
    revision["partes"][0]["fuentes"].append("s4")
    monkeypatch.setattr(revisados, "cargar", lambda: {"unir": [], "separar": [revision]})
    revisados.separar(vilna, AHORA, MODELOS, cliente=None)
    candidatos = {c["id"]: c for c in vilna.candidatos()}
    assert VILNA[3][0] in candidatos["CAND-20260914T0830-ETNG-aeropuerto"]["articulos"]
    (nuevo,) = [c for c in candidatos.values() if c.get("separado_de")]
    assert nuevo["articulos"] == [VILNA[2][0], VILNA[3][0]]
    # Con tres noticias, la regla de siempre deja este y funde en él la ficha del cierre.
    cierre = vilna.incidente("EODI-2026-00072")
    assert cierre is not None and incidentes.activo(cierre)
    assert {f["id"] for f in cierre["fuentes"]} == {"s1", "s2", "s4", "c1", "c2"}
    # El estado vuelve a empezar en «notificado», con la primera noticia que queda.
    assert cierre["estado"]["historial"][0]["estado"] == "notificado"


def test_sin_las_fuentes_de_otro_suceso_no_quedan_valores_sin_respaldo() -> None:
    """Lo que solo afirmaba la fuente que sale (las medidas, la fecha, los drones) no se queda
    sin origen: la exportación semanal no lo admitiría."""
    s1 = _fuente("s1", VILNA[0][0], VILNA[0][1], VILNA[0][2])
    s3 = _fuente("s3", VILNA[2][0], VILNA[2][1], VILNA[2][2])
    documento = _incidente("EODI-2026-00072", [s1, s3], "2026-09-14T22:00Z")
    documento["tiempo"]["inicio"] = ejemplos.instante("2026-09-14T22:00Z", "hora")
    documento["respuesta"] = {"medidas": ["cazas", "derribo"]}
    documento["drones"] = {"numero": {"min": 1, "max": 1}}
    documento["afirmaciones"] = [
        {"campo": campo, "valor": valor, "fuente_id": "s3", "confianza_extraccion": 0.9}
        for campo, valor in (("medidas", ["cazas", "derribo"]), ("drones", {"min": 1, "max": 1}),
                             ("inicio", "2026-09-14T22:00"))
    ]  # fmt: skip
    nuevo = revisados.sin_fuentes(documento, {VILNA[2][0]})
    assert nuevo is not None
    assert "respuesta" not in nuevo
    assert nuevo["drones"]["numero"] == "desconocido"
    assert nuevo["tiempo"]["inicio"] == {"valor": "2026-09-14T08:30Z", "precision": "aproximada"}
    assert nuevo["tiempo"]["origen_inicio"]["tipo"] == "publicacion"


def test_la_ficha_publicada_lleva_sus_sucesos_relacionados() -> None:
    from exportacion import geojson

    relacionado = {"id": "EODI-2026-00179", "separado_de": "EODI-2026-00072",
                   "nota": {"es": "juntaba dos sucesos", "en": "it merged two events"}}  # fmt: skip
    documento = _incidente("EODI-2026-00007", [
        _fuente("c1", "https://bt.dk/cierre", "2026-09-13T11:15:00Z", "Vilnius Lufthavn er lukket"),
    ], "2026-09-13T00:00Z")  # fmt: skip
    documento["relacionados"] = [relacionado]
    publico = geojson.vista_publica(documento)
    assert publico is not None and publico["relacionados"] == [relacionado]
    sin_punto = {**documento, "lugar": {"pais": "LT", "nivel": "pais"}}
    publico = geojson.sin_ubicacion(sin_punto)
    assert publico is not None and publico["relacionados"] == [relacionado]
