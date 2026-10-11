"""Visitas y resumen diario (recogida/visitas.py), sin red ni systemd: una base de GoatCounter de
prueba con su esquema, ntfy y el almacén sustituidos."""

import gzip
import json
import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from recogida import visitas

DIA = date(2026, 10, 11)


def _sql(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def base_goatcounter(ruta: Path, paginas: list[tuple[str, str, str, str, str, int, str]]) -> Path:
    """Las tablas de GoatCounter 2.7 que lee el resumen. Cada página vista: (momento UTC, sesión,
    ruta, referente, esquema del referente, ancho, sistema y país «sistema|país»)."""
    conexion = sqlite3.connect(ruta)
    conexion.executescript(
        """
        create table paths (path_id integer primary key, site_id int, path text, title text,
                            event int default 0);
        create table refs (ref_id integer primary key, ref text, ref_scheme text);
        create table systems (system_id integer primary key, name text, version text);
        create table locations (location_id integer primary key, country text, region text,
                                country_name text, region_name text);
        create table hits (hit_id integer primary key autoincrement, site_id int, path_id int,
                           ref_id int, session blob, first_visit int, browser_id int,
                           system_id int, width int, location text, created_at text);
        insert into refs values (1, '', 'o');
        insert into locations values (1, '', '', '(unknown)', ''),
            (2, 'US', '', 'United States', ''), (3, 'ES', '', 'Spain', ''),
            (4, 'SC', '', 'Seychelles', '');
        """
    )
    for momento, sesion, camino, ref, esquema, ancho, sistema_pais in paginas:
        sistema, pais = sistema_pais.split("|")
        path_id = _id(
            conexion,
            "paths",
            "path",
            camino,
            "insert into paths (site_id, path, title) values (1, ?, '')",
        )
        ref_id = _id(
            conexion,
            "refs",
            "ref",
            ref,
            f"insert into refs (ref, ref_scheme) values (?, '{esquema}')",
        )
        system_id = _id(
            conexion,
            "systems",
            "name",
            sistema,
            "insert into systems (name, version) values (?, '')",
        )
        conexion.execute(
            "insert into hits (site_id, path_id, ref_id, session, first_visit, browser_id,"
            " system_id, width, location, created_at) values (1, ?, ?, ?, 1, 1, ?, ?, ?, ?)",
            (path_id, ref_id, sesion.encode(), system_id, ancho, pais, momento),
        )
    conexion.commit()
    conexion.close()
    return ruta


def _id(conexion: sqlite3.Connection, tabla: str, columna: str, valor: str, insertar: str) -> int:
    fila = conexion.execute(f"select rowid from {tabla} where {columna} = ?", (valor,)).fetchone()
    if fila:
        return int(fila[0])
    return int(conexion.execute(insertar, (valor,)).lastrowid or 0)


def en_madrid(dia: date, h: int, m: int = 0) -> str:
    return _sql(datetime(dia.year, dia.month, dia.day, h, m, tzinfo=visitas.MADRID))


@pytest.fixture
def goatcounter(tmp_path: Path) -> Path:
    paginas = [
        # Visitante a: móvil desde LinkedIn en España, tres páginas.
        (en_madrid(DIA, 0, 5), "a", "/", "www.linkedin.com/feed", "h", 390, "iOS|ES"),
        (
            en_madrid(DIA, 0, 6),
            "a",
            "/EODI-2026-00509",
            "www.linkedin.com/feed",
            "h",
            390,
            "iOS|ES",
        ),
        (en_madrid(DIA, 0, 7), "a", "/", "", "o", 390, "iOS|ES"),
        # Visitante b: ordenador desde Google en EE. UU.
        (en_madrid(DIA, 12), "b", "/metodologia", "www.google.com/", "h", 1920, "Windows|US"),
        # Visitante c: directo, Seychelles (sin nombre en español: el de GoatCounter).
        (en_madrid(DIA, 23, 59), "c", "/", "", "o", 1440, "macOS|SC"),
        # Fuera del día de Madrid (las 00:30 del día siguiente en Madrid).
        (en_madrid(DIA + timedelta(days=1), 0, 30), "d", "/", "", "o", 390, "Android|ES"),
        # El día anterior: una visita.
        (en_madrid(DIA - timedelta(days=1), 10), "e", "/", "", "o", 390, "Android|ES"),
    ]
    return base_goatcounter(tmp_path / "goatcounter.sqlite3", paginas)


def test_limites_del_dia_con_el_cambio_de_hora() -> None:
    inicio, fin = visitas.limites_del_dia(date(2026, 10, 25))
    assert inicio == datetime(2026, 10, 24, 22, tzinfo=UTC)
    assert fin - inicio == timedelta(hours=25)
    inicio, fin = visitas.limites_del_dia(DIA)
    assert (inicio.hour, fin - inicio) == (22, timedelta(hours=24))


def test_visitas_del_dia(goatcounter: Path) -> None:
    conexion = visitas.abrir_goatcounter(goatcounter)
    v = visitas.visitas_del_dia(conexion, DIA)
    assert (v.visitas, v.visitantes) == (5, 3)
    assert v.paginas[0] == ("/", 3)
    assert dict(v.procedencias) == {"LinkedIn": 1, "Google": 1, "Directo": 1}
    assert dict(v.paises) == {"España": 1, "Estados Unidos": 1, "Seychelles": 1}
    assert (v.movil, v.ordenador) == (1, 2)
    assert visitas.totales(conexion, DIA - timedelta(days=1)) == (1, 1)
    conexion.close()


@pytest.mark.parametrize(
    ("ref", "esquema", "nombre"),
    [
        ("", "o", "Directo"),
        ("lnkd.in/abc", "h", "LinkedIn"),
        ("www.google.es/", "h", "Google"),
        ("Google", "g", "Google"),
        ("t.co/xyz", "h", "X"),
        ("boletin", "c", "Campaña boletin"),
        ("www.elpais.com/internacional", "h", "elpais.com"),
    ],
)
def test_procedencia(ref: str, esquema: str, nombre: str) -> None:
    assert visitas.procedencia(ref, esquema) == nombre


def test_contar_recogidas() -> None:
    lineas = [
        "eodi-recogida.service: Deactivated successfully.",
        "eodi-recogida.service: Main process exited, code=exited, status=2/INVALIDARGUMENT",
        "eodi-recogida.service: Failed with result 'exit-code'.",
        "eodi-recogida.service: Main process exited, code=exited, status=1/FAILURE",
        "eodi-recogida.service: Deactivated successfully.",
    ]
    assert visitas.contar_recogidas(lineas) == (2, 1, 1)


def test_suscriptores_del_dia() -> None:
    def muestra(dia: date, h: int, n: int, nav: dict[str, int] | None = None) -> dict[str, Any]:
        momento = datetime(dia.year, dia.month, dia.day, h, tzinfo=visitas.MADRID)
        return {"momento": visitas._iso(momento), "suscriptores": n, "navegador": nav or {}}

    lista = [
        muestra(DIA - timedelta(days=1), 23, 10),
        muestra(DIA, 9, 14),
        muestra(DIA, 23, 12, {"drones-europe": 3, "drones-poland": 1}),
    ]
    s = visitas.suscriptores_del_dia(lista, DIA)
    assert (s.conectados, s.maximo, s.anterior) == (12, 14, 10)
    assert s.navegador_total == 4
    assert s.navegador_temas[0] == ("drones-europe", 3)


def test_incidentes_publicados_por_primera_vez(tmp_path: Path) -> None:
    datos = tmp_path / "datos"
    antes = datetime(2026, 10, 10, 9, tzinfo=UTC)
    anotados = visitas.anotar_publicados(
        datos, {"EODI-1": "Uno"}, antes, lambda ids: {"EODI-1": "2026-10-09T08:00:00Z"}
    )
    # La primera vez, la hora del alta en la base.
    assert anotados["EODI-1"]["desde"] == "2026-10-09T08:00:00Z"
    ahora = datetime(2026, 10, 11, 10, tzinfo=UTC)
    anotados = visitas.anotar_publicados(
        datos, {"EODI-1": "Uno", "EODI-2": "Dos"}, ahora, lambda _ids: {}
    )
    assert visitas.nuevos_del_dia(anotados, DIA) == [("EODI-2", "Dos")]
    assert visitas.nuevos_del_dia(anotados, date(2026, 10, 9)) == [("EODI-1", "Uno")]


def test_avisos_del_dia(tmp_path: Path) -> None:
    ruta = tmp_path / "avisos.sqlite"
    conexion = sqlite3.connect(ruta)
    conexion.execute("create table avisos (id text, tema text, momento text, inicial int)")
    conexion.executemany(
        "insert into avisos values (?, ?, ?, ?)",
        [
            ("EODI-1", "drones-europe", "2026-10-11T08:00:00Z", 0),
            ("EODI-1", "drones-poland", "2026-10-11T08:00:01Z", 0),
            ("EODI-0", "*", "2026-10-11T08:00:00Z", 1),
            ("EODI-2", "drones-europe", "2026-10-10T08:00:00Z", 0),
        ],
    )
    conexion.commit()
    conexion.close()
    assert visitas.avisos_del_dia(ruta, DIA) == (2, 1)


def _datos(goatcounter: Path, tmp_path: Path) -> visitas.Datos:
    conexion = visitas.abrir_goatcounter(goatcounter)
    v = visitas.visitas_del_dia(conexion, DIA)
    conexion.close()
    return visitas.Datos(
        dia=DIA,
        visitas=v,
        anterior=(1, 1),
        media7=(1 / 7, 1 / 7),
        suscriptores=visitas.Suscriptores(12, 14, 10, 4, [("drones-europe", 3)]),
        nuevos=[("EODI-2026-00509", "Dron se estrella en Moldavia")],
        avisos=(2, 1),
        recogidas=(23, 1, 0),
        problemas=[],
    )


def test_texto_del_resumen(goatcounter: Path, tmp_path: Path) -> None:
    texto = visitas.texto_resumen(_datos(goatcounter, tmp_path))
    assert texto.startswith("Datos del domingo 11 de octubre de 2026 (hora de Madrid).")
    assert "Visitas: 5 (día anterior 1, +400 %; media de 7 días 0,1, +3400 %)" in texto
    assert "Visitantes únicos: 3" in texto
    assert "1. /: 3" in texto
    assert "Dispositivos: móvil 33 % (1), ordenador 67 % (2)" in texto
    assert (
        "Suscriptores conectados al cierre: 12 (+2 respecto al día anterior; máximo del día 14)"
        in texto
    )
    assert "EODI-2026-00509: Dron se estrella en Moldavia" in texto
    assert "Recogidas: 24 correctas (1 con avisos), 0 fallidas" in texto
    assert "ningún problema abierto" in texto
    # Sin emoticonos: todo dentro del plano básico multilingüe y sin símbolos gráficos.
    assert not re.search("[\U0001f000-\U0001faff☀-➿]", texto)
    cuerpo = visitas.mensaje(_datos(goatcounter, tmp_path), "lucas-resumen")
    assert cuerpo["title"] == "EODI · Resumen diario"
    assert cuerpo["click"] == "https://stats.droneobservatory.eu/"
    assert len(cuerpo["message"].encode("utf-8")) < 4096


class Copia:
    def __init__(self) -> None:
        self.objetos: dict[str, bytes] = {}

    def subir(self, clave: str, cuerpo: bytes) -> None:
        self.objetos[clave] = cuerpo

    def existe(self, clave: str) -> bool:
        return clave in self.objetos

    def bajar(self, clave: str) -> bytes:
        return self.objetos[clave]


def _rutas(tmp_path: Path, goatcounter: Path) -> visitas.Rutas:
    secretos = tmp_path / "secretos"
    secretos.mkdir(exist_ok=True)
    return visitas.Rutas(
        secretos=secretos,
        datos=tmp_path / "datos",
        goatcounter=goatcounter,
        publicacion=tmp_path / "publicacion",
        base=tmp_path / "base.sqlite",
        avisos=tmp_path / "avisos.sqlite",
    )


def test_pasada_envia_una_vez_a_partir_de_las_8_y_reintenta(
    goatcounter: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("recogida.visitas.time.sleep", lambda _s: None)
    rutas = _rutas(tmp_path, goatcounter)
    enviados: list[dict[str, Any]] = []
    fallar = [True]
    copia = Copia()

    def enviar(cuerpo: dict[str, Any]) -> None:
        if fallar[0]:
            raise OSError("sin red")
        enviados.append(cuerpo)

    def pasar(momento: datetime) -> dict[str, Any]:
        return visitas.pasada(
            rutas, momento, enviar, lambda: {"ntfy_subscribers_total": 7.0}, lambda: copia,
            lambda _orden: "", lambda: [],
        )  # fmt: skip

    # 07:55 de Madrid: todavía no.
    estado = pasar(datetime(2026, 10, 12, 5, 55, tzinfo=UTC))
    assert "resumen" not in estado and enviados == []
    assert set(copia.objetos) == {"visitas/ultima.sqlite.gz", "visitas/diaria/2026-10-12.sqlite.gz"}
    assert gzip.decompress(copia.objetos["visitas/ultima.sqlite.gz"]).startswith(b"SQLite format 3")
    # 08:00: falla tres veces y queda anotado; la vigilancia aún no lo ve como problema.
    estado = pasar(datetime(2026, 10, 12, 6, 0, tzinfo=UTC))
    assert estado["resumen"]["fallos_seguidos"] == 1 and "sin red" in estado["resumen"]["error"]
    assert (
        visitas.problemas_para_vigilancia(estado, datetime(2026, 10, 12, 6, 30, tzinfo=UTC)) == []
    )
    # 08:05: sale el del día 11, al tema privado; después no se repite.
    fallar[0] = False
    estado = pasar(datetime(2026, 10, 12, 6, 5, tzinfo=UTC))
    assert estado["resumen"]["dia"] == "2026-10-11"
    assert [c["topic"] for c in enviados] == ["lucas-resumen"]
    assert "Visitas: 5" in enviados[0]["message"]
    pasar(datetime(2026, 10, 12, 6, 10, tzinfo=UTC))
    assert len(enviados) == 1
    # La copia de la base se repite solo pasada casi una hora.
    assert estado["copia"]["ultima"] == "2026-10-12T05:55:00Z"
    muestras = (rutas.datos / visitas.MUESTRAS).read_text(encoding="utf-8").splitlines()
    assert len(muestras) == 4 and json.loads(muestras[0])["suscriptores"] == 7


def test_problemas_para_la_vigilancia() -> None:
    a_las_nueve = datetime(2026, 10, 12, 7, 1, tzinfo=UTC)  # 09:01 de Madrid
    sin_enviar = {"resumen": {"dia": "2026-10-10"}, "copia": {"ultima": "2026-10-12T06:30:00Z"}}
    assert [p["id"] for p in visitas.problemas_para_vigilancia(sin_enviar, a_las_nueve)] == [
        "resumen"
    ]
    enviado = {"resumen": {"dia": "2026-10-11"}, "copia": {"ultima": "2026-10-12T03:00:00Z"}}
    assert [p["id"] for p in visitas.problemas_para_vigilancia(enviado, a_las_nueve)] == [
        "copia_visitas"
    ]


def test_restaurar_comprueba_la_base(goatcounter: Path, tmp_path: Path) -> None:
    copia = Copia()
    estado: dict[str, Any] = {}
    visitas.copiar(goatcounter, estado, datetime(2026, 10, 12, 6, tzinfo=UTC), copia)
    resultado = visitas.restaurar(copia, tmp_path / "restaurada.sqlite3")
    assert resultado["paginas_vistas"] == 7


def test_el_resumen_de_prueba_nunca_va_a_un_tema_publico_ni_al_privado(
    monkeypatch: pytest.MonkeyPatch, goatcounter: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr(visitas, "rutas_del_entorno", lambda: _rutas(tmp_path, goatcounter))
    monkeypatch.setattr(visitas, "recogidas_del_dia", lambda _dia, _e=None: (0, 0, 0))
    monkeypatch.setattr(visitas, "problemas_abiertos", lambda: [])
    monkeypatch.setattr(visitas, "_enviador", lambda _s: pytest.fail("no debe enviar"))
    for tema in ("drones-europe", "lucas-resumen"):
        assert visitas.principal(["resumen", "--dia", "2026-10-11", "--tema", tema]) == 1


def test_fallos_de_privacidad() -> None:
    cerrado = {visitas.PANEL: 303}
    assert visitas.fallos_de_privacidad(lambda url: cerrado.get(url, 403)) == []
    # Un panel que se abre sin usuario es un fallo; uno que no responde, no (es otro problema).
    abierto = visitas.fallos_de_privacidad(lambda url: 200 if url == visitas.PANEL else 0)
    assert abierto == ["el panel de visitas se abre sin usuario (HTTP 200)"]
