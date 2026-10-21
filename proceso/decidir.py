"""Un solo sitio decide el estado y la presencia del dron de un incidente.

Los demás pasos de la recogida (el extractor, las declaraciones oficiales, la competencia entre
autoridades, las rectificaciones, el control de las fichas, las fusiones y las revisiones a mano de
configuracion/incidentes_revisados.json) aportan pruebas: fuentes con su frase, pasos del historial
del estado con su fuente, afirmaciones y pasos de `presencia_historial`. `decidir_estado` y
`decidir_presencia` calculan el valor a partir de esas pruebas con el método
(docs/rectificaciones.md, docs/control_fichas.md) y devuelven también qué fuente y qué regla lo
deciden. `aplicar` deja el incidente con esos valores; lo llama `Almacen.guardar_incidente` cada
vez que se guarda, así que lo que escriba otro paso antes no es lo que queda.
"""

import copy
import json
from dataclasses import dataclass
from functools import cache

from esquema import Documento
from proceso import competencia, declaraciones, incidentes, rectificaciones, titulares
from proceso.estados import Estado

# Las fuentes de una revisión a mano (configuracion/incidentes_revisados.json): mandan.
REVISADA = "revisada-"


@dataclass(frozen=True)
class Decision:
    valor: str
    fuente_id: str | None
    regla: str


def _historial_vigente(incidente: Documento) -> Documento:
    """El incidente con el desmentido que no vale ya corregido (proceso/competencia.py): una frase
    que no niega nada o una autoridad que cede frente a otra competente que lo confirmó. Tampoco
    vale el desmentido que solo niega el dron o su hallazgo («n'avaient permis de retrouver aucun
    drone», EODI-2025-00357) o lo explica por otra causa (una bandada de pájaros, EODI-2026-00007):
    el suceso, el aviso, ocurrió; lo que se rectifica es la presencia."""
    corregido = competencia.corregir_desmentido(incidente)
    resultado = corregido[0] if corregido else incidente
    historial = resultado["estado"]["historial"]
    if len(historial) > 1 and historial[-1]["estado"] == Estado.DESMENTIDO:
        from proceso import presencia

        fuentes = {f["id"]: f for f in resultado.get("fuentes", [])}
        frase = str((fuentes.get(historial[-1].get("fuente_id") or "") or {}).get("frase_origen"))
        if presencia.dice_no_hallado(frase) or presencia.otra_causa(resultado):
            resultado = copy.deepcopy(resultado)
            resultado["estado"]["historial"] = historial[:-1]
            resultado["estado"]["actual"] = historial[-2]["estado"]
            resultado.get("control", {}).pop("motivo_desmentido", None)
    return resultado


def _autoridad_que_lo_cuenta(incidente: Documento) -> Documento | None:
    """La primera autoridad u operador oficial que cuenta lo ocurrido (el portavoz del aeropuerto,
    el control aéreo, la policía o el ministerio), aunque diga que no encontró el dron o que era
    otra cosa: el suceso queda confirmado (docs/control_fichas.md, «estado»)."""
    autoridades = [
        f for f in incidente.get("fuentes", [])
        if declaraciones.de_autoridad(f) and str(f.get("frase_origen") or "").strip()
    ]  # fmt: skip
    return min(autoridades, key=lambda f: (f["fecha"]["valor"], f["id"]), default=None)


def decidir_estado(incidente: Documento) -> Decision:
    """El estado es el último paso de su historial (cada paso lo da una fuente: la noticia, la
    declaración de una autoridad, la revisión a mano o la rectificación del control), salvo un
    desmentido que no vale; y «confirmado» si sigue «notificado» y una autoridad cuenta lo
    ocurrido."""
    vigente = _historial_vigente(incidente)
    historial = vigente["estado"]["historial"]
    if not historial:
        return Decision(str(incidente["estado"]["actual"]), None, "sin_historial")
    ultimo = historial[-1]
    # Un paso que retira la confirmación con su motivo (una revisión a mano o el control de las
    # fichas) manda: la regla no la vuelve a confirmar.
    if (
        ultimo["estado"] == Estado.NOTIFICADO
        and not ultimo.get("motivo")
        and (cuenta := _autoridad_que_lo_cuenta(vigente))
    ):
        return Decision(Estado.CONFIRMADO.value, str(cuenta["id"]), "autoridad_lo_cuenta")
    regla = "competencia" if historial is not incidente["estado"]["historial"] else "historial"
    return Decision(str(ultimo["estado"]), ultimo.get("fuente_id"), regla)


def _afirmada(incidente: Documento, fuente_id: str) -> str | None:
    for afirmacion in incidente.get("afirmaciones", []):
        if afirmacion.get("campo") == "presencia_dron" and afirmacion.get("fuente_id") == fuente_id:
            return str(afirmacion["valor"])
    return None


@cache
def _revisadas() -> dict[str, str]:
    """La presencia revisada a mano de cada incidente, con su cita (configuracion/
    incidentes_revisados.json, «titulares»)."""
    from proceso import presencia

    datos = json.loads(presencia.REVISADOS.read_text(encoding="utf-8"))
    return {
        str(t["incidente"]): str(t["presencia"]["valor"])
        for t in datos.get("titulares", [])
        if isinstance(t.get("presencia"), dict) and t["presencia"].get("valor")
    }


def _abierta(incidente: Documento, negadas: frozenset[str]) -> bool:
    """Lo que deja abierta la presencia aunque una autoridad la atribuya a un dron (las mismas
    condiciones que proceso/presencia.pendientes): un desmentido,
    una fuente que cuenta que no se encontró el dron sin pruebas físicas, o una fuente
    en que el control de las fichas lee que no se encontró o que se desmiente."""
    from proceso import presencia

    if incidente["estado"]["actual"] == Estado.DESMENTIDO:
        return True
    if presencia.no_hallado(incidente) is not None and not (
        presencia.pruebas_fisicas_confirmadas(incidente)
    ):
        return True
    return bool(negadas & {str(f["id"]) for f in incidente.get("fuentes", [])})


