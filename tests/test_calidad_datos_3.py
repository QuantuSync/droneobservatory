"""Calidad de los datos, tercera parte: fecha del suceso comprobada con su frase, un incidente
por objetivo y suceso, los siete incidentes que faltaban, búsqueda dirigida, nivel de detalle e
indicadores."""

import copy
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from almacen.base import Almacen
from esquema import VERSION, Documento, Esquema, validador
from exportacion import procedencia as origenes
from proceso import detalle, extraccion, fechas, incidentes
from proceso.noticias import (
    Articulo,
    Candidato,
    agrupar,
    filtro,
    lugar,
    lugares_en,
    nomenclator,
    separar,
)
from proceso.ubicacion import Ubicacion, afinar
from proceso.validacion_ficha import Validada, fecha_valida, recuperar_inicio
from recogida import busqueda_dirigida, extractor, gdelt
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_extraccion import campo, extraer_ejemplo, ficha_ejemplo, suceso

AHORA = datetime(2026, 10, 2, 12, tzinfo=UTC)


def zona(pais: str) -> ZoneInfo:
    hallada = fechas.zona(pais)
    assert hallada is not None
    return hallada


BERLIN, LONDRES, BUCAREST = zona("DE"), zona("GB"), zona("RO")


def momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=UTC)


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


# --- Fecha del suceso -----------------------------------------------------------------


def dias(frase: str, publicacion: str, zona: Any, idioma: str | None) -> list[date]:
    return [lec.dia for lec in fechas.leer(frase, momento(publicacion), zona, idioma)]


def test_anoche_en_una_nota_de_la_manana_es_la_vispera() -> None:
    assert dias("Drones were spotted over Munich airport last night", "2025-10-03T05:40",
                LONDRES, "en") == [date(2025, 10, 2)]  # fmt: skip
    assert dias("In der Nacht wurden Drohnen gesichtet", "2025-10-03T05:40", BERLIN, "de") == [
        date(2025, 10, 2)
    ]


def test_la_fecha_relativa_se_resuelve_con_la_hora_local_del_medio() -> None:
    # Las 22:30 UTC del 2 de octubre son ya las 00:30 del 3 en Berlín: «heute» es el 3.
    assert dias("Heute wurden Drohnen gesichtet", "2025-10-02T22:30", BERLIN, "de") == [
        date(2025, 10, 3)
    ]
    assert dias("Heute wurden Drohnen gesichtet", "2025-10-02T22:30", fechas.zona("IS"), "de") == [
        date(2025, 10, 2)
    ]


@pytest.mark.parametrize(
    ("frase", "publicacion", "pais", "idioma", "dia"),
    [
        ("Københavns Lufthavn var lukket fra klokken 20.30 mandag aften", "2025-09-23T05:12",
         "DK", "da", date(2025, 9, 22)),
        ("am Donnerstagabend gegen 22 Uhr eingestellt worden", "2025-10-03T06:40", "DE", "de",
         date(2025, 10, 2)),
        ("In der Nacht zum Freitag wurden Drohnen gesichtet", "2025-10-04T08:00", "DE", "de",
         date(2025, 10, 2)),
        ("W nocy z wtorku na środę przestrzeń powietrzna Polski została naruszona",
         "2025-09-10T07:00", "PL", "pl", date(2025, 9, 9)),
        ("Le trafic aérien a été brièvement interrompu jeudi vers 21h20", "2025-11-07T08:00",
         "BE", "nl", date(2025, 11, 6)),  # frase en francés en una nota que GDELT da en neerlandés
        ("Alarmi u dha të premten në mbrëmje", "2026-09-19T08:00", "AL", "sq", date(2026, 9, 18)),
    ],
)  # fmt: skip
def test_dia_de_la_semana(frase: str, publicacion: str, pais: str, idioma: str, dia: date) -> None:
    assert dia in dias(frase, publicacion, fechas.zona(pais), idioma)


@pytest.mark.parametrize(
    ("frase", "idioma", "dia"),
    [
        ("Am 22.09. wurden Drohnen über dem Flughafen gesehen", "de", date(2025, 9, 22)),
        ("On 22nd of September 2025, drones closed the airport", "en", date(2025, 9, 22)),
        ("Le 4 novembre, des drones ont été aperçus", "fr", date(2025, 11, 4)),
        ("în dimineața zilei de 30 septembrie", "ro", date(2025, 9, 30)),
        ("Drones on 2025-09-22 over the airport", "en", date(2025, 9, 22)),
    ],
)
def test_fecha_explicita(frase: str, idioma: str, dia: date) -> None:
    assert dias(frase, "2025-11-06T10:00", BERLIN, idioma) == [dia]


def test_sin_expresion_de_dia_no_hay_lectura() -> None:
    assert dias("Flughafen München stellt Betrieb ein", "2025-10-03T21:30", BERLIN, "de") == []
    # «luni» (lunes en rumano) es también «meses»: solo cuenta con la parte del día.
    assert dias("în ultimele luni au fost observate drone", "2025-09-30T10:00", BUCAREST,
                "ro") == []  # fmt: skip


