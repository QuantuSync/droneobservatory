"""Calidad de los datos: lugar del suceso, fronteras, tipo, presencia del dron, cierre y
episodios, con los tres casos reales que los mostraron (Ibiza, Estonia y Anenii Noi)."""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from exportacion import publicar
from exportacion.geojson import exportar, exportar_sin_ubicacion
from modelo import cliente as cliente_servicio
from modelo import coste, ficha
from proceso import declaraciones, extraccion, incidentes
from proceso.fronteras import dentro_del_pais, es_nombre_de_pais
from proceso.noticias import Articulo, localidades_declinadas, lugares_en, nomenclator
from proceso.ubicacion import Objetivo, Pistas, ubicar
from proceso.validacion_ficha import Contexto, Validada, nombrado_en, revalidar, validar
from recogida import extractor, gdelt, revision
from tests import ejemplos
from tests.test_extraccion import MODELOS, campo, respuesta, suceso

AHORA = datetime(2026, 9, 30, 12, tzinfo=UTC)

# --- Textos reales ---------------------------------------------------------------------

IBIZA = (
    "DRON AEROPUERTO DE IBIZA | El equipo Pegaso de la Guardia Civil investiga el vuelo del "
    "dron que paralizó el aeropuerto de Ibiza durante 35 minutos. El vuelo del dron que "
    "paralizó el aeropuerto de Ibiza"
)
ESTONIA = (
    "Ukraine drone shot down by NATO jet over Estonia. Ukraine has blamed Russia for steering "
    "one of its drones into Estonian airspace where a NATO jet shot it down. It later said it "
    "found no evidence that a drone had entered its air space."
)
ANENII_NOI = (
    "ALERTĂ de securitate: O dronă a survolat spațiul aerian al Moldovei și a explodat în "
    "raionul Anenii Noi. O dronă a pătruns în spațiul aerian al Republicii Moldova în "
    "dimineața zilei de 30 septembrie, prăbușindu-se și explodând ulterior în raionul Anenii "
    "Noi. Ministerul Apărării a confirmat incidentul."
)
LA_GUARDIA = "aeropuerto:node/4437532936"
FUENTES_DE_ANDALUCIA = "loc:2517500"
FUNDU_MOLDOVEI = "loc:677788"
ANENII = "loc:617702"


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def candidato(almacen: Almacen, lugar: str, titular: str, n: int = 1) -> dict[str, Any]:
    """Un candidato del lugar que casó en el titular, con un artículo."""
    articulo = Articulo(
        url=f"https://medio{n}.eu/nota/{n}", medio=f"medio{n}.eu",
        fecha=AHORA - timedelta(hours=2), titular=titular, idioma="es", pais=None,
        lugares=(lugar,),
    )  # fmt: skip
    gdelt.incorporar(almacen, [articulo])
    (hallado,) = [c for c in almacen.candidatos() if articulo.url in c["articulos"]]
    return hallado


def extraer(
    almacen: Almacen, cand: dict[str, Any], texto: str, datos: dict[str, Any]
) -> str | None:
    peticion = extraccion.preparar(almacen, cand, None)
    fuentes = [replace(f, texto=texto) for f in peticion.fuentes]
    peticion = replace(peticion, fuentes=fuentes)
    return extraccion.procesar_respuesta(
        almacen, peticion, respuesta(datos), AHORA, coste.Modo.REVISION, True, MODELOS
    )


def datos(**campos: Any) -> dict[str, Any]:
    base: dict[str, Any] = {nombre: campo(None) for nombre in ficha.CAMPOS}
    base |= {"titulo_es": "Título", "titulo_en": "Title"}
    return base | campos


# --- Los tres casos reales ---------------------------------------------------------------


def test_ibiza_va_a_su_aeropuerto_y_no_al_aerodromo_de_la_guardia(almacen: Almacen) -> None:
    # «la Guardia Civil» casó con el aeródromo de La Guardia (Toledo): el candidato estaba allí.
    cand = candidato(almacen, LA_GUARDIA, "Dron que paralizó el aeropuerto de Ibiza")
    frase = "paralizó el aeropuerto de Ibiza durante 35 minutos"
    id_ = extraer(almacen, cand, IBIZA, datos(
        es_incidente=campo(True, frase), pais=campo("ES", frase),
        lugar_suceso=campo(suceso("aeropuerto de Ibiza", "instalacion", "ES", "Islas Baleares"),
                           frase),
        objetivo_conocido=campo(False, frase), cierre=campo("si", frase),
        cierre_minutos=campo({"min": 35, "max": 35}, frase),
    ))  # fmt: skip
    incidente = almacen.incidente(id_ or "")
    assert incidente is not None
    assert incidente["objetivo"]["oaci"] == "LEIB"
    assert incidente["lugar"]["punto"] == {"lat": 38.87313, "lon": 1.37245}
    assert incidente["tipo"] == "interrupcion_aeroportuaria"


