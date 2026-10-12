"""Datos rotos a propósito: la recogida sigue publicando o se recupera sola.

Cada caso mete un fallo en una recogida (artículos vacíos, sin idioma, sin país, con fechas malas
o futuras, campos nulos, duplicados y textos enormes; un candidato sin fuentes; la API inválida,
caída, lenta, con 429/529 o con el tope diario agotado; GDELT caído o con un fichero corrupto; el
disco lleno) y comprueba que lo demás se publica, con el código que toca. El almacén de Núremberg
caído está en tests/test_servidor.py (la reserva de Helsinki), ntfy caído en tests/test_avisos.py
y GoatCounter caído aquí, en el resumen y la vigilancia.
"""

import errno
import json
import logging
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from exportacion import proyeccion, publicar
from modelo import coste, ficha, paginas
from modelo.cliente import ErrorTemporal
from proceso import extraccion
from proceso.noticias import Articulo
from recogida import extractor, gdelt, horaria, visitas
from recogida.plazo import TiempoAgotado
from tests.telegram_falso import CanalFalso
from tests.test_extraccion import AHORA, TEXTO, ClienteFalso, ficha_ejemplo, respuesta
from tests.test_horaria import entorno, subir_base  # noqa: F401 (fixture)

CLAVES = {
    "EODI_EXTRACTOR_CLAVE": "k", "EODI_EXTRACTOR_URL": "u", "EODI_EXTRACTOR_URL_LOTES": "l",
    "EODI_EXTRACTOR_MODELO": "m", "EODI_EXTRACTOR_CABECERAS": '{"c": "{clave}"}',
}  # fmt: skip
LUGAR = ("EKCH",)
TITULAR = "Droner over Københavns Lufthavn: lufthavnen lukket"


@pytest.fixture
def almacen(monkeypatch: pytest.MonkeyPatch) -> Iterator[Almacen]:
    for nombre, valor in CLAVES.items():
        monkeypatch.setenv(nombre, valor)
    monkeypatch.setattr(extractor, "Descargador", lambda **_: None)
    monkeypatch.setattr(paginas, "leer", lambda _d, _u: TEXTO)
    a = Almacen.abrir()
    yield a
    a.cerrar()


def articulo(n: int, horas: float = 2, **cambios: Any) -> Articulo:
    datos: dict[str, Any] = {
        "url": f"https://medio{n}.dk/nyhed/{n}", "medio": f"medio{n}.dk",
        "fecha": AHORA - timedelta(hours=horas), "titular": f"{TITULAR} {n}", "idioma": "da",
        "pais": "DK", "lugares": LUGAR,
    }  # fmt: skip
    return Articulo(**(datos | cambios))


ROTOS = {
    "vacío": articulo(1, titular=""),
    "sin idioma": articulo(2, idioma=None),
    "sin país": articulo(3, pais=None),
    "fecha futura": articulo(4, horas=-72),
    "fecha muy antigua": articulo(5, horas=24 * 365 * 30),
    "texto enorme": articulo(6, titular=TITULAR + " " + "x" * 200_000),
    "sin lugar": articulo(7, lugares=()),
    "lugar desconocido": articulo(8, lugares=("NO-EXISTE",)),
    "nulos": articulo(9, medio="", temas=(), pais=None, idioma=None),
}


# --- Artículos rotos ----------------------------------------------------------------------
@pytest.mark.parametrize("caso", sorted(ROTOS))
def test_un_articulo_roto_no_tumba_gdelt_ni_el_extractor(almacen: Almacen, caso: str) -> None:
    bueno = articulo(20)
    gdelt.incorporar(almacen, [ROTOS[caso], bueno, bueno])  # con un duplicado
    falso = ClienteFalso(ficha_ejemplo())
    resultado = extractor.horaria(almacen, AHORA, lambda _c: falso)
    assert resultado.parada in (None, extraccion.Parada.LIMITE_GASTO)
    assert falso.llamadas >= 1


