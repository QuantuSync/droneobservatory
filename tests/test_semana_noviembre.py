"""Los casos reales de la primera semana de noviembre de 2026, contra el ciclo de vida nuevo
(docs/ciclo_de_vida.md). Cada uno tenía ya su prueba del arreglo de su día; aquí está lo que
cambia de fondo, con el cerrojo en «aplicar» y sus identificadores de verdad.

Caso por caso (su prueba de entonces → lo que se prueba aquí):

- EODI-2026-00756 y 00757 (Letonia), una frase con dos días: test_dos_dias.py.
- EODI-2026-00746 y 00760 (Letonia), la publicada fundida en una recién dada de alta:
  test_parte_coincidente.py → aquí, la publicada sigue saliendo.
- EODI-2026-00743 y 00747 (Rumanía), la unión que el cerrojo devolvía cada hora: test_cerrojo.py y
  test_drones_de_otro_suceso.py → aquí, no se intenta ni deja versiones.
- EODI-2026-00770 y 00773 (Leipzig), vaivén cada hora y aviso con otros datos:
  test_vaiven_separadas.py y test_parte_separada.py → aquí, el aviso sale de lo publicado.
- EODI-2025-00106 y 00049 (Otopeni), una noticia retrospectiva repetía el suceso:
  test_otopeni_repetida.py (y la unión que se deshace entera, en test_ciclo_de_vida.py).
- EODI-2026-00771 (Hamburgo), la tarde de la víspera: test_tarde_vispera.py.
- EODI-2026-00765 (Leipzig), retrospectiva retenida 69 horas y retirada: test_retenidas.py → aquí,
  sin dirección porque nunca salió.
- EODI-2026-00622 (Melilla), una relectura perdía la fecha revisada: test_cerrojo.py → aquí, la
  invariante I3 la ve.
- EODI-2026-00766 (Moldavia), una relectura rebajaba la ficha: test_relectura.py.
- EODI-2026-00728 (Moldavia), el cerrojo devolvía lo que el filtro corregía:
  test_autoridad_00728.py → aquí, no en el filtro de entrada.
"""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from almacen.base import Almacen
from exportacion import publicar, puerta
from proceso import decidir, incidentes, invariantes, protegido
from recogida import avisos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import base, ficha, version_mala
from tests.test_control_fichas import AHORA
from tests.test_puerta import BUENO, MALO, _con_cierre, _minima

RAIZ = Path(__file__).resolve().parent
LETONIA_MARTES, LETONIA_NUEVA = "EODI-2026-00746", "EODI-2026-00760"
RUMANIA, RUMANIA_MANUAL = "EODI-2026-00743", "EODI-2026-00747"
LEIPZIG_DOMINGO = "EODI-2026-00773"
RETROSPECTIVA = "EODI-2026-00765"
MELILLA = "EODI-2026-00622"
MOLDAVIA = "EODI-2026-00728"


def _fila(id_: str, estado: str = puerta.PUBLICADA) -> dict[str, object]:
    return {
        "id": id_,
        "estado": estado,
        "fichero": publicar.INCIDENTES,
        "entrada": {"type": "Feature", "id": id_, "properties": {"id": id_}},
        "detalle": {},
    }


def test_00746_fundida_en_la_recien_nacida_00760_sigue_en_la_web() -> None:
    # 6/11/2026, 09:23 UTC: 00746 (publicada desde el 3/11) quedó fundida en 00760, dada de alta
    # en esa misma pasada, y su dirección pasó a redirigir a una ficha con 2 drones y otro día.
    filas = {LETONIA_MARTES: _fila(LETONIA_MARTES)}
    en_la_base = {
        LETONIA_MARTES: {"id": LETONIA_MARTES, "fusionado_en": LETONIA_NUEVA},
        LETONIA_NUEVA: {"id": LETONIA_NUEVA},
    }
    generados = {publicar.INCIDENTES: {"type": "FeatureCollection", "features": []}}
    mapa = puerta.ficheros(generados, filas, en_la_base)[publicar.INCIDENTES]
    # La nueva no ha pasado el control: no tiene fila, y la publicada no redirige a ella.
    assert [f["id"] for f in mapa["features"]] == [LETONIA_MARTES]
    assert "unidos" not in mapa
    assert invariantes.sin_direccion(filas, en_la_base) == []
    # Con la nueva ya publicada, sí: 308 a la que queda.
    filas[LETONIA_NUEVA] = _fila(LETONIA_NUEVA)
    filas[LETONIA_MARTES] = {
        **_fila(LETONIA_MARTES, puerta.UNIDA),
        "detalle": {"destino": LETONIA_NUEVA},
    }
    mapa = puerta.ficheros(generados, filas, en_la_base)[publicar.INCIDENTES]
    assert mapa["unidos"] == {LETONIA_MARTES: LETONIA_NUEVA}


def test_00747_en_00743_la_union_que_el_cerrojo_retiene_no_deja_nada() -> None:
    # Del 6 al 7/11/2026 la regla de fusión unía 00747 (del nivel manual) en 00743 y el cerrojo
    # lo devolvía, dos cambios cada hora (auditoría K). Con las fichas de verdad del nivel manual:
    assert {RUMANIA, RUMANIA_MANUAL} <= protegido.fichas_manuales()
    almacen = base(ficha(RUMANIA), ficha(RUMANIA_MANUAL))
    versiones = almacen.conexion.execute("SELECT count(*) FROM historial").fetchone()[0]
    for _ in range(3):
        assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS, frozenset()) == 0
    assert almacen.conexion.execute("SELECT count(*) FROM historial").fetchone()[0] == versiones
    assert almacen.fusiones() == []
    assert invariantes.versiones_iguales(almacen.cambios_desde("2000-01-01")) == []


