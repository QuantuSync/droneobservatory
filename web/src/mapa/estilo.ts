// Estilo del mapa: la base de Protomaps, oscura y apagada para que manden los incidentes, y
// las capas propias. Glifos y sprites se sirven desde este mismo sitio; las teselas, desde
// el subdominio de teselas.

import { layers } from "@protomaps/basemaps";
import type { Flavor } from "@protomaps/basemaps";
import type {
  ExpressionSpecification,
  LayerSpecification,
  StyleSpecification,
} from "maplibre-gl";

import { ESTADOS } from "../datos/vocabulario.ts";
import { COLOR_ESTADO, PALETA, TRAZO_DESMENTIDO } from "../paleta.ts";
import type { Idioma } from "../sitio.ts";

export const URL_TESELAS: string =
  (import.meta.env.VITE_TESELAS as string | undefined) ??
  "https://tiles.droneobservatory.eu/europa-z14.pmtiles";

export const FUENTE_BASE = "protomaps";
/** Tierra de Natural Earth para lo que queda fuera del recorte de teselas. */
export const FUENTE_TIERRA = "tierra";
export const FUENTE_PAISES = "paises";
export const FUENTE_PUNTOS = "incidentes";
export const FUENTE_PUNTOS_SUELTOS = "incidentes-sueltos";
export const FUENTE_AREAS = "areas";
export const FUENTE_EPISODIOS = "episodios";
export const FUENTE_SELECCION = "seleccion";
export const FUENTE_REGIONES = "ucrania-regiones";
export const FUENTE_CONTORNO = "ucrania-contorno";

export const CAPA_GRUPOS = "grupos";
export const CAPA_INCIDENTES_GRAVES = "incidentes-graves";
export const CAPA_INCIDENTES_DISCRETOS = "incidentes-discretos";
export const CAPA_REGIONES = "ucrania-relleno";
export const CAPA_REGION_ELEGIDA = "ucrania-elegida";
export const CAPA_PAIS = "pais-resaltado";
export const CAPA_RECIENTES = "recientes";
export const CAPA_SELECCION = "seleccion";
export const CAPA_EPISODIOS = "episodios";

/** Capas que se pueden pulsar, de la de más arriba a la de más abajo. */
export const CAPAS_PULSABLES: readonly string[] = [
  CAPA_INCIDENTES_GRAVES,
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_GRUPOS,
  CAPA_REGIONES,
];

/** Capas propias de cada capa del selector. */
export const CAPAS_DE_INCIDENTES: readonly string[] = [
  "areas-relleno",
  "areas-contorno",
  "areas-contorno-desmentido",
  CAPA_EPISODIOS,
  CAPA_GRUPOS,
  "grupos-numero",
  CAPA_RECIENTES,
  "novedades",
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_INCIDENTES_GRAVES,
  CAPA_SELECCION,
];
export const CAPAS_DE_UCRANIA: readonly string[] = [
  CAPA_REGIONES,
  "ucrania-regiones-linea",
  "ucrania-contorno",
  CAPA_REGION_ELEGIDA,
];
export const CAPAS_DE_DENSIDAD: readonly string[] = ["densidad"];

/** Hasta este zoom los incidentes cercanos se agrupan con su contador. */
export const ZOOM_MAXIMO_AGRUPADO = 5;
const RADIO_DE_AGRUPACION_PX = 44;
/** Zoom desde el que el área de precisión de cada incidente se empieza a ver. */
const ZOOM_AREAS = 4.5;
const ZOOM_AREAS_PLENAS = 6.5;
/** De cerca, el relleno se desvanece para no tapar el terreno (pistas, calles). */
const ZOOM_RELLENO_TENUE = 10;
const ZOOM_SIN_RELLENO = 12.5;
const OPACIDAD_AREA = 0.12;
/** Los notificados, más discretos, no compiten con lo confirmado. */
const OPACIDAD_DISCRETOS = 0.72;
/** Destello fijo de lo de las últimas 24 horas. */
const OPACIDAD_RECIENTE = 0.22;

const FUENTE_TIPOGRAFICA_NUMEROS = ["Noto Sans Medium"];

