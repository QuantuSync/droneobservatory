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
// - Desde el 4 de noviembre de 2026, igual con los ficheros fijos de la web (e2e/teselas.ts, «Los
//   ficheros fijos»): el código de /assets/ con huella en el nombre y los ficheros públicos del mapa
//   (contornos, fuentes, sprites, marca, banderas, iconos), en otra carpeta (FIJOS_CACHE; en
//   local, web/.cache/fijos) con su propia caché de Actions, ligada a la huella de esos ficheros.
//   Un fichero público solo se sirve de la caché si sus bytes son los del repositorio, y solo se
//   guarda si la web ha servido exactamente esos bytes. La única prueba que pide de verdad el
//   código y un contorno es «el código y los contornos se sirven por la web» (e2e/web.spec.ts).
//   Los recorridos de la app (e2e/app-recorridos.spec.ts, con su service worker) los piden siempre
//   a la web, como antes. En WebKit tampoco: no hay interceptación (arriba).
//
// Las pruebas importan `test` y `expect` de aquí, no de @playwright/test (tests/teselas.test.ts
// lo comprueba).

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test as base } from "@playwright/test";
import type { Browser, BrowserContext, Request, Route } from "@playwright/test";

import {
  OBJETIVO_FIJOS_BYTES,
  TOPE_FIJOS_BYTES,
  cabecerasAGuardar,
  claveDePublico,
  codigoGuardable,
  fijoDe,
  sobrantes,
  trozoDe,
} from "./teselas.ts";
import type { Fijo } from "./teselas.ts";

export { expect };

const CARPETA = process.env.TESELAS_CACHE ?? join(dirname(fileURLToPath(import.meta.url)), "..", ".cache", "teselas");
const REALES_SIEMPRE = process.env.TESELAS_REALES === "1";
const CARPETA_FIJOS = process.env.FIJOS_CACHE ?? join(dirname(fileURLToPath(import.meta.url)), "..", ".cache", "fijos");
const PUBLICA = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
// Los recorridos de la app piden los ficheros fijos a la web, como antes (su service worker los
// guarda y los sirve: es lo que prueban).
const SIN_FIJOS = /app-recorridos\.spec\.ts$/;

const cuenta = { red: 0, cache: 0 };
const cuentaFijos = { red: 0, cache: 0, guardados: 0 };
let reales = REALES_SIEMPRE;
let fijosReales = REALES_SIEMPRE;
let enWebkit = false;
const instalados = new WeakSet<BrowserContext>();
const contados = new WeakSet<BrowserContext>();
const deLaCache = new WeakSet<Request>();
const deLosFijos = new WeakSet<Request>();

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
    else if (deLosFijos.has(pedido)) anotar(pedido, "cache-fijos");
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
function recortar(carpeta = CARPETA, tope?: number, objetivo?: number): void {
  try {
    const ficheros = readdirSync(carpeta)
      .filter((n) => n.endsWith(".bin") || n.endsWith(".json"))
      .map((nombre) => {
        const s = statSync(join(carpeta, nombre));
        return { nombre, bytes: s.size, fecha: s.mtimeMs };
      });
    for (const nombre of sobrantes(ficheros, tope, objetivo)) unlinkSync(join(carpeta, nombre));
  } catch {
    // Sin carpeta o sin permiso: se trabaja sin recortar.
  }
}

function leer(clave: string, carpeta = CARPETA): { cuerpo: Buffer; cabeceras: Record<string, string> } | null {
  try {
    const cabeceras = JSON.parse(readFileSync(join(carpeta, `${clave}.json`), "utf8")) as Record<string, string>;
    const cuerpo = readFileSync(join(carpeta, `${clave}.bin`));
    if (typeof cabeceras !== "object" || cuerpo.length === 0) return null;
    return { cuerpo, cabeceras };
  } catch {
    return null;
  }
}