def test_00773_el_aviso_lleva_la_version_publicada_no_la_de_la_base(tmp_path: Path) -> None:
    # 9/11/2026, 17:42 UTC: el aviso de 00773 salió con los datos que tenía la base (dos drones,
    # el sábado), no con los de la ficha que enseñaba la web.
    ruta = tmp_path / "eodi.sqlite"
    almacen = Almacen.abrir(ruta)
    almacen.guardar_incidente(
        _con_cierre(_minima(LEIPZIG_DOMINGO), BUENO), AHORA, VOCABULARIO_MODELOS
    )
    puerta.dar_pase(almacen, AHORA, [LEIPZIG_DOMINGO])
    publicar.publicar(almacen, AHORA, tmp_path / "salida")
    # La base cambia después y esa versión no pasa la puerta (el control no ha terminado).
    despues = datetime(2026, 10, 13, 15, 17, tzinfo=UTC)
    documento = almacen.incidente(LEIPZIG_DOMINGO)
    assert documento is not None
    almacen.guardar_incidente(_con_cierre(documento, MALO), despues, VOCABULARIO_MODELOS)
    publicar.publicar(almacen, despues, tmp_path / "salida")
    almacen.conexion.commit()
    almacen.cerrar()
    publicados = avisos.ids_publicados(tmp_path / "salida")
    internos = avisos.publicados_internos(ruta, publicados)
    assert internos[LEIPZIG_DOMINGO]["consecuencias"]["cierre"]["minutos"]["max"] == BUENO
    assert (
        avisos.documentos(ruta, publicados)[LEIPZIG_DOMINGO]["consecuencias"]["cierre"]["minutos"][
            "max"
        ]
        == MALO
    )
    assert avisos.distintos_de_lo_publicado(internos, tmp_path / "salida") == {}


def test_00765_retirada_sin_haber_salido_no_tiene_direccion(tmp_path: Path) -> None:
    # Retenida del 6 al 9/11/2026 y retirada sin publicarse: no hay dirección que explicar.
    real = json.loads((RAIZ / "fixtures" / "retenida_00765.json").read_text(encoding="utf-8"))
    documento = copy.deepcopy(real[RETROSPECTIVA])
    documento["retirado"] = {
        "fecha": {"valor": "2026-11-09T11:17Z", "precision": "minuto"},
        "motivo": "No es un suceso nuevo que se pueda fechar.",
        "motivo_en": "Not a new event that can be dated.",
    }
    filas: dict[str, dict[str, object]] = {}
    unidos, retirados = puerta.direcciones(filas, {RETROSPECTIVA: documento})
    assert (unidos, retirados) == ({}, {})
    # Si hubiera salido, su dirección explicaría la retirada con ese motivo.
    detalle = puerta.detalle_de_retirada(documento["retirado"], "2026-11-09T11:37:00Z")
    filas[RETROSPECTIVA] = {**_fila(RETROSPECTIVA, puerta.RETIRADA), "detalle": detalle}
    _, retirados = puerta.direcciones(filas, {RETROSPECTIVA: documento})
    assert retirados[RETROSPECTIVA]["motivo"]["en"] == "Not a new event that can be dated."
    assert retirados[RETROSPECTIVA]["fecha"] == "2026-11-09T11:17Z"


def test_00622_la_relectura_que_pierde_la_fecha_revisada_no_pasa_la_puerta() -> None:
    # 7/11/2026: al releer su candidato, la ficha pasaba del 18 de septiembre (revisado con su
    # cita) al 25, la fecha de publicación. El cerrojo ya la retiene al guardar; si aun así
    # llegase a la base, la invariante I3 no la deja salir.
    caso = json.loads((RAIZ / "cerrojo" / "relectura_00622.json").read_text(encoding="utf-8"))
    assert caso["guardado"]["id"] == MELILLA
    assert decidir.distinto_de_su_revision(caso["guardado"]) == []
    assert decidir.distinto_de_su_revision(caso["releida"]) == ["inicio"]
    assert invariantes.de_ficha(caso["guardado"]) == []
    assert invariantes.de_ficha(caso["releida"]) == [invariantes.I3]


def test_00728_el_cerrojo_no_devuelve_lo_que_el_filtro_de_entrada_corrige() -> None:
    # Noviembre de 2026: 6 retenciones del cerrojo con el filtro de entrada en la pila (00728,
    # 00765, 00770, 00773): la ficha era nueva, aún no había salido, y el cerrojo la trataba como
    # publicada.
    almacen = base(ficha(MOLDAVIA))
    almacen.guardar_cursor("control_fichas", {"vistos": {}})
    guardado = almacen.incidente(MOLDAVIA)
    assert guardado is not None and almacen.en_el_filtro(MOLDAVIA)
    corregida = version_mala(guardado, "inicio")
    assert almacen.guardar_incidente(corregida, AHORA, VOCABULARIO_MODELOS) is True
    queda = almacen.incidente(MOLDAVIA)
    assert queda is not None and queda["tiempo"]["inicio"] == corregida["tiempo"]["inicio"]
    # Publicada y con su día escrito por una frase, ya no cambia sin una fuente nueva que lo diga.
    puerta.dar_pase(almacen, AHORA, [MOLDAVIA])
    assert almacen.guardar_incidente(guardado, AHORA, VOCABULARIO_MODELOS) is True
    assert almacen.guardar_incidente(corregida, AHORA, VOCABULARIO_MODELOS) is False
    assert almacen.incidente(MOLDAVIA) == guardado
