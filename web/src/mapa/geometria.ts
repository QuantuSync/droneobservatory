// Geometría de las capas propias del mapa: los símbolos de los incidentes (agrupados cuando
// comparten punto), el área de precisión de cada uno y las líneas de los episodios.

import type { Feature, FeatureCollection, LineString, Point, Polygon } from "geojson";

import { indiceBandera, varianteConjunta, varianteDe } from "../banderas.ts";
import { esGrave } from "../datos/derivar.ts";
import type {
  EpisodioResumen,
  Estado,
  FilaImpacto,
  FocoRegion,
  IncidenteResumen,
} from "../datos/tipos.ts";
import { anchoDeCorredor, arco, opacidadDePerdida } from "../datos/guerraSatelite.ts";
import type {
  CiudadAlumbrado,
  CiudadSinLuz,
  Corredor,
  PuntoSatelite,
} from "../datos/guerraSatelite.ts";
import { GRAVEDAD } from "../paleta.ts";
import { incidenteEnPeriodo } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";

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

/** Nombre del icono de un estado: el tipo no cambia el símbolo. */
export function nombreIcono(estado: string): string {
  return `incidente-${estado}`;
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
  estado: Estado;
  icono: string;
  /** 1 si el representante está confirmado o atribuido: se dibuja encima y late. */
  grave: 0 | 1;
  atribuido: 0 | 1;
  /** Cuántos hay de cada estado, para el color de los grupos al alejar. */
  n_confirmados: number;
  n_notificados: number;
  /** 1 si alguno empezó en las últimas 24 horas. */
  reciente: 0 | 1;
  /** 1 si alguno cambió desde la visita anterior. */
  novedad: 0 | 1;
  /** 1 si alguno tiene un foco térmico detectado por satélite. */
  foco: 0 | 1;
  /**
   * Marcador de los atribuidos del punto (banderas.ts): índice de la bandera común (-1 sin
   * bandera o de países distintos) y 1 si todos son personas.
   */
  bandera: number;
  persona: 0 | 1;
}

/**
 * Un símbolo por punto. Varios incidentes en el mismo sitio se pisaban: se dibuja el más
 * grave con el número de incidentes.
 */
export function pilas(
  incidentes: readonly IncidenteResumen[],
  opciones: { recientes: Periodo; novedades: ReadonlySet<string> },
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
    const marcador = varianteConjunta(
      ordenados.filter((i) => i.estado === "atribuido").map((i) => varianteDe(i.atribucion)),
    );
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [primero.punto.lon, primero.punto.lat] },
      properties: {
        id: primero.id,
        ids: ordenados.map((i) => i.id).join(","),
        n: ordenados.length,
        estado: primero.estado,
        icono: nombreIcono(primero.estado),
        grave: esGrave(primero.estado) ? 1 : 0,
        atribuido: primero.estado === "atribuido" ? 1 : 0,
        n_confirmados: cuenta("confirmado"),
        n_notificados: cuenta("notificado"),
        reciente: ordenados.some((i) => incidenteEnPeriodo(i, opciones.recientes)) ? 1 : 0,
        novedad: ordenados.some((i) => opciones.novedades.has(i.id)) ? 1 : 0,
        foco: ordenados.some((i) => i.foco) ? 1 : 0,
        bandera: indiceBandera(marcador.bandera),
        persona: marcador.persona ? 1 : 0,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

/**
 * Un marcador por punto con atribuidos: no se juntan con los círculos ni con sus grupos, para
 * que el estado más grave siempre esté a la vista. Varios atribuidos en el mismo punto exacto
 * son un solo marcador con su número (y una lista para elegir); los cercanos los junta la
 * agrupación propia de los atribuidos al alejar.
 */
export function atribuidos(
  incidentes: readonly IncidenteResumen[],
  opciones: { recientes: Periodo; novedades: ReadonlySet<string> },
): FeatureCollection<Point, PropiedadesPila> {
  return pilas(
    incidentes.filter((i) => i.estado === "atribuido"),
    opciones,
  );
}

/** Lo que va en círculos y grupos: todo menos los atribuidos, que llevan su marcador. */
export function sinAtribuidos(incidentes: readonly IncidenteResumen[]): IncidenteResumen[] {
  return incidentes.filter((i) => i.estado !== "atribuido");
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
  /** 1 si tiene información de satélite: el grupo que lo contiene lo señala. */
  satelite: 0 | 1;
}

/** Los impactos con lugar del periodo como puntos para la fuente agrupada del mapa. */
export function impactosEnMapa(
  filas: readonly FilaImpacto[],
  conSatelite: ReadonlySet<string> = new Set(),
): FeatureCollection<Point, PropiedadesImpacto> {
  return {
    type: "FeatureCollection",
    features: filas.map(([id, , sentido, lon, lat, foco, parte]) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: { id, sentido, foco, parte, satelite: conSatelite.has(id) ? 1 : 0 },
    })),
  };
}

