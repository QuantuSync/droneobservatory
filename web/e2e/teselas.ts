// Lo que decide la caché de teselas de los recorridos (e2e/base.ts), sin navegador ni disco: de qué
// trozo del mapa de fondo es una petición, con qué nombre se guarda y qué cabeceras se conservan;
// y lo mismo para los ficheros fijos de la web (código y ficheros públicos del mapa).
// Las pruebas: tests/teselas.test.ts.

/** El fichero del mapa de fondo (el de configuracion/almacen_publico.json y api/almacen.ts). */
export const OBJETO_TESELAS = "europa-z14.pmtiles";

/** Las cabeceras de una respuesta que se guardan con el trozo y se devuelven al servirlo. */
export const CABECERAS_CONSERVADAS = [
  "content-type",
  "etag",
  "content-range",
  "accept-ranges",
  "cache-control",
  // La reserva y el principal están en otro origen: sin esto el navegador no lee la respuesta.
  "access-control-allow-origin",
  "access-control-expose-headers",
] as const;

/** Un trozo del mapa de fondo: por la web (/almacen/…?o=&l=, 200) o directo al almacén (Range, 206). */
export interface Trozo {
  camino: "web" | "almacen";
  /** El nombre del fichero en la caché, sin extensión (solo letras, números y guiones). */
  clave: string;
  estado: 200 | 206;
}

const NUMERO = /^\d{1,12}$/;
const RANGO = /^bytes=(\d{1,12})-(\d{1,12})$/;

/**
 * El trozo que pide una petición, o null si no es del mapa de fondo (o no se sabe qué trozo es:
 * entonces va a la red como siempre).
 */
export function trozoDe(direccion: string, rango: string | undefined): Trozo | null {
  let url: URL;
  try {
    url = new URL(direccion);
  } catch {
    return null;
  }
  if (url.pathname === `/almacen/${OBJETO_TESELAS}`) {
    const o = url.searchParams.get("o") ?? "";
    const l = url.searchParams.get("l") ?? "";
    if (!NUMERO.test(o) || !NUMERO.test(l)) return null;
    return { camino: "web", clave: `web-o${o}-l${l}`, estado: 200 };
  }
  if (url.hostname.endsWith(".your-objectstorage.com") && url.pathname === `/${OBJETO_TESELAS}`) {
    const partes = RANGO.exec((rango ?? "").trim());
    if (partes === null) return null;
    return { camino: "almacen", clave: `rango-${partes[1]}-${partes[2]}`, estado: 206 };
  }
  return null;
}

/** Las cabeceras que se guardan de una respuesta (en minúsculas, solo las conservadas). */
export function cabecerasAGuardar(cabeceras: Record<string, string>): Record<string, string> {
  const fuera: Record<string, string> = {};
  for (const [nombre, valor] of Object.entries(cabeceras)) {
    const n = nombre.toLowerCase();
    if ((CABECERAS_CONSERVADAS as readonly string[]).includes(n)) fuera[n] = valor;
  }
  return fuera;
}

// Los ficheros fijos de la web (noviembre de 2026): el código y los ficheros públicos del mapa,
// que cada prueba volvía a bajar porque la interceptación de base.ts desactiva la caché HTTP del
// navegador (unas 21.000 peticiones por pasada). Dos clases:
// - «codigo»: lo que hay en /assets/ con la huella del contenido en el nombre (el de Vite, 8
//   caracteres, o el de scripts/paginas.ts, 12 o más en hexadecimal). Mientras no cambie el nombre
//   no cambia el contenido: la clave es el nombre.
// - «publico»: los ficheros de web/public que no llevan huella (contornos, fuentes y sprites del
//   mapa, marca, banderas, iconos). Solo se sirven de la caché si los bytes son los del fichero del
//   repositorio, y solo se guardan si la web ha servido exactamente esos bytes: la clave es la
//   huella sha256 del fichero.

/** Las carpetas de web/public cuyos ficheros pueden servirse de la caché. */
export const CARPETAS_PUBLICAS = ["/mapa/", "/marca/", "/banderas/", "/iconos/"] as const;
/** Los ficheros sueltos de web/public que pueden servirse de la caché. */
export const PUBLICOS_SUELTOS = ["/favicon.svg", "/favicon.ico", "/apple-touch-icon.png", "/arranque.js"] as const;

