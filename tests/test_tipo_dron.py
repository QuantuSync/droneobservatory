"""Tipo de dron: rasgos descritos, identificación por la autoridad, clase probable y su
comprobación contra casos de respuesta conocida (copia fija de la base del 6 de octubre de 2026,
tests/fixtures/tipo_dron/conocidos.json.gz)."""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from almacen.base import Almacen
from exportacion import procedencia
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE
from proceso.deduccion import catalogo as catalogo_
from proceso.tipo_dron import calculo, casos, comprobacion, identificacion, modelo, publico
from proceso.tipo_dron.rasgos import Frase, de_frase, de_frases
from recogida import tipo_dron

COPIA = Path(__file__).parent / "fixtures" / "tipo_dron" / "conocidos.json.gz"


def rasgos_de(texto: str, origen: str = "prensa") -> dict[str, object]:
    return {r["rasgo"]: r["valor"] for r in de_frase(Frase(texto, "f1", origen))}


# --- Rasgos ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "rasgo", "valor"),
    [
        ("A small quadcopter drone was seen hovering over the runway", "forma", "multirrotor"),
        ("A small quadcopter drone was seen hovering over the runway", "tamano", "pequeno"),
        ("A small quadcopter drone was seen hovering over the runway", "comportamiento",
         "estatico"),
        ("Major airport reopens after multiple 'large drones' cause travel chaos", "tamano",
         "grande"),
        ("nogle store droner, som har fløjet rundt derude", "tamano", "grande"),
        ("vehiculelor aeriene fără pilot cu propulsie cu reacție", "ruido", "reaccion"),
        ("Witnesses said the drone sounded like a moped", "ruido", "combustion"),
        ("O dronă Shahed a survolat 18 minute spațiul aerian", "duracion", {"minutos": 18.0}),
        ("a zburat deasupra regiunii, la o înălțime de circa 500 m", "altura", {"metros": 500.0}),
        ("un drone Shahed russe volant à 400 km/h a été abattu", "velocidad", {"kmh": 400.0}),
        ("A 10ft drone came so close to colliding with a passenger jet.", "tamano",
         {"metros": 3.05}),
        ("Dansk politi: Flere droner med lys flyr fortsatt over Aalborg lufthavn", "luces", "si"),
        ("O dronă maritimă a explodat în Portul Constanța", "forma", "maritimo"),
    ],
)  # fmt: skip
def test_rasgos_que_dice_la_frase(texto: str, rasgo: str, valor: object) -> None:
    assert rasgos_de(texto)[rasgo] == valor


@pytest.mark.parametrize(
    "texto",
    [
        # Nombres propios, comparativos de otra cosa y aviones de pasajeros no son rasgos.
        "drones gespot boven luchtmachtbasis van Kleine-Brogel",
        "Cierra el aeropuerto de Múnich, el segundo más grande de Alemania, tras el avistamiento",
        "condamne avec la plus grande fermeté l'incursion de drones russes",
        "A passenger jet came so close to colliding with a drone",
        "Zboruri oprite la München din cauza unei drone. Obiectul e căutat cu elicoptere",
        "The caller mentioned a larger number of drones",
        "A specialized team from the Burgas Naval Base confirmed the drone had no explosives",
        # Una confusión no describe ningún dron.
        "the crew had misidentified the red flashing lights of an F-15 as a drone",
        # La duración de un cierre no es la del vuelo.
        "Avvistamento di droni, l'aeroporto di Liegi chiude per 30 minuti",
        "Second drone scare in 24 hours grounds flights at Munich Airport",
    ],
)
def test_lo_que_no_es_un_rasgo(texto: str) -> None:
    hallados = rasgos_de(texto)
    hallados.pop("numero", None)
    hallados.pop("comportamiento", None)
    assert hallados == {}


def test_cada_rasgo_lleva_su_frase_y_su_fuente() -> None:
    lista = de_frases(
        [
            Frase("Un quadricottero da 32 chilogrammi", "fuente-a", "prensa", "it"),
            Frase("A quadcopter drone", "fuente-b", "oficial", "en"),
        ]
    )
    forma = [r for r in lista if r["rasgo"] == "forma"]
    assert forma == [
        {
            "rasgo": "forma",
            "valor": "multirrotor",
            "cita": "Un quadricottero da 32 chilogrammi",
            "fuente": "fuente-a",
            "origen": "prensa",
        }
    ]


# --- Identificación -----------------------------------------------------------------------------


def test_la_autoridad_identifica_sin_duda() -> None:
    hallado = identificacion.identificado(
        [Frase("Două drone UAV, tip Gerbera, au fost distruse", "mapn", "oficial_citado")]
    )
    assert hallado is not None
    assert (hallado["modelo"], hallado["grupo"], hallado["fuente"]) == (
        "Gerbera",
        "senuelo",
        "mapn",
    )


