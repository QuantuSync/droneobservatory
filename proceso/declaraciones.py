"""Declaraciones oficiales citadas por la prensa: cómo cambian el incidente.

Las autoridades confirman los incidentes en declaraciones a la prensa, no en sus
webs. Cada declaración que el extractor encuentra en una noticia (con su frase
literal, que tiene que estar en el texto enviado) se registra como fuente
«declaración oficial citada», de fiabilidad B, con el enlace a la noticia. Reglas:

- incidente o drones: pasa a confirmado (la autoridad dice que ocurrió).
- Presencia del dron: si la autoridad competente lo da por hecho, está confirmada. Basta con
  que actúe o declare atribuyendo el suceso a un dron (un cierre por dron, un aviso de dron
  que comunica, una intervención por dron): drones, incidente o autoria de un gobierno,
  ministerio, fuerzas armadas, policía, fiscalía, autoridad de aviación civil, gestor de
  navegación aérea o gestor aeroportuario confirman la presencia. No se piden restos, grabación
  ni detección por sensor. Solo queda sin confirmar si la propia autoridad lo deja abierto
  («posible dron», «objeto no identificado», «se investiga si era un dron»). Cada confirmación
  deja una afirmación de presencia_dron con la fuente que la provoca.
- sin_drones: presencia_dron descartada. niega_incidente: desmentido.
- autoria: atribuido, solo si quien atribuye es un gobierno.

Una autoridad habla de su país: una declaración de una autoridad de otro país no
cambia el incidente (el gobierno letón que dice que en Letonia no entró ningún dron
no desmiente el derribo en Estonia). Las fichas anteriores no traen el país de la
autoridad: sus declaraciones valen como antes.
"""

import contextlib
import copy
import re
from collections.abc import Sequence
from typing import Any

from esquema import Documento
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.noticias import filtro

MAX_PALABRAS_FRASE = 25
FIABILIDAD = "B"
# Autoridades competentes: si atribuyen el suceso a un dron, la presencia está confirmada.
AUTORIDADES_DEL_DRON = frozenset(
    {
        "gobierno", "ministerio", "fuerzas_armadas", "policia", "navegacion_aerea",
        "aeropuerto", "fiscalia", "aviacion_civil",
    }
)  # fmt: skip
# Declaraciones que, de una autoridad competente, atribuyen el suceso (un dron) a lo que pasó.
_CON_DRONES = frozenset({"incidente", "autoria"})
# Formas que el filtro de noticias no recoge por la declinación (genitivo griego) o por ser
# el adjetivo y no el nombre («bezpilotní letoun»).
_DRONES_DECLINADOS = re.compile(
    r"(?<!\w)(μη επανδρωμέν\w*|bezpilot\w*|беспилот\w*|безпілот\w*)", re.IGNORECASE
)
# La autoridad lo deja abierto: posible, presunto o sospechoso; objeto no identificado; se
# investiga si era un dron; no confirma que lo fuera.
ABIERTO = re.compile(
    r"(?<!\w)(?:possibl\w*|posibl\w*|possív\w*|mogelijk\w*|möglich\w*|eventuel\w*|"
    r"mulig\w*|möjlig\w*|mahdollis\w*|możliw\w*|ewentualn\w*|pravděpodob\w*|tikėtin\w*|"
    r"galim\w*|iespējam\w*|võimalik\w*|πιθαν\w*|можлив\w*|возможн\w*|"
    r"mutma\w*|vermut\w*|vermoed\w*|presunt\w*|présum\w*|supuest\w*|alleged\w*|"
    r"suspect\w*|sospech\w*|verdacht\w*|podejrzan\w*|misstänk\w*|mistænk\w*|mistenk\w*|"
    r"formod\w*|mistank\w*|misstank\w*|afkræft\w*|hverken|denken|denkt|resembl\w*|parecid\w*|przypominaj\w*|unidentified|"
    r"no identificad\w*|non identifi\w*|niet[- ]ge(?:ï|i)dentificeerd\w*|"
    r"nicht identifiziert\w*|unbekannte[snm]? (?:flug)?objekt\w*|onbekend\w* object\w*|"
    r"niezidentyfikowan\w*|oidentifier\w*|uidentificer\w*|uidentifiser\w*|"
    r"investigat\w* whether|se investiga si|investiga si|onderzo\w* of|ermittel\w* ob|"
    r"unclear|no está claro|nicht klar|niet duidelijk|pas clair|"
    r"(?:no|not|nicht|niet|pas|ikke|inte|nie)\s+(?:\w+\s+){0,3}"
    r"(?:confirm|bestätig|bevestig|bekræft|bekräft|potwierdz|confirmar)\w*)(?!\w)",
    re.IGNORECASE,
)
# Confianza de la afirmación de presencia que deja la regla: la frase es literal, comprobada
# en el texto de la noticia (validas), y la regla no interpreta nada más.
CONFIANZA_REGLA = 1.0
_CONFIRMAN = frozenset({"incidente", "drones"})


