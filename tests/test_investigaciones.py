"""Informes de investigación, cierres policiales y sentencias, sin red y con fragmentos reales."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from recogida import detalle, investigaciones
from recogida.descarga import AGENTE_EODI, Descargador, DescargaFallida, Respuesta

FIXTURES = Path(__file__).parent / "fixtures" / "detalle"
AHORA = datetime(2026, 10, 1, 12, tzinfo=UTC)


def leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def fuente(id_: str) -> dict[str, object]:
    return next(f for f in detalle.fuentes() if f["id"] == id_)


def descargador(paginas: dict[str, str | bytes], robots: str = "") -> Descargador:
    """Responde con los fragmentos por el comienzo de la dirección; lo demás, 404."""
    pedidas: list[str] = []

    def transporte(url: str, cabeceras: dict[str, str], limite: float) -> Respuesta:
        assert cabeceras["User-Agent"] == AGENTE_EODI
        pedidas.append(url)
        if url.endswith("/robots.txt"):
            return 200, {}, robots.encode("utf-8")
        for prefijo, contenido in paginas.items():
            if url.startswith(prefijo):
                datos = contenido if isinstance(contenido, bytes) else contenido.encode("utf-8")
                return 200, {}, datos
        return 404, {}, b""

    resultado = Descargador(transporte=transporte, dormir=lambda _: None, agente=AGENTE_EODI)
    resultado.pedidas = pedidas  # type: ignore[attr-defined]
    return resultado


def guardados(raiz: Path, fuente_id: str) -> list[dict[str, Any]]:
    datos: list[dict[str, Any]] = json.loads(
        detalle.ruta_documentos(raiz, fuente_id).read_text(encoding="utf-8")
    )
    return datos


def test_cada_fuente_de_la_configuracion_tiene_su_lector() -> None:
    from recogida import guardia_civil  # noqa: F401  (se registra al importarlo)

    tipos = {f["tipo"] for f in detalle.fuentes() if f["grupo"] == "investigaciones"}
    # La Guardia Civil tiene su propio módulo (recogida/guardia_civil.py).
    assert tipos - {"guardia_civil"} == set(investigaciones.RECOLECTORES)
    assert tipos <= set(detalle.RECOLECTORES)


# --- AAIB ---------------------------------------------------------------------------


def test_aaib_busqueda_y_pdf_del_informe() -> None:
    resultados = investigaciones.resultados_aaib(leer("inv_aaib_busqueda.json"))
    assert [r["date_of_occurrence"] for r in resultados] == [
        "2026-03-23",
        "2023-10-05",
        "2025-12-11",
    ]
    contenido = json.loads(leer("inv_aaib_contenido.json"))
    pdf = investigaciones.pdf_aaib(contenido)
    assert pdf is not None and pdf.endswith(
        "Experimental_Drone_Variant_4J_UAS_registration_N-A_04-26.pdf"
    )


def test_aaib_de_punta_a_punta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(investigaciones, "texto_pdf", lambda datos: leer("inv_aaib_informe.txt"))
    contenido = leer("inv_aaib_contenido.json")
    paginas: dict[str, str | bytes] = {
        "https://www.gov.uk/api/search.json": leer("inv_aaib_busqueda.json"),
        "https://www.gov.uk/api/content/aaib-reports/": contenido,
        "https://assets.publishing.service.gov.uk/": b"%PDF-1.7 fragmento",
    }
    n = investigaciones.recolector_aaib(
        fuente("aaib"), tmp_path, descargador(paginas), AHORA, False
    )
    assert n == 3
    documento = next(d for d in guardados(tmp_path, "aaib") if "experimental-drone" in str(d["id"]))
    assert documento["tipo"] == "informe_investigacion"
    assert documento["fecha"] == "2026-04-09"
    assert documento["pais"] == "GB"
    assert documento["pasajes"]
    # La segunda vez no vuelve a pedir los informes ya guardados.
    otro = descargador(paginas)
    investigaciones.recolector_aaib(fuente("aaib"), tmp_path, otro, AHORA, False)
    assert not any("/api/content/" in u for u in otro.pedidas)  # type: ignore[attr-defined]


# --- Havarikommissionen --------------------------------------------------------------


def test_havarikommissionen_casos_del_sitemap() -> None:
    sitemap = leer("inv_hcl_sitemap.xml")
    assert len(investigaciones.casos_hcl(sitemap, None)) == 2
    assert investigaciones.casos_hcl(sitemap, "2026-06-01") == [
        "https://havarikommissionen.dk/undersoegelsesresultater/soeg-i-luftfart/2026/2026-227"
    ]


def test_havarikommissionen_distingue_drones_y_fecha_de_publicacion() -> None:
    dron = investigaciones.caso_hcl(leer("inv_hcl_caso_dron.html"))
    avion = investigaciones.caso_hcl(leer("inv_hcl_caso_avion.html"))
    assert dron["drones"] and not avion["drones"]
    # El título lleva la fecha del suceso; la de publicación va después.
    assert (dron["fecha"], avion["fecha"]) == ("2026-07-02", "2025-01-16")
    assert str(dron["statement"]).endswith("/statement-2026-227")


def test_havarikommissionen_de_punta_a_punta(tmp_path: Path) -> None:
    base = "https://havarikommissionen.dk/undersoegelsesresultater/soeg-i-luftfart/"
    paginas: dict[str, str | bytes] = {
        "https://havarikommissionen.dk/sitemap.xml": leer("inv_hcl_sitemap.xml"),
        base + "2026/statement-2026-227": leer("inv_hcl_statement.html"),
        base + "2026/2026-227": leer("inv_hcl_caso_dron.html"),
        base + "2025/2025-17": leer("inv_hcl_caso_avion.html"),
    }
    f = fuente("havarikommissionen")
    assert (
        investigaciones.recolector_havarikommissionen(
            f, tmp_path, descargador(paginas), AHORA, True
        )
        == 1
    )
    (documento,) = guardados(tmp_path, "havarikommissionen")
    assert documento["id"] == "havarikommissionen:2026-227"
    assert any("batteri" in p for p in documento["pasajes"])
    # Las páginas ya vistas, de drones o no, no se vuelven a pedir.
    otro = descargador(paginas)
    investigaciones.recolector_havarikommissionen(f, tmp_path, otro, AHORA, False)
    assert otro.pedidas[-1].endswith("sitemap.xml")  # type: ignore[attr-defined]


# --- OVV -----------------------------------------------------------------------------


def test_ovv_resultados_de_la_busqueda() -> None:
    resultados = investigaciones.resultados_ovv(leer("inv_ovv_busqueda.html"))
    assert resultados[0]["titulo"] == "Near miss drone en helikopter, Amsterdam"
    assert resultados[0]["fecha"] == "2026-07-20"
    assert all(r["url"].startswith("https://onderzoeksraad.nl/onderzoek/") for r in resultados)


def test_ovv_de_punta_a_punta(tmp_path: Path) -> None:
    paginas: dict[str, str | bytes] = {
        "https://onderzoeksraad.nl/?s=": leer("inv_ovv_busqueda.html"),
        "https://onderzoeksraad.nl/onderzoek/": leer("inv_ovv_investigacion.html"),
    }
    n = investigaciones.recolector_ovv(fuente("ovv"), tmp_path, descargador(paginas), AHORA, False)
    documentos = guardados(tmp_path, "ovv")
    assert n == len(documentos) > 0
    assert all(d["tipo"] == "informe_investigacion" and d["idioma"] == "nl" for d in documentos)


# --- NSIA ----------------------------------------------------------------------------


def test_nsia_filas_e_informe() -> None:
    filas = investigaciones.filas_nsia(leer("inv_nsia_lista.html"))
    assert [f["url"].rsplit("/", 1)[-1] for f in filas if f["drones"]] == ["2024-06", "2024-04"]
    fecha, titulo, texto = investigaciones.informe_nsia(leer("inv_nsia_informe.html"))
    assert fecha == "2024-05-15"
    assert "DJI Mavic 3" in titulo
    assert "window" in texto


def test_nsia_de_punta_a_punta(tmp_path: Path) -> None:
    paginas: dict[str, str | bytes] = {
        "https://nsia.no/Aviation/Aviation/Published-reports?page=0": leer("inv_nsia_lista.html"),
        "https://nsia.no/Aviation/Aviation/Published-reports?page=": "<html><body></body></html>",
        "https://nsia.no/Aviation/Aviation/Published-reports/": leer("inv_nsia_informe.html"),
    }
    assert (
        investigaciones.recolector_nsia(fuente("nsia"), tmp_path, descargador(paginas), AHORA, True)
        == 2
    )


# --- PKBWL ---------------------------------------------------------------------------


def test_pkbwl_solo_los_sucesos_con_dron_y_su_ficha() -> None:
    registros = investigaciones.registros_pkbwl(leer("inv_pkbwl.json"))
    assert [r["nr_pkbwl"] for r in registros] == ["2026-0100", "2026-0067", "2026-0029"]
    documento = investigaciones.documento_pkbwl(fuente("pkbwl"), registros[1])
    assert documento["id"] == "pkbwl:2026-0067"
    assert documento["fecha"] == "2026-06-28"
    assert "Typ statku powietrznego: DJI Air 3" in documento["pasajes"][0]


def test_pkbwl_de_punta_a_punta(tmp_path: Path) -> None:
    paginas: dict[str, str | bytes] = {investigaciones.PKBWL: leer("inv_pkbwl.json")}
    # Sin histórico, solo los de los últimos 60 días.
    assert (
        investigaciones.recolector_pkbwl(
            fuente("pkbwl"), tmp_path, descargador(paginas), AHORA, False
        )
        == 1
    )
    assert (
        investigaciones.recolector_pkbwl(
            fuente("pkbwl"), tmp_path, descargador(paginas), AHORA, True
        )
        == 3
    )


# --- Policía danesa ------------------------------------------------------------------


def test_politi_lista_y_cierre_de_la_investigacion_de_copenhague() -> None:
    total, noticias = investigaciones.noticias_politi(leer("inv_politi_lista.html"))
    assert total == 5
    de_drones = [
        n for n in noticias if investigaciones.habla_de_drones(f"{n['Headline']} {n['Manchet']}")
    ]
    assert [n["DistrictName"] for n in de_drones] == ["Rigspolitiet", "Københavns Politi"]
    cierre = de_drones[1]
    texto = investigaciones._texto_html(leer("inv_politi_cierre.html"))
    assert investigaciones.tipo_politi(f"{cierre['Headline']}. {texto}") == "cierre_investigacion"
    assert (
        investigaciones.tipo_politi("Politiet har styrket indsatsen på droneområdet")
        == "nota_oficial"
    )


def test_politi_de_punta_a_punta(tmp_path: Path) -> None:
    paginas: dict[str, str | bytes] = {
        "https://politi.dk/nyhedsliste?": leer("inv_politi_lista.html"),
        "https://politi.dk/": leer("inv_politi_cierre.html"),
    }
    n = investigaciones.recolector_politi_dk(
        fuente("politi_dk"), tmp_path, descargador(paginas), AHORA, False
    )
    assert n == 2
    tipos = {d["autoridad"]: d["tipo"] for d in guardados(tmp_path, "politi_dk")}
    assert tipos["Københavns Politi"] == "cierre_investigacion"


def test_politi_el_filtro_de_drones_no_confunde_dronning() -> None:
    assert not investigaciones.de_drones_politi("Politiet efterforsker brand i Dronninglund")
    assert investigaciones.de_drones_politi("Droner observeret over Aalborg Lufthavn")
    assert investigaciones.de_drones_politi("Politiet har styrket indsatsen på droneområdet")


def test_politi_la_lista_lleva_fecha_distritos_y_pagina() -> None:
    url = investigaciones.lista_politi(
        "2026-06-01", "2026-10-01", ["Rigspolitiet", "Koebenhavns-Politi"], 2
    )
    assert url == (
        "https://politi.dk/nyhedsliste?fromDate=2026/6/1&toDate=2026/10/1"
        "&district=Rigspolitiet,Koebenhavns-Politi&page=2"
    )


# --- rechtspraak.nl ------------------------------------------------------------------


def test_rechtspraak_resumenes_y_sentencia() -> None:
    total, entradas = investigaciones.entradas_rechtspraak(leer("inv_rechtspraak_busqueda.xml"))
    assert total == 5
    # Nombra drones la de Amsterdam; la de Aruba es de un tribunal del Caribe.
    assert [e["ecli"] for e in entradas if investigaciones.de_drones_rechtspraak(e)] == [
        "ECLI:NL:GHAMS:2025:1930"
    ]
    fecha, tribunal, texto = investigaciones.sentencia_rechtspraak(
        leer("inv_rechtspraak_sentencia.xml")
    )
    assert (fecha, tribunal) == ("2025-07-22", "Gerechtshof Amsterdam")
    assert "drone" in texto


def test_rechtspraak_de_punta_a_punta(tmp_path: Path) -> None:
    paginas: dict[str, str | bytes] = {
        "https://data.rechtspraak.nl/uitspraken/zoeken": leer("inv_rechtspraak_busqueda.xml"),
        "https://data.rechtspraak.nl/uitspraken/content": leer("inv_rechtspraak_sentencia.xml"),
    }
    f = fuente("rechtspraak")
    assert (
        investigaciones.recolector_rechtspraak(f, tmp_path, descargador(paginas), AHORA, False) == 1
    )
    (documento,) = guardados(tmp_path, "rechtspraak")
    assert documento["id"] == "rechtspraak:ECLI:NL:GHAMS:2025:1930"
    assert documento["tipo"] == "sentencia"
    # La siguiente recogida pide solo lo modificado desde esta.
    otro = descargador(paginas)
    investigaciones.recolector_rechtspraak(f, tmp_path, otro, AHORA, False)
    assert "modified=2026-10-01T12:00:00" in otro.pedidas[1]  # type: ignore[attr-defined]


# --- Domsdatabasen -------------------------------------------------------------------


def test_domsdatabasen_la_busqueda_aproximada_no_da_casos_de_drones() -> None:
    texto = leer("inv_domsdatabasen.json")
    assert investigaciones.casos_doms(texto) == []
    caso = json.loads(texto)["cases"][0]
    documento = investigaciones.documento_doms(fuente("domsdatabasen"), caso)
    assert documento is not None
    assert (documento["fecha"], documento["autoridad"]) == ("2025-09-09", "Højesteret")
    assert documento["pasajes"] == []


# --- Reglas comunes ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("recolector", "id_"),
    [
        (investigaciones.recolector_aaib, "aaib"),
        (investigaciones.recolector_ovv, "ovv"),
        (investigaciones.recolector_pkbwl, "pkbwl"),
    ],
)
def test_robots_que_lo_prohibe_no_se_salta(
    tmp_path: Path, recolector: Callable[..., int], id_: str
) -> None:
    sin_paso = descargador({}, robots="User-agent: *\nDisallow: /\n")
    with pytest.raises(DescargaFallida, match="robots"):
        recolector(fuente(id_), tmp_path, sin_paso, AHORA, False)
    assert all(u.endswith("/robots.txt") for u in sin_paso.pedidas)  # type: ignore[attr-defined]


def test_un_contenido_inesperado_no_se_guarda(tmp_path: Path) -> None:
    bloqueo = descargador({investigaciones.PKBWL: "<html>Access denied</html>"})
    with pytest.raises(DescargaFallida):
        investigaciones.recolector_pkbwl(fuente("pkbwl"), tmp_path, bloqueo, AHORA, True)
    assert not detalle.ruta_documentos(tmp_path, "pkbwl").exists()


def test_los_identificadores_siguen_el_patron_del_esquema() -> None:
    assert investigaciones.identificador(
        "politi_dk", "koebenhavns-politi/nyhedsliste/x y/2026/06/25"
    ) == ("politi_dk:koebenhavns-politi/nyhedsliste/x-y/2026/06/25")
