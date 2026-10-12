"""salud.json del servidor (recogida/vigilancia.py) y la decisión de reiniciar
(recogida/reinicio.py), sin systemd ni red."""

import gzip
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from recogida import reinicio, vigilancia

AHORA = datetime(2026, 10, 7, 14, 50, tzinfo=UTC)


@pytest.fixture(autouse=True)
def sin_gracia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las pruebas de cada problema lo ven en su primera pasada; las de la espera la ponen. Sin
    red: los certificados, al día."""
    monkeypatch.setattr(vigilancia, "GRACIA", timedelta(0))
    monkeypatch.setattr(vigilancia, "dias_de_certificado", lambda _host: 60.0)


def test_un_certificado_sin_renovar_es_problema() -> None:
    assert vigilancia.certificados_que_caducan(lambda h: 60.0) == []
    caducan = vigilancia.certificados_que_caducan(lambda h: 10.0 if h.startswith("stats") else 60.0)
    assert caducan == ["stats.droneobservatory.eu (10 días)"]


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


class Sistema:
    """Responde a systemctl show y a journalctl como lo haría el servidor."""

    def __init__(
        self,
        codigo: int,
        fin: datetime,
        diario: list[str],
        seguimiento: str = "active",
        alertas: str = "active",
        recogida: str = "failed",
    ):
        self.codigo, self.fin, self.diario, self.seguimiento = codigo, fin, diario, seguimiento
        self.alertas, self.recogida = alertas, recogida

    def __call__(self, orden: Sequence[str]) -> str:
        if orden[0] == "journalctl":
            return "\n".join(self.diario)
        if orden[2] == vigilancia.UNIDAD_SEGUIMIENTO:
            return f"ActiveState={self.seguimiento}\n"
        if orden[2] == vigilancia.UNIDAD_ALERTAS:
            return f"ActiveState={self.alertas}\n"
        inicio = int((self.fin - timedelta(minutes=15)).timestamp())
        return (
            f"ActiveState={self.recogida}\nExecMainStatus={self.codigo}\n"
            f"ExecMainStartTimestamp=@{inicio}\nExecMainExitTimestamp=@{int(self.fin.timestamp())}\n"
        )


def preparar(tmp_path: Path, recepcion: datetime, copia: datetime) -> tuple[Path, Path]:
    secretos, datos = tmp_path / "secretos", tmp_path / "seguimiento"
    (datos / "copias").mkdir(parents=True)
    secretos.mkdir()
    (secretos / "base_modo").write_text("disco\n", encoding="utf-8")
    (secretos / "seguimiento.json").write_text(
        json.dumps({"ultima_recepcion": _iso(recepcion)}), encoding="utf-8"
    )
    (secretos / "replica.json").write_text(json.dumps({"ultima": _iso(copia)}), encoding="utf-8")
    (secretos / "alertas.json").write_text(
        json.dumps({"ultima_respuesta": _iso(recepcion)}), encoding="utf-8"
    )
    (secretos / "versiones.json").write_text(
        json.dumps({"publicadas": ["2026-10"], "comprobada": _iso(AHORA - timedelta(hours=12))}),
        encoding="utf-8",
    )
    (datos / "copias" / "2026-10-07.json").write_text(
        json.dumps({"objetos": {"neptun/x.gz": {"copiado": _iso(copia)}}}), encoding="utf-8"
    )
    return secretos, datos


def test_todo_bien_con_avisos_de_la_recogida_y_titulares_retenidos(tmp_path: Path) -> None:
    hace = AHORA - timedelta(seconds=20)
    secretos, datos = preparar(tmp_path, hace, AHORA - timedelta(minutes=47))
    retenido = "WARNING exportacion.geojson: EODI-2026-00486 no se publica: su cita no respalda"
    diario = [
        "WARNING recogida.oficiales: oficiales: tope de 240 s agotado; fuentes sin leer: 2",
        retenido + " el titular",
        retenido + " el titular",
        "INFO recogida.horaria: ficheros publicados",
    ]
    sistema = Sistema(2, AHORA - timedelta(minutes=17), diario)
    salud, detalle = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, sistema, lambda: AHORA - timedelta(minutes=18)
    )
    assert salud["problemas"] == []
    ids = [a["id"] for a in salud["avisos"]]
    assert ids == ["recogida_con_avisos", "titulares_retenidos"]
    assert "tope de 240 s agotado" in salud["avisos"][0]["frase"]
    assert "retiene 1 incidentes" in salud["avisos"][1]["frase"]
    # El identificador sin publicar no sale en el fichero público, solo en el diario.
    assert "EODI-2026-00486" not in json.dumps(salud)
    assert any("EODI-2026-00486" in linea for linea in detalle)
    # La hora de la última publicación queda en el registro.
    memoria = json.loads((secretos / "vigilancia.json").read_text(encoding="utf-8"))
    assert memoria["ultima_publicacion"] == _iso(AHORA - timedelta(minutes=17))


def test_cada_problema_tiene_su_frase(tmp_path: Path) -> None:
    secretos, datos = preparar(tmp_path, AHORA - timedelta(minutes=25), AHORA - timedelta(hours=4))
    sistema = Sistema(1, AHORA - timedelta(hours=3), [], seguimiento="failed", alertas="failed")
    (secretos / "alertas.json").write_text(
        json.dumps({"error_autorizacion": {"momento": _iso(AHORA), "http": 401}}), encoding="utf-8"
    )
    (secretos / "versiones.json").write_text(
        json.dumps({"publicadas": [], "fallo": "2026-10-01T02:35:00Z sin red"}), encoding="utf-8"
    )
    # Dos recogidas anteriores también fallidas: con esta son tres seguidas.
    anteriores = [{"fin": _iso(AHORA - timedelta(hours=h)), "codigo": 1} for h in (5, 4)]
    (secretos / "vigilancia.json").write_text(
        json.dumps({"recogidas": anteriores}), encoding="utf-8"
    )
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, sistema, lambda: AHORA - timedelta(hours=4)
    )
    ids = {p["id"] for p in salud["problemas"]}
    assert ids == {
        "publicacion",
        "recogida",
        "seguimiento",
        "alertas",
        "alertas_autorizacion",
        "copia_base",
        "copia_archivo",
        "replica",
        "versiones",
    }


def test_el_disco_avisa_antes_del_80(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secretos, datos = preparar(tmp_path, AHORA, AHORA)

    class Uso:
        total, used, free = 100, 76, 24

    monkeypatch.setattr("recogida.vigilancia.shutil.disk_usage", lambda _ruta: Uso())
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, Sistema(0, AHORA - timedelta(minutes=10), []),
        lambda: AHORA,
    )  # fmt: skip
    assert [p["id"] for p in salud["problemas"]] == ["disco"]


@pytest.mark.parametrize(("minutos", "problema"), [(14, False), (16, True)])
def test_alertas_sin_respuesta_mas_de_15_minutos(
    tmp_path: Path, minutos: int, problema: bool
) -> None:
    secretos, datos = preparar(tmp_path, AHORA, AHORA)
    (secretos / "alertas.json").write_text(
        json.dumps({"ultima_respuesta": _iso(AHORA - timedelta(minutes=minutos))}), encoding="utf-8"
    )
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, Sistema(0, AHORA - timedelta(minutes=10), []),
        lambda: AHORA,
    )  # fmt: skip
    ids = [p["id"] for p in salud["problemas"] if p["id"] != "disco"]
    assert ids == (["alertas"] if problema else [])
    assert salud["alertas"]["unidad"] == "active"


# --- Reinicio ---------------------------------------------------------------------------------
def flujo(tmp_path: Path, mensajes: list[dict[str, object]], cuando: datetime) -> Path:
    carpeta = tmp_path / "neptun" / f"{cuando:%Y}" / f"{cuando:%m}"
    carpeta.mkdir(parents=True, exist_ok=True)
    lineas = [
        json.dumps({"recibido": _iso(cuando), "via": "ws", "crudo": json.dumps(m)})
        for m in mensajes
    ]
    ruta = carpeta / f"neptun-{cuando:%Y-%m-%dT%H}.jsonl.gz"
    ruta.write_bytes(gzip.compress(("\n".join(lineas) + "\n").encode()))
    return tmp_path


def amenaza(ident: str, tipo: str = "uav") -> dict[str, object]:
    return {"id": ident, "type": tipo, "status": "active"}


def test_sin_ataque_se_puede_reiniciar(tmp_path: Path) -> None:
    mensajes: list[dict[str, object]] = [
        {"type": "snapshot", "data": {"threats": [amenaza(f"t{i}") for i in range(25)]}},
        *({"type": "remove", "data": {"id": f"t{i}"}} for i in range(10)),  # type: ignore[list-item]
        {"type": "upsert", "data": amenaza("k1", "kab")},
    ]
    datos = flujo(tmp_path, mensajes, AHORA - timedelta(minutes=1))
    se_puede, motivo = reinicio.decidir(AHORA, datos, lambda: ["eodi-directo.service"])
    assert se_puede, motivo
    assert "15 drones y 0 misiles" in motivo


@pytest.mark.parametrize(
    ("mensajes", "frase"),
    [
        ([{"type": "upsert", "data": amenaza("m1", "missile")}], "ataque en curso"),
        ([{"type": "snapshot", "data": {"threats": [amenaza(f"t{i}") for i in range(21)]}}],
         "ataque en curso"),
    ],
)  # fmt: skip
def test_con_ataque_no_se_reinicia(
    tmp_path: Path, mensajes: list[dict[str, object]], frase: str
) -> None:
    datos = flujo(tmp_path, mensajes, AHORA - timedelta(minutes=1))
    se_puede, motivo = reinicio.decidir(AHORA, datos, lambda: [])
    assert not se_puede
    assert frase in motivo


def test_ni_en_la_hora_de_la_recogida_ni_con_trabajos_ni_sin_neptun(tmp_path: Path) -> None:
    datos = flujo(tmp_path, [{"type": "heartbeat"}], AHORA - timedelta(minutes=1))
    assert not reinicio.decidir(AHORA.replace(minute=20), datos, lambda: [])[0]
    assert "trafico" in reinicio.decidir(AHORA, datos, lambda: ["eodi-trafico.service"])[1]
    viejo = flujo(tmp_path / "otro", [{"type": "heartbeat"}], AHORA - timedelta(hours=2))
    assert "NEPTUN" in reinicio.decidir(AHORA, viejo, lambda: [])[1]


def test_ntfy_sin_responder_y_avisos_que_fallan_dos_recogidas(tmp_path: Path) -> None:
    secretos, datos = preparar(
        tmp_path, AHORA - timedelta(seconds=20), AHORA - timedelta(minutes=47)
    )
    sistema = Sistema(0, AHORA - timedelta(minutes=17), [])
    copia = lambda: AHORA - timedelta(minutes=18)  # noqa: E731
    # Sin el token de ntfy (otro servidor, o antes de instalarlo), no se mira.
    salud, _ = vigilancia.componer(AHORA, secretos, datos, tmp_path, sistema, copia, lambda: False)
    assert salud["problemas"] == []
    (secretos / "ntfy_observatorio").write_text("tk_x", encoding="utf-8")
    (secretos / "avisos.json").write_text(json.dumps({"fallos_seguidos": 1}), encoding="utf-8")
    visitas_al_dia(secretos)
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, sistema, copia, lambda: True, lambda: True, list
    )
    assert salud["problemas"] == []
    (secretos / "avisos.json").write_text(
        json.dumps({"fallos_seguidos": 2, "error": "URLError: sin red"}), encoding="utf-8"
    )
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, sistema, copia, lambda: False, lambda: True, list
    )
    assert {p["id"] for p in salud["problemas"]} == {"ntfy", "avisos"}
    assert "2 recogidas seguidas" in next(
        p["frase"] for p in salud["problemas"] if p["id"] == "avisos"
    )


def visitas_al_dia(secretos: Path) -> None:
    (secretos / "visitas.json").write_text(
        json.dumps({
            "resumen": {"dia": "2026-10-06", "enviado": "2026-10-07T06:00:20Z"},
            "copia": {"ultima": _iso(AHORA - timedelta(minutes=30))},
        }),
        encoding="utf-8",
    )  # fmt: skip


def test_contador_de_visitas_resumen_y_su_copia(tmp_path: Path) -> None:
    secretos, datos = preparar(
        tmp_path, AHORA - timedelta(seconds=20), AHORA - timedelta(minutes=47)
    )
    sistema = Sistema(0, AHORA - timedelta(minutes=17), [])
    copia = lambda: AHORA - timedelta(minutes=18)  # noqa: E731
    (secretos / "ntfy_observatorio").write_text("tk_x", encoding="utf-8")
    visitas_al_dia(secretos)
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, sistema, copia, lambda: True, lambda: False,
        lambda: ["el panel de visitas se abre sin usuario (HTTP 200)"],
    )  # fmt: skip
    assert [p["id"] for p in salud["problemas"]] == ["goatcounter", "visitas_privadas"]
    # El resumen del día anterior sin enviar a las 16:50 de Madrid y la copia de hace 4 horas.
    (secretos / "visitas.json").write_text(
        json.dumps({
            "resumen": {"dia": "2026-10-05", "error": "URLError: sin red"},
            "copia": {"ultima": _iso(AHORA - timedelta(hours=4))},
        }),
        encoding="utf-8",
    )  # fmt: skip
    salud, _ = vigilancia.componer(
        AHORA, secretos, datos, tmp_path, sistema, copia, lambda: True, lambda: True, list
    )
    problemas = {p["id"]: p["frase"] for p in salud["problemas"]}
    assert set(problemas) == {"resumen", "copia_visitas"}
    assert "2026-10-06" in problemas["resumen"] and "sin red" in problemas["resumen"]


# --- Que se cura sola -------------------------------------------------------------------------
def test_una_o_dos_recogidas_fallidas_son_aviso_y_la_tercera_problema(tmp_path: Path) -> None:
    secretos, datos = preparar(tmp_path, AHORA, AHORA - timedelta(minutes=30))
    copia = lambda: AHORA - timedelta(minutes=18)  # noqa: E731
    for horas, esperado in ((2, "aviso"), (1, "aviso"), (0, "problema")):
        fin = AHORA - timedelta(hours=horas, minutes=1)
        salud, _ = vigilancia.componer(
            fin + timedelta(minutes=1), secretos, datos, tmp_path, Sistema(1, fin, []), copia
        )
        ids = {p["id"] for p in salud["problemas"]}
        avisos = {a["id"] for a in salud["avisos"]}
        if esperado == "aviso":
            assert "recogida" not in ids and "recogida_fallida" in avisos
        else:
            assert "recogida" in ids
    # La siguiente publica: se acabó el problema y queda como resuelto para el resumen.
    fin = AHORA + timedelta(hours=1)
    salud, _ = vigilancia.componer(
        fin + timedelta(minutes=1), secretos, datos, tmp_path, Sistema(0, fin, []), copia
    )
    assert "recogida" not in {p["id"] for p in salud["problemas"]}
    memoria = json.loads((secretos / "vigilancia.json").read_text(encoding="utf-8"))
    resueltos = {r["id"]: r for r in memoria["resueltos"]}
    assert set(resueltos) == {"recogida", "publicacion"}
    assert resueltos["recogida"]["incidencia"] is True


def test_una_recogida_en_marcha_no_se_juzga(tmp_path: Path) -> None:
    secretos, datos = preparar(tmp_path, AHORA, AHORA - timedelta(minutes=30))
    copia = lambda: AHORA - timedelta(minutes=18)  # noqa: E731
    anteriores = [{"fin": _iso(AHORA - timedelta(hours=h)), "codigo": 1} for h in (3, 2, 1)]
    (secretos / "vigilancia.json").write_text(
        json.dumps({"recogidas": anteriores, "ultima_publicacion": _iso(AHORA)}), encoding="utf-8"
    )
    # La unidad en marcha dice código 0 (systemd lo pone a cero al arrancar): no cierra nada.
    en_marcha = Sistema(0, AHORA - timedelta(hours=1), [], recogida="activating")
    salud, _ = vigilancia.componer(AHORA, secretos, datos, tmp_path, en_marcha, copia)
    assert "recogida" in {p["id"] for p in salud["problemas"]}
    assert salud["recogida"]["en_marcha"] is True


def test_un_fallo_suelto_queda_en_observacion_y_luego_en_resueltos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vigilancia, "GRACIA", timedelta(minutes=30))
    secretos, datos = preparar(tmp_path, AHORA, AHORA)
    sistema = Sistema(0, AHORA - timedelta(minutes=10), [], alertas="failed")
    copia = lambda: AHORA  # noqa: E731
    salud, _ = vigilancia.componer(AHORA, secretos, datos, tmp_path, sistema, copia)
    assert "alertas" not in {p["id"] for p in salud["problemas"]}
    assert "observacion_alertas" in {a["id"] for a in salud["avisos"]}
    # Sigue igual a los 30 minutos: ahora sí es problema.
    despues = AHORA + timedelta(minutes=31)
    salud, _ = vigilancia.componer(despues, secretos, datos, tmp_path, sistema, copia)
    assert "alertas" in {p["id"] for p in salud["problemas"]}
    # Se arregla: sale de los problemas y queda en resueltos con la incidencia que tuvo.
    (secretos / "alertas.json").write_text(
        json.dumps({"ultima_respuesta": _iso(despues)}), encoding="utf-8"
    )
    bien = Sistema(0, despues, [])
    salud, _ = vigilancia.componer(despues, secretos, datos, tmp_path, bien, copia)
    assert "alertas" not in {p["id"] for p in salud["problemas"]}
    memoria = json.loads((secretos / "vigilancia.json").read_text(encoding="utf-8"))
    assert [(r["id"], r["incidencia"]) for r in memoria["resueltos"]] == [("alertas", True)]


def test_un_fallo_que_se_arregla_antes_de_la_espera_no_llega_a_incidencia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vigilancia, "GRACIA", timedelta(minutes=30))
    secretos, datos = preparar(tmp_path, AHORA, AHORA)
    copia = lambda: AHORA  # noqa: E731
    mal = Sistema(0, AHORA - timedelta(minutes=10), [], seguimiento="failed")
    vigilancia.componer(AHORA, secretos, datos, tmp_path, mal, copia)
    bien = Sistema(0, AHORA - timedelta(minutes=10), [])
    salud, _ = vigilancia.componer(
        AHORA + timedelta(minutes=5), secretos, datos, tmp_path, bien, copia
    )
    assert salud["problemas"] == []
    memoria = json.loads((secretos / "vigilancia.json").read_text(encoding="utf-8"))
    assert [(r["id"], r["incidencia"]) for r in memoria["resueltos"]] == [("seguimiento", False)]
