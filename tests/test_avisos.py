"""Avisos públicos con ntfy (recogida/avisos.py, docs/avisos.md): qué se avisa, cómo se ve, que
cada incidente se avisa una sola vez y que la primera pasada no envía nada."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from recogida import avisos

AHORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
CONFIG = avisos.configuracion()


def fuente(medio: str = "Diario", fiabilidad: str = "C", autoridad: bool = False) -> dict[str, Any]:
    return {
        "id": f"f-{medio}",
        "medio": medio,
        "fiabilidad": fiabilidad,
        "es_autoridad": autoridad,
        "enlace": "https://ejemplo.org/noticia",
        "fecha": {"valor": "2026-10-10T08:30Z", "precision": "minuto"},
    }


def incidente(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "EODI-2026-00500",
        "tipo": "incursion",
        "estado": {"actual": "confirmado", "historial": []},
        "titulo": {
            "es": "Dron militar entra en el espacio aéreo",
            "en": "Military drone enters the airspace",
        },
        "tiempo": {"inicio": {"valor": "2026-10-10T08:04Z", "precision": "minuto"}},
        "lugar": {"pais": "SK", "localidad": "Michalovce"},
        "consecuencias": {"cierre": {"valor": "desconocido"}},
        "pruebas": {"dron_estatal": True, "entrada_exterior": True, "evidencia": []},
        "fuentes": [fuente("Ministerstvo obrany SR", "A", True)],
    }
    base.update(cambios)
    return base


# --- Qué se avisa ----------------------------------------------------------------------------
def test_incursion_desde_la_guerra_en_pais_otan_prioridad_alta() -> None:
    aviso = avisos.clasificar(incidente(), CONFIG, AHORA)
    assert aviso is not None
    assert (aviso.clase, aviso.estado, aviso.prioridad) == ("incursion", "confirmado", 4)


def test_moldavia_tambien_prioridad_alta_y_un_pais_fuera_de_la_otan_no() -> None:
    moldavia = avisos.clasificar(incidente(lugar={"pais": "MD"}), CONFIG, AHORA)
    austria = avisos.clasificar(incidente(lugar={"pais": "AT"}), CONFIG, AHORA)
    assert moldavia is not None and moldavia.prioridad == 4
    assert austria is not None and austria.prioridad == 3


def test_notificado_solo_con_fuente_oficial() -> None:
    prensa = incidente(estado={"actual": "notificado"}, fuentes=[fuente("Diario")])
    oficial = incidente(
        estado={"actual": "notificado"}, fuentes=[fuente("Diario"), fuente("Aeropuerto", "A", True)]
    )
    assert avisos.clasificar(prensa, CONFIG, AHORA) is None
    aviso = avisos.clasificar(oficial, CONFIG, AHORA)
    assert aviso is not None and aviso.estado == "notificado"


def test_desmentido_retirado_fuera_de_europa_o_antiguo_no_avisan() -> None:
    assert avisos.clasificar(incidente(estado={"actual": "desmentido"}), CONFIG, AHORA) is None
    assert (
        avisos.clasificar(incidente(retirado={"fecha": "x", "motivo": "y"}), CONFIG, AHORA) is None
    )
    assert avisos.clasificar(incidente(lugar={"pais": "UA"}), CONFIG, AHORA) is None
    antiguo = incidente(tiempo={"inicio": {"valor": "2026-10-05T08:00Z", "precision": "minuto"}})
    assert avisos.clasificar(antiguo, CONFIG, AHORA) is None


def test_cierre_y_suspension_de_aeropuerto_con_prioridad_normal() -> None:
    cierre = avisos.clasificar(
        incidente(
            tipo="interrupcion_aeroportuaria",
            consecuencias={"cierre": {"valor": "si"}},
            lugar={"pais": "DK"},
        ),
        CONFIG,
        AHORA,
    )
    suspension = avisos.clasificar(
        incidente(tipo="interrupcion_aeroportuaria", lugar={"pais": "DE"}), CONFIG, AHORA
    )
    assert cierre is not None and (cierre.clase, cierre.prioridad) == ("cierre", 3)
    assert suspension is not None and suspension.clase == "suspension"


def test_nunca_prioridad_maxima() -> None:
    for pais in CONFIG["paises"]:
        aviso = avisos.clasificar(incidente(lugar={"pais": pais}), CONFIG, AHORA)
        assert aviso is not None and aviso.prioridad in (3, 4)


# --- Cómo se ve ------------------------------------------------------------------------------
def test_formato_del_aviso() -> None:
    doc = incidente()
    aviso = avisos.clasificar(doc, CONFIG, AHORA)
    assert aviso is not None
    cuerpo = avisos.mensaje(aviso, doc, CONFIG, "slovakia")
    assert cuerpo["title"] == "ESLOVAQUIA · Incursión confirmada"
    es, vacia, en = cuerpo["message"].split("\n")
    assert vacia == ""
    assert en.startswith("SLOVAKIA · Confirmed incursion")
    # Hora local de Eslovaquia (verano, UTC+2) y UTC; lugar y estado en negrita; fuente oficial.
    assert "10/10/2026, 10:04 hora local (08:04 UTC)" in es
    assert "**Michalovce (Eslovaquia)**" in es and "**confirmado**" in es
    assert "Ministerstvo obrany SR" in es
    assert "10 Oct 2026, 10:04 local time (08:04 UTC)" in en and "**confirmed**" in en
    assert cuerpo["markdown"] is True and cuerpo["priority"] == 4
    assert cuerpo["click"] == "https://droneobservatory.eu/EODI-2026-00500"
    assert cuerpo["actions"] == [
        {
            "action": "view",
            "label": "Ver en el mapa / View on map",
            "url": "https://droneobservatory.eu/EODI-2026-00500",
        }
    ]
    assert cuerpo["icon"] == "https://droneobservatory.eu/marca/aviso-256.png"
    # Sin emoticonos ni etiquetas.
    assert "tags" not in cuerpo
    assert all(ord(c) < 0x2000 or c in "·" for c in cuerpo["title"] + cuerpo["message"])


def test_sin_hora_precisa_y_texto_sin_signos_de_markdown() -> None:
    doc = incidente(
        tiempo={"inicio": {"valor": "2026-10-10T00:00Z", "precision": "dia"}},
        titulo={"es": "Dron *sobre* la base_aérea", "en": "Drone *over* the air_base"},
    )
    aviso = avisos.clasificar(doc, CONFIG, AHORA)
    assert aviso is not None
    cuerpo = avisos.mensaje(aviso, doc, CONFIG, "general")
    assert (
        "(hora no precisada)" in cuerpo["message"] and "(time not specified)" in cuerpo["message"]
    )
    assert "Dron sobre la base aérea" in cuerpo["message"]


# --- Una sola vez ----------------------------------------------------------------------------
def _publicar(carpeta: Path, ids: list[str]) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    rasgos = [{"type": "Feature", "id": i, "properties": {"id": i}, "geometry": None} for i in ids]
    (carpeta / "incidentes.geojson").write_text(json.dumps({"features": rasgos}), encoding="utf-8")
    (carpeta / "incidentes_sin_ubicacion.json").write_text(
        json.dumps({"incidentes": []}), encoding="utf-8"
    )


def test_primera_pasada_anota_y_no_envia_y_despues_un_solo_aviso(tmp_path: Path) -> None:
    enviados_a: list[str] = []
    enviados = avisos.Enviados(tmp_path / "avisos.sqlite")
    viejo = incidente(id="EODI-2026-00499")
    nuevo = incidente()

    primera = avisos.pasar(
        {viejo["id"]},
        {viejo["id"]: viejo},
        enviados,
        CONFIG,
        AHORA,
        lambda c: enviados_a.append(c["topic"]),
    )
    assert (primera.marcados, primera.enviados, enviados_a) == (1, 0, [])

    internos = {viejo["id"]: viejo, nuevo["id"]: nuevo}
    segunda = avisos.pasar(
        set(internos), internos, enviados, CONFIG, AHORA, lambda c: enviados_a.append(c["topic"])
    )
    assert segunda.enviados == 2 and enviados_a == ["general", "slovakia"]

    # Una actualización (otro estado, otro titular) no vuelve a avisar.
    internos[nuevo["id"]] = incidente(
        estado={"actual": "atribuido"}, titulo={"es": "Otro", "en": "Other"}
    )
    tercera = avisos.pasar(
        set(internos),
        internos,
        enviados,
        CONFIG,
        AHORA + timedelta(hours=1),
        lambda c: enviados_a.append(c["topic"]),
    )
    assert tercera.enviados == 0 and len(enviados_a) == 2
    enviados.cerrar()


def test_si_falla_se_reintenta_sin_duplicar(tmp_path: Path) -> None:
    enviados = avisos.Enviados(tmp_path / "avisos.sqlite")
    avisos.pasar(set(), {}, enviados, CONFIG, AHORA, lambda c: None)
    doc = incidente()
    temas: list[str] = []

    def falla_el_pais(cuerpo: dict[str, Any]) -> None:
        if cuerpo["topic"] != "general":
            raise OSError("sin conexión")
        temas.append(cuerpo["topic"])

    pasada = avisos.pasar({doc["id"]}, {doc["id"]: doc}, enviados, CONFIG, AHORA, falla_el_pais)
    assert (pasada.enviados, pasada.fallidos) == (1, 1)
    estado = avisos.guardar_estado(tmp_path / "avisos.json", pasada, AHORA)
    assert estado["fallos_seguidos"] == 1 and avisos.problema_para_vigilancia(estado) is None

    otra = avisos.pasar({doc["id"]}, {doc["id"]: doc}, enviados, CONFIG, AHORA, falla_el_pais)
    estado = avisos.guardar_estado(tmp_path / "avisos.json", otra, AHORA)
    assert estado["fallos_seguidos"] == 2
    assert "2 recogidas seguidas" in (avisos.problema_para_vigilancia(estado) or "")

    reintento = avisos.pasar(
        {doc["id"]}, {doc["id"]: doc}, enviados, CONFIG, AHORA, lambda c: temas.append(c["topic"])
    )
    assert reintento.enviados == 1 and temas == ["general", "slovakia"]
    estado = avisos.guardar_estado(tmp_path / "avisos.json", reintento, AHORA)
    assert estado["fallos_seguidos"] == 0
    enviados.cerrar()


def test_ensayo_no_envia_ni_anota(tmp_path: Path) -> None:
    enviados = avisos.Enviados(tmp_path / "avisos.sqlite")
    avisos.pasar(set(), {}, enviados, CONFIG, AHORA, lambda c: None)
    doc = incidente()
    pasada = avisos.pasar({doc["id"]}, {doc["id"]: doc}, enviados, CONFIG, AHORA, None)
    assert pasada.enviados == 2 and enviados.temas(doc["id"]) == set()
    enviados.cerrar()


def test_ids_publicados_lee_los_dos_ficheros(tmp_path: Path) -> None:
    _publicar(tmp_path, ["EODI-2026-00001"])
    (tmp_path / "incidentes_sin_ubicacion.json").write_text(
        json.dumps({"incidentes": [{"id": "EODI-2026-00002"}]}), encoding="utf-8"
    )
    assert avisos.ids_publicados(tmp_path) == {"EODI-2026-00001", "EODI-2026-00002"}


# --- Canales ---------------------------------------------------------------------------------
def test_un_canal_por_pais_cubierto_y_nombres_validos() -> None:
    cubiertos = json.loads(
        (avisos.RAIZ / "configuracion" / "paises_europa.json").read_text(encoding="utf-8")
    )["cajas"]
    assert sorted(CONFIG["paises"]) == sorted(cubiertos)
    temas = avisos.temas_publicos(CONFIG)
    assert temas[0] == "general" and len(set(temas)) == len(temas)
    for tema in temas:
        assert tema == tema.lower() and all(c.isalnum() or c == "-" for c in tema)
    for clave in ("SK", "PL", "RO", "MD", "LT", "LV", "EE", "DE", "DK", "CZ", "HU", "GB"):
        assert CONFIG["paises"][clave]["tema"] in temas
    assert CONFIG["paises"]["GB"]["tema"] == "united-kingdom"


@pytest.mark.parametrize("tema", ["general", "slovakia"])
def test_ejemplo_nunca_a_un_tema_publico(tema: str, tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("tk_x", encoding="utf-8")
    codigo = avisos.principal(
        [
            "ejemplo",
            "--base",
            str(tmp_path / "base.sqlite"),
            "--id",
            "EODI-2026-00001",
            "--tema",
            tema,
            "--token",
            str(token),
        ]
    )
    assert codigo == 1