def resolver(valor: str | None, precision: str, frase: str, publicacion: str) -> fechas.Resolucion:
    return fechas.resolver(
        momento(valor) if valor else None, precision, [frase], momento(publicacion), BERLIN,
        BERLIN, "de",
    )  # fmt: skip


def test_el_dia_de_la_frase_corrige_el_de_la_ficha_y_conserva_la_hora() -> None:
    # El extractor dio el día de la noticia (3) a un cierre de la noche del jueves (2).
    hecho = resolver("2025-10-03T19:30", "hora", "am Donnerstagabend gegen 21.30 Uhr",
                     "2025-10-03T06:40")  # fmt: skip
    assert (hecho.valor, hecho.precision, hecho.origen, hecho.corregido) == (
        momento("2025-10-02T19:30"), "hora", "relativa", True,
    )  # fmt: skip
    # Un día que casa con la frase no cambia.
    hecho = resolver("2025-10-02T19:30", "hora", "am Donnerstagabend", "2025-10-03T06:40")
    assert (hecho.valor, hecho.corregido) == (momento("2025-10-02T19:30"), False)


def test_sin_dia_escrito_la_fecha_es_la_de_publicacion_aproximada() -> None:
    hecho = resolver("2025-11-06T00:00", "dia", "Bruxelles Lufthavn lukker flytrafikken",
                     "2025-11-06T09:15")  # fmt: skip
    assert (hecho.valor, hecho.precision, hecho.origen) == (
        momento("2025-11-06T09:15"), "aproximada", "publicacion",
    )  # fmt: skip
    assert "fecha de publicación" in hecho.motivo


def test_una_hora_sin_dia_se_conserva_con_el_dia_aproximado() -> None:
    hecho = resolver("2025-11-02T17:30", "hora", "gegen 19.30 Uhr im Bereich des Airports",
                     "2025-11-02T21:00")  # fmt: skip
    assert (hecho.valor, hecho.precision, hecho.origen) == (
        momento("2025-11-02T17:30"), "aproximada", "publicacion",
    )  # fmt: skip


def test_sin_inicio_en_la_ficha_la_fecha_es_la_primera_publicacion_aproximada() -> None:
    articulos = [
        {"url": "https://a.eu/1", "fecha": "2025-11-04T20:30:00Z", "pais": "BE", "idioma": "fr",
         "titular": "Drones à Liège"},
        {"url": "https://a.eu/2", "fecha": "2025-11-05T07:00:00Z", "pais": "BE", "idioma": "fr",
         "titular": "Drones à Liège"},
    ]  # fmt: skip
    hecho = fechas.inicio_de_ficha({}, [], articulos, "2025-11-04T20:30:00Z", "BE")
    assert (hecho.valor, hecho.precision, hecho.origen) == (
        momento("2025-11-04T20:30"), "aproximada", "publicacion",
    )  # fmt: skip


def test_el_incidente_declara_que_su_fecha_es_la_de_publicacion(almacen: Almacen) -> None:
    datos = ficha_ejemplo(inicio=campo(None), inicio_precision=campo(None))
    id_ = extraer_ejemplo(almacen, datos)
    incidente = almacen.incidente(str(id_))
    assert incidente is not None
    assert incidente["tiempo"]["inicio"]["precision"] == "aproximada"
    assert incidente["tiempo"]["origen_inicio"]["tipo"] == "publicacion"


def test_el_incidente_declara_el_dia_relativo_de_su_frase(almacen: Almacen) -> None:
    id_ = extraer_ejemplo(almacen)
    incidente = almacen.incidente(str(id_))
    assert incidente is not None
    origen = incidente["tiempo"]["origen_inicio"]
    assert origen["tipo"] == "relativa" and "mandag" in origen["motivo"]
    assert incidente["tiempo"]["inicio"] == ejemplos.instante("2025-09-22T18:30Z")


def test_el_inicio_se_compara_con_su_propia_nota() -> None:
    publicada = momento("2025-12-05T08:45")
    # Una nota de diciembre que vuelve sobre el 22 de septiembre: vale si escribe el día.
    assert fecha_valida("inicio", "2025-09-22", "the closure on 22 September", publicada,
                        AHORA) is None  # fmt: skip
    assert fecha_valida("inicio", "2025-09-22", "the closure in September", publicada, AHORA) == (
        "inicio más de una semana antes de su nota sin el día escrito"
    )
    assert fecha_valida("inicio", "2025-12-06", "", publicada, AHORA) == (
        "inicio posterior a su nota"
    )


def test_un_inicio_rechazado_solo_por_la_ventana_se_recupera() -> None:
    ficha_bruta = {"inicio": campo("2025-09-22", "Copenhagen airport closed on 22 September")}
    validada = Validada(campos={})
    motivos = ["inicio: inicio más de una semana antes del primer artículo"]
    recuperar_inicio(validada, ficha_bruta, motivos, (momento("2025-12-05T08:45"),), AHORA)
    assert validada.valor("inicio") == "2025-09-22"
    # Uno rechazado porque su frase no estaba en la fuente no se recupera.
    otra = Validada(campos={})
    recuperar_inicio(otra, ficha_bruta, ["inicio: la frase no está en la fuente"],
                     (momento("2025-12-05T08:45"),), AHORA)  # fmt: skip
    assert otra.valor("inicio") is None


