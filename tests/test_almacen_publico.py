"""Almacén público: configuración, firma S3 y subida tolerante a fallos, sin red."""

import email.message
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from recogida import almacen_publico, salud
from recogida.almacen_publico import Almacen

RAIZ = Path(__file__).resolve().parent.parent
VACIO = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@pytest.fixture
def almacen() -> Almacen:
    return almacen_publico.cargar()


def test_la_configuracion_da_el_almacen_de_hetzner(almacen: Almacen) -> None:
    assert almacen.punto_s3 == f"https://{almacen.ubicacion}.your-objectstorage.com"
    assert almacen.publico == (
        f"https://{almacen.bucket}.{almacen.ubicacion}.your-objectstorage.com"
    )
    assert almacen.url_publica("estado.json") == f"{almacen.publico}/estado.json"
    assert almacen.url_s3("estado.json") == (f"{almacen.punto_s3}/{almacen.bucket}/estado.json")
    assert almacen.objetos == {"estado": "estado.json", "teselas": "europa-z14.pmtiles"}


def test_ninguna_direccion_del_almacen_es_de_cloudflare() -> None:
    texto = (RAIZ / "configuracion" / "almacen_publico.json").read_text(encoding="utf-8")
    for dominio in ("cloudflare", "r2.dev", "tiles.droneobservatory.eu"):
        assert dominio not in texto


def test_la_vigilancia_lee_el_estado_del_almacen(almacen: Almacen) -> None:
    assert almacen.url_publica("estado.json") == salud.URL


def test_la_politica_de_contenido_admite_el_almacen_y_nada_de_cloudflare(
    almacen: Almacen,
) -> None:
    vercel = json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))
    politicas = [
        cabecera["value"]
        for regla in vercel["headers"]
        for cabecera in regla["headers"]
        if cabecera["key"] == "Content-Security-Policy"
    ]
    assert politicas
    for politica in politicas:
        directivas = {d.split()[0]: d.split()[1:] for d in politica.split(";") if d.strip()}
        assert directivas["connect-src"] == ["'self'", almacen.publico]
        assert "tiles.droneobservatory.eu" not in politica


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("punto_s3", "http://nbg1.your-objectstorage.com"), ("bucket", ""), ("publico", None)],
)
def test_una_configuracion_incompleta_o_sin_https_no_se_acepta(
    tmp_path: Path, campo: str, valor: str | None
) -> None:
    datos = json.loads((RAIZ / "configuracion" / "almacen_publico.json").read_text("utf-8"))
    datos[campo] = valor
    ruta = tmp_path / "almacen.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError, match=campo):
        almacen_publico.cargar(ruta)


