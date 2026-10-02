"""Validación con código de la ficha que devuelve el extractor.

Nada de lo que devuelve el modelo se usa sin pasar por aquí. Un campo que no
valida se descarta y su motivo queda en el registro interno de la extracción;
si no valida lo esencial (que es un incidente, su país y su fecha), la ficha
entera no se publica.

Comprobaciones:
- la frase de origen tiene 25 palabras como máximo y está, tal cual, en el
  texto de la fuente que cita (así no se cuela una frase inventada);
- la confianza está entre 0 y 1 y llega al umbral;
- el país existe en la lista de países europeos y las coordenadas de un lugar
  nuevo caen dentro de su polígono (`proceso/fronteras.py`);
- el nombre del lugar del suceso está en la frase que lo cita;
- el cierre solo vale si su frase habla de un cierre (o, para «no», de que todo
  siguió con normalidad): el modelo no puede poner un cierre que la fuente no dice;
- los rangos son coherentes y caben en los topes;
- las fechas son posibles: no futuras, el inicio no posterior a la nota de la que sale y,
  si es más de una semana anterior a esa nota (una noticia que vuelve sobre un suceso
  pasado), solo con el día escrito en su frase («el 22 de septiembre»);
- el país del suceso se sabe: el de la ficha o el del lugar del suceso. Nunca sale
  del objetivo del candidato, que es donde casó un nombre de la noticia y no
  necesariamente donde ocurrió el suceso.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

from proceso import fechas
from proceso.fronteras import dentro_del_pais, nombres_del_pais, paises
from proceso.noticias import normalizar

DIRECTORIO = Path(__file__).resolve().parent.parent / "configuracion"
MAX_PALABRAS_FRASE = 25
# Por debajo de 0,5 el modelo declara que supone: el campo no se usa.
UMBRAL_CONFIANZA = 0.5
# Topes de plausibilidad. Los avistamientos europeos más grandes de 2025 hablan de
# decenas de drones (19 a 23 en Polonia en septiembre): 100 deja margen.
MAX_DRONES = 100
# Un gran aeropuerto europeo mueve unos 1500 vuelos al día: más afectados es un error.
MAX_VUELOS = 2000
# Un cierre por drones dura horas; más de dos días es un error de unidades.
MAX_CIERRE_MIN = 2 * 24 * 60
# La noticia sale el mismo día o pocos días después: más de una semana antes es un error.
MAX_ANTELACION = timedelta(days=7)
# El artículo lleva la hora de su franja de GDELT, que puede ir hasta una hora por detrás
# de la publicación.
MARGEN_ARTICULO = timedelta(hours=1)
MAX_LETRAS_NOMBRE = 80
# Palabras de menos de 4 letras («de», «am», «the») no identifican una instalación.
MIN_LETRAS_PALABRA = 4
# Un nombre de lugar se reconoce en su frase aunque esté declinado: cada palabra suya
# comparte con alguna de la frase todas sus letras menos las dos últimas («Rzeszów» en «w
# Rzeszowie», «Moldova» en «Moldovei») y al menos tres («Łódź» en «w Łodzi»).
LETRAS_DECLINACION = 2
MIN_LETRAS_RAIZ = 3
RANGOS = ("drones", "cierre_minutos", "vuelos_desviados", "vuelos_cancelados", "vuelos_retrasados")
TOPES = {
    "drones": MAX_DRONES,
    "cierre_minutos": MAX_CIERRE_MIN,
    "vuelos_desviados": MAX_VUELOS,
    "vuelos_cancelados": MAX_VUELOS,
    "vuelos_retrasados": MAX_VUELOS,
}
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?$")


@cache
def cajas_paises(ruta: Path = DIRECTORIO / "paises_europa.json") -> dict[str, list[float]]:
    datos: dict[str, list[float]] = json.loads(ruta.read_text(encoding="utf-8"))["cajas"]
    return datos


@cache
def palabras_cierre(ruta: Path = DIRECTORIO / "cierres.json") -> dict[str, re.Pattern[str]]:
    """Por clase («cierre», «normalidad»), un patrón de sus comienzos de palabra."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {
        clase: re.compile(
            r"(?<!\w)(?:" + "|".join(re.escape(normalizar(p)) for p in datos[clase]) + ")"
        )
        for clase in ("cierre", "normalidad")
    }


