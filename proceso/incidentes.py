"""Incidentes europeos a partir de candidatos y fichas validadas; fusión y episodios.

Reglas del diseño:
- Qué es el mismo suceso lo dice proceso/suceso.py (docs/definicion_suceso.md) y nada de aquí
  lo decide por su cuenta: este módulo construye la ficha, ejecuta las uniones que la
  definición da por seguras (`fusionar`), deshace las que da por sucesos distintos
  (`revisar_fusiones`) y guarda los episodios que calcula (`agrupar_episodios`).
- Una fusión dudosa (el incidente encaja con dos) no se hace. Toda fusión es
  reversible: el absorbido queda en la base con `fusionado_en` y la tabla de
  fusiones anota qué fuentes aportó; el historial guarda cada cambio.
- Estado: las noticias notifican; confirmar corresponde a una autoridad.
- Tipo: si hay interrupción de aeropuerto, manda; es incursión cuando un dron militar
  o estatal entra desde fuera y lo demuestra una autoridad (el incidente está
  confirmado) o una prueba física (explosión, restos, caída, derribo, dron recuperado
  o rastreo por radar); si no, sobrevuelo.
- presencia_dron: la que da la ficha, independiente del estado, salvo cuando el
  incidente confirmado consiste en el propio dron (explotó, dejó restos, cayó, fue
  derribado o se recuperó): entonces la confirmación del incidente confirma el dron.
"""

import copy
import hashlib
import logging
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from almacen.base import Almacen
from esquema import Documento
from proceso import buques, cita_titular, fechas, suceso
from proceso.credibilidad import Declaracion, Fiabilidad, Postura, credibilidad
from proceso.estados import Estado, nuevo_estado
from proceso.fronteras import nombres_del_pais
from proceso.noticias import normalizar
from proceso.ubicacion import Ubicacion
from proceso.validacion_ficha import Validada, leer_fecha

registro = logging.getLogger(__name__)

MAX_PALABRAS_FRASE = 25
DECIMALES = 5
# Un suceso con drones no dura más de dos días: un fin más lejano es de otro.
MAX_DURACION = timedelta(days=2)
MAX_MOTIVO = 300
FIABILIDAD_NOTICIAS = "C"
# Pruebas físicas de que el incidente consiste en el propio dron.
PRUEBAS_FISICAS = frozenset({"explosion", "restos", "caida", "derribo", "recuperado"})
RASTREO = "rastreo"
# Un dron que explota lleva carga explosiva: es militar. También lo es uno de estos modelos.
MODELOS_MILITARES = ("shahed", "geran", "gerbera")
# Estados a los que solo lleva una autoridad.
CONFIRMADOS = frozenset({Estado.CONFIRMADO, Estado.ATRIBUIDO})
# Las reglas de la definición por las que dos fichas se unen sin leer sus fuentes.
REGLAS_DE_FUSION = frozenset({suceso.REGLA_SITIO_Y_JORNADA, suceso.REGLA_RESUMEN})
# Las reglas por las que una unión que hizo la regla de fusión se deshace sola.
REGLAS_QUE_DESHACEN = frozenset({suceso.REGLA_REVISION, suceso.REGLA_PAISES, suceso.REGLA_CIERRES})


def _instante(momento: datetime, precision: str) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


_leer_instante = suceso.leer_instante


def _frase(texto: str) -> str:
    return " ".join(texto.split()[:MAX_PALABRAS_FRASE])


def id_fuente(url: str) -> str:
    return "gdelt-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def huella(urls: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(urls)).encode("utf-8")).hexdigest()


def credibilidad_noticias(n: int) -> int:
    """Varias noticias de fiabilidad C sin contradicción: 3 por la regla."""
    declaraciones = [
        Declaracion(f"nota-{i}", Fiabilidad(FIABILIDAD_NOTICIAS), False, Postura.RESPALDA)
        for i in range(n)
    ]
    return int(credibilidad(declaraciones))


def nombres_del_suceso(ficha: Validada) -> list[str]:
    """El país y el lugar del suceso según la ficha: lo que la cita tiene que nombrar."""
    del_suceso = ficha.valor("lugar_suceso")
    lugar = {
        "suceso": del_suceso.get("nombre") if isinstance(del_suceso, dict) else None,
        "localidad": ficha.valor("localidad"),
        "region": del_suceso.get("region") if isinstance(del_suceso, dict) else None,
    }
    return [
        *nombres_del_pais(ficha.pais or ""),
        *cita_titular.nombres_del_lugar({"lugar": lugar}),
    ]


def cita_con_lugar(frases: list[str], titular: str, nombres: list[str], medio: str = "") -> str:
    """La cita de una fuente, comprobada: la primera de sus frases que nombra el lugar o el país
    del suceso; si ninguna lo nombra y el titular del artículo sí, el titular (tal como está
    guardado, sin el nombre del medio); si tampoco, la primera frase, como antes. Así la cita
    respalda el titular del incidente (proceso/cita_titular.py) siempre que la fuente lo permite."""
    for frase in frases:
        if cita_titular.nombra([frase], nombres):
            return frase
    limpio = cita_titular.titular_limpio(titular, medio)
    if limpio and cita_titular.nombra([limpio], nombres):
        return limpio
    return frases[0] if frases else titular


