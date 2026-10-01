"""Capa de guerra con lugar: formas declinadas, nomenclátor, lectura de mensajes reales
(recortados) de cada tipo de canal, en ucraniano y en ruso, y restricciones de Rosaviatsia."""

from datetime import UTC, date, datetime

import pytest

from proceso import restricciones
from proceso.declinacion import formas
from proceso.mensajes_guerra import analizar, dia_declarado, noche_declarada
from recogida.guerra import raices_regiones
from tests.nomenclator_falso import nomenclator

N = nomenclator()
PUBLICADO = datetime(2026, 10, 1, 6, 45, tzinfo=UTC)
JARKOV = frozenset({"UA-63"})
DNIPRO = frozenset({"UA-12"})
BELGOROD = frozenset({"RU-BEL"})


# --- Formas declinadas ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "idioma", "forma"),
    [
        ("Харків", "uk", "харкові"),
        ("Харків", "uk", "харкова"),
        ("Київ", "uk", "києві"),
        ("Одеса", "uk", "одесі"),
        ("Суми", "uk", "сумах"),
        ("Чернівці", "uk", "чернівцях"),
        ("Марганець", "uk", "марганцю"),
        ("Бориспіль", "uk", "борисполі"),
        ("Олександрівка", "uk", "олександрівці"),
        ("Покровське", "uk", "покровському"),
        ("Біла Церква", "uk", "білій церкві"),
        ("Белгород", "ru", "белгороде"),
        ("Брянск", "ru", "брянске"),
        ("Ярославль", "ru", "ярославле"),
        ("Старый Оскол", "ru", "старом осколе"),
        ("Кривий Ріг", "uk", "кривому розі"),
    ],
)
def test_formas_declinadas(nombre: str, idioma: str, forma: str) -> None:
    assert forma in formas(nombre, idioma)


def test_nombres_en_e_no_se_declinan() -> None:
    assert formas("Туапсе", "ru") == {"туапсе"}


# --- Nomenclátor ---------------------------------------------------------------------------


def _nombres(texto: str, regiones: frozenset[str] | None) -> list[str | None]:
    return [h.lugar.nombre if h.lugar else None for h in N.localidades_en(texto, regiones)]


def test_localidad_declinada_en_su_oblast() -> None:
    assert _nombres("Пошкоджено будинки у Чугуєві.", JARKOV) == ["Чугуїв"]


def test_localidad_de_otra_region_no_sale() -> None:
    assert _nombres("В Белгороде повреждены дома", JARKOV) == []
    assert _nombres("В Белгороде повреждены дома", BELGOROD) == ["Белгород"]


def test_homonimos_se_resuelven_con_el_distrito() -> None:
    sin_distrito = N.localidades_en("Влучання у Малинівці.", JARKOV)
    assert sin_distrito[0].lugar is None
    assert sin_distrito[0].motivo == "ambiguo"
    assert len(sin_distrito[0].candidatos) == 2
    con_distrito = _nombres("Влучання у Малинівці Чугуївського району.", JARKOV)
    assert con_distrito == ["Малинівка"]


def test_homonimos_se_resuelven_con_la_comunidad() -> None:
    assert _nombres("Пошкоджено будинок у Малинівці, Малинівська громада.", JARKOV) == ["Малинівка"]


def test_palabra_corriente_solo_con_su_tipo_de_lugar() -> None:
    assert _nombres("Мирне населення постраждало від атаки.", DNIPRO) == []
    assert _nombres("Пошкоджено будинок у селі Мирне.", DNIPRO) == ["Мирне"]


def test_nombre_de_pais_nunca_es_localidad() -> None:
    assert _nombres("Україна вистояла. Атака на Україна.", DNIPRO) == []


def test_minuscula_no_es_nombre_de_lugar() -> None:
    assert _nombres("харків", JARKOV) == []


def test_unidad_administrativa_no_es_la_localidad() -> None:
    # «Чугуївський район»: el distrito, no la ciudad.
    assert _nombres("У Чугуївському районі пошкоджено лінію електропередачі.", JARKOV) == []


