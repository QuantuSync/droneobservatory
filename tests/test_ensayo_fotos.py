"""La foto de una base y la comparación de dos fotos (recogida/ensayo.py): lo que enseña el ensayo
de varias recogidas seguidas sobre la misma copia."""

import copy
from pathlib import Path

from almacen.base import Almacen
from esquema import Documento
from exportacion import publicar, puerta
from recogida import ensayo
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_control_fichas import AHORA
from tests.test_puerta import BUENO, ID, MALO, OTRA, _con_cierre, _minima


def _base(ruta: Path) -> Almacen:
    almacen = Almacen.abrir(ruta)
    almacen.guardar_incidente(_con_cierre(_minima(), BUENO), AHORA, VOCABULARIO_MODELOS)
    puerta.dar_pase(almacen, AHORA, [ID])
    almacen.conexion.commit()
    return almacen


def test_dos_fotos_seguidas_sin_nada_nuevo_no_tienen_diferencias(tmp_path: Path) -> None:
    ruta, salida = tmp_path / "eodi.sqlite", tmp_path / "salida"
    almacen = _base(ruta)
    publicar.publicar(almacen, AHORA, salida)
    almacen.conexion.commit()
    una = ensayo.foto(ruta, salida)
    publicar.publicar(almacen, AHORA, salida)
    almacen.conexion.commit()
    otra = ensayo.foto(ruta, salida)
    diferencias = ensayo.comparar(una, otra)
    assert ensayo.sin_cambios(diferencias)
    assert una["publicado"] == {ID: puerta.PUBLICADA}
    assert "Fichas con algún dato cambiado: 0" in ensayo.informe(diferencias)


def test_la_comparacion_dice_que_nace_que_cambia_y_que_sale(tmp_path: Path) -> None:
    ruta, salida = tmp_path / "eodi.sqlite", tmp_path / "salida"
    almacen = _base(ruta)
    publicar.publicar(almacen, AHORA, salida)
    almacen.conexion.commit()
    antes = ensayo.foto(ruta, salida)
    # Una ficha nueva y un dato que cambia en la que había.
    almacen.guardar_incidente(_con_cierre(_minima(OTRA), BUENO), AHORA, VOCABULARIO_MODELOS)
    documento = almacen.incidente(ID)
    assert documento is not None
    almacen.guardar_incidente(_con_cierre(documento, MALO), AHORA, VOCABULARIO_MODELOS)
    puerta.dar_pase(almacen, AHORA, [OTRA])
    publicar.publicar(almacen, AHORA, salida)
    almacen.conexion.commit()
    diferencias = ensayo.comparar(antes, ensayo.foto(ruta, salida))
    assert diferencias["nuevas"] == [OTRA]
    assert list(diferencias["cambios"]) == [ID] and "cierre" in diferencias["cambios"][ID]
    assert diferencias["por_campo"] == {"cierre": [ID]}
    assert diferencias["versiones_nuevas"] == 2
    assert diferencias["publicacion"]["nuevas"] == [OTRA]
    assert list(diferencias["publicacion"]["cambios"]) == [ID]
    assert not ensayo.sin_cambios(diferencias)
    texto = ensayo.informe(diferencias, "Recogida 1")
    assert f"- {ID} · cierre:" in texto and "Fichas nuevas (1)" in texto


def test_una_ficha_que_sale_sin_direccion_se_ve() -> None:
    vista: Documento = {"fusionado_en": None, "retirado": False}
    antes: Documento = {
        "fichas": {ID: vista}, "fusiones": [], "separaciones": [],
        "recuentos": {"versiones": 1}, "publicacion": {"fichas": {ID: vista}},
    }  # fmt: skip
    despues = copy.deepcopy(antes)
    despues["publicacion"] = {"fichas": {}, "unidos": {}, "retirados": []}
    assert ensayo.comparar(antes, despues)["publicacion"]["sin_direccion"] == [ID]
    despues["publicacion"]["retirados"] = [ID]
    assert ensayo.comparar(antes, despues)["publicacion"]["sin_direccion"] == []
