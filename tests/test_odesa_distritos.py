"""Odesa casi sin impactos (docs/informe_odesa.md): el distrito como lugar cuando el mensaje no
nombra otro, con su radio real y nivel «distrito»; la ciudad del canal de una administración
municipal («по місту»); el ataque con drones sobre un lugar; «внаслідок обстрілу» en un mensaje
que solo nombra drones, y «ушкоджено». Con las protecciones de siempre."""

from datetime import UTC, datetime
from typing import Any

from proceso.lugares_guerra import RADIO_MAX_UNIDAD_KM, Nomenclator
from proceso.mensajes_guerra import analizar
from recogida.canales_guerra import cargar_canales

PUBLICADO = datetime(2026, 2, 15, 6, 0, tzinfo=UTC)
ODESA = frozenset({"UA-51"})
KIEV = frozenset({"UA-30"})


def _loc(
    id_: str, nombre: str, region: str, lat: float, lon: float, **extra: Any
) -> dict[str, Any]:
    return {
        "id": id_, "nombre": nombre, "pais": "UA", "region": region,
        "categoria": extra.pop("categoria", "aldea"), "lat": lat, "lon": lon,
        "radio_km": extra.pop("radio_km", 1.5), "nombres": {"uk": [nombre]},
        "origen_punto": "prueba", **extra,
    }  # fmt: skip


# Dos distritos de 2020 de Odesa, más anchos que el tope de una comunidad: el de Odesa (la ciudad
# y Biliaivka, a unos 40 km) y el de Izmaíl (Reni, Kilia y Vylkove, a 35, 35 y 60 km de Izmaíl).
N = Nomenclator.desde_datos(
    {
        "localidades": [
            _loc(
                "ua:odesa",
                "Одеса",
                "UA-51",
                46.48,
                30.72,
                categoria="ciudad",
                radio_km=12.0,
                raion="Одеський",
                hromada="Одеська",
            ),
            _loc(
                "ua:biliaivka",
                "Біляївка",
                "UA-51",
                46.48,
                30.20,
                categoria="ciudad",
                radio_km=3.0,
                raion="Одеський",
                hromada="Біляївська",
            ),
            _loc(
                "ua:izmail",
                "Ізмаїл",
                "UA-51",
                45.35,
                28.84,
                categoria="ciudad",
                radio_km=5.0,
                raion="Ізмаїльський",
                hromada="Ізмаїльська",
            ),
            _loc(
                "ua:reni",
                "Рені",
                "UA-51",
                45.46,
                28.29,
                categoria="ciudad",
                radio_km=3.0,
                raion="Ізмаїльський",
                hromada="Ренійська",
            ),
            _loc(
                "ua:kilia",
                "Кілія",
                "UA-51",
                45.45,
                29.27,
                categoria="ciudad",
                radio_km=3.0,
                raion="Ізмаїльський",
                hromada="Кілійська",
            ),
            _loc(
                "ua:vylkove",
                "Вилкове",
                "UA-51",
                45.40,
                29.59,
                categoria="ciudad",
                radio_km=2.0,
                raion="Ізмаїльський",
                hromada="Вилківська",
            ),
            # Una aldea que se llama como el jefe de la administración de Odesa.
            _loc("ua:oleh", "Олег", "UA-51", 46.90, 30.10, raion="Одеський", hromada="Одеська"),
            _loc("ua:kyiv", "Київ", "UA-30", 50.45, 30.52, categoria="ciudad", radio_km=15.0),
        ],
        "instalaciones": [],
        "distritos_urbanos": [{"nombre": "Приморський", "ciudad": "ua:odesa", "region": "UA-51"}],
    }
)


def _lugares(
    texto: str, regiones: frozenset[str] = ODESA, ciudad: str | None = None
) -> list[tuple[str, str]]:
    leido = analizar(texto, PUBLICADO, N, regiones, ciudad=ciudad)
    return [(i.lugar.nombre, i.lugar.nivel) for i in leido.impactos]


