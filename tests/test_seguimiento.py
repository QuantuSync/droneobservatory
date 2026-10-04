"""Captura del seguimiento en directo (recogida/seguimiento.py) y su archivo
(recogida/seguimiento_archivo.py), sin red: el flujo, el REST y Telegram son dobles que
devuelven mensajes reales capturados el 4 de octubre de 2026 (tests/fixtures/seguimiento/)."""

import asyncio
import contextlib
import gzip
import hashlib
import json
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from recogida import estado, salud, seguimiento, seguimiento_archivo
from recogida.seguimiento import Bloque, Respuesta, Ritmo, Servicio, bloques_pagina

MUESTRAS = Path(__file__).parent / "fixtures" / "seguimiento"
INICIO = datetime(2026, 10, 4, 10, 59, 50, tzinfo=UTC)


def frames() -> list[str]:
    """Mensajes del flujo tal como llegaron (snapshot, alerts, upsert, remove, heartbeat)."""
    lineas = (MUESTRAS / "neptun_flujo.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linea)["crudo"] for linea in lineas if linea.strip()]


def muestra(nombre: str) -> str:
    return (MUESTRAS / nombre).read_text(encoding="utf-8")


class Reloj:
    """Hora de pared y reloj monótono falsos, que avanzan a mano o al dormir."""

    def __init__(self, inicio: datetime = INICIO) -> None:
        self.momento = inicio
        self.t = 0.0

    def avanzar(self, segundos: float) -> None:
        self.momento += timedelta(seconds=segundos)
        self.t += segundos

    def ahora(self) -> datetime:
        return self.momento

    def reloj(self) -> float:
        return self.t

    async def dormir(self, segundos: float) -> None:
        self.avanzar(segundos)
        await asyncio.sleep(0)


class Conexion:
    """Doble de la conexión WebSocket: entrega sus mensajes (avanzando el reloj entre ellos) y
    después lanza el error indicado (el corte)."""

    def __init__(self, mensajes: Sequence[str | bytes], reloj: Reloj, corte: Exception) -> None:
        self.mensajes = list(mensajes)
        self.reloj = reloj
        self.corte = corte

    async def recv(self) -> str | bytes:
        await asyncio.sleep(0)
        if not self.mensajes:
            raise self.corte
        self.reloj.avanzar(1.0)
        return self.mensajes.pop(0)


def conector(
    guion: list[Conexion | Exception], servicio: list[Servicio]
) -> Callable[[], contextlib.AbstractAsyncContextManager[Conexion]]:
    """Cada llamada saca el siguiente paso del guion: una conexión o un fallo al conectar. Al
    acabar el guion pide parar."""

    @contextlib.asynccontextmanager
    async def conectar() -> AsyncIterator[Conexion]:
        if not guion:
            servicio[0].parar.set()
            await asyncio.sleep(0)
            raise ConnectionError("fin del guion")
        paso = guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        yield paso

    return conectar


class ServicioPrueba(Servicio):
    """Las esperas entre reconexiones se anotan y no duermen."""

    esperas: list[float]

    async def _esperar(self, segundos: float) -> None:
        self.esperas.append(segundos)
        await asyncio.sleep(0)


def servicio_de_prueba(
    tmp_path: Path,
    reloj: Reloj,
    guion: list[Conexion | Exception] | None = None,
    pedir: Callable[[str], Respuesta] | None = None,
) -> ServicioPrueba:
    caja: list[Servicio] = []
    s = ServicioPrueba(
        tmp_path / "datos",
        tmp_path / "registro.json",
        conectar=conector(guion or [], caja),
        pedir=pedir or (lambda url: Respuesta(503, "")),
        ahora=reloj.ahora,
        reloj=reloj.reloj,
        dormir=reloj.dormir,
    )
    s.esperas = []
    caja.append(s)
    return s


def lineas_archivo(datos: Path, fuente: str = "neptun") -> list[dict[str, Any]]:
    salida: list[dict[str, Any]] = []
    for ruta in sorted((datos / fuente).rglob("*.jsonl")):
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            salida.append(json.loads(linea))
    return salida


# --- Flujo: nada se pierde ni se transforma ---------------------------------------------------
def test_cada_mensaje_del_flujo_se_guarda_entero_y_en_orden(tmp_path: Path) -> None:
    reloj = Reloj()
    reales = frames()
    raros: list[str | bytes] = [b"\x00\x01binario", "no es json", '{"type":"nuevo_tipo"}']
    todos: list[str | bytes] = [*reales, *raros]
    guion: list[Conexion | Exception] = [Conexion(todos, reloj, ConnectionError("cortado"))]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    guardados = [x for x in lineas_archivo(s.datos) if x.get("via") == "ws"]
    assert [x["crudo"] for x in guardados[: len(reales)]] == reales
    assert guardados[len(reales)]["binario"] is True
    assert guardados[len(reales)]["crudo"] == "AAFiaW5hcmlv"
    assert [x["crudo"] for x in guardados[len(reales) + 1 :]] == raros[1:]
    tipos = {json.loads(f)["type"] for f in reales}
    assert {"snapshot", "upsert", "remove", "heartbeat", "alerts"} <= tipos
    for tipo in tipos:
        assert s.contadores.por_tipo[tipo] == sum(json.loads(f)["type"] == tipo for f in reales)
    assert s.contadores.por_tipo["nuevo_tipo"] == 1
    # La hora de recepción es la del momento en que llegó cada mensaje.
    assert guardados[0]["recibido"] == "2026-10-04T10:59:51.000000Z"


def test_la_linea_conserva_el_texto_byte_a_byte(tmp_path: Path) -> None:
    """El texto del mensaje vuelve idéntico al leer la línea (escapes, cirílico, espacios)."""
    reloj = Reloj()
    original = '{"type":"upsert","data":{"title":"Група БпЛА  (2+)\\n","x":1.50}}'
    guion: list[Conexion | Exception] = [Conexion([original], reloj, ConnectionError("x"))]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    (linea,) = [x for x in lineas_archivo(s.datos) if x.get("via") == "ws"]
    assert linea["crudo"] == original
    assert linea["crudo"].encode("utf-8") == original.encode("utf-8")


# --- Reconexión y huecos -----------------------------------------------------------------------
def test_reconecta_con_espera_creciente_y_anota_el_hueco(tmp_path: Path) -> None:
    reloj = Reloj()
    reales = frames()
    guion: list[Conexion | Exception] = [
        Conexion(reales[:3], reloj, ConnectionError("cortado por el servidor")),
        OSError("sin red"),
        OSError("sin red"),
        Conexion(reales[3:6], reloj, ConnectionError("otra vez")),
    ]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    # 2, 4 y 8 s entre intentos fallidos; tras la conexión breve no vuelve a empezar.
    assert s.esperas[:3] == [2.0, 4.0, 8.0]
    lineas = lineas_archivo(s.datos)
    huecos = [x for x in lineas if x.get("evento") == "hueco"]
    assert len(huecos) == 1
    hueco = huecos[0]
    ultima_antes = [x for x in lineas if x.get("via") == "ws"][2]["recibido"]
    primera_despues = [x for x in lineas if x.get("via") == "ws"][3]["recibido"]
    assert hueco["desde"] == ultima_antes
    assert hueco["hasta"] == primera_despues
    assert "cortado por el servidor" in hueco["motivo"]
    # El hueco va justo antes del primer mensaje tras reconectar, y también al registro común.
    indice = lineas.index(hueco)
    assert lineas[indice + 1].get("via") == "ws"
    comun = [json.loads(x) for x in (s.datos / "huecos.jsonl").read_text("utf-8").splitlines()]
    assert comun[0]["fuente"] == "neptun" and comun[0]["desde"] == ultima_antes
    eventos = [x["evento"] for x in lineas if "evento" in x]
    assert eventos.count("desconectado") == 4 and eventos.count("conectado") == 2


def test_tras_una_conexion_estable_la_espera_vuelve_a_empezar(tmp_path: Path) -> None:
    reloj = Reloj()
    largos: list[str | bytes] = [frames()[-1]] * 70  # 70 s conectado: estable
    guion: list[Conexion | Exception] = [
        OSError("a"),
        OSError("b"),
        Conexion(largos, reloj, ConnectionError("corte")),
        OSError("c"),
    ]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    assert s.esperas[:4] == [2.0, 4.0, 2.0, 4.0]


def test_un_minuto_sin_mensajes_es_una_conexion_muerta(tmp_path: Path) -> None:
    reloj = Reloj()
    guion: list[Conexion | Exception] = [Conexion([frames()[0]], reloj, TimeoutError())]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    desconexiones = [x for x in lineas_archivo(s.datos) if x.get("evento") == "desconectado"]
    assert desconexiones[0]["motivo"] == "sin mensajes en 60 s"


def test_un_hueco_de_mas_de_diez_minutos_queda_en_el_registro(tmp_path: Path) -> None:
    reloj = Reloj()
    s = servicio_de_prueba(tmp_path, reloj)
    s.recibido_flujo(frames()[0])
    s.desconectado("cortado")
    reloj.avanzar(11 * 60)
    s.recibido_flujo(frames()[1])
    s.guardar_registro()
    registro = json.loads((tmp_path / "registro.json").read_text("utf-8"))
    assert registro["ultimo_hueco_largo"]["desde"] == "2026-10-04T10:59:50.000000Z"
    assert registro["ultimo_hueco_largo"]["hasta"] == "2026-10-04T11:10:50.000000Z"


def test_al_arrancar_anota_el_hueco_desde_la_ejecucion_anterior(tmp_path: Path) -> None:
    reloj = Reloj()
    primero = servicio_de_prueba(tmp_path, reloj)
    primero.recibido_flujo(frames()[-1])
    primero.guardar_registro()
    reloj.avanzar(15 * 60)
    segundo = servicio_de_prueba(tmp_path, reloj)
    segundo.recibido_flujo(frames()[-1])
    huecos = [x for x in lineas_archivo(segundo.datos) if x.get("evento") == "hueco"]
    assert len(huecos) == 1
    assert huecos[0]["motivo"] == "servicio parado o reiniciado"
    assert huecos[0]["segundos"] == 900.0
    assert segundo.ultimo_hueco_largo is not None


# --- Rotación por horas ----------------------------------------------------------------------
def test_un_fichero_por_hora_de_recepcion(tmp_path: Path) -> None:
    reloj = Reloj(datetime(2026, 10, 4, 10, 59, 58, tzinfo=UTC))
    reales = frames()[:4]
    guion: list[Conexion | Exception] = [Conexion(list(reales), reloj, ConnectionError("x"))]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    s.neptun.cerrar()
    carpeta = s.datos / "neptun" / "2026" / "10"
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "neptun-2026-10-04T10.jsonl",
        "neptun-2026-10-04T11.jsonl",
    ]
    de_las_10 = (carpeta / "neptun-2026-10-04T10.jsonl").read_text("utf-8").splitlines()
    de_las_11 = (carpeta / "neptun-2026-10-04T11.jsonl").read_text("utf-8").splitlines()
    # 10:59:59 el primero; 11:00:00 en adelante los otros tres.
    assert [json.loads(x).get("crudo") for x in de_las_10 if '"via":"ws"' in x] == reales[:1]
    assert [json.loads(x).get("crudo") for x in de_las_11 if '"via":"ws"' in x] == reales[1:]


