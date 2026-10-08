// Lugar aproximado de un incidente sin punto (publicacion/incidentes_sin_ubicacion.json): la
// fuente nombra el país, una región o un mar, pero no un sitio que se pueda situar. El mapa lo
// pinta con un marcador propio en el centro de esa zona: el país (el punto de etiqueta de
// Natural Earth, el mismo con que se rotula el país en el mapa), la región que nombra la fuente
// (tabla de abajo) o el mar frente a la costa si el suceso es en el mar. La ficha dice el nivel y
// de dónde sale. No es un dato de la fuente: el punto solo sirve para que el incidente se vea.

import { pais } from "../i18n/index.ts";
import { nombreDeLugar } from "../i18n/nombresLugar.ts";
import type { Textos } from "../i18n/index.ts";

/** Hasta dónde se conoce el lugar de un incidente con marcador aproximado. */
export type NivelAproximado = "pais" | "region" | "mar";

export interface LugarAproximado {
  lon: number;
  lat: number;
  nivel: NivelAproximado;
  /** El nombre de la zona tal como lo da la fuente (región o mar); null en el país. */
  nombre: string | null;
}

/** Punto de etiqueta de cada país (Natural Earth, web/public/mapa/paises.geojson). */
export const PUNTO_PAIS: Readonly<Record<string, readonly [number, number]>> = {
  AD: [1.539, 42.548], AL: [20.114, 40.655], AM: [44.801, 40.459], AT: [14.131, 47.519],
  AX: [19.87, 60.156], AZ: [47.211, 40.402], BA: [18.068, 44.091], BE: [4.8, 50.785],
  BG: [25.157, 42.509], BY: [28.418, 53.822], CH: [7.464, 46.719], CY: [33.084, 34.913],
  CZ: [15.378, 49.882], DE: [9.678, 50.962], DK: [9.018, 55.967], EE: [25.867, 58.725],
  ES: [-3.465, 40.091], FI: [27.276, 63.252], FO: [-7.058, 62.186], FR: [2.552, 46.696],
  GB: [-2.116, 54.403], GE: [43.736, 41.87], GG: [-2.562, 49.464], GR: [21.726, 39.493],
  HR: [16.372, 45.806], HU: [19.448, 47.087], IE: [-7.799, 53.079], IM: [-4.53, 54.221],
  IS: [-18.674, 64.779], IT: [11.077, 44.732], JE: [-2.09, 49.221], LI: [9.559, 47.111],
  LT: [24.09, 55.104], LU: [6.078, 49.734], LV: [25.459, 57.067], MC: [7.398, 43.74],
  MD: [28.488, 47.435], ME: [19.144, 42.803], MK: [21.556, 41.558], MT: [14.433, 35.893],
  NL: [5.611, 52.422], NO: [9.68, 61.357], PL: [19.49, 51.99], PT: [-8.272, 39.607],
  RO: [24.973, 45.733], RS: [20.788, 44.19], RU: [44.686, 58.249], SE: [19.017, 65.859],
  SI: [14.915, 46.061], SK: [19.05, 48.734], SM: [12.441, 43.934], TR: [34.508, 39.345],
  UA: [32.141, 49.725], VA: [12.453, 41.903], XK: [20.861, 42.594],
};

interface Zona {
  pais: string;
  /** Formas en que la escriben las fuentes, normalizadas (minúsculas, sin acentos). */
  nombres: readonly string[];
  punto: readonly [number, number];
  /** El punto en el mar frente a esa costa, para un suceso en el mar. */
  mar?: readonly [number, number];
  /** La zona es un mar. */
  esMar?: true;
}

/**
 * Regiones y mares que nombran las fuentes de los incidentes sin punto, con su centro
 * aproximado. Una región que no está aquí deja el marcador en el país.
 */
