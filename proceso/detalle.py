"""Datos de las fuentes oficiales de detalle en los incidentes.

Las fuentes oficiales de detalle (recogida/detalle.py) dejan en la base registros propios:
encuentros con aeronave (UK Airprox Board) y documentos oficiales leídos (respuestas de
gobiernos en el parlamento, informes finales de investigación, cierres de investigaciones
policiales y sentencias), cada uno con los sucesos que cita y lo que dice de cada uno. Aquí:

- **Cruce.** Un encuentro o un suceso citado coincide con un incidente si encajan por la regla
  de fusión (proceso/incidentes.encajan: mismo sitio y misma ventana). Si encaja con uno solo,
  se enlaza; con varios, no.
- **Aportación.** Lo que el registro oficial sabe del incidente entra con una fuente propia
  (fiabilidad A, autoridad, con su método), sus afirmaciones y sus valores, y el incidente
  pasa a confirmado: la autoridad dice que ocurrió. presencia_dron solo cambia si el documento
  afirma expresamente que había drones.
- **Visibilidad.** Los campos públicos del incidente no cambian, salvo el estado, la presencia
  confirmada y las fuentes (enlace y frase breve). Los datos de detalle van a campos internos:
  la hora, el lugar, el número de drones y las medidas oficiales, al bloque `detalle_oficial`;
  la altura y la velocidad del dron, la detección y el resultado de las contramedidas, a sus
  campos internos del esquema.
- **Idempotencia.** Los incidentes se rehacen desde las fichas de noticias (reproceso, revisión):
  la aportación se vuelve a aplicar entera al rehacerlos (`reaplicar`) y en cada recogida
  horaria (`revisar`). Aplicada, no cambia nada.
- **Alta.** Un suceso citado con fecha y lugar que no coincide con ninguno entra como
  incidente nuevo por el flujo normal: la misma validación de la ficha, la misma ubicación, la
  misma construcción y las mismas reglas, con la fuente oficial en lugar de las noticias. Los
  encuentros con aeronave no dan de alta incidentes.
"""

import contextlib
import copy
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from almacen.base import Almacen, DocumentoInvalido
from esquema import Documento
from proceso import incidentes
from proceso.credibilidad import Credibilidad
from proceso.estados import Estado, TransicionNoPermitida, transitar
from proceso.fronteras import dentro_del_pais
from proceso.noticias import nomenclator
from proceso.ubicacion import Pistas, Ubicacion, ubicar
from proceso.validacion_ficha import Validada

MAX_PALABRAS = 25
VERSION_ALTA = "oficial/1"
PREFIJO_FUENTE = "detalle-"
# Posición de un encuentro de la UKAB: grados y minutos de arco, que en latitud son 1,85 km.
# El radio es el de esa precisión, redondeado por arriba.
RADIO_ENCUENTRO_KM = 2.0
# La presencia del dron solo la confirma una frase con confianza alta: «Drohnen wurden
# detektiert», no «möglicherweise eine Drohne».
CONFIANZA_PRESENCIA = 0.9
# Un punto oficial vale como punto del incidente con un radio de 50 km o menos (el máximo del
# esquema); por debajo de 0,1 km, el mínimo del esquema.
RADIO_MAX_PUNTO_KM = 50.0
RADIO_MIN_KM = 0.1
VOCABULARIO_LUGARES = "lugar"

# Campo del suceso que da el extractor → ruta del valor en el incidente. Los públicos que el
# documento oficial precisa (hora, lugar, número, medidas) van al bloque interno.
RUTAS_SUCESO = {
    "inicio": "detalle_oficial.inicio",
    "drones": "detalle_oficial.numero",
    "medidas": "detalle_oficial.medidas",
    "altura_m": "drones.altura_m",
    "velocidad_ms": "drones.velocidad_ms",
    "deteccion": "respuesta.deteccion",
    "resultado_contramedidas": "respuesta.resultado_contramedidas",
}
LISTAS = frozenset({"detalle_oficial.medidas", "respuesta.deteccion"})


def _instante(momento: datetime, precision: str = "minuto") -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


