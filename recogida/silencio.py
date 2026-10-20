"""Aviso de silencio: que no se pierda nada sin que lo sepa el responsable.

Al final de cada recogida horaria (nunca en un ensayo), un aviso único por su tema privado de ntfy
en cada uno de estos casos:

- **sin_incidentes**: 24 horas sin ningún incidente nuevo en Europa mientras siguen entrando
  noticias candidatas (al menos MIN_CANDIDATAS artículos de candidatos en esas 24 horas);
- **esperas**: candidatos que esperan al experto por los topes de gasto desde hace más de 6 horas,
  o la API sin saldo desde hace más de 6 horas;
- **sin_llamadas**: la extracción lleva más de 3 horas sin llamar al modelo y desde entonces han
  entrado noticias candidatas;
- **dudosos**: un descarte dudoso del modelo base (proceso/escalado.descarte_dudoso) que lleva más
  de 48 horas esperando al experto (uno por candidato).

Cada caso se avisa una vez y no vuelve a avisarse hasta que se resuelve (deja de darse). Lo ya
avisado queda en ~/.eodi/silencio.json (EODI_SILENCIO_ESTADO la cambia en pruebas). Nunca cambia el
código de salida de la recogida. Sin token de ntfy (fuera del servidor) no se avisa ni se anota.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from modelo import cliente
from proceso import escalado, extraccion
from recogida.gasto_api import Avisador

registro = logging.getLogger(__name__)

VARIABLE_ESTADO = "EODI_SILENCIO_ESTADO"
RUTA_ESTADO = Path.home() / ".eodi" / "silencio.json"
SIN_INCIDENTES = timedelta(hours=24)
ESPERA_LARGA = timedelta(hours=6)
SIN_LLAMADAS = timedelta(hours=3)
DUDOSO_LARGO = timedelta(hours=48)
# Las noticias candidatas que tienen que entrar en 24 horas para que el silencio sea raro.
MIN_CANDIDATAS = 3
TITULO = "EODI · Silencio en la recogida"
TITULO_DUDOSO = "EODI · Descarte dudoso sin experto"


@dataclass(frozen=True)
class Medidas:
    """Lo que mira el aviso, leído de la base (medir)."""

    ultima_alta: str | None = None
    candidatas_24h: int = 0
    ultima_llamada: str | None = None
    candidatas_tras_llamada: int = 0
    # Por candidato que espera al experto por el tope: desde cuándo y sus motivos.
    esperas: dict[str, dict[str, Any]] = field(default_factory=dict)
    saldo_desde: str | None = None


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def medir(almacen: Almacen, ahora: datetime) -> Medidas:
    ultima = almacen.ultima_llamada("horario")
    esperas = {
        id_: e for id_, e in extraccion.esperan_experto(almacen).items()
        if isinstance(e, dict) and e.get("por") == "tope"
    }  # fmt: skip
    saldo = _leer(cliente.ruta_saldo())
    return Medidas(
        ultima_alta=almacen.ultima_alta("incidentes"),
        candidatas_24h=almacen.articulos_candidatos_desde(_iso(ahora - SIN_INCIDENTES)),
        ultima_llamada=ultima,
        candidatas_tras_llamada=almacen.articulos_candidatos_desde(ultima) if ultima else 0,
        esperas=esperas,
        saldo_desde=saldo.get("desde"),
    )


def _dudoso(espera: dict[str, Any]) -> bool:
    return any(str(m).startswith(escalado.MOTIVO_DUDOSO) for m in espera.get("motivos", []))


def avisos(medidas: Medidas, ahora: datetime) -> dict[str, tuple[str, str]]:
    """Los casos que se dan ahora: {clave: (título, texto en una frase)}."""
    casos: dict[str, tuple[str, str]] = {}

    def hace(margen: timedelta) -> str:
        return _iso(ahora - margen)

    if (
        medidas.ultima_alta is not None
        and medidas.ultima_alta < hace(SIN_INCIDENTES)
        and medidas.candidatas_24h >= MIN_CANDIDATAS
    ):
        casos["sin_incidentes"] = (TITULO, (
            f"24 h sin incidentes nuevos con {medidas.candidatas_24h} noticias candidatas "
            f"recogidas (el último, {medidas.ultima_alta})."
        ))  # fmt: skip
    largas = sorted(
        str(e.get("desde", "")) for e in medidas.esperas.values()
        if str(e.get("desde", "")) < hace(ESPERA_LARGA)
    )  # fmt: skip
    if largas:
        casos["esperas"] = (TITULO, (
            f"{len(largas)} candidatos esperando al experto por los topes de gasto desde "
            f"{largas[0]}."
        ))  # fmt: skip
    elif medidas.saldo_desde and medidas.saldo_desde < hace(ESPERA_LARGA):
        casos["esperas"] = (TITULO, (
            f"La API sin saldo desde {medidas.saldo_desde}: hay candidatos sin extraer."
        ))  # fmt: skip
    if (
        medidas.ultima_llamada is not None
        and medidas.ultima_llamada < hace(SIN_LLAMADAS)
        and medidas.candidatas_tras_llamada > 0
    ):
        casos["sin_llamadas"] = (TITULO, (
            f"La extracción lleva más de 3 h sin llamar al modelo (la última, "
            f"{medidas.ultima_llamada}) y han entrado {medidas.candidatas_tras_llamada} noticias "
            "candidatas."
        ))  # fmt: skip
    for id_, espera in sorted(medidas.esperas.items()):
        if _dudoso(espera) and str(espera.get("desde", "")) < hace(DUDOSO_LARGO):
            casos[f"dudoso:{id_}"] = (TITULO_DUDOSO, (
                f"El candidato {id_} espera al experto desde {espera.get('desde')}: el modelo "
                "base lo descarta con poca seguridad."
            ))  # fmt: skip
    return casos


def ruta_estado() -> Path:
    return Path(os.environ.get(VARIABLE_ESTADO) or RUTA_ESTADO)


def _leer(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def revisar(almacen: Almacen, ahora: datetime, avisador: Avisador) -> list[str]:
    """Manda los avisos nuevos y devuelve sus claves. Lo que se resolvió sale del estado, y
    vuelve a avisarse si se repite."""
    ruta = ruta_estado()
    avisados = set(_leer(ruta).get("avisados", []))
    casos = avisos(medir(almacen, ahora), ahora)
    enviados: list[str] = []
    for clave, (titulo, texto) in casos.items():
        if clave in avisados:
            continue
        avisar = avisador(titulo)
        if avisar is None:
            continue
        try:
            avisar(texto)
        except Exception as error:
            registro.warning("aviso de silencio sin enviar: %s", str(error)[:200])
            continue
        registro.warning("aviso de silencio: %s", texto)
        enviados.append(clave)
    nuevos = sorted((avisados & set(casos)) | set(enviados))
    if nuevos != sorted(avisados) and ruta.parent.is_dir():
        try:
            ruta.write_text(json.dumps({"avisados": nuevos}, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            registro.warning("estado del silencio sin guardar: %s", str(error)[:200])
    return enviados
