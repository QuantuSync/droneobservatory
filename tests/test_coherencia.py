"""Fechas coherentes en lo publicado (proceso/coherencia.py): casos del repaso del 13 de octubre."""

from esquema import Documento
from proceso import coherencia


def fecha(valor: str, precision: str = "aproximada") -> Documento:
    return {"valor": valor, "precision": precision}


def incidente(inicio: Documento, *pasos: tuple[str, Documento, str]) -> Documento:
    return {
        "id": "EODI-2026-09999",
        "tiempo": {"inicio": inicio},
        "estado": {
            "actual": pasos[-1][0],
            "historial": [{"estado": e, "fecha": f, "fuente_id": s} for e, f, s in pasos],
        },
        "fuentes": [{"id": s, "fecha": f} for _, f, s in pasos],
    }


def test_quien_confirma_tambien_avisa() -> None:
    # EODI-2026-00202: aviso el 26 de agosto (metro.co.uk), confirmación el 15 de julio (UKAB).
    doc = incidente(
        fecha("2026-06-08T20:08Z", "minuto"),
        ("notificado", fecha("2026-08-26T16:45Z"), "gdelt-x"),
        ("confirmado", fecha("2026-07-15T00:00Z", "dia"), "ukab-2026107"),
    )
    assert coherencia.contradicciones(doc)
    arreglado = coherencia.coherente(doc)
    assert arreglado["estado"]["historial"][0]["fecha"] == fecha("2026-07-15T00:00Z", "dia")
    assert arreglado["estado"]["historial"][0]["fuente_id"] == "ukab-2026107"
    assert arreglado["estado"]["actual"] == "confirmado"
    assert arreglado["tiempo"] == doc["tiempo"]
    assert coherencia.contradicciones(arreglado) == []
    # No toca el documento de la base.
    assert doc["estado"]["historial"][0]["fecha"]["valor"] == "2026-08-26T16:45Z"


def test_un_suceso_no_empieza_despues_de_su_primer_aviso() -> None:
    # EODI-2025-00001: noticias del 27 de diciembre, suceso fechado el 28 (solo el día).
    doc = incidente(
        fecha("2025-12-28T00:00Z", "dia"), ("notificado", fecha("2025-12-27T10:15Z"), "g")
    )
    arreglado = coherencia.coherente(doc)
    assert arreglado["tiempo"]["inicio"] == fecha("2025-12-27T00:00Z", "dia")
    assert coherencia.contradicciones(arreglado) == []


def test_un_inicio_con_hora_no_se_toca() -> None:
    doc = incidente(
        fecha("2026-09-14T22:00Z", "hora"),
        ("notificado", fecha("2026-09-14T08:30Z"), "a"),
        ("confirmado", fecha("2026-09-15T07:15Z"), "b"),
    )
    assert coherencia.coherente(doc) == doc
    assert coherencia.contradicciones(doc) == []
    doc["estado"]["historial"][0]["fecha"] = fecha("2026-09-12T08:30Z")
    assert coherencia.contradicciones(doc) == [
        "el primer aviso es de más de un día antes del suceso"
    ]