const ZONAS: readonly Zona[] = [
  { pais: "BE", nombres: ["antwerpen", "anvers", "antwerp"], punto: [4.6, 51.2] },
  { pais: "BE", nombres: ["mechelen", "malines"], punto: [4.48, 51.03] },
  { pais: "BG", nombres: ["dobrich", "добрич"], punto: [27.85, 43.6], mar: [28.75, 43.4] },
  { pais: "BG", nombres: ["varna", "варна"], punto: [27.65, 43.2], mar: [28.2, 43.15] },
  { pais: "BG", nombres: ["burgas", "бургас"], punto: [27.2, 42.55], mar: [27.85, 42.5] },
  { pais: "DE", nombres: ["sachsen-anhalt", "saxony-anhalt"], punto: [11.7, 52.0] },
  { pais: "DK", nombres: ["nordjylland", "north jutland"], punto: [9.95, 57.05] },
  { pais: "EE", nombres: ["ida-viru", "ida-virumaa"], punto: [27.4, 59.2] },
  { pais: "FI", nombres: ["kymenlaakso"], punto: [26.9, 60.75] },
  { pais: "FI", nombres: ["southeast", "southeastern finland", "kaakkois-suomi"], punto: [27.6, 61.2] },
  { pais: "FR", nombres: ["haut-rhin"], punto: [7.3, 47.85] },
  { pais: "GB", nombres: ["bedfordshire"], punto: [-0.45, 52.1] },
  { pais: "GR", nombres: ["evros", "έβρος"], punto: [26.1, 41.1] },
  { pais: "GR", nombres: ["αιγαιο", "aegean", "egeo", "aigaio"], punto: [25.0, 38.5], esMar: true },
  {
    pais: "GR",
    nombres: ["βορειοανατολικο και κεντρικο αιγαιο", "north-east and central aegean"],
    punto: [25.6, 39.1],
    esMar: true,
  },
  { pais: "HR", nombres: ["splitsko-dalmatinska", "split-dalmatia"], punto: [16.6, 43.45] },
  { pais: "IE", nombres: ["dublin bay"], punto: [-6.1, 53.33], esMar: true },
  { pais: "LT", nombres: ["kaunas"], punto: [23.9, 54.9] },
  { pais: "LT", nombres: ["kaisiadorys", "kaišiadorys"], punto: [24.45, 54.86] },
  { pais: "LT", nombres: ["southeastern lithuania", "pietryciu lietuva"], punto: [25.3, 54.4] },
  { pais: "LV", nombres: ["balvi"], punto: [27.4, 57.1] },
  { pais: "LV", nombres: ["latgale", "latgalia"], punto: [27.0, 56.3] },
  { pais: "LV", nombres: ["eastern latvia"], punto: [27.0, 56.6] },
  { pais: "LV", nombres: ["northern latvia", "vidzeme"], punto: [25.3, 57.5] },
  { pais: "MD", nombres: ["gagauzia", "găgăuzia"], punto: [28.65, 46.3] },
  { pais: "MD", nombres: ["stefan voda", "ștefan vodă"], punto: [29.66, 46.52] },
  { pais: "MD", nombres: ["nord", "north", "northern moldova"], punto: [27.8, 47.9] },
  { pais: "NL", nombres: ["limburg"], punto: [5.9, 51.2] },
  { pais: "NO", nombres: ["nordland"], punto: [14.4, 66.8] },
  { pais: "NO", nombres: ["vestland"], punto: [6.4, 60.9] },
  { pais: "NO", nombres: ["troms og finnmark", "troms", "finnmark"], punto: [22.0, 69.8] },
  { pais: "PL", nombres: ["ostpolen", "eastern poland", "wschodnia polska"], punto: [23.0, 51.5] },
  { pais: "RO", nombres: ["arges", "argeș"], punto: [24.9, 45.1] },
  { pais: "RO", nombres: ["tulcea"], punto: [28.85, 45.0], mar: [29.75, 44.85] },
  { pais: "RO", nombres: ["constanta", "constanța", "constanza"], punto: [28.35, 44.2], mar: [29.0, 44.1] },
  { pais: "RO", nombres: ["romanian coast", "litoralul romanesc"], punto: [28.7, 44.4], mar: [29.2, 44.35] },
  { pais: "RO", nombres: ["dunare si marea neagra", "dunăre și marea neagră"], punto: [29.6, 44.75], esMar: true },
];

