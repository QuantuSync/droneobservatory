"""Segunda lectura que busca lo que falta: la parte que no llama a nada (docs/segunda_lectura.md,
«Lo que falta»).

La segunda lectura compara cada ficha con sus citas; estas búsquedas miran lo que la ficha no
tiene. Como el resto de la capa, **no deciden nada**: cada hallazgo es un candidato que pasa por el
circuito de siempre (la extracción con el experto, la regla estricta de atribución, la
verificación del experto). Aquí, sin llamadas:

- qué incidentes y qué noticias se miran en cada búsqueda;
- lo que se manda al modelo secundario (textos numerados) y el esquema de su respuesta;
- qué cuenta de la respuesta: siempre con una frase que esté, literal, en el texto numerado que se
  mandó (si no está, el hallazgo se descarta).

Las búsquedas:

- **declaracion** (a): un incidente publicado «notificado», o con la presencia «no confirmada», de
  más de 48 horas, y una noticia (las suyas o las posteriores que nombran su lugar) que cita una
  declaración de una autoridad oficial que confirma, niega o rectifica el suceso o el dron.
- **rescate** (b): una noticia recogida que no está en ninguna ficha publicada y cuenta un suceso
  con drones dentro del alcance del observatorio, que no coincide con ninguna ficha existente.
- **atribucion** (c): un incidente confirmado sin atribuir y una frase en la que una autoridad
  oficial afirma expresamente quién es el responsable. Una frase que investiga, sospecha o vincula
  (proceso/atribucion.expresion_de_duda) no es candidata.
- **efectos** (d): una ficha con el lugar a nivel de país o de región cuyas fuentes nombran la
  instalación o la localidad, o un cierre sin duración cuyas fuentes dan la duración o la hora de
  reapertura.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from esquema import Documento
from proceso import atribucion
from proceso import control_fichas as reglas
from proceso import segunda_lectura as lectura

DECLARACION, RESCATE, ATRIBUCION, EFECTOS = "declaracion", "rescate", "atribucion", "efectos"
BUSQUEDAS = (DECLARACION, RESCATE, ATRIBUCION, EFECTOS)
# Lo que hace cada búsqueda en la recogida: repetir la extracción con el experto (a, c), volver a
# la extracción normal (b) o la verificación del experto (d).
A_LA_EXTRACCION = frozenset({DECLARACION, RESCATE, ATRIBUCION})
MAX_TEXTOS = 6
MAX_LETRAS_TEXTO = 2500
MAX_SALIDA = 2000
MAX_FICHAS_CERCANAS = 8
AFIRMA = ("confirma", "niega", "rectifica")
NIVELES_VAGOS = frozenset({"pais", "region"})

_COMUN = lectura._COMUN

INSTRUCCIONES_DECLARACION = (
    _COMUN
    + """

Recibes un incidente publicado (sus datos) y textos numerados de noticias: las suyas y otras \
posteriores que nombran su lugar. Di si algún texto cita una declaración de una autoridad oficial \
(gobierno o su delegación, ministerio, fuerzas armadas, policía, fiscalía, aviación civil, \
gestor del aeropuerto o de la navegación aérea) que confirma que el suceso ocurrió o que hubo un \
dron («confirma»), lo niega («niega») o lo rectifica («rectifica»), también en estilo indirecto \
(«según la Delegación del Gobierno»). Lo que dicen periodistas, testigos, sindicatos, \
asociaciones o expertos no cuenta. Si lo hay: hay=true, el número del texto, la autoridad, qué \
afirma y la frase literal. Si no: hay=false y lo demás vacío."""
)

INSTRUCCIONES_RESCATE = (
    _COMUN
    + """

