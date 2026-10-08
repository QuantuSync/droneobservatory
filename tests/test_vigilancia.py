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
    ):
        self.codigo, self.fin, self.diario, self.seguimiento = codigo, fin, diario, seguimiento
        self.alertas = alertas

    def __call__(self, orden: Sequence[str]) -> str:
        if orden[0] == "journalctl":
            return "\n".join(self.diario)
        if orden[2] == vigilancia.UNIDAD_SEGUIMIENTO:
            return f"ActiveState={self.seguimiento}\n"
        if orden[2] == vigilancia.UNIDAD_ALERTAS:
            return f"ActiveState={self.alertas}\n"
        inicio = int((self.fin - timedelta(minutes=15)).timestamp())
        return (
            f"ActiveState=failed\nExecMainStatus={self.codigo}\n"
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
