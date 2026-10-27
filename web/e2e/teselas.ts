// Lo que decide la caché de teselas de los recorridos (e2e/base.ts), sin navegador ni disco: de qué
// trozo del mapa de fondo es una petición, con qué nombre se guarda y qué cabeceras se conservan.
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
