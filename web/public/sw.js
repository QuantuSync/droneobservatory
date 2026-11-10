// Service worker de la web (la app instalable). Escrito a mano, sin dependencias. Lo registra
// src/app/registro.ts solo en droneobservatory.eu y en sus vistas previas de Vercel.
//
// Qué guarda y cómo (reglaDe):
// - «huella»: los ficheros del build con huella en el nombre (/assets/…), primero de la caché: el
//   nombre cambia si cambia el contenido.
// - «pagina»: el HTML (la portada de cada idioma y las fichas ya abiertas), primero de la red. Si la
//   red no responde en ESPERA_PAGINA_MS y hay copia, se sirve la copia y, cuando llega la nueva, si
//   nombra otro código, la página recibe «version-nueva» («Hay una versión nueva · Actualizar»).
//   Sin red, la copia de esa dirección o, si no la hay, la portada de su idioma.
// - «datos»: /datos/…, primero de la red (el navegador sigue preguntando con If-None-Match: la
//   caché HTTP está debajo); sin red o con un fallo del servidor, la última copia guardada.
// - «estatico»: contornos y fuentes del mapa, iconos, banderas y los QR de los avisos: la copia guardada y, detrás, se
//   pide de nuevo (la caché HTTP del navegador responde casi siempre sin ir a la red).
// - Nunca: /almacen/ (el mapa de fondo, por trozos), /api/, /datos/versiones/, una navegación a un
//   fichero (una descarga, /sitemap.xml, una imagen: no es una página), los manifiestos (los
//   pide el navegador por su cuenta), otros sitios (el contador de visitas, la reserva de Helsinki),
//   peticiones con Range y todo lo que no sea GET.
//
// El código, los datos y lo estático se piden a la red con una petición nueva por su dirección (aparte),
// no con la de la página: Safari corta las peticiones de una página que se deja a mitad de carga, y
// con la de la página el corte llegaba al service worker y de él a la página como un error
// («FetchEvent.respondWith received an error: TypeError: Load failed», «Importing a module script
// failed»). La petición nueva termina y se guarda aunque la página ya no esté.
//
// Nada se guarda por adelantado por ficha: la página manda al terminar de cargar la lista de lo que
// ya ha descargado (mensaje «guardar») y se guarda desde la caché HTTP, sin volver a pedirlo.
// Sin clients.claim(): la página que registra el service worker no pasa a sus manos a mitad de carga;
// la siguiente carga, sí. Una versión nueva de este fichero se activa en cuanto se instala.
"use strict";

const VERSION = "1";
const PREFIJO = "eodi-";
const CACHE_PAGINAS = `${PREFIJO}paginas-v${VERSION}`;
const CACHE_HUELLA = `${PREFIJO}huella-v${VERSION}`;
const CACHE_DATOS = `${PREFIJO}datos-v${VERSION}`;
const CACHE_ESTATICO = `${PREFIJO}estatico-v${VERSION}`;
const CACHES_EN_USO = [CACHE_PAGINAS, CACHE_HUELLA, CACHE_DATOS, CACHE_ESTATICO];
/** Cuántas entradas guarda cada caché como mucho: se van las más antiguas. */
const TOPES = {
  [CACHE_PAGINAS]: 40,
  [CACHE_HUELLA]: 120,
  [CACHE_DATOS]: 150,
  [CACHE_ESTATICO]: 400,
};
const CACHE_DE_REGLA = {
  pagina: CACHE_PAGINAS,
  huella: CACHE_HUELLA,
  datos: CACHE_DATOS,
  estatico: CACHE_ESTATICO,
};
const ESPERA_PAGINA_MS = 4000;
const MAXIMO_A_GUARDAR = 300;

const NUNCA = ["/almacen/", "/api/", "/datos/versiones/"];
const ESTATICOS = ["/mapa/", "/iconos/", "/banderas/", "/marca/", "/capturas/", "/avisos/qr/"];
const ESTATICOS_SUELTOS = [
  "/favicon.ico",
  "/favicon.svg",
  "/apple-touch-icon.png",
];
/** Scripts sin huella de public/: primero de la red, como los datos. */
const SCRIPTS_SIN_HUELLA = ["/arranque.js", "/visitas.js", "/borrar-visita.js"];

