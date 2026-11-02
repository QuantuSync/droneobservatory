// Registro del service worker (public/sw.js) de la app instalable. Solo en droneobservatory.eu y en
// sus vistas previas de Vercel: en local y en cualquier otro sitio, la web va sin él.
//
// Al terminar de cargar, la página manda al service worker la lista de lo que ya ha descargado de la
// web (código, contornos del mapa, datos generales y, si se ha abierto, la ficha), para que lo guarde
// desde la caché HTTP del navegador sin volver a pedirlo. Así la primera visita ya deja la app lista
// para abrirse sin conexión, sin peticiones de más.

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
const GUARDABLES = ["/assets/", "/datos/", "/mapa/", "/iconos/", "/banderas/", "/marca/"];

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

function mandarLista(trabajador: ServiceWorker | null): void {
  if (trabajador === null) return;
  try {
    const recursos = performance.getEntriesByType("resource").map((entrada) => entrada.name);
    trabajador.postMessage({
      tipo: "guardar",
      direcciones: direccionesAGuardar(recursos, window.location.origin, window.location.pathname),
    });
  } catch {
    // Sin la lista no pasa nada: lo que se pida con el service worker activo se guarda igual.
  }
}

let registrado = false;

/** Registra el service worker cuando la página ha terminado de cargar. No hace nada fuera del sitio. */
export function registrarApp(): void {
  if (registrado || typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  if (!sitioConApp(window.location.hostname)) return;
  registrado = true;
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
