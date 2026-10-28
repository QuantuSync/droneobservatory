"""El filtro de entrada de las fichas nuevas y su medida a las 24 horas (recogida/entrada.py), con
los casos que lo motivaron: EODI-2026-00689 (el buque hundido frente a Bulgaria, un día después y
con el lugar vago), EODI-2026-00692 (el derribo de Sulina contado nueve días después) y la
autoridad de EODI-2026-00512 (el Consejo de Seguridad búlgaro tomado por moldavo)."""

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste
from proceso import control_fichas as reglas
from recogida import control_fichas, entrada, visitas
from tests import ejemplos
from tests.ejemplos import VOCABULARIO_MODELOS

AHORA = datetime(2026, 10, 27, 21, 17, tzinfo=UTC)
EXPERTO = "proveedor-sonnet-5-5"


def _ficha(
    id_: str, pais: str, inicio: str, precision: str = "dia", *, frase: str = "",
    punto: tuple[float, float] | None = None, nivel: str = "region", tipo: str = "sobrevuelo",
    publicada: str | None = None,
) -> dict[str, Any]:  # fmt: skip
    ficha = copy.deepcopy(ejemplos.incidente_minimo())
    publicacion = publicada or inicio
    fuente = {**ejemplos.fuente(f"{id_}-F1", "C"), "frase_origen": frase or f"Drones {id_}",
              "fecha": ejemplos.instante(publicacion, "aproximada"), "idioma": "en"}  # fmt: skip
    lugar: dict[str, Any] = {"pais": pais, "nivel": nivel, "region": "mar", "suceso": "mar"}
    if punto:
        lugar = {**lugar, "punto": {"lat": punto[0], "lon": punto[1]}, "radio_km": 10}
    ficha.update(
        id=id_, tipo=tipo, lugar=lugar, fuentes=[fuente],
        tiempo={"inicio": ejemplos.instante(inicio, precision)},
        estado={"actual": "notificado", "historial": [
            {"estado": "notificado", "fecha": ejemplos.instante(publicacion, "aproximada"),
             "fuente_id": fuente["id"]}]},
        control={"alta": ejemplos.instante(publicacion), "ultima_actualizacion":
                 ejemplos.instante(publicacion)},
    )  # fmt: skip
    return ficha


# Las fichas de los casos, mínimas.
BUQUE_512 = _ficha("EODI-2026-00512", "BG", "2026-10-12T00:00Z", punto=(43.2, 27.9),
                   nivel="localidad", frase="A ship sank off Krapets overnight")  # fmt: skip
BUQUE_689 = _ficha("EODI-2026-00689", "BG", "2026-10-13T00:00Z", publicada="2026-10-13T15:30Z",
                   frase="Two cargo ships were hit by drones overnight, and one was sunk, "
                   "Bulgarian officials said.")  # fmt: skip
SULINA_582 = _ficha("EODI-2026-00582", "RO", "2026-10-17T00:00Z", punto=(45.16, 29.6),
                    nivel="localidad", frase="Ambele incidente lângă Sulina.")  # fmt: skip
SULINA_692 = _ficha("EODI-2026-00692", "RO", "2026-10-27T19:45Z", "aproximada",
                    frase="Októberben a román F-16-os vadászgépek pilótái két "
                    "új generációs orosz drónt lőttek le a román felségvizek felett")  # fmt: skip


def test_el_conjunto_no_mira_la_distancia_ni_la_noche_partida() -> None:
    # 00689 (13/10, «coast of Bulgaria») y 00512 (12/10, Krapets).
    lejos = _ficha(
        "EODI-2026-00500", "FR", "2026-10-12T00:00Z", punto=(48.8, 2.3), nivel="localidad"
    )
    rumana = _ficha("EODI-2026-00513", "RO", "2026-10-12T22:30Z", "minuto", punto=(44.17, 28.6),
                    nivel="localidad")  # fmt: skip
    ids = [d["id"] for d in entrada.conjunto(BUQUE_689, [BUQUE_512, lejos, rumana, BUQUE_689])]
    # El mar entre dos países: también Rumanía; Francia, no; la propia, no.
    assert set(ids) == {"EODI-2026-00512", "EODI-2026-00513"}


def test_lugar_de_pais_mira_los_vecinos_y_el_preciso_solo_su_pais() -> None:
    pais = _ficha("EODI-2026-00700", "DE", "2026-10-20T00:00Z", nivel="pais")
    polaca = _ficha("EODI-2026-00701", "PL", "2026-10-19T00:00Z", punto=(52.2, 21.0),
                    nivel="localidad")  # fmt: skip
    assert "PL" in entrada.paises(pais)
    assert [d["id"] for d in entrada.conjunto(pais, [polaca])] == ["EODI-2026-00701"]
    preciso = _ficha("EODI-2026-00702", "DE", "2026-10-20T00:00Z", punto=(52.5, 13.4),
                     nivel="localidad")  # fmt: skip
    preciso["zona"] = {"grupo": "interior"}
    assert entrada.paises(preciso) == frozenset({"DE"})
    assert entrada.conjunto(preciso, [polaca]) == []