/**
 * Una navegación a un fichero (una descarga de /datos/, /sitemap.xml, /llms.txt, una imagen) no es
 * una página: guardada como tal, ocupaba el sitio de una ficha y, sin conexión, en su lugar salía
 * la portada (un «CSV» con HTML dentro). Va a la red, como sin service worker.
 */
function esFichero(ruta) {
  if (ruta.startsWith("/datos/")) return true;
  const nombre = ruta.slice(ruta.lastIndexOf("/") + 1);
  return /\.[A-Za-z0-9]+$/.test(nombre) && !nombre.endsWith(".html");
}

/**
 * La regla de una petición: "pagina", "huella", "datos", "estatico" o null (no se toca).
 * `peticion`: { url, method, mode, headers } (una Request o algo con esa forma).
 */
function reglaDe(peticion, origen) {
  if ((peticion.method ?? "GET") !== "GET") return null;
  let url;
  try {
    url = new URL(peticion.url);
  } catch {
    return null;
  }
  if (url.origin !== origen) return null;
  const cabeceras = peticion.headers;
  if (cabeceras !== undefined && typeof cabeceras.has === "function" && cabeceras.has("range")) return null;
  const ruta = url.pathname;
  if (NUNCA.some((prefijo) => ruta.startsWith(prefijo))) return null;
  if (ruta === "/sw.js") return null;
  if (peticion.mode === "navigate") return esFichero(ruta) ? null : "pagina";
  if (ruta.startsWith("/assets/")) return "huella";
  if (ruta.startsWith("/datos/")) return "datos";
  if (SCRIPTS_SIN_HUELLA.includes(ruta)) return "datos";
  if (ESTATICOS.some((prefijo) => ruta.startsWith(prefijo)) || ESTATICOS_SUELTOS.includes(ruta)) return "estatico";
  return null;
}

/** La portada del idioma de una dirección: /en para /en y /en/…; / para el resto. */
function portadaDe(ruta) {
  return ruta === "/en" || ruta.startsWith("/en/") ? "/en" : "/";
}

/** La clave con la que se guarda: la dirección sin búsqueda ni fragmento (los filtros no cuentan). */
function claveDe(url) {
  const u = new URL(url);
  return `${u.origin}${u.pathname}`;
}

/** Los ficheros con huella que nombra un HTML: si cambian, hay una versión nueva del código. */
function codigoDe(html) {
  return [...new Set(html.match(/\/assets\/[A-Za-z0-9._-]+/g) ?? [])].sort().join(" ");
}

/**
 * Una petición nueva a la misma dirección, sin la señal de corte de la página (ni su modo o destino):
 * la usan el código, los datos y lo estático. Las páginas van con la suya (una navegación no se puede
 * rehacer, y su corte no llega a ninguna página). Conserva el «sin caché» de quien la pide: los
 * reintentos de la web (src/datos/reintentos.ts) vuelven a pedir con «no-cache» por si el navegador
 * guardó una respuesta mala, y sin esto volvían a su caché HTTP.
 */
const SIN_CACHE_HTTP = ["no-cache", "reload", "no-store"];
function aparte(peticion) {
  const opciones = { method: "GET", credentials: "same-origin" };
  if (SIN_CACHE_HTTP.includes(peticion.cache)) opciones.cache = peticion.cache;
  return new Request(peticion.url, opciones);
}

function guardable(respuesta) {
  return respuesta !== undefined && respuesta !== null && respuesta.status === 200 && respuesta.type === "basic";
}

/** Quita las entradas más antiguas de una caché por encima de su tope. */
async function recortar(cajas, nombre) {
  const tope = TOPES[nombre];
  if (tope === undefined) return;
  const caja = await cajas.open(nombre);
  const claves = await caja.keys();
  const sobran = claves.length - tope;
  for (let i = 0; i < sobran; i += 1) await caja.delete(claves[i]);
}

