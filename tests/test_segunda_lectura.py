"""Segunda lectura con el servicio secundario de modelos (docs/segunda_lectura.md): el cliente con
su ritmo y sus fallos, lo que cuenta de cada respuesta, la pasada con su base propia, el paso de la
recogida que solo lee sus candidatos y los manda al experto con su tope, y que la capa nunca toca
la base principal ni decide nada por sí sola."""

import copy
import hashlib
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste, secundario
from proceso import control_fichas as reglas
from proceso import segunda_lectura as lectura
from recogida import control_fichas, rectificaciones
from recogida import segunda_lectura as segunda
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_rectificaciones import BASE, EXPERTO, ID, _copenhague, _decision
from tests.test_rectificaciones import Cliente as ClienteModelos

AHORA = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
FRASE_CIERRE = "Lufthavnen er lukket ned, grundet to til tre droner"
FRASE_TARDIA = "Politiet har hverken kunnet bevise eller afvise"
TITULAR = "Danish police find no proof drones caused Københavns Lufthavn shutdown"


# --- El servicio secundario simulado ---------------------------------------------------------


def _ok(
    datos: Any, razonamiento: str = 'pienso {"campos": "nada"}'
) -> tuple[int, dict[str, str], bytes]:
    cuerpo = {"choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(datos, ensure_ascii=False),
        "reasoning": razonamiento}}]}  # fmt: skip
    return 200, {}, json.dumps(cuerpo).encode("utf-8")


def _texto(contenido: str) -> tuple[int, dict[str, str], bytes]:
    cuerpo = {"choices": [{"finish_reason": "stop", "message": {"content": contenido}}]}
    return 200, {}, json.dumps(cuerpo).encode("utf-8")


class Servicio:
    """El transporte del servicio secundario: da las respuestas en orden y apunta lo pedido."""

    def __init__(self, respuestas: list[Any]) -> None:
        self.respuestas = list(respuestas)
        self.pedidas: list[dict[str, Any]] = []

    def __call__(self, metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None,
                 limite_s: float) -> tuple[int, dict[str, str], bytes]:  # fmt: skip
        self.pedidas.append(json.loads(cuerpo) if cuerpo else {"url": url})
        respuesta = self.respuestas.pop(0) if self.respuestas else OSError("sin red")
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta  # type: ignore[no-any-return]


def _cliente(servicio: Servicio, dormidas: list[float] | None = None) -> secundario.Cliente:
    config = secundario.Configuracion("https://secundario.example/v1", "clave-secreta", "modelo-x")
    apunte = dormidas if dormidas is not None else []
    return secundario.Cliente(config, secundario.Ritmo(), servicio, apunte.append, lambda: 0.0)


def _lectura(**cambios: tuple[str, str]) -> dict[str, Any]:
    campos = {c: {"valor": "apoyado", "frase": ""} for c in lectura.CAMPOS}
    for campo, (valor, frase) in cambios.items():
        if campo != "varios_sucesos":
            campos[campo] = {"valor": valor, "frase": frase}
    varios = cambios.get("varios_sucesos")
    return {"campos": campos, "varios_sucesos": {"valor": bool(varios), "frase": varios[1]
                                                 if varios else ""}}  # fmt: skip


# --- Bases ---------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def entorno(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("EODI_MODELO_BASE", BASE)
    monkeypatch.setenv("EODI_MODELO_EXPERTO", EXPERTO)
    monkeypatch.setenv("EODI_SECUNDARIO_URL", "https://secundario.example/v1")
    monkeypatch.setenv("EODI_SECUNDARIO_CLAVE", "clave-secreta")
    monkeypatch.setenv("EODI_SECUNDARIO_MODELO", "modelo-x")
    datos = tmp_path / "capa"
    monkeypatch.setenv(segunda.VARIABLE_DATOS, str(datos))
    monkeypatch.setattr(rectificaciones, "cargar", lambda: {"rectificaciones": []})
    # Las páginas de las noticias no se descargan en las pruebas.
    monkeypatch.setattr(control_fichas, "paginas_de", lambda enlaces, plazo: {})
    return datos