Recibes una noticia (titular y primeras frases) y una lista de fichas ya publicadas del mismo \
país y de fechas cercanas. Di si la noticia cuenta un suceso concreto con drones en Europa (un \
dron que sobrevuela una instalación, entra en el espacio aéreo de un país desde fuera o \
interrumpe un aeropuerto), con su día y su lugar. Un análisis, una opinión, una entrevista, un \
resumen de varios sucesos, un vuelo autorizado, un ejercicio o una noticia de otro continente no \
cuentan. Si es un suceso, da la fecha (AAAA-MM-DD), el lugar, el país (código ISO) y la frase \
literal que lo cuenta; y si es el mismo suceso que alguna de las fichas, su identificador en \
coincide_con (si no, vacío)."""
)

INSTRUCCIONES_ATRIBUCION = (
    _COMUN
    + """

Recibes un incidente confirmado y sin atribuir y textos numerados de sus noticias. Busca una \
frase en la que una autoridad oficial (gobierno, ministerio, fuerzas armadas, fiscalía o \
policía) afirme EXPRESAMENTE, como un hecho, quién es el responsable del dron: un Estado o una \
persona. Que la autoridad investigue, sospeche, no descarte, vea posible o «vincule» no cuenta, \
ni que lo diga un periodista. Si la hay: hay=true, el número del texto, la autoridad, el \
responsable y la frase literal. Si no: hay=false y lo demás vacío."""
)

INSTRUCCIONES_EFECTOS = (
    _COMUN
    + """

