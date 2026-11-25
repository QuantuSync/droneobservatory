"""La alerta de Galaţi del martes 24 de noviembre de 2026 (EODI-2026-01000).

La nota de monitoruldegalati.ro (publicada a las 15:03, hora de Rumanía) empieza con dos «UPDATE»
y da la hora sin día: «a fost dispusă trecerea la faza de alertă aeriană începând cu ora 14:52».
El día lo escribe la frase siguiente, «Locuitorii din Galaţi au primit, marţi, la ora 14:53, un
mesaj RO-ALERT», que quedaba tras el principio que leen la extracción y el experto del filtro de
entrada (600 letras). El filtro la retuvo sin fecha y la retiró a las 6 horas. Desde el 25/11 el
filtro busca el día de esa hora en la nota entera (proceso/fechas.dia_en_la_nota) y la publica con
el día firme. Una nota retrospectiva (la comprobación N) sigue retenida."""

import copy
from datetime import UTC, datetime
from typing import Any

import pytest

from modelo import paginas
from proceso import fechas
from recogida import control_fichas, entrada
from tests import ejemplos, test_entrada
from tests.test_entrada import SULINA_582, Cliente, _base, _contexto, _respuesta

ID = "EODI-2026-01000"
ENLACE = "https://monitoruldegalati.ro/alerta-aeriana-galati"
NOTA = (
    "UPDATE: Inspectoratul General pentru Situații de Urgență (IGSU) a transmis un nou mesaj "
    "RO-ALERT de tip „Alertă Extremă”, prin care anunță populația că alarma aeriană (drone) a "
    "încetat. UPDATE: „ALERTĂ AERIANĂ. În urma discuţiilor telefonice cu SMFA din cadrul MApN, a "
    "fost dispusă trecerea la faza de alertă aeriană începând cu ora 14:52 ca urmare a observării "
    "unei drone neidentificate, care se îndreaptă spre judeţul Galaţi. A fost emis mesaj de "
    "avertizare a populaţiei prin sistemul RO-ALERT pentru zona vizată de alarma aeriană”, au "
    "transmis autorităţile. Locuitorii din Galaţi au primit, marţi, la ora 14:53, un mesaj "
    "RO-ALERT de tip „Extreme Alert”, prin care sunt avertizaţi cu privire la o posibilă "
    "incursiune de drone."
)
PRINCIPIO = NOTA[: NOTA.index(" Locuitorii")]


def galati() -> dict[str, Any]:
    """La ficha como la dejó la extracción (datos de la base)."""
    ficha = copy.deepcopy(ejemplos.incidente_minimo())
    fuente = {
        **ejemplos.fuente(f"{ID}-F1", "C"), "enlace": ENLACE, "medio": "monitoruldegalati.ro",
        "fecha": ejemplos.instante("2026-11-24T16:00Z", "aproximada"), "idioma": "ro",
        "frase_origen": "ca urmare a observării unei drone neidentificate, care se îndreaptă spre "
        "judeţul Galaţi",
    }  # fmt: skip
    ficha.update(
        id=ID, tipo="sobrevuelo", fuentes=[fuente],
        lugar={"pais": "RO", "nivel": "region", "region": "Galaţi", "suceso": "Galaţi",
               "punto": {"lat": 45.43, "lon": 28.05}, "radio_km": 30},
        tiempo={
            "inicio": ejemplos.instante("2026-11-24T12:52Z", "aproximada"),
            "origen_inicio": {
                "tipo": fechas.PUBLICACION, "fuente_id": fuente["id"],
                "motivo": f"{fechas.HORA_SIN_DIA}: día de la publicación (2026-11-24 18:00, hora "
                "local del medio)",
            },
        },
        estado={"actual": "notificado", "historial": [
            {"estado": "notificado", "fecha": ejemplos.instante("2026-11-24T16:00Z", "aproximada"),
             "fuente_id": fuente["id"]}]},
        control={"alta": ejemplos.instante("2026-11-24T17:17Z"),
                 "ultima_actualizacion": ejemplos.instante("2026-11-24T17:17Z")},
    )  # fmt: skip
    return ficha


def test_la_nota_da_el_dia_de_la_hora_sin_dia() -> None:
    fuente_id, frase, origen = fechas.dia_en_la_nota(galati(), [(f"{ID}-F1", NOTA)]) or ("", "", "")
    assert fuente_id == f"{ID}-F1" and origen == fechas.RELATIVA
    assert frase.startswith("Locuitorii din Galaţi au primit, marţi, la ora 14:53")
    # El principio que leen la extracción y el experto no la tiene.
    assert fechas.dia_en_la_nota(galati(), [(f"{ID}-F1", PRINCIPIO)]) is None


