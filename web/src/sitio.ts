// Constantes del sitio que comparten la web, el build y los tests.

/** El nombre del proyecto va siempre en inglés, también en la versión española. */
export const NOMBRE = "European Observatory of Drone Incidents";
/** El nombre en español, al lado del oficial en la portada y en el pie de las páginas de texto. */
export const NOMBRE_ES = "Observatorio Europeo de Incidentes con Drones";
export const SIGLAS = "EODI";
export const ORIGEN = "https://droneobservatory.eu";
export const CONTACTO_SEGURIDAD = "192205734+QuantuSync@users.noreply.github.com";

export type Idioma = "es" | "en";
export const IDIOMAS: readonly Idioma[] = ["es", "en"];
export const IDIOMA_POR_DEFECTO: Idioma = "es";
/** La versión inglesa cuelga de /en; la española, de la raíz. */
export const PREFIJO_EN = "/en";

/** Ficheros de datos abiertos que se generan en el build, dentro de /datos. */
export const DESCARGAS = {
  incidentesGeojson: "/datos/incidentes.geojson",
  incidentesCsv: "/datos/incidentes.csv",
  ucraniaJson: "/datos/ucrania.json",
  ucraniaCsv: "/datos/ucrania.csv",
  sinUbicacionJson: "/datos/incidentes_sin_ubicacion.json",
} as const;

export const LICENCIA_DATOS = "CC BY 4.0";
export const LICENCIA_DATOS_URL = "https://creativecommons.org/licenses/by/4.0/";

// Créditos del autor: los mismos que configuracion/licencia_datos.json, que los mete en cada
// fichero publicado (tests/creditos.test.ts comprueba que coinciden).
export const AUTOR_NOMBRE = "Lucas Alaniz Pintos";
/** Cómo firma el autor en cada idioma. */
export const AUTOR_FIRMA: Record<Idioma, string> = {
  es: "Dr. Lucas Alaniz Pintos",
  en: "Lucas Alaniz Pintos, PhD",
};
/** La línea de autoría, en cada idioma. */
export const AUTOR_LINEA: Record<Idioma, string> = {
  es: `Autor: ${AUTOR_FIRMA.es}`,
  en: `Author: ${AUTOR_FIRMA.en}`,
};
export const ORCID = "0009-0008-5179-2534";
export const ORCID_URL = `https://orcid.org/${ORCID}`;
/**
 * El correo de contacto del autor no está en el repositorio: lo da la variable VITE_CORREO_AUTOR del
 * entorno de la compilación (en Vercel, la del proyecto; en las pruebas, vite.config.ts). Sin ella,
 * la web y los ficheros van sin correo.
 */
export const CORREO_AUTOR: string = (
  (import.meta.env as ImportMetaEnv | undefined)?.VITE_CORREO_AUTOR ??
  (typeof process === "undefined" ? undefined : process.env.VITE_CORREO_AUTOR) ??
  ""
).trim();

/** La versión (AAAA-MM, en UTC) que se cita para unos datos actualizados en `instante`. */
export function versionDeDatos(instante: string): string {
  return new Date(instante).toISOString().slice(0, 7);
}

/** La cita recomendada de la versión AAAA-MM. */
export function citaRecomendada(version: string, idioma: Idioma): string {
  const anio = version.slice(0, 4);
  return idioma === "en"
    ? `Alaniz Pintos, L. (${anio}). ${NOMBRE}. Version ${version}. ${ORIGEN}. Licence ${LICENCIA_DATOS}.`
    : `Alaniz Pintos, L. (${anio}). ${NOMBRE}. Versión ${version}. ${ORIGEN}. Licencia ${LICENCIA_DATOS}.`;
}

/** El autor como persona de schema.org, con su ORCID. */
export function autorEstructurado(): Record<string, unknown> {
  return {
    "@type": "Person",
    "@id": ORCID_URL,
    name: AUTOR_NOMBRE,
    honorificPrefix: "Dr.",
    identifier: { "@type": "PropertyValue", propertyID: "ORCID", value: ORCID },
    sameAs: [ORCID_URL],
    url: ORCID_URL,
  };
}

/** El observatorio como editor de schema.org: el nombre completo, la forma corta y el sitio. */
export function editorEstructurado(idioma: Idioma): Record<string, unknown> {
  return {
    "@type": "Organization",
    "@id": `${ORIGEN}/#observatorio`,
    name: NOMBRE,
    alternateName: [NOMBRE_ES, SIGLAS, "droneobservatory.eu"],
    url: ORIGEN + rutaDeIdioma(idioma),
    logo: `${ORIGEN}/marca/logo-384.png`,
    founder: autorEstructurado(),
  };
}

/** Imagen de la vista previa de un incidente: el contorno de Europa con su punto, su titular y su estado. */
export function imagenDeFicha(id: string, idioma: Idioma): string {
  return `/compartir/${id}${idioma === "en" ? "-en" : ""}.png`;
}

/** Imagen de la vista previa al compartir (logo, nombre y mapa), una por idioma. */
export const IMAGEN_COMPARTIR: Record<Idioma, string> = {
  es: "/compartir.png",
  en: "/compartir-en.png",
};
export const IMAGEN_COMPARTIR_ANCHO = 1200;
export const IMAGEN_COMPARTIR_ALTO = 630;

export function rutaDeIdioma(idioma: Idioma): string {
  return idioma === "en" ? PREFIJO_EN : "/";
}

/** Ruta propia de un incidente o de un ataque: /EODI-… en español y /en/EODI-… en inglés. */
export function rutaDeFicha(id: string, idioma: Idioma): string {
  return idioma === "en" ? `${PREFIJO_EN}/${id}` : `/${id}`;
}
