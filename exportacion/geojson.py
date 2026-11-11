"""Genera incidentes.geojson para la web y el fichero de los incidentes sin punto.

Solo se dibujan en el mapa los incidentes con un punto dentro de su país. Los que
solo se saben a nivel de país o de región van a incidentes_sin_ubicacion.json, con
su país y su región. Los retirados y los fundidos en otro no salen en ninguno; el GeoJSON
lleva además, en «unidos», a qué incidente publicado fue a parar cada identificador fundido
(la web redirige su dirección a la del que queda).
"""

import logging
from collections.abc import Callable, Iterable
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
from proceso import cita_titular, coherencia, fechas, nombres_lugar, regiones_aproximadas
from proceso.estados import Capa
from proceso.focos_termicos import solo_detectado
from proceso.mediciones import solo_publico
from proceso.validaciones import errores_ubicacion, validar_incidente

registro = logging.getLogger(__name__)


def campos_fuera_de_lista(coleccion: Documento) -> list[str]:
    return fuera_de_lista(
        [f["properties"] for f in coleccion["features"]], CAMPOS_PUBLICOS_INCIDENTE
    )


def con_nombres(documento: Documento) -> Documento:
    """El documento con los nombres de lugar de cada versión de la web (`nombres`) y el titular
    escrito con ellos (proceso/nombres_lugar.py). Lo que aun así la revisión da por mal escrito
    no se publica: la ficha cae entonces en lo seguro (el titular, la localidad o el país)."""
    documento["titulo"] = nombres_lugar.titulo_corregido(documento)
    for idioma, texto in documento["titulo"].items():
        repetida = nombres_lugar.palabra_repetida(str(texto or ""))
        if repetida:
            registro.warning(
                "%s: titular %s con palabra repetida «%s»", documento.get("id"), idioma, repetida
            )
    nombres = nombres_lugar.nombres_publicos(documento)
    pais = documento["lugar"].get("pais")
    for campo in ("objetivo", "region", "localidad"):
        valor = nombres.get(campo)
        if valor is not None and any(
            nombres_lugar.problemas_texto(valor[i], i, pais) for i in nombres_lugar.IDIOMAS
        ):
            registro.warning("%s: nombre sin publicar (%s): %s", documento.get("id"), campo, valor)
            del nombres[campo]
    for lista in ("otros", "anteriores"):
        nombres_lista = nombres.get(lista) or []
        for i, valor in enumerate(nombres_lista):
            if valor is not None and any(
                nombres_lugar.problemas_texto(valor[j], j, pais) for j in nombres_lugar.IDIOMAS
            ):
                registro.warning(
                    "%s: nombre sin publicar (%s): %s", documento.get("id"), lista, valor
                )
                nombres_lista[i] = None
    if "localidad" not in nombres:
        # Sin localidad publicable, la región si la hay y se puede publicar; si no, el país.
        nombres["lugar"] = nombres_lugar.lugar_con_pais(nombres.get("region"), documento)
    documento["nombres"] = nombres
    for problema in nombres_lugar.problemas(documento):
        registro.warning("%s: %s", documento.get("id"), problema)
    return documento


def feature(incidente: Documento) -> Documento | None:
    """Feature pública del incidente, o None si ninguna de sus fuentes es pública."""
    documento = con_afirmaciones(incidente)
    if documento is None:
        return None
    documento = con_nombres(coherencia.coherente(documento))
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
    # Un fin que ninguna frase escribe no se publica (proceso/fechas.sin_fin_sin_frase).
    fechas.sin_fin_sin_frase(documento)
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
    documento = con_nombres(coherencia.coherente(documento))
    # El centro de la región que nombra la fuente, para el marcador aproximado de la web.
    documento["lugar"] = regiones_aproximadas.con_centro(documento["lugar"])
    proyectado: Documento = proyectar(documento, CAMPOS_PUBLICOS_SIN_UBICACION)
    return proyectado