def _normal(texto: str) -> str:
    return " ".join(texto.lower().split())


def validas(declaraciones: Sequence[dict[str, Any]], textos: Sequence[str]) -> list[dict[str, Any]]:
    """Las declaraciones cuya frase está en el texto de su fuente, con la frase recortada."""
    resultado = []
    for declaracion in declaraciones:
        numero = declaracion.get("fuente")
        frase = str(declaracion.get("frase", ""))
        if not isinstance(numero, int) or not 1 <= numero <= len(textos) or not frase.strip():
            continue
        if _normal(frase) not in _normal(textos[numero - 1]):
            continue
        palabras = frase.split()[:MAX_PALABRAS_FRASE]
        resultado.append({**declaracion, "frase": " ".join(palabras)})
    return resultado


def habla_de_drones(frase: str) -> bool:
    return bool(filtro().dron.search(frase) or _DRONES_DECLINADOS.search(frase))


# La sospecha de una infracción («mistanke om ulovlig droneflyvning», «suspected of illegally
# flying a drone») no deja abierto que fuera un dron: lo que se sospecha es que fuera ilegal.
_INFRACCION = re.compile(
    r"^\W*(?:\w+\W+){0,2}(?:ulovlig\w*|olaglig\w*|ulovlig|illegal\w*|ilegal\w*|"
    r"unerlaubt\w*|verboten\w*|illegaal|nielegaln\w*|unlawful\w*|unauthori[sz]ed)",
    re.IGNORECASE,
)


def abierto(*textos: str) -> bool:
    """Si alguno de los textos deja abierto que fuera un dron."""
    for texto in textos:
        for duda in ABIERTO.finditer(texto or ""):
            if not _INFRACCION.search(texto[duda.end() : duda.end() + 40]):
                return True
    return False


def confirma_dron(declaracion: dict[str, Any], contexto: str = "") -> bool:
    """Si la autoridad da por hecho el dron: afirma que hubo drones (drones), o una autoridad
    competente confirma o atribuye el suceso (incidente, autoria), que es un suceso de dron.
    No si la frase o el `contexto` (la frase de la noticia que la cita) lo dejan abierto."""
    if abierto(str(declaracion.get("frase", "")), contexto):
        return False
    if declaracion["afirma"] == "drones":
        return True
    return (
        declaracion["afirma"] in _CON_DRONES
        and declaracion.get("categoria") in AUTORIDADES_DEL_DRON
    )


def afirmacion_presencia(fuente_id: str) -> Documento:
    """Quién confirma la presencia del dron: queda en el incidente y en su historial."""
    return {
        "campo": "presencia_dron",
        "valor": "confirmada",
        "fuente_id": fuente_id,
        "confianza_extraccion": CONFIANZA_REGLA,
    }


def confirmar_presencia(incidente: Documento, fuente_id: str, expresa: bool = False) -> bool:
    """Deja la presencia confirmada por esa fuente. False si ya lo estaba, o si estaba
    descartada y la declaración no afirma expresamente los drones."""
    actual = incidente.get("presencia_dron")
    if actual == "confirmada" or (actual == "descartada" and not expresa):
        return False
    incidente["presencia_dron"] = "confirmada"
    afirmacion = afirmacion_presencia(fuente_id)
    if afirmacion not in incidente.get("afirmaciones", []):
        incidente["afirmaciones"] = [*incidente.get("afirmaciones", []), afirmacion]
    return True