def test_una_retrospectiva_a_nueve_dias_tiene_la_ficha_del_suceso() -> None:
    # 00692 lleva la fecha de publicación (27/10); el derribo fue el 17/10.
    assert not reglas.candidatos(SULINA_692, SULINA_582)
    viejo = _ficha("EODI-2026-00300", "RO", "2026-09-01T00:00Z", punto=(45.16, 29.6),
                   nivel="localidad")  # fmt: skip
    ids = [d["id"] for d in entrada.conjunto(SULINA_692, [SULINA_582, viejo])]
    assert ids == ["EODI-2026-00582"]


def test_con_mas_de_cuarenta_primero_el_mismo_tipo_y_lo_mas_cercano() -> None:
    otras = [
        _ficha(f"EODI-2026-01{n:03d}", "RO", f"2026-10-{1 + n % 27:02d}T00:00Z",
               tipo="incursion" if n % 2 else "sobrevuelo")
        for n in range(60)
    ]  # fmt: skip
    elegidas = entrada.conjunto(SULINA_692, otras)
    assert len(elegidas) == entrada.MAX_CONJUNTO == 40
    assert all(d["tipo"] == "sobrevuelo" for d in elegidas[:30])


# --- La respuesta -------------------------------------------------------------------------


def _respuesta(**cambios: Any) -> dict[str, Any]:
    base = {
        "mismo_suceso": "ninguna", "motivo_mismo": "", "otro_dia": False, "fecha_suceso": "",
        "fecha_fuente": 1, "fecha_frase": "no", "lugar_fuente": 1, "lugar_frase": "no",
        "autoridades": [], "duda": False, "dudosas": [], "motivo_es": "x", "motivo_en": "x",
    }  # fmt: skip
    return {**base, **cambios}


class Cliente:
    """El experto falso: da las respuestas en orden y apunta lo que se le pide."""

    modelo = EXPERTO

    def __init__(self, respuestas: list[dict[str, Any]]) -> None:
        self.respuestas = list(respuestas)
        self.pedidas: list[str] = []

    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]:
        self.pedidas.append(str(cuerpo["messages"][0]["content"]))
        salida = self.respuestas.pop(0)
        return {
            "stop_reason": "end_turn", "model": EXPERTO,
            "content": [{"type": "text", "text": json.dumps(salida)}],
            "usage": {"input_tokens": 4000, "output_tokens": 300},
        }  # fmt: skip


class Servicio:
    def __init__(self, cliente: Cliente) -> None:
        self.cliente = cliente

    def experto(self) -> Cliente:
        return self.cliente


def _contexto(almacen: Almacen, cliente: Cliente | None) -> control_fichas.Contexto:
    resultado = control_fichas.Resultado()
    fabrica = (lambda: Servicio(cliente)) if cliente is not None else None
    llamador = control_fichas.Llamador(
        almacen,
        fabrica,  # type: ignore[arg-type]
        coste.Modo.CONTROL,
        AHORA,
        None,
        resultado,
    )
    return control_fichas.Contexto(almacen, AHORA, VOCABULARIO_MODELOS, llamador, resultado,
                                   None, None, almacen.controles())  # fmt: skip


@pytest.fixture(autouse=True)
def _sin_descargas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})


def _base(*fichas: dict[str, Any]) -> Almacen:
    almacen = Almacen.abrir()
    for ficha in fichas:
        almacen.guardar_incidente(ficha, AHORA, VOCABULARIO_MODELOS)
    return almacen


def test_el_mismo_suceso_se_une_antes_de_publicarse() -> None:
    almacen = _base(BUQUE_512, BUQUE_689)
    frase = "Two cargo ships were hit by drones overnight"
    cliente = Cliente([_respuesta(mismo_suceso="EODI-2026-00512", fecha_frase=frase,
                                  lugar_frase=frase)])  # fmt: skip
    ctx = _contexto(almacen, cliente)
    assert entrada.filtrar(ctx, {"EODI-2026-00512"}) == 1
    decision = ctx.nuevas[entrada.clave("EODI-2026-00689")]
    assert decision["decision"] == entrada.UNIDA and decision["conserva"] == "EODI-2026-00512"
    unida = almacen.incidente("EODI-2026-00689")
    assert unida is not None and unida["fusionado_en"] == "EODI-2026-00512"
    # La lista llevaba 00512 aunque la noche cae en dos días y el lugar es vago.
    assert "EODI-2026-00512 |" in cliente.pedidas[0]