def fuentes_incidente(
    articulos: list[Documento], enviadas: list[str], ficha: Validada
) -> list[Documento]:
    """Una fuente por artículo con idioma conocido; las enviadas llevan sus campos y frase. La
    frase de cada fuente es la que nombra el lugar o el país del suceso (cita_con_lugar), con la
    de es_incidente delante."""
    por_fuente: dict[str, list[str]] = defaultdict(list)
    frases: dict[str, list[str]] = defaultdict(list)
    for nombre, campo in sorted(ficha.campos.items(), key=lambda c: c[0] != "es_incidente"):
        url = enviadas[campo["fuente"] - 1]
        por_fuente[url].append(nombre)
        if campo.get("frase"):
            frases[url].append(campo["frase"])
    nombres = nombres_del_suceso(ficha)
    utiles = [a for a in articulos if a.get("idioma")]
    nivel = credibilidad_noticias(len(utiles))
    resultado = []
    for articulo in sorted(utiles, key=lambda a: (a["fecha"], a["url"])):
        url = articulo["url"]
        fuente: Documento = {
            "id": id_fuente(url),
            "enlace": url,
            "medio": articulo["medio"],
            "fecha": _instante(datetime.fromisoformat(articulo["fecha"]), "aproximada"),
            "idioma": articulo["idioma"],
            "fiabilidad": FIABILIDAD_NOTICIAS,
            "credibilidad": nivel,
            "frase_origen": _frase(
                cita_con_lugar(frases[url], str(articulo["titular"]), nombres, articulo["medio"])
            ),
            "replicas": articulo.get("replicas", 0),
            "es_autoridad": False,
            "interna_fuera_de_ucrania": False,
            "publica": True,
        }
        if por_fuente.get(url):
            fuente["campos_respaldados"] = sorted(por_fuente[url])
        resultado.append(fuente)
    return resultado


def _rango(valor: Any) -> Documento | str:
    return {"min": valor["min"], "max": valor["max"]} if isinstance(valor, dict) else "desconocido"


def _hay_interrupcion(documento: Documento) -> bool:
    consecuencias = documento.get("consecuencias", {})
    cierre = consecuencias.get("cierre", {}).get("valor") == "si"
    vuelos = any(
        isinstance(consecuencias.get(c), dict) and consecuencias[c]["min"] > 0
        for c in ("vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados")
    )
    return (cierre and documento.get("objetivo", {}).get("categoria") == "aeropuerto") or vuelos


def origen_inicio(
    resolucion: "fechas.Resolucion", enviadas: list[str], ficha: Validada
) -> Documento:
    """De dónde sale el día del inicio: la frase que lo escribe (explícito o relativo a la
    publicación) o, si no lo escribe ninguna, la fecha de publicación."""
    origen: Documento = {"tipo": resolucion.origen, "motivo": resolucion.motivo[:MAX_MOTIVO]}
    campo = ficha.campos.get("inicio")
    fuente = campo.get("fuente") if campo else None
    if isinstance(fuente, int) and 1 <= fuente <= len(enviadas):
        origen["fuente_id"] = id_fuente(enviadas[fuente - 1])
    if resolucion.corregido:
        origen["corregido"] = True
    return origen


def documento_lugar(ubicacion: Ubicacion, localidad: str | None) -> Documento:
    """El lugar del incidente: con punto y radio solo si la ubicación lo tiene."""
    lugar: Documento = {"pais": ubicacion.pais, "nivel": ubicacion.nivel}
    if ubicacion.sitio is not None:
        lugar["punto"] = {
            "lat": round(ubicacion.sitio.lat, DECIMALES),
            "lon": round(ubicacion.sitio.lon, DECIMALES),
        }
        lugar["radio_km"] = ubicacion.sitio.radio_km
        lugar["geocodificacion"] = ubicacion.origen
    if localidad:
        lugar["localidad"] = localidad
    if ubicacion.region:
        lugar["region"] = ubicacion.region
    if ubicacion.nombre:
        lugar["suceso"] = ubicacion.nombre
    return lugar


def pruebas(ficha: Validada) -> Documento:
    """Lo que la ficha dice del dron y de su entrada, para las reglas de tipo y presencia.

    Las fichas anteriores a estos datos solo tienen origen_demostrado (rastreo o restos
    que prueban que entró desde otro país): valen como entrada desde fuera de un dron
    estatal si la ficha decía incursión.
    """
    origen = set(ficha.valor("origen_demostrado") or [])
    legado = ficha.valor("tipo") == "incursion" and bool(origen)
    evidencia = set(ficha.valor("evidencia") or []) | origen
    modelo = normalizar(str(ficha.valor("modelo_dron") or ""))
    militar = "explosion" in evidencia or any(m in modelo for m in MODELOS_MILITARES)
    return {
        "dron_estatal": bool(ficha.valor("dron_estatal") or legado or militar),
        "entrada_exterior": bool(ficha.valor("entrada_exterior") or legado),
        "evidencia": sorted(evidencia),
    }


def aplicar_reglas(documento: Documento) -> Documento:
    """Tipo, presencia del dron y pruebas del origen según las reglas del diseño.

    Se aplica cada vez que cambia algo de lo que dependen: al construir el incidente, tras
    las declaraciones oficiales, al enlazar una nota oficial y al fundir.
    """
    resultado = copy.deepcopy(documento)
    if "pruebas" in resultado:
        fisicas = set(resultado["pruebas"].get("evidencia", [])) & PRUEBAS_FISICAS
        autoridad = resultado["estado"]["actual"] in CONFIRMADOS
        if autoridad and fisicas and resultado.get("presencia_dron") != "descartada":
            resultado["presencia_dron"] = "confirmada"
        resultado.pop("origen_demostrado_por", None)
    return con_tipo(resultado)


