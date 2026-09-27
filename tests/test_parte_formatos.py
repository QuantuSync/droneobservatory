"""Formatos de parte encontrados en la auditoría de cobertura, con fixtures breves."""

from datetime import UTC, datetime

import pytest

from recogida.parte import Derribo, es_parte, leer


def rango(minimo: int, maximo: int | None = None) -> dict[str, int]:
    return {"min": minimo, "max": minimo if maximo is None else maximo}


# --- Periodo --------------------------------------------------------------------


def test_noche_con_mes_y_anio_en_los_dos_dias() -> None:
    texto = (
        "У ніч з 31 грудня 2022 на 1 січня 2023 року окупанти атакували Україну БпЛА.\n"
        "Знищено 45 ударних БпЛА."
    )
    assert es_parte(texto)
    leido = leer(texto, datetime(2023, 1, 1, 6, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2022-12-31T16:00Z", "precision": "aproximada"}
    assert leido.derribados == rango(45)


def test_noche_de_un_mes_a_otro_sin_anio() -> None:
    texto = "У ніч з 28 лютого на 1 березня ворог атакував Україну. Усі чотири БпЛА знищено."
    assert es_parte(texto)
    assert leer(texto, datetime(2023, 3, 1, 6, tzinfo=UTC)).derribados == rango(4)


@pytest.mark.parametrize(
    "texto",
    [
        "Сьогодні вночі противник атакував Сумщину двома ударними БпЛА. Обидва знищено.",
        "⚡️Цієї ночі ворог застосував чотири ударні БпЛА типу «Shahed-136/131».",
        "У новорічну ніч 2024 року ворог застосував 90 ударних БпЛА типу «Shahed».",
    ],
)
def test_noche_relativa_es_la_de_la_publicacion(texto: str) -> None:
    assert es_parte(texto)
    leido = leer(texto, datetime(2024, 1, 1, 6, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2023-12-31T16:00Z", "precision": "aproximada"}


def test_noche_relativa_con_inicio_explicito() -> None:
    texto = (
        "Протягом ночі (з 00:10 13 квітня) противник атакував 98 ударними БпЛА типу Shahed.\n"
        "За попередніми даними, станом на 08:00, збито/подавлено 87 ворожих БпЛА."
    )
    leido = leer(texto, datetime(2026, 4, 13, 5, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2026-04-12T21:10Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2026-04-13T05:00Z", "precision": "minuto"}


@pytest.mark.parametrize(
    "texto",
    [
        # Aviso previo sin cifras.
        "❗️Цієї ночі ворог випустив рекордну кількість ударних БпЛА. Найближчим часом повідомимо.",
        # Cita en mitad de un reportaje.
        "Коли ми пишемо: «цієї ночі виявлено понад 150 повітряних цілей», це робота РТВ. БпЛА.",
        # Pie de vídeo.
        "💥 На відео – бойова робота у ніч на 2 червня. Ворог застосував 700 засобів, 50 БпЛА.",
    ],
)
def test_noche_relativa_sin_cifra_o_pie_de_video_no_es_parte(texto: str) -> None:
    assert not es_parte(texto)


def test_noche_con_fecha_numerica_corta() -> None:
    texto = "У ніч на 24.03.23 противник атакував Україну 6 ударними безпілотниками «Shahed»."
    leido = leer(texto, datetime(2023, 3, 24, 7, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2023-03-23T16:00Z"
    assert leido.lanzados["total"] == rango(6)


@pytest.mark.parametrize(
    ("texto", "inicio", "fin"),
    [
        (
            "Із 20.00 вечора 5-го до опівночі 6-го листопада 2023 року окупанти атакували "
            "Україну 22 ударними БпЛА.",
            {"valor": "2023-11-05T18:00Z", "precision": "minuto"},
            {"valor": "2023-11-05T22:00Z", "precision": "minuto"},
        ),
        (
            "Із 20-ї години 17-го по 04 годину 18 листопада 2023 року російські окупанти "
            "атакували Україну 38 ударними БпЛА.",
            {"valor": "2023-11-17T18:00Z", "precision": "minuto"},
            {"valor": "2023-11-18T02:00Z", "precision": "minuto"},
        ),
        (
            "Із вечора 13 липня по 4 ранку 14 липня 2023 року рашисти атакували Україну 17-ма "
            "ударними безпілотниками.",
            {"valor": "2023-07-13T15:00Z", "precision": "aproximada"},
            {"valor": "2023-07-14T01:00Z", "precision": "minuto"},
        ),
        (
            "Чергова атака розпочалась 25 травня о 22.00 і тривала до 5.00 26 травня. Загалом "
            "зафіксовано пуски 31 ударного БпЛА.",
            {"valor": "2023-05-25T19:00Z", "precision": "minuto"},
            {"valor": "2023-05-26T02:00Z", "precision": "minuto"},
        ),
    ],
)
def test_rangos_con_horas_en_palabras(
    texto: str, inicio: dict[str, str], fin: dict[str, str]
) -> None:
    assert es_parte(texto)
    leido = leer(texto, datetime(2023, 11, 20, 6, tzinfo=UTC))
    assert (leido.inicio.documento(), leido.fin.documento()) == (inicio, fin)


def test_intervalo_de_un_dia_sin_la_palabra_periodo() -> None:
    texto = (
        "З 00.00 год по 05.00 год 29 травня 2023 року російські окупанти атакували Україну "
        "ударними дронами. Усього – близько 35 ударних дронів."
    )
    leido = leer(texto, datetime(2023, 5, 29, 5, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2023-05-28T21:00Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2023-05-29T02:00Z", "precision": "minuto"}


def test_noche_con_intervalo_sin_parentesis() -> None:
    texto = (
        "У ніч на 30 травня 2023 року з 23.30 по 4.30 окупанти атакують Україну. Загалом "
        "зафіксовано пуски 31 дрона-камікадзе. Знищено 29 ударних БпЛА."
    )
    assert es_parte(texto)
    leido = leer(texto, datetime(2023, 5, 30, 5, tzinfo=UTC))
    assert leido.inicio.documento()["valor"] == "2023-05-29T20:30Z"
    assert leido.fin.documento()["valor"] == "2023-05-30T01:30Z"
    assert (leido.lanzados["total"], leido.derribados) == (rango(31), rango(29))


def test_inicio_entre_parentesis_tras_iz() -> None:
    texto = "У ніч на 22 квітня 2025 року із (21.00 21 квітня) противник атакував 54-ма БпЛА."
    leido = leer(texto, datetime(2025, 4, 22, 6, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2025-04-21T18:00Z", "precision": "minuto"}


@pytest.mark.parametrize(
    ("texto", "inicio"),
    [
        ("10 лютого 2023 року противник завдав ударів. Застосовано сім дронів-камікадзе.",
         "2023-02-09T22:00Z"),
        ("На початку доби 7 лютого 2024 року противник здійснив кілька ударів: 20 ударних БпЛА.",
         "2024-02-06T22:00Z"),
        ("У вечірній час 10 лютого 2023 року окупанти атакували Україну 20 ударними БпЛА.",
         "2023-02-09T22:00Z"),
    ],
)  # fmt: skip
def test_fecha_de_dia_sin_hora(texto: str, inicio: str) -> None:
    assert es_parte(texto)
    leido = leer(texto, datetime(2024, 2, 7, 8, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": inicio, "precision": "dia"}


def test_fecha_con_franja_de_dia_y_derribados_como_minimo() -> None:
    texto = (
        "❗️18 серпня 2026 року протягом денної пори (з 07.00 по 18.30) ворог завдав удару по "
        "Україні 76 реактивними БпЛА типу Shahed.\n"
        "За попередніми даними вдалося збити та подавити понад 70 реактивних БпЛА."
    )
    leido = leer(texto, datetime(2026, 8, 18, 17, tzinfo=UTC))
    assert leido.inicio.documento() == {"valor": "2026-08-18T04:00Z", "precision": "minuto"}
    assert leido.fin.documento() == {"valor": "2026-08-18T15:30Z", "precision": "minuto"}
    # "Понад 70" de 76 lanzados: entre 70 y 76.
    assert leido.derribados == rango(70, 76)


# --- Detección ------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "У ніч на 18 жовтня 2024 року противник атакує Україну ударними БпЛА. Виявлено 135 БпЛА.",
        "Із 14.00 12 грудня по 10.00 13 грудня 2024 року противник здійснив комбінований "
        "повітряний напад. Загалом виявлено 193 БпЛА.",
        "У ніч на 15 січня 2025 року окупанти здійснили комбінований удар ракетами та 74 БпЛА.",
        "У ніч на 2 січня 2023 року окупанти завдали масованого удару 39 ударними БпЛА.",
        "Уночі 11 червня 2023 року атаковано прифронтові зони. Знищено шість ударних дронів.",
        # Falta el verbo: "противник 104-ма ударними БпЛА".
        "У ніч на 25 серпня (із 19.00 24 серпня) противник 104-ма ударними БпЛА типу Shahed.",
        # Solo "N із M" junto al periodo.
        "У ніч на 16 березня 2024 року Силами оборони знищено 2 із 2 ударних БпЛА типу «Shahed».",
    ],
)
def test_verbos_de_ataque_nuevos(texto: str) -> None:
    assert es_parte(texto)


def test_firma_regional_solo_al_principio_de_linea() -> None:
    nacional = (
        'Вночі 6 травня 2023 року противник атакував "шахедами". Окупанти застосували вісім '
        'ударних дронів. Усі – знищено силами та засобами Повітряне командування "Схід".'
    )
    assert es_parte(nacional)
    regional = "У ніч на 14 липня противник атакував 4 БпЛА.\n#повітряне_командування_Південь"
    assert not es_parte(regional)


# --- Cifras ---------------------------------------------------------------------


def test_numeros_compuestos() -> None:
    texto = (
        "У ніч на 8 травня 2023 року противник атакував Київщину. Було застосовано 35 ударних "
        "БпЛА. Знищено усі тридцять п’ять «Shahed-136/131»."
    )
    assert leer(texto, datetime(2023, 5, 8, 4, tzinfo=UTC)).derribados == rango(35)


def test_drones_de_reconocimiento_ots_fuera() -> None:
    texto = (
        "Уранці 3-го липня 2024 року противник завдав удару 5-ма ударними БпЛА типу «Shahed».\n"
        "Збито 6 повітряних цілей:\n- 5 ударних БпЛА «Shahed-131/136»;\n- 1 БпЛА ОТР «Орлан-10»."
    )
    assert leer(texto, datetime(2024, 7, 3, 8, tzinfo=UTC)).derribados == rango(5)


def test_solo_el_titular_da_los_derribados() -> None:
    texto = (
        "⚡️ЗНИЩЕНО ДВА УДАРНИХ БПЛА\n"
        "У ніч на 4 січня 2024 року ворог атакував двома ударними БпЛА. Обидва – знищені."
    )
    assert leer(texto, datetime(2024, 1, 4, 6, tzinfo=UTC)).derribados == rango(2)


# --- Derribados o neutralizados -------------------------------------------------


def test_una_sola_cifra_para_derribados_y_neutralizados() -> None:
    texto = (
        "У ніч на 26 вересня (з 18:00 25 вересня) противник атакував 173 ударними БпЛА.\n"
        "Станом на 07:30 збито/подавлено 134 ворожі БпЛА."
    )
    leido = leer(texto, datetime(2026, 9, 26, 5, tzinfo=UTC))
    assert leido.derribados == rango(134)
    assert leido.derribados_categoria is Derribo.DERRIBADOS_O_NEUTRALIZADOS


def test_derribados_separados_de_la_guerra_electronica() -> None:
    texto = (
        "У ніч на 9 грудня (з 19:00 8 грудня) противник атакував 50-ма ударними БпЛА.\n"
        "Станом на 09:00 підтверджено збиття 23 ударних БпЛА; 22 ворожі БпЛА – локаційно втрачені."
    )
    leido = leer(texto, datetime(2024, 12, 9, 7, tzinfo=UTC))
    assert leido.derribados_categoria is Derribo.DERRIBADOS
