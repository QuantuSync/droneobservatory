"""Alta y actualización de ataques de la capa de Ucrania a partir de partes leídos."""

import copy
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from almacen.base import Almacen
from esquema import Documento
from proceso.credibilidad import Declaracion, Fiabilidad, Postura, credibilidad
from proceso.estados import Estado, nuevo_estado
from recogida.parte import KYIV, VERSION_PARSER, Instante, ParteLeido
from recogida.telegram import Publicacion

SENTIDO_RU_UA = "RU_UA"
IDIOMA_PARTES = "uk"
TIPO_ATAQUE = "ataque_guerra"


@dataclass(frozen=True)
class Resultado:
    id: str
    nuevo: bool
    cambiado: bool


def instante(momento: datetime, precision: str = "minuto") -> Documento:
    return Instante(momento.astimezone(UTC), precision).documento()


def id_fuente(publicacion: Publicacion) -> str:
    return f"{publicacion.canal}-{publicacion.id}"


def campos_respaldados(leido: ParteLeido) -> list[str]:
    campos = ["periodo", "lanzados", "derribados", "derribados_categoria"]
    campos += ["perdidos_guerra_electronica"]
    campos += ["localizaciones_impacto", "localizaciones_restos"]
    opcionales = {
        "zonas_lanzamiento": leido.zonas_lanzamiento,
        "lugares_impacto": leido.lugares_impacto,
        "lugares_restos": leido.lugares_restos,
        "regiones": leido.regiones,
        "cruces": leido.cruces,
    }
    return campos + [campo for campo, valor in opcionales.items() if valor]


def fuente_parte(publicacion: Publicacion, leido: ParteLeido, config: Documento) -> Documento:
    # Los partes de un mismo canal no son fuentes independientes entre sí:
    # comparten nota a efectos de la regla de credibilidad.
    declaracion = Declaracion(
        nota=config["id"],
        fiabilidad=Fiabilidad(config["fiabilidad"]),
        es_autoridad=config["es_autoridad"],
        postura=Postura.RESPALDA,
    )
    return {
        "id": id_fuente(publicacion),
        "enlace": publicacion.enlace,
        "medio": config["medio"],
        "fecha": instante(publicacion.fecha),
        "idioma": IDIOMA_PARTES,
        "fiabilidad": config["fiabilidad"],
        "credibilidad": int(credibilidad([declaracion])),
        "frase_origen": leido.frase,
        "replicas": 0,
        "campos_respaldados": campos_respaldados(leido),
        "es_autoridad": config["es_autoridad"],
        "interna_fuera_de_ucrania": config["interna_fuera_de_ucrania"],
        "publica": True,
    }


def huella(anterior: str | None, texto: str) -> str:
    """Encadena la huella de cada texto de parte que ha contribuido al ataque."""
    propia = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    return hashlib.sha256(f"{anterior or ''}{propia}".encode()).hexdigest()


def datos_parte(leido: ParteLeido) -> Documento:
    """Campos del ataque que salen del parte."""
    datos: Documento = {
        "periodo": {"inicio": leido.inicio.documento(), "fin": leido.fin.documento()},
        "lanzados": copy.deepcopy(leido.lanzados),
        "zonas_lanzamiento": list(leido.zonas_lanzamiento),
        "derribados": leido.derribados,
        "derribados_categoria": leido.derribados_categoria.value,
        "perdidos_guerra_electronica": leido.perdidos_guerra_electronica,
        "localizaciones_impacto": leido.localizaciones_impacto,
        "localizaciones_restos": leido.localizaciones_restos,
        "lugares_impacto": list(leido.lugares_impacto),
        "lugares_restos": list(leido.lugares_restos),
        "cruces": [{"pais": pais, "numero": numero} for pais, numero in leido.cruces],
        "regiones": [{"region": codigo} for codigo in sorted(leido.regiones)],
    }
    return datos


def nuevo_ataque(
    id_: str, publicacion: Publicacion, leido: ParteLeido, config: Documento, texto: str,
    ahora: datetime,
) -> Documento:  # fmt: skip
    fuente = fuente_parte(publicacion, leido, config)
    publicado = instante(publicacion.fecha)
    estado = nuevo_estado(publicado, fuente["id"])
    # El parte oficial cuenta como confirmación del ataque.
    estado["actual"] = Estado.CONFIRMADO.value
    estado["historial"].append(
        {"estado": Estado.CONFIRMADO.value, "fecha": publicado, "fuente_id": fuente["id"]}
    )
    return {
        "id": id_,
        "tipo": TIPO_ATAQUE,
        "sentido": SENTIDO_RU_UA,
        "estado": estado,
        **datos_parte(leido),
        "fuentes": [fuente],
        "control": {
            "alta": instante(ahora),
            "ultima_actualizacion": instante(ahora),
            "version_extractor": VERSION_PARSER,
            "huella_fuentes": huella(None, texto),
        },
    }


def actualizar(
    ataque: Documento, publicacion: Publicacion, leido: ParteLeido, config: Documento, texto: str,
    ahora: datetime,
) -> Documento:  # fmt: skip
    """Añade el parte al ataque. Las cifras del parte más reciente sustituyen a las anteriores."""
    resultado = copy.deepcopy(ataque)
    fuente = fuente_parte(publicacion, leido, config)
    otras = [f for f in resultado["fuentes"] if f["id"] != fuente["id"]]
    repetida = len(otras) < len(resultado["fuentes"])
    mas_reciente = all(f["fecha"]["valor"] <= fuente["fecha"]["valor"] for f in otras)
    resultado["fuentes"] = sorted([*otras, fuente], key=lambda f: f["fecha"]["valor"])
    if mas_reciente:
        resultado.update(datos_parte(leido))
    control = resultado["control"]
    if not repetida:
        control["huella_fuentes"] = huella(control.get("huella_fuentes"), texto)
    control["version_extractor"] = VERSION_PARSER
    return resultado


def _sin_control(documento: Documento) -> Documento:
    return {k: v for k, v in documento.items() if k != "control"}


def incorporar(
    almacen: Almacen, publicacion: Publicacion, leido: ParteLeido, config: Documento, texto: str,
    ahora: datetime,
) -> Resultado:  # fmt: skip
    """Da de alta el ataque o lo actualiza si ya existe (mismo parte o mismo periodo declarado)."""
    existente = almacen.ataque_con_fuente(id_fuente(publicacion)) or almacen.ataque_con_periodo(
        SENTIDO_RU_UA, leido.inicio.documento()["valor"]
    )
    if existente is None:
        anio = leido.fin.valor.astimezone(KYIV).year
        documento = nuevo_ataque(
            almacen.siguiente_id_ataque(anio), publicacion, leido, config, texto, ahora
        )
        almacen.guardar_ataque_ucrania(documento, ahora)
        return Resultado(documento["id"], nuevo=True, cambiado=True)
    documento = actualizar(existente, publicacion, leido, config, texto, ahora)
    # Reprocesar el mismo parte sin cambios no toca la base.
    cambiado = _sin_control(documento) != _sin_control(existente)
    if cambiado:
        documento["control"]["ultima_actualizacion"] = instante(ahora)
        almacen.guardar_ataque_ucrania(documento, ahora)
    return Resultado(documento["id"], nuevo=False, cambiado=cambiado)