def con_tipo(documento: Documento) -> Documento:
    """El documento (modificado) con su tipo (docs/control_fichas.md, «tipo»): interrupción
    aeroportuaria si se interrumpió un aeropuerto; incursión solo si una autoridad (la que lo
    atribuye o la que cuenta el espacio aéreo violado, la frontera cruzada, el rastreo, el derribo,
    la caída o los restos), o una prueba física o un rastreo con el suceso confirmado por una
    autoridad, demuestra que un dron estatal entró desde fuera; si no, sobrevuelo. Que el suceso
    esté confirmado no demuestra la entrada (EODI-2025-00080, Kleine-Brogel: nadie dice de dónde
    venían), ni que un buque fuera alcanzado en el mar (EODI-2026-00512: ninguna autoridad dice
    que estuviera en aguas búlgaras)."""
    resultado = documento
    if "pruebas" not in resultado:
        # Incidente anterior a estas reglas: solo se aplica la precedencia de la interrupción.
        if _hay_interrupcion(resultado):
            resultado["tipo"] = "interrupcion_aeroportuaria"
            resultado.pop("origen_demostrado_por", None)
        return resultado
    datos = resultado["pruebas"]
    evidencia = set(datos.get("evidencia", []))
    confirmado = resultado["estado"]["actual"] in CONFIRMADOS
    # Los restos en un buque alcanzado en el mar no dicen que el dron entrara en el país; el
    # radar y el espacio aéreo que cuenta la autoridad, sí (EODI-2026-00541, al sureste de Sulina).
    en_el_mar = alcanzado_en_el_mar(resultado)
    pruebas = (
        (evidencia & ({RASTREO} if en_el_mar else PRUEBAS_FISICAS | {RASTREO}))
        if confirmado
        else set()
    )
    atribuido = resultado["estado"]["actual"] == Estado.ATRIBUIDO
    autoridad = atribuido or (
        confirmado and autoridad_cuenta_la_entrada(resultado, solo_espacio=en_el_mar)
    )
    demostrada = sorted(pruebas | ({"autoridad"} if autoridad else set()))
    if _hay_interrupcion(resultado):
        resultado["tipo"] = "interrupcion_aeroportuaria"
    elif datos.get("dron_estatal") and datos.get("entrada_exterior") and demostrada:
        resultado["tipo"] = "incursion"
        resultado["origen_demostrado_por"] = demostrada
    else:
        resultado["tipo"] = "sobrevuelo"
        resultado.pop("origen_demostrado_por", None)
    return resultado


# Lo que cuenta una autoridad cuando demuestra la entrada: el espacio aéreo violado, la frontera
# cruzada, el rastreo, el derribo, la caída o los restos del dron (EODI-2026-00238: «au stabilit
# că este vorba despre resturi de dronă»; EODI-2026-00112: «a survolat ... ilegal spațiul
# aerian»). Un ministro que dice que los drones «no eran un sobrevuelo normal» no lo demuestra
# (EODI-2025-00080, Kleine-Brogel).
_ESPACIO_DE_AUTORIDAD = (
    r"spa[tțţ]iul(?:ui)? aerian|espacio a[eé]reo|airspace|przestrze[nń]\w* powietrzn|luftraum|"
    r"luchtruim|ilmatila|luftrum|espace a[eé]rien|spazio aereo|въздушно(?:то)? пространство|"
    r"повітрян\w* простор|воздушн\w* пространств"
)
_ESPACIO_AEREO = re.compile(_ESPACIO_DE_AUTORIDAD, re.IGNORECASE)
_ENTRADA_DE_AUTORIDAD = re.compile(
    _ESPACIO_DE_AUTORIDAD + "|"
    # la frontera cruzada o el dron llegado de fuera (en el mar no dice dónde estaba el buque)
    r"fronti?er\w* de stat|granic\w* pa[nń]stw|state border|hailed from|din ucraina|"
    r"from (?:ukraine|russia|belarus)|z bia[lł]orusi|rusești|rusesti|russian drone|"
    # el rastreo, el derribo, la caída o los restos
    r"detectat|detected|urm[aă]rit|tracked|reperat|radar|survol|dobor[aâ]t|shot down|derribad|"
    r"zestrzel|c[aă]zut|crashed|pr[aă]bu[sșş]|eksplozj|explod|distrus|destroyed|"
    r"resturi|fragmente|szcz[aą]tk|restos del dron|debris|wreckage|tr[uü]mmer",
    re.IGNORECASE,
)


def autoridad_cuenta_la_entrada(documento: Documento, solo_espacio: bool = False) -> bool:
    """Una autoridad cuenta el espacio aéreo violado, la frontera cruzada, el rastreo, el derribo,
    la caída o los restos del dron (con `solo_espacio`, en el mar, solo el espacio aéreo
    violado)."""
    from proceso import declaraciones

    patron = _ESPACIO_AEREO if solo_espacio else _ENTRADA_DE_AUTORIDAD
    return any(
        declaraciones.de_autoridad(f) and patron.search(str(f.get("frase_origen") or ""))
        for f in documento.get("fuentes", [])
    )


def alcanzado_en_el_mar(documento: Documento) -> bool:
    """Un buque alcanzado por un dron en el mar, según el titular y las frases de sus fuentes."""
    textos = buques.textos_de(documento)
    return buques.alcanzado(textos) and buques.en_el_mar(textos)


def objetivo_es_la_localidad(objetivo: Documento | None, lugar: Documento) -> bool:
    """Un objetivo «otra» que se llama como la localidad del suceso no es una instalación: es el
    lugar. No se guarda como objetivo (EODI-2026-00648, «Józefów · Otro lugar»). Con el lugar a
    nivel de instalación, el sitio del suceso es la propia instalación y no cuenta: la cárcel de
    Mas d'Enric de EODI-2025-00404 salía en la auditoría A y el control la quitaba cada hora."""
    nombre = normalizar(str((objetivo or {}).get("nombre") or ""))
    campos = ("localidad",) if lugar.get("nivel") == "instalacion" else ("localidad", "suceso")
    return (
        (objetivo or {}).get("categoria") == "otra"
        and bool(nombre)
        and nombre in {normalizar(str(lugar[c])) for c in campos if lugar.get(c)}
    )