def test_otro_dia_toma_la_fecha_de_la_frase_y_vuelve_a_pasar() -> None:
    almacen = _base(SULINA_582, SULINA_692)
    frase = "Októberben a román F-16-os vadászgépek pilótái két új generációs orosz drónt lőttek le"
    cliente = Cliente([
        _respuesta(otro_dia=True, fecha_suceso="2026-10-17", fecha_frase=frase, lugar_frase=frase),
        _respuesta(mismo_suceso="EODI-2026-00582", fecha_frase=frase, lugar_frase=frase),
    ])  # fmt: skip
    ctx = _contexto(almacen, cliente)
    entrada.filtrar(ctx, {"EODI-2026-00582"})
    decision = ctx.nuevas[entrada.clave("EODI-2026-00692")]
    assert decision["decision"] == entrada.UNIDA and decision["cambios"] == [
        f"día 2026-10-17: «{frase}»"
    ]
    assert len(cliente.pedidas) == 2
    unida = almacen.incidente("EODI-2026-00692")
    assert unida is not None and unida["fusionado_en"] == "EODI-2026-00582"


def test_sin_frase_de_la_fecha_no_se_publica_y_el_lugar_queda_en_el_pais() -> None:
    almacen = _base(SULINA_582, SULINA_692)
    # Las dos respuestas sin frase: la segunda, con las fuentes de la candidata.
    cliente = Cliente([_respuesta(), _respuesta()])
    ctx = _contexto(almacen, cliente)
    entrada.filtrar(ctx, {"EODI-2026-00582"})
    decision = ctx.nuevas[entrada.clave("EODI-2026-00692")]
    assert decision["decision"] == entrada.RETENER and decision.get("repetida") is True
    assert "Fuentes de EODI-2026-00582:" in cliente.pedidas[1]
    queda = almacen.incidente("EODI-2026-00692")
    assert queda is not None and queda["lugar"] == {"pais": "RO", "nivel": "pais"}
    assert entrada.motivo_retencion(decision, queda) == (
        "filtro de entrada: ninguna frase da la fecha del suceso"
    )


def _con_declaracion(ficha: dict[str, Any], autoridad: str, frase: str) -> dict[str, Any]:
    nueva = copy.deepcopy(ficha)
    declaracion = {**ejemplos.fuente(f"{ficha['id']}-F1-declaracion-1", "B", es_autoridad=True),
                   "medio": f"{autoridad} (declaración oficial citada en mediafax.ro)",
                   "frase_origen": frase, "idioma": "ro",
                   "enlace": ficha["fuentes"][0]["enlace"]}  # fmt: skip
    nueva["fuentes"].append(declaracion)
    nueva["estado"] = {"actual": "confirmado", "historial": [
        *nueva["estado"]["historial"],
        {"estado": "confirmado", "fecha": nueva["estado"]["historial"][0]["fecha"],
         "fuente_id": declaracion["id"]}]}  # fmt: skip
    return nueva


def test_la_autoridad_de_otro_pais_sin_frase_que_lo_diga_no_es_oficial() -> None:
    consejo = "Consiliul de Securitate de pe lângă Consiliul de Miniștri"
    frase = f"{consejo} a decis convocarea ambasadorului"
    nueva = _con_declaracion(BUQUE_689, consejo, frase)
    almacen = _base(nueva)
    dia = "Two cargo ships were hit by drones overnight"
    autoridad = {"nombre": consejo, "pais": "MD", "fuente": 1, "frase": frase}
    cliente = Cliente([_respuesta(fecha_frase=dia, lugar_frase=dia, autoridades=[autoridad])] * 2)
    ctx = _contexto(almacen, cliente)
    entrada.filtrar(ctx, set())
    decision = ctx.nuevas[entrada.clave("EODI-2026-00689")]
    assert decision["decision"] == entrada.PUBLICAR
    assert consejo in decision["autoridades_fuera"]
    queda = almacen.incidente("EODI-2026-00689")
    assert queda is not None and queda["estado"]["actual"] == "notificado"
    oficial = next(f for f in queda["fuentes"] if "declaracion" in f["id"])
    assert oficial["publica"] is False and oficial["es_autoridad"] is False
    # Con el país de la ficha y su frase, sí es oficial.
    bien = {**autoridad, "pais": "BG"}
    otra = entrada.decidir(_respuesta(fecha_frase=dia, lugar_frase=dia, autoridades=[bien]),
                           [("a", f"{dia} {frase}")], [], nueva)  # fmt: skip
    assert otra["autoridades_fuera"] == {} and otra["autoridades"] == {consejo: "BG"}


