// Autoridades que atribuyen, confirman o investigan incidentes, escritas para que se entiendan
// sin saber su idioma: el nombre traducido y, en las instituciones, el original entre
// paréntesis («el Gobierno federal alemán (Bundesregierung)»). Las claves son los nombres tal
// como los guarda la base. Una autoridad que no está aquí se escribe tal cual.

import type { Idioma } from "../sitio.ts";

interface Autoridad {
  es: string;
  en: string;
  /** Una institución: lleva su nombre original entre paréntesis. */
  original?: true;
}

// ș y ț son la «ș» y la «ț» rumanas.
export const AUTORIDADES: Record<string, Autoridad> = {
  "Pre\u0219edintele Maia Sandu": { es: "la presidenta de Moldavia, Maia Sandu", en: "the President of Moldova, Maia Sandu" },
  "Ministerul de Interne": {
    es: "el Ministerio del Interior de Moldavia",
    en: "the Moldovan Ministry of Internal Affairs",
    original: true,
  },
  "Autorit\u0103\u021bile moldave": { es: "las autoridades moldavas", en: "the Moldovan authorities" },
  "Ministerul Ap\u0103r\u0103rii Moldovei": {
    es: "el Ministerio de Defensa de Moldavia",
    en: "the Moldovan Ministry of Defence",
    original: true,
  },
  Bundesregierung: { es: "el Gobierno federal alemán", en: "the German Federal Government", original: true },
  "Bundesregierung Deutschland": {
    es: "el Gobierno federal alemán",
    en: "the German Federal Government",
    original: true,
  },
  Bundesanwaltschaft: {
    es: "la Fiscalía federal alemana",
    en: "the German Federal Prosecutor's Office",
    original: true,
  },
  Generalbundesanwalt: {
    es: "el Fiscal General federal alemán",
    en: "the German Federal Prosecutor General",
    original: true,
  },
  "F\u00f6rsvarsmakten": { es: "las Fuerzas Armadas de Suecia", en: "the Swedish Armed Forces", original: true },
  "Prezes Rady Ministr\u00f3w": { es: "el primer ministro de Polonia", en: "the Prime Minister of Poland", original: true },
  "Kancelaria Prezesa Rady Ministr\u00f3w": {
    es: "la Cancillería del primer ministro de Polonia",
    en: "the Chancellery of the Prime Minister of Poland",
    original: true,
  },
  "Ministerstwo Obrony Narodowej": {
    es: "el Ministerio de Defensa Nacional de Polonia",
    en: "the Polish Ministry of National Defence",
    original: true,
  },
  "Pre\u0219edintele Rom\u00e2niei": { es: "el presidente de Rumanía", en: "the President of Romania", original: true },
  "Prefectul I\u0061\u0219i": { es: "el prefecto de I\u0061\u0219i", en: "the Prefect of I\u0061\u0219i" },
  "Directorul Aeroportului Interna\u021bional I\u0061\u0219i": {
    es: "el director del Aeropuerto Internacional de I\u0061\u0219i",
    en: "the director of I\u0061\u0219i International Airport",
  },
  "Direc\u021bia Aeroportului Interna\u021bional I\u0061\u0219i": {
    es: "la dirección del Aeropuerto Internacional de I\u0061\u0219i",
    en: "the management of I\u0061\u0219i International Airport",
    original: true,
  },
};

/** La autoridad escrita en el idioma de la web: «el Gobierno federal alemán (Bundesregierung)». */
export function autoridadEscrita(original: string, idioma: Idioma): string {
  const conocida = AUTORIDADES[original];
  if (conocida === undefined) return original;
  return conocida.original === true ? `${conocida[idioma]} (${original})` : conocida[idioma];
}

const DECLARACION = /^(.+) \(declaración oficial citada en (.+)\)$/;

/**
 * El nombre de una fuente para la ficha. Una declaración oficial citada por un medio («X
 * (declaración oficial citada en medio)», como la guarda la base) se escribe en el idioma de la
 * web con la autoridad traducida; las demás, tal cual.
 */
export function medioEscrito(
  medio: string,
  idioma: Idioma,
  declaracion: (autoridad: string, medio: string) => string,
): string {
  const partes = DECLARACION.exec(medio);
  if (partes === null) return medio;
  const [, autoridad = "", fuente = ""] = partes;
  return declaracion(autoridadEscrita(autoridad, idioma), fuente);
}