# --- Respaldo REST y su tope ------------------------------------------------------------------
def test_el_ritmo_deja_diez_segundos_entre_peticiones() -> None:
    reloj = Reloj()
    ritmo = Ritmo(10.0, reloj.reloj, reloj.dormir)
    momentos: list[float] = []

    async def pedir_varias() -> None:
        async def una() -> None:
            await ritmo.turno()
            momentos.append(reloj.t)

        await asyncio.gather(*(una() for _ in range(6)))

    asyncio.run(pedir_varias())
    assert len(momentos) == 6
    assert all(b - a >= 10.0 for a, b in pairwise(momentos))


def test_el_respaldo_y_los_mensajes_comparten_el_tope_de_una_peticion_cada_diez_segundos(
    tmp_path: Path,
) -> None:
    reloj = Reloj()
    pedidas: list[tuple[float, str]] = []
    cuerpos = {
        "threats": muestra("rest_threats.json"),
        "alerts": muestra("rest_alerts.json"),
        "messages": muestra("rest_messages.json"),
    }

    def pedir(url: str) -> Respuesta:
        pedidas.append((reloj.t, url))
        return Respuesta(200, cuerpos[url.rsplit("/", 1)[1]])

    s = servicio_de_prueba(tmp_path, reloj, pedir=pedir)
    turnos: list[float] = []

    class RitmoAnotado(Ritmo):
        async def turno(self) -> None:
            await super().turno()
            turnos.append(reloj.t)

    s.ritmo_rest = RitmoAnotado(seguimiento.INTERVALO_REST_S, reloj.reloj, reloj.dormir)
    s.desconectado("cortado")
    reloj.avanzar(31)

    async def correr() -> None:
        tareas = [asyncio.create_task(s.respaldo()), asyncio.create_task(s.mensajes())]
        while reloj.t < 400:
            await asyncio.sleep(0)
        s.parar.set()
        await asyncio.gather(*tareas, return_exceptions=True)

    asyncio.run(correr())
    assert len(pedidas) > 20
    # Cada petición sale en cuanto el ritmo le da el turno: todas, a 10 s o más de la anterior.
    momentos = turnos[: len(pedidas)]
    assert all(b - a >= 10.0 for a, b in pairwise(momentos))
    urls = {u.rsplit("/", 1)[1] for _, u in pedidas}
    assert urls == {"threats", "alerts", "messages"}
    guardadas = [x for x in lineas_archivo(s.datos) if x.get("via") == "rest"]
    assert {x["crudo"] for x in guardadas} == {cuerpos["threats"], cuerpos["alerts"]}
    assert s.hueco is not None and s.hueco.respaldo == len(guardadas)