def lugar_sin_buque(lugar: Documento, textos: list[str]) -> Documento:
    """El lugar del suceso sin el nombre de un buque (proceso/buques.py): si el lugar es el nombre
    del barco, pasa a ser la zona marítima que nombran las fuentes (o el mar), sin punto, a nivel
    de región. El 20 de octubre de 2026 el buque Chelsea 3 salió como lugar del suceso."""
    nombres = [lugar.get("suceso"), lugar.get("localidad")]
    if not any(buques.es_nombre_de_buque(n, textos) for n in nombres if n):
        return lugar
    zona = buques.zona_maritima(textos)
    nuevo: Documento = {
        "pais": lugar["pais"],
        "nivel": "region",
        "suceso": zona[0] if zona else "mar",
    }
    if lugar.get("region"):
        nuevo["region"] = lugar["region"]
    return nuevo


def _fin_con_frase(
    ficha: Validada,
    fin: datetime,
    inicio: datetime,
    articulos: list[Documento],
    enviadas: list[str],
    ubicacion: Ubicacion,
) -> bool:
    """La frase del fin escribe esa hora o la duración que lleva a ella (fechas.fin_escrito):
    un fin que el extractor deduce sin que nadie lo escriba no se guarda (EODI-2025-00154)."""
    campo = ficha.campos.get("fin") or {}
    fuente = campo.get("fuente")
    url = enviadas[fuente - 1] if isinstance(fuente, int) and 1 <= fuente <= len(enviadas) else None
    idioma = next((a.get("idioma") for a in articulos if a.get("url") == url), None)
    punto = ubicacion.sitio
    zona_suceso = fechas.zona(
        ubicacion.pais, punto.lat if punto else None, punto.lon if punto else None
    )
    return fechas.fin_escrito(
        str(campo.get("frase") or ""), idioma, fin.replace(tzinfo=fin.tzinfo or UTC),
        inicio.replace(tzinfo=inicio.tzinfo or UTC), zona_suceso or ZoneInfo("UTC"),
    )  # fmt: skip


def construir(
    id_: str,
    ubicacion: Ubicacion,
    candidato: Documento,
    articulos: list[Documento],
    enviadas: list[str],
    ficha: Validada,
    ahora: datetime,
    version: str,
    modelos_validos: frozenset[str],
) -> Documento:
    """Documento del incidente a partir del candidato y la ficha ya validada."""
    fuentes = fuentes_incidente(articulos, enviadas, ficha)
    primera = fuentes[0]
    # El día del suceso, comprobado con la frase que lo dice (proceso/fechas.py): si la frase
    # no escribe el día, la fecha es la de publicación, aproximada, y así se declara.
    punto = ubicacion.sitio
    resolucion = fechas.inicio_de_ficha(
        ficha.campos, enviadas, articulos, candidato["inicio"], ubicacion.pais,
        punto.lat if punto else None, punto.lon if punto else None,
    )  # fmt: skip
    inicio = _instante(resolucion.valor, resolucion.precision)
    tiempo: Documento = {"inicio": inicio, "origen_inicio": origen_inicio(resolucion, enviadas,
                                                                          ficha)}  # fmt: skip
    fin_ficha = leer_fecha(ficha.valor("fin") or "")
    if fin_ficha is not None and "T" in ficha.valor("fin"):
        # El fin lleva el mismo error que el inicio si este venía en hora local
        # (fechas.hora_en_utc).
        fin_ficha -= resolucion.desfase
    if (
        fin_ficha is not None
        and "T" in ficha.valor("fin")
        and resolucion.precision in suceso.PRECISIONES_HORA
        and timedelta(0) <= fin_ficha - resolucion.valor <= MAX_DURACION
        and _fin_con_frase(ficha, fin_ficha, resolucion.valor, articulos, enviadas, ubicacion)
    ):
        tiempo["fin"] = _instante(fin_ficha, "minuto")
        tiempo["duracion_min"] = int((fin_ficha - _leer_instante(inicio)).total_seconds()) // 60
    lugar = documento_lugar(ubicacion, ficha.valor("localidad"))
    textos_buque = [str(c.get("frase") or "") for c in ficha.campos.values()]
    textos_buque += [str(a.get("titular") or "") for a in articulos]
    textos_buque += [ficha.titulo_es or "", ficha.titulo_en or ""]
    sin_buque = lugar_sin_buque(lugar, textos_buque)
    if sin_buque is not lugar:
        lugar = sin_buque
        ubicacion = Ubicacion(ubicacion.pais, "region", nombre=sin_buque["suceso"],
                              region=sin_buque.get("region"))  # fmt: skip
    objetivo = ubicacion.sitio
    datos_objetivo: Documento | None = None
    if objetivo is not None:
        datos_objetivo = {"categoria": objetivo.categoria, "nombre": objetivo.nombre}
        if objetivo.oaci and objetivo.categoria == "aeropuerto":
            datos_objetivo["oaci"] = objetivo.oaci
    elif ficha.valor("objetivo_categoria"):
        datos_objetivo = {"categoria": ficha.valor("objetivo_categoria")}
        if ficha.valor("objetivo_nombre"):
            datos_objetivo["nombre"] = ficha.valor("objetivo_nombre")
    sitio = objetivo.nombre if objetivo else ubicacion.nombre or ubicacion.pais
    if objetivo_es_la_localidad(datos_objetivo, lugar):
        datos_objetivo = None
    drones: Documento = {"numero": _rango(ficha.valor("drones"))}
    if ficha.valor("modelo_dron") in modelos_validos:
        drones["modelo"] = ficha.valor("modelo_dron")
    consecuencias: Documento = {"cierre": {"valor": ficha.valor("cierre") or "desconocido"}}
    if ficha.valor("cierre_minutos"):
        consecuencias["cierre"]["minutos"] = _rango(ficha.valor("cierre_minutos"))
    for campo in ("vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados"):
        if ficha.valor(campo):
            consecuencias[campo] = _rango(ficha.valor(campo))
    documento: Documento = {
        "id": id_,
        "tipo": "sobrevuelo",
        "estado": nuevo_estado(primera["fecha"], primera["id"]),
        "titulo": {
            "es": ficha.titulo_es or f"Drones en {sitio}",
            "en": ficha.titulo_en or f"Drones at {sitio}",
        },
        "presencia_dron": ficha.valor("presencia_dron") or "no_confirmada",
        "tiempo": tiempo,
        "lugar": lugar,
        "drones": drones,
        "consecuencias": consecuencias,
        "fuentes": fuentes,
        "afirmaciones": [
            {
                "campo": nombre,
                "valor": campo["valor"],
                "fuente_id": id_fuente(enviadas[campo["fuente"] - 1]),
                "confianza_extraccion": float(campo["confianza"]),
            }
            for nombre, campo in sorted(ficha.campos.items())
            if any(f["id"] == id_fuente(enviadas[campo["fuente"] - 1]) for f in fuentes)
        ],
        "control": {
            "alta": _instante(ahora, "minuto"),
            "ultima_actualizacion": _instante(ahora, "minuto"),
            "version_extractor": version,
            "huella_fuentes": huella([f["enlace"] for f in fuentes]),
            # El candidato del que sale: al rehacerlo, conserva su identificador.
            "candidato": candidato["id"],
        },
    }
    if datos_objetivo is not None:
        documento["objetivo"] = datos_objetivo
    medidas = ficha.valor("medidas")
    if medidas:
        documento["respuesta"] = {"medidas": sorted(set(medidas))}
    documento["pruebas"] = pruebas(ficha)
    # El tipo sigue las reglas del diseño, no lo que diga la ficha.
    return aplicar_reglas(documento)


