"""Auditoría de las fichas vigentes: cuántas tienen cada fallo conocido, con sus identificadores.

Solo lee y no llama a nada: las mismas reglas que corrigen las fichas, pasadas sobre todas. Corre
en cada control de las fichas (recogida/control_fichas.escribir_estado); sus recuentos salen en
el resumen diario y, si alguno sube respecto al día anterior, el aviso de silencio lo cuenta
(recogida/silencio.py). A mano: `python -m recogida.auditoria_fichas`.

- **A, cabecera**: la cabecera de la ficha en la web (el nombre de la instalación o, si no la
  hay, el titular: web/src/componentes/FichaIncidente.tsx) tiene menos de 3 palabras, o un
  objetivo «otra» se llama como la localidad del suceso (EODI-2026-00648, «Józefów · Otro
  lugar»).
- **B, instalación no reconocida**: sin objetivo o con objetivo «otra», y el titular nombra un
  aeropuerto, una base, un puerto o una central (EODI-2026-00131, «Berlín · Otro lugar»).
- **C, cita de autoridad vacía**: una fuente de autoridad cuya cita es solo quién habla y el
  verbo de decir («… Komendy Stołecznej Policji przekazała»: proceso/declaraciones.sin_afirmacion).
- **D, titular sin respaldo**: ninguna cita guardada nombra lo que afirma el titular
  (proceso/cita_titular.respalda), salvo los justificados a mano.
- **E, presencia sin base**: dron confirmado sin ninguna autoridad que lo atribuya a drones ni
  documento ni pruebas físicas de una autoridad, ni revisión a mano; o sin confirmar con una
  autoridad que sí lo atribuye; o, en lo que publica la web (proceso/coherencia.py), una misma
  fuente da un paso que confirma y otro que desmiente (EODI-2025-00124, Sofía).
- **F, lugar**: un buque como lugar, un suceso en el mar en la zona «interior», o la fecha de
  publicación como fecha del suceso cuando una fuente escribe otro día.
- **G, nombres**: un punto anterior sin nombre (`nombres.anteriores` con null), o un titular
  publicado que escribe una ciudad de otra forma que la ficha (EODI-2026-00050: «Alexandrópolis»
  frente a «Alejandrópolis»).
"""

import re
from collections.abc import Callable, Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from esquema import Documento
from proceso import (
    buques,
    cita_titular,
    coherencia,
    declaraciones,
    fechas,
    incidentes,
    nombres_lugar,
)
from proceso.presencia import (
    atribuida_por_autoridad,
    documento_oficial_decide,
    presencias_revisadas,
    pruebas_fisicas_confirmadas,
)

COMPROBACIONES = ("A", "B", "C", "D", "E", "F", "G")
NOMBRES = {
    "A": "cabecera de una palabra",
    "B": "instalación no reconocida",
    "C": "cita de autoridad vacía",
    "D": "titular sin respaldo",
    "E": "presencia sin base",
    "F": "lugar",
    "G": "nombres",
}
MIN_PALABRAS_CABECERA = 3
# Lo que nombra una instalación en un titular (en español o en inglés, las dos versiones).
_INSTALACION = re.compile(
    r"\b(?:aeropuerto|aeródromo|airport|airfield|aerodrome|base(?: aérea| militar| naval)?|"
    r"air ?base|naval base|military base|puerto|port|harbou?r|central (?:nuclear|eléctrica|"
    r"térmica)|(?:nuclear |power )plant|power station)\b",
    re.IGNORECASE,
)


def palabras(texto: str) -> int:
    return len(str(texto or "").split())


def _clave(texto: str) -> str:
    return nombres_lugar.clave(str(texto or ""))


def instalacion_de_verdad(incidente: Documento) -> bool:
    """El objetivo es una instalación con categoría propia (no «otra»): solo entonces la cabecera
    de la ficha es su nombre."""
    objetivo = incidente.get("objetivo") or {}
    return bool(objetivo.get("nombre")) and objetivo.get("categoria") not in (None, "otra")


def objetivo_es_la_localidad(incidente: Documento) -> bool:
    """Un objetivo «otra» que se llama como la localidad del suceso: no es una instalación."""
    return incidentes.objetivo_es_la_localidad(
        incidente.get("objetivo"), incidente.get("lugar") or {}
    )


def cabecera(incidente: Documento, idioma: str = "es") -> str:
    """La cabecera de la ficha en la web: el nombre de la instalación o, si no, el titular."""
    if instalacion_de_verdad(incidente):
        escrito = (_nombres(incidente).get("objetivo") or {}).get(idioma)
        return str(escrito or incidente["objetivo"]["nombre"])
    return str((incidente.get("titulo") or {}).get(idioma, ""))


def _nombres(incidente: Documento) -> Documento:
    """El campo `nombres` que publica la exportación (proceso/nombres_lugar.nombres_publicos)."""
    if incidente.get("nombres") is not None:
        return dict(incidente["nombres"])
    try:
        return nombres_lugar.nombres_publicos(incidente)
    except (KeyError, TypeError, ValueError):
        return {}


def _a(incidente: Documento) -> bool:
    # El nombre de una instalación puede ser corto («RAF Lakenheath», «Karup Airport»); de una
    # palabra, no («Józefów»). Un titular, de 3 palabras como mínimo.
    minimo = 2 if instalacion_de_verdad(incidente) else MIN_PALABRAS_CABECERA
    return objetivo_es_la_localidad(incidente) or any(
        palabras(cabecera(incidente, i)) < minimo for i in ("es", "en")
    )


