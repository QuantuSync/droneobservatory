"""El historial público de la presencia del dron (proceso/cambios_presencia.py).

EODI-2026-01008 (Ludza, Letonia, 27 de noviembre de 2026) salió a la 01:23 UTC con la presencia «no
confirmada» y a las 07:32 pasó a «confirmada» con la nota ampliada del ejército letón. La web solo
enseñaba el historial del estado del suceso: quien había leído la ficha a la 01:17 no podía ver el
cambio. Ahora cada cambio de presencia se guarda con su regla y su frase, y se publica en
`presencia_cambios` desde que la ficha salió en la web.

EODI-2026-00821 (RAF Lakenheath) es el caso de una bajada: pasó a «confirmada» el 14/11 y volvió a
«no confirmada» el 21/11, cuando la regla dejó de leer «responded to "suspected unauthorised drone
activity"» como una afirmación del dron.
"""

import copy
import json
from pathlib import Path

from almacen.base import Almacen
from esquema import Documento, Esquema, Visibilidad, rutas_por_visibilidad, validador_definicion
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE, CAMPOS_PUBLICOS_SIN_UBICACION
from proceso import cambios_presencia, presencia
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_cerrojo import ENLACE, base, ficha, guardar
from tests.test_control_fichas import AHORA
from tests.test_presencia_reserva import USAF

ID = "EODI-2026-09600"
CAMPOS_ANTES = Path(__file__).parent / "fixtures" / "campos_publicos_1_20_0.json"


def sin_autoridad() -> Documento:
    """La ficha sin la declaración de la policía: el suceso notificado, el dron no confirmado."""
    d = ficha(ID)
    oficial = d["fuentes"].pop()
    d["estado"] = {"actual": "notificado", "historial": d["estado"]["historial"][:1]}
    d["presencia_dron"] = "no_confirmada"
    d["afirmaciones"] = [a for a in d["afirmaciones"] if a["fuente_id"] != oficial["id"]]
    return d


def test_el_cambio_se_guarda_con_su_regla_y_su_frase() -> None:
    almacen = base(sin_autoridad())
    assert almacen.incidente(ID)["presencia_dron"] == "no_confirmada"  # type: ignore[index]
    assert almacen.cambios_presencia() == {}
    guardar(almacen, ficha(ID))
    assert almacen.incidente(ID)["presencia_dron"] == "confirmada"  # type: ignore[index]
    [cambio] = almacen.cambios_presencia()[ID]
    assert (cambio["de"], cambio["a"], cambio["regla"]) == (
        "no_confirmada", "confirmada", "autoridad_atribuye",
    )  # fmt: skip
    assert cambio["frase"] == "Die Polizei bestätigte die Drohne über dem Flughafen."
    assert cambio["enlace"] == ENLACE
    assert cambio["fuente_id"] == "gdelt-base-declaracion-1"
    assert cambio["anterior"] is False
    # Volver a guardar lo mismo no añade nada.
    guardar(almacen, ficha(ID))
    assert len(almacen.cambios_presencia()[ID]) == 1


def test_una_bajada_cita_la_frase_en_que_se_apoyaba() -> None:
    """Como 00821: la frase de la autoridad pasa a leerse como una respuesta a avisos."""
    almacen = base(ficha(ID))
    nueva = ficha(ID)
    nueva["fuentes"][1]["frase_origen"] = USAF
    guardar(almacen, nueva)
    # El cerrojo la deja confirmada; la corrección horaria del criterio de presencia la baja.
    presencia.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    [cambio] = almacen.cambios_presencia()[ID]
    assert (cambio["de"], cambio["a"]) == ("confirmada", "no_confirmada")
    assert cambio["regla"] == "sin_autoridad"
    assert cambio["anterior"] is True
    assert cambio["frase"] == USAF
    [paso] = cambios_presencia.pasos_publicos([cambio], "")
    assert paso["motivo"]["es"].endswith("antes se apoyaba en esta frase")
    assert paso["motivo"]["en"].endswith("it previously relied on this sentence")


def test_una_fuente_que_no_es_publica_no_sale() -> None:
    almacen = base(sin_autoridad())
    nueva = ficha(ID)
    nueva["fuentes"][1]["publica"] = False
    guardar(almacen, nueva)
    cambios = almacen.cambios_presencia().get(ID, [])
    for cambio in cambios:
        assert cambio["frase"] is None and cambio["enlace"] is None


def _fila(id_: int, fecha: str, de: str, a: str, regla: str = "autoridad_atribuye") -> Documento:
    return {"id": id_, "fecha": fecha, "de": de, "a": a, "regla": regla, "fuente_id": None,
            "frase": None, "enlace": None, "medio": None, "anterior": False}  # fmt: skip