# --- Fusión -------------------------------------------------------------------------


def absorber(
    destino: Documento, absorbido: Documento, ahora: datetime
) -> tuple[Documento, list[str]]:
    """El destino con las fuentes y afirmaciones del absorbido; y las fuentes aportadas."""
    resultado = copy.deepcopy(destino)
    ids = {f["id"] for f in resultado["fuentes"]}
    aportadas = [f for f in absorbido["fuentes"] if f["id"] not in ids]
    resultado["fuentes"] = sorted(
        resultado["fuentes"] + copy.deepcopy(aportadas),
        key=lambda f: (f["fecha"]["valor"], f["id"]),
    )
    nivel = credibilidad_noticias(len(resultado["fuentes"]))
    for fuente in resultado["fuentes"]:
        fuente["credibilidad"] = nivel
    aportadas_ids = {f["id"] for f in aportadas}
    # Las afirmaciones del absorbido de todas las fuentes que quedan en el destino, no solo
    # de las nuevas: un valor que el destino hereda (sus medidas, su fin) tiene que llevar la
    # afirmación que lo respalda aunque su fuente ya estuviera en el destino.
    en_destino = {f["id"] for f in resultado["fuentes"]}
    propias = resultado.get("afirmaciones", [])
    resultado["afirmaciones"] = propias + [
        a for a in absorbido.get("afirmaciones", [])
        if a["fuente_id"] in en_destino and a not in propias
    ]  # fmt: skip
    # Lo que al destino le faltaba y el absorbido sabe. Un día escrito por una fuente manda
    # sobre la fecha de publicación, si puede ser el de la jornada del destino: la fecha sale
    # del suceso, no de la ficha que llega (suceso.toma_el_tiempo).
    if suceso.toma_el_tiempo(resultado, absorbido):
        resultado["tiempo"] = copy.deepcopy(absorbido["tiempo"])
    if "fin" not in resultado["tiempo"] and "fin" in absorbido["tiempo"]:
        fin = absorbido["tiempo"]["fin"]
        if fin["valor"] >= resultado["tiempo"]["inicio"]["valor"]:
            resultado["tiempo"]["fin"] = fin
            inicio = _leer_instante(resultado["tiempo"]["inicio"])
            resultado["tiempo"]["duracion_min"] = (
                int((_leer_instante(fin) - inicio).total_seconds()) // 60
            )
    if "respuesta" not in resultado and "respuesta" in absorbido:
        resultado["respuesta"] = copy.deepcopy(absorbido["respuesta"])
    if resultado.get("presencia_dron") == "no_confirmada" and absorbido.get("presencia_dron"):
        resultado["presencia_dron"] = absorbido["presencia_dron"]
    propias, ajenas = resultado.get("pruebas", {}), absorbido.get("pruebas", {})
    if propias or ajenas:
        resultado["pruebas"] = {
            "dron_estatal": bool(propias.get("dron_estatal") or ajenas.get("dron_estatal")),
            "entrada_exterior": bool(
                propias.get("entrada_exterior") or ajenas.get("entrada_exterior")
            ),
            "evidencia": sorted(
                set(propias.get("evidencia", [])) | set(ajenas.get("evidencia", []))
            ),
        }
    resultado["control"]["huella_fuentes"] = huella([f["enlace"] for f in resultado["fuentes"]])
    resultado["control"]["ultima_actualizacion"] = _instante(ahora, "minuto")
    resultado["estado"] = estado_con_el_absorbido(resultado, absorbido)
    return aplicar_reglas(resultado), sorted(aportadas_ids)


# Orden de los estados que da una fuente oficial: un registro unido no pierde el que tenía.
RANGO_ESTADO = {"notificado": 0, "confirmado": 1, "atribuido": 2}


