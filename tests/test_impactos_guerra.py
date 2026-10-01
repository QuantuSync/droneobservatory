"""Impactos con lugar: enlace con el ataque de la noche, fuentes que se unen, credibilidad
(regla general, confirmación cruzada, foco térmico), mensajes editados, procesado de punta a
punta desde lo que deja el lector, extractor y restricciones de Rosaviatsia."""

import copy
import dataclasses
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste, guerra
from proceso import extraccion_guerra, impactos_guerra, restricciones
from proceso.impactos_guerra import Ataques, enlazar
from proceso.mensajes_guerra import MensajeLeido, analizar
from recogida import canales_guerra
from recogida import guerra as paso
from recogida.canales_guerra import Canal, Datos
from tests import ejemplos
from tests.nomenclator_falso import nomenclator

N = nomenclator()
AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def canal(id_: str, nombre: str, region: str | None, sentido: str, fiabilidad: str, origen: str,
          pais: str, institucion: str | None = None) -> Canal:  # fmt: skip
    return Canal(
        id=id_, canal=nombre, grupo="ova_ua" if origen == "oficial" else "gobernadores_ru",
        pais=pais, region=region, sentido=sentido, idioma="uk" if pais == "UA" else "ru",
        titulo=nombre, insignia=False, descripcion_enlaza=(), web_oficial=None, web_enlaza=None,
        web_desde_servidor=False, fiabilidad=fiabilidad, origen=origen, medio=nombre,
        autoridad_ocupacion=False, identificado={"fecha": "2026-10-01"},
        institucion=institucion or id_,
    )  # fmt: skip


OVA = canal("ova_kharkiv", "kharkivoda", "UA-63", "RU_UA", "B", "oficial", "UA")
OVA_JEFE = canal("ova_kharkiv_jefe", "synegubov", "UA-63", "RU_UA", "B", "oficial", "UA",
                 institucion="ova_kharkiv")  # fmt: skip
ESTADO_MAYOR = canal("estado_mayor_ua", "GeneralStaffZSU", None, "UA_RU", "C", "parte", "UA")
GOBERNADOR = canal("gob_riazan", "gobriazan", "RU-RYA", "UA_RU", "C", "parte", "RU")
CANALES = {c.canal.lower(): c for c in (OVA, OVA_JEFE, ESTADO_MAYOR, GOBERNADOR)}


@pytest.fixture(autouse=True)
def canales_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impactos_guerra, "_canales", lambda: CANALES)


def ataque(id_: str, sentido: str, inicio: str, fin: str, **extra: Any) -> dict[str, Any]:
    documento = ejemplos.ataque_completo()
    documento.update(
        id=id_, sentido=sentido,
        periodo={"inicio": ejemplos.instante(inicio), "fin": ejemplos.instante(fin)}, **extra,
    )  # fmt: skip
    return documento


NOCHE_RU = ataque("EODI-UA-2026-1013", "RU_UA", "2026-09-29T15:00Z", "2026-09-30T05:00Z")
DIA_RU = ataque("EODI-UA-2026-1015", "RU_UA", "2026-09-30T05:00Z", "2026-09-30T15:30Z")
NOCHE_UA = ataque("EODI-UA-2026-1014", "UA_RU", "2026-09-29T17:00Z", "2026-09-30T05:00Z")
TRAMO = ataque("EODI-UA-2026-1010", "UA_RU", "2026-09-29T17:00Z", "2026-09-29T20:00Z",
               incluido_en="EODI-UA-2026-1014")  # fmt: skip
ATAQUES = Ataques([NOCHE_RU, DIA_RU, NOCHE_UA, TRAMO])


def momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


# --- Enlace -------------------------------------------------------------------------------


def test_noche_declarada() -> None:
    leido = MensajeLeido(noche=date(2026, 9, 30), es_noche=True)
    assert enlazar(ATAQUES, "UA_RU", momento("2026-09-30T09:00Z"), leido) == (
        "EODI-UA-2026-1014", "noche_declarada",
    )  # fmt: skip


def test_el_tramo_incluido_en_un_total_no_se_usa() -> None:
    leido = MensajeLeido()
    assert enlazar(ATAQUES, "UA_RU", momento("2026-09-29T18:00Z"), leido)[0] == "EODI-UA-2026-1014"


