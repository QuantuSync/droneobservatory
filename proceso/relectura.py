"""Una lectura nueva no borra lo que una autoridad ya había dicho (desde el 7 de noviembre de 2026).

Cuando el candidato de una ficha publicada se vuelve a leer, la lectura nueva conserva lo que la
lectura publicada tenía con la frase de una autoridad y la nueva ha perdido: las declaraciones de
autoridad, la presencia del dron (si la nueva es más baja) y los datos de los que sale el tipo
(dron estatal y entrada desde fuera, si la nueva no los da). Solo si la frase sigue en el texto
de alguna fuente que se acaba de leer, y nunca si la lectura nueva trae una autoridad que diga lo
contrario (que no hubo drones, que no pasó nada, que no lo era o que lo deja abierto).

Vale para cualquier modelo. Con dos modelos, la red era repetir con el experto la lectura del base
que rebajaba una ficha publicada (escalado.motivos_publicada); con el modelo único no hay nadie a
quien repetirla. EODI-2026-00766 (Vărăncău, Moldavia): la fuente dice «…, anunță Ministerul
Apărării» al final del párrafo; una lectura la recogió y otra no, y la ficha bajaba de presencia
confirmada a no confirmada, de incursión a sobrevuelo y a «Un posible dron».
"""

from typing import Any

from esquema import Documento

RANGO_PRESENCIA = {"descartada": 0, "no_acreditada": 1, "no_confirmada": 2, "confirmada": 3}
# Lo que una autoridad dice en contra: entonces manda la lectura nueva (EODI-2026-00743: el
# Ministerio de Defensa rumano, «dron no confirmado»).
AFIRMA_CONTRA = frozenset({"sin_drones", "niega_incidente"})
# Los datos de los que sale el tipo «incursión» (incidentes.con_tipo), además de la presencia.
DATOS_DEL_TIPO = ("dron_estatal", "entrada_exterior")
MOTIVO = "relectura: se conserva de la lectura publicada"


def _normal(texto: str) -> str:
    return " ".join(str(texto).lower().split())


def fuente_con(frase: str, textos: tuple[str, ...]) -> int | None:
    """El número (desde 1) de la primera fuente leída cuyo texto trae la frase, o None."""
    buscada = _normal(frase)
    if not buscada:
        return None
    for numero, texto in enumerate(textos, 1):
        if buscada in _normal(texto):
            return numero
    return None


def lectura_publicada(extracciones: list[Documento], publicada: str) -> Documento | None:
    """La última lectura del candidato que se aplicó a la ficha publicada (la que tiene «ficha»;
    una conservada guarda la suya como «ficha_base»)."""
    for extraccion in reversed(extracciones):
        if extraccion.get("incidente") == publicada and isinstance(extraccion.get("ficha"), dict):
            return extraccion
    return None


def _frases(declaraciones: list[dict[str, Any]]) -> list[str]:
    return [_normal(d.get("frase", "")) for d in declaraciones if _normal(d.get("frase", ""))]


def contraria(leida: dict[str, Any], textos: tuple[str, ...]) -> bool:
    """La lectura nueva trae una autoridad que dice lo contrario: que no hubo drones o no pasó
    nada, o la presencia descartada o abierta con la frase de una de sus declaraciones."""
    nuevas = [
        d for d in leida.get("declaraciones") or []
        if isinstance(d, dict) and fuente_con(str(d.get("frase", "")), textos)
    ]  # fmt: skip
    if any(d.get("afirma") in AFIRMA_CONTRA for d in nuevas):
        return True
    presencia = leida.get("presencia_dron")
    if not isinstance(presencia, dict):
        return False
    if presencia.get("valor") == "descartada":
        return True
    frase = _normal(presencia.get("frase", ""))
    if not frase or RANGO_PRESENCIA.get(str(presencia.get("valor")), 3) >= 3:
        return False
    return any(frase in f or f in frase for f in _frases(nuevas))


def _citas_de_autoridad(publicada: Documento) -> list[str]:
    return _frases(
        [{"frase": f.get("frase_origen", "")} for f in publicada.get("fuentes", [])
         if f.get("es_autoridad")]
    )  # fmt: skip


def conservar(
    leida: dict[str, Any],
    anterior: Documento | None,
    publicada: Documento | None,
    textos: tuple[str, ...],
) -> tuple[dict[str, Any], list[str]]:
    """(lectura nueva con lo que conserva de la publicada, motivos). Solo lo que la ficha publicada
    tiene de verdad: la declaración, si la publicada la cita como fuente de autoridad; la presencia,
    si la publicada está a ese nivel; el dron estatal y la entrada, si la publicada los tiene en
    sus pruebas. Sin lectura publicada, o con una autoridad en contra en la nueva, la nueva tal
    cual."""
    if anterior is None or publicada is None or contraria(leida, textos):
        return leida, []
    citas = _citas_de_autoridad(publicada)
    pruebas = publicada.get("pruebas") or {}
    publicada_rango = RANGO_PRESENCIA.get(str(publicada.get("presencia_dron")), -1)
    vieja: dict[str, Any] = anterior.get("ficha") or {}
    resultado = dict(leida)
    motivos: list[str] = []
    propias = leida.get("declaraciones") or []
    ya = _frases([d for d in propias if isinstance(d, dict)])
    anadidas = []
    for declaracion in anterior.get("declaraciones") or vieja.get("declaraciones") or []:
        if not isinstance(declaracion, dict) or declaracion.get("afirma") in AFIRMA_CONTRA:
            continue
        frase = _normal(declaracion.get("frase", ""))
        if not frase or any(frase in f or f in frase for f in ya):
            continue
        if not any(frase in c or c in frase for c in citas):
            continue
        numero = fuente_con(str(declaracion.get("frase", "")), textos)
        if numero is None:
            continue
        anadidas.append({**declaracion, "fuente": numero})
        ya.append(frase)
        motivos.append(f"{MOTIVO} la declaración de {declaracion.get('autoridad') or '?'}")
    if anadidas:
        resultado["declaraciones"] = [*propias, *anadidas]
    antes, ahora = vieja.get("presencia_dron"), leida.get("presencia_dron")
    rango_antes = RANGO_PRESENCIA.get(str((antes or {}).get("valor")), -1)
    rango_ahora = RANGO_PRESENCIA.get(str((ahora or {}).get("valor")), -1)
    if isinstance(antes, dict) and rango_antes > rango_ahora and publicada_rango >= rango_antes:
        numero = fuente_con(str(antes.get("frase", "")), textos)
        if numero is not None:
            resultado["presencia_dron"] = {**antes, "fuente": numero}
            motivos.append(f"{MOTIVO} la presencia {antes.get('valor')}")
    for campo in DATOS_DEL_TIPO:
        antes, ahora = vieja.get(campo), leida.get(campo)
        if not isinstance(antes, dict) or antes.get("valor") is not True:
            continue
        if pruebas.get(campo) is not True:
            continue
        if isinstance(ahora, dict) and ahora.get("valor") is not None:
            continue
        numero = fuente_con(str(antes.get("frase", "")), textos)
        if numero is not None:
            resultado[campo] = {**antes, "fuente": numero}
            motivos.append(f"{MOTIVO} {campo}")
    return resultado, motivos
