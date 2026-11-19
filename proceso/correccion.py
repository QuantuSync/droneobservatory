"""La comprobación de coherencia de la puerta: lo que dice una ficha y no sostienen sus frases.

Desde el 14 de noviembre de 2026 la puerta corrige en vez de retener (docs/ciclo_de_vida.md,
«Coherencia en la puerta»). Aquí van las comprobaciones, puras (una ficha entra, salen sus
hallazgos); la corrección y la relectura con el modelo grande están en recogida/correccion.py.

- a) Un suceso es un país y una jornada: una frase que da dos días (`suceso.varios_dias`).
- b) La fecha casa con su episodio (la noche que agrupa sus fichas); la de sus fuentes ya la
  mira la auditoría (letras F, J, S y Z).
- c) El lugar está en el país de la ficha y lo nombra una frase de sus fuentes.
- d) El número de drones lo da una fuente de la ficha (una afirmación con su fuente).
- f) El titular no nombra otro país que el de la ficha, ni una localidad de otro país que no
  nombre ninguna frase de sus fuentes (el titular tal como lo enseña la web).

Las frases que cuentan son las de las fuentes públicas (las que enseña la web): `frase_origen` y
el titular del artículo. Los nombres se comparan sin tildes ni mayúsculas y por su raíz (las
cuatro primeras letras de cada palabra larga, menos las tres últimas), para que «варшавском»
nombre «Варшава» y «Rēzeknes» nombre «Rēzekne»."""

import copy
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache

from esquema import Documento
from proceso import autoridades, fechas, fronteras, rectificaciones, suceso, titulares
from proceso import control_fichas as reglas
from proceso.noticias import (
    Nomenclator,
    _grupos,
    _mayusculas,
    generico,
    localidades_declinadas,
    lugares_en,
    nomenclator,
    normalizar,
)

# Comprobaciones (la letra del punto 6 del encargo).
UN_SUCESO, FECHA, LUGAR, DRONES, TITULAR = "a", "b", "c", "d", "f"
# Una ficha y su episodio pueden diferir en la noche (la tarde o la madrugada): más, no.
MARGEN_EPISODIO = timedelta(days=1)
# Palabras de un nombre de lugar que no lo distinguen.
_VACIAS = frozenset(
    {"de", "del", "la", "el", "los", "las", "di", "da", "do", "du", "von", "der", "im", "am",
     "the", "of", "and", "y", "i", "na", "pri", "pod", "nad", "w", "v", "u", "z"}
)  # fmt: skip
# Palabras de tipo de lugar: no distinguen un sitio de otro («aeropuerto» no es Melilla).
_TIPOS = frozenset(
    {"aeropuerto", "airport", "flughafen", "lidosta", "aeroporto", "aeroport", "lotnisko",
     "lufthavn", "lufthamn", "luchthaven", "aerodromo", "base", "aerea", "militar", "puerto",
     "port", "hafen", "centrale", "central", "nuclear", "nucleaire", "deposito", "petroleo",
     "municipio", "municipios", "region", "provincia", "distrito", "junto", "frontera", "cerca",
     "norte", "sur", "este", "oeste", "centro", "zona", "ciudad", "pueblo", "penitenciari",
     "centre", "carcel", "prision", "internacional", "international"}
)  # fmt: skip
# Margen sobre los radios para que un sitio nombrado en una frase sea el de la ficha.
MARGEN_KM = 10.0
SIN_DATO = "desconocido"


@dataclass(frozen=True)
class Hallazgo:
    comprobacion: str
    motivo: str


def publicas(ficha: Documento) -> list[Documento]:
    return [
        f for f in ficha.get("fuentes", [])
        if f.get("publica", True) and f.get("fiabilidad") not in {"E", "F"}
    ]  # fmt: skip


def textos(ficha: Documento) -> list[str]:
    """Las frases de las fuentes públicas, como están: la del dato y el titular."""
    salida = []
    for fuente in publicas(ficha):
        for clave in ("frase_origen", "titular"):
            texto = str(fuente.get(clave) or "").strip()
            if texto:
                salida.append(texto)
    return salida


