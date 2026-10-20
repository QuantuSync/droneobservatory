"""Segunda lectura que busca lo que falta (proceso/ y recogida/segunda_busqueda.py):
declaraciones oficiales que faltan, incidentes que faltan, atribución, lugar y duración, y el
barrido de un país. Con el servicio secundario simulado: cada búsqueda marca su candidato; una
frase que no está literal en lo que se mandó se descarta; lo que ya tiene ficha no se rescata; con
el servicio caído no pasa nada; la base principal nunca se escribe; y en la recogida cada
candidato va por el camino de siempre."""

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste
from proceso import extraccion
from proceso import segunda_busqueda as busqueda
from recogida import articulos_dirigidos, rectificaciones
from recogida import segunda_busqueda as buscar
from recogida import segunda_lectura as segunda
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_segunda_lectura import Servicio, _cliente, _ok

AHORA = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
DELEGACION = (
    "La Delegación del Gobierno en Melilla ha informado que el aparato se encontraba en el lado "
    "marroquí de la frontera"
)
PARRAFO = "El vuelo de Iberia tuvo que esperar cerca de una hora en el aire sobre la ciudad."
NOTICIA = "https://medio.es/melilla-dron"
OTRA = "https://otro.es/dron-sobre-la-carcel"
SOLO_BUSQUEDA = frozenset({"busqueda"})


class Paginas:
    """El descargador: el HTML de cada noticia (sin red)."""

    def __init__(self, textos: dict[str, str]) -> None:
        self.textos = textos

    def texto(self, url: str, _validar: Any) -> str:
        parrafos = "".join(f"<p>{p}</p>" for p in self.textos.get(url, "").split("|"))
        return f"<html><body><article>{parrafos}</article></body></html>"


