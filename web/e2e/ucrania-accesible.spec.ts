// Capa de Ucrania sin ratón, en 360 × 800, 768 × 1024, 1366 × 768 y 1920 × 1080. Con el teclado:
// encender la capa, recorrer sus regiones e impactos a la vista (cada uno señalado en el mapa),
// abrir su ficha con Intro, cerrarla con Escape (el foco vuelve al botón y se anuncia el cierre,
// sin mover el mapa) y usar la lista de la capa (agrupada; elegir abre la ficha y lleva el mapa).
// Además pasa axe (WCAG 2.1 A y AA) con la capa encendida y deja el resultado en AXE_SALIDA.
// Va contra producción por defecto; con BASE=http://localhost:4173, contra el servidor local; con
// BASE=<vista previa> y BYPASS=<clave>, contra una vista previa protegida. SOLO_AXE=1 pasa solo axe.
import { appendFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "ucrania-accesible");
const AXE_SALIDA = process.env.AXE_SALIDA;
const MAPA = "[data-mapa-listo=true]";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, tactil: true },
  { nombre: "768x1024", width: 768, height: 1024, tactil: true },
  { nombre: "1366x768", width: 1366, height: 768, tactil: false },
  { nombre: "1920x1080", width: 1920, height: 1080, tactil: false },
] as const;
const AXE = createRequire(import.meta.url).resolve("axe-core/axe.min.js");

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com|tiles\.droneobservatory\.eu/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  await pagina.waitForTimeout(1600);
  let anterior = "";
  for (let i = 0; i < 30; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior) break;
    anterior = ahora;
  }
  return anterior;
}

/** Tabula hasta que el foco cumple la condición (como mucho `maximo` veces). */
async function tabularHasta(pagina: Page, condicion: string, maximo = 400): Promise<void> {
  for (let i = 0; i < maximo; i += 1) {
    if (await pagina.evaluate((selector) => document.activeElement?.matches(selector) === true, condicion)) return;
    await pagina.keyboard.press("Tab");
  }
  throw new Error(`el tabulador no llega a ${condicion}`);
}

async function axe(pagina: Page, cuando: string, tamano: string) {
  await pagina.addScriptTag({ path: AXE });
  const resultado = await pagina.evaluate(async () => {
    const r = await (window as unknown as { axe: { run: (c: unknown, o: unknown) => Promise<{ violations: { id: string; impact: string; nodes: unknown[] }[] }> } }).axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    });
    return r.violations.map((v) => ({ id: v.id, impacto: v.impact, nodos: v.nodes.length }));
  });
  if (AXE_SALIDA !== undefined) appendFileSync(AXE_SALIDA, `${JSON.stringify({ cuando, tamano, fallos: resultado })}\n`);
  return resultado;
}