def publicables(
    incidentes: Iterable[Documento],
    ahora: datetime,
    vocabulario_modelos: frozenset[str],
    apartados: dict[str, str] | None = None,
) -> list[Documento]:
    """Los incidentes que se publican, validados. Un punto fuera de su país no se publica:
    queda en el registro de la ejecución con el motivo.

    Con `apartados`, cada ficha va aislada (docs/ciclo_de_vida.md): la que no se puede publicar
    queda apuntada ahí con su motivo y las demás siguen; la puerta de la publicación deja entonces
    su última versión publicada. Sin él, una ficha que no valida para la exportación entera."""
    resultado = []
    for incidente in incidentes:
        # Un incidente fundido en otro sale dentro de aquel; uno retirado no sale.
        if "fusionado_en" in incidente or "retirado" in incidente:
            continue
        try:
            motivo = _no_publicable(incidente, ahora, vocabulario_modelos)
        except Exception as error:
            if apartados is None:
                raise
            motivo = f"no se pudo preparar: {error!r}"[:200]
        if motivo is None:
            resultado.append(incidente)
            continue
        if apartados is None and motivo.startswith(NO_VALIDA):
            raise ExportacionInvalida(f"{incidente.get('id')}: {motivo.removeprefix(NO_VALIDA)}")
        registro.warning("%s no se publica: %s", incidente.get("id"), motivo)
        if apartados is not None:
            apartados[str(incidente.get("id"))] = motivo
    return resultado


NO_VALIDA = "no valida: "


def _no_publicable(
    incidente: Documento, ahora: datetime, vocabulario_modelos: frozenset[str]
) -> str | None:
    """Por qué no se publica el incidente tal como está, o None si se publica."""
    # El titular no puede afirmar lo que sus citas publicadas no dicen: si ninguna lo
    # respalda (y no está revisado y justificado a mano), no se publica hasta que se revise
    # (proceso/cita_titular.py). Un parte de guerra solo no es autoridad sobre otro país.
    publico = vista_publica(incidente)
    if publico is not None and not cita_titular.publicable(publico):
        return "su cita no respalda el titular"
    fuera = errores_ubicacion(incidente)
    if fuera:
        return str(fuera[0].mensaje)
    errores = validar_incidente(incidente, ahora, vocabulario_modelos)
    if errores:
        return f"{NO_VALIDA}{errores[0].mensaje}"
    return None


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


def _aislada(
    incidente: Documento,
    preparar: Callable[[Documento], Documento | None],
    campos: frozenset[str],
    apartados: dict[str, str] | None,
) -> Documento | None:
    """La entrada pública del incidente. Con `apartados`, la que falla o trae un campo fuera de
    la lista queda apuntada y no sale, sin parar a las demás."""
    if apartados is None:
        return preparar(incidente)
    try:
        publicado = preparar(incidente)
        if publicado is None:
            apartados[str(incidente.get("id"))] = "ninguna de sus fuentes es pública"
            return None
        sobrantes = fuera_de_lista([publicado.get("properties", publicado)], campos)
        if sobrantes:
            raise ExportacionInvalida(f"campos fuera de la lista: {sobrantes}")
    except Exception as error:
        registro.exception("%s no se publica: su entrada no se pudo preparar", incidente.get("id"))
        apartados[str(incidente.get("id"))] = f"no se pudo preparar: {error!r}"[:200]
        return None
    return publicado


def exportar(
    incidentes: Iterable[Documento],
    ahora: datetime,
    vocabulario_modelos: frozenset[str],
    apartados: dict[str, str] | None = None,
) -> Documento:
    incidentes = list(incidentes)
    features = []
    validos = publicables(incidentes, ahora, vocabulario_modelos, apartados)
    for incidente in validos:
        if "punto" not in incidente["lugar"]:
            continue
        publicado = _aislada(incidente, feature, CAMPOS_PUBLICOS_INCIDENTE, apartados)
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
    incidentes: Iterable[Documento],
    ahora: datetime,
    vocabulario_modelos: frozenset[str],
    apartados: dict[str, str] | None = None,
) -> Documento:
    """Los incidentes sin punto, con su país y, si se sabe, su región."""
    lista = [
        publicado
        for incidente in publicables(incidentes, ahora, vocabulario_modelos, apartados)
        if "punto" not in incidente["lugar"]
        and (
            publicado := _aislada(
                incidente, sin_ubicacion, CAMPOS_PUBLICOS_SIN_UBICACION, apartados
            )
        )
        is not None
    ]
    sobrantes = fuera_de_lista(lista, CAMPOS_PUBLICOS_SIN_UBICACION)
    if sobrantes:
        raise ExportacionInvalida(f"campos fuera de la lista: {sobrantes}")
    return {"incidentes": sorted(lista, key=lambda i: str(i["id"]))}
