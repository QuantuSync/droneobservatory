"""Lo decidido de una ficha no se pierde al volver a extraerla.

Una extracción nueva de un candidato que ya tiene ficha (fuentes nuevas, la reextracción
programada de `revisados.reextraer`, la espera del experto, la revisión de una separación o una
unión) rehace la ficha desde cero (proceso/extraccion._alta). Lo que la ficha anterior tenía
decidido con la frase de una de sus fuentes (el día y la hora del inicio con su fin, el número de
drones, el cierre y su duración, el lugar del suceso con su instalación) solo cambia si la
extracción nueva trae su propia frase:

- si la nueva no lo da (el día pasa a la fecha de publicación, el número a «sin dato», el cierre a
  desconocido, el lugar a uno menos preciso), se conserva el de la anterior con su afirmación,
  siempre que la fuente que lo daba siga en la ficha (tras una separación ya no está, y el dato
  se va con su suceso);
- si la nueva da otro valor con su frase, se conserva el de la anterior y la contradicción pasa
  al control de las fichas («reextraccion:<id>», recogida/control_fichas.py), que vuelve a
  verificar la ficha con sus fuentes: nunca cambia en silencio.

Lo revisado a mano (configuracion/incidentes_revisados.json) lo vuelve a poner proceso/decidir.py
al guardar, lo que rectificó una autoridad lo conserva proceso/rectificaciones.mantener y las
correcciones del control las vuelve a aplicar el control (aplicar_verificaciones). La comprobación
W de la auditoría (proceso/auditoria_fichas.py) vigila que nada de esto se pierda.
"""

import copy
from dataclasses import dataclass, field

from esquema import Documento

# Del menos al más preciso.
NIVELES_LUGAR = ("pais", "region", "localidad", "instalacion")
PRECISIONES = ("aproximada", "dia", "hora", "minuto")
# El origen del inicio cuando ninguna frase da el día (proceso/fechas.py).
SIN_FRASE = "publicacion"
# Las fuentes que pone una revisión a mano: las vuelve a poner proceso/revisados.py.
REVISADA = "revisada-"

DATOS = ("inicio", "drones", "cierre", "lugar")


@dataclass
class Conservacion:
    incidente: Documento
    # Los datos de la anterior que se conservan porque la extracción nueva no los da.
    conservados: list[str] = field(default_factory=list)
    # Los que la nueva da distintos con su frase: {dato, antes, despues}; se conserva el de antes
    # y los decide el control.
    contradichos: list[Documento] = field(default_factory=list)


def _fuentes(incidente: Documento) -> set[str]:
    return {str(f["id"]) for f in incidente.get("fuentes", [])}


def _afirmacion(incidente: Documento, campo: str) -> Documento | None:
    return next((a for a in incidente.get("afirmaciones", []) if a.get("campo") == campo), None)


def _respaldada(anterior: Documento, campos: tuple[str, ...], fuentes: set[str]) -> bool:
    """La anterior lo afirmaba con una fuente que la ficha nueva sigue teniendo."""
    return any(
        (a := _afirmacion(anterior, c)) is not None and str(a.get("fuente_id")) in fuentes
        for c in campos
    )


def _tiempo(incidente: Documento) -> Documento:
    return incidente.get("tiempo") or {}


def _precision(tiempo: Documento) -> int:
    return PRECISIONES.index((tiempo.get("inicio") or {}).get("precision", "aproximada"))


def _inicio_decidido(anterior: Documento, fuentes: set[str]) -> bool:
    """El inicio de la anterior sale de una frase de una fuente que la nueva sigue teniendo."""
    origen = _tiempo(anterior).get("origen_inicio") or {}
    fuente = str(origen.get("fuente_id") or "")
    return (
        origen.get("tipo") not in (None, SIN_FRASE)
        and not fuente.startswith(REVISADA)
        and fuente in fuentes
    )


def _juicio_inicio(nuevo: Documento, anterior: Documento, fuentes: set[str]) -> str | None:
    """«pierde», «contradice» o None (la nueva vale)."""
    if not _inicio_decidido(anterior, fuentes):
        return None
    antes, despues = _tiempo(anterior), _tiempo(nuevo)
    origen = despues.get("origen_inicio") or {}
    if origen.get("tipo") in (None, SIN_FRASE):
        return "pierde"
    dia_antes = str((antes.get("inicio") or {}).get("valor", ""))[:10]
    dia_despues = str((despues.get("inicio") or {}).get("valor", ""))[:10]
    misma = origen.get("motivo") == (antes.get("origen_inicio") or {}).get("motivo")
    if dia_antes != dia_despues:
        # La misma frase leída con las reglas de ahora no es una contradicción.
        return None if misma else "contradice"
    if _precision(despues) < _precision(antes):
        # El mismo día sin la hora que daba la anterior.
        return "pierde"
    if (
        _precision(despues) >= PRECISIONES.index("hora")
        and (antes.get("inicio") or {}).get("valor") != (despues.get("inicio") or {}).get("valor")
        and not misma
    ):
        return "contradice"
    if antes.get("fin") and not despues.get("fin"):
        return "pierde"
    return None


def _numero(incidente: Documento) -> object:
    return (incidente.get("drones") or {}).get("numero", "desconocido")


def _juicio_drones(nuevo: Documento, anterior: Documento, fuentes: set[str]) -> str | None:
    antes, despues = _numero(anterior), _numero(nuevo)
    if antes in (None, "desconocido") or antes == despues:
        return None
    if not _respaldada(anterior, ("drones",), fuentes):
        return None
    return "pierde" if despues in (None, "desconocido") else "contradice"


def _cierre(incidente: Documento) -> Documento:
    return (incidente.get("consecuencias") or {}).get("cierre") or {}


