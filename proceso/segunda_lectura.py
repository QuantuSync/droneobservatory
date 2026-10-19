"""Segunda lectura de lo publicado: la parte que no llama a nada (docs/segunda_lectura.md).

Un modelo secundario, gratuito y prescindible, vuelve a leer las fichas publicadas con las citas
literales de sus fuentes y señala lo que conviene revisar. **No decide nada**: lo que marca son
candidatos que pasan por el circuito de siempre (el experto, con las reglas del control de las
fichas y de las rectificaciones). Aquí, sin llamadas:

- lo que se le manda de cada ficha (los datos clave y las citas, en su idioma) y la huella que
  dice si la ficha cambió desde la última lectura;
- el orden de lectura: lo nunca leído, lo que cambió y, después, la lectura más antigua;
- qué hallazgo cuenta: un dato «contradicho», o «sin apoyo» en el lugar, la fecha, la presencia
  o el número de drones, o una ficha que parece resumir varios sucesos; siempre con una frase
  que esté, literal, en las citas que se mandaron (si no está, el hallazgo no cuenta);
- los pares de posibles duplicados con márgenes más amplios que los del control
  (proceso/control_fichas.pares_candidatos), sin los que el control ya compara ni los que una
  revisión separó;
- los titulares que el barrido diario de rectificaciones manda al modelo y cuáles elige.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from jsonschema import Draft202012Validator

from esquema import Documento
from proceso import control_fichas as reglas
from proceso import incidentes

VERSION = "segunda/1"
# Los datos de la ficha que se comprueban, con lo que significa cada uno para el modelo.
CAMPOS: dict[str, str] = {
    "es_incidente": "la ficha cuenta un incidente concreto con drones (no un análisis, una "
    "opinión ni un resumen general)",
    "tipo": "el tipo de incidente",
    "pais": "el país donde ocurrió (código ISO)",
    "lugar": "el sitio donde ocurrió y su nivel (instalación, localidad, región o país)",
    "inicio": "el día (y la hora, si la hay) en que empezó el suceso",
    "presencia": "si hubo dron: confirmada por una autoridad, no confirmada, no acreditada tras "
    "una investigación o descartada",
    "drones": "cuántos drones",
    "cierre": "si se cerró el aeropuerto, una pista o el espacio aéreo",
    "minutos_cierre": "cuántos minutos duró el cierre",
    "dron_estatal": "si el dron es de un Estado (militar o enviado por un Estado)",
}
# «Sin apoyo» en estos datos es un candidato; en los demás, no.
CLAVE_SIN_APOYO = frozenset({"lugar", "inicio", "presencia", "drones"})
APOYADO, CONTRADICHO, SIN_APOYO = "apoyado", "contradicho", "sin_apoyo"
VALORACIONES = (APOYADO, CONTRADICHO, SIN_APOYO)
DESCONOCIDOS = frozenset({"", "sin dato", "desconocido", "None"})
MAX_CITAS = 12
MAX_LETRAS_CITA = 600
MAX_SALIDA = 6000
MAX_SALIDA_PAR = 4000
MAX_SALIDA_RECTIFICACION = 3000
MAX_TITULARES = 12
DECISIONES_PAR = ("mismo", "distinto", "dudoso")

_VALORACION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["valor", "frase"],
    "properties": {"valor": {"enum": list(VALORACIONES)}, "frase": {"type": "string"}},
}

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["campos", "varios_sucesos"],
    "properties": {
        "campos": {
            "type": "object",
            "additionalProperties": False,
            "required": list(CAMPOS),
            "properties": dict.fromkeys(CAMPOS, _VALORACION),
        },
        "varios_sucesos": {
            "type": "object",
            "additionalProperties": False,
            "required": ["valor", "frase"],
            "properties": {"valor": {"type": "boolean"}, "frase": {"type": "string"}},
        },
    },
}

ESQUEMA_PAR: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "frase_a", "frase_b", "motivo"],
    "properties": {
        "decision": {"enum": list(DECISIONES_PAR)},
        "frase_a": {"type": "string"},
        "frase_b": {"type": "string"},
        "motivo": {"type": "string"},
    },
}

ESQUEMA_RECTIFICACION: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["titulares"],
    "properties": {"titulares": {"type": "array", "items": {"type": "integer"}}},
}

_COMUN = """Eres un segundo lector del European Observatory of Drone Incidents, que registra \
incidentes con drones en Europa con su fuente y su fecha. No decides nada: solo señalas lo que \
conviene que revise otra persona. Lee solo lo que dicen las citas; no deduzcas ni añadas nada. \
Cada frase que des tiene que estar copiada LITERALMENTE de una cita (sin traducir, sin cambiar \
ni una letra, 25 palabras como máximo)."""

INSTRUCCIONES = (
    _COMUN
    + """