def _dia(fecha: str) -> Documento:
    return {"valor": f"{fecha}T00:00Z", "precision": "dia"}


def _frase(texto: str) -> str:
    return " ".join(texto.split()[:MAX_PALABRAS])


def id_fuente(enlace: str) -> str:
    return PREFIJO_FUENTE + hashlib.sha256(enlace.encode("utf-8")).hexdigest()[:16]


@dataclass
class Aportacion:
    """Lo que un registro oficial aporta a un incidente."""

    fuente: Documento
    valores: dict[str, Any] = field(default_factory=dict)
    confianzas: dict[str, float] = field(default_factory=dict)
    presencia: str | None = None
    encuentro: str | None = None

    def afirmaciones(self) -> list[Documento]:
        return [
            {"campo": ruta, "valor": valor, "fuente_id": self.fuente["id"],
             "confianza_extraccion": self.confianzas.get(ruta, 1.0)}
            for ruta, valor in sorted(self.valores.items())
        ]  # fmt: skip


# --- Encuentros ---------------------------------------------------------------------


def fuente_encuentro(encuentro: Documento, rutas: list[str]) -> Documento:
    fecha = encuentro.get("reunion") or encuentro["instante"]["valor"][:10]
    frase = encuentro["objeto"].get("descripcion") or encuentro["objeto"].get("opinion_junta")
    return {
        "id": f"ukab-{encuentro['numero']}",
        "enlace": encuentro["enlace"],
        "medio": encuentro["fuente"]["medio"],
        "fecha": _dia(fecha),
        "idioma": "en",
        "fiabilidad": encuentro["fuente"]["fiabilidad"],
        "credibilidad": encuentro["fuente"]["credibilidad"],
        "frase_origen": _frase(frase or f"Airprox {encuentro['numero']}"),
        "replicas": 0,
        "campos_respaldados": sorted({"estado", *rutas}),
        "es_autoridad": True,
        "interna_fuera_de_ucrania": False,
        "publica": True,
        "metodo": "parser",
        "documento_oficial": encuentro["id"],
    }


def aportacion_encuentro(encuentro: Documento) -> Aportacion:
    """Hora y posición del encuentro, altura del dron por la regla de la separación y la
    detección por el piloto, que es quien lo notifica."""
    valores: dict[str, Any] = {"detalle_oficial.inicio": encuentro["instante"]}
    punto = encuentro.get("posicion", {}).get("punto")
    if punto is not None:
        valores["detalle_oficial.punto"] = punto
        valores["detalle_oficial.radio_km"] = RADIO_ENCUENTRO_KM
    if "altura_m" in encuentro["objeto"]:
        valores["drones.altura_m"] = encuentro["objeto"]["altura_m"]
    valores["respuesta.deteccion"] = ["piloto"]
    fuente = fuente_encuentro(encuentro, sorted(valores))
    return Aportacion(fuente, valores, encuentro=encuentro["id"])


def pseudo_encuentro(encuentro: Documento) -> Documento | None:
    """El encuentro con la forma mínima que pide la regla de fusión."""
    punto = encuentro.get("posicion", {}).get("punto")
    if punto is None:
        return None
    return {
        "id": encuentro["id"],
        "lugar": {"punto": punto, "radio_km": RADIO_ENCUENTRO_KM, "pais": encuentro["pais"]},
        "tiempo": {"inicio": encuentro["instante"]},
        "fuentes": [],
    }


def coincidentes(almacen_incidentes: list[Documento], pseudo: Documento) -> list[str]:
    return sorted(
        i["id"] for i in almacen_incidentes
        if incidentes.activo(i) and i["lugar"]["pais"] == pseudo["lugar"]["pais"]
        and incidentes.encajan(i, pseudo)
    )  # fmt: skip


def _destino(almacen: Almacen, id_: str) -> str:
    """El incidente vivo: si se fundió en otro, el otro."""
    vistos = set()
    while id_ not in vistos:
        vistos.add(id_)
        documento = almacen.incidente(id_)
        if documento is None or "fusionado_en" not in documento:
            return id_
        id_ = documento["fusionado_en"]
    return id_


