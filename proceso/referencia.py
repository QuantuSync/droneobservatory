"""El conjunto de referencia: unas 50 fichas cuyo valor correcto de cada dato está comprobado
contra el texto completo de sus fuentes (tests/referencia/fichas.json).

`valores` saca de una ficha los datos que se comparan, con las mismas funciones que los deciden
al publicar (reglas, coherencia del historial, zona, cabecera). La prueba de la CI los saca de la
copia pública guardada de cada ficha (tests/referencia/fichas/) y el control de fichas del
servidor, de la ficha de la base; las dos comparan con la referencia y solo admiten las
discrepancias conocidas (tests/referencia/discrepancias.json), una lista que solo puede encoger.
La referencia solo se cambia con una cita nueva de una fuente, nunca para que pase una prueba.
"""

import copy
import json
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import auditoria_fichas, coherencia, decidir, fechas, incidentes, zona

DIRECTORIO = Path(__file__).resolve().parent.parent / "tests" / "referencia"
CAMPOS = (
    "estado", "presencia_dron", "tipo", "objetivo", "pais", "lugar", "inicio", "zona",
    "drones", "cabecera",
)  # fmt: skip
# Lo que se guarda de cada ficha: solo campos que ya se publican, más las pruebas (de qué
# depende el tipo) y el lugar con su punto (que el mapa ya dibuja).
CAMPOS_COPIA = (
    "id", "titulo", "tipo", "estado", "presencia_dron", "presencia_historial", "objetivo",
    "lugar", "tiempo", "drones", "consecuencias", "respuesta", "pruebas", "relacionados",
    "nombres", "fuentes",
)  # fmt: skip
CAMPOS_FUENTE = (
    "id", "enlace", "medio", "fecha", "idioma", "frase_origen", "traduccion", "es_autoridad",
    "fiabilidad", "credibilidad", "copia_archivada", "documento_oficial", "campos_respaldados",
)  # fmt: skip


def copia_publica(documento: Documento) -> Documento:
    """Lo que se guarda en el repositorio de una ficha de la referencia."""
    copia = {c: copy.deepcopy(documento[c]) for c in CAMPOS_COPIA if c in documento}
    copia["fuentes"] = [
        {c: f[c] for c in CAMPOS_FUENTE if c in f} for f in documento.get("fuentes", [])
    ]
    # Lo que cada fuente afirma de la presencia: con ello la decide proceso/decidir.py.
    copia["afirmaciones"] = [
        {c: a[c] for c in ("campo", "valor", "fuente_id")}
        for a in documento.get("afirmaciones", [])
        if a.get("campo") == "presencia_dron"
    ]
    return copia


def _numero(drones: Documento | None) -> Any:
    numero = (drones or {}).get("numero")
    if isinstance(numero, dict) and numero.get("min") == numero.get("max"):
        return numero.get("min")
    return numero


def valores(documento: Documento) -> dict[str, Any]:
    """Los datos de la ficha tal y como se publican."""
    ficha = incidentes.aplicar_reglas(documento)
    # El estado y la presencia, como los decide el guardado (proceso/decidir.py).
    confirmada = ficha.get("presencia_dron") == "confirmada"
    ficha = coherencia.coherente(decidir.aplicar(ficha, confirmada=confirmada))
    objetivo = ficha.get("objetivo")
    if not objetivo or incidentes.objetivo_es_la_localidad(objetivo, ficha.get("lugar") or {}):
        objetivo = None
    lugar = ficha.get("lugar") or {}
    localidad = ((ficha.get("nombres") or {}).get("localidad") or {}).get("es")
    inicio = (ficha.get("tiempo") or {}).get("inicio")
    return {
        "estado": ficha["estado"]["actual"],
        "presencia_dron": ficha.get("presencia_dron"),
        "tipo": ficha.get("tipo"),
        "objetivo": None
        if objetivo is None
        else {c: objetivo.get(c) for c in ("categoria", "nombre", "oaci") if objetivo.get(c)},
        "pais": lugar.get("pais"),
        "lugar": localidad or lugar.get("localidad"),
        # El día local del lugar del suceso, como se publica (proceso/fechas.dia_local).
        "inicio": fechas.dia_local(inicio, ficha) if inicio and inicio.get("valor") else None,
        "zona": zona.clasificar(ficha)["grupo"],
        "drones": _numero(ficha.get("drones")),
        "cabecera": auditoria_fichas.cabecera(ficha, "es"),
    }


