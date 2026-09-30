// Constantes del sitio que comparten la web, el build y los tests.

/** El nombre del proyecto va siempre en inglés, también en la versión española. */
export const NOMBRE = "European Observatory of Drone Incidents";
export const SIGLAS = "EODI";
export const ORIGEN = "https://droneobservatory.eu";
export const REPOSITORIO = "https://github.com/QuantuSync/droneobservatory";
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
} as const;

export const LICENCIA_DATOS = "CC BY 4.0";
export const LICENCIA_DATOS_URL = "https://creativecommons.org/licenses/by/4.0/";

/** Imagen fija del mapa para la vista previa al compartir. */
export const IMAGEN_COMPARTIR = "/compartir.png";
export const IMAGEN_COMPARTIR_ANCHO = 1200;
export const IMAGEN_COMPARTIR_ALTO = 630;

export function rutaDeIdioma(idioma: Idioma): string {
  return idioma === "en" ? PREFIJO_EN : "/";
}

/** Ruta propia de un incidente o de un ataque: /EODI-… en español y /en/EODI-… en inglés. */
export function rutaDeFicha(id: string, idioma: Idioma): string {
  return idioma === "en" ? `${PREFIJO_EN}/${id}` : `/${id}`;
}