def nombrado_en(nombre: str, frase: str) -> bool:
    """Cada palabra del nombre está en la frase, entera o declinada."""
    palabras_frase = normalizar(frase).split()

    def esta(palabra: str) -> bool:
        raiz = max(MIN_LETRAS_RAIZ, len(palabra) - LETRAS_DECLINACION)
        return any(
            p == palabra or (len(p) >= raiz and p[:raiz] == palabra[:raiz]) for p in palabras_frase
        )

    palabras = normalizar(nombre).split()
    return bool(palabras) and all(esta(p) for p in palabras)


@dataclass(frozen=True)
class Contexto:
    """Lo que el extractor recibió: textos de las fuentes, objetivo y primer artículo."""

    textos: tuple[str, ...]
    pais_objetivo: str
    primer_articulo: datetime
    ahora: datetime
    # Palabras propias (sin las de tipo de lugar) de los nombres de la instalación conocida;
    # vacío si el objetivo es una localidad o un lugar del GKG.
    palabras_objetivo: frozenset[str] = frozenset()
    prefijos_genericos: tuple[str, ...] = ()
    # Hora de publicación de cada fuente enviada, en su orden: el inicio se compara con la de
    # la nota que lo dice, no con la primera del candidato (que puede ser de otro día).
    publicaciones: tuple[datetime, ...] = ()

    def publicacion(self, fuente: Any) -> datetime:
        if isinstance(fuente, int) and 1 <= fuente <= len(self.publicaciones):
            return self.publicaciones[fuente - 1]
        return self.primer_articulo


@dataclass
class Validada:
    """Campos que pasan, con su valor, fuente (índice desde 1), frase y confianza."""

    campos: dict[str, dict[str, Any]] = field(default_factory=dict)
    motivos: list[str] = field(default_factory=list)
    titulo_es: str = ""
    titulo_en: str = ""

    @property
    def publicable(self) -> bool:
        """Es un incidente y se sabe su país. La fecha, si la ficha no la da o no valida,
        sale del candidato (con precisión de día)."""
        return (
            "es_incidente" in self.campos
            and bool(self.campos["es_incidente"]["valor"])
            and self.pais is not None
        )

    @property
    def pais(self) -> str | None:
        """El país del suceso: el de la ficha o, si no lo da, el de su lugar."""
        suceso = self.valor("lugar_suceso")
        pais = self.valor("pais") or (suceso["pais"] if suceso else None)
        return str(pais) if pais else None

    def valor(self, campo: str) -> Any:
        return self.campos[campo]["valor"] if campo in self.campos else None


def leer_fecha(texto: str) -> datetime | None:
    if not _FECHA.match(texto):
        return None
    formato = "%Y-%m-%dT%H:%M" if "T" in texto else "%Y-%m-%d"
    try:
        return datetime.strptime(texto, formato).replace(tzinfo=UTC)
    except ValueError:
        return None


def _frase_valida(campo: dict[str, Any], textos: tuple[str, ...]) -> str | None:
    """Motivo por el que la frase o la fuente no valen, o None."""
    fuente, frase = campo.get("fuente"), campo.get("frase")
    if not isinstance(fuente, int) or not 1 <= fuente <= len(textos):
        return "fuente inexistente"
    if not isinstance(frase, str) or not frase.strip():
        return "sin frase de origen"
    if normalizar(frase) not in normalizar(textos[fuente - 1]):
        return "la frase no está en la fuente"
    return None


def _rango_valido(nombre: str, valor: Any) -> str | None:
    if not isinstance(valor, dict) or set(valor) != {"min", "max"}:
        return "rango mal formado"
    minimo, maximo = valor["min"], valor["max"]
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (minimo, maximo)):
        return "rango no entero"
    if minimo < 0 or minimo > maximo:
        return "rango incoherente"
    if maximo > TOPES[nombre]:
        return f"por encima del tope de {TOPES[nombre]}"
    return None


def _lugar_valido(valor: Any) -> str | None:
    if not isinstance(valor, dict):
        return "lugar mal formado"
    nombre, pais = valor.get("nombre"), valor.get("pais")
    if not isinstance(nombre, str) or not 0 < len(nombre.strip()) <= MAX_LETRAS_NOMBRE:
        return "lugar sin nombre"
    lat, lon = valor.get("lat"), valor.get("lon")
    if (
        not isinstance(pais, str)
        or not isinstance(lat, int | float)
        or not isinstance(lon, int | float)
    ):
        return "lugar sin país o coordenadas"
    if not dentro_del_pais(pais, float(lat), float(lon)):
        return "coordenadas fuera del país citado"
    return None