def test_solo_se_publica_desde_la_primera_publicacion_y_uno_por_hora() -> None:
    filas = [
        # Antes de salir en la web: no se publica.
        _fila(1, "2026-11-27T01:20:00Z", "confirmada", "no_confirmada"),
        # 01008: la nota ampliada del ejército letón.
        _fila(2, "2026-11-27T07:32:57Z", "no_confirmada", "confirmada"),
        # Va y vuelve en la misma hora: nunca salió en la web.
        _fila(3, "2026-11-27T09:20:00Z", "confirmada", "no_confirmada", "sin_autoridad"),
        _fila(4, "2026-11-27T09:31:00Z", "no_confirmada", "confirmada"),
    ]
    pasos = cambios_presencia.pasos_publicos(filas, "2026-11-27T01:40:00Z")
    assert pasos == [
        {
            "fecha": {"valor": "2026-11-27T07:32Z", "precision": "minuto"},
            "de": "no_confirmada",
            "a": "confirmada",
            "motivo": {
                "es": "una autoridad afirma que hubo un dron",
                "en": "an authority states there was a drone",
            },
        }
    ]
    # Una ficha que nunca salió en la web no publica nada; una sembrada («») cuenta desde siempre.
    assert cambios_presencia.pasos_publicos(filas, None) == []
    assert len(cambios_presencia.pasos_publicos(filas, "")) == 2


def test_relleno_desde_el_historial_una_sola_vez() -> None:
    """Los cambios anteriores a la tabla salen del historial de la base: la versión de antes y la
    de después están guardadas. Sin regla que dé ese valor, el cambio sale sin motivo."""
    almacen = Almacen.abrir()
    conexion = almacen.conexion
    antes, despues = sin_autoridad(), ficha(ID)
    with conexion:
        conexion.execute(
            "INSERT INTO incidentes (id, tipo, estado, documento) VALUES (?, ?, ?, ?)",
            (ID, antes["tipo"], "notificado", json.dumps(antes)),
        )
        conexion.execute(
            "UPDATE incidentes SET documento = ? WHERE id = ?", (json.dumps(despues), ID)
        )
        # Un cambio sin regla que lo explique hoy: la presencia confirmada sin ninguna fuente.
        raro = copy.deepcopy(antes)
        raro["presencia_dron"] = "descartada"
        conexion.execute("UPDATE incidentes SET documento = ? WHERE id = ?", (json.dumps(raro), ID))
    assert cambios_presencia.rellenar(almacen) == 2
    cambios = almacen.cambios_presencia()[ID]
    assert [(c["de"], c["a"], c["regla"]) for c in cambios] == [
        ("no_confirmada", "confirmada", "autoridad_atribuye"),
        ("confirmada", "descartada", "sin_motivo"),
    ]
    assert cambios[0]["frase"] == "Die Polizei bestätigte die Drohne über dem Flughafen."
    # Una sola vez.
    assert cambios_presencia.rellenar(almacen) == 0
    assert len(almacen.cambios_presencia()[ID]) == 2
    paso = cambios_presencia.pasos_publicos(cambios, "")[-1]
    assert paso["motivo"]["es"].startswith("cambio anterior al registro de sus motivos")
    assert "frase" not in paso


def test_con_cambios_solo_en_las_fichas_que_los_tienen() -> None:
    almacen = base(sin_autoridad(), ficha("EODI-2026-09601"))
    guardar(almacen, ficha(ID))
    with almacen.conexion:
        for id_ in (ID, "EODI-2026-09601"):
            almacen.conexion.execute(
                "INSERT INTO publicado (id, estado, fichero, entrada, interno, detalle, primera, "
                "fecha) VALUES (?, 'publicada', 'incidentes.geojson', '{}', '{}', '{}', ?, ?)",
                (id_, "2000-01-01T00:00:00Z", "2000-01-01T00:00:00Z"),
            )
    publicos: list[Documento] = [{"id": ID}, {"id": "EODI-2026-09601"}]
    cambios_presencia.con_cambios(publicos, almacen)
    assert "presencia_cambios" not in publicos[1]
    [paso] = publicos[0]["presencia_cambios"]
    assert (paso["de"], paso["a"]) == ("no_confirmada", "confirmada")
    assert paso["enlace"] == ENLACE and paso["medio"].startswith("Polizei Nürnberg")
    assert paso["frase"] == "Die Polizei bestätigte die Drohne über dem Flughafen."


