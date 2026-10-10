// Un solo toque selecciona y se ve en blanco al momento, en el primer control y en los demás, al
// abrir el panel por primera vez y tras cerrarlo y reabrirlo: filtros, menú del teléfono y subcapas
// de Ucrania, con eventos táctiles de bajo nivel en 360 × 800 y 768 × 1024. Al quitar la selección,
// el control vuelve a verse inactivo (el «hover» no se queda pegado en una pantalla táctil).
// Va contra producción por defecto; BASE y BYPASS como en los demás.
import { expect, test } from "@playwright/test";
import type { CDPSession, Locator, Page } from "@playwright/test";

const MAPA = "[data-mapa-listo=true]";
const BLANCO = "rgb(244, 247, 251)";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "768x1024", width: 768, height: 1024 },
] as const;

async function tocar(cdp: CDPSession, elemento: Locator) {
  const caja = await elemento.boundingBox();
  if (caja === null) throw new Error("sin caja");
  const punto = { x: caja.x + caja.width / 2, y: caja.y + caja.height / 2 };
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [punto] });
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

/** Fondo del control un instante después del toque (sin transición: se ve al momento). */
async function fondo(elemento: Locator) {
  await elemento.page().waitForTimeout(50);
  return elemento.evaluate((e) => getComputedStyle(e).backgroundColor);
}

/** Un toque en cada uno de los dos primeros conmutadores del panel: cambia y se ve al momento. */
async function comprobarToques(cdp: CDPSession, panel: Locator) {
  for (const i of [0, 1]) {
    const control = panel.locator("button[aria-pressed]").nth(i);
    const antes = await control.getAttribute("aria-pressed");
    await tocar(cdp, control);
    const despues = antes === "true" ? "false" : "true";
    await expect(control).toHaveAttribute("aria-pressed", despues);
    const color = await fondo(control);
    if (despues === "true") expect(color).toBe(BLANCO);
    else expect(color).not.toBe(BLANCO);
  }
}

function botonMenu(pagina: Page) {
  return pagina.locator("#root header button[aria-haspopup=dialog]", { hasText: /^(Menú|Menu)$/ });
}

async function abrirMenu(cdp: CDPSession, pagina: Page) {
  await tocar(cdp, botonMenu(pagina));
  await expect(pagina.locator("dialog[open]")).toBeVisible();
}

for (const tamano of TAMANOS) {
  test(`un toque selecciona en ${tamano.nombre}`, async ({ browser, baseURL, browserName }, info) => {
    test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
    const contexto = await browser.newContext({
      viewport: { width: tamano.width, height: tamano.height },
      hasTouch: true,
      isMobile: true,
      ...(baseURL === undefined ? {} : { baseURL }),
      ...(process.env.BYPASS === undefined ? {} : { extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } }),
    });
    if (baseURL?.includes("localhost") === true) {
      await contexto.route(/your-objectstorage\.com/, async (ruta) => {
        const respuesta = await ruta.fetch();
        await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
      });
    }
    const pagina = await contexto.newPage();
    const cdp = await contexto.newCDPSession(pagina);
    await pagina.goto("/", { waitUntil: "domcontentloaded" });
    await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });

    // Filtros: dos aperturas seguidas.
    for (let vez = 0; vez < 2; vez += 1) {
      await tocar(cdp, pagina.locator("[data-botones-mapa] button:visible").first());
      const filtros = pagina.locator("[data-filtros]:visible");
      await expect(filtros).toBeVisible();
      await comprobarToques(cdp, filtros);
      await pagina.keyboard.press("Escape");
      await expect(filtros).toBeHidden();
    }

    // Menú del teléfono (en 768 × 1024 los botones de capa van a la vista, sin menú).
    if (await botonMenu(pagina).isVisible()) {
      for (let vez = 0; vez < 2; vez += 1) {
        await abrirMenu(cdp, pagina);
        await comprobarToques(cdp, pagina.locator("dialog[open]"));
        await pagina.keyboard.press("Escape");
      }
      // Subcapas de Ucrania, con la capa encendida.
      await abrirMenu(cdp, pagina);
      const ucrania = pagina.locator("dialog[open] button[aria-pressed]", { hasText: /^Ucrania$/ }).first();
      if ((await ucrania.getAttribute("aria-pressed")) !== "true") await tocar(cdp, ucrania);
      for (let vez = 0; vez < 2; vez += 1) {
        if (vez > 0) await abrirMenu(cdp, pagina);
        await comprobarToques(cdp, pagina.locator("dialog[open] [data-capas-guerra]"));
        await pagina.keyboard.press("Escape");
      }
    } else {
      const capas = pagina.locator("[role=group][aria-label]:visible", { has: pagina.locator("button[aria-pressed]") }).first();
      await comprobarToques(cdp, capas);
    }
    await contexto.close();
  });
}
