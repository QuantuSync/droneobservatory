"""Control de calidad de las fichas: la parte que no llama a nada (docs/control_fichas.md).

- Pares candidatos a ser el mismo suceso: del mismo país, con los inicios a 48 horas como mucho,
  a menos de 60 km más los radios si los dos tienen punto (sin punto, solo el país: el lugar
  aproximado cuenta) y del mismo tipo de sitio. Nunca los que una revisión separó, ni dos cierres
  del mismo sitio en noches distintas.
- La verificación de una ficha: lo que dicen sus fuentes de cada dato, con la frase literal. Una
  frase que no está en el texto de su fuente no cuenta. Con lo que queda se corrige la ficha:
  la presencia no se queda confirmada si una fuente cuenta que no se encontró el dron; el número
  de drones solo si alguna fuente lo da; el cierre y su duración, solo con frase; la hora, solo
  con frase; el lugar sin punto gana el sitio que nombra la frase. Nunca sube un estado ni
  confirma una presencia: eso lo deciden las reglas de siempre con las fuentes oficiales.
- El estado: confirmado o atribuido solo con un paso de una fuente oficial.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from esquema import Documento
from proceso import declaraciones, incidentes
from proceso.estados import RETIRADAS, Estado
from proceso.fronteras import dentro_del_pais
from proceso.noticias import (
    Nomenclator,
    distancia_km,
    localidades_declinadas,
    lugares_en,
    normalizar,
)
from proceso.presencia import (
    documento_oficial_decide,
    presencias_revisadas,
    pruebas_fisicas_confirmadas,
)
from proceso.ubicacion import (
    CATEGORIA_LUGAR,
    DECIMALES,
    Objetivo,
    localidad_pequena,
)
from proceso.validaciones import errores_presencia

VENTANA_PAR = timedelta(hours=48)
MARGEN_PAR_KM = 60.0
MARGEN_MISMO_SITIO_KM = 10.0
CATEGORIAS_INSTALACION = frozenset(CATEGORIA_LUGAR.values())
# Una presencia que no se queda confirmada, con la fuente que lo cuenta.
NIEGAN = frozenset({"no_hallado", "desmentido"})
_RANGO = re.compile(r"^\s*(\d{1,3})\s*(?:[-–]\s*(\d{1,3}))?\s*$")
_HORA = re.compile(r"^\s*([01]?\d|2[0-3]):([0-5]\d)\s*$")
_DIA = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*$")
MAX_DRONES = 100
MAX_MINUTOS = 7 * 24 * 60
# Un día que da la fuente, si la ficha solo tenía la fecha de publicación: como mucho una semana
# antes de la primera noticia.
DIAS_ANTES_MAX = 7
MOTIVO = "control de fichas"


def clave_par(a: str, b: str) -> str:
    uno, otro = sorted((a, b))
    return f"par:{uno}|{otro}"


def clave_verificacion(id_: str) -> str:
    return f"verificacion:{id_}"


def huella_fuentes(incidente: Documento) -> str:
    """Las fuentes del incidente: cambia cuando llega una nueva."""
    ids = sorted(f["id"] for f in incidente.get("fuentes", []))
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:16]


def instante(incidente: Documento) -> datetime:
    return incidentes._leer_instante(incidente["tiempo"]["inicio"])


def primera_noticia(incidente: Documento) -> datetime:
    return datetime.strptime(incidentes.primera_noticia(incidente)[:16], "%Y-%m-%dT%H:%M").replace(
        tzinfo=instante(incidente).tzinfo
    )


def mas_antiguo(a: Documento, b: Documento) -> tuple[Documento, Documento]:
    """(el que se conserva, el que se une): el de alta más antigua; a la par, el de número menor."""
    uno, otro = sorted((a, b), key=lambda d: (d["control"]["alta"]["valor"], d["id"]))
    return uno, otro


def _cerca_en_el_tiempo(a: Documento, b: Documento) -> bool:
    if abs(instante(a) - instante(b)) <= VENTANA_PAR:
        return True
    # Con la fecha de publicación, también la primera noticia.
    return abs(primera_noticia(a) - primera_noticia(b)) <= VENTANA_PAR and (
        incidentes.APROXIMADA
        in {a["tiempo"]["inicio"]["precision"], b["tiempo"]["inicio"]["precision"]}
    )


def _punto(d: Documento) -> tuple[float, float] | None:
    punto = d["lugar"].get("punto")
    return (float(punto["lat"]), float(punto["lon"])) if punto else None


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    from proceso.noticias import Lugar

    uno = Lugar("", "", "", a[0], a[1], 0.0, "", (), ())
    otro = Lugar("", "", "", b[0], b[1], 0.0, "", (), ())
    return distancia_km(uno, otro)


def _cerca_en_el_espacio(a: Documento, b: Documento) -> bool:
    if a["lugar"]["pais"] != b["lugar"]["pais"]:
        return False
    pa, pb = _punto(a), _punto(b)
    if pa is None or pb is None:
        return True
    radios = float(a["lugar"].get("radio_km", 0)) + float(b["lugar"].get("radio_km", 0))
    return _km(pa, pb) <= radios + MARGEN_PAR_KM


def _mismo_tipo_de_sitio(a: Documento, b: Documento) -> bool:
    """Dos sitios de distinto tipo (un aeropuerto y una base) no son el mismo suceso, salvo que
    estén juntos (aeropuertos de uso mixto)."""
    ca = (a.get("objetivo") or {}).get("categoria")
    cb = (b.get("objetivo") or {}).get("categoria")
    if ca not in CATEGORIAS_INSTALACION or cb not in CATEGORIAS_INSTALACION or ca == cb:
        return True
    pa, pb = _punto(a), _punto(b)
    return pa is not None and pb is not None and _km(pa, pb) <= MARGEN_MISMO_SITIO_KM


def separados(a: Documento, b: Documento) -> bool:
    """Una revisión los separó (sucesos relacionados) o son cierres de noches distintas."""
    relacionados = {r.get("id") for r in a.get("relacionados", [])} | {
        r.get("id") for r in b.get("relacionados", [])
    }
    return (
        a["id"] in relacionados
        or b["id"] in relacionados
        or incidentes.cierres_de_noches_distintas(a, b)
    )


def candidatos(a: Documento, b: Documento) -> bool:
    """Pueden ser el mismo suceso y lo tiene que decidir el control."""
    return (
        a["id"] != b["id"]
        and _cerca_en_el_tiempo(a, b)
        and _cerca_en_el_espacio(a, b)
        and _mismo_tipo_de_sitio(a, b)
        and not separados(a, b)
    )


def pares_candidatos(activos: list[Documento], foco: set[str]) -> list[tuple[Documento, Documento]]:
    """Los pares de candidatos con al menos uno del foco, primero los más cercanos en el
    tiempo."""
    pares: dict[str, tuple[Documento, Documento]] = {}
    por_pais: dict[str, list[Documento]] = {}
    for d in activos:
        por_pais.setdefault(d["lugar"]["pais"], []).append(d)
    for d in activos:
        if d["id"] not in foco:
            continue
        for otro in por_pais.get(d["lugar"]["pais"], []):
            if candidatos(d, otro):
                pares.setdefault(clave_par(d["id"], otro["id"]), (d, otro))
    return sorted(pares.values(), key=lambda p: abs(instante(p[0]) - instante(p[1])))


# --- Lo que ve el control de una ficha ----------------------------------------------------


def _rango_texto(valor: Any) -> str:
    if isinstance(valor, dict) and "min" in valor:
        return (
            str(valor["min"]) if valor["min"] == valor["max"] else f"{valor['min']}-{valor['max']}"
        )
    return "sin dato"


def vista(incidente: Documento) -> dict[str, Any]:
    """Los datos de la ficha que se comprueban, como se leen en la web."""
    consecuencias = incidente.get("consecuencias") or {}
    cierre = consecuencias.get("cierre") or {}
    lugar = incidente["lugar"]
    objetivo = incidente.get("objetivo") or {}
    sitio = objetivo.get("nombre") or lugar.get("localidad") or lugar.get("suceso") or ""
    inicio = incidente["tiempo"]["inicio"]
    return {
        "titular": (incidente.get("titulo") or {}).get("es", ""),
        "tipo": incidente.get("tipo"),
        "presencia_dron": incidente.get("presencia_dron"),
        "drones": _rango_texto((incidente.get("drones") or {}).get("numero")),
        "cierre": cierre.get("valor", "desconocido"),
        "duracion_min": _rango_texto(cierre.get("minutos")),
        "inicio": f"{inicio['valor']} ({inicio['precision']})",
        "lugar": f"{sitio} ({lugar.get('nivel', '?')}), {lugar['pais']}".strip(),
    }


# --- La verificación ----------------------------------------------------------------------


def _normal(texto: str) -> str:
    return " ".join(texto.lower().split())


def frase_valida(frase: str, texto: str) -> bool:
    """La frase está, literal (sin mayúsculas ni espacios de más), en el texto de su fuente."""
    frase = _normal(frase).strip(" «»\"'.")
    return len(frase) >= 3 and frase in _normal(texto)


@dataclass
class Verificada:
    """Lo comprobado de la respuesta: cada dato con su valor y su fuente (el identificador de la
    fuente del incidente), o None si ninguna fuente válida lo dice."""

    datos: dict[str, tuple[Any, str, str]] = field(default_factory=dict)

    def valor(self, campo: str) -> Any:
        dato = self.datos.get(campo)
        return dato[0] if dato else None


def comprobar(respuesta: dict[str, Any], fuentes: list[tuple[str, str]]) -> Verificada:
    """Los datos de la respuesta cuya frase está en el texto de su fuente. `fuentes`: (id de la
    fuente del incidente, texto de la fuente: titular, primeras frases y frases guardadas), en
    el orden en que se mandaron."""
    resultado = Verificada()
    for campo, dato in respuesta.items():
        if not isinstance(dato, dict):
            continue
        numero = dato.get("fuente")
        frase = str(dato.get("frase") or "")
        valor = dato.get("valor") if campo != "lugar" else {
            "nombre": str(dato.get("nombre") or ""), "nivel": dato.get("nivel")}  # fmt: skip
        if not isinstance(numero, int) or not 1 <= numero <= len(fuentes) or not frase:
            continue
        id_, texto = fuentes[numero - 1]
        if not frase_valida(frase, texto):
            continue
        valor = _interpretar(campo, valor, frase)
        if valor is not None:
            resultado.datos[campo] = (valor, id_, " ".join(frase.split()))
    return resultado


def _interpretar(campo: str, valor: Any, frase: str) -> Any:
    if campo == "presencia":
        return valor if valor in {"confirmada", "posible", "no_hallado", "desmentido"} else None
    if campo == "cierre":
        return valor if valor in {"si", "no"} else None
    if campo in {"drones", "duracion_min"}:
        m = _RANGO.match(str(valor or ""))
        if m is None:
            return None
        minimo, maximo = int(m[1]), int(m[2] or m[1])
        tope = MAX_DRONES if campo == "drones" else MAX_MINUTOS
        if not 0 < minimo <= maximo <= tope:
            return None
        return {"min": minimo, "max": maximo}
    if campo == "dia":
        m = _DIA.match(str(valor or ""))
        return m[1] if m else None
    if campo == "hora":
        m = _HORA.match(str(valor or ""))
        return f"{int(m[1]):02d}:{m[2]}" if m else None
    if campo == "lugar":
        nombre = valor["nombre"].strip()
        if valor["nivel"] not in {"instalacion", "localidad"} or len(nombre) < 3:
            return None
        # El nombre tiene que estar en la frase (en cualquier forma: «Nürnberg», «Nürnberger»).
        raiz = normalizar(nombre)[:5]
        return valor if raiz and raiz in normalizar(frase) else None
    return None


@dataclass
class Correccion:
    incidente: Documento
    cambios: list[str] = field(default_factory=list)
    # Lo que se cita en «Qué dice la fuente»: campo público -> (fuente, frase).
    respaldos: dict[str, tuple[str, str]] = field(default_factory=dict)
    dudas: list[str] = field(default_factory=list)


def _sin_afirmaciones(documento: Documento, campo: str) -> list[Documento]:
    return [a for a in documento.get("afirmaciones", []) if a.get("campo") != campo]


def _afirmacion(campo: str, valor: Any, fuente_id: str) -> Documento:
    return {"campo": campo, "valor": valor, "fuente_id": fuente_id,
            "confianza_extraccion": declaraciones.CONFIANZA_REGLA}  # fmt: skip


def _presencia(c: Correccion, v: Verificada) -> None:
    d = c.incidente
    dato = v.datos.get("presencia")
    if dato is None:
        return
    valor, fuente, frase = dato
    c.respaldos["presencia_dron"] = (fuente, frase)
    if (
        valor in NIEGAN
        and d.get("presencia_dron") == "confirmada"
        and d["id"] not in presencias_revisadas()
        and not documento_oficial_decide(d)
        and not pruebas_fisicas_confirmadas(d)
    ):
        afirmaciones = [
            a for a in d.get("afirmaciones", [])
            if not (a["campo"] == "presencia_dron" and a["valor"] == "confirmada")
        ]  # fmt: skip
        afirmaciones.append(_afirmacion("presencia_dron", "no_confirmada", fuente))
        nuevo = {**d, "presencia_dron": "no_confirmada", "afirmaciones": afirmaciones}
        if errores_presencia(nuevo):
            # La autoridad que lo confirmó atribuye el suceso a un dron: manda.
            c.dudas.append(f"una fuente dice «{frase}», pero la autoridad lo atribuye a un dron")
            return
        c.incidente = nuevo
        c.cambios.append(f"presencia no confirmada: «{frase}»")


def _drones(c: Correccion, v: Verificada, conservar: frozenset[str]) -> None:
    d = c.incidente
    actual = (d.get("drones") or {}).get("numero", "desconocido")
    dato = v.datos.get("drones")
    if dato is not None:
        valor, fuente, frase = dato
        c.respaldos["drones.numero"] = (fuente, frase)
        if actual != valor:
            afirmaciones = [*_sin_afirmaciones(d, "drones"), _afirmacion("drones", valor, fuente)]
            c.incidente = {**d, "drones": {**(d.get("drones") or {}), "numero": valor},
                           "afirmaciones": afirmaciones}  # fmt: skip
            c.cambios.append(f"drones {_rango_texto(actual)} -> {_rango_texto(valor)}: «{frase}»")
        return
    if isinstance(actual, dict) and "drones" not in conservar:
        c.incidente = {**d, "drones": {**(d.get("drones") or {}), "numero": "desconocido"},
                       "afirmaciones": _sin_afirmaciones(d, "drones")}  # fmt: skip
        c.cambios.append(f"drones {_rango_texto(actual)} -> sin dato: ninguna fuente da el número")


def _cierre(
    c: Correccion, v: Verificada, cierre_por_regla: bool, conservar: frozenset[str]
) -> None:
    d = c.incidente
    consecuencias = dict(d.get("consecuencias") or {})
    cierre = dict(consecuencias.get("cierre") or {"valor": "desconocido"})
    dato = v.datos.get("cierre")
    if dato is not None:
        valor, fuente, frase = dato
        c.respaldos["consecuencias.cierre.valor"] = (fuente, frase)
        if valor == "si" and cierre.get("valor") != "si":
            cierre["valor"] = "si"
            c.cambios.append(f"cierre: «{frase}»")
    elif cierre.get("valor") == "si" and not cierre_por_regla and "cierre" not in conservar:
        cierre = {"valor": "desconocido"}
        c.cambios.append("cierre -> sin dato: ninguna fuente lo cuenta")
    minutos = v.datos.get("duracion_min")
    if minutos is not None and cierre.get("valor") == "si":
        valor, fuente, frase = minutos
        c.respaldos["consecuencias.cierre.minutos"] = (fuente, frase)
        if cierre.get("minutos") != valor:
            cierre["minutos"] = valor
            c.cambios.append(f"duración del cierre {_rango_texto(valor)} min: «{frase}»")
    elif isinstance(cierre.get("minutos"), dict) and "duracion_min" not in conservar:
        cierre.pop("minutos")
        c.cambios.append("duración del cierre -> sin dato: ninguna fuente la da")
    if cierre != (consecuencias.get("cierre") or {"valor": "desconocido"}):
        consecuencias["cierre"] = cierre
        afirmaciones = d.get("afirmaciones", [])
        if cierre.get("valor") != "si":
            afirmaciones = [
                a for a in afirmaciones if a.get("campo") not in {"cierre", "cierre_minutos"}
            ]
        c.incidente = {**d, "consecuencias": consecuencias, "afirmaciones": afirmaciones}


def _hora(c: Correccion, v: Verificada, primera: datetime, conservar: frozenset[str]) -> None:
    d = c.incidente
    tiempo = d["tiempo"]
    inicio = tiempo["inicio"]
    origen = (tiempo.get("origen_inicio") or {}).get("tipo")
    hora, dia = v.datos.get("hora"), v.datos.get("dia")
    if dia is not None:
        c.respaldos["tiempo.inicio"] = (dia[1], dia[2])
    elif hora is not None:
        c.respaldos["tiempo.inicio"] = (hora[1], hora[2])
    if origen in {"oficial", "parte", "medido"} or "inicio" in conservar:
        return
    if inicio["precision"] in incidentes.PRECISIONES_HORA and hora is None:
        valor = inicio["valor"][:10] + "T00:00Z"
        nuevo = {**tiempo, "inicio": {"valor": valor, "precision": "dia"}}
        nuevo.pop("fin", None)
        nuevo.pop("duracion_min", None)
        c.incidente = {**d, "tiempo": nuevo}
        c.cambios.append("hora -> solo el día: ninguna fuente da la hora")
        return
    if inicio["precision"] == incidentes.APROXIMADA and dia is not None:
        escrito = datetime.strptime(dia[0], "%Y-%m-%d").date()
        lectura = _dia_en_la_frase(d, dia[1], dia[2], escrito)
        if lectura is None:
            # La frase no escribe ese día ni lo da respecto a la publicación («el martes»,
            # «anoche»): el día no se toma de ella.
            return
        if primera.date() - timedelta(days=DIAS_ANTES_MAX) <= escrito <= primera.date():
            nuevo = {**tiempo, "inicio": {"valor": f"{dia[0]}T00:00Z", "precision": "dia"},
                     "origen_inicio": {"tipo": lectura, "fuente_id": dia[1],
                                       "motivo": f"{MOTIVO}: «{dia[2]}»"[:300]}}  # fmt: skip
            nuevo.pop("fin", None)
            nuevo.pop("duracion_min", None)
            c.incidente = {**d, "tiempo": nuevo}
            c.cambios.append(f"día {dia[0]}: «{dia[2]}»")
        else:
            c.dudas.append(f"día {dia[0]} lejos de la primera noticia")


def _dia_en_la_frase(incidente: Documento, fuente_id: str, frase: str, dia: Any) -> str | None:
    """«explicita» o «relativa» si la frase de esa fuente escribe ese día o lo da respecto a la
    publicación de su noticia (proceso/fechas.leer, con su víspera para la noche); None si no."""
    from datetime import UTC

    from proceso import fechas

    fuente = next((f for f in incidente.get("fuentes", []) if f["id"] == fuente_id), None)
    if fuente is None:
        return None
    publicacion = incidentes._leer_instante(fuente["fecha"])
    zona = fechas.zona(str(incidente["lugar"].get("pais") or "")) or UTC
    for lectura in fechas.leer(frase, publicacion, zona, fuente.get("idioma")):
        if dia == lectura.dia or dia in lectura.admitidos:
            return str(lectura.origen)
    return None


def lugar_de_nombre(nombre: str, nivel: str, pais: str, region: str | None,
                    nom: Nomenclator) -> tuple[Objetivo, str] | None:  # fmt: skip
    """El sitio del país con ese nombre: una sola instalación o una sola localidad."""
    if nivel == "instalacion":
        ids = [i for i in lugares_en(nombre, nom) if nom.lugares[i].pais == pais
               and nom.lugares[i].tipo in CATEGORIA_LUGAR]  # fmt: skip
        if len(ids) == 1:
            return Objetivo.de_lugar(nom.lugares[ids[0]]), "instalacion"
    ids = [i for i in localidades_declinadas(nombre, nom) if nom.lugares[i].pais == pais]
    if len(ids) == 1:
        return Objetivo.de_lugar(nom.lugares[ids[0]]), "localidad"
    if not ids and (pequena := localidad_pequena(nombre, pais, region)):
        return pequena, "localidad"
    return None


def _lugar(c: Correccion, v: Verificada, nom: Nomenclator | None) -> None:
    d = c.incidente
    dato = v.datos.get("lugar")
    if dato is None:
        return
    valor, fuente, frase = dato
    c.respaldos["lugar"] = (fuente, frase)
    if nom is None or "punto" in d["lugar"]:
        return
    pais = d["lugar"]["pais"]
    hallado = lugar_de_nombre(valor["nombre"], valor["nivel"], pais, d["lugar"].get("region"), nom)
    if hallado is None:
        c.dudas.append(f"lugar «{valor['nombre']}» sin situar")
        return
    sitio, nivel = hallado
    if not dentro_del_pais(pais, sitio.lat, sitio.lon):
        c.dudas.append(f"lugar «{valor['nombre']}» fuera de {pais}")
        return
    lugar = {k: v2 for k, v2 in d["lugar"].items() if k in {"region", "historial", "otros_lugares"}}
    lugar.update(pais=pais, nivel=nivel, radio_km=sitio.radio_km, geocodificacion="frase_origen",
                 punto={"lat": round(sitio.lat, DECIMALES), "lon": round(sitio.lon, DECIMALES)},
                 suceso=valor["nombre"])  # fmt: skip
    if nivel == "localidad":
        lugar["localidad"] = sitio.nombre
    resultado = {**d, "lugar": lugar}
    if nivel == "instalacion":
        objetivo: Documento = {"categoria": sitio.categoria, "nombre": sitio.nombre}
        if sitio.oaci and sitio.categoria == "aeropuerto":
            objetivo["oaci"] = sitio.oaci
        resultado["objetivo"] = objetivo
    c.incidente = resultado
    c.cambios.append(f"lugar {sitio.nombre} ({nivel}): «{frase}»")


def aplicar(
    incidente: Documento,
    verificada: Verificada,
    cierre_por_regla: bool,
    nom: Nomenclator | None,
    conservar: frozenset[str] = frozenset(),
) -> Correccion:
    """La ficha corregida con lo que dicen sus fuentes. Después hay que aplicar las reglas de
    tipo y de presencia (proceso/incidentes.aplicar_reglas) y el titular."""
    c = Correccion(incidente)
    primera = primera_noticia(incidente)
    _presencia(c, verificada)
    _drones(c, verificada, conservar)
    _cierre(c, verificada, cierre_por_regla, conservar)
    _hora(c, verificada, primera, conservar)
    _lugar(c, verificada, nom)
    return c


# --- El estado ----------------------------------------------------------------------------


def oficial(fuente: Documento) -> bool:
    """Fuente oficial: una autoridad, leída directamente o citada por un medio."""
    return bool(fuente.get("es_autoridad")) or fuente.get("fiabilidad") in {"A", "B"}


def estado_sin_respaldo(incidente: Documento) -> str | None:
    """El paso de estado más alto sin una fuente oficial que lo dé, o None si está bien."""
    actual = Estado(incidente["estado"]["actual"])
    if actual not in {Estado.CONFIRMADO, Estado.ATRIBUIDO}:
        return None
    fuentes = {f["id"]: f for f in incidente.get("fuentes", [])}
    for paso in incidente["estado"]["historial"]:
        if paso["estado"] == actual.value:
            fuente = fuentes.get(paso.get("fuente_id", ""))
            if fuente is not None and oficial(fuente):
                return None
    return actual.value


def bajar_estado(incidente: Documento, instante_: Documento) -> Documento | None:
    """El incidente con el estado sin respaldo vuelto a notificado (una retirada permitida)."""
    sin = estado_sin_respaldo(incidente)
    if sin is None or (Estado(sin), Estado.NOTIFICADO) not in RETIRADAS:
        return None
    primera = incidente["estado"]["historial"][0]
    paso = {
        "estado": Estado.NOTIFICADO.value,
        "fecha": instante_,
        "fuente_id": primera["fuente_id"],
        "motivo": {
            "es": f"Ninguna fuente oficial da el estado «{sin}» (control de fichas).",
            "en": f"No official source gives the status «{sin}» (record check).",
        },
    }
    historial = [*incidente["estado"]["historial"], paso]
    return {**incidente, "estado": {"actual": Estado.NOTIFICADO.value, "historial": historial}}


def resumen_json(datos: Any) -> str:
    return json.dumps(datos, ensure_ascii=False, sort_keys=True)
