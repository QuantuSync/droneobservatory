import pytest

from recogida.plazo import Plazo, TiempoAgotado
from tests.test_descarga import Reloj

TOPE_S = 10.0


def test_el_plazo_cuenta_desde_que_se_crea() -> None:
    reloj = Reloj()
    reloj.ahora = 100.0
    plazo = Plazo(TOPE_S, reloj)
    reloj.ahora += 4.0
    assert plazo.restante() == TOPE_S - 4.0
    assert not plazo.agotado()
    plazo.comprobar()


def test_una_espera_que_no_cabe_agota_el_plazo() -> None:
    reloj = Reloj()
    plazo = Plazo(TOPE_S, reloj)
    plazo.comprobar(espera_s=TOPE_S / 2)
    with pytest.raises(TiempoAgotado, match="tope de 10 s agotado"):
        plazo.comprobar(espera_s=TOPE_S)


def test_plazo_agotado() -> None:
    reloj = Reloj()
    plazo = Plazo(TOPE_S, reloj)
    reloj.ahora += TOPE_S
    assert plazo.agotado()
    with pytest.raises(TiempoAgotado):
        plazo.comprobar()