def _es_el_objetivo(nombre: str, frase: str, contexto: Contexto) -> bool:
    """El nombre es el de la instalación conocida y la frase la nombra, aunque de otra forma
    («Aeroport d'Eivissa - es Codolar» por «el aeropuerto de Ibiza»)."""
    propias = {
        p
        for p in normalizar(nombre).split()
        if len(p) >= MIN_LETRAS_PALABRA and not p.startswith(contexto.prefijos_genericos)
    }
    en_frase = set(normalizar(frase).split())
    return (
        bool(propias)
        and propias <= contexto.palabras_objetivo
        and bool(en_frase & contexto.palabras_objetivo)
    )


def propias_en_fuentes(nombre: str, textos: tuple[str, ...], genericos: tuple[str, ...]) -> bool:
    """Cada palabra propia del nombre (sin las de tipo de lugar) está, entera o declinada,
    en la frase o en el texto de las fuentes: «Flughafen Bremen» por «Bremer Flughafen»."""
    propias = [
        p
        for p in normalizar(nombre).split()
        if len(p) >= MIN_LETRAS_PALABRA and not p.startswith(genericos)
    ]
    return bool(propias) and all(any(nombrado_en(p, t) for t in textos) for p in propias)


def _suceso_valido(
    valor: Any, frase: str, contexto: Contexto | None = None, textos: tuple[str, ...] = ()
) -> str | None:
    if not isinstance(valor, dict) or valor.get("pais") not in paises():
        return "país desconocido"
    nombre = str(valor["nombre"]).strip()
    if len(nombre) > MAX_LETRAS_NOMBRE:
        return "nombre demasiado largo"
    genericos = contexto.prefijos_genericos if contexto is not None else ()
    fuentes = (frase, *(contexto.textos if contexto is not None else ()), *textos)
    if (
        nombrado_en(nombre, frase)
        or propias_en_fuentes(nombre, fuentes, genericos)
        or (contexto is not None and _es_el_objetivo(nombre, frase, contexto))
    ):
        return None
    return "el nombre no está en la frase"


def _cierre_valido(valor: Any, frase: str) -> str | None:
    """Un cierre sin palabra de cierre en su frase es una suposición del modelo."""
    patrones = palabras_cierre()
    normal = normalizar(frase)
    if patrones["cierre"].search(normal):
        return None
    if valor == "no" and patrones["normalidad"].search(normal):
        return None
    return "la frase no habla de cierre"


def fecha_valida(
    nombre: str, valor: Any, frase: str, publicacion: datetime, ahora: datetime
) -> str | None:
    """Motivo por el que el inicio o el fin no valen, o None. `publicacion`: la de la nota de
    la que sale el dato."""
    momento = leer_fecha(valor) if isinstance(valor, str) else None
    if momento is None:
        return "fecha imposible"
    if momento > ahora:
        return "fecha futura"
    if nombre == "inicio" and momento > publicacion + MARGEN_ARTICULO:
        return "inicio posterior a su nota"
    if (
        nombre == "inicio"
        and momento < publicacion - MAX_ANTELACION
        and not fechas.dia_escrito(str(valor), frase, publicacion)
    ):
        return "inicio más de una semana antes de su nota sin el día escrito"
    return None


def _valor_valido(
    nombre: str, valor: Any, frase: str, contexto: Contexto, fuente: Any = None
) -> str | None:
    """Motivo por el que el valor no vale, o None."""
    if nombre in RANGOS:
        return _rango_valido(nombre, valor)
    if nombre == "pais":
        return None if isinstance(valor, str) and valor in paises() else "país desconocido"
    if nombre == "lugar_nuevo":
        return _lugar_valido(valor)
    if nombre == "lugar_suceso":
        return _suceso_valido(valor, frase, contexto)
    if nombre == "cierre" and valor in {"si", "no"}:
        return _cierre_valido(valor, frase)
    if nombre in {"inicio", "fin"}:
        return fecha_valida(nombre, valor, frase, contexto.publicacion(fuente), contexto.ahora)
    if nombre in {"localidad", "objetivo_nombre", "modelo_dron"}:
        texto_ok = isinstance(valor, str) and 0 < len(valor.strip()) <= MAX_LETRAS_NOMBRE
        return None if texto_ok else "texto vacío o demasiado largo"
    return None


