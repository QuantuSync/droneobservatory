"""Exportación semanal para AEGIS: la base entera, cifrada, en una versión inmutable.

Una versión (AAAA.MM.DD) tiene un manifiesto en claro y estos ficheros, cada uno cifrado con
age con la misma clave pública que la base:

- incidentes.jsonl: un incidente por línea con todos sus campos, públicos e internos, como
  están en la base (también los fundidos y los retirados, que lo dicen en su documento);
- afirmaciones.jsonl: cada dato por fuente, con la fuente que lo dice y su código del
  Almirantazgo, sin filtrar ninguna (también las de fiabilidad E y F y las del Ministerio
  de Defensa ruso fuera de la capa de guerra);
- episodios.jsonl, ucrania_ataques.jsonl y ucrania_regiones.jsonl;
- guerra_impactos.jsonl: los impactos con lugar de la capa de guerra (localidad o instalación,
  los dos sentidos), con su foco térmico completo y la procedencia de cada valor (también los
  unidos a otro y los retirados, que lo dicen en su documento);
- guerra_mensajes.jsonl: cada mensaje leído de los canales de la capa de guerra, sin su texto
  (enlace, canal, fecha, resultado, impactos que dio, cifras de derribos y víctimas, motivo
  si no dio ninguno y lo que hizo el extractor);
- restricciones_aeropuertos.jsonl: las restricciones temporales de aeropuertos rusos que
  anuncia Rosaviatsia, con su ataque UA_RU si lo hay (serie interna);
- frecuencias.json: incidentes por categoría de objetivo, país y mes, con el sesgo de
  cobertura declarado;
- descartes.jsonl: noticias rechazadas, partes que no se entienden, duplicados, fusiones no
  hechas por dudosas, desmentidos y retirados;
- vocabulario.json: la correspondencia con las categorías y clases de AEGIS
  (configuracion/vocabulario_aegis.json);
- encuentros.jsonl, estadisticas_oficiales.jsonl y documentos_oficiales.jsonl: los registros
  internos de las fuentes oficiales de detalle (encuentros de drones con aeronaves de la UK
  Airprox Board, cifras oficiales y documentos oficiales leídos, con los sucesos que citan y su
  cruce con los incidentes);
- esquema/: el JSON Schema de cada fichero. Los de la base (esquema/eodi/) llevan la marca
  de visibilidad de cada campo: un campo interno nuevo entra en la exportación sin tocar
  este código, porque se exportan los documentos enteros.

La salida es determinista: el mismo contenido de la base da los mismos ficheros en claro,
byte a byte (orden estable de registros y de claves, sin la hora de la exportación). El
cifrado no lo es (age usa una clave efímera), por eso el manifiesto da las dos huellas.
Una versión que no valida contra sus esquemas no se escribe.
"""

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

import pyrage
from jsonschema import Draft202012Validator

import esquema
from almacen.base import Almacen
from esquema import Documento, Esquema, validador
from exportacion import procedencia as origenes
from modelo import ficha
from proceso import incidentes as reglas
from proceso.estados import Estado
from proceso.focos_termicos import con_focos
from proceso.mediciones import con_mediciones
from proceso.restricciones import por_ataque

VERSION_FORMATO = "1.1.0"
RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_ESQUEMAS = RAIZ / "esquema" / "exportacion" / VERSION_FORMATO
VOCABULARIO = RAIZ / "configuracion" / "vocabulario_aegis.json"
MEDIOS = RAIZ / "configuracion" / "medios_europa.json"
OFICIALES = RAIZ / "configuracion" / "fuentes_oficiales.json"
MANIFIESTO = "manifiesto.json"
# Cada fichero se comprime antes de cifrar (gzip sin fecha: el mismo contenido da los mismos
# bytes): el texto se reduce a una fracción y el repositorio de datos crece por semanas.
EXTENSION = ".gz.age"
NIVEL_COMPRESION = 9
FORMATO_VERSION = "%Y.%m.%d"
FORMATO_INSTANTE = "%Y-%m-%dT%H:%M:%SZ"
SIN_OBJETIVO = "sin_objetivo"
PREFIJO_UCRANIA = "EODI-UA-"
PREFIJO_IMPACTO = "EODI-IG-"
ESQUEMAS_BASE = "esquema/eodi"
ESQUEMAS_PROPIOS = "esquema/exportacion"


class ExportacionInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Fichero:
    """Un fichero de la versión, en claro, con el esquema de sus registros."""

    nombre: str
    contenido: bytes
    registros: int
    esquema: str


def _linea(documento: Any) -> str:
    return json.dumps(documento, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _jsonl(documentos: list[Any]) -> bytes:
    return "".join(_linea(d) + "\n" for d in documentos).encode("utf-8")


def _json(documento: Any) -> bytes:
    return (json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode(
        "utf-8"
    )


def _leer_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


# --- Esquemas -------------------------------------------------------------------------


@cache
def esquema_propio(nombre: str) -> Documento:
    contenido: Documento = _leer_json(DIRECTORIO_ESQUEMAS / f"{nombre}.schema.json")
    return contenido


def validador_propio(nombre: str) -> Draft202012Validator:
    return Draft202012Validator(esquema_propio(nombre))


def _errores(validador_: Draft202012Validator, documento: Any) -> list[str]:
    return [f"{e.json_path}: {e.message}" for e in validador_.iter_errors(documento)]


def _comprobar(nombre: str, documentos: Iterable[Any], *validadores: Draft202012Validator) -> None:
    """Todos los registros validan contra sus esquemas; si no, no hay versión."""
    for numero, documento in enumerate(documentos, 1):
        for validador_ in validadores:
            errores = _errores(validador_, documento)
            if errores:
                # Solo la ruta del error, nunca el contenido.
                raise ExportacionInvalida(f"{nombre}, registro {numero}: {errores[0][:200]}")


# --- Contenido ------------------------------------------------------------------------


def _vigentes(documentos: list[Documento]) -> dict[str, set[str]]:
    """Por entidad, las afirmaciones de su documento actual (en forma canónica)."""
    return {d["id"]: {_linea(a) for a in d.get("afirmaciones", [])} for d in documentos}


def _datos_fuente(fuente: Documento, credibilidad: int | None) -> Documento:
    datos: Documento = {
        "medio": fuente["medio"],
        "enlace": fuente["enlace"],
        "fiabilidad": fuente["fiabilidad"],
        "es_autoridad": bool(fuente.get("es_autoridad", False)),
        "interna_fuera_de_ucrania": bool(fuente.get("interna_fuera_de_ucrania", False)),
        "publica": bool(fuente["publica"]),
    }
    if "fecha" in fuente:
        datos["fecha"] = fuente["fecha"]["valor"]
    if credibilidad is not None:
        datos["credibilidad"] = credibilidad
    return datos


def _capa(entidad: str) -> str:
    return "ucrania" if entidad.startswith((PREFIJO_UCRANIA, PREFIJO_IMPACTO)) else "general"


def _valor(documento: Documento, ruta: str) -> Any:
    """El valor de una ruta con puntos («drones.numero»), o None si no está."""
    valor: Any = documento
    for parte in ruta.split("."):
        if not isinstance(valor, dict) or parte not in valor:
            return None
        valor = valor[parte]
    return valor


def _respaldos(
    documento: Documento, extraidas: set[tuple[str, str]], fichas: origenes.Fichas
) -> list[Documento]:
    """Lo que dice cada fuente que no pasó por el extractor: los partes de la capa de Ucrania
    (Fuerza Aérea de Ucrania, Ministerio de Defensa ruso), las declaraciones oficiales y las
    notas oficiales. La fuente anota los campos que respalda; el valor es el de la entidad
    (en el estado, el paso del historial que provoca). No hay confianza de extracción."""
    resultado = []
    # Los impactos de la capa de guerra dicen cómo se leyó cada fuente (código o extractor).
    lecturas = {x["fuente_id"]: x for x in documento.get("lecturas", [])}
    for fuente in documento["fuentes"]:
        lectura = lecturas.get(fuente["id"], {})
        for campo in sorted(fuente.get("campos_respaldados", [])):
            if (campo, fuente["id"]) in extraidas:
                continue
            if campo == "estado":
                valores = [
                    paso["estado"] for paso in documento["estado"]["historial"]
                    if paso.get("fuente_id") == fuente["id"]
                ]  # fmt: skip
            else:
                valor = _valor(documento, campo)
                valores = [] if valor is None else [valor]
            entradas = [
                {**origenes.exportar_afirmacion(
                    {"campo": campo, "valor": v, "fuente_id": fuente["id"],
                     "confianza_extraccion": None},
                    documento["id"], fuente, fichas, extractor=False),
                 "vigente": True, "fuente": _datos_fuente(fuente, fuente.get("credibilidad"))}
                for v in valores
            ]  # fmt: skip
            if lectura.get("metodo") == origenes.EXTRACTOR:
                for entrada in entradas:
                    entrada["metodo"] = origenes.EXTRACTOR
                    entrada["confianza_extraccion"] = lectura.get("confianza")
            resultado += entradas
    return resultado


def afirmaciones(
    almacen: Almacen,
    incidentes: list[Documento],
    ataques: list[Documento],
    fichas: origenes.Fichas,
) -> list[Documento]:
    """Cada dato por fuente: las afirmaciones que dejó el extractor (con su confianza),
    también las que ya no están en su entidad, y lo que respalda cada fuente que no pasó
    por el extractor. Ninguna fuente se filtra."""
    fuentes = almacen.fuentes()
    entidades = {d["id"]: d for d in [*incidentes, *ataques]}
    vigentes = _vigentes(incidentes) | _vigentes(ataques)
    credibilidades = {(d["id"], f["id"]): f["credibilidad"] for d in entidades.values()
                      for f in d["fuentes"]}  # fmt: skip
    por_entidad: dict[str, list[Documento]] = defaultdict(list)
    for entidad, afirmacion in almacen.todas_las_afirmaciones():
        fuente = fuentes[afirmacion["fuente_id"]]
        por_entidad[entidad].append({
            **origenes.exportar_afirmacion(afirmacion, entidad, fuente, fichas, extractor=True),
            "vigente": _linea(afirmacion) in vigentes.get(entidad, set()),
            "fuente": _datos_fuente(fuente, credibilidades.get((entidad, afirmacion["fuente_id"]))),
        })  # fmt: skip
    for id_, documento in entidades.items():
        extraidas = {(a["campo"], a["fuente_id"]) for a in por_entidad.get(id_, [])}
        por_entidad[id_] += _respaldos(documento, extraidas, fichas)
    return [
        {**afirmacion, "entidad_id": entidad, "capa": _capa(entidad)}
        for entidad in sorted(por_entidad)
        for afirmacion in por_entidad[entidad]
    ]


def _categoria(incidente: Documento) -> str:
    return str(incidente.get("objetivo", {}).get("categoria", SIN_OBJETIVO))


def _medios_por_pais() -> tuple[Counter[str], dict[str, str]]:
    medios = _leer_json(MEDIOS)
    dominios = Counter(medios["dominios"].values())
    nacionales = {pais: f".{tld}" for tld, pais in medios["tld"].items()}
    return dominios, nacionales


def _oficiales_por_pais() -> dict[str, list[str]]:
    resultado: dict[str, list[str]] = defaultdict(list)
    for fuente in _leer_json(OFICIALES)["fuentes"]:
        resultado[fuente["pais"]].append(fuente["id"])
    return {pais: sorted(ids) for pais, ids in resultado.items()}


FUENTES_COBERTURA = (
    {
        "id": "gdelt",
        "cubre": "Todos los países europeos: noticias de los ficheros GKG de GDELT en las lenguas "
        "europeas, filtradas por palabras de dron en el titular y agrupadas en candidatos que "
        "el extractor convierte en incidentes.",
        "sesgo": "Depende de cuánto publica la prensa de cada país y de cuánto de ella indexa "
        "GDELT: países con más medios y más prensa en línea aportan más incidentes, y los "
        "sucesos menores solo llegan si alguien los cuenta. El filtro por titular deja fuera "
        "las noticias que no nombran el dron en el titular.",
    },
    {
        "id": "oficiales",
        "cubre": "Solo los países con fuentes oficiales leídas (por_pais.fuentes_oficiales): "
        "confirman incidentes que ya hay, no crean incidentes nuevos.",
        "sesgo": "En esos países hay más incidentes confirmados que en los demás por tener una "
        "fuente oficial leída, no por haber más incidentes.",
    },
    {
        "id": "fuentes_detalle",
        "cubre": "Respuestas de gobiernos en el Bundestag, la Tweede Kamer y el Parlamento "
        "británico; informes de organismos de investigación, cierres policiales y sentencias "
        "leídos; encuentros con aeronaves de la UK Airprox Board; estadísticas de gestores y "
        "autoridades (referencias_oficiales). Confirman y precisan incidentes que ya hay; solo "
        "una respuesta parlamentaria con fecha y lugar da de alta uno nuevo.",
        "sesgo": "Los países con estas fuentes (DE, NL, GB, DK y los de las estadísticas) tienen "
        "más incidentes confirmados y más detalle que los demás por tener la fuente, no por "
        "haber más incidentes. Las cifras oficiales cuentan cosas distintas (avistamientos, "
        "afectaciones, encuentros): solo se comparan en el mismo país, categoría y periodo.",
    },
    {
        "id": "fuerza_aerea_ua",
        "cubre": "Capa de Ucrania y cruces a otros países que cuenta el parte de la Fuerza Aérea "
        "de Ucrania.",
        "sesgo": "Los cruces a países vecinos se notifican según los cuenta el parte, que no "
        "es exhaustivo fuera de Ucrania.",
    },
)

MOTIVO_SIN_CORRECCION = (
    "Las frecuencias son recuentos de lo que recoge el observatorio. No se corrigen porque no "
    "hay una tasa de notificación conocida por país ni por tipo de instalación con que hacerlo "
    "sin inventarla. Para normalizar, por_pais da los artículos recogidos de medios de cada "
    "país, los medios con dominio propio en la lista de GDELT y las fuentes oficiales leídas; "
    "quien use las frecuencias decide si y cómo corrige con ellos."
)


def _en_periodo(incidente: Documento, periodo: Documento) -> bool:
    dia = incidente["tiempo"]["inicio"]["valor"][:10]
    return bool(periodo["inicio"] <= dia <= periodo["fin"])


def _de_la_cifra(incidente: Documento, ambito: Documento) -> bool:
    """El incidente es del ámbito de la cifra: su país y, si la cifra los da, su categoría y su
    instalación (por el nombre del objetivo o el OACI)."""
    if incidente["lugar"]["pais"] != ambito["pais"]:
        return False
    objetivo = incidente.get("objetivo", {})
    if ambito.get("categoria") and objetivo.get("categoria") != ambito["categoria"]:
        return False
    if ambito.get("oaci"):
        return bool(objetivo.get("oaci") == ambito["oaci"])
    if ambito.get("instalacion"):
        nombre = str(objetivo.get("nombre", "")).casefold()
        return bool(nombre) and (nombre in ambito["instalacion"].casefold()
                                 or ambito["instalacion"].casefold() in nombre)  # fmt: skip
    return True


def referencias_oficiales(
    activos: list[Documento], estadisticas: list[Documento]
) -> list[Documento]:
    """Cada cifra oficial con los incidentes que el observatorio tiene en su ámbito y periodo."""
    return [
        {
            "estadistica": e["id"], "autoridad": e["autoridad"], "pais": e["ambito"]["pais"],
            "categoria": e["ambito"].get("categoria"),
            "instalacion": e["ambito"].get("instalacion"),
            "periodo": e["periodo"], "metrica": e["metrica"], "cifra": e["cifra"],
            "incidentes_observatorio": sum(
                _de_la_cifra(i, e["ambito"]) and _en_periodo(i, e["periodo"]) for i in activos
            ),
        }
        for e in sorted(estadisticas, key=lambda x: x["id"])
    ]  # fmt: skip


def frecuencias(
    almacen: Almacen, incidentes: list[Documento], estadisticas: list[Documento] | None = None
) -> Documento:
    activos = [i for i in incidentes if reglas.activo(i)]
    grupos: dict[tuple[str, str, str], list[Documento]] = defaultdict(list)
    for incidente in activos:
        clave = (_categoria(incidente), incidente["lugar"]["pais"],
                 incidente["tiempo"]["inicio"]["valor"][:7])  # fmt: skip
        grupos[clave].append(incidente)
    filas = [
        {
            "categoria": categoria,
            "pais": pais,
            "mes": mes,
            "incidentes": len(grupo),
            "por_estado": dict(sorted(Counter(i["estado"]["actual"] for i in grupo).items())),
            "por_tipo": dict(sorted(Counter(i["tipo"] for i in grupo).items())),
            "presencia_confirmada": sum(i.get("presencia_dron") == "confirmada" for i in grupo),
            "por_nivel_detalle": dict(sorted(Counter(i["nivel_detalle"] for i in grupo).items())),
        }
        for (categoria, pais, mes), grupo in sorted(grupos.items())
    ]
    por_pais = Counter(i["lugar"]["pais"] for i in activos)
    articulos = Counter(a["pais"] for a in almacen.articulos() if a.get("pais"))
    dominios, nacionales = _medios_por_pais()
    oficiales = _oficiales_por_pais()
    paises = sorted(set(por_pais) | set(articulos) | set(oficiales))
    return {
        "criterio": "Incidentes activos de la capa general (ni fundidos en otro ni retirados), "
        "con cualquier estado, por categoría de objetivo (sin_objetivo si no se sabe), país "
        "del suceso y mes de inicio (UTC).",
        "filas": filas,
        "totales": {
            "incidentes": len(activos),
            "por_categoria": dict(sorted(Counter(_categoria(i) for i in activos).items())),
            "por_pais": dict(sorted(por_pais.items())),
            "por_mes": dict(
                sorted(Counter(i["tiempo"]["inicio"]["valor"][:7] for i in activos).items())
            ),
            "por_nivel_detalle": dict(sorted(Counter(i["nivel_detalle"] for i in activos).items())),
        },
        "sesgo_cobertura": {
            "correccion": "ninguna",
            "motivo": MOTIVO_SIN_CORRECCION,
            "fuentes": list(FUENTES_COBERTURA),
            "por_pais": [
                {
                    "pais": pais,
                    "incidentes": por_pais.get(pais, 0),
                    "articulos": articulos.get(pais, 0),
                    "dominios_listados": dominios.get(pais, 0),
                    "dominio_nacional": nacionales.get(pais),
                    "fuentes_oficiales": oficiales.get(pais, []),
                }
                for pais in paises
            ],
            "referencias_oficiales": referencias_oficiales(activos, estadisticas or []),
        },
    }


def fusiones_dudosas(incidentes: list[Documento]) -> list[tuple[str, list[str]]]:
    """Incidentes activos que encajan con dos o más anteriores: la fusión no se hace
    (proceso/incidentes.fusionar)."""
    activos = sorted(
        (i for i in incidentes if reglas.activo(i)),
        key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]),
    )
    resultado = []
    for posicion, incidente in enumerate(activos):
        anteriores = sorted(
            otro["id"] for otro in activos[:posicion] if reglas.encajan(otro, incidente)
        )
        if len(anteriores) > 1:
            resultado.append((incidente["id"], anteriores))
    return sorted(resultado)


