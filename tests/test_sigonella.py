"""Sigonella, 20 de noviembre de 2026 (EODI-2026-00937 y EODI-2026-00997).

leggo.it volvió a publicar la nota de Il Messaggero del 21/11 («l'allerta è scattata nella serata
di ieri») y GDELT la vio el 24/11 a las 12:30: con esa fecha, su «ieri» fue el 23 y salió otra
ficha del mismo suceso, EODI-2026-00997. La página decía haberse publicado el 21/11 a las 11:50
(datePublished). Desde el 25/11 manda la fecha de la página cuando es claramente anterior a la de
GDELT (proceso/extraccion.con_fechas_de_pagina) y la auditoría marca una ficha así (AF)."""

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from modelo import paginas
from proceso import auditoria_fichas, fechas
from recogida import extractor
from tests import ejemplos
from tests.test_extraccion import TEXTO, almacen, candidato_con_articulos  # noqa: F401
from tests.test_gdelt import AHORA

LEGGO = """<html><head>
<meta property="article:published_time" content="2026-11-21T11:50:29+01:00">
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
 {"@type": "NewsArticle", "datePublished": "2026-11-21T11:50:29+0100",
  "dateModified": "2026-11-21T12:54:54+0100"}]}</script>
</head><body><p>Droni su Sigonella: l'allerta è scattata nella serata di ieri.</p></body></html>"""


def test_la_fecha_de_la_pagina_es_la_ultima_que_declara() -> None:
    # La de modificación manda: una página viva nunca se fecha antes de lo que dice.
    assert paginas.fecha_de_la_pagina(LEGGO) == datetime(2026, 11, 21, 11, 54, 54, tzinfo=UTC)
    assert paginas.fecha_de_la_pagina("<p>sin fecha</p>") is None
    # Sin zona no vale: la hora sería de un huso desconocido.
    sin_zona = '<meta property="article:published_time" content="2026-11-21T11:50:29">'
    assert paginas.fecha_de_la_pagina(sin_zona) is None


@pytest.mark.parametrize(
    ("antes", "despues", "corrige"),
    [
        (timedelta(days=3), timedelta(0), True),
        (timedelta(hours=8), timedelta(0), False),
        (timedelta(days=3), timedelta(days=10), False),
    ],
)
def test_la_nota_vieja_que_gdelt_ve_tarde_toma_la_fecha_de_su_pagina(
    almacen: Almacen,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    antes: timedelta,
    despues: timedelta,
    corrige: bool,
) -> None:
    # 3 días: la copia de leggo.it. 8 horas: lo más que tardó GDELT en ver una nota nueva en las
    # fuentes de las fichas del 15/10 al 25/11. Diez días después, la dirección puede servir otra
    # página (cedarnews.net): no se corrige.
    candidato = candidato_con_articulos(almacen, horas=2)
    url = candidato["articulos"][0]
    (vista,) = [a["fecha"] for a in almacen.articulos_de([url])]
    de_la_pagina = datetime.fromisoformat(vista.replace("Z", "+00:00")) - antes

    def leer(_d: object, _url: str, **_k: object) -> paginas.Pagina:
        return paginas.Pagina(TEXTO, fecha=de_la_pagina)

    monkeypatch.setattr(paginas, "leer_pagina", leer)
    (peticion,) = extractor.preparar_todas(
        almacen,
        [candidato],
        lambda: None,  # type: ignore[arg-type,return-value]
        AHORA + despues,
    )
    esperada = de_la_pagina.strftime("%Y-%m-%dT%H:%M:%SZ") if corrige else vista
    assert {a["url"]: a["fecha"] for a in peticion.articulos}[url] == esperada
    assert {f.url: f.fecha for f in peticion.fuentes}[url] == esperada
    # En la base, con la fecha de GDELT en el historial.
    assert [a["fecha"] for a in almacen.articulos_de([url])] == [esperada]
    pasos = [p for p in almacen.historial(url) if "fecha" in (p["anterior"] or {})]
    assert [(p["anterior"], p["nuevo"]["fecha"]) for p in pasos] == (
        [({"fecha": vista}, esperada)] if corrige else []
    )