def test_estonia_no_va_a_andalucia_y_se_publica_sin_punto(almacen: Almacen) -> None:
    # «Ukraine» era un nombre alternativo de Fuentes de Andalucía en GeoNames.
    cand = candidato(almacen, FUENTES_DE_ANDALUCIA, "Ukraine drone shot down over Estonia")
    frase = "Ukraine drone shot down by NATO jet over Estonia"
    id_ = extraer(almacen, cand, ESTONIA, datos(
        es_incidente=campo(True, frase), pais=campo("EE", frase),
        lugar_suceso=campo(suceso("Estonia", "pais", "EE"), frase),
        objetivo_conocido=campo(False, frase), dron_estatal=campo(True, frase),
        entrada_exterior=campo(True, "steering one of its drones into Estonian airspace"),
        evidencia=campo(["derribo"], "a NATO jet shot it down"),
    ))  # fmt: skip
    incidente = almacen.incidente(id_ or "")
    assert incidente is not None
    assert incidente["lugar"] == {"pais": "EE", "nivel": "pais", "suceso": "Estonia"}
    assert incidente["tipo"] == "incursion"
    geojson = exportar(almacen.incidentes(), AHORA, MODELOS)
    sin_punto = exportar_sin_ubicacion(almacen.incidentes(), AHORA, MODELOS)
    assert geojson["features"] == []
    assert [i["id"] for i in sin_punto["incidentes"]] == [id_]
    assert sin_punto["incidentes"][0]["lugar"] == {"pais": "EE", "nivel": "pais"}


def test_anenii_noi_es_incursion_con_dron_confirmado_y_sin_cierre(almacen: Almacen) -> None:
    cand = candidato(almacen, ANENII, "O dronă a explodat în raionul Anenii Noi")
    frase = "prăbușindu-se și explodând ulterior în raionul Anenii Noi"
    entrada = "O dronă a pătruns în spațiul aerian al Republicii Moldova"
    datos_ = datos(
        es_incidente=campo(True, entrada), pais=campo("MD", entrada),
        lugar_suceso=campo(suceso("Anenii Noi", "localidad", "MD", "Anenii Noi"), frase),
        entrada_exterior=campo(True, entrada), evidencia=campo(["caida", "explosion"], frase),
        presencia_dron=campo("no_confirmada", entrada),
    )  # fmt: skip
    peticion = extraccion.preparar(almacen, cand, None)
    peticion = replace(peticion, fuentes=[replace(f, texto=ANENII_NOI) for f in peticion.fuentes])
    bruta = respuesta(datos_)
    salida = json.loads(bruta["content"][0]["text"])
    salida["declaraciones"] = [{
        "autoridad": "Ministerul Apărării", "pais": "MD", "categoria": "ministerio",
        "afirma": "incidente", "autor": "", "fuente": 1,
        "frase": "Ministerul Apărării a confirmat incidentul.",
    }]  # fmt: skip
    bruta["content"][0]["text"] = json.dumps(salida, ensure_ascii=False)
    id_ = extraccion.procesar_respuesta(
        almacen, peticion, bruta, AHORA, coste.Modo.REVISION, True, MODELOS
    )
    incidente = almacen.incidente(id_ or "")
    assert incidente is not None
    assert incidente["estado"]["actual"] == "confirmado"
    # Explotó: el dron era militar; entró desde fuera y el ministerio lo confirma.
    assert incidente["tipo"] == "incursion"
    assert incidente["origen_demostrado_por"] == ["autoridad", "caida", "explosion"]
    # El incidente confirmado es el propio dron: la confirmación confirma el dron.
    assert incidente["presencia_dron"] == "confirmada"
    # La fuente no habla de cierre: desconocido, nunca un cierre sin confirmar inventado.
    assert incidente["consecuencias"]["cierre"] == {"valor": "desconocido"}
    assert (incidente["lugar"]["pais"], incidente["lugar"]["punto"]) == (
        "MD", {"lat": 46.87795, "lon": 29.23503},
    )  # fmt: skip


