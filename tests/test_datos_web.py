"""Los ficheros de la descarga abierta en una sola versión de los datos (recogida/datos_web.py)."""

import json

import pytest

from recogida import datos_web

BASE = "https://droneobservatory.eu/datos/"


def _web(horas: list[str]) -> tuple[datos_web.Leer, list[str]]:
    """Una web falsa: cada lectura de resumen.json da la siguiente hora de la lista."""
    pedidas: list[str] = []
    resumenes = iter(horas)

    def leer(url: str) -> bytes:
        pedidas.append(url)
        if url == BASE + "resumen.json":
            return json.dumps({"actualizado": next(resumenes)}).encode()
        return url.rsplit("/", 1)[1].encode()

    return leer, pedidas


def test_baja_los_ficheros_entre_dos_resumenes_iguales() -> None:
    leer, pedidas = _web(["10:17", "10:17"])
    resumen, ficheros = datos_web.bajar_version(leer, ["a.csv", "b.json"], lambda _s: None)
    assert resumen == {"actualizado": "10:17"}
    assert ficheros == {"a.csv": b"a.csv", "b.json": b"b.json"}
    assert pedidas == [
        BASE + "resumen.json",
        BASE + "a.csv",
        BASE + "b.json",
        BASE + "resumen.json",
    ]


def test_si_publica_una_recogida_en_medio_se_repite_tras_un_minuto() -> None:
    leer, _ = _web(["10:17", "11:17", "11:17", "11:17"])
    esperas: list[float] = []
    resumen, _ficheros = datos_web.bajar_version(leer, ["a.csv"], esperas.append)
    assert resumen == {"actualizado": "11:17"}
    assert esperas == [60.0]


def test_si_cambian_en_cada_intento_no_da_nada_por_bueno() -> None:
    leer, _ = _web([str(i) for i in range(2 * datos_web.INTENTOS)])
    with pytest.raises(datos_web.DatosCambiantes):
        datos_web.bajar_version(leer, ["a.csv"], lambda _s: None)
