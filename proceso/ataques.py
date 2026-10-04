"""Alta y actualización de ataques de la capa de Ucrania a partir de partes leídos."""

import copy
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from almacen.base import Almacen
from esquema import Documento
from proceso.credibilidad import Declaracion, Fiabilidad, Postura, credibilidad
from proceso.estados import Estado, nuevo_estado
from proceso.zonas_lanzamiento import normalizar_lista
from recogida.parte import Instante, ParteLeido, exacto
from recogida.telegram import Publicacion

SENTIDO_RU_UA = "RU_UA"
SENTIDO_UA_RU = "UA_RU"
TIPO_ATAQUE = "ataque_guerra"


@dataclass(frozen=True)
class Perfil:
    """Lo que distingue a los partes de una fuente al convertirlos en ataques."""

    sentido: str
    idioma: str
    # Zona del canal: da el año del identificador del ataque.
    zona: ZoneInfo
    version_parser: str
    # El parte es la reivindicación de una de las partes en guerra (la Fuerza Aérea de
    # Ucrania o el Ministerio de Defensa ruso); se publica marcado así.
    reivindicacion: bool = False


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
        "regiones_misiles": leido.regiones_misiles,
        "cruces": leido.cruces,
    }
    return campos + [campo for campo, valor in opcionales.items() if valor]


def fuente_parte(
    publicacion: Publicacion, leido: ParteLeido, config: Documento, perfil: Perfil
) -> Documento:
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
        "idioma": perfil.idioma,
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


def _region(codigo: str, leido: ParteLeido) -> Documento:
    region: Documento = {"region": codigo}
    por_region = dict(leido.derribados_por_region)
    if codigo in por_region:
        region["derribados"] = exacto(por_region[codigo])
    return region


def datos_parte(leido: ParteLeido) -> Documento:
    """Campos del ataque que salen del parte."""
    datos: Documento = {
        "periodo": {"inicio": leido.inicio.documento(), "fin": leido.fin.documento()},
        "lanzados": copy.deepcopy(leido.lanzados),
        # Una zona con su nombre normalizado, aunque el parte la escriba de otra forma; lo
        # escrito queda en zonas_lanzamiento_citadas.
        "zonas_lanzamiento": normalizar_lista(leido.zonas_lanzamiento)[0],
        "zonas_lanzamiento_citadas": list(leido.zonas_lanzamiento),
        "derribados": leido.derribados,
        "derribados_categoria": leido.derribados_categoria.value,
        "perdidos_guerra_electronica": leido.perdidos_guerra_electronica,
        "localizaciones_impacto": leido.localizaciones_impacto,
        "localizaciones_restos": leido.localizaciones_restos,
        "lugares_impacto": list(leido.lugares_impacto),
        "lugares_restos": list(leido.lugares_restos),
        "cruces": [{"pais": pais, "numero": numero} for pais, numero in leido.cruces],
        # Los que declara el parte; `cruces` lleva además las incursiones enlazadas
        # (proceso/cruces.py).
        "cruces_parte": [{"pais": pais, "numero": numero} for pais, numero in leido.cruces],
        "regiones": [_region(codigo, leido) for codigo in sorted(leido.regiones)],
        "regiones_misiles": sorted(leido.regiones_misiles),
    }
    if leido.tipos_dron:
        datos["tipos_dron"] = list(leido.tipos_dron)
    return datos


def nuevo_ataque(
    id_: str, publicacion: Publicacion, leido: ParteLeido, config: Documento, texto: str,
    ahora: datetime, perfil: Perfil,
) -> Documento:  # fmt: skip
    fuente = fuente_parte(publicacion, leido, config, perfil)
    publicado = instante(publicacion.fecha)
    estado = nuevo_estado(publicado, fuente["id"])
    # El parte oficial cuenta como confirmación del ataque.
    estado["actual"] = Estado.CONFIRMADO.value
    estado["historial"].append(
        {"estado": Estado.CONFIRMADO.value, "fecha": publicado, "fuente_id": fuente["id"]}
    )
    documento: Documento = {
        "id": id_,
        "tipo": TIPO_ATAQUE,
        "sentido": perfil.sentido,
        "estado": estado,
        **datos_parte(leido),
        "fuentes": [fuente],
        "control": {
            "alta": instante(ahora),
            "ultima_actualizacion": instante(ahora),
            "version_extractor": perfil.version_parser,
            "huella_fuentes": huella(None, texto),
        },
    }
    if perfil.reivindicacion:
        documento["reivindicacion_de_parte"] = True
    return documento