def test_el_distrito_es_el_lugar_si_no_hay_otro() -> None:
    texto = (
        "Вночі ворог атакував Ізмаїльський район ударними безпілотниками. Внаслідок атаки є "
        "пошкодження будівель припортової інфраструктури."
    )
    leido = analizar(texto, PUBLICADO, N, ODESA)
    (impacto,) = leido.impactos
    assert impacto.lugar.nombre == "Ізмаїльський район"
    assert impacto.lugar.nivel == "distrito"
    # Con su radio real, más ancho que el tope de una comunidad: no es una localidad.
    assert impacto.lugar.radio_km > RADIO_MAX_UNIDAD_KM
    texto = "Внаслідок удару по Одеському району пошкоджено приватні житлові будинки. БпЛА."
    assert _lugares(texto) == [("Одеський район", "distrito")]


def test_la_localidad_manda_sobre_su_distrito() -> None:
    texto = "Ворог атакував Ізмаїльський район ударними БпЛА: в Ізмаїлі пошкоджено склад."
    assert _lugares(texto) == [("Ізмаїл", "localidad")]


def test_el_oblast_y_el_sur_de_la_region_no_son_lugar() -> None:
    for texto in (
        "Вночі ворог знову атакував південь Одещини ударними безпілотниками. Пошкоджено склади.",
        "Ворог масовано атакував Одещину ударними БпЛА. Пошкоджено об'єкт енергетики.",
    ):
        leido = analizar(texto, PUBLICADO, N, ODESA)
        assert leido.impactos == [] and leido.motivo == "sin_lugar"


def test_la_ciudad_del_canal_municipal() -> None:
    texto = (
        "Ворог атакував місто ударними БпЛА. "
        "Є влучання в приватний будинок в одному з районів міста."
    )
    assert _lugares(texto, ciudad="Одеса") == [("Одеса", "localidad")]
    # En el canal de la región, «місто» puede ser cualquier ciudad.
    assert _lugares(texto) == []
    # «Місто Чорноморськ»: nombra otra; y una cifra acumulada no es un ataque.
    assert (
        _lugares("Безпілотник влучив у місто Чорноморськ, пошкоджено будинок.", ciudad="Одеса")
        == []
    )
    acumulado = "Атаки БпЛА. Лише цього року 866 жителів міста постраждали, 166 - загинули."
    assert _lugares(acumulado, KIEV, ciudad="Київ") == []


def test_el_ataque_con_drones_sobre_un_lugar_con_danos() -> None:
    texto = (
        "Вночі ворог здійснив масовану атаку на Одесу ударними БпЛА. Пошкоджено житлові будинки."
    )
    assert _lugares(texto) == [("Одеса", "localidad")]
    # Sin daños es una alerta o un relato del ataque, no un impacto.
    assert _lugares("Триває атака ударними БпЛА на Одесу. Перебувайте в укриттях!") == []
    # Sin arma en la frase, tampoco («атаки на …» en un parte con otras armas).
    assert (
        _lugares("Не припинялися атаки на Ізмаїл. Над областю збито 5 БпЛА, пошкоджено склад.")
        == []
    )


def test_consecuencia_del_ataque_con_drones() -> None:
    texto = (
        "Вночі ворог атакував Одесу ударними БпЛА. Внаслідок обстрілу в Приморському районі "
        "ушкоджено фасад багатоповерхівки."
    )
    assert _lugares(texto) == [("Одеса", "localidad")]
    # Si el mensaje nombra otra arma, «обстріл» sigue sin poder atribuirse a un dron.
    mixto = (
        "Ворог атакував Одещину ракетами та БпЛА. Внаслідок обстрілу в Ізмаїлі пошкоджено склад."
    )
    assert _lugares(mixto) == []