export interface PropiedadesSatelite {
  id: string;
  imagen: 0 | 1;
  foco: 0 | 1;
}

/** Los impactos con información de satélite, sin agrupar: se ven siempre, por encima. */
export function impactosConSateliteEnMapa(
  puntos: readonly PuntoSatelite[],
): FeatureCollection<Point, PropiedadesSatelite> {
  return {
    type: "FeatureCollection",
    features: puntos
      .filter((p) => p.clase === "impacto")
      // Los de imagen, al final: quedan encima.
      .sort((a, b) => Number(a.imagen) - Number(b.imagen))
      .map((p) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        properties: { id: p.clave, imagen: p.imagen ? 1 : 0, foco: p.foco ? 1 : 0 },
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

export interface PropiedadesCorredor {
  clave: string;
  ancho: number;
  drones: number;
}

/** Los corredores del periodo como arcos, con el grosor según sus drones. */
export function corredoresEnMapa(
  corredores: readonly Corredor[],
): FeatureCollection<LineString, PropiedadesCorredor> {
  const maximo = Math.max(0, ...corredores.map((c) => c.drones));
  return {
    type: "FeatureCollection",
    // Los gruesos al final: quedan encima de los finos.
    features: [...corredores]
      .sort((a, b) => a.drones - b.drones)
      .map((c) => ({
        type: "Feature",
        geometry: { type: "LineString", coordinates: arco(c.desde, c.hasta) },
        properties: { clave: c.clave, ancho: anchoDeCorredor(c.drones, maximo), drones: c.drones },
      })),
  };
}

export interface PropiedadesCiudadLuz {
  clave: string;
  nombre: string;
  perdida: number;
  opacidad: number;
}

/** Ciudades con pérdida de luz en el periodo. */
export function ciudadesSinLuzEnMapa(
  ciudades: readonly CiudadSinLuz[],
): FeatureCollection<Point, PropiedadesCiudadLuz> {
  return {
    type: "FeatureCollection",
    features: ciudades.map((c) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [c.lon, c.lat] },
      properties: {
        clave: `${c.region}|${c.nombre}`,
        nombre: c.nombre,
        perdida: c.perdida,
        opacidad: opacidadDePerdida(c.perdida),
      },
    })),
  };
}

export interface PropiedadesAlumbrado {
  clave: string;
  nombre: string;
  brillo: number;
}

/** Ciudades con alumbrado reducido de forma permanente. */
export function alumbradoEnMapa(
  ciudades: readonly CiudadAlumbrado[],
): FeatureCollection<Point, PropiedadesAlumbrado> {
  return {
    type: "FeatureCollection",
    features: ciudades.map((c) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [c.ciudad.punto.lon, c.ciudad.punto.lat] },
      properties: { clave: c.ciudad.id, nombre: c.ciudad.nombre, brillo: c.actual.brillo },
    })),
  };
}
