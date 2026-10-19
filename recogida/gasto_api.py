"""Avisos del gasto de la API al responsable, por su tema privado de ntfy.

Al final de cada recogida horaria (nunca en un ensayo), con lo gastado en el mes (UTC) en la
base y el tope mensual (modelo/coste.py, 10 USD por defecto):

- al 80 % del tope, una vez al mes: el gasto va alto;
- al 100 %, una vez al mes: desde ahí solo trabaja el modelo base de la recogida horaria y
  los casos críticos con la reserva del experto;
- con el saldo agotado o un error de facturación (modelo/cliente.ErrorSaldo, anotado en
  ~/.eodi/saldo_api.json), una vez por episodio: «Saldo de la API agotado: recargar». La
  recogida sigue publicando lo que no necesita el modelo, con el mismo código de salida.

Lo ya avisado queda en ~/.eodi/gasto_api.json (EODI_GASTO_API_ESTADO la cambia en pruebas).
Sin token de ntfy (fuera del servidor) no se avisa ni se anota nada.
"""

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from modelo import cliente, coste

registro = logging.getLogger(__name__)

VARIABLE_ESTADO = "EODI_GASTO_API_ESTADO"
RUTA_ESTADO = Path.home() / ".eodi" / "gasto_api.json"
TITULO_SALDO = "Saldo de la API agotado: recargar"
TITULO_80 = "Gasto de la API al 80 % del tope del mes"
TITULO_100 = "Gasto de la API: tope del mes alcanzado"

Avisador = Callable[[str], Callable[[str], None] | None]


def ruta_estado() -> Path:
    return Path(os.environ.get(VARIABLE_ESTADO) or RUTA_ESTADO)


def _leer(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _enviar(avisador: Avisador, titulo: str, texto: str) -> bool:
    avisar = avisador(titulo)
    if avisar is None:
        return False
    try:
        avisar(texto)
    except Exception as error:
        registro.warning("aviso del gasto sin enviar: %s", str(error)[:200])
        return False
    return True


def revisar(almacen: Almacen, ahora: datetime, avisador: Avisador) -> list[str]:
    """Manda los avisos que tocan y devuelve sus títulos."""
    ruta = ruta_estado()
    estado = _leer(ruta)
    mes = coste.mes(ahora)
    if estado.get("mes") != mes:
        estado = {"mes": mes, "saldo_avisado": estado.get("saldo_avisado")}
    total = coste.del_mes(almacen, ahora).total
    tope = coste.tope_mensual()
    enviados: list[str] = []
    resumen = f"Gastado en {mes}: {total:.2f} de {tope:.2f} USD."
    if total >= tope and not estado.get("aviso_100"):
        texto = (f"{resumen} Hasta fin de mes solo trabaja el modelo base de la recogida "
                 "horaria y los casos críticos con la reserva del experto.")  # fmt: skip
        if _enviar(avisador, TITULO_100, texto):
            estado["aviso_100"] = estado["aviso_80"] = True
            enviados.append(TITULO_100)
    elif total >= coste.AVISO_MENSUAL * tope and not estado.get("aviso_80"):
        if _enviar(avisador, TITULO_80, f"{resumen} Al llegar al tope, solo lo crítico."):
            estado["aviso_80"] = True
            enviados.append(TITULO_80)
    saldo = _leer(cliente.ruta_saldo())
    desde = saldo.get("desde")
    if desde and desde != estado.get("saldo_avisado"):
        texto = (f"La API contesta sin saldo desde {desde} ({saldo.get('motivo', '')}). La "
                 "recogida sigue publicando lo que no necesita el modelo.")  # fmt: skip
        if _enviar(avisador, TITULO_SALDO, texto):
            estado["saldo_avisado"] = desde
            enviados.append(TITULO_SALDO)
    if desde and _llamada_despues(almacen, str(saldo.get("ultimo") or desde)):
        # Se recargó: el episodio termina y el siguiente vuelve a avisar.
        _escribir(cliente.ruta_saldo(), {})
    if enviados or estado != _leer(ruta):
        _escribir(ruta, estado)
    return enviados


def _llamada_despues(almacen: Almacen, momento: str) -> bool:
    return any(str(ll["fecha"]) > momento for ll in almacen.llamadas())


def _escribir(ruta: Path, datos: dict[str, Any]) -> None:
    if not ruta.parent.is_dir():
        return
    try:
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        registro.warning("estado del gasto sin guardar: %s", str(error)[:200])