def test_mensaje_de_la_manana_que_habla_de_la_noche() -> None:
    # Publicado a las 07:30 de Kyiv, con el periodo de día ya empezado: «вночі» manda.
    leido = MensajeLeido(es_noche=True)
    assert enlazar(ATAQUES, "RU_UA", momento("2026-09-30T05:30Z"), leido) == (
        "EODI-UA-2026-1013", "noche_mencionada",
    )  # fmt: skip
    assert enlazar(ATAQUES, "RU_UA", momento("2026-09-30T05:30Z"), MensajeLeido())[0] == (
        "EODI-UA-2026-1015"
    )


def test_un_dia_anterior_con_varios_ataques_queda_sin_enlace() -> None:
    leido = MensajeLeido(dia=date(2026, 9, 30))
    assert enlazar(ATAQUES, "RU_UA", momento("2026-10-01T09:00Z"), leido) == (None, None)


def test_sin_ataque_que_encaje() -> None:
    assert enlazar(ATAQUES, "RU_UA", momento("2026-09-20T12:00Z"), MensajeLeido()) == (None, None)


# --- Alta y credibilidad --------------------------------------------------------------------


def leer(texto: str, regiones: frozenset[str] | None, publicado: str) -> MensajeLeido:
    from recogida.guerra import raices_regiones

    return analizar(texto, momento(publicado), N, regiones, raices_regiones())


def test_dos_mensajes_del_mismo_lugar_y_ataque_son_un_impacto() -> None:
    almacen = Almacen.abrir()
    texto = "Вночі ворог вдарив дроном по Чугуєву, пошкоджено приватний будинок."
    for publicacion_id, hora in ((100, "2026-09-30T03:10Z"), (101, "2026-09-30T04:40Z")):
        leido = leer(texto, frozenset({"UA-63"}), hora)
        impactos_guerra.incorporar(almacen, ATAQUES, OVA, publicacion_id, momento(hora), leido,
                                   AHORA)  # fmt: skip
    (impacto,) = impactos_guerra.vigentes(almacen)
    assert impacto["ataque"] == "EODI-UA-2026-1013"
    assert len(impacto["fuentes"]) == 2
    # Dos mensajes del mismo canal no son independientes: una fuente B, «probable».
    assert impacto["credibilidad"] == 2
    assert "reivindicacion_de_parte" not in impacto
    # Tampoco el canal del jefe de la misma administración.
    leido = leer(texto, frozenset({"UA-63"}), "2026-09-30T04:50Z")
    impactos_guerra.incorporar(almacen, ATAQUES, OVA_JEFE, 7, momento("2026-09-30T04:50Z"),
                               leido, AHORA)  # fmt: skip
    assert impactos_guerra.vigentes(almacen)[0]["credibilidad"] == 2


def _refineria(almacen: Almacen) -> dict[str, Any]:
    texto = (
        "У ніч на 30 вересня 2026 року підрозділи Сил оборони України уразили Рязанський НПЗ у "
        "Рязанській області рф. Зафіксовано пожежу. Застосовувалися ударні БпЛА."
    )
    leido = leer(texto, None, "2026-09-30T08:00Z")
    impactos_guerra.incorporar(almacen, ATAQUES, ESTADO_MAYOR, 42000, momento("2026-09-30T08:00Z"),
                               leido, AHORA)  # fmt: skip
    (impacto,) = impactos_guerra.vigentes(almacen)
    return impacto


def test_reivindicacion_del_estado_mayor() -> None:
    impacto = _refineria(Almacen.abrir())
    assert impacto["lugar"]["id"] == "osm:way/1"
    assert impacto["ataque"] == "EODI-UA-2026-1014"
    assert impacto["credibilidad"] == 3
    assert impacto["reivindicacion_de_parte"] is True


def test_confirmacion_cruzada_del_gobernador_sube_a_probable() -> None:
    almacen = Almacen.abrir()
    _refineria(almacen)
    texto = "В результате атаки БПЛА на Рязанском НПЗ произошло возгорание, пострадавших нет."
    leido = leer(texto, frozenset({"RU-RYA"}), "2026-09-30T06:00Z")
    impactos_guerra.incorporar(almacen, ATAQUES, GOBERNADOR, 5, momento("2026-09-30T06:00Z"),
                               leido, AHORA)  # fmt: skip
    (impacto,) = impactos_guerra.vigentes(almacen)
    assert len(impacto["fuentes"]) == 2
    assert impacto["credibilidad"] == 2
    assert "reivindicacion_de_parte" not in impacto


def test_el_foco_termico_detectado_sube_la_credibilidad() -> None:
    almacen = Almacen.abrir()
    impacto = _refineria(almacen)
    almacen.guardar_foco_termico(impacto["id"], ejemplos.foco_termico())
    assert impactos_guerra.aplicar_focos(almacen, AHORA) == 1
    (despues,) = impactos_guerra.vigentes(almacen)
    assert despues["credibilidad"] == 2
    assert "reivindicacion_de_parte" not in despues