def frases(ficha: Documento) -> list[str]:
    """`textos`, normalizados."""
    return [normalizar(t) for t in textos(ficha)]


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    f1, f2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((f2 - f1) / 2) ** 2
         + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)  # fmt: skip
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _raiz(palabra: str) -> str:
    return palabra if len(palabra) <= 5 else palabra[: max(4, len(palabra) - 3)]


def nombra(frase: str, nombre: str) -> bool:
    """La frase (normalizada) nombra el lugar: cada palabra que lo distingue aparece en ella por
    su raíz."""
    palabras = [p for p in normalizar(nombre).replace("-", " ").split() if p not in _VACIAS]
    palabras = [p for p in palabras if len(p) >= 3]
    if not palabras:
        return False
    de_la_frase = frase.replace("-", " ").split()
    return all(any(w.startswith(_raiz(p)) for w in de_la_frase) for p in palabras)


def nombra_alguna(frase: str, nombre: str) -> bool:
    """La frase (normalizada) nombra por su raíz alguna palabra propia del nombre (de cinco
    letras o más, que no sea de tipo de lugar)."""
    propias = [
        p for p in normalizar(nombre).replace("-", " ").replace(",", " ").split()
        if len(p) >= 5 and p not in _VACIAS and p not in _TIPOS
    ]  # fmt: skip
    de_la_frase = frase.replace("-", " ").split()
    return any(any(w.startswith(_raiz(p)) for w in de_la_frase) for p in propias)


def nombres_del_lugar(ficha: Documento) -> list[str]:
    lugar = ficha.get("lugar") or {}
    nombres = [
        lugar.get("suceso"),
        lugar.get("localidad"),
        (ficha.get("objetivo") or {}).get("nombre"),
    ]
    if lugar.get("nivel") == "region":
        nombres.append(lugar.get("region"))
    return [str(n) for n in nombres if n]


def sitio_nombrado(ficha: Documento, nom: Nomenclator | None = None) -> bool:
    """Una frase nombra un sitio del nomenclátor (con sus alias y sus formas declinadas) del país
    de la ficha y a menos de los dos radios más MARGEN_KM de su punto."""
    lugar = ficha.get("lugar") or {}
    punto = lugar.get("punto")
    if not punto:
        return False
    nom = nom or nomenclator()
    radio = float(lugar.get("radio_km") or 0)
    for texto in textos(ficha):
        for id_ in {*lugares_en(texto, nom), *localidades_declinadas(texto, nom)}:
            sitio = nom.lugares.get(id_)
            if sitio is None or sitio.pais != lugar.get("pais"):
                continue
            lejos = _km(float(punto["lat"]), float(punto["lon"]), sitio.lat, sitio.lon)
            if lejos <= radio + sitio.radio_km + MARGEN_KM:
                return True
    return False


def lugar_sin_frase(ficha: Documento, nom: Nomenclator | None = None) -> bool:
    """c) Un lugar más preciso que el país que no nombra ninguna frase de sus fuentes: ni un
    sitio del nomenclátor junto a su punto (`sitio_nombrado`) ni una palabra propia de su nombre
    (`nombra_alguna`)."""
    lugar = ficha.get("lugar") or {}
    if lugar.get("nivel") in (None, "pais"):
        return False
    nombres = nombres_del_lugar(ficha)
    if not nombres:
        return False
    normalizadas = frases(ficha)
    if any(nombra_alguna(t, n) for t in normalizadas for n in nombres):
        return False
    return not sitio_nombrado(ficha, nom)


def lugar_fuera_del_pais(ficha: Documento) -> bool:
    """c) El punto de la ficha cae fuera de su país (con el margen de la frontera y del mar)."""
    lugar = ficha.get("lugar") or {}
    punto = lugar.get("punto")
    pais = str(lugar.get("pais") or "")
    if not punto or pais not in fronteras.paises():
        return False
    return not fronteras.dentro_del_pais(pais, float(punto["lat"]), float(punto["lon"]))