def cruzar_encuentros(almacen: Almacen, ahora: datetime) -> int:
    """Enlaza cada encuentro sin incidente con el único que encaje. Devuelve cuántos enlaza."""
    activos = [i for i in almacen.incidentes() if incidentes.activo(i)]
    enlazados = 0
    for encuentro in almacen.encuentros():
        if "incidente" in encuentro:
            destino = _destino(almacen, encuentro["incidente"])
            if destino != encuentro["incidente"]:
                almacen.guardar_encuentro({**encuentro, "incidente": destino}, ahora)
            continue
        pseudo = pseudo_encuentro(encuentro)
        if pseudo is None:
            continue
        hallados = coincidentes(activos, pseudo)
        if len(hallados) == 1:
            almacen.guardar_encuentro({**encuentro, "incidente": hallados[0]}, ahora)
            enlazados += 1
    return enlazados


# --- Documentos oficiales -------------------------------------------------------------


def fuente_documento(documento: Documento, rutas: list[str], frase: str) -> Documento:
    return {
        "id": id_fuente(documento["enlace"]),
        "enlace": documento["enlace"],
        "medio": documento["autoridad"],
        "fecha": _dia(documento["fecha"]),
        "idioma": documento["idioma"],
        "fiabilidad": documento.get("fiabilidad", "A"),
        "credibilidad": documento.get("credibilidad", int(Credibilidad.CONFIRMADO)),
        "frase_origen": _frase(frase or documento["titulo"]),
        "replicas": 0,
        "campos_respaldados": sorted({"estado", *rutas}),
        "es_autoridad": True,
        "interna_fuera_de_ucrania": False,
        "publica": True,
        "metodo": documento["control"].get("metodo", "extractor"),
        "documento_oficial": documento["id"],
    }


def _valor(dato: Documento) -> Any:
    return dato["valor"]


def aportacion_suceso(documento: Documento, suceso: Documento) -> Aportacion:
    """Lo que el documento dice del suceso, en las rutas internas del incidente."""
    datos = suceso["datos"]
    valores: dict[str, Any] = {}
    confianzas: dict[str, float] = {}
    for campo, ruta in RUTAS_SUCESO.items():
        if campo not in datos:
            continue
        valor = _valor(datos[campo])
        if campo == "inicio":
            precision = _valor(datos["inicio_precision"]) if "inicio_precision" in datos else None
            precision = precision or ("minuto" if "T" in valor else "dia")
            valor = {"valor": valor + ("Z" if "T" in valor else "T00:00Z"),
                     "precision": precision if "T" in valor else "dia"}  # fmt: skip
        valores[ruta] = valor
        confianzas[ruta] = float(datos[campo]["confianza"])
    punto = suceso.get("punto")
    if punto is not None:
        valores["detalle_oficial.punto"] = {"lat": punto["lat"], "lon": punto["lon"]}
        valores["detalle_oficial.radio_km"] = punto["radio_km"]
    presencia = None
    dato = datos.get("presencia_dron")
    if dato and float(dato["confianza"]) >= CONFIANZA_PRESENCIA:
        # Confirmada, no confirmada («no se ha podido demostrar ni descartar») o descartada:
        # lo que dice expresamente la autoridad en su documento.
        presencia = str(dato["valor"])
        valores["presencia_dron"] = presencia
        confianzas["presencia_dron"] = float(dato["confianza"])
    frase = next((d["frase"] for d in datos.values() if d.get("frase")), "")
    fuente = fuente_documento(documento, sorted(valores), frase)
    return Aportacion(fuente, valores, confianzas, presencia)


