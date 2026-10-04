"""Incursiones en países fronterizos enlazadas con el ataque ruso contra Ucrania de su noche.

Un incidente europeo de Rumanía, Moldavia, Polonia, Lituania, Letonia, Estonia, Bulgaria,
Eslovaquia o Hungría (incursión o sobrevuelo de drones de un Estado, o cualquier tipo si la
fuente lo relaciona con el ataque) se enlaza con el ataque de la Fuerza Aérea de Ucrania (sentido
RU→UA, sin los tramos ya sumados en otro) cuyo periodo contiene el inicio del incidente:

- **por la fuente** (`por: fuente`): la fuente la relaciona con el ataque contra Ucrania («durante
  ataque a Ucrania», «atacul rusesc asupra Ucrainei», «attack on Ukraine»);
- **por la fecha** (`por: fecha`): coincide en fecha y la incursión viene de Ucrania: la fuente
  lo dice («din Ucraina», «from Ukraine», «desde Ucrania») o, en Rumanía y Moldavia, que solo
  reciben drones del ataque a través de Ucrania, el dron es de un Estado, entró desde fuera o la
  fuente dice que es ruso (Shahed, Gerbera).

No se enlaza lo que viene de Bielorrusia («procedente de Bielorrusia», «from Belarus»), los
drones ucranianos (salvo que la fuente los relacione con el ataque) ni lo que no tiene relación
con un ataque (globos de contrabando sobre Lituania, drones marinos en Constanza). El enlace va
en los dos sentidos: el incidente lleva `ataque` (id, noche y por qué) y el ataque lista el
cruce de su país (`cruces[].incidentes`); si el parte no declaró ese cruce, se añade con el
número de drones del incidente. Enlazar nunca crea un incidente: un cruce que solo cuenta el parte
ucraniano queda en el ataque como cruce declarado por Ucrania (proceso/incursiones.py). Se
recalcula entero en cada recogida horaria (después de rehacer partes e incidentes) y solo se
guarda lo que cambia, con su motivo en el historial.
"""

import copy
import json
import re
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from esquema import Documento
from proceso.ataques import jornada
from proceso.impactos_guerra import Ataques

if TYPE_CHECKING:
    from almacen.base import Almacen

