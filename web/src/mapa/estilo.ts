// Estilo del mapa: la base de Protomaps con la paleta del observatorio y las capas propias
// (incidentes, áreas de precisión, episodios, densidad y Ucrania). Glifos y sprites se
// sirven desde este mismo sitio; las teselas, desde el subdominio de teselas.

import { layers } from "@protomaps/basemaps";
import type { Flavor } from "@protomaps/basemaps";
import type {
  ExpressionSpecification,
  LayerSpecification,
  StyleSpecification,
} from "maplibre-gl";

import { ESTADOS } from "../datos/vocabulario.ts";
import { COLOR_ESTADO, GROSOR_CONTORNO, PALETA, TRAZO_DESMENTIDO } from "../paleta.ts";
import type { Idioma } from "../sitio.ts";

export const URL_TESELAS: string =
  (import.meta.env.VITE_TESELAS as string | undefined) ??
  "https://tiles.droneobservatory.eu/europa.pmtiles";

export const FUENTE_BASE = "protomaps";
/** Tierra de Natural Earth para lo que queda fuera del recorte de teselas. */
export const FUENTE_TIERRA = "tierra";
export const FUENTE_PUNTOS = "incidentes";
export const FUENTE_PUNTOS_SUELTOS = "incidentes-sueltos";
export const FUENTE_AREAS = "areas";
export const FUENTE_EPISODIOS = "episodios";
export const FUENTE_SELECCION = "seleccion";
export const FUENTE_REGIONES = "ucrania-regiones";
export const FUENTE_CONTORNO = "ucrania-contorno";

export const CAPA_GRUPOS = "grupos";
export const CAPA_INCIDENTES = "incidentes";
export const CAPA_REGIONES = "ucrania-relleno";
export const CAPA_REGION_ELEGIDA = "ucrania-elegida";

/** Capas propias de cada capa del selector. */
export const CAPAS_DE_INCIDENTES: readonly string[] = [
  "areas-relleno",
  "areas-contorno",
  "areas-contorno-desmentido",
  "episodios",
  CAPA_GRUPOS,
  "grupos-numero",
  CAPA_INCIDENTES,
  "seleccion",
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
const OPACIDAD_AREA = 0.14;

const FUENTE_TIPOGRAFICA_NUMEROS = ["Noto Sans Medium"];

/** Tonos de tierra entre la superficie 1 y la 2 para que el relieve no distraiga. */
const TIERRA = PALETA.superficie1;
const TIERRA_VERDE = "#10233a";
const TIERRA_URBANA = "#12243e";
const VIA = PALETA.linea;
const VIA_PRINCIPAL = "#2f4a73";
const FRONTERA = "#4a6288";
const ROTULO = PALETA.secundario;
const ROTULO_TENUE = "#6c7e97";

const SABOR: Flavor = {
  background: PALETA.fondo,
  earth: TIERRA,
  park_a: TIERRA_VERDE,
  park_b: TIERRA_VERDE,
  hospital: TIERRA_URBANA,
  industrial: TIERRA_URBANA,
  school: TIERRA_URBANA,
  wood_a: TIERRA_VERDE,
  wood_b: TIERRA_VERDE,
  pedestrian: TIERRA_URBANA,
  scrub_a: TIERRA_VERDE,
  scrub_b: TIERRA_VERDE,
  glacier: TIERRA_URBANA,
  sand: TIERRA,
  beach: TIERRA_URBANA,
  aerodrome: TIERRA_URBANA,
  runway: VIA_PRINCIPAL,
  water: PALETA.fondo,
  zoo: TIERRA_VERDE,
  military: TIERRA_URBANA,
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
  buildings: TIERRA_URBANA,
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
  city_label_halo: PALETA.fondo,
  state_label: ROTULO_TENUE,
  state_label_halo: TIERRA,
  country_label: ROTULO,
  address_label: ROTULO_TENUE,
  address_label_halo: TIERRA,
  landcover: {
    barren: TIERRA,
    farmland: TIERRA,
    forest: TIERRA_VERDE,
    glacier: TIERRA_URBANA,
    grassland: TIERRA,
    scrub: TIERRA_VERDE,
    urban_area: TIERRA_URBANA,
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

/** Color según el estado del incidente. */
const COLOR_POR_ESTADO: ExpressionSpecification = [
  "match",
  ["get", "estado"],
  ...ESTADOS.flatMap((estado) => [estado, COLOR_ESTADO[estado]]),
  PALETA.secundario,
] as unknown as ExpressionSpecification;

const ES_DESMENTIDO: ExpressionSpecification = ["==", ["get", "estado"], "desmentido"];

/** Opacidad que crece con el zoom desde cero hasta el valor dado. */
function opacidadSegunZoom(plena: number): ExpressionSpecification {
  return ["interpolate", ["linear"], ["zoom"], ZOOM_AREAS, 0, ZOOM_AREAS_PLENAS, plena];
}

function capasPropias(): LayerSpecification[] {
  return [
    {
      id: CAPA_REGIONES,
      type: "fill",
      source: FUENTE_REGIONES,
      paint: { "fill-color": PALETA.atribuido, "fill-opacity": 0 },
    },
    {
      id: "ucrania-regiones-linea",
      type: "line",
      source: FUENTE_REGIONES,
      paint: { "line-color": PALETA.atribuido, "line-width": 0.5, "line-opacity": 0.5 },
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
      paint: { "line-color": PALETA.dorado, "line-width": 1 },
    },
    {
      id: "densidad",
      type: "heatmap",
      source: FUENTE_PUNTOS_SUELTOS,
      paint: {
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 2, 14, 6, 34, 10, 60],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 2, 0.5, 8, 1.4],
        "heatmap-opacity": 0.7,
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(147, 163, 184, 0)",
          0.25,
          "rgba(147, 163, 184, 0.35)",
          0.6,
          "rgba(237, 232, 218, 0.6)",
          1,
          "rgba(237, 232, 218, 0.9)",
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
        "fill-opacity": opacidadSegunZoom(OPACIDAD_AREA),
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
        "line-width": GROSOR_CONTORNO,
        "line-opacity": opacidadSegunZoom(1),
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
        "line-width": GROSOR_CONTORNO,
        "line-dasharray": [...TRAZO_DESMENTIDO],
        "line-opacity": opacidadSegunZoom(1),
      },
    },
    {
      id: "episodios",
      type: "line",
      source: FUENTE_EPISODIOS,
      paint: { "line-color": PALETA.dorado, "line-width": 1, "line-opacity": 0.8 },
    },
    {
      id: CAPA_GRUPOS,
      type: "circle",
      source: FUENTE_PUNTOS,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": PALETA.superficie1,
        "circle-opacity": 0.92,
        "circle-stroke-color": PALETA.dorado,
        "circle-stroke-width": 1,
        "circle-radius": ["step", ["get", "point_count"], 12, 10, 15, 50, 19],
      },
    },
    {
      id: "grupos-numero",
      type: "symbol",
      source: FUENTE_PUNTOS,
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count_abbreviated"],
        "text-font": FUENTE_TIPOGRAFICA_NUMEROS,
        "text-size": 12,
        "text-allow-overlap": true,
      },
      paint: { "text-color": PALETA.texto },
    },
    {
      id: CAPA_INCIDENTES,
      type: "symbol",
      source: FUENTE_PUNTOS,
      filter: ["!", ["has", "point_count"]],
      layout: {
        "icon-image": ["get", "icono"],
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    },
    {
      id: "seleccion",
      type: "circle",
      source: FUENTE_SELECCION,
      paint: {
        "circle-radius": 13,
        "circle-color": "rgba(0, 0, 0, 0)",
        "circle-stroke-color": PALETA.dorado,
        "circle-stroke-width": 1,
      },
    },
  ];
}

