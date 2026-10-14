"""Control de calidad permanente de las fichas (recogida/control_fichas.py, docs/control_fichas.md):
los duplicados entre idiomas se unen conservando el identificador más antiguo, el lugar es el más
preciso que dan el titular y las fuentes, cada dato tiene que estar respaldado por una frase
literal de sus fuentes, las citas se traducen una vez, lo nuevo sin controlar se retiene como
mucho 6 horas y un suceso unido a otro ya avisado no se vuelve a avisar."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from exportacion import citas
from modelo import coste
from proceso import control_fichas as reglas
from proceso import lugar_preciso, presencia
from proceso.noticias import nomenclator
from recogida import avisos, control_fichas, vigilancia, visitas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 10, 13, 14, 17, tzinfo=UTC)
INFRANKEN = "https://infranken.de/lk/nuernberg/blaulicht/flughafen-nuernberg-art-6403002"
SCHWAEBISCHE = "https://schwaebische.de/regional/bayern/moegliche-drohne-4933216"
DNEWS = "https://dnews.gr/eidhseis/kosmos/616139/ekleise-to-aerodromio-tis-nyremvergis"
NO_HALLADO = "allerdings konnte eine Drohne nicht gefunden werden."
GRIEGA = "Σε κατάσταση συναγερμού τέθηκε το αεροδρόμιο της Νυρεμβέργης, στη Γερμανία"


def _fuente(
    id_: str, enlace: str, medio: str, idioma: str, frase: str, hora: str
) -> dict[str, Any]:
    return {
        **ejemplos.fuente(id_, "C"),
        "enlace": enlace,
        "medio": medio,
        "idioma": idioma,
        "frase_origen": frase,
        "credibilidad": 3,
        "replicas": 0,
        "campos_respaldados": [],
        "fecha": ejemplos.instante(f"2026-10-13T{hora}Z", "aproximada"),
    }


def _nuremberg_alemana() -> dict[str, Any]:
    """Como EODI-2026-00515: solo el país, dron «confirmado» por el cierre y 2-10 drones."""
    d = ejemplos.incidente_minimo()
    d["id"] = "EODI-2026-09515"
    d["titulo"] = {
        "es": "Posible avistamiento de dron causa perturbaciones en el aeropuerto de Núremberg",
        "en": "Possible drone sighting causes disruptions at Nuremberg Airport",
    }
    d["lugar"] = {"pais": "DE", "nivel": "pais"}
    d["tiempo"] = {"inicio": ejemplos.instante("2026-10-13T08:30Z", "aproximada")}
    d["fuentes"] = [
        _fuente(
            "gdelt-infranken",
            INFRANKEN,
            "infranken.de",
            "de",
            "Am Flughafen Nürnberg ist es am frühen Dienstagmorgen (13. Oktober 2026) zu "
            "Beeinträchtigungen des Flugverkehrs gekommen.",
            "08:30",
        ),
        _fuente("gdelt-schwaebische", SCHWAEBISCHE, "schwaebische.de", "de", NO_HALLADO, "08:45"),
    ]
    d["presencia_dron"] = "confirmada"
    d["drones"] = {"numero": {"min": 2, "max": 10}}
    d["consecuencias"] = {"cierre": {"valor": "si"}}
    d["afirmaciones"] = [
        {
            "campo": "drones",
            "valor": {"min": 2, "max": 10},
            "fuente_id": "gdelt-infranken",
            "confianza_extraccion": 0.8,
        },
        {
            "campo": "presencia_dron",
            "valor": "confirmada",
            "fuente_id": "gdelt-schwaebische",
            "confianza_extraccion": 1.0,
        },
    ]
    d["estado"]["historial"][0].update(
        fuente_id="gdelt-infranken", fecha=ejemplos.instante("2026-10-13T08:30Z", "aproximada")
    )
    alta = ejemplos.instante("2026-10-13T09:17Z")
    d["control"] = {"alta": alta, "ultima_actualizacion": alta}
    return d


def _nuremberg_griega() -> dict[str, Any]:
    """Como EODI-2026-00516: una fuente griega y el punto genérico de la ciudad."""
    d = ejemplos.incidente_minimo()
    d["id"] = "EODI-2026-09516"
    d["titulo"] = {
        "es": "Alerta en el aeropuerto de Núremberg por posible avistamiento de dron",
        "en": "Alert at Nuremberg airport over possible drone sighting",
    }
    d["lugar"] = {
        "pais": "DE",
        "nivel": "localidad",
        "punto": {"lat": 49.45421, "lon": 11.07752},
        "radio_km": 10.0,
        "geocodificacion": "gkg",
        "suceso": "Nuremberg",
    }
    d["objetivo"] = {"categoria": "otra", "nombre": "Nuremberg"}
    d["tiempo"] = {"inicio": ejemplos.instante("2026-10-13T12:30Z", "aproximada")}
    d["fuentes"] = [_fuente("gdelt-dnews", DNEWS, "dnews.gr", "el", GRIEGA, "12:30")]
    d["presencia_dron"] = "no_confirmada"
    d["estado"]["historial"][0].update(
        fuente_id="gdelt-dnews", fecha=ejemplos.instante("2026-10-13T12:30Z", "aproximada")
    )
    alta = ejemplos.instante("2026-10-13T13:17Z")
    d["control"] = {"alta": alta, "ultima_actualizacion": alta}
    return d


class Servicio:
    """El servicio de mensajes, falso: decide por el tipo de petición."""

    def __init__(self, decision: str = "mismo") -> None:
        self.decision = decision
        self.pedidas: list[str] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        contenido = str(cuerpo["messages"][0]["content"])
        if contenido.startswith("Ficha A:"):
            self.pedidas.append("comparar")
            salida: dict[str, Any] = {
                "mismo_dia": self.decision == "mismo",
                "mismo_sitio": self.decision == "mismo",
                "varios_sucesos": False,
                "decision": self.decision,
                "motivo_es": "la misma alerta",
                "motivo_en": "the same alert",
            }
        elif contenido.startswith("Ficha:"):
            self.pedidas.append("verificar")
            vacio = {"valor": "", "fuente": 0, "frase": ""}
            salida = {
                "presencia": {"valor": "no_hallado", "fuente": 2, "frase": NO_HALLADO},
                # El modelo dice «2-10» pero la frase no está en la fuente: no cuenta.
                "drones": {"valor": "2-10", "fuente": 1, "frase": "Mehrere Drohnen gesichtet"},
                "cierre": {
                    "valor": "si",
                    "fuente": 1,
                    "frase": "Beeinträchtigungen des Flugverkehrs",
                },
                "duracion_min": vacio,
                "dia": {
                    "valor": "2026-10-13",
                    "fuente": 1,
                    "frase": "Dienstagmorgen (13. Oktober 2026)",
                },
                "hora": vacio,
                "lugar": {
                    "nombre": "Flughafen Nürnberg",
                    "nivel": "instalacion",
                    "fuente": 1,
                    "frase": "Am Flughafen Nürnberg",
                },
            }
        else:
            self.pedidas.append("traducir")
            lineas = [linea for linea in contenido.splitlines() if linea.strip()]
            salida = {
                "traducciones": [
                    {"n": n, "es": f"traducción {n}", "en": f"translation {n}"}
                    for n in range(1, len(lineas) + 1)
                ]
            }
        return {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(salida)}],
            "usage": {"input_tokens": 1000, "output_tokens": 200},
        }


@pytest.fixture(autouse=True)
def sin_descargas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})


def _base(*documentos: dict[str, Any]) -> Almacen:
    almacen = Almacen.abrir()
    for documento in documentos:
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    return almacen


# --- Presencia: «no se encontró el dron» -----------------------------------------------------
@pytest.mark.parametrize(
    "frase",
    [
        NO_HALLADO,
        "Politiet fandt ingen droner",
        "Es sei aber keine Drohne zu sehen gewesen",
        "Police did not find the drone",
        "no se encontró ningún dron",
    ],
)
def test_frases_de_dron_no_hallado(frase: str) -> None:
    assert presencia.dice_no_hallado(frase)


@pytest.mark.parametrize(
    "frase",
    [
        "No Drone Debris Found on Damaged Black Sea Ship",
        "Flughafen Hannover-Langenhagen: Keine Landungen nach Drohnensichtung möglich",
        "Ingen droner blev nedtaget under aktivitet ved Aalborg Lufthavn",
    ],
)
def test_frases_que_no_dicen_que_no_se_hallara(frase: str) -> None:
    assert not presencia.dice_no_hallado(frase)


def test_la_presencia_no_queda_confirmada_si_no_se_encontro_el_dron() -> None:
    documento = _nuremberg_alemana()
    assert presencia.por_actuacion(documento) is None
    nuevo = presencia.quitar_por_no_hallado(documento)
    assert nuevo["presencia_dron"] == "no_confirmada"
    assert {
        "campo": "presencia_dron",
        "valor": "no_confirmada",
        "fuente_id": "gdelt-schwaebische",
        "confianza_extraccion": 1.0,
    } in nuevo["afirmaciones"]
    assert not any(a["valor"] == "confirmada" for a in nuevo["afirmaciones"])


# --- Lugar: la instalación que nombra el titular --------------------------------------------
def test_el_titular_con_el_aeropuerto_da_el_lugar() -> None:
    nuevo = lugar_preciso.precisar(_nuremberg_alemana(), nomenclator(), AHORA)
    assert nuevo is not None
    assert nuevo["objetivo"]["oaci"] == "EDDN" and nuevo["lugar"]["nivel"] == "instalacion"
    assert "punto" in nuevo["lugar"]


def test_el_punto_generico_de_la_ciudad_pasa_al_aeropuerto_con_historial() -> None:
    nuevo = lugar_preciso.precisar(_nuremberg_griega(), nomenclator(), AHORA)
    assert nuevo is not None and nuevo["objetivo"]["oaci"] == "EDDN"
    assert nuevo["lugar"]["historial"][-1]["anterior"]["punto"] == {
        "lat": 49.45421,
        "lon": 11.07752,
    }


@pytest.mark.parametrize(
    "titulo",
    [
        "Dron no autorizado causa riesgo de colisión con un avión que se aproximaba a Heathrow "
        "sobre Marlow",
        "Drones derribados obligan a cerrar el aeropuerto de Varsovia",
        "Drones sobre bases militares alemanas en Manching y Neuburg",
    ],
)
def test_titulares_que_no_dan_una_sola_instalacion_sin_duda(titulo: str) -> None:
    documento = ejemplos.incidente_minimo()
    documento["titulo"] = {"es": titulo, "en": titulo}
    documento["lugar"] = {
        "pais": {"Marlow": "GB", "Varsovia": "PL"}.get(
            next((p for p in ("Marlow", "Varsovia") if p in titulo), ""), "DE"
        ),
        "nivel": "pais",
    }
    assert lugar_preciso.instalacion_del_titulo(documento, nomenclator()) is None


# --- Pares candidatos --------------------------------------------------------------------------
def test_pares_candidatos_tambien_con_lugar_solo_de_pais() -> None:
    a, b = _nuremberg_alemana(), _nuremberg_griega()
    assert reglas.candidatos(a, b)
    lejos = copy.deepcopy(b)
    lejos["tiempo"]["inicio"] = ejemplos.instante("2026-10-06T12:30Z", "dia")
    for f in lejos["fuentes"]:
        f["fecha"] = ejemplos.instante("2026-10-06T12:30Z", "aproximada")
    assert not reglas.candidatos(a, lejos)
    otro_pais = copy.deepcopy(b)
    otro_pais["lugar"]["pais"] = "AT"
    assert not reglas.candidatos(a, otro_pais)


def test_separados_por_una_revision_no_son_candidatos() -> None:
    a, b = _nuremberg_alemana(), _nuremberg_griega()
    b["relacionados"] = [{"id": a["id"], "separado_de": a["id"], "nota": {"es": "x", "en": "x"}}]
    assert not reglas.candidatos(a, b)


# --- El paso horario -------------------------------------------------------------------------
def _ejecutar(
    almacen: Almacen, servicio: Servicio | None, ahora: datetime = AHORA, alcance: str = "horaria"
) -> control_fichas.Resultado:
    fabrica = (lambda: servicio) if servicio is not None else None
    return control_fichas.ejecutar(almacen, ahora, VOCABULARIO_MODELOS, alcance, fabrica)


def test_une_el_duplicado_entre_idiomas_y_corrige_la_ficha() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    servicio = Servicio()
    resultado = _ejecutar(almacen, servicio, alcance="repaso")
    assert resultado.unidos == ["EODI-2026-09516 -> EODI-2026-09515"]
    unido = almacen.incidente("EODI-2026-09516")
    assert unido is not None and unido["fusionado_en"] == "EODI-2026-09515"
    queda = almacen.incidente("EODI-2026-09515")
    assert queda is not None
    assert queda["objetivo"]["oaci"] == "EDDN" and "punto" in queda["lugar"]
    assert queda["presencia_dron"] == "no_confirmada"
    assert queda["drones"]["numero"] == "desconocido"
    assert not any(a["campo"] == "drones" for a in queda["afirmaciones"])
    assert queda["tiempo"]["inicio"] == {"valor": "2026-10-13T00:00Z", "precision": "dia"}
    assert {f["id"] for f in queda["fuentes"]} >= {"gdelt-dnews", "gdelt-schwaebische"}
    decision = almacen.controles("par:")["par:EODI-2026-09515|EODI-2026-09516"]
    assert decision["decision"] == "mismo" and decision["conserva"] == "EODI-2026-09515"
    traducciones = almacen.traducciones()
    assert traducciones[citas.huella_texto(GRIEGA)]["es"].startswith("traducción")
    assert almacen.gastado(coste.Modo.CONTROL_REPASO.value) > 0
    # Idempotente: otra pasada no vuelve a llamar ni cambia nada.
    antes = len(servicio.pedidas)
    otra = _ejecutar(almacen, servicio, alcance="repaso")
    assert len(servicio.pedidas) == antes and not otra.corregidos and not otra.unidos


def test_la_union_se_rehace_si_el_que_queda_pierde_las_fuentes() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    _ejecutar(almacen, Servicio(), alcance="repaso")
    queda = almacen.incidente("EODI-2026-09515")
    assert queda is not None
    # Como si el extractor la volviera a extraer solo con su candidato.
    queda["fuentes"] = [f for f in queda["fuentes"] if f["id"] != "gdelt-dnews"]
    almacen.guardar_incidente(queda, AHORA, VOCABULARIO_MODELOS)
    _ejecutar(almacen, None, AHORA + timedelta(hours=1))
    otra_vez = almacen.incidente("EODI-2026-09515")
    assert otra_vez is not None and "gdelt-dnews" in {f["id"] for f in otra_vez["fuentes"]}


def test_lo_distinto_no_se_une() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    resultado = _ejecutar(almacen, Servicio("distinto"), alcance="repaso")
    assert resultado.unidos == [] and resultado.distintos == 1
    griega = almacen.incidente("EODI-2026-09516")
    assert griega is not None and "fusionado_en" not in griega


def test_lo_nuevo_sin_controlar_se_retiene_como_mucho_seis_horas() -> None:
    almacen = _base(_nuremberg_alemana())
    _ejecutar(almacen, None)  # primera pasada: lo que había se da por visto
    almacen.guardar_incidente(_nuremberg_griega(), AHORA, VOCABULARIO_MODELOS)
    resultado = _ejecutar(almacen, None, AHORA + timedelta(hours=1))
    assert "EODI-2026-09516" in resultado.retenidos
    assert control_fichas.retenidos(almacen) == frozenset({"EODI-2026-09516"})
    # Lo ya publicado no se retiene nunca.
    assert "EODI-2026-09515" not in resultado.retenidos
    tarde = _ejecutar(almacen, None, AHORA + timedelta(hours=7, minutes=30))
    assert "EODI-2026-09516" in tarde.liberados
    assert control_fichas.retenidos(almacen) == frozenset()


def test_dudoso_se_resuelve_a_las_seis_horas() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    _ejecutar(almacen, Servicio("dudoso"), alcance="repaso")
    assert almacen.controles("par:")["par:EODI-2026-09515|EODI-2026-09516"]["decision"] == "dudoso"
    _ejecutar(almacen, Servicio("mismo"), AHORA + timedelta(hours=7), alcance="repaso")
    decision = almacen.controles("par:")["par:EODI-2026-09515|EODI-2026-09516"]
    assert decision["decision"] == "distinto" and decision["plazo"] is True


def test_el_tope_de_gasto_para_las_llamadas() -> None:
    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    almacen.registrar_llamada(
        {
            "fecha": "2026-10-13T00:01:00Z",
            "modo": "control",
            "candidato": "x",
            "lote": False,
            "entrada": 0,
            "salida": 0,
            "escritura_cache": 0,
            "lectura_cache": 0,
            "coste": 0.15,
        }
    )
    servicio = Servicio()
    resultado = _ejecutar(almacen, servicio)
    assert resultado.parada == "limite_gasto" and servicio.pedidas == []


# --- Verificación: cada dato con su frase ------------------------------------------------------
def test_una_frase_que_no_esta_en_la_fuente_no_cuenta() -> None:
    fuentes = [("F1", "Am Flughafen Nürnberg ist es zu Beeinträchtigungen gekommen")]
    respuesta = {
        "drones": {"valor": "3", "fuente": 1, "frase": "drei Drohnen"},
        "cierre": {"valor": "si", "fuente": 1, "frase": "zu Beeinträchtigungen gekommen"},
    }
    verificada = reglas.comprobar(respuesta, fuentes)
    assert "drones" not in verificada.datos and verificada.valor("cierre") == "si"


def test_con_fuentes_nuevas_no_se_quita_un_valor_distinto_del_comprobado() -> None:
    documento = _nuremberg_alemana()
    sin_dato = reglas.aplicar(documento, reglas.Verificada(), True, None)
    assert sin_dato.incidente["drones"]["numero"] == "desconocido"
    conservado = reglas.aplicar(documento, reglas.Verificada(), True, None, frozenset({"drones"}))
    assert conservado.incidente["drones"]["numero"] == {"min": 2, "max": 10}


def test_el_estado_confirmado_pide_una_fuente_oficial() -> None:
    documento = _nuremberg_alemana()
    documento["estado"]["actual"] = "confirmado"
    documento["estado"]["historial"].append(
        {
            "estado": "confirmado",
            "fuente_id": "gdelt-infranken",
            "fecha": ejemplos.instante("2026-10-13T09:00Z"),
        }
    )
    bajado = reglas.bajar_estado(documento, ejemplos.instante("2026-10-13T12:17Z"))
    assert bajado is not None and bajado["estado"]["actual"] == "notificado"
    documento["fuentes"][0]["es_autoridad"] = True
    assert reglas.bajar_estado(documento, ejemplos.instante("2026-10-13T12:17Z")) is None


# --- Publicación: citas traducidas y respaldo de cada dato -----------------------------------
def test_publicacion_con_traduccion_y_cita_de_respaldo() -> None:
    publico: dict[str, Any] = {
        "id": "EODI-2026-09515",
        "presencia_dron": "no_confirmada",
        "fuentes": [
            {
                "id": "F2",
                "medio": "schwaebische.de",
                "fiabilidad": "C",
                "credibilidad": 3,
                "fecha": ejemplos.instante("2026-10-13T08:45Z"),
                "frase_origen": NO_HALLADO,
            }
        ],
    }
    verificacion = {"datos": {"presencia": ["no_hallado", "F2", NO_HALLADO]}}
    traducciones = {
        citas.huella_texto(NO_HALLADO): {
            "es": "no se encontró ningún dron",
            "en": "no drone was found",
        }
    }
    citas.enriquecer_incidentes([publico], {"EODI-2026-09515": verificacion}, traducciones)
    assert publico["fuentes"][0]["traduccion"]["es"] == "no se encontró ningún dron"
    afirmacion = publico["afirmaciones_publicas"][0]
    assert afirmacion["campo"] == "presencia_dron" and afirmacion["cita"] == NO_HALLADO
    assert afirmacion["cita_traduccion"]["en"] == "no drone was found"


# --- Avisos: un suceso unido a otro ya avisado no se avisa otra vez ---------------------------
def test_unido_a_uno_ya_avisado_no_se_vuelve_a_avisar(tmp_path: Path) -> None:
    base = tmp_path / "eodi.sqlite"
    almacen = Almacen.abrir(base)
    almacen.registrar_fusion("2026-10-13T09:00Z", "EODI-2026-00514", "EODI-2026-00513", "x", [])
    almacen.conexion.commit()
    almacen.cerrar()
    unidos = avisos.unidos_en(base)
    assert unidos == {"EODI-2026-00513": {"EODI-2026-00514"}}
    enviados = avisos.Enviados(tmp_path / "avisos.sqlite")
    enviados.activar([], AHORA)
    for tema in ("drones-europe", "drones-bulgaria"):
        enviados.anotar("EODI-2026-00514", tema, AHORA)
    hechos = enviados.temas("EODI-2026-00513")
    for otro in unidos["EODI-2026-00513"]:
        hechos |= enviados.temas(otro)
    assert {"drones-europe", "drones-bulgaria"} <= hechos
    enviados.cerrar()


# --- Resumen diario y vigilancia ------------------------------------------------------------------
def test_resumen_dice_que_corrigio_y_por_que(tmp_path: Path) -> None:
    ruta = tmp_path / "control.json"
    ruta.write_text(
        json.dumps(
            {
                "fallos_seguidos": 0,
                "pasadas": [
                    {
                        "fecha": "2026-10-13T12:17:00Z",
                        "unidos": ["EODI-2026-09516 -> EODI-2026-09515"],
                        "corregidos": {
                            "EODI-2026-09515": [
                                "drones 2-10 -> sin dato: ninguna fuente da el número"
                            ]
                        },
                        "retenidos": {"EODI-2026-09517": "posible duplicado sin decidir"},
                        "liberados": {},
                        "gasto": 0.012,
                        "parada": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    control = visitas.control_del_dia(ruta, AHORA.date())
    texto = "\n".join(visitas.lineas_control(control))
    assert "1 fichas corregidas (drones 1)" in texto and "1 duplicados unidos" in texto
    assert "EODI-2026-09517" in texto and "0,0120 USD" in texto


def test_vigilancia_solo_si_el_control_falla_varias_veces_seguidas() -> None:
    assert vigilancia.problemas_del_control({"fallos_seguidos": 2}) == []
    assert vigilancia.problemas_del_control({"fallos_seguidos": 3})[0]["id"] == "control_fichas"


# --- Repaso de todo lo publicado, por lotes ---------------------------------------------------
class ServicioLotes(Servicio):
    """Un lote que termina en el acto con las respuestas del servicio falso."""

    def __init__(self) -> None:
        super().__init__()
        self.lotes: list[list[dict[str, Any]]] = []

    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]:
        self.lotes.append(peticiones)
        return {"id": f"lote-{len(self.lotes)}", "processing_status": "ended"}

    def lote(self, id_: str) -> dict[str, Any]:
        return {"id": id_, "processing_status": "ended"}

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]:
        peticiones = self.lotes[int(lote["id"].removeprefix("lote-")) - 1]
        return [
            {
                "custom_id": p["custom_id"],
                "result": {"type": "succeeded", "message": self.mensaje(p["params"])},
            }
            for p in peticiones
        ]


def test_repaso_por_lotes_en_dos_rondas() -> None:
    import contextlib

    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    servicio = ServicioLotes()
    base = control_fichas.Base(
        abrir=lambda: almacen, guardar=lambda a: None, cerrojo=contextlib.nullcontext
    )
    resultado = control_fichas.repaso(base, lambda: servicio, dormir=lambda s: None)
    assert len(servicio.lotes) == 2
    assert resultado.unidos == ["EODI-2026-09516 -> EODI-2026-09515"]
    queda = almacen.incidente("EODI-2026-09515")
    assert queda is not None and queda["drones"]["numero"] == "desconocido"
    assert almacen.gastado(coste.Modo.CONTROL_REPASO.value) > 0
    llamadas = [ll for ll in almacen.llamadas() if ll["modo"] == "control_repaso"]
    assert llamadas and all(ll["lote"] for ll in llamadas)


def test_union_a_mano_conserva_el_registro_indicado() -> None:
    from recogida import revisados

    almacen = _base(_nuremberg_alemana(), _nuremberg_griega())
    hechos = revisados.unir_grupo(
        almacen,
        ["EODI-2026-09515", "EODI-2026-09516"],
        "x",
        AHORA,
        VOCABULARIO_MODELOS,
        conserva="EODI-2026-09516",
    )
    assert hechos == 1
    alemana = almacen.incidente("EODI-2026-09515")
    assert alemana is not None and alemana["fusionado_en"] == "EODI-2026-09516"


def test_noche_traduce_lo_atrasado_por_lote(tmp_path: Path) -> None:
    import contextlib

    almacen = _base(_nuremberg_alemana())
    almacen.guardar_cursor(
        control_fichas.CURSOR_CITAS,
        {"europa": {}, "ucrania": {citas.huella_texto("Одна цитата"): ["uk", "Одна цитата"]}},
    )
    servicio = ServicioLotes()
    base = control_fichas.Base(
        abrir=lambda: almacen, guardar=lambda a: None, cerrojo=contextlib.nullcontext
    )
    control_fichas.noche(base, lambda: servicio, tmp_path / "control.json", dormir=lambda s: None)
    assert citas.huella_texto("Одна цитата") in almacen.traducciones()
    assert any(ll["modo"] == "control" and ll["lote"] for ll in almacen.llamadas())
    assert json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))["pasadas"]


def test_titular_sin_posible_repetido() -> None:
    from proceso import titulares

    assert (
        titulares.ajustar(
            "Posible avistamiento de posible dron causa perturbaciones en el aeropuerto de Núremberg",  # noqa: E501
            "no_confirmada",
            "es",
        )
        == "Posible avistamiento de dron causa perturbaciones en el aeropuerto de Núremberg"
    )


def test_la_union_no_pierde_la_confirmacion_oficial_del_unido() -> None:
    from proceso import incidentes

    antiguo = _nuremberg_griega()
    nuevo = _nuremberg_alemana()
    nuevo["fuentes"][0]["es_autoridad"] = True
    nuevo["estado"] = {
        "actual": "confirmado",
        "historial": [
            nuevo["estado"]["historial"][0],
            {
                "estado": "confirmado",
                "fuente_id": "gdelt-infranken",
                "fecha": ejemplos.instante("2026-10-13T13:00Z"),
            },
        ],
    }
    unido, _ = incidentes.absorber(antiguo, nuevo, AHORA)
    assert unido["estado"]["actual"] == "confirmado"
    assert unido["estado"]["historial"][-1]["fuente_id"] == "gdelt-infranken"


def test_mismo_solo_con_el_mismo_dia_y_el_mismo_sitio() -> None:
    base = {"decision": "mismo", "mismo_dia": True, "mismo_sitio": True, "varios_sucesos": False}
    assert control_fichas.decision_comprobada(base) == "mismo"
    assert control_fichas.decision_comprobada({**base, "mismo_dia": False}) == "dudoso"
    assert control_fichas.decision_comprobada({**base, "varios_sucesos": True}) == "dudoso"
    assert control_fichas.decision_comprobada({**base, "decision": "distinto"}) == "distinto"


def test_dias_distintos_con_fecha_escrita_no_son_candidatos() -> None:
    a, b = _nuremberg_alemana(), _nuremberg_griega()
    a["tiempo"]["inicio"] = ejemplos.instante("2026-10-12T00:00Z", "dia")
    b["tiempo"]["inicio"] = ejemplos.instante("2026-10-13T20:00Z", "hora")
    assert not reglas.candidatos(a, b)
    b["tiempo"]["inicio"] = ejemplos.instante("2026-10-12T21:00Z", "hora")
    assert reglas.candidatos(a, b)


def test_no_se_anade_un_cierre_ni_una_duracion_sin_frase_de_cierre() -> None:
    documento = _nuremberg_alemana()
    documento["consecuencias"] = {"cierre": {"valor": "desconocido"}}
    verificada = reglas.Verificada(
        {"cierre": ("si", "gdelt-infranken", "Rumunjska je podigla borbene zrakoplove")}
    )
    assert reglas.aplicar(documento, verificada, False, None).incidente["consecuencias"] == {
        "cierre": {"valor": "desconocido"}
    }
    documento["consecuencias"] = {"cierre": {"valor": "si"}}
    avistamiento = reglas.Verificada(
        {
            "duracion_min": (
                {"min": 30, "max": 30},
                "gdelt-infranken",
                "The sightings occurred around 10 p.m. for roughly 30 minutes",
            )
        }
    )
    cierre = reglas.aplicar(documento, avistamiento, True, None).incidente["consecuencias"]
    assert "minutos" not in cierre["cierre"]


def test_con_fuentes_sin_leer_no_se_quita_nada_por_falta_de_frase() -> None:
    documento = _nuremberg_alemana()
    incompleta = reglas.aplicar(documento, reglas.Verificada(), False, None, completa=False)
    assert incompleta.incidente["drones"]["numero"] == {"min": 2, "max": 10}
    assert incompleta.incidente["consecuencias"]["cierre"]["valor"] == "si"