def test_los_campos_publicos_solo_se_anaden() -> None:
    """Quien ya lee los datos publicados (github.com/tryph0n/hybrid-tracker, la descarga diaria)
    sigue encontrando todos los campos de antes con el mismo nombre: el esquema 1.21.0 solo añade
    `presencia_cambios`."""
    antes = json.loads(CAMPOS_ANTES.read_text(encoding="utf-8"))
    assert set(antes["incidente"]) <= CAMPOS_PUBLICOS_INCIDENTE
    assert set(antes["sin_ubicacion"]) <= CAMPOS_PUBLICOS_SIN_UBICACION
    nuevos = CAMPOS_PUBLICOS_INCIDENTE - set(antes["incidente"])
    assert nuevos and all(c.startswith("presencia_cambios") for c in nuevos)
    assert CAMPOS_PUBLICOS_SIN_UBICACION - set(antes["sin_ubicacion"]) == nuevos
    publicos = rutas_por_visibilidad(Esquema.INCIDENTE)[Visibilidad.PUBLICO]
    assert nuevos <= publicos


def test_el_paso_publicado_valida_contra_el_esquema() -> None:
    almacen = base(sin_autoridad())
    guardar(almacen, ficha(ID))
    pasos = cambios_presencia.pasos_publicos(almacen.cambios_presencia()[ID], "")
    assert pasos
    assert list(validador_definicion("presencia_cambios").iter_errors(pasos)) == []
    # Un paso con un campo interno (la regla) no valida.
    malo = [{**pasos[0], "regla": "autoridad_atribuye"}]
    assert list(validador_definicion("presencia_cambios").iter_errors(malo)) != []


# Motivos reales que guardó la base (historial, incidentes_motivos) con cambios de presencia que
# las reglas de hoy ya no explican: lo que decidía la regla de entonces.
MOTIVOS_REALES = [
    ("un solo sitio decide (proceso/decidir.py): estado por historial, presencia confirmada por "
     "autoridad_atribuye", "confirmada", "autoridad_atribuye"),  # EODI-2026-00821, 14/11
    ("criterio de presencia: la autoridad actúa por un dron (cierre o intervención) y lo cuenta la "
     "fuente: «Police responding to drone threats near Prague airport»", "confirmada",
     "actuacion"),  # EODI-2025-00037
    ("criterio de presencia del dron (la autoridad competente que lo da por hecho lo confirma), "
     "titular coherente con la presencia y un incidente por noche de cierre", "confirmada",
     "autoridad_atribuye"),  # EODI-2025-00214
    ("criterio de presencia: ninguna autoridad dice que fuera un dron (solo la prensa o los "
     "testigos, o una medida de la autoridad sin atribuirlo); la presencia no queda confirmada",
     "no_confirmada", "sin_autoridad"),  # EODI-2025-00059
    ("control de fichas: presencia no confirmada: «De drones zijn volgens Defensie daarna "
     "weggevlogen en niet teruggevonden.»", "no_confirmada", "abierta"),  # EODI-2025-00066
    ("repaso de entrada con el experto: Suceso nuevo en la cárcel de Picassent; la ficha "
     "publicada afirma un dron «posible» no confirmado…", "confirmada", "experto"),  # 00629
    ("cita revisada a mano (configuracion/incidentes_revisados.json, citas)", "confirmada",
     "revision"),  # EODI-2026-00146
    ("Una portavoz de la Bundeswehr confirma que los soldados vieron el dron y que se derribó.",
     "confirmada", "revision"),  # EODI-2025-00317
    # No hablan de la presencia: el cambio queda sin motivo.
    ("titular coherente con la presencia del dron (proceso/titulares.py)", "confirmada", None),
    ("control de fichas: lugar en Aéroport de Luxembourg, que nombra el titular", "confirmada",
     None),  # EODI-2026-00048
]  # fmt: skip


def test_la_regla_de_entonces_sale_del_motivo_guardado() -> None:
    for motivo, a, regla in MOTIVOS_REALES:
        assert cambios_presencia.regla_de_motivo(motivo, a) == regla, motivo


def test_el_motivo_guardado_explica_el_cambio_y_cita_su_frase() -> None:
    """Un cambio que las reglas de hoy no dan: lo explica el motivo guardado, y la frase es la
    que cita entre comillas."""
    antes = sin_autoridad()
    despues = copy.deepcopy(antes)
    despues["presencia_dron"] = "confirmada"
    despues["fuentes"][0]["frase_origen"] = "Police responding to drone threats near the airport"
    motivo = (
        "criterio de presencia: la autoridad actúa por un dron (cierre o intervención) y lo "
        "cuenta la fuente: «Police responding to drone threats near the airport»"
    )
    cambio = cambios_presencia.describir(ID, "2026-10-03T21:28:43Z", antes, despues, motivo=motivo)
    assert cambio is not None
    assert cambio.regla == "actuacion"
    assert cambio.frase == "Police responding to drone threats near the airport"
    sin = cambios_presencia.describir(ID, "2026-10-03T21:28:43Z", antes, despues)
    assert sin is not None and sin.regla == "sin_motivo" and sin.frase is None