/** Guarda una copia (la entrada se mueve al final: es la más reciente). */
async function guardar(cajas, nombre, clave, respuesta) {
  const caja = await cajas.open(nombre);
  await caja.delete(clave);
  await caja.put(clave, respuesta);
  await recortar(cajas, nombre);
}

function crearManejador(entorno) {
  const { cajas, pedir, origen, avisar, esperaMs = ESPERA_PAGINA_MS } = entorno;

  async function copia(nombre, clave) {
    const caja = await cajas.open(nombre);
    return (await caja.match(clave, { ignoreSearch: true })) ?? null;
  }

  async function huella(peticion) {
    const clave = claveDe(peticion.url);
    const guardada = await copia(CACHE_HUELLA, clave);
    if (guardada !== null) return guardada;
    const respuesta = await pedir(aparte(peticion));
    if (guardable(respuesta)) await guardar(cajas, CACHE_HUELLA, clave, respuesta.clone());
    return respuesta;
  }

  async function datos(peticion) {
    const clave = claveDe(peticion.url);
    try {
      const respuesta = await pedir(aparte(peticion));
      if (guardable(respuesta)) {
        await guardar(cajas, CACHE_DATOS, clave, respuesta.clone());
        return respuesta;
      }
      if (respuesta.status >= 500) return (await copia(CACHE_DATOS, clave)) ?? respuesta;
      return respuesta;
    } catch (error) {
      const guardada = await copia(CACHE_DATOS, clave);
      if (guardada !== null) return guardada;
      throw error;
    }
  }

  async function estatico(peticion, esperar) {
    const clave = claveDe(peticion.url);
    const guardada = await copia(CACHE_ESTATICO, clave);
    const nueva = pedir(aparte(peticion)).then(async (respuesta) => {
      if (guardable(respuesta)) await guardar(cajas, CACHE_ESTATICO, clave, respuesta.clone());
      return respuesta;
    });
    if (guardada !== null) {
      esperar(nueva.catch(() => undefined));
      return guardada;
    }
    return nueva;
  }

  async function pagina(peticion, esperar, cliente) {
    const clave = claveDe(peticion.url);
    const guardada = await copia(CACHE_PAGINAS, clave);
    const nueva = pedir(peticion).then(async (respuesta) => {
      if (guardable(respuesta)) await guardar(cajas, CACHE_PAGINAS, clave, respuesta.clone());
      return respuesta;
    });
    const red = nueva.then(
      (respuesta) => ({ respuesta }),
      (error) => ({ error }),
    );
    const plazo =
      guardada === null
        ? new Promise(() => undefined)
        : new Promise((hecho) => setTimeout(() => hecho({ plazo: true }), esperaMs));
    const primero = await Promise.race([red, plazo]);
    if (primero.plazo === true) {
      // La nueva sigue llegando: se guarda y, si trae otro código, se avisa a la página.
      const textoAntes = guardada.clone().text();
      esperar(
        nueva.then(
          async (respuesta) => {
            if (!guardable(respuesta)) return;
            const [antes, ahora] = await Promise.all([textoAntes, respuesta.clone().text()]);
            if (codigoDe(antes) !== codigoDe(ahora)) await avisar(cliente, { tipo: "version-nueva" });
          },
          () => undefined,
        ),
      );
      return guardada;
    }
    if (primero.respuesta !== undefined) {
      const respuesta = primero.respuesta;
      if (respuesta.status >= 500 && guardada !== null) return guardada;
      return respuesta;
    }
    // Sin red: la copia de esta dirección o la portada de su idioma.
    if (guardada !== null) return guardada;
    const portada = await copia(CACHE_PAGINAS, `${origen}${portadaDe(new URL(peticion.url).pathname)}`);
    if (portada !== null) return portada;
    throw primero.error;
  }

  /** La respuesta a una petición, o null si no se toca (va a la red como sin service worker). */
  function responder(peticion, esperar = () => undefined, cliente = null) {
    const regla = reglaDe(peticion, origen);
    if (regla === "huella") return huella(peticion);
    if (regla === "datos") return datos(peticion);
    if (regla === "estatico") return estatico(peticion, esperar);
    if (regla === "pagina") return pagina(peticion, esperar, cliente);
    return null;
  }

  /**
   * Guarda lo que la página ya ha descargado (sus direcciones), desde la caché HTTP del navegador
   * («force-cache»: sin volver a la red si está ahí). Las de fichas solo si se han abierto.
   */
  async function guardarLista(direcciones) {
    let guardadas = 0;
    for (const direccion of direcciones.slice(0, MAXIMO_A_GUARDAR)) {
      let url;
      try {
        url = new URL(direccion, origen);
      } catch {
        continue;
      }
      const html = direccion.endsWith("#pagina");
      const regla = reglaDe({ url: url.href, method: "GET", mode: html ? "navigate" : "cors" }, origen);
      if (regla === null) continue;
      const nombre = CACHE_DE_REGLA[regla];
      const clave = claveDe(url.href);
      if ((await copia(nombre, clave)) !== null) continue;
      try {
        const respuesta = await pedir(new Request(clave, { cache: "force-cache", credentials: "same-origin" }));
        if (guardable(respuesta)) {
          await guardar(cajas, nombre, clave, respuesta);
          guardadas += 1;
        }
      } catch {
        // Sin red o sin copia: se guardará la próxima vez.
      }
    }
    return guardadas;
  }

  /** Borra las cachés de versiones anteriores de este fichero. */
  async function limpiarViejas() {
    const nombres = await cajas.keys();
    await Promise.all(
      nombres.filter((n) => n.startsWith(PREFIJO) && !CACHES_EN_USO.includes(n)).map((n) => cajas.delete(n)),
    );
  }

  /** Borra todas las cachés de la web («Borrar mi última visita»). */
  async function borrarTodo() {
    const nombres = await cajas.keys();
    await Promise.all(nombres.filter((n) => n.startsWith(PREFIJO)).map((n) => cajas.delete(n)));
  }

  return { responder, guardarLista, limpiarViejas, borrarTodo };
}