def test_se_mantienen_las_protecciones() -> None:
    # Colectas, balances y homenajes no dan impactos, aunque nombren un distrito.
    balance = (
        "Тижневий дайджест: за минулий тиждень ворог атакував Ізмаїльський район 40 БпЛА, "
        "є пошкодження."
    )
    assert analizar(balance, PUBLICADO, N, ODESA).motivo == "balance"
    homenaje = (
        "Пам'яті Івана Петренка. Загинув 3 березня 2025 року в Ізмаїльському районі "
        "від удару дрона."
    )
    assert analizar(homenaje, PUBLICADO, N, ODESA).motivo == "homenaje"
    # Un año escrito como fecha no es una cifra de víctimas.
    leido = analizar(
        "Унаслідок удару БпЛА по Одесі 13 лютого 2025 року поранено 3 людей, пошкоджено будинок.",
        PUBLICADO, N, ODESA,
    )  # fmt: skip
    assert leido.heridos == 3


def test_canales_de_ciudad() -> None:
    canales = {c.id: c for c in cargar_canales()}
    assert canales["mva_odesa"].ciudad == "Одеса"
    assert canales["kmva"].ciudad == "Київ"
    assert all(c.ciudad is None for c in canales.values() if c.id not in {"mva_odesa", "kmva"})


def test_el_nombre_de_una_persona_no_es_un_lugar() -> None:
    texto = (
        "Голова Одеської ОДА Олег Кіпер відвідав пологовий будинок, який зазнав пошкоджень "
        "внаслідок атаки БпЛА."
    )
    assert _lugares(texto) == []
    # La aldea, sí, cuando no es el nombre tras un cargo.
    assert _lugares("Безпілотник влучив у будинок у селі Олег.") == [("Олег", "localidad")]


def test_el_puerto_de_una_ciudad_sin_puerto_en_el_nomenclator() -> None:
    texto = (
        "Вночі ворог масовано атакував безпілотниками портову інфраструктуру півдня Одещини. "
        "На території Ізмаїльського порту пошкоджено цивільне судно, причал, баржу."
    )
    leido = analizar(texto, PUBLICADO, N, ODESA)
    assert [(i.lugar.nombre, i.categorias) for i in leido.impactos] == [("Ізмаїл", ("puerto",))]


def test_un_ataque_que_niega_los_danos_no_es_un_impacto() -> None:
    sin_danos = (
        "Вночі та під ранок ворог атакував Одесу кількома хвилями ударних безпілотників. "
        "Завдяки професійній роботі наших Сил оборони обійшлося без влучань та постраждалих."
    )
    leido = analizar(sin_danos, PUBLICADO, N, ODESA)
    assert leido.impactos == [] and leido.motivo == "sin_impacto"
    # Con un daño, aunque no haya víctimas, sí.
    con_dano = "Ворог атакував Одесу ударними БпЛА. Пошкоджено житловий будинок, без постраждалих."
    assert _lugares(con_dano) == [("Одеса", "localidad")]
    # Un golpe sobre algo es un impacto aunque no haya víctimas.
    golpe = "Ще один удар БпЛА в Ізмаїлі, на щастя, без постраждалих."
    assert _lugares(golpe) == [("Ізмаїл", "localidad")]


def test_un_incendio_es_un_dano() -> None:
    assert _lugares("Через ворожий безпілотник в Ізмаїлі зайнялась приватна оселя.") == [
        ("Ізмаїл", "localidad")
    ]


def test_sin_noticia_de_danos_no_es_un_impacto() -> None:
    texto = (
        "З ночі ворог атакував Одесу ударними безпілотниками. Наразі інформація щодо руйнувань "
        "та постраждалих не надходила."
    )
    assert _lugares(texto) == []
    # «Se está aclarando» no niega nada.
    assert _lugares(
        "Ворог атакував Одесу ударними БпЛА. Інформація щодо постраждалих уточнюється."
    ) == [("Одеса", "localidad")]