def decidir_presencia(
    incidente: Documento, negadas: frozenset[str] = frozenset(), confirmada: bool = False
) -> Decision:
    """La presencia del dron por orden de prioridad:

    1. rectificación: el último paso de `presencia_historial` (una autoridad lo rectificó; lo
       decide el experto o una revisión a mano con su cita);
    2. revisión a mano: la cita revisada de configuracion/incidentes_revisados.json, que entra como
       una fuente más con su afirmación;
    3. documento oficial: la autoridad lo dice en su propio documento;
    4. descartada: una fuente afirma que era otra cosa (la autoridad, o la noticia que cuenta lo
       que concluyó);
    5. una autoridad lo atribuye a un dron (salvo lo que la deja abierta, `_abierta`; `negadas`
       son las fuentes en que el control de las fichas lee que no se encontró el dron), o
       pruebas físicas con el suceso confirmado: confirmada;
    6. si no, no confirmada (lo dejan abierto o solo lo cuentan la prensa o los testigos).
    """
    pasos = [p for p in incidente.get("presencia_historial") or [] if not p.get("parcial")]
    if pasos:
        return Decision(str(pasos[-1]["valor"]), pasos[-1].get("fuente_id"), "rectificacion")
    fuentes = incidente.get("fuentes", [])
    for afirmacion in incidente.get("afirmaciones", []):
        if afirmacion.get("campo") == "presencia_dron" and str(
            afirmacion.get("fuente_id", "")
        ).startswith(REVISADA):
            return Decision(str(afirmacion["valor"]), str(afirmacion["fuente_id"]), "revision")
    if incidente["id"] in _revisadas():
        return Decision(_revisadas()[incidente["id"]], REVISADA + "titular", "revision")
    for fuente in fuentes:
        if fuente.get("documento_oficial") and "presencia_dron" in fuente.get(
            "campos_respaldados", []
        ):
            valor = _afirmada(incidente, str(fuente["id"]))
            if valor is not None:
                return Decision(valor, str(fuente["id"]), "documento_oficial")
    for afirmacion in incidente.get("afirmaciones", []):
        # La autoridad dice que era otra cosa, en su declaración o en la noticia que la cuenta.
        if afirmacion.get("campo") == "presencia_dron" and afirmacion.get("valor") == (
            rectificaciones.DESCARTADA
        ):
            return Decision(rectificaciones.DESCARTADA, str(afirmacion["fuente_id"]), "descartada")
    # Lo que la deja abierta impide confirmarla de nuevo, pero no baja la que ya estaba confirmada
    # (`confirmada`, lo guardado): eso lo hacen las rectificaciones y el criterio de presencia.
    for fuente in fuentes if confirmada or not _abierta(incidente, negadas) else []:
        # Una autoridad lo atribuye a un dron sin dejarlo abierto.
        if declaraciones.de_autoridad(fuente) and declaraciones.atribuye_dron(
            str(fuente.get("frase_origen") or "")
        ):
            return Decision("confirmada", str(fuente["id"]), "autoridad_atribuye")
    fisicas = set((incidente.get("pruebas") or {}).get("evidencia", [])) & (
        incidentes.PRUEBAS_FISICAS
    )
    if fisicas and incidente["estado"]["actual"] in incidentes.CONFIRMADOS:
        return Decision("confirmada", None, "pruebas_fisicas")
    return Decision("no_confirmada", None, "sin_autoridad")


def aplicar(
    incidente: Documento, negadas: frozenset[str] = frozenset(), confirmada: bool = False
) -> Documento:
    """El incidente con el estado y la presencia que deciden sus pruebas, y el titular coherente
    con la presencia (proceso/titulares.py). Sin cambios si ya los tenía."""
    resultado = _historial_vigente(incidente)
    estado = decidir_estado(resultado)
    if resultado is incidente and estado.valor == incidente["estado"]["actual"]:
        resultado = incidente
    else:
        resultado = copy.deepcopy(resultado)
        if estado.regla == "autoridad_lo_cuenta":
            fuente = next(f for f in resultado["fuentes"] if f["id"] == estado.fuente_id)
            resultado["estado"]["historial"].append({
                "estado": estado.valor, "fecha": copy.deepcopy(fuente["fecha"]),
                "fuente_id": estado.fuente_id,
            })  # fmt: skip
        resultado["estado"]["actual"] = estado.valor
        if estado.valor != Estado.DESMENTIDO:
            resultado.get("control", {}).pop("motivo_desmentido", None)
    presencia = decidir_presencia(resultado, negadas, confirmada)
    if presencia.valor != resultado.get("presencia_dron"):
        resultado = titulares.ajustar_incidente(
            {**copy.deepcopy(resultado), "presencia_dron": presencia.valor}
        )
    return resultado


def motivo(
    incidente: Documento, negadas: frozenset[str] = frozenset(), confirmada: bool = False
) -> str:
    """El motivo del cambio que hace `aplicar`, para el historial: el del criterio de presencia
    si es una presencia sin base (proceso/presencia.py); si no, la regla que decide."""
    from proceso import presencia

    if presencia.sin_base(incidente):
        return presencia.motivo_sin_base(incidente)
    estado, decision = decidir_estado(incidente), decidir_presencia(incidente, negadas, confirmada)
    return (
        f"un solo sitio decide (proceso/decidir.py): estado por {estado.regla}, presencia "
        f"{decision.valor} por {decision.regla}"
    )