def _principal(tmp_path: Path, con_tardia: bool = True) -> Path:
    ruta = tmp_path / "eodi.sqlite"
    almacen = Almacen.abrir(ruta)
    d = _copenhague()
    if not con_tardia:
        d["fuentes"] = [f for f in d["fuentes"] if f["id"] != "N2"]
    almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    almacen.cerrar()
    return ruta


def _pasada(ruta: Path, datos: Path, servicio: Servicio, **opciones: Any) -> segunda.Resumen:
    principal = segunda.abrir_principal(ruta)
    propia = segunda.Propia.abrir(datos / segunda.BASE)
    try:
        return segunda.pasada(principal, propia, _cliente(servicio), AHORA, float("inf"),
                              lambda: 0.0, **opciones)  # fmt: skip
    finally:
        principal.cerrar()
        propia.cerrar()


def _candidatos(datos: Path) -> list[dict[str, Any]]:
    return segunda.leer_candidatos(datos / segunda.BASE, 5.0)


SOLO_LECTURA = frozenset({"lectura"})


# --- El cliente ----------------------------------------------------------------------------


def test_respuesta_valida_sin_el_razonamiento() -> None:
    servicio = Servicio([_ok({"titulares": [1]})])
    cliente = _cliente(servicio)
    datos = cliente.json("inst", "texto", "r", lectura.ESQUEMA_RECTIFICACION, 100)
    assert datos == {"titulares": [1]}
    pedida = servicio.pedidas[0]
    assert pedida["response_format"]["type"] == "json_schema"
    assert pedida["model"] == "modelo-x" and pedida["temperature"] == 0


def test_json_object_si_no_admite_el_esquema() -> None:
    servicio = Servicio([(400, {}, b'{"error": "response_format json_schema not supported"}'),
                         _ok({"titulares": []})])  # fmt: skip
    cliente = _cliente(servicio)
    assert cliente.json("inst", "t", "r", lectura.ESQUEMA_RECTIFICACION, 100) == {"titulares": []}
    assert servicio.pedidas[1]["response_format"] == {"type": "json_object"}
    assert cliente.formato == "json_object"


def test_429_espera_exponencial_y_reintenta() -> None:
    servicio = Servicio([(429, {"Retry-After": "2"}, b"lento"), (503, {}, b"caido"),
                         _ok({"titulares": [2]})])  # fmt: skip
    dormidas: list[float] = []
    cliente = _cliente(servicio, dormidas)
    assert cliente.json("i", "t", "r", lectura.ESQUEMA_RECTIFICACION, 100) == {"titulares": [2]}
    esperas = [d for d in dormidas if d != 7.5]  # las demás son el ritmo de 8 por minuto
    assert esperas == [5.0, 10.0]


def test_caida_total_sin_la_clave_en_el_error() -> None:
    servicio = Servicio([(500, {}, b"error con clave-secreta dentro")] * 4)
    with pytest.raises(secundario.ServicioCaido) as error:
        _cliente(servicio).json("i", "t", "r", lectura.ESQUEMA_RECTIFICACION, 100)
    assert "clave-secreta" not in str(error.value) and len(servicio.pedidas) == 4


def test_sin_variables_no_hay_servicio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EODI_SECUNDARIO_URL")
    assert secundario.configuracion() is None


# --- Lo que cuenta de una respuesta --------------------------------------------------------


def test_frase_inventada_no_cuenta() -> None:
    citas = [lectura.Cita("tv2.dk", "2025-09-22", "da", FRASE_CIERRE)]
    datos = lectura.ficha(_copenhague())
    respuesta = _lectura(drones=("contradicho", "Der var fem droner over lufthavnen"),
                         presencia=("contradicho", "grundet to til tre droner"))  # fmt: skip
    hallados = lectura.hallazgos(respuesta, datos, citas)
    assert [(h.campo, h.valoracion) for h in hallados] == [("presencia", "contradicho")]


