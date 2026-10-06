"""Mejoras del detector de cierres (docs/informe_prevision.md): revisión de las candidatas del
archivo diario y, en directo, vigilados con cierres publicados, receptores caídos y un
despegue suelto que no reinicia la persistencia."""

from datetime import date
from typing import Any

from proceso import directo, mediciones, trafico, vuelos
from tests.test_directo import CIERRE, Movimientos, base_constante, hora, reproducir

DIA = "2026-05-04"


def anomalia(oaci: str = "EDDB", **cambios: Any) -> dict[str, Any]:
    documento = {
        "oaci": oaci, "inicio": f"{DIA}T12:00Z", "fin": f"{DIA}T13:00Z", "duracion_min": 60,
        "estado": "candidata", "precision": "movimientos", "llegadas_perdidas": 15,
        "salidas_perdidas": 15, "llegadas_vistas": 0, "salidas_vistas": 0, "llegadas_base": 15.0,
        "salidas_base": 15.0, "esperas": 3, "desvios": 6,
        "cobertura": {"indice": 0.9, "nivel": "alta"},
    }  # fmt: skip
    return {**documento, **cambios}


def estado(anomalias: list[dict[str, Any]], dias: dict[str, set[str]] | None = None) -> str:
    resultado = mediciones.estados_revisados(anomalias, dias or {})
    return resultado[f"{anomalias[0]['oaci']}/{anomalias[0]['inicio']}"]


def test_un_cierre_claro_sigue_siendo_candidata() -> None:
    assert estado([anomalia()]) == "candidata"


def test_cobertura_baja_del_dia() -> None:
    assert estado([anomalia(cobertura={"indice": 0.52, "nivel": "media"})]) == "cobertura_baja"


def test_muchos_aeropuertos_a_la_vez_es_la_fuente() -> None:
    otros = [anomalia(f"LFP{chr(65 + i)}") for i in range(mediciones.SIMULTANEAS_FUENTE)]
    assert estado([anomalia(), *otros]) == "caida_de_la_fuente"


def test_de_madrugada_poco_trafico_no_es_un_cierre() -> None:
    noche = anomalia(llegadas_base=2.0, salidas_base=2.5, llegadas_perdidas=4, salidas_perdidas=4,
                     duracion_min=90)  # fmt: skip
    assert estado([noche]) == "poco_trafico"


def test_sin_esperas_ni_desvios_son_los_receptores() -> None:
    assert estado([anomalia(esperas=0, desvios=1)]) == "sin_desvios"


def test_un_hueco_habitual_de_ese_aeropuerto() -> None:
    dias = {f"2026-04-{d:02d}" for d in range(6, 30)}
    previas = [
        anomalia(inicio=f"{d}T12:00Z", fin=f"{d}T13:00Z", estado="menor") for d in sorted(dias)[:6]
    ]
    # Seis días de 24 con un hueco igual: el 25 %, más del 15 %.
    previas = [{**p, "estado": "habitual"} for p in previas]
    assert estado([anomalia(), *previas], {"EDDB": dias}) == "habitual"


def test_casadas_meteorologia_y_menores_no_se_tocan() -> None:
    for intocable in ("casada", "meteorologia", "menor"):
        assert mediciones.estados_revisados([anomalia(estado=intocable)], {}) == {}


# --- En directo -----------------------------------------------------------------------------


def test_un_aeropuerto_con_cierre_publicado_se_vigila_con_cobertura_media() -> None:
    dia = date(2026, 9, 8)
    dias_base = trafico.dias_base(dia)

    def nivel(oaci: str, d: date) -> str | None:
        return trafico.ALTA if oaci == "EDDB" else trafico.MEDIA

    bases = base_constante(0.3)  # unos 58 movimientos al día
    assert len(dias_base) >= directo.DIAS_COBERTURA_ALTA
    assert directo.vigilables(dia, ["EDDB", "LUKK"], nivel, bases) == ["EDDB"]
    assert directo.vigilables(dia, ["EDDB", "LUKK"], nivel, bases, {"LUKK"}) == ["EDDB", "LUKK"]


def test_un_despegue_en_curso_no_reinicia_la_persistencia() -> None:
    class ConActividad(Movimientos):
        def actividad(self, ahora: float) -> set[str]:
            # Un despegue suelto que se ve durante unos minutos en mitad del cierre.
            return {"EKCH"} if hora(18.42) <= ahora <= hora(18.47) else set()

    detector = directo.Detector(base_constante())
    cambios = reproducir(ConActividad(CIERRE), detector, hora(15), hora(22))
    sin = reproducir(Movimientos(CIERRE), directo.Detector(base_constante()), hora(15), hora(22))
    assert cambios[0][1] == directo.POSIBLE
    # Sin reiniciar la persistencia, el aviso sale como mucho un ciclo después del despegue.
    assert cambios[0][0] - sin[0][0] <= max(0.0, hora(18.47) - sin[0][0]) + directo.PASO_S


def test_receptores_caidos() -> None:
    aeropuerto = vuelos.Aeropuerto("LTAI", "Antalya", "TR", 36.9, 30.8, 177.0, True, True)
    vivos = directo.Vivos((aeropuerto,))
    t0 = hora(9)
    posiciones = []
    # De 6:00 a 8:30, 20 aeronaves distintas cada media hora cerca del aeropuerto; después, 1.
    for k in range(5):
        for n in range(20):
            t = t0 - 3 * 3600 + k * 1800 + n
            posiciones.append(directo.Posicion(f"a{k}{n}", t, 36.9, 30.8, 3000.0, False))
    posiciones.append(directo.Posicion("b1", t0 - 600, 36.9, 30.8, 3000.0, False))
    vivos.anadir(posiciones)
    assert vivos.receptores_caidos("LTAI", t0)
    nuevas = [directo.Posicion(f"c{n}", t0 - 300 + n, 36.9, 30.8, 3000.0, False) for n in range(15)]
    vivos.anadir(nuevas)
    assert not vivos.receptores_caidos("LTAI", t0)
