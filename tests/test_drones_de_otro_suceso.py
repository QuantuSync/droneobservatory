"""Rumanía, EODI-2026-00743 (6 de noviembre de 2026): el control no toma el número de drones de una
nota sobre otro suceso del mismo país, y una ficha con el día de «la noche del 1 al 2» se enlaza
con la noche que empieza ese día (proceso/control_fichas.dia_de_otro_suceso,
proceso/cruces.dia_de_una_noche)."""

from typing import Any

from proceso import control_fichas as reglas
from proceso import cruces, suceso

DOS_DRONES = "când două drone au pătruns neautorizat în spațiul aerian al României"


def _ficha(motivo: str, dia: str = "2026-11-01", tipo: str = "explicita") -> dict[str, Any]:
    return {
        "id": "EODI-2026-09743",
        "tipo": "sobrevuelo",
        "lugar": {"pais": "RO", "nivel": "pais"},
        "tiempo": {
            "inicio": {"valor": f"{dia}T00:00Z", "precision": "dia"},
            "origen_inicio": {"fuente_id": "mapn", "motivo": motivo, "tipo": tipo},
        },
        "drones": {"numero": "desconocido"},
        "fuentes": [
            {
                "id": "mapn",
                "enlace": "https://www.mapn.ro/cpresa/19462",
                "frase_origen": "",
                "fecha": {"valor": "2026-11-02T00:00Z", "precision": "dia"},
            },
            {
                "id": "prompt",
                "enlace": "https://promptmedia.ro/2026/11/x",
                "frase_origen": "",
                "fecha": {"valor": "2026-11-05T15:00Z", "precision": "aproximada"},
            },
        ],
        "estado": {"actual": "notificado", "historial": []},
        "presencia_dron": "no_confirmada",
        "afirmaciones": [
            # promptmedia.ro contaba «incidentul din seara de 31 octombrie» (EODI-2026-00719).
            {"campo": "inicio", "valor": "2026-10-31", "fuente_id": "prompt"},
            {"campo": "drones", "valor": {"min": 2, "max": 2}, "fuente_id": "prompt"},
        ],
    }


NOCHE_1_2 = "control de fichas: «În noaptea de 1 spre 2 noiembrie»"


def test_los_drones_de_una_nota_de_otro_dia_no_se_toman() -> None:
    ficha = _ficha(NOCHE_1_2)
    assert suceso.dia_de_otro_suceso(ficha, "prompt") == "2026-10-31"
    verificada = reglas.Verificada({"drones": ({"min": 2, "max": 2}, "prompt", DOS_DRONES)})
    corregida = reglas.aplicar(ficha, verificada, True, None)
    assert corregida.incidente["drones"]["numero"] == "desconocido"
    assert any("da otro día (2026-10-31)" in d for d in corregida.dudas)


def test_los_drones_de_una_nota_del_mismo_suceso_si() -> None:
    # La nota que da el día de la noche (el 1 o el 2) cuenta este suceso.
    ficha = _ficha(NOCHE_1_2)
    ficha["afirmaciones"][0]["valor"] = "2026-11-02"
    assert suceso.dia_de_otro_suceso(ficha, "prompt") is None
    verificada = reglas.Verificada({"drones": ({"min": 2, "max": 2}, "prompt", DOS_DRONES)})
    corregida = reglas.aplicar(ficha, verificada, True, None)
    assert corregida.incidente["drones"]["numero"] == {"min": 2, "max": 2}


def test_la_noche_que_empieza_el_dia_de_la_ficha() -> None:
    assert cruces.dia_de_una_noche(_ficha(NOCHE_1_2))
    assert cruces.dia_de_una_noche(
        _ficha("control de fichas: «on the night of 16-17 January»", "2025-01-16")
    )
    assert cruces.dia_de_una_noche(
        _ficha(
            "«noaptea trecuta» en una nota publicada el 2026-10-11 12:45 (hora local del medio)",
            "2026-10-10",
            "relativa",
        )
    )


def test_lo_que_no_dice_la_tarde_se_queda() -> None:
    # «În noaptea de 18 martie» no dice si es la del 17 o la del 18 (EODI-2026-00141); un
    # «overnight» cuyo día es el de la nota es la noche que acaba ese día (EODI-2026-00230).
    assert not cruces.dia_de_una_noche(
        _ficha("control de fichas: «în noaptea de 18 martie, spațiul aerian»", "2026-03-18")
    )
    assert not cruces.dia_de_una_noche(
        _ficha(
            "«overnight» en una nota publicada el 2026-08-13 10:30 (hora local del medio)",
            "2026-08-13",
            "relativa",
        )
    )
