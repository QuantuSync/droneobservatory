"""El aviso solo sale cuando la web ya sirve la ficha (recogida/avisos.py), contra un servidor web
simulado de verdad: la ficha no está y luego aparece, no aparece nunca, la comprobación falla por
red, redirección y página sin la ficha. En ningún caso se envía antes, y nunca dos veces."""

import json
import threading
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from recogida import avisos, vigilancia, visitas

AHORA = datetime(2026, 11, 1, 19, 35, tzinfo=UTC)
ID = "EODI-2026-00736"


class Web:
    """Un sitio que contesta por identificador lo que diga `respuestas`."""

    def __init__(self) -> None:
        self.respuestas: dict[str, tuple[int, bytes, dict[str, str]]] = {}
        self.peticiones: list[str] = []
        web = self

        class Manejador(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                id_ = self.path.strip("/")
                web.peticiones.append(id_)
                codigo, cuerpo, cabeceras = web.respuestas.get(id_, (404, b"no existe", {}))
                self.send_response(codigo)
                for nombre, valor in cabeceras.items():
                    self.send_header(nombre, valor)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *argumentos: Any) -> None:
                pass

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.sitio = f"http://127.0.0.1:{self.servidor.server_address[1]}"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def publicar(self, id_: str = ID) -> None:
        self.respuestas[id_] = (200, f"<html>{id_}</html>".encode(), {})


@pytest.fixture
def web() -> Iterator[Web]:
    sitio = Web()
    yield sitio
    sitio.servidor.shutdown()
    sitio.servidor.server_close()


class Reloj:
    """Tiempo simulado: `dormir` lo adelanta y puede publicar la ficha a media espera."""

    def __init__(self, antes: Any = None) -> None:
        self.t = 0.0
        self.antes = antes

    def __call__(self) -> float:
        return self.t

    def dormir(self, segundos: float) -> None:
        self.t += segundos
        if self.antes is not None:
            self.antes(self.t)


def incidente(id_: str = ID, **cambios: Any) -> dict[str, Any]:
    base = {
        "id": id_,
        "lugar": {"pais": "RO", "nivel": "pais"},
        "estado": {"actual": "confirmado"},
        "tiempo": {"inicio": {"valor": "2026-11-01T17:00Z", "precision": "hora"}},
        "fuentes": [],
        "tipo": "incursion",
    }
    return {**base, **cambios}


@pytest.fixture
def enviados(tmp_path: Path) -> Iterator[avisos.Enviados]:
    base = avisos.Enviados(tmp_path / "avisos.sqlite")
    base.activar([], AHORA - timedelta(days=1))
    yield base
    base.cerrar()


def pasar(
    enviados: avisos.Enviados,
    web: Web,
    salidos: list[dict[str, Any]],
    reloj: Reloj,
    tope_s: float = 900,
    ahora: datetime = AHORA,
    documento: dict[str, Any] | None = None,
) -> avisos.Pasada:
    doc = documento or incidente()
    return avisos.pasar(
        {doc["id"]},
        {doc["id"]: doc},
        enviados,
        avisos.configuracion(),
        ahora,
        salidos.append,
        None,
        avisos.Espera(avisos.comprobador(web.sitio), tope_s, 60, reloj.dormir, reloj),
        ahora - timedelta(seconds=20),
    )


def test_la_ficha_no_esta_y_luego_aparece(web: Web, enviados: avisos.Enviados) -> None:
    salidos: list[dict[str, Any]] = []

    def aparece(segundos: float) -> None:
        # Hasta el minuto 6 la web no la sirve: y hasta entonces no ha salido nada.
        if segundos == 360:
            assert salidos == []
            web.publicar()

    reloj = Reloj(aparece)
    pasada = pasar(enviados, web, salidos, reloj)
    assert reloj.t == 360
    assert len(salidos) == 2  # el canal de Europa y el del país
    assert pasada.enviados == 2
    assert pasada.pendientes == {}
    assert enviados.pendientes() == {}


def test_no_aparece_nunca_queda_pendiente_con_su_hora_y_sin_enviar(
    web: Web, enviados: avisos.Enviados
) -> None:
    salidos: list[dict[str, Any]] = []
    reloj = Reloj()
    pasada = pasar(enviados, web, salidos, reloj)
    assert salidos == []
    assert reloj.t == 900
    assert web.peticiones.count(ID) == 16
    assert pasada.pendientes == {ID: "2026-11-01T19:34:40Z"}