def test_sin_corte_no_hay_respaldo(tmp_path: Path) -> None:
    reloj = Reloj()
    s = servicio_de_prueba(tmp_path, reloj)
    s.desconectado("cortado")
    reloj.avanzar(5)
    assert not s.en_respaldo()
    reloj.avanzar(30)
    assert s.en_respaldo()
    s.recibido_flujo(frames()[0])
    assert not s.en_respaldo()


def test_los_mensajes_solo_se_guardan_si_cambian(tmp_path: Path) -> None:
    reloj = Reloj()
    cuerpo = muestra("rest_messages.json")
    respuestas = [cuerpo, cuerpo, cuerpo.replace("2026-10-04T11:4", "2026-10-04T12:4")]
    s = servicio_de_prueba(tmp_path, reloj, pedir=lambda url: Respuesta(200, respuestas.pop(0)))
    for _ in range(3):
        asyncio.run(s._mensajes_una_vez())
        reloj.avanzar(120)
    lineas = lineas_archivo(s.datos)
    guardados = [x for x in lineas if x.get("via") == "mensajes"]
    assert [x["crudo"] for x in guardados] == [
        cuerpo,
        cuerpo.replace("2026-10-04T11:4", "2026-10-04T12:4"),
    ]
    # Entre la segunda y la tercera no se solapan: queda anotado que falta lo de en medio.
    assert [x["evento"] for x in lineas if "evento" in x] == ["hueco_mensajes"]