PAISES = frozenset({"RO", "MD", "PL", "LT", "LV", "EE", "BG", "SK", "HU"})
# Solo reciben drones del ataque ruso a través de Ucrania.
VECINOS_DEL_SUR = frozenset({"RO", "MD"})
TIPOS = frozenset({"incursion", "sobrevuelo"})
_BIELORRUSIA = (
    r"(?:bielorrus\w*|belarus\w*|białoru\w*|bialoru\w*|baltarus\w*|baltkriev\w*|valgeven\w*|"
    r"білорус\w*|беларус\w*|belarús\w*|belorus\w*)"
)
# Viene de Bielorrusia: «procedente de Bielorrusia», «from Belarus», «iš Baltarusijos».
DESDE_BIELORRUSIA = re.compile(
    r"(?:desde|from|din|dinspre|z|ze|iš|no|з|из|aus|depuis|procedente\s+de|proveniente\s+de|"
    r"entered\s+from|came\s+from)\s+(?:territori\w*\s+)?(?:de\s+|of\s+)?" + _BIELORRUSIA,
    re.IGNORECASE,
)
SIN_ATAQUE = re.compile(
    r"globo|balloon|balion|balon\b|balonu|baliona|kontraband|contraband|contrabando|сигарет|"
    r"cigaret|papiros|dron(?:es)? (?:naval|marino)|naval drone|sea drone|dron(?:ă|a) naval|"
    r"drone navale|dron marino ucraniano",
    re.IGNORECASE,
)
MAR = re.compile(
    r"puerto de constan|port\w* (?:of )?constan|mar negro|black sea|marea neagr|plataforma|"
    r"marítim|maritim|en el mar\b|in the sea\b",
    re.IGNORECASE,
)
# Un dron ucraniano no es del ataque ruso (salvo que la fuente lo relacione con él).
DRON_UCRANIANO = re.compile(
    r"dron(?:es)?\s+(?:\w+\s+)?ucranian|ukrainian\s+(?:\w+\s+)?drone|dron\w*\s+ucrainean",
    re.IGNORECASE,
)
# Dron del ataque ruso: «dron ruso», «Shahed», «Geran», «Gerbera».
DRON_RUSO = re.compile(
    r"dron(?:es)?\s+(?:\w+\s+)?rus[oa]s?\b|russian\s+(?:\w+\s+)?drones?|drone?\w*\s+ruse\w*|"
    r"російськ\w*\s+(?:ударн\w+\s+)?(?:дрон|безпілот|бпла)|"
    r"российск\w*\s+(?:ударн\w+\s+)?(?:дрон|беспилот|бпла)|shahed|шахед|geran|герань|"
    r"gerbera|гербер",
    re.IGNORECASE,
)
_UCRANIA = r"(?:ucrani\w*|ukrain\w*|ucrain\w*|україн\w*|украин\w*|ukrajin\w*|ukrayn\w*|ukrain)"
RELACION_ATAQUE = re.compile(
    r"(?:ataque|attack|atac|атак|angriff|atak|ataka|ataku|uzbrukum|rünnak|attaque)\w*"
    r"[^.!?\n]{0,80}?" + _UCRANIA + r"|" + _UCRANIA + r"[^.!?\n]{0,40}?"
    r"(?:ataque|attack|atac|атак|angriff|atak|ataka|ataku|uzbrukum|rünnak|attaque)\w*|"
    r"izmail|ismail|reni\b|portur\w* ucrainen\w*|ukrainian ports?|puertos? ucranian\w*",
    re.IGNORECASE,
)
DESDE_UCRANIA = re.compile(
    r"(?:desde|from|din|dinspre|z|ze|iš|no|з|из|aus|depuis|from the direction of)\s+"
    r"(?:territori\w*\s+)?(?:de\s+|of\s+|al\s+)?" + _UCRANIA,
    re.IGNORECASE,
)
# Margen alrededor del periodo del ataque según la precisión del inicio del incidente.
MARGEN = {"minuto": timedelta(hours=2), "hora": timedelta(hours=3),
          "aproximada": timedelta(hours=6)}  # fmt: skip
MOTIVO = (
    "incursión enlazada con el ataque ruso contra Ucrania de su noche (proceso/cruces.py): la "
    "fuente la relaciona con el ataque o coincide en fecha y viene de Ucrania"
)
KYIV_DESFASE = timedelta(hours=3)
FRASES = Path(__file__).resolve().parent.parent / "configuracion" / "frases_cruces.json"