def test_lo_pendiente_sale_en_la_recogida_siguiente_una_sola_vez(
    web: Web, enviados: avisos.Enviados
) -> None:
    salidos: list[dict[str, Any]] = []
    pasar(enviados, web, salidos, Reloj())
    web.publicar()
    despues = AHORA + timedelta(hours=1)
    pasada = pasar(enviados, web, salidos, Reloj(), ahora=despues)
    assert pasada.enviados == 2
    # Otra recogida: ni otra vez, ni al otro tema.
    pasar(enviados, web, salidos, Reloj(), ahora=despues + timedelta(hours=1))
    assert len(salidos) == 2
    assert len({s["topic"] for s in salidos}) == 2


def test_la_ventana_de_72_horas_se_mide_desde_la_hora_original(
    web: Web, enviados: avisos.Enviados
) -> None:
    """Pendiente a falta de una hora para cumplir las 72 del suceso: al reintentar, pasadas las
    72, se sigue avisando; sin pendiente, ya no."""
    salidos: list[dict[str, Any]] = []
    inicio = (AHORA - timedelta(hours=71)).strftime("%Y-%m-%dT%H:%MZ")
    documento = incidente(tiempo={"inicio": {"valor": inicio, "precision": "hora"}})
    pasar(enviados, web, salidos, Reloj(), documento=documento)
    web.publicar()
    pasar(enviados, web, salidos, Reloj(), ahora=AHORA + timedelta(hours=2), documento=documento)
    assert len(salidos) == 2

    tardio = incidente("EODI-2026-00737", tiempo=documento["tiempo"])
    web.publicar("EODI-2026-00737")
    pasada = pasar(
        enviados, web, salidos, Reloj(), ahora=AHORA + timedelta(hours=2), documento=tardio
    )
    assert pasada.enviados == 0


def test_la_comprobacion_falla_por_red(enviados: avisos.Enviados) -> None:
    salidos: list[dict[str, Any]] = []
    # Un puerto cerrado: conexión rechazada.
    documento = incidente()
    reloj = Reloj()
    pasada = avisos.pasar(
        {ID},
        {ID: documento},
        enviados,
        avisos.configuracion(),
        AHORA,
        salidos.append,
        None,
        avisos.Espera(avisos.comprobador("http://127.0.0.1:9"), 120, 60, reloj.dormir, reloj),
    )
    assert salidos == []
    assert ID in pasada.pendientes


@pytest.mark.parametrize(
    "respuesta",
    [
        (308, b"", {"Location": "/EODI-2026-00001"}),
        (500, ID.encode(), {}),
        (200, b"<html>otra pagina</html>", {}),
        (404, ID.encode(), {}),
    ],
)
def test_nada_que_no_sea_la_ficha_vale(
    respuesta: tuple[int, bytes, dict[str, str]], web: Web
) -> None:
    web.respuestas[ID] = respuesta
    web.respuestas["EODI-2026-00001"] = (200, ID.encode(), {})
    assert avisos.comprobador(web.sitio)(ID) is False


def test_si_ntfy_falla_con_la_ficha_servida_no_se_repite_lo_salido(
    web: Web, enviados: avisos.Enviados
) -> None:
    web.publicar()
    salidos: list[dict[str, Any]] = []

    def falla_el_pais(cuerpo: dict[str, Any]) -> None:
        if cuerpo["topic"] != avisos.configuracion()["general"]["tema"]:
            raise OSError("ntfy caído")
        salidos.append(cuerpo)

    documento = incidente()
    avisos.pasar(
        {ID}, {ID: documento}, enviados, avisos.configuracion(), AHORA, falla_el_pais, None,
        avisos.Espera(avisos.comprobador(web.sitio)),
    )  # fmt: skip
    assert len(salidos) == 1
    assert ID in enviados.pendientes()
    pasar(enviados, web, salidos, Reloj(), ahora=AHORA + timedelta(hours=1))
    assert len(salidos) == 2
    assert len({s["topic"] for s in salidos}) == 2
    assert enviados.pendientes() == {}


