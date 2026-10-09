// El almacén público a través de la red de Vercel: /almacen/<objeto> (reescritura de vercel.json).
//
// La web ya no pide al almacén de Hetzner directamente: el mapa de fondo, estado.json, directo.json
// y las capas del almacén pasan por aquí, y la caché de Vercel guarda cada respuesta. Así una
// avalancha de visitas no llega al almacén (Hetzner limita cada bucket a 750 peticiones por
// segundo, y una visita nueva pide de 37 a 57 trozos del mapa): el primer visitante de cada región
// lo trae del almacén y los siguientes lo reciben de la caché.
//
// - El mapa de fondo se pide por trozos: ?o=<desde>&l=<largo>. La caché de Vercel no guarda las
//   respuestas a peticiones con Range (lo probamos el 9 de octubre de 2026 con una reescritura
//   directa: guardó el primer trozo y lo sirvió para cualquier otro rango). Aquí el trozo va en la
//   dirección y se responde con 200, así que cada trozo tiene su sitio en la caché.
// - Si el almacén principal (Núremberg) no responde, da un error o tarda más de TOPE_MS en
//   contestar, se pide a la copia pública de reserva (Helsinki, almacen/reserva.py; hasta
//   TOPE_RESERVA_MS), y durante
//   PAUSA_MS ya no se intenta el principal. Lo que esté en la caché se sigue sirviendo aunque los
//   dos fallen (stale-if-error).
//
// Sin import: el empaquetado de Vercel no sigue los ficheros .ts de web/. Las direcciones y el
// nombre del mapa de fondo son los de configuracion/almacen_publico.json (web/tests/almacen.test.ts
// comprueba que coinciden).

export const ORIGENES = [
  { nombre: "principal", url: "https://droneobservatory-almacen.nbg1.your-objectstorage.com" },
  { nombre: "reserva", url: "https://droneobservatory-reserva.hel1.your-objectstorage.com" },
] as const;
export const OBJETO_TESELAS = "europa-z14.pmtiles";
/** Lo que se puede pedir: los objetos que usa la web, nada más (no es un proxy abierto). */
const PERMITIDO =
  /^(?:estado\.json|directo\.json|salud\.json|europa-z14\.pmtiles|(?:gnss|focos|luces|satelite|rutas|publicacion|versiones)\/[A-Za-z0-9._-]+(?:\/[A-Za-z0-9._-]+)*)$/;
const NUMERO = /^\d{1,12}$/;
/** El trozo más grande del mapa de fondo que se sirve (los directorios y teselas son mucho menores). */
export const LARGO_MAXIMO = 8 * 1024 * 1024;
/** Lo que se espera a que el principal empiece a responder antes de probar la reserva. */
export const TOPE_MS = 3000;
/**
 * Lo que se espera a la reserva: es el último recurso, y Helsinki lee más lento en frío (medido el
 * 9 de octubre de 2026: mediana 0,49 s frente a 0,22 s de Núremberg, y alguna lectura de 4 s).
 */
export const TOPE_RESERVA_MS = 10_000;
/** Tras un fallo del principal, cuánto tiempo se va directo a la reserva. */
export const PAUSA_MS = 60_000;
const SIN_ERROR = "stale-if-error=604800";

/** Cuánto guarda la caché de Vercel cada objeto, en segundos (lo que cambia más, menos). */
export function segundosEnCache(objeto: string): number {
  if (objeto === OBJETO_TESELAS) return 31_536_000;
  if (objeto.startsWith("versiones/")) return 86_400;
  if (objeto === "directo.json" || objeto === "estado.json" || objeto === "salud.json") return 30;
  if (objeto.startsWith("publicacion/")) return 60;
  return 300;
}

export interface Pedido {
  objeto: string;
  rango: { desde: number; largo: number } | null;
}

/** Lo que pide la dirección, o null si no es algo que la web use. */
export function leerPedido(url: URL): Pedido | null {
  const objeto = url.searchParams.get("objeto") ?? "";
  if (!PERMITIDO.test(objeto) || objeto.includes("..")) return null;
  const desde = url.searchParams.get("o");
  const largo = url.searchParams.get("l");
  if (objeto !== OBJETO_TESELAS) return desde === null && largo === null ? { objeto, rango: null } : null;
  // El mapa de fondo solo por trozos: entero son 24,6 GB.
  if (desde === null || largo === null || !NUMERO.test(desde) || !NUMERO.test(largo)) return null;
  const l = Number(largo);
  if (l <= 0 || l > LARGO_MAXIMO) return null;
  return { objeto, rango: { desde: Number(desde), largo: l } };
}