def otro_objetivo(nombre: Any, contexto: Contexto) -> bool:
    """El nombre no comparte ninguna palabra propia con los de la instalación conocida."""
    if not isinstance(nombre, str) or not contexto.palabras_objetivo:
        return False
    propias = {
        p
        for p in normalizar(nombre).split()
        if len(p) >= MIN_LETRAS_PALABRA and not p.startswith(contexto.prefijos_genericos)
    }
    return bool(propias) and not propias & contexto.palabras_objetivo


def validar(ficha: dict[str, Any], contexto: Contexto) -> Validada:
    resultado = Validada(
        titulo_es=str(ficha.get("titulo_es", "")).strip(),
        titulo_en=str(ficha.get("titulo_en", "")).strip(),
        motivos=list(ficha.get("ilegibles", [])),
    )
    for nombre, campo in ficha.items():
        if not isinstance(campo, dict) or campo.get("valor") is None:
            continue
        confianza = campo.get("confianza")
        if not isinstance(confianza, int | float) or not 0 <= confianza <= 1:
            resultado.motivos.append(f"{nombre}: confianza fuera de 0 a 1")
            continue
        if confianza < UMBRAL_CONFIANZA:
            resultado.motivos.append(f"{nombre}: confianza baja")
            continue
        if isinstance(campo.get("frase"), str) and len(campo["frase"].split()) > MAX_PALABRAS_FRASE:
            # Una frase más larga se recorta a sus primeras 25 palabras: sigue siendo cita literal.
            campo = {**campo, "frase": " ".join(campo["frase"].split()[:MAX_PALABRAS_FRASE])}
        motivo = _frase_valida(campo, contexto.textos) or _valor_valido(
            nombre, campo["valor"], str(campo["frase"]), contexto, campo.get("fuente")
        )
        if motivo:
            resultado.motivos.append(f"{nombre}: {motivo}")
            continue
        resultado.campos[nombre] = campo
    # Coherencias entre campos.
    fin, inicio = resultado.valor("fin"), resultado.valor("inicio")
    if (
        fin
        and inicio
        and (leer_fecha(fin) or contexto.ahora) < (leer_fecha(inicio) or contexto.ahora)
    ):
        resultado.campos.pop("fin")
        resultado.motivos.append("fin: anterior al inicio")
    if "cierre_minutos" in resultado.campos and resultado.valor("cierre") != "si":
        resultado.campos.pop("cierre_minutos")
        resultado.motivos.append("cierre_minutos: minutos sin cierre")
    conocido = resultado.valor("objetivo_conocido")
    if conocido is not False and otro_objetivo(resultado.valor("objetivo_nombre"), contexto):
        # «Alarm am Flughafen Leipzig» en un candidato de Núremberg: la instalación que nombra
        # el modelo no es la conocida aunque diga que sí.
        resultado.campos["objetivo_conocido"] = {
            **resultado.campos.get(
                "objetivo_conocido", {"fuente": 1, "frase": "", "confianza": 1.0}
            ),
            "valor": False,
        }
        conocido = False
        resultado.motivos.append("objetivo_nombre: no es la instalación conocida")
    suceso = resultado.valor("lugar_suceso")
    if suceso and resultado.valor("pais") not in {None, suceso["pais"]}:
        resultado.campos.pop("lugar_suceso")
        resultado.motivos.append("lugar_suceso: país distinto del del incidente")
    if conocido is not False and resultado.pais not in {None, contexto.pais_objetivo}:
        # Un dron en Rumanía no ocurre en una base de Alemania: el objetivo conocido no es,
        # pero el suceso sigue siendo del país que dice la ficha.
        resultado.campos["objetivo_conocido"] = {
            **resultado.campos.get(
                "objetivo_conocido", {"fuente": 1, "frase": "", "confianza": 1.0}
            ),
            "valor": False,
        }
        conocido = False
        resultado.motivos.append("objetivo_conocido: el suceso es de otro país")
    nuevo = resultado.valor("lugar_nuevo")
    if conocido is False and nuevo and nuevo["pais"] != resultado.pais:
        resultado.campos.pop("lugar_nuevo")
        resultado.motivos.append("lugar_nuevo: país distinto del del incidente")
    _pais_nombrado(resultado, ficha, contexto.textos)
    if resultado.pais is None:
        resultado.motivos.append("pais: sin país del suceso")
    if not resultado.titulo_es or not resultado.titulo_en:
        resultado.motivos.append("sin título")
    return resultado


