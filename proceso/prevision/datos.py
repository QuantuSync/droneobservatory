"""Lo que necesita la previsión, sacado de los ficheros publicados.

Se calcula con lo mismo que ve cualquiera (`publicacion/incidentes.geojson`,
`incidentes_sin_ubicacion.json` y `ucrania.json`), no con la base: la comprobación con el pasado
que corre en la integración continua usa una copia fija de esto mismo
(`tests/fixtures/prevision/datos.json.gz`), así que lo que se publica y lo que se comprueba
salen del mismo cálculo.

- Un incidente cuenta una vez, por la fecha del suceso (no la de la noticia): los fundidos en
  otro ya no se publican y los desmentidos no cuentan.
- La noche de un incidente es la de su ataque si está enlazado con uno; si no, la que acaba el
  día de su inicio (o la que empieza ese día si se sabe la hora y es de tarde, desde las 15:00
  UTC, las 18:00 en Kiev).
- Cada noche de ataque sobre Ucrania suma los drones lanzados de los partes de la Fuerza Aérea
  de Ucrania de esa noche (sin los tramos ya incluidos en otro parte) y anota si alguno salió de
  Crimea.
"""

import gzip
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso import zona

# Zonas de lanzamiento de Crimea, como las escribe la Fuerza Aérea de Ucrania
# (configuracion/zonas_lanzamiento_nombres.json): el camino del sur, hacia el Danubio.
ZONAS_CRIMEA = frozenset(
    {"Чауда", "Гвардійське", "Крим", "Балаклава", "Кача", "Джанкой", "Бельбек"}
)
HORA_TARDE_UTC = 15


@dataclass(frozen=True)
class Incidente:
    id: str
    pais: str
    dia: date
    noche: date
    grupo: str
    tipo: str


@dataclass(frozen=True)
class Impacto:
    """Impacto con lugar de la capa de guerra sobre Ucrania (sin los partes diarios de primera
    línea): su día, sus tipos de objetivo y los canales que lo cuentan."""

    dia: date
    categorias: tuple[str, ...]
    canales: tuple[str, ...]


@dataclass(frozen=True)
class Noche:
    """Noche de ataque ruso sobre Ucrania; `fecha` es el día en que acaba."""

    fecha: date
    lanzados: float
    desde_crimea: bool


@dataclass(frozen=True)
class Datos:
    incidentes: tuple[Incidente, ...]
    noches: dict[date, Noche]
    # Último día con datos: el de la fecha de cálculo.
    hasta: date
    # Caja (lon mín., lat mín., lon máx., lat máx.) de cada país, para llevar el mapa a él.
    cajas: dict[str, tuple[float, float, float, float]]
    impactos: tuple[Impacto, ...] = ()


def _dia(valor: str) -> date:
    return date.fromisoformat(valor[:10])


def _numero(valor: Any) -> float | None:
    if isinstance(valor, dict) and "min" in valor and "max" in valor:
        return (float(valor["min"]) + float(valor["max"])) / 2
    return None


def noche_del_incidente(propiedades: Documento) -> date:
    ataque = propiedades.get("ataque")
    if ataque and ataque.get("jornada"):
        return _dia(ataque["jornada"]["hasta"])
    inicio = propiedades["tiempo"]["inicio"]
    dia = _dia(inicio["valor"])
    if inicio["precision"] in ("minuto", "hora") and int(inicio["valor"][11:13]) >= HORA_TARDE_UTC:
        return dia + timedelta(days=1)
    return dia


def _incidente(propiedades: Documento, punto: tuple[float, float] | None) -> Incidente | None:
    if propiedades.get("estado", {}).get("actual") == "desmentido":
        return None
    grupo = (propiedades.get("zona") or {}).get("grupo")
    if grupo not in zona.GRUPOS:
        documento = dict(propiedades)
        if punto is not None:
            documento["lugar"] = {**documento["lugar"], "punto": {"lat": punto[1], "lon": punto[0]}}
        grupo = zona.clasificar(documento)["grupo"]
    return Incidente(
        id=str(propiedades["id"]),
        pais=str(propiedades["lugar"]["pais"]),
        dia=_dia(propiedades["tiempo"]["inicio"]["valor"]),
        noche=noche_del_incidente(propiedades),
        grupo=str(grupo),
        tipo=str(propiedades["tipo"]),
    )


def noches_de_ataque(ataques: Iterable[Documento]) -> dict[date, Noche]:
    suma: dict[date, float] = {}
    crimea: dict[date, bool] = {}
    for ataque in ataques:
        if ataque.get("sentido") != "RU_UA" or ataque.get("incluido_en"):
            continue
        if ataque.get("jornada", {}).get("tipo") != "noche":
            continue
        fecha = _dia(ataque["jornada"]["hasta"])
        lanzados = _numero(ataque.get("lanzados", {}).get("total"))
        suma[fecha] = suma.get(fecha, 0.0) + (lanzados or 0.0)
        zonas = {z for z in ataque.get("zonas_lanzamiento", []) if isinstance(z, str)}
        crimea[fecha] = crimea.get(fecha, False) or bool(zonas & ZONAS_CRIMEA)
    return {f: Noche(f, suma[f], crimea[f]) for f in sorted(suma)}


