// «Aplicar» en el menú del teléfono y en la hoja de Ucrania, con toques reales en 360 × 800: fijo
// abajo y a todo el ancho; cierra el panel y encuadra lo que queda a la vista (con Ucrania, Ucrania,
// Crimea y las regiones rusas fronterizas); sin nada a la vista no mueve el mapa y avisa; la equis,
// Escape y tocar fuera no mueven el mapa; tras aplicar, el foco vuelve al botón que abrió el panel.
// En 768 × 1024 (disposición de escritorio: los paneles no tapan más de la mitad del mapa) solo los
// filtros llevan «Aplicar», también con toques. Deja capturas en docs/capturas/aplicar-menu
// (CAPTURAS para otra carpeta). Va contra producción por defecto; con BASE=<vista previa> y
// BYPASS=<clave>, contra una vista previa.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Browser, Page } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "aplicar-menu");
const MAPA = "[data-mapa-listo=true]";

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

async function abrirPagina(browser: Browser, baseURL: string | undefined, width: number, height: number, ruta = "/") {
  const contexto = await browser.newContext({
    viewport: { width, height },
    hasTouch: true,
    isMobile: width < 768,
    ...(baseURL === undefined ? {} : { baseURL }),
    ...(process.env.BYPASS === undefined ? {} : { extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } }),
  });
  const pagina = await contexto.newPage();
  await pagina.goto(ruta, { waitUntil: "domcontentloaded" });
  await pagina.locator(MAPA).waitFor({ timeout: 60_000 });
  return { contexto, pagina, inicial: await vista(pagina) };
}

function menu(pagina: Page) {
  return pagina.locator("dialog[open]");
}

async function abrirMenu(pagina: Page) {
  await pagina.locator("[data-boton-menu]").tap();
  await expect(menu(pagina)).toBeVisible();
}

function capa(pagina: Page, nombre: string) {
  return menu(pagina).getByRole("group", { name: "Capas" }).getByRole("button", { name: nombre, exact: true });
}