def test_dia_escrito_solo_si_la_frase_da_el_dia() -> None:
    publicada = momento("2025-12-05T08:45")
    assert fechas.dia_escrito("2025-09-22", "am 22. September", publicada)
    assert not fechas.dia_escrito("2025-09-22", "im September", publicada)


# --- Fecha oficial -------------------------------------------------------------------


def fuente_oficial() -> Documento:
    return {**ejemplos.fuente("politi-1", "A"), "es_autoridad": True, "medio": "politi.dk",
            "enlace": "https://politi.dk/1"}  # fmt: skip


def test_la_fecha_oficial_manda_y_el_cambio_se_declara() -> None:
    tiempo = {"inicio": ejemplos.instante("2025-09-26T08:30Z", "hora")}
    oficial = ejemplos.instante("2025-09-25T21:44Z")
    nuevo = detalle.inicio_oficial(tiempo, oficial, fuente_oficial())
    assert nuevo["inicio"] == oficial
    assert (nuevo["origen_inicio"]["tipo"], nuevo["origen_inicio"]["corregido"]) == (
        "oficial", True,
    )  # fmt: skip


def test_un_dia_oficial_conserva_la_hora_de_la_prensa_del_mismo_dia() -> None:
    tiempo = {"inicio": ejemplos.instante("2024-12-23T19:00Z", "hora")}
    nuevo = detalle.inicio_oficial(tiempo, ejemplos.instante("2024-12-23T00:00Z", "dia"),
                                   fuente_oficial())  # fmt: skip
    assert nuevo["inicio"] == tiempo["inicio"]
    assert nuevo["origen_inicio"]["tipo"] == "oficial"
    assert "corregido" not in nuevo["origen_inicio"]


def test_el_punto_oficial_situa_un_incidente_sin_punto() -> None:
    lugar_ = {"pais": "DK", "nivel": "region", "region": "Nordjylland"}
    combinados = {"detalle_oficial.punto": {"lat": 57.09, "lon": 9.85},
                  "detalle_oficial.radio_km": 2.0}  # fmt: skip
    nuevo = detalle.punto_oficial(lugar_, combinados)
    assert nuevo["punto"] == {"lat": 57.09, "lon": 9.85}
    assert (nuevo["geocodificacion"], nuevo["nivel"]) == ("oficial", "localidad")
    # Con punto ya, no cambia; fuera del país, tampoco.
    con_punto = {**lugar_, "punto": {"lat": 57.0, "lon": 9.9}, "radio_km": 5}
    assert detalle.punto_oficial(con_punto, combinados) == con_punto
    fuera = {**combinados, "detalle_oficial.punto": {"lat": 40.4, "lon": -3.7}}
    assert detalle.punto_oficial(lugar_, fuera) == lugar_


# --- Fusión: un incidente por objetivo y suceso ----------------------------------------


def inc(
    id_: str,
    inicio: str,
    precision: str,
    objetivo: str = "Flughafen München",
    punto: tuple[float, float] = (48.354, 11.786),
    pais: str = "DE",
    fuentes: int = 1,
    primera: str | None = None,
) -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["id"] = id_
    documento["tiempo"] = {"inicio": ejemplos.instante(inicio, precision)}
    documento["lugar"] = {"punto": {"lat": punto[0], "lon": punto[1]}, "radio_km": 5,
                          "pais": pais}  # fmt: skip
    documento["objetivo"] = {"categoria": "aeropuerto", "nombre": objetivo}
    fecha = primera or inicio
    documento["fuentes"] = [
        {
            **ejemplos.fuente(f"F{id_[-3:]}-{n}", "C"),
            "fecha": ejemplos.instante(fecha, "aproximada"),
        }
        for n in range(fuentes)
    ]
    documento["estado"]["historial"][0]["fuente_id"] = documento["fuentes"][0]["id"]
    return documento


def test_la_misma_instalacion_dos_noches_seguidas_son_dos_incidentes() -> None:
    dos = inc("EODI-2025-00001", "2025-10-02T20:18Z", "minuto")
    tres = inc("EODI-2025-00002", "2025-10-03T19:30Z", "hora", primera="2025-10-04T06:00Z")
    assert not incidentes.encajan(dos, tres)
    # Aunque las noticias del primero sigan saliendo el día 3: no son actividad del suceso.
    dos["fuentes"].append(
        {
            **ejemplos.fuente("tarde", "C"),
            "fecha": ejemplos.instante("2025-10-03T18:00Z", "aproximada"),
        }
    )
    assert not incidentes.encajan(dos, tres)


def test_dos_objetivos_la_misma_noche_son_dos_incidentes() -> None:
    bruselas = inc("EODI-2025-00001", "2025-11-04T18:45Z", "minuto", "Brussels Airport",
                   (50.901, 4.484), "BE")  # fmt: skip
    lieja = inc("EODI-2025-00002", "2025-11-04T19:09Z", "minuto", "Liège Airport",
                (50.637, 5.443), "BE")  # fmt: skip
    assert not incidentes.encajan(bruselas, lieja)


