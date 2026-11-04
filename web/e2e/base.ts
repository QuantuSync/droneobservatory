// `test` y `expect` de los recorridos: los de Playwright con una caché del mapa de fondo.
//
// Hasta el 27 de octubre de 2026 cada prueba abría un contexto nuevo y cargaba el mapa de fondo
// desde la web (de 37 a 57 trozos de europa-z14.pmtiles por carga), en 11 trabajos y varias veces
// por hora: el 97 % de las peticiones que recibía Vercel eran de los recorridos. Ahora cada trozo
// se pide una vez y se guarda en una carpeta del ejecutor (TESELAS_CACHE; en local,
// web/.cache/teselas), que la CI conserva entre ejecuciones con su caché; las siguientes veces se
// sirve desde ahí (son los mismos bytes: el nombre del fichero cambia si cambia el mapa).
//
// - Teselas reales en una prueba: test.use({ teselasReales: true }); en todas: TESELAS_REALES=1.
//   La única prueba que comprueba el camino real es «el mapa de fondo se sirve por la web»
//   (e2e/web.spec.ts).
// - En WebKit (iPhone y escritorio-webkit) no hay caché: con la interceptación de peticiones
//   puesta, WebKit da «Importing a module script failed» al navegar mientras la página aún carga
//   su código (las fichas unidas que redirigen, en control-fichas-recorridos.spec.ts; visto en el
//   PR del 27 de octubre de 2026, y sin interceptar no pasa). Son 2 de los 11 trabajos.
// - Las rutas que registra una prueba después tienen prioridad (Playwright prueba primero la
//   última registrada, y las de la página antes que las del contexto).
// - Al añadir algún trozo se deja el fichero «nuevos» en la carpeta: la CI solo guarda la caché
//   si lo encuentra.
//
// Las pruebas importan `test` y `expect` de aquí, no de @playwright/test (tests/teselas.test.ts
// lo comprueba).

import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test as base } from "@playwright/test";
import type { Browser, BrowserContext, Request, Route } from "@playwright/test";

import { cabecerasAGuardar, sobrantes, trozoDe } from "./teselas.ts";

export { expect };

const CARPETA = process.env.TESELAS_CACHE ?? join(dirname(fileURLToPath(import.meta.url)), "..", ".cache", "teselas");
const REALES_SIEMPRE = process.env.TESELAS_REALES === "1";

const cuenta = { red: 0, cache: 0 };
let reales = REALES_SIEMPRE;
let enWebkit = false;
const instalados = new WeakSet<BrowserContext>();
const contados = new WeakSet<BrowserContext>();
const deLaCache = new WeakSet<Request>();

// Cuántas peticiones llegan a la web que se recorre, por quién las hace (la página o el service
// worker de la app), por cómo se sirven y por tipo de ruta: se escribe una línea «peticiones:» por
// trabajo al terminar. Sirve para medir lo que cuesta cada pasada en Vercel (noviembre de 2026).
// Las del service worker solo se ven en Chromium.
const SITIO = (() => {
  try {
    return new URL(process.env.BASE ?? "https://droneobservatory.eu").host;
  } catch {
    return "droneobservatory.eu";
  }
})();
const peticiones = new Map<string, number>();

function tipoDeRuta(camino: string): string {
  for (const prefijo of ["/almacen/", "/assets/", "/datos/", "/api/", "/mapa/", "/iconos/", "/banderas/", "/marca/"]) {
    if (camino.startsWith(prefijo)) return prefijo.slice(1, -1);
  }
  return camino.includes(".") ? "otros" : "paginas";
}

function anotar(pedido: Request, como: string): void {
  let url: URL;
  try {
    url = new URL(pedido.url());
  } catch {
    return;
  }
  if (url.host !== SITIO) return;
  const quien = pedido.serviceWorker() === null ? "pagina" : "sw";
  const clave = `${quien} ${como} ${tipoDeRuta(url.pathname)}`;
  peticiones.set(clave, (peticiones.get(clave) ?? 0) + 1);
}

function contar(contexto: BrowserContext): void {
  if (contados.has(contexto)) return;
  contados.add(contexto);
  contexto.on("response", (respuesta) => {
    const pedido = respuesta.request();
    if (deLaCache.has(pedido)) anotar(pedido, "cache-teselas");
    else if (respuesta.fromServiceWorker()) anotar(pedido, "cache-sw");
    else anotar(pedido, "red");
  });
  contexto.on("requestfailed", (pedido) => anotar(pedido, "fallida"));
}

type OpcionesDeContexto = Parameters<Browser["newContext"]>[0];

/**
 * Las opciones de un contexto que abre una prueba con browser.newContext(): sin el service worker
 * de la app si la prueba no dice otra cosa (lo mismo que playwright.config.ts para los demás; el
 * motivo está allí). Los recorridos de la app lo piden con serviceWorkers: "allow".
 */
function sinServiceWorker(opciones: OpcionesDeContexto): OpcionesDeContexto {
  return { serviceWorkers: "block", ...opciones };
}