def test_moldova_ya_no_es_un_nombre_de_fundu_moldovei() -> None:
    titular = "O dronă a survolat spațiul aerian al Republicii Moldova"
    assert localidades_declinadas(titular, nomenclator()) == ()
    assert localidades_declinadas("Ukraine-Krieg: Drohne über Estland", nomenclator()) == ()
    assert es_nombre_de_pais("moldova") and es_nombre_de_pais("ukraine")
    assert FUNDU_MOLDOVEI in nomenclator().lugares


# --- Fronteras ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pais", "lat", "lon", "dentro"),
    [
        ("ES", 38.87313, 1.37245, True),  # aeropuerto de Ibiza
        ("EE", 37.46409, -5.34615, False),  # Fuentes de Andalucía no es Estonia
        ("MD", 47.53333, 25.4, False),  # Fundu Moldovei es Rumanía
        ("RO", 47.53333, 25.4, True),
        ("MD", 46.87795, 29.23503, True),  # Anenii Noi
        ("FI", 59.83, 29.03, False),  # central de Leningrado: tierra rusa
        ("NO", 58.5, 2.0, False),  # mar del Norte, lejos de la costa
    ],
)
def test_el_punto_cae_en_su_pais(pais: str, lat: float, lon: float, dentro: bool) -> None:
    assert dentro_del_pais(pais, lat, lon) is dentro


def test_un_punto_fuera_de_su_pais_no_se_publica(almacen: Almacen) -> None:
    documento = ejemplos.incidente_minimo()
    # Bélgica con el punto de Fuentes de Andalucía.
    documento["lugar"]["punto"] = {"lat": 37.46409, "lon": -5.34615}
    assert exportar([documento], AHORA, MODELOS)["features"] == []
    assert exportar_sin_ubicacion([documento], AHORA, MODELOS)["incidentes"] == []


# --- Lugar del suceso --------------------------------------------------------------------


def test_nombre_del_lugar_en_su_frase_tambien_declinado() -> None:
    assert nombrado_en("Rzeszów", "drony nad lotniskiem w Rzeszowie")
    assert nombrado_en("Estonia", "into Estonian airspace")
    assert not nombrado_en("Madrid", "el aeropuerto de Ibiza")


def contexto(texto: str, pais: str = "ES") -> Contexto:
    return Contexto(textos=(texto,), pais_objetivo=pais,
                    primer_articulo=AHORA, ahora=AHORA)  # fmt: skip


def test_un_lugar_del_suceso_que_la_frase_no_nombra_no_vale() -> None:
    frase = "paralizó el aeropuerto de Ibiza durante 35 minutos"
    validada = validar(datos(
        es_incidente=campo(True, frase), pais=campo("ES", frase),
        lugar_suceso=campo(suceso("Madrid", "localidad", "ES"), frase),
    ), contexto(IBIZA))  # fmt: skip
    assert "lugar_suceso: el nombre no está en la frase" in validada.motivos


def pistas(lugar: str, objetivo: Objetivo | None = None) -> Pistas:
    sitio = nomenclator().lugares.get(lugar)
    objetivo = objetivo or (Objetivo.de_lugar(sitio) if sitio else None)
    nombres = (sitio.nombre, *sitio.alias, *sitio.ciudades) if sitio else ()
    return Pistas(lugar, objetivo, nombres, {}, extraccion.prefijos_genericos())


def validada(**campos: Any) -> Validada:
    return Validada(campos={k: {"valor": v, "fuente": 1, "frase": "", "confianza": 0.9}
                            for k, v in campos.items()})  # fmt: skip


def test_una_region_o_un_pais_no_tienen_punto() -> None:
    for nivel, nombre in (("region", "Andalucía"), ("pais", "Estonia")):
        ubicacion = ubicar(
            validada(es_incidente=True, lugar_suceso=suceso(nombre, nivel, "ES")),
            pistas(FUENTES_DE_ANDALUCIA), nomenclator(),
        )  # fmt: skip
        assert ubicacion.sitio is None
        assert ubicacion.nivel == nivel