# --- Fuerza Aérea ---------------------------------------------------------------------------
def test_bloques_de_la_pagina_del_canal() -> None:
    html = muestra("kpszsu_pagina.html")
    bloques = bloques_pagina(html)
    assert [b.id for b in bloques] == [82766, 82767, 82768]
    for bloque in bloques:
        assert bloque.crudo.startswith('<div class="tgme_widget_message_wrap')
        assert bloque.crudo in html
        assert f'data-post="kpszsu/{bloque.id}"' in bloque.crudo
    assert bloques[0].fecha.startswith("2026-10-04T")
    assert "tgme_widget_message_centered" not in bloques[-1].crudo


def test_el_canal_guarda_lo_nuevo_y_las_ediciones_una_vez(tmp_path: Path) -> None:
    reloj = Reloj()
    html = muestra("kpszsu_pagina.html")
    editada = html.replace("Реактивний БпЛА", "Реактивний БпЛА (уточнено)")
    paginas = [html, html.replace(">1</span>", ">7</span>"), editada]

    def pedir(url: str) -> Respuesta:
        return Respuesta(200, paginas.pop(0))

    s = servicio_de_prueba(tmp_path, reloj, pedir=pedir)
    for _ in range(3):
        asyncio.run(s.kpszsu_una_vez(repasar=False))
        reloj.avanzar(60)
    guardadas = lineas_archivo(s.datos, "kpszsu")
    primeras = [x for x in guardadas if x["version"] == 0]
    assert [x["id"] for x in primeras] == [82766, 82767, 82768]
    # Cambiar el contador de vistas no es una edición; cambiar el texto sí.
    ediciones = [x for x in guardadas if x["version"] == 1]
    assert ediciones and all("уточнено" in x["crudo"] for x in ediciones)
    assert len(guardadas) == 3 + len(ediciones)
    # Tras reiniciar, lo ya guardado no se repite.
    s.guardar_registro()
    otro = servicio_de_prueba(tmp_path, reloj, pedir=lambda url: Respuesta(200, editada))
    asyncio.run(otro.kpszsu_una_vez(repasar=False))
    assert len(lineas_archivo(s.datos, "kpszsu")) == len(guardadas)