def test_distrito_urbano_es_la_ciudad() -> None:
    assert _nombres("В Київському районі зафіксовано влучання ворожого БпЛА.", JARKOV) == ["Харків"]


def test_territorio_ocupado_con_codigo_de_ucrania() -> None:
    hallado = N.localidades_en("В Феодосии повреждена нефтебаза", frozenset({"UA-43"}))
    assert hallado[0].lugar is not None
    assert hallado[0].lugar.region == "UA-43"
    assert hallado[0].lugar.pais == "UA"


# --- Mensajes -------------------------------------------------------------------------------


def test_administracion_ucraniana_dron_en_la_ciudad() -> None:
    # t.me/kharkivoda/31198 (1 de octubre de 2026).
    texto = (
        "🔻Окупанти вдарили дроном по Київському району Харкова. \n\nПопередньо, влучання — у "
        "землю на відкритій території. \n\nПошкоджено 5 автомобілів. \n\nПрофільні служби "
        "працюють на місці обстрілу."
    )
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert [i.lugar.nombre for i in leido.impactos] == ["Харків"]
    assert leido.impactos[0].tipo == "impacto"
    assert not leido.para_extractor


def test_solo_misiles_no_se_registra() -> None:
    texto = "Ворог завдав ракетного удару по Харкову. Пошкоджено будинки."
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert leido.motivo == "sin_dron"
    texto = "Ворог завдав ракетного удару по Чугуєву, пошкоджено будинки. Над областю збито 3 БпЛА."
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert leido.impactos == []
    assert leido.derribados == 3


def test_frase_con_drones_y_misiles_va_al_extractor() -> None:
    texto = "Ворог атакував Нікополь дронами та артилерією. Пошкоджено приватний будинок."
    leido = analizar(texto, PUBLICADO, N, DNIPRO)
    assert leido.impactos == []
    assert leido.para_extractor


def test_arma_de_la_frase_anterior() -> None:
    texto = (
        "Вночі ворог атакував область ударними БпЛА. Пошкоджено будинки в Нікополі та "
        "Марганці. Також ракетою пошкоджено склад у Мирному."
    )
    leido = analizar(texto, PUBLICADO, N, DNIPRO)
    assert sorted(i.lugar.nombre for i in leido.impactos) == ["Марганець", "Нікополь"]
    assert leido.es_noche


def test_aviso_de_alarma_no_es_ataque() -> None:
    # t.me/kyivoda/59511.
    texto = "🟡 Чугуївський район — повітряна тривога, жовтий рівень: Дронова загроза"
    assert analizar(texto, PUBLICADO, N, JARKOV).motivo == "aviso"


def test_solo_derribos_no_da_lugares() -> None:
    texto = "Протягом ночі над Харківщиною збито 12 ворожих БпЛА. Над Чугуєвом знищено 2 дрони."
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert leido.impactos == []
    assert leido.derribados == 12


def test_caida_de_restos() -> None:
    texto = (
        "Внаслідок падіння уламків збитого БпЛА у Чугуєві пошкоджено приватний будинок. "
        "Постраждалих немає."
    )
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert [(i.lugar.nombre, i.tipo) for i in leido.impactos] == [("Чугуїв", "restos")]
    assert "residencial" in leido.impactos[0].categorias
    assert leido.heridos is None


def test_victimas_sin_confundir_fechas_ni_edades() -> None:
    # t.me/khersonskaODA/68788, con otro lugar.
    texto = (
        "❗️До лікарні звернулись двоє людей, які вночі 29 вересня постраждали через атаку "
        "російського дрона у Чугуєві. У 81-річної жінки та 31-річного чоловіка діагностували "
        "вибухову травму."
    )
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert leido.heridos != 29
    assert leido.dia == date(2026, 9, 29)
    assert [i.lugar.nombre for i in leido.impactos] == ["Чугуїв"]


def test_gobernador_ruso() -> None:
    texto = (
        "В результате атаки БПЛА в Шебекино повреждены два частных дома и автомобиль. "
        "Ранен мужчина, ему оказывается помощь."
    )
    leido = analizar(texto, PUBLICADO, N, BELGOROD)
    assert [i.lugar.nombre for i in leido.impactos] == ["Шебекино"]
    assert leido.impactos[0].heridos == 1
    assert "residencial" in leido.impactos[0].categorias