Recibes una ficha publicada (sus datos clave) y las citas numeradas de sus fuentes (titular y \
frases), en su idioma original. Para cada dato de la ficha, di si las citas lo apoyan \
(«apoyado»), lo contradicen («contradicho») o no dicen nada de él («sin_apoyo»), con la frase \
que lo justifica; con «sin_apoyo», la frase vacía. Los datos:
"""
    + "\n".join(f"- {campo}: {texto}." for campo, texto in CAMPOS.items())
    + """

Además, varios_sucesos: cierto si la ficha parece resumir varios sucesos distintos (otros días, \
otros sitios, un balance de varias noches), con la frase que lo muestra; si no, falso y la frase \
vacía."""
)

INSTRUCCIONES_PAR = (
    _COMUN
    + """

Recibes dos fichas publicadas del mismo país y de fechas cercanas, cada una con las citas de sus \
fuentes. Di si cuentan el mismo suceso, es decir, el mismo hecho físico (los mismos drones, en \
el mismo sitio, el mismo día o la misma noche): «mismo», «distinto» o «dudoso». Con «mismo», da \
en frase_a una frase de las citas de A y en frase_b una de las de B que lo muestren (el sitio, \
el día). El motivo, en una frase en español."""
)

INSTRUCCIONES_RECTIFICACION = (
    _COMUN
    + """