test("menú del teléfono: «Aplicar» fijo abajo, encuadra, avisa y no mueve el mapa al cerrar", async ({ browser, baseURL, browserName }, info) => {
  test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
  const { contexto, pagina, inicial } = await abrirPagina(browser, baseURL, 360, 800);

  // Fijo abajo y a todo el ancho, también con el menú desplazado hasta arriba o hasta abajo.
  await abrirMenu(pagina);
  const aplicar = menu(pagina).locator("[data-pie-menu] [data-aplicar]");
  await expect(aplicar).toBeInViewport({ ratio: 1 });
  const caja = await aplicar.boundingBox();
  expect(caja?.width ?? 0).toBeGreaterThan(300);
  expect((caja?.y ?? 0) + (caja?.height ?? 0)).toBeGreaterThan(740);
  await pagina.screenshot({ path: join(CAPTURAS, "menu-360x800.png") });
  await menu(pagina).evaluate((d) => d.scrollTo(0, d.scrollHeight));
  await expect(aplicar).toBeInViewport({ ratio: 1 });

  // La equis, Escape y tocar fuera (no hay fuera: el menú es a pantalla completa) no mueven el mapa.
  await menu(pagina).getByRole("button", { name: "Cerrar el menú" }).tap();
  await expect(menu(pagina)).toHaveCount(0);
  expect(await vista(pagina)).toBe(inicial);
  await abrirMenu(pagina);
  await pagina.keyboard.press("Escape");
  await expect(menu(pagina)).toHaveCount(0);
  expect(await vista(pagina)).toBe(inicial);

  // Solo Ucrania: encuadra Ucrania, Crimea y las regiones rusas fronterizas; el foco vuelve a «Menú».
  await abrirMenu(pagina);
  await capa(pagina, "Incidentes").tap();
  await capa(pagina, "Ucrania").tap();
  await expect(capa(pagina, "Ucrania")).toHaveAttribute("aria-pressed", "true");
  await pagina.screenshot({ path: join(CAPTURAS, "menu-ucrania-360x800.png") });
  await menu(pagina).locator("[data-aplicar]").tap();
  await expect(menu(pagina)).toHaveCount(0);
  const trasUcrania = await vista(pagina);
  const [lon = 0, lat = 0] = (trasUcrania.split("|")[0] ?? "").split(",").map(Number);
  expect(lon).toBeGreaterThan(22);
  expect(lon).toBeLessThan(45);
  expect(lat).toBeGreaterThan(43);
  expect(lat).toBeLessThan(55);
  expect(Number(trasUcrania.split("|")[1])).toBeLessThanOrEqual(8.0001);
  await expect(pagina.locator("[data-boton-menu]")).toBeFocused();
  await pagina.screenshot({ path: join(CAPTURAS, "tras-aplicar-ucrania-360x800.png") });

  // La hoja de Ucrania («Lista») también lleva «Aplicar».
  await abrirMenu(pagina);
  await menu(pagina).locator("[data-boton-lista-ucrania]").tap();
  const hoja = pagina.locator("[data-hoja-propia]");
  await expect(hoja.locator("[data-aplicar]")).toBeInViewport({ ratio: 1 });
  await pagina.screenshot({ path: join(CAPTURAS, "hoja-ucrania-360x800.png") });
  await hoja.locator("[data-aplicar]").tap();
  await expect(pagina.locator("[data-hoja-propia]")).toHaveCount(0);
  const trasHoja = await vista(pagina);
  const [lonHoja = 0, latHoja = 0] = (trasHoja.split("|")[0] ?? "").split(",").map(Number);
  expect(Math.abs(lonHoja - lon)).toBeLessThan(3);
  expect(Math.abs(latHoja - lat)).toBeLessThan(3);
  await expect(pagina.locator("[data-boton-menu]")).toBeFocused();

  // Sin nada a la vista: el mapa no se mueve y se avisa.
  await abrirMenu(pagina);
  await capa(pagina, "Ucrania").tap();
  await menu(pagina).locator("[data-aplicar]").tap();
  await expect(pagina.locator("[data-sin-resultados]")).toHaveText("Nada a la vista: enciende alguna capa");
  expect(await vista(pagina)).toBe(trasHoja);
  await pagina.screenshot({ path: join(CAPTURAS, "nada-a-la-vista-360x800.png") });

  // Incidentes otra vez: encuadra Europa.
  await abrirMenu(pagina);
  await capa(pagina, "Incidentes").tap();
  await menu(pagina).locator("[data-aplicar]").tap();
  await expect(pagina.locator("[data-sin-resultados]")).toHaveCount(0);
  expect(await vista(pagina)).not.toBe(trasHoja);
  await pagina.screenshot({ path: join(CAPTURAS, "tras-aplicar-incidentes-360x800.png") });
  await contexto.close();
});

test("768 × 1024 con toques: los filtros con «Aplicar»; el resto, como estaba", async ({ browser, baseURL, browserName }, info) => {
  test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
  const { contexto, pagina, inicial } = await abrirPagina(browser, baseURL, 768, 1024);
  await expect(pagina.locator("[data-boton-menu]:visible")).toHaveCount(0);
  const filtros = pagina.locator("[data-botones-mapa] button:visible").first();
  await filtros.tap();
  await expect(pagina.locator("[data-filtros]:visible")).toBeVisible();
  // El panel no tapa más de la mitad del mapa.
  const panel = await pagina.locator("[data-filtros]:visible").evaluate((f) => {
    const caja = (f.closest("[role=dialog], dialog") ?? f).getBoundingClientRect();
    return caja.width * caja.height;
  });
  expect(panel).toBeLessThan((768 * 1024) / 2);
  await pagina.locator("[data-aplicar]:visible").tap();
  await expect(pagina.locator("[data-filtros]:visible")).toHaveCount(0);
  await expect(filtros).toBeFocused();
  expect(await vista(pagina)).not.toBe("");
  // Las capas de la cabecera no abren ningún panel: el mapa cambia a la vista, sin moverse.
  await pagina.getByRole("group", { name: "Capas" }).getByRole("button", { name: "Ucrania", exact: true }).tap();
  await pagina.screenshot({ path: join(CAPTURAS, "escritorio-768x1024.png") });
  expect(inicial).not.toBe("");
  await contexto.close();
});
