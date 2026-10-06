// Las direcciones de fichas que no son un fichero del despliegue. Vercel sirve primero los
// ficheros y solo después aplica las reescrituras de vercel.json, que traen aquí lo que queda:
//
// - un incidente unido a otro: redirección permanente (308) a la ficha del que lo absorbió, en
//   su idioma;
// - un ataque de la capa de Ucrania (/EODI-UA-AAAA-NNNN y /en/…): la portada con el mapa si
//   existe; si no, 404 real con la página 404;
// - cualquier otro /EODI-…: 404 real.
//
// La lista sale del build (web/scripts/paginas.ts escribe /rutas.json con los datos de ese
// despliegue): una sola regla para todos los unidos en los dos idiomas, sin el tope de capacidad
// de las redirecciones masivas de Vercel, y sin coste para las fichas que existen, que nunca
// llegan aquí. Sin import: el empaquetado de Vercel no sigue los ficheros .ts de web/. La
// decisión (decidirBorde) la usan también el build, el servidor local y las pruebas de web/.

/** Lista que escribe el build en /rutas.json con los datos de ese despliegue. */
export interface RutasBorde {
  /** Ruta de la ficha de un unido → ruta de la ficha del que lo absorbió, en los dos idiomas. */
  redirecciones: Record<string, string>;
  /** Identificadores de los ataques publicados de la capa de Ucrania. */
  ataques: string[];
}

export type DecisionBorde =
  | { tipo: "redirigir"; destino: string }
  | { tipo: "no_existe" }
  | { tipo: "portada"; ruta: string };

export const RUTA_LISTA_BORDE = "/rutas.json";
const ATAQUE = /^\/(?:(en)\/)?(EODI-UA-\d{4}-\d{4})$/;
const FICHA = /^\/(?:en\/)?EODI-[A-Za-z0-9-]+$/;
// Lo que la CDN guarda cada respuesta: un despliegue nuevo la vacía.
const CACHE = "public, max-age=0, s-maxage=3600";

/** Qué hacer con una dirección de ficha que no es un fichero del despliegue. */
export function decidirBorde(ruta: string, rutas: RutasBorde, ataques: ReadonlySet<string>): DecisionBorde {
  const destino = Object.hasOwn(rutas.redirecciones, ruta) ? rutas.redirecciones[ruta] : undefined;
  if (destino !== undefined) return { tipo: "redirigir", destino };
  const ataque = ATAQUE.exec(ruta);
  if (ataque?.[2] !== undefined && ataques.has(ataque[2])) {
    return { tipo: "portada", ruta: ataque[1] === "en" ? "/en" : "/" };
  }
  return { tipo: "no_existe" };
}

interface Lista {
  rutas: RutasBorde;
  ataques: Set<string>;
}

// La lista no cambia dentro de un despliegue: se lee una vez por instancia.
let cargada: Promise<Lista | null> | undefined;

/**
 * Las cabeceras de acceso de la petición, para las lecturas propias: en una vista previa
 * protegida, sin ellas la lista y las páginas no se pueden leer. En producción no hay ninguna.
 */
function acceso(peticion: Request): Headers {
  const cabeceras = new Headers();
  for (const nombre of ["cookie", "x-vercel-protection-bypass"]) {
    const valor = peticion.headers.get(nombre);
    if (valor !== null) cabeceras.set(nombre, valor);
  }
  return cabeceras;
}

async function cargar(origen: string, cabeceras: Headers): Promise<Lista | null> {
  try {
    const respuesta = await fetch(new URL(RUTA_LISTA_BORDE, origen), { headers: cabeceras });
    if (!respuesta.ok) return null;
    const rutas = (await respuesta.json()) as RutasBorde;
    return { rutas, ataques: new Set(rutas.ataques) };
  } catch {
    return null;
  }
}

/** Una página del propio despliegue con el código dado y sus cabeceras, sin las del transporte. */
async function pagina(peticion: Request, origen: string, ruta: string, codigo: number): Promise<Response> {
  const respuesta = await fetch(new URL(ruta, origen), { headers: acceso(peticion) });
  const cabeceras = new Headers(respuesta.headers);
  for (const nombre of ["content-encoding", "content-length", "etag", "age"]) cabeceras.delete(nombre);
  cabeceras.set("Content-Type", "text/html; charset=utf-8");
  cabeceras.set("Cache-Control", CACHE);
  // Con cleanUrls, /404 es 404.html, que Vercel puede servir ya con 404: vale el cuerpo.
  const conPagina = respuesta.ok || respuesta.status === 404;
  return new Response(conPagina ? respuesta.body : String(codigo), { status: codigo, headers: cabeceras });
}

/** La reescritura de vercel.json trae el identificador y el idioma en la consulta. */
export function rutaPedida(url: URL): string | null {
  const id = url.searchParams.get("id") ?? "";
  const ruta = `${url.searchParams.get("idioma") === "en" ? "/en/" : "/"}${id}`;
  return FICHA.test(ruta) ? ruta : null;
}

export async function GET(peticion: Request): Promise<Response> {
  const url = new URL(peticion.url);
  const ruta = rutaPedida(url);
  if (ruta === null) return pagina(peticion, url.origin, "/404", 404);
  cargada ??= cargar(url.origin, acceso(peticion));
  const lista = await cargada;
  if (lista === null) {
    cargada = undefined;
    // Sin la lista, como antes: un ataque abre la portada y lo demás no existe.
    const ataque = ATAQUE.exec(ruta);
    if (ataque === null) return pagina(peticion, url.origin, "/404", 404);
    return pagina(peticion, url.origin, ataque[1] === "en" ? "/en" : "/", 200);
  }
  const decision = decidirBorde(ruta, lista.rutas, lista.ataques);
  if (decision.tipo === "redirigir") {
    return new Response(null, {
      status: 308,
      headers: { Location: new URL(decision.destino, url).toString(), "Cache-Control": CACHE },
    });
  }
  if (decision.tipo === "portada") return pagina(peticion, url.origin, decision.ruta, 200);
  return pagina(peticion, url.origin, "/404", 404);
}

export const HEAD = GET;
