// Estilo del mapa: la base de Protomaps, oscura y apagada para que manden los incidentes, y
// las capas propias. Glifos y sprites se sirven desde este mismo sitio; las teselas, desde
// el almacén público (configuracion/almacen_publico.json).

import { layers } from "@protomaps/basemaps";
import type { Flavor } from "@protomaps/basemaps";
import type {
  ExpressionSpecification,
  LayerSpecification,
  StyleSpecification,
} from "maplibre-gl";

import { OBJETO_TESELAS, urlDelAlmacen } from "../almacenPublico.ts";
import { OPACIDAD_GNSS } from "../datos/gnss.ts";
import { ESTADOS } from "../datos/vocabulario.ts";
import { COLOR_ESTADO, PALETA, TRAZO_DESMENTIDO } from "../paleta.ts";
import {
  DESPLAZAMIENTO_BANDERA,
  ETIQUETA_AVISO,
  ICONO_BANDERA,
  ESCALA_BANDERA_ELEGIDA,
  ICONO_OBSTACULO,
  LADO_OBSTACULO,
  RADIO_INCIDENTE,
} from "./iconos.ts";
import { ZONA_ARCO_RATON_PX } from "./seleccion.ts";
import type { Idioma } from "../sitio.ts";

export const URL_TESELAS: string =
  (import.meta.env.VITE_TESELAS as string | undefined) ?? urlDelAlmacen(OBJETO_TESELAS);

export const FUENTE_BASE = "protomaps";
/** Tierra de Natural Earth para lo que queda fuera del recorte de teselas. */
export const FUENTE_TIERRA = "tierra";
export const FUENTE_PAISES = "paises";
export const FUENTE_PUNTOS = "incidentes";
export const FUENTE_PUNTOS_SUELTOS = "incidentes-sueltos";
/** Los atribuidos, cada uno con su bandera: no se agrupan nunca. */
export const FUENTE_BANDERAS = "banderas";
export const FUENTE_AREAS = "areas";
export const FUENTE_EPISODIOS = "episodios";
export const FUENTE_SELECCION = "seleccion";
export const FUENTE_REGIONES = "ucrania-regiones";
export const FUENTE_CONTORNO = "ucrania-contorno";
export const FUENTE_FOCOS_UCRANIA = "ucrania-focos";
export const FUENTE_REGIONES_RUSIA = "rusia-regiones";
export const FUENTE_IMPACTOS = "guerra-impactos";
export const FUENTE_GNSS = "gnss";
export const FUENTE_DIRECTO = "directo";
export const FUENTE_CORREDORES = "guerra-corredores";
export const FUENTE_REALCE_ARCO = "guerra-realce-arco";
export const FUENTE_SATELITE = "guerra-satelite";
export const FUENTE_REALCE_PUNTO = "guerra-realce-punto";
export const FUENTE_LUZ_CIUDADES = "guerra-luz-ciudades";
export const FUENTE_ALUMBRADO = "guerra-alumbrado";
export const FUENTE_FOCOS_VIVOS = "guerra-focos-vivos";

export const CAPA_GRUPOS = "grupos";
export const CAPA_NUMERO_GRUPOS = "grupos-numero";
export const CAPA_INCIDENTES_GRAVES = "incidentes-graves";
export const CAPA_INCIDENTES_DISCRETOS = "incidentes-discretos";
export const CAPA_REGIONES = "ucrania-relleno";
export const CAPA_REGION_ELEGIDA = "ucrania-elegida";
export const CAPA_PAIS = "pais-resaltado";
export const CAPA_RECIENTES = "recientes";
export const CAPA_SELECCION = "seleccion";
export const CAPA_SELECCION_BANDERA = "seleccion-bandera";
export const CAPA_FOCOS_BANDERA = "focos-termicos-bandera";
export const CAPA_EPISODIOS = "episodios";
export const CAPA_FOCOS = "focos-termicos";
export const CAPA_FOCOS_UCRANIA = "ucrania-focos-termicos";
export const CAPA_REGIONES_RUSIA = "rusia-relleno";
export const CAPA_REGION_ELEGIDA_RUSIA = "rusia-elegida";
export const CAPA_IMPACTOS = "guerra-impactos";
export const CAPA_IMPACTOS_GRUPOS = "guerra-impactos-grupos";
export const CAPA_IMPACTOS_FOCO = "guerra-impactos-foco";
export const CAPA_IMPACTOS_FOCO_GRUPO = "guerra-impactos-foco-grupo";
export const CAPA_PRESION = "presion-relleno";
export const CAPA_PRESION_LINEA = "presion-linea";
export const CAPA_GNSS = "gnss-relleno";
export const CAPA_GNSS_LINEA = "gnss-linea";
export const CAPA_DIRECTO = "directo-avisos";
export const CAPA_CORREDORES = "guerra-corredores";
/** Zona sensible de los arcos: la misma geometría, ancha e invisible. */
export const CAPA_CORREDORES_ZONA = "guerra-corredores-zona";
export const CAPA_REALCE_ARCO = "guerra-realce-arco";
/** Impactos con información de satélite: más grandes, con aro (doble si hay imagen). */
export const CAPA_SATELITE = "guerra-satelite";
export const CAPA_SATELITE_ARO = "guerra-satelite-aro";
export const CAPA_SATELITE_FOCO = "guerra-satelite-foco";
export const CAPA_REALCE_PUNTO = "guerra-realce-punto";
export const CAPA_LUZ_REGIONES = "ucrania-luz";
export const CAPA_LUZ_REGIONES_RUSIA = "rusia-luz";
export const CAPA_LUZ_CIUDADES = "guerra-luz-ciudades";
export const CAPA_ALUMBRADO = "guerra-alumbrado";
export const CAPA_ALUMBRADO_PUNTO = "guerra-alumbrado-punto";
export const CAPA_FOCOS_VIVOS = "guerra-focos-vivos";
export const CAPA_FOCOS_VIVOS_IMPACTO = "guerra-focos-vivos-impacto";
export const CAPA_BANDERAS = "banderas";
export const CAPA_NUMERO_BANDERAS = "banderas-numero";
export const CAPA_OBSTACULOS = "obstaculos";
export const CAPA_OBSTACULOS_IMPACTOS = "guerra-impactos-obstaculos";