def aportaciones(almacen: Almacen) -> dict[str, list[Aportacion]]:
    """Por incidente, lo que le aportan los registros oficiales que lo enlazan."""
    resultado: dict[str, list[Aportacion]] = defaultdict(list)
    for encuentro in almacen.encuentros():
        if "incidente" in encuentro:
            resultado[_destino(almacen, encuentro["incidente"])].append(
                aportacion_encuentro(encuentro)
            )
    for documento in almacen.documentos_oficiales("extraido"):
        for suceso in documento.get("sucesos", []):
            if suceso.get("incidente") and suceso["cruce"] in {"existente", "nuevo"}:
                resultado[_destino(almacen, suceso["incidente"])].append(
                    aportacion_suceso(documento, suceso)
                )
    return dict(resultado)


# --- Aplicación ----------------------------------------------------------------------


def _poner(documento: Documento, ruta: str, valor: Any) -> None:
    *padres, ultima = ruta.split(".")
    nodo = documento
    for parte in padres:
        nodo = nodo.setdefault(parte, {})
    nodo[ultima] = copy.deepcopy(valor)


def _combinar(lista: list[Aportacion]) -> dict[str, Any]:
    """Un valor por ruta: las listas se unen; en lo demás gana la mayor confianza y, a la par,
    la fuente de identificador menor (orden estable)."""
    valores: dict[str, Any] = {}
    elegidos: dict[str, tuple[float, str]] = {}
    for aportacion in sorted(lista, key=lambda a: a.fuente["id"]):
        for ruta, valor in aportacion.valores.items():
            if ruta in LISTAS:
                valores[ruta] = sorted(set(valores.get(ruta, [])) | set(valor))
                continue
            clave = (-aportacion.confianzas.get(ruta, 1.0), aportacion.fuente["id"])
            if ruta not in elegidos or clave < elegidos[ruta]:
                elegidos[ruta] = clave
                valores[ruta] = valor
    return valores


def aplicar(incidente: Documento, lista: list[Aportacion]) -> Documento:
    """El incidente con lo que le aportan los registros oficiales. Idempotente."""
    if not lista:
        return incidente
    resultado = copy.deepcopy(incidente)
    fuentes = {f["id"]: f for f in resultado["fuentes"]}
    for aportacion in sorted(lista, key=lambda a: a.fuente["id"]):
        nueva = copy.deepcopy(aportacion.fuente)
        if (previa := fuentes.get(nueva["id"])) is not None:
            # La misma fuente ya estaba (un incidente que dio de alta este documento, otro
            # suceso del mismo documento): respalda lo de antes y lo nuevo.
            nueva["campos_respaldados"] = sorted(
                set(previa.get("campos_respaldados", [])) | set(nueva["campos_respaldados"])
            )
        fuentes[nueva["id"]] = nueva
    resultado["fuentes"] = sorted(fuentes.values(), key=lambda f: (f["fecha"]["valor"], f["id"]))
    afirmaciones = list(resultado.get("afirmaciones", []))
    for aportacion in lista:
        for afirmacion in aportacion.afirmaciones():
            if afirmacion not in afirmaciones:
                afirmaciones.append(afirmacion)
    resultado["afirmaciones"] = afirmaciones
    combinados = _combinar(lista)
    for ruta, valor in sorted(combinados.items()):
        if ruta != "presencia_dron":
            _poner(resultado, ruta, valor)
    resultado["lugar"] = punto_oficial(resultado["lugar"], combinados)
    if "detalle_oficial.inicio" in combinados:
        oficial = combinados["detalle_oficial.inicio"]
        fuente_inicio = next(
            a.fuente for a in sorted(lista, key=lambda a: a.fuente["id"])
            if a.valores.get("detalle_oficial.inicio") == oficial
        )  # fmt: skip
        resultado["tiempo"] = inicio_oficial(resultado["tiempo"], oficial, fuente_inicio)
        for fuente in resultado["fuentes"]:
            if fuente["id"] == fuente_inicio["id"]:
                fuente["campos_respaldados"] = sorted(
                    {*fuente.get("campos_respaldados", []), "tiempo.inicio"}
                )
    encuentros = sorted(
        {a.encuentro for a in lista if a.encuentro} | set(resultado.get("encuentros", []))
    )
    if encuentros:
        resultado["encuentros"] = encuentros
    con_presencia = [a for a in lista if a.presencia]
    if con_presencia:
        # La del documento más reciente: una investigación cerrada corrige a una respuesta
        # anterior. A la par, la más prudente.
        prudencia = {"descartada": 0, "no_confirmada": 1, "confirmada": 2}
        ultima = max(
            con_presencia,
            key=lambda a: (a.fuente["fecha"]["valor"], -prudencia[str(a.presencia)]),
        )
        resultado["presencia_dron"] = ultima.presencia
    confirmante = min(lista, key=lambda a: (a.fuente["credibilidad"], a.fuente["id"])).fuente
    if resultado["estado"]["actual"] not in incidentes.CONFIRMADOS:
        # Un desmentido de una autoridad más fiable no se revierte con esta fuente.
        with contextlib.suppress(TransicionNoPermitida):
            resultado["estado"] = transitar(
                resultado["estado"], Estado.CONFIRMADO, confirmante["fecha"], confirmante["id"],
                {f["id"]: f for f in resultado["fuentes"]},
            )  # fmt: skip
    return incidentes.aplicar_reglas(resultado)


