"""Fuentes oficiales de detalle: pasajes, ficha y validación, extracción con cruce y alta,
orquestación (recogida, incorporación, histórico por lotes), estadísticas y listas
renderizadas. Sin red y con textos reales."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from esquema import Documento
from exportacion.geojson import exportar
from modelo import cliente as servicio_extractor
from modelo import coste, ficha_oficial
from proceso import detalle, extraccion_oficial, presencia
from proceso.pasajes import localizar, parrafos
from proceso.validacion_oficial import validar_cifra, validar_suceso
from recogida import detalle as recogida_detalle
from recogida import estadisticas, navegador, oficiales
from recogida.descarga import PaginaBloqueada
from recogida.estado import CON_AVISO, LEIDA, NO_LEIDA
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_detalle import heathrow

FIXTURES = Path(__file__).parent / "fixtures" / "detalle"
AHORA = datetime(2026, 10, 1, 12, tzinfo=UTC)
RIGSPOLITIET = (FIXTURES / "politi_rigspolitiet_2026-06-25.txt").read_text(encoding="utf-8")


# --- Pasajes ------------------------------------------------------------------------------


def leido(documento: Documento | None) -> Documento:
    assert documento is not None
    return documento


def test_solo_llegan_los_pasajes_que_nombran_drones_y_el_siguiente() -> None:
    texto = "\n\n".join(
        [
            "Introducción sin nada que ver con el tema que nos ocupa hoy aquí.",
            "Im Jahr 2025 wurden 172 Drohnenbehinderungen dokumentiert, schrieb die Regierung.",
            "Die Zahl umfasst alle Verkehrsflughäfen in Deutschland ohne Ausnahme.",
            "Otro párrafo largo que ya no habla de aquello y no debe llegar al extractor.",
        ]
    )
    pasajes = localizar(texto)
    assert len(pasajes.textos) == 2
    assert "172 Drohnenbehinderungen" in pasajes.textos[0]
    assert "Verkehrsflughäfen" in pasajes.textos[1]
    assert len(pasajes.huella) == 64


def test_un_parrafo_largo_se_trocea_por_frases() -> None:
    trozos = parrafos(RIGSPOLITIET)
    assert len(trozos) > 1 and all(len(t) <= 1000 for t in trozos)
    pasajes = localizar(RIGSPOLITIET)
    assert any("7.000 anmeldelser" in p for p in pasajes.textos)
    assert any("hverken kunnet påvises eller afvises" in p for p in pasajes.textos)


def test_un_documento_sin_drones_no_tiene_pasajes() -> None:
    assert localizar("Ein Bericht über Lärmschutz an Flughäfen.\n\nNichts weiter.").textos == ()


def test_las_tablas_van_enteras() -> None:
    tabla = "Flughafen  2022  2023\nFrankfurt  26  21\nLeipzig  12  21"
    assert parrafos(tabla) == [tabla]


# --- Ficha y validación ------------------------------------------------------------------


def respuesta(sucesos: list[Documento], cifras: list[Documento]) -> dict[str, Any]:
    return {
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 3000, "output_tokens": 400},
        "content": [{"type": "text", "text": json.dumps({"sucesos": sucesos, "cifras": cifras})}],
    }


def cifra(**cambios: Any) -> Documento:
    return {
        "metrica": "avistamientos",
        "valor": "7.000-7.000",
        "periodo_inicio": "2025-09-22",
        "periodo_fin": "2026-06-25",
        "pais": "DK",
        "categoria": "",
        "instalacion": "",
        "frase": "mere end 7.000 anmeldelser om mulige droneobservationer i dansk luftrum",
        "confianza": 0.9,
        **cambios,
    }


def test_la_respuesta_se_lee_con_sus_valores_tipados() -> None:
    leida = ficha_oficial.leer_respuesta(
        respuesta(
            [
                {
                    "titulo_es": "t",
                    "titulo_en": "t",
                    "datos": [
                        {"campo": "altura_m", "valor": "100-150", "frase": "f", "confianza": 0.9},
                        {
                            "campo": "deteccion",
                            "valor": "radar, visual",
                            "frase": "f",
                            "confianza": 0.9,
                        },
                        {
                            "campo": "resultado_contramedidas",
                            "valor": "no_funciono",
                            "frase": "f",
                            "confianza": 0.9,
                        },
                        {"campo": "drones", "valor": "varios", "frase": "f", "confianza": 0.9},
                    ],
                }
            ],
            [{**cifra(), "valor": "7000"}],
        )
    )
    datos = leida["sucesos"][0]["datos"]
    assert datos["altura_m"]["valor"] == {"min": 100.0, "max": 150.0}
    assert datos["deteccion"]["valor"] == ["radar", "visual"]
    assert datos["resultado_contramedidas"]["valor"] == "no_funciono"
    assert "drones" not in datos and leida["ilegibles"] == [
        "suceso 1, drones: no es un número ni un rango"
    ]
    assert leida["cifras"][0]["valor"] == {"min": 7000, "max": 7000}


@pytest.mark.parametrize(
    ("cambios", "motivo"),
    [
        ({}, None),
        ({"frase": "más de siete mil avisos"}, "la frase no está en el texto"),
        (
            {"frase": "Politiet modtog i perioden fra den 22. september 2025"},
            "la cifra no está escrita en su frase",
        ),
        ({"confianza": 0.4}, "confianza baja"),
        ({"pais": "US"}, "país fuera de la recogida"),
        ({"periodo_inicio": "2026-07-01"}, "periodo con fin anterior al inicio"),
        ({"categoria": "cuartel"}, "categoría fuera de la lista"),
    ],
)
def test_validacion_de_las_cifras(cambios: Documento, motivo: str | None) -> None:
    valor = {"valor": {"min": 7000, "max": 7000}}
    assert validar_cifra({**cifra(**cambios), **valor}, RIGSPOLITIET, date(2026, 6, 25)) == motivo


def test_un_suceso_posterior_al_documento_o_de_frase_inventada_pierde_esos_datos() -> None:
    suceso = {
        "titulo_es": "t",
        "titulo_en": "t",
        "datos": {
            "inicio": {
                "valor": "2026-07-01",
                "frase": "Københavns Politi har i dag fremlagt resultaterne",
                "confianza": 0.9,
            },
            "altura_m": {
                "valor": {"min": 50.0, "max": 60.0},
                "frase": "a 50 metros de altura",
                "confianza": 0.9,
            },
            "pais": {
                "valor": "DK",
                "frase": "droneobservationer i dansk luftrum",
                "confianza": 0.9,
            },
        },
    }
    validado, motivos = validar_suceso(suceso, RIGSPOLITIET, "DK", date(2026, 6, 25), AHORA)
    assert "inicio" not in validado.datos and "altura_m" not in validado.datos
    assert validado.datos["pais"]["valor"] == "DK"
    assert "inicio: posterior al documento" in motivos
    assert "altura_m: la frase no está en el texto" in motivos


# --- Extracción: cruce, alta y estadísticas -------------------------------------------------

TEXTO_GB = (
    "On 20 August 2025 at 13:40 a drone was detected by radar near London Heathrow Airport and "
    "jamming was used without success. Since 1 January 2025 there have been a total of 187 drone "
    "sightings in the vicinity of military establishments in the UK. On 12 May 2025 a drone was "
    "seen over RAF Lakenheath, near Brandon."
)


def recogido(tipo: str = "respuesta_parlamentaria", texto: str = TEXTO_GB) -> Documento:
    return {
        "id": "uk_parlamento:1843693",
        "fuente_detalle": "uk_parlamento",
        "tipo": tipo,
        "autoridad": "UK Government (Ministry of Defence)",
        "pais": "GB",
        "idioma": "en",
        "titulo": "Military Bases: Unmanned Air Systems",
        "fecha": "2025-11-04",
        "enlace": "https://questions-statements.parliament.uk/written-questions/detail/2025-10-21/HL11210",
        "fiabilidad": "A",
        "credibilidad": 1,
        "pasajes": [texto],
    }


def dato(valor: str, frase: str, confianza: float = 0.95) -> Documento:
    return {"valor": valor, "frase": frase, "confianza": confianza}


def suceso_heathrow() -> Documento:
    return {
        "titulo_es": "Dron sobre Heathrow",
        "titulo_en": "Drone over Heathrow",
        "datos": [
            {"campo": c, **d}
            for c, d in {
                "inicio": dato(
                    "2025-08-20T13:40", "On 20 August 2025 at 13:40 a drone was detected by radar"
                ),
                "inicio_precision": dato("minuto", "On 20 August 2025 at 13:40"),
                "pais": dato("GB", "near London Heathrow Airport"),
                "lugar_suceso": dato(
                    "London Heathrow Airport; instalacion; GB;",
                    "a drone was detected by radar near London Heathrow Airport",
                ),
                "deteccion": dato("radar", "a drone was detected by radar"),
                "medidas": dato("inhibicion", "jamming was used without success"),
                "resultado_contramedidas": dato("no_funciono", "jamming was used without success"),
                "presencia_dron": dato("confirmada", "a drone was detected by radar"),
            }.items()
        ],
    }


def suceso_lakenheath() -> Documento:
    return {
        "titulo_es": "Dron sobre RAF Lakenheath",
        "titulo_en": "Drone over RAF Lakenheath",
        "datos": [
            {"campo": c, **d}
            for c, d in {
                "inicio": dato("2025-05-12", "On 12 May 2025 a drone was seen over RAF Lakenheath"),
                "pais": dato("GB", "a drone was seen over RAF Lakenheath"),
                "lugar_suceso": dato(
                    "RAF Lakenheath; instalacion; GB;", "a drone was seen over RAF Lakenheath"
                ),
                "objetivo_categoria": dato("base_militar", "a drone was seen over RAF Lakenheath"),
            }.items()
        ],
    }


def cifra_gb() -> Documento:
    return {
        "metrica": "avistamientos",
        "valor": "187",
        "periodo_inicio": "2025-01-01",
        "periodo_fin": "2025-11-04",
        "pais": "GB",
        "categoria": "base_militar",
        "instalacion": "",
        "frase": "Since 1 January 2025 there have been a total of 187 drone sightings",
        "confianza": 0.95,
    }


def base_con_heathrow() -> Almacen:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(heathrow(), AHORA, VOCABULARIO_MODELOS)
    return almacen


def procesar(
    almacen: Almacen, documento: Documento, sucesos: list[Documento], cifras: list[Documento]
) -> Documento:
    return extraccion_oficial.procesar(
        almacen,
        documento,
        respuesta(sucesos, cifras),
        AHORA,
        coste.Modo.HORARIO,
        False,
        VOCABULARIO_MODELOS,
    )


def test_la_respuesta_parlamentaria_confirma_el_incidente_y_da_la_cifra() -> None:
    almacen = base_con_heathrow()
    documento = procesar(almacen, recogido(), [suceso_heathrow()], [cifra_gb()])
    assert documento["estado"] == "extraido"
    (cruce,) = [s for s in documento["sucesos"] if s.get("incidente") == "EODI-2025-00134"]
    assert cruce["cruce"] == "existente"
    detalle.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    incidente = almacen.incidente("EODI-2025-00134")
    assert incidente is not None and incidente["estado"]["actual"] == "confirmado"
    assert incidente["respuesta"]["deteccion"] == ["radar"]
    assert incidente["presencia_dron"] == "confirmada"
    (estadistica,) = almacen.estadisticas_oficiales()
    assert estadistica["cifra"] == {"min": 187, "max": 187}
    assert estadistica["procedencia"]["cifra"]["metodo"] == "extractor"
    assert estadistica["ambito"] == {"pais": "GB", "categoria": "base_militar"}
    (llamada,) = almacen.llamadas()
    assert llamada["modo"] == "horario" and llamada["candidato"] == "uk_parlamento:1843693"


def test_un_suceso_citado_que_no_esta_entra_como_incidente_nuevo() -> None:
    almacen = base_con_heathrow()
    documento = procesar(almacen, recogido(), [suceso_lakenheath()], [])
    (cruce,) = documento["sucesos"]
    assert cruce["cruce"] == "nuevo", cruce
    nuevo = almacen.incidente(cruce["incidente"])
    assert nuevo is not None
    assert nuevo["control"]["version_extractor"] == "oficial/1"
    assert nuevo["estado"]["actual"] == "confirmado"
    assert "Lakenheath" in nuevo["objetivo"]["nombre"] and nuevo["lugar"]["pais"] == "GB"
    (fuente,) = nuevo["fuentes"]
    assert fuente["id"] == detalle.id_fuente(recogido()["enlace"]) and fuente["fiabilidad"] == "A"
    assert {a["fuente_id"] for a in nuevo["afirmaciones"]} == {fuente["id"]}
    # Sale a la web como cualquier otro, con su fuente oficial.
    assert exportar([nuevo], AHORA, VOCABULARIO_MODELOS)["features"]


def test_un_informe_de_investigacion_no_da_de_alta_incidentes() -> None:
    almacen = base_con_heathrow()
    documento = procesar(almacen, recogido("informe_investigacion"), [suceso_lakenheath()], [])
    assert documento["sucesos"][0]["cruce"] == "sin_incidente"
    assert len(almacen.incidentes()) == 1


def test_una_respuesta_ilegible_deja_el_documento_sin_datos() -> None:
    almacen = Almacen.abrir()
    malo = {"stop_reason": "max_tokens", "usage": {}, "content": []}
    documento = extraccion_oficial.procesar(
        almacen, recogido(), malo, AHORA, coste.Modo.DETALLE, True, VOCABULARIO_MODELOS
    )
    assert documento["estado"] == "sin_datos" and documento["descartados"] == ["parada: max_tokens"]
    assert almacen.llamadas()[0]["modo"] == "detalle"


def test_un_cierre_que_no_pudo_demostrar_los_drones_corrige_la_presencia() -> None:
    confirmado = heathrow()
    confirmado["presencia_dron"] = "confirmada"
    almacen = Almacen.abrir()
    almacen.guardar_incidente(confirmado, AHORA, VOCABULARIO_MODELOS)
    cierre = {
        **recogido("cierre_investigacion"),
        "id": "politi_dk:kbh-2026-06-25",
        "fecha": "2026-06-25",
        "enlace": "https://politi.example/cierre",
    }
    documento = extraccion_oficial.documento_base(cierre, AHORA)
    documento.update(
        {
            "estado": "extraido",
            "sucesos": [
                {
                    "datos": {
                        "presencia_dron": dato(
                            "no_confirmada", "hverken kunnet påvises eller afvises"
                        )
                    },
                    "cruce": "existente",
                    "incidente": "EODI-2025-00134",
                }
            ],
        }
    )
    almacen.guardar_documento_oficial(documento, AHORA)
    detalle.revisar(almacen, AHORA, VOCABULARIO_MODELOS)
    incidente = almacen.incidente("EODI-2025-00134")
    assert incidente is not None and incidente["presencia_dron"] == "no_confirmada"
    # La regla de las declaraciones citadas no la vuelve a confirmar.
    assert all(i["id"] != "EODI-2025-00134" for i, _ in presencia.pendientes(almacen))


def test_las_llamadas_directas_paran_en_el_limite_de_gasto() -> None:
    almacen = Almacen.abrir()

    class Servicio:
        def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
            return respuesta([], [])

    almacen.registrar_llamada(
        {
            "fecha": "2026-10-01T10:00:00Z",
            "modo": "horario",
            "candidato": "x",
            "lote": False,
            "entrada": 0,
            "salida": 0,
            "escritura_cache": 0,
            "lectura_cache": 0,
            "coste": coste.LIMITE_DIARIO_USD,
        }
    )
    hechos = extraccion_oficial.extraer(
        almacen, Servicio(), [recogido()], AHORA, coste.Modo.HORARIO, VOCABULARIO_MODELOS
    )
    assert hechos.documentos == [] and str(hechos.parada) == "límite de gasto"


# --- Orquestación ------------------------------------------------------------------------


@pytest.fixture
def fuentes_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recogida_detalle,
        "fuentes",
        lambda: [
            {"id": "ukab", "tipo": "prueba_bien", "grupo": "airprox"},
            {"id": "dip", "tipo": "prueba_mal", "grupo": "parlamentos"},
            {"id": "tk", "tipo": "prueba_bien", "grupo": "parlamentos"},
        ],
    )
    monkeypatch.setitem(recogida_detalle.RECOLECTORES, "prueba_bien", lambda *a: 3)

    def mal(*argumentos: Any) -> int:
        raise PaginaBloqueada("403")

    monkeypatch.setitem(recogida_detalle.RECOLECTORES, "prueba_mal", mal)


@pytest.mark.usefixtures("fuentes_de_prueba")
def test_una_fuente_que_falla_no_para_las_demas_y_queda_en_el_estado(tmp_path: Path) -> None:
    resultado = recogida_detalle.recoger(tmp_path, AHORA)
    assert resultado.leidas == ["ukab", "tk"] and resultado.fallidas == ["dip"]
    estados = recogida_detalle.estados(tmp_path)
    assert estados["airprox"].estado == LEIDA and estados["airprox"].ultimo_dato == AHORA
    assert estados["parlamentos"].estado == CON_AVISO
    assert estados["investigaciones"].estado == NO_LEIDA
    control = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert control["dip"]["error"] == "403" and "ultima_correcta" not in control["dip"]


def preparar_raiz(raiz: Path) -> None:
    from tests import ejemplos

    (raiz / "airprox").mkdir(parents=True)
    (raiz / "airprox" / "encuentros.json").write_text(
        json.dumps([ejemplos.encuentro()]), encoding="utf-8"
    )
    recogida_detalle.guardar_documentos(
        raiz,
        "uk_parlamento",
        [
            {**recogido(), "fecha": "2026-09-20"},
            {**recogido(), "id": "uk_parlamento:1", "fecha": "2025-01-10"},
            {**recogido(), "id": "uk_parlamento:2", "fecha": "2026-09-21", "pasajes": []},
        ],
    )


class Cliente:
    def __init__(self) -> None:
        self.mensajes = 0
        self.lotes: list[list[dict[str, Any]]] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.mensajes += 1
        assert "Pasaje 1:" in cuerpo["messages"][0]["content"]
        return respuesta([], [cifra_gb()])

    def crear_lote(self, peticiones: list[dict[str, Any]]) -> dict[str, Any]:
        self.lotes.append(peticiones)
        return {"id": "lote-1", "processing_status": "ended"}

    def lote(self, id_: str) -> dict[str, Any]:
        return {"id": id_, "processing_status": "ended"}

    def resultados_lote(self, lote: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "custom_id": p["custom_id"],
                "result": {"type": "succeeded", "message": respuesta([], [cifra_gb()])},
            }
            for p in self.lotes[-1]
        ]


def test_la_incorporacion_horaria_extrae_solo_lo_reciente(tmp_path: Path) -> None:
    preparar_raiz(tmp_path)
    almacen = Almacen.abrir()
    # Sin configuración del extractor no se llama; con ella, solo a lo de los últimos 30 días.
    hecho = recogida_detalle.incorporar(almacen, AHORA, VOCABULARIO_MODELOS, tmp_path)
    assert hecho.encuentros == 1 and hecho.documentos == 3
    assert hecho.parada is not None and "sin configurar" in hecho.parada
    estados = {d["id"]: d["estado"] for d in almacen.documentos_oficiales()}
    assert estados == {
        "uk_parlamento:1": "pendiente",
        "uk_parlamento:1843693": "pendiente",
        "uk_parlamento:2": "sin_drones",
    }


def test_la_incorporacion_con_extractor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    preparar_raiz(tmp_path)
    almacen = Almacen.abrir()
    cliente = Cliente()
    monkeypatch.setattr(servicio_extractor, "configuracion", lambda: object())
    hecho = recogida_detalle.incorporar(
        almacen, AHORA, VOCABULARIO_MODELOS, tmp_path, fabrica=lambda _c: cliente
    )
    assert cliente.mensajes == 1 and hecho.extraidos == 1
    assert leido(almacen.documento_oficial("uk_parlamento:1843693"))["estado"] == "extraido"
    assert leido(almacen.documento_oficial("uk_parlamento:1"))["estado"] == "pendiente"
    # Volver a incorporar no cambia nada.
    recogida_detalle.incorporar(
        almacen, AHORA, VOCABULARIO_MODELOS, tmp_path, fabrica=lambda _c: cliente
    )
    assert cliente.mensajes == 1


def test_el_historico_va_por_lotes_con_su_presupuesto(tmp_path: Path) -> None:
    preparar_raiz(tmp_path)
    almacen = Almacen.abrir()
    recogida_detalle.incorporar(almacen, AHORA, VOCABULARIO_MODELOS, tmp_path)
    cliente = Cliente()
    assert recogida_detalle.historico(tmp_path, almacen, cliente, AHORA) == 1
    (peticiones,) = cliente.lotes
    assert len(peticiones) == 1  # solo lo anterior a los últimos 30 días
    # Mientras no se incorpore, no se envía otro.
    assert recogida_detalle.historico(tmp_path, almacen, cliente, AHORA) == 0
    assert recogida_detalle.incorporar_lotes(almacen, tmp_path, AHORA, VOCABULARIO_MODELOS) == 1
    assert leido(almacen.documento_oficial("uk_parlamento:1"))["estado"] == "extraido"
    assert almacen.gastado(coste.Modo.DETALLE.value) > 0
    assert recogida_detalle.incorporar_lotes(almacen, tmp_path, AHORA, VOCABULARIO_MODELOS) == 0


# --- Estadísticas ------------------------------------------------------------------------


def test_la_tabla_mensual_de_la_ukab_se_lee_con_codigo() -> None:
    from recogida import airprox

    contenido = (FIXTURES / "ukab_ua_other_meses.xlsx").read_bytes()
    cifras = estadisticas.cifras_meses(airprox.filas_xlsx(contenido, "By Month"), "2026-09-29")
    por_frase = {c["frase"]: c for c in cifras}
    assert por_frase["By Month: 2016 May 10"]["periodo_inicio"] == "2016-05-01"
    assert por_frase["By Month: 2016 May 10"]["periodo_fin"] == "2016-05-31"
    # Una celda vacía no es un cero; un cero escrito, sí.
    assert "By Month: 2014 Jan 0" not in por_frase
    assert por_frase["By Month: 2020 Apr 0"]["valor"] == {"min": 0, "max": 0}
    total = next(c for c in cifras if c["frase"].startswith("By Month: 2026 Total"))
    assert total["periodo_fin"] == "2026-09-29"  # el año en curso, hasta el día del Excel
    assert airprox.fecha_xlsx(contenido) == "2026-09-29"


def test_una_publicacion_html_da_sus_pasajes_y_su_fecha() -> None:
    publicacion = {
        "id": "dfs_2026_01_05",
        "autoridad": "DFS Deutsche Flugsicherung",
        "pais": "DE",
        "idioma": "en",
        "formato": "html",
        "fecha": "2026-01-05",
        "titulo": "Air traffic in Germany 2025",
        "url": "https://www.dfs.de/homepage/en/media/press/2026/05-01-2026/",
    }
    documento = estadisticas.documento_publicacion(
        publicacion, (FIXTURES / "dfs_2026-01-05.html").read_bytes()
    )
    assert documento["tipo"] == "estadistica" and documento["fecha"] == "2026-01-05"
    assert any("225" in p for p in documento["pasajes"])


# --- Listas renderizadas ---------------------------------------------------------------------

LVNL = {
    "id": "lvnl",
    "medio": "Luchtverkeersleiding Nederland",
    "pais": "NL",
    "idioma": "nl",
    "tipo": "pagina_js",
    "zona": "Europe/Amsterdam",
    "url": "https://www.lvnl.nl/nieuws",
    "enlace": r"lvnl\.nl/nieuws/[a-z0-9-]+$",
    "sobra_titulo": r"\d{1,2} \w+ \d{4}$",
}


def test_la_lista_renderizada_se_guarda_y_caduca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (FIXTURES / "js_lvnl_lista.html").read_text(encoding="utf-8")
    monkeypatch.setattr(navegador, "renderizar", lambda url, tope_s=30.0: html)
    render = navegador.leer(LVNL, tmp_path)
    assert render.enlaces == 13
    assert navegador.guardado(LVNL, tmp_path, datetime.now(UTC)) == html
    assert navegador.guardado(LVNL, tmp_path, datetime(2099, 1, 1, tzinfo=UTC)) is None


def test_una_lista_sin_notas_es_un_bloqueo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        navegador, "renderizar", lambda url, tope_s=30.0: "<html>Just a moment</html>"
    )
    with pytest.raises(PaginaBloqueada):
        navegador.leer(LVNL, tmp_path)


def test_la_recogida_horaria_lee_las_notas_de_la_lista_renderizada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (FIXTURES / "js_lvnl_lista.html").read_text(encoding="utf-8")
    nota = (
        '<html><head><meta property="article:published_time" content="2026-08-21T10:00:00+02:00">'
        "</head><body><p>" + "Nieuwe stap naar uniforme aanvraagprocedure voor dronevluchten in "
        "Nederland, met regels voor drones rond luchthavens. " * 2 + "</p></body></html>"
    )
    monkeypatch.setattr(navegador, "renderizar", lambda url, tope_s=30.0: html)
    navegador.leer(LVNL, tmp_path / "paginas_js")
    monkeypatch.setenv(oficiales.VARIABLE_DATOS_DETALLE, str(tmp_path))
    pedidas: list[str] = []

    def transporte(
        url: str, cabeceras: dict[str, str], limite: float
    ) -> tuple[int, dict[str, str], bytes]:
        pedidas.append(url)
        if url.endswith("/robots.txt"):
            return 200, {}, b"User-agent: *\nAllow: /\n"
        return 200, {}, nota.encode()

    from recogida.descarga import Descargador

    descargador = Descargador(transporte=transporte, dormir=lambda _: None, agente="EODI-bot/1.0")
    lector = oficiales.robots(descargador, LVNL["url"])
    notas = oficiales.leer_pagina(
        descargador,
        lector,
        LVNL,
        navegador.guardado(LVNL, oficiales.carpeta_renders(), datetime.now(UTC)),
    )
    # La lista no se pide: viene del render. Solo se abren las notas que hablan de drones.
    assert "https://www.lvnl.nl/nieuws" not in pedidas
    assert notas and all("drone" in n.titulo.lower() for n in notas)
