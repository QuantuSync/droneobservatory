"""Parser de partes con fixtures breves de cada variante de formato."""

from datetime import UTC, datetime

import pytest

from recogida.parte import DESCONOCIDO, ParteIlegible, es_parte, frases, leer, zonas

PUBLICADO = datetime(2026, 9, 26, 4, 17, tzinfo=UTC)


def rango(minimo: int, maximo: int | None = None) -> dict[str, int]:
    return {"min": minimo, "max": minimo if maximo is None else maximo}


# --- Variante 2025-2026: una frase con varios modelos y subcuenta ---------------

NOCHE_2026 = """⚡️ ЗБИТО/ПОДАВЛЕНО 134 ВОРОЖІ БПЛА
➖➖➖➖➖➖➖➖➖➖
У ніч на 26 вересня (з 18:00 25 вересня) противник атакував 173 ударними БпЛА типу Shahed (понад 50 із них - реактивні), Гербера, дронами-імітаторами типу “Пародія” із напрямків: Орел,  Курськ, Міллерово - рф; ТОТ Донецьк та ТОТ АР Крим – Гвардійське.

💥 За попередніми даними, станом на 07:30, протиповітряною обороною збито/подавлено 134 ворожі БпЛА типу Shahed, Гербера та дронів інших типів.

Зафіксовано влучання засобів повітряного нападу противника на 19 локаціях а також падіння збитих (уламки) на 8 локаціях.
"""  # noqa: E501


def test_noche_2026_periodo_en_utc() -> None:
    leido = leer(NOCHE_2026, PUBLICADO)
    # 18:00 y 07:30 en Kyiv (UTC+3 en septiembre).
    assert leido.inicio.documento() == {"valor": "2026-09-25T15:00Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2026-09-26T04:30Z", "precision": "minuto"}


def test_noche_2026_total_con_modelos_en_rango() -> None:
    leido = leer(NOCHE_2026, PUBLICADO)
    assert leido.lanzados == {
        "total": rango(173),
        "shahed_geran": rango(50, 173),
        "gerbera_senuelos": rango(0, 173),
        "otros": rango(0),
    }
    assert leido.derribados == rango(134)
    assert leido.perdidos_guerra_electronica == DESCONOCIDO


def test_noche_2026_zonas_localizaciones_y_regiones() -> None:
    leido = leer(NOCHE_2026, PUBLICADO)
    assert leido.zonas_lanzamiento == ("Орел", "Курськ", "Міллерово", "Донецьк", "Гвардійське")
    assert leido.localizaciones_impacto == rango(19)
    assert leido.localizaciones_restos == rango(8)
    # Donetsk y Crimea son zonas de lanzamiento, no regiones afectadas.
    assert leido.regiones == ()
    assert leido.frase.startswith("У ніч на 26 вересня (з 18:00 25 вересня) противник атакував")
    assert len(leido.frase.split()) <= 25


# --- Variante con lista de armas y derribos por viñetas -------------------------

LISTA_2026 = """⚡️ ЗБИТО/ПОДАВЛЕНО 110 ЦІЛЕЙ ПРОТИВНИКА
У ніч на 22 вересня (з 18:00 21 вересня) противник атакував:

- балістичними ракетами Іскандер-М із Курської обл. рф;
- 4 крилатими ракетами морського базування "Калібр" із акваторії Каспійського моря;
- 8 "Бандероль"/"Дань-Т" з повітряного простору Білгородської обл. рф;
- 212 ударними БпЛА типу Shahed (в т.ч. реактивними) та дронами-імітаторами типу “Пародія” із напрямків:  Орел, Шаталово – рф., ТОТ Донецьк, Гвардійське, Чауда – ТОТ АР Крим.

❗️Основні напрямки удару - Дніпропетровщина, Кіровоградщина та Полтавщина.

💥 За попередніми даними, станом на 08:00, протиповітряною обороною збито/подавлено 186 цілей:

- 1 крилату ракету "Калібр";
- 8 "Бандероль"/"Дань-Т";
- 177 БпЛА типу Shahed, Гербера та дронів інших типів.
"""  # noqa: E501