def test_la_region_descarta_un_homonimo() -> None:
    # Hay un Grindu en Tulcea y otro en Ialomița; el nomenclátor tiene el de Ialomița.
    ficha_ = validada(
        es_incidente=True,
        lugar_suceso=suceso("Grindu", "localidad", "RO", "Tulcea"),
        localidad="Tulcea",
    )
    ubicacion = ubicar(ficha_, pistas(FUNDU_MOLDOVEI), nomenclator())
    assert ubicacion.sitio is not None
    assert ubicacion.sitio.nombre == "Tulcea"


@pytest.mark.parametrize(("tipo", "punto"), [("1", False), ("5", False), ("2", False),
                                             ("4", True)])  # fmt: skip
def test_el_gkg_solo_vale_para_una_ciudad_con_el_nombre_del_suceso(tipo: str, punto: bool) -> None:
    lugar = f"gkg:{tipo}:45.1787:28.8050:RO:Tulcea"
    ficha_ = validada(es_incidente=True, lugar_suceso=suceso("Tulceax", "localidad", "RO"))
    objetivo = Objetivo(lugar, "otra", "Tulcea", "RO", 45.1787, 28.805, 10.0)
    ubicacion = ubicar(ficha_, replace(pistas(lugar, objetivo), nombres_candidato=()),
                       nomenclator())  # fmt: skip
    assert (ubicacion.sitio is not None) is punto
    assert ubicacion.origen == ("gkg" if punto else None)


def test_un_punto_hallado_fuera_del_pais_invalida_la_ubicacion() -> None:
    fuera = Objetivo("X", "otra", "Andalucía", "EE", 37.46409, -5.34615, 3.0)
    vocabulario = {"X": fuera.__dict__}
    ficha_ = validada(es_incidente=True, lugar_suceso=suceso("Andalucía", "localidad", "EE"))
    ubicacion = ubicar(ficha_, replace(pistas("X", fuera), vocabulario=vocabulario),
                       nomenclator())  # fmt: skip
    assert not ubicacion.valida


# --- Tipo y presencia --------------------------------------------------------------------


def con_pruebas(estatal: bool, entrada: bool, evidencia: list[str], estado: str) -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["pruebas"] = {"dron_estatal": estatal, "entrada_exterior": entrada,
                            "evidencia": evidencia}  # fmt: skip
    documento["estado"]["actual"] = estado
    return documento


@pytest.mark.parametrize(
    ("estatal", "entrada", "evidencia", "estado", "tipo"),
    [
        (True, True, [], "confirmado", "incursion"),  # lo demuestra una autoridad
        (True, True, ["restos"], "notificado", "incursion"),  # o una prueba física
        (True, True, ["rastreo"], "notificado", "incursion"),
        (True, True, [], "notificado", "sobrevuelo"),  # un avistamiento nunca
        (False, True, ["derribo"], "confirmado", "sobrevuelo"),  # no es militar
        (True, False, ["derribo"], "confirmado", "sobrevuelo"),  # no entró desde fuera
    ],
)
def test_regla_de_incursion(
    estatal: bool, entrada: bool, evidencia: list[str], estado: str, tipo: str
) -> None:
    assert (
        incidentes.aplicar_reglas(con_pruebas(estatal, entrada, evidencia, estado))["tipo"] == tipo
    )


def test_la_interrupcion_aeroportuaria_manda_sobre_la_incursion() -> None:
    documento = con_pruebas(True, True, ["derribo"], "confirmado")
    documento["consecuencias"] = {"vuelos_desviados": {"min": 3, "max": 3}}
    assert incidentes.aplicar_reglas(documento)["tipo"] == "interrupcion_aeroportuaria"


@pytest.mark.parametrize(
    ("evidencia", "estado", "antes", "despues"),
    [
        (["explosion"], "confirmado", "no_confirmada", "confirmada"),
        (["recuperado"], "atribuido", "no_confirmada", "confirmada"),
        (["explosion"], "notificado", "no_confirmada", "no_confirmada"),
        ([], "confirmado", "no_confirmada", "no_confirmada"),  # confirma un cierre, no el dron
        (["derribo"], "confirmado", "descartada", "descartada"),
    ],
)
def test_presencia_por_la_confirmacion_del_propio_dron(
    evidencia: list[str], estado: str, antes: str, despues: str
) -> None:
    documento = con_pruebas(False, False, evidencia, estado)
    documento["presencia_dron"] = antes
    assert incidentes.aplicar_reglas(documento)["presencia_dron"] == despues