def punto_oficial(lugar: Documento, combinados: dict[str, Any]) -> Documento:
    """Un incidente sin punto (solo se sabía la región o el país) toma el punto y el radio que
    da la autoridad en su documento, si caen en su país. Uno que ya tenía punto lo conserva:
    el oficial queda en detalle_oficial."""
    punto, radio = (
        combinados.get("detalle_oficial.punto"),
        combinados.get("detalle_oficial.radio_km"),
    )
    if "punto" in lugar or punto is None or radio is None or float(radio) > RADIO_MAX_PUNTO_KM:
        return lugar
    if not dentro_del_pais(lugar["pais"], float(punto["lat"]), float(punto["lon"])):
        return lugar
    resultado = copy.deepcopy(lugar)
    resultado["punto"] = {
        "lat": round(float(punto["lat"]), 5),
        "lon": round(float(punto["lon"]), 5),
    }
    resultado["radio_km"] = max(float(radio), RADIO_MIN_KM)
    resultado["geocodificacion"] = "oficial"
    if resultado.get("nivel") in {"region", "pais"}:
        resultado["nivel"] = "localidad"
    return resultado


def inicio_oficial(tiempo: Documento, oficial: Documento, fuente: Documento) -> Documento:
    """El inicio del incidente con la fecha de la fuente oficial, que manda sobre la de la
    prensa: su día está escrito en el documento (o es el instante de un encuentro). Si la
    autoridad solo da el día y la prensa da la hora de ese mismo día, se queda la hora de la
    prensa con el día confirmado por la autoridad."""
    resultado = copy.deepcopy(tiempo)
    actual = tiempo["inicio"]
    mismo_dia = actual["valor"][:10] == oficial["valor"][:10]
    if oficial["precision"] == "dia" and mismo_dia and actual["precision"] in {"minuto", "hora"}:
        inicio = actual
        motivo = f"el día lo da {fuente['medio']} ({fuente['enlace']}); la hora, la prensa"
    else:
        inicio = copy.deepcopy(oficial)
        motivo = f"fecha de {fuente['medio']} ({fuente['enlace']})"
    resultado["inicio"] = inicio
    origen = {"tipo": "oficial", "motivo": motivo[:300], "fuente_id": fuente["id"]}
    previo = tiempo.get("origen_inicio", {})
    ya_aplicado = previo.get("tipo") == "oficial" and previo.get("fuente_id") == fuente["id"]
    if inicio != actual or (ya_aplicado and previo.get("corregido")):
        origen["corregido"] = True
    resultado["origen_inicio"] = origen
    if "fin" in resultado and resultado["fin"]["valor"] < inicio["valor"]:
        # El fin de la prensa era de otro día: no casa con el inicio oficial.
        resultado.pop("fin")
        resultado.pop("duracion_min", None)
    elif "fin" in resultado:
        fin = datetime.strptime(resultado["fin"]["valor"], "%Y-%m-%dT%H:%MZ")
        comienzo = datetime.strptime(inicio["valor"], "%Y-%m-%dT%H:%MZ")
        resultado["duracion_min"] = int((fin - comienzo).total_seconds()) // 60
    return resultado