def test_lista_solo_cuenta_drones() -> None:
    leido = leer(LISTA_2026, datetime(2026, 9, 22, 5, tzinfo=UTC))
    assert leido.lanzados == {
        "total": rango(220),
        "shahed_geran": rango(0, 212),
        "gerbera_senuelos": rango(0, 212),
        "otros": rango(8),
    }
    # 8 Bandérol y 177 drones; el misil Kalibr no cuenta.
    assert leido.derribados == rango(185)
    assert leido.zonas_lanzamiento == ("Орел", "Шаталово", "Донецьк", "Гвардійське", "Чауда")
    assert leido.regiones == ("UA-12", "UA-35", "UA-53")


def test_las_viñetas_se_unen_a_su_cabecera_aunque_haya_lineas_en_blanco() -> None:
    bloque = [f for f in frases(LISTA_2026) if f.startswith("💥")]
    assert bloque[0].endswith("177 БпЛА типу Shahed, Гербера та дронів інших типів.")


# --- Variante de día con intervalo explícito ------------------------------------

DIA_2026 = """❗️ Протягом дня 25 вересня (із 7.00 до 18.30) противник атакував Україну 162 ударними БпЛА (76 із них — реактивні), Гербара, "Бандероль/Дань-Т" та дронами інших типів.

За попередніми даними, протиповітряною обороною протягом вказаного періоду збито/подавлено 127 БпЛА (44 із них - реактивні).

Станом на 20.00 у повітряному просторі спостерігаються декілька ударних безпілотників.
"""  # noqa: E501