/** Capas que se pueden pulsar, de la de más arriba a la de más abajo. Los arcos de los
 * corredores van aparte, con su zona sensible (seleccion.ts). */
export const CAPAS_PULSABLES: readonly string[] = [
  CAPA_DIRECTO,
  CAPA_BANDERAS,
  CAPA_INCIDENTES_GRAVES,
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_GRUPOS,
  CAPA_SATELITE,
  CAPA_IMPACTOS,
  CAPA_IMPACTOS_GRUPOS,
  CAPA_FOCOS_VIVOS_IMPACTO,
  CAPA_LUZ_CIUDADES,
  CAPA_ALUMBRADO,
  CAPA_REGIONES,
  CAPA_REGIONES_RUSIA,
  CAPA_GNSS,
  CAPA_PRESION,
];

/** Capas propias de cada capa del selector. */
export const CAPAS_DE_INCIDENTES: readonly string[] = [
  "areas-relleno",
  "areas-contorno",
  "areas-contorno-desmentido",
  CAPA_EPISODIOS,
  CAPA_GRUPOS,
  CAPA_NUMERO_GRUPOS,
  CAPA_RECIENTES,
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_INCIDENTES_GRAVES,
  CAPA_FOCOS,
  CAPA_BANDERAS,
  CAPA_NUMERO_BANDERAS,
  CAPA_FOCOS_BANDERA,
  CAPA_SELECCION,
  CAPA_SELECCION_BANDERA,
  CAPA_OBSTACULOS,
];
export const CAPAS_DE_UCRANIA: readonly string[] = [
  CAPA_REGIONES_RUSIA,
  "rusia-regiones-linea",
  CAPA_REGION_ELEGIDA_RUSIA,
  CAPA_REGIONES,
  "ucrania-regiones-linea",
  "ucrania-contorno",
  CAPA_REGION_ELEGIDA,
  CAPA_FOCOS_UCRANIA,
  CAPA_IMPACTOS_GRUPOS,
  "guerra-impactos-numero",
  CAPA_IMPACTOS,
  CAPA_IMPACTOS_FOCO,
  CAPA_IMPACTOS_FOCO_GRUPO,
  CAPA_OBSTACULOS_IMPACTOS,
  CAPA_SATELITE_ARO,
  CAPA_SATELITE,
  CAPA_SATELITE_FOCO,
];

/** Con «Con satélite», lo demás de la capa de guerra se atenúa: [capa, propiedad, valor]. */
export const ATENUADAS_SIN_SATELITE: readonly [
  string,
  "circle-opacity" | "circle-stroke-opacity" | "text-opacity",
  number,
][] = [
  [CAPA_IMPACTOS, "circle-opacity", 0.15],
  [CAPA_IMPACTOS, "circle-stroke-opacity", 0.15],
  [CAPA_IMPACTOS_GRUPOS, "circle-opacity", 0.2],
  [CAPA_IMPACTOS_GRUPOS, "circle-stroke-opacity", 0.25],
  ["guerra-impactos-numero", "text-opacity", 0.25],
  [CAPA_IMPACTOS_FOCO, "circle-opacity", 0.15],
  [CAPA_IMPACTOS_FOCO_GRUPO, "circle-opacity", 0.15],
  [CAPA_FOCOS_UCRANIA, "circle-opacity", 0.15],
  [CAPA_FOCOS_VIVOS, "circle-opacity", 0.12],
  [CAPA_FOCOS_VIVOS_IMPACTO, "circle-opacity", 0.15],
];
/** Opacidad de los arcos con «Con satélite». */
export const OPACIDAD_CORREDOR_SIN_SATELITE = 0.05;
export const CAPAS_DE_DENSIDAD: readonly string[] = ["densidad"];
export const CAPAS_DE_PRESION: readonly string[] = [CAPA_PRESION, CAPA_PRESION_LINEA];
export const CAPAS_DE_GNSS: readonly string[] = [CAPA_GNSS, CAPA_GNSS_LINEA];

