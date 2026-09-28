"""Extractor sin red: cliente con transporte falso, ficha, validación, incidentes y fusión."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste, ficha, paginas
from modelo.cliente import Cliente, Configuracion, LlamadaFallida
from modelo.paginas import primeras_frases
from proceso import extraccion, incidentes
from proceso.validacion_ficha import Contexto, validar
from proceso.validaciones import validar_incidente
from recogida import gdelt
from tests.test_gdelt import articulo

AHORA = datetime(2025, 9, 24, 12, tzinfo=UTC)
MODELOS = frozenset({"shahed_geran", "gerbera_senuelos", "otros"})
TITULAR = "Droner over Københavns Lufthavn: lufthavnen lukket"
TEXTO = (
    "Københavns Lufthavn var lukket fra klokken 20.30 mandag aften, efter at der blev "
    "observeret tre til fire store droner. 31 fly blev omdirigeret."
)
CONFIG = Configuracion(
    clave="k", url="https://servicio/mensajes", url_lotes="https://servicio/lotes",
    modelo="m", cabeceras={"clave-cabecera": "{clave}", "version": "1"},
)  # fmt: skip


def campo(valor: Any, frase: str = "", confianza: float = 0.9, fuente: int = 1) -> dict[str, Any]:
    return {"valor": valor, "fuente": fuente, "frase": frase, "confianza": confianza}


def _texto(valor: Any) -> str:
    """El valor con el formato de texto que devuelve el servicio."""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, dict) and set(valor) == {"min", "max"}:
        return f"{valor['min']}-{valor['max']}"
    if isinstance(valor, dict):
        return "; ".join(str(valor[k]) for k in ("nombre", "categoria", "pais", "lat", "lon"))
    if isinstance(valor, list):
        return ", ".join(valor)
    return str(valor)


def a_servicio(datos: dict[str, Any]) -> dict[str, Any]:
    """La ficha como la devuelve el servicio: lista de datos con el valor como texto."""
    return {
        "datos": [
            {"campo": nombre, **c, "valor": _texto(c["valor"])}
            for nombre, c in datos.items()
            if isinstance(c, dict) and c.get("valor") is not None
        ],
        "titulo_es": datos["titulo_es"],
        "titulo_en": datos["titulo_en"],
    }


def ficha_ejemplo(**cambios: Any) -> dict[str, Any]:
    datos: dict[str, Any] = {nombre: campo(None) for nombre in ficha.CAMPOS}
    datos |= {
        "es_incidente": campo(
            True, "Københavns Lufthavn var lukket fra klokken 20.30 mandag aften"
        ),
        "tipo": campo("interrupcion_aeroportuaria", "Københavns Lufthavn var lukket"),
        "inicio": campo("2025-09-22T18:30", "fra klokken 20.30 mandag aften"),
        "inicio_precision": campo("minuto", "fra klokken 20.30 mandag aften"),
        "pais": campo("DK", "Københavns Lufthavn"),
        "localidad": campo("Copenhague", "Københavns Lufthavn"),
        "objetivo_conocido": campo(True, "Københavns Lufthavn"),
        "drones": campo({"min": 3, "max": 4}, "observeret tre til fire store droner"),
        "presencia_dron": campo("no_confirmada", "observeret tre til fire store droner"),
        "cierre": campo("si", "Københavns Lufthavn var lukket"),
        "vuelos_desviados": campo({"min": 31, "max": 31}, "31 fly blev omdirigeret"),
        "titulo_es": "Drones sobre el aeropuerto de Copenhague obligan a cerrarlo",
        "titulo_en": "Drones over Copenhagen Airport force its closure",
    }
    datos |= cambios
    return datos


def respuesta(datos: dict[str, Any], entrada: int = 1000, salida: int = 500) -> dict[str, Any]:
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": json.dumps(a_servicio(datos), ensure_ascii=False)}],
        "usage": {"input_tokens": entrada, "output_tokens": salida,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 4000},
    }  # fmt: skip


def contexto() -> Contexto:
    return Contexto(
        textos=(f"{TITULAR}. {TEXTO}",),
        pais_objetivo="DK",
        primer_articulo=datetime(2025, 9, 23, 5, tzinfo=UTC),
        ahora=AHORA,
    )


# --- Cliente --------------------------------------------------------------------------


class Servicio:
    """Transporte falso: responde lo preparado y anota lo pedido."""

    def __init__(self, respuestas: list[tuple[int, dict[str, str], bytes]]) -> None:
        self.respuestas = respuestas
        self.pedidas: list[tuple[str, str, dict[str, str], Any]] = []

    def __call__(
        self, metodo: str, url: str, cabeceras: dict[str, str], cuerpo: bytes | None, limite: float
    ) -> tuple[int, dict[str, str], bytes]:
        self.pedidas.append((metodo, url, cabeceras, json.loads(cuerpo) if cuerpo else None))
        return self.respuestas.pop(0)


def test_cliente_pone_la_clave_en_su_cabecera_y_reintenta_el_429() -> None:
    servicio = Servicio([(429, {"retry-after": "30"}, b"{}"), (200, {}, b'{"ok": 1}')])
    esperas: list[float] = []
    cliente = Cliente(CONFIG, servicio, esperas.append)
    assert cliente.mensaje({"max_tokens": 5}) == {"ok": 1}
    _, url, cabeceras, cuerpo = servicio.pedidas[0]
    assert (url, cabeceras["clave-cabecera"], cabeceras["version"]) == (CONFIG.url, "k", "1")
    assert cuerpo == {"model": "m", "max_tokens": 5}
    assert esperas == [30.0]


def test_cliente_no_reintenta_un_400_ni_cuenta_el_texto_del_error() -> None:
    cuerpo = b'{"error": {"type": "invalid_request_error", "message": "secreto"}}'
    cliente = Cliente(CONFIG, Servicio([(400, {}, cuerpo)]), lambda _: None)
    with pytest.raises(LlamadaFallida) as error:
        cliente.mensaje({})
    assert "invalid_request_error" in str(error.value)
    assert "secreto" not in str(error.value)


def test_cliente_de_lotes() -> None:
    servicio = Servicio([
        (200, {}, b'{"id": "l1", "processing_status": "in_progress"}'),
        (200, {}, b'{"id": "l1", "processing_status": "ended", "results_url": "https://r"}'),
        (200, {}, b'{"custom_id": "a", "result": {"type": "succeeded"}}\n'),
    ])  # fmt: skip
    cliente = Cliente(CONFIG, servicio, lambda _: None)
    lote = cliente.crear_lote([{"custom_id": "a", "params": {"max_tokens": 5}}])
    assert servicio.pedidas[0][3] == {
        "requests": [{"custom_id": "a", "params": {"model": "m", "max_tokens": 5}}]
    }
    terminado = cliente.lote(lote["id"])
    assert servicio.pedidas[1][1] == "https://servicio/lotes/l1"
    assert cliente.resultados_lote(terminado) == [
        {"custom_id": "a", "result": {"type": "succeeded"}}
    ]


# --- Ficha y páginas ------------------------------------------------------------------


def _objetos(nodo: Any) -> Iterator[dict[str, Any]]:
    if isinstance(nodo, dict):
        if nodo.get("type") == "object":
            yield nodo
        for hijo in nodo.values():
            yield from _objetos(hijo)
    elif isinstance(nodo, list):
        for hijo in nodo:
            yield from _objetos(hijo)


def test_el_esquema_de_la_ficha_cumple_lo_que_exige_la_salida_estructurada() -> None:
    for objeto in _objetos(ficha.ESQUEMA):
        assert objeto["additionalProperties"] is False
        assert set(objeto["required"]) == set(objeto["properties"])
    texto = json.dumps(ficha.ESQUEMA)
    assert "minimum" not in texto and "maximum" not in texto


def test_la_peticion_cachea_instrucciones_y_obliga_el_esquema() -> None:
    fuentes = [ficha.FuenteTexto("dr.dk", "2025-09-23T05:00:00Z", "da", TITULAR, TEXTO)]
    cuerpo = ficha.cuerpo("Aeropuerto de Copenhague (aeropuerto, DK, EKCH)", fuentes)
    assert cuerpo["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert cuerpo["output_config"]["format"]["schema"] is ficha.ESQUEMA
    assert "Fuente 1 (dr.dk" in cuerpo["messages"][0]["content"]


def test_leer_respuesta() -> None:
    assert ficha.leer_respuesta(respuesta(ficha_ejemplo()))["pais"]["valor"] == "DK"
    with pytest.raises(ficha.RespuestaInvalida):
        ficha.leer_respuesta({**respuesta(ficha_ejemplo()), "stop_reason": "max_tokens"})


def test_primeras_frases_de_los_parrafos_utiles() -> None:
    html = (
        "<html><nav><p>Menú con muchas palabras que no son la noticia en absoluto</p></nav>"
        "<p>Foto: agencia</p><p>" + TEXTO + "</p><script>var x = 1;</script>"
        "<footer><p>Pie de página con suficientes palabras para parecer un párrafo</p></footer>"
    )
    assert primeras_frases(html) == TEXTO
    assert len(primeras_frases("<p>" + "Una frase larga de prueba. " * 60 + "</p>")) <= 600


# --- Validación -----------------------------------------------------------------------


def test_la_ficha_de_ejemplo_valida_entera() -> None:
    validada = validar(ficha_ejemplo(), contexto())
    assert validada.motivos == []
    assert validada.publicable


@pytest.mark.parametrize(
    ("cambio", "motivo"),
    [
        ({"localidad": campo("Kastrup", "frase inventada que no está")}, "localidad: la frase no"),
        ({"drones": campo({"min": 5, "max": 2}, "tre til fire")}, "drones: rango incoherente"),
        ({"drones": campo({"min": 5, "max": 500}, "tre til fire")}, "drones: por encima"),
        ({"fin": campo("2026-01-01T00:00", "mandag aften")}, "fin: fecha futura"),
        ({"inicio": campo("2025-09-01T10:00", "mandag aften")}, "inicio: inicio más de una"),
        ({"cierre": campo("si", "lukket", 0.3)}, "cierre: confianza baja"),
        ({"pais": campo("SE", "Københavns Lufthavn")}, "pais: distinto del país"),
    ],
)
def test_lo_que_no_valida_se_descarta_con_su_motivo(cambio: dict[str, Any], motivo: str) -> None:
    validada = validar(ficha_ejemplo(**cambio), contexto())
    assert any(m.startswith(motivo) for m in validada.motivos), validada.motivos
    assert next(iter(cambio)) not in validada.campos


def test_un_lugar_nuevo_fuera_de_su_pais_no_vale() -> None:
    nuevo = {"nombre": "Billund Lufthavn", "categoria": "aeropuerto", "pais": "DK",
             "lat": 41.9, "lon": 12.5}  # fmt: skip
    cambios = {
        "objetivo_conocido": campo(False, "Københavns Lufthavn"),
        "lugar_nuevo": campo(nuevo, "Københavns Lufthavn"),
    }
    validada = validar(ficha_ejemplo(**cambios), contexto())
    assert "lugar_nuevo: coordenadas fuera del país citado" in validada.motivos
    assert not validada.publicable


# --- Incidentes, fusión y episodios -----------------------------------------------------


@pytest.fixture
def almacen() -> Iterator[Almacen]:
    a = Almacen.abrir()
    yield a
    a.cerrar()


def candidato_con_articulos(almacen: Almacen, horas: float = 10, n: int = 1) -> dict[str, Any]:
    articulos = [
        articulo(n * 10 + i, f"{TITULAR} {i}" if i else TITULAR, horas - i) for i in range(2)
    ]
    gdelt.incorporar(almacen, articulos)
    (candidato,) = [c for c in almacen.candidatos() if articulos[0].url in c["articulos"]]
    return candidato


def extraer_ejemplo(almacen: Almacen, datos: dict[str, Any] | None = None) -> str | None:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    peticion = extraccion.Peticion(
        **{**peticion.__dict__, "fuentes": [
            ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, TEXTO)
            for f in peticion.fuentes
        ]}
    )  # fmt: skip
    return extraccion.procesar_respuesta(
        almacen, peticion, respuesta(datos or ficha_ejemplo()), AHORA, coste.Modo.HISTORICO,
        True, MODELOS,
    )  # fmt: skip


def test_de_la_ficha_al_incidente(almacen: Almacen) -> None:
    id_ = extraer_ejemplo(almacen)
    assert id_ == "EODI-2025-00001"
    incidente = almacen.incidente(id_)
    assert incidente is not None
    assert validar_incidente(incidente, AHORA, MODELOS) == []
    assert incidente["tipo"] == "interrupcion_aeroportuaria"
    assert incidente["estado"]["actual"] == "notificado"
    assert incidente["presencia_dron"] == "no_confirmada"
    assert (incidente["objetivo"]["categoria"], incidente["objetivo"]["oaci"]) == (
        "aeropuerto",
        "EKCH",
    )
    assert incidente["tiempo"]["inicio"] == {"valor": "2025-09-22T18:30Z", "precision": "minuto"}
    assert incidente["consecuencias"]["vuelos_desviados"] == {"min": 31, "max": 31}
    assert {f["credibilidad"] for f in incidente["fuentes"]} == {3}
    (llamada,) = almacen.llamadas()
    # Lote: la mitad de 1000 de entrada, 500 de salida y 4000 leídos de la caché.
    assert llamada["coste"] == pytest.approx((1000 * 1 + 500 * 5 + 4000 * 0.1) / 1e6 / 2)


def test_la_ficha_que_no_es_incidente_no_se_publica_y_queda_registrada(almacen: Almacen) -> None:
    assert extraer_ejemplo(almacen, ficha_ejemplo(es_incidente=campo(False, TITULAR))) is None
    (extraida,) = almacen.extracciones(almacen.candidatos()[0]["id"])
    assert extraida["valida"] is False
    assert almacen.incidentes() == []


def test_el_modelo_de_dron_amplia_el_vocabulario(almacen: Almacen) -> None:
    datos = ficha_ejemplo(modelo_dron=campo("DJI Mavic", "store droner"))
    id_ = extraer_ejemplo(almacen, datos)
    assert id_ is not None
    assert "DJI Mavic" in almacen.vocabulario("modelo_dron")
    incidente = almacen.incidente(id_)
    assert incidente is not None
    assert incidente["drones"]["modelo"] == "DJI Mavic"


def _copia(incidente: dict[str, Any], id_: str, horas: int, url: str) -> dict[str, Any]:
    otro = json.loads(json.dumps(incidente))
    otro["id"] = id_
    inicio = datetime(2025, 9, 22, 18, 30, tzinfo=UTC) + timedelta(hours=horas)
    otro["tiempo"] = {"inicio": {"valor": f"{inicio:%Y-%m-%dT%H:%MZ}", "precision": "hora"}}
    otro["fuentes"][0]["id"] = incidentes.id_fuente(url)
    otro["fuentes"][0]["enlace"] = url
    otro["fuentes"] = otro["fuentes"][:1]
    otro["estado"]["historial"][0]["fuente_id"] = otro["fuentes"][0]["id"]
    otro["afirmaciones"] = []
    copia: dict[str, Any] = otro
    return copia


def test_fusion_reversible_y_fusion_dudosa(almacen: Almacen) -> None:
    id_ = extraer_ejemplo(almacen)
    assert id_ is not None
    base = almacen.incidente(id_)
    assert base is not None
    segundo = _copia(base, "EODI-2025-00002", 2, "https://otro.dk/1")
    almacen.guardar_incidente(segundo, AHORA, MODELOS)
    assert incidentes.fusionar(almacen, AHORA, MODELOS) == 1
    destino, fundido = almacen.incidente(id_), almacen.incidente("EODI-2025-00002")
    assert destino is not None and fundido is not None
    assert fundido["fusionado_en"] == id_
    assert "https://otro.dk/1" in [f["enlace"] for f in destino["fuentes"]]
    incidentes.revertir(almacen, "EODI-2025-00002", AHORA, MODELOS)
    destino, fundido = almacen.incidente(id_), almacen.incidente("EODI-2025-00002")
    assert destino is not None and fundido is not None
    assert "fusionado_en" not in fundido
    assert "https://otro.dk/1" not in [f["enlace"] for f in destino["fuentes"]]
    assert almacen.fusiones()[0]["revertida"] is True


def test_una_fusion_dudosa_no_se_hace(almacen: Almacen) -> None:
    id_ = extraer_ejemplo(almacen)
    assert id_ is not None
    base = almacen.incidente(id_)
    assert base is not None
    # Dos sitios a 25 km (más que 5 + 5 + 10) y un tercero en medio, que encaja con los dos.
    punto = base["lugar"]["punto"]
    for n, horas, desplazamiento, nombre in ((2, 2, 0.225, "Otro"), (3, 3, 0.1125, "Medio")):
        otro = _copia(base, f"EODI-2025-0000{n}", horas, f"https://otro.dk/{n}")
        otro["objetivo"] = {"categoria": "otra", "nombre": nombre}
        otro["lugar"]["punto"] = {"lat": round(punto["lat"] + desplazamiento, 5),
                                  "lon": punto["lon"]}  # fmt: skip
        otro["tipo"] = "sobrevuelo"
        otro["consecuencias"] = {"cierre": {"valor": "desconocido"}}
        almacen.guardar_incidente(otro, AHORA, MODELOS)
    assert incidentes.fusionar(almacen, AHORA, MODELOS) == 0
    assert all("fusionado_en" not in i for i in almacen.incidentes())


def test_mas_de_doce_horas_sin_actividad_es_otro_incidente() -> None:
    a = {"tiempo": {"inicio": {"valor": "2025-09-22T18:30Z", "precision": "hora"}},
         "fuentes": [{"fecha": {"valor": "2025-09-22T19:00Z"}}]}  # fmt: skip
    b: dict[str, Any] = {
        "tiempo": {"inicio": {"valor": "2025-09-23T09:00Z", "precision": "hora"}},
        "fuentes": [],
    }
    assert not incidentes.misma_ventana(a, b)
    b["tiempo"]["inicio"]["valor"] = "2025-09-22T23:00Z"
    assert incidentes.misma_ventana(a, b)


def test_varios_objetivos_en_una_noche_forman_un_episodio(almacen: Almacen) -> None:
    id_ = extraer_ejemplo(almacen)
    assert id_ is not None
    base = almacen.incidente(id_)
    assert base is not None
    otro = _copia(base, "EODI-2025-00002", 1, "https://otro.dk/3")
    otro["objetivo"] = {"categoria": "base_militar", "nombre": "Skrydstrup"}
    otro["lugar"]["punto"] = {"lat": 55.22, "lon": 9.26}
    almacen.guardar_incidente(otro, AHORA, MODELOS)
    assert incidentes.agrupar_episodios(almacen, AHORA, MODELOS) == 2
    (episodio,) = almacen.episodios()
    assert episodio["incidentes"] == [id_, "EODI-2025-00002"]
    assert episodio["noche"] == "2025-09-22"


# --- Llamadas y límites ---------------------------------------------------------------


class ClienteFalso:
    def __init__(self, datos: dict[str, Any]) -> None:
        self.datos = datos
        self.llamadas = 0

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.llamadas += 1
        return respuesta(self.datos)


def test_el_limite_diario_detiene_las_llamadas(almacen: Almacen) -> None:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    almacen.registrar_llamada({
        "fecha": "2025-09-24T01:00:00Z", "modo": "horario", "candidato": "x", "lote": False,
        "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_DIARIO_USD,
    })  # fmt: skip
    falso = ClienteFalso(ficha_ejemplo())
    extraccion.extraer(almacen, falso, [peticion], AHORA, coste.Modo.HORARIO, MODELOS)
    assert falso.llamadas == 0


def test_candidatos_que_necesitan_extraccion(almacen: Almacen) -> None:
    candidato = candidato_con_articulos(almacen)
    assert extraccion.necesita_extraccion(almacen, candidato)
    extraer_ejemplo(almacen)
    (candidato,) = almacen.candidatos()
    # Misma huella de artículos: no se repite.
    assert not extraccion.necesita_extraccion(almacen, candidato)


def test_recorte_del_lote_al_limite_del_historico(almacen: Almacen) -> None:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    caso = coste.peor_caso(peticion.letras(), ficha.MAX_TOKENS_SALIDA, lote=True)
    almacen.registrar_llamada({
        "fecha": "2025-09-24T01:00:00Z", "modo": "historico", "candidato": "x", "lote": True,
        "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_HISTORICO_USD - caso * 1.5,
    })  # fmt: skip
    elegidas, previsto = extraccion.recortar_para_lote(almacen, [peticion, peticion])
    assert len(elegidas) == 1
    assert previsto == pytest.approx(caso)


def test_paso_horario_sin_configuracion_no_hace_nada(
    almacen: Almacen, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recogida import extractor

    for variable in ("EODI_EXTRACTOR_CLAVE", "EODI_EXTRACTOR_URL"):
        monkeypatch.delenv(variable, raising=False)
    candidato_con_articulos(almacen)
    assert extractor.horaria(almacen, AHORA).llamadas == 0


def test_paso_horario_con_servicio(almacen: Almacen, monkeypatch: pytest.MonkeyPatch) -> None:
    from recogida import extractor

    valores = {
        "EODI_EXTRACTOR_CLAVE": "k", "EODI_EXTRACTOR_URL": "u", "EODI_EXTRACTOR_URL_LOTES": "l",
        "EODI_EXTRACTOR_MODELO": "m", "EODI_EXTRACTOR_CABECERAS": '{"c": "{clave}"}',
    }  # fmt: skip
    for nombre, valor in valores.items():
        monkeypatch.setenv(nombre, valor)
    monkeypatch.setattr(extractor, "Descargador", lambda: None)
    monkeypatch.setattr(paginas, "leer", lambda _d, _u: TEXTO)
    candidato_con_articulos(almacen, horas=2)
    falso = ClienteFalso(ficha_ejemplo(inicio=campo("2025-09-23T08:30", "mandag aften")))
    resultado = extractor.horaria(almacen, AHORA, lambda _c: falso)
    assert (resultado.candidatos, resultado.llamadas, resultado.publicados) == (1, 1, 1)
    assert almacen.gastado("horario", "2025-09-24") > 0


def test_frase_larga_recortada_y_sin_fecha_se_publica_con_la_del_candidato() -> None:
    larga = f"{TITULAR}. {TEXTO}"
    cambios = {"es_incidente": campo(True, larga), "inicio": campo(None)}
    validada = validar(ficha_ejemplo(**cambios), contexto())
    assert len(validada.campos["es_incidente"]["frase"].split()) == 25
    assert validada.publicable


def test_otro_sitio_sin_lugar_nuevo_no_se_publica() -> None:
    validada = validar(ficha_ejemplo(objetivo_conocido=campo(False, TITULAR)), contexto())
    assert not validada.publicable


class LotesFalsos:
    """Servicio de lotes falso: el lote termina en la segunda consulta."""

    def __init__(self, datos: dict[str, Any]) -> None:
        self.datos = datos
        self.enviadas: list[dict[str, Any]] = []
        self.consultas = 0

    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]:
        self.enviadas = peticiones
        return {"id": "l1", "processing_status": "in_progress"}

    def lote(self, id_: str) -> dict[str, Any]:
        self.consultas += 1
        return {"id": id_, "processing_status": "ended", "results_url": "r"}

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"custom_id": p["custom_id"], "result": {"type": "succeeded",
                                                      "message": respuesta(self.datos)}}
            for p in self.enviadas
        ]  # fmt: skip


def test_lote_envia_espera_y_procesa(almacen: Almacen) -> None:
    candidato = candidato_con_articulos(almacen)
    peticion = extraccion.preparar(almacen, candidato, None)
    fuentes = [
        ficha.FuenteTexto(f.medio, f.fecha, f.idioma, f.titular, TEXTO) for f in peticion.fuentes
    ]
    peticion = extraccion.Peticion(**{**peticion.__dict__, "fuentes": fuentes})
    falso = LotesFalsos(ficha_ejemplo())
    recuentos = extraccion.extraer_lote(
        almacen, falso, [peticion], lambda: AHORA, MODELOS, lambda _: None
    )
    assert recuentos == {"enviadas": 1, "publicadas": 1, "fallidas": 0, "fuera_de_limite": 0}
    assert falso.consultas == 1
    (llamada,) = almacen.llamadas()
    assert llamada["lote"] == 1


def test_otra_instalacion_que_la_conocida_no_se_publica_alli(almacen: Almacen) -> None:
    # «Alarm am Flughafen Leipzig» en un candidato de otro aeropuerto.
    datos = ficha_ejemplo(objetivo_nombre=campo("Flughafen Leipzig", "Københavns Lufthavn"))
    assert extraer_ejemplo(almacen, datos) is None
    (extraida,) = almacen.extracciones(almacen.candidatos()[0]["id"])
    assert "objetivo_nombre: no es la instalación conocida" in extraida["motivos"]


def test_reconstruir_rehace_el_incidente_sin_llamar(almacen: Almacen) -> None:
    id_ = extraer_ejemplo(almacen)
    assert id_ is not None
    llamadas = len(almacen.llamadas())
    assert extraccion.reconstruir(almacen, AHORA, MODELOS) == 1
    assert len(almacen.llamadas()) == llamadas
    rehecho = almacen.incidente(id_)
    assert rehecho is not None
    assert rehecho["tipo"] == "interrupcion_aeroportuaria"