def test_la_fecha_de_publicacion_casa_con_el_suceso_de_la_vispera() -> None:
    suceso_ = inc("EODI-2025-00001", "2025-10-02T20:18Z", "minuto")
    nota = inc("EODI-2025-00002", "2025-10-03T06:40Z", "aproximada")
    assert incidentes.encajan(suceso_, nota)
    # Con el día escrito, el día siguiente es otro suceso.
    otro_dia = inc("EODI-2025-00003", "2025-10-03T00:00Z", "dia")
    assert not incidentes.encajan(suceso_, otro_dia)


def test_la_madrugada_es_la_noche_de_la_vispera_en_hora_local() -> None:
    # La 01:00 en Galați (22:00 UTC del 28) y un suceso fechado el 28 por «anoche».
    hora = inc("EODI-2026-00001", "2026-05-28T22:00Z", "hora", "Galaţi", (45.437, 28.05), "RO")
    vispera = inc("EODI-2026-00002", "2026-05-28T00:00Z", "dia", "Galaţi", (45.437, 28.05), "RO")
    dia = inc("EODI-2026-00003", "2026-05-29T00:00Z", "dia", "Galaţi", (45.437, 28.05), "RO")
    assert incidentes.encajan(vispera, hora) and incidentes.encajan(hora, dia)


def test_en_la_fusion_queda_el_publicado_y_despues_el_de_mas_fuentes_oficiales(
    almacen: Almacen,
) -> None:
    original = inc("EODI-2025-00154", "2025-09-22T18:30Z", "hora", fuentes=3,
                   primera="2025-09-22T19:45Z")  # fmt: skip
    retrospectiva = inc("EODI-2025-00025", "2025-09-22T00:00Z", "dia", primera="2025-12-05T08:45Z")
    for documento in (original, retrospectiva):
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS) == 1
    fundido = almacen.incidente("EODI-2025-00025")
    assert fundido is not None and fundido["fusionado_en"] == "EODI-2025-00154"
    destino, _ = incidentes.destino_de(retrospectiva, original, frozenset({"EODI-2025-00025"}))
    assert destino["id"] == "EODI-2025-00025"  # solo él estaba publicado


def test_lo_que_hereda_el_destino_lleva_su_afirmacion_aunque_compartan_fuente() -> None:
    destino = inc("EODI-2025-00001", "2025-10-02T20:18Z", "minuto")
    absorbido = inc("EODI-2025-00002", "2025-10-02T21:00Z", "hora")
    compartida = destino["fuentes"][0]
    absorbido["fuentes"] = [compartida]
    absorbido["respuesta"] = {"medidas": ["patrulla"]}
    afirmacion = {"campo": "medidas", "valor": ["patrulla"], "fuente_id": compartida["id"],
                  "confianza_extraccion": 0.9}  # fmt: skip
    absorbido["afirmaciones"] = [afirmacion]
    nuevo, aportadas = incidentes.absorber(destino, absorbido, AHORA)
    assert aportadas == [] and nuevo["respuesta"] == {"medidas": ["patrulla"]}
    assert afirmacion in nuevo["afirmaciones"]
    exportado = exportar(nuevo)
    assert exportado["procedencia"]["respuesta.medidas"]["origen"] == "prensa"


def test_un_dia_con_hora_no_hace_de_puente_hacia_la_noche_siguiente() -> None:
    # El extractor dio «2 de octubre, 22:00 UTC» con precisión de día: cuenta su fecha, el 2,
    # y el cierre del 3 por la tarde es otro suceso. Dos días seguidos sin hora sí casan.
    puente = inc("EODI-2025-00001", "2025-10-02T22:00Z", "dia")
    tercero = inc("EODI-2025-00002", "2025-10-03T19:30Z", "hora")
    assert not incidentes.encajan(puente, tercero)
    assert incidentes.encajan(puente, inc("EODI-2025-00003", "2025-10-03T00:00Z", "dia"))
    # Con un fin conocido se miden las 12 horas sin actividad aunque el inicio sea un día.
    puente["tiempo"]["fin"] = ejemplos.instante("2025-10-03T03:00Z")
    tercero["tiempo"]["inicio"] = ejemplos.instante("2025-10-03T17:30Z", "hora")
    assert not incidentes.encajan(puente, tercero)


def test_la_fusion_dudosa_no_se_hace(almacen: Almacen) -> None:
    for documento in (
        inc("EODI-2025-00001", "2025-10-02T20:18Z", "minuto"),
        inc("EODI-2025-00002", "2025-10-03T19:30Z", "hora"),
        # La nota del 3 por la noche encaja con los dos: no se funde.
        inc("EODI-2025-00003", "2025-10-03T20:00Z", "aproximada"),
    ):
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    assert incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS) == 0


def test_una_fecha_de_publicacion_no_compite_con_una_escrita(almacen: Almacen) -> None:
    for documento in (
        inc("EODI-2025-00001", "2025-10-03T19:00Z", "hora"),
        inc("EODI-2025-00002", "2025-10-03T19:30Z", "aproximada"),
        # Una hora del 4 de madrugada encaja con el cierre del 3 y con la nota: va al cierre.
        inc("EODI-2025-00003", "2025-10-04T00:00Z", "hora"),
    ):
        almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    incidentes.fusionar(almacen, AHORA, VOCABULARIO_MODELOS)
    fundido = almacen.incidente("EODI-2025-00003")
    assert fundido is not None and fundido["fusionado_en"] == "EODI-2025-00001"