def test_la_autoridad_de_otro_pais_no_cambia_el_incidente() -> None:
    documento = ejemplos.incidente_minimo()
    letonia = {"autoridad": "Latvia", "pais": "LV", "categoria": "gobierno",
               "afirma": "niega_incidente", "autor": "", "fuente": 1,
               "frase": "found no evidence that a drone had entered its air space"}  # fmt: skip
    resultado = declaraciones.aplicar(documento, [letonia], [documento["fuentes"][0]["enlace"]])
    assert resultado["estado"]["actual"] == "notificado"


# --- Cierre ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "frase", "vale"),
    [
        ("si", "paralizó el aeropuerto de Ibiza durante 35 minutos", True),
        ("si", "Københavns Lufthavn var lukket", True),
        ("si", "Ministerul Apărării a confirmat incidentul", False),
        ("no", "las operaciones siguieron con normalidad", True),
        ("no", "Ministerul Apărării a confirmat incidentul", False),
    ],
)
def test_el_cierre_solo_si_la_frase_habla_de_cierre(valor: str, frase: str, vale: bool) -> None:
    revisada = revalidar(Validada(campos={"cierre": {"valor": valor, "frase": frase}}))
    assert ("cierre" in revisada.campos) is vale


# --- Episodios ---------------------------------------------------------------------------


def de_noche(documento: dict[str, Any], id_: str, lat: float, lon: float) -> dict[str, Any]:
    documento = json.loads(json.dumps(documento))
    documento["id"] = id_
    documento["tiempo"] = {"inicio": {"valor": "2025-11-04T21:00Z", "precision": "hora"}}
    documento["lugar"] = {"punto": {"lat": lat, "lon": lon}, "radio_km": 5, "pais": "RO"}
    documento["objetivo"] = {"categoria": "otra", "nombre": id_}
    documento["fuentes"][0]["enlace"] = f"https://medio.ro/{id_}"
    return documento


def test_un_incidente_sin_punto_no_entra_en_un_episodio(almacen: Almacen) -> None:
    base = ejemplos.incidente_minimo()
    tulcea = de_noche(base, "EODI-2025-00010", 45.18, 28.8)
    sin_punto = de_noche(base, "EODI-2025-00011", 0, 0)
    sin_punto["lugar"] = {"pais": "RO", "nivel": "pais"}
    for documento in (tulcea, sin_punto):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    assert incidentes.agrupar_episodios(almacen, AHORA, MODELOS) == 0
    assert almacen.episodios() == []


def test_varios_paises_solo_si_una_fuente_los_relaciona(almacen: Almacen) -> None:
    base = ejemplos.incidente_minimo()
    rumania = de_noche(base, "EODI-2025-00010", 45.18, 28.8)
    moldavia = de_noche(base, "EODI-2025-00011", 46.88, 29.24)
    moldavia["lugar"]["pais"] = "MD"
    for documento in (rumania, moldavia):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    assert incidentes.agrupar_episodios(almacen, AHORA, MODELOS) == 0
    moldavia["fuentes"][0]["enlace"] = rumania["fuentes"][0]["enlace"]
    almacen.guardar_incidente(moldavia, AHORA, MODELOS)
    assert incidentes.agrupar_episodios(almacen, AHORA, MODELOS) == 2
    (episodio,) = almacen.episodios()
    assert episodio["incidentes"] == ["EODI-2025-00010", "EODI-2025-00011"]


def test_un_episodio_que_deja_de_serlo_se_deshace(almacen: Almacen) -> None:
    base = ejemplos.incidente_minimo()
    uno, otro = (de_noche(base, f"EODI-2025-0001{n}", 45.18 + n, 26.0) for n in (0, 1))
    for documento in (uno, otro):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    incidentes.agrupar_episodios(almacen, AHORA, MODELOS)
    otro["lugar"] = {"pais": "RO", "nivel": "pais"}
    otro.pop("episodio", None)
    almacen.guardar_incidente({**otro, "episodio": almacen.episodios()[0]["id"]}, AHORA, MODELOS)
    assert incidentes.agrupar_episodios(almacen, AHORA, MODELOS) == 2
    (episodio,) = almacen.episodios()
    assert "deshecho" in episodio
    assert all("episodio" not in i for i in almacen.incidentes())