def test_sin_experto_espera_como_caso_critico_y_no_sale_nunca_por_tiempo() -> None:
    almacen = _base(SULINA_692)
    ctx = _contexto(almacen, None)
    entrada.filtrar(ctx, set())
    clave = entrada.clave("EODI-2026-00692")
    decision = ctx.nuevas[clave]
    assert decision["decision"] == entrada.ESPERA and decision["critico"] is True
    almacen.guardar_controles(ctx.nuevas, "2026-10-27T21:17:00Z")
    assert clave in [c["clave"] for c in control_fichas.criticos_esperando(almacen)]
    ficha = almacen.incidente("EODI-2026-00692")
    assert ficha is not None
    assert entrada.motivo_retencion(decision, ficha) is not None
    assert entrada.motivo_retencion(None, ficha) == "sin pasar por el filtro de entrada"


def test_el_cupo_de_entrada_es_aparte_del_experto() -> None:
    almacen = _base(SULINA_692)
    almacen.registrar_llamada({
        "fecha": "2026-10-27T10:00:00Z", "modo": "entrada", "candidato": "x", "lote": False,
        "entrada": 0, "salida": 0, "escritura_cache": 0, "lectura_cache": 0,
        "coste": coste.LIMITE_ENTRADA_DIARIO_USD, "modelo": EXPERTO, "escalada": True,
    })  # fmt: skip
    # No cuenta contra el tope del experto, sí contra su propio cupo: la ficha espera.
    assert almacen.gastado_modelo(EXPERTO, "2026-10-27") == 0.0
    assert almacen.gastado_experto_en("entrada", "2026-10-27") == coste.LIMITE_ENTRADA_DIARIO_USD
    cliente = Cliente([_respuesta()])
    ctx = _contexto(almacen, cliente)
    entrada.filtrar(ctx, set())
    decision = ctx.nuevas[entrada.clave("EODI-2026-00692")]
    assert decision["decision"] == entrada.ESPERA and decision["motivo"].startswith("cupo")
    assert cliente.pedidas == []
    assert coste.limite(coste.Modo.ENTRADA) == 3.00
    assert coste.TOPE_MENSUAL_USD == 150.00
    assert coste.REPARTO_MENSUAL_USD[coste.Modo.ENTRADA] == 90.00


def test_la_medida_a_las_24_horas_une_el_duplicado_y_lo_cuenta() -> None:
    almacen = _base(BUQUE_512, BUQUE_689)
    frase = "Two cargo ships were hit by drones overnight"
    ctx = _contexto(almacen, Cliente([_respuesta(fecha_frase=frase, lugar_frase=frase)]))
    entrada.filtrar(ctx, {"EODI-2026-00512"})
    almacen.guardar_controles(ctx.nuevas, "2026-10-27T21:17:00Z")
    publicada = {"EODI-2026-00689": "2026-10-27T21:17:00Z"}
    almacen.guardar_cursor(control_fichas.CURSOR, {"vistos": publicada, "retenidos": {}})
    # Antes de 24 horas no se mide.
    temprano = _contexto(almacen, Cliente([]))
    assert entrada.medir(temprano, publicada) == 0
    error = {"dato": "duplicado", "correcto": "", "duplicado_de": "EODI-2026-00512", "fuente": 0,
             "frase": ""}  # fmt: skip
    medida = {"errores": [error], "motivo_es": "es 00512", "motivo_en": "it is 00512"}
    ctx = _contexto(almacen, Cliente([medida]))
    ctx.ahora = AHORA + timedelta(hours=25)
    assert entrada.medir(ctx, publicada) == 1
    unida = almacen.incidente("EODI-2026-00689")
    assert unida is not None and unida["fusionado_en"] == "EODI-2026-00512"
    almacen.guardar_controles(ctx.nuevas, "2026-10-28T22:17:00Z")
    estado = entrada.estado_por_dia(almacen, ctx.ahora, {})
    assert estado["2026-10-27"] == {
        "nuevas": ["EODI-2026-00689"], "medidas": ["EODI-2026-00689"],
        "con_error": ["EODI-2026-00689"],
    }  # fmt: skip


def test_la_linea_del_resumen_diario() -> None:
    dia = {"nuevas": ["A", "B", "C"], "medidas": ["A", "B"], "con_error": ["B"]}
    assert visitas.lineas_entrada(dia) == [
        "  Fichas nuevas de ayer: 3; con error a las 24 h: 1 (B); medidas 2 de 3"
    ]
    assert visitas.lineas_entrada(None) == ["  Fichas nuevas de ayer: 0; con error a las 24 h: 0"]
