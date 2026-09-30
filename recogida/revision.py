"""Revisión de todo lo publicado con las reglas de calidad de los datos.

Vuelve a extraer, en un solo lote, todos los candidatos que ya pasaron por el
extractor (del histórico y de la recogida horaria) con la ficha actual, que separa
el lugar del suceso de los demás lugares de la noticia y trae las declaraciones
oficiales citadas. Después rehace todos los incidentes con las reglas actuales
(ubicación, tipo, presencia del dron, cierre), deshace las fusiones y los
episodios y los vuelve a calcular, y publica.

El gasto tiene su propio límite (modo «revision», 5 dólares). Antes del lote se
hacen unas llamadas directas de muestra y se calcula lo que costaría: si el total
previsto pasa del límite, el lote no se envía.

Deja un informe en JSON con lo publicado antes y después, leído de los propios
ficheros publicados: incidentes en el mapa y sin ubicación, cambios de sitio, de
tipo, de estado y de presencia del dron, episodios deshechos, una muestra al azar
con semilla fija y la comparación con la lista de Wikipedia de 2025.

En el servidor se lanza con `servidor/revision.sh`, con el mismo cerrojo que la
recogida horaria para que nunca escriban a la vez en la base.

Uso:
    python -m recogida.revision --correo <correo> --repositorio <url> --informe <ruta>
        [--muestra 10] [--lote <id de un lote ya enviado>]
"""

import json
import logging
import math
import random
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from exportacion.publicar import DIRECTORIO, INCIDENTES, SIN_UBICACION, publicar
from modelo import cliente as servicio
from modelo import coste, ficha
from proceso import extraccion, incidentes, incursiones
from recogida import comparacion
from recogida.descarga import Descargador
from recogida.extractor import con_base, modelos_base, opciones_base, preparar_todas

registro = logging.getLogger("recogida")

SEMILLA = 1
MUESTRA_COSTE = 10
MUESTRA_INFORME = 20
# Un punto que se mueve menos que esto es el mismo sitio (el redondeo de las coordenadas y
# el cambio de un aeropuerto por su ficha del nomenclátor ampliado).
CAMBIO_SITIO_KM = 1.0
RADIO_TIERRA_KM = 6371.0


def candidatos(almacen: Almacen) -> list[Documento]:
    """Los candidatos ya extraídos cuya última ficha es de una versión anterior."""
    return [
        c
        for c in almacen.candidatos()
        if (e := almacen.extracciones(c["id"])) and e[-1]["version"] != ficha.VERSION
    ]


# --- Coste ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Prevision:
    muestra: int
    medio_directo: float
    restantes: int
    lote: float
    gastado: float

    @property
    def total(self) -> float:
        return self.gastado + self.lote

    @property
    def cabe(self) -> bool:
        return self.total <= coste.LIMITE_REVISION_USD


def estimar(
    almacen: Almacen,
    cliente: extraccion.Servicio,
    pendientes: list[Documento],
    ahora: datetime,
    muestra: int,
    descargador: Any = Descargador,
) -> Prevision | None:
    """Llamadas directas de muestra y coste previsto del lote con los demás candidatos."""
    elegidos = random.Random(SEMILLA).sample(pendientes, min(muestra, len(pendientes)))
    antes = len(almacen.llamadas())
    peticiones = preparar_todas(almacen, elegidos, descargador)
    extraidas = extraccion.extraer(
        almacen, cliente, peticiones, ahora, coste.Modo.REVISION, modelos_base()
    )
    if extraidas.parada is not None:
        registro.warning("muestra cortada por %s: %s", extraidas.parada, extraidas.motivo)
    hechas = almacen.llamadas()[antes:]
    if not hechas:
        return None
    medio = sum(ll["coste"] for ll in hechas) / len(hechas)
    restantes = len(pendientes) - len(hechas)
    return Prevision(
        muestra=len(hechas),
        medio_directo=medio,
        restantes=restantes,
        lote=medio * coste.DESCUENTO_LOTE * restantes,
        gastado=almacen.gastado(coste.Modo.REVISION.value),
    )


# --- Rehacer -------------------------------------------------------------------------