def test_el_canal_enlaza_con_las_paginas_anteriores_si_falta_algo(tmp_path: Path) -> None:
    reloj = Reloj()
    html = muestra("kpszsu_pagina.html")
    pedidas: list[str] = []

    def pedir(url: str) -> Respuesta:
        pedidas.append(url)
        return Respuesta(200, html)

    s = servicio_de_prueba(tmp_path, reloj, pedir=pedir)
    s.kpszsu_ultimo_id = 82700
    asyncio.run(s.kpszsu_una_vez(repasar=False))
    # La doble devuelve siempre la misma página: lee una anterior, no enlaza y lo anota.
    assert pedidas == [seguimiento.KPSZSU_URL, seguimiento.KPSZSU_URL + "?before=82766"]
    nota = [x for x in lineas_archivo(s.datos, "kpszsu") if x.get("evento") == "ids_sin_enlazar"]
    assert nota == [
        {"recibido": nota[0]["recibido"], "evento": "ids_sin_enlazar", "desde_id": 82701,
         "hasta_id": 82765}
    ]  # fmt: skip


def test_la_marca_de_edicion_cambia_la_huella() -> None:
    html = muestra("kpszsu_pagina.html")
    marcada = html.replace(
        '<span class="tgme_widget_message_meta"><a class="tgme_widget_message_date" '
        'href="https://t.me/kpszsu/82768">',
        '<span class="tgme_widget_message_meta">edited <a class="tgme_widget_message_date" '
        'href="https://t.me/kpszsu/82768">',
    )
    antes = {b.id: b.huella for b in bloques_pagina(html)}
    despues = {b.id: b.huella for b in bloques_pagina(marcada)}
    assert antes[82768] != despues[82768]
    assert antes[82766] == despues[82766]


# --- Estado y vigilancia -----------------------------------------------------------------------
def test_estado_del_seguimiento() -> None:
    ahora = datetime(2026, 10, 4, 12, 30, tzinfo=UTC)
    registro = {
        "ultimo_latido": "2026-10-04T12:25:00.123456Z",
        "ultima_recepcion": "2026-10-04T12:25:00.123456Z",
        "ultimo_hueco_largo": {"desde": "2026-10-04T09:00:00Z", "hasta": "2026-10-04T09:15:00Z",
                               "motivo": "x"},
    }  # fmt: skip
    resultado = estado.estado_seguimiento(registro, ahora)
    assert resultado == {
        "estado": "en_marcha",
        "ultima_recepcion": "2026-10-04T12:25Z",
        "ultimo_latido": "2026-10-04T12:25Z",
        "ultimo_hueco_largo": {"desde": "2026-10-04T09:00Z", "hasta": "2026-10-04T09:15Z"},
    }
    solo_rest = {**registro, "ultimo_latido": "2026-10-04T12:00:00Z"}
    assert estado.estado_seguimiento(solo_rest, ahora)["estado"] == "con_respaldo"
    assert estado.estado_seguimiento(None, ahora)["estado"] == "parado"
    compuesto = estado.componer(
        ahora, ahora, 0, None, None, 17, seguimiento=registro, con_seguimiento=True
    )
    assert compuesto["seguimiento"]["estado"] == "en_marcha"
    assert "seguimiento" not in estado.componer(ahora, ahora, 0, None, None, 17)


def test_el_vigia_avisa_si_para_o_si_hubo_un_hueco_largo() -> None:
    ahora = datetime(2026, 10, 4, 12, 41, tzinfo=UTC)
    base: dict[str, Any] = {
        "fin": "2026-10-04T12:33Z",
        "seguimiento": {"estado": "en_marcha", "ultima_recepcion": "2026-10-04T12:33Z",
                        "ultimo_latido": "2026-10-04T12:33Z", "ultimo_hueco_largo": None},
    }  # fmt: skip
    assert salud.diagnostico_seguimiento(base, ahora)[0] is True
    parado = {**base, "seguimiento": {**base["seguimiento"], "estado": "parado"}}
    assert salud.diagnostico_seguimiento(parado, ahora)[0] is False
    hueco = {"desde": "2026-10-04T11:50Z", "hasta": "2026-10-04T12:05Z"}
    reciente = {**base, "seguimiento": {**base["seguimiento"], "ultimo_hueco_largo": hueco}}
    al_dia, frase = salud.diagnostico_seguimiento(reciente, ahora)
    assert al_dia is False and "11:50" in frase
    antiguo = {"desde": "2026-10-04T08:00Z", "hasta": "2026-10-04T08:15Z"}
    viejo = {**base, "seguimiento": {**base["seguimiento"], "ultimo_hueco_largo": antiguo}}
    assert salud.diagnostico_seguimiento(viejo, ahora)[0] is True
    assert salud.diagnostico_seguimiento({"fin": "x"}, ahora)[0] is True