def test_sin_apoyo_solo_en_los_datos_clave() -> None:
    citas = [lectura.Cita("tv2.dk", "2025-09-22", "da", FRASE_CIERRE)]
    datos = lectura.ficha(_copenhague())
    respuesta = _lectura(lugar=("sin_apoyo", ""), tipo=("sin_apoyo", ""),
                         inicio=("sin_apoyo", "frase que no está"))  # fmt: skip
    assert [h.campo for h in lectura.hallazgos(respuesta, datos, citas)] == ["lugar"]
    # La fecha aproximada es la de la publicación: ninguna cita la escribe.
    datos["inicio"] = "2025-09-22T00:00Z (aproximada)"
    respuesta = _lectura(inicio=("sin_apoyo", ""))
    assert lectura.hallazgos(respuesta, datos, citas) == []


def test_orden_de_lectura() -> None:
    fichas = {"EODI-2025-00001": "a", "EODI-2025-00002": "b", "EODI-2025-00003": "c",
              "EODI-2025-00004": "d"}  # fmt: skip
    lecturas = {"EODI-2025-00001": ("a", "2026-10-10"), "EODI-2025-00002": ("x", "2026-10-12"),
                "EODI-2025-00003": ("c", "2026-10-01")}  # fmt: skip
    assert lectura.orden_lectura(fichas, lecturas) == [
        "EODI-2025-00004", "EODI-2025-00002", "EODI-2025-00003", "EODI-2025-00001"]  # fmt: skip


def test_ventana_de_cada_pasada() -> None:
    assert segunda.fin_de_pasada(datetime(2026, 10, 15, 10, 45, 3, tzinfo=UTC)) == datetime(
        2026, 10, 15, 11, 10, tzinfo=UTC)  # fmt: skip
    assert segunda.fin_de_pasada(datetime(2026, 10, 15, 23, 50, tzinfo=UTC)) == datetime(
        2026, 10, 16, 0, 10, tzinfo=UTC)  # fmt: skip
    assert segunda.fin_de_pasada(datetime(2026, 10, 15, 11, 5, tzinfo=UTC)) == datetime(
        2026, 10, 15, 11, 10, tzinfo=UTC)  # fmt: skip
    # Entre el minuto 10 y el 45 corre la recogida: no se lanza.
    assert segunda.fin_de_pasada(datetime(2026, 10, 15, 11, 17, tzinfo=UTC)) is None


def test_pares_con_margenes_amplios() -> None:
    a = _copenhague()
    a["tipo"] = "sobrevuelo"
    a["consecuencias"] = {"cierre": {"valor": "no"}}
    b = copy.deepcopy(a)
    b["id"] = "EODI-2025-00160"
    b["tiempo"] = {"inicio": ejemplos.instante("2025-09-24T20:00Z", "hora")}
    # A 48 horas: el control no los compara (el mismo día o la misma noche); la segunda lectura sí.
    assert not reglas.candidatos(a, b)
    assert len(lectura.pares_amplios([a, b], 72, 30, set())) == 1
    assert lectura.pares_amplios([a, b], 72, 30, {f"par:{ID}|EODI-2025-00160"}) == []
    b["relacionados"] = [{"id": ID}]
    assert lectura.pares_amplios([a, b], 72, 30, set()) == []
    # Dos cierres del mismo sitio en noches distintas son dos sucesos (regla del control).
    b.pop("relacionados")
    a["consecuencias"] = b["consecuencias"] = {"cierre": {"valor": "si"}}
    a["tipo"] = b["tipo"] = "interrupcion_aeroportuaria"
    assert lectura.pares_amplios([a, b], 72, 30, set()) == []


