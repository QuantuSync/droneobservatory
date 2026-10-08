"""Archivo de alertas de alerts.in.ua (recogida/alertas.py), sin red: la API es un doble que
responde con alertas de la forma real (comprobada el 8 de octubre de 2026) y un reloj falso."""

import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from recogida import alertas, seguimiento_archivo
from recogida.alertas import Respuesta, Servicio
from recogida.seguimiento import Archivo, instante

TOKEN = "token-de-prueba-que-no-debe-salir"
INICIO = datetime(2026, 10, 4, 22, 30, tzinfo=UTC)


def alerta(
    ident: int, uid: str = "101", fin: str | None = None, amenazas: bool = True
) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "id": ident,
        "location_title": "Ізмаїльський район",
        "location_type": "raion",
        "started_at": "2026-10-04T22:31:56.261Z",
        "finished_at": fin,
        "updated_at": "2026-10-04T22:32:01.000Z",
        "alert_type": "air_raid",
        "location_oblast": "Одеська область",
        "location_uid": uid,
        "notes": None,
        "country": None,
        "alert_level": "yellow",
        "location_title_en": "Izmail raion",
        "location_oblast_uid": int(uid),
    }
    if amenazas:
        datos["threats"] = [{
            "threat_type": "drones", "level": "yellow", "started_at": "2026-10-04T22:31:56.261Z",
            "source_message": "Дронова загроза (жовтий рівень)",
        }]  # fmt: skip
    return datos


def cuerpo(lista: list[dict[str, Any]]) -> str:
    return json.dumps({"alerts": lista, "meta": {"type": "full"}}, ensure_ascii=False)


class Api:
    """Doble de la API: lo que responde cada ruta, con 304 si no ha cambiado."""

    def __init__(self, reloj: "Reloj") -> None:
        self.reloj = reloj
        self.respuestas: dict[str, tuple[int, str]] = {}
        self.pedidas: list[tuple[float, str, dict[str, str]]] = []
        self.version: dict[str, str] = {}

    def poner(self, ruta: str, http: int, texto: str) -> None:
        self.respuestas[ruta] = (http, texto)
        self.version[ruta] = f"v{len(self.pedidas)}-{hash(texto)}"

    def __call__(self, ruta: str, cabeceras: dict[str, str]) -> Respuesta:
        self.pedidas.append((self.reloj.t, ruta, dict(cabeceras)))
        http, texto = self.respuestas.get(ruta, (200, cuerpo([])))
        marca = self.version.get(ruta, "v0")
        if http == 200 and cabeceras.get("If-Modified-Since") == marca:
            return Respuesta(304, "", marca)
        return Respuesta(http, texto, marca if http == 200 else None)


class Reloj:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def ahora(self) -> datetime:
        return INICIO + timedelta(seconds=self.t - 1000.0)


def servicio(tmp_path: Path) -> tuple[Servicio, Api, Reloj]:
    reloj = Reloj()
    api = Api(reloj)
    s = Servicio(tmp_path / "datos", tmp_path / "alertas.json", api, reloj, reloj.ahora)
    s.tabla.cargar(reloj.ahora())
    return s, api, reloj


def correr(s: Servicio, reloj: Reloj, segundos: float) -> None:
    fin = reloj.t + segundos
    while reloj.t < fin:
        # Como el servicio: nunca duerme más de 5 s seguidos.
        reloj.t += min(max(s.paso(), 0.5), 5.0)
    s.crudo.cerrar()
    s.tabla.archivo.cerrar()


def lineas(datos: Path, fuente: str) -> list[dict[str, Any]]:
    return [
        json.loads(t)
        for r in alertas.ficheros(datos, fuente)
        for t in r.read_text("utf-8").splitlines()
    ]


