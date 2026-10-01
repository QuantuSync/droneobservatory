"""UK Airprox Board: Excel histórico, catálogo, informes en PDF y encuentros, sin red."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from proceso.validaciones import validar_encuentro
from recogida import airprox
from recogida.descarga import Descargador

FIXTURES = Path(__file__).parent / "fixtures" / "detalle"
AHORA = datetime(2026, 10, 1, 12, tzinfo=UTC)


def leer(nombre: str) -> bytes:
    return (FIXTURES / nombre).read_bytes()


def texto(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def consolidada() -> dict[str, airprox.Bloque]:
    return airprox.bloques(airprox.texto_pdf(leer("ukab_consolidada_2025.pdf")))


def test_la_pagina_del_anio_da_el_catalogo_y_cada_informe() -> None:
    pagina = airprox.leer_pagina_anio(texto("ukab_pagina_2025.html"))
    assert pagina.catalogo is not None and pagina.catalogo.endswith("/4178")
    assert pagina.informes["2025022"].startswith(airprox.BASE + "/Documents/Download/")
    assert len(pagina.informes) == 29


def test_el_excel_se_lee_sin_bibliotecas_y_con_sus_cabeceras() -> None:
    filas = airprox.leer_xlsx(leer("ukab_catalogo_2025.xlsx"))
    fila = next(f for f in filas if f["Airprox No"] == 2025022)
    assert fila["Latitude"] == "52:05:00 N" and fila["Risk Category"] == "A"
    assert airprox._hora_excel(fila["Time (UTC)"]) == (12, 15)
    assert airprox._fecha_excel(fila["Date"]) == datetime(2025, 3, 3, tzinfo=UTC)
    assert airprox._coordenada_excel("002:10:00 W") == -2.16667


@pytest.mark.parametrize(
    ("numero", "lado"),
    [(2025001, None), (2025002, 2), (2025003, 1), (2025022, 2)],
)
def test_que_aeronave_es_el_dron_o_el_objeto(numero: int, lado: int | None) -> None:
    filas = {f["Airprox No"]: f for f in airprox.leer_xlsx(leer("ukab_catalogo_2025.xlsx"))}
    assert airprox.lado_objeto(filas[numero]) == lado


def test_el_historico_es_el_indice_y_deja_fuera_los_globos() -> None:
    indice = airprox.indice(airprox.leer_xlsx(leer("ukab_ua_other.xlsx")))
    assert "2021021" not in indice  # un globo de fiesta
    assert indice["2021022"]["Object"] == "Unknown"
    assert indice["2026108"]["Object"] == "Drone"


def test_hoja_consolidada_campos_fijos(consolidada: dict[str, airprox.Bloque]) -> None:
    bloque = consolidada["2025022"]
    assert bloque.fecha == datetime(2025, 3, 3, tzinfo=UTC) and bloque.hora == (12, 15)
    assert (bloque.aeronave, bloque.operador, bloque.objeto) == (
        "Atlas A400M",
        "HQ Air Ops",
        "Drone",
    )
    assert (bloque.lat, bloque.lon) == (52.08333, -1.21667)
    assert (bloque.ubicacion, bloque.altitud) == ("5NM E Banbury", "375ft")
    assert (bloque.espacio, bloque.clase_espacio) == ("London FIR", "G")
    assert bloque.separacion == "50ft V/0m H"
    assert (bloque.riesgo_notificado, bloque.riesgo) == ("Medium", "A")
    assert bloque.reunion == datetime(2025, 4, 23, tzinfo=UTC)
    assert bloque.opinion and bloque.opinion.startswith("In the Board’s opinion")


def test_el_riesgo_de_un_bloque_partido_entre_paginas(
    consolidada: dict[str, airprox.Bloque],
) -> None:
    # El informe de 2025025 sigue en la página siguiente: la letra no está al final del bloque.
    assert consolidada["2025025"].riesgo == "B"
    assert set(consolidada) == {"2025022", "2025025"}


def test_el_objeto_en_dos_lineas() -> None:
    # Texto real de la hoja de la reunión del 23 de abril de 2025 (página 3).
    texto_pdf = (
        "Consolidated Drone/Balloon/Model/Unknown Object Summary Sheet for UKAB Meeting on 23rd "
        "April 2025 \n2025028 12 Mar 25 \n2125 \nChinook \n(HQ JAC) \nUnk \nObj \n5053N  00051W "
        "\nIVO Chichester \n900ft \n \n \nLondon FIR \n(G) \nThe Chinook pilot reports that the "
        "aircraft had been \nin a medium level cruise routeing northbound. The Captain saw a "
        "bright light \nappear in the aircraft’s one o’clock.\n"
    )
    bloque = airprox.bloques(texto_pdf)["2025028"]
    assert (bloque.aeronave, bloque.operador, bloque.objeto) == ("Chinook", "HQ JAC", "Unk Obj")
    assert (bloque.ubicacion, bloque.altitud, bloque.espacio) == (
        "IVO Chichester",
        "900ft",
        "London FIR",
    )


def test_hojas_de_otros_anios_y_el_informe_individual() -> None:
    hoja_2017 = airprox.bloques(texto("ukab_texto_2017025.txt"))
    assert hoja_2017["2017007"].separacion == "300ft V/200m H"
    assert hoja_2017["2017004"].altitud == "310ft agl"
    hoja_2021 = airprox.bloques(texto("ukab_texto_2021026.txt"))
    assert hoja_2021["2021022"].objeto == "Unk Obj"
    assert hoja_2021["2021021"].objeto == "Balloon"
    individual = airprox.bloques(texto("ukab_texto_2015024.txt"))["2015024"]
    assert (individual.hora, individual.ubicacion) == ((9, 23), "5nm west of Heathrow")
    assert individual.separacion == "50ft V/0m H"


@pytest.mark.parametrize(
    ("texto_", "vertical", "horizontal"),
    [
        ("50ft V/0m H", {"min": 15.24, "max": 15.24}, {"min": 0.0, "max": 0.0}),
        ("300ftV/ 0M H", {"min": 91.44, "max": 91.44}, {"min": 0.0, "max": 0.0}),
        ("0ft V/50-100ft H", {"min": 0.0, "max": 0.0}, {"min": 15.24, "max": 30.48}),
        ("Nil V/0.25NM H", {"min": 0.0, "max": 0.0}, {"min": 463.0, "max": 463.0}),
        ("NK V/100m H", None, {"min": 100.0, "max": 100.0}),
    ],
)
def test_separacion(texto_: str, vertical: object, horizontal: object) -> None:
    resultado = airprox.separacion(texto_)
    assert resultado.get("vertical_m") == vertical
    assert resultado.get("horizontal_m") == horizontal


def test_separacion_ilegible_se_guarda_solo_como_texto() -> None:
    assert airprox.separacion("NK") == {"texto": "NK"}


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (375.0, {"pies": 375, "texto": "375ft", "referencia": "sin_referencia"}),
        ("310ft agl", {"pies": 310, "texto": "310ft agl", "referencia": "agl"}),
        ("FL078", {"pies": 7800, "texto": "FL078", "referencia": "nivel_vuelo"}),
        ("sin dato", None),
    ],
)
def test_altitud(valor: object, esperado: object) -> None:
    assert airprox.altitud(valor) == esperado


@pytest.mark.parametrize(
    ("frase", "clase"),
    [
        ("a grey quadcopter type UAS was observed", "multirrotor_pequeno"),
        ("a white fixed-wing drone with a 2m wingspan", "ala_fija"),
        ("a small black object", "desconocido"),
    ],
)
def test_clase_por_las_palabras_de_la_descripcion(frase: str, clase: str) -> None:
    assert airprox.clase(frase) == clase


def test_la_descripcion_es_la_frase_que_describe_el_objeto() -> None:
    cuerpo = (
        "The Atlas pilot reports flying a low level sortie. The drone operator was not traced. "
        "A grey quadcopter type UAS was observed to pass over the top of the aircraft within "
        "50ft. Reported Separation: 50ft V/0m H"
    )
    descripcion = airprox.descripcion(cuerpo)
    assert descripcion is not None and descripcion.startswith("A grey quadcopter")


def encuentro_2025022(consolidada: dict[str, airprox.Bloque]) -> dict[str, object] | None:
    filas = {
        airprox._numero(f["Airprox No"]): f
        for f in airprox.leer_xlsx(leer("ukab_catalogo_2025.xlsx"))
    }
    indice = airprox.indice(airprox.leer_xlsx(leer("ukab_ua_other.xlsx")))
    return airprox.encuentro(
        "2025022", indice["2025022"], filas["2025022"], consolidada["2025022"],
        "https://www.airproxboard.org.uk/Documents/Download/2501/x/3600", None, AHORA,
    )  # fmt: skip


def test_el_encuentro_junta_historico_catalogo_e_informe(
    consolidada: dict[str, airprox.Bloque],
) -> None:
    documento = encuentro_2025022(consolidada)
    assert documento is not None
    assert validar_encuentro(documento, AHORA) == []
    assert documento["instante"] == {"valor": "2025-03-03T12:15Z", "precision": "minuto"}
    assert documento["posicion"] == {
        "punto": {"lat": 52.08333, "lon": -1.21667},
        "descripcion": "5NM E Banbury",
    }
    objeto = documento["objeto"]
    assert isinstance(objeto, dict)
    # La clasificación de la UKAB tal cual; la clase, por regla.
    assert objeto["clasificacion"] == "Drone" and objeto["clase"] == "multirrotor_pequeno"
    # 375 ft ± 50 ft de separación vertical.
    assert objeto["altura_m"] == {"min": 99.06, "max": 129.54}
    assert documento["categoria_riesgo"] == "A"
    procedencia = documento["procedencia"]
    assert isinstance(procedencia, dict)
    assert procedencia["objeto.altura_m"]["metodo"] == "regla"
    assert procedencia["instante"] == {"origen": "oficial", "metodo": "parser",
                                       "fuentes": ["UKAB-2025022"]}  # fmt: skip


def test_sin_catalogo_ni_informe_el_historico_basta_con_precision_de_dia() -> None:
    indice = airprox.indice(airprox.leer_xlsx(leer("ukab_ua_other.xlsx")))
    documento = airprox.encuentro("2010004", indice["2010004"], None, None, "https://x.org/a.pdf",
                                  None, AHORA)  # fmt: skip
    assert documento is not None and validar_encuentro(documento, AHORA) == []
    assert documento["instante"] == {"valor": "2010-02-12T00:00Z", "precision": "dia"}
    assert documento["posicion"]["punto"] == {"lat": 51.21667, "lon": -2.0}


def test_un_globo_no_es_un_encuentro() -> None:
    bloque = airprox.bloques(texto("ukab_texto_2021026.txt"))["2021021"]
    assert (
        airprox.encuentro("2021021", None, None, bloque, "https://x.org/a.pdf", None, AHORA) is None
    )


class Transporte:
    """Responde con los fixtures; registra lo pedido."""

    def __init__(self, respuestas: dict[str, bytes]) -> None:
        self.respuestas = respuestas
        self.pedidas: list[str] = []

    def __call__(
        self, url: str, cabeceras: dict[str, str], limite: float
    ) -> tuple[int, dict[str, str], bytes]:
        self.pedidas.append(url)
        assert "EODI-bot" in cabeceras["User-Agent"]
        for clave, cuerpo in self.respuestas.items():
            if url.endswith(clave):
                return 200, {}, cuerpo
        return 404, {}, b""


def test_recoger_de_principio_a_fin_sin_red(tmp_path: Path) -> None:
    pagina = texto("ukab_pagina_2025.html")
    drones = (
        '<html><body>Airprox <a href="/media/abc/ua_other-airprox-count.xlsx">x</a></body></html>'
    )
    transporte = Transporte({
        "/topical-issues-and-themes/drones/": drones.encode(),
        "ua_other-airprox-count.xlsx": leer("ukab_ua_other.xlsx"),
        "/individual-airprox-reports/2025/": pagina.encode(),
        "/4178": leer("ukab_catalogo_2025.xlsx"),
        "/3654": leer("ukab_consolidada_2025.pdf"),
    })  # fmt: skip
    pagina_anio = airprox.leer_pagina_anio(pagina)
    for numero in ("2025022", "2025025", "2025027", "2025028"):
        transporte.respuestas[pagina_anio.informes[numero].rsplit("/", 1)[1]] = leer(
            "ukab_consolidada_2025.pdf"
        )
    descargador = Descargador(transporte=transporte, dormir=lambda _: None, agente="EODI-bot/1.0")
    datos = airprox.Datos(tmp_path)
    recuentos = airprox.recoger(datos, descargador, [2025], frozenset({2025}))
    assert recuentos.informes_nuevos == 4 and recuentos.fallidos == 0
    lista = airprox.encuentros(datos, AHORA)
    assert [e["id"] for e in lista] == [
        "UKAB-2025022",
        "UKAB-2025025",
        "UKAB-2025027",
        "UKAB-2025028",
    ]
    assert all(validar_encuentro(e, AHORA) == [] for e in lista)
    # Lo ya descargado no se vuelve a pedir.
    antes = len(transporte.pedidas)
    airprox.recoger(datos, descargador, [2025])
    assert not any(url.endswith(".pdf") or "/3654" in url for url in transporte.pedidas[antes:])
