// Rutas de los drones sobre Ucrania en el teléfono (360, 390 y 412 px) y en escritorio: la
// subcapa «Rutas» con 7 días, 30 días y «Todo», sola y junto a los corredores; tocar una franja
// abre su ficha (con el enlace a NEPTUN si sale de sus datos) y cerrarla no mueve el mapa; «Noche
// a noche» con las rutas de la noche; y el recorrido de una incursión al abrir su ficha. Deja
// capturas en CAPTURAS (por defecto fuera del repositorio). Va contra producción por defecto; con
// BASE=http://localhost:…, contra el servidor local.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";
import type { Map as MapaGL } from "maplibre-gl";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "..", "eodi-tr-cap");
const MAPA = "[data-mapa-listo=true]";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, movil: true },
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "412x915", width: 412, height: 915, movil: true },
  { nombre: "escritorio", width: 1440, height: 900, movil: false },
];
const PERIODOS = [
  { nombre: "7d", busqueda: "ultimos=7d" },
  { nombre: "30d", busqueda: "ultimos=30d" },
  { nombre: "todo", busqueda: "" },
];

type ElementoDelMapa = HTMLElement & { mapaDePruebas?: MapaGL };
/** Capas de marcas (las que ganan a una franja al tocar), por su nombre en el estilo. */
const CAPAS_DE_MARCAS = [
  "guerra-impactos", "guerra-impactos-grupos", "guerra-satelite", "incidentes-graves",
  "incidentes-discretos", "grupos", "atribuidos", "directo-avisos", "guerra-luz-ciudades",
  "guerra-alumbrado", "guerra-corredores-zona",
];

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    try {
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

/** Lleva el mapa sobre Ucrania y devuelve los puntos en pantalla de las franjas dibujadas. */
async function franjasEnPantalla(pagina: Page, zoom: number): Promise<{ x: number; y: number }[]> {
  return pagina.evaluate(async ({ z, MARCAS }) => {
    const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
    if (mapa === undefined) throw new Error("sin mapa");
    mapa.jumpTo({ center: [32.5, 48.8], zoom: z });
    await new Promise((listo) => mapa.once("idle", listo));
    const lienzo = mapa.getCanvas().getBoundingClientRect();
    const rasgos = mapa.queryRenderedFeatures({ layers: ["guerra-rutas"] });
    const puntos: { x: number; y: number }[] = [];
    for (const rasgo of rasgos.slice(0, 400)) {
      if (rasgo.geometry.type !== "Polygon") continue;
      const anillo = rasgo.geometry.coordinates[0] ?? [];
      const lon = anillo.reduce((s, c) => s + (c[0] ?? 0), 0) / anillo.length;
      const lat = anillo.reduce((s, c) => s + (c[1] ?? 0), 0) / anillo.length;
      const p = mapa.project([lon, lat]);
      if (p.x < 20 || p.y < 140 || p.x > lienzo.width - 20 || p.y > lienzo.height * 0.6) continue;
      // Solo donde no hay ninguna marca cerca (una marca gana a la franja).
      const marcas = MARCAS.filter((id) => mapa.getLayer(id) !== undefined);
      const encima = mapa.queryRenderedFeatures(
        [
          [p.x - 24, p.y - 24],
          [p.x + 24, p.y + 24],
        ],
        { layers: marcas },
      );
      const soloAreas = encima.length === 0;
      if (soloAreas) puntos.push({ x: lienzo.left + p.x, y: lienzo.top + p.y });
    }
    return puntos;
  }, { z: zoom, MARCAS: CAPAS_DE_MARCAS });
}

for (const tamano of TAMANOS) {
  test.describe(`rutas en ${tamano.nombre}`, () => {
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    for (const periodo of PERIODOS) {
      test(`subcapa «Rutas» con ${periodo.nombre}, sola y con los corredores`, async ({ page, context, baseURL }) => {
        await preparar(context, baseURL);
        const separador = periodo.busqueda === "" ? "" : "&";
        await page.goto(`/?${periodo.busqueda}${separador}guerra=rutas`);
        await page.locator(MAPA).waitFor();
        const leyenda = page.locator("[data-leyenda=rutas]");
        await expect(leyenda).toBeVisible({ timeout: 20000 });
        await expect(leyenda).toContainText(/Rutas de|Ninguna noche/);
        const total = Number((await leyenda.locator("[data-rutas-total]").getAttribute("data-rutas-total")) ?? "0");
        if (total > 0) await expect(leyenda.locator("[data-enlace-neptun]")).toBeVisible();
        await page.waitForTimeout(2500);
        await page.screenshot({ path: join(CAPTURAS, `rutas-${periodo.nombre}-${tamano.nombre}.png`) });
        await page.goto(`/?${periodo.busqueda}${separador}guerra=corredores,rutas`);
        await page.locator(MAPA).waitFor();
        await expect(page.locator("[data-leyenda=rutas]")).toBeVisible({ timeout: 20000 });
        await page.waitForTimeout(2500);
        await page.screenshot({ path: join(CAPTURAS, `rutas-corredores-${periodo.nombre}-${tamano.nombre}.png`) });
      });
    }

    test("tocar una franja abre su ficha con NEPTUN y cerrarla no mueve el mapa", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/?guerra=rutas");
      await page.locator(MAPA).waitFor();
      await expect(page.locator("[data-leyenda=rutas] [data-rutas-total]")).toBeVisible({ timeout: 20000 });
      await page.waitForTimeout(2000);
      const puntos = await franjasEnPantalla(page, tamano.movil ? 6.5 : 6);
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
      if ((await ficha.textContent())?.includes("NEPTUN") === true) {
        await expect(ficha.locator("[data-enlace-neptun]")).toBeVisible();
      }
      await page.screenshot({ path: join(CAPTURAS, `rutas-ficha-${tamano.nombre}.png`) });
      const antes = await vista(page);
      await page.getByRole("button", { name: /Cerrar la ficha|Close the record/ }).first().click();
      await page.waitForTimeout(800);
      expect(await vista(page)).toBe(antes);
    });

    test("«Noche a noche» dibuja las rutas de la noche", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/?desde=2026-10-05&hasta=2026-10-05&guerra=rutas");
      await page.locator(MAPA).waitFor();
      await expect(page.locator("[data-leyenda=rutas]")).toBeVisible({ timeout: 20000 });
      if (tamano.movil) await page.getByRole("button", { name: /Menú|Menu/ }).first().click();
      await page.getByRole("button", { name: /Noche a noche|Night by night/ }).first().click();
      await expect(page.locator("[data-noche]")).toBeVisible();
      await expect(page.locator("[data-leyenda=rutas]")).toContainText(/Rutas de esta noche|Routes of this night/, { timeout: 20000 });
      await page.waitForTimeout(1500);
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
  const ucrania = await (await request.get("/ucrania")).text();
  expect(ucrania).toContain("Rutas de los drones sobre Ucrania");
  const metodo = await (await request.get("/en/methodology")).text();
  expect(metodo).toContain("Drone routes over Ukraine");
  const incursion = await (await request.get("/EODI-2026-00193")).text();
  expect(incursion).toContain('data-recorrido=""');
});
