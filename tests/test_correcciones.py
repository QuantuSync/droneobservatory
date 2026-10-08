"""Registro público de correcciones (exportacion/correcciones.py): qué entra, qué no y con qué
motivo en los dos idiomas."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from exportacion import correcciones
from tests import ejemplos

AHORA = datetime(2026, 10, 8, 20, 30, tzinfo=UTC)
RAIZ = Path(__file__).resolve().parent.parent
CITA = "cita revisada a mano (configuracion/incidentes_revisados.json, citas)"
DUPLICADO = "duplicado de EODI-2026-00011, el mismo cruce a Rumanía contado por su fuente: x"


class BaseFalsa:
    """Lo que el registro lee de la base, escrito a mano."""

    def __init__(
        self,
        incidentes: list[dict[str, Any]],
        activas: dict[str, list[str]],
        motivos: list[dict[str, Any]] | None = None,
        fusiones: list[dict[str, Any]] | None = None,
    ) -> None:
        self._incidentes = incidentes
        self._activas = activas
        self._motivos = motivos or []
        self._fusiones = fusiones or []

    def incidentes(self) -> list[dict[str, Any]]:
        return self._incidentes

    def versiones_activas(self) -> dict[str, list[str]]:
        return self._activas

    def motivos_anotados(self, tabla: str) -> list[dict[str, Any]]:
        assert tabla == correcciones.TABLA_MOTIVOS
        return self._motivos

    def fusiones(self) -> list[dict[str, Any]]:
        return self._fusiones


def _incidente(id_: str, **extra: Any) -> dict[str, Any]:
    documento = ejemplos.incidente_minimo()
    documento["id"] = id_
    documento["titulo"] = {"es": f"Titular de {id_}", "en": f"Headline of {id_}"}
    documento.update(extra)
    return documento


def _registro(base: BaseFalsa) -> list[dict[str, Any]]:
    resultado: list[dict[str, Any]] = correcciones.construir(base, AHORA)["correcciones"]  # type: ignore[arg-type]
    return resultado


def test_la_recogida_de_un_momento_empieza_en_el_minuto_17() -> None:
    assert correcciones.recogida_de(datetime(2026, 10, 8, 15, 29, tzinfo=UTC)).hour == 15
    assert correcciones.recogida_de(datetime(2026, 10, 8, 15, 5, tzinfo=UTC)).hour == 14
    # Activo en la recogida de las 14:17 y cambiado en la de las 15:17: ya se había publicado.
    assert correcciones.publicado_antes(
        ["2026-10-08T14:30:00Z"], datetime(2026, 10, 8, 15, 29, tzinfo=UTC)
    )
    # Dado de alta y cambiado en la misma recogida: nunca se publicó así.
    assert not correcciones.publicado_antes(
        ["2026-10-08T15:20:00Z"], datetime(2026, 10, 8, 15, 40, tzinfo=UTC)
    )


def test_entra_un_titular_revisado_de_un_incidente_ya_publicado() -> None:
    revisados = json.loads(
        (RAIZ / "configuracion" / "incidentes_revisados.json").read_text("utf-8")
    )
    titular = revisados["titulares"][0]
    id_ = titular["incidente"]
    motivo = {
        "entidad_id": id_, "fecha": "2026-10-05T16:31:30Z",
        "anterior": {"titulo": {"es": "Antes", "en": "Before"}},
        "nuevo": {"titulo": titular["titulo"], "motivo": titular["motivo"]["es"]},
    }  # fmt: skip
    base = BaseFalsa([_incidente(id_)], {id_: ["2026-10-04T10:20:00Z"]}, [motivo])
    [entrada] = _registro(base)
    assert entrada["incidente"] == id_ and entrada["enlace"] == id_
    assert entrada["cambios"] == [
        {"campo": "titulo", "antes": {"es": "Antes", "en": "Before"}, "despues": titular["titulo"]}
    ]
    assert entrada["motivo"] == titular["motivo"]
    assert entrada["revision"] == "a_mano"
    assert entrada["fecha"] == "2026-10-05T16:31Z"


def test_no_entran_los_datos_nuevos_ni_lo_que_no_se_ve_ni_lo_nunca_publicado() -> None:
    id_ = "EODI-2026-00001"
    filas = [
        # Una autoridad atribuye el suceso: dato nuevo.
        {"entidad_id": id_, "fecha": "2026-10-05T12:28:44Z",
         "anterior": {"estado": {"actual": "confirmado"}},
         "nuevo": {"estado": {"actual": "atribuido"},
                   "motivo": "declaración de la autoridad leída en su página oficial (x)"}},
        # Solo cambian las fuentes (una cita guardada): no se ve.
        {"entidad_id": id_, "fecha": "2026-10-05T16:31:29Z", "anterior": {"fuentes": []},
         "nuevo": {"fuentes": [1], "motivo": CITA}},
    ]  # fmt: skip
    base = BaseFalsa([_incidente(id_)], {id_: ["2026-10-01T10:20:00Z"]}, filas)
    assert _registro(base) == []
    # El mismo cambio de titular, en la misma recogida en que se dio de alta: no entra.
    fila = {
        "entidad_id": id_, "fecha": "2026-10-05T12:40:00Z",
        "anterior": {"titulo": {"es": "a", "en": "a"}},
        "nuevo": {"titulo": {"es": "b", "en": "b"},
                  "motivo": "titular coherente con la presencia del dron (proceso/titulares.py)"},
    }  # fmt: skip
    assert _registro(BaseFalsa([_incidente(id_)], {id_: ["2026-10-05T12:20:00Z"]}, [fila])) == []
    assert (
        len(_registro(BaseFalsa([_incidente(id_)], {id_: ["2026-10-05T11:20:00Z"]}, [fila]))) == 1
    )


def test_retirada_union_revisada_y_motivo_de_regla_en_los_dos_idiomas() -> None:
    retirado = _incidente(
        "EODI-2026-00010",
        retirado={"fecha": ejemplos.instante("2026-10-04T12:30Z"),
                  "motivo": DUPLICADO},
    )  # fmt: skip
    unido = _incidente("EODI-2025-00442", fusionado_en="EODI-2025-00295")
    destino = _incidente("EODI-2025-00295")
    fusion = {
        "fecha": "2026-10-08T15:29Z", "absorbido": "EODI-2025-00442", "destino": "EODI-2025-00295",
        "motivo": "revisión: un texto antiguo", "fuentes": [], "revertida": False,
    }  # fmt: skip
    activas = {
        "EODI-2026-00010": ["2026-10-03T10:20:00Z"],
        "EODI-2025-00442": ["2026-10-08T13:20:00Z"],
    }
    entradas = _registro(BaseFalsa([retirado, unido, destino], activas, [], [fusion]))
    assert [e["incidente"] for e in entradas] == ["EODI-2025-00442", "EODI-2026-00010"]
    union, retirada = entradas
    assert union["cambios"] == [{"campo": "union", "destino": "EODI-2025-00295"}]
    assert union["enlace"] == "EODI-2025-00295" and union["revision"] == "a_mano"
    # El motivo es el del grupo de la configuración, con su traducción.
    assert union["motivo"]["en"].startswith("the same event: the drones that entered Poland")
    assert retirada["cambios"] == [{"campo": "retirada"}] and retirada["enlace"] is None
    assert retirada["motivo"]["en"].startswith(
        "Duplicate of EODI-2026-00011: the same crossing into Romania"
    )
    # Revertida, la unión ya no está.
    fusion["revertida"] = True
    assert [
        e["incidente"]
        for e in _registro(BaseFalsa([retirado, unido, destino], activas, [], [fusion]))
    ] == ["EODI-2026-00010"]


def test_la_atribucion_corregida_no_publica_sus_valores() -> None:
    id_ = "EODI-2026-00015"
    fila = {
        "entidad_id": id_, "fecha": "2026-10-04T13:21:20Z",
        "anterior": {"atribucion": {"autor": "Nombre Inventado"},
                     "estado": {"actual": "atribuido"}},
        "nuevo": {"estado": {"actual": "confirmado"}, "motivo": "otra cosa"},
    }  # fmt: skip
    [entrada] = _registro(BaseFalsa([_incidente(id_)], {id_: ["2026-10-01T10:20:00Z"]}, [fila]))
    assert {"campo": "atribucion", "retirada": True} in entrada["cambios"]
    assert "Nombre Inventado" not in json.dumps(entrada, ensure_ascii=False)


def test_a_raiz_de_un_aviso(monkeypatch: Any) -> None:
    conf = dict(correcciones.configuracion())
    conf["a_raiz_de_un_aviso"] = [{"incidente": "EODI-2026-00010", "dia": "2026-10-04"}]
    monkeypatch.setattr(correcciones, "configuracion", lambda: conf)
    retirado = _incidente(
        "EODI-2026-00010",
        retirado={"fecha": ejemplos.instante("2026-10-04T12:30Z"),
                  "motivo": "ficha no publicable con las reglas actuales"},
    )  # fmt: skip
    [entrada] = _registro(BaseFalsa([retirado], {"EODI-2026-00010": ["2026-10-03T10:20:00Z"]}))
    assert entrada["a_raiz_de_un_aviso"] is True


def test_cada_regla_tiene_sus_dos_idiomas_y_casa_con_su_motivo() -> None:
    conf = correcciones.configuracion()
    for regla in conf["motivos"]:
        if regla.get("corrige", True):
            assert regla["es"] and regla["en"], regla["patron"]
    motivos = correcciones.Motivos()
    resultado = motivos.de("la fecha del suceso no da el día en su frase")
    assert resultado is not None and resultado[0]["en"].startswith("Withdrawn")
    validacion = motivos.de("pais: sin país del suceso")
    assert validacion is not None and "validation rules" in validacion[0]["en"]
    assert motivos.sin_traducir == set()


def test_lee_una_base_de_verdad() -> None:
    almacen = Almacen.abrir()
    almacen.guardar_incidente(_incidente("EODI-2026-00001"), AHORA, frozenset())
    registro = correcciones.construir(almacen, AHORA)
    assert registro["version"] == correcciones.VERSION and registro["correcciones"] == []
    assert registro["actualizado"] is None
    assert almacen.versiones_activas() == {"EODI-2026-00001": [registro_fecha(almacen)]}


def registro_fecha(almacen: Almacen) -> str:
    return str(almacen.historial("EODI-2026-00001")[0]["fecha"])


def test_la_union_de_una_nota_posterior_tiene_su_motivo() -> None:
    from proceso import incidentes

    motivo = correcciones.Motivos().de(incidentes.MOTIVO_NOTA_POSTERIOR)
    assert motivo is not None and motivo[0]["en"].startswith("It is a later report")
