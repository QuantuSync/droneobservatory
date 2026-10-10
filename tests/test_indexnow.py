"""IndexNow (recogida/indexnow.py, docs/posicionamiento.md): la primera vez se envía todo el
sitemap una sola vez; después, solo los incidentes nuevos o cambiados, por lotes y sin repetir; un
lote que falla se reintenta; sin el fichero de la clave en la web no se envía nada."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from recogida import indexnow

AHORA = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)
CONFIG: dict[str, Any] = {
    "clave": "0123456789abcdef0123456789abcdef",
    "sitio": "https://droneobservatory.eu",
    "punto": "https://api.indexnow.org/indexnow",
    "lote": 2,
}
SITIO = "https://droneobservatory.eu"


def sitemap(paginas: dict[str, str]) -> str:
    filas = "".join(
        f"<url><loc>{SITIO}{ruta}</loc><lastmod>{fecha}</lastmod>"
        f'<xhtml:link rel="alternate" hreflang="en" href="{SITIO}/en{ruta}"/></url>'
        for ruta, fecha in paginas.items()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        f'xmlns:xhtml="http://www.w3.org/1999/xhtml">{filas}</urlset>'
    )


class Web:
    def __init__(self, paginas: dict[str, str], clave: str = CONFIG["clave"]) -> None:
        self.paginas = paginas
        self.clave = clave

    def __call__(self, url: str) -> str:
        if url.endswith("/sitemap.xml"):
            return sitemap(self.paginas)
        if url.endswith(".txt"):
            return self.clave
        raise AssertionError(url)


class Buscador:
    def __init__(self, codigos: list[int] | None = None) -> None:
        self.lotes: list[list[str]] = []
        self.cuerpos: list[dict[str, Any]] = []
        self.codigos = codigos or []

    def __call__(self, cuerpo: dict[str, Any]) -> int:
        self.cuerpos.append(cuerpo)
        codigo = self.codigos.pop(0) if self.codigos else 200
        if codigo in (200, 202):
            self.lotes.append(cuerpo["urlList"])
        return codigo


def test_la_primera_vez_todo_y_despues_solo_incidentes_nuevos_o_cambiados(tmp_path: Path) -> None:
    estado = tmp_path / "indexnow.json"
    paginas = {
        "/": "2026-10-10T15:17:00Z",
        "/metodologia": "2026-10-10T15:17:00Z",
        "/EODI-2026-00001": "2026-10-01T10:00:00Z",
        "/EODI-2026-00002": "2026-10-02T10:00:00Z",
        "/en/EODI-2026-00002": "2026-10-02T10:00:00Z",
    }
    web = Web(paginas)
    buscador = Buscador()
    assert indexnow.pasar(CONFIG, estado, web, buscador, AHORA) == (5, 0)
    # Por lotes de 2, sin repetir.
    assert [len(lote) for lote in buscador.lotes] == [2, 2, 1]
    assert sum(len(lote) for lote in buscador.lotes) == len(
        {u for lote in buscador.lotes for u in lote}
    )
    primero = buscador.cuerpos[0]
    assert primero["host"] == "droneobservatory.eu"
    assert primero["key"] == CONFIG["clave"]
    assert primero["keyLocation"] == f"{SITIO}/{CONFIG['clave']}.txt"

    # Sin cambios: nada. Las páginas de texto cambian de fecha cada hora y no se envían.
    paginas["/"] = paginas["/metodologia"] = "2026-10-10T16:17:00Z"
    buscador = Buscador()
    assert indexnow.pasar(CONFIG, estado, web, buscador, AHORA) == (0, 0)
    assert buscador.cuerpos == []

    # Un incidente cambiado y uno nuevo, en los dos idiomas.
    paginas["/EODI-2026-00001"] = "2026-10-10T16:00:00Z"
    paginas["/EODI-2026-00003"] = "2026-10-10T16:00:00Z"
    paginas["/en/EODI-2026-00003"] = "2026-10-10T16:00:00Z"
    assert indexnow.pasar(CONFIG, estado, web, buscador, AHORA) == (3, 0)
    assert sorted(u for lote in buscador.lotes for u in lote) == [
        f"{SITIO}/EODI-2026-00001",
        f"{SITIO}/EODI-2026-00003",
        f"{SITIO}/en/EODI-2026-00003",
    ]
    assert json.loads(estado.read_text(encoding="utf-8"))["ultima"] == "2026-10-10T18:00:00Z"


def test_un_lote_que_falla_se_reintenta_y_lo_enviado_no_se_repite(tmp_path: Path) -> None:
    estado = tmp_path / "indexnow.json"
    paginas = {f"/EODI-2026-0000{n}": "2026-10-01T10:00:00Z" for n in range(1, 5)}
    web = Web(paginas)
    assert indexnow.pasar(CONFIG, estado, web, Buscador([200, 429]), AHORA) == (2, 2)
    buscador = Buscador()
    assert indexnow.pasar(CONFIG, estado, web, buscador, AHORA) == (2, 0)
    assert buscador.lotes == [[f"{SITIO}/EODI-2026-00003", f"{SITIO}/EODI-2026-00004"]]


def test_la_primera_vez_sin_ningun_envio_bueno_no_anota_nada(tmp_path: Path) -> None:
    estado = tmp_path / "indexnow.json"
    web = Web({"/": "2026-10-10T15:17:00Z"})
    assert indexnow.pasar(CONFIG, estado, web, Buscador([403]), AHORA) == (0, 1)
    assert not estado.exists()


def test_sin_el_fichero_de_la_clave_no_se_envia(tmp_path: Path) -> None:
    buscador = Buscador()
    with pytest.raises(ValueError, match="clave"):
        indexnow.pasar(
            CONFIG, tmp_path / "e.json", Web({"/": ""}, clave="<html>404"), buscador, AHORA
        )
    assert buscador.cuerpos == []


def test_el_ensayo_no_envia_ni_anota(tmp_path: Path) -> None:
    estado = tmp_path / "indexnow.json"
    assert indexnow.pasar(CONFIG, estado, Web({"/": "", "/EODI-2026-00001": ""}), None, AHORA) == (
        2,
        0,
    )
    assert not estado.exists()


def test_configuracion_y_fichero_de_la_clave_en_la_web() -> None:
    config = indexnow.configuracion()
    clave = config["clave"]
    assert len(clave) == 32 and all(c in "0123456789abcdef" for c in clave)
    publicado = indexnow.RAIZ / "web" / "public" / f"{clave}.txt"
    assert publicado.read_text(encoding="utf-8").strip() == clave
    assert config["punto"] == "https://api.indexnow.org/indexnow"
    assert 1 <= config["lote"] <= indexnow.LOTE_MAXIMO


def test_el_envio_va_tras_publicar_bien_y_el_ensayo_no_envia() -> None:
    servidor = indexnow.RAIZ / "servidor"
    recogida = (servidor / "recogida.sh").read_text(encoding="utf-8")
    publicar = recogida.index('if publicar_en_almacen "$modo_pub"; then')
    envio = recogida.index("-m recogida.indexnow enviar")
    no_publicado = recogida.index('echo "aviso: los ficheros no se publicaron en el almacén"')
    assert publicar < envio < no_publicado
    ensayo = (servidor / "ensayo.sh").read_text(encoding="utf-8")
    assert "-m recogida.indexnow ensayo" in ensayo and "recogida.indexnow enviar" not in ensayo
