"""Una ficha retenida siempre tiene salida (docs/control_fichas.md, «Retención»). El caso es
EODI-2026-00765 tal como estaba el 9 de noviembre de 2026: la búsqueda (6/11) de los autores del
intento de atentado con dron de agosto en el aeropuerto de Leipzig/Halle, retenida desde el 6/11
como noticia retrospectiva. El experto había respondido tres veces que era retrospectiva y que
ninguna frase da la fecha; con la misma huella no se le vuelve a preguntar y la retención no tenía
plazo. En ese aeropuerto hay dos fichas de agosto: 00134 (4/8, el intento) y 00058 (26/8)."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from modelo import coste
from proceso import control_fichas as reglas
from proceso import fechas
from recogida import control_fichas, entrada, visitas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

FIJAS = Path(__file__).parent / "fixtures"
FICHAS: dict[str, dict[str, Any]] = json.loads(
    (FIJAS / "retenida_00765.json").read_text(encoding="utf-8")
)
RETRO: dict[str, dict[str, Any]] = json.loads(
    (FIJAS / "retrospectivas.json").read_text(encoding="utf-8")
)
ID, ATAQUE, AGOSTO_26 = "EODI-2026-00765", "EODI-2026-00134", "EODI-2026-00058"
AHORA = datetime(2026, 11, 9, 9, 17, tzinfo=UTC)
DESDE = "2026-11-06T14:17:03Z"
# La última respuesta del experto (6/11, 17:17 UTC), tal como está en control_fichas.
RESPUESTA = {
    "fecha": "",
    "frase": "Das Bundeskriminalamt konnte bislang zwei Tatverdächtige identifizieren.",
    "fuente": 1, "misma_que": "", "precision": "", "retrospectiva": True,
    "motivo_es": "Las noticias cuentan una investigación policial sobre un ataque anterior, sin "
                 "fecha escrita.",
    "motivo_en": "The articles report a police manhunt over an earlier attack with no date.",
}  # fmt: skip


def _ficha(id_: str = ID) -> dict[str, Any]:
    return copy.deepcopy(FICHAS[id_])


def _ataque() -> dict[str, Any]:
    """00134, mínima: su lugar, su instalación y su fecha comprobada (4/8/2026)."""
    ficha = {**ejemplos.incidente_minimo(), "id": ATAQUE}
    ficha.update({c: copy.deepcopy(RETRO[ATAQUE][c]) for c in ("lugar", "objetivo", "tiempo")})
    return ficha


def _contexto(almacen: Almacen, ahora: datetime = AHORA) -> control_fichas.Contexto:
    resultado = control_fichas.Resultado()
    llamador = control_fichas.Llamador(almacen, None, coste.Modo.CONTROL, ahora, None, resultado)
    return control_fichas.Contexto(almacen, ahora, VOCABULARIO_MODELOS, llamador, resultado,
                                   None, None, almacen.controles())  # fmt: skip


def _base(ficha: dict[str, Any], *previas: dict[str, Any], respuesta: bool = True) -> Almacen:
    almacen = Almacen.abrir()
    for documento in (*previas, ficha):
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    guardada = almacen.incidente(ficha["id"])
    assert guardada is not None
    decisiones: dict[str, Any] = {
        entrada.clave(ficha["id"]): {"decision": entrada.PUBLICAR,
                                     "huella": entrada.huella(guardada)},
        reglas.clave_retrospectiva(ficha["id"]): {
            "decision": None, "huella": reglas.huella_fuentes(guardada),
            "motivo": f"ficha anterior del mismo sitio: {AGOSTO_26}", "version": "retrospectiva/1",
            **({"respuesta": RESPUESTA} if respuesta else {"espera_experto": DESDE}),
        },
    }  # fmt: skip
    almacen.guardar_controles(decisiones, DESDE)
    return almacen


def _retener(almacen: Almacen, desde: str = DESDE) -> tuple[dict[str, Any], Any]:
    ctx = _contexto(almacen)
    vistos = {d["id"]: DESDE for d in almacen.incidentes() if d["id"] != ID}
    cursor = {"vistos": vistos, "retenidos": {ID: {"desde": desde}}}
    return control_fichas.retener(ctx, cursor, False, con_entrada=True), ctx.resultado


def test_00765_sin_fecha_se_retira_nombrando_las_fichas_del_sitio() -> None:
    almacen = _base(_ficha(), _ataque(), _ficha(AGOSTO_26))
    nuevo, resultado = _retener(almacen)
    assert ID not in nuevo["retenidos"]
    queda = almacen.incidente(ID)
    assert queda is not None and queda.get("retirado")
    assert "No es un suceso nuevo" in queda["retirado"]["motivo"]
    assert f"{AGOSTO_26}, {ATAQUE}" in queda["retirado"]["motivo"]
    assert ATAQUE in queda["retirado"]["motivo_en"]
    assert "12 horas" in resultado.liberados[ID]
    # Lo demás no se toca.
    assert all(d.get("retirado") is None for d in almacen.incidentes() if d["id"] != ID)


def test_antes_del_plazo_sigue_retenida() -> None:
    almacen = _base(_ficha(), _ataque(), _ficha(AGOSTO_26))
    hace_poco = (AHORA - timedelta(hours=11)).strftime("%Y-%m-%dT%H:%M:%SZ")
    nuevo, _ = _retener(almacen, hace_poco)
    assert nuevo["retenidos"][ID]["motivo"] == control_fichas.MOTIVO_RETROSPECTIVA
    queda = almacen.incidente(ID)
    assert queda is not None and not queda.get("retirado")


def test_sin_respuesta_del_experto_un_fallo_no_retira() -> None:
    # Ni una palabra de sus fuentes ni el experto dicen que sea un suceso anterior: solo comparte
    # aeropuerto. Sigue retenida (y el resumen diario la señala a las 24 horas).
    almacen = _base(_ficha(), _ataque(), _ficha(AGOSTO_26), respuesta=False)
    nuevo, _ = _retener(almacen)
    assert ID in nuevo["retenidos"]
    queda = almacen.incidente(ID)
    assert queda is not None and not queda.get("retirado")


def _con_mes() -> dict[str, Any]:
    ficha = _ficha()
    ficha["fuentes"][1]["frase_origen"] = (
        "Anschlagsversuch mit einer Drohne auf den Flughafen Leipzig/Halle im August"
    )
    return ficha


def test_el_mes_de_la_frase_no_basta_si_hay_fichas_del_sitio_ese_mes() -> None:
    almacen = _base(_con_mes(), _ataque(), _ficha(AGOSTO_26))
    _retener(almacen)
    queda = almacen.incidente(ID)
    assert queda is not None and queda.get("retirado")
    assert queda["tiempo"]["inicio"]["valor"] == "2026-11-06T13:30Z"


def test_sin_fichas_del_sitio_ese_mes_sale_con_el_mes_y_su_cita() -> None:
    ficha = _con_mes()
    assert fechas.mes_retrospectivo(ficha) == (
        ficha["fuentes"][1]["id"],
        ficha["fuentes"][1]["frase_origen"],
        datetime(2026, 8, 1).date(),
    )
    almacen = _base(ficha)
    nuevo, resultado = _retener(almacen)
    queda = almacen.incidente(ID)
    assert queda is not None and not queda.get("retirado")
    assert queda["tiempo"]["inicio"] == {"valor": "2026-08-01T00:00Z", "precision": "aproximada"}
    origen = queda["tiempo"]["origen_inicio"]
    assert origen["tipo"] == fechas.EXPLICITA and "im August" in origen["motivo"]
    # Ya no pide fecha; espera una pasada más al filtro de entrada (su decisión ya no vale).
    assert reglas.pide_fecha(queda, almacen.incidentes()) is None
    assert nuevo["retenidos"][ID]["motivo"].startswith(control_fichas.NOTA_CON_FECHA)
    assert ID in resultado.corregidos


def test_el_resumen_marca_lo_retenido_mas_de_24_horas() -> None:
    datos = {
        "generado": "2026-11-09T07:17:03Z",
        "retenidos": {
            ID: {"desde": DESDE, "motivo": control_fichas.MOTIVO_RETROSPECTIVA},
            "EODI-2026-00799": {"desde": "2026-11-09T01:17:03Z", "motivo": "verificación"},
        },
    }
    assert visitas.atascadas(datos) == [(ID, 65, control_fichas.MOTIVO_RETROSPECTIVA)]
    control = {"pasadas": 1, "corregidas": {}, "clases": {}, "unidos": [], "retenidas": [ID],
               "gasto": 0.0, "errores": 0, "atascadas": visitas.atascadas(datos)}  # fmt: skip
    lineas = visitas.lineas_control(control)
    assert f"  Retenida más de 24 h: {ID}, 65 h (fecha del suceso sin respaldar " in "\n".join(
        lineas
    )
