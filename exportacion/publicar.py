"""Escribe los ficheros públicos a partir de la base: ucrania.json, incidentes.geojson (los
incidentes con punto, para el mapa) e incidentes_sin_ubicacion.json (los que solo se saben a
nivel de país o de región).

El foco térmico de cada impacto (proceso/focos_termicos.py) y las mediciones de cada incidente
(tráfico aéreo y condiciones, proceso/mediciones.py) y la pérdida de luz nocturna de cada ataque
(proceso/luces.py) viven en sus propias tablas y se añaden aquí a su incidente, a su región o a
su ataque antes de exportar. Igual la copia archivada de cada fuente de los incidentes y la marca
de enlace caído (tabla copias_archivadas, recogida/archivo_web.py).

El control de las fichas (recogida/control_fichas.py) deja fuera las fichas nuevas que retiene
(como mucho 6 horas) y añade a lo publicado la traducción de cada cita y la frase que respalda
cada dato verificado (exportacion/citas.py).

Cada fichero se genera por separado: si uno falla, queda el que ya había, los demás se publican
y el fallo queda en el registro (y en `fallidos`, si se pasa). Solo si no se puede generar ninguno
sale el error."""

import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from almacen.base import Almacen
from esquema import Documento
from exportacion.citas import Pendientes, con_traducciones, enriquecer_incidentes
from exportacion.geojson import exportar, exportar_sin_ubicacion
from exportacion.proyeccion import escribir
from exportacion.ucrania import exportar_ucrania
from proceso import impactos_guerra, rectificaciones
from proceso.configuracion import cargar_vocabulario_modelos
from proceso.focos_termicos import con_focos
from proceso.luces import con_luces
from proceso.mediciones import con_mediciones
from proceso.tipo_dron import publico as tipo_dron
from recogida.archivo_web import con_copias_archivadas

# En el servidor, una carpeta fuera del clon (servidor/configuracion.sh): la publicación ya no vive
# en el repositorio. Sin la variable, la carpeta publicacion/ del repositorio.
VARIABLE_DIRECTORIO = "EODI_PUBLICACION_DIRECTORIO"
DIRECTORIO = Path(
    os.environ.get(VARIABLE_DIRECTORIO) or Path(__file__).resolve().parent.parent / "publicacion"
)
UCRANIA = "ucrania.json"
INCIDENTES = "incidentes.geojson"
SIN_UBICACION = "incidentes_sin_ubicacion.json"

registro = logging.getLogger(__name__)


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


def _mas_reciente(elemento: Documento) -> str:
    fechas = [str((f.get("fecha") or {}).get("valor", "")) for f in elemento.get("fuentes", [])]
    return max(fechas, default="")


class NadaPublicado(RuntimeError):
    """No se pudo generar ninguno de los ficheros publicados."""


def sin_retenidos(incidente: Documento, retenidos: frozenset[str]) -> Documento:
    """El incidente sin los sucesos relacionados que el control retiene todavía: su página no
    existe hasta que se publique y el enlace daría 404 (EODI-2025-00066 enlazaba a la 00444,
    retenida, el 20 de octubre de 2026). El enlace vuelve solo cuando se publica."""
    relacionados = incidente.get("relacionados")
    if not relacionados or not any(r.get("id") in retenidos for r in relacionados):
        return incidente
    quedan = [r for r in relacionados if r.get("id") not in retenidos]
    resultado = {k: v for k, v in incidente.items() if k != "relacionados"}
    if quedan:
        resultado["relacionados"] = quedan
    return resultado