# --- Los incidentes que faltaban ------------------------------------------------------


def articulo(titular: str, fecha: str, url: str, lugares: tuple[str, ...] = ("EDDM",)) -> Articulo:
    return Articulo(url=url, medio=url.split("/")[2], fecha=momento(fecha), titular=titular,
                    idioma="de", pais="DE", lugares=lugares)  # fmt: skip


MUNICH = [
    articulo("Flughafen München: Flugausfälle wegen Drohnensichtungen", "2025-10-03T00:00",
             "https://a.de/1"),
    articulo("Drohnen am Flughafen München: Was bekannt ist", "2025-10-03T08:00",
             "https://f.de/6"),
    articulo("Munich airport reopens after overnight closure", "2025-10-03T18:15", "https://b.de/2"),
    articulo("Flughafen München stellt wegen Drohnen erneut den Betrieb ein", "2025-10-03T21:30",
             "https://c.de/3"),
    articulo("Tausende Menschen gestrandet am Flughafen München", "2025-10-03T23:45",
             "https://d.de/4"),
]  # fmt: skip


def test_munich_el_titular_de_repeticion_separa_el_segundo_cierre() -> None:
    resultado = agrupar(MUNICH, filtro(), nomenclator())
    assert [len(c.articulos) for c in resultado.candidatos] == [3, 2]
    segundo = resultado.candidatos[1]
    assert segundo.separado_de == resultado.candidatos[0].id
    # Lo que llega después, sin la palabra, va al suceso más reciente.
    assert "https://d.de/4" in segundo.articulos


def test_una_repeticion_antes_de_18_horas_es_el_mismo_suceso() -> None:
    temprano = [MUNICH[0], articulo("Wieder Drohnenalarm in München", "2025-10-03T09:00",
                                    "https://e.de/5")]  # fmt: skip
    assert len(agrupar(temprano, filtro(), nomenclator()).candidatos) == 1


def test_separar_un_candidato_agrupado_antes_de_la_regla() -> None:
    sitio = lugar("EDDM", nomenclator())
    viejo = Candidato("CAND-20251003T0000-EDDM-aeropuerto", "aeropuerto", sitio,
                      momento("2025-10-03T00:00"), momento("2025-10-03T23:45"), "dia",
                      [a.url for a in MUNICH])  # fmt: skip
    grupos = separar(viejo, MUNICH, filtro())
    assert [g.id for g in grupos] == [viejo.id, "CAND-20251003T2130-EDDM-aeropuerto"]
    # Repasar lo ya separado no cambia nada.
    assert len(separar(grupos[0], MUNICH[:3], filtro())) == 1


@pytest.mark.parametrize(
    ("titular", "esperados"),
    [
        ("Drones over Sonderborg airport", {"EKSB"}),  # «ø» plegada
        ("Danish Police Says Drones Observed by Airports in Esbjerg, Sonderborg, Skrydstrup",
         {"EKEB", "EKSB", "EKSP"}),
        ("Mulig droneobservasjon på kampflybasen på Ørlandet", {"ENOL"}),  # forma definida
        ("Politiet: Gode observasjoner av droner ved kampflybasen på Ørland", {"ENOL"}),
    ],
)  # fmt: skip
def test_instalaciones_que_antes_no_se_reconocian(titular: str, esperados: set[str]) -> None:
    assert set(lugares_en(titular, nomenclator())) == esperados


def test_lieja_un_incidente_por_objetivo() -> None:
    validada = Validada(campos={
        "es_incidente": campo(True, "x"),
        "lugar_suceso": campo(suceso("Brussels Airport", "instalacion", "BE"), "Brussels Airport"),
        "objetivo_conocido": campo(False, "Brussels Airport"),
    })  # fmt: skip
    articulos = [
        {"url": "https://a.be/1", "titular": "Brussels, Liege airports closed due to drones"},
        {"url": "https://b.be/2", "titular": "Les aéroports de Bruxelles et de Liège fermés"},
        {"url": "https://c.be/3", "titular": "Chiuso anche aeroporto di Liegi"},
    ]  # fmt: skip
    assert extraccion.objetivo_compartido(validada, "EBLG", articulos, ["https://a.be/1"])
    assert validada.valor("lugar_suceso")["nombre"] == lugar("EBLG", nomenclator()).nombre
    assert validada.valor("objetivo_conocido") is True


