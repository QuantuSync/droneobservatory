"""Segunda lectura que busca lo que falta (proceso/segunda_busqueda.py, docs/segunda_lectura.md).

Dos partes, como el resto de la capa:

- **En la pasada** (recogida/segunda_lectura.pasada), con la base principal abierta solo para leer:
  las búsquedas de declaraciones oficiales, incidentes que faltan, atribución y lugar o duración,
  cada una con su cupo por pasada (configuracion/segunda_lectura.json, «busqueda»), y una vez al
  día, desde las 03:00 UTC, el barrido de un país (rotando, de más a menos incidentes) sin el
  filtro de antigüedad. Lo que se manda se guarda con su huella en la base de la capa
  (`busquedas`) y no se vuelve a preguntar mientras no cambie. Los hallazgos son candidatos.
- **En la recogida horaria** (`entregar`), cada candidato por el camino que ya existe, sin
  decidir nada:
  - declaraciones y atribución: el artículo entra en el candidato de la ficha y su frase va a
    la extracción (el cursor interno de los artículos dirigidos), y el candidato se repite con el
    experto con el motivo opcional «declaracion» (proceso/escalado.py: si el experto agotó su
    tope, vale el base y no espera; nunca la reserva crítica). El estado y la atribución los
    deciden las reglas de siempre (proceso/declaraciones.py, la regla estricta de
    proceso/atribucion.py);
  - incidentes que faltan: la noticia vuelve a la extracción normal por el mismo camino que los
    artículos dirigidos (sin escribir en configuracion/articulos_dirigidos.json); si su candidato
    ya se extrajo, se repite con el experto. Pasa por el control de duplicados como cualquier
    otra ficha;
  - lugar y duración: la verificación del experto (recogida/segunda_lectura.verificar).
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from modelo import coste, paginas
from proceso import extraccion
from proceso import segunda_busqueda as busqueda
from proceso.noticias import nomenclator
from recogida import articulos_dirigidos, control_fichas, rectificaciones
from recogida.descarga import Descargador, DescargaFallida

registro = logging.getLogger(__name__)

MOTIVO = "segunda lectura: búsqueda de lo que falta"
ESTADO_BARRIDO = "barrido_pais"


def conf() -> Documento:
    from recogida import segunda_lectura

    datos: Documento = segunda_lectura.configuracion()["busqueda"]
    return datos


def _iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Los textos que se mandan ---------------------------------------------------------------


class Textos:
    """Las noticias como se mandan: titular y comienzo de la página (o, si no se descarga, la
    frase guardada). Una sola descarga por dirección en la pasada."""

    def __init__(self, principal: Almacen, descargador: Descargador | None) -> None:
        self.principal, self.descargador = principal, descargador
        self._cache: dict[str, str] = {}

    def de(self, url: str, medio: str, fecha: str, respaldo: str = "") -> busqueda.Texto:
        if url not in self._cache:
            articulo = next(iter(self.principal.articulos_de([url])), None)
            titular = str((articulo or {}).get("titular") or "")
            cuerpo = ""
            if self.descargador is not None:
                try:
                    html = self.descargador.texto(url, paginas.es_html)
                    cuerpo = paginas.primeras_frases(html, busqueda.MAX_LETRAS_TEXTO)
                except DescargaFallida:
                    cuerpo = ""
            partes = [titular, cuerpo or respaldo]
            texto = " ".join(dict.fromkeys(" ".join(p.split()) for p in partes if p.strip()))
            self._cache[url] = texto[: busqueda.MAX_LETRAS_TEXTO]
        return busqueda.Texto(url, medio, fecha, self._cache[url])


def textos_de(incidente: Documento, textos: Textos, otros: list[Documento]) -> list[busqueda.Texto]:
    """Las fuentes públicas del incidente (una por enlace) y, después, los otros artículos."""
    vistos: dict[str, busqueda.Texto] = {}
    for fuente in control_fichas._publicas(incidente):
        enlace = str(fuente.get("enlace") or "")
        if enlace and enlace not in vistos:
            vistos[enlace] = textos.de(enlace, str(fuente.get("medio", "")),
                                       str(fuente["fecha"]["valor"]),
                                       str(fuente.get("frase_origen") or ""))  # fmt: skip
    for articulo in otros:
        if articulo["url"] not in vistos:
            vistos[articulo["url"]] = textos.de(articulo["url"], str(articulo["medio"]),
                                                str(articulo["fecha"]))  # fmt: skip
    return [t for t in vistos.values() if t.texto][: busqueda.MAX_TEXTOS]


# --- La pasada ------------------------------------------------------------------------------


def _articulos_desde(principal: Almacen, desde: str) -> list[Documento]:
    filas = principal._conexion.execute(
        "SELECT url, medio, fecha, idioma, titular, lugares, pais FROM articulos "
        "WHERE fecha >= ? ORDER BY fecha",
        (desde,),
    ).fetchall()
    claves = ("url", "medio", "fecha", "idioma", "titular", "lugares", "pais")
    resultado = []
    for fila in filas:
        articulo = dict(zip(claves, fila, strict=True))
        try:
            articulo["lugares"] = json.loads(articulo["lugares"] or "[]")
        except ValueError:
            articulo["lugares"] = []
        resultado.append(articulo)
    return resultado


def pais_de_articulo(articulo: Documento) -> str:
    """El país del suceso que sugiere la noticia: el de su primer lugar del nomenclátor, o el del
    medio."""
    nom = nomenclator()
    for lugar in articulo.get("lugares") or []:
        sitio = nom.lugares.get(lugar)
        if sitio is not None:
            return str(sitio.pais)
    return str(articulo.get("pais") or "")


def fuera_de_fichas(principal: Almacen, fichas: list[Documento]) -> set[str]:
    """Las noticias que ya están en el flujo: las fuentes y los candidatos de las fichas
    publicadas, y los candidatos que aún esperan su primera extracción."""
    dentro = {str(f.get("enlace")) for d in fichas for f in d.get("fuentes", [])}
    de_fichas = {str((d.get("control") or {}).get("candidato") or "") for d in fichas}
    for candidato in principal.candidatos():
        if candidato["id"] in de_fichas or not principal.extracciones(candidato["id"]):
            dentro.update(candidato["articulos"])
    return dentro


class Busquedas:
    """Las búsquedas de una pasada, con el lector de la capa y su base."""

    def __init__(self, principal: Almacen, propia: Any, lector: Any, ahora: datetime,
                 textos: Textos) -> None:  # fmt: skip
        self.principal, self.propia, self.lector, self.ahora = principal, propia, lector, ahora
        self.textos = textos
        self.hecho: Documento = {
            b: {"preguntadas": 0, "candidatos": []} for b in busqueda.BUSQUEDAS
        }

    def _ya(self, clave: str, huella: str) -> bool:
        return bool(self.propia.busqueda(clave) == huella)

    def _preguntar(self, tipo: str, contenido: str) -> Documento | None:
        instrucciones, esquema = busqueda.INSTRUCCIONES[tipo]
        respuesta = self.lector.preguntar(instrucciones, contenido, tipo, esquema,
                                          busqueda.MAX_SALIDA)  # fmt: skip
        if respuesta is not None:
            self.hecho[tipo]["preguntadas"] += 1
        return respuesta  # type: ignore[no-any-return]

    def _marcar(self, tipo: str, ref: str, huella: str, datos: Documento) -> None:
        clave = f"{tipo}:{ref}:{huella}"
        self.propia.marcar(clave, tipo, ref, None, _iso(self.ahora), {"huella": huella, **datos})
        self.hecho[tipo]["candidatos"].append(ref)

    def incidente(self, tipo: str, incidente: Documento, otros: list[Documento]) -> None:
        """Una búsqueda (declaración, atribución o efectos) sobre un incidente."""
        datos = busqueda.datos_de(incidente)
        textos = textos_de(incidente, self.textos, otros)
        if not textos:
            return
        huella = busqueda.huella(tipo, datos, [(t.url, t.texto) for t in textos])
        clave = f"{tipo}:{incidente['id']}"
        if self._ya(clave, huella):
            return
        respuesta = self._preguntar(tipo, busqueda.contenido(datos, textos))
        if respuesta is None:
            return
        if tipo == busqueda.DECLARACION:
            hallado = busqueda.declaracion(respuesta, textos)
            hallados = [hallado] if hallado else []
        elif tipo == busqueda.ATRIBUCION:
            hallado = busqueda.atribucion_hallada(respuesta, textos)
            hallados = [hallado] if hallado else []
        else:
            hallados = busqueda.efectos(respuesta, textos, datos)
        self.propia.guardar_busqueda(clave, huella, _iso(self.ahora), len(hallados))
        if tipo == busqueda.EFECTOS and hallados:
            self._marcar(tipo, incidente["id"], huella, {"hallazgos": hallados})
        elif hallados:
            self._marcar(tipo, incidente["id"], huella, hallados[0])

    def rescatar(self, articulo: Documento, fichas: list[Documento]) -> None:
        """La búsqueda de un incidente que falta en una noticia fuera de las fichas."""
        clave = f"{busqueda.RESCATE}:{articulo['url']}"
        texto = self.textos.de(articulo["url"], str(articulo["medio"]), str(articulo["fecha"]))
        if not texto.texto:
            return
        pais = pais_de_articulo(articulo)
        cercanas = busqueda.cercanas(fichas, pais, str(articulo["fecha"]))
        huella = busqueda.huella(busqueda.RESCATE, texto.texto, [d["id"] for d in cercanas])
        if self._ya(clave, huella):
            return
        respuesta = self._preguntar(busqueda.RESCATE, busqueda.contenido_rescate(texto, cercanas))
        if respuesta is None:
            return
        hallado = busqueda.rescate(respuesta, texto, cercanas)
        self.propia.guardar_busqueda(clave, huella, _iso(self.ahora), int(hallado is not None))
        if hallado is not None:
            self._marcar(busqueda.RESCATE, articulo["url"], huella,
                         {**hallado, "lugares": articulo.get("lugares") or []})  # fmt: skip


def otros_articulos(principal: Almacen, incidente: Documento,
                    articulos: list[Documento]) -> list[Documento]:  # fmt: skip
    """Las noticias posteriores que nombran el lugar del incidente (la selección del barrido de
    rectificaciones), las primeras después del suceso."""
    return rectificaciones.nombran_el_lugar(incidente, articulos, 0)[: busqueda.MAX_TEXTOS]


def buscar(principal: Almacen, propia: Any, lector: Any, ahora: datetime, fichas: list[Documento],
           descargador: Descargador | None, pais: str | None = None,
           cupos: dict[str, int] | None = None) -> Documento:  # fmt: skip
    """Las cuatro búsquedas, cada una hasta su cupo. Con `pais`, el barrido de ese país: todos
    sus incidentes sin el filtro de antigüedad y todas sus noticias."""
    ajustes = conf()
    cupos = cupos or {b: int(ajustes["por_pasada"][b]) for b in busqueda.BUSQUEDAS}
    horas = 0.0 if pais else float(ajustes["horas_minimas"])
    trabajo = Busquedas(principal, propia, lector, ahora, Textos(principal, descargador))
    desde_articulos = "0000" if pais else (ahora - timedelta(days=400)).strftime("%Y-%m-%d")
    articulos = _articulos_desde(principal, desde_articulos)
    propias = [d for d in fichas if not pais or (d.get("lugar") or {}).get("pais") == pais]
    # Lo más reciente primero: una declaración que falta suele ser de los últimos días o semanas;
    # lo ya preguntado no se repite (su huella), así que la pasada siguiente sigue con lo de antes.
    propias.sort(key=lambda d: d["tiempo"]["inicio"]["valor"], reverse=True)
    for tipo in (busqueda.DECLARACION, busqueda.ATRIBUCION, busqueda.EFECTOS):
        for incidente in propias:
            if lector.parado or trabajo.hecho[tipo]["preguntadas"] >= cupos[tipo]:
                break
            if busqueda.toca(tipo, incidente, ahora, horas):
                otros = otros_articulos(principal, incidente, articulos) if (
                    tipo == busqueda.DECLARACION) else []  # fmt: skip
                trabajo.incidente(tipo, incidente, otros)
    dias = int(ajustes["dias_rescate"])
    corte = "0000" if pais else (ahora - timedelta(days=dias)).strftime("%Y-%m-%d")
    dentro = fuera_de_fichas(principal, fichas)
    sueltos = [a for a in reversed(articulos)
               if a["fecha"] >= corte and a["url"] not in dentro
               and (not pais or pais_de_articulo(a) == pais)]  # fmt: skip
    for articulo in sueltos:
        if (
            lector.parado
            or trabajo.hecho[busqueda.RESCATE]["preguntadas"] >= cupos[busqueda.RESCATE]
        ):
            break
        trabajo.rescatar(articulo, fichas)
    return trabajo.hecho


def toca_barrido(propia: Any, ahora: datetime) -> bool:
    ajustes = conf()["barrido_pais"]
    hecho = json.loads(propia.estado(ESTADO_BARRIDO) or "{}")
    return ahora.hour >= int(ajustes["hora_utc"]) and hecho.get("dia") != ahora.strftime("%Y-%m-%d")


def siguiente_pais(propia: Any, fichas: list[Documento]) -> str | None:
    """El país del barrido de hoy: rotando por los países con incidentes, de más a menos."""
    cuenta: dict[str, int] = {}
    for d in fichas:
        pais = str((d.get("lugar") or {}).get("pais") or "")
        if pais:
            cuenta[pais] = cuenta.get(pais, 0) + 1
    orden = sorted(cuenta, key=lambda p: (-cuenta[p], p))
    hecho = json.loads(propia.estado(ESTADO_BARRIDO) or "{}")
    vuelta = [p for p in hecho.get("vuelta", []) if p in cuenta]
    pendientes = [p for p in orden if p not in vuelta]
    return pendientes[0] if pendientes else (orden[0] if orden else None)


def barrido_pais(principal: Almacen, propia: Any, lector: Any, ahora: datetime,
                 fichas: list[Documento],
                 descargador: Descargador | None) -> Documento:  # fmt: skip
    """El barrido diario de un país; queda anotado en la base de la capa (país y fecha)."""
    pais = siguiente_pais(propia, fichas)
    if pais is None:
        return {}
    tope = int(conf()["barrido_pais"]["por_pasada"])
    hecho = buscar(principal, propia, lector, ahora, fichas, descargador, pais,
                   dict.fromkeys(busqueda.BUSQUEDAS, tope))  # fmt: skip
    anterior = json.loads(propia.estado(ESTADO_BARRIDO) or "{}")
    vuelta = [p for p in anterior.get("vuelta", []) if p != pais] + [pais]
    paises = {str((d.get("lugar") or {}).get("pais")) for d in fichas}
    if paises <= set(vuelta):
        vuelta = []
    historial = [*anterior.get("historial", []), {"pais": pais, "fecha": _iso(ahora)}][-60:]
    propia.fijar(ESTADO_BARRIDO, json.dumps(
        {"dia": ahora.strftime("%Y-%m-%d"), "pais": pais, "vuelta": vuelta,
         "historial": historial}, ensure_ascii=False))  # fmt: skip
    return {"pais": pais, **hecho}


# --- En la recogida horaria -----------------------------------------------------------------


def _al_cursor_dirigidos(almacen: Almacen, url: str, candidato: str, ahora: datetime,
                         datos: Documento) -> None:  # fmt: skip
    cursor: dict[str, Any] = dict(almacen.cursor(articulos_dirigidos.FUENTE_ID) or {})
    entrada = dict(cursor.get(url) or {})
    entrada.update(
        entrado=entrada.get("entrado") or ahora.strftime("%Y-%m-%dT%H:%MZ"),
        candidatos=sorted({*entrada.get("candidatos", []), candidato}),
        origen="segunda_lectura", frase=str(datos.get("frase") or ""),
    )  # fmt: skip
    cursor[url] = entrada
    almacen.guardar_cursor(articulos_dirigidos.FUENTE_ID, cursor)


def _repetir_con_experto(almacen: Almacen, candidato: str, motivo: str, ahora: datetime,
                         cupo: bool = False) -> None:  # fmt: skip
    """La extracción se repite con el experto en la recogida (`revision`). Con `cupo`, se paga con
    el cupo propio de las búsquedas de lo que falta (coste.Modo.SEGUNDA_BUSQUEDA)."""
    extraccion.anotar_espera(
        almacen, candidato, [motivo], ahora - extraccion.ESPERA_FALLO_EXPERTO, False, True,
        cupo=coste.Modo.SEGUNDA_BUSQUEDA.value if cupo else None,
    )  # fmt: skip


def _candidato_de(almacen: Almacen, id_: str) -> Documento | None:
    incidente = almacen.incidente(id_)
    if incidente is None:
        return None
    candidato_id = (incidente.get("control") or {}).get("candidato")
    return next((c for c in almacen.candidatos() if c["id"] == candidato_id), None)


def _a_la_extraccion(candidato_id: str, cupo: bool) -> Documento:
    hecho: Documento = {"resultado": "a_la_extraccion", "candidato": candidato_id}
    return {**hecho, "cupo": True} if cupo else hecho


def entregar(almacen: Almacen, ahora: datetime, candidato: Documento,
             cupo: bool = False) -> Documento:  # fmt: skip
    """Un candidato de declaración, atribución o rescate, al circuito de siempre. Devuelve lo
    hecho, que se guarda como la decisión del candidato (no se repite). Con `cupo` (declaraciones
    e incidentes que faltan), el experto lo extrae con el cupo propio de la segunda lectura."""
    datos, tipo = candidato["datos"], candidato["tipo"]
    url = str(datos.get("url") or "")
    if tipo in {busqueda.DECLARACION, busqueda.ATRIBUCION}:
        incidente = almacen.incidente(candidato["incidente"])
        destino = _candidato_de(almacen, candidato["incidente"])
        if incidente is None or destino is None:
            return {"resultado": "sin_ficha"}
        if url and url not in destino["articulos"] and almacen.articulos_de([url]):
            destino = {**destino, "articulos": [*destino["articulos"], url]}
            almacen.corregir_candidatos([destino], f"{MOTIVO}: {tipo}")
        if url:
            _al_cursor_dirigidos(almacen, url, destino["id"], ahora, datos)
        quien = datos.get("autoridad") or "una autoridad"
        if tipo == busqueda.ATRIBUCION:
            detalle = f"atribución de «{quien}» a {datos.get('responsable')}"
        else:
            detalle = f"habla «{quien}» ({datos.get('afirma')})"
        _repetir_con_experto(
            almacen, destino["id"],
            f"declaracion: {detalle} y la ficha no trae su declaración (segunda lectura)", ahora,
            cupo,
        )  # fmt: skip
        return _a_la_extraccion(destino["id"], cupo)
    # Un incidente que falta.
    destino = next((c for c in almacen.candidatos() if url in c["articulos"]), None)
    if destino is None:
        lugares = [str(lugar) for lugar in datos.get("lugares") or []
                   if lugar in nomenclator().lugares]  # fmt: skip
        documento = next(iter(almacen.articulos_de([url])), None)
        if documento is None or not lugares:
            return {"resultado": "sin_lugar"}
        from recogida.calidad import situar_en_candidatos

        tocados = situar_en_candidatos(almacen, [(documento, lugares)], MOTIVO)
        if not tocados:
            return {"resultado": "sin_lugar"}
        _al_cursor_dirigidos(almacen, url, tocados[0], ahora, datos)
        if cupo:
            # Con el cupo, la primera extracción del candidato ya la hace el experto.
            _repetir_con_experto(almacen, tocados[0], _motivo_rescate(datos), ahora, cupo)
        return _a_la_extraccion(tocados[0], cupo)
    _al_cursor_dirigidos(almacen, url, destino["id"], ahora, datos)
    if almacen.extracciones(destino["id"]) or cupo:
        _repetir_con_experto(almacen, destino["id"], _motivo_rescate(datos), ahora, cupo)
    return _a_la_extraccion(destino["id"], cupo)


def _motivo_rescate(datos: Documento) -> str:
    return f"segunda lectura: posible incidente que falta: «{str(datos.get('frase'))[:120]}»"
