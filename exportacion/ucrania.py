"""Genera ucrania.json: ataques de la capa de Ucrania con sus regiones por código ISO 3166-2."""

from collections.abc import Iterable
from datetime import datetime

from esquema import Documento
from exportacion.campos import CAMPOS_PUBLICOS_ATAQUE
from exportacion.proyeccion import (
    ExportacionInvalida,
    fuera_de_lista,
    proyectar,
    solo_fuentes_publicas,
)
from proceso.estados import Capa
from proceso.focos_termicos import solo_detectado
from proceso.validaciones import validar_ataque_ucrania


def campos_fuera_de_lista(publicacion: Documento) -> list[str]:
    return fuera_de_lista(publicacion["ataques"], CAMPOS_PUBLICOS_ATAQUE)


def ataque_publico(ataque: Documento) -> Documento | None:
    """Ataque público, o None si ninguna de sus fuentes es pública."""
    documento = solo_fuentes_publicas(ataque, Capa.UCRANIA)
    if documento is None:
        return None
    documento["regiones"] = sorted(documento.get("regiones", []), key=lambda r: r["region"])
    # El foco térmico de una región sale solo si es detectado.
    for region in documento["regiones"]:
        solo_detectado(region)
    publico: Documento = proyectar(documento, CAMPOS_PUBLICOS_ATAQUE)
    return publico


def exportar_ucrania(ataques: Iterable[Documento], ahora: datetime) -> Documento:
    publicados = []
    for ataque in ataques:
        errores = validar_ataque_ucrania(ataque, ahora)
        if errores:
            raise ExportacionInvalida(f"{ataque.get('id')}: {errores[0].mensaje}")
        publico = ataque_publico(ataque)
        if publico is not None:
            publicados.append(publico)
    publicacion: Documento = {"ataques": sorted(publicados, key=lambda a: str(a["id"]))}
    # Segunda barrera: la proyección ya filtra, pero se comprueba el resultado.
    sobrantes = campos_fuera_de_lista(publicacion)
    if sobrantes:
        raise ExportacionInvalida(f"campos fuera de la lista: {sobrantes}")
    return publicacion