@pytest.mark.parametrize(
    ("texto", "origen"),
    [
        ("un aparat de zbor necunoscut, asemănător unei drone de tip Shahed", "oficial_citado"),
        ("dronă rusească de tip Shahed ar fi survolat spațiul aerian", "oficial_citado"),
        ("O dronă de tip Shahed a survolat spațiul aerian", "prensa"),
    ],
)
def test_parecido_duda_o_prensa_no_identifican(texto: str, origen: str) -> None:
    assert identificacion.identificado([Frase(texto, "f", origen)]) is None


def test_tapar_modelos_quita_el_nombre() -> None:
    tapado = identificacion.tapar_modelos("Drona de tip Geran-2 a căzut; DJI Mavic incautat")
    assert "Geran" not in tapado and "DJI" not in tapado and "Mavic" not in tapado


# --- Modelo y comprobación ----------------------------------------------------------------------


def conocidos() -> list[casos.Conocido]:
    datos = json.loads(gzip.decompress(COPIA.read_bytes()))
    return [casos.de_documento(d) for d in datos["casos"]]


def test_la_comprobacion_mejora_a_la_referencia() -> None:
    """Falla si el método deja de mejorar a «decir siempre el grupo más frecuente»."""
    resumen = comprobacion.resumen(comprobacion.evaluar(catalogo_.cargar(), conocidos()))
    assert resumen["pasa"]
    assert resumen["metodo"]["acierto"] > resumen["referencia"]["acierto"]
    assert resumen["metodo"]["log_por_caso"] > resumen["referencia"]["log_por_caso"] + 0.05
    assert resumen["mejora_log_p10"] > 0
    # Lo comprobado el 6 de octubre de 2026: la frontera, con los dos grupos de largo alcance.
    assert set(resumen["grupos_publicados"]) == {"largo_alcance_helice", "senuelo"}


def test_un_grupo_sin_casos_suficientes_no_se_publica() -> None:
    resumen = comprobacion.resumen(comprobacion.evaluar(catalogo_.cargar(), conocidos()))
    for grupo, datos in resumen["grupos"].items():
        if datos["casos"] < 5:
            assert not datos["publica"], grupo


def test_la_velocidad_separa_helice_de_reaccion() -> None:
    catalogo = catalogo_.cargar()
    previa = [(k.entrada.zona, k.respuesta) for k in conocidos()]
    for kmh, sube in ((180.0, "largo_alcance_helice"), (360.0, "reaccion")):
        entrada = modelo.Entrada(
            zona="frontera", con_punto=True, d_partes_km=20, entrada_exterior=True,
            rasgos=[{"rasgo": "velocidad", "valor": {"kmh": kmh}, "cita": "x", "fuente": "f",
                     "origen": "oficial"}],
        )  # fmt: skip
        resultado = modelo.calcular(catalogo, entrada, previa)
        assert resultado.ordenados()[0][0] == sube


def test_entre_230_y_300_la_velocidad_no_dice_nada() -> None:
    catalogo = catalogo_.cargar()
    previa = [(k.entrada.zona, k.respuesta) for k in conocidos()]
    sin = modelo.calcular(catalogo, modelo.Entrada(zona="frontera"), previa)
    con = modelo.calcular(
        catalogo,
        modelo.Entrada(zona="frontera", rasgos=[{"rasgo": "velocidad", "valor": {"kmh": 260.0},
                                                 "cita": "x", "fuente": "f", "origen": "oficial"}]),
        previa,
    )  # fmt: skip
    assert con.por_grupo["reaccion"] == pytest.approx(sin.por_grupo["reaccion"], rel=0.05)


def test_sin_base_no_se_publica() -> None:
    catalogo = catalogo_.cargar()
    k = conocidos()
    documento = {"id": "EODI-2026-99999", "tipo": "sobrevuelo", "presencia_dron": "confirmada",
                 "estado": {"actual": "confirmado"}, "lugar": {"pais": "DE"},
                 "zona": {"grupo": "interior"}}  # fmt: skip
    salida = calculo.documento_incidente(
        catalogo, documento, [("prensa", "f", "Drohnen über dem Flughafen gesichtet", "de")],
        None, k, ["largo_alcance_helice", "senuelo"],
    )  # fmt: skip
    assert not salida["con_base"] and "publicado" not in salida


def test_un_posible_dron_no_lleva_clase() -> None:
    catalogo = catalogo_.cargar()
    documento = {"id": "EODI-2026-99998", "tipo": "incursion", "presencia_dron": "no_confirmada",
                 "estado": {"actual": "notificado"}, "lugar": {"pais": "RO"},
                 "zona": {"grupo": "frontera"}}  # fmt: skip
    salida = calculo.documento_incidente(
        catalogo, documento, [], None, conocidos(), ["largo_alcance_helice", "senuelo"]
    )
    assert "publicado" not in salida