def drones_sin_frase(ficha: Documento) -> bool:
    """d) Un número de drones que no da ninguna fuente pública de la ficha."""
    numero = (ficha.get("drones") or {}).get("numero")
    if numero in (None, SIN_DATO):
        return False
    ids = {str(f.get("id")) for f in publicas(ficha)}
    return not any(
        a.get("campo") == "drones" and str(a.get("fuente_id")) in ids
        for a in ficha.get("afirmaciones", [])
    )


def fecha_fuera_del_episodio(ficha: Documento, noche: date | None) -> bool:
    """b) El día de la ficha está a más de un día de la noche de su episodio."""
    if noche is None:
        return False
    pais = str((ficha.get("lugar") or {}).get("pais") or "")
    dia = suceso.dia_local(suceso.instante(ficha), pais)
    return abs(dia - noche) > MARGEN_EPISODIO


def titulo_de_otro_pais(ficha: Documento) -> str | None:
    """f) El titular en español nombra otro país del alcance, y no el de la ficha: el código del
    otro país, o None."""
    titulo = normalizar(str((ficha.get("titulo") or {}).get("es") or ""))
    pais = str((ficha.get("lugar") or {}).get("pais") or "")
    if not titulo or not pais:
        return None
    palabras = titulo.split()

    texto = f" {' '.join(palabras)} "

    def nombrado(codigo: str) -> bool:
        # El nombre entero, como palabras: «España» no es «espacio».
        return any(
            f" {normalizar(n)} " in texto for n in fronteras.nombres_del_pais(codigo) if len(n) > 3
        )

    if nombrado(pais):
        return None
    for otro in sorted(fronteras.paises()):
        if otro != pais and nombrado(otro):
            return otro
    return None


# Un nombre de localidad de otro país en un titular: como mínimo estas letras (menos son siglas y
# palabras sueltas).
MIN_LETRAS_LOCALIDAD = 5


@cache
def _calendario() -> frozenset[str]:
    """Los meses y los días de la semana de todos los léxicos de fechas («March» no es la
    localidad inglesa en «el 8 de marzo»)."""
    salida: set[str] = set()
    for lx in fechas.lexicos().values():
        salida.update(lx.meses)
        salida.update(forma for forma, _ in lx.dias)
    return frozenset(salida)


def localidad_de_otro_pais(ficha: Documento, nom: Nomenclator | None = None) -> str | None:
    """f) El titular, tal como lo enseña la web (nombres_lugar.titulo_corregido), nombra con
    mayúscula una localidad que solo es de otro país, por su nombre propio (no por uno de sus alias:
    «Canal» no es Canale), y que ninguna frase de sus fuentes nombra: su nombre, o None. «frente a
    Bielsko-Biała» en una ficha de Bulgaria (EODI-2026-00862, 19 de noviembre de 2026): la fuente
    decía Byala, en la costa búlgara. No cuentan la primera palabra
    del titular (siempre va con mayúscula), las palabras corrientes («Vecinos», «Tres»), los
    nombres que también son de un lugar del país de la ficha, ni un nombre de otro país que dice
    una fuente («un dron de Kaliningrado»)."""
    from proceso import nombres_lugar

    pais = str((ficha.get("lugar") or {}).get("pais") or "")
    if not pais:
        return None
    nom = nom or nomenclator()
    normalizadas: list[str] | None = None
    for idioma, titulo in nombres_lugar.titulo_corregido(ficha).items():
        if idioma not in ("es", "en") or not isinstance(titulo, str):
            continue
        normal = normalizar(titulo)
        primera = normal.split()[0] if normal else ""
        mayusculas = _mayusculas(titulo)
        for grupo in _grupos(normal):
            ids = nom.localidades.get(grupo, ())
            if (
                len(ids) != 1
                or grupo.split()[0] not in mayusculas
                or grupo == primera
                or len(grupo) < MIN_LETRAS_LOCALIDAD
                or generico(grupo)
                or grupo in nombres_lugar.nombres_del_pais(pais)
            ):
                continue
            sitio = nom.lugares.get(ids[0])
            if (
                sitio is None
                or sitio.pais == pais
                or normalizar(sitio.nombre) != grupo
                or grupo in _calendario()
            ):
                continue
            normalizadas = frases(ficha) if normalizadas is None else normalizadas
            if any(nombra(f, grupo) or nombra(f, sitio.nombre) for f in normalizadas):
                continue
            return str(sitio.nombre)
    return None


