// Rutas de los drones sobre Ucrania en el teléfono (360, 390 y 412 px) y en escritorio: la
// subcapa «Rutas» dibuja una sola noche (la última terminada) con un recorrido por grupo, tenue en
// el origen y con punta de flecha; la leyenda dice qué noche y cuántos grupos de cuántos, cabe
// entera en la pantalla y enlaza a NEPTUN; mientras se ve, los impactos se atenúan; tocar un
// recorrido abre la ficha del grupo y cerrarla no mueve el mapa; «Noche a noche» dibuja la noche
// que muestra; y el recorrido de una incursión al abrir su ficha. Deja capturas en CAPTURAS (por
// defecto fuera del repositorio), de lejos (toda Ucrania) y acercando al norte y al sur. Va contra
// producción por defecto; con BASE=http://localhost:…, contra el servidor local, y con
// RUTAS_LOCAL=<carpeta>, las rutas/… se sirven de esa carpeta (las generadas antes de publicar).
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";
import type { Map as MapaGL } from "maplibre-gl";

import ajuste from "../../configuracion/rutas_en_la_web.json" with { type: "json" };

/** Con las rutas apagadas en la web, sus pruebas se saltan (las comprueba rutas-apagadas.spec.ts). */
const SIN_RUTAS = !ajuste.mostrar;

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "..", "eodi-rl-cap");
const MAPA = "[data-mapa-listo=true]";
const LEYENDA = "[data-leyenda=rutas]";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, movil: true },
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "412x915", width: 412, height: 915, movil: true },
  { nombre: "escritorio", width: 1440, height: 900, movil: false },
];
const VISTAS = [
  { nombre: "ucrania", centro: [31.4, 48.6], movil: 4.55, escritorio: 5.6 },
  { nombre: "norte", centro: [33.0, 51.0], movil: 6.3, escritorio: 7.0 },
  { nombre: "sur", centro: [32.0, 46.9], movil: 6.3, escritorio: 7.0 },
] as const;
const COMBINACIONES = [
  { nombre: "sola", guerra: "rutas" },
  { nombre: "corredores", guerra: "corredores,rutas" },
];

type ElementoDelMapa = HTMLElement & { mapaDePruebas?: MapaGL };

const RUTAS_LOCAL = process.env.RUTAS_LOCAL;

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    try {
      const camino = new URL(ruta.request().url()).pathname;
      const local = RUTAS_LOCAL === undefined ? null : join(RUTAS_LOCAL, camino);
      if (local !== null && camino.startsWith("/rutas/") && existsSync(local)) {
        await ruta.fulfill({
          body: readFileSync(local),
          headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
        });
        return;
      }
      const respuesta = await ruta.fetch();
      await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
    } catch {
      // La prueba ya ha terminado: la petición en vuelo no importa.
    }
  });
}

async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  let anterior = "";
  for (let i = 0; i < 30; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior && !ahora.includes("null")) return ahora;
    anterior = ahora;
  }
  return anterior;
}

async function irA(pagina: Page, centro: readonly number[], zoom: number): Promise<void> {
  await pagina.evaluate(async ({ c, z }) => {
    const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
    if (mapa === undefined) throw new Error("sin mapa");
    mapa.jumpTo({ center: [c[0] ?? 0, c[1] ?? 0], zoom: z });
    await new Promise((listo) => mapa.once("idle", listo));
  }, { c: centro, z: zoom });
}

