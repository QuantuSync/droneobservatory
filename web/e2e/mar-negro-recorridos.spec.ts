// Fichas del mar Negro que esperaban al experto el 15 de octubre de 2026 y la EODI-2025-00248, como
// las ve una persona: en un Android (Chromium, Pixel 7), un iPhone (WebKit, iPhone 14), una tableta
// táctil y el escritorio (Chromium y WebKit), en español y en inglés (docs/modelos.md, «Topes»).
//
// - Cada ficha del mar Negro (00512, 00532, 00536, 00537, 00538, 00539, 00540, 00541) se abre: o es
//   su propia ficha o su enlace antiguo lleva a la ficha con la que se unió; las retiradas (la 00539,
//   un reportaje) responden 404. Adónde lleva cada una se lee de los datos publicados
//   (e2e/publicados.ts): el repaso puede unir o retirar fichas sin que el recorrido cambie.
// - La EODI-2025-00248 (Malinas-Sur) sale con la presencia de dron de sus datos (no confirmado).
// - Sin errores de consola y con los enlaces internos de las fichas respondiendo.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "./base.ts";
import type { BrowserContext, Page } from "@playwright/test";

import { textos } from "../src/i18n/index.ts";
import { destino, publicados } from "./publicados.ts";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "mar-negro");
const MAR_NEGRO = (
  process.env.MAR_NEGRO ??
  "EODI-2026-00512,EODI-2026-00532,EODI-2026-00536,EODI-2026-00537,EODI-2026-00538,EODI-2026-00539,EODI-2026-00540,EODI-2026-00541"
)
  .split(",")
  .filter(Boolean);
const MALINAS = "EODI-2025-00248";
const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];

function ruta(id: string, idioma: "es" | "en"): string {
  return idioma === "en" ? `/en/${id}` : `/${id}`;
}

function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("console", (m) => {
    // La hoja de estilo que inyecta la captura de Playwright en WebKit choca con la CSP: no es de la web.
    if (m.type() !== "error" || /ntfy:|intent:|Ignored attempt to cancel a touchmove|Refused to apply a stylesheet/.test(m.text())) return;
    errores.push(`consola: ${m.text()}`);
  });
  pagina.on("pageerror", (e) => {
    if (/access control checks/.test(e.message)) return;
    errores.push(`excepción: ${e.message}`);
  });
  pagina.on("requestfailed", (p) => {
    const motivo = p.failure()?.errorText ?? "";
    if (/ABORTED|cancelled|access control checks/i.test(motivo)) return;
    errores.push(`petición: ${p.url()} ${motivo}`);
  });
  return errores;
}

/** En el teléfono, sube la hoja con el dedo; en el escritorio, mueve la rueda sobre la ficha. */
async function leerComoPersona(pagina: Page, contexto: BrowserContext, chromium: boolean, tactil: boolean) {
  const ficha = pagina.locator("[data-ficha] article").first();
  await expect(ficha).toBeVisible({ timeout: 30_000 });
  if (!tactil) {
    const caja = await ficha.boundingBox();
    if (caja !== null) {
      await pagina.mouse.move(caja.x + caja.width / 2, caja.y + Math.min(caja.height / 2, 300));
      await pagina.mouse.wheel(0, 800);
      await pagina.waitForTimeout(400);
    }
    return;
  }
  const asa = pagina.locator("aside[data-altura] button[data-arrastre]").first();
  if ((await asa.count()) === 0 || !(await asa.isVisible())) return;
  const caja = await asa.boundingBox();
  if (caja === null) return;
  const x = caja.x + caja.width / 2;
  const y = caja.y + caja.height / 2;
  if (chromium) {
    const cdp = await contexto.newCDPSession(pagina);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    for (let i = 1; i <= 14; i += 1) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y - (350 * i) / 14 }] });
      await pagina.waitForTimeout(16);
    }
    await pagina.waitForTimeout(300);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  } else {
    await pagina.mouse.move(x, y);
    await pagina.mouse.down();
    await pagina.mouse.move(x, y - 350, { steps: 14 });
    await pagina.mouse.up();
  }
  await pagina.waitForTimeout(700);
}

async function enlacesInternos(pagina: Page): Promise<string[]> {
  const hrefs = await pagina.locator("[data-ficha] article a[href]").evaluateAll((enlaces) =>
    enlaces.map((a) => (a as HTMLAnchorElement).href).filter((h) => h.startsWith(location.origin)),
  );
  const rotos: string[] = [];
  for (const href of [...new Set(hrefs)]) {
    const respuesta = await pagina.request.get(href);
    if (respuesta.status() >= 400) rotos.push(`${href} → ${respuesta.status()}`);
  }
  return rotos;
}

async function abrir(pagina: Page, contexto: BrowserContext, id: string, idioma: "es" | "en", chromium: boolean, tactil: boolean) {
  await pagina.goto(ruta(id, idioma), { waitUntil: "domcontentloaded" });
  const queda = destino(await publicados(pagina.request), id) ?? id;
  await expect(pagina).toHaveURL(new RegExp(`${queda}$`), { timeout: 30_000 });
  await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
  await leerComoPersona(pagina, contexto, chromium, tactil);
  return pagina.locator("[data-ficha] article").first();
}

test.describe("Fichas del mar Negro y la 00248, como una persona", () => {
  for (const idioma of ["es", "en"] as const) {
    test(`mar Negro y enlaces antiguos (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(600_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const datos = await publicados(pagina.request);
      for (const id of MAR_NEGRO) {
        if (destino(datos, id) === null) {
          expect((await pagina.request.get(ruta(id, idioma))).status(), `${id} retirada`).toBe(404);
          continue;
        }
        const ficha = await abrir(pagina, contexto, id, idioma, browserName === "chromium", tactil);
        await expect(ficha.locator("h2, h3").first()).toBeVisible();
        expect(await enlacesInternos(pagina), `${id} enlaces internos`).toEqual([]);
        await pagina.screenshot({ path: join(CAPTURAS, `${id}-${idioma}-${info.project.name}.png`) });
      }
      expect(errores).toEqual([]);
    });

    test(`la 00248 con la presencia de dron de sus datos (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(300_000);
      const errores = vigilar(pagina);
      const ficha = await abrir(pagina, contexto, MALINAS, idioma, browserName === "chromium", info.project.use.hasTouch === true);
      // Lo que dicen los datos publicados (el 15 de octubre de 2026, «no confirmado»): si una
      // autoridad lo cambia, la ficha tiene que decir lo nuevo, no lo de entonces.
      const datos = await publicados(pagina.request);
      const presencia = datos.fichas.get(destino(datos, MALINAS) ?? MALINAS)?.presencia_dron ?? "no_confirmada";
      const etiquetas = textos(idioma).presencia;
      await expect(ficha).toContainText(etiquetas[presencia]);
      if (presencia !== "confirmada") await expect(ficha).not.toContainText(etiquetas.confirmada);
      expect(await enlacesInternos(pagina), "enlaces internos de la 00248").toEqual([]);
      await pagina.screenshot({ path: join(CAPTURAS, `${MALINAS}-${idioma}-${info.project.name}.png`) });
      expect(errores).toEqual([]);
    });
  }
});