def impactos_de_guerra(impactos: Iterable[Documento]) -> tuple[Impacto, ...]:
    resultado = []
    for impacto in impactos:
        if impacto.get("sentido") != "RU_UA" or impacto.get("parte_diario"):
            continue
        canales = sorted({f["id"].rsplit("-", 1)[0] for f in impacto.get("fuentes", [])})
        resultado.append(
            Impacto(
                _dia(impacto.get("dia") or impacto["fecha"]["valor"]),
                tuple(sorted(impacto.get("categorias_objetivo", []))),
                tuple(canales),
            )
        )
    return tuple(sorted(resultado, key=lambda i: (i.dia, i.categorias, i.canales)))


def cajas_de_paises(paises: Iterable[str]) -> dict[str, tuple[float, float, float, float]]:
    """La caja del polígono más grande de cada país (sin territorios lejanos)."""
    from proceso import fronteras

    datos = fronteras.fronteras()
    resultado = {}
    for pais in sorted(set(paises)):
        poligonos = datos.paises.get(pais, ())
        if not poligonos:
            continue
        mayor = max(poligonos, key=lambda p: (p.caja[2] - p.caja[0]) * (p.caja[3] - p.caja[1]))
        resultado[pais] = tuple(round(v, 2) for v in mayor.caja)
    return resultado  # type: ignore[return-value]


def desde_publicados(
    incidentes: Documento, sin_ubicacion: Documento, ucrania: Documento, hasta: date
) -> Datos:
    lista: list[Incidente] = []
    for feature in incidentes.get("features", []):
        coordenadas = (feature.get("geometry") or {}).get("coordinates")
        punto = (float(coordenadas[0]), float(coordenadas[1])) if coordenadas else None
        hallado = _incidente(feature["properties"], punto)
        if hallado is not None:
            lista.append(hallado)
    for propiedades in sin_ubicacion.get("incidentes", []):
        hallado = _incidente(propiedades, None)
        if hallado is not None:
            lista.append(hallado)
    lista.sort(key=lambda i: (i.dia, i.id))
    return Datos(
        incidentes=tuple(lista),
        noches=noches_de_ataque(ucrania.get("ataques", [])),
        hasta=hasta,
        cajas=cajas_de_paises(i.pais for i in lista),
        impactos=impactos_de_guerra(ucrania.get("impactos", [])),
    )


def leer_publicados(directorio: Path, hasta: date) -> Datos:
    def leer(nombre: str) -> Documento:
        ruta = directorio / nombre
        if not ruta.exists():
            return {}
        documento: Documento = json.loads(ruta.read_text(encoding="utf-8"))
        return documento

    return desde_publicados(
        leer("incidentes.geojson"),
        leer("incidentes_sin_ubicacion.json"),
        leer("ucrania.json"),
        hasta,
    )


# --- Copia compacta, para la comprobación fija de la integración continua -------------------


def compactos(datos: Datos) -> Documento:
    return {
        "hasta": datos.hasta.isoformat(),
        "incidentes": [
            [i.id, i.pais, i.dia.isoformat(), i.noche.isoformat(), i.grupo, i.tipo]
            for i in datos.incidentes
        ],
        "noches": [
            [n.fecha.isoformat(), round(n.lanzados, 1), int(n.desde_crimea)]
            for n in datos.noches.values()
        ],
        "cajas": {p: list(c) for p, c in datos.cajas.items()},
        "impactos": [
            [i.dia.isoformat(), list(i.categorias), list(i.canales)] for i in datos.impactos
        ],
    }


def de_compactos(documento: Documento) -> Datos:
    incidentes = tuple(
        Incidente(i[0], i[1], date.fromisoformat(i[2]), date.fromisoformat(i[3]), i[4], i[5])
        for i in documento["incidentes"]
    )
    noches = {
        date.fromisoformat(n[0]): Noche(date.fromisoformat(n[0]), float(n[1]), bool(n[2]))
        for n in documento["noches"]
    }
    cajas = {p: (c[0], c[1], c[2], c[3]) for p, c in documento["cajas"].items()}
    impactos = tuple(
        Impacto(date.fromisoformat(i[0]), tuple(i[1]), tuple(i[2]))
        for i in documento.get("impactos", [])
    )
    return Datos(incidentes, noches, date.fromisoformat(documento["hasta"]), cajas, impactos)


def leer_compactos(ruta: Path) -> Datos:
    with gzip.open(ruta, "rt", encoding="utf-8") as fichero:
        documento: Documento = json.load(fichero)
    return de_compactos(documento)


def escribir_compactos(datos: Datos, ruta: Path) -> None:
    contenido = json.dumps(compactos(datos), ensure_ascii=False, separators=(",", ":"))
    with gzip.GzipFile(ruta, "wb", mtime=0) as fichero:
        fichero.write(contenido.encode("utf-8"))


def log1p(valor: float) -> float:
    return math.log1p(max(0.0, valor))
