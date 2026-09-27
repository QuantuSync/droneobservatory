"""Fuente del Ministerio de Defensa ruso: parser con fixtures breves de cada variante."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from almacen.base import Almacen
from exportacion.ucrania import exportar_ucrania
from recogida.cache import CachePaginas
from recogida.ejecucion import ejecutar
from recogida.fuente import CanalNoVerificado
from recogida.mindef import FUENTE, es_parte, leer, motivo_no_parte, verificar
from recogida.parte import DESCONOCIDO, Derribo, ParteIlegible
from recogida.recorrido import pagina
from tests.telegram_falso import CanalFalso, descargador

PIE = "\n\n🔹 Минобороны России"
# 07:12 en Moscú (UTC+3).
MANANA = datetime(2025, 7, 31, 4, 12, tzinfo=UTC)


def rango(n: int) -> dict[str, int]:
    return {"min": n, "max": n}


def instante(valor: str, precision: str = "minuto") -> dict[str, str]:
    return {"valor": valor, "precision": precision}


# --- Periodo --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inicio_texto", "publicado", "inicio", "fin"),
    [
        # Fechas numéricas y «C» latina.
        ("C 23.20 мск 30.07 до 04.00 мск 31.07", MANANA,
         instante("2025-07-30T20:20Z"), instante("2025-07-31T01:00Z")),
        # Fecha en letras tras la hora y «мск» solo en el fin.
        ("В течение прошедшей ночи с 22.41 30 июля до 05.05 мск 31 июля", MANANA,
         instante("2025-07-30T19:41Z"), instante("2025-07-31T02:05Z")),
        # Sin fechas: el mismo día de la publicación.
        ("В период с 8.00 мск до 20.00 мск", datetime(2025, 7, 31, 17, 30, tzinfo=UTC),
         instante("2025-07-31T05:00Z"), instante("2025-07-31T17:00Z")),
        # Sin fechas y cruzando la medianoche: empieza la víspera.
        ("С 21.50 мск до 05.20 мск", MANANA,
         instante("2025-07-30T18:50Z"), instante("2025-07-31T02:20Z")),
        # «до полуночи» publicado pasada la medianoche: el día anterior.
        ("С 21.50 мск до полуночи", datetime(2025, 7, 29, 21, 23, tzinfo=UTC),
         instante("2025-07-29T18:50Z"), instante("2025-07-29T21:00Z")),
        ("С полуночи до 06.00 мск", MANANA,
         instante("2025-07-30T21:00Z"), instante("2025-07-31T03:00Z")),
        # «24.00» con fecha es la medianoche que cierra ese día.
        ("В течение прошедшей ночи в период с 24.00 мск 30 июля до 7.00 мск 31 июля", MANANA,
         instante("2025-07-30T21:00Z"), instante("2025-07-31T04:00Z")),
        # «т.г.» y solo el inicio: acaba al publicarse.
        ("В период с 20.00 30 июля т.г.", MANANA,
         instante("2025-07-30T17:00Z"), instante("2025-07-31T04:12Z", "aproximada")),
        ("Около 06.05 мск", MANANA,
         instante("2025-07-31T03:05Z", "aproximada"), instante("2025-07-31T03:05Z", "aproximada")),
        ("В 06.40 мск", MANANA, instante("2025-07-31T03:40Z"), instante("2025-07-31T03:40Z")),
        ("В течение прошедшей ночи", MANANA,
         instante("2025-07-30T17:00Z", "aproximada"), instante("2025-07-31T04:12Z", "aproximada")),
        ("В утренние часы 31 июля", MANANA,
         instante("2025-07-30T21:00Z", "dia"), instante("2025-07-31T04:12Z", "aproximada")),
        ("По состоянию на 20.00 мск", datetime(2025, 7, 31, 18, 6, tzinfo=UTC),
         instante("2025-07-30T21:00Z", "dia"), instante("2025-07-31T17:00Z")),
    ],
)  # fmt: skip
def test_periodo_de_moscu_a_utc(
    inicio_texto: str, publicado: datetime, inicio: dict[str, str], fin: dict[str, str]
) -> None:
    texto = (
        f"🎖🎖 {inicio_texto} дежурными средствами ПВО перехвачены и уничтожены 32 украинских "
        "беспилотных летательных аппарата самолетного типа над территорией Курской области." + PIE
    )
    assert es_parte(texto)
    leido = leer(texto, publicado)
    assert (leido.inicio.documento(), leido.fin.documento()) == (inicio, fin)


# --- Cifras, regiones y tipo ----------------------------------------------------


def test_lista_de_regiones_con_viñetas() -> None:
    texto = (
        "🎖🎖 С 23.00 мск 28.09 до 07.00 мск 29.09 дежурными средствами ПВО перехвачены и "
        "уничтожены 78 украинских беспилотных летательных аппаратов самолетного типа:\n\n"
        "▫️ 24 – над территорией Брянской области,\n"
        "▫️ 21 – над территорией Республики Крым,\n"
        "▫️ 9 БПЛА – над акваторией Черного моря,\n"
        "▫️ 4 – над территорией Московского региона.\n\n"
        "❗️ Всего в ночное время перехвачено и уничтожено 84 украинских беспилотных "
        "летательных аппарата самолетного типа." + PIE
    )
    leido = leer(texto, datetime(2025, 9, 29, 4, 45, tzinfo=UTC))
    # La cifra del parte es la de su periodo; «Всего» suma otros partes de la noche.
    assert leido.derribados == rango(78)
    assert leido.regiones == ("RU-BRY", "UA-43", "RU-MOS")
    assert leido.tipos_dron == ("ala_fija",)
    assert leido.derribados_categoria is Derribo.DERRIBADOS
    assert leido.lanzados["total"] == DESCONOCIDO


def test_cifra_en_letras_singular_y_region_sin_territorio() -> None:
    texto = (
        "В 13.40 мск дежурными средствами ПВО уничтожен один украинский беспилотный летательный "
        "аппарат самолетного типа над Московским регионом." + PIE
    )
    leido = leer(texto, datetime(2025, 7, 16, 11, 39, tzinfo=UTC))
    assert leido.derribados == rango(1)
    assert leido.regiones == ("RU-MOS",)
    sin_cifra = texto.replace("один украинский", "украинский")
    assert leer(sin_cifra, datetime(2025, 7, 16, 11, 39, tzinfo=UTC)).derribados == rango(1)


def test_regiones_de_una_lista_en_una_frase() -> None:
    texto = (
        "В течение дня в период с 8.00 до 20.00 мск дежурными силами ПВО перехвачены и "
        "уничтожены 426 украинских беспилотных летательных аппаратов самолетного типа над "
        "территориями Белгородской, Брянской, Тверской областей, Московского региона, "
        "Краснодарского края, Республики Марий Эл и Республики Крым." + PIE
    )
    leido = leer(texto, datetime(2025, 9, 3, 17, 31, tzinfo=UTC))
    assert leido.regiones == ("RU-BEL", "RU-BRY", "RU-TVE", "RU-MOS", "RU-KDA", "RU-ME", "UA-43")
    assert len(leido.frase.split()) <= 25


def test_region_fuera_del_vocabulario_deja_el_parte_como_fallido() -> None:
    texto = (
        "В течение прошедшей ночи дежурными средствами ПВО уничтожены 5 украинских БПЛА над "
        "территорией Энской области." + PIE
    )
    with pytest.raises(ParteIlegible, match="región fuera del vocabulario: Энской"):
        leer(texto, MANANA)


def test_neutralizados_por_guerra_electronica() -> None:
    texto = (
        "В течение прошедшей ночи дежурными средствами ПВО уничтожены и подавлены средствами "
        "радиоэлектронной борьбы 12 украинских БПЛА над территорией Курской области." + PIE
    )
    assert leer(texto, MANANA).derribados_categoria is Derribo.DERRIBADOS_O_NEUTRALIZADOS


def test_sin_periodo_es_ilegible() -> None:
    texto = "Дежурными средствами ПВО уничтожены 3 украинских БПЛА над территорией Курской области."
    with pytest.raises(ParteIlegible, match="sin periodo"):
        leer(texto, MANANA)


# --- Detección ------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        # Resumen del día: repite partes ya publicados.
        "Главное за день\n\n▫️ За день над территорией Курской области уничтожены 20 украинских "
        "БПЛА.",
        # Derribos en la zona de combate, sin «над территорией».
        "Средствами противовоздушной обороны сбиты 105 беспилотных летательных аппаратов "
        "самолетного типа.",
        # Operación rusa con drones, no derribos.
        "Расчет ударных БПЛА «Молния-2» уничтожил пункт управления дронами ВСУ.",
        # Misiles solos.
        "С 7.00 до 9.00 мск над территорией Белгородской области сбиты две ракеты «Нептун».",
    ],
)
def test_no_son_partes_de_drones_derribados(texto: str) -> None:
    assert not es_parte(texto)


def test_motivos_de_no_parte() -> None:
    assert motivo_no_parte("Главное за день\n▫️ 20 БПЛА") == "resumen del día o de la semana"
    assert motivo_no_parte("Сбиты 105 беспилотных летательных аппаратов.") == (
        "derribos en la zona de combate, no sobre territorio"
    )


# --- Canal y ejecución ----------------------------------------------------------

PARTE = (
    "⚡️ В течение прошедшей ночи дежурными средствами ПВО перехвачены и уничтожены {n} "
    "украинских беспилотных летательных аппаратов самолетного типа над территорией Брянской "
    "области." + PIE
)


def canal() -> CanalFalso:
    base = datetime(2026, 9, 20, 4, tzinfo=UTC)
    textos = {1: "Итоги недели", 2: PARTE.format(n=40), 3: "Видео", 4: PARTE.format(n=55)}
    publicaciones = {i: (base + timedelta(days=i // 2), t) for i, t in textos.items()}
    return CanalFalso(publicaciones, titulo="Минобороны России", canal="mod_russia")


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def test_canal_oficial_por_insignia_y_titulo(tmp_path: Path) -> None:
    falso = canal()
    cache = CachePaginas(tmp_path)
    verificar(descargador(falso), pagina(descargador(falso), cache, "mod_russia", None, False))
    falso.verificado = False
    with pytest.raises(CanalNoVerificado, match="insignia"):
        verificar(descargador(falso), pagina(descargador(falso), cache, "mod_russia", None, False))
    falso.verificado, falso.titulo = True, "Минобороны Украины"
    with pytest.raises(CanalNoVerificado, match="título"):
        verificar(descargador(falso), pagina(descargador(falso), cache, "mod_russia", None, False))


def test_ejecucion_da_ataques_ua_ru_reivindicados_con_credibilidad_3(
    almacen: Almacen, tmp_path: Path
) -> None:
    falso = canal()
    almacen.guardar_cursor("mindef_ru", {"ultimo_id": 0})
    ahora = datetime(2026, 9, 28, tzinfo=UTC)
    recuentos = ejecutar(almacen, descargador(falso), CachePaginas(tmp_path), FUENTE, ahora)
    assert (recuentos.partes, recuentos.leidos, recuentos.nuevos) == (2, 2, 2)
    ataque = almacen.ataques_ucrania()[0]
    assert ataque["sentido"] == "UA_RU"
    assert ataque["reivindicacion_de_parte"] is True
    assert ataque["estado"]["actual"] == "confirmado"
    (fuente,) = ataque["fuentes"]
    assert (fuente["fiabilidad"], fuente["credibilidad"], fuente["idioma"]) == ("D", 3, "ru")
    assert fuente["enlace"] == "https://t.me/mod_russia/2"
    publico = exportar_ucrania(almacen.ataques_ucrania(), ahora)["ataques"][0]
    assert publico["reivindicacion_de_parte"] is True
    assert publico["tipos_dron"] == ["ala_fija"]
    assert publico["regiones"] == [{"region": "RU-BRY"}]
    # La fuente es pública en la capa de Ucrania aunque sea interna fuera de ella.
    assert publico["fuentes"][0]["id"] == "mod_russia-2"
