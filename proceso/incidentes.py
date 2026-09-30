"""Incidentes europeos a partir de candidatos y fichas validadas; fusión y episodios.

Reglas del diseño:
- Fusión: mismo objetivo o puntos a menos de la suma de radios más 10 km; con
  precisión de hora, inicios a menos de 6 horas; con precisión de día, el
  mismo día o el siguiente; más de 12 horas sin actividad es otro incidente.
  Una fusión dudosa (el incidente encaja con dos) no se hace. Toda fusión es
  reversible: el absorbido queda en la base con `fusionado_en` y la tabla de
  fusiones anota qué fuentes aportó; el historial guarda cada cambio.
- Un incidente sin punto (su lugar solo se sabe a nivel de país o de región) solo se
  funde con otro sin punto del mismo país y con el mismo lugar del suceso.
- Episodio: varios objetivos distintos del mismo país en una misma noche, todos con
  punto; o de varios países si una misma fuente los cuenta. Un incidente sin punto
  (ubicación dudosa) no entra en ningún episodio.
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
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from almacen.base import Almacen
from esquema import Documento
from proceso.credibilidad import Declaracion, Fiabilidad, Postura, credibilidad
from proceso.estados import Estado, nuevo_estado
from proceso.noticias import normalizar
from proceso.ubicacion import Ubicacion
from proceso.validacion_ficha import Validada, leer_fecha

MAX_PALABRAS_FRASE = 25
DECIMALES = 5
MARGEN_FUSION_KM = 10.0
INICIOS_HORA = timedelta(hours=6)
SIN_ACTIVIDAD = timedelta(hours=12)
RADIO_TIERRA_KM = 6371.0
# La noche de un episodio: de las 16:00 a las 06:00 UTC (17:00 a 07:00 en Europa central
# en invierno, 18:00 a 08:00 en verano), cuando se producen casi todos los avistamientos.
HORA_INICIO_NOCHE = 16
HORA_FIN_NOCHE = 6
MEDIODIA = 12
PRECISIONES_HORA = frozenset({"minuto", "hora"})
FIABILIDAD_NOTICIAS = "C"
# «Varios objetivos»: dos o más.
MIN_OBJETIVOS_EPISODIO = 2
# Pruebas físicas de que el incidente consiste en el propio dron.
PRUEBAS_FISICAS = frozenset({"explosion", "restos", "caida", "derribo", "recuperado"})
RASTREO = "rastreo"
# Un dron que explota lleva carga explosiva: es militar. También lo es uno de estos modelos.
MODELOS_MILITARES = ("shahed", "geran", "gerbera")
# Estados a los que solo lleva una autoridad.
CONFIRMADOS = frozenset({Estado.CONFIRMADO, Estado.ATRIBUIDO})


def _instante(momento: datetime, precision: str) -> Documento:
    return {"valor": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ"), "precision": precision}


def _leer_instante(instante: Documento) -> datetime:
    return datetime.strptime(instante["valor"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


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


def fuentes_incidente(
    articulos: list[Documento], enviadas: list[str], ficha: Validada
) -> list[Documento]:
    """Una fuente por artículo con idioma conocido; las enviadas llevan sus campos y frase."""
    por_fuente: dict[str, list[str]] = defaultdict(list)
    frases: dict[str, str] = {}
    for nombre, campo in ficha.campos.items():
        url = enviadas[campo["fuente"] - 1]
        por_fuente[url].append(nombre)
        frases.setdefault(url, campo["frase"])
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
            "frase_origen": _frase(frases.get(url) or str(articulo["titular"])),
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
    if "pruebas" not in resultado:
        # Incidente anterior a estas reglas: solo se aplica la precedencia de la interrupción.
        if _hay_interrupcion(resultado):
            resultado["tipo"] = "interrupcion_aeroportuaria"
            resultado.pop("origen_demostrado_por", None)
        return resultado
    datos = resultado["pruebas"]
    evidencia = set(datos.get("evidencia", []))
    fisicas = evidencia & PRUEBAS_FISICAS
    autoridad = resultado["estado"]["actual"] in CONFIRMADOS
    if autoridad and fisicas and resultado.get("presencia_dron") != "descartada":
        resultado["presencia_dron"] = "confirmada"
    demostrada = sorted(fisicas | (evidencia & {RASTREO}) | ({"autoridad"} if autoridad else set()))
    resultado.pop("origen_demostrado_por", None)
    if _hay_interrupcion(resultado):
        resultado["tipo"] = "interrupcion_aeroportuaria"
    elif datos.get("dron_estatal") and datos.get("entrada_exterior") and demostrada:
        resultado["tipo"] = "incursion"
        resultado["origen_demostrado_por"] = demostrada
    else:
        resultado["tipo"] = "sobrevuelo"
    return resultado


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
    inicio_ficha = leer_fecha(ficha.valor("inicio") or "")
    if inicio_ficha is not None:
        precision = ficha.valor("inicio_precision") or "dia"
        if "T" not in ficha.valor("inicio"):
            precision = "dia"
        inicio = _instante(inicio_ficha, precision)
    else:
        inicio = _instante(datetime.fromisoformat(candidato["inicio"]), "dia")
    tiempo: Documento = {"inicio": inicio}
    fin_ficha = leer_fecha(ficha.valor("fin") or "")
    if fin_ficha is not None and "T" in ficha.valor("fin"):
        tiempo["fin"] = _instante(fin_ficha, "minuto")
        tiempo["duracion_min"] = int((fin_ficha - _leer_instante(inicio)).total_seconds()) // 60
    lugar = documento_lugar(ubicacion, ficha.valor("localidad"))
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


def _distancia_km(a: Documento, b: Documento) -> float:
    pa, pb = a["lugar"]["punto"], b["lugar"]["punto"]
    f1, f2 = math.radians(pa["lat"]), math.radians(pb["lat"])
    df, dl = f2 - f1, math.radians(pb["lon"] - pa["lon"])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def con_punto(documento: Documento) -> bool:
    return "punto" in documento["lugar"]


def mismo_sitio(a: Documento, b: Documento) -> bool:
    if a["lugar"]["pais"] != b["lugar"]["pais"]:
        return False
    if not con_punto(a) or not con_punto(b):
        # Sin punto, solo dos sin punto con el mismo lugar del suceso.
        sucesos = [normalizar(d["lugar"].get("suceso", "")) for d in (a, b)]
        return not con_punto(a) and not con_punto(b) and bool(sucesos[0]) and len(set(sucesos)) == 1
    oa, ob = a.get("objetivo", {}), b.get("objetivo", {})
    if oa.get("nombre") and oa.get("nombre") == ob.get("nombre"):
        return True
    radios = float(a["lugar"]["radio_km"]) + float(b["lugar"]["radio_km"])
    return _distancia_km(a, b) < radios + MARGEN_FUSION_KM


def ultima_actividad(documento: Documento) -> datetime:
    momentos = [_leer_instante(documento["tiempo"]["inicio"])]
    if "fin" in documento["tiempo"]:
        momentos.append(_leer_instante(documento["tiempo"]["fin"]))
    momentos += [_leer_instante(f["fecha"]) for f in documento["fuentes"]]
    return max(momentos)


def misma_ventana(a: Documento, b: Documento) -> bool:
    """`a` empezó antes o a la vez que `b`."""
    inicio_a, inicio_b = a["tiempo"]["inicio"], b["tiempo"]["inicio"]
    ta, tb = _leer_instante(inicio_a), _leer_instante(inicio_b)
    if inicio_b["precision"] in PRECISIONES_HORA and tb - ultima_actividad(a) > SIN_ACTIVIDAD:
        return False
    if inicio_a["precision"] in PRECISIONES_HORA and inicio_b["precision"] in PRECISIONES_HORA:
        return abs(tb - ta) < INICIOS_HORA
    return tb.date() in {ta.date(), ta.date() + timedelta(days=1)}


def encajan(a: Documento, b: Documento) -> bool:
    primero, segundo = sorted((a, b), key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]))
    return mismo_sitio(a, b) and misma_ventana(primero, segundo)


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
    resultado["afirmaciones"] = resultado.get("afirmaciones", []) + [
        a for a in absorbido.get("afirmaciones", []) if a["fuente_id"] in aportadas_ids
    ]
    # Lo que al destino le faltaba y el absorbido sabe.
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
    return aplicar_reglas(resultado), sorted(aportadas_ids)


def activo(documento: Documento) -> bool:
    """Ni fundido en otro ni retirado."""
    return "fusionado_en" not in documento and "retirado" not in documento


def fusionar(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Funde los incidentes que encajan con uno solo anterior. Devuelve cuántas fusiones hace."""
    activos = sorted(
        (i for i in almacen.incidentes() if activo(i)),
        key=lambda d: (d["tiempo"]["inicio"]["valor"], d["id"]),
    )
    vivos = {i["id"]: i for i in activos}
    hechas = 0
    for incidente in activos:
        if incidente["id"] not in vivos:
            continue
        anteriores = [
            otro
            for otro in vivos.values()
            if otro["id"] != incidente["id"]
            and (otro["tiempo"]["inicio"]["valor"], otro["id"])
            < (incidente["tiempo"]["inicio"]["valor"], incidente["id"])
            and encajan(otro, incidente)
        ]
        # Dudosa si encaja con dos: no se hace.
        if len(anteriores) != 1:
            continue
        destino = anteriores[0]
        nuevo, aportadas = absorber(destino, incidente, ahora)
        fundido = {**copy.deepcopy(incidente), "fusionado_en": destino["id"]}
        almacen.guardar_incidente(nuevo, ahora, modelos)
        almacen.guardar_incidente(fundido, ahora, modelos)
        almacen.registrar_fusion(
            _instante(ahora, "minuto")["valor"], incidente["id"], destino["id"],
            "mismo sitio y misma ventana", aportadas,
        )  # fmt: skip
        vivos[destino["id"]] = nuevo
        del vivos[incidente["id"]]
        hechas += 1
    return hechas


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
    aportadas = set(fusion["fuentes"])
    destino["fuentes"] = [f for f in destino["fuentes"] if f["id"] not in aportadas]
    destino["afirmaciones"] = [
        a for a in destino.get("afirmaciones", []) if a["fuente_id"] not in aportadas
    ]
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


