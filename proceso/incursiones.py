"""Los cruces que cuenta solo el parte de la Fuerza Aérea de Ucrania no son incidentes europeos.

Cuando un parte dice que drones del ataque salieron hacia otro país («Один безпілотник увійшов в
повітряний простір Румунії»), el cruce se guarda dentro del ataque (`cruces` y `cruces_parte`,
con la frase literal del parte) y la web lo muestra como cruce declarado por Ucrania. La Fuerza
Aérea no es autoridad sobre el espacio aéreo de otro país: su parte no confirma por sí solo que
hubo un dron en Rumanía o en Moldavia, y el cruce no cuenta en el total europeo ni en las cifras
por país. Pasa a ser un incidente europeo solo si lo cuenta una fuente del país afectado; entonces
entra por la vía normal de las noticias y proceso/cruces.py lo enlaza con su ataque.

Hasta el 4 de octubre de 2026 cada cruce de un ataque daba de alta un incidente «Drones del
ataque ruso contra Ucrania cruzan a …» con el parte como única fuente (versiones incursion/1 e
incursion/2). Al enlazar las incursiones europeas con su ataque (proceso/cruces.py), cada una
añadía su país a los cruces del ataque y la recogida siguiente creaba con ello una copia del
incidente. Esas altas se retiran aquí, con su motivo, y no se crea ninguna más.
"""

from datetime import datetime, timedelta

from almacen.base import Almacen
from esquema import Documento
from proceso.extraccion import retirar as retirar_incidente
from proceso.incidentes import activo

# Versiones de las altas desde el parte, que ya no se crean.
VERSIONES = frozenset({"incursion/1", "incursion/2"})
# Otro incidente del mismo país a menos de este tiempo del parte es el mismo cruce.
VENTANA_PAREJA = timedelta(hours=30)
NOMBRES_ES = {
    "MD": "Moldavia", "RO": "Rumanía", "PL": "Polonia", "HU": "Hungría", "SK": "Eslovaquia",
}  # fmt: skip


def es_del_parte(incidente: Documento) -> bool:
    """Alta hecha desde el parte ucraniano, sin otra fuente que el propio parte."""
    return incidente.get("control", {}).get("version_extractor") in VERSIONES and all(
        f["id"].startswith("kpszsu-") for f in incidente["fuentes"]
    )


def _momento(instante: Documento) -> datetime:
    return datetime.fromisoformat(instante["valor"].replace("Z", "+00:00"))


def pareja(incidente: Documento, otros: list[Documento]) -> Documento | None:
    """El incidente del mismo país y la misma noche que cuenta una fuente propia: el enlazado
    con el mismo ataque o, si no, el más cercano a menos de 30 horas del parte."""
    pais = incidente["lugar"]["pais"]
    ataque = incidente.get("ataque", {}).get("id")
    candidatos = [o for o in otros if o["lugar"]["pais"] == pais]
    enlazados = [o for o in candidatos if ataque and o.get("ataque", {}).get("id") == ataque]
    if enlazados:
        return min(enlazados, key=lambda o: o["id"])
    fin = _momento(incidente["tiempo"].get("fin", incidente["tiempo"]["inicio"]))
    cerca = [
        (abs(_momento(o["tiempo"]["inicio"]) - fin), o["id"], o) for o in candidatos
        if abs(_momento(o["tiempo"]["inicio"]) - fin) < VENTANA_PAREJA
    ]  # fmt: skip
    return min(cerca, key=lambda x: (x[0], x[1]))[2] if cerca else None


def motivo(incidente: Documento, otros: list[Documento], ataques: dict[str, Documento]) -> str:
    pais = incidente["lugar"]["pais"]
    nombre = NOMBRES_ES.get(pais, pais)
    ataque_id = incidente.get("ataque", {}).get("id")
    autoridad = (
        f"la Fuerza Aérea de Ucrania no es autoridad sobre el espacio aéreo de {nombre} y su "
        "parte no confirma por sí solo un dron allí"
    )
    buena = pareja(incidente, otros)
    if buena is not None:
        enlace = (
            f"; el enlace con el ataque {ataque_id} queda en {buena['id']}" if ataque_id else ""
        )
        return (
            f"duplicado de {buena['id']}, el mismo cruce a {nombre} contado por su fuente: este "
            f"incidente salía solo del parte ucraniano ({autoridad}){enlace}"
        )
    # Sin enlace, el ataque es el del propio parte.
    ataque = ataques.get(ataque_id or "") or next(
        (a for a in ataques.values()
         if {f["id"] for f in a["fuentes"]} & {f["id"] for f in incidente["fuentes"]}),
        None,
    )  # fmt: skip
    ataque_id = ataque["id"] if ataque else ataque_id
    declarados = (ataque or {}).get("cruces_parte") or []
    if any(c["pais"] == pais for c in declarados):
        return (
            f"cruce declarado solo por Ucrania: queda en la ficha del ataque {ataque_id} como "
            f"cruce declarado por Ucrania, con la frase del parte; no es un incidente europeo "
            f"({autoridad})"
        )
    return f"el parte no dice que hubiera un cruce a {nombre}: no es un incidente ({autoridad})"


def retirar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Retira, con su motivo, las altas que salían solo del parte. Devuelve cuántas retira."""
    incidentes = almacen.incidentes()
    otros = [i for i in incidentes if activo(i) and not es_del_parte(i)]
    ataques = {a["id"]: a for a in almacen.ataques_ucrania()}
    retirados = 0
    for incidente in incidentes:
        if not activo(incidente) or not es_del_parte(incidente):
            continue
        texto = motivo(incidente, otros, ataques)
        if retirar_incidente(almacen, incidente["id"], texto, ahora, modelos):
            retirados += 1
    return retirados