/** Base apagada: tierra casi del color del fondo y rótulos tenues. */
const TIERRA = "#0b111c";
const TIERRA_MATIZ = "#0d1420";
const AGUA = PALETA.fondo;
const VIA = "#172131";
const VIA_PRINCIPAL = "#223047";
const FRONTERA = "#34445d";
const ROTULO = "#7d8aa0";
const ROTULO_TENUE = "#556277";

const SABOR: Flavor = {
  background: AGUA,
  earth: TIERRA,
  park_a: TIERRA_MATIZ,
  park_b: TIERRA_MATIZ,
  hospital: TIERRA_MATIZ,
  industrial: TIERRA_MATIZ,
  school: TIERRA_MATIZ,
  wood_a: TIERRA_MATIZ,
  wood_b: TIERRA_MATIZ,
  pedestrian: TIERRA_MATIZ,
  scrub_a: TIERRA_MATIZ,
  scrub_b: TIERRA_MATIZ,
  glacier: TIERRA_MATIZ,
  sand: TIERRA,
  beach: TIERRA_MATIZ,
  aerodrome: TIERRA_MATIZ,
  runway: VIA_PRINCIPAL,
  water: AGUA,
  zoo: TIERRA_MATIZ,
  military: TIERRA_MATIZ,
  tunnel_other_casing: TIERRA,
  tunnel_minor_casing: TIERRA,
  tunnel_link_casing: TIERRA,
  tunnel_major_casing: TIERRA,
  tunnel_highway_casing: TIERRA,
  tunnel_other: VIA,
  tunnel_minor: VIA,
  tunnel_link: VIA,
  tunnel_major: VIA,
  tunnel_highway: VIA,
  pier: VIA,
  buildings: TIERRA_MATIZ,
  minor_service_casing: TIERRA,
  minor_casing: TIERRA,
  link_casing: TIERRA,
  major_casing_late: TIERRA,
  highway_casing_late: TIERRA,
  other: VIA,
  minor_service: VIA,
  minor_a: VIA,
  minor_b: VIA,
  link: VIA,
  major_casing_early: TIERRA,
  major: VIA,
  highway_casing_early: TIERRA,
  highway: VIA_PRINCIPAL,
  railway: VIA,
  boundaries: FRONTERA,
  bridges_other_casing: TIERRA,
  bridges_minor_casing: TIERRA,
  bridges_link_casing: TIERRA,
  bridges_major_casing: TIERRA,
  bridges_highway_casing: TIERRA,
  bridges_other: VIA,
  bridges_minor: VIA,
  bridges_link: VIA,
  bridges_major: VIA,
  bridges_highway: VIA_PRINCIPAL,
  roads_label_minor: ROTULO_TENUE,
  roads_label_minor_halo: TIERRA,
  roads_label_major: ROTULO_TENUE,
  roads_label_major_halo: TIERRA,
  ocean_label: ROTULO_TENUE,
  subplace_label: ROTULO_TENUE,
  subplace_label_halo: TIERRA,
  city_label: ROTULO,
  city_label_halo: AGUA,
  state_label: ROTULO_TENUE,
  state_label_halo: TIERRA,
  country_label: ROTULO,
  address_label: ROTULO_TENUE,
  address_label_halo: TIERRA,
  landcover: {
    barren: TIERRA,
    farmland: TIERRA,
    forest: TIERRA_MATIZ,
    glacier: TIERRA_MATIZ,
    grassland: TIERRA,
    scrub: TIERRA_MATIZ,
    urban_area: TIERRA_MATIZ,
  },
};

/** Capas de la base que sobran en un mapa de situación: puntos de interés, escudos, portales. */
const CAPAS_DESCARTADAS: ReadonlySet<string> = new Set([
  "pois",
  "roads_shields",
  "roads_oneway",
  "address_label",
]);

/** Capas de lugares: llevan un solo nombre, en el idioma de la web, sin la segunda línea. */
const CAPAS_DE_LUGARES: ReadonlySet<string> = new Set([
  "places_subplace",
  "places_region",
  "places_locality",
  "places_country",
]);

