"""La hora local de la frase que el extractor copió como si fuera UTC (proceso/fechas.hora_en_utc)
y la comprobación J de la auditoría."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from proceso import auditoria_fichas, fechas

BERLIN = ZoneInfo("Europe/Berlin")
CHISINAU = ZoneInfo("Europe/Chisinau")
POLICIA_BREMEN = (
    "Die Drohne wurde gegen 19.30 Uhr im unmittelbaren Bereich des Airports gesichtet, wie ein "
    "Sprecher der Polizei mitteilte."
)


def momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


def test_bremen_en_noviembre_es_utc_mas_uno() -> None:
    # EODI-2025-00007: «gegen 19.30 Uhr» el 2 de noviembre de 2025 (hora de invierno).
    hecho = fechas.hora_en_utc(momento("2025-11-02T19:30"), "minuto", POLICIA_BREMEN, BERLIN)
    assert hecho == momento("2025-11-02T18:30")


def test_en_horario_de_verano_es_utc_mas_tres() -> None:
    # EODI-2026-00136: «la ora 3.16» del 20 de agosto de 2026 en Moldavia (UTC+3): 00:16 UTC.
    frase = (
        "Potrivit Ministerului Apărării de la Chișinău, drona a fost detectată joi, 20 august, "
        "la ora 3.16."
    )
    hecho = fechas.hora_en_utc(momento("2026-08-20T03:16"), "minuto", frase, CHISINAU)
    assert hecho == momento("2026-08-20T00:16")


def test_bien_convertida_u_otra_hora_no_se_toca() -> None:
    assert fechas.hora_en_utc(momento("2025-11-02T18:30"), "minuto", POLICIA_BREMEN, BERLIN) is None
    assert fechas.hora_en_utc(momento("2025-11-02T17:00"), "minuto", POLICIA_BREMEN, BERLIN) is None
    assert fechas.hora_en_utc(momento("2025-11-02T19:30"), "dia", POLICIA_BREMEN, BERLIN) is None
    sin_hora = "Der Flugverkehr am Bremer Flughafen ist nach einer Drohnensichtung unterbrochen."
    assert fechas.hora_en_utc(momento("2025-11-02T19:30"), "minuto", sin_hora, BERLIN) is None


def test_la_ficha_pasa_inicio_y_fin_a_utc() -> None:
    articulos = [{"url": "https://kreiszeitung.de/a", "fecha": "2025-11-02T21:45:00Z",
                  "pais": "DE", "idioma": "de", "titular": "Drohne in Bremen"}]  # fmt: skip
    campos = {
        "inicio": {"valor": "2025-11-02T19:30", "fuente": 1,
                   "frase": "Am Sonntagabend wurde die Drohne gegen 19.30 Uhr gesichtet."},
        "inicio_precision": {"valor": "minuto", "fuente": 1},
    }  # fmt: skip
    hecho = fechas.inicio_de_ficha(
        campos, ["https://kreiszeitung.de/a"], articulos, "2025-11-02T21:45:00Z", "DE"
    )
    assert hecho.valor == momento("2025-11-02T18:30")
    assert hecho.desfase == timedelta(hours=1)
    assert "hora local (Europe/Berlin)" in hecho.motivo


def ficha(inicio: str, frase: str, pais: str = "DE") -> dict[str, object]:
    return {
        "id": "EODI-2025-00007",
        "estado": {"actual": "confirmado"},
        "tiempo": {"inicio": {"valor": inicio, "precision": "minuto"}},
        "lugar": {"pais": pais},
        "fuentes": [{"id": "f1", "frase_origen": frase}],
    }


def test_auditoria_j_marca_la_hora_local_tomada_como_utc() -> None:
    mal = ficha("2025-11-02T19:30Z", POLICIA_BREMEN)
    bien = ficha("2025-11-02T18:30Z", POLICIA_BREMEN)
    assert auditoria_fichas._j(mal)
    assert not auditoria_fichas._j(bien)
    assert auditoria_fichas.auditar([mal])["J"] == ["EODI-2025-00007"]
