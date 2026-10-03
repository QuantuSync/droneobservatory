"""Barrido dirigido de España, puertos y presas, y scripts del servidor del catálogo vivo y del
barrido. Sin red."""

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from recogida import barrido_dirigido, busqueda_dirigida

RAIZ = Path(__file__).resolve().parent.parent


def _titular(texto: str, url: str = "https://medio.es/1") -> dict[str, Any]:
    return {"titular": texto, "url": url, "fecha": "2025-03-01T10:00:00Z", "idioma": "es"}


def test_halla_instalaciones_espanolas_y_localidades_con_instalacion() -> None:
    nombres = barrido_dirigido.lugares_buscados()
    hallados = barrido_dirigido.hallar(
        [
            _titular("Dron sobre la central nuclear de Cofrentes"),
            _titular("Detenido un hombre por volar un dron sobre la cárcel de Algeciras"),
            _titular("Un dron obliga a cerrar el aeropuerto de Palma de Mallorca"),
            _titular("Espectáculo de drones en Madrid para la fiesta"),
            _titular("Un dron ruso impacta en la central nuclear de Chernóbil"),
            _titular("Rumanía halla restos de un dron a baja altura"),
        ],
        nombres,
    )
    textos = [h["titular"] for h in hallados]
    assert "Espectáculo de drones en Madrid para la fiesta" not in textos
    # «La Central» o «Central» no nombran ningún sitio: no casan con cualquier central.
    assert "Un dron ruso impacta en la central nuclear de Chernóbil" not in textos
    # Un nombre de una sola palabra escrito en minúscula es una palabra corriente.
    assert "Rumanía halla restos de un dron a baja altura" not in textos
    assert len(hallados) == 3
    assert all(h["lugares_dirigidos"] for h in hallados)


def test_los_puertos_y_presas_de_europa_tambien_se_buscan() -> None:
    nombres = barrido_dirigido.lugares_buscados()
    tipos = {t for lista in nombres.values() for _, t in lista}
    assert {"puerto", "presa"} <= tipos
    # Las localidades y las subestaciones no se buscan por su nombre solo.
    assert not tipos & barrido_dirigido.NO_BUSCADOS


def test_la_lectura_solo_pide_los_dias_que_faltan(tmp_path: Path) -> None:
    busqueda_dirigida.guardar_dia(tmp_path, date(2025, 1, 2), [_titular("ya leído")])
    pedidas: list[datetime] = []

    def lector(_plazo: Any) -> Any:
        def leer(franja: datetime) -> list[Any]:
            pedidas.append(franja)
            return []

        return leer

    cuentas = barrido_dirigido.leer(tmp_path, date(2025, 1, 1), date(2025, 1, 3), 2, lector, 60)
    assert cuentas["faltaban"] == 2 and cuentas["leidos"] == 2
    assert {f.date() for f in pedidas} == {date(2025, 1, 1), date(2025, 1, 3)}
    # Reanudable: con todo guardado no se pide nada.
    pedidas.clear()
    assert barrido_dirigido.leer(tmp_path, date(2025, 1, 1), date(2025, 1, 3), 2, lector, 60)[
        "faltaban"] == 0  # fmt: skip
    assert not pedidas


def test_la_busqueda_deja_lo_hallado_sin_repetir(tmp_path: Path) -> None:
    dia = date(2025, 3, 1)
    texto = "Dron sobre la central nuclear de Cofrentes"
    busqueda_dirigida.guardar_dia(tmp_path, dia, [_titular(texto), _titular(texto)])
    resumen = barrido_dirigido.buscar(tmp_path, dia, dia)
    assert resumen["articulos"] == 1 and resumen["dias_leidos"] == 1
    hallados = json.loads((tmp_path / "dirigido" / "hallados.json").read_text(encoding="utf-8"))
    assert hallados["articulos"][0]["lugares_dirigidos"]


def test_el_modo_de_gasto_del_barrido_dirigido_tiene_su_limite() -> None:
    from modelo import coste

    assert coste.limite(coste.Modo.DIRIGIDA) == 3.00
    assert not coste.diario(coste.Modo.DIRIGIDA)


# --- Scripts del servidor ----------------------------------------------------------------


def _texto(nombre: str) -> str:
    return (RAIZ / "servidor" / nombre).read_text(encoding="utf-8")


def test_el_catalogo_vivo_tiene_su_cerrojo_su_unidad_y_su_temporizador() -> None:
    script = _texto("catalogo.sh")
    assert '"$CERROJO_CATALOGO"' in script and not re.search(r'"\$CERROJO"', script)
    assert "-m recogida.catalogo_vivo barrer" in script
    configuracion = _texto("configuracion.sh")
    assert 'CERROJO_CATALOGO="$SECRETOS/catalogo.lock"' in configuracion
    assert 'CATALOGO_DATOS="${EODI_CATALOGO_DATOS:-$CASA/datos/catalogo}"' in configuracion
    instalar = _texto("instalar.sh")
    unidad = instalar.split('cat > "/etc/systemd/system/$UNIDAD_CATALOGO.service"')[1].split("FIN")[
        1
    ]
    assert "ExecStart=/usr/bin/env bash $CLON/servidor/catalogo.sh" in unidad
    assert "Nice=$CATALOGO_NICE" in unidad and "IOSchedulingClass=idle" in unidad
    temporizador = instalar.split('cat > "/etc/systemd/system/$UNIDAD_CATALOGO.timer"')[1]
    assert "OnCalendar=$CALENDARIO_CATALOGO" in temporizador
    assert '"$UNIDAD_CATALOGO.timer"' in _texto("reconstruir.sh")


def test_el_barrido_dirigido_busca_sin_cerrojo_e_incorpora_con_el_de_la_recogida() -> None:
    script = _texto("dirigido.sh")
    busca = script.index("-m recogida.barrido_dirigido buscar")
    cerrojo = script.index('exec 9> "$CERROJO"')
    incorpora = script.index("-m recogida.barrido_dirigido incorporar")
    assert busca < cerrojo < incorpora
    assert 'DIRIGIDO_INFORME="$CASA/dirigido-informe.json"' in _texto("configuracion.sh")


def test_la_recogida_horaria_incorpora_el_catalogo_vivo() -> None:
    horaria = (RAIZ / "recogida" / "horaria.py").read_text(encoding="utf-8")
    assert "catalogo_vivo.paso_horario(almacen)" in horaria


def test_los_articulos_de_la_base_que_nombran_un_lugar_buscado() -> None:
    from almacen.base import Almacen

    almacen = Almacen.abrir()
    base: dict[str, Any] = {"medio": "medio.es", "idioma": "es", "pais": None, "temas": [],
                            "lugares": [], "replicas": 0, "titular_normalizado": "x"}  # fmt: skip
    almacen.guardar_articulo({**base, "url": "https://medio.es/a", "fecha": "2025-03-01T10:00Z",
                              "titular": "Dron sobre la central nuclear de Cofrentes"})  # fmt: skip
    almacen.guardar_articulo({**base, "url": "https://medio.es/b", "fecha": "2024-03-01T10:00Z",
                              "titular": "Dron sobre la central nuclear de Cofrentes"})  # fmt: skip
    almacen.guardar_articulo({**base, "url": "https://medio.es/c", "fecha": "2025-03-01T10:00Z",
                              "titular": "Espectáculo de drones en Madrid"})  # fmt: skip
    hallados = barrido_dirigido.articulos_de_la_base(almacen)
    assert [d["url"] for d, _ in hallados] == ["https://medio.es/a"]
    assert hallados[0][1]