function nombre(idioma: Idioma): ExpressionSpecification {
  return [
    "coalesce",
    ["get", `name:${idioma}`],
    ["get", "name:en"],
    ["get", "pgf:name"],
    ["get", "name"],
  ];
}

export function capasBase(idioma: Idioma): LayerSpecification[] {
  return layers(FUENTE_BASE, SABOR, { lang: idioma })
    .filter((capa) => !CAPAS_DESCARTADAS.has(capa.id))
    .map((capa) =>
      capa.type === "symbol" && CAPAS_DE_LUGARES.has(capa.id)
        ? { ...capa, layout: { ...capa.layout, "text-field": nombre(idioma) } }
        : capa,
    );
}

/** Color según el estado de un incidente o de una pila. */
const COLOR_POR_ESTADO: ExpressionSpecification = [
  "match",
  ["get", "estado"],
  ...ESTADOS.flatMap((estado) => [estado, COLOR_ESTADO[estado]]),
  PALETA.secundario,
] as unknown as ExpressionSpecification;

/** Color del anillo de un grupo: el del estado más grave que contiene. */
export const COLOR_DE_GRUPO: ExpressionSpecification = [
  "case",
  [">", ["get", "n_atribuidos"], 0],
  COLOR_ESTADO.atribuido,
  [">", ["get", "n_confirmados"], 0],
  COLOR_ESTADO.confirmado,
  [">", ["get", "n_notificados"], 0],
  COLOR_ESTADO.notificado,
  COLOR_ESTADO.desmentido,
];

const ES_DESMENTIDO: ExpressionSpecification = ["==", ["get", "estado"], "desmentido"];
/**
 * Un solo sistema de marcas: todo lo que junta más de un incidente (un grupo de la
 * agrupación o una pila en el mismo punto exacto) es un círculo con su número; un símbolo
 * suelto es siempre un incidente.
 */
const ES_GRUPO: ExpressionSpecification = [
  "any",
  ["has", "point_count"],
  [">", ["coalesce", ["get", "n"], 1], 1],
];
/** Incidentes que junta un círculo: el total de un grupo o el de una pila. */
const CUENTA: ExpressionSpecification = ["coalesce", ["get", "total"], ["get", "n"]];
/** Radio de un círculo según su cuenta: crece con la raíz, entre un mínimo y un máximo legibles. */
export const RADIO_GRUPO_MINIMO = 11;
export const RADIO_GRUPO_MAXIMO = 26;
/** Cuenta (su raíz) a partir de la cual el círculo ya no crece: cien incidentes. */
const RAIZ_CUENTA_MAXIMA = 10;

/** El mismo radio que dibuja el mapa, para quien lo necesite fuera de él (el pulso). */
export function radioDeGrupo(cuenta: number): number {
  const raiz = Math.min(Math.max(Math.sqrt(cuenta), 1), RAIZ_CUENTA_MAXIMA);
  const avance = (raiz - 1) / (RAIZ_CUENTA_MAXIMA - 1);
  return RADIO_GRUPO_MINIMO + avance * (RADIO_GRUPO_MAXIMO - RADIO_GRUPO_MINIMO);
}

const RADIO_DE_GRUPO: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["sqrt", CUENTA],
  1,
  RADIO_GRUPO_MINIMO,
  RAIZ_CUENTA_MAXIMA,
  RADIO_GRUPO_MAXIMO,
];

function opacidadSegunZoom(plena: number): ExpressionSpecification {
  return ["interpolate", ["linear"], ["zoom"], ZOOM_AREAS, 0, ZOOM_AREAS_PLENAS, plena];
}