// En el navegador (en las pruebas, `self` es un objeto de mentira sin addEventListener).
if (typeof self !== "undefined" && typeof self.addEventListener === "function" && typeof caches !== "undefined") {
  const manejador = crearManejador({
    cajas: caches,
    pedir: (peticion) => fetch(peticion),
    origen: self.location.origin,
    avisar: async (id, mensaje) => {
      if (id === null || id === undefined || id === "") return;
      const cliente = await self.clients.get(id);
      cliente?.postMessage(mensaje);
    },
  });

  self.addEventListener("install", () => {
    void self.skipWaiting();
  });

  self.addEventListener("activate", (evento) => {
    evento.waitUntil(manejador.limpiarViejas());
  });

  self.addEventListener("fetch", (evento) => {
    const respuesta = manejador.responder(
      evento.request,
      (promesa) => evento.waitUntil(promesa),
      evento.resultingClientId || evento.clientId,
    );
    if (respuesta !== null) evento.respondWith(respuesta);
  });

  self.addEventListener("message", (evento) => {
    const datos = evento.data;
    if (datos === null || typeof datos !== "object") return;
    if (datos.tipo === "guardar" && Array.isArray(datos.direcciones)) {
      evento.waitUntil(manejador.guardarLista(datos.direcciones.filter((d) => typeof d === "string")));
    } else if (datos.tipo === "borrar") {
      evento.waitUntil(manejador.borrarTodo());
    }
  });
}

// Para las pruebas (tests/sw.test.ts): las reglas y el manejador sin el navegador.
if (typeof self !== "undefined") {
  self.eodiSw = { reglaDe, portadaDe, claveDe, codigoDe, crearManejador, CACHES_EN_USO, PREFIJO, VERSION };
}