def test_articulos_sin_idioma_no_abren_candidato(almacen: Almacen) -> None:
    """12 de octubre de 2026: un artículo en panyabí abrió solo un candidato en Milán."""
    gdelt.incorporar(almacen, [articulo(30, idioma=None), articulo(31, idioma=None)])
    assert almacen.candidatos() == []
    assert len(almacen.articulos_de([articulo(30).url])) == 1


def test_un_candidato_sin_fuentes_se_anota_y_no_se_llama(almacen: Almacen) -> None:
    gdelt.incorporar(almacen, [articulo(40)])
    (candidato,) = almacen.candidatos()
    # Como el de Milán: su único artículo, sin idioma reconocido.
    almacen.conexion.execute("UPDATE articulos SET idioma = NULL")
    almacen.conexion.commit()
    falso = ClienteFalso(ficha_ejemplo())
    resultado = extractor.horaria(almacen, AHORA, lambda _c: falso)
    assert falso.llamadas == 0 and resultado.parada is None
    assert extraccion.apartados(almacen)[candidato["id"]]["motivo"] == extraccion.SIN_IDIOMA
    # La recogida siguiente ni lo prepara.
    assert extractor.pendientes(almacen, AHORA - timedelta(days=3)) == []


# --- Un candidato que falla se aparta y se retira tras 3 recogidas -----------------------
class ClienteQueRompeUno:
    """Responde bien a todos, salvo una respuesta con la que el proceso falla."""

    def __init__(self, malo: str) -> None:
        self.malo = malo
        self.pedidos: list[str] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        texto = json.dumps(cuerpo, ensure_ascii=False)
        self.pedidos.append(texto)
        return {"rota": True} if self.malo in texto else respuesta(ficha_ejemplo())