def estado_con_el_absorbido(destino: Documento, absorbido: Documento) -> Documento:
    """El estado del destino con los pasos a confirmado o atribuido del absorbido que el destino
    no tenía, si su fuente pasa al destino: al conservar el registro más antiguo
    (recogida/control_fichas.py), la confirmación oficial del otro no se pierde, aunque sea anterior
    al «notificado» del destino. Un desmentido no se toca, ni una rebaja con motivo posterior al
    paso del absorbido."""
    estado: Documento = destino["estado"]
    actual = estado["actual"]
    if actual not in RANGO_ESTADO or absorbido["estado"]["actual"] not in RANGO_ESTADO:
        return estado
    fuentes = {f["id"] for f in destino["fuentes"]}
    nivel = RANGO_ESTADO[actual]
    ultimo = estado["historial"][-1]["fecha"]["valor"]
    rebajado = "motivo" in estado["historial"][-1]
    nuevos = []
    for paso in absorbido["estado"]["historial"]:
        rango = RANGO_ESTADO.get(paso["estado"], -1)
        if (
            rango > nivel
            and paso.get("fuente_id") in fuentes
            and "motivo" not in paso
            and (paso["fecha"]["valor"] >= ultimo or not rebajado)
        ):
            nuevos.append(copy.deepcopy(paso))
            nivel = rango
    if not nuevos:
        return estado
    historial = [*estado["historial"], *nuevos]
    return {"actual": nuevos[-1]["estado"], "historial": historial}


def activo(documento: Documento) -> bool:
    """Ni fundido en otro ni retirado."""
    return "fusionado_en" not in documento and "retirado" not in documento


def fusionar(
    almacen: Almacen,
    ahora: datetime,
    modelos: frozenset[str],
    publicados: frozenset[str] | None = None,
) -> int:
    """Funde los incidentes que la definición da por el mismo suceso que uno solo anterior sin
    tener que leer sus fuentes (suceso.veredicto: el mismo sitio y la misma jornada, o la nota de
    una noche y sus alertas). Devuelve cuántas fusiones hace.

    `publicados`: los que estaban publicados antes (al rehacer todo, los activos de antes de
    deshacer las fusiones); por defecto, los dados de alta antes de esta ejecución."""
    activos = sorted(
        (i for i in almacen.incidentes() if activo(i)),
        key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]),
    )
    if publicados is None:
        marca = _instante(ahora, "minuto")["valor"]
        publicados = frozenset(i["id"] for i in activos if i["control"]["alta"]["valor"] < marca)
    vivos = {i["id"]: i for i in activos}
    del_experto = suceso.distintos_del_experto(almacen)
    hechas = 0
    for incidente in activos:
        if incidente["id"] not in vivos:
            continue
        dichos = {
            otro["id"]: suceso.veredicto(otro, incidente, del_experto)
            for otro in vivos.values()
            if otro["id"] != incidente["id"]
            and (otro["tiempo"]["inicio"]["valor"], otro["id"])
            < (incidente["tiempo"]["inicio"]["valor"], incidente["id"])
        }
        anteriores = [
            vivos[id_] for id_, dicho in dichos.items()
            if dicho.relacion == suceso.MISMO and dicho.regla in REGLAS_DE_FUSION
        ]  # fmt: skip
        # Dudosa si encaja con dos: no se hace. Una fecha de publicación no compite con una
        # escrita: entre los que encajan cuenta solo la mejor clase de fecha (hora, día,
        # publicación), y si de esa hay uno solo, es ese.
        anteriores = suceso.de_mejor_fecha(anteriores)
        if len(anteriores) > 1 and suceso.todos_encajan(anteriores):
            # Si los anteriores encajan también entre sí, son un mismo suceso partido (noticias
            # del mismo cierre en dos fichas): no hay duda, va al primero.
            anteriores = anteriores[:1]
        motivo = dichos[anteriores[0]["id"]].motivo if len(anteriores) == 1 else ""
        if not anteriores and suceso.nota_posterior(incidente):
            # Una nota que vuelve semanas o meses después sobre un suceso ya registrado: se une a
            # él si es el único de ese país, tipo y día (si hay dos, no se sabe a cuál).
            anteriores = [
                otro for otro in vivos.values()
                if otro["id"] != incidente["id"]
                and suceso.mismo_suceso_posterior(otro, incidente)
                and not suceso.no_se_juntan(otro, incidente, del_experto)
            ]  # fmt: skip
            motivo = suceso.MOTIVO_NOTA_POSTERIOR
        if len(anteriores) != 1:
            continue
        destino, absorbido = suceso.destino_de(anteriores[0], incidente, publicados)
        if retiene_la_union(almacen, absorbido, destino["id"]):
            continue
        if revisiones_distintas(absorbido["id"], destino["id"]):
            continue
        nuevo, aportadas = absorber(destino, absorbido, ahora)
        fundido = {**copy.deepcopy(absorbido), "fusionado_en": destino["id"]}
        fundido.pop("episodio", None)
        almacen.guardar_incidente(nuevo, ahora, modelos)
        almacen.guardar_incidente(fundido, ahora, modelos)
        almacen.registrar_fusion(
            _instante(ahora, "minuto")["valor"], absorbido["id"], destino["id"], motivo, aportadas,
            instantanea(almacen, destino, absorbido),
        )  # fmt: skip
        vivos[destino["id"]] = nuevo
        del vivos[absorbido["id"]]
        hechas += 1
    return hechas


def instantanea(almacen: Almacen, destino: Documento, absorbido: Documento) -> Documento:
    """La instantánea de una unión recién guardada, para `Almacen.registrar_fusion`: las dos
    fichas como estaban justo antes y la que queda como ha quedado guardada (con lo que hayan
    decidido las revisiones y el cerrojo al guardar)."""
    return {
        "destino": destino,
        "absorbido": absorbido,
        "despues": almacen.incidente(str(destino["id"])) or destino,
    }


# Lo que una unión le copia a la ficha que queda cuando le faltaba (`absorber`,
# `recogida/revisados.completar`): el día, el fin, la respuesta, la presencia, las pruebas y el
# cierre. Al deshacerla vuelve a su valor de antes.
COPIADOS_AL_UNIR = ("tiempo", "respuesta", "presencia_dron", "pruebas", "consecuencias")