# --- Publicación ---------------------------------------------------------------------------


def test_se_publican_tres_ficheros(almacen: Almacen, tmp_path: Path) -> None:
    documento = ejemplos.incidente_minimo()
    documento["lugar"] = {"pais": "BE", "nivel": "region", "region": "Limburg"}
    almacen.guardar_incidente(documento, AHORA, MODELOS)
    publicar.publicar(almacen, AHORA, tmp_path)
    sin_punto = json.loads((tmp_path / publicar.SIN_UBICACION).read_text(encoding="utf-8"))
    (publicado,) = sin_punto["incidentes"]
    assert publicado["lugar"] == {"pais": "BE", "nivel": "region", "region": "Limburg"}
    mapa = json.loads((tmp_path / publicar.INCIDENTES).read_text(encoding="utf-8"))
    assert mapa["features"] == []


def test_una_ficha_que_ya_no_es_incidente_retira_el_suyo(almacen: Almacen) -> None:
    cand = candidato(almacen, LA_GUARDIA, "Dron que paralizó el aeropuerto de Ibiza")
    frase = "paralizó el aeropuerto de Ibiza durante 35 minutos"
    primera = datos(es_incidente=campo(True, frase), pais=campo("ES", frase))
    id_ = extraer(almacen, cand, IBIZA, primera)
    assert id_ is not None
    extraer(almacen, cand, IBIZA, datos(es_incidente=campo(False, frase)))
    retirado = almacen.incidente(id_)
    assert retirado is not None and "retirado" in retirado
    assert exportar(almacen.incidentes(), AHORA, MODELOS)["features"] == []
    assert exportar_sin_ubicacion(almacen.incidentes(), AHORA, MODELOS)["incidentes"] == []


def test_ibiza_en_el_nomenclator_por_la_ciudad_y_el_tipo() -> None:
    assert lugares_en("aeropuerto de Ibiza", nomenclator()) == ("LEIB",)


# --- Revisión ----------------------------------------------------------------------------


def publicado(
    punto: list[float] | None, tipo: str = "sobrevuelo", episodio: str | None = None
) -> dict[str, Any]:
    return {
        "punto": punto, "pais": "RO", "region": None, "tipo": tipo, "estado": "notificado",
        "presencia_dron": "no_confirmada", "cierre": "desconocido", "episodio": episodio,
        "inicio": "2026-08-20T01:23Z", "titulo": "t", "enlace": "https://medio.ro/1",
    }  # fmt: skip


def test_la_revision_cuenta_lo_que_cambia() -> None:
    antes = {
        "A": publicado([45.18, 28.8], episodio="EP"),
        "B": publicado([47.53, 25.4], episodio="EP"),  # Fundu Moldovei
        "C": publicado([46.0, 26.0]),
    }
    despues = {
        "A": publicado([45.18, 28.8], tipo="incursion"),
        "B": publicado(None),
        "D": publicado([44.0, 26.0]),
    }
    cambios = revision.cambios(antes, despues)
    assert (cambios["retirados"], cambios["nuevos"]) == (["C"], ["D"])
    assert (cambios["sitio"], cambios["sin_punto_ahora"]) == (["B"], ["B"])
    assert (cambios["tipo"], cambios["episodios_deshechos"]) == (["A"], ["EP"])
    assert revision.resumen(despues) == {
        "publicados": 3, "en_mapa": 2, "sin_ubicacion": 1, "episodios": 0,
    }  # fmt: skip


@pytest.mark.parametrize(("gastado", "cabe"), [(0.0, True), (4.0, False)])
def test_el_lote_no_se_envia_si_no_cabe_en_el_limite(gastado: float, cabe: bool) -> None:
    prevision = revision.Prevision(
        muestra=10, medio_directo=0.004, restantes=1000, lote=2.0, gastado=gastado
    )
    assert prevision.cabe is cabe


def test_una_orden_parada_no_publica_ni_sube_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    def prohibido(*_: object) -> None:
        raise AssertionError("no se publica ni se guarda")

    base = tmp_path / "db.age"
    base.write_bytes(b"sin cambios")
    monkeypatch.setattr(extractor, "cargar_clave_local", lambda: None)
    monkeypatch.setattr(cliente_servicio, "cargar_local", lambda: None)
    monkeypatch.setattr(extractor, "abrir_cifrada", lambda _ruta: Almacen.abrir().conexion)
    monkeypatch.setattr(extractor, "publicar", prohibido)
    monkeypatch.setattr(extractor, "guardar_cifrada", prohibido)
    args = extractor.opciones_base(None).parse_args(["--base", str(base)])
    assert extractor.con_base(args, lambda _almacen: 1) == 1
    assert base.read_bytes() == b"sin cambios"