@pytest.mark.parametrize(
    ("cambio", "nota"),
    [
        # Otro día: la ficha y la nota son del miércoles y la frase dice «marţi».
        ("del_25", NOTA),
        # Otra hora: la frase con el día no es la de esta hora.
        ("", NOTA.replace("la ora 14:53", "la ora 18:20")),
        # Sin día en la frase.
        ("", NOTA.replace("marţi, ", "")),
        # Retrospectiva (N): la frase de la ficha sitúa el suceso en octubre.
        ("retrospectiva", NOTA),
        # La fecha no es una hora sin día: no hay hora que casar.
        ("sin_hora", NOTA),
    ],
)
def test_sin_la_misma_hora_y_el_mismo_dia_no_hay_dia(cambio: str, nota: str) -> None:
    ficha = galati()
    if cambio == "del_25":
        ficha["fuentes"][0]["fecha"] = ejemplos.instante("2026-11-25T16:00Z", "aproximada")
        ficha["tiempo"]["inicio"] = ejemplos.instante("2026-11-25T12:52Z", "aproximada")
    if cambio == "retrospectiva":
        ficha["fuentes"][0]["frase_origen"] = "Pe 3 octombrie, o dronă s-a îndreptat spre Galaţi"
    if cambio == "sin_hora":
        ficha["tiempo"]["origen_inicio"]["motivo"] = (
            "ninguna frase escribe el día del suceso: fecha de publicación"
        )
    assert fechas.dia_en_la_nota(ficha, [(f"{ID}-F1", nota)]) is None


def test_aalborg_la_hora_y_el_dia_en_otra_frase() -> None:
    # EODI-2025-00185 (tv2nord.dk): la ficha tenía las 22:00 sin día; la nota dice «klokken 21.44
    # onsdag aften» (miércoles 24 de septiembre de 2025), el día en que quedó al unirse.
    ficha = galati()
    ficha["lugar"] = {"pais": "DK", "nivel": "instalacion", "punto": {"lat": 57.09, "lon": 9.85}}
    ficha["tiempo"]["inicio"] = ejemplos.instante("2025-09-24T20:00Z", "aproximada")
    ficha["fuentes"][0].update(
        fecha=ejemplos.instante("2025-09-24T21:00Z", "aproximada"), idioma="da",
        frase_origen="Droner i Aalborg Lufthavn: Fly kan ikke lande.",
    )  # fmt: skip
    texto = (
        "Politiet efterforsker. Den første observation af droner ved Aalborg Lufthavn skete "
        "klokken 21.44 onsdag aften."
    )
    resultado = fechas.dia_en_la_nota(ficha, [(f"{ID}-F1", texto)])
    assert resultado is not None and "onsdag aften" in resultado[1]


def test_el_filtro_la_publica_con_el_dia_firme(monkeypatch: pytest.MonkeyPatch) -> None:
    # La recogida de las 17:17 del 24/11, en que el filtro la retuvo.
    monkeypatch.setattr(test_entrada, "AHORA", datetime(2026, 11, 24, 17, 17, tzinfo=UTC))
    monkeypatch.setattr(entrada, "unir_por_la_definicion", lambda *a: None)
    monkeypatch.setattr(
        control_fichas, "paginas_con_nota",
        lambda enlaces, plazo: {e: paginas.Pagina(PRINCIPIO, nota=NOTA) for e in enlaces},
    )  # fmt: skip
    almacen = _base(SULINA_582, galati())
    lugar = {"lugar_fuente": 1, "lugar_frase": "care se îndreaptă spre judeţul Galaţi"}
    ctx = _contexto(almacen, Cliente([_respuesta(**lugar), _respuesta(**lugar)]))
    entrada.filtrar(ctx, {"EODI-2026-00582"})
    decision = ctx.nuevas[entrada.clave(ID)]
    assert decision["decision"] == entrada.PUBLICAR
    assert decision["frase_fecha"][1].startswith("Locuitorii din Galaţi au primit, marţi")
    queda = almacen.incidente(ID)
    assert queda is not None
    assert queda["tiempo"]["inicio"] == {"valor": "2026-11-24T12:52Z", "precision": "minuto"}
    assert queda["tiempo"]["origen_inicio"]["tipo"] == fechas.RELATIVA
    # Sin esa frase en la nota, se retiene como antes.
    monkeypatch.setattr(
        control_fichas, "paginas_con_nota",
        lambda enlaces, plazo: {e: paginas.Pagina(PRINCIPIO, nota=PRINCIPIO) for e in enlaces},
    )  # fmt: skip
    almacen = _base(SULINA_582, galati())
    ctx = _contexto(almacen, Cliente([_respuesta(**lugar), _respuesta(**lugar)]))
    entrada.filtrar(ctx, {"EODI-2026-00582"})
    assert ctx.nuevas[entrada.clave(ID)]["decision"] == entrada.RETENER