Recibes un incidente publicado (sus datos) y textos numerados de sus noticias. Di si algún \
texto nombra el sitio concreto donde ocurrió (una instalación con nombre propio, como un \
aeropuerto, una base o una cárcel, o una localidad) cuando la ficha solo tiene el país o la \
región; y si algún texto da cuánto duró el cierre o a qué hora se reabrió, cuando la ficha tiene \
un cierre sin duración. Para cada cosa, la frase literal y el número del texto; vacío si no."""
)

_TEXTO_O_VACIO = {"type": "string"}
ESQUEMA_DECLARACION: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["hay", "texto", "autoridad", "afirma", "frase"],
    "properties": {
        "hay": {"type": "boolean"}, "texto": {"type": "integer"},
        "autoridad": _TEXTO_O_VACIO, "afirma": {"enum": [*AFIRMA, ""]}, "frase": _TEXTO_O_VACIO,
    },
}  # fmt: skip
ESQUEMA_RESCATE: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["suceso", "fecha", "lugar", "pais", "frase", "coincide_con"],
    "properties": {
        "suceso": {"type": "boolean"}, "fecha": _TEXTO_O_VACIO, "lugar": _TEXTO_O_VACIO,
        "pais": _TEXTO_O_VACIO, "frase": _TEXTO_O_VACIO, "coincide_con": _TEXTO_O_VACIO,
    },
}  # fmt: skip
ESQUEMA_ATRIBUCION: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["hay", "texto", "autoridad", "responsable", "frase"],
    "properties": {
        "hay": {"type": "boolean"}, "texto": {"type": "integer"},
        "autoridad": _TEXTO_O_VACIO, "responsable": _TEXTO_O_VACIO, "frase": _TEXTO_O_VACIO,
    },
}  # fmt: skip
_DATO_EFECTO = {
    "type": "object", "additionalProperties": False, "required": ["frase", "texto"],
    "properties": {"frase": _TEXTO_O_VACIO, "texto": {"type": "integer"}},
}  # fmt: skip
ESQUEMA_EFECTOS: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["lugar", "duracion"],
    "properties": {"lugar": _DATO_EFECTO, "duracion": _DATO_EFECTO},
}  # fmt: skip

INSTRUCCIONES = {
    DECLARACION: (INSTRUCCIONES_DECLARACION, ESQUEMA_DECLARACION),
    RESCATE: (INSTRUCCIONES_RESCATE, ESQUEMA_RESCATE),
    ATRIBUCION: (INSTRUCCIONES_ATRIBUCION, ESQUEMA_ATRIBUCION),
    EFECTOS: (INSTRUCCIONES_EFECTOS, ESQUEMA_EFECTOS),
}


@dataclass(frozen=True)
class Texto:
    """Una noticia tal como se manda: su dirección (no se manda), medio, fecha y texto."""

    url: str
    medio: str
    fecha: str
    texto: str

    def bloque(self, numero: int) -> str:
        return f"Texto {numero} ({self.medio}, {self.fecha[:10]}): {self.texto}"


def huella(*partes: Any) -> str:
    """Cambia cuando cambia lo que se manda: una búsqueda no se repite con lo mismo."""
    texto = json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def contenido(datos: dict[str, str], textos: list[Texto]) -> str:
    return (
        "Incidente:\n"
        + "\n".join(f"- {k}: {v}" for k, v in datos.items())
        + "\n\nTextos:\n"
        + "\n".join(t.bloque(n) for n, t in enumerate(textos, 1))
    )


def contenido_rescate(texto: Texto, cercanas: list[Documento]) -> str:
    lineas = [
        f"- {d['id']}: {d['tiempo']['inicio']['valor'][:10]}, "
        f"{(d.get('titulo') or {}).get('es', '')}"
        for d in cercanas[:MAX_FICHAS_CERCANAS]
    ]
    return f"Noticia ({texto.medio}, {texto.fecha[:10]}): {texto.texto}\n\nFichas publicadas:\n" + (
        "\n".join(lineas) if lineas else "(ninguna)"
    )


def _en(frase: str, texto: Texto) -> bool:
    return reglas.frase_valida(frase, texto.texto)


def _texto(respuesta: Documento, textos: list[Texto]) -> Texto | None:
    numero = respuesta.get("texto")
    if isinstance(numero, int) and 1 <= numero <= len(textos):
        return textos[numero - 1]
    return None


def declaracion(respuesta: Documento, textos: list[Texto]) -> Documento | None:
    """El hallazgo de la búsqueda de declaraciones, o None (no hay, o la frase no está literal en
    el texto que dice)."""
    texto = _texto(respuesta, textos)
    frase = " ".join(str(respuesta.get("frase") or "").split())
    if (
        respuesta.get("hay") is not True
        or texto is None
        or respuesta.get("afirma") not in AFIRMA
        or not str(respuesta.get("autoridad") or "").strip()
        or not _en(frase, texto)
    ):
        return None
    return {"url": texto.url, "medio": texto.medio, "fecha": texto.fecha, "frase": frase,
            "autoridad": str(respuesta["autoridad"])[:120],
            "afirma": respuesta["afirma"]}  # fmt: skip


def atribucion_hallada(respuesta: Documento, textos: list[Texto]) -> Documento | None:
    """El hallazgo de la búsqueda de atribución, o None: sin frase literal, o con una frase que
    investiga, sospecha o vincula (eso nunca atribuye)."""
    texto = _texto(respuesta, textos)
    frase = " ".join(str(respuesta.get("frase") or "").split())
    if (
        respuesta.get("hay") is not True
        or texto is None
        or not str(respuesta.get("responsable") or "").strip()
        or not _en(frase, texto)
        or atribucion.expresion_de_duda(frase) is not None
    ):
        return None
    return {"url": texto.url, "medio": texto.medio, "fecha": texto.fecha, "frase": frase,
            "autoridad": str(respuesta.get("autoridad") or "")[:120],
            "responsable": str(respuesta["responsable"])[:120]}  # fmt: skip


def efectos(respuesta: Documento, textos: list[Texto], datos: dict[str, str]) -> list[Documento]:
    """Los hallazgos de lugar o de duración con su frase literal; solo lo que la ficha no tiene."""
    hallados = []
    for campo, falta in (("lugar", vago(datos)), ("duracion", sin_duracion(datos))):
        dato = respuesta.get(campo) or {}
        texto = _texto(dato, textos)
        frase = " ".join(str(dato.get("frase") or "").split())
        if falta and texto is not None and _en(frase, texto):
            hallados.append({"campo": campo, "valoracion": "falta", "frase": frase,
                             "url": texto.url, "valor": datos.get(campo, "")})  # fmt: skip
    return hallados


def rescate(respuesta: Documento, texto: Texto, cercanas: list[Documento]) -> Documento | None:
    """El hallazgo de la búsqueda de incidentes que faltan, o None: no es un suceso, la frase no
    está en la noticia, o coincide con una ficha que ya existe (entonces no se rescata)."""
    frase = " ".join(str(respuesta.get("frase") or "").split())
    coincide = str(respuesta.get("coincide_con") or "").strip()
    if respuesta.get("suceso") is not True or not _en(frase, texto):
        return None
    if coincide:
        # Coincide con una ficha (de las que se le mandaron o de otras): no se rescata.
        return None
    return {"url": texto.url, "medio": texto.medio, "fecha": texto.fecha, "frase": frase,
            "fecha_suceso": str(respuesta.get("fecha") or "")[:10],
            "lugar": str(respuesta.get("lugar") or "")[:120],
            "pais": str(respuesta.get("pais") or "")[:2].upper()}  # fmt: skip


# --- Qué se mira ---------------------------------------------------------------------------


def _inicio(incidente: Documento) -> datetime:
    return datetime.strptime(incidente["tiempo"]["inicio"]["valor"][:16], "%Y-%m-%dT%H:%M")


def vago(datos: dict[str, str]) -> bool:
    return datos.get("nivel", "") in NIVELES_VAGOS


def sin_duracion(datos: dict[str, str]) -> bool:
    return datos.get("cierre") == "si" and datos.get("minutos_cierre") in lectura.DESCONOCIDOS


def datos_de(incidente: Documento) -> dict[str, str]:
    """Lo que se manda del incidente: los datos de la segunda lectura, su estado y su nivel."""
    datos = lectura.ficha(incidente)
    datos.pop("es_incidente", None)
    datos["estado"] = str(incidente["estado"]["actual"])
    datos["nivel"] = str((incidente.get("lugar") or {}).get("nivel") or "")
    datos["titulo"] = str((incidente.get("titulo") or {}).get("es") or "")
    return datos


def toca(busqueda: str, incidente: Documento, ahora: datetime, horas_minimas: float) -> bool:
    """El incidente entra en la búsqueda (sin el filtro de antigüedad si horas_minimas es 0)."""
    if ahora.replace(tzinfo=None) - _inicio(incidente) < timedelta(hours=horas_minimas):
        return False
    estado = incidente["estado"]["actual"]
    if busqueda == DECLARACION:
        return estado == "notificado" or incidente.get("presencia_dron") == "no_confirmada"
    if busqueda == ATRIBUCION:
        return estado == "confirmado" and not incidente.get("atribucion")
    if busqueda == EFECTOS:
        datos = datos_de(incidente)
        return vago(datos) or sin_duracion(datos)
    return False


def cercanas(fichas: list[Documento], pais: str, fecha: str, dias: int = 3) -> list[Documento]:
    """Las fichas publicadas del mismo país a `dias` días de la fecha (para no rescatar un suceso
    que ya tiene ficha)."""
    try:
        centro = datetime.strptime(fecha[:10], "%Y-%m-%d")
    except ValueError:
        return []
    margen = timedelta(days=dias)
    return sorted(
        (d for d in fichas if (d.get("lugar") or {}).get("pais") == pais
         and abs(_inicio(d).replace(hour=0, minute=0) - centro) <= margen),
        key=lambda d: d["tiempo"]["inicio"]["valor"],
    )  # fmt: skip


def prioridad(candidato: Documento) -> int:
    """El orden del experto con lo que marca la capa: primero las declaraciones y los incidentes
    que faltan; después lo contradicho de la segunda lectura; después la atribución, el lugar y
    la duración; al final, el resto."""
    tipo = candidato.get("tipo")
    if tipo in {DECLARACION, RESCATE}:
        return 0
    if tipo in {ATRIBUCION, EFECTOS}:
        return 3
    if tipo == "duplicado":
        return 2
    return 1 if lectura.prioridad(candidato) == 0 else 4