def cargar(directorio: Path = DIRECTORIO) -> tuple[list[Documento], list[Documento]]:
    """(fichas de la referencia, discrepancias conocidas)."""
    fichas = json.loads((directorio / "fichas.json").read_text(encoding="utf-8"))["fichas"]
    conocidas = json.loads((directorio / "discrepancias.json").read_text(encoding="utf-8"))
    return fichas, conocidas["discrepancias"]


def correcto(ficha: Documento, campo: str) -> Any:
    return ficha["valores"][campo]["valor"]


def _igual(campo: str, hoy: Any, bien: Any) -> bool:
    if campo == "objetivo" and isinstance(hoy, dict) and isinstance(bien, dict):
        # El nombre de la instalación se escribe de varias formas: manda la categoría y el OACI.
        return hoy.get("categoria") == bien.get("categoria") and hoy.get("oaci") == bien.get("oaci")
    return bool(hoy == bien)


def diferencias(ficha: Documento, hoy: dict[str, Any]) -> list[Documento]:
    """Los campos de la ficha que no tienen el valor correcto (los que la referencia comprueba)."""
    return [
        {
            "id": ficha["id"],
            "campo": campo,
            "ficha": hoy.get(campo),
            "correcto": correcto(ficha, campo),
        }
        for campo in CAMPOS
        if campo in ficha["valores"] and not _igual(campo, hoy.get(campo), correcto(ficha, campo))
    ]


def comparar(
    documentos: dict[str, Documento], directorio: Path = DIRECTORIO
) -> dict[str, list[Documento]]:
    """{nuevas, corregidas, ausentes}: diferencias que no están en la lista de conocidas, conocidas
    que ya no lo son y fichas de la referencia que no se encuentran."""
    fichas, conocidas = cargar(directorio)
    claves = {(d["id"], d["campo"]) for d in conocidas}
    halladas: set[tuple[str, str]] = set()
    nuevas, ausentes = [], []
    for ficha in fichas:
        documento = documentos.get(ficha["id"])
        if documento is None:
            ausentes.append({"id": ficha["id"]})
            continue
        for diferencia in diferencias(ficha, valores(documento)):
            halladas.add((diferencia["id"], diferencia["campo"]))
            if (diferencia["id"], diferencia["campo"]) not in claves:
                nuevas.append(diferencia)
    vistas = {f["id"] for f in fichas} - {a["id"] for a in ausentes}
    corregidas = [
        d for d in conocidas if d["id"] in vistas and (d["id"], d["campo"]) not in halladas
    ]
    return {"nuevas": nuevas, "corregidas": corregidas, "ausentes": ausentes}


def publicada(documento: Documento) -> Documento:
    """La ficha de la base como la publica la exportación: solo sus fuentes públicas y con los
    nombres de cada versión de la web (exportacion/geojson.py)."""
    from exportacion.geojson import con_afirmaciones, con_nombres

    if "nombres" in documento:
        # Ya es una ficha publicada (las copias de tests/referencia/fichas/).
        return copy.deepcopy(documento)
    return con_nombres(con_afirmaciones(documento) or copy.deepcopy(documento))


def fallos(documentos: Any, directorio: Path = DIRECTORIO) -> list[str]:
    """Para la auditoría del control de fichas: las fichas de la referencia con una diferencia
    nueva («ID campo») o que ya no están vigentes, fundidas en otra o retiradas («ID ausente»).
    Las discrepancias conocidas no cuentan, ni las fichas que no vienen en `documentos`."""
    fichas, _ = cargar(directorio)
    buscadas = {f["id"] for f in fichas}
    vistas = [d for d in documentos if d.get("id") in buscadas]
    vigentes = {d["id"]: publicada(d) for d in vistas if incidentes.activo(d)}
    resultado = comparar(vigentes, directorio)
    vistos = {d["id"] for d in vistas}
    return sorted(
        [f"{d['id']} {d['campo']}" for d in resultado["nuevas"]]
        + [f"{d['id']} ausente" for d in resultado["ausentes"] if d["id"] in vistos]
    )