def test_objetivo_compartido_necesita_dos_titulares_y_no_cuenta_siglas() -> None:
    def con_suceso() -> Validada:
        return Validada(campos={
            "lugar_suceso": campo(suceso("Flughafen Leipzig/Halle", "instalacion", "DE"), "x"),
            "objetivo_conocido": campo(False, "x"),
        })  # fmt: skip

    uno = [{"url": "https://a/1", "titular": "Brussels, Liege airports closed"}]
    assert not extraccion.objetivo_compartido(
        Validada(campos={"lugar_suceso": campo(suceso("Brussels Airport", "instalacion", "BE"),
                                               "x"),
                         "objetivo_conocido": campo(False, "x")}), "EBLG", uno, [],
    )  # fmt: skip
    # «NATO» es una ciudad de Geilenkirchen en OpenStreetMap: no la nombra.
    otan = [{"url": f"https://a/{n}", "titular": "NATO: Drohne über Flughafen Leipzig"}
            for n in range(3)]  # fmt: skip
    assert not extraccion.objetivo_compartido(con_suceso(), "ETNG", otan, [])


def test_esbjerg_y_skrydstrup_los_nunca_extraidos_con_varios_medios_tienen_prioridad(
    almacen: Almacen,
) -> None:
    gdelt.incorporar(almacen, [
        Articulo("https://sme.sk/1", "sme.sk", momento("2025-09-25T04:45"),
                 "Letisko v dánskom Aalborgu uzavreli pre drony, ktoré zachytili aj v okolí "
                 "letísk Esbjerg, Sönderborg a Skrydstrup", "sk", "SK", (), ("EKEB", "EKSP")),
        Articulo("https://reuters.com/2", "reuters.com", momento("2025-09-25T04:45"),
                 "Danish Police Says Drones Observed by Airports in Esbjerg, Sonderborg, "
                 "Skrydstrup -Reports", "en", None, (), ("EKEB", "EKSP")),
        Articulo("https://x.dk/3", "x.dk", momento("2025-09-26T10:00"), "Drone i Billund lufthavn",
                 "da", "DK", (), ("EKBI",)),
    ])  # fmt: skip
    elegidos = {c["lugar"] for c in extractor.prioritarios(almacen)}
    assert elegidos == {"EKEB", "EKSP"}  # Billund, con un solo medio, no


def test_kiel_se_afina_de_la_region_a_la_localidad() -> None:
    ubicacion = Ubicacion("DE", "region", nombre="Schleswig-Holstein", region="Schleswig-Holstein")
    textos = (
        "Kraftwerk, Klinikum, Landtag: Drohnen über Schleswig-Holstein spähten offenbar aus",
        "Drohnensichtungen über Kraftwerk, Klinik und Werft in Kiel",
    )
    afinada = afinar(ubicacion, textos, nomenclator())
    assert afinada.sitio is not None and afinada.sitio.nombre == "Kiel"
    assert (afinada.origen, afinada.nivel) == ("frase_origen", "localidad")


def test_la_localidad_que_se_llama_como_la_region_no_afina() -> None:
    ubicacion = Ubicacion("RO", "region", nombre="Tulcea County", region="Tulcea")
    afinada = afinar(ubicacion, ("Dronă prăbușită în Tulcea",), nomenclator())
    assert afinada.sitio is None
    # Un suceso de nivel país no se afina: la capital del ministro no es el lugar.
    pais = Ubicacion("LT", "pais", nombre="Lituania")
    assert afinar(pais, ("Vilnius: NATO jets shot down a drone",), nomenclator()).sitio is None


# --- Búsqueda dirigida -----------------------------------------------------------------


ANOMALIA: Documento = {
    "oaci": "EBLG", "inicio": "2025-11-04T19:09Z", "fin": "2025-11-05T00:45Z",
    "duracion_min": 336, "estado": "candidata", "motivos_meteorologicos": [],
    "cobertura": {"nivel": "alta", "vistos": 160, "indice": 0.87},
}  # fmt: skip


def test_los_nombres_del_aeropuerto_incluyen_su_ciudad_en_otros_idiomas() -> None:
    nombres = busqueda_dirigida.nombres("EBLG", nomenclator())
    assert {"liege", "luttich", "luik", "lieja", "liegi"} <= nombres


def test_un_nombre_de_una_palabra_tiene_que_ir_con_mayuscula() -> None:
    # «Leck» es un nombre de Lieja en GeoNames y «leck», una fuga en neerlandés.
    nombres = {"leck", "luik"}
    assert busqueda_dirigida.nombra("Drone boven Luik gesignaleerd", nombres)
    assert not busqueda_dirigida.nombra("Drone met een leck in de tank", nombres)


def titulares_del_dia(franja: datetime) -> list[Articulo]:
    if franja == momento("2025-11-04T20:00"):
        return [
            Articulo("https://lesoir.be/1", "lesoir.be", franja,
                     "Des drones survolent Liège, le trafic est interrompu", "fr", "BE"),
            Articulo("https://x.de/2", "x.de", franja, "Drohnen über München", "de", "DE"),
        ]  # fmt: skip
    if franja == momento("2025-11-05T07:00"):
        return [Articulo("https://hln.be/3", "hln.be", franja, "Drones boven Luik", "nl", "BE")]
    return []


