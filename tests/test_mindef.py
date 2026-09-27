"""Fuente del Ministerio de Defensa ruso: parser con fixtures breves de cada variante."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from almacen.base import Almacen
from exportacion.ucrania import exportar_ucrania
from recogida.cache import CachePaginas
from recogida.ejecucion import configuracion_fuente, ejecutar, procesar
from recogida.fuente import CanalNoVerificado
from recogida.mindef import (
    FUENTE,
    derribados,
    derribados_por_region,
    es_parte,
    leer,
    motivo_no_parte,
    parte_principal,
    verificar,
    vocabulario,
)
from recogida.parte import DESCONOCIDO, Derribo, ParteIlegible
from recogida.recorrido import pagina
from recogida.telegram import Publicacion
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
    assert publico["regiones"] == [{"region": "RU-BRY", "derribados": rango(40)}]
    # La fuente es pública en la capa de Ucrania aunque sea interna fuera de ella.
    assert publico["fuentes"][0]["id"] == "mod_russia-2"


@pytest.mark.parametrize(
    "frase",
    [
        "дежурными средствами ПВО беспилотный летательный аппарат уничтожен над территорией "
        "Белгородской области",
        "дежурными средствами ПВО украинский БПЛА уничтожен над территорией Белгородской области",
        "дежурными средствами ПВО уничтожен БпЛА самолетного типа над Белгородской областью",
    ],
)
def test_formato_2024_en_singular_tras_el_intento(frase: str) -> None:
    texto = (
        "⚡️ В течение прошедшей ночи при попытке киевского режима совершить террористическую "
        "атаку с применением трех беспилотных летательных аппаратов по объектам на территории "
        f"Российской Федерации {frase}." + PIE
    )
    assert es_parte(texto)
    leido = leer(texto, MANANA)
    # La cifra del intento (tres) no cuenta: solo lo que dice haber derribado.
    assert leido.derribados == rango(1)
    assert leido.regiones == ("RU-BEL",)


def test_hora_aproximada_sin_zona() -> None:
    texto = (
        "⚡️ Около 07.15 дежурными средствами ПВО уничтожены четыре украинских беспилотных "
        "летательных аппарата над территорией Курской области." + PIE
    )
    leido = leer(texto, datetime(2024, 10, 19, 5, 58, tzinfo=UTC))
    assert leido.inicio.documento() == instante("2024-10-19T04:15Z", "aproximada")
    assert leido.derribados == rango(4)


def test_sin_defensa_aerea_no_es_parte() -> None:
    texto = "Расчет ЗРК уничтожил разведывательный БпЛА ВСУ в небе над Харьковской областью." + PIE
    assert not es_parte(texto)


PREAMBULO = (
    "⚡️ {cuando} пресечена попытка киевского режима совершить террористическую атаку с "
    "применением трех БПЛА самолетного типа по объектам на территории Российской Федерации.\n\n"
)


@pytest.mark.parametrize(
    ("cuando", "derribo", "n", "inicio"),
    [
        ("Сегодня ночью",
         "Дежурными средствами ПВО двадцать два украинских беспилотных летательных аппарата "
         "уничтожено и еще тринадцать перехвачено над территорией Республики Крым.",
         35, instante("2023-12-04T17:00Z", "aproximada")),
        ("Ночью 5 декабря",
         "Дежурными средствами ПВО два украинских беспилотных летательных аппарата уничтожены над "
         "территорией Брянской области и еще три БПЛА перехвачены над акваторией Черного моря.",
         5, instante("2023-12-04T17:00Z", "aproximada")),
        ("В течение сегодняшней ночи",
         "Дежурными средствами ПВО были уничтожены пять и перехвачены три украинских беспилотных "
         "летательных аппарата над территорией Воронежской области, четыре БПЛА – над "
         "территорией Белгородской области.",
         12, instante("2023-12-04T17:00Z", "aproximada")),
        # Sin cifra: todos los del intento.
        ("Сегодня днем",
         "Дежурными средствами ПВО все беспилотные летательные аппараты уничтожены над территорией "
         "Брянской области.",
         3, instante("2023-12-04T21:00Z", "dia")),
        ("20 декабря в районе 04.00 мск",
         "Два украинских БпЛА уничтожены над территорией Брянской области.",
         2, instante("2023-12-20T01:00Z", "aproximada")),
        ("Около 5 часов",
         "Дежурными средствами ПВО один реактивный снаряд и украинский беспилотный летательный "
         "аппарат уничтожены над территорией Белгородской области.",
         1, instante("2023-12-05T02:00Z", "aproximada")),
    ],
)  # fmt: skip
def test_formato_2023_en_dos_parrafos(
    cuando: str, derribo: str, n: int, inicio: dict[str, str]
) -> None:
    texto = PREAMBULO.format(cuando=cuando) + derribo + PIE
    publicado = datetime(2023, 12, 5, 3, 9, tzinfo=UTC)
    if cuando.startswith("20 декабря"):
        publicado = datetime(2023, 12, 20, 2, tzinfo=UTC)
    assert es_parte(texto)
    leido = leer(texto, publicado)
    # La cifra del intento (tres) no se toma salvo que el parte diga «todos».
    assert leido.derribados == rango(n)
    assert leido.inicio.documento() == inicio


@pytest.mark.parametrize(
    ("texto", "n", "regiones"),
    [
        ("⚡️ Сегодня утром пресечена попытка киевского режима осуществить террористическую атаку "
         "семью беспилотными летательными аппаратами.\n\n▫️ Два украинских БПЛА уничтожены "
         "средствами ПВО над акваторией Черного моря.\n\n▫️ Еще пять БПЛА подавлено средствами "
         "радиоэлектронной борьбы.\n\n▫️ Над территорией Республики Крым уничтожена ракета.",
         7, ()),
        ("⚡️ Сегодня около 9.00 мск пресечена попытка киевского режима осуществить "
         "террористическую атаку.\n\n▫️ Средствами ПВО украинский ударный БПЛА был обнаружен и "
         "уничтожен над территорией Ступинского района Московской области.",
         1, ("RU-MOS",)),
        ("⚡️ В ночь с 20 на 21 сентября пресечена попытка киевского режима совершить "
         "террористическую атаку с применением двух БпЛА.\n\nДежурными средствами ПВО оба "
         "украинских беспилотных летательных аппарата перехвачены над территорией Брянской "
         "области.",
         2, ("RU-BRY",)),
    ],
)  # fmt: skip
def test_formato_2023_con_viñetas(texto: str, n: int, regiones: tuple[str, ...]) -> None:
    assert es_parte(texto + PIE)
    leido = leer(texto + PIE, datetime(2023, 9, 21, 4, tzinfo=UTC))
    assert leido.derribados == rango(n)
    # La viñeta del misil no aporta región.
    assert leido.regiones == regiones


def test_parte_de_2026_sin_decir_de_quien_son_los_drones() -> None:
    texto = (
        "⚡️ В течение прошедшей ночи дежурными силами ПВО перехвачены и уничтожены 244 "
        "беспилотных летательных аппарата самолетного типа над территориями Белгородской и "
        "Брянской областей." + PIE
    )
    assert es_parte(texto)
    assert leer(texto, MANANA).derribados == rango(244)


def test_noche_y_manana_con_fecha_y_regimen_en_instrumental() -> None:
    texto = (
        "⚡️ 27 августа в ночные и утренние часы киевским режимом были предприняты попытки "
        "террористических атак с применением БПЛА самолетного типа.\n\n▫️ Дежурными средствами "
        "ПВО были обнаружены и уничтожены в полете два беспилотных летательных аппарата над "
        "территорией Брянской и Курской областей." + PIE
    )
    assert es_parte(texto)
    leido = leer(texto, datetime(2023, 8, 27, 4, 14, tzinfo=UTC))
    assert leido.inicio.documento() == instante("2023-08-26T17:00Z", "aproximada")
    assert (leido.derribados, leido.regiones) == (rango(2), ("RU-BRY", "RU-KRS"))


# --- Derribos por región (casos reales de la caché) -------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        # 51077: lista con la cabecera del total, que no se suma.
        (
            "За период с 20.00 мск 8 апреля по 06.00 мск 9 апреля дежурными средствами ПВО "
            "перехвачены и уничтожены 12 украинских беспилотных летательных аппаратов "
            "самолетного типа:\n\n▪️7 БпЛА – над территорией Краснодарского края,\n"
            "▪️пять БпЛА – над территорией Ростовской области.",
            {"RU-KDA": 7, "RU-ROS": 5},
        ),
        # 37778: «из которых:» y viñetas sin la palabra dron; «по одному» para cada región.
        (
            "Дежурными средствами ПВО были уничтожены и перехвачены пятьдесят украинских БпЛА "
            "из которых: двадцать шесть – над территорией Белгородской области; десять – над "
            "территорией Брянской области; восемь – над территорией Курской области; два – "
            "над Тульской областью и по одному – над "
            "территориями Смоленской, Рязанской, Калужской и Московской областей.",
            {
                "RU-BEL": 26,
                "RU-BRY": 10,
                "RU-KRS": 8,
                "RU-TUL": 2,
                "RU-SMO": 1,
                "RU-RYA": 1,
                "RU-KLU": 1,
                "RU-MOS": 1,
            },
        ),
        # 34717: «пять и перехвачены три» sobre la misma región.
        (
            "Дежурными средствами ПВО были уничтожены пять и перехвачены три украинских "
            "беспилотных летательных аппарата над территорией Воронежской области, четыре БПЛА "
            "перехвачены над территорией Белгородской области.",
            {"RU-VOR": 8, "RU-BEL": 4},
        ),
        # 52931: «по одному» sigue en el mar, que suma pero no tiene código.
        (
            "уничтожены 4 украинских беспилотных летательных аппаратов самолетного типа:\n"
            "▪️ 1 БпЛА – над территорией Брянской области,\n▪️ по одному БпЛА – над "
            "территориями Тульской, Калужской областей и над акваторией Черного моря.",
            {"RU-BRY": 1, "RU-TUL": 1, "RU-KLU": 1},
        ),
        # 29663: la cifra va en una frase y el «над» en la siguiente.
        (
            "▫️ Дежурными силами ПВО два украинских беспилотных летательных аппарата были "
            "обнаружены и подавлены средствами радиоэлектронной борьбы.\n\n▫️ Потеряв "
            "управление, БПЛА потерпели крушение над акваторией Чёрного моря.",
            {},
        ),
        # 54825: la aclaración «в том числе ... на Москву» no es otra región.
        (
            "уничтожены 6 украинских беспилотных летательных аппаратов самолетного типа:\n"
            "▫️ 4 БПЛА – над территорией Московского региона, в том числе 3 БПЛА, летевших на "
            "Москву,\n▫️ 2 БПЛА – над территорией Тульской области.",
            {"RU-MOS": 4, "RU-TUL": 2},
        ),
        # 65571: la cifra es del conjunto de regiones: no hay reparto.
        (
            "дежурными средствами ПВО перехвачены и уничтожены 25 украинских беспилотных "
            "летательных аппарата самолетного типа над территориями Белгородской, Брянской "
            "областей и над акваторией Черного моря.",
            {},
        ),
    ],
)
def test_derribos_por_region(texto: str, esperado: dict[str, int]) -> None:
    total = derribados(parte_principal(texto))
    assert derribados_por_region(texto, total, vocabulario()) == esperado


def test_derribos_por_region_que_no_suman_el_total_no_se_guardan() -> None:
    texto = "уничтожены 3 БПЛА – над территорией Курской области."
    assert derribados_por_region(texto, 5, vocabulario()) == {}


# --- Resumen que cubre un tramo (51073 y 51077) ------------------------------------------

TRAMO_51073 = (
    "🎖🎖🎖🎖 В период с 22.00 до 22.15 мск дежурными средствами ПВО уничтожены пять украинских "
    "беспилотных летательных аппаратов самолетного типа: четыре БпЛА – над территорией "
    "Ростовской области и один БпЛА – над акваторией Азовского моря." + PIE
)
RESUMEN_51077 = (
    "🎖🎖 За период с 20.00 мск 8 апреля по 06.00 мск 9 апреля дежурными средствами ПВО "
    "перехвачены и уничтожены 158 украинских беспилотных летательных аппаратов самолетного "
    "типа:\n\n▪️67 БпЛА – над территорией Краснодарского края,\n▪️91 БпЛА – над территорией "
    "Ростовской области." + PIE
)


def test_el_resumen_con_por_da_el_fin_declarado() -> None:
    leido = leer(RESUMEN_51077, datetime(2025, 4, 9, 4, 4, tzinfo=UTC))
    assert leido.inicio.documento() == instante("2025-04-08T17:00Z")
    assert leido.fin.documento() == instante("2025-04-09T03:00Z")
    assert dict(leido.derribados_por_region) == {"RU-KDA": 67, "RU-ROS": 91}


def almacen_con_partes() -> Almacen:
    """Base con el tramo de las 22.00 y el resumen de la noche que lo cubre."""
    almacen = Almacen.abrir()
    config = configuracion_fuente("mindef_ru")
    publicaciones = [
        Publicacion("mod_russia", 51073, datetime(2025, 4, 8, 19, 37, tzinfo=UTC), TRAMO_51073),
        Publicacion("mod_russia", 51077, datetime(2025, 4, 9, 4, 4, tzinfo=UTC), RESUMEN_51077),
    ]
    recuentos = procesar(almacen, publicaciones, FUENTE, config, datetime(2025, 4, 10, tzinfo=UTC))
    assert recuentos.nuevos == len(publicaciones)
    return almacen