# --- Archivo: compresión, índice, copia y restauración --------------------------------------------
def preparar_archivo(tmp_path: Path) -> Path:
    reloj = Reloj(datetime(2026, 10, 3, 23, 59, 55, tzinfo=UTC))
    reales = frames()
    guion: list[Conexion | Exception] = [Conexion(list(reales), reloj, ConnectionError("x"))]
    s = servicio_de_prueba(tmp_path, reloj, guion)
    asyncio.run(s.flujo())
    s._guardar_bloques(bloques_pagina(muestra("kpszsu_pagina.html")), seguimiento.KPSZSU_URL)
    s.neptun.cerrar()
    s.kpszsu.cerrar()
    return s.datos


def test_comprime_solo_las_horas_cerradas_sin_cambiar_un_byte(tmp_path: Path) -> None:
    datos = preparar_archivo(tmp_path)
    originales = {p.name: p.read_bytes() for p in datos.rglob("*.jsonl")}
    ahora = datetime(2026, 10, 4, 0, 1, tzinfo=UTC)
    # A las 00:01 la hora de las 23 acaba de cerrar: espera al margen de 2 minutos.
    assert seguimiento_archivo.comprimir_cerrados(datos, ahora) == []
    hechos = seguimiento_archivo.comprimir_cerrados(datos, ahora + timedelta(minutes=2))
    assert [p.name for p in hechos] == [
        "neptun-2026-10-03T23.jsonl.gz",
        "kpszsu-2026-10-04T00.jsonl.gz",
    ] or [p.name for p in hechos] == ["neptun-2026-10-03T23.jsonl.gz"]
    for ruta in hechos:
        assert gzip.decompress(ruta.read_bytes()) == originales[ruta.name[: -len(".gz")]]
    # Las líneas de una hora ya comprimida que lleguen tarde van a otra parte, sin reescribir.
    tarde = datos / "neptun" / "2026" / "10" / "neptun-2026-10-03T23.jsonl"
    tarde.write_text('{"recibido":"x"}\n', encoding="utf-8")
    (otro,) = seguimiento_archivo.comprimir_cerrados(datos, ahora + timedelta(hours=2))[:1]
    assert otro.name == "neptun-2026-10-03T23.parte2.jsonl.gz"


def test_indice_diario(tmp_path: Path) -> None:
    datos = preparar_archivo(tmp_path)
    dia = datetime(2026, 10, 3, tzinfo=UTC).date()
    assert seguimiento_archivo.escribir_indice(datos, dia) is None  # aún sin comprimir
    seguimiento_archivo.comprimir_cerrados(datos, datetime(2026, 10, 5, tzinfo=UTC))
    ruta = seguimiento_archivo.escribir_indice(datos, dia)
    assert ruta is not None
    indice = json.loads(ruta.read_text("utf-8"))
    reales = frames()
    # 5 s de las 23:59:55 caen el 3; lo demás, el 4.
    del_dia_3 = reales[:4]
    esperado: dict[str, int] = {}
    for f in del_dia_3:
        tipo = json.loads(f)["type"]
        esperado[tipo] = esperado.get(tipo, 0) + 1
    assert indice["neptun"]["mensajes_por_tipo"] == dict(sorted(esperado.items()))
    assert indice["bytes"] == sum(f["bytes"] for f in indice["ficheros"])
    assert all(len(f["sha256"]) == 64 for f in indice["ficheros"])
    # Una vez escrito no se rehace.
    assert seguimiento_archivo.escribir_indice(datos, dia) is None
    dia4 = seguimiento_archivo.componer_indice(datos, dia.replace(day=4))
    assert dia4["neptun"]["amenazas_distintas"] > 0
    assert dia4["kpszsu"]["publicaciones_distintas"] == 3


