"""Paso 2 del extractor (modelo/detalles.py): cuándo se llama y cómo se fusiona lo que devuelve.

Reglas fijas, que no dependen de que el modelo obedezca:

- Solo si el paso 1 da un incidente y alguna nota sigue más allá de lo que leyó el paso 1.
- Solo campos de detalle (modelo/detalles.CAMPOS): ni lugar, ni país, ni si es incidente.
- Solo lo que el paso 1 no dio: lo que dijo el paso 1 no se cambia.
- La hora, solo si el paso 1 dio el día sin hora y la hora es de ese mismo día (UTC); el fin,
  del día del inicio o del siguiente. Sin día del paso 1, ni hora ni fin.
- Cada detalle y cada declaración, con su frase literal en la nota de su fuente.
- Si no hay margen en el tope de gasto, o el servicio falla, la ficha sale con el paso 1.

Lo que añade el paso 2 va marcado (`"paso": 2`): la validación comprueba su frase contra la nota
(proceso/validacion_ficha.validar) y la extracción guarda qué campos puso (`paso2`).
"""

import copy
import json
import logging
from datetime import datetime
from typing import Any, Protocol

from modelo import coste, detalles, ficha
from proceso.noticias import normalizar
from proceso.validacion_ficha import MAX_PALABRAS_FRASE

registro = logging.getLogger(__name__)

PASO = 2
# Dónde queda, en la respuesta y en la extracción guardada, lo que añadió el paso 2.
CLAVE = "paso2"
# Una nota que solo pasa del principio por unas pocas letras no trae nada que leer.
MIN_LETRAS_DE_MAS = 200
# Los detalles con número: solo si el paso 1 no los dio.
CAMPOS_RANGO = ("cierre_minutos", "vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados",
                "drones")  # fmt: skip


class Servicio(Protocol):
    def mensaje(self, cuerpo: dict[str, Any]) -> dict[str, Any]: ...


def bruta(respuesta: dict[str, Any]) -> dict[str, Any] | None:
    """El JSON de una respuesta del servicio, o None si no se puede leer."""
    if respuesta.get("stop_reason") not in {"end_turn", "stop_sequence"}:
        return None
    textos = [b.get("text", "") for b in respuesta.get("content", []) if b.get("type") == "text"]
    try:
        datos = json.loads("".join(textos))
    except ValueError:
        return None
    return datos if isinstance(datos, dict) else None


def con_bruta(respuesta: dict[str, Any], datos: dict[str, Any]) -> dict[str, Any]:
    """La respuesta con su JSON cambiado por `datos`."""
    nueva = copy.deepcopy(respuesta)
    nueva["content"] = [{"type": "text", "text": json.dumps(datos, ensure_ascii=False)}]
    return nueva


def hace_falta(paso1: dict[str, Any] | None, fuentes: list[ficha.FuenteTexto]) -> bool:
    """El paso 1 da un incidente y alguna nota sigue más allá de su principio."""
    if paso1 is None:
        return False
    incidente = [d for d in paso1.get("datos", []) if d.get("campo") == "es_incidente"]
    if not incidente or str(incidente[-1].get("valor", "")).strip().lower() != "true":
        return False
    return any(len(f.nota) >= len(f.texto) + MIN_LETRAS_DE_MAS for f in fuentes)


def _valor(datos: list[dict[str, Any]], campo: str) -> str | None:
    elegidos = sorted(
        (d for d in datos if d.get("campo") == campo), key=lambda d: d.get("confianza", 0)
    )
    return str(elegidos[-1].get("valor", "")).strip() if elegidos else None


def suceso(paso1: dict[str, Any]) -> str:
    """El suceso que decidió el paso 1, como lo lee el paso 2."""
    datos = paso1.get("datos", [])
    partes = [str(paso1.get("titulo_es", "")).strip()]
    lugar = _valor(datos, "lugar_suceso")
    if lugar:
        partes.append(f"lugar: {lugar.split(';')[0].strip()}")
    pais = _valor(datos, "pais")
    if pais:
        partes.append(f"país: {pais}")
    inicio = _valor(datos, "inicio")
    if inicio:
        partes.append(f"día: {inicio[:10]}")
    return "; ".join(p for p in partes if p) + "."


def _en_la_nota(frase: str, numero: Any, fuentes: list[ficha.FuenteTexto]) -> bool:
    if not isinstance(numero, int) or not 1 <= numero <= len(fuentes) or not frase.strip():
        return False
    fuente = fuentes[numero - 1]
    texto = f"{fuente.titular}. {fuente.texto} {fuente.nota}"
    corta = " ".join(frase.split()[:MAX_PALABRAS_FRASE])
    return normalizar(corta) in normalizar(texto)


def _legible(campo: str, valor: str) -> bool:
    try:
        ficha.interpretar(campo, valor)
    except ficha.ValorIlegible:
        return False
    return True


def _dia(valor: str | None) -> str:
    return (valor or "")[:10]


def _con_hora(valor: str) -> bool:
    return len(valor) >= len("AAAA-MM-DDTHH:MM") and valor[10:11] == "T"