# --- Publicación y exportación ------------------------------------------------------------------


def test_lo_publico_esta_en_la_lista_cerrada() -> None:
    for ruta in ("tipo_dron.publicado.compatible[].grupo", "tipo_dron.identificado.cita",
                 "tipo_dron.razones[].datos.cita"):  # fmt: skip
        assert ruta in CAMPOS_PUBLICOS_INCIDENTE
    assert "tipo_dron.probabilidades" not in CAMPOS_PUBLICOS_INCIDENTE
    assert "tipo_dron.rasgos" not in CAMPOS_PUBLICOS_INCIDENTE


def test_una_cita_de_una_fuente_no_publica_no_sale() -> None:
    tipo = {"version": "tipo-dron-1.0.0", "publicado": {"compatible": [], "otras": 0.0},
            "razones": [{"tipo": "rasgo", "clave": "tamano:grande",
                         "datos": {"rasgo": "tamano", "valor": "grande", "cita": "x",
                                   "fuente": "privada"}}]}  # fmt: skip
    incidente = {"fuentes": [{"id": "publica", "publica": True, "fiabilidad": "B"}]}
    bloque = publico.bloque(tipo, incidente)
    assert bloque is not None
    assert "cita" not in bloque["razones"][0]["datos"]


def test_cada_valor_de_la_exportacion_tiene_regla_de_origen() -> None:
    tipo = {"version": "tipo-dron-1.0.0", "version_rasgos": "rasgos-1.0.0",
            "rasgos": [{"rasgo": "forma", "valor": "multirrotor", "cita": "a quadcopter",
                        "fuente": "f1", "origen": "prensa"}],
            "probabilidades": {}, "grupos": {}, "razones": [], "con_base": True,
            "identificado": {"modelo": "Gerbera", "clases": [], "grupo": "senuelo", "cita": "c",
                             "fuente": "f2", "origen": "oficial"}}  # fmt: skip
    mapa = procedencia.procedencia_tipo_dron(tipo)
    assert mapa["tipo_dron.rasgos.0"]["origen"] == "prensa"
    assert mapa["tipo_dron.identificado"]["origen"] == "oficial"
    assert mapa["tipo_dron"]["origen"] == "deducido"


def test_un_campo_sin_regla_rompe_la_exportacion() -> None:
    with pytest.raises(procedencia.SinOrigen):
        procedencia.procedencia_tipo_dron({"version": "tipo-dron-1.0.0", "nuevo": 1})
    with pytest.raises(procedencia.SinOrigen):
        procedencia.procedencia_tipo_dron(
            {"version": "tipo-dron-1.0.0",
             "rasgos": [{"rasgo": "forma", "valor": "x", "fuente": "f", "origen": "rumor"}]}
        )  # fmt: skip


def test_lo_que_deja_de_publicarse_queda_retirado_con_motivo() -> None:
    almacen = Almacen.abrir(":memory:")
    ahora = datetime(2026, 10, 6, 20, tzinfo=UTC)
    antes = {
        "version": "tipo-dron-1.0.0",
        "publicado": {"compatible": [{"grupo": "senuelo", "probabilidad": 0.5}], "otras": 0.5},
    }
    despues = tipo_dron._con_retirada({"version": "tipo-dron-1.0.0"}, antes, ahora)
    assert despues["retirado"]["motivo"]["es"] and despues["retirado"]["motivo"]["en"]
    assert almacen.guardar_tipo_dron("EODI-2026-00001", antes)
    assert almacen.guardar_tipo_dron("EODI-2026-00001", despues)
    historial = almacen._conexion.execute(
        "SELECT COUNT(*) FROM historial WHERE tabla = 'tipos_dron'"
    ).fetchone()[0]
    assert historial == 2


def test_la_exportacion_lleva_el_tipo_de_dron_con_su_origen() -> None:
    from exportacion import semanal
    from tests import base_prueba

    ficheros = {f.nombre: f for f in semanal.generar(base_prueba.base_prueba())}
    lineas = [json.loads(x) for x in ficheros["incidentes.jsonl"].contenido.splitlines()]
    incidente = next(i for i in lineas if i["id"] == "EODI-2025-00001")
    tipo = incidente["tipo_dron"]
    for i in range(len(tipo["rasgos"])):
        assert incidente["procedencia"][f"tipo_dron.rasgos.{i}"]["origen"] == "prensa"
    assert incidente["procedencia"]["tipo_dron.identificado"]["origen"] == "oficial"
    assert incidente["procedencia"]["tipo_dron"]["origen"] == "deducido"