@pytest.fixture(autouse=True)
def entorno(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("EODI_SECUNDARIO_URL", "https://secundario.example/v1")
    monkeypatch.setenv("EODI_SECUNDARIO_CLAVE", "clave-secreta")
    monkeypatch.setenv("EODI_SECUNDARIO_MODELO", "modelo-x")
    datos = tmp_path / "capa"
    monkeypatch.setenv(segunda.VARIABLE_DATOS, str(datos))
    monkeypatch.setattr(rectificaciones, "cargar", lambda: {"rectificaciones": []})
    return datos


def _melilla() -> dict[str, Any]:
    """Como EODI-2026-00146 antes del 19/10/2026: notificado, sin la declaración de la
    Delegación, que estaba en el cuerpo de una de sus noticias."""
    d = ejemplos.incidente_minimo()
    d["id"] = "EODI-2026-00146"
    d["titulo"] = {"es": "Un dron sobre el aeropuerto de Melilla",
                   "en": "A drone over Melilla airport"}  # fmt: skip
    d["tiempo"] = {"inicio": ejemplos.instante("2026-09-22T20:00Z", "hora")}
    d["lugar"] = {"punto": {"lat": 35.28, "lon": -2.95}, "radio_km": 5, "pais": "ES",
                  "localidad": "Melilla", "nivel": "localidad"}  # fmt: skip
    d["fuentes"] = [{**ejemplos.fuente("F1", "C"), "enlace": NOTICIA, "idioma": "es",
                     "frase_origen": "Un dron sobre el aeropuerto de Melilla obliga a desviar "
                                     "un vuelo"}]  # fmt: skip
    d["control"] = {**d["control"], "candidato": "CAND-MELILLA"}
    return d


def _base(tmp_path: Path, *documentos: dict[str, Any], articulos: tuple[dict[str, Any], ...] = (),
          candidatos: tuple[dict[str, Any], ...] = ()) -> Path:  # fmt: skip
    ruta = tmp_path / "eodi.sqlite"
    almacen = Almacen.abrir(ruta)
    for d in documentos:
        almacen.guardar_incidente(d, AHORA, VOCABULARIO_MODELOS)
    for a in articulos:
        almacen.guardar_articulo(a)
    for c in candidatos:
        almacen.guardar_candidato(c)
    almacen.cerrar()
    return ruta


def _articulo(url: str, titular: str, fecha: str = "2026-10-15T08:00:00Z",
              lugares: list[str] | None = None) -> dict[str, Any]:  # fmt: skip
    return {"url": url, "medio": url.split("/")[2], "fecha": fecha, "idioma": "es", "pais": "ES",
            "titular": titular, "titular_normalizado": titular.lower(), "temas": [],
            "lugares": lugares or []}  # fmt: skip


def _pasada(ruta: Path, datos: Path, servicio: Servicio, paginas: Paginas,
            **opciones: Any) -> segunda.Resumen:  # fmt: skip
    principal = segunda.abrir_principal(ruta)
    propia = segunda.Propia.abrir(datos / segunda.BASE)
    try:
        return segunda.pasada(principal, propia, _cliente(servicio), AHORA, float("inf"),
                              lambda: 0.0, tareas=opciones.pop("tareas", SOLO_BUSQUEDA),
                              descargador=paginas, **opciones)  # fmt: skip
    finally:
        principal.cerrar()
        propia.cerrar()


def _candidatos(datos: Path) -> list[dict[str, Any]]:
    return segunda.leer_candidatos(datos / segunda.BASE, 5.0)


def _declaracion(frase: str) -> dict[str, Any]:
    return {"hay": True, "texto": 1, "autoridad": "Delegación del Gobierno en Melilla",
            "afirma": "confirma", "frase": frase}  # fmt: skip


NADA = {"hay": False, "texto": 0, "autoridad": "", "responsable": "", "afirma": "", "frase": ""}


def _nada(tipo: str) -> dict[str, Any]:
    _, esquema = busqueda.INSTRUCCIONES[tipo]
    if tipo == busqueda.EFECTOS:
        return {"lugar": {"frase": "", "texto": 0}, "duracion": {"frase": "", "texto": 0}}
    if tipo == busqueda.RESCATE:
        return {"suceso": False, "fecha": "", "lugar": "", "pais": "", "frase": "",
                "coincide_con": ""}  # fmt: skip
    return {k: v for k, v in NADA.items() if k in esquema["properties"]}


# --- a) Declaraciones oficiales que faltan -----------------------------------------------------


def test_marca_la_declaracion_oficial_que_falta(tmp_path: Path, entorno: Path) -> None:
    ruta = _base(tmp_path, _melilla())
    huella_antes = hashlib.sha256(ruta.read_bytes()).hexdigest()
    servicio = Servicio([_ok(_declaracion(DELEGACION))])
    paginas = Paginas({NOTICIA: f"{PARRAFO}|{DELEGACION}, según fuentes oficiales."})
    resumen = _pasada(ruta, entorno, servicio, paginas)
    assert resumen.busquedas[busqueda.DECLARACION]["candidatos"] == ["EODI-2026-00146"]
    (candidato,) = [c for c in _candidatos(entorno) if c["tipo"] == busqueda.DECLARACION]
    assert candidato["datos"]["frase"] == DELEGACION and candidato["datos"]["url"] == NOTICIA
    # Lo que se mandó lleva el cuerpo de la noticia, no solo la frase guardada.
    assert DELEGACION in json.dumps(servicio.pedidas[0], ensure_ascii=False)
    # La base principal no se toca.
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == huella_antes
    # Lo mismo no se vuelve a preguntar.
    otra = Servicio([])
    _pasada(ruta, entorno, otra, paginas)
    assert not [p for p in otra.pedidas if "messages" in p]


def test_una_frase_inventada_se_descarta(tmp_path: Path, entorno: Path) -> None:
    ruta = _base(tmp_path, _melilla())
    servicio = Servicio([_ok(_declaracion("La Delegación confirma el ataque marroquí con drones"))])
    _pasada(ruta, entorno, servicio, Paginas({NOTICIA: f"{PARRAFO}|{DELEGACION}."}))
    assert _candidatos(entorno) == []


def test_un_incidente_reciente_o_confirmado_no_se_busca(tmp_path: Path, entorno: Path) -> None:
    reciente = _melilla()
    reciente["tiempo"] = {"inicio": ejemplos.instante("2026-10-18T20:00Z", "hora")}
    assert not busqueda.toca(busqueda.DECLARACION, reciente, AHORA, 48)
    assert busqueda.toca(busqueda.DECLARACION, _melilla(), AHORA, 48)
    # El barrido del país, sin el filtro de antigüedad.
    assert busqueda.toca(busqueda.DECLARACION, reciente, AHORA, 0)


# --- b) Incidentes que faltan --------------------------------------------------------------------


def _rescate(frase: str, coincide: str = "") -> dict[str, Any]:
    return {"suceso": True, "fecha": "2026-10-14", "lugar": "Cárcel de Picassent", "pais": "ES",
            "frase": frase, "coincide_con": coincide}  # fmt: skip


SUCESO = "Un dron con droga ha sido interceptado sobre la prisión de Picassent este martes"


def test_rescata_la_noticia_que_no_esta_en_ninguna_ficha(tmp_path: Path, entorno: Path) -> None:
    ruta = _base(tmp_path, _melilla(), articulos=(
        _articulo(OTRA, "Interceptan un dron sobre la prisión de Picassent"),))  # fmt: skip
    servicio = Servicio([_ok(_nada(busqueda.DECLARACION)), _ok(_rescate(SUCESO))])
    resumen = _pasada(
        ruta, entorno, servicio, Paginas({OTRA: SUCESO + ", según la Guardia Civil."})
    )
    assert resumen.busquedas[busqueda.RESCATE]["candidatos"] == [OTRA]


def test_lo_que_ya_tiene_ficha_no_se_rescata(tmp_path: Path, entorno: Path) -> None:
    ruta = _base(tmp_path, _melilla(), articulos=(
        _articulo(OTRA, "Un dron sobre el aeropuerto de Melilla", "2026-09-24T08:00:00Z"),
        _articulo(NOTICIA, "Un dron sobre el aeropuerto de Melilla"),))  # fmt: skip
    servicio = Servicio([_ok(_nada(busqueda.DECLARACION)),
                         _ok(_rescate(SUCESO, coincide="EODI-2026-00146"))])  # fmt: skip
    resumen = _pasada(ruta, entorno, servicio, Paginas({OTRA: SUCESO + ".", NOTICIA: PARRAFO}))
    assert resumen.busquedas[busqueda.RESCATE]["candidatos"] == []
    # La noticia que es fuente de una ficha publicada ni se pregunta.
    assert not any(NOTICIA in json.dumps(p) and "Noticia (" in json.dumps(p, ensure_ascii=False)
                   for p in servicio.pedidas)  # fmt: skip


# --- c) Atribución y d) lugar y duración -------------------------------------------------------


def _confirmado() -> dict[str, Any]:
    d = _melilla()
    d["estado"] = {"actual": "confirmado", "historial": [
        *d["estado"]["historial"],
        {"estado": "confirmado", "fecha": ejemplos.instante("2026-09-25T10:00Z"),
         "fuente_id": "F1"},
    ]}  # fmt: skip
    return d


@pytest.mark.parametrize(
    ("frase", "marca"),
    [
        ("El Gobierno afirma que el dron pertenecía a las fuerzas de seguridad marroquíes", True),
        ("La Delegación vincula el dron con las fuerzas de seguridad marroquíes", False),
    ],
)
def test_atribucion_solo_con_una_afirmacion_expresa(frase: str, marca: bool) -> None:
    textos = [busqueda.Texto(NOTICIA, "medio.es", "2026-09-25", f"{PARRAFO} {frase}.")]
    respuesta = {"hay": True, "texto": 1, "autoridad": "Gobierno", "responsable": "Marruecos",
                 "frase": frase}  # fmt: skip
    assert (busqueda.atribucion_hallada(respuesta, textos) is not None) is marca


def test_lugar_y_duracion_que_dan_las_fuentes() -> None:
    datos = {"nivel": "pais", "cierre": "si", "minutos_cierre": "sin dato"}
    texto = busqueda.Texto(
        NOTICIA,
        "medio.es",
        "2026-09-25",
        "El aeropuerto de Melilla reabrió a las 21:40 tras el aviso.",
    )
    respuesta = {"lugar": {"frase": "El aeropuerto de Melilla", "texto": 1},
                 "duracion": {"frase": "reabrió a las 21:40", "texto": 1}}  # fmt: skip
    hallados = busqueda.efectos(respuesta, [texto], datos)
    assert [h["campo"] for h in hallados] == ["lugar", "duracion"]
    # Con el lugar ya preciso y la duración sabida, nada.
    assert busqueda.efectos(respuesta, [texto], {"nivel": "instalacion", "cierre": "no"}) == []


# --- El servicio caído --------------------------------------------------------------------------


def test_con_el_servicio_caido_no_pasa_nada(tmp_path: Path, entorno: Path) -> None:
    ruta = _base(tmp_path, _melilla())
    servicio = Servicio([OSError("caído")] * 20)
    resumen = _pasada(ruta, entorno, servicio, Paginas({NOTICIA: f"{PARRAFO}|{DELEGACION}."}))
    assert resumen.fallos >= 1 and _candidatos(entorno) == []


# --- El barrido del país -------------------------------------------------------------------------


def test_el_barrido_rota_por_los_paises_de_mas_a_menos(tmp_path: Path, entorno: Path) -> None:
    propia = segunda.Propia.abrir(entorno / segunda.BASE)
    belga = ejemplos.incidente_minimo()
    fichas = [_melilla(), copy.deepcopy(_melilla()), belga]
    assert buscar.siguiente_pais(propia, fichas) == "ES"
    propia.fijar(buscar.ESTADO_BARRIDO, json.dumps({"dia": "2026-10-18", "vuelta": ["ES"]}))
    assert buscar.siguiente_pais(propia, fichas) == "BE"
    assert buscar.toca_barrido(propia, AHORA)
    propia.cerrar()


# --- En la recogida -------------------------------------------------------------------------------


def test_la_declaracion_va_a_la_extraccion_con_el_experto(tmp_path: Path) -> None:
    candidato = {"id": "CAND-MELILLA", "articulos": [NOTICIA], "lugar": "GEML",
                 "ultimo": "2026-09-23T08:00:00Z"}  # fmt: skip
    otra = _articulo("https://gaceta.es/melilla", "La Delegación reconoce los drones de Melilla")
    ruta = _base(tmp_path, _melilla(), articulos=(otra,), candidatos=(candidato,))
    almacen = Almacen.abrir(ruta)
    marcado = {"clave": "declaracion:EODI-2026-00146:x", "tipo": busqueda.DECLARACION,
               "incidente": "EODI-2026-00146", "datos": {
                   "url": otra["url"], "frase": DELEGACION, "autoridad": "Delegación del Gobierno",
                   "afirma": "confirma"}}  # fmt: skip
    hecho = buscar.entregar(almacen, AHORA, marcado)
    assert hecho == {"resultado": "a_la_extraccion", "candidato": "CAND-MELILLA"}
    (actual,) = [c for c in almacen.candidatos() if c["id"] == "CAND-MELILLA"]
    assert otra["url"] in actual["articulos"]
    cursor = almacen.cursor(articulos_dirigidos.FUENTE_ID) or {}
    assert cursor[otra["url"]]["frase"] == DELEGACION
    espera = extraccion.esperan_experto(almacen)["CAND-MELILLA"]
    assert espera["revision"] and espera["motivos"][0].startswith("declaracion:")
    # El motivo es opcional: nunca la reserva crítica ni una espera si el experto no puede.
    from proceso import escalado

    assert escalado.opcionales(espera["motivos"])
    almacen.cerrar()


def test_con_el_cupo_la_espera_lo_lleva_y_nunca_es_critica(tmp_path: Path) -> None:
    candidato = {"id": "CAND-MELILLA", "articulos": [NOTICIA], "lugar": "GEML",
                 "ultimo": "2026-09-23T08:00:00Z"}  # fmt: skip
    ruta = _base(tmp_path, _melilla(), candidatos=(candidato,))
    almacen = Almacen.abrir(ruta)
    marcado = {"clave": "declaracion:EODI-2026-00146:x", "tipo": busqueda.DECLARACION,
               "incidente": "EODI-2026-00146", "datos": {
                   "frase": DELEGACION, "autoridad": "Delegación del Gobierno",
                   "afirma": "confirma"}}  # fmt: skip
    hecho = buscar.entregar(almacen, AHORA, marcado, cupo=True)
    assert hecho == {"resultado": "a_la_extraccion", "candidato": "CAND-MELILLA", "cupo": True}
    espera = extraccion.esperan_experto(almacen)["CAND-MELILLA"]
    assert espera["cupo"] == "segunda_busqueda" and not espera.get("critico")
    # La respuesta del experto se anota en el modo del cupo, no en el de la recogida.
    motivos = [*espera["motivos"], f"{extraccion.PREFIJO_CUPO}: segunda_busqueda"]
    assert extraccion.modo_de_la_respuesta(motivos, coste.Modo.HORARIO) is (
        coste.Modo.SEGUNDA_BUSQUEDA
    )
    assert extraccion.modo_de_la_respuesta(espera["motivos"], coste.Modo.HORARIO) is (
        coste.Modo.HORARIO
    )
    almacen.cerrar()


def test_lo_entregado_hace_poco_no_se_repite() -> None:
    ahora = datetime(2026, 10, 20, 8, 30, tzinfo=UTC)
    decididas = {
        # Antes del 20 de octubre de 2026 la decisión no guardaba la clave de entrega.
        "segunda:declaracion:EODI-2026-00488:ed5a": {
            "fecha": "2026-10-20T05:30:58Z", "resultado": "a_la_extraccion"},
        "segunda:rescate:https://x.md/1:0cb4": {
            "fecha": "2026-10-19T05:30:58Z", "resultado": "a_la_extraccion",
            "entrega": "rescate:https://x.md/1"},
        "segunda:declaracion:EODI-2026-00515:aa": {
            "fecha": "2026-10-10T05:30:58Z", "resultado": "a_la_extraccion"},
        "segunda:campos:EODI-2026-00001:bb": {"fecha": "2026-10-20T05:30:58Z",
                                              "resultado": "verificada"},
    }  # fmt: skip
    ya = busqueda.entregados_recientes(decididas, ahora)
    assert ya == {"incidente:EODI-2026-00488": "declaracion:EODI-2026-00488:ed5a",
                  "rescate:https://x.md/1": "rescate:https://x.md/1:0cb4"}  # fmt: skip
    otra_frase = {"tipo": busqueda.ATRIBUCION, "incidente": "EODI-2026-00488", "datos": {}}
    assert busqueda.clave_de_entrega(otra_frase) in ya
    rescate = {"tipo": busqueda.RESCATE, "incidente": None, "datos": {"url": "https://x.md/1"}}
    assert busqueda.clave_de_entrega(rescate) in ya


def test_la_cola_va_del_suceso_mas_reciente_al_mas_antiguo() -> None:
    def marcado(tipo: str, fecha: str, suceso: str | None) -> dict[str, Any]:
        datos = {"fecha_suceso": suceso} if suceso else {}
        return {"tipo": tipo, "fecha": fecha, "datos": datos}

    viejo = marcado(busqueda.DECLARACION, "2026-10-20T01:00:00Z", "2025-09-26")
    nuevo = marcado(busqueda.DECLARACION, "2026-10-19T01:00:00Z", "2026-10-18")
    sin_fecha = marcado(busqueda.RESCATE, "2026-10-17T01:00:00Z", None)
    assert busqueda.fecha_del_suceso(sin_fecha) == "2026-10-17T01:00:00Z"
    cola = sorted([viejo, sin_fecha, nuevo], key=busqueda.fecha_del_suceso, reverse=True)
    assert cola == [nuevo, sin_fecha, viejo]


def test_prioridad_de_lo_que_marca_la_capa() -> None:
    def c(tipo: str, hallazgos: list[dict[str, str]] | None = None) -> dict[str, Any]:
        return {"tipo": tipo, "datos": {"hallazgos": hallazgos or []}}

    orden = sorted(
        [c(busqueda.EFECTOS), c("campos", [{"campo": "lugar", "valoracion": "sin_apoyo"}]),
         c("duplicado"), c("campos", [{"campo": "lugar", "valoracion": "contradicho"}]),
         c(busqueda.RESCATE), c(busqueda.ATRIBUCION), c(busqueda.DECLARACION)],
        key=busqueda.prioridad,
    )  # fmt: skip
    tipos = [x["tipo"] for x in orden]
    assert tipos[:2] == [busqueda.RESCATE, busqueda.DECLARACION]
    assert tipos[2] == "campos" and tipos[3] == "duplicado" and tipos[-1] == "campos"
