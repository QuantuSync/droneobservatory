"""Lector de canales de la capa de guerra: comprobación de canal oficial en cada lectura,
filtro de lo que se guarda, relectura y histórico reanudable. Sin red: canal y web falsos."""

import dataclasses
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from recogida import canales_guerra as cg
from recogida.descarga import Descargador, Respuesta
from recogida.plazo import Plazo
from tests.telegram_falso import CanalFalso

AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
WEB = "https://sitio.oficial/ova"
DRON = "Окупанти вдарили дроном по Київському району Харкова. Пошкоджено 5 автомобілів."
OTRO = "Дорогі Захисники і Захисниці України! Дякую!"

CANAL = cg.Canal(
    id="ova_kharkiv", canal="kharkivoda", grupo="ova_ua", pais="UA", region="UA-63",
    sentido="RU_UA", idioma="uk", titulo="Харківська ОВА", insignia=True,
    descripcion_enlaza=("sitio.oficial",), web_oficial=WEB, web_enlaza="kharkivoda",
    web_desde_servidor=True, fiabilidad="B", origen="oficial", medio="Харківська ОВА",
    autoridad_ocupacion=False, identificado={"fecha": "2026-10-01"},
)  # fmt: skip


def falso(**cambios: object) -> CanalFalso:
    publicaciones = {
        i: (AHORA - timedelta(hours=40 - i), DRON if i % 2 else OTRO) for i in range(1, 21)
    }
    canal = CanalFalso(
        publicaciones,
        titulo="Харківська ОВА",
        web=WEB,
        web_enlaza='<html><a href="https://t.me/kharkivoda">Telegram</a></html>',
        canal="kharkivoda",
    )
    return dataclasses.replace(canal, **cambios)  # type: ignore[arg-type]


def descargador(canal: CanalFalso) -> Descargador:
    return Descargador(canal, dormir=lambda _: None, pausa_minima_s=0, reintentos=0)


def recoger(canal: CanalFalso, tmp_path: Path, estado: dict[str, object] | None = None,
            config: cg.Canal = CANAL) -> tuple[int, dict[str, object], cg.Datos]:  # fmt: skip
    datos = cg.Datos(tmp_path)
    estado = {} if estado is None else estado
    guardadas = cg.recoger_canal(config, descargador(canal), datos, estado, AHORA)
    return guardadas, estado, datos


def test_lee_solo_lo_que_habla_de_drones(tmp_path: Path) -> None:
    guardadas, estado, datos = recoger(falso(), tmp_path)
    textos = {p["texto"] for p in datos.ultimas("kharkivoda").values()}
    assert textos == {DRON}
    assert guardadas >= 1
    assert estado["ultimo_id"] == 20
    assert estado["web_resultado"] == "enlaza"


def test_sin_insignia_no_se_lee(tmp_path: Path) -> None:
    with pytest.raises(cg.NoVerificado, match="insignia"):
        recoger(falso(verificado=False), tmp_path)


def test_con_otro_titulo_no_se_lee(tmp_path: Path) -> None:
    with pytest.raises(cg.NoVerificado, match="título"):
        recoger(falso(titulo="Канал продається"), tmp_path)


def test_si_la_descripcion_ya_no_enlaza_la_web_no_se_lee(tmp_path: Path) -> None:
    with pytest.raises(cg.NoVerificado, match="descripción"):
        recoger(falso(web="https://otro.sitio/"), tmp_path)


def test_si_la_web_ya_no_enlaza_el_canal_no_se_lee(tmp_path: Path) -> None:
    with pytest.raises(cg.NoVerificado, match="ya no enlaza"):
        recoger(falso(web_enlaza="<html>sin enlaces</html>"), tmp_path)


def test_web_que_no_carga_vale_la_ultima_comprobacion_de_menos_de_30_dias(tmp_path: Path) -> None:
    canal = falso(web_enlaza="")  # la web devuelve algo que no es una página
    reciente: dict[str, object] = {"web_ultima_correcta": "2026-09-20T00:00:00Z"}
    recoger(canal, tmp_path, reciente)
    vieja: dict[str, object] = {"web_ultima_correcta": "2026-08-01T00:00:00Z"}
    with pytest.raises(cg.NoVerificado, match="30 días"):
        recoger(canal, tmp_path / "otra", vieja)


def test_web_que_nunca_carga_desde_el_servidor_se_lee_con_el_resto(tmp_path: Path) -> None:
    config = dataclasses.replace(CANAL, web_desde_servidor=False)
    guardadas, estado, _ = recoger(falso(web_enlaza=""), tmp_path, config=config)
    assert guardadas >= 1
    assert str(estado["web_resultado"]).startswith("no carga")


