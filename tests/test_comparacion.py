"""Cobertura frente a la lista de referencia, sin red."""

from datetime import date

from recogida.comparacion import Punto, comparar, cubre, referencia, tabla


def test_la_referencia_carga_los_25_sucesos_con_coordenadas() -> None:
    sucesos = referencia()
    assert len(sucesos) == 25
    copenhague = sucesos[0]
    assert (copenhague.oaci, copenhague.fecha) == ("EKCH", date(2025, 9, 22))
    assert 55 < copenhague.lat < 56


def test_cubre_por_aeropuerto_o_distancia_y_ventana_de_fechas() -> None:
    copenhague = referencia()[0]
    assert cubre(copenhague, Punto("a", date(2025, 9, 23), 0, 0, "EKCH"))
    assert not cubre(copenhague, Punto("b", date(2025, 9, 26), 0, 0, "EKCH"))
    cerca = Punto("c", date(2025, 9, 22), copenhague.lat + 0.1, copenhague.lon, None)
    assert cubre(copenhague, cerca)
    lejos = Punto("d", date(2025, 9, 22), copenhague.lat + 1, copenhague.lon, None)
    assert not cubre(copenhague, lejos)


def test_tabla_cuenta_los_encontrados() -> None:
    sucesos = referencia()[:2]
    texto = tabla(comparar(sucesos, [Punto("CAND-1", date(2025, 9, 22), 0, 0, "EKCH")]))
    assert "| 2025-09-22 | DK | Aeropuerto de Copenhague | CAND-1 |" in texto
    assert "1 de 2 sucesos encontrados." in texto
