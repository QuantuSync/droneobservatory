"""Descartes dudosos del modelo base: sin margen del experto, esperan (proceso/escalado.py, regla
descarte_dudoso). El 20 de octubre de 2026 el base dio por «no es incidente», con 0,6, el ataque
al buque Chelsea 3 frente a Bulgaria, y quedó descartado sin que lo viera el experto."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from almacen.base import Almacen
from modelo import coste, ficha
from proceso import escalado, extraccion
from tests.test_extraccion import AHORA, MODELOS, campo, ficha_ejemplo
from tests.test_modelos import (
    BASE,
    EXPERTO,
    SIN_CIERRE,
    Cliente,
    _gasto_experto,
    _leida,
    _peticion,
)  # fmt: skip
from tests.test_modelos import almacen as almacen

# Sin el cierre del ejemplo (un cierre ya hace crítico el caso).
DUDOSA = ficha_ejemplo(**SIN_CIERRE, es_incidente=campo(False, "Droner over", 0.6))
SEGURA = ficha_ejemplo(**SIN_CIERRE, es_incidente=campo(False, "Droner over", 0.95))
LLANO = "Nogen så noget i himlen over byen i aftes."
BUQUE = "Restos de un dron en la cubierta del buque Chelsea 3, en aguas de Bulgaria."


def _peticion_texto(almacen: Almacen, texto: str, id_: str | None = None) -> extraccion.Peticion:
    peticion = _peticion(almacen)
    candidato = {**peticion.candidato, "id": id_ or peticion.candidato["id"]}
    return extraccion.Peticion(
        **{
            **peticion.__dict__,
            "candidato": candidato,
            "fuentes": [
                ficha.FuenteTexto(f.medio, f.fecha, f.idioma, "Noticia", texto)
                for f in peticion.fuentes
            ],
            "objetivo": replace(peticion.objetivo, pais="BG"),
        }
    )


def test_la_regla_del_descarte_dudoso() -> None:
    motivos = escalado.motivos_ficha(_leida(DUDOSA), (LLANO,))
    assert "poca_seguridad: es_incidente" in motivos
    assert escalado.descarte_dudoso(motivos, _leida(DUDOSA))
    # Seguro de que no es incidente, o dando el incidente: no es un descarte dudoso.
    assert not escalado.descarte_dudoso(escalado.motivos_ficha(_leida(SEGURA), (LLANO,)), None)
    con_pais = ficha_ejemplo(pais=campo("DK", "Københavns Lufthavn", 0.5))
    assert not escalado.descarte_dudoso(["poca_seguridad: pais"], _leida(con_pais))


def test_un_buque_una_autoridad_o_una_fuente_oficial_del_alcance_no_esperan() -> None:
    assert escalado.dudoso_critico((BUQUE,), ("BG",))
    # Fuera del alcance territorial, el buque no basta.
    assert not escalado.dudoso_critico((BUQUE,), ("RU", ""))
    assert escalado.dudoso_critico(("La policía dice que vio un dron.",), ("RU",))
    assert escalado.dudoso_critico((LLANO,), ("DK",), oficial=True)
    assert not escalado.dudoso_critico((LLANO,), ("DK",))


def _peticiones(almacen: Almacen, texto: str) -> extraccion.Peticion:
    return _peticion_texto(almacen, texto)


def test_sin_margen_del_experto_el_descarte_dudoso_espera_y_no_bloquea_nada(
    almacen: Almacen,
) -> None:
    _gasto_experto(almacen, coste.LIMITE_EXPERTO_DIARIO_USD)
    peticion = _peticiones(almacen, LLANO)
    cliente = Cliente(DUDOSA, ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE] and hechas.esperan == [peticion.candidato["id"]]
    assert hechas.parada is None and almacen.extracciones(peticion.candidato["id"]) == []
    espera: dict[str, Any] = extraccion.esperan_experto(almacen)[peticion.candidato["id"]]
    assert espera["revision"] and not espera.get("critico")
    assert any(m.startswith(escalado.MOTIVO_DUDOSO) for m in espera["motivos"])
    assert espera["hasta"].endswith("T00:00:00Z")
    # Otro candidato sigue: uno seguro de que no es incidente vale el base, sin esperar.
    otro = _peticion_texto(almacen, LLANO, "otro")
    segura = Cliente(SEGURA, ficha_ejemplo())
    extraccion.extraer(almacen, segura, [otro], AHORA, coste.Modo.HORARIO, MODELOS)
    assert segura.pedidas == [BASE] and "otro" not in extraccion.esperan_experto(almacen)
    # Al día siguiente, con su tope renovado, lo decide el experto.
    manana = AHORA + timedelta(days=1)
    luego = extraccion.extraer(almacen, cliente, [peticion], manana, coste.Modo.HORARIO, MODELOS)
    assert luego.escalados == [peticion.candidato["id"]]
    assert peticion.candidato["id"] not in extraccion.esperan_experto(almacen)


def test_el_buque_del_alcance_usa_la_reserva_critica(almacen: Almacen) -> None:
    _gasto_experto(almacen, coste.LIMITE_EXPERTO_DIARIO_USD)
    peticion = _peticiones(almacen, BUQUE)
    cliente = Cliente(DUDOSA, ficha_ejemplo())
    hechas = extraccion.extraer(almacen, cliente, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert cliente.pedidas == [BASE, EXPERTO] and hechas.esperan == []
    (extraida,) = almacen.extracciones(peticion.candidato["id"])
    assert any(m.startswith(escalado.MOTIVO_DUDOSO) for m in extraida["escalado"])


def test_los_descartes_dudosos_desde_el_13_de_octubre_van_una_vez_al_experto(
    almacen: Almacen,
) -> None:
    dudoso = _peticion_texto(almacen, LLANO)
    seguro = _peticion_texto(almacen, LLANO, "seguro")
    # Antes de la regla: el base sin el experto (sin margen, valía su ficha).
    extraccion.extraer(almacen, Cliente(DUDOSA, None), [dudoso], AHORA, coste.Modo.HORARIO,
                       MODELOS)  # fmt: skip
    extraccion.extraer(almacen, Cliente(SEGURA, None), [seguro], AHORA, coste.Modo.HORARIO,
                       MODELOS)  # fmt: skip
    marcados = extraccion.revisar_descartes_dudosos(almacen, AHORA, "2000-01-01T00:00:00Z")
    assert marcados == [dudoso.candidato["id"]]
    assert extraccion.esperan_experto(almacen)[dudoso.candidato["id"]]["revision"]
    assert not extraccion.espera_experto(almacen, dudoso.candidato["id"], AHORA)
    # Una sola vez.
    assert extraccion.revisar_descartes_dudosos(almacen, AHORA, "2000-01-01T00:00:00Z") == []
