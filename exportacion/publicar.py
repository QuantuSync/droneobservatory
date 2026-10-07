"""Escribe los ficheros públicos a partir de la base: ucrania.json, incidentes.geojson (los
incidentes con punto, para el mapa) e incidentes_sin_ubicacion.json (los que solo se saben a
nivel de país o de región).

El foco térmico de cada impacto (proceso/focos_termicos.py) y las mediciones de cada incidente
(tráfico aéreo y condiciones, proceso/mediciones.py) y la pérdida de luz nocturna de cada ataque
(proceso/luces.py) viven en sus propias tablas y se añaden aquí a su incidente, a su región o a
su ataque antes de exportar."""

from datetime import datetime
from pathlib import Path

from almacen.base import Almacen
from esquema import Documento
from exportacion.geojson import exportar, exportar_sin_ubicacion
from exportacion.proyeccion import escribir
from exportacion.ucrania import exportar_ucrania
from proceso import impactos_guerra
from proceso.configuracion import cargar_vocabulario_modelos
from proceso.focos_termicos import con_focos
from proceso.luces import con_luces
from proceso.mediciones import con_mediciones
from proceso.tipo_dron import publico as tipo_dron

DIRECTORIO = Path(__file__).resolve().parent.parent / "publicacion"
UCRANIA = "ucrania.json"
INCIDENTES = "incidentes.geojson"
SIN_UBICACION = "incidentes_sin_ubicacion.json"


def modelos(almacen: Almacen) -> frozenset[str]:
    """El vocabulario de modelos de la configuración más el que ha crecido con el uso."""
    return cargar_vocabulario_modelos() | frozenset(almacen.vocabulario("modelo_dron"))


def con_tipo_dron(incidentes: list[Documento], tipos: dict[str, Documento]) -> list[Documento]:
    """Cada incidente con lo que se publica de su tipo de dron (tabla tipos_dron)."""
    salida = []
    for incidente in incidentes:
        tipo = tipos.get(incidente["id"])
        publicado = tipo_dron.bloque(tipo, incidente)
        nuevo = {**incidente, "tipo_dron": publicado} if publicado else dict(incidente)
        recorrido = tipo_dron.recorrido_publico(tipo, incidente)
        if recorrido is not None:
            nuevo["recorrido"] = recorrido
        salida.append(nuevo)
    return salida


def publicar(almacen: Almacen, ahora: datetime, directorio: Path = DIRECTORIO) -> list[Path]:
    """Regenera los ficheros y devuelve los que han cambiado."""
    directorio.mkdir(parents=True, exist_ok=True)
    incidentes, ataques = con_focos(
        almacen.incidentes(), almacen.ataques_ucrania(), almacen.focos_termicos()
    )
    incidentes, ataques = con_mediciones(incidentes, ataques, almacen)
    incidentes = con_tipo_dron(incidentes, almacen.tipos_dron())
    ataques = con_luces(ataques, almacen.luces_nocturnas())
    vocabulario = modelos(almacen)
    focos = almacen.focos_termicos()
    impactos = [
        {**d, "foco_termico": focos[d["id"]]}
        if d["id"] in focos and impactos_guerra.con_firms(d)
        else d
        for d in almacen.impactos_guerra()
    ]
    documentos = {
        UCRANIA: exportar_ucrania(ataques, ahora, impactos),
        INCIDENTES: exportar(incidentes, ahora, vocabulario),
        SIN_UBICACION: exportar_sin_ubicacion(incidentes, ahora, vocabulario),
    }
    cambiados = []
    for nombre, documento in documentos.items():
        ruta = directorio / nombre
        anterior = ruta.read_bytes() if ruta.exists() else None
        escribir(documento, ruta)
        if ruta.read_bytes() != anterior:
            cambiados.append(ruta)
    return cambiados