def _instante(instante: Documento) -> str:
    return str(instante["valor"])


def descartes(almacen: Almacen, incidentes: list[Documento]) -> list[Documento]:
    resultado: list[Documento] = []
    for candidato in almacen.candidatos():
        legibles = [e for e in almacen.extracciones(candidato["id"]) if "ficha" in e]
        if not legibles or legibles[-1].get("incidente"):
            continue
        ultima = legibles[-1]
        motivos = [str(m) for m in ultima.get("motivos", [])]
        resultado.append({
            "tipo": "noticia_rechazada",
            "id": candidato["id"],
            "fecha": ultima["fecha"],
            "version_extractor": ultima["version"],
            "motivo": "; ".join(motivos) or "la ficha no es un incidente",
            "articulos": sorted(candidato.get("articulos", [])),
        })  # fmt: skip
    for fallido in almacen.todos_los_fallidos():
        resultado.append({
            "tipo": "parte_fallido", "id": fallido["enlace"], "fecha": fallido["fecha"],
            "fuente_id": fallido["fuente_id"], "motivo": fallido["motivo"],
            "resuelto": fallido["resuelto"],
        })  # fmt: skip
    for fusion in almacen.fusiones():
        resultado.append({
            "tipo": "duplicado", "id": fusion["absorbido"], "fecha": fusion["fecha"],
            "destino": fusion["destino"], "motivo": fusion["motivo"],
            "fuentes_aportadas": fusion["fuentes"], "revertida": fusion["revertida"],
        })  # fmt: skip
    for id_, anteriores in fusiones_dudosas(incidentes):
        resultado.append({
            "tipo": "fusion_dudosa", "id": id_, "encaja_con": anteriores,
            "motivo": "mismo sitio y misma ventana que varios anteriores: no se funde",
        })  # fmt: skip
    for incidente in incidentes:
        if incidente["estado"]["actual"] == Estado.DESMENTIDO:
            paso = incidente["estado"]["historial"][-1]
            resultado.append({
                "tipo": "desmentido", "id": incidente["id"], "fecha": _instante(paso["fecha"]),
                "fuente_id": paso["fuente_id"],
                "motivo": incidente["control"].get("motivo_desmentido", ""),
            })  # fmt: skip
        if "retirado" in incidente:
            resultado.append({
                "tipo": "retirado", "id": incidente["id"],
                "fecha": _instante(incidente["retirado"]["fecha"]),
                "motivo": incidente["retirado"]["motivo"],
            })  # fmt: skip
    orden = ("noticia_rechazada", "parte_fallido", "duplicado", "fusion_dudosa", "desmentido",
             "retirado")  # fmt: skip
    return sorted(resultado, key=lambda d: (orden.index(d["tipo"]), d["id"], _linea(d)))


