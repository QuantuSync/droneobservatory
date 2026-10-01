"""Declaraciones oficiales citadas por la prensa: cómo cambian el incidente.

Las autoridades confirman los incidentes en declaraciones a la prensa, no en sus
webs. Cada declaración que el extractor encuentra en una noticia (con su frase
literal, que tiene que estar en el texto enviado) se registra como fuente
«declaración oficial citada», de fiabilidad B, con el enlace a la noticia. Reglas:

- incidente o drones: pasa a confirmado (la autoridad dice que ocurrió).
- drones: presencia_dron confirmada; solo si la frase no habla de avisos recibidos
  («la policía recibió avisos de drones» no confirma nada).
- incidente o autoria de un gobierno, ministerio, fuerzas armadas, policía o gestor del
  espacio aéreo cuya frase dice expresamente que hubo drones: presencia_dron confirmada
  también. Una atribución oficial que habla de drones afirma que los hubo; la que confirma
  un cierre sin nombrar drones no dice nada del dron. Cada confirmación así deja una
  afirmación de presencia_dron con la fuente que la provoca.
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
# Autoridades cuya palabra de que hubo drones confirma su presencia: gobierno, ministerio,
# fuerzas armadas, policía y gestor del espacio aéreo. El aeropuerto no: confirma el cierre.
AUTORIDADES_DEL_DRON = frozenset(
    {"gobierno", "ministerio", "fuerzas_armadas", "policia", "navegacion_aerea"}
)
# Declaraciones cuya frase, si nombra drones, afirma que los hubo.
_CON_DRONES = frozenset({"incidente", "autoria"})
# Formas que el filtro de noticias no recoge por la declinación (genitivo griego) o por ser
# el adjetivo y no el nombre («bezpilotní letoun»).
_DRONES_DECLINADOS = re.compile(
    r"(?<!\w)(μη επανδρωμέν\w*|bezpilot\w*|беспилот\w*|безпілот\w*)", re.IGNORECASE
)
# Frases que nombran drones sin afirmar que los hubo: niegan o no lo saben («no hemos
# confirmado ni descartado que fueran drones»), lo suponen («si creemos ver un dron»,
# «un objeto parecido a un dron») o cuentan un aviso recibido («recibimos información de
# que se vio un dron»). Solo para la regla de la frase: el filtro de avisos de `cuenta`
# sigue igual para lo demás.
_SIN_AFIRMAR = re.compile(
    r"(?<!\w)(ikke|hverken|inte|nicht|kein\w*|not|nie|niet|geen|nijedn\w*|δεν|не|"
    r"afkræft\w*|denken|possibl\w*|posibil\w*|suspect\w*|mutma\w*|vermut\w*|mulig\w*|"
    r"formod\w*|mistænk\w*|misstänk\w*|mistank\w*|misstank\w*|podejrzan\w*|przypominaj\w*|resembl\w*|presunt\w*|"
    r"sospech\w*|présum\w*|prijav\w*|pranešim\w*|informacij\w*|ilmoitu\w*|zgłosi\w*|"
    r"signalement\w*|segnalazion\w*)(?!\w)",
    re.IGNORECASE,
)
# Confianza de la afirmación de presencia que deja la regla: la frase es literal, comprobada
# en el texto de la noticia (validas), y la regla no interpreta nada más.
CONFIANZA_REGLA = 1.0
# Avisos o llamadas recibidos por la autoridad: no son una afirmación suya.
_AVISOS = re.compile(
    r"\b(avisos?|llamadas|report(s|ed)?|tips?|meldinger|henvendelser|anmeldelser|"
    r"Hinweise|Meldungen|Anrufe|zgłosze\w*|sesizări|meldingen)\b",
    re.IGNORECASE,
)
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


def cuenta(declaracion: dict[str, Any]) -> bool:
    """Si la declaración es una afirmación de la autoridad y no un aviso que recibió."""
    return not (declaracion["afirma"] in _CONFIRMAN and _AVISOS.search(declaracion["frase"]))


def habla_de_drones(frase: str) -> bool:
    return bool(filtro().dron.search(frase) or _DRONES_DECLINADOS.search(frase))


def confirma_dron(declaracion: dict[str, Any]) -> bool:
    """Si la declaración afirma que hubo drones: lo dice expresamente (drones), o es la
    confirmación o la atribución de una autoridad del dron que los nombra. Un aviso recibido
    no cuenta."""
    if not cuenta(declaracion):
        return False
    if declaracion["afirma"] == "drones":
        return True
    frase = str(declaracion.get("frase", ""))
    return (
        declaracion["afirma"] in _CON_DRONES
        and declaracion.get("categoria") in AUTORIDADES_DEL_DRON
        and habla_de_drones(frase)
        and not _SIN_AFIRMAR.search(frase)
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
        if noticia is None or not cuenta(declaracion):
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
        if afirma == "drones" and confirma_dron(declaracion):
            # Lo afirma expresamente: vale aunque la ficha lo hubiera descartado.
            confirmar_presencia(resultado, origen["id"], expresa=True)
        elif confirma_dron(declaracion):
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