class S3Falso:
    """Doble del bucket privado: HEAD, PUT y GET con la huella en x-amz-meta-sha256."""

    def __init__(self) -> None:
        self.objetos: dict[str, tuple[bytes, str]] = {}
        self.puts = 0

    def __call__(self, peticion: Any) -> seguimiento_archivo.RespuestaS3:
        clave = peticion.full_url.split("/droneobservatory-archivo/", 1)[-1]
        assert "authorization" in {k.lower() for k in peticion.headers}
        metodo = peticion.get_method()
        if metodo == "HEAD":
            if clave in self.objetos:
                return seguimiento_archivo.RespuestaS3(
                    200, {"x-amz-meta-sha256": self.objetos[clave][1]}, b""
                )
            return seguimiento_archivo.RespuestaS3(404, {}, b"")
        if metodo == "PUT":
            self.puts += 1
            cabeceras = {k.lower(): v for k, v in peticion.headers.items()}
            self.objetos[clave] = (peticion.data, cabeceras["x-amz-meta-sha256"])
            return seguimiento_archivo.RespuestaS3(200, {}, b"")
        cuerpo, huella = self.objetos[clave]
        return seguimiento_archivo.RespuestaS3(200, {"x-amz-meta-sha256": huella}, cuerpo)


def test_copia_diaria_sin_sobrescribir_y_restauracion(tmp_path: Path) -> None:
    datos = preparar_archivo(tmp_path)
    s3 = S3Falso()
    copia = seguimiento_archivo.Copia(
        seguimiento_archivo.cargar_destino(), seguimiento_archivo.Credenciales("id", "secreto"), s3
    )
    resultado = seguimiento_archivo.ciclo(datos, datetime(2026, 10, 5, 0, 5, tzinfo=UTC), copia)
    assert set(resultado["copias"]) == {"2026-10-03", "2026-10-04"}
    assert seguimiento_archivo.dia_copiado(datos, datetime(2026, 10, 3, tzinfo=UTC).date())
    puts = s3.puts
    # Otra pasada no sube nada.
    seguimiento_archivo.ciclo(datos, datetime(2026, 10, 5, 1, 5, tzinfo=UTC), copia)
    assert s3.puts == puts
    # Restaurar un fichero: los mismos bytes, con la huella anotada.
    objeto = "seguimiento/neptun/2026/10/neptun-2026-10-03T23.jsonl.gz"
    cuerpo, huella = copia.bajar(objeto)
    local = datos / "neptun" / "2026" / "10" / "neptun-2026-10-03T23.jsonl.gz"
    assert cuerpo == local.read_bytes()
    assert huella == hashlib.sha256(cuerpo).hexdigest()
    # Un objeto con otra huella no se sobrescribe.
    assert copia.subir(objeto, b"otra cosa", "application/gzip") == "distinto"
    assert s3.objetos[objeto][0] == cuerpo


def test_el_archivo_espera_fuera_de_la_hora_de_la_recogida() -> None:
    momentos = iter([
        datetime(2026, 10, 4, 12, 20, tzinfo=UTC),
        datetime(2026, 10, 4, 12, 39, tzinfo=UTC),
        datetime(2026, 10, 4, 12, 40, tzinfo=UTC),
        datetime(2026, 10, 4, 12, 40, 30, tzinfo=UTC),
    ])  # fmt: skip
    en_marcha = iter([True, False])
    esperas: list[float] = []
    seguimiento_archivo.esperar_turno(
        ahora=lambda: next(momentos), en_marcha=lambda: next(en_marcha), dormir=esperas.append
    )
    assert len(esperas) == 3


def test_bloque_de_un_canal_ajeno_no_cuenta() -> None:
    ajeno = muestra("kpszsu_pagina.html").replace('data-post="kpszsu/', 'data-post="otro/')
    assert bloques_pagina(ajeno) == []
    assert isinstance(Bloque(1, "", "", ""), Bloque)


@pytest.mark.parametrize(
    "nombre", ["neptun-2026-10-03T23.jsonl", "kpszsu-2026-10-03T23.parte2.jsonl.gz"]
)
def test_hora_del_nombre(nombre: str) -> None:
    assert seguimiento_archivo.hora_del_fichero(Path(nombre)) == datetime(2026, 10, 3, 23)