/** El mar frente a la costa de un país, para un suceso en el mar sin región. */
const MAR_DE_PAIS: Readonly<Record<string, { punto: readonly [number, number]; nombre: { es: string; en: string } }>> = {
  RO: { punto: [29.4, 44.3], nombre: { es: "mar Negro", en: "Black Sea" } },
  BG: { punto: [28.4, 42.9], nombre: { es: "mar Negro", en: "Black Sea" } },
  GR: { punto: [25.0, 38.5], nombre: { es: "mar Egeo", en: "Aegean Sea" } },
};

/** Lo que dice que el suceso es en el mar (en el titular, en español o en inglés). */
const EN_EL_MAR =
  /zona económica exclusiva|exclusive economic zone|\bbarcos?\b|\bbuques?\b|\bships?\b|\bvessels?\b|\bmar negro\b|\bblack sea\b|frente a la costa|off the coast/i;

export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

const POR_NOMBRE = new Map<string, Zona>(
  ZONAS.flatMap((zona) => zona.nombres.map((nombre) => [`${zona.pais}|${normalizar(nombre)}`, zona] as const)),
);

/** Si el titular dice que el suceso fue en el mar. */
export function enElMar(titulo: { es: string; en: string }): boolean {
  return EN_EL_MAR.test(titulo.es) || EN_EL_MAR.test(titulo.en);
}

/**
 * El lugar aproximado de un incidente sin punto: la región que nombra la fuente (o el mar
 * frente a ella, si el suceso es en el mar), el mar del país o, si no, el país. null solo si el
 * país no está en la tabla.
 */
export function lugarAproximado(
  lugar: { pais: string; region?: string | undefined },
  titulo: { es: string; en: string },
): LugarAproximado | null {
  const mar = enElMar(titulo);
  if (lugar.region !== undefined) {
    const zona = POR_NOMBRE.get(`${lugar.pais}|${normalizar(lugar.region)}`);
    if (zona !== undefined) {
      if (zona.esMar === true) return { lon: zona.punto[0], lat: zona.punto[1], nivel: "mar", nombre: lugar.region };
      if (mar && zona.mar !== undefined) {
        return { lon: zona.mar[0], lat: zona.mar[1], nivel: "mar", nombre: lugar.region };
      }
      return { lon: zona.punto[0], lat: zona.punto[1], nivel: "region", nombre: lugar.region };
    }
  }
  const delMar = mar ? MAR_DE_PAIS[lugar.pais] : undefined;
  if (delMar !== undefined) return { lon: delMar.punto[0], lat: delMar.punto[1], nivel: "mar", nombre: null };
  const punto = PUNTO_PAIS[lugar.pais];
  if (punto === undefined) return null;
  return { lon: punto[0], lat: punto[1], nivel: "pais", nombre: null };
}

/** La zona del marcador en palabras: el país, la región tal como la da la fuente o el mar. */
export function zonaEscrita(aproximado: LugarAproximado, codigoPais: string, idioma: "es" | "en"): string {
  if (aproximado.nivel === "pais") return pais(codigoPais, idioma);
  const nombre = aproximado.nombre === null ? null : nombreDeLugar(aproximado.nombre, idioma);
  if (nombre !== null) return nombre;
  return marDelPais(codigoPais, idioma) ?? pais(codigoPais, idioma);
}

/** Lo que la ficha dice de un lugar aproximado: el nivel y de dónde sale el marcador. */
export function textoAproximado(
  t: Textos,
  idioma: "es" | "en",
  aproximado: LugarAproximado,
  codigoPais: string,
): { nivel: string; deDonde: string } {
  return {
    nivel: t.imprecisa.aproximado(t.imprecisa.niveles[aproximado.nivel]),
    deDonde: t.imprecisa.deDonde(aproximado.nivel, zonaEscrita(aproximado, codigoPais, idioma)),
  };
}

/** El nombre del mar de un país, para la ficha cuando la fuente no nombra la zona. */
export function marDelPais(pais: string, idioma: "es" | "en"): string | null {
  return MAR_DE_PAIS[pais]?.nombre[idioma] ?? null;
}
