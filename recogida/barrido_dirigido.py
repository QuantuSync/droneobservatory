"""Barrido dirigido, una vez, desde el 1 de enero de 2025: España, puertos y presas.

Busca en los GKG de GDELT, día a día (y en los artículos que ya tiene la base), las noticias
con una palabra de dron (también en catalán,
gallego y euskera: configuracion/gdelt.json) que nombran una instalación de España o un puerto o
una presa de Europa del nomenclátor (en cualquiera de sus nombres), y las hace entrar por el flujo
normal: artículos del lugar, candidatos, extractor y reconstrucción de incidentes.

En tres tiempos:

1. **Lectura** (`leer`, sin la base, con prioridad baja): descarga los días que faltan y guarda
   todos los titulares con dron de cada día en la carpeta de la búsqueda dirigida
   (`dias/AAAA-MM-DD.jsonl.gz`, la misma caché que `recogida/busqueda_dirigida.py`), con varios
   días a la vez. Reanudable: un día guardado no se vuelve a pedir.
2. **Búsqueda** (`buscar`, sin la base): deja en `dirigido/hallados.json` los titulares que
   nombran una instalación española o un puerto o una presa, con el lugar.
3. **Incorporación y extractor** (`incorporar`, con el cerrojo de la recogida, como la revisión
   de calidad): guarda los hallados como artículos de su lugar, los agrupa en candidatos y
   extrae en un lote con su propio presupuesto (modo «dirigida», 3 dólares, una vez) los
   candidatos tocados y los nunca extraídos de esos lugares; rehace los incidentes, publica en
   el clon y sube la base.

Uso:
    python -m recogida.barrido_dirigido leer --desde 2025-01-01 [--hasta AAAA-MM-DD] [--hilos 3]
    python -m recogida.barrido_dirigido buscar [--desde ...] [--hasta ...]
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from esquema import Documento
from proceso.noticias import Nomenclator, nomenclator, normalizar
from recogida import busqueda_dirigida
from recogida.descarga import DescargaFallida
from recogida.plazo import Plazo, TiempoAgotado

registro = logging.getLogger("recogida.barrido_dirigido")

DESDE = date(2025, 1, 1)
CARPETA = "dirigido"
HALLADOS = "hallados.json"
VERSION = "1.0.0"
TIPOS_PUERTO_PRESA = frozenset({"puerto", "presa"})
# Palabras que no nombran ningún sitio concreto (tipos de instalación y palabras vacías): un
# nombre del nomenclátor tiene que tener al menos una palabra propia de 4 letras o más que no
# sea una de estas («La Central», «Presa», «Port» no nombran nada).
PALABRAS_GENERICAS = """
de del la el los las lo d i a e y o do da dos das of the and w z na v u al l s san santa sant
central centrale centrala presa barragem barrage barajul hidroelectrica hidraulica electrica
termica nuclear plaza toros estadio estadi stadium stadion stade arena campo camp municipal
futbol football aerodromo aerodrom aeropuerto aeroport airport aerea naval militar base port
porto puerto portu harbour harbor haven hafen havn hamn terminal satama morski damm dam hraz
zapora diga azud brana resclosa embalse encoro urtegi pantano rybnika vodni dilo power plant
station kraftwerk hydro reservoir lago lake ii iii ch vd cami nou
guardia civil cuartel comandancia policia nacional ejercito armada
"""
GENERICAS = frozenset(PALABRAS_GENERICAS.split())
# Una localidad española cuenta si el titular nombra una instalación de esa localidad (en
# castellano, catalán, gallego o euskera): «aeropuerto de Sevilla», «cárcel de Algeciras»,
# «central nuclear de Cofrentes». La localidad sola no (suele ser el nombre de un periódico).
# Las localidades y subestaciones no son instalaciones que se busquen por su nombre solo.
NO_BUSCADOS = frozenset({"localidad", "subestacion"})
INSTALACION_DE = re.compile(
    r"\b(?i:aeropuerto|aeroport|aeroporto|aireportu|puerto|port|porto|portu|presa|embalse|"
    r"pantano|encoro|central(?: nuclear| t[eé]rmica| hidroel[eé]ctrica)?|c[aá]rcel|"
    r"prisi[oó]n|pres[oó]|centro penitenciario|base (?:a[eé]rea|naval|militar)|cuartel|"
    r"refiner[ií]a|planta)\s+(?:de|d'|del|da|do)\s*(?:la |el |les |los |las )?"
    r"([A-ZÁÉÍÓÚÑÇ][\wÁÉÍÓÚÑÇáéíóúñç'-]+"
    r"(?:\s+(?:de |del |la )?[A-ZÁÉÍÓÚÑÇ][\wÁÉÍÓÚÑÇáéíóúñç'-]+){0,2})"
)
# Un nombre de una sola palabra tan corto casa con demasiadas cosas («Port», «Dam»).
MIN_LETRAS = 5
MOTIVO = (
    "barrido dirigido: noticia con una palabra de dron que nombra una instalación de España o un "
    "puerto o una presa de Europa"
)


def dias(desde: date, hasta: date) -> list[date]:
    return [desde + timedelta(days=n) for n in range((hasta - desde).days + 1)]


def leer(
    datos: Path,
    desde: date,
    hasta: date,
    hilos: int,
    lector: Callable[[Plazo], Callable[[datetime], list[Any]]],
    tope_s: float,
) -> Counter[str]:
    """Descarga los días que faltan, varios a la vez. Devuelve los recuentos."""
    faltan = [d for d in dias(desde, hasta) if busqueda_dirigida.cargar_dia(datos, d) is None]
    cuentas: Counter[str] = Counter({"faltaban": len(faltan)})
    plazo = Plazo(tope_s)

    def uno(dia: date) -> str:
        try:
            titulares = busqueda_dirigida.leer_dia(dia, lector(plazo), plazo)
        except (TiempoAgotado, DescargaFallida, Exception) as error:  # se reintenta otro día
            registro.info("día %s sin leer: %s", dia, type(error).__name__)
            return "sin_leer"
        busqueda_dirigida.guardar_dia(datos, dia, titulares)
        return "leidos"

    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        for resultado in grupo.map(uno, faltan):
            cuentas[resultado] += 1
    return cuentas


@cache
def lugares_buscados() -> dict[str, list[tuple[str, str]]]:
    """Nombre normalizado → [(id del lugar, tipo)] de las instalaciones de España y de los
    puertos y presas de Europa del nomenclátor."""
    nom: Nomenclator = nomenclator()
    resultado: dict[str, list[tuple[str, str]]] = {}
    for sitio in nom.lugares.values():
        if sitio.tipo in NO_BUSCADOS or (
            sitio.pais != "ES" and sitio.tipo not in TIPOS_PUERTO_PRESA
        ):
            continue
        for nombre in {sitio.nombre, *sitio.alias}:
            normal = normalizar(nombre)
            propias = [p for p in normal.split() if p not in GENERICAS and len(p) >= 4]
            if len(normal) < MIN_LETRAS or not propias:
                continue
            resultado.setdefault(normal, []).append((sitio.id, sitio.tipo))
    return resultado


@cache
def localidades_es() -> dict[str, str]:
    """Localidad española normalizada → su id en el nomenclátor."""
    nom: Nomenclator = nomenclator()
    return {
        normalizar(s.nombre): s.id
        for s in nom.lugares.values()
        if s.pais == "ES" and s.tipo == "localidad" and len(normalizar(s.nombre)) >= MIN_LETRAS
    }


def hallar(
    titulares: list[Documento], nombres: dict[str, list[tuple[str, str]]]
) -> list[Documento]:
    """Los titulares que nombran alguno de los lugares buscados, con el lugar. Se buscan los
    grupos de hasta MAX_PALABRAS palabras seguidas del titular en el índice de nombres."""
    largo = max((n.count(" ") + 1 for n in nombres), default=1)
    hallados = []
    for documento in titulares:
        palabras = normalizar(documento["titular"]).split()
        # Un nombre de una sola palabra solo cuenta escrito con mayúscula: «halla», «bassa» o
        # «pistas» son palabras corrientes en otros titulares.
        propias = {
            normalizar(w) for w in re.findall(r"[^\W\d_]+", documento["titular"]) if w[0].isupper()
        }
        lugares: set[str] = set()
        for i in range(len(palabras)):
            for j in range(i + 1, min(len(palabras), i + largo) + 1):
                if j == i + 1 and palabras[i] not in propias:
                    continue
                for id_, _ in nombres.get(" ".join(palabras[i:j]), ()):
                    lugares.add(id_)
        if not lugares:
            localidades = localidades_es()
            for m in INSTALACION_DE.finditer(documento["titular"]):
                nombre = normalizar(m.group(1)).split()
                for j in range(len(nombre), 0, -1):
                    localidad = localidades.get(" ".join(nombre[:j]))
                    if localidad:
                        lugares.add(localidad)
                        break
        if lugares:
            hallados.append({**documento, "lugares_dirigidos": sorted(lugares)})
    return hallados


def buscar(datos: Path, desde: date, hasta: date) -> Documento:
    """Recorre los días guardados y deja lo hallado. Devuelve el resumen."""
    nombres = lugares_buscados()
    hallados: list[Documento] = []
    leidos = 0
    for dia in dias(desde, hasta):
        titulares = busqueda_dirigida.cargar_dia(datos, dia)
        if titulares is None:
            continue
        leidos += 1
        hallados += hallar(titulares, nombres)
    vistos: dict[str, Documento] = {}
    for documento in hallados:
        vistos.setdefault(documento["url"], documento)
    resultado = {
        "version": VERSION,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "dias_leidos": leidos,
        "articulos": sorted(vistos.values(), key=lambda d: (d["fecha"], d["url"])),
    }
    destino = datos / CARPETA / HALLADOS
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8", newline="\n") as fichero:
        fichero.write(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n")
    temporal.replace(destino)
    articulos: list[Documento] = resultado["articulos"]  # type: ignore[assignment]
    return {k: v for k, v in resultado.items() if k != "articulos"} | {"articulos": len(articulos)}


def articulos_de_la_base(almacen: Any, desde: date = DESDE) -> list[tuple[Documento, list[str]]]:
    """Los artículos de la base desde `desde` cuyo titular nombra un lugar buscado (España,
    puertos y presas) que no está entre sus lugares."""
    nombres = lugares_buscados()
    resultado = []
    for documento in almacen.articulos():
        if str(documento.get("fecha", ""))[:10] < desde.isoformat():
            continue
        hallado = hallar([documento], nombres)
        if not hallado:
            continue
        faltan = [i for i in hallado[0]["lugares_dirigidos"] if i not in documento["lugares"]]
        if faltan:
            resultado.append((documento, faltan))
    return resultado


def candidatos_de_lugares(almacen: Any, lugares: set[str]) -> list[str]:
    """Los candidatos de los lugares buscados que nunca han pasado por el extractor."""
    resultado = []
    for candidato in almacen.candidatos():
        if candidato.get("lugar") in lugares and not almacen.extracciones(candidato["id"]):
            resultado.append(candidato["id"])
    return resultado


def incorporar(
    almacen: Any, datos: Path, informe: Path, lote_id: str | None, sin_llamadas: bool
) -> int:
    """Hallados → artículos y candidatos; lote del extractor (modo «dirigida»); rehacer,
    publicar en el clon e informe. La base la sube quien llama (recogida.extractor.con_base)."""
    from exportacion.publicar import publicar
    from modelo import coste
    from proceso import detalle, extraccion, incidentes
    from recogida import calidad, revision
    from recogida.extractor import modelos_base

    antes = revision.foto()
    ruta = datos / CARPETA / HALLADOS
    hallados = json.loads(ruta.read_text(encoding="utf-8"))["articulos"] if ruta.exists() else []
    nuevos: list[tuple[Documento, list[str]]] = []
    for documento in hallados:
        lugares = documento.pop("lugares_dirigidos")
        if almacen.guardar_articulo({**documento, "lugares": lugares}):
            nuevos.append((documento, lugares))
        else:
            existente = almacen.articulos_de([documento["url"]])
            if existente and not existente[0]["candidato"]:
                nuevos.append((existente[0], lugares))
    # Y los artículos que ya tiene la base (recogidos con el filtro general) cuyo titular nombra
    # un lugar buscado que no tenían.
    vistos = {d["url"] for d, _ in nuevos}
    for documento, lugares in articulos_de_la_base(almacen):
        if documento["url"] not in vistos:
            nuevos.append((documento, lugares))
    tocados = calidad.situar_en_candidatos(almacen, nuevos, MOTIVO)
    buscados = {i for lista in lugares_buscados().values() for i, _ in lista}
    prioridad = list(dict.fromkeys([*tocados, *candidatos_de_lugares(almacen, buscados)]))
    por_id = {c["id"]: c for c in almacen.candidatos()}
    elegidos = []
    for id_ in prioridad:
        candidato = por_id.get(id_)
        if candidato is None:
            continue
        anteriores = almacen.extracciones(id_)
        if anteriores and anteriores[-1]["huella"] == incidentes.huella(candidato["articulos"]):
            continue
        elegidos.append(candidato)
    extra: Documento = {
        "hallados": len(hallados), "articulos_nuevos": len(nuevos),
        "candidatos_tocados": len(tocados), "para_extraer": len(elegidos),
    }  # fmt: skip
    if not sin_llamadas and elegidos:
        extra["lote"] = calidad.extraer(almacen, elegidos, lote_id, coste.Modo.DIRIGIDA)
        registro.info("dirigido: lote %s", extra["lote"])
    ahora = datetime.now(UTC)
    extra["rehacer"] = revision.rehacer(almacen, ahora, modelos_base())
    extra["detalle"] = detalle.revisar(
        almacen, ahora, extraccion.modelos_validos(almacen, modelos_base())
    ).texto()
    publicar(almacen, datetime.now(UTC))
    resultado = revision.informe(almacen, antes, revision.foto(), extra)
    resultado["gasto_dirigida_usd"] = round(almacen.gastado(coste.Modo.DIRIGIDA.value), 4)
    informe.parent.mkdir(parents=True, exist_ok=True)
    informe.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    registro.info("dirigido: antes %s después %s", resultado["antes"], resultado["despues"])
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = argparse.ArgumentParser(description=__doc__)
    orden = opciones.add_subparsers(dest="orden", required=True)
    for nombre in ("leer", "buscar"):
        sub = orden.add_parser(nombre)
        sub.add_argument("--datos", type=Path, default=None)
        sub.add_argument("--desde", type=date.fromisoformat, default=DESDE)
        sub.add_argument(
            "--hasta",
            type=date.fromisoformat,
            default=(datetime.now(UTC) - timedelta(days=1)).date(),
        )
        if nombre == "leer":
            sub.add_argument("--hilos", type=int, default=3)
            sub.add_argument("--tope-h", type=float, default=20.0)
    if argumentos is None and len(sys.argv) > 1 and sys.argv[1] == "incorporar":
        return _incorporar(sys.argv[2:])
    args = opciones.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    datos = args.datos or busqueda_dirigida.directorio_datos()
    if args.orden == "leer":
        cuentas = leer(datos, args.desde, args.hasta, args.hilos,
                       busqueda_dirigida._lector, args.tope_h * 3600)  # fmt: skip
        registro.info("lectura: %s", dict(cuentas))
        return 0
    registro.info("búsqueda: %s", json.dumps(buscar(datos, args.desde, args.hasta)))
    return 0


def _incorporar(argumentos: list[str]) -> int:
    """`incorporar --correo ... --repositorio ... --informe ... [--datos] [--lote] [--sin-llamadas]`
    con la base de la rama estado (la descarga y la sube recogida.extractor.con_base)."""
    from recogida.extractor import con_base, opciones_base

    opciones = opciones_base(__doc__)
    opciones.add_argument("--informe", type=Path, required=True)
    opciones.add_argument("--datos", type=Path, default=None)
    opciones.add_argument("--lote", help="procesa un lote ya enviado en vez de enviar otro")
    opciones.add_argument("--sin-llamadas", action="store_true")
    args = opciones.parse_args(argumentos)
    datos = args.datos or busqueda_dirigida.directorio_datos()
    return con_base(
        args, lambda almacen: incorporar(almacen, datos, args.informe, args.lote, args.sin_llamadas)
    )


if __name__ == "__main__":
    sys.exit(principal())
