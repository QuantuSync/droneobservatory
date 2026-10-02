"""Cruces a países de la OTAN: ¿pudo un señuelo sin guiado derivar con el viento hasta el punto
de caída, o la trayectoria exige un rumbo deliberado?

Hipótesis de deriva: el dron pierde el guiado al salir del territorio de las partes en guerra
(Ucrania, Rusia o Bielorrusia; se toma el punto de su frontera más cercano al de caída) y desde
ahí lo lleva el viento: su desplazamiento neto es el del aire. Con el viento medido en su banda
de vuelo (niveles de presión del lugar de caída a la hora del incidente):

- compatible con deriva: el punto de caída queda a sotavento del de salida (la dirección del
  desplazamiento se aparta del viento menos de 45° más la dispersión de las direcciones medidas
  en la banda) y a una distancia que el viento cubre en el tiempo máximo de vuelo de la clase;
- no compatible con deriva: el desplazamiento va contra el viento (90° o más, más la
  dispersión) o es más largo de lo que el viento recorre en ese tiempo con un 10 % de margen:
  hizo falta volar con un rumbo propio;
- indeterminado: viento flojo (menos de 2 m/s), sin dirección (solo el día), direcciones de la
  banda repartidas en más de 45°, punto a menos de 5 km de la frontera o en la franja intermedia.

Solo se evalúa en los países de la OTAN y con el punto de caída a 200 km o menos del territorio
de las partes: más lejos no es un cruce desde la guerra.
"""

import math
from dataclasses import dataclass
from typing import Any

from proceso.deduccion import capacidades, geo, viento
from proceso.deduccion.catalogo import Catalogo

VERSION = ("deriva", "1.0.0")
ORIGENES = ("UA", "RU", "BY")
TOLERANCIA_GRADOS = 45.0
CONTRA_GRADOS = 90.0
VIENTO_MINIMO_MS = 2.0
# Solo es un cruce desde la guerra si el punto de caída está cerca del territorio de las partes:
# más lejos (Bélgica, Dinamarca, Alemania...) la pregunta de la deriva no tiene sentido.
DISTANCIA_MAXIMA_KM = 200.0
# Más cerca de la frontera que esto, el desplazamiento cabe en la incertidumbre del punto.
DISTANCIA_MINIMA_KM = 5.0
# Con las direcciones de la banda más repartidas que esto, el viento no tiene una dirección
# dominante con que comparar el desplazamiento.
DISPERSION_MAXIMA_GRADOS = 45.0
MARGEN_DISTANCIA = 0.10
# Países de la OTAN de la recogida (a 1 de octubre de 2026).
OTAN = frozenset(
    {
        "AL",
        "BE",
        "BG",
        "CA",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GB",
        "GR",
        "HR",
        "HU",
        "IS",
        "IT",
        "LT",
        "LU",
        "LV",
        "ME",
        "MK",
        "NL",
        "NO",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
        "TR",
        "US",
    }
)

COMPATIBLE = "compatible_con_deriva"
NO_COMPATIBLE = "no_compatible_con_deriva"
INDETERMINADO = "indeterminado"


@dataclass(frozen=True)
class Deriva:
    resultado: str
    motivo: str
    datos: dict[str, Any]

    def documento(self) -> dict[str, Any]:
        return {
            "regla": VERSION[0],
            "version": VERSION[1],
            "resultado": self.resultado,
            "motivo": self.motivo,
            "datos": self.datos,
        }


def _dispersión(lista: list[viento.Lectura], medio: float) -> float:
    direcciones = [x.direccion for x in lista if x.direccion is not None]
    if not direcciones:
        return 0.0
    return max(geo.diferencia_angular(d, medio) for d in direcciones)


def evaluar(
    catalogo: Catalogo, clase: str, lat: float, lon: float, lugar: dict[str, Any] | None
) -> Deriva | None:
    """None si el punto queda a más de DISTANCIA_MAXIMA_KM del territorio de las partes."""
    origen_pais, origen = None, None
    mejor = math.inf
    for pais in ORIGENES:
        punto = geo.punto_mas_cercano(pais, lat, lon)
        if punto is None:
            continue
        d = geo.distancia_km(punto[0], punto[1], lat, lon)
        if d < mejor:
            mejor, origen, origen_pais = d, punto, pais
    if origen is None or mejor > DISTANCIA_MAXIMA_KM:
        return None
    datos: dict[str, Any] = {
        "origen_pais": origen_pais,
        "origen": [round(origen[0], 4), round(origen[1], 4)],
        "distancia_km": round(mejor, 1),
        "rumbo_desplazamiento": round(geo.rumbo(origen[0], origen[1], lat, lon), 1),
        "clase": clase,
    }
    tipica = catalogo.envolvente(clase, "altura_tipica")
    banda = viento.en_banda(viento.lecturas(lugar), tipica.minimo, tipica.maximo)
    medio = viento.medio(banda)
    if medio is None:
        return Deriva(INDETERMINADO, "sin dirección del viento (solo el día o sin medida)", datos)
    velocidad = math.hypot(*medio)
    hacia = (math.degrees(math.atan2(medio[0], medio[1])) + 360.0) % 360.0
    dispersion = _dispersión(banda, (hacia + 180.0) % 360.0)
    datos.update(
        {
            "viento_ms": round(velocidad, 1),
            "viento_hacia": round(hacia, 1),
            "dispersion_grados": round(dispersion, 1),
            "niveles": [x.nombre for x in banda],
        }
    )
    if velocidad < VIENTO_MINIMO_MS:
        return Deriva(INDETERMINADO, "viento flojo: no empuja en ninguna dirección", datos)
    if dispersion > DISPERSION_MAXIMA_GRADOS:
        return Deriva(INDETERMINADO, "viento sin una dirección dominante en la banda", datos)
    if mejor < DISTANCIA_MINIMA_KM:
        return Deriva(
            INDETERMINADO, "pegado a la frontera: el desplazamiento no se distingue", datos
        )
    desvio = geo.diferencia_angular(datos["rumbo_desplazamiento"], hacia)
    datos["desvio_grados"] = round(desvio, 1)
    if desvio >= CONTRA_GRADOS + dispersion:
        return Deriva(NO_COMPATIBLE, "el desplazamiento va contra el viento", datos)
    tiempo = capacidades.de_clase(catalogo, clase, capacidades.tiempo_max_min)
    maximo = max(x.velocidad_ms for x in banda)
    if tiempo.valor is not None:
        cubre = maximo * tiempo.valor * 60.0 / 1000.0
        datos["viento_cubre_km"] = round(cubre, 1)
        datos["tiempo_max_min"] = round(tiempo.valor, 1)
        al_alcance = mejor <= cubre * (1 + MARGEN_DISTANCIA)
        # Más lejos de lo que el viento lleva a cualquier modelo de la clase (hace falta la
        # cota de todos): no es deriva.
        if not al_alcance and tiempo.sirve:
            return Deriva(NO_COMPATIBLE, "más lejos de lo que el viento lo lleva", datos)
        # A sotavento y al alcance del viento con algún modelo de la clase.
        if al_alcance and desvio <= TOLERANCIA_GRADOS + dispersion:
            return Deriva(COMPATIBLE, "a sotavento y al alcance del viento", datos)
    return Deriva(INDETERMINADO, "ni a favor ni en contra del viento", datos)