def test_la_busqueda_lee_cada_dia_una_vez_y_deja_lo_hallado(tmp_path: Path) -> None:
    (tmp_path / busqueda_dirigida.ANOMALIAS).write_text(
        json.dumps({"anomalias": [ANOMALIA]}), encoding="utf-8"
    )
    llamadas: list[datetime] = []

    def lector(franja: datetime) -> list[Articulo]:
        llamadas.append(franja)
        return titulares_del_dia(franja)

    recuentos = busqueda_dirigida.buscar(tmp_path, lector)
    assert recuentos == {"anomalias": 1, "dias_leidos": 2, "con_noticias": 1}
    assert len(llamadas) == 2 * busqueda_dirigida.FRANJAS_DIA
    hallado = json.loads(next((tmp_path / busqueda_dirigida.HALLADOS).glob("*.json")).read_text(
        encoding="utf-8"))  # fmt: skip
    assert [a["url"] for a in hallado["articulos"]] == ["https://lesoir.be/1", "https://hln.be/3"]
    # Otra anomalía del mismo día no vuelve a bajar nada.
    otra = {**ANOMALIA, "inicio": "2025-11-04T22:28Z"}
    (tmp_path / busqueda_dirigida.ANOMALIAS).write_text(
        json.dumps({"anomalias": [ANOMALIA, otra]}), encoding="utf-8"
    )
    llamadas.clear()
    assert busqueda_dirigida.buscar(tmp_path, lector)["anomalias"] == 1
    assert llamadas == []


def test_lo_hallado_entra_por_el_flujo_normal_y_la_anomalia_queda_buscada(
    almacen: Almacen, tmp_path: Path
) -> None:
    almacen.guardar_anomalia({**ANOMALIA, "regla": {"nombre": "trafico_aereo", "version": "1.0.0"},
                              "evaluado": ejemplos.instante("2026-10-01T19:17Z")})  # fmt: skip
    assert [busqueda_dirigida.identificador(a) for a in busqueda_dirigida.elegibles(almacen)] == [
        "EBLG/2025-11-04T19:09Z"
    ]
    (tmp_path / busqueda_dirigida.ANOMALIAS).write_text(
        json.dumps({"anomalias": [ANOMALIA]}), encoding="utf-8"
    )
    busqueda_dirigida.buscar(tmp_path, titulares_del_dia)
    hecho = busqueda_dirigida.incorporar(almacen, tmp_path, AHORA)
    assert (hecho.anomalias, hecho.con_noticias, hecho.articulos) == (1, 1, 2)
    [candidato] = [c for c in almacen.candidatos() if c["lugar"] == "EBLG"]
    assert len(candidato["articulos"]) == 2
    assert busqueda_dirigida.elegibles(almacen) == []
    # Su candidato va delante en el extractor.
    assert extractor.prioritarios(almacen)[0]["id"] == candidato["id"]
    # Incorporar otra vez no duplica nada.
    assert busqueda_dirigida.incorporar(almacen, tmp_path, AHORA).anomalias == 0


def test_solo_se_buscan_las_de_cobertura_alta_sin_mal_tiempo(almacen: Almacen) -> None:
    base = {**ANOMALIA, "regla": {"nombre": "trafico_aereo", "version": "1.0.0"},
            "evaluado": ejemplos.instante("2026-10-01T19:17Z")}  # fmt: skip
    almacen.guardar_anomalia({**base, "cobertura": {"nivel": "media", "vistos": 90, "indice": 0.6}})
    almacen.guardar_anomalia({**base, "inicio": "2025-11-05T10:00Z", "motivos_meteorologicos":
                              ["niebla"]})  # fmt: skip
    assert busqueda_dirigida.elegibles(almacen) == []


# --- Nivel de detalle e indicadores ----------------------------------------------------


def de_prensa(precision: str = "minuto", radio: float = 3) -> Documento:
    documento = ejemplos.incidente_minimo()
    documento["tiempo"] = {"inicio": ejemplos.instante("2025-09-22T18:30Z", precision)}
    documento["lugar"]["radio_km"] = radio
    documento["fuentes"] = [{**ejemplos.fuente("F1", "C"), "campos_respaldados": []}]
    return documento


def con_cierre(documento: Documento, nivel: str = "alta") -> Documento:
    resultado = copy.deepcopy(documento)
    medido = ejemplos.trafico_aereo()
    medido["cierre"]["cobertura"]["nivel"] = nivel
    resultado["trafico_aereo"] = medido
    return resultado


def exportar(documento: Documento) -> Documento:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(documento, AHORA, VOCABULARIO_MODELOS)
    return origenes.exportar_incidente(documento, origenes.Fichas.de(almacen))


def test_b_con_un_cierre_medido_en_un_aeropuerto_de_cobertura_alta() -> None:
    assert exportar(de_prensa())["nivel_detalle"] == "D"
    assert exportar(con_cierre(de_prensa()))["nivel_detalle"] == "B"
    # Con cobertura media no basta; sin la precisión de B, tampoco.
    assert exportar(con_cierre(de_prensa(), "media"))["nivel_detalle"] == "D"
    assert exportar(con_cierre(de_prensa("dia")))["nivel_detalle"] == "D"
    assert exportar(con_cierre(de_prensa(radio=10)))["nivel_detalle"] == "D"