def titulo_ajeno(ficha: Documento, nom: Nomenclator | None = None) -> str | None:
    """f) Lo que el titular nombra de otro país sin respaldo: el país (`titulo_de_otro_pais`) o la
    localidad (`localidad_de_otro_pais`), o None."""
    return titulo_de_otro_pais(ficha) or localidad_de_otro_pais(ficha, nom)


def quien_de(fuente: Documento, traducidas: autoridades.Traducidas | None = None) -> Documento:
    """Quién declara la fuente, en español y en inglés: la tabla de autoridades, la traducción
    guardada de su nombre (`traducidas`, nombre -> {es, en}: las mismas que la web enseña en
    `autoridades`) o «una autoridad»."""
    medio = str(fuente.get("medio", ""))
    return {i: autoridades.de_la_fuente(medio, i, traducidas) for i in ("es", "en")}


def _autoridad_de_la_presencia(
    ficha: Documento, texto_de: Callable[[Documento], str],
    traducidas: autoridades.Traducidas | None = None,
) -> Documento | None:  # fmt: skip
    """La declaración de una autoridad que da la presencia de la ficha: una fuente pública de
    autoridad que respalda la presencia (`campos_respaldados` o una afirmación con ese valor), con
    un nombre que la web pueda escribir y cuya frase está, literal, en lo guardado de su artículo
    (`texto_de`, Almacen.texto_guardado). La más temprana, o None."""
    valor = ficha.get("presencia_dron")
    afirmadas = {
        str(a.get("fuente_id")) for a in ficha.get("afirmaciones", [])
        if a.get("campo") == "presencia_dron" and a.get("valor") == valor
    }  # fmt: skip
    validas = []
    for fuente in publicas(ficha):
        if not fuente.get("es_autoridad"):
            continue
        if (
            "presencia_dron" not in (fuente.get("campos_respaldados") or [])
            and str(fuente.get("id")) not in afirmadas
        ):
            continue
        quien = quien_de(fuente, traducidas)
        if not quien["es"].strip() or not quien["en"].strip():
            continue
        if not reglas.frase_valida(str(fuente.get("frase_origen") or ""), texto_de(fuente)):
            continue
        validas.append(fuente)
    return min(validas, key=rectificaciones._fecha_clave) if validas else None