def vocabulario() -> Documento:
    contenido: Documento = _leer_json(VOCABULARIO)
    return contenido


def _esquemas() -> list[Fichero]:
    """Los JSON Schema de la base (con su marca de visibilidad) y los propios."""
    base = [
        Fichero(f"{ESQUEMAS_BASE}/{ruta.name}", ruta.read_bytes(), 1, "")
        for ruta in sorted(esquema.DIRECTORIO.glob("*.schema.json"))
    ]
    propios = [
        Fichero(f"{ESQUEMAS_PROPIOS}/{ruta.name}", ruta.read_bytes(), 1, "")
        for ruta in sorted(DIRECTORIO_ESQUEMAS.glob("*.schema.json"))
    ]
    return base + propios


def _base(nombre: str) -> str:
    return f"{ESQUEMAS_BASE}/{nombre}.schema.json"


def _propio(nombre: str) -> str:
    return f"{ESQUEMAS_PROPIOS}/{nombre}.schema.json"


def generar(almacen: Almacen) -> list[Fichero]:
    """Los ficheros de una versión, en claro y ya validados."""
    # El foco térmico de FIRMS vive en su propia tabla: aquí va completo, con lo interno.
    focos = almacen.focos_termicos()
    base, ataques_base = con_focos(almacen.incidentes(), almacen.ataques_ucrania(), focos)
    # Igual con el tráfico aéreo y las condiciones medidas (proceso/mediciones.py), con su
    # fuente y sus afirmaciones medidas, que así quedan vigentes.
    base, ataques_base = con_mediciones(base, ataques_base, almacen)
    episodios = almacen.episodios()
    fichas = origenes.Fichas.de(almacen)
    try:
        incidentes = [origenes.exportar_incidente(i, fichas) for i in base]
        ataques = [origenes.exportar_ataque(a) for a in ataques_base]
    except origenes.SinOrigen as error:
        raise ExportacionInvalida(f"valor sin origen: {error}") from error
    guerra = [
        origenes.exportar_impacto({**d, "foco_termico": focos[d["id"]]} if d["id"] in focos else d)
        for d in almacen.impactos_guerra()
    ]
    restricciones = [origenes.exportar_restriccion(r) for r in almacen.restricciones()]
    mensajes = [{k: v for k, v in m.items() if k != "huella"} for m in almacen.mensajes_guerra()]
    # Restricciones de aeropuertos de cada ataque UA_RU: cuántos aeropuertos y cuántas horas.
    restringidos = por_ataque(almacen.restricciones())
    ataques = [
        {**a, "restricciones_aeropuertos": restringidos[a["id"]],
         "procedencia": {**a["procedencia"], "restricciones_aeropuertos": {
             "origen": "oficial", "metodo": "regla", "fuentes": ["rosaviatsia"]}}}
        if a["id"] in restringidos else a
        for a in ataques
    ]  # fmt: skip
    por_ataque_procedencia = {a["id"]: a["procedencia"] for a in ataques}
    regiones = [
        {
            "ataque_id": a,
            "region": r,
            "procedencia": origenes.procedencia_region(r, por_ataque_procedencia[a]),
        }
        for a, r in (
            (a, {**r, "foco_termico": focos[f"{a}/{r['region']}"]})
            if f"{a}/{r['region']}" in focos
            else (a, r)
            for a, r in almacen.todas_las_regiones_ucrania()
        )
    ]
    lista_afirmaciones = afirmaciones(
        almacen, base, ataques_base + almacen.impactos_guerra(), fichas
    )
    lista_descartes = descartes(almacen, base)
    encuentros = almacen.encuentros()
    estadisticas = almacen.estadisticas_oficiales()
    documentos = almacen.documentos_oficiales()
    datos_frecuencias = frecuencias(almacen, incidentes, estadisticas)
    datos_vocabulario = vocabulario()
    entradas_vocabulario = sum(
        len(datos_vocabulario[c]) for c in ("categorias_objetivo", "clases_dron")
    )
    sin_origen = [a for a in lista_afirmaciones if not a.get("origen") or not a.get("metodo")]
    if sin_origen:
        raise ExportacionInvalida(f"afirmaciones.jsonl: {len(sin_origen)} sin origen")

    _comprobar("incidentes.jsonl", incidentes, validador(Esquema.INCIDENTE))
    _comprobar("episodios.jsonl", episodios, validador(Esquema.EPISODIO))
    _comprobar("ucrania_ataques.jsonl", ataques, validador(Esquema.ATAQUE_UCRANIA))
    _comprobar("ucrania_regiones.jsonl", regiones, validador_propio("region_ucrania"))
    _comprobar(
        "ucrania_regiones.jsonl", (r["region"] for r in regiones),
        validador(Esquema.REGION_UCRANIA),
    )  # fmt: skip
    _comprobar("guerra_impactos.jsonl", guerra, validador(Esquema.IMPACTO_GUERRA))
    _comprobar(
        "restricciones_aeropuertos.jsonl", restricciones, validador(Esquema.RESTRICCION_AEROPUERTO)
    )
    _comprobar("guerra_mensajes.jsonl", mensajes, validador_propio("mensaje_guerra"))
    _comprobar("afirmaciones.jsonl", lista_afirmaciones, validador_propio("afirmacion"))
    _comprobar("descartes.jsonl", lista_descartes, validador_propio("descarte"))
    _comprobar("frecuencias.json", [datos_frecuencias], validador_propio("frecuencias"))
    _comprobar("vocabulario.json", [datos_vocabulario], validador_propio("vocabulario"))
    _comprobar("encuentros.jsonl", encuentros, validador(Esquema.ENCUENTRO))
    _comprobar("estadisticas_oficiales.jsonl", estadisticas, validador(Esquema.ESTADISTICA_OFICIAL))
    _comprobar("documentos_oficiales.jsonl", documentos, validador(Esquema.DOCUMENTO_OFICIAL))

    datos = [
        Fichero("afirmaciones.jsonl", _jsonl(lista_afirmaciones), len(lista_afirmaciones),
                _propio("afirmacion")),
        Fichero("descartes.jsonl", _jsonl(lista_descartes), len(lista_descartes),
                _propio("descarte")),
        Fichero("documentos_oficiales.jsonl", _jsonl(documentos), len(documentos),
                _base("documento_oficial")),
        Fichero("encuentros.jsonl", _jsonl(encuentros), len(encuentros), _base("encuentro")),
        Fichero("episodios.jsonl", _jsonl(episodios), len(episodios), _base("episodio")),
        Fichero("estadisticas_oficiales.jsonl", _jsonl(estadisticas), len(estadisticas),
                _base("estadistica_oficial")),
        Fichero("frecuencias.json", _json(datos_frecuencias), len(datos_frecuencias["filas"]),
                _propio("frecuencias")),
        Fichero("guerra_impactos.jsonl", _jsonl(guerra), len(guerra), _base("impacto_guerra")),
        Fichero("guerra_mensajes.jsonl", _jsonl(mensajes), len(mensajes),
                _propio("mensaje_guerra")),
        Fichero("incidentes.jsonl", _jsonl(incidentes), len(incidentes), _base("incidente")),
        Fichero("restricciones_aeropuertos.jsonl", _jsonl(restricciones), len(restricciones),
                _base("restriccion_aeropuerto")),
        Fichero("ucrania_ataques.jsonl", _jsonl(ataques), len(ataques),
                _base("ataque_ucrania")),
        Fichero("ucrania_regiones.jsonl", _jsonl(regiones), len(regiones),
                _propio("region_ucrania")),
        Fichero("vocabulario.json", _json(datos_vocabulario), entradas_vocabulario,
                _propio("vocabulario")),
    ]  # fmt: skip
    return datos + _esquemas()