def noche(documento: Documento) -> str | None:
    """Fecha de la tarde de la noche del incidente, o None si no fue de noche o no se sabe."""
    inicio = documento["tiempo"]["inicio"]
    if inicio["precision"] not in PRECISIONES_HORA:
        return None
    momento = _leer_instante(inicio)
    if HORA_FIN_NOCHE <= momento.hour < HORA_INICIO_NOCHE:
        return None
    return (momento - timedelta(hours=MEDIODIA)).date().isoformat()


def _grupos_de_una_noche(miembros: list[Documento]) -> list[list[Documento]]:
    """Grupos de una noche: los del mismo país, unidos a los de otro país con una fuente en
    común (una noticia que cuenta los dos)."""
    padre = {m["id"]: m["id"] for m in miembros}

    def raiz(id_: str) -> str:
        while padre[id_] != id_:
            padre[id_] = padre[padre[id_]]
            id_ = padre[id_]
        return id_

    def unir(a: str, b: str) -> None:
        padre[raiz(a)] = raiz(b)

    for i, uno in enumerate(miembros):
        enlaces = {f["enlace"] for f in uno["fuentes"]}
        for otro in miembros[i + 1 :]:
            mismo_pais = uno["lugar"]["pais"] == otro["lugar"]["pais"]
            if mismo_pais or enlaces & {f["enlace"] for f in otro["fuentes"]}:
                unir(uno["id"], otro["id"])
    grupos: dict[str, list[Documento]] = defaultdict(list)
    for miembro in miembros:
        grupos[raiz(miembro["id"])].append(miembro)
    return list(grupos.values())


