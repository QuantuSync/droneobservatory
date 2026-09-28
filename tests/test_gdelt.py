"""Recogida de GDELT sin red: ficheros GKG de ejemplo, franjas pendientes, réplicas y candidatos."""

import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from almacen.base import Almacen
from proceso.noticias import Articulo, configuracion, filtro, nomenclator
from recogida import gdelt
from recogida.descarga import Descargador, Respuesta
from recogida.informe_gdelt import informe

AHORA = datetime(2025, 9, 23, 12, 5, tzinfo=UTC)
TITULAR = "Droner over Københavns Lufthavn: lufthavnen lukket"


def fila(
    n: int,
    titular: str,
    franja: str = "20250923114500",
    medio: str | None = None,
    traduccion: str = "srclc:dan;eng:GT-DAN 1.0",
    lugares: str = "",
    temas: str = "DRONES;TAX_FNCACT;SECURITY_SERVICES",
) -> str:
    campos = [""] * gdelt.NUM_COLUMNAS
    campos[gdelt.COL_FECHA] = franja
    campos[gdelt.COL_MEDIO] = medio or f"medio{n}.dk"
    campos[gdelt.COL_URL] = f"https://www.medio{n}.dk/nyhed/{n}?utm_source=x"
    campos[gdelt.COL_TEMAS] = temas
    campos[gdelt.COL_LUGARES] = lugares
    campos[gdelt.COL_TRADUCCION] = traduccion
    # El titular llega con entidades HTML, como en los ficheros reales.
    campos[gdelt.COL_EXTRAS] = f"<PAGE_TITLE>{titular.replace('ø', '&#xF8;')}</PAGE_TITLE>"
    return "\t".join(campos)


def comprimido(lineas: list[str]) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("x.gkg.csv", "\n".join(lineas) + "\n")
    return salida.getvalue()


class GdeltFalso:
    """Índices y ficheros GKG en memoria. Una franja sin fichero da 404."""

    def __init__(self, ultima: str) -> None:
        self.ultima = ultima
        self.ficheros: dict[str, bytes] = {}
        self.pedidas: list[str] = []
        self.caido = False

    def poner(self, franja: str, lineas: list[str], flujo: str = "traducido") -> None:
        self.ficheros[franja + gdelt.FLUJOS[flujo][1]] = comprimido(lineas)

    def __call__(self, url: str, cabeceras: dict[str, str], limite_s: float) -> Respuesta:
        if self.caido:
            return 503, {}, b""
        self.pedidas.append(url)
        if url.endswith(".txt"):
            sufijo = ".translation.gkg.csv.zip" if "translation" in url else ".gkg.csv.zip"
            linea = f"1 x {gdelt.BASE}{self.ultima}{sufijo}\n"
            return 200, {}, linea.encode()
        nombre = url.removeprefix(gdelt.BASE)
        if nombre in self.ficheros:
            return 200, {}, self.ficheros[nombre]
        return 404, {}, b""


def descargador(falso: GdeltFalso) -> Descargador:
    return Descargador(falso, dormir=lambda _: None, pausa_minima_s=0, reintentos=0)


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def articulo(n: int, titular: str, horas: float, pais: str | None = "DK") -> Articulo:
    return Articulo(
        url=f"https://medio{n}.dk/nyhed/{n}",
        medio=f"medio{n}.dk",
        fecha=AHORA - timedelta(hours=horas),
        titular=titular,
        idioma="da",
        pais=pais,
        lugares=("EKCH",) if "Lufthavn" in titular else (),
    )


# --- Filas ------------------------------------------------------------------------


def test_fila_con_titular_idioma_pais_temas_y_lugar() -> None:
    config, med = configuracion(), gdelt.medios()
    campos = fila(1, TITULAR).split("\t")
    a = gdelt.articulo(campos, filtro(), nomenclator(), med, config)
    assert a is not None
    assert (a.url, a.titular, a.idioma, a.pais) == (
        "https://medio1.dk/nyhed/1",
        TITULAR,
        "da",
        "DK",
    )
    assert a.fecha == datetime(2025, 9, 23, 11, 45, tzinfo=UTC)
    # Las taxonomías largas no se guardan.
    assert a.temas == ("DRONES", "SECURITY_SERVICES")
    assert a.lugares == ("EKCH",)