/** Espera a que la leyenda haya cargado la noche y comprueba que cabe entera en la pantalla. */
async function leyendaLista(pagina: Page, ancho: number): Promise<number> {
  const leyenda = pagina.locator(LEYENDA);
  await expect(leyenda).toBeVisible({ timeout: 20000 });
  await expect(leyenda.locator("[data-rutas-total]")).not.toContainText(/Cargando|Loading/, { timeout: 20000 });
  await expect(leyenda).toContainText(/noche del|night of/i);
  const caja = await leyenda.boundingBox();
  expect(caja).not.toBeNull();
  expect(caja?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((caja?.x ?? 0) + (caja?.width ?? 0)).toBeLessThanOrEqual(ancho);
  const total = Number((await leyenda.locator("[data-rutas-total]").getAttribute("data-rutas-total")) ?? "0");
  if (total > 0) {
    const enlace = leyenda.locator("[data-enlace-neptun]");
    await expect(enlace).toBeVisible();
    const cajaEnlace = await enlace.boundingBox();
    expect(cajaEnlace?.x ?? -1).toBeGreaterThanOrEqual(0);
    expect((cajaEnlace?.x ?? 0) + (cajaEnlace?.width ?? 0)).toBeLessThanOrEqual(ancho);
  }
  return total;
}

/** Puntos en pantalla del medio de los recorridos dibujados, lejos de cualquier marca. */
async function recorridosEnPantalla(pagina: Page): Promise<{ x: number; y: number }[]> {
  return pagina.evaluate(() => {
    const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
    if (mapa === undefined) throw new Error("sin mapa");
    const lienzo = mapa.getCanvas().getBoundingClientRect();
    const marcas = [
      "guerra-impactos", "guerra-impactos-grupos", "guerra-satelite", "incidentes-graves",
      "incidentes-discretos", "grupos", "atribuidos", "directo-avisos", "guerra-luz-ciudades",
      "guerra-alumbrado", "guerra-corredores-zona",
    ].filter((id) => mapa.getLayer(id) !== undefined);
    const puntos: { x: number; y: number }[] = [];
    for (const rasgo of mapa.queryRenderedFeatures({ layers: ["guerra-rutas-linea"] }).slice(0, 200)) {
      if (rasgo.geometry.type !== "LineString") continue;
      const linea = rasgo.geometry.coordinates;
      const medio = linea[Math.floor(linea.length / 2)];
      if (medio === undefined) continue;
      const p = mapa.project([medio[0] ?? 0, medio[1] ?? 0]);
      if (p.x < 20 || p.y < 160 || p.x > lienzo.width - 20 || p.y > lienzo.height * 0.7) continue;
      const encima = mapa.queryRenderedFeatures([[p.x - 24, p.y - 24], [p.x + 24, p.y + 24]], { layers: marcas });
      if (encima.length === 0) puntos.push({ x: lienzo.left + p.x, y: lienzo.top + p.y });
    }
    return puntos;
  });
}

for (const tamano of TAMANOS) {
  test.describe(`rutas en ${tamano.nombre}`, () => {
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    for (const combinacion of COMBINACIONES) {
      test(`«Rutas» ${combinacion.nombre}: una noche, recorridos con flecha y leyenda entera`, async ({ page, context, baseURL }) => {
        test.skip(SIN_RUTAS, "rutas apagadas en la web");
        await preparar(context, baseURL);
        const inicio = Date.now();
        await page.goto(`/?guerra=${combinacion.guerra}`);
        await page.locator(MAPA).waitFor();
        const total = await leyendaLista(page, tamano.width);
        // La subcapa aparece en menos de dos segundos desde que el mapa está listo… y la página
        // entera, con su mapa, en un tiempo razonable.
        expect(Date.now() - inicio).toBeLessThan(20000);
        const dibujados = await page.evaluate(() => {
          const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
          return {
            lineas: mapa?.querySourceFeatures("guerra-rutas").length ?? 0,
            flechas: mapa?.querySourceFeatures("guerra-rutas-flechas").length ?? 0,
            impactos: mapa?.getPaintProperty("guerra-impactos", "circle-opacity"),
          };
        });
        if (total > 0) {
          expect(dibujados.lineas).toBeGreaterThan(0);
          expect(dibujados.flechas).toBeGreaterThan(0);
          // Con las rutas a la vista, los impactos se atenúan.
          expect(dibujados.impactos).toBe(0.15);
        }
        for (const v of VISTAS) {
          await irA(page, v.centro, tamano.movil ? v.movil : v.escritorio);
          await page.waitForTimeout(600);
          await page.screenshot({ path: join(CAPTURAS, `rutas-${combinacion.nombre}-${v.nombre}-${tamano.nombre}.png`) });
        }
      });
    }

    test("tocar un recorrido abre la ficha del grupo con NEPTUN y cerrarla no mueve el mapa", async ({ page, context, baseURL }) => {
        test.skip(SIN_RUTAS, "rutas apagadas en la web");
      await preparar(context, baseURL);
      await page.goto("/?guerra=rutas");
      await page.locator(MAPA).waitFor();
      await leyendaLista(page, tamano.width);
      let puntos: { x: number; y: number }[] = [];
      for (const centro of [[32.5, 49.6], [33.5, 50.8], [31.5, 47.4], [35, 48.5]]) {
        await irA(page, centro, tamano.movil ? 6 : 6.5);
        puntos = await recorridosEnPantalla(page);
        if (puntos.length > 0) break;
      }
      expect(puntos.length).toBeGreaterThan(0);
      let abierta = false;
      for (const punto of puntos.slice(0, 12)) {
        if (tamano.movil) await page.touchscreen.tap(punto.x, punto.y);
        else await page.mouse.click(punto.x, punto.y);
        await page.waitForTimeout(700);
        if ((await page.locator("[data-ficha-ruta]").count()) > 0) {
          abierta = true;
          break;
        }
        await page.keyboard.press("Escape");
      }
      expect(abierta).toBe(true);
      const ficha = page.locator("[data-ficha-ruta]");
      await expect(ficha).toContainText(/Precisión|Precision/);
      await expect(ficha).toContainText(/Noche del|Night of/i);
      if ((await ficha.textContent())?.includes("NEPTUN") === true) {
        await expect(ficha.locator("[data-enlace-neptun]")).toBeVisible();
      }
      await page.screenshot({ path: join(CAPTURAS, `rutas-ficha-${tamano.nombre}.png`) });
      const antes = await vista(page);
      await page.getByRole("button", { name: /Cerrar la ficha|Close the record/ }).first().click();
      await page.waitForTimeout(800);
      expect(await vista(page)).toBe(antes);
    });

    test("«Noche a noche» dibuja solo la noche que muestra", async ({ page, context, baseURL }) => {
        test.skip(SIN_RUTAS, "rutas apagadas en la web");
      await preparar(context, baseURL);
      await page.goto("/?desde=2026-10-05&hasta=2026-10-05&guerra=rutas");
      await page.locator(MAPA).waitFor();
      await leyendaLista(page, tamano.width);
      if (tamano.movil) await page.getByRole("button", { name: /Menú|Menu/ }).first().click();
      await page.getByRole("button", { name: /Noche a noche|Night by night/ }).first().click();
      await expect(page.locator("[data-noche]")).toBeVisible();
      await page.waitForTimeout(1500);
      await expect(page.locator(LEYENDA)).toBeVisible();
      await page.screenshot({ path: join(CAPTURAS, `rutas-noche-a-noche-${tamano.nombre}.png`) });
    });

    test("el recorrido de una incursión se dibuja al abrir su ficha y se quita al cerrarla", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/EODI-2026-00193");
      await page.locator(MAPA).waitFor();
      await expect(page.locator("[data-recorrido]").first()).toBeVisible({ timeout: 20000 });
      const dibujado = await page.evaluate(async () => {
        const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
        await new Promise((listo) => setTimeout(listo, 1500));
        return mapa?.querySourceFeatures("recorrido").length ?? 0;
      });
      expect(dibujado).toBeGreaterThan(0);
      await page.screenshot({ path: join(CAPTURAS, `recorrido-${tamano.nombre}.png`) });
      const antes = await vista(page);
      await page.getByRole("button", { name: /Cerrar la ficha|Close the record/ }).first().click();
      await page.waitForTimeout(800);
      expect(await vista(page)).toBe(antes);
      const quitado = await page.evaluate(() => {
        const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
        return mapa?.querySourceFeatures("recorrido").length ?? -1;
      });
      expect(quitado).toBe(0);
    });
  });
}

test("la página de texto de Ucrania y la metodología explican las rutas sin ejecutar código", async ({ request }) => {
  test.skip(SIN_RUTAS, "rutas apagadas en la web");
  const ucrania = await (await request.get("/ucrania")).text();
  expect(ucrania).toContain("Rutas de los drones sobre Ucrania");
  const metodo = await (await request.get("/en/methodology")).text();
  expect(metodo).toContain("Drone routes over Ukraine");
  expect(metodo).toContain("arrowhead");
});

test("la página de texto de una incursión lleva su recorrido sin ejecutar código", async ({ request }) => {
  const incursion = await (await request.get("/EODI-2026-00193")).text();
  expect(incursion).toContain('data-recorrido=""');
});