def _leer(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(UTC)


def _textos(incidente: Documento) -> str:
    partes = [incidente.get("titulo", {}).get(c, "") for c in ("es", "en")]
    partes += [f.get("frase_origen", "") for f in incidente.get("fuentes", [])]
    partes += [a.get("cita", "") for a in incidente.get("afirmaciones_publicas", [])]
    partes += [a.get("frase", "") for a in incidente.get("afirmaciones", [])]
    return "\n".join(p for p in partes if p)


def _ataque_de(
    ataques: Ataques, incidente: Documento
) -> str | None:  # fmt: skip
    """El ataque RU→UA de la noche del incidente: el que contiene su inicio (con margen según
    la precisión) o, si solo se sabe el día, la noche que acaba ese día (la que contiene sus
    02:00 en Kiev)."""
    inicio = incidente["tiempo"]["inicio"]
    momento = _leer(inicio["valor"])
    if inicio["precision"] == "dia":
        dos = datetime.combine(momento.date(), datetime.min.time(), tzinfo=UTC) - KYIV_DESFASE
        periodo = ataques.que_contiene("RU_UA", dos + timedelta(hours=2))
        return periodo.id if periodo else None
    periodo = ataques.que_contiene("RU_UA", momento)
    if periodo is not None:
        return periodo.id
    margen = MARGEN.get(inicio["precision"], timedelta(hours=2))
    cerca = [
        p for p in ataques.por_sentido.get("RU_UA", [])
        if p.inicio - margen <= momento <= p.fin + margen
    ]  # fmt: skip
    if not cerca:
        return None
    return min(cerca, key=lambda p: (min(abs(p.inicio - momento), abs(p.fin - momento)), p.id)).id


def enlace(incidente: Documento, ataques: Ataques) -> tuple[str, str] | None:
    """(id del ataque, por qué) si la incursión forma parte de un ataque; si no, None."""
    if "fusionado_en" in incidente or "retirado" in incidente:
        return None
    if incidente["lugar"]["pais"] not in PAISES:
        return None
    textos = _textos(incidente)
    if DESDE_BIELORRUSIA.search(textos) or SIN_ATAQUE.search(textos):
        return None
    pruebas = incidente.get("pruebas", {})
    relacionado = bool(RELACION_ATAQUE.search(textos))
    ruso = bool(DRON_RUSO.search(textos))
    # Un dron ucraniano desviado (sobre los países bálticos, en los ataques ucranianos contra
    # Rusia) no es del ataque ruso, salvo que sea un Shahed mal atribuido.
    titulo = " ".join(incidente.get("titulo", {}).get(c, "") for c in ("es", "en"))
    if DRON_UCRANIANO.search(titulo) or (DRON_UCRANIANO.search(textos) and not ruso):
        return None
    # Fuera de Rumanía y Moldavia (donde los drones también llegan desde Bielorrusia o en los
    # ataques ucranianos contra Rusia), el titular tiene que decir que el dron es ruso o que
    # viene de Ucrania: las fuentes de esos incidentes mezclan titulares de otros sucesos.
    if incidente["lugar"]["pais"] not in VECINOS_DEL_SUR and not (
        DRON_RUSO.search(titulo) or DESDE_UCRANIA.search(titulo)
    ):
        return None
    # A Rumanía y Moldavia solo llegan drones del ataque a través de Ucrania: basta con que
    # el dron sea de un Estado o venga de fuera, o que la fuente diga que es ruso.
    del_sur = incidente["lugar"]["pais"] in VECINOS_DEL_SUR and (
        pruebas.get("dron_estatal") is True or pruebas.get("entrada_exterior") is True
        or bool(DRON_RUSO.search(textos))
    )  # fmt: skip
    # En el puerto de Constanza y en el mar llegan también drones marinos a la deriva: solo
    # con la fuente que lo relaciona con el ataque.
    if MAR.search(titulo) and not relacionado:
        return None
    desde_ucrania = bool(DESDE_UCRANIA.search(textos)) or del_sur
    if not relacionado and (incidente["tipo"] not in TIPOS or not desde_ucrania):
        return None
    ataque = _ataque_de(ataques, incidente)
    if ataque is None:
        return None
    return ataque, "fuente" if relacionado else "fecha"


def enlazar(almacen: "Almacen", ahora: datetime, modelos: frozenset[str]) -> dict[str, int]:
    """Recalcula los enlaces y guarda lo que cambia en incidentes y ataques."""
    todos = almacen.ataques_ucrania()
    por_id = {a["id"]: a for a in todos}
    ataques = Ataques(todos)
    enlaces: dict[str, tuple[str, str]] = {}
    incidentes = almacen.incidentes()
    for incidente in incidentes:
        hallado = enlace(incidente, ataques)
        if hallado is not None:
            enlaces[incidente["id"]] = hallado
    resumen = {"enlazados": len(enlaces), "incidentes_cambiados": 0, "ataques_cambiados": 0}
    for incidente in incidentes:
        hallado = enlaces.get(incidente["id"])
        nuevo = copy.deepcopy(incidente)
        if hallado is None:
            nuevo.pop("ataque", None)
        else:
            ataque_id, por = hallado
            nuevo["ataque"] = {
                "id": ataque_id, "jornada": jornada(por_id[ataque_id]["periodo"]), "por": por,
            }  # fmt: skip
        if nuevo == incidente:
            continue
        almacen.guardar_incidente(nuevo, ahora, modelos)
        almacen.anotar_motivo(
            "incidentes", incidente["id"], {"ataque": incidente.get("ataque")},
            {"ataque": nuevo.get("ataque")}, MOTIVO,
        )  # fmt: skip
        resumen["incidentes_cambiados"] += 1
    por_ataque: dict[str, list[Documento]] = {}
    for incidente in incidentes:
        if incidente["id"] in enlaces:
            por_ataque.setdefault(enlaces[incidente["id"]][0], []).append(incidente)
    for ataque in todos:
        nuevo = copy.deepcopy(ataque)
        nuevo["cruces"] = cruces_con_incidentes(ataque, por_ataque.get(ataque["id"], []))
        # Lo que declaró el parte, para rehacer los cruces sin las incursiones de otra hora.
        if nuevo["cruces"] != cruces_del_parte(ataque) or "cruces_parte" in ataque:
            nuevo["cruces_parte"] = cruces_del_parte(ataque)
        if nuevo == ataque:
            continue
        almacen.guardar_ataque_ucrania(nuevo, ahora)
        almacen.anotar_motivo(
            "ataques_ucrania", ataque["id"], {"cruces": ataque.get("cruces")},
            {"cruces": nuevo["cruces"]}, MOTIVO,
        )  # fmt: skip
        resumen["ataques_cambiados"] += 1
    return resumen


@cache
def frases_guardadas(ruta: Path = FRASES) -> dict[str, dict[str, str]]:
    """La frase de los cruces de los partes guardados antes de que el lector la guardara."""
    datos: dict[str, dict[str, str]] = json.loads(ruta.read_text(encoding="utf-8"))["frases"]
    return datos


def cruces_del_parte(ataque: Documento) -> list[Documento]:
    """Los cruces que declaró el parte (`cruces_parte`), con la frase que los dice; en un ataque
    guardado antes de que existiera ese campo, sus cruces tal cual (aún no tenían incidentes
    añadidos)."""
    declarados = ataque.get("cruces_parte")
    if declarados is None:
        declarados = ataque.get("cruces") or []
    frases: dict[str, str] = {}
    for fuente in ataque.get("fuentes", []):
        frases |= frases_guardadas().get(fuente["id"], {})
    return [
        {**c, "frase": frases[c["pais"]]} if "frase" not in c and c["pais"] in frases else dict(c)
        for c in declarados
    ]


def cruces_con_incidentes(ataque: Documento, incidentes: list[Documento]) -> list[Documento]:
    """Los cruces del parte con sus incidentes, y los países que el parte no declaró pero tienen
    una incursión enlazada (con el número de drones del incidente). Los cruces que solo existían
    por un incidente que ya no se enlaza desaparecen."""
    propios = [{k: v for k, v in c.items() if k != "incidentes"} for c in cruces_del_parte(ataque)]
    por_pais: dict[str, list[Documento]] = {}
    for incidente in sorted(incidentes, key=lambda i: i["id"]):
        por_pais.setdefault(incidente["lugar"]["pais"], []).append(incidente)
    resultado = []
    for cruce in propios:
        ids = [i["id"] for i in por_pais.pop(cruce["pais"], [])]
        resultado.append({**cruce, **({"incidentes": ids} if ids else {})})
    for pais, lista in sorted(por_pais.items()):
        numero: Any = lista[0].get("drones", {}).get("numero", "desconocido")
        if len(lista) > 1 or not isinstance(numero, dict):
            numero = "desconocido" if len(lista) > 1 or numero is None else numero
        resultado.append({"pais": pais, "numero": numero,
                          "incidentes": [i["id"] for i in lista]})  # fmt: skip
    return resultado