# --- Versión cifrada -------------------------------------------------------------------


Cifrador = Callable[[bytes], bytes]


def version_de(momento: datetime) -> str:
    return momento.strftime(FORMATO_VERSION)


def empaquetar(
    ficheros: list[Fichero],
    version: str,
    fecha_corte: str,
    generada: datetime,
    destinatario: str,
    cifrar: Cifrador | None = None,
) -> dict[str, bytes]:
    """Ruta dentro de la versión → contenido: cada fichero cifrado y el manifiesto en claro."""
    receptor = pyrage.x25519.Recipient.from_str(destinatario)
    cifrar = cifrar or (lambda datos: pyrage.encrypt(datos, [receptor]))
    salida: dict[str, bytes] = {}
    entradas = []
    for fichero in sorted(ficheros, key=lambda f: f.nombre):
        cifrado = cifrar(gzip.compress(fichero.contenido, NIVEL_COMPRESION, mtime=0))
        salida[fichero.nombre + EXTENSION] = cifrado
        entradas.append({
            "nombre": fichero.nombre,
            "esquema": fichero.esquema or "https://json-schema.org/draft/2020-12/schema",
            "registros": fichero.registros,
            "bytes": len(fichero.contenido),
            "sha256": sha256(fichero.contenido),
            "cifrado": {
                "nombre": fichero.nombre + EXTENSION,
                "bytes": len(cifrado),
                "sha256": sha256(cifrado),
            },
        })  # fmt: skip
    manifiesto = {
        "version": version,
        "fecha_corte": fecha_corte,
        "generada": generada.strftime(FORMATO_INSTANTE),
        "version_esquema": esquema.VERSION,
        "version_formato": VERSION_FORMATO,
        "version_logica_extraccion": ficha.VERSION,
        "version_vocabulario": vocabulario()["version"],
        "cifrado": {
            "metodo": "age",
            "compresion": "gzip",
            "destinatario": destinatario,
            "extension": EXTENSION,
        },
        "ficheros": entradas,
    }
    _comprobar(MANIFIESTO, [manifiesto], validador_propio("manifiesto"))
    salida[MANIFIESTO] = _json(manifiesto)
    return salida


def escribir(contenido: dict[str, bytes], directorio: Path) -> None:
    for nombre, datos in contenido.items():
        ruta = directorio / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)