function guardar(clave: string, cuerpo: Buffer, cabeceras: Record<string, string>, carpeta = CARPETA): void {
  try {
    mkdirSync(carpeta, { recursive: true });
    writeFileSync(join(carpeta, `${clave}.bin`), cuerpo);
    writeFileSync(join(carpeta, `${clave}.json`), JSON.stringify(cabeceras));
    writeFileSync(join(carpeta, "nuevos"), "");
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

const huellasLocales = new Map<string, string | null>();

/** La huella sha256 del fichero de web/public que corresponde a un camino, o null si no existe. */
function huellaLocal(camino: string): string | null {
  const guardada = huellasLocales.get(camino);
  if (guardada !== undefined) return guardada;
  let huella: string | null;
  try {
    const fichero = join(PUBLICA, ...camino.split("/").filter((p) => p !== ""));
    huella = createHash("sha256").update(readFileSync(fichero)).digest("hex");
  } catch {
    huella = null;
  }
  huellasLocales.set(camino, huella);
  return huella;
}

/** La clave en la caché de un fichero fijo, o null si no puede servirse de la caché. */
function claveDeFijo(fijo: Fijo): string | null {
  if (fijo.tipo === "codigo") return fijo.clave ?? null;
  const huella = huellaLocal(fijo.camino);
  return huella === null ? null : claveDePublico(huella);
}

/** Si lo que ha servido la web de un fichero fijo se puede guardar. */
function guardable(fijo: Fijo, estado: number, cabeceras: Record<string, string>, cuerpo: Buffer): boolean {
  if (!codigoGuardable(estado, cabeceras) || cuerpo.length === 0) return false;
  if (fijo.tipo === "codigo") return true;
  return createHash("sha256").update(cuerpo).digest("hex") === huellaLocal(fijo.camino);
}

async function servirFijo(ruta: Route, fijo: Fijo): Promise<void> {
  const pedido = ruta.request();
  const clave = claveDeFijo(fijo);
  if (clave === null || fijosReales || pedido.method() !== "GET" || (await pedido.headerValue("range")) !== null) {
    await ruta.fallback();
    return;
  }
  const guardado = leer(clave, CARPETA_FIJOS);
  if (guardado !== null) {
    cuentaFijos.cache += 1;
    deLosFijos.add(pedido);
    await ruta.fulfill({ status: 200, headers: guardado.cabeceras, body: guardado.cuerpo });
    return;
  }
  try {
    const respuesta = await ruta.fetch();
    cuentaFijos.red += 1;
    const cuerpo = await respuesta.body();
    if (guardable(fijo, respuesta.status(), respuesta.headers(), cuerpo)) {
      cuentaFijos.guardados += 1;
      guardar(clave, cuerpo, cabecerasAGuardar(respuesta.headers()), CARPETA_FIJOS);
    }
    await ruta.fulfill({ response: respuesta });
  } catch {
    // La prueba ya ha terminado (o la red ha fallado): la petición en vuelo no importa.
    await ruta.abort().catch(() => undefined);
  }
}

/** Los trozos del mapa de fondo y los ficheros fijos, cada uno con su caché. */
async function enrutar(ruta: Route): Promise<void> {
  const fijo = fijoDe(ruta.request().url(), SITIO);
  if (fijo !== null) await servirFijo(ruta, fijo);
  else await servir(ruta);
}

async function instalar(contexto: BrowserContext): Promise<void> {
  contar(contexto);
  if (enWebkit || instalados.has(contexto)) return;
  instalados.add(contexto);
  await contexto.route((url) => trozoDe(url.href, "bytes=0-0") !== null || fijoDe(url.href, SITIO) !== null, enrutar);
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
      if (!existsSync(CARPETA_FIJOS)) mkdirSync(CARPETA_FIJOS, { recursive: true });
      recortar(CARPETA_FIJOS, TOPE_FIJOS_BYTES, OBJETIVO_FIJOS_BYTES);
      const original = browser.newContext.bind(browser);
      browser.newContext = async (opciones?: OpcionesDeContexto) => {
        const contexto = await original(sinServiceWorker(opciones));
        await instalar(contexto);
        return contexto;
      };
      await usar(undefined);
      browser.newContext = original;
      console.log(`teselas: ${cuenta.red} trozos de la red, ${cuenta.cache} de la caché (${CARPETA})`);
      console.log(
        `fijos: ${cuentaFijos.red} de la red (${cuentaFijos.guardados} guardados), ${cuentaFijos.cache} de la caché (${CARPETA_FIJOS})`,
      );
      console.log(resumenPeticiones());
    },
    { scope: "worker", auto: true },
  ],
  _teselas: [
    async ({ teselasReales }, usar, info) => {
      reales = REALES_SIEMPRE || teselasReales;
      fijosReales = REALES_SIEMPRE || SIN_FIJOS.test(info.file);
      await usar(undefined);
      reales = REALES_SIEMPRE;
      fijosReales = REALES_SIEMPRE;
    },
    { auto: true },
  ],
  context: async ({ context }, usar) => {
    await instalar(context);
    await usar(context);
  },
});