def pais_nombrado(pais: str, textos: tuple[str, ...]) -> bool:
    """Alguna fuente nombra el país, en cualquier idioma y declinado («Republicii Moldova»,
    «Estonian airspace»)."""
    return any(nombrado_en(n, texto) for n in nombres_del_pais(pais) for texto in textos)


def _pais_nombrado(resultado: Validada, ficha: dict[str, Any], textos: tuple[str, ...]) -> None:
    """El país que da la ficha vale aunque su frase no esté literal en la fuente, si la fuente
    nombra ese país: el modelo parafrasea a veces la frase, pero el país no lo inventa si la
    fuente lo dice. Solo cuando la ficha no da ningún país válido."""
    campo = ficha.get("pais")
    if resultado.pais is not None or not isinstance(campo, dict):
        return
    valor = campo.get("valor")
    if isinstance(valor, str) and valor in paises() and pais_nombrado(valor, textos):
        resultado.campos["pais"] = campo
        resultado.motivos.append("pais: la fuente nombra el país")


# Motivos con que se rechazó un inicio cuya frase sí estaba en la fuente: solo la ventana de
# fechas, que se comparaba con la primera nota del candidato y no con la suya.
_MOTIVOS_VENTANA = (
    "inicio: inicio posterior al primer artículo",
    "inicio: inicio más de una semana antes del primer artículo",
)


def recuperar_inicio(
    resultado: Validada,
    ficha: dict[str, Any],
    motivos_previos: list[str],
    publicaciones: tuple[datetime, ...],
    ahora: datetime,
) -> None:
    """Vuelve a comprobar con la regla de ahora un inicio rechazado solo por la ventana de
    fechas (su frase y su confianza ya habían pasado): una noticia que vuelve sobre un suceso
    de semanas atrás vale con el día escrito, y la fecha se compara con su propia nota."""
    campo = ficha.get("inicio")
    if "inicio" in resultado.campos or not isinstance(campo, dict):
        return
    if not any(m in motivos_previos for m in _MOTIVOS_VENTANA):
        return
    fuente = campo.get("fuente")
    if not isinstance(fuente, int) or not 1 <= fuente <= len(publicaciones):
        return
    frase = " ".join(str(campo.get("frase") or "").split()[:MAX_PALABRAS_FRASE])
    if fecha_valida("inicio", campo.get("valor"), frase, publicaciones[fuente - 1], ahora):
        return
    resultado.campos["inicio"] = {**campo, "frase": frase}
    resultado.motivos.append("inicio: válido con la ventana de su nota")


def revalidar(
    validada: Validada,
    ficha: dict[str, Any] | None = None,
    textos: tuple[str, ...] = (),
    genericos: tuple[str, ...] = (),
) -> Validada:
    """Repite sobre una ficha ya guardada la comprobación del cierre, que solo necesita la
    frase, por si se validó con reglas anteriores; y, con la ficha en bruto y los textos que
    se guardan (los titulares), acepta el país que la fuente nombra y el lugar del suceso
    cuyas palabras propias están en su frase o en las fuentes."""
    resultado = Validada(
        campos=dict(validada.campos),
        motivos=list(validada.motivos),
        titulo_es=validada.titulo_es,
        titulo_en=validada.titulo_en,
    )
    if ficha is not None:
        _pais_nombrado(resultado, ficha, textos)
        suceso = ficha.get("lugar_suceso")
        if "lugar_suceso" not in resultado.campos and isinstance(suceso, dict):
            frase = str(suceso.get("frase", ""))
            contexto = Contexto(
                textos=textos, pais_objetivo="", primer_articulo=datetime.now(UTC),
                ahora=datetime.now(UTC), prefijos_genericos=genericos,
            )  # fmt: skip
            if genericos and _suceso_valido(suceso.get("valor"), frase, contexto) is None:
                resultado.campos["lugar_suceso"] = suceso
    cierre = resultado.campos.get("cierre")
    if cierre is not None and cierre["valor"] in {"si", "no"}:
        motivo = _cierre_valido(cierre["valor"], str(cierre.get("frase", "")))
        if motivo:
            resultado.campos.pop("cierre")
            resultado.motivos.append(f"cierre: {motivo}")
    if "cierre_minutos" in resultado.campos and resultado.valor("cierre") != "si":
        resultado.campos.pop("cierre_minutos")
    suceso = resultado.valor("lugar_suceso")
    if suceso and resultado.valor("pais") not in {None, suceso["pais"]}:
        resultado.campos.pop("lugar_suceso")
    return resultado