def episodios_calculados(incidentes_: list[Documento]) -> list[tuple[str, list[Documento]]]:
    """(noche, miembros) de cada episodio: incidentes activos, con punto y de noche."""
    por_noche: dict[str, list[Documento]] = defaultdict(list)
    for incidente in incidentes_:
        fecha = noche(incidente)
        if activo(incidente) and con_punto(incidente) and fecha is not None:
            por_noche[fecha].append(incidente)
    resultado = []
    for fecha, miembros in sorted(por_noche.items()):
        for grupo in _grupos_de_una_noche(sorted(miembros, key=lambda m: m["id"])):
            objetivos = {m.get("objetivo", {}).get("nombre") or m["id"] for m in grupo}
            if len(objetivos) >= MIN_OBJETIVOS_EPISODIO:
                resultado.append((fecha, grupo))
    return resultado


def agrupar_episodios(almacen: Almacen, ahora: datetime, modelos: frozenset[str]) -> int:
    """Rehace los episodios con las reglas: los que dejan de serlo se deshacen (nada se
    borra: el episodio queda marcado) y sus incidentes pierden el enlace. Devuelve cuántos
    incidentes cambian de episodio."""
    todos = almacen.incidentes()
    anteriores = {e["id"]: e for e in almacen.episodios()}
    asignado: dict[str, str] = {}
    usados: set[str] = set()
    for fecha, miembros in episodios_calculados(todos):
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
