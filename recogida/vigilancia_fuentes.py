"""El estado de las fuentes que se leen en la recogida, para la vigilancia.

La recogida deja en `fuentes.json` (al lado de `control.json`) las fuentes oficiales
(recogida/oficiales.py) y los medios públicos (recogida/medios_publicos.py) que vienen fallando,
con desde cuándo y el último motivo; la vigilancia (recogida/vigilancia.py) lo convierte en:

- **medios_publicos** (problema): un medio público lleva más de MAX_SIN_LEER sin leerse. Donde se
  lee un medio público (LRT en Lituania) es porque ninguna web oficial del país deja entrar al
  servidor: sin él, de ese país solo llega lo que traiga GDELT, horas después.
- **fuentes_oficiales** (aviso, se ve y no abre incidencia): las fuentes oficiales que llevan más
  de MAX_SIN_LEER sin leerse. Al responsable ya le llega su aviso privado, una vez por racha.

El fichero solo lleva identificadores de fuentes (los de la configuración, que es pública), horas
y el motivo del fallo (la dirección pública que se pidió y lo que respondió)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

FICHERO = "fuentes.json"
MAX_SIN_LEER = timedelta(hours=3)
# El fichero de una recogida de hace más de esto no dice nada de ahora (la recogida parada es
# otro problema, con su propio aviso).
MAX_FICHERO = timedelta(hours=3)
MAX_MOTIVO = 160


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instante(texto: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")) if texto else None
    except ValueError:
        return None


def _publico(estados: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        id_: {
            "fallos_seguidos": int(estado.get("fallos_seguidos") or 0),
            "primer_fallo": estado.get("primer_fallo"),
            "motivo": str(estado.get("motivo") or "")[:MAX_MOTIVO],
        }
        for id_, estado in sorted(estados.items())
    }


def escribir(ruta: Path, almacen: Any, ahora: datetime) -> None:
    """Lo que deja la recogida: las fuentes que vienen fallando (vacío si todas se leen)."""
    from recogida import medios_publicos, oficiales

    documento = {
        "fecha": _iso(ahora),
        "oficiales": _publico(oficiales.fallos(almacen)),
        "medios_publicos": _publico(medios_publicos.fallos(almacen)),
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(documento, ensure_ascii=False, indent=1), encoding="utf-8")


def _sin_leer(estados: Any, ahora: datetime) -> list[tuple[str, datetime, dict[str, Any]]]:
    """(fuente, desde cuándo falla, su estado) de las que llevan más de MAX_SIN_LEER fallando."""
    largas = []
    for id_, estado in sorted((estados or {}).items()):
        desde = _instante(estado.get("primer_fallo")) if isinstance(estado, dict) else None
        if desde is not None and ahora - desde >= MAX_SIN_LEER:
            largas.append((str(id_), desde, estado))
    return largas


def problemas(estado: dict[str, Any], ahora: datetime) -> list[dict[str, str]]:
    """Los medios públicos que llevan más de MAX_SIN_LEER sin leerse."""
    fecha = _instante(estado.get("fecha"))
    if fecha is None or ahora - fecha > MAX_FICHERO:
        return []
    largas = _sin_leer(estado.get("medios_publicos"), ahora)
    if not largas:
        return []
    partes = [
        f"{id_} desde el {desde:%Y-%m-%d %H:%M} UTC ({datos.get('fallos_seguidos', 0)} recogidas "
        f"seguidas: {datos.get('motivo') or 'sin motivo'})"
        for id_, desde, datos in largas
    ]
    return [{
        "id": "medios_publicos",
        "frase": "Medios públicos que se leen como fuente y llevan más de 3 horas sin leerse: "
        + "; ".join(partes)[:500] + ".",
    }]  # fmt: skip


def avisos(estado: dict[str, Any], ahora: datetime) -> list[dict[str, str]]:
    """Las fuentes oficiales que llevan más de MAX_SIN_LEER sin leerse."""
    fecha = _instante(estado.get("fecha"))
    if fecha is None or ahora - fecha > MAX_FICHERO:
        return []
    largas = _sin_leer(estado.get("oficiales"), ahora)
    if not largas:
        return []
    partes = [f"{id_} desde el {desde:%Y-%m-%d %H:%M} UTC" for id_, desde, _ in largas]
    return [{
        "id": "fuentes_oficiales",
        "frase": "Fuentes oficiales que llevan más de 3 horas sin leerse (se siguen probando en "
        "cada recogida): " + "; ".join(partes)[:400] + ".",
    }]  # fmt: skip