// Hasta cuándo se salta el principal tras un fallo (por instancia de la función).
let principalCaidoHasta = 0;

/** Pide a un origen; da la respuesta en cuanto llegan las cabeceras, o null si no llegan a tiempo. */
async function pedir(url: string, cabeceras: Headers, metodo: string, topeMs: number): Promise<Response | null> {
  const control = new AbortController();
  const tope = setTimeout(() => {
    control.abort();
  }, topeMs);
  try {
    return await fetch(url, { method: metodo, headers: cabeceras, signal: control.signal });
  } catch {
    return null;
  } finally {
    clearTimeout(tope);
  }
}

function respuestaDe(r: Response, pedido: Pedido, origen: string, metodo: string): Response {
  const cabeceras = new Headers();
  for (const nombre of ["content-type", "content-disposition", "etag", "last-modified"]) {
    const valor = r.headers.get(nombre);
    if (valor !== null && !(nombre === "etag" && pedido.rango !== null)) cabeceras.set(nombre, valor);
  }
  const segundos = segundosEnCache(pedido.objeto);
  // fetch ya ha descomprimido el cuerpo: Vercel lo vuelve a comprimir para el navegador.
  cabeceras.set("Cache-Control", r.headers.get("cache-control") ?? `public, max-age=${Math.min(segundos, 300)}`);
  if (pedido.rango !== null) cabeceras.set("Cache-Control", "public, max-age=604800, immutable");
  cabeceras.set(
    "CDN-Cache-Control",
    pedido.rango !== null
      ? `public, max-age=${segundos}, immutable`
      : `public, max-age=${segundos}, stale-while-revalidate=${segundos}, ${SIN_ERROR}`,
  );
  cabeceras.set("X-Almacen", origen);
  return new Response(metodo === "HEAD" ? null : r.body, { status: 200, headers: cabeceras });
}

function sinObjeto(estado: number, mensaje: string, cacheable: boolean): Response {
  return new Response(mensaje, {
    status: estado,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      "CDN-Cache-Control": cacheable ? "public, max-age=30" : "no-store",
    },
  });
}

export async function GET(peticion: Request): Promise<Response> {
  const pedido = leerPedido(new URL(peticion.url));
  if (pedido === null) return sinObjeto(404, "no existe", true);
  const metodo = peticion.method === "HEAD" ? "HEAD" : "GET";
  const cabeceras = new Headers({ "User-Agent": "EODI-web (+https://droneobservatory.eu)" });
  if (pedido.rango !== null) {
    const { desde, largo } = pedido.rango;
    cabeceras.set("Range", `bytes=${desde}-${desde + largo - 1}`);
  }
  let noExiste = false;
  for (const origen of ORIGENES) {
    if (origen.nombre === "principal" && Date.now() < principalCaidoHasta) continue;
    const tope = origen.nombre === "principal" ? TOPE_MS : TOPE_RESERVA_MS;
    const r = await pedir(`${origen.url}/${pedido.objeto}`, cabeceras, metodo, tope);
    const correcta = r !== null && (pedido.rango === null ? r.status === 200 : r.status === 206);
    if (correcta) return respuestaDe(r, pedido, origen.nombre, metodo);
    // Un 200 a una petición por trozos sería el fichero entero: se corta sin leerlo.
    await r?.body?.cancel();
    // El almacén responde 403 a lo que no existe (no deja listar). Se pregunta también a la
    // reserva: un bucket que responde 403 a todo también es una caída (así cayó el anterior).
    if (r !== null && (r.status === 403 || r.status === 404)) {
      noExiste = true;
      continue;
    }
    if (origen.nombre === "principal") principalCaidoHasta = Date.now() + PAUSA_MS;
  }
  return noExiste ? sinObjeto(404, "no existe", true) : sinObjeto(502, "el almacén no responde", false);
}

export const HEAD = GET;

/** Para las pruebas: vuelve a intentar el principal desde ya. */
export function olvidarCaidas(): void {
  principalCaidoHasta = 0;
}