def _sigonella(id_: str, inicio: str, motivo: str, tipo: str, fuentes: list[str]) -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["id"] = id_
    documento["tiempo"] = {
        "inicio": ejemplos.instante(inicio, "dia"),
        "origen_inicio": {"fuente_id": "F-1", "motivo": motivo, "tipo": tipo},
    }
    documento["lugar"] = {"punto": {"lat": 37.40353, "lon": 14.91737}, "radio_km": 5.0,
                          "pais": "IT", "nivel": "instalacion", "suceso": "Sigonella"}  # fmt: skip
    documento["objetivo"] = {"categoria": "aeropuerto", "nombre": "Base aerea di Sigonella",
                             "oaci": "LICZ"}  # fmt: skip
    documento["fuentes"] = [
        {**ejemplos.fuente(f"F-{n}", "C"), "fecha": ejemplos.instante(fecha, "aproximada")}
        for n, fecha in enumerate(fuentes, 1)
    ]
    documento["estado"]["historial"][0]["fuente_id"] = "F-1"
    return documento


def fichas() -> tuple[Documento, Documento]:
    """Las dos fichas como estaban publicadas el 25/11 (datos de la base)."""
    primera = _sigonella(
        "EODI-2026-00937", "2026-11-20T00:00Z",
        "«20 novembre» en una nota publicada el 2026-11-21 01:45 (hora local del medio)",
        fechas.EXPLICITA,
        ["2026-11-21T00:45Z", "2026-11-21T02:45Z", "2026-11-21T13:30Z", "2026-11-23T17:00Z"],
    )  # fmt: skip
    copia = _sigonella(
        "EODI-2026-00997", "2026-11-23T00:00Z",
        "«ieri», «nella serata» en una nota publicada el 2026-11-24 13:30 (hora local del medio)",
        fechas.RELATIVA, ["2026-11-24T12:30Z", "2026-11-24T12:30Z"],
    )  # fmt: skip
    return primera, copia


def test_af_marca_la_copia_tardia_de_sigonella() -> None:
    primera, copia = fichas()
    assert auditoria_fichas.auditar([primera, copia])["AF"] == ["EODI-2026-00997→EODI-2026-00937"]
    # Unidas (00997 fundida en 00937), no queda nada.
    fundida = {**copia, "fusionado_en": "EODI-2026-00937"}
    assert auditoria_fichas.auditar([primera, fundida])["AF"] == []
    # Si el experto las dio por distintas, tampoco.
    par = frozenset({"EODI-2026-00937", "EODI-2026-00997"})
    assert auditoria_fichas.auditar([primera, copia], del_experto=frozenset({par}))["AF"] == []


@pytest.mark.parametrize(
    "cambio",
    [
        # Un suceso nuevo contado el mismo día (Brønnøysund, 28 y 30/9/2025).
        {"fuentes_copia": ["2026-11-23T20:30Z", "2026-11-24T08:00Z"]},
        # La nota llega el día siguiente a la otra (Kleine Brogel, 2 y 4/11/2025, sí son dos).
        {"fuentes_primera": ["2026-11-23T08:00Z"]},
        # Otra instalación.
        {"oaci": "LICC"},
        # Fechada por un día escrito, no por un «ayer».
        {"tipo": fechas.EXPLICITA},
    ],
)
def test_af_no_marca_sucesos_seguidos_contados_a_su_tiempo(cambio: dict[str, Any]) -> None:
    primera, copia = (copy.deepcopy(d) for d in fichas())
    if "fuentes_copia" in cambio:
        copia["fuentes"] = [
            {**ejemplos.fuente(f"F-{n}", "C"), "fecha": ejemplos.instante(f, "aproximada")}
            for n, f in enumerate(cambio["fuentes_copia"], 1)
        ]
    if "fuentes_primera" in cambio:
        primera["fuentes"] = [
            {**ejemplos.fuente(f"F-{n}", "C"), "fecha": ejemplos.instante(f, "aproximada")}
            for n, f in enumerate(cambio["fuentes_primera"], 1)
        ]
        primera["tiempo"]["inicio"] = ejemplos.instante("2026-11-22T00:00Z", "dia")
    if "oaci" in cambio:
        copia["objetivo"]["oaci"] = cambio["oaci"]
    if "tipo" in cambio:
        copia["tiempo"]["origen_inicio"]["tipo"] = cambio["tipo"]
    assert auditoria_fichas.auditar([primera, copia])["AF"] == []