def publicar(
    almacen: Almacen,
    ahora: datetime,
    directorio: Path = DIRECTORIO,
    fallidos: list[str] | None = None,
) -> list[Path]:
    """Regenera los ficheros y devuelve los que han cambiado."""
    directorio.mkdir(parents=True, exist_ok=True)
    incidentes, ataques = con_focos(
        almacen.incidentes(), almacen.ataques_ucrania(), almacen.focos_termicos()
    )
    incidentes, ataques = con_mediciones(incidentes, ataques, almacen)
    incidentes = con_tipo_dron(incidentes, almacen.tipos_dron())
    incidentes = con_copias_archivadas(incidentes, almacen.copias_archivadas())
    ataques = con_luces(ataques, almacen.luces_nocturnas())
    vocabulario = modelos(almacen)
    focos = almacen.focos_termicos()
    impactos = [
        {**d, "foco_termico": focos[d["id"]]}
        if d["id"] in focos and impactos_guerra.con_firms(d)
        else d
        for d in almacen.impactos_guerra()
    ]
    from recogida import control_fichas

    retenidos = control_fichas.retenidos(almacen)
    if retenidos:
        registro.info("fichas retenidas por el control: %s", ", ".join(sorted(retenidos)))
    incidentes = [sin_retenidos(i, retenidos) for i in incidentes if i["id"] not in retenidos]
    # El «quién» del primer paso del historial de presencia, con la tabla de autoridades de hoy.
    incidentes = [rectificaciones.con_quien_de_hoy(i) for i in incidentes]
    verificaciones = {
        clave.removeprefix("verificacion:"): decision
        for clave, decision in almacen.controles("verificacion:").items()
    }
    traducciones = almacen.traducciones()
    pendientes = Pendientes()

    def con_citas(documento: Documento, clave: str) -> Documento:
        """Las citas traducidas y la frase que respalda cada dato (exportacion/citas.py). Si
        falla, se publica sin ellas: la web enseña entonces el original."""
        try:
            return _con_citas(documento, clave)
        except Exception:
            registro.exception("%s sin citas traducidas ni respaldos", clave)
            return documento

    def _con_citas(documento: Documento, clave: str) -> Documento:
        if clave == "features":
            enriquecer_incidentes(
                [f["properties"] for f in documento.get("features", [])], verificaciones,
                traducciones, pendientes.europa,
            )  # fmt: skip
        elif clave == "incidentes":
            enriquecer_incidentes(
                documento.get("incidentes", []), verificaciones, traducciones, pendientes.europa
            )
        else:
            # Las más recientes primero: el control traduce lo atrasado en ese orden.
            elementos = [e for capa in ("ataques", "impactos") for e in documento.get(capa, [])]
            elementos.sort(key=_mas_reciente, reverse=True)
            for elemento in elementos:
                con_traducciones(elemento, traducciones, pendientes.ucrania)
        return documento

    documentos: dict[str, Callable[[], Documento]] = {
        UCRANIA: lambda: con_citas(exportar_ucrania(ataques, ahora, impactos), "ucrania"),
        INCIDENTES: lambda: con_citas(exportar(incidentes, ahora, vocabulario), "features"),
        SIN_UBICACION: lambda: con_citas(
            exportar_sin_ubicacion(incidentes, ahora, vocabulario), "incidentes"
        ),
    }
    cambiados = []
    errores: list[str] = []
    for nombre, generar in documentos.items():
        ruta = directorio / nombre
        anterior = ruta.read_bytes() if ruta.exists() else None
        try:
            escribir(generar(), ruta)
        except Exception as error:
            # Queda el fichero que ya había (escribir lo sustituye de una vez): los demás siguen.
            registro.exception("%s sin generar: queda el anterior", nombre)
            errores.append(f"{nombre}: {error!r}")
            continue
        if ruta.read_bytes() != anterior:
            cambiados.append(ruta)
    # Las citas que se publican sin traducción, para que el control las traduzca (si falla, se
    # publica igual: se vuelven a anotar en la recogida siguiente).
    try:
        control_fichas.anotar_pendientes(almacen, pendientes)
    except Exception:
        registro.exception("citas sin traducir sin anotar")
    if fallidos is not None:
        fallidos.extend(errores)
    if len(errores) == len(documentos):
        raise NadaPublicado("; ".join(errores))
    return cambiados
