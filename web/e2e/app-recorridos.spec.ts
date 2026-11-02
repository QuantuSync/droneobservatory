// La app instalable (public/sw.js, src/app/): el manifiesto de cada idioma y el registro del service
// worker, abrir sin conexión (context.setOffline) con los últimos datos y la barra «Sin conexión»,
// una ficha ya visitada sin conexión, y una versión nueva que sustituye a la guardada. Corre en los
// recorridos de cada dispositivo; solo donde la web registra el service worker (droneobservatory.eu
// y sus vistas previas), no en local.

import type { Page } from "@playwright/test";

import { expect, test } from "./base.ts";
import { elegir, publicados } from "./publicados.ts";

const CACHE_PAGINAS = "eodi-paginas-v1";
const CACHE_DATOS = "eodi-datos-v1";

/** ¿Hay una copia de esta dirección en esa caché del service worker? */
function guardada(pagina: Page, cache: string, ruta: string): Promise<boolean> {
  return pagina.evaluate(
    async ([nombre, r]) => {
      const caja = await caches.open(nombre);
      return (await caja.match(new URL(r, location.origin).href)) !== undefined;
    },
    [cache, ruta] as const,
  );
}

/**
 * Abre `ruta`, espera a que el service worker esté activo y la vuelve a abrir ya en sus manos (la
 * primera carga nunca lo está: sw.js no usa clients.claim). Salta la prueba donde no hay app.
 */
async function abrirConApp(pagina: Page, ruta: string): Promise<void> {
  await pagina.goto(ruta);
  const conApp = await pagina.evaluate(async () => {
    if (!("serviceWorker" in navigator)) return false;
    // registrarApp (src/app/registro.ts) registra al terminar de cargar; si en 15 s no hay
    // registro, este sitio no tiene app (local).
    for (let i = 0; i < 30; i += 1) {
      if ((await navigator.serviceWorker.getRegistration()) !== undefined) {
        await navigator.serviceWorker.ready;
        return true;
      }
      await new Promise((hecho) => setTimeout(hecho, 500));
    }
    return false;
  });
  test.skip(!conApp, "este sitio no registra el service worker (solo droneobservatory.eu y sus vistas previas)");
  await pagina.reload();
  await expect.poll(() => pagina.evaluate(() => navigator.serviceWorker.controller !== null), { timeout: 20_000 }).toBe(true);
}

// Límite de Playwright con WebKit (iPhone y Safari de escritorio): con context.setOffline, recargar o
// abrir una dirección da «WebKit encountered an internal error» en vez de cargar la página, también
// sin el service worker (lo comprueba la última prueba de este fichero; Chromium da en ese caso
// net::ERR_INTERNET_DISCONNECTED), y un fetch de la página sin red falla aunque lo responda el
// service worker («Load failed»). Las dos pruebas sin conexión se saltan en WebKit; abrir sin conexión
// se comprueba en Chromium (Android, tableta y escritorio).
const SIN_RED_EN_WEBKIT =
  "WebKit + setOffline: Playwright no navega sin red («WebKit encountered an internal error», también sin service worker)";

/**
 * Diagnóstico de las pruebas sin conexión: las peticiones que fallan, los errores de la página y lo
 * que hay en cada caché de la app. Se escribe en el registro de la prueba al terminar.
 */
function diagnosticar(pagina: Page): () => Promise<void> {
  const fallos: string[] = [];
  pagina.on("requestfailed", (p) => fallos.push(`petición: ${p.url()} ${p.failure()?.errorText ?? ""}`));
  pagina.on("console", (m) => {
    if (m.type() === "error") fallos.push(`consola: ${m.text()}`);
  });
  pagina.on("pageerror", (e) => fallos.push(`excepción: ${e.message}`));
  return async () => {
    const cajas = await pagina
      .evaluate(async () => {
        const nombres = await caches.keys();
        const partes: string[] = [];
        for (const nombre of nombres) {
          const claves = (await (await caches.open(nombre)).keys()).map((c) => new URL(c.url).pathname);
          partes.push(`${nombre}: ${claves.length} (${claves.filter((c) => c.startsWith("/assets/")).slice(0, 40).join(" ")})`);
        }
        return partes.join(" | ");
      })
      .catch((e: unknown) => `sin cachés: ${String(e)}`);
    console.log(`[diagnóstico sin conexión] cachés: ${cajas}`);
    console.log(`[diagnóstico sin conexión] fallos: ${fallos.slice(0, 40).join(" | ")}`);
  };
}

