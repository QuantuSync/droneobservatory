"""Odesa y las regiones con pocos impactos (docs/informe_revision_contenido.md, bloque 2): los
canales oficiales que faltaban y las formas de escribir el lugar que el analizador no leía."""

from datetime import UTC, datetime

from proceso.mensajes_guerra import VERSION, analizar
from recogida.canales_guerra import cargar_canales
from tests.nomenclator_falso import nomenclator

N = nomenclator()
PUBLICADO = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
JARKOV = frozenset({"UA-63"})


def test_version_nueva_del_analizador() -> None:
    # La relectura de la recogida horaria vuelve a leer todo lo guardado con la versión nueva.
    assert VERSION == "mensajes-guerra/6"


def test_canales_oficiales_que_faltaban() -> None:
    canales = {c.canal: c for c in cargar_canales()}
    # Odesa: el canal del jefe de la administración, además del que enlaza su web, y el de la
    # administración militar de la ciudad (por la cadena de la web de la ciudad).
    assert canales["odeskaODA"].region == canales["odesaoda"].region == "UA-51"
    assert canales["odeskaODA"].institucion == canales["odesaoda"].institucion
    assert canales["odesaMVA"].cadena == (("odesacityofficial", "Одеса. Офіційно"),)
    assert canales["odesaMVA"].web_enlaza == "odesacityofficial"
    # Las tres regiones que no tenían ningún canal.
    for canal, region in (
        ("volynskaODA", "UA-07"), ("zhytomyrskaODA", "UA-18"), ("ternopilskaODA", "UA-61"),
    ):  # fmt: skip
        assert canales[canal].region == region
        assert canales[canal].grupo == "ova_ua"
        assert canales[canal].fiabilidad == "B"
        # La página del Gobierno que los da como oficiales no carga para lectores
        # automáticos: se comprueban título, insignia y descripción.
        assert canales[canal].web_enlaza is None
        assert "kmu.gov.ua" in canales[canal].identificado["pagina"]


def test_prilit_en_ucraniano_es_un_impacto() -> None:
    # Como t.me/volynskaODA/10140: «також були прильоти в Ковелі».
    leido = analizar("Атака шахедів. Також були прильоти в Чугуєві.", PUBLICADO, N, JARKOV)
    assert [i.lugar.nombre for i in leido.impactos] == ["Чугуїв"]


def test_tergromada_y_territorialna_gromada() -> None:
    # Como t.me/cherkaskaODA/16104: «У Бобрицькій тергромаді уламками дрона пошкоджено вікна».
    for forma in ("тергромаді", "територіальній громаді"):
        leido = analizar(
            f"У Малинівській {forma} уламками дрона пошкоджено вікна.", PUBLICADO, N, JARKOV
        )
        assert [(i.lugar.nombre, i.lugar.nivel) for i in leido.impactos] == [
            ("Малинівська громада", "comunidad")
        ]


def test_oblasnyi_tsentr_es_la_capital_de_la_region_del_canal() -> None:
    # Como t.me/ternopilskaODA/28138: «на обласний центр, було здійснено атаку … падіння
    # уламків на територію промислового об'єкта».
    leido = analizar(
        "Внаслідок атаки БпЛА в обласному центрі пошкоджено промисловий об'єкт.",
        PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert [i.lugar.nombre for i in leido.impactos] == ["Харків"]


def test_oblasnyi_tsentr_sin_region_del_canal_no_da_lugar() -> None:
    # En los canales de todo el país no se sabe de qué región es el «обласний центр».
    leido = analizar(
        "Внаслідок атаки БпЛА в обласному центрі пошкоджено будинок.", PUBLICADO, N, None
    )
    assert leido.impactos == []


def test_colectas_y_balances_no_son_impactos() -> None:
    # Pendiente de docs/informe_errores_datos.md: como t.me/people_of_action/52939 y
    # t.me/chernigivskaODA/22524, que nombran drones y lugares sin contar un ataque nuevo.
    colecta = analizar(
        "Микола та Марічка передали свій весільний донат на ремонт будинку, "
        "пошкодженого дроном у Чугуєві.",
        PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert colecta.motivo == "colecta" and colecta.impactos == []
    balance = analizar(
        "Тільки за минулий тиждень армія рф атакувала 32 населені пункти області. У Чугуєві "
        "внаслідок атаки FPV-дроном пошкоджено будинок.",
        PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert balance.motivo == "balance" and balance.impactos == []
    # Un parte del día que al final compara con la semana sigue contando su ataque.
    parte = analizar(
        "Вночі ворожий дрон влучив у будинок у Чугуєві. " + "Рятувальники працюють. " * 12
        + "За минулий тиждень це вже третій удар.",
        PUBLICADO, N, JARKOV,
    )  # fmt: skip
    assert [i.lugar.nombre for i in parte.impactos] == ["Чугуїв"]