def test_lo_pendiente_que_se_retira_deja_de_esperar(web: Web, enviados: avisos.Enviados) -> None:
    salidos: list[dict[str, Any]] = []
    pasar(enviados, web, salidos, Reloj())
    retirado = incidente(retirado={"motivo": "x"})
    pasar(enviados, web, salidos, Reloj(), documento=retirado)
    assert enviados.pendientes() == {}
    assert salidos == []


def test_lo_que_tarda_la_web_queda_medido_una_vez(
    tmp_path: Path, web: Web, enviados: avisos.Enviados
) -> None:
    salidos: list[dict[str, Any]] = []

    def aparece(segundos: float) -> None:
        if segundos == 300:
            web.publicar()

    pasar(enviados, web, salidos, Reloj(aparece))
    inicio = datetime(2026, 11, 1, tzinfo=UTC)
    media = avisos.espera_del_dia(tmp_path / "avisos.sqlite", inicio, inicio + timedelta(days=1))
    assert media == pytest.approx(5 + 20 / 60)
    # Otro día, nada; y una base anterior sin la tabla no rompe el resumen.
    otro = inicio - timedelta(days=1)
    assert avisos.espera_del_dia(tmp_path / "avisos.sqlite", otro, inicio) is None
    assert avisos.espera_del_dia(tmp_path / "no-hay.sqlite", otro, inicio) is None


def test_la_linea_del_resumen() -> None:
    datos = visitas.Datos(
        dia=date(2026, 11, 1), visitas=None, anterior=None, media7=None,
        suscriptores=visitas.suscriptores_del_dia([], date(2026, 11, 1)), nuevos=[],
        avisos=(4, 2), recogidas=(24, 0, 0), problemas=[], espera_web=5.34,
    )  # fmt: skip
    assert "  Avisos: 2 enviados; espera media de la web 5,3 min" in visitas.texto_resumen(datos)


def test_vigilancia_a_los_30_minutos() -> None:
    estado = {"pendientes": {ID: "2026-11-01T19:35:00Z"}}
    assert avisos.pendiente_para_vigilancia({}, AHORA) is None
    assert avisos.pendiente_para_vigilancia(estado, AHORA + timedelta(minutes=29)) is None
    frase = avisos.pendiente_para_vigilancia(estado, AHORA + timedelta(minutes=31))
    assert frase is not None
    assert ID in frase
    assert "avisos_ntfy" in vars(vigilancia)


def test_lo_pendiente_se_escribe_en_cuanto_se_sabe(
    tmp_path: Path, web: Web, enviados: avisos.Enviados
) -> None:
    ruta = tmp_path / "avisos.json"
    ruta.write_text(json.dumps({"enviados": 3}), encoding="utf-8")
    documento = incidente()
    salidos: list[dict[str, Any]] = []
    reloj = Reloj()
    avisos.pasar(
        {ID}, {ID: documento}, enviados, avisos.configuracion(), AHORA, salidos.append, None,
        avisos.Espera(avisos.comprobador(web.sitio), 0, 60, reloj.dormir, reloj,
                      lambda p: avisos.guardar_pendientes(ruta, p)),
    )  # fmt: skip
    estado = json.loads(ruta.read_text(encoding="utf-8"))
    assert estado["enviados"] == 3
    assert list(estado["pendientes"]) == [ID]


def test_hora_de_subida(tmp_path: Path) -> None:
    ruta = tmp_path / "publicacion.json"
    assert avisos.hora_de_subida(None, AHORA) == AHORA
    assert avisos.hora_de_subida(ruta, AHORA) == AHORA
    ruta.write_text(json.dumps({"subido": "2026-11-01T19:34:00Z"}), encoding="utf-8")
    assert avisos.hora_de_subida(ruta, AHORA) == AHORA - timedelta(minutes=1)
    ruta.write_text(json.dumps({"subido": "2026-11-02T19:34:00Z"}), encoding="utf-8")
    assert avisos.hora_de_subida(ruta, AHORA) == AHORA


def test_la_orden_comprobar_no_envia(
    web: Web, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    web.publicar()
    original = avisos.configuracion()
    monkeypatch.setattr(avisos, "configuracion", lambda: {**original, "sitio": web.sitio})
    assert avisos.principal(["comprobar", "--id", ID]) == 0
    assert json.loads(capsys.readouterr().out) == {ID: True}
    assert avisos.principal(["comprobar", "--id", ID, "--id", "EODI-2026-09999"]) == 1