def test_sin_lugar_del_suceso_no_se_toma_el_objetivo_del_candidato(almacen: Almacen) -> None:
    # Ficha anterior a la ficha 5: dice que el suceso es en el objetivo conocido y su frase
    # nombra «la Guardia Civil», que casa con el aeródromo de La Guardia.
    cand = candidato(almacen, LA_GUARDIA, "Dron que paralizó el aeropuerto de Ibiza")
    frase = "El equipo Pegaso de la Guardia Civil investiga el vuelo del dron"
    id_ = extraer(almacen, cand, IBIZA, datos(
        es_incidente=campo(True, frase), pais=campo("ES", frase),
        objetivo_conocido=campo(True, frase),
    ))  # fmt: skip
    incidente = almacen.incidente(id_ or "")
    assert incidente is not None
    assert "punto" not in incidente["lugar"]


def test_rehacer_reutiliza_el_episodio_con_los_mismos_incidentes(almacen: Almacen) -> None:
    base = ejemplos.incidente_minimo()
    uno, otro = (de_noche(base, f"EODI-2025-0001{n}", 45.18 + n, 26.0) for n in (0, 1))
    for documento in (uno, otro):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    incidentes.agrupar_episodios(almacen, AHORA, MODELOS)
    (episodio,) = almacen.episodios()
    # Al rehacerse, los incidentes vuelven sin enlace al episodio.
    for documento in (uno, otro):
        almacen.guardar_incidente(documento, AHORA, MODELOS)
    incidentes.agrupar_episodios(almacen, AHORA, MODELOS)
    assert [e["id"] for e in almacen.episodios()] == [episodio["id"]]
    assert "deshecho" not in almacen.episodios()[0]


def test_el_pais_vale_si_la_fuente_lo_nombra_aunque_la_frase_no_sea_literal() -> None:
    frase_libre = "Una dronă a intrat în spațiul aerian"
    validada = validar(datos(
        es_incidente=campo(True, "O dronă a survolat spațiul aerian al Moldovei"),
        pais=campo("MD", frase_libre),
    ), contexto(ANENII_NOI, "MD"))  # fmt: skip
    assert validada.pais == "MD"
    assert "pais: la fuente nombra el país" in validada.motivos
    otro = validar(datos(
        es_incidente=campo(True, "O dronă a survolat spațiul aerian al Moldovei"),
        pais=campo("EE", frase_libre),
    ), contexto(ANENII_NOI, "MD"))  # fmt: skip
    assert otro.pais is None


def test_el_nombre_del_lugar_vale_con_sus_palabras_propias_en_las_fuentes() -> None:
    texto = "Wegen einer Drohne wurde der Bremer Flughafen am Abend gesperrt."
    frase = "der Bremer Flughafen am Abend gesperrt"
    contexto_ = replace(contexto(texto, "DE"), prefijos_genericos=extraccion.prefijos_genericos())
    bremen = validar(datos(
        es_incidente=campo(True, frase), pais=campo("DE", frase),
        lugar_suceso=campo(suceso("Flughafen Bremen", "instalacion", "DE"), frase),
    ), contexto_)  # fmt: skip
    assert "lugar_suceso" in bremen.campos
    # Solo coincide la palabra de tipo de lugar: no vale.
    hamburgo = validar(datos(
        es_incidente=campo(True, frase), pais=campo("DE", frase),
        lugar_suceso=campo(suceso("Flughafen Hamburg", "instalacion", "DE"), frase),
    ), contexto_)  # fmt: skip
    assert "lugar_suceso" not in hamburgo.campos


def test_sin_lugar_del_suceso_se_busca_la_instalacion_que_nombra_la_ficha() -> None:
    ficha_ = validada(es_incidente=True, pais="DE", objetivo_nombre="Flughafen Bremen")
    ubicacion = ubicar(ficha_, pistas(LA_GUARDIA), nomenclator())
    assert ubicacion.sitio is not None
    assert ubicacion.sitio.oaci == "EDDW"