def test_los_partes_diarios_no_se_cruzan_con_firms() -> None:
    almacen = Almacen.abrir()
    impacto = _refineria(almacen)
    almacen.guardar_impacto_guerra({**impacto, "parte_diario": True})
    almacen.guardar_foco_termico(impacto["id"], ejemplos.foco_termico())
    assert impactos_guerra.aplicar_focos(almacen, AHORA) == 0
    (despues,) = impactos_guerra.vigentes(almacen)
    assert not impactos_guerra.con_firms(despues)
    assert despues["credibilidad"] == impacto["credibilidad"]


def test_sin_ataque_se_enlaza_despues_cuando_llega_el_parte() -> None:
    almacen = Almacen.abrir()
    texto = "Ворог вдарив дроном по Чугуєву, пошкоджено будинок."
    leido = leer(texto, frozenset({"UA-63"}), "2026-09-30T04:00Z")
    impactos_guerra.incorporar(almacen, Ataques([]), OVA, 9, momento("2026-09-30T04:00Z"), leido,
                               AHORA)  # fmt: skip
    assert "ataque" not in impactos_guerra.vigentes(almacen)[0]
    resumen = impactos_guerra.reenlazar(almacen, ATAQUES, momento("2026-09-30T10:00Z"))
    assert resumen.reenlazados == 1
    assert impactos_guerra.vigentes(almacen)[0]["ataque"] == "EODI-UA-2026-1013"


# --- Procesado desde lo que deja el lector ---------------------------------


def _datos(tmp_path: Path, publicaciones: list[tuple[int, str, str]]) -> Datos:
    datos = Datos(tmp_path)
    ruta = tmp_path / "canales" / "kharkivoda" / "2026-09.jsonl"
    ruta.parent.mkdir(parents=True)
    with ruta.open("w", encoding="utf-8") as fichero:
        for id_, fecha, texto in publicaciones:
            fichero.write(json.dumps({"id": id_, "fecha": fecha, "texto": texto},
                                     ensure_ascii=False) + "\n")  # fmt: skip
    datos.guardar_control({"canales": {"ova_kharkiv": {"resultado": "leido"}}})
    return datos


