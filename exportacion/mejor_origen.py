"""Valor a valor, el mejor origen que tiene cada dato que usa AEGIS.

La procedencia (exportacion/procedencia.py) da a cada valor el origen de las fuentes que lo
respaldan. Muchos valores llegan de la prensa aunque la base tenga otro mejor para el mismo dato:
la hora y la duración de un cierre que el tráfico aéreo ha medido, la hora que da una nota
oficial, la instalación que sale de un registro público, el número de drones que escribe una
autoridad. Aquí, después de la procedencia y sin tocar la base ni lo que se publica en la web, el
documento exportado toma el valor de mejor origen y su procedencia lo dice; el valor de la prensa
queda en `sustituye`. Nada se relaja: lo que solo dice la prensa sigue siendo prensa.

- Hora y duración: un cierre medido con tráfico aéreo con cobertura alta o media da el inicio,
  el fin y la duración (origen medido). Si no lo hay, el inicio que precisa un registro oficial
  (detalle_oficial.inicio, origen oficial). Si la fecha del incidente es la de publicación, una
  interrupción medida en su aeropuerto en las 48 horas anteriores, si es una sola, da la fecha
  y la hora (origen medido).
- Instalación: categoría, nombre y código OACI salen del nomenclátor de instalaciones, hecho con
  OpenStreetMap: origen «registro» (dato de un registro público de instalaciones). El país del
  incidente, también, cuando el lugar es la propia instalación del registro.
- Número de drones y patrón de vuelo: los que escriben las fuentes (proceso/textos_dron.py),
  con el origen de la frase: documentos oficiales, notas oficiales y encuentros de la UK Airprox
  Board (oficial), declaraciones citadas (oficial_citado) o noticias (prensa). Gana el de mayor
  rango.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

from esquema import Documento
from proceso import fechas, textos_dron
from proceso.deduccion import geo
from proceso.ubicacion import CATEGORIA_LUGAR, DIRECTORIO

MEDIDO, OFICIAL, REGISTRO = "medido", "oficial", "registro"
REGLA = "regla"
COBERTURA = frozenset({"alta", "media"})
# Anomalías que pueden ser el suceso: sin explicar o ya casadas con un incidente.
ESTADOS_ANOMALIA = frozenset({"candidata", "casada"})
VENTANA_FECHA = timedelta(hours=48)
VENTANA_CIERRE = timedelta(hours=12)
REGISTROS = ("lugares_europa.json", "instalaciones_europa.json")
NOMBRE_REGISTRO = "OpenStreetMap"
# Distancia máxima del punto del incidente a la instalación del registro (su radio, al menos).
MARGEN_KM = 5.0
INSTALACION = ("objetivo.categoria", "objetivo.nombre", "objetivo.oaci")
# Las reglas con que este módulo pone un valor (procedencia[ruta]["regla"]["nombre"]).
REGLAS = frozenset(
    {
        "cierre_medido",
        "fecha_medida",
        "hora_en_frase",
        "numero_en_frase",
        "patron_en_frase",
        "registro_oficial",
        "fecha_de_documento",
    }
)
# Días del inicio que escribe una fuente o da una autoridad (no la fecha de publicación).
DIAS_VERIFICADOS = frozenset({"explicita", "relativa", "oficial", "parte"})
ORIGENES_AUTORIDAD = frozenset({"oficial", "oficial_citado"})


@dataclass
class Contexto:
    """Lo que la base sabe de un incidente fuera de su documento."""

    documentos: list[Documento] = field(default_factory=list)
    encuentros: list[Documento] = field(default_factory=list)
    anomalias: list[Documento] = field(default_factory=list)
    # Sucesos de los documentos oficiales del país del incidente que no se han enlazado con
    # ningún incidente: (id del documento, suceso).
    sucesos_sin_incidente: list[tuple[str, Documento]] = field(default_factory=list)


@dataclass(frozen=True)
class Instalacion:
    id: str
    nombre: str
    categoria: str
    pais: str
    lat: float
    lon: float
    radio_km: float
    oaci: str | None


@cache
def registro() -> dict[str, list[Instalacion]]:
    """Instalaciones del nomenclátor por nombre (y por cada alias)."""
    por_nombre: dict[str, list[Instalacion]] = {}
    for fichero in REGISTROS:
        datos = json.loads((DIRECTORIO / fichero).read_text(encoding="utf-8"))
        for id_, lugar in datos["lugares"].items():
            categoria = CATEGORIA_LUGAR.get(lugar["tipo"])
            if lugar["tipo"] == "helipuerto":
                categoria = "aeropuerto"
            if categoria is None:
                continue
            instalacion = Instalacion(
                id_,
                lugar["nombre"],
                categoria,
                lugar["pais"],
                lugar["lat"],
                lugar["lon"],
                float(lugar["radio_km"]),
                lugar.get("oaci"),
            )
            for nombre in {lugar["nombre"], *lugar.get("alias", [])}:
                por_nombre.setdefault(nombre, []).append(instalacion)
    return por_nombre


def instalacion_de(documento: Documento) -> Instalacion | None:
    """La instalación del registro que es el objetivo del incidente: la de su nombre, con la
    misma categoría y a menos de su radio (o de 5 km) del punto del incidente."""
    objetivo = documento.get("objetivo") or {}
    punto = (documento.get("lugar") or {}).get("punto")
    nombre = objetivo.get("nombre")
    if not nombre or not punto:
        return None
    for instalacion in registro().get(nombre, []):
        if instalacion.categoria != objetivo.get("categoria"):
            continue
        if objetivo.get("oaci") and instalacion.oaci and objetivo["oaci"] != instalacion.oaci:
            continue
        distancia = geo.distancia_km(instalacion.lat, instalacion.lon, punto["lat"], punto["lon"])
        if distancia <= max(instalacion.radio_km, MARGEN_KM):
            return instalacion
    return None


def _leer(documento: Documento, ruta: str) -> Any:
    nodo: Any = documento
    for parte in ruta.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            return None
        nodo = nodo[parte]
    return nodo


def _poner(documento: Documento, ruta: str, valor: Any) -> None:
    partes = ruta.split(".")
    nodo = documento
    for parte in partes[:-1]:
        nodo = nodo.setdefault(parte, {})
    nodo[partes[-1]] = valor


def _sustituir(exportado: Documento, procedencia: Documento, ruta: str, valor: Any,
               nueva: Documento) -> None:  # fmt: skip
    """Pone el valor de mejor origen y su procedencia; lo anterior queda en `sustituye`."""
    anterior = _leer(exportado, ruta)
    previa = procedencia.get(ruta)
    if anterior is not None and anterior != valor:
        nueva = {**nueva, "sustituye": {"valor": anterior}}
        if previa and "origen" in previa:
            nueva["sustituye"]["origen"] = previa["origen"]
    _poner(exportado, ruta, valor)
    procedencia[ruta] = nueva


def _instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def _cierre(exportado: Documento) -> Documento | None:
    cierre = (exportado.get("trafico_aereo") or {}).get("cierre") or {}
    if cierre.get("resultado") != "cierre_medido":
        return None
    if (cierre.get("cobertura") or {}).get("nivel") not in COBERTURA or not cierre.get("inicio"):
        return None
    # El cierre tiene que ser del momento del incidente: a menos de 36 horas de su inicio (o,
    # con la fecha de publicación, en las 48 horas antes de ella).
    tiempo = exportado.get("tiempo", {})
    inicio = _instante(tiempo["inicio"]["valor"])
    medido = _instante(cierre["inicio"]["valor"])
    if tiempo.get("origen_inicio", {}).get("tipo") == "publicacion":
        if not inicio - VENTANA_FECHA <= medido <= inicio + VENTANA_CIERRE:
            return None
    elif abs(medido - inicio) > VENTANA_CIERRE * 3:
        return None
    return dict(cierre)


def _anomalia(exportado: Documento, anomalias: list[Documento]) -> Documento | None:
    """La única interrupción medida en el aeropuerto en las 48 horas antes de la publicación
    (si la fecha del incidente es la de publicación)."""
    tiempo = exportado.get("tiempo", {})
    if tiempo.get("origen_inicio", {}).get("tipo") != "publicacion":
        return None
    publicado = _instante(tiempo["inicio"]["valor"])
    cerca = [
        a
        for a in anomalias
        if a.get("estado") in ESTADOS_ANOMALIA
        and (a.get("cobertura") or {}).get("nivel") in COBERTURA
        and publicado - VENTANA_FECHA <= _instante(a["inicio"]) <= publicado
    ]
    return cerca[0] if len(cerca) == 1 else None


def _hora_de_autoridad(exportado: Documento, procedencia: Documento, contexto: Contexto,
                       origen_de: Any, actual: str | None) -> bool:  # fmt: skip
    """La hora local que escribe una autoridad (nota oficial o declaración citada) en el día ya
    verificado del incidente. Si el incidente ya tiene hora, la de la autoridad tiene que caer a
    menos de 6 horas de ella (si no, habla de otra cosa)."""
    tiempo = exportado.get("tiempo", {})
    if tiempo.get("origen_inicio", {}).get("tipo") not in DIAS_VERIFICADOS:
        return False
    zona = fechas.zona((exportado.get("lugar") or {}).get("pais"))
    if zona is None:
        return False
    inicio = tiempo["inicio"]
    momento = _instante(inicio["valor"])
    dia = momento.date() if inicio["precision"] == "dia" else momento.astimezone(zona).date()
    for origen, id_, frase, _ in frases(exportado, contexto, origen_de):
        if origen not in ORIGENES_AUTORIDAD or RANGO_FRASES.index(origen) >= _rango(actual):
            continue
        hora = textos_dron.hora_local(frase)
        if hora is None:
            continue
        local = datetime(dia.year, dia.month, dia.day, hora[0], hora[1], tzinfo=zona)
        nuevo = local.astimezone(UTC)
        if inicio["precision"] in {"hora", "minuto"} and abs(nuevo - momento) > timedelta(hours=6):
            continue
        valor = {"precision": "minuto", "valor": nuevo.strftime("%Y-%m-%dT%H:%MZ")}
        _sustituir(
            exportado,
            procedencia,
            "tiempo.inicio",
            valor,
            {
                "origen": origen,
                "metodo": REGLA,
                "fuentes": [id_],
                "regla": {"nombre": "hora_en_frase", "version": "1.0.0"},
            },
        )
        return True
    return False


VENTANA_DOCUMENTO = timedelta(days=10)


def _fecha_de_documento(exportado: Documento, procedencia: Documento, contexto: Contexto) -> bool:
    """Con solo la fecha de publicación: el único suceso de un documento oficial del mismo país,
    sin incidente enlazado, en el mismo sitio (a menos del radio de los dos más 5 km) y en los 10
    días antes de la publicación da la fecha del suceso (origen oficial)."""
    tiempo = exportado.get("tiempo", {})
    punto = (exportado.get("lugar") or {}).get("punto")
    if tiempo.get("origen_inicio", {}).get("tipo") != "publicacion" or not punto:
        return False
    publicado = _instante(tiempo["inicio"]["valor"])
    radio = float((exportado.get("lugar") or {}).get("radio_km") or 0.0)
    elegidos = []
    for documento_id, suceso in contexto.sucesos_sin_incidente:
        otro = suceso.get("punto")
        inicio = ((suceso.get("datos") or {}).get("inicio") or {}).get("valor")
        if not otro or not inicio:
            continue
        cerca = geo.distancia_km(punto["lat"], punto["lon"], otro["lat"], otro["lon"]) <= (
            radio + float(otro.get("radio_km") or 0.0) + MARGEN_KM
        )
        texto = str(inicio) + ("Z" if "T" in str(inicio) else "T00:00Z")
        momento = _instante(texto)
        if cerca and publicado - VENTANA_DOCUMENTO <= momento <= publicado + timedelta(hours=12):
            elegidos.append((documento_id, suceso, texto))
    if len(elegidos) != 1:
        return False
    documento_id, suceso, texto = elegidos[0]
    datos = suceso.get("datos") or {}
    precision = (datos.get("inicio_precision") or {}).get("valor") or (
        "minuto" if "T" in texto[:11] and not texto.endswith("T00:00Z") else "dia"
    )
    valor = {"valor": texto, "precision": precision if "T00:00Z" not in texto else "dia"}
    _sustituir(
        exportado,
        procedencia,
        "tiempo.inicio",
        valor,
        {
            "origen": OFICIAL,
            "metodo": REGLA,
            "fuentes": [documento_id],
            "regla": {"nombre": "fecha_de_documento", "version": "1.0.0"},
        },
    )
    _origen_inicio(
        exportado,
        procedencia,
        "oficial",
        "fecha del suceso en un documento oficial del mismo sitio",
        [documento_id],
    )
    return True


def _rango(origen: str | None) -> int:
    return RANGO_FRASES.index(origen) if origen in RANGO_FRASES else len(RANGO_FRASES)


def _tiempo(exportado: Documento, procedencia: Documento, contexto: Contexto,
            origen_de: Any) -> None:  # fmt: skip
    cierre = _cierre(exportado)
    fuente_trafico = (procedencia.get("trafico_aereo") or {}).get("fuentes", [])
    if cierre is not None:
        base = {
            "origen": MEDIDO,
            "metodo": REGLA,
            "fuentes": list(fuente_trafico),
            "regla": {"nombre": "cierre_medido", "version": "1.0.0"},
        }
        _sustituir(exportado, procedencia, "tiempo.inicio", cierre["inicio"], dict(base))
        if cierre.get("fin"):
            _sustituir(exportado, procedencia, "tiempo.fin", cierre["fin"], dict(base))
        if cierre.get("duracion_min") is not None:
            _sustituir(
                exportado,
                procedencia,
                "tiempo.duracion_min",
                int(cierre["duracion_min"]),
                dict(base),
            )
        _origen_inicio(
            exportado,
            procedencia,
            "medido",
            f"inicio del cierre medido con tráfico aéreo en {cierre.get('aeropuerto')}",
            fuente_trafico,
        )
        return
    oficial = (exportado.get("detalle_oficial") or {}).get("inicio")
    origen_oficial = procedencia.get("detalle_oficial.inicio", {})
    actual = procedencia.get("tiempo.inicio", {}).get("origen")
    if oficial and origen_oficial.get("origen") == OFICIAL and actual not in {MEDIDO, OFICIAL}:
        nueva = {
            "origen": OFICIAL,
            "metodo": origen_oficial.get("metodo", REGLA),
            "fuentes": list(origen_oficial.get("fuentes", [])),
            "regla": {"nombre": "registro_oficial", "version": "1.0.0"},
        }
        _sustituir(exportado, procedencia, "tiempo.inicio", oficial, nueva)
        _origen_inicio(
            exportado, procedencia, "oficial", "inicio del registro oficial", nueva["fuentes"]
        )
        return
    if _hora_de_autoridad(exportado, procedencia, contexto, origen_de, actual):
        return
    if _fecha_de_documento(exportado, procedencia, contexto):
        return
    anomalia = _anomalia(exportado, contexto.anomalias)
    if anomalia is not None:
        id_ = f"anomalia:{anomalia['oaci']}/{anomalia['inicio']}"
        base = {
            "origen": MEDIDO,
            "metodo": REGLA,
            "fuentes": [id_],
            "regla": {"nombre": "fecha_medida", "version": "1.0.0"},
        }
        _sustituir(
            exportado,
            procedencia,
            "tiempo.inicio",
            {"precision": "minuto", "valor": anomalia["inicio"]},
            dict(base),
        )
        if anomalia.get("fin"):
            _sustituir(
                exportado,
                procedencia,
                "tiempo.fin",
                {"precision": "minuto", "valor": anomalia["fin"]},
                dict(base),
            )
        if anomalia.get("duracion_min") is not None:
            _sustituir(
                exportado,
                procedencia,
                "tiempo.duracion_min",
                int(anomalia["duracion_min"]),
                dict(base),
            )
        _origen_inicio(
            exportado,
            procedencia,
            "medido",
            f"única interrupción medida en {anomalia['oaci']} en las 48 h antes de la publicación",
            [id_],
        )


def _origen_inicio(exportado: Documento, procedencia: Documento, tipo: str, motivo: str,
                   fuentes: list[str]) -> None:  # fmt: skip
    nuevo: Documento = {"tipo": tipo, "motivo": motivo[:300]}
    if fuentes:
        nuevo["fuente_id"] = fuentes[0]
    previo = exportado.get("tiempo", {}).get("origen_inicio")
    if previo and previo.get("tipo") != tipo:
        nuevo["corregido"] = True
    _sustituir(
        exportado,
        procedencia,
        "tiempo.origen_inicio",
        nuevo,
        {
            "origen": tipo if tipo in {MEDIDO, OFICIAL} else OFICIAL,
            "metodo": REGLA,
            "fuentes": list(fuentes),
            "regla": dict(procedencia["tiempo.inicio"]["regla"]),
        },
    )


def _instalacion(exportado: Documento, procedencia: Documento) -> None:
    instalacion = instalacion_de(exportado)
    if instalacion is None:
        return
    nueva = {
        "origen": REGISTRO,
        "metodo": REGLA,
        "fuentes": [],
        "registro": {"nombre": NOMBRE_REGISTRO, "id": instalacion.id},
    }
    registro_ = {"nombre": NOMBRE_REGISTRO, "id": instalacion.id}
    for ruta in INSTALACION:
        if _leer(exportado, ruta) is not None:
            procedencia[ruta] = {**nueva, "registro": dict(registro_)}
    lugar = exportado.get("lugar") or {}
    if lugar.get("nivel") == "instalacion" and lugar.get("pais") == instalacion.pais:
        actual = procedencia.get("lugar.pais", {}).get("origen")
        if actual not in {MEDIDO, OFICIAL}:
            procedencia["lugar.pais"] = {**nueva, "registro": dict(registro_)}


# Rango de los orígenes de las frases (el de exportacion.procedencia, con registro).
RANGO_FRASES = ("medido", "oficial", "oficial_citado", "parte", "prensa")


def frases(exportado: Documento, contexto: Contexto,
           origen_de: Any) -> list[tuple[str, str, str, str | None]]:  # fmt: skip
    """(origen, id de la fuente, frase, idioma) de todo lo que escribe sobre el incidente."""
    lista: list[tuple[str, str, str, str | None]] = []
    for fuente in exportado.get("fuentes", []):
        if fuente.get("frase_origen"):
            lista.append(
                (origen_de(fuente), fuente["id"], fuente["frase_origen"], fuente.get("idioma"))
            )
    for documento in contexto.documentos:
        for suceso in documento.get("sucesos", []):
            if suceso.get("incidente") != exportado["id"]:
                continue
            for dato in (suceso.get("datos") or {}).values():
                if isinstance(dato, dict) and dato.get("frase"):
                    lista.append((OFICIAL, documento["id"], dato["frase"], documento.get("idioma")))
    for encuentro in contexto.encuentros:
        descripcion = (encuentro.get("objeto") or {}).get("descripcion")
        if descripcion:
            lista.append((OFICIAL, encuentro["id"], descripcion, "en"))
    return sorted(
        lista, key=lambda x: (RANGO_FRASES.index(x[0]) if x[0] in RANGO_FRASES else 9, x[1])
    )


def _drones(exportado: Documento, procedencia: Documento, contexto: Contexto,
            origen_de: Any) -> None:  # fmt: skip
    lista = frases(exportado, contexto, origen_de)
    actual = procedencia.get("drones.numero", {})
    valor_actual = _leer(exportado, "drones.numero")
    # Número oficial de un documento oficial enlazado (lo leyó su extractor con frase).
    oficiales: list[tuple[str, str, tuple[int, int]]] = []
    for documento in contexto.documentos:
        for suceso in documento.get("sucesos", []):
            dato = (suceso.get("datos") or {}).get("drones")
            if suceso.get("incidente") == exportado["id"] and isinstance(dato, dict):
                valor = dato.get("valor")
                if isinstance(valor, dict) and valor.get("min") is not None:
                    maximo = valor.get("max")
                    minimo = int(valor["min"])
                    oficiales.append(
                        (OFICIAL, documento["id"], (minimo, int(maximo) if maximo else minimo))
                    )
    leidos = oficiales + [
        (origen, id_, n)
        for origen, id_, frase, idioma in lista
        if (n := textos_dron.numero_drones(frase, idioma)) is not None
    ]
    if leidos:
        origen, id_, (minimo, maximo) = min(
            leidos, key=lambda x: RANGO_FRASES.index(x[0]) if x[0] in RANGO_FRASES else 9
        )
        rango_actual = (
            RANGO_FRASES.index(actual["origen"]) if actual.get("origen") in RANGO_FRASES else 9
        )
        mejor = RANGO_FRASES.index(origen) if origen in RANGO_FRASES else 9
        if mejor < rango_actual or actual.get("desconocido") or valor_actual == "desconocido":
            _sustituir(
                exportado,
                procedencia,
                "drones.numero",
                {"min": minimo, "max": maximo},
                {
                    "origen": origen,
                    "metodo": REGLA,
                    "fuentes": [id_],
                    "regla": {"nombre": "numero_en_frase", "version": "1.0.0"},
                },
            )
    if _leer(exportado, "drones.patron") is None:
        for origen, id_, frase, _ in lista:
            encontrado = textos_dron.patron(frase)
            if encontrado is not None:
                _sustituir(
                    exportado,
                    procedencia,
                    "drones.patron",
                    encontrado,
                    {
                        "origen": origen,
                        "metodo": REGLA,
                        "fuentes": [id_],
                        "regla": {"nombre": "patron_en_frase", "version": "1.0.0"},
                    },
                )
                break


def aplicar(exportado: Documento, procedencia: Documento, contexto: Contexto,
            origen_de: Any) -> None:  # fmt: skip
    """Cambia en su sitio el documento exportado y su procedencia."""
    if (exportado.get("control") or {}).get("version_extractor", "").startswith("incursion/"):
        return
    _tiempo(exportado, procedencia, contexto, origen_de)
    _instalacion(exportado, procedencia)
    _drones(exportado, procedencia, contexto, origen_de)


def momento(documento: Documento, contexto: Contexto, origen_de: Any) -> Documento:
    """El tiempo del incidente con el mejor origen que hay en la base, para quien no pasa por la
    exportación (el motor de deducción): {"tiempo": ..., "origen": ..., "regla": ...}. Las
    reglas son las de la exportación; lo que no mejora queda como está, con origen None."""
    copia: Documento = json.loads(
        json.dumps(
            {
                k: documento[k]
                for k in ("id", "tiempo", "lugar", "fuentes", "trafico_aereo", "detalle_oficial")
                if k in documento
            }
        )
    )
    procedencia: Documento = {}
    if (copia.get("detalle_oficial") or {}).get("inicio"):
        procedencia["detalle_oficial.inicio"] = {"origen": OFICIAL, "metodo": REGLA, "fuentes": []}
    if "trafico_aereo" in copia:
        fuente = (copia["trafico_aereo"] or {}).get("fuente_id")
        procedencia["trafico_aereo"] = {"origen": MEDIDO, "metodo": REGLA,
                                        "fuentes": [fuente] if fuente else []}  # fmt: skip
    _tiempo(copia, procedencia, contexto, origen_de)
    elegido = procedencia.get("tiempo.inicio")
    return {
        "tiempo": copia.get("tiempo", {}),
        "origen": elegido["origen"] if elegido else None,
        "regla": (elegido or {}).get("regla", {}).get("nombre"),
    }