// Con el service worker (lo de siempre en Playwright, escrito por si cambia el valor por defecto).
test.use({ serviceWorkers: "allow" });

test.describe("la app instalable", () => {
  for (const [idioma, ruta, manifiesto, nombre] of [
    ["es", "/", "/manifest.webmanifest", "Observatorio Europeo de Incidentes con Drones"],
    ["en", "/en", "/manifest-en.webmanifest", "European Observatory of Drone Incidents"],
  ] as const) {
    test(`instalable (${idioma}): manifiesto válido del idioma y service worker registrado`, async ({ page: pagina }) => {
      await pagina.goto(ruta);
      await expect(pagina.locator('link[rel="manifest"]')).toHaveAttribute("href", manifiesto);
      const respuesta = await pagina.request.get(manifiesto);
      expect(respuesta.ok()).toBe(true);
      const m = (await respuesta.json()) as Record<string, unknown> & { icons: { sizes: string; purpose?: string }[] };
      expect(m).toMatchObject({ display: "standalone", start_url: ruta, id: ruta, scope: "/", name: nombre, lang: idioma });
      expect(m.icons.some((i) => i.sizes === "512x512" && i.purpose === "maskable")).toBe(true);
      await abrirConApp(pagina, ruta);
      const alcance = await pagina.evaluate(async () => (await navigator.serviceWorker.getRegistration())?.scope ?? "");
      expect(new URL(alcance).pathname).toBe("/");
      // Sin banners: nada de instalación a la vista sin pedirlo.
      await expect(pagina.locator("[data-pasos-instalar]")).toHaveCount(0);
    });
  }

  test("sin conexión: abre con los últimos datos y la barra «Sin conexión · datos de las …»", async ({
    page: pagina,
    context: contexto,
    browserName,
  }) => {
    test.skip(browserName === "webkit", SIN_RED_EN_WEBKIT);
    await abrirConApp(pagina, "/");
    await expect.poll(() => guardada(pagina, CACHE_DATOS, "/datos/resumen.json"), { timeout: 30_000 }).toBe(true);
    await expect.poll(() => guardada(pagina, CACHE_PAGINAS, "/"), { timeout: 30_000 }).toBe(true);
    const informar = diagnosticar(pagina);
    await contexto.setOffline(true);
    try {
      await pagina.reload();
      await expect(pagina.locator("[data-sin-conexion]:visible").first()).toContainText(/Sin conexión · datos (de las|del)/, {
        timeout: 30_000,
      });
      await expect(pagina.locator('[data-frescura="al_dia"]')).toHaveCount(0);
      await expect(pagina.locator("[data-error-carga]")).toHaveCount(0);
      // Los datos generales salen de la copia guardada.
      const datos = await pagina.evaluate(async () => {
        const r = await fetch("/datos/resumen.json");
        return r.ok ? ((await r.json()) as { actualizado?: string }).actualizado ?? null : null;
      });
      expect(datos).not.toBeNull();
    } finally {
      await informar();
      await contexto.setOffline(false);
    }
    // Al volver la conexión, la barra vuelve sola al estado de los datos.
    await expect(pagina.locator("[data-sin-conexion]")).toHaveCount(0, { timeout: 30_000 });
  });

  test("una ficha ya visitada se abre sin conexión", async ({ page: pagina, context: contexto, request: peticiones, browserName }) => {
    test.skip(browserName === "webkit", SIN_RED_EN_WEBKIT);
    const datos = await publicados(peticiones);
    const id = elegir(datos, "", (f) => datos.puntos.has(f.id));
    expect(id).not.toBeNull();
    const ruta = `/en/${id ?? ""}`;
    await abrirConApp(pagina, ruta);
    await expect(pagina.locator("[data-ficha]:visible").first()).toBeVisible({ timeout: 60_000 });
    await expect.poll(() => guardada(pagina, CACHE_PAGINAS, ruta), { timeout: 30_000 }).toBe(true);
    await expect.poll(() => guardada(pagina, CACHE_DATOS, `/datos/incidentes/${id ?? ""}.json`), { timeout: 30_000 }).toBe(true);
    const informar = diagnosticar(pagina);
    await contexto.setOffline(true);
    try {
      await pagina.goto("about:blank");
      await pagina.goto(ruta);
      await expect(pagina.locator("[data-ficha]:visible").first()).toBeVisible({ timeout: 60_000 });
      await expect(pagina.locator("[data-sin-conexion]:visible").first()).toContainText(/Offline · data from/);
    } finally {
      await informar();
      await contexto.setOffline(false);
    }
  });

  test("actualización: una versión nueva de la web sustituye a la guardada", async ({ page: pagina }) => {
    await abrirConApp(pagina, "/");
    await expect.poll(() => guardada(pagina, CACHE_PAGINAS, "/"), { timeout: 30_000 }).toBe(true);
    // La copia guardada pasa a ser «de un build anterior»: otra huella de código y una marca.
    await pagina.evaluate(async (nombre) => {
      const caja = await caches.open(nombre);
      const clave = new URL("/", location.origin).href;
      const vieja = await caja.match(clave);
      const html = (await vieja?.text()) ?? "";
      const marcada = html.replace("<head>", '<head><meta name="eodi-build-viejo" content="1"><script type="module" src="/assets/build-viejo.js"></script>');
      await caja.put(clave, new Response(marcada, { headers: { "content-type": "text/html; charset=utf-8" } }));
    }, CACHE_PAGINAS);
    await pagina.reload();
    // Con red, la página sale del despliegue nuevo, nunca de la copia vieja, y la copia se renueva.
    await expect(pagina.locator('meta[name="eodi-build-viejo"]')).toHaveCount(0);
    await expect
      .poll(
        () =>
          pagina.evaluate(async (nombre) => {
            const r = await (await caches.open(nombre)).match(new URL("/", location.origin).href);
            return (await r?.text())?.includes("eodi-build-viejo") ?? true;
          }, CACHE_PAGINAS),
        { timeout: 20_000 },
      )
      .toBe(false);
    // Y el service worker se comprueba contra el servidor en cada carga (sin la caché HTTP).
    const actualiza = await pagina.evaluate(async () => (await navigator.serviceWorker.getRegistration())?.updateViaCache ?? "");
    expect(actualiza).toBe("none");
  });
});

// El límite de WebKit, comprobado sin el service worker: recargar sin red falla también (lo que diga
// Playwright queda en el registro de la prueba), así que no es cosa de public/sw.js.
test.describe("sin service worker", () => {
  test.use({ serviceWorkers: "block" });

  test("recargar sin red falla en el navegador, sin el service worker", async ({ page: pagina, context: contexto, browserName }) => {
    await pagina.goto("/");
    await contexto.setOffline(true);
    let error = "";
    try {
      await pagina.reload({ timeout: 30_000 });
    } catch (e) {
      error = e instanceof Error ? (e.message.split(/\r?\n/)[0] ?? "") : String(e);
    } finally {
      await contexto.setOffline(false);
    }
    console.log(`[${browserName}] recargar sin red y sin service worker: ${error}`);
    test.info().annotations.push({ type: "error sin red", description: error });
    expect(error).not.toBe("");
  });
});