def presencia_sin_quien(
    ficha: Documento, texto_de: Callable[[Documento], str],
    traducidas: autoridades.Traducidas | None = None,
) -> tuple[Documento, str] | None:  # fmt: skip
    """P) La presencia rebajada (no acreditada o descartada) sin un paso del historial que diga
    qué autoridad la rebajó y cuándo (la letra P de la auditoría). Para una ficha que nunca se ha
    publicado (recogida/correccion.sin_publicar), la ficha corregida y lo que cambia, o None si
    no hay nada que corregir aquí:

    - si una autoridad de la ficha lo declara con una frase literal
      (`_autoridad_de_la_presencia`), el historial empieza con ese paso: el valor, la fecha y la
      fuente de la declaración y quién la hace (como la semilla de una rectificación,
      `rectificaciones.semilla`), con su nombre escrito como en la web (`quien_de`), y la
      afirmación de la presencia con esa fuente;
    - si no, ninguna autoridad la rebaja: la presencia queda «no confirmada» (lo que cuentan la
      prensa o los testigos, docs/rectificaciones.md) sin las afirmaciones rebajadas, y el titular
      sigue a la presencia (`titulares.ajustar_incidente`).

    Una ficha con historial (una rectificación o una revisión a mano) no se toca aquí: el
    historial solo crece y la revisión manda (EODI-2026-00847, Chișinău, 15 de noviembre de
    2026: descartada por la extracción con la declaración de la AAC dentro de la noticia, sin
    historial; la puerta la dejó fuera de la web 11 recogidas)."""
    from proceso import auditoria_fichas

    valor = ficha.get("presencia_dron")
    if valor not in rectificaciones.RECTIFICADOS or ficha.get("presencia_historial"):
        return None
    if not auditoria_fichas.presencia_rebajada_sin_cierre(ficha):
        return None
    nuevo = copy.deepcopy(ficha)
    autoridad = _autoridad_de_la_presencia(ficha, texto_de, traducidas)
    if autoridad is not None:
        quien = quien_de(autoridad, traducidas)
        nuevo["presencia_historial"] = [{
            "valor": valor,
            "fecha": copy.deepcopy(autoridad["fecha"]),
            "fuente_id": autoridad["id"],
            "quien": quien,
        }]  # fmt: skip
        afirmacion = {
            "campo": "presencia_dron", "valor": valor, "fuente_id": autoridad["id"],
            "confianza_extraccion": rectificaciones.CONFIANZA_RECTIFICACION,
        }  # fmt: skip
        if not any(
            a.get("campo") == "presencia_dron" and a.get("valor") == valor
            and a.get("fuente_id") == autoridad["id"]
            for a in nuevo.get("afirmaciones", [])
        ):  # fmt: skip
            nuevo["afirmaciones"] = [*nuevo.get("afirmaciones", []), afirmacion]
        frase = " ".join(str(autoridad.get("frase_origen") or "").split())
        return nuevo, f"presencia {valor} declarada por {quien['es']} («{frase[:120]}»)"
    nuevo["presencia_dron"] = rectificaciones.NO_CONFIRMADA
    rebajadas = rectificaciones.RECTIFICADOS
    nuevo["afirmaciones"] = [
        a for a in nuevo.get("afirmaciones", [])
        if not (a.get("campo") == "presencia_dron" and a.get("valor") in rebajadas)
    ]  # fmt: skip
    nuevo = titulares.ajustar_incidente(nuevo)
    return nuevo, f"presencia {valor} sin autoridad que la declare: no confirmada"


def hallazgos(
    ficha: Documento, noche: date | None = None, nom: Nomenclator | None = None
) -> list[Hallazgo]:
    """Lo que la ficha dice sin que lo sostengan sus fuentes, por comprobación."""
    salida = []
    if suceso.dos_dias_sin_revisar(ficha):
        frase, dias = suceso.varios_dias(ficha) or ("", [])
        salida.append(
            Hallazgo(UN_SUCESO, f"una frase da dos días ({', '.join(map(str, dias))}): «{frase}»")
        )
    if fecha_fuera_del_episodio(ficha, noche):
        salida.append(
            Hallazgo(FECHA, f"la fecha está a más de un día de la noche de su episodio ({noche})")
        )
    if lugar_fuera_del_pais(ficha):
        salida.append(Hallazgo(LUGAR, "el punto cae fuera del país de la ficha"))
    elif lugar_sin_frase(ficha, nom):
        salida.append(Hallazgo(LUGAR, "ninguna frase de sus fuentes nombra el lugar"))
    if drones_sin_frase(ficha):
        salida.append(Hallazgo(DRONES, "ninguna fuente de la ficha da el número de drones"))
    otro = titulo_de_otro_pais(ficha)
    if otro is not None:
        salida.append(Hallazgo(TITULAR, f"el titular nombra otro país ({otro})"))
    elif (ajena := localidad_de_otro_pais(ficha, nom)) is not None:
        salida.append(
            Hallazgo(TITULAR, f"el titular nombra un lugar de otro país sin frase ({ajena})")
        )
    return salida
