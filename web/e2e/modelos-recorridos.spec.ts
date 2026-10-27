// Dos modelos y arreglos del 14 de octubre de 2026 (docs/modelos.md), como lo ve una persona: en un
// Android (Chromium, Pixel 7), un iPhone (WebKit, iPhone 14), una tableta táctil y el escritorio
// (Chromium y WebKit), en español y en inglés.
//
// - Ficha de un ataque de la capa de Ucrania: las zonas de lanzamiento y la autoridad del historial
//   en el idioma de la página, nunca en cirílico; sus citas, traducidas, con el original que se
//   despliega con el dedo o el ratón.
// - Fichas nuevas (NUEVAS, las que publicó la recogida con los modelos nuevos): se abren, se leen y
//   sus citas salen traducidas.
// - Sin errores de consola y con los enlaces internos de las fichas respondiendo.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "./base.ts";
import type { BrowserContext, CDPSession, Locator, Page } from "@playwright/test";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "modelos");
/** Un ataque con zonas de lanzamiento que el parte escribe en ucraniano (14 de octubre de 2026). */
const ATAQUE = process.env.ATAQUE ?? "EODI-UA-2026-1051";
const ZONAS = {
  es: ["Millerovo", "Oriol", "Donetsk (ocupada)", "Hvardiiske (Crimea ocupada)", "mar de Azov"],
  en: ["Millerovo", "Oryol", "Donetsk (occupied)", "Hvardiiske (occupied Crimea)", "Sea of Azov"],
};
const NUEVAS = (process.env.NUEVAS ?? "").split(",").filter(Boolean);
const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];
const CIRILICO = /[Ѐ-ӿ]/u;

function ruta(id: string, idioma: "es" | "en"): string {
  return idioma === "en" ? `/en/${id}` : `/${id}`;
}

function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("console", (m) => {
    if (m.type() !== "error" || /ntfy:|intent:|Ignored attempt to cancel a touchmove/.test(m.text())) return;
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

async function capturar(pagina: Page, errores: string[], ruta_: string) {
  const antes = errores.length;
  await pagina.screenshot({ path: ruta_, caret: "initial" });
  await pagina.waitForTimeout(200);
  const despues = errores.splice(antes).filter((e) => !/Refused to apply a stylesheet/.test(e));
  errores.push(...despues);
}

async function arrastrar(pagina: Page, cdp: CDPSession | null, x: number, y: number, dy: number) {
  if (cdp !== null) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    for (let i = 1; i <= 14; i += 1) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: y + (dy * i) / 14 }] });
      await pagina.waitForTimeout(16);
    }
    await pagina.waitForTimeout(300);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  } else {
    await pagina.mouse.move(x, y);
    await pagina.mouse.down();
    await pagina.mouse.move(x, y + dy, { steps: 14 });
    await pagina.mouse.up();
  }
  await pagina.waitForTimeout(700);
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
  const cdp = chromium ? await contexto.newCDPSession(pagina) : null;
  const asa = pagina.locator("aside[data-altura] button[data-arrastre]").first();
  if ((await asa.count()) > 0 && (await asa.isVisible())) {
    const caja = await asa.boundingBox();
    if (caja !== null) await arrastrar(pagina, cdp, caja.x + caja.width / 2, caja.y + caja.height / 2, -350);
  }
}

/** Lleva el elemento a la vista y lo toca (o lo pulsa con el ratón). */
async function tocar(pagina: Page, elemento: Locator, tactil: boolean) {
  await elemento.scrollIntoViewIfNeeded();
  const caja = await elemento.boundingBox();
  if (caja === null) throw new Error("elemento sin caja");
  if (tactil) await pagina.touchscreen.tap(caja.x + caja.width / 2, caja.y + caja.height / 2);
  else await pagina.mouse.click(caja.x + caja.width / 2, caja.y + caja.height / 2);
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
  await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
  await leerComoPersona(pagina, contexto, chromium, tactil);
  return pagina.locator("[data-ficha] article").first();
}

/** Toca «Ver original» de la primera cita traducida y comprueba que se ve el original. */
async function desplegarOriginal(pagina: Page, ficha: Locator, idioma: "es" | "en", tactil: boolean) {
  const traducida = ficha.locator("[data-cita-traducida]:visible").first();
  await expect(traducida).toBeAttached();
  const desplegable = traducida.locator("details").first();
  await expect(desplegable.locator("summary")).toHaveText(idioma === "es" ? "Ver original" : "Show original");
  await tocar(pagina, desplegable.locator("summary"), tactil);
  await expect(desplegable.locator("[data-cita-original]")).toBeVisible();
}

if (process.env.ANCHO !== undefined && process.env.ALTO !== undefined) {
  test.use({ viewport: { width: Number(process.env.ANCHO), height: Number(process.env.ALTO) } });
}

test.describe("Dos modelos y arreglos del 14 de octubre, como una persona", () => {
  for (const idioma of ["es", "en"] as const) {
    test(`ficha de un ataque de Ucrania en el idioma de la página (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(300_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const ficha = await abrir(pagina, contexto, ATAQUE, idioma, browserName === "chromium", tactil);
      const fila = ficha.locator("dt", { hasText: idioma === "es" ? "Zonas de lanzamiento" : "Launch areas" }).locator("xpath=following-sibling::dd[1]");
      await expect(fila).toBeVisible();
      for (const zona of ZONAS[idioma]) await expect(fila).toContainText(zona);
      expect(await fila.textContent()).not.toMatch(CIRILICO);
      const historial = ficha.locator("section ol").last();
      expect(await historial.textContent()).not.toMatch(CIRILICO);
      await desplegarOriginal(pagina, ficha, idioma, tactil);
      expect(await enlacesInternos(pagina), "enlaces internos del ataque").toEqual([]);
      await capturar(pagina, errores, join(CAPTURAS, `${ATAQUE}-${idioma}-${info.project.name}.png`));
      expect(errores).toEqual([]);
    });

    test(`fichas nuevas con los modelos nuevos (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.skip(NUEVAS.length === 0, "sin fichas nuevas que mirar (NUEVAS)");
      test.setTimeout(600_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      for (const id of NUEVAS) {
        const ficha = await abrir(pagina, contexto, id, idioma, browserName === "chromium", tactil);
        await expect(ficha.locator("h2, h3").first()).toBeVisible();
        expect(await enlacesInternos(pagina), `${id} enlaces internos`).toEqual([]);
        if ((await ficha.locator("[data-cita-traducida]:visible").count()) > 0) {
          await desplegarOriginal(pagina, ficha, idioma, tactil);
        }
        await capturar(pagina, errores, join(CAPTURAS, `${id}-${idioma}-${info.project.name}.png`));
      }
      expect(errores).toEqual([]);
    });
  }
});