def test_un_candidato_que_falla_se_aparta_y_se_retira_tras_tres_recogidas(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    gdelt.incorporar(almacen, [articulo(50, titular="Droner over Københavns Lufthavn MALO")])
    gdelt.incorporar(almacen, [articulo(51, horas=30, titular="Droner over Aalborg Lufthavn")])

    def procesar(almacen: Almacen, peticion: Any, respuesta: Any, *args: Any) -> Any:
        if "rota" in respuesta:
            raise KeyError("content")
        return None

    monkeypatch.setattr(extraccion, "procesar_respuesta", procesar)
    url_malo = articulo(50).url
    (malo,) = [c["id"] for c in almacen.candidatos() if url_malo in c["articulos"]]
    for hora in range(3):
        cliente = ClienteQueRompeUno("MALO")
        momento = AHORA + timedelta(hours=hora)
        resultado = extractor.horaria(almacen, momento, lambda _c: cliente)  # noqa: B023
        assert resultado.parada is None
    apartados = extraccion.apartados(almacen)
    retirados = extraccion.retirados(almacen)
    assert retirados, apartados
    assert retirados == {malo}
    assert "retirado tras fallar en 3 recogidas distintas" in apartados[malo]["motivo"]
    # Ya no se intenta.
    assert malo not in {c["id"] for c in extractor.pendientes(almacen)}


def test_varios_fallos_en_la_misma_recogida_cuentan_como_uno(almacen: Almacen) -> None:
    for _ in range(3):
        extraccion.anotar_fallo(almacen, "CAND-x", "fallo", AHORA)
    assert extraccion.retirados(almacen) == set()
    assert len(extraccion.apartados(almacen)["CAND-x"]["fallos"]) == 1


def test_un_candidato_que_no_se_puede_preparar_no_frena_a_los_demas(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    gdelt.incorporar(almacen, [articulo(60)])
    gdelt.incorporar(almacen, [articulo(61, horas=30, titular="Droner over Aalborg Lufthavn")])
    original = extraccion.preparar
    primero = almacen.candidatos()[0]["id"]

    def preparar(almacen: Almacen, candidato: dict[str, Any], *args: Any) -> Any:
        if candidato["id"] == primero:
            raise ValueError("objetivo sin vocabulario")
        return original(almacen, candidato, *args)

    monkeypatch.setattr(extraccion, "preparar", preparar)
    falso = ClienteFalso(ficha_ejemplo())
    resultado = extractor.horaria(almacen, AHORA, lambda _c: falso)
    assert resultado.parada is None
    assert primero in extraccion.apartados(almacen)


# --- La API ---------------------------------------------------------------------------------
class ClienteRoto:
    def __init__(self, fallo: Exception | dict[str, Any]) -> None:
        self.fallo, self.llamadas = fallo, 0

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.llamadas += 1
        if isinstance(self.fallo, Exception):
            raise self.fallo
        return self.fallo


@pytest.mark.parametrize(
    ("fallo", "parada"),
    [
        (ErrorTemporal("código 429; reintentos: 1"), extraccion.Parada.SERVICIO_CAIDO),
        (ErrorTemporal("código 529 overloaded; reintentos: 1"), extraccion.Parada.SERVICIO_CAIDO),
        (ErrorTemporal("corte de conexión (TimeoutError)"), extraccion.Parada.SERVICIO_CAIDO),
        (TiempoAgotado("tope de 420 s agotado"), extraccion.Parada.TIEMPO),
        (ValueError("Expecting value: line 1 column 1"), extraccion.Parada.SERVICIO_CAIDO),
        ({"content": "no es una lista", "usage": None}, None),
        ({}, None),
    ],
)
def test_la_api_rota_deja_los_candidatos_pendientes_sin_tumbar_nada(
    almacen: Almacen, fallo: Exception | dict[str, Any], parada: extraccion.Parada | None
) -> None:
    gdelt.incorporar(almacen, [articulo(70)])
    cliente = ClienteRoto(fallo)
    resultado = extractor.horaria(almacen, AHORA, lambda _c: cliente)
    assert resultado.parada is parada


def test_tope_diario_agotado_no_llama_ni_es_fallo(almacen: Almacen) -> None:
    gdelt.incorporar(almacen, [articulo(80)])
    almacen.registrar_llamada({
        "fecha": AHORA.strftime("%Y-%m-%dT%H:%M:%SZ"), "modo": "horario", "candidato": "x",
        "lote": False, "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_DIARIO_USD,
    })  # fmt: skip
    falso = ClienteFalso(ficha_ejemplo())
    resultado = extractor.horaria(almacen, AHORA, lambda _c: falso)
    assert falso.llamadas == 0
    assert resultado.parada is extraccion.Parada.LIMITE_GASTO and not resultado.en_rojo


# --- Recogida completa ------------------------------------------------------------------------
def _recoger(repositorio: str) -> int:
    return horaria.principal(["--correo", "a@b.org", "--repositorio", repositorio])


def test_recogida_completa_con_articulos_rotos_publica(
    entorno: tuple[str, CanalFalso, Path],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repositorio, _, salida = entorno
    subir_base(repositorio, tmp_path, ultimo_id=1)
    for nombre, valor in CLAVES.items():
        monkeypatch.setenv(nombre, valor)
    monkeypatch.setattr(extractor, "Descargador", lambda **_: None)
    monkeypatch.setattr(paginas, "leer", lambda _d, _u: TEXTO)
    ahora = datetime.now(UTC)
    rotos = [Articulo(**{**a.__dict__, "fecha": ahora - (AHORA - a.fecha)}) for a in ROTOS.values()]
    monkeypatch.setattr(gdelt, "ejecutar", lambda almacen, *_: gdelt.incorporar(almacen, rotos))
    monkeypatch.setattr("modelo.cliente.Cliente", lambda *_a, **_k: ClienteRoto({}))
    assert _recoger(repositorio) in (0, horaria.SALIDA_AVISO)
    assert (salida / publicar.INCIDENTES).exists()


@pytest.mark.parametrize(
    "fallo",
    [
        gdelt.GdeltNoDisponible("la API no responde"),
        zipfile.BadZipFile("File is not a zip file"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
)
def test_gdelt_caido_o_con_un_fichero_corrupto_publica_con_aviso(
    entorno: tuple[str, CanalFalso, Path],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fallo: Exception,
) -> None:
    repositorio, _, salida = entorno
    subir_base(repositorio, tmp_path, ultimo_id=1)

    def roto(*_: Any) -> None:
        raise fallo

    monkeypatch.setattr(gdelt, "ejecutar", roto)
    assert _recoger(repositorio) == horaria.SALIDA_AVISO
    assert (salida / publicar.INCIDENTES).exists()


def test_un_paso_que_revienta_no_frena_a_los_demas_y_publica(
    entorno: tuple[str, CanalFalso, Path],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repositorio, _, salida = entorno
    subir_base(repositorio, tmp_path, ultimo_id=1)

    def revienta(*_: Any, **__: Any) -> None:
        raise RuntimeError("fallo inesperado")

    for objetivo in (
        "recogida.oficiales.ejecutar", "proceso.solapes.enlazar", "proceso.incursiones.retirar",
        "proceso.presencia.revisar", "recogida.barrera.paso_horario",
        "recogida.prevision.paso_horario",
    ):  # fmt: skip
        monkeypatch.setattr(objetivo, revienta)
    caplog.set_level(logging.WARNING, logger="recogida")
    assert _recoger(repositorio) == horaria.SALIDA_AVISO
    assert (salida / publicar.INCIDENTES).exists()
    assert "pasos fallidos en esta recogida" in caplog.text


def test_disco_lleno_en_un_fichero_publica_los_demas(
    entorno: tuple[str, CanalFalso, Path],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repositorio, _, salida = entorno
    subir_base(repositorio, tmp_path, ultimo_id=1)
    original = proyeccion.escribir

    def lleno(documento: Any, ruta: Path) -> None:
        if ruta.name == publicar.UCRANIA:
            raise OSError(errno.ENOSPC, "No space left on device")
        original(documento, ruta)

    monkeypatch.setattr("exportacion.publicar.escribir", lleno)
    assert _recoger(repositorio) == horaria.SALIDA_AVISO
    assert (salida / publicar.INCIDENTES).exists()
    assert not (salida / publicar.UCRANIA).exists()


def test_disco_lleno_del_todo_es_codigo_1_para_que_systemd_la_repita(
    entorno: tuple[str, CanalFalso, Path],  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repositorio, _, _ = entorno
    subir_base(repositorio, tmp_path, ultimo_id=1)

    def lleno(_documento: Any, _ruta: Path) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr("exportacion.publicar.escribir", lleno)
    assert _recoger(repositorio) == 1


# --- GoatCounter caído ------------------------------------------------------------------------
def test_goatcounter_caido_el_resumen_sale_igual(tmp_path: Path) -> None:
    datos = visitas.reunir(
        AHORA.date(), tmp_path / "no-existe.sqlite3", tmp_path / "datos", tmp_path / "pub",
        tmp_path / "base.sqlite", tmp_path / "avisos.sqlite", AHORA, lambda _o: "", lambda: None,
    )  # fmt: skip
    texto = visitas.texto_resumen(datos)
    assert "No se pudo leer el contador de visitas." in texto
    assert "no se pudo leer salud.json" in texto


def test_ficha_valida_tras_los_fallos() -> None:
    """La ficha de ejemplo sigue siendo la del servicio (si cambia, estas pruebas no prueban)."""
    assert ficha.leer_respuesta(respuesta(ficha_ejemplo()))


# --- Artículos dirigidos ----------------------------------------------------------------------
def test_un_articulo_dirigido_entra_una_vez_y_va_delante(almacen: Almacen, tmp_path: Path) -> None:
    from recogida import articulos_dirigidos

    ruta = tmp_path / "dirigidos.json"
    articulo_ = {
        "url": "https://medio.dk/nyhed/dirigida", "medio": "medio.dk",
        "fecha": "2025-09-23T05:00:00Z", "idioma": "da", "pais": "DK", "titular": TITULAR,
        "lugar": "EKCH",
    }  # fmt: skip
    roto = {**articulo_, "url": "https://medio.dk/sin-lugar", "lugar": "NO-EXISTE"}
    ruta.write_text(json.dumps({"articulos": [articulo_, roto]}), encoding="utf-8")
    assert articulos_dirigidos.paso_horario(almacen, AHORA, ruta) == 1
    assert articulos_dirigidos.paso_horario(almacen, AHORA, ruta) == 0
    (candidato,) = articulos_dirigidos.candidatos(almacen)
    assert extractor.prioritarios(almacen)[0]["id"] == candidato