def test_estado_mayor_refineria_con_nombre_entre_comillas() -> None:
    # t.me/GeneralStaffZSU/41981 (22 de agosto de 2026).
    texto = (
        "У ніч на 22 серпня 2026 року підрозділи Сил оборони України уразили потужності "
        "нафтопереробного заводу «Новокуйбишевський» у Самарській області рф. Зафіксовано "
        "пожежу. Також застосовувалися ударні БпЛА."
    )
    publicado = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
    leido = analizar(texto, publicado, N, None, raices_regiones())
    assert [(i.lugar.id, i.lugar.nivel) for i in leido.impactos] == [("osm:way/2", "instalacion")]
    assert leido.noche == date(2026, 8, 22)
    assert "combustible" in leido.impactos[0].categorias


def test_refineria_por_el_adjetivo_de_la_ciudad() -> None:
    texto = "Беспилотники атаковали Рязанский НПЗ, возник пожар."
    leido = analizar(texto, PUBLICADO, N, frozenset({"RU-RYA"}))
    assert [i.lugar.id for i in leido.impactos] == ["osm:way/1"]


def test_autoridad_de_ocupacion_en_crimea() -> None:
    texto = "В Феодосии в результате атаки БПЛА произошло возгорание на нефтебазе."
    leido = analizar(texto, PUBLICADO, N, frozenset({"UA-43"}))
    assert [i.lugar.id for i in leido.impactos] == ["osm:way/4"]
    assert leido.impactos[0].lugar.region == "UA-43"


def test_noche_y_dia_declarados() -> None:
    assert noche_declarada("В ночь на 1 октября атаковали", PUBLICADO) == date(2026, 10, 1)
    # Una noche más de un día después de la publicación es del año anterior.
    assert noche_declarada("В ночь на 5 октября атаковали", PUBLICADO) == date(2025, 10, 5)
    assert dia_declarado("26 сентября был атакован", PUBLICADO) == date(2026, 9, 26)
    assert dia_declarado("сегодня, 1 жовтня", PUBLICADO) is None


# --- Rosaviatsia -----------------------------------------------------------------------------


def test_restriccion_y_levantamiento() -> None:
    # t.me/favt_info/8287 y 8289.
    inicio = restricciones.leer(
        "▫️Аэропорт КАЛУГА (Грабцево)  ✈️ВВЕДЕНЫ временные ограничения на прием и выпуск "
        "воздушных судов.", datetime(2026, 9, 30, 16, 47, tzinfo=UTC),
    )  # fmt: skip
    fin = restricciones.leer(
        "⬜️Аэропорт КАЛУГА (Грабцево) ✈️СНЯТЫ ограничения на прием и выпуск воздушных судов.",
        datetime(2026, 10, 1, 3, 42, tzinfo=UTC),
    )
    assert inicio is not None and inicio.accion == "inicio"
    assert inicio.aeropuertos == ("КАЛУГА (Грабцево)",)
    assert fin is not None and fin.accion == "fin"


def test_varios_aeropuertos_y_formato_antiguo() -> None:
    varios = restricciones.leer(
        "▫️Аэропорты  – ПЕНЗА  – САРАТОВ (Гагарин)  ✈️ВВЕДЕНЫ временные ограничения",
        PUBLICADO,
    )
    assert varios is not None and varios.aeropuertos == ("ПЕНЗА", "САРАТОВ (Гагарин)")
    antiguo = restricciones.leer(
        "Для обеспечения безопасности полетов временные ограничения на их прием и выпуск с 04:45 "
        "МСК введены в аэропорту Калуга (Грабцево; код ИКАО: UUBC).",
        datetime(2025, 5, 24, 2, 0, tzinfo=UTC),
    )
    assert antiguo is not None
    assert antiguo.oaci == ("UUBC",)
    assert antiguo.hora == datetime(2025, 5, 24, 1, 45, tzinfo=UTC)