function capasPropias(acento: string): LayerSpecification[] {
  return [
    {
      id: CAPA_PAIS,
      type: "fill",
      source: FUENTE_PAISES,
      filter: ["==", ["get", "iso"], ""],
      paint: { "fill-color": PALETA.texto, "fill-opacity": 0.07 },
    },
    {
      id: CAPA_REGIONES,
      type: "fill",
      source: FUENTE_REGIONES,
      paint: {
        "fill-color": PALETA.atribuido,
        "fill-opacity": 0,
        "fill-opacity-transition": { duration: 260, delay: 0 },
      },
    },
    {
      id: "ucrania-regiones-linea",
      type: "line",
      source: FUENTE_REGIONES,
      paint: { "line-color": PALETA.atribuido, "line-width": 0.5, "line-opacity": 0.45 },
    },
    {
      id: "ucrania-contorno",
      type: "line",
      source: FUENTE_CONTORNO,
      paint: { "line-color": PALETA.atribuido, "line-width": 1.5, "line-dasharray": [4, 3] },
    },
    {
      id: CAPA_REGION_ELEGIDA,
      type: "line",
      source: FUENTE_REGIONES,
      filter: ["in", ["get", "iso"], ["literal", []]],
      paint: { "line-color": acento, "line-width": 1.2 },
    },
    {
      id: "densidad",
      type: "heatmap",
      source: FUENTE_PUNTOS_SUELTOS,
      paint: {
        "heatmap-weight": ["get", "n"],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 2, 14, 6, 34, 10, 60],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 2, 0.5, 8, 1.4],
        "heatmap-opacity": 0.7,
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(147, 160, 180, 0)",
          0.25,
          "rgba(147, 160, 180, 0.3)",
          0.6,
          "rgba(232, 238, 246, 0.55)",
          1,
          "rgba(232, 238, 246, 0.85)",
        ],
      },
    },
    {
      id: "areas-relleno",
      type: "fill",
      source: FUENTE_AREAS,
      minzoom: ZOOM_AREAS,
      filter: ["!", ES_DESMENTIDO],
      paint: {
        "fill-color": COLOR_POR_ESTADO,
        "fill-opacity": [
          "interpolate",
          ["linear"],
          ["zoom"],
          ZOOM_AREAS,
          0,
          ZOOM_AREAS_PLENAS,
          OPACIDAD_AREA,
          ZOOM_RELLENO_TENUE,
          OPACIDAD_AREA,
          ZOOM_SIN_RELLENO,
          0,
        ],
      },
    },
    {
      id: "areas-contorno",
      type: "line",
      source: FUENTE_AREAS,
      minzoom: ZOOM_AREAS,
      filter: ["!", ES_DESMENTIDO],
      paint: {
        "line-color": COLOR_POR_ESTADO,
        "line-width": 1,
        "line-opacity": opacidadSegunZoom(0.7),
      },
    },
    {
      id: "areas-contorno-desmentido",
      type: "line",
      source: FUENTE_AREAS,
      minzoom: ZOOM_AREAS,
      filter: ES_DESMENTIDO,
      paint: {
        "line-color": PALETA.desmentido,
        "line-width": 1,
        "line-dasharray": [...TRAZO_DESMENTIDO],
        "line-opacity": opacidadSegunZoom(0.7),
      },
    },
    {
      id: CAPA_EPISODIOS,
      type: "line",
      source: FUENTE_EPISODIOS,
      paint: { "line-color": PALETA.texto, "line-width": 1, "line-opacity": 0.55 },
    },
    {
      id: CAPA_GRUPOS,
      type: "circle",
      source: FUENTE_PUNTOS,
      filter: ES_GRUPO,
      paint: {
        "circle-color": PALETA.panelSolido,
        "circle-opacity": 0.92,
        "circle-stroke-color": COLOR_DE_GRUPO,
        "circle-stroke-width": 1.5,
        "circle-radius": RADIO_DE_GRUPO,
      },
    },
    {
      id: "grupos-numero",
      type: "symbol",
      source: FUENTE_PUNTOS,
      filter: ES_GRUPO,
      layout: {
        "text-field": ["to-string", CUENTA],
        "text-font": FUENTE_TIPOGRAFICA_NUMEROS,
        "text-size": 12,
        "text-allow-overlap": true,
      },
      paint: { "text-color": PALETA.texto },
    },
    {
      id: CAPA_RECIENTES,
      type: "circle",
      source: FUENTE_PUNTOS,
      filter: ["all", ["!", ES_GRUPO], ["==", ["get", "reciente"], 1]],
      paint: {
        "circle-radius": 16,
        "circle-color": COLOR_POR_ESTADO,
        "circle-blur": 1,
        "circle-opacity": OPACIDAD_RECIENTE,
      },
    },
    {
      id: "novedades",
      type: "circle",
      source: FUENTE_PUNTOS,
      filter: ["all", ["!", ES_GRUPO], ["==", ["get", "novedad"], 1]],
      paint: {
        "circle-radius": 15,
        "circle-color": "rgba(0, 0, 0, 0)",
        "circle-stroke-color": acento,
        "circle-stroke-width": 1,
        "circle-stroke-opacity": 0.85,
      },
    },
    {
      id: CAPA_INCIDENTES_DISCRETOS,
      type: "symbol",
      source: FUENTE_PUNTOS,
      filter: ["all", ["!", ES_GRUPO], ["==", ["get", "grave"], 0]],
      layout: {
        "icon-image": ["get", "icono"],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
      paint: { "icon-opacity": OPACIDAD_DISCRETOS },
    },
    {
      id: CAPA_INCIDENTES_GRAVES,
      type: "symbol",
      source: FUENTE_PUNTOS,
      filter: ["all", ["!", ES_GRUPO], ["==", ["get", "grave"], 1]],
      layout: {
        "icon-image": ["get", "icono"],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    },
    {
      id: CAPA_SELECCION,
      type: "circle",
      source: FUENTE_SELECCION,
      paint: {
        "circle-radius": 14,
        "circle-color": "rgba(0, 0, 0, 0)",
        "circle-stroke-color": acento,
        "circle-stroke-width": 1.5,
      },
    },
  ];
}