def reaplicar(almacen: Almacen, incidente: Documento) -> Documento:
    """Al rehacer un incidente desde su ficha: vuelve a llevar lo oficial que lo enlaza. Lo
    que llega por un incidente fundido en este lo aplica la revisión horaria."""
    id_ = incidente["id"]
    lista = [aportacion_encuentro(e) for e in almacen.encuentros_de(id_)]
    for documento in almacen.documentos_oficiales_de(id_):
        if documento["estado"] != "extraido":
            continue
        lista += [
            aportacion_suceso(documento, s) for s in documento.get("sucesos", [])
            if s.get("incidente") == id_ and s["cruce"] in {"existente", "nuevo"}
        ]  # fmt: skip
    return aplicar(incidente, lista)


@dataclass
class Revision:
    enlazados: int = 0
    actualizados: list[str] = field(default_factory=list)
    sin_guardar: list[str] = field(default_factory=list)

    def texto(self) -> str:
        return (
            f"encuentros enlazados={self.enlazados} incidentes con datos oficiales "
            f"actualizados={len(self.actualizados)} sin guardar={len(self.sin_guardar)}"
        )


def revisar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> Revision:
    """Cruza los encuentros sin incidente y aplica las aportaciones a sus incidentes."""
    revision = Revision(enlazados=cruzar_encuentros(almacen, ahora))
    for id_, lista in sorted(aportaciones(almacen).items()):
        anterior = almacen.incidente(id_)
        if anterior is None or not incidentes.activo(anterior):
            continue
        nuevo = aplicar(anterior, lista)
        if nuevo == anterior:
            continue
        nuevo["control"]["ultima_actualizacion"] = _instante(ahora)
        try:
            almacen.guardar_incidente(nuevo, ahora, modelos)
        except DocumentoInvalido:
            revision.sin_guardar.append(id_)
            continue
        revision.actualizados.append(id_)
    return revision


# --- Sucesos citados: cruce y alta -------------------------------------------------------


def validada(suceso: Documento) -> Validada:
    """Los datos del suceso como una ficha validada de noticias, fuente 1: el documento."""
    campos = {
        nombre: {"valor": dato["valor"], "fuente": 1, "frase": dato["frase"],
                 "confianza": dato["confianza"]}
        for nombre, dato in suceso["datos"].items()
    }  # fmt: skip
    campos.setdefault("es_incidente", {"valor": True, "fuente": 1, "frase": "", "confianza": 1.0})
    return Validada(
        campos=campos,
        titulo_es=str(suceso.get("titulo_es", "")),
        titulo_en=str(suceso.get("titulo_en", "")),
    )


def ubicar_suceso(almacen: Almacen, ficha: Validada, genericos: tuple[str, ...]) -> Ubicacion:
    pistas = Pistas(
        lugar_candidato="",
        objetivo_candidato=None,
        nombres_candidato=(),
        vocabulario=almacen.vocabulario(VOCABULARIO_LUGARES),
        genericos=genericos,
    )
    return ubicar(ficha, pistas, nomenclator())


def pseudo_suceso(ubicacion: Ubicacion, ficha: Validada) -> Documento | None:
    inicio = ficha.valor("inicio")
    if not inicio:
        return None
    precision = ficha.valor("inicio_precision") if "T" in inicio else "dia"
    lugar: Documento = {"pais": ubicacion.pais}
    if ubicacion.sitio is not None:
        lugar["punto"] = {
            "lat": round(ubicacion.sitio.lat, 5),
            "lon": round(ubicacion.sitio.lon, 5),
        }
        lugar["radio_km"] = ubicacion.sitio.radio_km
    if ubicacion.nombre:
        lugar["suceso"] = ubicacion.nombre
    documento: Documento = {
        "id": "suceso",
        "lugar": lugar,
        "tiempo": {"inicio": {"valor": inicio + ("Z" if "T" in inicio else "T00:00Z"),
                              "precision": precision or "dia"}},
        "fuentes": [],
    }  # fmt: skip
    if ubicacion.sitio is not None:
        documento["objetivo"] = {"nombre": ubicacion.sitio.nombre}
    return documento