def test_procesado_y_mensaje_editado(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    for documento in (NOCHE_RU, DIA_RU):
        sin_extra = {k: v for k, v in documento.items() if k != "restricciones_aeropuertos"}
        almacen.guardar_ataque_ucrania(copy.deepcopy(sin_extra), AHORA)
    datos = _datos(tmp_path, [
        (1, "2026-09-30T03:10:00Z", "Вночі ворог вдарив дроном по Чугуєву, пошкоджено будинок."),
        (2, "2026-09-30T03:20:00Z", "🟡 Чугуївський район — повітряна тривога: Дронова загроза"),
        (3, "2026-09-30T03:30:00Z", "Ворог завдав ракетного удару по Харкову."),
    ])  # fmt: skip
    resumen = paso.procesar(almacen, datos, [OVA], N, AHORA)
    assert resumen.con_impactos == 1
    assert resumen.motivos.get("aviso") == 1
    assert resumen.motivos.get("sin_dron") == 1
    assert [d["lugar"]["nombre"] for d in impactos_guerra.vigentes(almacen)] == ["Чугуїв"]
    # Sin cambios, el mismo mensaje no se vuelve a leer.
    assert paso.procesar(almacen, datos, [OVA], N, AHORA, todo=True).mensajes == 0
    # Editado: ya no habla de Chuhuiv, sino de Malynivka del distrito de Chuhuiv.
    ruta = tmp_path / "canales" / "kharkivoda" / "2026-09.jsonl"
    with ruta.open("a", encoding="utf-8") as fichero:
        fichero.write(json.dumps({
            "id": 1, "fecha": "2026-09-30T03:10:00Z",
            "texto": "Вночі ворог вдарив дроном по Малинівці Чугуївського району.",
        }, ensure_ascii=False) + "\n")  # fmt: skip
    paso.procesar(almacen, Datos(tmp_path), [OVA], N, AHORA, todo=True)
    vigentes = impactos_guerra.vigentes(almacen)
    assert [d["lugar"]["nombre"] for d in vigentes] == ["Малинівка"]
    retirado = [d for d in almacen.impactos_guerra() if "retirado" in d]
    assert retirado[0]["lugar"]["nombre"] == "Чугуїв"


def test_sin_datos_del_lector_el_paso_no_hace_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(canales_guerra.VARIABLE_DATOS, str(tmp_path / "nada"))
    estados, resumen = paso.paso_horario(Almacen.abrir(), AHORA)
    assert resumen.mensajes == 0
    assert {e["estado"] for e in estados.values()} == {"no_leida"}


# --- Extractor ---------------------------------------------------------------------------------


TEXTO_MIXTO = "Ворог атакував Нікополь дронами та артилерією. Пошкоджено приватний будинок."


def respuesta(lugares: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": json.dumps({"lugares": lugares})}],
        "usage": {"input_tokens": 900, "output_tokens": 120},
    }


def lugar(**cambios: Any) -> dict[str, Any]:
    base = {
        "nombre": "Нікополь", "nivel": "localidad", "arma": "dron", "tipo": "impacto",
        "categorias": ["residencial"], "frase": "Ворог атакував Нікополь дронами та артилерією.",
        "confianza": 0.9,
    }  # fmt: skip
    return {**base, **cambios}


def test_validacion_de_lo_que_da_el_extractor() -> None:
    lugares = [
        lugar(),
        lugar(nombre="Марганець", arma="artilleria", frase="Пошкоджено приватний будинок."),
        lugar(nombre="Марганець", frase="Марганець атакували дрони"),
        lugar(nombre="Марганець", confianza=0.3, frase="Пошкоджено приватний будинок."),
        lugar(nombre="Харків", frase="Пошкоджено приватний будинок."),
    ]
    validacion = extraccion_guerra.validar(lugares, TEXTO_MIXTO, N, frozenset({"UA-12"}), ())
    assert [i.lugar.nombre for i in validacion.impactos] == ["Нікополь"]
    assert validacion.descartes == [
        "Марганець: arma artilleria",
        "Марганець: frase que no está en el texto",
        "Марганець: confianza baja",
        "Харків: no se resuelve en el nomenclátor",
    ]


class Servicio:
    def __init__(self, lugares: list[dict[str, Any]]) -> None:
        self.lugares = lugares
        self.cuerpos: list[dict[str, Any]] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.cuerpos.append(cuerpo)
        return respuesta(self.lugares)


def test_el_extractor_con_su_limite_diario_y_su_registro(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    dnipro = dataclasses.replace(OVA, id="ova_dnipro", canal="adm_dp", region="UA-12")
    datos = Datos(tmp_path)
    ruta = tmp_path / "canales" / "adm_dp" / "2026-09.jsonl"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"id": 5, "fecha": "2026-09-30T10:00:00Z", "texto": TEXTO_MIXTO},
                               ensure_ascii=False) + "\n", encoding="utf-8")  # fmt: skip
    datos.guardar_control({"canales": {}})
    resumen = paso.procesar(almacen, datos, [dnipro], N, AHORA)
    assert resumen.para_extractor == 1
    servicio = Servicio([lugar()])
    hecho = extraccion_guerra.horaria(almacen, datos, [dnipro], N, (), AHORA, lambda: servicio)
    assert (hecho.llamadas, hecho.impactos) == (1, 1)
    (impacto,) = impactos_guerra.vigentes(almacen)
    assert impacto["lecturas"][0]["metodo"] == "extractor"
    assert almacen.gastado(coste.Modo.GUERRA.value, "2026-10-01") > 0
    # El texto que se manda es el mínimo, sin saludos.
    assert "Нікополь" in servicio.cuerpos[0]["messages"][0]["content"]
    # Ya extraído: no se vuelve a llamar. Y con el límite diario agotado, tampoco.
    assert extraccion_guerra.horaria(almacen, datos, [dnipro], N, (), AHORA,
                                     lambda: servicio).llamadas == 0  # fmt: skip


def test_limite_diario_propio() -> None:
    almacen = Almacen.abrir()
    almacen.registrar_llamada({
        "fecha": "2026-10-01T08:00:00Z", "modo": "guerra", "candidato": "x", "lote": False,
        "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0, "coste": 0.199,
    })  # fmt: skip
    with pytest.raises(coste.LimiteGasto):
        coste.comprobar(almacen.gastado("guerra", "2026-10-01"), 0.01, coste.Modo.GUERRA)
    # No toca el límite horario de las noticias.
    assert almacen.gastado("horario", "2026-10-01") == 0