def _b(incidente: Documento) -> bool:
    objetivo = incidente.get("objetivo") or {}
    if objetivo.get("categoria") not in (None, "otra"):
        return False
    return any(_INSTALACION.search(str(t)) for t in (incidente.get("titulo") or {}).values())


def citas_vacias(incidente: Documento) -> list[str]:
    """Las fuentes de autoridad cuya cita no dice nada: solo quién habla y el verbo de decir."""
    return [
        f["id"] for f in incidente.get("fuentes", [])
        if declaraciones.cita_vacia(f)
    ]  # fmt: skip


def _c(incidente: Documento) -> bool:
    return bool(citas_vacias(incidente))


def _d(incidente: Documento) -> bool:
    return incidente["id"] not in cita_titular.justificados() and not cita_titular.respalda(
        incidente
    )


def misma_fuente_en_pasos_opuestos(incidente: Documento) -> bool:
    """En lo publicado, una misma fuente da un paso que confirma (o atribuye) y otro que
    desmiente."""
    pasos = coherencia.coherente(incidente)["estado"]["historial"]
    confirman = {p.get("fuente_id") for p in pasos if p["estado"] in ("confirmado", "atribuido")}
    desmienten = {p.get("fuente_id") for p in pasos if p["estado"] == "desmentido"}
    return bool((confirman & desmienten) - {None})


def _e(incidente: Documento) -> bool:
    if misma_fuente_en_pasos_opuestos(incidente):
        return True
    presencia = incidente.get("presencia_dron")
    if incidente["id"] in presencias_revisadas():
        return False
    atribuida = atribuida_por_autoridad(incidente) or documento_oficial_decide(incidente)
    if presencia == "confirmada":
        return not atribuida and not pruebas_fisicas_confirmadas(incidente)
    return presencia == "no_confirmada" and atribuida_por_autoridad(incidente)


def _fecha_de_publicacion(incidente: Documento) -> bool:
    """La ficha tomó la fecha de publicación y una fuente escribe otro día del suceso."""
    tiempo = incidente.get("tiempo") or {}
    if (tiempo.get("origen_inicio") or {}).get("tipo") != "publicacion":
        return False
    dia = str(tiempo["inicio"]["valor"])[:10]
    for fuente in incidente.get("fuentes", []):
        try:
            publicacion = datetime.fromisoformat(
                str(fuente["fecha"]["valor"]).replace("Z", "+00:00")
            )
        except (KeyError, ValueError):
            continue
        zona = fechas.zona(fuente.get("pais") or incidente["lugar"].get("pais")) or ZoneInfo("UTC")
        frase = str(fuente.get("frase_origen") or "")
        propia = publicacion.astimezone(zona).date()
        for lectura in fechas.leer(frase, publicacion, zona, fuente.get("idioma")):
            # La fecha de la propia nota («– DW – 10.11.2025», EODI-2025-00125) no es la del
            # suceso.
            if lectura.origen == "explicita" and lectura.dia not in (date.fromisoformat(dia),
                                                                       propia):  # fmt: skip
                return True
    return False


def _f(incidente: Documento) -> bool:
    textos = buques.textos_de(incidente)
    lugar = incidente.get("lugar") or {}
    if incidentes.lugar_sin_buque(lugar, textos) is not lugar:
        return True
    zona = incidente.get("zona") or {}
    if zona.get("grupo") == "interior" and incidentes.alcanzado_en_el_mar(incidente):
        return True
    return _fecha_de_publicacion(incidente)


def _g(incidente: Documento) -> bool:
    nombres = _nombres(incidente)
    if any(a is None for a in nombres.get("anteriores") or []):
        return True
    # El titular como lo publica la exportación (exportacion/geojson.py), con los nombres ya en
    # la forma de cada idioma: lo que queda de otra forma es lo que se ve en la web.
    pais = (incidente.get("lugar") or {}).get("pais")
    return any(
        nombres_lugar.formas_ajenas(str(texto), idioma, pais)
        for idioma, texto in nombres_lugar.titulo_corregido(incidente).items()
        if idioma in nombres_lugar.IDIOMAS
    )


_REGLAS: dict[str, Callable[[Documento], bool]] = {
    "A": _a, "B": _b, "C": _c, "D": _d, "E": _e, "F": _f, "G": _g,
}  # fmt: skip


def auditar(documentos: Iterable[Documento]) -> dict[str, list[str]]:
    """Por comprobación, los identificadores de las fichas vigentes que la incumplen."""
    resultado: dict[str, list[str]] = {c: [] for c in COMPROBACIONES}
    for documento in documentos:
        if not incidentes.activo(documento):
            continue
        for clave, regla in _REGLAS.items():
            try:
                fallo = regla(documento)
            except (KeyError, TypeError, ValueError):
                # Una ficha a la que le falta algo que la regla lee no cuenta como fallo: la
                # auditoría no para por una.
                fallo = False
            if fallo:
                resultado[clave].append(str(documento["id"]))
    return {c: sorted(ids) for c, ids in resultado.items()}


def recuentos(resultado: dict[str, list[str]]) -> dict[str, int]:
    return {c: len(ids) for c, ids in resultado.items()}


def texto(resultado: dict[str, list[str]], limite: int = 40) -> str:
    lineas = []
    for clave in COMPROBACIONES:
        ids = resultado.get(clave, [])
        muestra = ", ".join(ids[:limite]) + (" …" if len(ids) > limite else "")
        lineas.append(f"{clave} {NOMBRES[clave]}: {len(ids)}" + (f" ({muestra})" if ids else ""))
    return "\n".join(lineas)