/**
 * Interferencia GPS: gris más claro cuanta más proporción de aeronaves afectadas, y el nivel
 * alto (más del 10 %) con el color de estado de alerta.
 */
const GRIS_GNSS_BAJO = PALETA.linea;
const GRIS_GNSS_ALTO = PALETA.texto;
export const COLOR_GNSS: ExpressionSpecification = [
  "case",
  ["==", ["get", "nivel"], "alta"],
  PALETA.atribuido,
  ["interpolate", ["linear"], ["get", "proporcion"], 0, GRIS_GNSS_BAJO, 0.1, GRIS_GNSS_ALTO],
];

/** Capas de la guerra por satélite: se ven con la capa de Ucrania y su propio interruptor. */
export const CAPAS_DE_CORREDORES: readonly string[] = [
  CAPA_CORREDORES,
  CAPA_CORREDORES_ZONA,
  CAPA_REALCE_ARCO,
];
/** Marcas puntuales de la capa de guerra que se realzan al pasar el ratón y ganan a los arcos. */
export const CAPAS_DE_PUNTOS_DE_GUERRA: readonly string[] = [
  CAPA_SATELITE,
  CAPA_IMPACTOS,
  CAPA_IMPACTOS_GRUPOS,
  CAPA_FOCOS_VIVOS_IMPACTO,
  CAPA_LUZ_CIUDADES,
  CAPA_ALUMBRADO,
];
/** Con el dedo, las marcas de la guerra que se alcanzan a 28 px (ZONA_ARCO_DEDO_PX): no los
 * grupos de impactos, que ya son círculos grandes y cuentan solo si se tocan. */
export const CAPAS_DE_PUNTOS_AL_TOQUE: readonly string[] = CAPAS_DE_PUNTOS_DE_GUERRA.filter(
  (id) => id !== CAPA_IMPACTOS_GRUPOS,
);
/** Áreas: solo reciben el clic si no hay ninguna marca ni ningún arco. */
export const CAPAS_DE_AREAS: readonly string[] = [
  CAPA_REGIONES,
  CAPA_REGIONES_RUSIA,
  CAPA_GNSS,
  CAPA_PRESION,
];
export const CAPAS_DE_LUZ: readonly string[] = [
  CAPA_LUZ_REGIONES,
  CAPA_LUZ_REGIONES_RUSIA,
  CAPA_LUZ_CIUDADES,
  CAPA_ALUMBRADO,
  CAPA_ALUMBRADO_PUNTO,
];
export const CAPAS_DE_FOCOS_VIVOS: readonly string[] = [CAPA_FOCOS_VIVOS, CAPA_FOCOS_VIVOS_IMPACTO];

/** Corredores: trazo fino, gris y de baja opacidad, por debajo de los impactos. */
const COLOR_CORREDOR = PALETA.guerra;
export const OPACIDAD_CORREDOR = 0.18;
/** Opacidad de los demás arcos mientras uno está realzado. */
export const OPACIDAD_CORREDOR_ATENUADO = 0.08;
/** Radio del aro de realce de un punto de la capa de guerra. */
export const RADIO_REALCE_PUNTO = 9;
/** Focos de calor de 24 h: puntos pequeños; los que coinciden con un impacto, resaltados. */
const RADIO_FOCO_VIVO = 1.7;
const OPACIDAD_FOCO_VIVO = 0.7;
const RADIO_FOCO_VIVO_IMPACTO = 3.2;

/** Marca del foco térmico: pequeña, junto al símbolo, como en la ayuda (MarcaFoco). */
const RADIO_MARCA_FOCO = 3.5;
const DESPLAZAMIENTO_MARCA_FOCO: [number, number] = [9, -9];

/** Impactos con lugar de la capa de guerra: puntos pequeños, agrupados al alejar. */
const RADIO_IMPACTO = 3.5;
const RADIO_GRUPO_IMPACTOS_MINIMO = 8;
const RADIO_GRUPO_IMPACTOS_MAXIMO = 18;
/** Cuenta a partir de la cual el círculo de un grupo de impactos ya no crece. */
const CUENTA_GRUPO_IMPACTOS_MAXIMA = 200;
export const ZOOM_MAXIMO_AGRUPADO_IMPACTOS = 7;
const RADIO_DE_AGRUPACION_IMPACTOS_PX = 30;
const RADIO_GRUPO_IMPACTOS: ExpressionSpecification = [
  "interpolate", ["linear"], ["get", "point_count"],
  2, RADIO_GRUPO_IMPACTOS_MINIMO,
  CUENTA_GRUPO_IMPACTOS_MAXIMA, RADIO_GRUPO_IMPACTOS_MAXIMO,
];