# --- La pasada -----------------------------------------------------------------------------


def test_pasada_marca_lo_contradicho(tmp_path: Path, entorno: Path) -> None:
    ruta = _principal(tmp_path)
    servicio = Servicio([_ok(_lectura(presencia=("contradicho", FRASE_TARDIA)))])
    resumen = _pasada(ruta, entorno, servicio, tareas=SOLO_LECTURA)
    assert resumen.leidas == 1 and resumen.con_hallazgos == [ID]
    [candidato] = _candidatos(entorno)
    assert candidato["tipo"] == "campos" and candidato["incidente"] == ID
    assert candidato["datos"]["hallazgos"][0]["frase"] == FRASE_TARDIA
    # Lo que se manda: los datos clave y las citas en su idioma; nada interno.
    enviado = servicio.pedidas[0]["messages"][1]["content"]
    assert FRASE_CIERRE in enviado and "presencia: confirmada" in enviado
    # Sin cambios, la ficha no se vuelve a leer antes que otra nunca leída; y su candidato sigue.
    servicio = Servicio([_ok(_lectura())])
    _pasada(ruta, entorno, servicio, tareas=SOLO_LECTURA)
    assert _candidatos(entorno) == []  # releída sin hallazgos: el anterior ya no vale


def test_json_invalido_se_descarta(tmp_path: Path, entorno: Path) -> None:
    ruta = _principal(tmp_path)
    resumen = _pasada(ruta, entorno, Servicio([_texto("esto no es JSON")]), tareas=SOLO_LECTURA)
    assert resumen.invalidas == 1 and resumen.leidas == 0 and resumen.parada is None
    resumen = _pasada(ruta, entorno, Servicio([_ok({"campos": {}})]), tareas=SOLO_LECTURA)
    assert resumen.invalidas == 1 and _candidatos(entorno) == []


def test_frase_inventada_no_marca_nada(tmp_path: Path, entorno: Path) -> None:
    ruta = _principal(tmp_path)
    servicio = Servicio([_ok(_lectura(drones=("contradicho", "Der var fem droner")))])
    resumen = _pasada(ruta, entorno, servicio, tareas=SOLO_LECTURA)
    assert resumen.leidas == 1 and _candidatos(entorno) == []


