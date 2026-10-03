"""Catálogo de prestaciones de drones, sus fuentes, las clases del motor y las zonas de lanzamiento.

Tres ficheros de `configuracion/`, cada uno con su esquema propio en `esquema/catalogo/1.1.0/`:

- `catalogo_drones.json`: prestaciones por modelo, cada valor con su fuente y la frase de la
  fuente que lo da, y las clases que usa el motor. Las cifras están con la unidad de la fuente;
  aquí se convierten a la unidad canónica de cada campo (m, kg, m/s, km, min, °C, m²) sin
  redondear.
- `catalogo_fuentes.json`: las fuentes numeradas. Las de prioridad baja dan estimaciones
  débiles: un valor que solo sale de ellas no sirve para descartar.
- `zonas_lanzamiento.json`: las zonas de lanzamiento de los partes ucranianos con su punto.

Un valor de un modelo es un intervalo [mínimo, máximo] con todas sus fuentes. Si una fuente da
una cota abierta («más de 4 h»), el extremo que no da queda sin saber (None): nunca se supone.
La envolvente de una clase es el mínimo de los mínimos y el máximo de los máximos de sus
modelos; si a un modelo le falta el dato, ese extremo de la clase queda sin saber.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

RAIZ = Path(__file__).resolve().parent.parent.parent
CONFIGURACION = RAIZ / "configuracion"
CATALOGO = CONFIGURACION / "catalogo_drones.json"
FUENTES = CONFIGURACION / "catalogo_fuentes.json"
ZONAS = CONFIGURACION / "zonas_lanzamiento.json"
VERSION_ESQUEMA = "1.1.0"
ESQUEMAS = RAIZ / "esquema" / "catalogo" / VERSION_ESQUEMA

Documento = dict[str, Any]

# Conversión de cada unidad de las fuentes a la canónica de su magnitud: factor y unidad.
CONVERSION: dict[str, tuple[float, str]] = {
    "m": (1.0, "m"),
    "mm": (0.001, "m"),
    "cm": (0.01, "m"),
    "ft": (0.3048, "m"),
    "kg": (1.0, "kg"),
    "g": (0.001, "kg"),
    "lb": (0.45359237, "kg"),
    "m/s": (1.0, "m/s"),
    "km/h": (1 / 3.6, "m/s"),
    "kn": (1852 / 3600, "m/s"),
    "mph": (1609.344 / 3600, "m/s"),
    "km": (1.0, "km"),
    "mi": (1.609344, "km"),
    "min": (1.0, "min"),
    "h": (60.0, "min"),
    "°C": (1.0, "°C"),
    "m2": (1.0, "m2"),
    "ft/min": (0.00508, "m/s"),
    "°": (1.0, "°"),
    "m/s2": (1.0, "m/s2"),
    "n": (1.0, "n"),
    "s": (1.0, "s"),
}


# Radio de una zona de lanzamiento como origen, por tipo: no sale de las fuentes, es el margen
# del motor. Un aeródromo o una instalación y sus alrededores (las plataformas de lanzamiento
# están a 1-2 km de la pista en Primorsko-Ajtarsk y Millerovo); un polígono de tiro; una zona
# que el parte nombra por una ciudad o una dirección (Oriol, Briansk), con su punto de referencia.
RADIO_ZONA_KM = {"aerodromo": 5.0, "instalacion_lanzamiento": 5.0, "poligono": 10.0, "zona": 30.0}


# Metros por unidad de longitud canónica (m y km son las de los campos).
LONGITUD = {"m": 1.0, "km": 1000.0}


class CatalogoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Intervalo:
    """Lo que dicen las fuentes de una magnitud, en su unidad canónica. `minimo` o `maximo` son
    None cuando alguna fuente da una cota abierta por ese lado o no hay dato. `debil`: solo hay
    fuentes de prioridad baja. `derivado`: sale de la envolvente de otros modelos."""

    minimo: float | None
    maximo: float | None
    fuentes: tuple[str, ...]
    debil: bool = False
    derivado: bool = False

    @property
    def vacio(self) -> bool:
        return not self.fuentes

    def documento(self) -> Documento:
        resultado: Documento = {
            "min": self.minimo,
            "max": self.maximo,
            "fuentes": list(self.fuentes),
        }
        if self.debil:
            resultado["debil"] = True
        if self.derivado:
            resultado["derivado"] = True
        return resultado


SIN_DATO = Intervalo(None, None, ())


@dataclass(frozen=True)
class Texto:
    texto: str
    fuente: str


@dataclass
class Modelo:
    id: str
    nombre: str
    otros_nombres: tuple[str, ...]
    tipo_aeronave: str
    clase: str
    numeros: dict[str, Intervalo] = field(default_factory=dict)
    textos: dict[str, tuple[Texto, ...]] = field(default_factory=dict)
    derivado_de: tuple[str, ...] = ()

    def valor(self, campo: str) -> Intervalo:
        return self.numeros.get(campo, SIN_DATO)


@dataclass(frozen=True)
class Clase:
    id: str
    nombre: str
    tipo_aeronave: str
    propulsion: str
    tamano: str
    corto_alcance: bool
    clase_esquema: str | None
    aegis: tuple[str, ...]
    equivalencia_aegis: str
    modelos: tuple[str, ...]


@dataclass(frozen=True)
class Zona:
    id: str
    nombre: str
    raices: tuple[str, ...]
    excluir: tuple[str, ...]
    tipo: str
    lat: float | None
    lon: float | None
    radio_km: float | None
    fuente: str | None

    def nombra(self, texto: str) -> bool:
        minusculas = texto.lower()
        return any(r in minusculas for r in self.raices) and not any(
            e in minusculas for e in self.excluir
        )


@dataclass
class Catalogo:
    version: str
    campos: dict[str, Documento]
    fuentes: dict[str, Documento]
    modelos: dict[str, Modelo]
    clases: dict[str, Clase]
    zonas: list[Zona]
    version_zonas: str
    version_fuentes: str

    def numericos(self) -> list[str]:
        return [c for c, d in self.campos.items() if d["tipo"] == "numero"]

    def modelos_de(self, clase: str) -> list[Modelo]:
        return [self.modelos[m] for m in self.clases[clase].modelos]

    def envolvente(self, clase: str, campo: str) -> Intervalo:
        return envolvente(self.modelos_de(clase), campo)

    def zonas_de(self, texto: str) -> list[Zona]:
        return [z for z in self.zonas if z.nombra(texto)]


def _leer(ruta: Path) -> Documento:
    contenido: Documento = json.loads(ruta.read_text(encoding="utf-8"))
    return contenido


def esquema(nombre: str) -> Documento:
    return _leer(ESQUEMAS / f"{nombre}.schema.json")


def _validar(nombre: str, documento: Documento) -> None:
    errores = sorted(Draft202012Validator(esquema(nombre)).iter_errors(documento), key=str)
    if errores:
        detalle = "; ".join(f"{list(e.absolute_path)}: {e.message[:200]}" for e in errores[:5])
        raise CatalogoInvalido(f"{nombre}: {len(errores)} errores: {detalle}")


def convertir(valor: float, unidad: str, destino: str | None = None) -> float:
    """El valor en la unidad `destino` (por defecto, la canónica de su magnitud). Las
    longitudes pasan también de metros a kilómetros y al revés."""
    factor, canonica = CONVERSION[unidad]
    destino = destino or canonica
    if destino == canonica:
        return valor * factor
    if canonica in LONGITUD and destino in LONGITUD:
        return valor * factor * LONGITUD[canonica] / LONGITUD[destino]
    raise CatalogoInvalido(f"no se convierte {unidad} a {destino}")


def convertible(unidad: str, destino: str) -> bool:
    canonica = CONVERSION[unidad][1]
    return canonica == destino or (canonica in LONGITUD and destino in LONGITUD)


def intervalo(
    datos: Iterable[Documento], debiles: set[str], destino: str | None = None
) -> Intervalo:
    """Intervalo de un campo numérico con las entradas de sus fuentes. Las de fuentes débiles
    solo cuentan si no hay otras."""
    lista = [d for d in datos if "texto" not in d]
    if not lista:
        return SIN_DATO
    fuertes = [d for d in lista if d["fuente"] not in debiles]
    usadas, debil = (fuertes, False) if fuertes else (lista, True)
    minimos: list[float | None] = []
    maximos: list[float | None] = []
    for dato in usadas:
        if "valor" in dato:
            v = convertir(dato["valor"], dato["unidad"], destino)
            minimos.append(v)
            maximos.append(v)
        else:
            minimos.append(
                convertir(dato["min"], dato["unidad"], destino) if "min" in dato else None
            )
            maximos.append(
                convertir(dato["max"], dato["unidad"], destino) if "max" in dato else None
            )
    minimo = None if any(m is None for m in minimos) else min(m for m in minimos if m is not None)
    maximo = None if any(m is None for m in maximos) else max(m for m in maximos if m is not None)
    fuentes = tuple(sorted({d["fuente"] for d in usadas}))
    return Intervalo(minimo, maximo, fuentes, debil=debil)


def envolvente(modelos: list[Modelo], campo: str) -> Intervalo:
    """Mínimo de los mínimos y máximo de los máximos. Un extremo sin saber en un modelo deja sin
    saber ese extremo de la envolvente: con un modelo sin dato, la clase no tiene cota."""
    valores = [m.valor(campo) for m in modelos]
    if not valores or all(v.vacio for v in valores):
        return SIN_DATO
    minimos = [v.minimo for v in valores]
    maximos = [v.maximo for v in valores]
    return Intervalo(
        None if any(m is None for m in minimos) else min(m for m in minimos if m is not None),
        None if any(m is None for m in maximos) else max(m for m in maximos if m is not None),
        tuple(sorted({f for v in valores for f in v.fuentes})),
        debil=any(v.debil for v in valores),
        derivado=any(v.derivado for v in valores),
    )


def construir(catalogo: Documento, fuentes: Documento, zonas: Documento) -> Catalogo:
    """Valida los tres ficheros y sus referencias cruzadas y construye el catálogo."""
    _validar("catalogo_drones", catalogo)
    _validar("catalogo_fuentes", fuentes)
    _validar("zonas_lanzamiento", zonas)
    lista_fuentes: dict[str, Documento] = fuentes["fuentes"]
    debiles = {i for i, f in lista_fuentes.items() if f["prioridad"] == "baja"}
    campos: dict[str, Documento] = catalogo["campos"]
    clases_crudas = {c["id"]: c for c in catalogo["clases"]}
    errores: list[str] = []
    modelos: dict[str, Modelo] = {}
    for crudo in catalogo["modelos"]:
        if crudo["id"] in modelos:
            errores.append(f"modelo repetido: {crudo['id']}")
        if crudo["clase"] not in clases_crudas:
            errores.append(f"{crudo['id']}: clase desconocida {crudo['clase']}")
        modelo = Modelo(
            crudo["id"],
            crudo["nombre"],
            tuple(crudo["otros_nombres"]),
            crudo["tipo_aeronave"],
            crudo["clase"],
            derivado_de=tuple(crudo.get("derivado_de", ())),
        )
        for campo, contenido in crudo.get("campos", {}).items():
            if campo not in campos:
                errores.append(f"{crudo['id']}: campo desconocido {campo}")
                continue
            for dato in contenido["datos"]:
                if dato["fuente"] not in lista_fuentes:
                    errores.append(f"{crudo['id']}.{campo}: fuente desconocida {dato['fuente']}")
                es_texto = "texto" in dato
                if not es_texto and campos[campo]["tipo"] == "texto":
                    errores.append(f"{crudo['id']}.{campo}: cifra en un campo de texto")
                elif not es_texto and not convertible(dato["unidad"], campos[campo]["unidad"]):
                    errores.append(f"{crudo['id']}.{campo}: unidad {dato['unidad']} no convertible")
                elif not es_texto and "min" in dato and "max" in dato and dato["min"] > dato["max"]:
                    errores.append(f"{crudo['id']}.{campo}: mínimo mayor que el máximo")
            if campos[campo]["tipo"] == "numero":
                # Un texto en un campo numérico es cualitativo («sin ojiva»): no da cifra.
                modelo.numeros[campo] = intervalo(
                    contenido["datos"], debiles, campos[campo]["unidad"]
                )
                modelo.textos[campo] = tuple(
                    Texto(d["texto"], d["fuente"]) for d in contenido["datos"] if "texto" in d
                )
            else:
                modelo.textos[campo] = tuple(
                    Texto(d["texto"], d["fuente"]) for d in contenido["datos"]
                )
        if "campos" in crudo:
            faltan = sorted(set(campos) - set(crudo["campos"]))
            if faltan:
                errores.append(f"{crudo['id']}: faltan campos {faltan} (vacíos: sin_fuente)")
        modelos[modelo.id] = modelo
    for modelo in modelos.values():
        if not modelo.derivado_de:
            continue
        origen = [modelos[i] for i in modelo.derivado_de if i in modelos]
        if len(origen) != len(modelo.derivado_de) or any(m.derivado_de for m in origen):
            errores.append(f"{modelo.id}: derivado de modelos desconocidos o derivados")
            continue
        for campo, definicion in campos.items():
            if definicion["tipo"] != "numero":
                continue
            base = envolvente(origen, campo)
            modelo.numeros[campo] = Intervalo(
                base.minimo, base.maximo, base.fuentes, base.debil, derivado=True
            )
    clases = {}
    for id_, crudo in clases_crudas.items():
        miembros = tuple(m.id for m in modelos.values() if m.clase == id_)
        if not miembros:
            errores.append(f"clase sin modelos: {id_}")
        clases[id_] = Clase(
            id_,
            crudo["nombre"],
            crudo["tipo_aeronave"],
            crudo["propulsion"],
            crudo["tamano"],
            bool(crudo.get("corto_alcance", False)),
            crudo["clase_esquema"],
            tuple(crudo["aegis"]),
            crudo["equivalencia_aegis"],
            miembros,
        )
    lista_zonas = []
    for crudo in zonas["zonas"]:
        punto = crudo["punto"]
        fuentes_zona = [u["fuente"] for u in crudo["uso"]] + ([punto["fuente"]] if punto else [])
        errores += [
            f"zona {crudo['id']}: fuente desconocida {f}"
            for f in fuentes_zona
            if f not in lista_fuentes
        ]
        lista_zonas.append(
            Zona(
                crudo["id"],
                crudo["nombre"],
                tuple(crudo["raices"]),
                tuple(crudo.get("excluir", ())),
                crudo["tipo"],
                punto["lat"] if punto else None,
                punto["lon"] if punto else None,
                RADIO_ZONA_KM[crudo["tipo"]] if punto else None,
                punto["fuente"] if punto else None,
            )
        )
    if errores:
        raise CatalogoInvalido("; ".join(errores[:20]))
    return Catalogo(
        catalogo["version"],
        campos,
        lista_fuentes,
        modelos,
        clases,
        lista_zonas,
        zonas["version"],
        fuentes["version"],
    )


def version_viva(base: str, vivo: Documento | None) -> str:
    """Versión del catálogo con los cambios admitidos por el barrido: «1.1.0+vivo.N»."""
    if not vivo or not vivo.get("version"):
        return base
    return f"{base}+vivo.{int(vivo['version'])}"


def aplicar_vivo(
    catalogo: Documento, fuentes: Documento, vivo: Documento | None
) -> tuple[Documento, Documento]:
    """El catálogo y sus fuentes con lo que ha admitido el barrido periódico
    (recogida/catalogo_vivo.py): fuentes nuevas, modelos nuevos y cifras nuevas de modelos ya
    conocidos. Nada se quita ni se cambia: una cifra nueva se añade a las que ya hay, así que la
    envolvente de una clase solo puede ensancharse (nunca descarta más que antes por un dato
    nuevo). Sin cambios admitidos devuelve los ficheros tal cual."""
    if not vivo or not vivo.get("version"):
        return catalogo, fuentes
    catalogo = json.loads(json.dumps(catalogo))
    fuentes = json.loads(json.dumps(fuentes))
    version = version_viva(catalogo["version"], vivo)
    catalogo["version"] = version
    fuentes["version"] = version_viva(fuentes["version"], vivo)
    for id_, fuente in sorted(vivo.get("fuentes", {}).items()):
        fuentes["fuentes"].setdefault(id_, fuente)
    vacio = {"datos": [], "sin_fuente": True}
    modelos = {m["id"]: m for m in catalogo["modelos"]}
    for nuevo in vivo.get("modelos", []):
        if nuevo["id"] in modelos:
            continue
        modelo = json.loads(json.dumps(nuevo))
        modelo["campos"] = {
            c: modelo.get("campos", {}).get(c, dict(vacio)) for c in catalogo["campos"]
        }
        catalogo["modelos"].append(modelo)
        modelos[modelo["id"]] = modelo
    for entrada in vivo.get("datos", []):
        modelo = modelos.get(entrada["modelo"])
        if modelo is None or "campos" not in modelo or entrada["campo"] not in catalogo["campos"]:
            continue
        campo = modelo["campos"].setdefault(entrada["campo"], dict(vacio))
        if entrada["dato"] in campo["datos"]:
            continue
        campo["datos"] = [*campo["datos"], entrada["dato"]]
        campo["sin_fuente"] = False
        propio = modelo.setdefault("vivo", {"alta": entrada["alta"], "fuentes": []})
        if entrada["dato"]["fuente"] not in propio["fuentes"]:
            propio["fuentes"] = sorted({*propio["fuentes"], entrada["dato"]["fuente"]})
    # Las aceleraciones de los modelos nuevos se derivan como las de la configuración (ángulo de
    # inclinación, empuje/peso...), con su fórmula y sus datos de partida.
    from proceso.deduccion import aceleraciones

    return aceleraciones.con_derivadas(catalogo), fuentes


@cache
def cargar() -> Catalogo:
    return construir(_leer(CATALOGO), _leer(FUENTES), _leer(ZONAS))


def cargar_vivo(vivo: Documento | None) -> Catalogo:
    """El catálogo con los cambios admitidos por el barrido (o el de la configuración)."""
    if not vivo or not vivo.get("version"):
        return cargar()
    catalogo, fuentes = aplicar_vivo(_leer(CATALOGO), _leer(FUENTES), vivo)
    return construir(catalogo, fuentes, _leer(ZONAS))


def ficheros(vivo: Documento | None = None) -> dict[str, Documento]:
    """Los tres ficheros, con los cambios admitidos por el barrido, para la exportación."""
    catalogo, fuentes = aplicar_vivo(_leer(CATALOGO), _leer(FUENTES), vivo)
    return {
        "catalogo_drones.json": catalogo,
        "catalogo_fuentes.json": fuentes,
        "zonas_lanzamiento.json": _leer(ZONAS),
    }


def clases_con_envolvente(catalogo: Catalogo) -> Documento:
    """Las clases con sus modelos y la envolvente de cada campo numérico (para la exportación y
    para AEGIS, que la usa como límites de movimiento por clase)."""
    resultado = []
    for clase in catalogo.clases.values():
        envolventes = {
            campo: {
                **catalogo.envolvente(clase.id, campo).documento(),
                "unidad": catalogo.campos[campo]["unidad"],
            }
            for campo in catalogo.numericos()
        }
        resultado.append(
            {
                "id": clase.id,
                "nombre": clase.nombre,
                "tipo_aeronave": clase.tipo_aeronave,
                "propulsion": clase.propulsion,
                "tamano": clase.tamano,
                "corto_alcance": clase.corto_alcance,
                "clase_esquema": clase.clase_esquema,
                "aegis": list(clase.aegis),
                "equivalencia_aegis": clase.equivalencia_aegis,
                "modelos": list(clase.modelos),
                "envolvente": envolventes,
            }
        )
    return {"version_catalogo": catalogo.version, "clases": resultado}