def actualizar(
    ataque: Documento, publicacion: Publicacion, leido: ParteLeido, config: Documento, texto: str,
    perfil: Perfil,
) -> Documento:  # fmt: skip
    """Añade el parte al ataque. Las cifras del parte más reciente sustituyen a las anteriores."""
    resultado = copy.deepcopy(ataque)
    fuente = fuente_parte(publicacion, leido, config, perfil)
    otras = [f for f in resultado["fuentes"] if f["id"] != fuente["id"]]
    repetida = len(otras) < len(resultado["fuentes"])
    mas_reciente = all(f["fecha"]["valor"] <= fuente["fecha"]["valor"] for f in otras)
    resultado["fuentes"] = sorted([*otras, fuente], key=lambda f: f["fecha"]["valor"])
    if mas_reciente:
        resultado.pop("tipos_dron", None)
        resultado.update(datos_parte(leido))
    control = resultado["control"]
    if not repetida:
        control["huella_fuentes"] = huella(control.get("huella_fuentes"), texto)
    control["version_extractor"] = perfil.version_parser
    # Un ataque dado de alta antes de marcar la fuente como parte en guerra la recibe ahora.
    if perfil.reivindicacion:
        resultado["reivindicacion_de_parte"] = True
    return resultado


def _sin_control(documento: Documento) -> Documento:
    return {k: v for k, v in documento.items() if k != "control"}


def incorporar(
    almacen: Almacen, publicacion: Publicacion, leido: ParteLeido, config: Documento, texto: str,
    ahora: datetime, perfil: Perfil,
) -> Resultado:  # fmt: skip
    """Da de alta el ataque o lo actualiza si ya existe (mismo parte o mismo periodo declarado)."""
    existente = almacen.ataque_con_fuente(id_fuente(publicacion)) or almacen.ataque_con_periodo(
        perfil.sentido, leido.inicio.documento()["valor"]
    )
    if existente is None:
        anio = leido.fin.valor.astimezone(perfil.zona).year
        documento = nuevo_ataque(
            almacen.siguiente_id_ataque(anio), publicacion, leido, config, texto, ahora, perfil
        )
        almacen.guardar_ataque_ucrania(documento, ahora)
        return Resultado(documento["id"], nuevo=True, cambiado=True)
    documento = actualizar(existente, publicacion, leido, config, texto, perfil)
    # Reprocesar el mismo parte sin cambios no toca la base.
    cambiado = _sin_control(documento) != _sin_control(existente)
    if cambiado:
        documento["control"]["ultima_actualizacion"] = instante(ahora)
        almacen.guardar_ataque_ucrania(documento, ahora)
    return Resultado(documento["id"], nuevo=False, cambiado=cambiado)


def jornada(periodo: Documento) -> Documento:
    """La noche (o el día) a que pertenece un parte: la regla única de los datos y de la web
    (`jornada` en web/src/datos/ucrania.ts). Noche si el periodo acaba un día UTC después del
    que empieza («noche del 3 al 4 de octubre»); día si empieza y acaba el mismo día UTC. Un
    periodo que acaba más de un día después (un error de la fuente o un resumen) cuenta en la
    noche de su comienzo."""
    desde = date.fromisoformat(periodo["inicio"]["valor"][:10])
    fin = date.fromisoformat(periodo["fin"]["valor"][:10])
    if fin > desde:
        return {"tipo": "noche", "desde": desde.isoformat(),
                "hasta": (desde + timedelta(days=1)).isoformat()}  # fmt: skip
    return {"tipo": "dia", "desde": desde.isoformat(), "hasta": desde.isoformat()}
