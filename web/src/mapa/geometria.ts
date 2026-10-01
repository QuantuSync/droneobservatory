// Geometría de las capas propias del mapa: los símbolos de los incidentes (agrupados cuando
// comparten punto), el área de precisión de cada uno y las líneas de los episodios.

import type { Feature, FeatureCollection, LineString, Point, Polygon } from "geojson";

import { esGrave } from "../datos/derivar.ts";
import type {
  EpisodioResumen,
  Estado,
  FilaImpacto,
  FocoRegion,
  IncidenteResumen,
} from "../datos/tipos.ts";
import { GRAVEDAD } from "../paleta.ts";

const RADIO_TERRESTRE_KM = 6371.0088;
/** Lados del polígono que aproxima el círculo: a 50 km de radio el error es inapreciable. */
const LADOS_CIRCULO = 48;
/** Decimales con que se comparan los puntos: los mismos que publica el esquema. */
const DECIMALES_PUNTO = 5;

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

export function nombreIcono(tipo: string, estado: string): string {
  return `${tipo}-${estado}`;
}

/** Los incidentes con punto, que son los únicos que se dibujan. */
export function conPunto(
  incidentes: readonly IncidenteResumen[],
): (IncidenteResumen & { punto: NonNullable<IncidenteResumen["punto"]> })[] {
  return incidentes.filter(
    (i): i is IncidenteResumen & { punto: NonNullable<IncidenteResumen["punto"]> } =>
      i.punto !== null,
  );
}

/** Primero el más grave; a igual gravedad, el más reciente. */
export function ordenPorGravedad(a: IncidenteResumen, b: IncidenteResumen): number {
  return GRAVEDAD[b.estado] - GRAVEDAD[a.estado] || b.dia - a.dia || b.id.localeCompare(a.id);
}

export interface PropiedadesPila {
  /** El incidente que representa la pila: el más grave. */
  id: string;
  /** Todos los incidentes de ese punto, del más grave al menos, separados por comas. */
  ids: string;
  n: number;
  tipo: string;
  estado: Estado;
  icono: string;
  /** 1 si el representante está confirmado o atribuido: se dibuja encima y late. */
  grave: 0 | 1;
  atribuido: 0 | 1;
  /** Cuántos hay de cada estado, para el color de los grupos al alejar. */
  n_atribuidos: number;
  n_confirmados: number;
  n_notificados: number;
  /** 1 si alguno empezó en las últimas 24 horas. */
  reciente: 0 | 1;
  /** 1 si alguno cambió desde la visita anterior. */
  novedad: 0 | 1;
  /** 1 si alguno tiene un foco térmico detectado por satélite. */
  foco: 0 | 1;
}

/**
 * Un símbolo por punto. Varios incidentes en el mismo sitio, con formas distintas, se
 * pisaban y dibujaban figuras que no significan nada (un cuadrado y un rombo encima hacen
 * una estrella de ocho puntas): se dibuja el más grave con el número de incidentes.
 */
export function pilas(
  incidentes: readonly IncidenteResumen[],
  opciones: { hoy: number; novedades: ReadonlySet<string> },
): FeatureCollection<Point, PropiedadesPila> {
  const porPunto = new Map<string, (IncidenteResumen & { punto: { lon: number; lat: number } })[]>();
  for (const incidente of conPunto(incidentes)) {
    const clave = `${incidente.punto.lon.toFixed(DECIMALES_PUNTO)},${incidente.punto.lat.toFixed(DECIMALES_PUNTO)}`;
    const grupo = porPunto.get(clave) ?? [];
    grupo.push(incidente);
    porPunto.set(clave, grupo);
  }
  const features: Feature<Point, PropiedadesPila>[] = [];
  for (const grupo of porPunto.values()) {
    const ordenados = grupo.slice().sort(ordenPorGravedad);
    const primero = ordenados[0];
    if (primero === undefined) continue;
    const cuenta = (estado: Estado) => ordenados.filter((i) => i.estado === estado).length;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [primero.punto.lon, primero.punto.lat] },
      properties: {
        id: primero.id,
        ids: ordenados.map((i) => i.id).join(","),
        n: ordenados.length,
        tipo: primero.tipo,
        estado: primero.estado,
        icono: nombreIcono(primero.tipo, primero.estado),
        grave: esGrave(primero.estado) ? 1 : 0,
        atribuido: primero.estado === "atribuido" ? 1 : 0,
        n_atribuidos: cuenta("atribuido"),
        n_confirmados: cuenta("confirmado"),
        n_notificados: cuenta("notificado"),
        reciente: ordenados.some((i) => i.dia >= opciones.hoy - 1) ? 1 : 0,
        novedad: ordenados.some((i) => opciones.novedades.has(i.id)) ? 1 : 0,
        foco: ordenados.some((i) => i.foco) ? 1 : 0,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export interface PropiedadesArea {
  id: string;
  estado: Estado;
}

export function areas(
  incidentes: readonly IncidenteResumen[],
): FeatureCollection<Polygon, PropiedadesArea> {
  return {
    type: "FeatureCollection",
    features: conPunto(incidentes).map(
      (incidente): Feature<Polygon, PropiedadesArea> => ({
        type: "Feature",
        geometry: circulo(incidente.punto.lon, incidente.punto.lat, incidente.punto.radio_km),
        properties: { id: incidente.id, estado: incidente.estado },
      }),
    ),
  };
}

/** Un punto por región de Ucrania con foco térmico en el periodo, en su centro. */
export function focosDeRegiones(
  focos: readonly FocoRegion[],
): FeatureCollection<Point, { region: string }> {
  const porRegion = new Map<string, [number, number]>();
  for (const foco of focos) porRegion.set(foco.region, foco.centro);
  return {
    type: "FeatureCollection",
    features: [...porRegion].map(([region, centro]) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: centro },
      properties: { region },
    })),
  };
}

/** Propiedades de un impacto con lugar en el mapa: banderas 0/1 que la agrupación suma. */
export interface PropiedadesImpacto {
  id: string;
  sentido: 0 | 1;
  foco: 0 | 1;
  parte: 0 | 1;
}

/** Los impactos con lugar del periodo como puntos para la fuente agrupada del mapa. */
export function impactosEnMapa(
  filas: readonly FilaImpacto[],
): FeatureCollection<Point, PropiedadesImpacto> {
  return {
    type: "FeatureCollection",
    features: filas.map(([id, , sentido, lon, lat, foco, parte]) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: { id, sentido, foco, parte },
    })),
  };
}

/** Una línea por episodio, solo con los incidentes visibles; hacen falta al menos dos. */
export function lineasDeEpisodio(
  episodios: readonly EpisodioResumen[],
  visibles: readonly IncidenteResumen[],
): FeatureCollection<LineString, { id: string }> {
  const porId = new Map(conPunto(visibles).map((incidente) => [incidente.id, incidente]));
  const features: Feature<LineString, { id: string }>[] = [];
  for (const episodio of episodios) {
    const coordenadas = episodio.incidentes
      .map((id) => porId.get(id))
      .filter((incidente) => incidente !== undefined)
      .map((incidente) => [incidente.punto.lon, incidente.punto.lat]);
    if (coordenadas.length < 2) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: coordenadas },
      properties: { id: episodio.id },
    });
  }
  return { type: "FeatureCollection", features };
}