def test_la_cadena_oficial_se_comprueba(tmp_path: Path) -> None:
    """Rosaviatsia: favt.gov.ru enlaza @favt_ru, y su descripción enlaza @favt_info."""
    config = dataclasses.replace(
        CANAL, canal="favt_info", titulo="Говорит Росавиация", insignia=False,
        descripcion_enlaza=(), web_enlaza="favt_ru", cadena=(("favt_ru", "Росавиация"),),
    )  # fmt: skip

    @dataclasses.dataclass
    class Cadena(CanalFalso):
        # Lo que enlaza la descripción del canal intermedio (@favt_ru).
        enlace_siguiente: str = ""

        def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
            if "/s/favt_ru" in url:
                titulo = self.titulo
                self.titulo, self.web = "Росавиация", self.enlace_siguiente
                try:
                    return super().__call__(url, cabeceras, limite_s)
                finally:
                    self.titulo, self.web = titulo, WEB
            return super().__call__(url, cabeceras, limite_s)

    base = falso(
        titulo="Говорит Росавиация",
        canal="favt_info",
        web_enlaza='<html><a href="https://t.me/favt_ru">TG</a></html>',
    )
    bien = Cadena(**dataclasses.asdict(base), enlace_siguiente="https://t.me/favt_info")
    recoger(bien, tmp_path, config=config)
    mal = Cadena(**dataclasses.asdict(base), enlace_siguiente="https://t.me/otro")
    with pytest.raises(cg.NoVerificado, match="favt_ru ya no enlaza"):
        recoger(mal, tmp_path / "mal", config=config)


def test_una_publicacion_editada_se_guarda_otra_vez_y_vale_la_ultima(tmp_path: Path) -> None:
    datos = cg.Datos(tmp_path)
    canal = falso()
    recoger(canal, tmp_path)
    # Editada en las últimas 12 horas: la lectura siguiente la vuelve a mirar.
    canal.publicaciones[19] = (AHORA - timedelta(hours=2), DRON + " Постраждалих немає.")
    estado: dict[str, object] = {"ultimo_id": 20, "web_ultima_correcta": "2026-10-01T00:00:00Z"}
    cg.recoger_canal(CANAL, descargador(canal), datos, estado, AHORA)
    assert cg.Datos(tmp_path).ultimas("kharkivoda")[19]["texto"].endswith("немає.")


def test_un_canal_que_falla_no_para_a_los_demas(tmp_path: Path) -> None:
    datos = cg.Datos(tmp_path)
    otro = dataclasses.replace(CANAL, id="ova_otra", titulo="Інша ОВА")
    control = cg.recoger([otro, CANAL], descargador(falso()), datos, AHORA, Plazo(60))
    assert control["canales"]["ova_otra"]["resultado"] == "no_verificado"
    assert control["canales"]["ova_kharkiv"]["resultado"] == "leido"


def test_el_historico_baja_hasta_la_fecha_y_se_reanuda(tmp_path: Path) -> None:
    datos = cg.Datos(tmp_path)
    canal = falso()
    desde = (AHORA - timedelta(hours=30)).date()
    terminado = cg.historico([CANAL], descargador(canal), datos, desde, Plazo(60), AHORA)
    assert terminado
    avance = datos.control()["canales"]["ova_kharkiv"]["historico"]
    assert avance["terminado"] is True
    pedidas = len(canal.pedidas)
    # Ya terminado: no vuelve a pedir nada.
    cg.historico([CANAL], descargador(canal), datos, desde, Plazo(60), AHORA)
    assert len(canal.pedidas) == pedidas
    assert desde == date(2026, 9, 30)


def test_la_configuracion_real_tiene_canales_completos() -> None:
    canales = cg.cargar_canales()
    grupos = {c.grupo for c in canales}
    assert grupos == {"ova_ua", "estado_mayor_ua", "gobernadores_ru", "rosaviatsia"}
    for canal in canales:
        assert canal.titulo
        assert canal.identificado["fecha"]
        assert canal.origen in {"oficial", "parte"}
        # Lo ocupado lleva siempre el código de Ucrania; Rusia, el suyo.
        if canal.region is not None:
            assert canal.region.startswith(f"{canal.pais}-")


def test_el_historico_empieza_por_los_canales_que_situan_impactos_en_rusia() -> None:
    grupos = [c.grupo for c in cg.orden_historico(cg.cargar_canales())]
    assert grupos[0] == "estado_mayor_ua"
    assert grupos.index("ova_ua") > max(i for i, g in enumerate(grupos) if g == "gobernadores_ru")