def test_respeta_los_limites_y_baja_el_historico_de_las_27_regiones(tmp_path: Path) -> None:
    s, api, reloj = servicio(tmp_path)
    correr(s, reloj, 40 * 60)
    momentos = [t for t, _, _ in api.pedidas]
    # Nunca dos consultas a menos de 20 s, ni más de 3 en un minuto.
    assert all(b - a >= alertas.PAUSA_MINIMA_S for a, b in itertools.pairwise(momentos))
    assert max(sum(1 for t in momentos if m <= t < m + 60) for m in momentos) <= 3
    historico = [(t, r) for t, r, _ in api.pedidas if "/regions/" in r]
    assert all(b - a >= 60 for (a, _), (b, _) in itertools.pairwise(historico))
    assert {r for _, r in historico} == {alertas.HISTORICO.format(uid=u) for u in alertas.REGIONES}
    assert len(historico) == 27
    assert s.tabla.ultima_pasada_historico is not None
    # Las activas, cada minuto.
    activas = [t for t, r, _ in api.pedidas if r == alertas.ACTIVAS]
    assert 38 <= len(activas) <= 41


def test_guarda_solo_lo_que_cambia_y_la_tabla_solo_crece(tmp_path: Path) -> None:
    s, api, reloj = servicio(tmp_path)
    s.tabla.historico_pendiente = []
    s.tabla.ultima_pasada_historico = instante(reloj.ahora())
    api.poner(alertas.ACTIVAS, 200, cuerpo([alerta(1), alerta(2, "105")]))
    correr(s, reloj, 150)  # tres consultas: la primera guarda, las otras dos son 304
    datos = tmp_path / "datos"
    crudo = [linea for linea in lineas(datos, "alertas") if "via" in linea]
    assert len(crudo) == 1 and crudo[0]["fuente"] == "alerts.in.ua"
    assert any("If-Modified-Since" in c for _, _, c in api.pedidas[1:])
    # La 2 termina: sale de las activas; luego el histórico trae su fin oficial.
    api.poner(alertas.ACTIVAS, 200, cuerpo([alerta(1)]))
    correr(s, reloj, 60)
    terminada = alerta(2, "105", fin="2026-10-04T23:58:15.000Z", amenazas=False)
    s.tabla.incorporar([terminada], "historico", reloj.ahora())
    s.tabla.incorporar([terminada], "historico", reloj.ahora())  # el mismo: no se repite
    s.tabla.archivo.cerrar()
    tabla = lineas(datos, "alertas_tabla")
    dos = [(f["version"], f["via"], f["cambio"]) for f in tabla if f["id"] == 2]
    assert dos == [(0, "activas", "nueva"), (1, "activas", "sale_de_activas"),
                   (2, "historico", "cambia")]  # fmt: skip
    ultima = [f for f in tabla if f["id"] == 2][-1]
    assert ultima["utc"]["fin"] == "2026-10-04T23:58:15.000Z"
    assert ultima["alerta"]["finished_at"] == "2026-10-04T23:58:15.000Z"
    assert all(f["fuente"] == "alerts.in.ua" for f in tabla)
    uno = [f for f in tabla if f["id"] == 1]
    assert len(uno) == 1 and uno[0]["utc"]["amenazas"] == ["2026-10-04T22:31:56.261Z"]
    registro = json.loads((tmp_path / "alertas.json").read_text("utf-8")) if (
        tmp_path / "alertas.json").exists() else s.documento_registro()  # fmt: skip
    assert registro["fuente"] == "alerts.in.ua"
    assert s.documento_registro()["ultima_respuesta"]