def test_sin_dron_en_el_titular_o_fuera_de_europa_no_pasa() -> None:
    config, med = configuracion(), gdelt.medios()
    args = (filtro(), nomenclator(), med, config)
    sin_dron = fila(1, "Københavns Lufthavn lukket").split("\t")
    assert gdelt.articulo(sin_dron, *args) is None
    lejos = fila(2, "Drone strike in Texas", medio="ejemplo.com", traduccion="").split("\t")
    assert gdelt.articulo(lejos, *args) is None
    # Un medio de fuera que sitúa la noticia en un país europeo sí pasa, sin país del medio.
    cerca = fila(
        3, "Drone sightings close Munich airport", medio="ejemplo.com", traduccion="",
        lugares="4#Munich, Bayern, Germany#GM#GM02#48.15#11.58#-1829149",
    ).split("\t")  # fmt: skip
    a = gdelt.articulo(cerca, *args)
    assert a is not None
    assert (a.pais, a.idioma) == (None, "en")


def test_pais_del_medio_por_dominio_o_sufijo() -> None:
    med = gdelt.medios()
    assert med.pais("www.dr.dk") == "DK"
    assert med.pais("bbc.co.uk") == "GB"
    assert med.pais("ejemplo.com") is None
    assert med.paises_lugares("1#Spain#SP#SP#40#-4#SP;1#Russia#RS#RS#60#100#RS") == {"ES"}


def test_franjas() -> None:
    assert gdelt.franja_de(datetime(2025, 9, 23, 11, 59, 30, tzinfo=UTC)) == datetime(
        2025, 9, 23, 11, 45, tzinfo=UTC
    )
    assert gdelt.url_fichero(datetime(2025, 9, 23, 11, 45, tzinfo=UTC), "ingles").endswith(
        "/20250923114500.gkg.csv.zip"
    )


# --- Incorporación ----------------------------------------------------------------


def test_incorpora_filtra_deduplica_y_agrupa(almacen: Almacen) -> None:
    recibidos = [
        articulo(1, TITULAR, 10),
        # Réplica: el mismo titular en otro medio.
        articulo(2, TITULAR + " - TV2", 9),
        articulo(3, "Politiet: droner ved Københavns Lufthavn i nat, flyvninger aflyst", 8),
        # Ocio: fuera.
        articulo(4, "Stort droneshow i Aarhus", 7),
        # La misma URL otra vez.
        articulo(1, TITULAR, 10),
    ]
    recuentos = gdelt.incorporar(almacen, recibidos)
    assert (recuentos.recibidos, recuentos.ya_vistos, recuentos.descartados) == (5, 1, 1)
    assert (recuentos.replicas, recuentos.nuevos, recuentos.candidatos_nuevos) == (1, 2, 1)
    articulos = almacen.articulos()
    assert [a["replicas"] for a in articulos] == [1, 0]
    (candidato,) = almacen.candidatos()
    assert candidato["lugar"] == "EKCH"
    assert len(candidato["articulos"]) == 2
    assert {a["candidato"] for a in articulos} == {candidato["id"]}


def test_el_candidato_crece_entre_ejecuciones(almacen: Almacen) -> None:
    gdelt.incorporar(almacen, [articulo(1, TITULAR, 10)])
    gdelt.incorporar(almacen, [articulo(3, "Politiet: nye droner ved Københavns Lufthavn", 2)])
    (candidato,) = almacen.candidatos()
    assert len(candidato["articulos"]) == 2


# --- Ejecución --------------------------------------------------------------------


def test_procesa_las_franjas_pendientes_y_avanza_el_cursor(almacen: Almacen) -> None:
    falso = GdeltFalso("20250923114500")
    almacen.guardar_cursor("gdelt", {"franja": "2025-09-23T11:15:00Z", "inicio": "x"})
    falso.poner("20250923113000", [fila(1, TITULAR, "20250923113000")])
    falso.poner("20250923113000", [], "ingles")
    falso.poner("20250923114500", [fila(2, "Ny drone ved Københavns Lufthavn i aften")])
    falso.poner("20250923114500", [], "ingles")
    recuentos = gdelt.ejecutar(almacen, descargador(falso), AHORA)
    assert (recuentos.franjas, recuentos.filas, recuentos.nuevos) == (2, 2, 2)
    assert almacen.cursor("gdelt") == {"franja": "2025-09-23T11:45:00Z", "inicio": "x"}
    # Nada nuevo: no se pide ningún fichero.
    falso.pedidas.clear()
    gdelt.ejecutar(almacen, descargador(falso), AHORA)
    assert all(url.endswith(".txt") for url in falso.pedidas)