def rehacer(almacen: Almacen, ahora: datetime, modelos_base: frozenset[str]) -> dict[str, int]:
    """Todos los incidentes con las reglas actuales; fusiones y episodios, de nuevo."""
    for fusion in almacen.fusiones():
        if not fusion["revertida"]:
            almacen.revertir_fusion(fusion["absorbido"])
    rehechos = extraccion.reconstruir(almacen, ahora, modelos_base, rehacer=True)
    vocabulario = extraccion.modelos_validos(almacen, modelos_base)
    rehechas = incursiones.registrar(almacen, ahora, vocabulario)
    for incidente in almacen.incidentes():
        if "fusionado_en" in incidente:
            documento = {k: v for k, v in incidente.items() if k != "fusionado_en"}
            almacen.guardar_incidente(documento, ahora, vocabulario)
    return {
        "rehechos": rehechos,
        "incursiones_rehechas": rehechas,
        "fusiones": incidentes.fusionar(almacen, ahora, vocabulario),
        "cambios_episodio": incidentes.agrupar_episodios(almacen, ahora, vocabulario),
    }


# --- Informe -------------------------------------------------------------------------


def _leer(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def foto(directorio: Path = DIRECTORIO) -> dict[str, Documento]:
    """Lo publicado, por incidente: sitio (o ninguno), país, tipo, estado, presencia,
    episodio, título y primer enlace."""
    resultado: dict[str, Documento] = {}
    coleccion = _leer(directorio / INCIDENTES) or {"features": []}
    sin_punto = _leer(directorio / SIN_UBICACION) or {"incidentes": []}
    entradas = [(f["properties"], f["geometry"]["coordinates"]) for f in coleccion["features"]]
    entradas += [(i, None) for i in sin_punto["incidentes"]]
    for propiedades, coordenadas in entradas:
        resultado[propiedades["id"]] = {
            "punto": [coordenadas[1], coordenadas[0]] if coordenadas else None,
            "pais": propiedades["lugar"]["pais"],
            "region": propiedades["lugar"].get("region"),
            "tipo": propiedades["tipo"],
            "estado": propiedades["estado"]["actual"],
            "presencia_dron": propiedades.get("presencia_dron"),
            "cierre": propiedades.get("consecuencias", {}).get("cierre", {}).get("valor"),
            "episodio": propiedades.get("episodio"),
            "inicio": propiedades["tiempo"]["inicio"]["valor"],
            "titulo": propiedades["titulo"]["es"],
            "enlace": propiedades["fuentes"][0]["enlace"],
        }
    return resultado


def _km(a: list[float], b: list[float]) -> float:
    f1, f2 = math.radians(a[0]), math.radians(b[0])
    df, dl = f2 - f1, math.radians(b[1] - a[1])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def _episodios(publicado: dict[str, Documento]) -> dict[str, list[str]]:
    grupos: dict[str, list[str]] = {}
    for id_, datos in sorted(publicado.items()):
        if datos["episodio"]:
            grupos.setdefault(datos["episodio"], []).append(id_)
    return grupos


def _wikipedia(publicado: dict[str, Documento]) -> Documento:
    puntos = [
        comparacion.Punto(id_, date.fromisoformat(d["inicio"][:10]), d["punto"][0], d["punto"][1],
                          None)
        for id_, d in publicado.items() if d["punto"]
    ]  # fmt: skip
    resultado = comparacion.comparar(comparacion.referencia(), puntos)
    return {
        "encontrados": sum(1 for _, ids in resultado if ids),
        "sucesos": len(resultado),
        "tabla": comparacion.tabla(resultado),
    }


def cambios(antes: dict[str, Documento], despues: dict[str, Documento]) -> Documento:
    comunes = sorted(set(antes) & set(despues))

    def distintos(campo: str) -> list[str]:
        return [i for i in comunes if antes[i][campo] != despues[i][campo]]

    de_sitio = [
        i
        for i in comunes
        if (antes[i]["punto"] is None) != (despues[i]["punto"] is None)
        or (
            antes[i]["punto"] is not None
            and despues[i]["punto"] is not None
            and _km(antes[i]["punto"], despues[i]["punto"]) >= CAMBIO_SITIO_KM
        )
    ]
    episodios_antes, episodios_despues = _episodios(antes), _episodios(despues)
    return {
        "retirados": sorted(set(antes) - set(despues)),
        "nuevos": sorted(set(despues) - set(antes)),
        "sitio": de_sitio,
        "sin_punto_ahora": [i for i in de_sitio if despues[i]["punto"] is None],
        "tipo": distintos("tipo"),
        "estado": distintos("estado"),
        "presencia_dron": distintos("presencia_dron"),
        "cierre": distintos("cierre"),
        "episodios_deshechos": sorted(
            e for e, miembros in episodios_antes.items() if episodios_despues.get(e) != miembros
        ),
        "episodios_nuevos": sorted(
            e for e, miembros in episodios_despues.items() if episodios_antes.get(e) != miembros
        ),
    }


def resumen(publicado: dict[str, Documento]) -> Documento:
    en_mapa = sum(1 for d in publicado.values() if d["punto"])
    return {
        "publicados": len(publicado),
        "en_mapa": en_mapa,
        "sin_ubicacion": len(publicado) - en_mapa,
        "episodios": len(_episodios(publicado)),
    }


def muestra(almacen: Almacen, publicado: dict[str, Documento]) -> list[Documento]:
    """Incidentes al azar, con semilla fija, con su lugar del suceso para comprobarlos."""
    elegidos = random.Random(SEMILLA).sample(sorted(publicado), min(MUESTRA_INFORME,
                                                                     len(publicado)))  # fmt: skip
    resultado = []
    for id_ in sorted(elegidos):
        documento = almacen.incidente(id_) or {"lugar": {}}
        resultado.append({
            "id": id_, **publicado[id_],
            "suceso": documento["lugar"].get("suceso"),
            "nivel": documento["lugar"].get("nivel"),
            "geocodificacion": documento["lugar"].get("geocodificacion"),
        })  # fmt: skip
    return resultado


def informe(
    almacen: Almacen,
    antes: dict[str, Documento],
    despues: dict[str, Documento],
    extra: Documento,
) -> Documento:
    return {
        "fecha": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "antes": resumen(antes),
        "despues": resumen(despues),
        "cambios": cambios(antes, despues),
        "muestra": muestra(almacen, despues),
        "wikipedia": {"antes": _wikipedia(antes), "despues": _wikipedia(despues)},
        "gasto_revision_usd": round(almacen.gastado(coste.Modo.REVISION.value), 4),
        "publicado_antes": antes,
        "publicado_despues": despues,
        **extra,
    }


# --- Orden ---------------------------------------------------------------------------


def orden(almacen: Almacen, muestra_coste: int, ruta_informe: Path, lote_id: str | None) -> int:
    antes = foto()
    cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
    pendientes = sorted(candidatos(almacen), key=lambda c: c["id"])
    registro.info("revisión: %d candidatos con ficha anterior", len(pendientes))
    extra: Documento = {"candidatos": len(pendientes)}
    if lote_id is None and pendientes:
        prevision = estimar(almacen, cliente, pendientes, datetime.now(UTC), muestra_coste)
        if prevision is None:
            registro.error("sin llamadas de muestra: no se puede estimar")
            return 1
        extra["prevision"] = {**prevision.__dict__, "total": prevision.total}
        registro.info("previsión %s total=%.4f", prevision, prevision.total)
        if not prevision.cabe:
            registro.error(
                "el lote no cabe en el límite: %.4f > %.2f USD; no se envía",
                prevision.total, coste.LIMITE_REVISION_USD,
            )  # fmt: skip
            return 1
    pendientes = sorted(candidatos(almacen), key=lambda c: c["id"])
    peticiones = preparar_todas(almacen, pendientes, Descargador)
    if lote_id is not None:
        lote = cliente.lote(lote_id)
        extra["lote"] = extraccion.procesar_lote(
            almacen, cliente, lote, peticiones, lambda: datetime.now(UTC), modelos_base(),
            coste.Modo.REVISION,
        )  # fmt: skip
    elif peticiones:
        extra["lote"] = extraccion.extraer_lote(
            almacen, cliente, peticiones, lambda: datetime.now(UTC), modelos_base(),
            modo=coste.Modo.REVISION,
        )  # fmt: skip
    registro.info("lote %s", extra.get("lote"))
    extra["rehacer"] = rehacer(almacen, datetime.now(UTC), modelos_base())
    registro.info("rehecho %s", extra["rehacer"])
    publicar(almacen, datetime.now(UTC))
    datos = informe(almacen, antes, foto(), extra)
    ruta_informe.parent.mkdir(parents=True, exist_ok=True)
    ruta_informe.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    registro.info("revisión: antes %s después %s", datos["antes"], datos["despues"])
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = opciones_base(__doc__)
    opciones.add_argument("--informe", type=Path, required=True, help="informe en JSON")
    opciones.add_argument("--muestra", type=int, default=MUESTRA_COSTE)
    opciones.add_argument("--lote", help="procesa un lote ya enviado en vez de enviar otro")
    args = opciones.parse_args(argumentos)
    return con_base(args, lambda almacen: orden(almacen, args.muestra, args.informe, args.lote))


if __name__ == "__main__":
    sys.exit(principal())