def test_errores_de_autorizacion_y_esperas(tmp_path: Path) -> None:
    s, api, reloj = servicio(tmp_path)
    api.poner(alertas.ACTIVAS, 401, '{"message": "API token required"}')
    correr(s, reloj, 30)
    assert s.documento_registro()["error_autorizacion"]["http"] == 401
    antes = len(api.pedidas)
    correr(s, reloj, alertas.ESPERA_AUTORIZACION_S - 60)
    assert len(api.pedidas) == antes  # nada en 10 minutos
    api.poner(alertas.ACTIVAS, 200, cuerpo([alerta(1)]))
    correr(s, reloj, 120)
    assert "error_autorizacion" not in s.documento_registro()
    # Un fallo de red espera 1, 2, 4… minutos.
    api.poner(alertas.ACTIVAS, 0, "URLError: sin red")
    s.tabla.historico_pendiente = []
    s.tabla.ultima_pasada_historico = instante(reloj.ahora())
    inicio = len(api.pedidas)
    correr(s, reloj, 7 * 60 + 30)
    fallidas = [t for t, r, _ in api.pedidas[inicio:] if r == alertas.ACTIVAS]
    pausas = [b - a for a, b in itertools.pairwise(fallidas)]
    assert [round(x) for x in pausas[:3]] == [60, 120, 240]


def test_el_token_no_sale_en_ningun_fichero(tmp_path: Path) -> None:
    s, api, reloj = servicio(tmp_path)
    api.poner(alertas.ACTIVAS, 403, '{"message": "Forbidden"}')
    correr(s, reloj, 30)
    s.guardar_registro()
    s.tabla.guardar(reloj.ahora())
    for ruta in tmp_path.rglob("*"):
        if ruta.is_file():
            assert TOKEN not in ruta.read_text("utf-8")


def test_tabla_desde_crudo_no_repite(tmp_path: Path) -> None:
    datos = tmp_path / "datos"
    archivo = Archivo(datos, alertas.CRUDO)
    linea = {
        "via": "historico",
        "fuente": "alerts.in.ua",
        "url": "/v1/regions/18/alerts/month_ago.json",
        "region": 18,
        "http": 200,
        "last_modified": None,
        "crudo": cuerpo([alerta(7, amenazas=False), alerta(8, "105", amenazas=False)]),
    }
    archivo.escribir(linea, INICIO)
    archivo.cerrar()
    primera = alertas.tabla_desde_crudo(datos, INICIO + timedelta(hours=1))
    assert primera == {"respuestas": 1, "nuevas": 2, "cambian": 0, "salen": 0}
    segunda = alertas.tabla_desde_crudo(datos, INICIO + timedelta(hours=1))
    assert segunda == {"respuestas": 1, "nuevas": 0, "cambian": 0, "salen": 0}
    # Sin el estado, se rehace leyendo la tabla y tampoco repite.
    (datos / "alertas_tabla" / "estado.json").unlink()
    tercera = alertas.tabla_desde_crudo(datos, INICIO + timedelta(hours=1))
    assert tercera["nuevas"] == 0
    assert len(lineas(datos, "alertas_tabla")) == 2


def test_el_archivo_comprime_indexa_y_copia_las_alertas(tmp_path: Path) -> None:
    s, api, reloj = servicio(tmp_path)
    s.tabla.historico_pendiente = []
    s.tabla.ultima_pasada_historico = instante(reloj.ahora())
    api.poner(alertas.ACTIVAS, 200, cuerpo([alerta(1), alerta(2, "105")]))
    correr(s, reloj, 60)
    datos = tmp_path / "datos"
    hechos = seguimiento_archivo.comprimir_cerrados(datos, INICIO + timedelta(hours=3))
    assert {p.name for p in hechos} == {
        "alertas-2026-10-04T22.jsonl.gz", "alertas_tabla-2026-10-04T22.jsonl.gz",
    }  # fmt: skip
    indice = seguimiento_archivo.componer_indice(datos, INICIO.date())
    assert indice["alertas"] == {"alertas_distintas": 2, "versiones": {"nueva": 2}}
    assert indice["mensajes_por_via"]["alertas:activas"] == 1
    nombres = {f["nombre"] for f in indice["ficheros"]}
    assert "alertas/2026/10/alertas-2026-10-04T22.jsonl.gz" in nombres