const CAMINO_SEGURO = /^\/[A-Za-z0-9 ._/-]+$/;
const CODIGO = /^\/assets\/[A-Za-z0-9._-]+-(?:([A-Za-z0-9_-]{8})|[0-9a-f]{12,64})\.(?:js|css|woff2|woff|ttf|svg|png|webp|jpg|json|wasm)$/;

/** Un fichero fijo de la web. */
export interface Fijo {
  tipo: "codigo" | "publico";
  camino: string;
  /** Solo en el código: el nombre del fichero en la caché (letras, números, guiones y _). */
  clave?: string;
}

/**
 * El fichero fijo que pide una petición GET al sitio que se recorre, o null si no lo es (o hay
 * duda: entonces va a la red como siempre).
 */
export function fijoDe(direccion: string, sitio: string): Fijo | null {
  let url: URL;
  try {
    url = new URL(direccion);
  } catch {
    return null;
  }
  if (url.host !== sitio || url.search !== "" || url.username !== "" || url.password !== "") return null;
  // Las fuentes del mapa están en carpetas con espacios («Noto Sans Regular»).
  let camino: string;
  try {
    camino = decodeURIComponent(url.pathname);
  } catch {
    return null;
  }
  if (!CAMINO_SEGURO.test(camino) || camino.includes("..") || camino.includes("//")) return null;
  const codigo = CODIGO.exec(camino);
  if (codigo !== null) {
    // Una huella de Vite sin mayúsculas, cifras ni «_» podría ser una palabra: a la red.
    if (codigo[1] !== undefined && !/[A-Z0-9_]/.test(codigo[1])) return null;
    const nombre = camino.slice("/assets/".length).replace(/[^A-Za-z0-9_-]/g, "_");
    return { tipo: "codigo", camino, clave: `codigo-${nombre}` };
  }
  if (CARPETAS_PUBLICAS.some((c) => camino.startsWith(c) && camino.length > c.length && !camino.endsWith("/"))) {
    return { tipo: "publico", camino };
  }
  if ((PUBLICOS_SUELTOS as readonly string[]).includes(camino)) return { tipo: "publico", camino };
  return null;
}

/** La clave en la caché de un fichero público: la huella sha256 (hexadecimal) de su contenido. */
export function claveDePublico(huella: string): string {
  return `publico-${huella.slice(0, 64)}`;
}

/** Si una respuesta de la web a un fichero de código puede guardarse (nunca una página HTML). */
export function codigoGuardable(estado: number, cabeceras: Record<string, string>): boolean {
  if (estado !== 200) return false;
  const tipo = Object.entries(cabeceras).find(([n]) => n.toLowerCase() === "content-type")?.[1] ?? "";
  return tipo !== "" && !tipo.toLowerCase().includes("html");
}

/** Por encima de esto, al empezar se recorta la caché de los ficheros fijos... */
export const TOPE_FIJOS_BYTES = 150 * 1024 * 1024;
/** ...hasta quedar por debajo de esto. */
export const OBJETIVO_FIJOS_BYTES = 100 * 1024 * 1024;

/** Un fichero de la caché con su tamaño y su fecha, para recortarla. */
export interface Guardado {
  nombre: string;
  bytes: number;
  fecha: number;
}

/** Por encima de esto, al empezar se recorta la caché... */
export const TOPE_BYTES = 300 * 1024 * 1024;
/** ...hasta quedar por debajo de esto, quitando primero lo más antiguo. */
export const OBJETIVO_BYTES = 200 * 1024 * 1024;

/** Los ficheros que hay que quitar para que la caché vuelva por debajo de OBJETIVO_BYTES. */
export function sobrantes(ficheros: readonly Guardado[], tope = TOPE_BYTES, objetivo = OBJETIVO_BYTES): string[] {
  let total = ficheros.reduce((s, f) => s + f.bytes, 0);
  if (total <= tope) return [];
  const fuera: string[] = [];
  for (const f of [...ficheros].sort((a, b) => a.fecha - b.fecha)) {
    if (total < objetivo) break;
    fuera.push(f.nombre);
    total -= f.bytes;
  }
  return fuera;
}