/**
 * Banderas de los atribuidos: se juntan solo entre ellas, cuando se pisarían en la pantalla,
 * hasta el zoom 7. Desde el 8 (el de las fichas) cada una va en su punto.
 */
export const ZOOM_MAXIMO_AGRUPADO_BANDERAS = 7;
const RADIO_DE_AGRUPACION_BANDERAS_PX = 18;
/** Atribuidos que junta una bandera: los de su grupo o los de su punto exacto. */
const CUENTA_BANDERAS: ExpressionSpecification = ["coalesce", ["get", "total"], ["get", "n"]];
/** El número va a la derecha del paño, a su altura, en ems del texto. */
const POSICION_NUMERO_BANDERA: [number, number] = [2.4, -1.75];

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
/** Tamaño del número dentro de un grupo. */
export const TAMANO_NUMERO_GRUPO = 12;
/** Código OACI dentro de la etiqueta de un aviso, centrado en la píldora. */
export const TAMANO_TEXTO_AVISO = 10;
/** Altura del centro de la píldora sobre el punto del aeropuerto, en píxeles. */
export const CENTRO_TEXTO_AVISO = ETIQUETA_AVISO.hueco + ETIQUETA_AVISO.punta + ETIQUETA_AVISO.alto / 2;

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

/**
 * Color del anillo de un grupo: el del estado más grave que contiene. Rojo si hay algún
 * confirmado; naranja si todos son notificados. Los atribuidos no se agrupan: van con su
 * bandera, siempre a la vista.
 */
export const COLOR_DE_GRUPO: ExpressionSpecification = [
  "case",
  [">", ["get", "n_confirmados"], 0],
  COLOR_ESTADO.confirmado,
  [">", ["get", "n_notificados"], 0],
  COLOR_ESTADO.notificado,
  COLOR_ESTADO.desmentido,
];