def fuente(declaracion: dict[str, Any], noticia: Documento, numero: int) -> Documento:
    resultado = copy.deepcopy(noticia)
    resultado.update({
        "id": f"{noticia['id']}-declaracion-{numero}",
        "medio": f"{declaracion['autoridad']} (declaración oficial citada en {noticia['medio']})",
        "fiabilidad": FIABILIDAD,
        "credibilidad": int(Credibilidad.CONFIRMADO),
        "frase_origen": declaracion["frase"],
        "replicas": 0,
        "campos_respaldados": ["estado", "presencia_dron"],
        "es_autoridad": True,
    })  # fmt: skip
    return resultado


def _transitar(incidente: Documento, destino: Estado, origen: Documento) -> None:
    if incidente["estado"]["actual"] == destino:
        return
    fuentes = {f["id"]: f for f in incidente["fuentes"]}
    # Un cambio que la máquina de estados no permite (revertir un desmentido de más
    # fiabilidad, atribuir sin confirmar) se deja sin hacer.
    with contextlib.suppress(TransicionNoPermitida):
        incidente["estado"] = transitar(
            incidente["estado"], destino, origen["fecha"], origen["id"], fuentes
        )


def aplicar(
    incidente: Documento, declaraciones: Sequence[dict[str, Any]], enviadas: Sequence[str]
) -> Documento:
    """El incidente con las declaraciones como fuentes y sus cambios de estado y presencia."""
    resultado = copy.deepcopy(incidente)
    por_enlace = {f["enlace"]: f for f in resultado["fuentes"]}
    nuevas: list[tuple[dict[str, Any], Documento]] = []
    for numero, declaracion in enumerate(declaraciones, 1):
        noticia = por_enlace.get(enviadas[declaracion["fuente"] - 1])
        pais = str(declaracion.get("pais") or "").strip().upper()
        if noticia is None:
            continue
        if pais and pais != resultado["lugar"]["pais"]:
            continue
        nuevas.append((declaracion, fuente(declaracion, noticia, numero)))
    resultado["fuentes"] = [*resultado["fuentes"], *(f for _, f in nuevas)]
    # Primero lo que confirma y después lo que desmiente o atribuye.
    orden = {"incidente": 0, "drones": 0, "sin_drones": 1, "niega_incidente": 2, "autoria": 3}
    por_frase: list[Documento] = []
    for declaracion, origen in sorted(nuevas, key=lambda n: orden[n[0]["afirma"]]):
        afirma = declaracion["afirma"]
        if afirma in _CONFIRMAN:
            _transitar(resultado, Estado.CONFIRMADO, origen)
        contexto = str(por_enlace.get(origen["enlace"], {}).get("frase_origen", ""))
        if afirma == "drones" and confirma_dron(declaracion, contexto):
            # Lo afirma expresamente: vale aunque la ficha lo hubiera descartado.
            confirmar_presencia(resultado, origen["id"], expresa=True)
        elif confirma_dron(declaracion, contexto):
            por_frase.append(origen)
        if afirma == "sin_drones":
            resultado["presencia_dron"] = "descartada"
        elif afirma == "niega_incidente":
            _transitar(resultado, Estado.DESMENTIDO, origen)
            if resultado["estado"]["actual"] == Estado.DESMENTIDO:
                resultado["control"]["motivo_desmentido"] = (
                    f"{declaracion['autoridad']}: «{declaracion['frase']}»"
                )
        elif afirma == "autoria" and declaracion["categoria"] == "gobierno":
            actor = str(declaracion.get("autor", "")).strip()
            if actor and resultado["estado"]["actual"] == Estado.CONFIRMADO:
                _transitar(resultado, Estado.ATRIBUIDO, origen)
            if actor and resultado["estado"]["actual"] == Estado.ATRIBUIDO:
                resultado["atribucion"] = {
                    "actor": actor,
                    "autoridad": declaracion["autoridad"],
                    "fecha": origen["fecha"],
                }
    # La frase que nombra drones confirma su presencia si nadie los descartó y el incidente no
    # está desmentido: una autoridad que dice que no pasó nada pesa más que la que lo cuenta.
    if resultado["estado"]["actual"] != Estado.DESMENTIDO:
        for origen in por_frase:
            if confirmar_presencia(resultado, origen["id"]):
                break
    return resultado