def test_la_respuesta_sin_lista_no_vale() -> None:
    with pytest.raises(guerra.RespuestaInvalida):
        guerra.leer_respuesta(
            {"stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]}
        )


# --- Rosaviatsia ------------------------------------------------------------------------------


def test_restriccion_emparejada_por_respuesta_y_enlazada_al_ataque() -> None:
    almacen = Almacen.abrir()
    ataques = Ataques([NOCHE_UA])
    inicio = restricciones.leer(
        "▫️Аэропорт КАЛУГА (Грабцево) ✈️ВВЕДЕНЫ временные ограничения", momento("2026-09-29T21:00Z")
    )
    fin = restricciones.leer(
        "⬜️Аэропорт КАЛУГА (Грабцево) ✈️СНЯТЫ ограничения", momento("2026-09-30T03:30Z")
    )
    assert inicio is not None and fin is not None
    restricciones.incorporar(almacen, N, ataques, 8287, momento("2026-09-29T21:00Z"), None, inicio)
    restricciones.incorporar(almacen, N, ataques, 8289, momento("2026-09-30T03:30Z"), 8287, fin)
    (r,) = almacen.restricciones()
    assert r["aeropuerto"]["oaci"] == "UUBC"
    assert r["ataque"] == "EODI-UA-2026-1014"
    assert r["emparejado"] == "respuesta"
    assert r["horas"] == 6.5
    assert restricciones.por_ataque([r]) == {"EODI-UA-2026-1014": {"aeropuertos": 1, "horas": 6.5}}


def test_un_levantamiento_sin_restriccion_abierta_no_hace_nada() -> None:
    almacen = Almacen.abrir()
    fin = restricciones.leer("Аэропорт ПЕНЗА ✈️СНЯТЫ ограничения", AHORA)
    assert fin is not None
    assert restricciones.incorporar(almacen, N, Ataques([]), 9, AHORA, None, fin) == 0


def test_dia_de_la_restriccion_en_hora_de_moscu() -> None:
    assert restricciones.dia(momento("2026-09-30T22:30Z")) == date(2026, 10, 1)


class ServicioLotes:
    """Servicio de lotes falso: termina el lote en la segunda consulta."""

    def __init__(self, lugares: list[dict[str, Any]]) -> None:
        self.lugares = lugares
        self.enviadas: list[dict[str, Any]] = []
        self.consultas = 0

    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]:
        self.enviadas = peticiones
        return {"id": "lote-1", "processing_status": "in_progress"}

    def lote(self, id_: str) -> dict[str, Any]:
        self.consultas += 1
        estado = "ended" if self.consultas > 1 else "in_progress"
        return {"id": id_, "processing_status": estado}

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"custom_id": p["custom_id"],
             "result": {"type": "succeeded", "message": respuesta(self.lugares)}}
            for p in self.enviadas
        ]  # fmt: skip


def test_el_lote_del_historico_se_envia_una_vez_y_se_incorpora_sin_esperar(
    tmp_path: Path,
) -> None:
    almacen = Almacen.abrir()
    dnipro = dataclasses.replace(OVA, id="ova_dnipro", canal="adm_dp", region="UA-12")
    datos = Datos(tmp_path)
    ruta = tmp_path / "canales" / "adm_dp" / "2025-03.jsonl"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"id": 5, "fecha": "2025-03-10T10:00:00Z", "texto": TEXTO_MIXTO},
                               ensure_ascii=False) + "\n", encoding="utf-8")  # fmt: skip
    datos.guardar_control({"canales": {"ova_dnipro": {"historico": {"siguiente": 3}}}})
    paso.procesar(almacen, datos, [dnipro], N, AHORA)
    servicio = ServicioLotes([lugar()])

    def paso_lote(al_dia: bool = True) -> dict[str, Any] | None:
        return extraccion_guerra.paso_lote(
            almacen, lambda: servicio, datos, [dnipro], N, (), AHORA, al_dia
        )

    # Con el histórico a medias o lo leído sin procesar, no se envía.
    assert paso_lote() is None
    datos.guardar_control({"canales": {"ova_dnipro": {"historico": {"terminado": True}}}})
    assert paso_lote(al_dia=False) is None
    assert (paso_lote() or {}).get("enviadas") == 1
    # La ejecución siguiente consulta y no espera; la otra lo incorpora.
    assert paso_lote() == {"lote": "lote-1", "estado": "en_proceso"}
    marca = paso_lote()
    assert marca is not None and (marca["estado"], marca["impactos"]) == ("incorporado", 1)
    (impacto,) = impactos_guerra.vigentes(almacen)
    assert impacto["lecturas"][0]["metodo"] == "extractor"
    assert almacen.gastado(coste.Modo.GUERRA_HISTORICO.value) > 0
    # Una sola vez: después no hace nada.
    assert paso_lote() is None
    assert len(servicio.enviadas) == 1