def test_caida_total_la_pasada_termina_sin_fallar(
    tmp_path: Path, entorno: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _principal(tmp_path)
    for n in range(5):
        almacen = Almacen.abrir(ruta)
        d = _copenhague()
        d["id"] = f"EODI-2025-{n + 300:05d}"
        almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
        almacen.cerrar()
    servicio = Servicio([])  # cada petición, un corte de conexión
    resumen = _pasada(ruta, entorno, servicio, tareas=SOLO_LECTURA)
    assert resumen.parada == "3 fallos seguidos del servicio" and resumen.fallos == 3
    assert len(servicio.pedidas) == 3 * (secundario.Ritmo().reintentos + 1)
    # La orden entera, contra una dirección que no responde: código 0, sin avisos.
    monkeypatch.setenv("EODI_SECUNDARIO_URL", "http://127.0.0.1:9/v1")
    config = {**segunda.configuracion(), "ritmo": {**segunda.configuracion()["ritmo"],
              "reintentos": 0, "por_minuto": 6000, "limite_s": 2}}  # fmt: skip
    monkeypatch.setattr(segunda, "configuracion", lambda: config)
    avisos: list[Any] = []
    monkeypatch.setattr("recogida.avisos.enviar", lambda *a, **k: avisos.append(a), raising=False)
    codigo = segunda.principal(["pasada", "--manual", "--base", str(ruta), "--datos",
                                str(entorno), "--solo", "lectura"])  # fmt: skip
    assert codigo == 0 and avisos == []
    estado = json.loads((entorno / segunda.ESTADO).read_text(encoding="utf-8"))
    assert estado["ultima_pasada"]["parada"] == "3 fallos seguidos del servicio"


def test_desactivada_sin_url(
    tmp_path: Path, entorno: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EODI_SECUNDARIO_URL")
    monkeypatch.setattr(secundario, "RUTA_LOCAL", tmp_path / "no-existe.env")
    ruta = _principal(tmp_path)
    assert segunda.principal(["pasada", "--manual", "--base", str(ruta)]) == 0
    assert not (entorno / segunda.BASE).exists()
    almacen = Almacen.abrir(ruta)
    assert segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS) == {"activa": False}
    almacen.cerrar()


def test_la_capa_nunca_toca_la_base_principal(tmp_path: Path, entorno: Path) -> None:
    ruta = _principal(tmp_path)
    antes = hashlib.sha256(ruta.read_bytes()).hexdigest()
    servicio = Servicio([_ok(_lectura(presencia=("contradicho", FRASE_TARDIA))),
                         _ok({"titulares": []})])  # fmt: skip
    _pasada(ruta, entorno, servicio, forzar_diaria=True)
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == antes
    principal = segunda.abrir_principal(ruta)
    with pytest.raises(sqlite3.OperationalError):
        principal.guardar_cursor("x", {"y": 1})
    principal.cerrar()


# --- El paso de la recogida ----------------------------------------------------------------


def _marcar(datos: Path, ruta: Path) -> None:
    _pasada(ruta, datos, Servicio([_ok(_lectura(presencia=("contradicho", FRASE_TARDIA)))]),
            tareas=SOLO_LECTURA)  # fmt: skip


VERIFICACION = {
    "presencia": {"valor": "confirmada", "fuente": 1, "frase": FRASE_CIERRE},
    "drones": {"valor": "", "fuente": 0, "frase": ""},
    "cierre": {"valor": "si", "fuente": 1, "frase": "Lufthavnen er lukket ned"},
    "duracion_min": {"valor": "", "fuente": 0, "frase": ""},
    "dia": {"valor": "", "fuente": 0, "frase": ""}, "hora": {"valor": "", "fuente": 0, "frase": ""},
    "lugar": {"nombre": "", "nivel": "sin_dato", "fuente": 0, "frase": ""},
}  # fmt: skip


@pytest.fixture
def recogida(tmp_path: Path, entorno: Path) -> Iterator[tuple[Almacen, ClienteModelos]]:
    ruta = _principal(tmp_path)
    _marcar(entorno, ruta)
    almacen = Almacen.abrir(ruta)
    cliente = ClienteModelos([VERIFICACION])
    yield almacen, cliente
    almacen.cerrar()


def test_el_experto_verifica_lo_marcado_una_sola_vez(
    recogida: tuple[Almacen, ClienteModelos], monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen, cliente = recogida
    monkeypatch.setattr(control_fichas, "_fabrica", lambda: lambda: cliente)
    hecho = segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert len(hecho["decididos"]) == 1 and hecho["esperan"] == 0
    # Solo el experto, nunca el base; con la petición de verificación del control.
    assert cliente.pedidas_base == [] and len(cliente.pedidas) == 1
    assert "presencia" in json.dumps(cliente.pedidas[0]["output_config"])
    verificacion = almacen.controles(f"verificacion:{ID}")[f"verificacion:{ID}"]
    assert verificacion["modelo"] == EXPERTO and "presencia" in verificacion["datos"]
    assert verificacion["escalado"][0].startswith("segunda lectura")
    assert almacen.gastado_experto_en(coste.Modo.SEGUNDA_LECTURA.value, "2026-10-15") > 0
    # La decisión queda guardada: la recogida siguiente no la repite.
    segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert len(cliente.pedidas) == 1


def test_con_el_tope_agotado_los_candidatos_esperan(
    recogida: tuple[Almacen, ClienteModelos], monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen, cliente = recogida
    monkeypatch.setattr(control_fichas, "_fabrica", lambda: lambda: cliente)
    almacen.registrar_llamada({
        "fecha": "2026-10-15T03:00:00Z", "modo": coste.Modo.SEGUNDA_LECTURA.value,
        "candidato": "x", "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0,
        "lectura_cache": 0, "coste": coste.LIMITE_SEGUNDA_EXPERTO_DIARIO_USD, "modelo": EXPERTO,
        "escalada": True,
    })  # fmt: skip
    hecho = segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert cliente.pedidas == [] and hecho["decididos"] == [] and hecho["esperan"] == 1
    assert almacen.controles(segunda.PREFIJO) == {}
    # El experto con su tope normal ya gastado en otras cosas: tampoco (nunca la reserva).
    otro = Almacen.abrir()
    otro.guardar_incidente(_copenhague(), AHORA, VOCABULARIO_MODELOS)
    otro.registrar_llamada({
        "fecha": "2026-10-15T03:00:00Z", "modo": coste.Modo.HORARIO.value, "candidato": "y",
        "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_EXPERTO_DIARIO_USD, "modelo": EXPERTO, "escalada": True,
    })  # fmt: skip
    hecho = segunda.paso_horario(otro, AHORA, VOCABULARIO_MODELOS)
    assert cliente.pedidas == [] and hecho["decididos"] == [] and "tope" in hecho["experto"]
    # Al día siguiente, ya de madrugada (el margen de los escalados es fijo, no un reparto por
    # horas que deje la mañana sin experto), el candidato pasa.
    hecho = segunda.paso_horario(almacen, datetime(2026, 10, 16, 1, 17, tzinfo=UTC),
                                 VOCABULARIO_MODELOS)  # fmt: skip
    assert len(cliente.pedidas) == 1 and len(hecho["decididos"]) == 1


def test_base_de_la_capa_ausente_rota_o_bloqueada(tmp_path: Path, entorno: Path) -> None:
    almacen = Almacen.abrir(_principal(tmp_path))
    antes = almacen.incidente(ID)
    hecho = segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hecho["candidatos"] == 0 and "error" not in hecho
    entorno.mkdir(parents=True, exist_ok=True)
    (entorno / segunda.BASE).write_bytes(b"esto no es una base" * 100)
    hecho = segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hecho["candidatos"] == 0
    (entorno / segunda.BASE).rename(entorno / "rota.sqlite")
    propia = segunda.Propia.abrir(entorno / segunda.BASE)
    propia.marcar("campos:x:y", "campos", ID, None, "2026-10-15T11:00:00Z", {"hallazgos": []})
    propia.conexion.execute("BEGIN EXCLUSIVE")
    assert segunda.leer_candidatos(entorno / segunda.BASE, 0.3) == []
    propia.conexion.rollback()
    propia.cerrar()
    assert almacen.incidente(ID) == antes
    # Y si algo falla por dentro, no sale nada del paso ni del estado.
    assert "error" in segunda.paso_horario(None, AHORA, VOCABULARIO_MODELOS)  # type: ignore[arg-type]
    assert "error" in segunda.estado_para_control(None, AHORA, None)  # type: ignore[arg-type]
    almacen.cerrar()


def test_el_estado_interno_lleva_la_capa(tmp_path: Path, entorno: Path) -> None:
    ruta = _principal(tmp_path)
    _marcar(entorno, ruta)
    segunda.escribir_estado(entorno, {"leidas": 1}, segunda.Propia.abrir(entorno / segunda.BASE))
    almacen = Almacen.abrir(ruta)
    destino = tmp_path / "control.json"
    estado = segunda.estado_para_control(almacen, AHORA, {"candidatos": 1})
    control_fichas.escribir_estado(destino, None, almacen, AHORA, estado)
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["segunda_lectura"]["candidatos_vigentes"] == 1
    assert datos["segunda_lectura"]["limite_experto"] == coste.LIMITE_SEGUNDA_EXPERTO_DIARIO_USD
    almacen.cerrar()


# --- Rectificaciones diarias ---------------------------------------------------------------


def test_rectificaciones_diarias_a_la_cola_del_mensual(tmp_path: Path, entorno: Path) -> None:
    ruta = _principal(tmp_path, con_tardia=False)
    almacen = Almacen.abrir(ruta)
    for url, texto in [
        ("https://reuters.example/no-proof", TITULAR),
        ("https://otro.example/x", "Drones over Københavns Lufthavn again"),
    ]:
        almacen.guardar_articulo({"url": url, "medio": url.split("/")[2],
                                  "fecha": "2026-06-25T12:00Z", "idioma": "en", "titular": texto,
                                  "titular_normalizado": texto.lower()})  # fmt: skip
    almacen.guardar_cursor(rectificaciones.CURSOR_MENSUAL, {"mes": "2026-10", "pendientes": []})
    almacen.cerrar()
    servicio = Servicio([_ok({"titulares": [1, 7]})])
    resumen = _pasada(ruta, entorno, servicio, tareas=frozenset({"rectificaciones"}),
                      forzar_diaria=True)  # fmt: skip
    assert resumen.rectificaciones["elegidos"] == 1
    assert "Drones over" not in json.dumps(servicio.pedidas[0], ensure_ascii=False)
    # Una vez al día: la pasada siguiente no vuelve a preguntar.
    servicio = Servicio([])
    _pasada(ruta, entorno, servicio, tareas=frozenset({"rectificaciones"}))
    assert servicio.pedidas == []
    # La recogida lo pone en la cola del barrido mensual; el experto lo decide con sus reglas.
    almacen = Almacen.abrir(ruta)
    hecho = segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hecho["rectificaciones_encoladas"] == 1
    cola = (almacen.cursor(rectificaciones.CURSOR_MENSUAL) or {})["pendientes"]
    assert [p["origen"] for p in cola] == ["segunda_lectura"]
    segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert len((almacen.cursor(rectificaciones.CURSOR_MENSUAL) or {})["pendientes"]) == 1
    cliente = ClienteModelos([_decision(frase="find no proof drones caused")])
    rectificaciones.ejecutar(almacen, AHORA, VOCABULARIO_MODELOS, lambda: cliente)
    d = almacen.incidente(ID)
    assert d is not None and d["presencia_dron"] == "no_acreditada"
    assert almacen.gastado_experto_en(coste.Modo.SEGUNDA_LECTURA.value, "2026-10-15") > 0
    assert almacen.gastado_experto_en(coste.Modo.RECTIFICACIONES.value, "2026-10-15") == 0
    almacen.cerrar()


def test_rectificacion_con_el_tope_de_la_capa_agotado_espera(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    d = _copenhague()
    d["fuentes"] = [f for f in d["fuentes"] if f["id"] != "N2"]
    almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    almacen.guardar_cursor(rectificaciones.CURSOR_MENSUAL, {"mes": "2026-10", "pendientes": []})
    rectificaciones.encolar(almacen, [{"incidente": ID, "url": "https://r.example/a",
                                       "medio": "r.example", "fecha": "2026-06-25T12:00Z",
                                       "idioma": "en", "titular": TITULAR}])  # fmt: skip
    almacen.registrar_llamada({
        "fecha": "2026-10-15T03:00:00Z", "modo": coste.Modo.SEGUNDA_LECTURA.value,
        "candidato": "x", "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0,
        "lectura_cache": 0, "coste": coste.LIMITE_SEGUNDA_EXPERTO_DIARIO_USD, "modelo": EXPERTO,
        "escalada": True,
    })  # fmt: skip
    cliente = ClienteModelos([_decision(frase="find no proof drones caused")])
    hechos = rectificaciones.ejecutar(almacen, AHORA, VOCABULARIO_MODELOS, lambda: cliente)
    assert cliente.pedidas == [] and len(hechos.esperan) == 1
    assert (almacen.incidente(ID) or {})["presencia_dron"] == "confirmada"
    almacen.cerrar()


def test_margen_para_los_escalados_del_resto_del_dia() -> None:
    """La segunda lectura solo gasta del experto lo que deja libre el margen fijo de los escalados
    (sin reparto por horas que deje la mañana sin experto)."""
    margen = coste.MARGEN_ESCALADOS_USD
    libre = coste.LIMITE_EXPERTO_DIARIO_USD - margen
    assert coste.margen_escalados(datetime(2026, 10, 19, 0, 0, tzinfo=UTC)) == margen
    assert coste.margen_escalados(datetime(2026, 10, 19, 12, 0, tzinfo=UTC)) == margen
    # Al final del día, solo lo que corresponde a lo que queda de él.
    assert coste.margen_escalados(datetime(2026, 10, 19, 23, 0, tzinfo=UTC)) < margen
    for momento in (datetime(2026, 10, 19, 0, 30, tzinfo=UTC),
                    datetime(2026, 10, 19, 12, 0, tzinfo=UTC)):  # fmt: skip
        coste.comprobar_segunda(libre - 0.06, 0.0, 0.05, momento)
        with pytest.raises(coste.LimiteGasto, match="escalados"):
            coste.comprobar_segunda(libre - 0.04, 0.0, 0.05, momento)
    # Su modo, como mucho 0,10 USD al día.
    with pytest.raises(coste.LimiteGasto, match="segunda_lectura"):
        coste.comprobar_segunda(0.0, 0.08, 0.05, datetime(2026, 10, 19, 12, 0, tzinfo=UTC))


def test_fecha_sin_apoyo_sola_no_va_al_experto() -> None:
    def candidato(*hallazgos: tuple[str, str]) -> dict[str, Any]:
        return {"tipo": "campos", "datos": {"hallazgos": [
            {"campo": c, "valoracion": v, "frase": "", "valor": "x"} for c, v in hallazgos
        ]}}  # fmt: skip

    assert not lectura.al_experto(candidato(("inicio", lectura.SIN_APOYO)))
    assert lectura.al_experto(candidato(("inicio", lectura.CONTRADICHO)))
    assert lectura.al_experto(
        candidato(("inicio", lectura.SIN_APOYO), ("lugar", lectura.SIN_APOYO))
    )
    assert lectura.al_experto({"tipo": "duplicado", "datos": {}})
    assert "fecha" in lectura.motivo_sin_experto(candidato(("inicio", lectura.SIN_APOYO)))


def test_lo_que_no_vale_para_el_experto_se_descarta_con_su_motivo(
    tmp_path: Path, entorno: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    almacen = Almacen.abrir(_principal(tmp_path))
    cliente = ClienteModelos([])
    monkeypatch.setattr(control_fichas, "_fabrica", lambda: lambda: cliente)
    entorno.mkdir(parents=True, exist_ok=True)
    propia = segunda.Propia.abrir(entorno / segunda.BASE)
    solo_fecha = {"hallazgos": [{"campo": "inicio", "valoracion": lectura.SIN_APOYO,
                                 "frase": "", "valor": "2026-09-22"}]}  # fmt: skip
    propia.marcar("campos:x:y", "campos", ID, None, "2026-10-15T11:00:00Z", solo_fecha)
    propia.cerrar()
    hecho = segunda.paso_horario(almacen, AHORA, VOCABULARIO_MODELOS)
    assert hecho["descartados"] == 1 and hecho["esperan"] == 0 and cliente.pedidas == []
    decision = almacen.controles(segunda.PREFIJO)[segunda.PREFIJO + "campos:x:y"]
    assert decision["resultado"] == "descartado" and "fecha" in decision["motivo"]
    almacen.cerrar()