def devolver_lo_copiado(destino: Documento, unida: Documento | None) -> list[str]:
    """Quita de `destino` (lo modifica) lo que la unión le copió del absorbido: cada dato de
    `COPIADOS_AL_UNIR` que la unión cambió vuelve a su valor de antes si sigue siendo el que la
    unión puso; lo que cambió después por otra vía (una revisión, una fuente nueva) se respeta.
    Devuelve los datos devueltos. Hasta el 10 de noviembre de 2026 deshacer una unión dejaba en
    la ficha que queda el día y las pruebas del otro suceso."""
    if not unida or not unida.get("destino") or not unida.get("despues"):
        return []
    antes, despues = unida["destino"], unida["despues"]
    devueltos = []
    for campo in COPIADOS_AL_UNIR:
        if despues.get(campo) == antes.get(campo) or destino.get(campo) != despues.get(campo):
            continue
        if campo in antes:
            destino[campo] = copy.deepcopy(antes[campo])
        else:
            destino.pop(campo, None)
        devueltos.append(campo)
    return devueltos


def retiene_la_reapertura(almacen: Almacen, absorbido: Documento, destino: str) -> bool:
    """El cerrojo, en «aplicar», retendría la reapertura de `absorbido` (deja de estar fundido en
    `destino`) hecha por una regla: solo pasa la de un par que no se une (una separación, unos
    distintos). La misma regla que `Almacen._cerrojo_reapertura`: lo que no va a pasar no se
    intenta, y no deja cada hora un guardado que el cerrojo devuelve."""
    from proceso import protegido

    if protegido.modo() != protegido.APLICAR:
        return False
    propio = {k: v for k, v in absorbido.items() if k != "fusionado_en"}
    return not protegido.es_separacion(almacen, propio, destino)


def retiene_la_union(almacen: Almacen, absorbido: Documento, destino: str) -> bool:
    """El cerrojo, en «aplicar», retendría marcar `absorbido` como fundida en `destino` (un par
    prohibido o una ficha manual que desaparecería; proceso/protegido.py, la misma regla): la
    unión no se intenta. Intentarla guardaba la que queda con las fuentes de la otra y el cerrojo
    la devolvía a lo que era en el mismo instante, en cada recogida: EODI-2026-00747 en
    EODI-2026-00743 desde el 6 de noviembre de 2026, dos cambios cada hora (auditoría K)."""
    from proceso import protegido

    if protegido.modo() != protegido.APLICAR:
        return False
    fundido = {**absorbido, "fusionado_en": destino}
    return (
        protegido.union_prohibida(almacen, fundido, destino) is not None
        or protegido.union_de_manual(almacen, absorbido, destino) is not None
    )


def revisiones_distintas(absorbido: str, destino: str) -> list[str]:
    """Los datos que las dos fichas tienen revisados a mano con valores distintos
    (proceso/decidir.revisiones_en_conflicto). Con alguno, la unión se retiene y no se hace, y
    queda en el registro: las revisiones van por el número de la ficha y la absorbida pasa las
    suyas a la que queda, así que no hay a cuál de las dos hacer caso."""
    from proceso import decidir

    distintos = decidir.revisiones_en_conflicto(absorbido, destino)
    if distintos:
        registro.warning(
            "unión %s→%s retenida: las dos tienen revisado a mano, con valores distintos, %s",
            absorbido, destino, ", ".join(distintos),
        )  # fmt: skip
    return distintos


def union_que_se_deshace(
    fusion: Documento, absorbido: Documento, destino: Documento,
    decididas: dict[str, dict[str, str]],
) -> suceso.Veredicto | None:  # fmt: skip
    """El veredicto por el que una unión vigente se deshace sola, o None: la definición da las
    dos fichas por sucesos distintos (suceso.veredicto) por una regla firme que no depende de
    haber leído las fuentes.

    - Las de la regla de fusión: una revisión que las separó, países distintos, dos cierres de
      noches distintas o un cierre que se repite.
    - Las que hizo el control leyendo las fuentes: solo países distintos (lo demás lo decidió
      quien las leyó). El 11 de noviembre de 2026 el filtro unió cinco fichas de Lituania a un
      resumen con el lugar en Letonia (EODI-2026-00778), y ahí siguieron.
    - Las revisadas a mano (recogida/revisados.py), nunca: no las deshace una regla."""
    motivo = str(fusion["motivo"])
    del_control = motivo.startswith(suceso.PREFIJO_CONTROL)
    if motivo.startswith(suceso.PREFIJO_REVISADA) and not del_control:
        return None
    propio = {k: v for k, v in absorbido.items() if k != "fusionado_en"}
    dicho = suceso.veredicto(
        propio, destino, de_a=decididas.get(str(absorbido["id"])),
        de_b=decididas.get(str(destino["id"])), vigente=True,
    )  # fmt: skip
    if dicho.relacion != suceso.DISTINTOS:
        return None
    reglas = {suceso.REGLA_PAISES} if del_control else REGLAS_QUE_DESHACEN
    return dicho if dicho.regla in reglas else None


