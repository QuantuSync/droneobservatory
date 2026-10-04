"""Víctimas y homenajes en la capa de guerra: un año no es una cifra de víctimas, más de 100
por impacto solo con la cifra pegada al verbo, las víctimas solo de frases de drones y sin
acumulados, y los homenajes, obituarios y la memoria de caídos no son impactos. Textos reales
de los canales oficiales (los seis ejemplos del informe docs/informe_errores_datos.md) y
corrección de lo ya guardado."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from proceso import impactos_guerra
from proceso.mensajes_guerra import _HERIDOS, _MUERTOS, _victimas_frase, analizar, anios_en_frase
from recogida import guerra as paso
from recogida.canales_guerra import Canal, Datos
from tests import ejemplos
from tests.nomenclator_falso import nomenclator

N = nomenclator()
PUBLICADO = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
DONETSK = frozenset({"UA-14"})
JARKOV = frozenset({"UA-63"})

# --- Los seis ejemplos: homenajes y memoria, nunca impactos ---------------------------------

# t.me/DonetskaODA/54848 (EODI-IG-2025-00179, Rozdolne, mostraba «2.024 fallecidos»).
ROZDOLNE = (
    "Молодший лейтенант Олександр Боровий на псевдо Бур загинув 30 грудня 2024 року поблизу "
    "селища Роздольне Волноваського району. Прикриваючи побратимів у бою, він отримав смертельні "
    "поранення внаслідок атаки ворожого FPV-дрона. Захисникові було 36 років.\n\n"
    "О 9:00 — загальнонаціональна хвилина мовчання."
)
# t.me/DonetskaODA/45074 (EODI-IG-2025-00165).
MEMORIAL_BUR = (
    "Молодший лейтенант Олександр Боровий, позивний «Бур», загинув 30 грудня 2024 року поблизу "
    "селища Роздольне на Волноваському напрямку. Прикриваючи побратимів, дістав смертельні "
    "поранення від удару ворожого FPV-дрона. Йому було 36 років.\n\n"
    "О 9:00 — загальнонаціональна хвилина мовчання. Донецька ОВА та платформа Меморіал "
    "згадують загиблих захисників з Донеччини."
)
# t.me/DonetskaODA/56084 (EODI-IG-2026-03500).
PREMIO = (
    "Національна спілка журналістів України відзначила посмертно Олену Губанову та Євгенія "
    "Кармазіна Національною премією за захист свободи слова\n\nПравління Національної спілки "
    "журналістів України присудило Національну премію за захист свободи слова імені Ігоря "
    "Лубченка за 2025 рік журналістам телеканалу FREEДОМ — Альоні Грамовій та Євгену Кармазіну. "
    "Вони загинули 23 жовтня 2025 року в Краматорську, виконуючи професійне завдання. "
    "Російський ударний дрон влучив у знімальну групу під час роботи на місці обстрілу."
)
# t.me/DonetskaODA/56431 (EODI-IG-2026-00059).
SLOVIANSK = (
    "Олександр Кудрявцев загинув увечері 19 грудня 2025 року на околиці міста Слов’янськ. "
    "Автомобіль, в якому був чоловік, атакував російський дрон.\n\nОлександрові було 66 років. "
    "Народився 3 жовтня 1959-го в місті Чорнобиль.\n\n9:00 — загальнонаціональна хвилина "
    "мовчання. Донецька ОВА та платформа Меморіал згадують убитих росіянами жителів Донеччини."
)
# t.me/people_of_action/62214 (EODI-IG-2026-03471).
LVIV = (
    "Щоденно о 9 годині – загальнонаціональна хвилина мовчання. Зупиніться, де б ви не були, і "
    "вшануйте світлу пам’ять усіх, хто загинув за Україну через російську агресію.\n\n"
    "Сьогодні Львівщина прощається із захисниками:\n\n🕯️ Іван Приймич\nДрогобичанин.\n"
    "Виконував бойові завдання у складі 24-ї окремої механізованої бригади.\nЗагинув  24 "
    "квітня 2024 року під час виконання бойового завдання поблизу населеного пункту Богданівка "
    "на Бахмутському напрямку фронту. Тривалий час вважався зниклим безвісти. Удар дрона."
)
# t.me/DonetskaODA/65557 (EODI-IG-2026-00068).
LYPTSI = (
    "Солдат Олександр Верпека загинув 19 травня 2024 року поблизу Липців на Харківщині. Його "
    "життя обірвав удар ворожого FPV-дрона. Захисникові було 37 років.\n\n"
    "О 9:00 — загальнонаціональна хвилина мовчання. Донецька ОВА та платформа Меморіал "
    "згадують загиблих захисників з Донеччини."
)


@pytest.mark.parametrize("texto", [ROZDOLNE, MEMORIAL_BUR, PREMIO, SLOVIANSK, LVIV, LYPTSI])
def test_homenajes_y_memoria_no_son_impactos(texto: str) -> None:
    leido = analizar(texto, PUBLICADO, N, DONETSK)
    assert leido.motivo == "homenaje"
    assert leido.impactos == []
    assert leido.fallecidos not in {2023, 2024, 2025}


def test_el_anio_de_la_frase_no_es_una_cifra_de_victimas() -> None:
    frase = (
        "Молодший лейтенант Олександр Боровий на псевдо Бур загинув 30 грудня 2024 року поблизу "
        "селища Роздольне Волноваського району."
    )
    assert anios_en_frase(frase) == {2024}
    assert _victimas_frase(frase, _MUERTOS) == []
    assert _victimas_frase("Він загинув у 2025 році під Покровськом.", _MUERTOS) == []
    assert _victimas_frase("В 2024 году погибли 3 человека.", _MUERTOS) == [3]


def test_mas_de_100_solo_con_la_cifra_pegada_al_verbo() -> None:
    assert _victimas_frase("Загинули 120 людей.", _MUERTOS) == [120]
    assert _victimas_frase("Поранено 130 осіб.", _HERIDOS) == [130]
    # La cifra lejos del verbo, o detrás de «понад», no es inequívoca.
    assert _victimas_frase("Поранені понад 2100 людей, з них 177 дітей.", _HERIDOS) == []
    assert _victimas_frase("Загинули 500 голів свійської тварини.", _MUERTOS) == []


def test_edades_sin_guion_no_son_victimas() -> None:
    frase = "Минулими вихідними були госпіталізовані жінки 59 та 67 років після атак FPV дронів."
    assert 59 not in _victimas_frase(frase, _HERIDOS)


def test_victimas_solo_de_frases_de_drones_y_sin_acumulados() -> None:
    # t.me/zoda_gov_ua/39478: acumulado desde el inicio de la invasión.
    acumulado = (
        "16 постраждалих від ворожих обстрілів знаходяться в медзакладах Запоріжжя. Чоловік з "
        "Гуляйполя поранений внаслідок скиду fpv-дрона. Загалом з початку повномасштабного "
        "вторгнення внаслідок російських атак на область поранені понад 2100 людей."
    )
    assert analizar(acumulado, PUBLICADO, N, JARKOV).heridos != 2100
    # t.me/adm_dp/28692: los muertos son de un misil en otro lugar.
    misil = (
        "▪️Агресор атакував Харків БпЛА Shahed. Є руйнування на території підприємства.\n"
        "На жаль, у лікарні померла жінка, яка постраждала через ракетний удар напередодні. "
        "Загалом загинули 5 людей."
    )
    leido = analizar(misil, PUBLICADO, N, JARKOV)
    assert [i.lugar.nombre for i in leido.impactos] == ["Харків"]
    assert leido.fallecidos is None


def test_condolencia_dentro_de_un_parte_no_lo_anula() -> None:
    # t.me/adm_dp/34632 (con la ciudad del nomenclátor de prueba).
    texto = (
        "🕯Сьогодні місто в скорботі за трьома загиблими через ракетну атаку напередодні.\n\n"
        "Схиляємо голови на згадку про невинних жертв російської агресії. Світла пам'ять.\n\n"
        "▪️Вночі ворог спрямував на область безпілотники. Були влучання у Харкові."
    )
    leido = analizar(texto, PUBLICADO, N, JARKOV)
    assert leido.motivo is None
    assert [i.lugar.nombre for i in leido.impactos] == ["Харків"]
    assert leido.fallecidos is None


# --- Corrección de lo guardado -------------------------------------------------------------

OVA = Canal(
    id="ova_kharkiv", canal="kharkivoda", grupo="ova_ua", pais="UA", region="UA-63",
    sentido="RU_UA", idioma="uk", titulo="kharkivoda", insignia=False, descripcion_enlaza=(),
    web_oficial=None, web_enlaza=None, web_desde_servidor=False, fiabilidad="B",
    origen="oficial", medio="Харківська ОВА", autoridad_ocupacion=False,
    identificado={"fecha": "2026-10-01"}, institucion="ova_kharkiv",
)  # fmt: skip
AHORA = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def canales_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impactos_guerra, "_canales", lambda: {"kharkivoda": OVA})


def _impacto(id_: str, mensaje: int, **victimas: int) -> dict[str, Any]:
    fuente_id = f"kharkivoda-{mensaje}"
    documento = {
        "id": id_, "tipo": "impacto_guerra", "sentido": "RU_UA", "region": "UA-63",
        "lugar": {"id": "katotth:UA63120270010096107", "nombre": "Харків", "nivel": "localidad",
                  "punto": {"lat": 49.99, "lon": 36.23}, "radio_km": 15.0},
        "impacto": "impacto", "categorias_objetivo": [],
        "fecha": ejemplos.instante("2026-09-30T06:00Z"), "credibilidad": 2,
        "fuentes": [{
            "id": fuente_id, "enlace": f"https://t.me/kharkivoda/{mensaje}",
            "medio": "Харківська ОВА", "fecha": ejemplos.instante("2026-09-30T06:00Z"),
            "idioma": "uk", "fiabilidad": "B", "credibilidad": 2, "frase_origen": "frase",
            "replicas": 0, "campos_respaldados": ["lugar"], "es_autoridad": False,
            "interna_fuera_de_ucrania": False, "publica": True,
        }],
        # Lectura anterior a la regla de víctimas: sin `victimas`.
        "lecturas": [{"fuente_id": fuente_id, "metodo": "parser", "version": "mensajes-guerra/2"}],
        "control": {"alta": ejemplos.instante("2026-09-30T07:00Z"),
                    "ultima_actualizacion": ejemplos.instante("2026-09-30T07:00Z")},
    }  # fmt: skip
    for campo, valor in victimas.items():
        documento[campo] = {"min": valor, "max": valor}
    return documento


def _datos(tmp_path: Path, textos: dict[int, str]) -> Datos:
    ruta = tmp_path / "canales" / "kharkivoda" / "2026-09.jsonl"
    ruta.parent.mkdir(parents=True)
    with ruta.open("w", encoding="utf-8") as fichero:
        for id_, texto in textos.items():
            fichero.write(json.dumps({"id": id_, "fecha": "2026-09-30T06:00:00Z", "texto": texto},
                                     ensure_ascii=False) + "\n")  # fmt: skip
    return Datos(tmp_path)


def test_correccion_retira_homenajes_y_corrige_victimas(tmp_path: Path) -> None:
    almacen = Almacen.abrir()
    homenaje = _impacto("EODI-IG-2025-00179", 1, fallecidos=2024)
    parte = _impacto("EODI-IG-2026-00001", 2, heridos=74, fallecidos=1)
    for documento in (homenaje, parte):
        almacen.guardar_impacto_guerra(copy.deepcopy(documento))
    datos = _datos(tmp_path, {
        1: ROZDOLNE,
        2: "Вночі ворог атакував Харків безпілотниками. Поранено 74-річного чоловіка, загинула "
           "жінка.",
    })  # fmt: skip
    hecho = paso.corregir(almacen, datos, [OVA], N, AHORA)
    assert hecho is not None
    assert (hecho.retirados, hecho.victimas_cambiadas) == (1, 1)
    guardados = {d["id"]: d for d in almacen.impactos_guerra()}
    retirado = guardados["EODI-IG-2025-00179"]["retirado"]
    assert retirado["motivo"].startswith("homenaje")
    corregido = guardados["EODI-IG-2026-00001"]
    assert corregido["heridos"] == {"min": 1, "max": 1}
    assert corregido["fallecidos"] == {"min": 1, "max": 1}
    assert corregido["lecturas"][0]["victimas"] == {"heridos": 1, "fallecidos": 1}
    # El motivo de cada cambio queda en el historial y nada se borra.
    assert any("motivo" in h.get("nuevo", {}) or "motivo" in json.dumps(h)
               for h in almacen.historial("EODI-IG-2026-00001"))  # fmt: skip
    # Una vez por versión.
    assert paso.corregir(almacen, datos, [OVA], N, AHORA) is None


def test_volver_a_leer_un_mensaje_corrige_la_cifra_en_vez_de_quedarse_con_la_mayor() -> None:
    documento = _impacto("EODI-IG-2026-00002", 2, heridos=74)
    documento["lecturas"][0]["victimas"] = {"heridos": 1}
    impactos_guerra.victimas_por_lecturas(documento, documento)
    assert documento["heridos"] == {"min": 1, "max": 1}