def test_un_fichero_reciente_que_falta_se_espera(almacen: Almacen) -> None:
    falso = GdeltFalso("20250923114500")
    almacen.guardar_cursor("gdelt", {"franja": "2025-09-23T11:30:00Z", "inicio": "x"})
    falso.poner("20250923114500", [], "ingles")
    assert gdelt.ejecutar(almacen, descargador(falso), AHORA).franjas == 0
    assert almacen.cursor("gdelt") == {"franja": "2025-09-23T11:30:00Z", "inicio": "x"}


def test_un_fichero_antiguo_que_falta_se_da_por_perdido(almacen: Almacen) -> None:
    falso = GdeltFalso("20250923114500")
    almacen.guardar_cursor("gdelt", {"franja": "2025-09-23T05:30:00Z", "inicio": "x"})
    franjas = [datetime(2025, 9, 23, 5, 45, tzinfo=UTC) + gdelt.FRANJA * i for i in range(25)]
    for i, franja in enumerate(franjas):
        falso.poner(f"{franja:%Y%m%d%H%M%S}", [], "ingles")
        if i:
            falso.poner(f"{franja:%Y%m%d%H%M%S}", [])
    recuentos = gdelt.ejecutar(almacen, descargador(falso), AHORA)
    assert (recuentos.franjas, recuentos.ausentes) == (25, 1)


def test_el_cursor_de_la_api_antigua_se_convierte(almacen: Almacen) -> None:
    falso = GdeltFalso("20250923114500")
    almacen.guardar_cursor("gdelt", {"hasta": "2025-09-23T11:40:12Z", "inicio": "y"})
    falso.poner("20250923113000", [], "ingles")
    falso.poner("20250923113000", [])
    falso.poner("20250923114500", [], "ingles")
    falso.poner("20250923114500", [])
    assert gdelt.ejecutar(almacen, descargador(falso), AHORA).franjas == 2
    assert almacen.cursor("gdelt") == {"franja": "2025-09-23T11:45:00Z", "inicio": "y"}


def test_tope_de_franjas_por_ejecucion(almacen: Almacen) -> None:
    falso = GdeltFalso("20250923114500")
    almacen.guardar_cursor("gdelt", {"franja": "2025-09-23T11:00:00Z", "inicio": "x"})
    for franja in ("1115", "1130", "1145"):
        falso.poner(f"20250923{franja}00", [], "ingles")
        falso.poner(f"20250923{franja}00", [])
    assert gdelt.ejecutar(almacen, descargador(falso), AHORA, max_franjas=2).franjas == 2
    assert almacen.cursor("gdelt") == {"franja": "2025-09-23T11:30:00Z", "inicio": "x"}


def test_mas_de_un_dia_pendiente_queda_en_rojo(almacen: Almacen) -> None:
    falso = GdeltFalso("20250923114500")
    falso.caido = True
    almacen.guardar_cursor("gdelt", {"franja": "2025-09-23T09:00:00Z", "inicio": "x"})
    assert gdelt.ejecutar(almacen, descargador(falso), AHORA).franjas == 0
    with pytest.raises(gdelt.GdeltNoDisponible):
        gdelt.ejecutar(almacen, descargador(falso), AHORA + timedelta(days=1))


def test_informe_por_mes_y_muestra(almacen: Almacen) -> None:
    gdelt.incorporar(almacen, [articulo(1, TITULAR, 30), articulo(2, TITULAR + " - TV2", 29)])
    texto = informe(almacen)
    assert "| 2025-09 | 1 | 1 | 1 |" in texto
    assert TITULAR in texto


def test_ubicacion_del_gkg_la_mas_precisa_en_europa() -> None:
    med = gdelt.medios()
    lugares = (
        "1#Norway#NO#NO#62#10#NO;5#Vestfold, Norway#NO#NO09#59.3#10.2#-1;"
        "4#Tonsberg, Vestfold, Norway#NO#NO09#59.2672#10.4076#-2;"
        "4#Moscow, Moskva, Russia#RS#RS48#55.75#37.61#-3"
    )
    (id_,) = med.ubicacion(lugares)
    assert id_.startswith("gkg:4:59.2672:10.4076:NO:Tonsberg")
    assert med.ubicacion("1#Norway#NO#NO#62#10#NO") == ()
