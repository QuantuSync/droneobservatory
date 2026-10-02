"""Tercera revisión de la calidad de los datos: un candidato por suceso, artículos que ahora se
sitúan, fechas comprobadas con su frase y lo pendiente del extractor.

Aplica a lo ya recogido las reglas nuevas que la recogida horaria aplica a lo que llega:

1. **Candidatos por suceso** (`proceso/noticias.separar`): un candidato que se agrupó antes
   de la regla de repetición se separa donde un titular dice que el suceso se repite («Flughafen
   München erneut gesperrt»). El primero conserva su identificador; cada separación queda en el
   historial con su motivo.
2. **Artículos que ahora se sitúan**: con el nomenclátor de ahora (letras como «ø» plegadas,
   palabras de base aérea, forma definida noruega), un titular que nombra una instalación que
   antes no casaba («Sonderborg», «kampflybasen på Ørlandet») entra en el candidato de esa
   instalación o abre uno nuevo, con el cambio en el historial.
3. **Búsqueda dirigida** (`recogida/busqueda_dirigida.py`): lo que dejó en disco, si se le da
   el directorio, entra como artículos por el flujo normal.
4. **Extractor**, en un lote con su propio presupuesto (modo «calidad», 2 dólares): los
   candidatos separados, los que reciben artículos nuevos, los de la búsqueda dirigida y los
   nunca extraídos con noticias de varios medios (recogida/extractor.prioritarios), en ese
   orden, hasta donde llegue el límite por el peor caso.
5. **Rehacer** todos los incidentes con las reglas de ahora (fecha comprobada con su frase,
   fusión por la actividad del suceso, un incidente por objetivo), las fusiones, los
   episodios y lo que aportan los registros oficiales (fecha oficial incluida); publicar en el
   clon y subir la base. Los cruces con FIRMS, el tráfico aéreo y las condiciones se repiten
   solos en las recogidas horarias siguientes: dependen de la fecha y su huella cambia.

Deja un informe en JSON con lo publicado antes y después.

En el servidor, con `servidor/calidad.sh`, con el mismo cerrojo que la recogida horaria.

Uso:
    python -m recogida.calidad --correo <correo> --repositorio <url> --informe <ruta>
        [--busqueda <directorio de la búsqueda dirigida>] [--lote <id de un lote enviado>]
        [--sin-llamadas]
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from exportacion.publicar import publicar
from modelo import cliente as servicio
from modelo import coste
from proceso import detalle, extraccion, incidentes
from proceso.noticias import (
    TIPO_APARENTE,
    Candidato,
    Filtro,
    Nomenclator,
    filtro,
    lugares_en,
    nomenclator,
    nuevo_candidato,
    separar,
)
from recogida import revision
from recogida.descarga import Descargador
from recogida.extractor import con_base, modelos_base, opciones_base, preparar_todas, prioritarios
from recogida.gdelt import _candidato, _documento_candidato, articulo_de_documento

registro = logging.getLogger("recogida")

MOTIVO_SEPARACION = (
    "calidad de los datos 3: un titular dice que el suceso se repite 18 horas o más después "
    "del inicio del candidato; un candidato por suceso"
)
MOTIVO_LUGARES = (
    "calidad de los datos 3: el titular nombra una instalación que el nomenclátor anterior no "
    "reconocía (letras plegadas, palabras de base aérea, forma definida noruega)"
)
# Un artículo entra en un candidato de su instalación que empezó ese día o el anterior, como
# en la agrupación (proceso/noticias.misma_ventana con precisión de día).
VENTANA_CANDIDATO = timedelta(days=1)


@dataclass
class Resumen:
    separados: list[dict[str, Any]] = field(default_factory=list)
    articulos_situados: int = 0
    candidatos_tocados: list[str] = field(default_factory=list)
    candidatos_nuevos: list[str] = field(default_factory=list)

    def documento(self) -> Documento:
        return {
            "separados": self.separados,
            "articulos_situados": self.articulos_situados,
            "candidatos_tocados": sorted(set(self.candidatos_tocados)),
            "candidatos_nuevos": sorted(set(self.candidatos_nuevos)),
        }


def _candidatos(almacen: Almacen, nom: Nomenclator) -> list[Candidato]:
    resultado = []
    for documento in almacen.candidatos():
        try:
            resultado.append(_candidato(documento, nom))
        except KeyError:
            # Un lugar del vocabulario (un lugar nuevo de una ficha): no se reagrupa.
            continue
    return resultado


def separar_candidatos(almacen: Almacen, filtro_: Filtro, nom: Nomenclator) -> list[Documento]:
    """Separa los candidatos que juntan dos sucesos del mismo sitio. Devuelve lo separado."""
    articulos = {a["url"]: articulo_de_documento(a) for a in almacen.articulos()}
    separados: list[Documento] = []
    for candidato in _candidatos(almacen, nom):
        propios = [articulos[u] for u in candidato.articulos if u in articulos]
        grupos = separar(candidato, propios, filtro_)
        if len(grupos) < 2:
            continue
        # Los artículos que ya no están en la tabla (no debería haberlos) se quedan donde
        # estaban: separar no pierde nada.
        grupos[0].articulos += [u for u in candidato.articulos if u not in articulos]
        documentos = [_documento_candidato(g) for g in grupos]
        almacen.corregir_candidatos(documentos, MOTIVO_SEPARACION)
        separados.append({
            "candidato": candidato.id,
            "en": [{"id": g.id, "articulos": len(g.articulos)} for g in grupos],
        })  # fmt: skip
    return separados


def _destino(candidatos: list[Candidato], articulo: Any, sitio: Any, tipo: str) -> Candidato | None:
    """El candidato de la instalación al que va el artículo: el más reciente de ese tipo que
    empezó ese día o el anterior, antes que el artículo."""
    posibles = [
        c for c in candidatos
        if c.lugar.id == sitio.id and c.tipo == tipo
        and c.inicio <= articulo.fecha <= c.inicio + VENTANA_CANDIDATO
    ]  # fmt: skip
    return max(posibles, key=lambda c: c.inicio) if posibles else None


def situar_en_candidatos(
    almacen: Almacen,
    pares: list[tuple[Documento, list[str]]],
    motivo: str,
    candidatos: list[Candidato] | None = None,
) -> list[str]:
    """Cada artículo entra en el candidato de cada instalación dada (o abre uno), sin salir
    del que ya tenía; sus lugares y los candidatos que cambian quedan con su motivo en el
    historial. Devuelve los candidatos tocados."""
    nom, filtro_ = nomenclator(), filtro()
    candidatos = candidatos if candidatos is not None else _candidatos(almacen, nom)
    tocados: dict[str, Candidato] = {}
    for documento, instalaciones in sorted(pares, key=lambda p: (p[0]["fecha"], p[0]["url"])):
        lugares = list(dict.fromkeys([*documento.get("lugares", []), *instalaciones]))
        almacen.corregir_lugares_articulo(documento["url"], lugares, motivo)
        articulo = articulo_de_documento({**documento, "lugares": lugares})
        for id_ in instalaciones:
            sitio = nom.lugares[id_]
            tipo = filtro_.tipo(articulo.titular, sitio)
            destino = _destino(candidatos, articulo, sitio, tipo)
            if destino is None:
                destino = nuevo_candidato(articulo, sitio, tipo, "dia")
                candidatos.append(destino)
            elif articulo.url not in destino.articulos:
                destino.articulos.append(articulo.url)
                destino.ultimo = max(destino.ultimo, articulo.fecha)
            tocados[destino.id] = destino
    almacen.corregir_candidatos([_documento_candidato(c) for c in tocados.values()], motivo)
    return list(tocados)


def situar_articulos(almacen: Almacen, filtro_: Filtro, nom: Nomenclator, resumen: Resumen) -> None:
    """Los artículos cuyo titular nombra ahora instalaciones que antes no se reconocían entran
    en sus candidatos (o abren uno), sin salir del que ya tenían."""
    existentes = {c["id"] for c in almacen.candidatos()}
    pares: list[tuple[Documento, list[str]]] = []
    for documento in almacen.articulos():
        nuevos = [
            i for i in lugares_en(documento["titular"], nom)
            if i not in documento["lugares"] and nom.lugares[i].tipo in TIPO_APARENTE
        ]  # fmt: skip
        if nuevos and filtro_.pasa(documento["titular"], tuple(nuevos)):
            pares.append((documento, nuevos))
    resumen.articulos_situados = len(pares)
    tocados = situar_en_candidatos(almacen, pares, MOTIVO_LUGARES)
    resumen.candidatos_tocados += tocados
    resumen.candidatos_nuevos += [c for c in tocados if c not in existentes]


# --- Extractor -----------------------------------------------------------------------


def para_extraer(almacen: Almacen, prioridad: list[str]) -> list[Documento]:
    """Los candidatos que necesitan ficha: primero los de `prioridad` (separados, con
    artículos nuevos, de la búsqueda dirigida) que no la tienen al día, después los nunca
    extraídos con noticias de varios medios."""
    por_id = {c["id"]: c for c in almacen.candidatos()}
    elegidos: list[Documento] = []
    vistos: set[str] = set()
    for id_ in prioridad:
        candidato = por_id.get(id_)
        if candidato is None or id_ in vistos:
            continue
        anteriores = almacen.extracciones(id_)
        if anteriores and anteriores[-1]["huella"] == incidentes.huella(candidato["articulos"]):
            continue
        elegidos.append(candidato)
        vistos.add(id_)
    elegidos += [c for c in prioritarios(almacen) if c["id"] not in vistos]
    return elegidos


def extraer(almacen: Almacen, candidatos: list[Documento], lote_id: str | None) -> Documento:
    """Un lote del extractor dentro del límite del modo calidad (o procesa uno ya enviado)."""
    cliente = servicio.Cliente(servicio.configuracion(), insistencia=servicio.HISTORICO)
    peticiones = preparar_todas(almacen, candidatos, Descargador)
    antes = almacen.gastado(coste.Modo.CALIDAD.value)
    if lote_id is not None:
        recuentos = extraccion.procesar_lote(
            almacen, cliente, cliente.lote(lote_id), peticiones, lambda: datetime.now(UTC),
            modelos_base(), coste.Modo.CALIDAD,
        )  # fmt: skip
    else:
        recuentos = extraccion.extraer_lote(
            almacen, cliente, peticiones, lambda: datetime.now(UTC), modelos_base(),
            modo=coste.Modo.CALIDAD,
        )  # fmt: skip
    return {
        **recuentos,
        "candidatos": len(candidatos),
        "gasto_usd": round(almacen.gastado(coste.Modo.CALIDAD.value) - antes, 4),
        "gasto_total_usd": round(almacen.gastado(coste.Modo.CALIDAD.value), 4),
    }


# --- Orden ---------------------------------------------------------------------------


def preparar(almacen: Almacen, busqueda: Path | None) -> tuple[Resumen, list[str]]:
    """Pasos sin llamadas: separar, situar e incorporar la búsqueda dirigida. Devuelve el
    resumen y los candidatos que tocan, en orden de prioridad."""
    filtro_, nom = filtro(), nomenclator()
    resumen = Resumen()
    resumen.separados = separar_candidatos(almacen, filtro_, nom)
    registro.info("calidad: %d candidatos separados", len(resumen.separados))
    situar_articulos(almacen, filtro_, nom, resumen)
    registro.info(
        "calidad: %d artículos situados en %d candidatos (%d nuevos)",
        resumen.articulos_situados, len(set(resumen.candidatos_tocados)),
        len(set(resumen.candidatos_nuevos)),
    )  # fmt: skip
    prioridad = [g["id"] for s in resumen.separados for g in s["en"]]
    prioridad += resumen.candidatos_tocados
    if busqueda is not None:
        from recogida import busqueda_dirigida

        hallados = busqueda_dirigida.incorporar(almacen, busqueda, datetime.now(UTC))
        registro.info("calidad: búsqueda dirigida %s", hallados.texto())
        prioridad += hallados.candidatos
    return resumen, prioridad


def orden(
    almacen: Almacen,
    ruta_informe: Path,
    busqueda: Path | None,
    lote_id: str | None,
    sin_llamadas: bool,
) -> int:
    antes = revision.foto()
    resumen, prioridad = preparar(almacen, busqueda)
    extra: Documento = {"preparacion": resumen.documento()}
    candidatos = para_extraer(almacen, prioridad)
    extra["para_extraer"] = len(candidatos)
    if not sin_llamadas and candidatos:
        extra["lote"] = extraer(almacen, candidatos, lote_id)
        registro.info("calidad: lote %s", extra["lote"])
    ahora = datetime.now(UTC)
    extra["rehacer"] = revision.rehacer(almacen, ahora, modelos_base())
    registro.info("calidad: rehecho %s", extra["rehacer"])
    extra["detalle"] = detalle.revisar(almacen, ahora, extraccion.modelos_validos(
        almacen, modelos_base())).texto()  # fmt: skip
    publicar(almacen, datetime.now(UTC))
    datos = revision.informe(almacen, antes, revision.foto(), extra)
    datos["gasto_calidad_usd"] = round(almacen.gastado(coste.Modo.CALIDAD.value), 4)
    ruta_informe.parent.mkdir(parents=True, exist_ok=True)
    ruta_informe.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    registro.info("calidad: antes %s después %s", datos["antes"], datos["despues"])
    return 0


def principal(argumentos: list[str] | None = None) -> int:
    opciones = opciones_base(__doc__)
    opciones.add_argument("--informe", type=Path, required=True, help="informe en JSON")
    opciones.add_argument("--busqueda", type=Path, help="directorio de la búsqueda dirigida")
    opciones.add_argument("--lote", help="procesa un lote ya enviado en vez de enviar otro")
    opciones.add_argument(
        "--sin-llamadas", action="store_true", help="todo menos el extractor (para medir)"
    )
    args = opciones.parse_args(argumentos)
    return con_base(
        args,
        lambda almacen: orden(almacen, args.informe, args.busqueda, args.lote, args.sin_llamadas),
    )


if __name__ == "__main__":
    sys.exit(principal())
