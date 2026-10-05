"""Genera incidentes.geojson para la web y el fichero de los incidentes sin punto.

Solo se dibujan en el mapa los incidentes con un punto dentro de su país. Los que
solo se saben a nivel de país o de región van a incidentes_sin_ubicacion.json, con
su país y su región. Los retirados y los fundidos en otro no salen en ninguno; el GeoJSON
lleva además, en «unidos», a qué incidente publicado fue a parar cada identificador fundido
(la web redirige su dirección a la del que queda).
"""

import logging
from collections.abc import Iterable
from datetime import datetime

from esquema import Documento
from exportacion.afirmaciones import afirmaciones_publicas
from exportacion.campos import CAMPOS_PUBLICOS_INCIDENTE, CAMPOS_PUBLICOS_SIN_UBICACION
from exportacion.proyeccion import (
    ExportacionInvalida,
    fuera_de_lista,
    proyectar,
    solo_fuentes_publicas,
)
from proceso import cita_titular
from proceso.estados import Capa
from proceso.focos_termicos import solo_detectado
from proceso.mediciones import solo_publico
from proceso.validaciones import errores_ubicacion, validar_incidente

registro = logging.getLogger(__name__)


def campos_fuera_de_lista(coleccion: Documento) -> list[str]:
    return fuera_de_lista(
        [f["properties"] for f in coleccion["features"]], CAMPOS_PUBLICOS_INCIDENTE
    )


def feature(incidente: Documento) -> Documento | None:
    """Feature pública del incidente, o None si ninguna de sus fuentes es pública."""
    documento = con_afirmaciones(incidente)
    if documento is None:
        return None
    punto = documento["lugar"].pop("punto")
    return {
        "type": "Feature",
        "id": documento["id"],
        "geometry": {"type": "Point", "coordinates": [punto["lon"], punto["lat"]]},
        "properties": proyectar(documento, CAMPOS_PUBLICOS_INCIDENTE),
    }


def con_afirmaciones(incidente: Documento) -> Documento | None:
    """Copia con solo las fuentes públicas, si las hay sus afirmaciones públicas, el foco
    térmico solo si es detectado y el tráfico aéreo solo si hay un cierre medido válido."""
    documento = solo_fuentes_publicas(incidente, Capa.GENERAL)
    if documento is None:
        return None
    solo_detectado(documento)
    solo_publico(documento)
    afirmaciones = afirmaciones_publicas(documento)
    if afirmaciones:
        documento["afirmaciones_publicas"] = afirmaciones
    return documento


def vista_publica(incidente: Documento) -> Documento | None:
    """Lo que se publica del incidente (con las mismas listas de campos que el mapa o que los
    incidentes sin punto): sobre esto se comprueba que la cita respalda el titular, igual que
    la prueba fija lo comprueba sobre los ficheros publicados."""
    documento = con_afirmaciones(incidente)
    if documento is None:
        return None
    campos = (
        CAMPOS_PUBLICOS_INCIDENTE
        if "punto" in documento["lugar"]
        else CAMPOS_PUBLICOS_SIN_UBICACION
    )
    publico: Documento = proyectar(documento, campos)
    publico["id"] = documento["id"]
    return publico


def sin_ubicacion(incidente: Documento) -> Documento | None:
    documento = con_afirmaciones(incidente)
    if documento is None:
        return None
    documento["lugar"].setdefault("nivel", "pais")
    proyectado: Documento = proyectar(documento, CAMPOS_PUBLICOS_SIN_UBICACION)
    return proyectado


def publicables(
    incidentes: Iterable[Documento], ahora: datetime, vocabulario_modelos: frozenset[str]
) -> list[Documento]:
    """Los incidentes que se publican, validados. Un punto fuera de su país no se publica:
    queda en el registro de la ejecución con el motivo."""
    resultado = []
    for incidente in incidentes:
        # Un incidente fundido en otro sale dentro de aquel; uno retirado no sale.
        if "fusionado_en" in incidente or "retirado" in incidente:
            continue
        # El titular no puede afirmar lo que sus citas publicadas no dicen: si ninguna lo
        # respalda (y no está revisado y justificado a mano), no se publica hasta que se revise
        # (proceso/cita_titular.py). Un parte de guerra solo no es autoridad sobre otro país.
        publico = vista_publica(incidente)
        if publico is not None and not cita_titular.publicable(publico):
            registro.warning("%s no se publica: su cita no respalda el titular", incidente["id"])
            continue
        fuera = errores_ubicacion(incidente)
        if fuera:
            registro.warning("%s no se publica: %s", incidente.get("id"), fuera[0].mensaje)
            continue
        errores = validar_incidente(incidente, ahora, vocabulario_modelos)
        if errores:
            raise ExportacionInvalida(f"{incidente.get('id')}: {errores[0].mensaje}")
        resultado.append(incidente)
    return resultado


def unidos(incidentes: Iterable[Documento], publicados: set[str]) -> dict[str, str]:
    """Identificador fundido -> incidente publicado en que acaba (siguiendo la cadena de
    fusiones). Los que acaban en uno retirado o no publicado no salen."""
    destino = {str(i["id"]): str(i["fusionado_en"]) for i in incidentes if "fusionado_en" in i}
    resultado = {}
    for origen in destino:
        actual, vistos = origen, set()
        while actual in destino and actual not in vistos:
            vistos.add(actual)
            actual = destino[actual]
        if actual in publicados:
            resultado[origen] = actual
    return dict(sorted(resultado.items()))


def exportar(
    incidentes: Iterable[Documento], ahora: datetime, vocabulario_modelos: frozenset[str]
) -> Documento:
    incidentes = list(incidentes)
    features = []
    validos = publicables(incidentes, ahora, vocabulario_modelos)
    for incidente in validos:
        if "punto" not in incidente["lugar"]:
            continue
        publicado = feature(incidente)
        if publicado is not None:
            features.append(publicado)
    coleccion: Documento = {
        "type": "FeatureCollection",
        "features": sorted(features, key=lambda f: str(f["id"])),
    }
    fundidos = unidos(incidentes, {str(i["id"]) for i in validos})
    if fundidos:
        coleccion["unidos"] = fundidos
    # Segunda barrera: la proyección ya filtra, pero se comprueba el resultado.
    sobrantes = campos_fuera_de_lista(coleccion)
    if sobrantes:
        raise ExportacionInvalida(f"campos fuera de la lista: {sobrantes}")
    return coleccion


def exportar_sin_ubicacion(
    incidentes: Iterable[Documento], ahora: datetime, vocabulario_modelos: frozenset[str]
) -> Documento:
    """Los incidentes sin punto, con su país y, si se sabe, su región."""
    lista = [
        publicado
        for incidente in publicables(incidentes, ahora, vocabulario_modelos)
        if "punto" not in incidente["lugar"] and (publicado := sin_ubicacion(incidente)) is not None
    ]
    sobrantes = fuera_de_lista(lista, CAMPOS_PUBLICOS_SIN_UBICACION)
    if sobrantes:
        raise ExportacionInvalida(f"campos fuera de la lista: {sobrantes}")
    return {"incidentes": sorted(lista, key=lambda i: str(i["id"]))}