function resumenPeticiones(): string {
  const total = { red: 0, fallida: 0 };
  for (const [clave, n] of peticiones) {
    if (clave.includes(" red ")) total.red += n;
    if (clave.includes(" fallida ")) total.fallida += n;
  }
  const detalle = Object.fromEntries([...peticiones].sort((a, b) => b[1] - a[1]));
  return `peticiones: ${JSON.stringify({ sitio: SITIO, ...total, detalle })}`;
}

/** Quita lo más antiguo si la caché ha crecido demasiado (es del ejecutor, no del repositorio). */
function recortar(): void {
  try {
    const ficheros = readdirSync(CARPETA)
      .filter((n) => n.endsWith(".bin") || n.endsWith(".json"))
      .map((nombre) => {
        const s = statSync(join(CARPETA, nombre));
        return { nombre, bytes: s.size, fecha: s.mtimeMs };
      });
    for (const nombre of sobrantes(ficheros)) unlinkSync(join(CARPETA, nombre));
  } catch {
    // Sin carpeta o sin permiso: se trabaja sin recortar.
  }
}

function leer(clave: string): { cuerpo: Buffer; cabeceras: Record<string, string> } | null {
  try {
    const cabeceras = JSON.parse(readFileSync(join(CARPETA, `${clave}.json`), "utf8")) as Record<string, string>;
    const cuerpo = readFileSync(join(CARPETA, `${clave}.bin`));
    if (typeof cabeceras !== "object" || cuerpo.length === 0) return null;
    return { cuerpo, cabeceras };
  } catch {
    return null;
  }
}

function guardar(clave: string, cuerpo: Buffer, cabeceras: Record<string, string>): void {
  try {
    mkdirSync(CARPETA, { recursive: true });
    writeFileSync(join(CARPETA, `${clave}.bin`), cuerpo);
    writeFileSync(join(CARPETA, `${clave}.json`), JSON.stringify(cabeceras));
    writeFileSync(join(CARPETA, "nuevos"), "");
  } catch {
    // Sin poder guardar, la prueba sigue: el trozo ya se ha servido de la red.
  }
}

async function servir(ruta: Route): Promise<void> {
  const pedido = ruta.request();
  const trozo = pedido.method() === "GET" ? trozoDe(pedido.url(), (await pedido.headerValue("range")) ?? undefined) : null;
  if (trozo === null || reales) {
    await ruta.fallback();
    return;
  }
  const guardado = leer(trozo.clave);
  if (guardado !== null) {
    cuenta.cache += 1;
    deLaCache.add(pedido);
    await ruta.fulfill({ status: trozo.estado, headers: guardado.cabeceras, body: guardado.cuerpo });
    return;
  }
  try {
    const respuesta = await ruta.fetch();
    cuenta.red += 1;
    if (respuesta.status() === trozo.estado) {
      guardar(trozo.clave, await respuesta.body(), cabecerasAGuardar(respuesta.headers()));
    }
    await ruta.fulfill({ response: respuesta });
  } catch {
    // La prueba ya ha terminado (o la red ha fallado): la petición en vuelo no importa.
    await ruta.abort().catch(() => undefined);
  }
}

async function instalar(contexto: BrowserContext): Promise<void> {
  contar(contexto);
  if (enWebkit || instalados.has(contexto)) return;
  instalados.add(contexto);
  await contexto.route((url) => trozoDe(url.href, "bytes=0-0") !== null, servir);
}

export const test = base.extend<{ teselasReales: boolean; _teselas: undefined }, { _cacheTeselas: undefined }>({
  teselasReales: [false, { option: true }],
  // Una vez por proceso: recortar la caché y poner la ruta también en los contextos que las
  // pruebas abren por su cuenta (browser.newContext).
  _cacheTeselas: [
    async ({ browser, browserName }, usar) => {
      enWebkit = browserName === "webkit";
      if (enWebkit) {
        const original = browser.newContext.bind(browser);
        browser.newContext = async (opciones?: OpcionesDeContexto) => {
          const contexto = await original(sinServiceWorker(opciones));
          contar(contexto);
          return contexto;
        };
        await usar(undefined);
        browser.newContext = original;
        console.log(resumenPeticiones());
        return;
      }
      if (!existsSync(CARPETA)) mkdirSync(CARPETA, { recursive: true });
      recortar();
      const original = browser.newContext.bind(browser);
      browser.newContext = async (opciones?: OpcionesDeContexto) => {
        const contexto = await original(sinServiceWorker(opciones));
        await instalar(contexto);
        return contexto;
      };
      await usar(undefined);
      browser.newContext = original;
      console.log(`teselas: ${cuenta.red} trozos de la red, ${cuenta.cache} de la caché (${CARPETA})`);
      console.log(resumenPeticiones());
    },
    { scope: "worker", auto: true },
  ],
  _teselas: [
    async ({ teselasReales }, usar) => {
      reales = REALES_SIEMPRE || teselasReales;
      await usar(undefined);
      reales = REALES_SIEMPRE;
    },
    { auto: true },
  ],
  context: async ({ context }, usar) => {
    await instalar(context);
    await usar(context);
  },
});