def fusionar(
    paso1: dict[str, Any], paso2: dict[str, Any], fuentes: list[ficha.FuenteTexto]
) -> tuple[dict[str, Any], list[str]]:
    """La ficha del paso 1 con los detalles del paso 2 que pasan las reglas, y los campos que
    añadió (o la hora que puso al inicio). Nunca cambia lo que dijo el paso 1."""
    resultado = copy.deepcopy(paso1)
    datos: list[dict[str, Any]] = resultado.setdefault("datos", [])
    dichos = {d.get("campo") for d in datos}
    propuestos = [
        d for d in paso2.get("detalles", [])
        if isinstance(d, dict) and d.get("campo") in detalles.CAMPOS
        and _legible(str(d.get("campo")), str(d.get("valor", "")))
        and _en_la_nota(str(d.get("frase", "")), d.get("fuente"), fuentes)
    ]  # fmt: skip
    por_campo: dict[str, dict[str, Any]] = {}
    for dato in sorted(propuestos, key=lambda d: d.get("confianza", 0)):
        por_campo[str(dato["campo"])] = dato
    anadidos: list[str] = []

    def anadir(dato: dict[str, Any]) -> None:
        datos.append({**{k: dato[k] for k in ("campo", "valor", "fuente", "frase", "confianza")},
                      "paso": PASO})  # fmt: skip
        anadidos.append(str(dato["campo"]))

    # La hora: el paso 1 da el día sin hora y el paso 2 una hora de ese mismo día.
    inicio1 = _valor(datos, "inicio")
    precision1 = _valor(datos, "inicio_precision")
    hora = por_campo.get("inicio")
    if (
        hora is not None and inicio1 and not _con_hora(inicio1)
        and precision1 in {None, "dia"}
        and _con_hora(str(hora["valor"])) and _dia(str(hora["valor"])) == _dia(inicio1)
    ):  # fmt: skip
        resultado["datos"] = datos = [
            d for d in datos if d.get("campo") not in {"inicio", "inicio_precision"}
        ]
        anadir(hora)
        precision = por_campo.get("inicio_precision")
        valor = str((precision or {}).get("valor", "")).strip().lower()
        anadir({**hora, "campo": "inicio_precision",
                "valor": valor if valor in {"minuto", "hora"} else "hora"})  # fmt: skip
    # El fin: con el inicio del paso 1, del mismo día o del siguiente.
    fin = por_campo.get("fin")
    if fin is not None and "fin" not in dichos and inicio1 and _con_hora(str(fin["valor"])):
        try:
            dias = (
                datetime.fromisoformat(_dia(str(fin["valor"])))
                - datetime.fromisoformat(_dia(inicio1))
            ).days
        except ValueError:
            dias = -1
        if 0 <= dias <= 1:
            anadir(fin)
    # El cierre y lo que cuelga de él, los vuelos y los drones: solo si el paso 1 no los dio.
    for campo in ("cierre", *CAMPOS_RANGO):
        elegido = por_campo.get(campo)
        if elegido is None or campo in dichos:
            continue
        if campo == "cierre_minutos" and "si" not in {
            _valor(datos, "cierre"),
            str((por_campo.get("cierre") or {}).get("valor", "")).strip(),
        }:
            continue
        anadir(elegido)
    # Las declaraciones que el paso 1 no tenía, con su frase literal en la nota.
    vistas = {normalizar(str(d.get("frase", ""))) for d in resultado.get("declaraciones", [])}
    nuevas = []
    for declaracion in paso2.get("declaraciones", []):
        if not isinstance(declaracion, dict):
            continue
        frase = str(declaracion.get("frase", ""))
        if normalizar(frase) in vistas or not _en_la_nota(
            frase, declaracion.get("fuente"), fuentes
        ):
            continue
        vistas.add(normalizar(frase))
        nuevas.append({**declaracion, "paso": PASO})
    if nuevas:
        resultado["declaraciones"] = [*resultado.get("declaraciones", []), *nuevas]
        anadidos.append(f"declaraciones:{len(nuevas)}")
    return resultado, anadidos


def completar(
    cliente: Servicio,
    respuesta: dict[str, Any],
    fuentes: list[ficha.FuenteTexto],
    gastado: float,
    modo: coste.Modo,
    mes: coste.Mes | None,
    anotar: Any,
) -> tuple[dict[str, Any], list[str]]:
    """La respuesta del paso 1 completada con el paso 2, y lo que añadió. `anotar(respuesta)`
    anota la llamada del paso 2 con su coste. Sin margen de gasto o con el servicio fallando,
    la respuesta del paso 1 tal cual (y la lista vacía)."""
    from modelo.cliente import LlamadaFallida

    paso1 = bruta(respuesta)
    if paso1 is None or not hace_falta(paso1, fuentes):
        return respuesta, []
    descripcion = suceso(paso1)
    previsto = coste.peor_caso(
        detalles.letras(descripcion, fuentes), detalles.MAX_TOKENS_SALIDA,
        esfuerzo=detalles.ESFUERZO,
    )  # fmt: skip
    try:
        coste.comprobar(gastado, previsto, modo, mes)
    except coste.LimiteGasto as error:
        registro.info("paso 2 sin hacer: %s", error)
        return respuesta, []
    try:
        segunda = cliente.mensaje(detalles.cuerpo(descripcion, fuentes))
    except LlamadaFallida as error:
        registro.warning("paso 2 sin hacer: %s", error)
        return respuesta, []
    anotar(segunda)
    paso2 = bruta(segunda)
    if paso2 is None:
        registro.warning("paso 2: respuesta ilegible")
        return respuesta, []
    fusionada, anadidos = fusionar(paso1, paso2, fuentes)
    if not anadidos:
        return respuesta, []
    return con_bruta(respuesta, fusionada), anadidos