def test_vuelos_por_acuerdo_no_es_restriccion() -> None:
    texto = (
        "🟡 Аэропорт ДОМОДЕДОВО принимает и отправляет рейсы по согласованию с соответствующими "
        "органами в связи с введением ограничений"
    )
    assert restricciones.leer(texto, PUBLICADO) is None


def test_aeropuerto_en_el_nomenclator() -> None:
    lugar = restricciones.aeropuerto("КАЛУГА (Грабцево)", N)
    assert lugar is not None and lugar.oaci == "UUBC"


def test_parte_diario_por_frase_y_sin_ataque_concreto() -> None:
    # t.me/zoda_gov_ua/47911, recortado.
    texto = (
        "Упродовж доби окупанти завдали 391 удар по 16 населених пунктах. \n▪️Ворог наніс 10 "
        "ракетних ударів по Нікополю. \n▪️286 БпЛА різної модифікації (переважно FPV) атакували "
        "Марганець. \nНадійшло 382 повідомлення про пошкодження будинків."
    )
    leido = analizar(texto, PUBLICADO, N, DNIPRO)
    assert [i.lugar.nombre for i in leido.impactos] == ["Марганець"]
    assert leido.parte_diario
    assert leido.dia == date(2026, 9, 30)


def test_la_ciudad_frente_a_aldeas_homonimas() -> None:
    from proceso.lugares_guerra import Nomenclator
    from tests.nomenclator_falso import LOCALIDADES, _loc

    aldea = _loc("katotth:UA23000000000000001", "Запоріжжя", "UA", "UA-23", 47.5, 35.5)
    ciudad = _loc("katotth:UA23060150010069720", "Запоріжжя", "UA", "UA-23", 47.84, 35.14,
                  categoria="ciudad", radio_km=10.0)  # fmt: skip
    nomenclator = Nomenclator.desde_datos({"localidades": [*LOCALIDADES, aldea, ciudad]})
    (hallado,) = nomenclator.localidades_en("Дрон атакував Запоріжжя.", frozenset({"UA-23"}))
    assert hallado.lugar is not None and hallado.lugar.categoria == "ciudad"


def test_el_parte_de_derribos_del_estado_mayor_no_da_lugares() -> None:
    # t.me/GeneralStaffZSU/42432: los lugares son zonas de lanzamiento de un ataque ruso.
    texto = (
        "⚡️ ЗБИТО/ПОДАВЛЕНО 87 ВОРОЖИХ БПЛА У ніч на 01 жовтня противник атакував 107 ударними "
        "БпЛА типу Shahed із напрямків: Орел, Брянськ, Курськ – рф. Зафіксовано влучання."
    )
    leido = analizar(texto, PUBLICADO, N, None, raices_regiones(), reivindicacion=True)
    assert leido.impactos == []


def test_el_dron_como_objetivo_no_es_un_ataque_con_drones() -> None:
    texto = "У Харкові уражено склад БпЛА противника."
    assert analizar(texto, PUBLICADO, N, JARKOV).motivo == "sin_dron"


def test_lista_de_distritos_no_es_un_pueblo() -> None:
    texto = (
        "Над регионом сбиты 5 БПЛА. Места падения обломков зафиксированы на территории "
        "Шебекинского и Белгородского районов."
    )
    leido = analizar(texto, PUBLICADO, N, BELGOROD)
    assert leido.impactos == []


def test_una_visita_posterior_no_es_un_ataque() -> None:
    texto = "Навестил пострадавших в результате атаки БПЛА на Шебекино, ранены двое."
    assert analizar(texto, PUBLICADO, N, BELGOROD).motivo == "retrospectivo"


def test_reivindicacion_sin_arma_no_es_un_ataque_con_drones() -> None:
    # t.me/GeneralStaffZSU/42388: «БпЛА» solo como objetivo; el arma no consta.
    texto = (
        "У Донецьку Донецької області уражено місце зберігання, підготовки та пуску ударних "
        "БпЛА. Також у Луганську уражено два склади боєприпасів."
    )
    leido = analizar(texto, PUBLICADO, N, None, raices_regiones(), reivindicacion=True)
    assert leido.motivo == "sin_dron"