def test_la_firma_coincide_con_el_ejemplo_publicado_de_sigv4() -> None:
    # Ejemplo «GET Object» de la documentación de Signature Version 4 de Amazon S3.
    cabeceras = almacen_publico.firmar(
        "GET",
        "https://examplebucket.s3.amazonaws.com/test.txt",
        {"Range": "bytes=0-9"},
        VACIO,
        "us-east-1",
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        datetime(2013, 5, 24, tzinfo=UTC),
    )
    assert cabeceras["authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


class Envios:
    """Doble del envío: responde con lo que se le pide, en orden, y anota cada petición."""

    def __init__(self, *respuestas: int | Exception) -> None:
        self.respuestas = list(respuestas)
        self.peticiones: list[urllib.request.Request] = []
        self.topes: list[float] = []

    def __call__(self, peticion: urllib.request.Request, tope_s: float) -> int:
        self.peticiones.append(peticion)
        self.topes.append(tope_s)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def _http(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", codigo, "error", email.message.Message(), None)


def _subir(almacen: Almacen, envios: Envios, esperas: list[float]) -> tuple[bool, str]:
    return almacen_publico.subir(
        almacen,
        "estado.json",
        b'{"version": 1}',
        "identificador",
        "secreto",
        "application/json",
        "public, max-age=60",
        envios,
        esperas.append,
        reloj=lambda: sum(esperas),
    )


def test_sube_firmado_al_bucket_con_su_cache(almacen: Almacen) -> None:
    esperas: list[float] = []
    envios = Envios(200)
    assert _subir(almacen, envios, esperas) == (True, "subido en el intento 1")
    assert esperas == []
    (peticion,) = envios.peticiones
    assert peticion.get_method() == "PUT"
    assert peticion.full_url == almacen.url_s3("estado.json")
    cabeceras = {k.lower(): v for k, v in peticion.header_items()}
    assert cabeceras["cache-control"] == "public, max-age=60"
    assert cabeceras["content-type"] == "application/json"
    assert cabeceras["authorization"].startswith("AWS4-HMAC-SHA256 Credential=identificador/")
    assert f"/{almacen.ubicacion}/s3/aws4_request" in cabeceras["authorization"]
    # El secreto nunca viaja: solo la firma.
    assert all("secreto" not in v for v in cabeceras.values())


def test_reintenta_con_espera_creciente(almacen: Almacen) -> None:
    esperas: list[float] = []
    envios = Envios(_http(503), OSError("sin red"), 200)
    assert _subir(almacen, envios, esperas) == (True, "subido en el intento 3")
    assert esperas == [2.0, 4.0]


def test_un_error_definitivo_no_se_reintenta(almacen: Almacen) -> None:
    esperas: list[float] = []
    envios = Envios(_http(403))
    correcto, motivo = _subir(almacen, envios, esperas)
    assert not correcto
    assert "403" in motivo
    assert esperas == []
    assert len(envios.peticiones) == 1


def test_si_todo_falla_devuelve_el_motivo_sin_lanzar(almacen: Almacen) -> None:
    esperas: list[float] = []
    envios = Envios(_http(500), TimeoutError(), _http(502))
    assert _subir(almacen, envios, esperas) == (False, "HTTP 502 tras 3 intentos")
    assert esperas == [2.0, 4.0]
    # Cada intento con su tope y todos dentro del tope total.
    assert all(t <= almacen_publico.TOPE_INTENTO_S for t in envios.topes)


def test_no_pasa_del_tope_total(almacen: Almacen) -> None:
    envios = Envios(_http(500), _http(500), 200)
    instantes = iter([0.0, 0.0, 59.0])
    correcto, motivo = almacen_publico.subir(
        almacen, "estado.json", b"{}", "i", "s", enviar=envios, dormir=lambda _s: None,
        reloj=lambda: next(instantes, 59.0),
    )  # fmt: skip
    assert not correcto
    assert motivo == "HTTP 500 tras 1 intentos"
    assert len(envios.peticiones) == 1


def test_sin_credenciales_no_sube_y_sale_con_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichero = tmp_path / "estado.json"
    fichero.write_text("{}", encoding="utf-8")
    envios = Envios()
    argumentos = ["subir", "--fichero", str(fichero), "--objeto", "estado.json"]
    assert almacen_publico.principal(argumentos, {}, envios) == 1
    assert "sin ALMACEN_ID" in capsys.readouterr().out
    assert envios.peticiones == []


def test_la_orden_sube_con_las_credenciales_del_entorno(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichero = tmp_path / "estado.json"
    fichero.write_text("{}", encoding="utf-8")
    envios = Envios(_http(500), 200)
    esperas: list[float] = []
    entorno = {"ALMACEN_ID": "identificador", "ALMACEN_SECRETO": "secreto"}
    argumentos = ["subir", "--fichero", str(fichero), "--objeto", "estado.json",
                  "--tipo", "application/json", "--cache", "public, max-age=60"]  # fmt: skip
    assert almacen_publico.principal(argumentos, entorno, envios, esperas.append) == 0
    assert esperas == [2.0]
    salida = capsys.readouterr().out
    assert "subido en el intento 2" in salida
    assert "secreto" not in salida
