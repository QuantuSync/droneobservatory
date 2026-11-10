"""Las partes de una separación revisada no van y vuelven cada hora. El caso es EODI-2026-00770
(Leipzig/Halle, el sábado 7 de noviembre de 2026) y EODI-2026-00773 (el domingo 8), con sus filas
reales del 10 de noviembre (tests/fixtures/vaiven_leipzig.json: candidatos, última extracción,
fichas, afirmaciones, decisión del filtro de entrada y cursor de la separación).

Del 9/11 a las 20:17 al 10/11 a las 00:17 UTC, en cada recogida:
- la agrupación de GDELT volvía a guardar los candidatos de las dos partes sin su «parte»;
- revisados.separar se la ponía con la fecha de ahora y las dos se volvían a extraer;
- la versión nueva se guardaba sin las citas revisadas de la Polizei Leipzig ni el enlace entre
  ellas («Un posible dron…», estado y presencia retenidos por el cerrojo), y segundos después
  separar y corregir la devolvían a lo revisado (auditoría K)."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import control_fichas as reglas
from proceso import extraccion, protegido
from proceso.noticias import nomenclator
from recogida import avisos, gdelt, revisados
from tests.ejemplos import VOCABULARIO_MODELOS

FIJAS = Path(__file__).parent / "fixtures"
DATOS: dict[str, list[dict[str, Any]]] = json.loads(
    (FIJAS / "vaiven_leipzig.json").read_text(encoding="utf-8")
)
AHORA = datetime(2026, 11, 10, 8, 17, tzinfo=UTC)
SABADO, DOMINGO = "EODI-2026-00770", "EODI-2026-00773"
CANDIDATO_DOMINGO = "CAND-20261109T1215-EDDP-aeropuerto-2"
POLIZEI = "Polizei Leipzig"


def _almacen(ruta: Path | str = ":memory:") -> Almacen:
    almacen = Almacen.abrir(ruta)
    con = almacen.conexion
    for fila in DATOS["incidentes"]:
        almacen._escribir_incidente(json.loads(fila["documento"]))
    for tabla in ("articulos", "candidatos", "extracciones", "cursores", "afirmaciones"):
        for fila in DATOS[tabla]:
            con.execute(
                f"INSERT OR IGNORE INTO {tabla} ({', '.join(fila)}) "
                f"VALUES ({', '.join('?' * len(fila))})",
                tuple(fila.values()),
            )
    for fila in DATOS["controles"]:
        con.execute(
            "INSERT INTO control_fichas (clave, fecha, documento) VALUES (?, ?, ?)",
            (fila["clave"], fila["fecha"], fila["documento"]),
        )
    con.commit()
    return almacen


@pytest.fixture
def leipzig(monkeypatch: pytest.MonkeyPatch) -> Almacen:
    """Las dos fichas como estaban, con el cerrojo en «aplicar», como en producción."""
    monkeypatch.setattr(protegido, "modo", lambda ruta=None: protegido.APLICAR)
    return _almacen()


def _cambios(almacen: Almacen) -> list[dict[str, Any]]:
    return list(almacen.cambios_desde("2026-01-01T00:00:00Z"))


def _retenidos(almacen: Almacen) -> list[str]:
    filas = almacen.conexion.execute(
        "SELECT clave FROM control_fichas WHERE clave LIKE 'retenido:%' ORDER BY id"
    )
    return [str(f[0]) for f in filas]


def _sin_control(documento: dict[str, Any] | None) -> dict[str, Any]:
    """Los datos de la ficha. Las afirmaciones, aparte: la de presencia de la prensa la quitaba
    la versión sin la cita de la policía (proceso/presencia.quitar_sin_base) y, con ella, se
    queda una vez."""
    assert documento is not None
    return {k: v for k, v in documento.items() if k not in {"control", "afirmaciones"}}


def test_la_ficha_rehecha_parte_de_lo_revisado(leipzig: Almacen) -> None:
    antes = {i: leipzig.incidente(i) for i in (SABADO, DOMINGO)}
    extraccion.reconstruir(leipzig, AHORA, VOCABULARIO_MODELOS)
    sabado, domingo = leipzig.incidente(SABADO), leipzig.incidente(DOMINGO)
    assert sabado is not None and domingo is not None
    # El sábado, igual que estaba: el titular revisado, confirmada por la Polizei Leipzig y
    # enlazada con el domingo.
    assert _sin_control(sabado) == _sin_control(antes[SABADO])
    assert sabado["titulo"]["es"].startswith("Un dron obliga a cerrar unos minutos la pista sur")
    assert [r["id"] for r in sabado["relacionados"]] == [DOMINGO]
    # El domingo, igual salvo lo que pide su revisión nueva: el cierre de media hora con la cita
    # de la policía (el control lo leía de la misma frase y el cerrojo lo retenía cada hora).
    assert domingo["consecuencias"]["cierre"]["minutos"] == {"min": 30, "max": 30}
    assert domingo["titulo"]["es"].startswith("Un dron obliga a cerrar media hora la pista norte")
    assert [r["id"] for r in domingo["relacionados"]] == [SABADO]
    for documento in (sabado, domingo):
        previo = antes[documento["id"]]
        assert previo is not None
        assert documento["estado"]["actual"] == "confirmado"
        assert documento["presencia_dron"] == "confirmada"
        assert documento["estado"] == previo["estado"]
        assert documento["fuentes"] == previo["fuentes"]
    # Ningún dato de las dos fichas se retiene: la versión rehecha no vuelve a lo de antes de la
    # revisión (solo queda la retención del lugar de la extracción del domingo, ya apuntada).
    assert _retenidos(leipzig) == ["retenido:EODI-2026-00773:lugar:0e1264e5a997"]


def test_rehacerla_otra_vez_no_cambia_nada(leipzig: Almacen) -> None:
    extraccion.reconstruir(leipzig, AHORA, VOCABULARIO_MODELOS)
    fichas = {i: leipzig.incidente(i) for i in (SABADO, DOMINGO)}
    cambios, retenidos = len(_cambios(leipzig)), _retenidos(leipzig)
    extraccion.reconstruir(leipzig, AHORA.replace(hour=9), VOCABULARIO_MODELOS)
    # Solo la hora de la última actualización, como en cualquier ficha rehecha; ningún dato.
    for cambio in _cambios(leipzig)[cambios:]:
        assert cambio["tabla"] == "incidentes"
        anterior, nuevo = cambio["anterior"], cambio["nuevo"]
        assert {k for k in set(anterior) | set(nuevo) if anterior.get(k) != nuevo.get(k)} == {
            "control"
        }
    assert _retenidos(leipzig) == retenidos
    for id_ in (SABADO, DOMINGO):
        ahora, antes = leipzig.incidente(id_), fichas[id_]
        assert ahora is not None and antes is not None
        assert _sin_control(ahora) == _sin_control(antes)
        assert ahora["afirmaciones"] == antes["afirmaciones"]


def test_el_control_reconoce_la_nota_de_la_policia(leipzig: Almacen) -> None:
    """La declaración de la Polizei Leipzig citada en la revisión sostiene el estado: el control
    no baja las fichas rehechas a notificado."""
    extraccion.reconstruir(leipzig, AHORA, VOCABULARIO_MODELOS)
    for id_ in (SABADO, DOMINGO):
        documento = leipzig.incidente(id_)
        assert documento is not None
        assert POLIZEI in reglas.declaraciones_de(documento)
        assert reglas.estado_sin_respaldo(documento) is None
        assert reglas.bajar_estado(documento, {"valor": "2026-11-10T08:17Z"}) is None


def _como_gdelt(almacen: Almacen) -> None:
    """Lo que hace la agrupación de GDELT con un artículo nuevo en la ventana de 12 horas: leer
    el candidato y volver a guardarlo."""
    for documento in almacen.candidatos():
        almacen.guardar_candidato(
            gdelt._documento_candidato(gdelt._candidato(documento, nomenclator()))
        )


def test_el_candidato_conserva_su_parte_al_agruparse() -> None:
    almacen = _almacen()
    antes = {c["id"]: c for c in almacen.candidatos()}
    _como_gdelt(almacen)
    for candidato in almacen.candidatos():
        assert candidato["parte"] == antes[candidato["id"]]["parte"]
        assert candidato == antes[candidato["id"]]


def test_la_parte_ya_extraida_no_se_vuelve_a_extraer(
    leipzig: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas: list[str] = []

    def extraer(almacen: Almacen, cliente: Any, candidato: Any, ahora: datetime) -> int:
        llamadas.append(candidato["id"])
        return 1

    monkeypatch.setattr(revisados, "_extraer", extraer)
    for hora in (8, 9, 10):
        _como_gdelt(leipzig)
        revisados.separar(leipzig, AHORA.replace(hour=hora), VOCABULARIO_MODELOS, object())
    assert llamadas == []
    for candidato in leipzig.candidatos():
        assert candidato["parte"]["desde"] == "2026-11-10T00:17Z"


def test_sin_aviso_hasta_tener_sus_datos(tmp_path: Path) -> None:
    ruta = tmp_path / "eodi.sqlite"
    _almacen(ruta).cerrar()
    # Las dos partes ya extraídas con su suceso: se avisan si toca.
    assert avisos.partes_sin_datos_propios(ruta) == set()
    almacen = Almacen.abrir(ruta)
    (domingo,) = [c for c in almacen.candidatos() if c["id"] == CANDIDATO_DOMINGO]
    # Recién nacida de la separación, sin su parte (el 9/11 a las 17:23 UTC): no se avisa.
    almacen.corregir_candidatos([{k: v for k, v in domingo.items() if k != "parte"}], "prueba")
    almacen.cerrar()
    assert avisos.partes_sin_datos_propios(ruta) == {DOMINGO}
    # Con su parte, pero aún sin extraer con ella: tampoco.
    almacen = Almacen.abrir(ruta)
    posterior = copy.deepcopy(domingo)
    posterior["parte"]["desde"] = "2026-11-10T01:17Z"
    almacen.corregir_candidatos([posterior], "prueba")
    almacen.cerrar()
    assert avisos.partes_sin_datos_propios(ruta) == {DOMINGO}