const VACIA = { type: "FeatureCollection" as const, features: [] };

export function estilo(idioma: Idioma, origen: string, acento: string): StyleSpecification {
  const [fondo, ...base] = capasBase(idioma);
  if (fondo === undefined) throw new Error("el estilo base no tiene capas");
  // Bajo las teselas va la tierra de Natural Earth: fuera del recorte de Europa el mapa
  // sigue teniendo costa en lugar de cortarse en línea recta.
  const tierraDeFondo: LayerSpecification = {
    id: "tierra-de-fondo",
    type: "fill",
    source: FUENTE_TIERRA,
    paint: { "fill-color": TIERRA },
  };
  return {
    version: 8,
    glyphs: `${origen}/mapa/fuentes/{fontstack}/{range}.pbf`,
    sprite: `${origen}/mapa/sprites/dark`,
    sources: {
      [FUENTE_BASE]: { type: "vector", url: `pmtiles://${URL_TESELAS}` },
      [FUENTE_TIERRA]: { type: "geojson", data: `${origen}/mapa/tierra.geojson` },
      [FUENTE_PAISES]: { type: "geojson", data: `${origen}/mapa/paises.geojson` },
      [FUENTE_PUNTOS]: {
        type: "geojson",
        data: VACIA,
        cluster: true,
        clusterMaxZoom: ZOOM_MAXIMO_AGRUPADO,
        clusterRadius: RADIO_DE_AGRUPACION_PX,
        clusterProperties: {
          total: ["+", ["get", "n"]],
          n_atribuidos: ["+", ["get", "n_atribuidos"]],
          n_confirmados: ["+", ["get", "n_confirmados"]],
          n_notificados: ["+", ["get", "n_notificados"]],
        },
      },
      [FUENTE_PUNTOS_SUELTOS]: { type: "geojson", data: VACIA },
      [FUENTE_AREAS]: { type: "geojson", data: VACIA },
      [FUENTE_EPISODIOS]: { type: "geojson", data: VACIA },
      [FUENTE_SELECCION]: { type: "geojson", data: VACIA },
      [FUENTE_REGIONES]: { type: "geojson", data: `${origen}/mapa/ucrania-regiones.geojson` },
      [FUENTE_CONTORNO]: { type: "geojson", data: `${origen}/mapa/ucrania-contorno.geojson` },
    },
    layers: [fondo, tierraDeFondo, ...base, ...capasPropias(acento)],
  };
}
