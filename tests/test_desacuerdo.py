"""El desacuerdo entre el filtro de entrada y el control, y lo que nunca es el mismo suceso. Con
las fichas reales de la noche del 10 al 11 de noviembre de 2026 (tests/fixtures/
alertas_2026-11-11.json): EODI-2026-00778 quedó retenida sin salida porque el filtro decía «el
mismo que EODI-2026-00777» y el experto los había dado por distintos en el control; y la ficha de
Lituania, EODI-2026-00779, se unió a la 00778, con el lugar en Letonia."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from almacen.base import Almacen
from modelo import coste
from recogida import control_fichas, entrada
from tests.ejemplos import VOCABULARIO_MODELOS
from tests.test_entrada import Cliente, Servicio, _ficha, _respuesta

AHORA = datetime(2026, 11, 11, 8, 17, tzinfo=UTC)

CASO = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "alertas_2026-11-11.json").read_text(
        encoding="utf-8"
    )
)
F777, F778, F779 = (CASO[f"EODI-2026-0077{n}"] for n in (7, 8, 9))
PAR = "par:EODI-2026-00777|EODI-2026-00778"
FRASE_778 = F778["fuentes"][0]["frase_origen"]
NKVC = "National Crisis Management Centre"


@pytest.fixture(autouse=True)
def _sin_descargas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(control_fichas, "descargar", lambda enlaces, plazo: {})


def _contexto(almacen: Almacen, cliente: Cliente) -> control_fichas.Contexto:
    resultado = control_fichas.Resultado()
    llamador = control_fichas.Llamador(
        almacen,
        lambda: Servicio(cliente),  # type: ignore[arg-type,return-value]
        coste.Modo.CONTROL,
        AHORA,
        None,
        resultado,
    )
    return control_fichas.Contexto(almacen, AHORA, VOCABULARIO_MODELOS, llamador, resultado,
                                   None, None, almacen.controles())  # fmt: skip


def _base(*fichas: dict[str, Any]) -> Almacen:
    almacen = Almacen.abrir()
    for ficha in fichas:
        almacen.guardar_incidente(copy.deepcopy(ficha), AHORA, VOCABULARIO_MODELOS)
    return almacen


def test_el_caso_real_es_un_desacuerdo_sin_salida() -> None:
    """Lo que había en la base: el experto dio el par por distinto y el filtro, tres veces,
    «el mismo que 00777»; con la huella sin cambiar, no volvía a pasar nunca."""
    par = CASO["control"][PAR]
    assert par["decision"] == "distinto" and par["escalado"] and not par.get("plazo")
    primera = CASO["entrada_00778"][0]
    assert (primera["decision"], primera["mismo"]) == (entrada.RETENER, "EODI-2026-00777")
    assert entrada.SIN_SALIDA in primera["motivo"]
    assert entrada.vigente(primera, F778)
    # Ahora sí vuelve a pasar: esa retención ya no es una decisión que se quede.
    assert entrada.pendiente(primera, F778, AHORA)


def test_el_filtro_no_compara_con_la_ficha_que_el_experto_dio_por_distinta() -> None:
    almacen = _base(F777, F778)
    almacen.guardar_controles({PAR: CASO["control"][PAR]}, "2026-11-11T02:17:03Z")
    activos = [F777, F778]
    assert [d["id"] for d in entrada.conjunto(F778, activos)] == ["EODI-2026-00777"]
    from proceso import incidentes

    distintos = incidentes.distintos_del_experto(almacen)
    assert entrada.conjunto(F778, activos, distintos) == []
    cliente = Cliente([_respuesta(fecha_frase=FRASE_778, lugar_frase=FRASE_778)])
    ctx = _contexto(almacen, cliente)
    assert entrada.filtrar(ctx, {"EODI-2026-00777"}) == 1
    decision = ctx.nuevas[entrada.clave("EODI-2026-00778")]
    # Sale sola: ni retenida ni unida.
    assert decision["decision"] == entrada.PUBLICAR
    assert "EODI-2026-00777 |" not in cliente.pedidas[0]
    sigue = almacen.incidente("EODI-2026-00778")
    assert sigue is not None and "fusionado_en" not in sigue
    assert entrada.motivo_retencion(decision, sigue) is None


def test_sin_la_decision_del_experto_el_filtro_sigue_uniendo() -> None:
    # Con otro número: EODI-2026-00778 tiene una revisión a mano (su retirada) y el cerrojo no
    # deja unir una ficha revisada.
    resumen = {**copy.deepcopy(F778), "id": "EODI-2026-00998"}
    almacen = _base(F777, resumen)
    cliente = Cliente(
        [_respuesta(mismo_suceso="EODI-2026-00777", fecha_frase=FRASE_778, lugar_frase=FRASE_778)]
    )
    ctx = _contexto(almacen, cliente)
    entrada.filtrar(ctx, {"EODI-2026-00777"})
    decision = ctx.nuevas[entrada.clave("EODI-2026-00998")]
    assert decision["decision"] == entrada.UNIDA and decision["conserva"] == "EODI-2026-00777"


def test_la_ficha_de_lituania_no_se_une_a_la_de_letonia() -> None:
    """EODI-2026-00779 (LT, el aviso del Centro Nacional de Gestión de Crisis) y EODI-2026-00778
    (LV): países distintos y una autoridad del suyo. El experto dijo «el mismo»; no se unen."""
    assert (F779["lugar"]["pais"], F778["lugar"]["pais"]) == ("LT", "LV")
    regla = entrada.nunca_el_mismo(F779, F778, {NKVC: "LT"}, {})
    assert regla is not None and "LT y LV" in regla
    # También del otro lado, y con lo que la tabla sabe de la autoridad letona de la 00777.
    assert entrada.nunca_el_mismo(F778, F779, {}, {NKVC: "LT"}) is not None
    assert entrada.paises_de_autoridades(F777, {}) == {"LV"}
    assert entrada.nunca_el_mismo(F779, F777, {}, {}) is not None

    almacen = _base(F778, F779)
    declaracion = next(f for f in F779["fuentes"] if "-declaracion-" in f["id"])
    frase = F779["fuentes"][0]["frase_origen"]
    autoridad = {"nombre": NKVC, "pais": "LT", "fuente": 1, "frase": declaracion["frase_origen"]}
    respuesta = _respuesta(mismo_suceso="EODI-2026-00778", fecha_frase=frase, lugar_frase=frase,
                           autoridades=[autoridad])  # fmt: skip
    cliente = Cliente([respuesta, respuesta])
    ctx = _contexto(almacen, cliente)
    entrada.filtrar(ctx, {"EODI-2026-00778"})
    decision = ctx.nuevas[entrada.clave("EODI-2026-00779")]
    assert decision["mismo_descartado"]["id"] == "EODI-2026-00778"
    assert "mismo" not in decision and decision["decision"] != entrada.UNIDA
    lituana = almacen.incidente("EODI-2026-00779")
    assert lituana is not None and "fusionado_en" not in lituana


def test_sin_autoridad_de_ninguno_de_los_dos_paises_decide_el_experto() -> None:
    """Un buque en el mar entre Bulgaria y Rumanía: el país de la ficha es dudoso y nadie de
    ninguno de los dos habla. La regla no dice nada."""
    bulgara = _ficha("EODI-2026-00689", "BG", "2026-10-13T00:00Z")
    rumana = _ficha("EODI-2026-00513", "RO", "2026-10-12T22:30Z", "minuto")
    assert entrada.nunca_el_mismo(bulgara, rumana, {}, {}) is None
    # Una autoridad de un tercer país (la OTAN) tampoco la activa.
    assert entrada.nunca_el_mismo(bulgara, rumana, {"NATO": "NATO"}, {}) is None
    assert entrada.nunca_el_mismo(bulgara, rumana, {"Ministry of Defence": "BG"}, {}) is not None


def _alerta(id_: str, nombre: str, frase: str) -> dict[str, Any]:
    """Una ficha nueva salida de una nota de mil.lv que entró como artículo."""
    ficha = copy.deepcopy(F777)
    articulo = {**ficha["fuentes"][0], "id": f"gdelt-{id_}", "es_autoridad": False,
                "enlace": f"https://www.mil.lv/lv/zinas/{nombre}", "frase_origen": frase,
                "medio": "Nacionālie bruņotie spēki"}  # fmt: skip
    return {**ficha, "id": id_, "fuentes": [articulo]}


def test_dos_alertas_letonas_de_otra_zona_y_otra_hora_no_son_el_mismo_suceso() -> None:
    smiltene = _alerta(
        "EODI-2026-00790",
        "papildinats-plkst-0318-gaisa-telpas-apdraudejums-izsludinats-smiltenes-un-gulbenes-novados",
        "Nacionālie bruņotie spēki informē, ka 11. novembrī no plkst. 03:18 Latvijas gaisa telpā "
        "Smiltenes un Gulbenes novados ir izsludināts apdraudējums.",
    )
    regla = entrada.nunca_el_mismo(smiltene, F777, {}, {})
    assert regla is not None and "zonas distintas y a horas distintas" in regla
    decision = entrada.sin_el_mismo_imposible(
        {"mismo": "EODI-2026-00777", "motivo_mismo": "x", "autoridades": {}}, smiltene, F777, {}
    )
    assert "mismo" not in decision and decision["mismo_descartado"]["id"] == "EODI-2026-00777"
    # La misma zona a otra hora (la alerta de Krāslava que sigue) sí puede ser el mismo.
    kraslava = _alerta(
        "EODI-2026-00791",
        "apdraudejums-kraslavas-novada",
        "no plkst. 02.40 Latvijas gaisa telpā Krāslavas novadā ir izsludināts apdraudējums.",
    )
    assert entrada.nunca_el_mismo(kraslava, F777, {}, {}) is None
    igual = {"mismo": "EODI-2026-00777", "autoridades": {}}
    assert entrada.sin_el_mismo_imposible(igual, kraslava, F777, {}) is igual
