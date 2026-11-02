// Registro del service worker (public/sw.js) de la app instalable. Solo en droneobservatory.eu y en
// sus vistas previas de Vercel: en local y en cualquier otro sitio, la web va sin él.
//
// Al terminar de cargar, la página manda al service worker la lista de lo que ya ha descargado de la
// web (código, contornos del mapa, datos generales y, si se ha abierto, la ficha), para que lo guarde
// desde la caché HTTP del navegador sin volver a pedirlo. Así la primera visita ya deja la app lista
// para abrirse sin conexión, sin peticiones de más. Después, lo que se va descargando (el código que
// se carga aparte, como el del mapa o el de la ficha, y los datos de cada ficha abierta) se manda en
// tandas, con un PerformanceObserver: el service worker no guarda al vuelo lo que no tiene copia
// (public/sw.js), y la lista de performance se llena a las 250 entradas.

/** El evento con el que la web enseña «Hay una versión nueva · Actualizar» (componentes/AvisoVersion.tsx). */
export const EVENTO_VERSION_NUEVA = "eodi:version-nueva";

const PRODUCCION = new Set(["droneobservatory.eu", "www.droneobservatory.eu"]);
/** Las vistas previas de Vercel del proyecto (droneobservatory-<despliegue o rama>-<equipo>.vercel.app). */
const VISTA_PREVIA = /^droneobservatory-[a-z0-9-]+-lucas-projects-cc09a9dd\.vercel\.app$/;

/** Si el service worker se registra en este sitio. */
export function sitioConApp(nombre: string): boolean {
  return PRODUCCION.has(nombre) || VISTA_PREVIA.test(nombre);
}

/** Prefijos de lo que se manda guardar: lo mismo que acepta public/sw.js (reglaDe). */
const GUARDABLES = ["/assets/", "/datos/", "/mapa/", "/iconos/", "/banderas/", "/marca/", "/arranque.js"];
/** Cuánto se espera para mandar juntas las descargas nuevas. */
const TANDA_MS = 1500;

/**
 * Lo que la página manda guardar: las direcciones de este sitio ya descargadas que el service worker
 * acepta, y la propia página (marcada con #pagina). Nunca /almacen/, /api/ ni /datos/versiones/.
 */
export function direccionesAGuardar(recursos: readonly string[], origen: string, pagina: string): string[] {
  const lista = new Set<string>();
  lista.add(`${pagina}#pagina`);
  for (const recurso of recursos) {
    let url: URL;
    try {
      url = new URL(recurso);
    } catch {
      continue;
    }
    if (url.origin !== origen) continue;
    if (url.pathname.startsWith("/datos/versiones/")) continue;
    if (GUARDABLES.some((prefijo) => url.pathname.startsWith(prefijo))) lista.add(url.pathname);
  }
  return [...lista];
}

function mandar(trabajador: ServiceWorker | null, recursos: readonly string[]): void {
  if (trabajador === null) return;
  try {
    trabajador.postMessage({
      tipo: "guardar",
      direcciones: direccionesAGuardar(recursos, window.location.origin, window.location.pathname),
    });
  } catch {
    // Sin la lista, se guardará la próxima vez.
  }
}

function mandarLista(trabajador: ServiceWorker | null): void {
  try {
    mandar(
      trabajador,
      performance.getEntriesByType("resource").map((entrada) => entrada.name),
    );
  } catch {
    // Sin performance no hay lista.
  }
}

/** Manda en tandas lo que la página va descargando (también lo que no cabe en la lista de performance). */
function vigilarDescargas(trabajador: () => ServiceWorker | null): void {
  if (typeof PerformanceObserver === "undefined") return;
  const pendientes = new Set<string>();
  let temporizador: number | undefined;
  try {
    new PerformanceObserver((lista) => {
      for (const entrada of lista.getEntries()) pendientes.add(entrada.name);
      if (temporizador !== undefined) return;
      temporizador = window.setTimeout(() => {
        temporizador = undefined;
        const recursos = [...pendientes];
        pendientes.clear();
        mandar(trabajador(), recursos);
      }, TANDA_MS);
    }).observe({ type: "resource", buffered: true });
  } catch {
    // Sin observador queda la lista del principio y la de al dejar la pestaña.
  }
}

let registrado = false;

/** Registra el service worker cuando la página ha terminado de cargar. No hace nada fuera del sitio. */
export function registrarApp(): void {
  if (registrado || typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  if (!sitioConApp(window.location.hostname)) return;
  registrado = true;
  try {
    // La lista de performance se llena a las 250 entradas (el mapa pide muchas): más sitio.
    performance.setResourceTimingBufferSize(1000);
  } catch {
    // Sin performance no hay lista: el service worker guarda igual lo que ve pasar.
  }
  const contenedor = navigator.serviceWorker;
  let habiaControlador = contenedor.controller !== null;
  contenedor.addEventListener("controllerchange", () => {
    // Una versión nueva del service worker ha tomado la página: el código de la página puede ser de
    // antes. Con la primera instalación no hay aviso (no había ninguno).
    if (habiaControlador) window.dispatchEvent(new Event(EVENTO_VERSION_NUEVA));
    habiaControlador = true;
  });
  contenedor.addEventListener("message", (evento: MessageEvent<unknown>) => {
    const datos = evento.data;
    if (typeof datos === "object" && datos !== null && (datos as { tipo?: unknown }).tipo === "version-nueva") {
      window.dispatchEvent(new Event(EVENTO_VERSION_NUEVA));
    }
  });
  const registrar = () => {
    contenedor
      .register("/sw.js", { scope: "/", updateViaCache: "none" })
      .then(async (registro) => {
        const listo = await contenedor.ready;
        const trabajador = () => listo.active ?? registro.active;
        // Lo descargado al cargar, y otra vez al dejar la pestaña (el mapa y las fichas abiertas).
        window.setTimeout(() => mandarLista(trabajador()), 3000);
        vigilarDescargas(trabajador);
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState === "hidden") mandarLista(trabajador());
        });
      })
      .catch(() => {
        // Sin service worker la web funciona igual que antes.
      });
  };
  if (document.readyState === "complete") registrar();
  else window.addEventListener("load", registrar, { once: true });
}
