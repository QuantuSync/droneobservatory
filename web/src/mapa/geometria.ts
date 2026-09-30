// Geometría de las capas propias del mapa: el área de precisión de cada incidente y las
// líneas que unen los incidentes de un mismo episodio.

import type { Feature, FeatureCollection, LineString, Point, Polygon } from "geojson";

import type { EpisodioResumen, IncidenteResumen } from "../datos/tipos.ts";

const RADIO_TERRESTRE_KM = 6371.0088;
/** Lados del polígono que aproxima el círculo: a 50 km de radio el error es inapreciable. */
const LADOS_CIRCULO = 48;

function radianes(grados: number): number {
  return (grados * Math.PI) / 180;
}

function grados(rad: number): number {
  return (rad * 180) / Math.PI;
}

/** Punto a una distancia y un rumbo de otro, sobre la esfera. Devuelve [lon, lat]. */
export function destino(
  lon: number,
  lat: number,
  distanciaKm: number,
  rumbo: number,
): [number, number] {
  const angular = distanciaKm / RADIO_TERRESTRE_KM;
  const lat1 = radianes(lat);
  const lon1 = radianes(lon);
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angular) + Math.cos(lat1) * Math.sin(angular) * Math.cos(rumbo),
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(rumbo) * Math.sin(angular) * Math.cos(lat1),
      Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2),
    );
  return [grados(lon2), grados(lat2)];
}

export function circulo(lon: number, lat: number, radioKm: number): Polygon {
  const anillo: [number, number][] = [];
  for (let i = 0; i < LADOS_CIRCULO; i += 1) {
    anillo.push(destino(lon, lat, radioKm, (2 * Math.PI * i) / LADOS_CIRCULO));
  }
  const primero = anillo[0];
  if (primero !== undefined) anillo.push(primero);
  return { type: "Polygon", coordinates: [anillo] };
}

export interface PropiedadesPunto {
  id: string;
  tipo: string;
  estado: string;
  /** Nombre del icono: forma por tipo y color por estado. */
  icono: string;
}

export function nombreIcono(tipo: string, estado: string): string {
  return `${tipo}-${estado}`;
}

function propiedades(incidente: IncidenteResumen): PropiedadesPunto {
  return {
    id: incidente.id,
    tipo: incidente.tipo,
    estado: incidente.estado,
    icono: nombreIcono(incidente.tipo, incidente.estado),
  };
}

export function puntos(
  incidentes: readonly IncidenteResumen[],
): FeatureCollection<Point, PropiedadesPunto> {
  return {
    type: "FeatureCollection",
    features: incidentes.map(
      (incidente): Feature<Point, PropiedadesPunto> => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [incidente.lon, incidente.lat] },
        properties: propiedades(incidente),
      }),
    ),
  };
}

export function areas(
  incidentes: readonly IncidenteResumen[],
): FeatureCollection<Polygon, PropiedadesPunto> {
  return {
    type: "FeatureCollection",
    features: incidentes.map(
      (incidente): Feature<Polygon, PropiedadesPunto> => ({
        type: "Feature",
        geometry: circulo(incidente.lon, incidente.lat, incidente.radio_km),
        properties: propiedades(incidente),
      }),
    ),
  };
}

/** Una línea por episodio, solo con los incidentes visibles; hacen falta al menos dos. */
export function lineasDeEpisodio(
  episodios: readonly EpisodioResumen[],
  visibles: readonly IncidenteResumen[],
): FeatureCollection<LineString, { id: string }> {
  const porId = new Map(visibles.map((incidente) => [incidente.id, incidente]));
  const features: Feature<LineString, { id: string }>[] = [];
  for (const episodio of episodios) {
    const coordenadas = episodio.incidentes
      .map((id) => porId.get(id))
      .filter((incidente) => incidente !== undefined)
      .map((incidente) => [incidente.lon, incidente.lat]);
    if (coordenadas.length < 2) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: coordenadas },
      properties: { id: episodio.id },
    });
  }
  return { type: "FeatureCollection", features };
}