Recibes una ficha publicada (un incidente con la presencia del dron que declaró una autoridad) \
y titulares de noticias posteriores, numerados. Di qué titulares pueden contar que una \
autoridad oficial (policía, fiscalía, fuerzas armadas, ministerio, gobierno, aviación civil, \
aeropuerto, organismo de investigación) rectifica la presencia del dron en ESE incidente: cierra \
la investigación sin pruebas del dron, no puede confirmarlo, retira lo que dijo o dice que era \
otra cosa. Lo que dicen periodistas, analistas u OSINT no cuenta. Devuelve los números de esos \
titulares (vacío si ninguno)."""
)


def con_esquema(instrucciones: str, esquema: dict[str, Any]) -> str:
    """Las instrucciones con el esquema de la respuesta (por si el servicio solo admite pedir un
    objeto JSON sin esquema)."""
    return f"{instrucciones}\n\nResponde solo con un objeto JSON con este esquema:\n" + json.dumps(
        esquema, ensure_ascii=False
    )


def valida(respuesta: Any, esquema: dict[str, Any]) -> bool:
    """La respuesta cumple su esquema; la que no, se descarta y se vuelve a pedir otro día."""
    return bool(Draft202012Validator(esquema).is_valid(respuesta))


# --- Lo que se manda de una ficha ----------------------------------------------------------


@dataclass(frozen=True)
class Cita:
    """Lo que dice una fuente pública: su titular y sus frases, en su idioma."""

    medio: str
    fecha: str
    idioma: str
    texto: str

    def bloque(self, numero: int) -> str:
        return f"Cita {numero} ({self.medio}, {self.fecha}, {self.idioma or '?'}): {self.texto}"


def citas_de(fuentes: list[Documento], titulares: dict[str, str]) -> list[Cita]:
    """Las citas de las fuentes públicas de una ficha, una por enlace (la noticia y las
    declaraciones que cita van juntas), las oficiales primero."""
    grupos: dict[str, list[Documento]] = {}
    for fuente in fuentes:
        grupos.setdefault(str(fuente.get("enlace") or fuente["id"]), []).append(fuente)

    def orden(par: tuple[str, list[Documento]]) -> tuple[int, str]:
        oficial = any(reglas.oficial(f) for f in par[1])
        return (0 if oficial else 1, min(f["fecha"]["valor"] for f in par[1]))

    citas = []
    for enlace, grupo in sorted(grupos.items(), key=orden)[:MAX_CITAS]:
        principal = next((f for f in grupo if "-declaracion-" not in f["id"]), grupo[0])
        partes = [titulares.get(enlace, "")]
        partes += [str(f.get("frase_origen") or "") for f in grupo]
        texto = " ".join(dict.fromkeys(" ".join(p.split()) for p in partes if p.strip()))
        if not texto:
            continue
        citas.append(Cita(str(principal.get("medio", "")), principal["fecha"]["valor"][:10],
                          str(principal.get("idioma") or ""), texto[:MAX_LETRAS_CITA]))  # fmt: skip
    return citas


def ficha(incidente: Documento) -> dict[str, str]:
    """Los datos clave de la ficha publicada, como texto."""
    vista = reglas.vista(incidente)
    lugar = incidente.get("lugar") or {}
    estatal = (incidente.get("pruebas") or {}).get("dron_estatal")
    return {
        "es_incidente": "sí",
        "tipo": str(incidente.get("tipo") or ""),
        "pais": str(lugar.get("pais") or ""),
        "lugar": str(vista["lugar"]),
        "inicio": str(vista["inicio"]),
        "presencia": str(incidente.get("presencia_dron") or ""),
        "drones": str(vista["drones"]),
        "cierre": str(vista["cierre"]),
        "minutos_cierre": str(vista["duracion_min"]) if vista["cierre"] == "si" else "sin dato",
        "dron_estatal": "sí" if estatal is True else "no" if estatal is False else "sin dato",
    }


def huella(datos: dict[str, str], citas: list[Cita]) -> str:
    """Cambia cuando cambia un dato clave o una cita."""
    texto = json.dumps([datos, [c.texto for c in citas]], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _resumen(datos: dict[str, str]) -> str:
    return "\n".join(f"- {campo}: {valor}" for campo, valor in datos.items())


def contenido(datos: dict[str, str], citas: list[Cita]) -> str:
    return (
        "Ficha:\n"
        + _resumen(datos)
        + "\n\nCitas:\n"
        + "\n".join(c.bloque(n) for n, c in enumerate(citas, 1))
    )


def contenido_par(a: dict[str, str], citas_a: list[Cita], b: dict[str, str],
                  citas_b: list[Cita]) -> str:  # fmt: skip
    partes = [
        "Ficha A:",
        _resumen(a),
        "Citas de A:",
        *(c.bloque(n) for n, c in enumerate(citas_a, 1)),
    ]
    partes += ["", "Ficha B:", _resumen(b), "Citas de B:"]
    partes += [c.bloque(n) for n, c in enumerate(citas_b, 1)]
    return "\n".join(partes)


# --- Qué cuenta de la respuesta ------------------------------------------------------------


def en_las_citas(frase: str, citas: list[Cita]) -> bool:
    """La frase está, literal (sin mayúsculas ni espacios de más), en alguna cita."""
    return any(reglas.frase_valida(frase, c.texto) for c in citas)


@dataclass(frozen=True)
class Hallazgo:
    campo: str
    valoracion: str
    frase: str
    valor: str = ""

    def documento(self) -> Documento:
        return {"campo": self.campo, "valoracion": self.valoracion, "frase": self.frase,
                "valor": self.valor}  # fmt: skip


def hallazgos(
    respuesta: dict[str, Any], datos: dict[str, str], citas: list[Cita]
) -> list[Hallazgo]:
    """Lo que cuenta de una respuesta válida: un dato contradicho, uno clave sin apoyo o varios
    sucesos, con una frase que está en las citas (una frase inventada anula el hallazgo). Un dato
    que la ficha no tiene no se valora, ni la fecha aproximada (la de la publicación) sin apoyo:
    ninguna cita la escribe."""
    resultado = []
    for campo, valoracion in respuesta["campos"].items():
        valor = datos.get(campo, "")
        if valor in DESCONOCIDOS:
            continue
        frase = " ".join(str(valoracion.get("frase") or "").split())
        if valoracion["valor"] == CONTRADICHO:
            if frase and en_las_citas(frase, citas):
                resultado.append(Hallazgo(campo, CONTRADICHO, frase, valor))
        elif (
            valoracion["valor"] == SIN_APOYO
            and campo in CLAVE_SIN_APOYO
            and not (campo == "inicio" and valor.endswith(f"({incidentes.APROXIMADA})"))
            and (not frase or en_las_citas(frase, citas))
        ):
            resultado.append(Hallazgo(campo, SIN_APOYO, "", valor))
    varios = respuesta["varios_sucesos"]
    frase = " ".join(str(varios.get("frase") or "").split())
    if varios["valor"] is True and frase and en_las_citas(frase, citas):
        resultado.append(Hallazgo("varios_sucesos", CONTRADICHO, frase))
    return resultado


def mismo_suceso(respuesta: dict[str, Any], citas_a: list[Cita], citas_b: list[Cita]) -> bool:
    """El par parece el mismo suceso: «mismo», con una frase de cada ficha que está en sus
    citas."""
    frase_a, frase_b = str(respuesta["frase_a"]), str(respuesta["frase_b"])
    return (
        respuesta["decision"] == "mismo"
        and en_las_citas(frase_a, citas_a)
        and en_las_citas(frase_b, citas_b)
    )


def elegidos(respuesta: dict[str, Any], cuantos: int) -> list[int]:
    """Los números de titular válidos que elige el barrido de rectificaciones, sin repetir."""
    return list(dict.fromkeys(
        n for n in respuesta["titulares"] if isinstance(n, int) and 1 <= n <= cuantos
    ))  # fmt: skip


def al_experto(candidato: Documento) -> bool:
    """El candidato merece la revisión del experto: un duplicado, o una ficha con algún hallazgo
    que no sea solo la fecha de inicio sin apoyo. Desde el 19 de octubre de 2026, «fecha sin
    apoyo» sola se queda marcada pero no gasta del experto: era el hallazgo más frecuente (168 de
    los primeros 280 candidatos) y casi siempre ruido (la fecha sale de la publicación)."""
    if candidato.get("tipo") == "duplicado":
        return True
    return any(
        not (h.get("campo") == "inicio" and h.get("valoracion") == SIN_APOYO)
        for h in (candidato.get("datos") or {}).get("hallazgos", [])
    )


def prioridad(candidato: Documento) -> int:
    """Lo contradicho y lo que resume varios sucesos, primero; luego los duplicados; al final,
    lo que solo no tiene apoyo."""
    if candidato.get("tipo") == "duplicado":
        return 1
    valoraciones = {
        h.get("valoracion") for h in (candidato.get("datos") or {}).get("hallazgos", [])
    }
    return 0 if CONTRADICHO in valoraciones else 2


# --- Orden de lectura ----------------------------------------------------------------------


def orden_lectura(fichas: dict[str, str], lecturas: dict[str, tuple[str, str]]) -> list[str]:
    """Los identificadores en el orden en que se leen: los nunca leídos (los más nuevos primero),
    los que cambiaron desde su última lectura y después la lectura más antigua. `fichas`: id ->
    huella; `lecturas`: id -> (huella, fecha de la lectura)."""
    nunca = sorted((i for i in fichas if i not in lecturas), key=reglas.orden_registro,
                   reverse=True)  # fmt: skip
    cambiadas = sorted(
        (i for i in fichas if i in lecturas and lecturas[i][0] != fichas[i]),
        key=lambda i: lecturas[i][1],
    )
    iguales = sorted(
        (i for i in fichas if i in lecturas and lecturas[i][0] == fichas[i]),
        key=lambda i: lecturas[i][1],
    )
    return [*nunca, *cambiadas, *iguales]


# --- Posibles duplicados -------------------------------------------------------------------


def cercanos(a: Documento, b: Documento, horas: float, km: float) -> bool:
    """Del mismo país, a `horas` como mucho (el suceso o la primera noticia), a `km` más los
    radios (sin punto, solo el país), del mismo tipo de sitio y que ninguna revisión separó; sin
    los que ya compara el control (proceso/control_fichas.candidatos)."""
    if a["id"] == b["id"] or a["lugar"]["pais"] != b["lugar"]["pais"]:
        return False
    ventana = timedelta(hours=horas)
    if (
        abs(reglas.instante(a) - reglas.instante(b)) > ventana
        and abs(reglas.primera_noticia(a) - reglas.primera_noticia(b)) > ventana
    ):
        return False
    pa, pb = reglas._punto(a), reglas._punto(b)
    if pa is not None and pb is not None:
        radios = float(a["lugar"].get("radio_km", 0)) + float(b["lugar"].get("radio_km", 0))
        if reglas._km(pa, pb) > radios + km:
            return False
    return (
        reglas._mismo_tipo_de_sitio(a, b)
        and not reglas.separados(a, b)
        and not reglas.candidatos(a, b)
    )


def pares_amplios(activos: list[Documento], horas: float, km: float,
                  ya_comparados: set[str]) -> list[tuple[Documento, Documento]]:  # fmt: skip
    """Los pares de posibles duplicados con márgenes más amplios, sin los que el control ya
    comparó (`ya_comparados`: claves `par:…`)."""
    pares = reglas.pares_candidatos(
        activos, {d["id"] for d in activos}, lambda a, b: cercanos(a, b, horas, km)
    )
    return [p for p in pares if reglas.clave_par(p[0]["id"], p[1]["id"]) not in ya_comparados]