def _juicio_cierre(nuevo: Documento, anterior: Documento, fuentes: set[str]) -> str | None:
    antes, despues = _cierre(anterior), _cierre(nuevo)
    if antes.get("valor") in (None, "desconocido") or antes == despues:
        return None
    if despues.get("valor") in (None, "desconocido"):
        return "pierde" if _respaldada(anterior, ("cierre",), fuentes) else None
    if despues.get("valor") != antes.get("valor"):
        return "contradice" if _respaldada(anterior, ("cierre",), fuentes) else None
    if antes.get("minutos") and not despues.get("minutos"):
        return "pierde" if _respaldada(anterior, ("cierre_minutos",), fuentes) else None
    return None


def _nivel(incidente: Documento) -> int:
    nivel = (incidente.get("lugar") or {}).get("nivel", "pais")
    return NIVELES_LUGAR.index(nivel) if nivel in NIVELES_LUGAR else 0


_CAMPOS_LUGAR = ("lugar_suceso", "localidad", "objetivo_nombre")


def _juicio_lugar(nuevo: Documento, anterior: Documento, fuentes: set[str]) -> str | None:
    """El lugar cambia por uno menos preciso (otro nombre del mismo sitio, al mismo nivel, no
    cuenta). Si la nueva lo dice con su frase («Marea Neagră, la aproximativ 24 de kilometri de
    Constanța» frente al puerto, EODI-2026-00669), es una contradicción que decide el control."""
    if _nivel(nuevo) >= _nivel(anterior):
        return None
    if (nuevo.get("lugar") or {}).get("pais") != (anterior.get("lugar") or {}).get("pais"):
        return None
    if not _respaldada(anterior, _CAMPOS_LUGAR, fuentes):
        return None
    return "contradice" if _respaldada(nuevo, ("lugar_suceso",), fuentes) else "pierde"


_JUICIOS = {
    "inicio": _juicio_inicio,
    "drones": _juicio_drones,
    "cierre": _juicio_cierre,
    "lugar": _juicio_lugar,
}


def juicios(nuevo: Documento, anterior: Documento) -> dict[str, str]:
    """{dato: «pierde» | «contradice»}: lo que la versión nueva le quita a lo decidido en la
    anterior (las fuentes, las de la nueva)."""
    fuentes = _fuentes(nuevo)
    resultado = {}
    for dato, juicio in _JUICIOS.items():
        veredicto = juicio(nuevo, anterior, fuentes)
        if veredicto is not None:
            resultado[dato] = veredicto
    return resultado


def perdidos(nuevo: Documento, anterior: Documento) -> list[str]:
    """Los datos decididos en la anterior que la nueva ya no tiene (auditoría W)."""
    return sorted(d for d, v in juicios(nuevo, anterior).items() if v == "pierde")


def _valor(incidente: Documento, dato: str) -> object:
    if dato == "inicio":
        tiempo = _tiempo(incidente)
        return {"inicio": tiempo.get("inicio"), "fin": tiempo.get("fin")}
    if dato == "drones":
        return _numero(incidente)
    if dato == "cierre":
        return _cierre(incidente)
    return {"suceso": (incidente.get("lugar") or {}).get("suceso"),
            "nivel": (incidente.get("lugar") or {}).get("nivel")}  # fmt: skip


_CAMPOS_AFIRMACION = {
    "inicio": ("inicio", "fin"),
    "drones": ("drones",),
    "cierre": ("cierre", "cierre_minutos"),
    "lugar": ("lugar_suceso", "localidad", "objetivo_nombre", "objetivo_categoria"),
}


def _con_afirmaciones(resultado: Documento, anterior: Documento, dato: str) -> None:
    """Las afirmaciones del dato conservado son las de la anterior (su fuente y su valor)."""
    campos = _CAMPOS_AFIRMACION[dato]
    resultado["afirmaciones"] = [
        *(a for a in resultado.get("afirmaciones", []) if a.get("campo") not in campos),
        *(copy.deepcopy(a) for a in anterior.get("afirmaciones", []) if a.get("campo") in campos),
    ]


def _poner(resultado: Documento, anterior: Documento, dato: str) -> None:
    if dato == "inicio":
        resultado["tiempo"] = copy.deepcopy(_tiempo(anterior))
    elif dato == "drones":
        resultado["drones"] = {**(resultado.get("drones") or {}), "numero": copy.deepcopy(
            _numero(anterior))}  # fmt: skip
    elif dato == "cierre":
        resultado["consecuencias"] = {
            **(resultado.get("consecuencias") or {}),
            "cierre": copy.deepcopy(_cierre(anterior)),
        }
    else:
        resultado["lugar"] = copy.deepcopy(anterior["lugar"])
        if "objetivo" in anterior:
            resultado["objetivo"] = copy.deepcopy(anterior["objetivo"])
        else:
            resultado.pop("objetivo", None)
    _con_afirmaciones(resultado, anterior, dato)


def conservar(nuevo: Documento, anterior: Documento) -> Conservacion:
    """La ficha rehecha por una extracción nueva con lo decidido de la anterior que la nueva no da
    o contradice (en ese caso, a la espera del control)."""
    veredictos = juicios(nuevo, anterior)
    if not veredictos:
        return Conservacion(nuevo)
    resultado = copy.deepcopy(nuevo)
    conservacion = Conservacion(resultado)
    for dato, veredicto in sorted(veredictos.items()):
        if veredicto == "contradice":
            conservacion.contradichos.append(
                {"dato": dato, "antes": _valor(anterior, dato), "despues": _valor(nuevo, dato)}
            )
        else:
            conservacion.conservados.append(dato)
        _poner(resultado, anterior, dato)
    return conservacion