def test_dia_con_intervalo_y_subcuentas() -> None:
    leido = leer(DIA_2026, datetime(2026, 9, 25, 17, 22, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2026-09-25T04:00Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2026-09-25T15:30Z", "precision": "minuto"}
    assert leido.lanzados["total"] == rango(162)
    assert leido.lanzados["shahed_geran"] == rango(76, 162)
    # La subcuenta "44 із них" no se suma a los derribados.
    assert leido.derribados == rango(127)


# --- Reglas generales -----------------------------------------------------------


def test_cambio_de_anio() -> None:
    texto = "У ніч на 1 січня (з 18:00 31 грудня) противник атакував 20 ударними БпЛА типу Shahed."
    leido = leer(texto, datetime(2026, 1, 1, 6, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2025-12-31T16:00Z"
    assert leido.fin.precision == "aproximada"


def test_sin_hora_de_inicio_declarada_es_aproximada() -> None:
    texto = "В ніч на 30 грудня противник атакував 16 шахедами. Знищено 16 з 16."
    leido = leer(texto, datetime(2025, 12, 30, 6, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2025-12-29T16:00Z", "precision": "aproximada"}
    assert leido.lanzados["shahed_geran"] == rango(16)
    assert leido.derribados == rango(16)


def test_misiles_y_drones_en_la_misma_frase() -> None:
    texto = (
        "У ніч на 15 квітня (з 18:00 14 квітня) противник атакував трьома балістичними ракетами "
        "Іскандер-М, а також 324 ударними БпЛА типу Shahed, Гербера, Італмас та безпілотниками "
        "інших типів із напрямків: Курськ – рф, близько 250 із них – шахеди."
    )
    leido = leer(texto, datetime(2026, 4, 15, 4, tzinfo=UTC))
    assert leido.lanzados["total"] == rango(324)
    assert leido.lanzados["shahed_geran"] == rango(250, 324)
    assert leido.lanzados["otros"] == rango(0, 324)
    assert leido.zonas_lanzamiento == ("Курськ",)


def test_perdidos_por_guerra_electronica() -> None:
    texto = (
        "У ніч на 9 грудня (з 19:00 8 грудня) противник атакував 50-ма ударними БпЛА типу Shahed "
        "та дронами-імітаторами.\nСтаном на 09:00 підтверджено збиття 23 ударних БпЛА; "
        "22 ворожі БпЛА – локаційно втрачені (без негативних наслідків)."
    )
    leido = leer(texto, datetime(2024, 12, 9, 7, tzinfo=UTC))
    assert leido.lanzados["total"] == rango(50)
    assert leido.derribados == rango(23)
    assert leido.perdidos_guerra_electronica == rango(22)
    assert leido.inicio.documento()["valor"] == "2024-12-08T17:00Z"


@pytest.mark.parametrize(
    "texto",
    [
        "🛵 БпЛА курсом на Київ.",
        "Групи ударних БпЛА на півночі Сумщини, курсом на південь.",
        "У ніч на 12 вересня противник атакував 8-ма крилатими ракетами Калібр.",
        "Відбій повітряної тривоги.",
    ],
)
def test_alertas_y_partes_sin_drones_no_son_partes(texto: str) -> None:
    assert not es_parte(texto)


def test_parte_sin_cifras_de_drones_es_ilegible() -> None:
    texto = "У ніч на 22 вересня противник атакував Україну ударними БпЛА. Деталі згодом."
    assert es_parte(texto)
    with pytest.raises(ParteIlegible, match="sin cifras de drones"):
        leer(texto, datetime(2026, 9, 22, 5, tzinfo=UTC))


def test_fecha_imposible_es_ilegible() -> None:
    texto = "У ніч на 31 вересня противник атакував 5 ударними БпЛА."
    with pytest.raises(ParteIlegible, match="fecha imposible"):
        leer(texto, datetime(2026, 10, 1, 5, tzinfo=UTC))


def test_zonas_sin_lista() -> None:
    assert zonas("противник атакував 5 ударними БпЛА.") == ()


# --- Variantes encontradas en el histórico --------------------------------------


def test_drones_en_la_frase_siguiente_con_a_takozh() -> None:
    texto = (
        "У ніч на 20 серпня (з 18:00 19 серпня) противник атакував Київщину ракетами Іскандер-М, "
        "двома баражуючими боєприпасами “Бандероль”. А також 168 ударними БпЛА типу Shahed та "
        "дронами-імітаторами із напрямків: Курськ – рф.\n"
        "Станом на 09:30 збито/подавлено 8 крилатих ракет, два баражуючі боєприпаси “Бандероль”, "
        "а також 145 ворожих БпЛА."
    )
    leido = leer(texto, datetime(2026, 8, 20, 7, tzinfo=UTC))
    assert leido.lanzados["total"] == rango(170)
    assert leido.lanzados["otros"] == rango(2)
    assert leido.derribados == rango(147)


def test_recuento_de_medios_detectados_con_vinetas() -> None:
    texto = (
        "У ніч на 27 грудня (з 18:00 26 грудня) противник завдав комбінованого удару із "
        "застосуванням ударних БпЛА та ракет.\n\n"
        "Загалом виявлено та здійснено супровід 559-ти засобів повітряного нападу – 40 ракет та "
        "519 БпЛА різних типів:\n\n"
        "- 40 крилатих ракет Х-101;\n"
        "- 519 ударних БпЛА типу Shahed, Гербера (понад 300 із них – «шахеди») із напрямків "
        "Курськ, Орел – рф.\n\n"
        "Станом на 11:00 збито/подавлено 474 цілі:\n- 30 ракет;\n- 444 ворожі БпЛА."
    )
    leido = leer(texto, datetime(2025, 12, 27, 9, tzinfo=UTC))
    # Las 519 de la cabecera no se suman a las 519 de la viñeta.
    assert leido.lanzados["total"] == rango(519)
    assert leido.lanzados["shahed_geran"] == rango(300, 519)
    assert leido.zonas_lanzamiento == ("Курськ", "Орел")
    assert leido.derribados == rango(444)


def test_salto_de_linea_en_mitad_de_la_frase_y_sufijo_de_caso() -> None:
    texto = (
        "У ніч на 12 жовтня (із 20.00 11 жовтня) противник атакував \n"
        "118-та ударними БпЛА типу Shahed із напрямків: Курськ – рф, близько 50 із них- шахеди.\n"
        "Станом на 09.00 збито/подавлено 103 ворожі БпЛА."
    )
    leido = leer(texto, datetime(2025, 10, 12, 6, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2025-10-11T17:00Z"
    assert leido.lanzados["total"] == rango(118)
    assert leido.zonas_lanzamiento == ("Курськ",)


def test_referencia_al_total_no_se_suma_a_los_derribados() -> None:
    texto = (
        "Протягом дня 27 серпня (із 7.00 по 19.00) противник атакував Україну 140 ударними БпЛА "
        "(понад 100 із них – реактивні).\n"
        "За попередніми даними із 140 БпЛА протиповітряною обороною збито/подавлено 120 дронів."
    )
    leido = leer(texto, datetime(2026, 8, 27, 16, tzinfo=UTC))
    assert leido.derribados == rango(120)
    # Sin otros modelos nombrados, la subcuenta solo fija el mínimo de su modelo.
    assert leido.lanzados["shahed_geran"] == rango(100, 140)
    assert leido.lanzados["gerbera_senuelos"] == rango(0, 140)


def test_cifra_sin_maximo_es_ilegible() -> None:
    texto = "У ніч на 12 травня ворог випустив по Україні понад 200 ударних безпілотників."
    with pytest.raises(ParteIlegible, match="sin máximo"):
        leer(texto, datetime(2026, 5, 12, 12, tzinfo=UTC))


@pytest.mark.parametrize(
    "texto",
    [
        # Balance parcial de un mando regional.
        'Бойова робота Повітряне командування "Захід". В ніч на 7 лютого противник атакував '
        "Захід. Знищено 65 ударних БпЛА.",
        # Pie de vídeo: el periodo y el verbo no van con ninguna cifra de drones.
        "Бойова робота у ніч на 2 червня. Цієї ночі ворог застосував понад 700 засобів, "
        "десятки БпЛА збито.",
    ],
)
def test_no_son_partes_nacionales(texto: str) -> None:
    assert not es_parte(texto)


def test_perdidos_por_guerra_electronica_en_la_misma_frase() -> None:
    texto = (
        "У ніч на 1 червня (із 19.30 31 травня) противник атакував 479-ма засобами:\n"
        "- 472 ударними БпЛА типу Shahed із напрямків: Курськ – рф.;\n"
        "- 3 балістичними ракетами Іскандер-М.\n\n"
        "Станом на 13.30 знешкоджено 385 засобів: 210 ворожих БпЛА та 3 крилаті ракети. "
        "213 — збито вогневими засобами, 172 — локаційно втрачені/подавлені РЕБ."
    )
    leido = leer(texto, datetime(2025, 6, 1, 11, tzinfo=UTC))
    assert leido.lanzados["total"] == rango(472)
    assert leido.derribados == rango(210)
    assert leido.perdidos_guerra_electronica == rango(172)


def test_perdidos_en_vinetas_sin_la_cabecera_ni_los_misiles() -> None:
    texto = (
        "У ніч на 23 червня (із 20.00 22 червня) противник атакував 352 ударними БпЛА типу "
        "Shahed із напрямків: Курськ, Орел – рф  (до 160 із них – шахеди).\n\n"
        "Станом на 09.00 знешкоджено 354 засоби, 158 збито, 196 – локаційно втрачені:\n"
        "- 146 ворожих БпЛА збито вогневими засобами, 193 — локаційно втрачені;\n"
        "- 7 балістичних ракет – збито, ще 3 – локаційно втрачені."
    )
    leido = leer(texto, datetime(2025, 6, 23, 6, tzinfo=UTC))
    assert leido.derribados == rango(146)
    assert leido.perdidos_guerra_electronica == rango(193)
    assert leido.zonas_lanzamiento == ("Курськ", "Орел")


def test_errata_en_el_mes_del_inicio() -> None:
    texto = "У ніч на 3 серпня (із 19.00 2 червня) противник атакував 76 ударними БпЛА."
    leido = leer(texto, datetime(2025, 8, 3, 6, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2025-08-02T16:00Z"
    incoherente = "У ніч на 3 серпня (із 19.00 12 червня) противник атакував 76 ударними БпЛА."
    with pytest.raises(ParteIlegible, match="incoherente"):
        leer(incoherente, datetime(2025, 8, 3, 6, tzinfo=UTC))


def test_las_zonas_acaban_en_la_siguiente_arma() -> None:
    frase = (
        "противник атакував 49-ма ударними БпЛА із напрямків: Міллерово, Брянськ – рф, "
        "Чауда - ТОТ Криму, протикорабельною ракетою Онікс, а також 8-ма БпЛА."
    )
    assert zonas(frase) == ("Міллерово", "Брянськ", "Чауда")


def test_titular_y_cuerpo_no_duplican_los_perdidos() -> None:
    texto = (
        "⚡️ ЗБИТО 52 ВОРОЖІ БПЛА, 44 БЕЗПІЛОТНИКІВ – НЕ ДОСЯГЛИ ЦІЛЕЙ (ЛОКАЦІЙНО ВТРАЧЕНІ)\n"
        "У ніч на 22 грудня 2024 року (із 09.00 21 грудня) противник, атакував 103-ма ударними "
        "БпЛА типу «Shahed».\n"
        "Станом на 10.00 підтверджено збиття 52 ударних БпЛА.\n"
        "44 ворожі безпілотники – локаційно втрачені."
    )
    leido = leer(texto, datetime(2024, 12, 22, 8, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2024-12-21T07:00Z"
    assert leido.derribados == rango(52)
    assert leido.perdidos_guerra_electronica == rango(44)


def test_intervalo_de_una_oleada_y_verbo_zavdav_udaru() -> None:
    texto = (
        "У період із 14.30 по 20.30 7 травня противник завдав удару 31-м ударним БпЛА та "
        "безпілотниками-імітаторами із району Міллерово – рф.\n"
        "Підтверджено збиття 20 ударних БпЛА.\n"
        "6 ворожих безпілотників-імітаторів — локаційно втрачені.\n"
        "Протягом поточної доби 8 травня, станом на 8.00, ударних БпЛА не зафіксовано."
    )
    leido = leer(texto, datetime(2025, 5, 8, 5, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2025-05-07T11:30Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2025-05-07T17:30Z", "precision": "minuto"}
    assert leido.lanzados["total"] == rango(31)
    assert leido.zonas_lanzamiento == ("Міллерово",)


def test_perdidos_sin_maximo_son_desconocidos() -> None:
    texto = (
        "У ніч на 28 листопада 2024 року ворог атакував критичну інфраструктуру. Крім того, "
        "збито три керовані авіаційні ракети та 35 ворожих БпЛА, понад 60 локаційно втрачено."
    )
    leido = leer(texto, datetime(2024, 11, 28, 12, tzinfo=UTC))
    assert leido.derribados == rango(35)
    assert leido.perdidos_guerra_electronica == DESCONOCIDO


def test_errata_en_el_dia_del_inicio() -> None:
    texto = "У ніч на 15 листопада 2024 року (із 21.00 15 листопада) противник атакував 29 БпЛА."
    leido = leer(texto, datetime(2024, 11, 15, 6, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2024-11-14T19:00Z"


def test_coma_tras_el_dia_de_la_noche() -> None:
    texto = "У ніч на 01, березня (з 18:00 28 лютого) противник атакував 123 ударними БпЛА."
    assert es_parte(texto)
    assert leer(texto, datetime(2026, 3, 1, 6, tzinfo=UTC)).lanzados["total"] == rango(123)


def test_formato_2024_con_medios_detectados_y_fechas_numericas() -> None:
    texto = (
        "⚡️ ЗБИТО 66 УДАРНИХ БПЛА\n"
        "У ніч на 24 вересня 2024 року (із 20.00 23.09 по 07.00 24.09) радіотехнічними військами "
        "Повітряних Сил виявлено та здійснено супровід 81 ударного БплА типу «Shahed» із "
        "напрямків: Курськ, Приморсько- Ахтарськ – рф.\n"
        "Станом на 09.00 збито 66 ударних БпЛА."
    )
    assert es_parte(texto)
    leido = leer(texto, datetime(2024, 9, 24, 5, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2024-09-23T17:00Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2024-09-24T04:00Z", "precision": "minuto"}
    assert leido.lanzados["shahed_geran"] == rango(81)
    assert leido.zonas_lanzamiento == ("Курськ", "Приморсько-Ахтарськ")
    assert leido.derribados == rango(66)


def test_reconocimiento_fuera_y_titular_solo_si_el_cuerpo_calla() -> None:
    texto = (
        "⚡️ ЗБИТО РАКЕТУ Х-59/69 ТА 11 БПЛА РІЗНИХ ТИПІВ\n"
        "У ніч на 27 липня 2024 року ворог атакував керованою авіаційною ракетою Х-59 та "
        "чотирма ударними БпЛА «Shahed» із Приморсько-Ахтарська – рф.\n"
        "💥 Усі цілі було збито силами та засобами Сил оборони України.\n"
        "Крім того, знищено ще вісім повітряних цілей: 4 розвідувальні БпЛА «Supercam»."
    )
    leido = leer(texto, datetime(2024, 7, 27, 5, tzinfo=UTC))
    assert leido.lanzados["total"] == rango(4)
    assert leido.derribados == rango(4)


def test_total_con_vinetas_y_numeros_en_letras() -> None:
    texto = (
        "У ніч на 12 червня 2024 року окупанти завдали ракетно-авіаційного удару по Україні.\n"
        "Усього – 30 засобів повітряного нападу:\n"
        "- 4 крилаті ракети Х-101;\n"
        "- одинадцять ударних БпЛА «Shahed-131/136» із Курської обл. – рф.\n"
        "💥 Збили 11 ударних БпЛА."
    )
    leido = leer(texto, datetime(2024, 6, 12, 5, tzinfo=UTC))
    assert leido.lanzados["total"] == rango(11)
    assert leido.derribados == rango(11)


# --- 2022 y 2023 ------------------------------------------------------------------


def test_2022_uno_chi_con_numeros_en_letras() -> None:
    texto = (
        "ЗБИТО П’ЯТЬ ІЗ СЕМИ ДРОНІВ-КАМІКАДЗЕ\n"
        "2 жовтня уночі російські окупаційні війська атакували Миколаївщину сімома "
        'дронами-камікадзе "Shahed-136".\n'
        'П’ять із семи "Shahed-136" знищено.'
    )
    leido = leer(texto, datetime(2022, 10, 2, 5, tzinfo=UTC))
    assert leido.inicio.precision == "aproximada"
    assert leido.lanzados["shahed_geran"] == rango(7)
    assert leido.derribados == rango(5)
    assert leido.regiones == ("UA-48",)


def test_2022_intervalo_hasta_medianoche() -> None:
    texto = "29 вересня з 23.00 по 24.00 окупанти атакували сімома дронами-камікадзе Shahed-136."
    leido = leer(texto, datetime(2022, 9, 29, 22, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2022-09-29T20:00Z"
    assert leido.fin.documento()["valor"] == "2022-09-29T21:00Z"


def test_firma_de_un_mando_regional_no_es_parte_nacional() -> None:
    texto = (
        "Уночі 5 жовтня окупанти атакували Україну сімома Shahed-136. П’ять знищено.\n"
        'Повітряне командування "Південь"'
    )
    assert not es_parte(texto)


def test_2023_intervalo_entre_dias_y_como_mucho() -> None:
    texto = (
        "ЗНИЩЕНО 14 «ШАХЕДІВ»\n"
        "Із 18.30 25 грудня по 03.00 26 грудня 2023 року противник атакував ударними БпЛА.\n"
        "Загалом зафіксовано до 17 пусків ударних БпЛА з району Приморсько-Ахтарськ.\n"
        "Усі ворожі БпЛА знищено."
    )
    leido = leer(texto, datetime(2023, 12, 26, 5, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2023-12-25T16:30Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2023-12-26T01:00Z", "precision": "minuto"}
    assert leido.lanzados["total"] == rango(0, 17)
    # "Усі ворожі БпЛА" son como mucho los 17 lanzados.
    assert leido.derribados == rango(17)


def test_2023_fecha_y_reconocimiento_no_son_cifras() -> None:
    texto = (
        "1 листопада уночі збито шість дронів-камікадзе Shahed-136, які атакували Україну.\n"
        "Крім того, у ніч на 16 травня противник атакував ударними дронами, а також проводив "
        "повітряну розвідку трьома безпілотниками."
    )
    leido = leer(texto, datetime(2022, 11, 1, 6, tzinfo=UTC))
    assert leido.lanzados["total"] == DESCONOCIDO
    assert leido.derribados == rango(6)


def test_2023_zonas_antes_de_la_cifra_y_entre_parentesis() -> None:
    antes = (
        "У ніч на 14 листопада 2023 року окупанти атакували Україну.\n"
        "Із району Приморсько-Ахтарськ (Краснодарський край -рф) зафіксовано пуски 9 ударних "
        "БпЛА «Shahed-136/131»."
    )
    assert leer(antes, datetime(2023, 11, 14, 6, tzinfo=UTC)).zonas_lanzamiento == (
        "Приморсько-Ахтарськ",
    )
    parentesis = (
        "У ніч на 28 січня 2024 року ворог атакував 8-ма ударними БпЛА типу «Shahed-136/131» з "
        "південно-східного напрямку (Приморсько-Ахтарськ – рф.), двома ракетами «Іскандер-М» з "
        "району Воронезької області."
    )
    leido = leer(parentesis, datetime(2024, 1, 28, 6, tzinfo=UTC))
    assert leido.zonas_lanzamiento == ("Приморсько-Ахтарськ",)