def revisar_fusiones(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> list[str]:
    """Deshace las uniones vigentes que la definición da por sucesos distintos
    (`union_que_se_deshace`): el absorbido vuelve con sus fuentes y pasa otra vez por el control
    como cualquier ficha. Devuelve los absorbidos que vuelven."""
    vueltos = []
    decididas: dict[str, dict[str, str]] | None = None
    for fusion in almacen.fusiones():
        if fusion["revertida"]:
            continue
        motivo = str(fusion["motivo"])
        if motivo.startswith(suceso.PREFIJO_REVISADA) and not motivo.startswith(
            suceso.PREFIJO_CONTROL
        ):
            continue
        absorbido = almacen.incidente(fusion["absorbido"])
        destino = almacen.incidente(fusion["destino"])
        if absorbido is None or destino is None or "fusionado_en" not in absorbido:
            continue
        if absorbido["fusionado_en"] != destino["id"]:
            continue
        if decididas is None:
            decididas = suceso.autoridades_decididas(almacen)
        dicho = union_que_se_deshace(fusion, absorbido, destino, decididas)
        if dicho is not None:
            registro.info(
                "unión %s→%s: la definición las da por sucesos distintos (%s: %s)",
                fusion["absorbido"], fusion["destino"], dicho.regla, dicho.motivo,
            )  # fmt: skip
            # Antes de intentarla se pregunta al cerrojo (como `fusionar` con las uniones): una
            # reapertura que retendría no se intenta en cada recogida.
            if retiene_la_reapertura(almacen, absorbido, str(fusion["destino"])):
                continue
            # Cada fusión, aislada: una que no se puede deshacer no corta las demás.
            try:
                revertir(almacen, fusion["absorbido"], ahora, modelos)
            except Exception as error:
                registro.warning(
                    "fusión de %s sin deshacer: %s", fusion["absorbido"], str(error)[:200]
                )
                continue
            vueltos.append(fusion["absorbido"])
    return vueltos


def revertir(almacen: Almacen, absorbido_id: str, ahora: datetime, modelos: frozenset[str]) -> None:
    """Deshace la fusión: el absorbido vuelve a publicarse y el destino pierde lo aportado."""
    fusion = next(
        f
        for f in reversed(almacen.fusiones())
        if f["absorbido"] == absorbido_id and not f["revertida"]
    )
    absorbido = almacen.incidente(absorbido_id)
    destino = almacen.incidente(fusion["destino"])
    if absorbido is None or destino is None:
        raise KeyError(absorbido_id)
    unida = almacen.instantanea_de_fusion(absorbido_id)
    aportadas = set(fusion["fuentes"])
    destino["fuentes"] = [f for f in destino["fuentes"] if f["id"] not in aportadas]
    destino["afirmaciones"] = [
        a for a in destino.get("afirmaciones", []) if a["fuente_id"] not in aportadas
    ]
    # La respuesta que el destino heredó del absorbido (absorber) se va con sus fuentes: sin una
    # afirmación de las medidas que quede, no tiene origen (EODI-2026-00281, el 19 de octubre de
    # 2026: la patrulla del dron de Palanca se quedaba en la ficha de Tudora).
    if "respuesta" in destino and not any(a["campo"] == "medidas" for a in destino["afirmaciones"]):
        del destino["respuesta"]
    # Los pasos del estado que dio una fuente del absorbido (estado_con_el_absorbido) se van con
    # ella: si no, el destino cita una fuente que ya no tiene y no se puede guardar.
    pasos = [p for p in destino["estado"]["historial"] if p.get("fuente_id") not in aportadas]
    if pasos and len(pasos) < len(destino["estado"]["historial"]):
        destino["estado"] = {"actual": pasos[-1]["estado"], "historial": pasos}
    # Lo que la unión le copió del absorbido (su día, su fin, su presencia, sus pruebas, su
    # cierre) vuelve a como estaba antes de unirse.
    devueltos = devolver_lo_copiado(destino, unida)
    if devueltos:
        registro.info(
            "%s: al deshacer la unión de %s vuelve a su valor de antes: %s",
            destino["id"], absorbido_id, ", ".join(devueltos),
        )  # fmt: skip
    nivel = credibilidad_noticias(len(destino["fuentes"]))
    for fuente in destino["fuentes"]:
        fuente["credibilidad"] = nivel
    destino["control"]["huella_fuentes"] = huella([f["enlace"] for f in destino["fuentes"]])
    destino["control"]["ultima_actualizacion"] = _instante(ahora, "minuto")
    absorbido.pop("fusionado_en")
    almacen.guardar_incidente(destino, ahora, modelos)
    almacen.guardar_incidente(absorbido, ahora, modelos)
    almacen.revertir_fusion(absorbido_id)


# --- Episodios ----------------------------------------------------------------------


def agrupar_episodios(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Rehace los episodios con las reglas: los que dejan de serlo se deshacen (nada se
    borra: el episodio queda marcado) y sus incidentes pierden el enlace. Devuelve cuántos
    incidentes cambian de episodio."""
    todos = almacen.incidentes()
    anteriores = {e["id"]: e for e in almacen.episodios()}
    asignado: dict[str, str] = {}
    usados: set[str] = set()
    for fecha, miembros in suceso.episodios_calculados(todos):
        ids = sorted(m["id"] for m in miembros)
        existentes = sorted(
            {m["episodio"] for m in miembros if "episodio" in m} - usados
        )  # fmt: skip
        # Un episodio con los mismos incidentes esa noche es el mismo aunque sus incidentes
        # hayan perdido el enlace al rehacerse: se reutiliza en vez de numerar otro.
        iguales = sorted(
            e["id"] for e in anteriores.values()
            if e["noche"] == fecha and e["incidentes"] == ids and e["id"] not in usados
        )  # fmt: skip
        candidatos_id = existentes or iguales
        id_ = candidatos_id[0] if candidatos_id else almacen.siguiente_id_episodio(int(fecha[:4]))
        usados.add(id_)
        documento = {"id": id_, "noche": fecha, "incidentes": ids}
        if anteriores.get(id_) != documento:
            almacen.guardar_episodio(documento, ahora)
        asignado |= {m["id"]: id_ for m in miembros}
    for id_, episodio in anteriores.items():
        if id_ not in usados and "deshecho" not in episodio:
            almacen.guardar_episodio({**episodio, "deshecho": _instante(ahora, "minuto")}, ahora)
    cambios = 0
    for incidente in todos:
        nuevo = asignado.get(incidente["id"])
        if incidente.get("episodio") == nuevo:
            continue
        documento = {k: v for k, v in incidente.items() if k != "episodio"}
        if nuevo is not None:
            documento["episodio"] = nuevo
        almacen.guardar_incidente(documento, ahora, modelos)
        cambios += 1
    return cambios