const VACIA = { type: "FeatureCollection" as const, features: [] };

export function estilo(idioma: Idioma, origen: string): StyleSpecification {
  const [fondo, ...base] = capasBase(idioma);
  if (fondo === undefined) throw new Error("el estilo base no tiene capas");
  // Bajo las teselas va la tierra de Natural Earth: fuera del recorte de Europa el mapa
  // sigue teniendo costa en lugar de cortarse en línea recta.
  const tierraDeFondo: LayerSpecification = {
    id: "tierra-de-fondo",
    type: "fill",
    source: FUENTE_TIERRA,
    paint: { "fill-color": PALETA.superficie1 },
  };
  return {
    version: 8,
    glyphs: `${origen}/mapa/fuentes/{fontstack}/{range}.pbf`,
    sprite: `${origen}/mapa/sprites/dark`,
    sources: {
      [FUENTE_BASE]: { type: "vector", url: `pmtiles://${URL_TESELAS}` },
      [FUENTE_TIERRA]: { type: "geojson", data: `${origen}/mapa/tierra.geojson` },
      [FUENTE_PUNTOS]: {
        type: "geojson",
        data: VACIA,
        cluster: true,
        clusterMaxZoom: ZOOM_MAXIMO_AGRUPADO,
        clusterRadius: RADIO_DE_AGRUPACION_PX,
      },
      [FUENTE_PUNTOS_SUELTOS]: { type: "geojson", data: VACIA },
      [FUENTE_AREAS]: { type: "geojson", data: VACIA },
      [FUENTE_EPISODIOS]: { type: "geojson", data: VACIA },
      [FUENTE_SELECCION]: { type: "geojson", data: VACIA },
      [FUENTE_REGIONES]: { type: "geojson", data: `${origen}/mapa/ucrania-regiones.geojson` },
      [FUENTE_CONTORNO]: { type: "geojson", data: `${origen}/mapa/ucrania-contorno.geojson` },
    },
    layers: [fondo, tierraDeFondo, ...base, ...capasPropias()],
  };
}