const ES_DESMENTIDO: ExpressionSpecification = ["==", ["get", "estado"], "desmentido"];
/** Un atribuido es solo su bandera: sin área ni aro alrededor. */
export const ES_ATRIBUIDO: ExpressionSpecification = ["==", ["get", "estado"], "atribuido"];
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
    // Presión por país: gris según los incidentes del periodo (la opacidad la pone el mapa).
    {
      id: CAPA_PRESION,
      type: "fill",
      source: FUENTE_PAISES,
      layout: { visibility: "none" },
      paint: {
        "fill-color": PALETA.texto,
        "fill-opacity": 0,
        "fill-opacity-transition": { duration: 260, delay: 0 },
      },
    },
    {
      id: CAPA_PRESION_LINEA,
      type: "line",
      source: FUENTE_PAISES,
      layout: { visibility: "none" },
      filter: ["in", ["get", "iso"], ["literal", []]],
      paint: { "line-color": PALETA.secundario, "line-width": 0.6, "line-opacity": 0.6 },
    },
    {
      id: CAPA_GNSS,
      type: "fill",
      source: FUENTE_GNSS,
      layout: { visibility: "none" },
      paint: { "fill-color": COLOR_GNSS, "fill-opacity": OPACIDAD_GNSS },
    },
    {
      id: CAPA_GNSS_LINEA,
      type: "line",
      source: FUENTE_GNSS,
      layout: { visibility: "none" },
      paint: { "line-color": PALETA.fondo, "line-width": 0.4, "line-opacity": 0.6 },
    },
    // Regiones rusas: el violeta apagado de la capa de guerra, con el contorno discontinuo,
    // para distinguirlas de las de Ucrania (violeta pleno). Sus cifras son las del Ministerio de
    // Defensa ruso, reivindicación de parte.
    {
      id: CAPA_REGIONES_RUSIA,
      type: "fill",
      source: FUENTE_REGIONES_RUSIA,
      paint: {
        "fill-color": PALETA.guerraTenue,
        "fill-opacity": 0,
        "fill-opacity-transition": { duration: 260, delay: 0 },
      },
    },
    {
      id: "rusia-regiones-linea",
      type: "line",
      source: FUENTE_REGIONES_RUSIA,
      paint: {
        "line-color": PALETA.guerraTenue,
        "line-width": 0.6,
        "line-opacity": 0.7,
        "line-dasharray": [3, 2],
      },
    },
    {
      id: CAPA_REGION_ELEGIDA_RUSIA,
      type: "line",
      source: FUENTE_REGIONES_RUSIA,
      filter: ["in", ["get", "iso"], ["literal", []]],
      paint: { "line-color": acento, "line-width": 1.2 },
    },
    {
      id: CAPA_REGIONES,
      type: "fill",
      source: FUENTE_REGIONES,
      paint: {
        "fill-color": PALETA.guerra,
        "fill-opacity": 0,
        "fill-opacity-transition": { duration: 260, delay: 0 },
      },
    },
    // Pérdida de luz nocturna: las regiones se oscurecen según la pérdida (opacidad por
    // región, la pone el mapa con el periodo). Sin color: oscuro sobre el relleno.
    {
      id: CAPA_LUZ_REGIONES_RUSIA,
      type: "fill",
      source: FUENTE_REGIONES_RUSIA,
      paint: { "fill-color": PALETA.fondo, "fill-opacity": 0 },
    },
    {
      id: CAPA_LUZ_REGIONES,
      type: "fill",
      source: FUENTE_REGIONES,
      paint: { "fill-color": PALETA.fondo, "fill-opacity": 0 },
    },
    {
      id: "ucrania-regiones-linea",
      type: "line",
      source: FUENTE_REGIONES,
      paint: { "line-color": PALETA.guerra, "line-width": 0.5, "line-opacity": 0.45 },
    },
    {
      id: "ucrania-contorno",
      type: "line",
      source: FUENTE_CONTORNO,
      paint: { "line-color": PALETA.guerra, "line-width": 1.5, "line-dasharray": [4, 3] },
    },
    {
      id: CAPA_REGION_ELEGIDA,
      type: "line",
      source: FUENTE_REGIONES,
      filter: ["in", ["get", "iso"], ["literal", []]],
      paint: { "line-color": acento, "line-width": 1.2 },
    },
    // Corredores de ataque: arcos sin animación, por debajo de impactos y focos.
    {
      id: CAPA_CORREDORES,
      type: "line",
      source: FUENTE_CORREDORES,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": COLOR_CORREDOR,
        "line-opacity": OPACIDAD_CORREDOR,
        "line-width": ["get", "ancho"],
      },
    },
    // Zona sensible de los arcos: invisible y ancha (la del dedo la pone el mapa al cargar).
    {
      id: CAPA_CORREDORES_ZONA,
      type: "line",
      source: FUENTE_CORREDORES,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": COLOR_CORREDOR,
        "line-opacity": 0,
        "line-width": ["+", ["get", "ancho"], ZONA_ARCO_RATON_PX],
      },
    },
    // El arco señalado (con el ratón, el teclado o su ficha abierta): violeta claro y más grueso.
    {
      id: CAPA_REALCE_ARCO,
      type: "line",
      source: FUENTE_REALCE_ARCO,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": PALETA.guerraClaro,
        "line-opacity": 0.95,
        "line-width": ["+", ["*", ["get", "ancho"], 1.6], 1.5],
      },
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
      filter: ["all", ["!", ES_DESMENTIDO], ["!", ES_ATRIBUIDO]],
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
      filter: ["all", ["!", ES_DESMENTIDO], ["!", ES_ATRIBUIDO]],
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
    // Foco térmico detectado por satélite: un punto claro con borde oscuro arriba a la
    // derecha del símbolo, sin color de estado (los colores son solo para los estados).
    {
      id: CAPA_FOCOS,
      type: "circle",
      source: FUENTE_PUNTOS,
      // También en una pila (varios incidentes en el mismo punto) que tenga alguno con foco;
      // no en los grupos de los zooms lejanos, que juntan puntos distintos.
      filter: ["all", ["!", ["has", "point_count"]], ["==", ["get", "foco"], 1]],
      paint: {
        "circle-radius": RADIO_MARCA_FOCO,
        "circle-color": PALETA.texto,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.5,
        "circle-translate": DESPLAZAMIENTO_MARCA_FOCO,
      },
    },
    // Ciudades que perdieron luz nocturna: un disco oscuro, más opaco cuanto mayor la pérdida.
    {
      id: CAPA_LUZ_CIUDADES,
      type: "circle",
      source: FUENTE_LUZ_CIUDADES,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 5, 8, 9, 11, 16],
        "circle-color": PALETA.fondo,
        "circle-opacity": ["get", "opacidad"],
        "circle-stroke-color": PALETA.guerraTenue,
        "circle-stroke-width": 0.8,
        "circle-stroke-opacity": 0.6,
      },
    },
    // Ciudades con alumbrado reducido de forma permanente: un aro violeta apagado con un punto
    // claro en el centro, distinto del disco oscuro de una ciudad que perdió luz tras un ataque.
    {
      id: CAPA_ALUMBRADO,
      type: "circle",
      source: FUENTE_ALUMBRADO,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 4.5, 8, 6.5, 11, 9],
        "circle-color": PALETA.fondo,
        "circle-opacity": 0.55,
        "circle-stroke-color": PALETA.guerraTenue,
        "circle-stroke-width": 1.2,
      },
    },
    {
      id: CAPA_ALUMBRADO_PUNTO,
      type: "circle",
      source: FUENTE_ALUMBRADO,
      paint: { "circle-radius": 1.6, "circle-color": PALETA.guerraClaro },
    },
    // El punto señalado de la capa de guerra: un aro violeta claro alrededor.
    {
      id: CAPA_REALCE_PUNTO,
      type: "circle",
      source: FUENTE_REALCE_PUNTO,
      paint: {
        "circle-radius": RADIO_REALCE_PUNTO,
        "circle-color": PALETA.guerraClaro,
        "circle-opacity": 0.12,
        "circle-stroke-color": PALETA.guerraClaro,
        "circle-stroke-width": 1.8,
      },
    },
    // Focos de calor de las últimas 24 horas: pequeños y discretos.
    {
      id: CAPA_FOCOS_VIVOS,
      type: "circle",
      source: FUENTE_FOCOS_VIVOS,
      filter: ["==", ["get", "impacto"], ""],
      paint: {
        "circle-radius": RADIO_FOCO_VIVO,
        "circle-color": PALETA.guerraTenue,
        "circle-opacity": OPACIDAD_FOCO_VIVO,
      },
    },
    {
      id: CAPA_FOCOS_VIVOS_IMPACTO,
      type: "circle",
      source: FUENTE_FOCOS_VIVOS,
      filter: ["!=", ["get", "impacto"], ""],
      paint: {
        "circle-radius": RADIO_FOCO_VIVO_IMPACTO,
        "circle-color": PALETA.guerraClaro,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.2,
      },
    },
    {
      id: CAPA_FOCOS_UCRANIA,
      type: "circle",
      source: FUENTE_FOCOS_UCRANIA,
      paint: {
        "circle-radius": RADIO_MARCA_FOCO + 0.5,
        "circle-color": PALETA.guerraClaro,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.5,
      },
    },
    // Impactos con lugar de la capa de guerra, en su violeta: el relleno es una fuente
    // oficial; el aro sin relleno, una reivindicación de parte. Al alejar se agrupan con su
    // contador; el foco térmico detectado se marca como en los incidentes, también en el grupo.
    {
      id: CAPA_IMPACTOS_GRUPOS,
      type: "circle",
      source: FUENTE_IMPACTOS,
      filter: ["has", "point_count"],
      paint: {
        "circle-radius": RADIO_GRUPO_IMPACTOS,
        "circle-color": PALETA.elevado,
        // Un grupo con algún impacto con información de satélite lleva el borde claro y más
        // grueso: ahí conviene acercarse.
        "circle-stroke-color": ["case", [">", ["get", "satelite"], 0], PALETA.guerraClaro, PALETA.guerra],
        "circle-stroke-width": ["case", [">", ["get", "satelite"], 0], 2.2, 1.2],
      },
    },
    {
      id: "guerra-impactos-numero",
      type: "symbol",
      source: FUENTE_IMPACTOS,
      filter: ["has", "point_count"],
      layout: {
        "text-field": ["get", "point_count_abbreviated"],
        "text-font": FUENTE_TIPOGRAFICA_NUMEROS,
        "text-size": 10,
        "text-allow-overlap": true,
        "text-ignore-placement": true,
      },
      paint: { "text-color": PALETA.texto },
    },
    {
      id: CAPA_IMPACTOS,
      type: "circle",
      source: FUENTE_IMPACTOS,
      filter: ["!", ["has", "point_count"]],
      paint: {
        "circle-radius": RADIO_IMPACTO,
        "circle-color": ["case", ["==", ["get", "parte"], 1], PALETA.fondo, PALETA.guerra],
        "circle-stroke-color": PALETA.guerra,
        "circle-stroke-width": 1.2,
      },
    },
    // La marca de foco va arriba a la derecha del punto o del grupo que lo contiene (el
    // desplazamiento no puede depender del dato: dos capas).
    {
      id: CAPA_IMPACTOS_FOCO,
      type: "circle",
      source: FUENTE_IMPACTOS,
      filter: ["all", ["!", ["has", "point_count"]], ["==", ["get", "foco"], 1]],
      paint: {
        "circle-radius": RADIO_MARCA_FOCO,
        "circle-color": PALETA.guerraClaro,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.5,
        "circle-translate": [6, -6],
      },
    },
    {
      id: CAPA_IMPACTOS_FOCO_GRUPO,
      type: "circle",
      source: FUENTE_IMPACTOS,
      filter: ["all", ["has", "point_count"], [">", ["get", "focos"], 0]],
      paint: {
        "circle-radius": RADIO_MARCA_FOCO,
        "circle-color": PALETA.guerraClaro,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.5,
        "circle-translate": [12, -12],
      },
    },
    // Impactos con información de satélite, siempre encima de los demás y sin agrupar: más
    // grandes, en violeta con el borde claro; con imagen de antes y después, un segundo aro; con
    // foco de calor, la marca de foco arriba a la derecha.
    {
      id: CAPA_SATELITE_ARO,
      type: "circle",
      source: FUENTE_SATELITE,
      filter: ["==", ["get", "imagen"], 1],
      paint: {
        "circle-radius": RADIO_IMPACTO + 6,
        "circle-opacity": 0,
        "circle-stroke-color": PALETA.guerraClaro,
        "circle-stroke-width": 1.3,
      },
    },
    {
      id: CAPA_SATELITE,
      type: "circle",
      source: FUENTE_SATELITE,
      paint: {
        "circle-radius": RADIO_IMPACTO + 2.5,
        "circle-color": PALETA.guerra,
        "circle-stroke-color": PALETA.guerraClaro,
        "circle-stroke-width": 1.8,
      },
    },
    {
      id: CAPA_SATELITE_FOCO,
      type: "circle",
      source: FUENTE_SATELITE,
      filter: ["==", ["get", "foco"], 1],
      paint: {
        "circle-radius": RADIO_MARCA_FOCO,
        "circle-color": PALETA.guerraClaro,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.5,
        "circle-translate": [9, -9],
      },
    },
    {
      id: CAPA_SELECCION,
      type: "circle",
      source: FUENTE_SELECCION,
      filter: ["!", ES_ATRIBUIDO],
      paint: {
        "circle-radius": 14,
        "circle-color": "rgba(0, 0, 0, 0)",
        "circle-stroke-color": acento,
        "circle-stroke-width": 1.5,
      },
    },
    // El número de un grupo va encima de todo, con un halo del fondo: ni un incidente suelto
    // en un punto muy cercano ni la etiqueta de un aviso lo tapan.
    {
      id: CAPA_NUMERO_GRUPOS,
      type: "symbol",
      source: FUENTE_PUNTOS,
      filter: ES_GRUPO,
      layout: {
        "text-field": ["to-string", CUENTA],
        "text-font": FUENTE_TIPOGRAFICA_NUMEROS,
        "text-size": TAMANO_NUMERO_GRUPO,
        "text-allow-overlap": true,
        "text-ignore-placement": true,
      },
      paint: { "text-color": PALETA.texto, "text-halo-color": PALETA.panelSolido, "text-halo-width": 2 },
    },
    // Obstáculos invisibles del tamaño de cada círculo: los nombres del mapa (países,
    // ciudades) ceden ante los marcadores en lugar de quedar partidos bajo ellos. Se colocan
    // antes que los nombres de la base (van por encima en la pila), siempre a la vista
    // (allow-overlap) y ocupando su sitio (sin ignore-placement).
    {
      id: CAPA_OBSTACULOS,
      type: "symbol",
      source: FUENTE_PUNTOS,
      layout: {
        "icon-image": ICONO_OBSTACULO,
        "icon-size": [
          "/",
          ["case", ES_GRUPO, ["+", ["*", 2, RADIO_DE_GRUPO], 3], 2 * RADIO_INCIDENTE + 2],
          LADO_OBSTACULO,
        ],
        "icon-allow-overlap": true,
        "icon-ignore-placement": false,
        "icon-padding": 1,
      },
    },
    {
      id: CAPA_OBSTACULOS_IMPACTOS,
      type: "symbol",
      source: FUENTE_IMPACTOS,
      layout: {
        "icon-image": ICONO_OBSTACULO,
        "icon-size": [
          "/",
          ["case", ["has", "point_count"], ["+", ["*", 2, RADIO_GRUPO_IMPACTOS], 2.4], 2 * RADIO_IMPACTO + 2.4],
          LADO_OBSTACULO,
        ],
        "icon-allow-overlap": true,
        "icon-ignore-placement": false,
        "icon-padding": 1,
      },
    },
    // Los atribuidos: solo su bandera, más grande que un círculo suelto y por encima de los
    // círculos y de los grupos. El pie del mástil marca el punto exacto. Los nombres del mapa
    // también ceden ante ella.
    {
      id: CAPA_BANDERAS,
      type: "symbol",
      source: FUENTE_BANDERAS,
      layout: {
        "icon-image": ICONO_BANDERA,
        "icon-anchor": "bottom-left",
        "icon-offset": DESPLAZAMIENTO_BANDERA,
        "icon-allow-overlap": true,
        "icon-ignore-placement": false,
      },
    },
    // Varios atribuidos juntos: la bandera con su número al lado, como el de los grupos.
    {
      id: CAPA_NUMERO_BANDERAS,
      type: "symbol",
      source: FUENTE_BANDERAS,
      filter: [">", CUENTA_BANDERAS, 1],
      layout: {
        "text-field": ["to-string", CUENTA_BANDERAS],
        "text-font": FUENTE_TIPOGRAFICA_NUMEROS,
        "text-size": TAMANO_NUMERO_GRUPO,
        "text-offset": POSICION_NUMERO_BANDERA,
        "text-allow-overlap": true,
        "text-ignore-placement": false,
      },
      paint: { "text-color": PALETA.texto, "text-halo-color": PALETA.panelSolido, "text-halo-width": 2 },
    },
    // El foco térmico de un atribuido va a la izquierda del mástil: a la derecha está el paño.
    {
      id: CAPA_FOCOS_BANDERA,
      type: "circle",
      source: FUENTE_BANDERAS,
      filter: ["==", ["get", "foco"], 1],
      paint: {
        "circle-radius": RADIO_MARCA_FOCO,
        "circle-color": PALETA.texto,
        "circle-stroke-color": PALETA.fondo,
        "circle-stroke-width": 1.5,
        "circle-translate": [-DESPLAZAMIENTO_MARCA_FOCO[0], DESPLAZAMIENTO_MARCA_FOCO[1]],
      },
    },
    // Un atribuido abierto: su bandera, algo más grande, sin aro ni borde. El desplazamiento
    // se escala con el icono, así que el pie sigue en el punto.
    {
      id: CAPA_SELECCION_BANDERA,
      type: "symbol",
      source: FUENTE_SELECCION,
      filter: ES_ATRIBUIDO,
      layout: {
        "icon-image": ICONO_BANDERA,
        "icon-size": ESCALA_BANDERA_ELEGIDA,
        "icon-anchor": "bottom-left",
        "icon-offset": DESPLAZAMIENTO_BANDERA,
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
    },
    // Avisos de la detección en directo: una etiqueta con el código OACI dentro, borde del
    // color de su estado y una punta que señala el aeropuerto, levantada sobre el punto para
    // no tapar el número de un grupo en el mismo sitio. Sin pulso. Va encima de todo: ningún
    // grupo vecino la pisa, y los nombres del mapa ceden ante ella.
    {
      id: CAPA_DIRECTO,
      type: "symbol",
      source: FUENTE_DIRECTO,
      layout: {
        "icon-image": ["concat", "aviso-", ["get", "estado"]],
        "icon-anchor": "bottom",
        "icon-offset": [0, -ETIQUETA_AVISO.hueco],
        "icon-allow-overlap": true,
        "icon-ignore-placement": false,
        "text-field": ["get", "oaci"],
        "text-font": FUENTE_TIPOGRAFICA_NUMEROS,
        "text-size": TAMANO_TEXTO_AVISO,
        "text-anchor": "center",
        "text-offset": [0, -CENTRO_TEXTO_AVISO / TAMANO_TEXTO_AVISO],
        "text-allow-overlap": true,
        "text-ignore-placement": false,
      },
      paint: { "text-color": PALETA.texto },
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
          n_confirmados: ["+", ["get", "n_confirmados"]],
          n_notificados: ["+", ["get", "n_notificados"]],
          n_novedades: ["+", ["get", "novedad"]],
        },
      },
      [FUENTE_PUNTOS_SUELTOS]: { type: "geojson", data: VACIA },
      [FUENTE_BANDERAS]: {
        type: "geojson",
        data: VACIA,
        cluster: true,
        clusterMaxZoom: ZOOM_MAXIMO_AGRUPADO_BANDERAS,
        clusterRadius: RADIO_DE_AGRUPACION_BANDERAS_PX,
        clusterProperties: {
          total: ["+", ["get", "n"]],
          n_novedades: ["+", ["get", "novedad"]],
          atribuido: ["max", ["get", "atribuido"]],
          foco: ["max", ["get", "foco"]],
        },
      },
      [FUENTE_AREAS]: { type: "geojson", data: VACIA },
      [FUENTE_EPISODIOS]: { type: "geojson", data: VACIA },
      [FUENTE_SELECCION]: { type: "geojson", data: VACIA },
      [FUENTE_REGIONES]: { type: "geojson", data: `${origen}/mapa/ucrania-regiones.geojson` },
      [FUENTE_CONTORNO]: { type: "geojson", data: `${origen}/mapa/ucrania-contorno.geojson` },
      [FUENTE_FOCOS_UCRANIA]: { type: "geojson", data: VACIA },
      [FUENTE_REGIONES_RUSIA]: { type: "geojson", data: `${origen}/mapa/rusia-regiones.geojson` },
      [FUENTE_GNSS]: { type: "geojson", data: VACIA },
      [FUENTE_DIRECTO]: { type: "geojson", data: VACIA },
      [FUENTE_CORREDORES]: { type: "geojson", data: VACIA },
      [FUENTE_LUZ_CIUDADES]: { type: "geojson", data: VACIA },
      [FUENTE_REALCE_ARCO]: { type: "geojson", data: VACIA },
      [FUENTE_SATELITE]: { type: "geojson", data: VACIA },
      [FUENTE_REALCE_PUNTO]: { type: "geojson", data: VACIA },
      [FUENTE_ALUMBRADO]: { type: "geojson", data: VACIA },
      [FUENTE_FOCOS_VIVOS]: { type: "geojson", data: VACIA },
      [FUENTE_IMPACTOS]: {
        type: "geojson",
        data: VACIA,
        cluster: true,
        clusterMaxZoom: ZOOM_MAXIMO_AGRUPADO_IMPACTOS,
        clusterRadius: RADIO_DE_AGRUPACION_IMPACTOS_PX,
        clusterProperties: {
          focos: ["+", ["get", "foco"]],
          satelite: ["max", ["get", "satelite"]],
        },
      },
    },
    layers: [fondo, tierraDeFondo, ...base, ...capasPropias(acento)],
  };
}