for (const tamano of TAMANOS) {
  test(`capa de Ucrania con teclado y axe en ${tamano.nombre}`, async ({ browser, baseURL, browserName }, info) => {
    test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
    const telefono = tamano.width < 768;
    const contexto = await browser.newContext({
      viewport: { width: tamano.width, height: tamano.height },
      hasTouch: tamano.tactil,
      bypassCSP: true,
      ...(baseURL === undefined ? {} : { baseURL }),
      ...(process.env.BYPASS === undefined ? {} : { extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } }),
    });
    await preparar(contexto, baseURL);
    const pagina = await contexto.newPage();
    await pagina.goto("/", { waitUntil: "domcontentloaded" });
    await pagina.locator(MAPA).waitFor({ timeout: 60_000 });
    // La capa, con su atajo de teclado.
    await pagina.locator("body").press("2");
    await pagina.waitForTimeout(4000);
    const fallos = await axe(pagina, process.env.CUANDO ?? "despues", tamano.nombre);
    if (process.env.SOLO_AXE === "1") {
      await contexto.close();
      return;
    }
    expect(fallos).toEqual([]);

    // Recorrer las regiones a la vista: el aro se pone en su sitio; Intro abre la ficha.
    const inicial = await vista(pagina);
    await pagina.locator("#mapa").focus();
    await tabularHasta(pagina, "[data-regiones-teclado] button");
    const region = (await pagina.evaluate(() => document.activeElement?.textContent)) ?? "";
    expect(region).toMatch(/ataques? en el periodo/);
    await expect(pagina.locator("[data-aro-teclado]")).toBeVisible();
    await expect(pagina.locator("[data-letrero]")).toBeVisible();
    await pagina.screenshot({ path: join(CAPTURAS, `despues-teclado-${tamano.nombre}.png`) });
    await pagina.keyboard.press("Enter");
    const ficha = pagina.locator("[data-ficha]:visible");
    await expect(ficha).toHaveAttribute("aria-label", new RegExp(region.split(" · ")[0] ?? ""));
    await expect(ficha).toBeFocused();
    await pagina.screenshot({ path: join(CAPTURAS, `despues-ficha-region-${tamano.nombre}.png`) });
    await pagina.keyboard.press("Escape");
    await expect(pagina.locator("[data-ficha]:visible")).toHaveCount(0);
    expect(await pagina.evaluate(() => document.activeElement?.textContent)).toBe(region);
    await expect(pagina.locator("[data-ficha-cerrada]")).toHaveText(/Ficha cerrada/);
    expect(await vista(pagina)).toBe(inicial);

    // Los impactos a la vista, igual.
    await tabularHasta(pagina, "[data-impactos-teclado] button");
    expect(await pagina.evaluate(() => document.activeElement?.textContent)).toMatch(/^Impacto con lugar · /);
    await pagina.keyboard.press("Enter");
    await expect(pagina.locator("[data-ficha]:visible")).toBeFocused();
    await pagina.keyboard.press("Escape");
    await expect(pagina.locator("[data-ficha]:visible")).toHaveCount(0);
    expect(await vista(pagina)).toBe(inicial);

    // La lista de la capa: en el teléfono, desde el menú; en escritorio, junto a «Con satélite».
    if (telefono) {
      await pagina.getByRole("button", { name: /Menú/ }).first().click();
    }
    const boton = pagina.locator("[data-boton-lista-ucrania]:visible");
    await boton.focus();
    await pagina.keyboard.press("Enter");
    const lista = pagina.locator("[data-lista-ucrania]:visible");
    await expect(lista).toBeVisible();
    await expect(lista.locator("summary").first()).toHaveText(/Regiones de Ucrania con ataques · \d+/);
    await pagina.screenshot({ path: join(CAPTURAS, `despues-lista-${tamano.nombre}.png`) });
    expect(await axe(pagina, "despues-lista-abierta", tamano.nombre)).toEqual([]);
    const primera = lista.locator("details[open] button").first();
    const nombre = (await primera.textContent()) ?? "";
    await primera.focus();
    await pagina.keyboard.press("Enter");
    await expect(pagina.locator("[data-ficha]:visible")).toHaveAttribute("aria-label", new RegExp(nombre.split(" · ")[0] ?? ""));
    const trasElegir = await vista(pagina);
    expect(trasElegir).not.toBe(inicial);
    await pagina.screenshot({ path: join(CAPTURAS, `despues-lista-elegida-${tamano.nombre}.png`) });
    await pagina.keyboard.press("Escape");
    await expect(pagina.locator("[data-ficha]:visible")).toHaveCount(0);
    expect(await vista(pagina)).toBe(trasElegir);
    // El foco vuelve a la lista (en el teléfono, la lista vuelve a abrirse).
    if (telefono) await expect(pagina.locator("[data-lista-ucrania]:visible")).toBeVisible();
    else expect(await pagina.evaluate(() => document.activeElement?.textContent)).toBe(nombre);
    await pagina.keyboard.press("Escape");
    await expect(pagina.locator("[data-lista-ucrania]:visible")).toHaveCount(0);
    expect(await axe(pagina, "despues-lista-cerrada", tamano.nombre)).toEqual([]);
    await contexto.close();
  });
}
