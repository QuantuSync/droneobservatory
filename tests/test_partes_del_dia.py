"""Partes del mismo día (docs/informe_errores_datos.md, bloque 5): la noche de cada parte con
la regla única de los datos y de la web, el parte de toda la noche del ministerio ruso que
incluye los tramos ya publicados, los periodos mal guardados y los partes de resumen."""

import json
from pathlib import Path
from typing import Any

import pytest

from exportacion.ucrania import ataque_publico
from proceso import periodos, solapes
from proceso.ataques import jornada
from tests import ejemplos

CASOS = json.loads(
    (Path(__file__).parent / "fixtures" / "jornadas.json").read_text(encoding="utf-8")
)["casos"]


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: f"{c['inicio']}-{c['fin']}")
def test_la_misma_regla_que_la_web(caso: dict[str, Any]) -> None:
    periodo = {"inicio": {"valor": caso["inicio"]}, "fin": {"valor": caso["fin"]}}
    assert jornada(periodo) == caso["jornada"]


def test_cada_ataque_publicado_lleva_su_noche() -> None:
    publico = ataque_publico(ejemplos.ataque_completo())
    assert publico is not None
    assert publico["jornada"] == jornada(publico["periodo"])


def _parte(id_: str, inicio: str, fin: str, derribados: int, frase: str, publicado: str,
           precision: str = "minuto") -> dict[str, Any]:  # fmt: skip
    return {
        "id": id_, "sentido": "UA_RU",
        "periodo": {"inicio": {"valor": inicio, "precision": precision},
                    "fin": {"valor": fin, "precision": "aproximada" if precision != "minuto"
                            else "minuto"}},
        "derribados": {"min": derribados, "max": derribados},
        "fuentes": [{"frase_origen": frase, "fecha": {"valor": publicado}}],
        "regiones": [],
    }  # fmt: skip


def test_el_parte_de_toda_la_noche_incluye_los_tramos_ya_publicados() -> None:
    # Ministerio de Defensa ruso: un tramo de la tarde y, por la mañana, la noche entera
    # sin horas escritas (como los partes de 2025; desde 2026 las escribe).
    tramo = _parte(
        "EODI-UA-2024-0519",
        "2024-04-19T18:00Z",
        "2024-04-19T19:00Z",
        3,
        "В период с 21.00 до 22.00 мск уничтожены три БПЛА",
        "2024-04-19T19:30Z",
    )
    noche = _parte("EODI-UA-2024-0520", "2024-04-19T17:00Z", "2024-04-20T04:14Z", 50,
                   "В течение прошедшей ночи дежурными средствами ПВО уничтожены 50 БПЛА",
                   "2024-04-20T04:14Z", precision="aproximada")  # fmt: skip
    enlaces = solapes.enlaces([t for p in (tramo, noche) if (t := solapes.tramo(p))])
    assert enlaces == {"EODI-UA-2024-0519": (solapes.INCLUIDO_EN, "EODI-UA-2024-0520")}
    # Si el tramo dice más que la noche, no es su total: cuentan los dos.
    grande = {**tramo, "derribados": {"min": 60, "max": 60}}
    tramos = [t for p in (grande, noche) if (t := solapes.tramo(p))]
    assert solapes.enlaces(tramos) == {}


def _ataque_ua(frase: str, inicio: str, fin: str, publicado: str, precision: str) -> dict[str, Any]:
    documento = ejemplos.ataque_completo()
    documento.update(
        sentido="RU_UA",
        periodo={"inicio": {"valor": inicio, "precision": precision},
                 "fin": {"valor": fin, "precision": "aproximada"}},
    )  # fmt: skip
    documento["fuentes"] = [{**documento["fuentes"][0], "frase_origen": frase,
                             "fecha": {"valor": publicado, "precision": "minuto"}}]  # fmt: skip
    return documento


def test_periodos_mal_guardados() -> None:
    # t.me/kpszsu/9454: el parte de enero de 2024 escribe 2023.
    anio, motivos = periodos.corregido(
        _ataque_ua(
            "У ніч на 5 січня 2023 року ворог атакував ударними БпЛА типу «Shahed».",
            "2023-01-04T16:00Z",
            "2024-01-05T10:07Z",
            "2024-01-05T10:07Z",
            "aproximada",
        )
    )
    assert anio["periodo"]["inicio"]["valor"] == "2024-01-04T16:00Z" and motivos
    # t.me/kpszsu/2318: «Увечері 11 лютого» empieza esa tarde, no a medianoche.
    tarde, _ = periodos.corregido(
        _ataque_ua(
            "Увечері 11 лютого 2023 року російські окупаційні війська атакували",
            "2023-02-10T22:00Z",
            "2023-02-12T07:02Z",
            "2023-02-12T07:02Z",
            "dia",
        )
    )
    assert tarde["periodo"]["inicio"] == {"valor": "2023-02-11T16:00Z", "precision": "aproximada"}
    # t.me/kpszsu/2422: «Вночі 27 березня» publicado a las 23:03 acaba por la mañana.
    noche, _ = periodos.corregido(
        _ataque_ua(
            "Вночі 27 березня 2023 року противник атакував Україну ударними безпілотниками",
            "2023-03-26T15:00Z",
            "2023-03-27T23:03Z",
            "2023-03-27T23:03Z",
            "aproximada",
        )
    )
    assert noche["periodo"]["fin"]["valor"] == "2023-03-27T06:00Z"
    assert "resumen" not in noche


def test_parte_de_resumen_no_se_suma() -> None:
    semana, _ = periodos.corregido(
        _ataque_ua(
            "За минулий тиждень противник атакував Україну 1200 ударними БпЛА",
            "2026-09-27T15:00Z",
            "2026-10-04T05:00Z",
            "2026-10-04T08:00Z",
            "aproximada",
        )
    )
    assert semana["resumen"] is True
    ataques = [{**semana, "derribados": {"min": 900, "max": 900}},
               {**ejemplos.ataque_completo(), "derribados": {"min": 10, "max": 10}}]  # fmt: skip
    assert solapes.derribados_contados(ataques) == 10