def alta(
    almacen: Almacen,
    documento: Documento,
    indice: int,
    ficha: Validada,
    ubicacion: Ubicacion,
    ahora: datetime,
    modelos: frozenset[str],
) -> Documento:
    """El incidente nuevo de un suceso citado, construido como uno de noticias, con la fuente
    oficial en lugar de los artículos."""
    enlace = documento["enlace"]
    candidato = {
        "id": f"oficial:{documento['id']}:{indice}",
        "inicio": f"{documento['fecha']}T00:00:00+00:00",
    }
    articulo = {
        "url": enlace, "medio": documento["autoridad"], "fecha": candidato["inicio"],
        "idioma": documento["idioma"], "titular": documento["titulo"], "replicas": 0,
    }  # fmt: skip
    inicio = str(ficha.valor("inicio"))
    id_ = almacen.siguiente_id_incidente(int(inicio[:4]))
    nuevo = incidentes.construir(
        id_, ubicacion, candidato, [articulo], [enlace], ficha, ahora, VERSION_ALTA, modelos
    )
    frase = next((c["frase"] for c in ficha.campos.values() if c.get("frase")), documento["titulo"])
    rutas = sorted({FICHA_A_RUTA_ALTA.get(a["campo"], a["campo"]) for a in nuevo["afirmaciones"]})
    fuente = fuente_documento(documento, rutas, frase)
    anterior_id = nuevo["fuentes"][0]["id"]
    nuevo["fuentes"] = [fuente]
    nuevo["afirmaciones"] = [{**a, "fuente_id": fuente["id"]} for a in nuevo["afirmaciones"]]
    nuevo["estado"]["historial"] = [
        {**p, "fuente_id": fuente["id"] if p["fuente_id"] == anterior_id else p["fuente_id"],
         "fecha": fuente["fecha"]}
        for p in nuevo["estado"]["historial"]
    ]  # fmt: skip
    nuevo["control"]["huella_fuentes"] = incidentes.huella([enlace])
    nuevo["estado"] = transitar(
        nuevo["estado"], Estado.CONFIRMADO, fuente["fecha"], fuente["id"], {fuente["id"]: fuente}
    )
    # El día está escrito en el documento oficial (validacion_oficial.dia_en_frase).
    precision = ficha.valor("inicio_precision") if "T" in inicio else "dia"
    nuevo["tiempo"] = {
        "inicio": {"valor": inicio + ("Z" if "T" in inicio else "T00:00Z"),
                   "precision": precision or "dia"},
        "origen_inicio": {"tipo": "oficial", "fuente_id": fuente["id"],
                          "motivo": f"día escrito en el documento de {documento['autoridad']}"},
    }  # fmt: skip
    return incidentes.aplicar_reglas(nuevo)


# Campo de la ficha → ruta, para los campos que respalda la fuente de un incidente nuevo.
FICHA_A_RUTA_ALTA = {
    "inicio": "tiempo.inicio", "inicio_precision": "tiempo.inicio", "pais": "lugar.pais",
    "lugar_suceso": "lugar.suceso", "localidad": "lugar.localidad",
    "objetivo_categoria": "objetivo.categoria", "objetivo_nombre": "objetivo.nombre",
    "drones": "drones.numero", "presencia_dron": "presencia_dron",
    "cierre": "consecuencias.cierre.valor", "cierre_minutos": "consecuencias.cierre.minutos",
    "vuelos_desviados": "consecuencias.vuelos_desviados",
    "vuelos_cancelados": "consecuencias.vuelos_cancelados",
    "vuelos_retrasados": "consecuencias.vuelos_retrasados", "medidas": "respuesta.medidas",
    "dron_estatal": "pruebas.dron_estatal", "entrada_exterior": "pruebas.entrada_exterior",
    "evidencia": "pruebas.evidencia", "tipo": "tipo", "es_incidente": "estado",
}  # fmt: skip
