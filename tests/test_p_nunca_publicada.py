"""Las comprobaciones de protección (P, R, V, W, X) no frenan una ficha que nunca se ha publicado:
la coherencia corrige lo que marcan y la ficha sale (recogida/correccion.sin_publicar,
exportacion/puerta.py; desde el 16 de noviembre de 2026). Sobre una ficha publicada, la red sigue
como estaba (tests/test_puerta.py).

El caso real: EODI-2026-00847 (Chișinău, 15 de noviembre de 2026, «Alertă falsă cu drone deasupra
Chișinăului! AAC explică ce au observat, de fapt, oamenii pe cerul Capitalei»). La extracción la
dio por descartada con la declaración de la AAC dentro de la noticia, sin historial de la
presencia: la auditoría la marcaba con la P y la puerta la dejó fuera de la web 11 recogidas."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from exportacion import citas, publicar, puerta
from modelo import coste
from proceso import auditoria_fichas, protegido, rectificaciones
from proceso import correccion as comprobaciones
from recogida import control_fichas, correccion
from recogida.plazo import Plazo
from tests.ejemplos import VOCABULARIO_MODELOS

CASO = json.loads(
    (Path(__file__).parent / "fixtures" / "p_nunca_publicada_00847.json").read_text(
        encoding="utf-8"
    )
)
# La recogida de las 06:17 UTC del 16/11/2026, la última que la dejó fuera.
AHORA = datetime(2026, 11, 16, 6, 17, tzinfo=UTC)
ID = "EODI-2026-00847"
AAC = "gdelt-62a57fa6030c68ad-declaracion-1"
NOTICIA = "gdelt-62a57fa6030c68ad"
# La traducción guardada del nombre (la que la web enseñaba en `autoridades` de su entrada).
TRADUCIDAS = {"AAC": {"es": "la AAC", "en": "the AAC"}}


def _ficha() -> Documento:
    return copy.deepcopy(CASO["ficha"])


def _texto(fuente: Documento) -> str:
    """Lo guardado de su artículo: el titular de la noticia de news.yam.md."""
    return str(CASO["titular"]) if "news.yam.md" in str(fuente.get("enlace")) else ""


@pytest.fixture(autouse=True)
def _sin_descargas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})
    monkeypatch.setattr(Almacen, "texto_guardado", lambda self, fuente: _texto(fuente))


def _base() -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_ficha(), AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_traducciones(
        {citas.huella_texto(n): t for n, t in TRADUCIDAS.items()}, "2026-11-15T21:00:00Z"
    )
    return almacen


def _p(documento: Documento) -> bool:
    return auditoria_fichas.presencia_rebajada_sin_cierre(documento)


# --- La corrección, pura --------------------------------------------------------------------


def test_00847_tal_como_estaba_la_marca_la_p() -> None:
    ficha = _ficha()
    assert ficha["presencia_dron"] == rectificaciones.DESCARTADA
    assert "presencia_historial" not in ficha
    assert _p(ficha)


def test_la_autoridad_con_su_frase_literal_da_el_paso_del_historial() -> None:
    hecho = comprobaciones.presencia_sin_quien(_ficha(), _texto, TRADUCIDAS)
    assert hecho is not None
    nuevo, cambio = hecho
    (paso,) = nuevo["presencia_historial"]
    assert paso["valor"] == rectificaciones.DESCARTADA and paso["fuente_id"] == AAC
    assert paso["fecha"] == {"precision": "aproximada", "valor": "2026-11-15T20:00Z"}
    assert paso["quien"] == {"es": "la AAC", "en": "the AAC"}
    # La presencia no cambia; la AAC queda como quien la afirma.
    assert nuevo["presencia_dron"] == rectificaciones.DESCARTADA
    assert {"campo": "presencia_dron", "valor": "descartada", "fuente_id": AAC,
            "confianza_extraccion": 1.0} in nuevo["afirmaciones"]  # fmt: skip
    assert "AAC explică ce au observat" in cambio and "la AAC" in cambio
    assert not _p(nuevo) and rectificaciones.errores(nuevo) == []
    # Corregida, ya no hay nada que corregir.
    assert comprobaciones.presencia_sin_quien(nuevo, _texto, TRADUCIDAS) is None


def test_sin_traduccion_del_nombre_la_declara_una_autoridad() -> None:
    # Como una rectificación cuya autoridad no está en la tabla: el paso queda igual de válido.
    hecho = comprobaciones.presencia_sin_quien(_ficha(), _texto)
    assert hecho is not None
    assert hecho[0]["presencia_historial"][0]["quien"] == {
        "es": "una autoridad",
        "en": "an authority",
    }
    assert not _p(hecho[0])


def test_sin_la_frase_de_la_autoridad_en_su_articulo_queda_no_confirmada() -> None:
    hecho = comprobaciones.presencia_sin_quien(_ficha(), lambda fuente: "")
    assert hecho is not None
    nuevo, cambio = hecho
    assert nuevo["presencia_dron"] == rectificaciones.NO_CONFIRMADA
    assert "presencia_historial" not in nuevo
    assert not any(
        a["campo"] == "presencia_dron" and a["valor"] in rectificaciones.RECTIFICADOS
        for a in nuevo["afirmaciones"]
    )
    assert "no confirmada" in cambio and not _p(nuevo)


def test_una_noticia_sin_autoridad_no_rebaja_la_presencia() -> None:
    ficha = _ficha()
    ficha["fuentes"] = [f for f in ficha["fuentes"] if f["id"] == NOTICIA]
    ficha["estado"]["historial"] = ficha["estado"]["historial"][:1]
    ficha["estado"]["actual"] = "notificado"
    hecho = comprobaciones.presencia_sin_quien(ficha, _texto)
    assert hecho is not None
    assert hecho[0]["presencia_dron"] == rectificaciones.NO_CONFIRMADA


def test_con_historial_o_sin_rebajar_no_hay_nada_que_corregir() -> None:
    ficha = _ficha()
    ficha["presencia_dron"] = rectificaciones.NO_CONFIRMADA
    assert comprobaciones.presencia_sin_quien(ficha, _texto) is None
    con_historial = _ficha()
    con_historial["presencia_historial"] = [{
        "valor": "descartada", "fuente_id": AAC,
        "fecha": {"precision": "aproximada", "valor": "2026-11-15T20:00Z"},
    }]  # fmt: skip
    assert comprobaciones.presencia_sin_quien(con_historial, _texto) is None


# --- La coherencia de la recogida y la puerta ---------------------------------------------------


def _corregir(almacen: Almacen) -> correccion.Resumen:
    resultado = control_fichas.Resultado()
    llamador = control_fichas.Llamador(almacen, None, coste.Modo.CONTROL, AHORA, None, resultado)
    ctx = control_fichas.Contexto(almacen, AHORA, VOCABULARIO_MODELOS, llamador, resultado,
                                  None, None, almacen.controles())  # fmt: skip
    return correccion.corregir(ctx, Plazo(60))


def test_la_coherencia_corrige_00847_y_sale_en_la_web(tmp_path: Path) -> None:
    almacen = _base()
    puerta.dar_pase(almacen, AHORA, [ID])
    resumen = _corregir(almacen)
    assert ID in resumen.corregidas
    ficha = almacen.incidente(ID)
    assert ficha is not None and not _p(ficha)
    assert ficha["presencia_historial"][0]["fuente_id"] == AAC
    assert ficha["presencia_historial"][0]["quien"] == {"es": "la AAC", "en": "the AAC"}
    # La puerta, con la auditoría real: sin marca y publicada, con su historial y su cita.
    assert puerta.marcadas(almacen, AHORA).get(ID) is None
    publicar.publicar(almacen, AHORA, tmp_path)
    fila = almacen.publicado()[ID]
    assert fila["estado"] == puerta.PUBLICADA
    propiedades = fila["entrada"].get("properties", fila["entrada"])
    assert propiedades["presencia_dron"] == "descartada"
    assert json.dumps(propiedades, ensure_ascii=False).count("AAC") >= 1
    assert (almacen.cursor(puerta.CURSOR) or {}).get("sustituidas") == []
    # La recogida siguiente no cambia nada.
    antes = almacen.incidente(ID)
    resumen = _corregir(almacen)
    assert ID not in resumen.corregidas and almacen.incidente(ID) == antes


def test_lo_revisado_a_mano_no_se_corrige(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protegido, "_fijado_a_mano", lambda ficha, dato: dato == "presencia_dron")
    almacen = _base()
    puerta.dar_pase(almacen, AHORA, [ID])
    assert ID not in _corregir(almacen).corregidas
    ficha = almacen.incidente(ID)
    assert ficha is not None and "presencia_historial" not in ficha


@pytest.mark.parametrize("comprobacion", protegido.AUDITORIA)
def test_la_marca_de_proteccion_no_frena_una_ficha_que_nunca_salio(
    comprobacion: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Aunque la corrección no llegara a quitar la marca, la ficha que nunca salió no se queda
    # fuera de la web por ella: no hay versión publicada que guardar.
    almacen = _base()
    puerta.dar_pase(almacen, AHORA, [ID])
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {ID: [comprobacion]})
    publicar.publicar(almacen, AHORA, tmp_path)
    assert almacen.publicado()[ID]["estado"] == puerta.PUBLICADA
    assert (almacen.cursor(puerta.CURSOR) or {}).get("sustituidas") == []


def test_las_demas_condiciones_siguen_frenandola(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sin el pase del control no sale, aunque la marca ya no cuente.
    almacen = _base()
    puerta.dar_pase(almacen, AHORA)
    monkeypatch.setattr(puerta, "marcadas", lambda *_: {ID: ["P"]})
    publicar.publicar(almacen, AHORA, tmp_path)
    assert ID not in almacen.publicado()
    # Sin auditoría, tampoco.
    puerta.dar_pase(almacen, AHORA, [ID])

    def sin_auditoria(*_: Any) -> dict[str, list[str]]:
        raise RuntimeError("sin auditoría")

    monkeypatch.setattr(puerta, "marcadas", sin_auditoria)
    publicar.publicar(almacen, AHORA, tmp_path)
    assert ID not in almacen.publicado()