def test_indicadores() -> None:
    vacio = exportar(de_prensa())["indicadores"]
    assert vacio == {
        "tiene_cierre_medido": False, "tiene_condiciones_medidas": False,
        "tiene_respuesta_militar_observada": False, "tiene_interferencia_gnss_medida": False,
        "tiene_foco_termico": False, "tiene_confirmacion_oficial_directa": False,
        "fecha_del_suceso_verificada": False,
    }  # fmt: skip
    completo = con_cierre(de_prensa())
    completo["condiciones"] = ejemplos.condiciones()
    completo["foco_termico"] = ejemplos.foco_termico()
    completo["tiempo"]["origen_inicio"] = {"tipo": "relativa", "motivo": "«mandag»"}
    oficial = {**ejemplos.fuente("politi-1", "A"), "es_autoridad": True,
               "campos_respaldados": ["estado"]}  # fmt: skip
    completo["fuentes"].append(oficial)
    completo["estado"] = {"actual": "confirmado", "historial": [
        *completo["estado"]["historial"],
        {"estado": "confirmado", "fecha": ejemplos.instante("2025-09-23T08:00Z"),
         "fuente_id": "politi-1"},
    ]}  # fmt: skip
    exportado = exportar(completo)
    indicadores = exportado["indicadores"]
    assert indicadores["tiene_cierre_medido"] and indicadores["tiene_condiciones_medidas"]
    assert indicadores["tiene_respuesta_militar_observada"]
    assert indicadores["tiene_foco_termico"] and indicadores["tiene_confirmacion_oficial_directa"]
    assert indicadores["fecha_del_suceso_verificada"]
    assert validador(Esquema.INCIDENTE).is_valid(exportado)


def test_la_fecha_la_verifica_un_cierre_medido_ese_dia() -> None:
    publicada = de_prensa("aproximada")
    publicada["tiempo"]["origen_inicio"] = {"tipo": "publicacion"}
    assert not exportar(publicada)["indicadores"]["fecha_del_suceso_verificada"]
    assert exportar(con_cierre(publicada))["indicadores"]["fecha_del_suceso_verificada"]
    otro_dia = con_cierre(publicada)
    otro_dia["tiempo"]["inicio"] = ejemplos.instante("2025-09-24T08:00Z", "aproximada")
    assert not exportar(otro_dia)["indicadores"]["fecha_del_suceso_verificada"]


# --- Cruces con una fecha de publicación -------------------------------------------------


def test_la_fecha_de_publicacion_abre_la_ventana_de_trafico_y_de_firms_a_la_vispera() -> None:
    from proceso import focos_termicos, trafico

    documento = de_prensa("aproximada")
    documento["tiempo"]["inicio"] = ejemplos.instante("2025-11-05T07:00Z", "aproximada")
    inicio, fin, precision = trafico.ventana_incidente(documento)
    assert (datetime.fromtimestamp(inicio, UTC), datetime.fromtimestamp(fin, UTC), precision) == (
        momento("2025-11-04T00:00"), momento("2025-11-05T07:00"), "dia",
    )  # fmt: skip
    documento["pruebas"] = {"dron_estatal": True, "entrada_exterior": True, "evidencia": ["caida"]}
    impacto = focos_termicos.impacto_de_incidente(documento)
    assert impacto is not None and impacto.inicio == momento("2025-11-04T07:00")


# --- Esquema ------------------------------------------------------------------------


def test_esquema_1_6_0_con_el_origen_del_inicio() -> None:
    # 1.6.0 o posterior de la misma mayor (el motor de deducción subió a 1.7.0).
    assert tuple(int(x) for x in VERSION.split(".")) >= (1, 6, 0)
    documento = ejemplos.incidente_minimo()
    documento["tiempo"]["origen_inicio"] = {"tipo": "publicacion", "motivo": "x", "corregido": True}
    assert validador(Esquema.INCIDENTE).is_valid(documento)
    documento["tiempo"]["origen_inicio"]["tipo"] = "inventada"
    assert not validador(Esquema.INCIDENTE).is_valid(documento)


def test_las_fechas_aproximadas_no_cambian_lo_que_ya_estaba_bien() -> None:
    # Un suceso fechado al minuto y su nota de la misma tarde siguen encajando.
    suceso_ = inc("EODI-2025-00001", "2025-09-22T18:26Z", "minuto", "Københavns Lufthavn",
                  (55.618, 12.656), "DK")  # fmt: skip
    nota = inc("EODI-2025-00002", "2025-09-22T21:00Z", "aproximada", "Københavns Lufthavn",
               (55.618, 12.656), "DK")  # fmt: skip
    assert incidentes.encajan(suceso_, nota)
    assert timedelta(hours=1) < incidentes.MADRUGADA


def test_el_vocabulario_describe_cada_indicador_y_cada_origen_del_inicio() -> None:
    from exportacion import semanal

    vocabulario = semanal.vocabulario()
    # 1.2.0 o posteriores (el motor de deducción subió los dos a 1.3.0).
    assert vocabulario["version"] >= "1.2.0" and semanal.VERSION_FORMATO >= "1.2.0"
    assert set(vocabulario["indicadores"]) == set(exportar(de_prensa())["indicadores"])
    assert set(vocabulario["origenes_inicio"]) == {
        "explicita", "relativa", "oficial", "parte", "publicacion",
    }  # fmt: skip
