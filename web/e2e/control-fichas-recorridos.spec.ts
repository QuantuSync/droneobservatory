// Control de calidad de las fichas (docs/control_fichas.md), como lo ve una persona: en un Android
// (Chromium, Pixel 7), un iPhone (WebKit, iPhone 14), una tableta táctil y el escritorio (Chromium
// y WebKit), en español y en inglés.
//
// - Bulgaria: el ataque a dos barcos de la noche del 12 al 13 de octubre de 2026 es una sola ficha
//   (EODI-2026-00512, la más antigua); los enlaces antiguos (00513 y 00514) llevan a ella, y el
//   ataque del 6 de octubre (00489) sigue aparte.
// - Núremberg: una sola ficha (00515) en el aeropuerto (EDDN), sin «Dron confirmado» ni «2–10»; el
//   enlace antiguo (00516) lleva a ella.
// - Las citas salen en el idioma de la página y el original se despliega con el dedo o el ratón
//   («Ver original» / «Show original»).
// - Moldavia (28 de noviembre de 2025): una sola ficha, la más antigua (EODI-2025-00243); los
//   enlaces de 00247, 00328 y 00046 llevan a ella.
// - Fichas corregidas por el repaso (CORREGIDAS) se abren y responden.
// - Adónde lleva cada identificador (su ficha, la que queda si se unió o 404 si se retiró) se lee de
//   los datos publicados (e2e/publicados.ts): un repaso posterior puede volver a unir fichas.
// - Sin errores de consola y con los enlaces internos de las fichas respondiendo.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "./base.ts";
import type { BrowserContext, CDPSession, Locator, Page } from "@playwright/test";

import { destino, publicados } from "./publicados.ts";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "control-fichas");
const BULGARIA = "EODI-2026-00512";
const BULGARIA_ANTIGUOS = ["EODI-2026-00513", "EODI-2026-00514"];
const BULGARIA_6_OCTUBRE = "EODI-2026-00489";
const NUREMBERG = "EODI-2026-00515";
const NUREMBERG_ANTIGUO = "EODI-2026-00516";
/** Moldavia, 28 de noviembre de 2025: queda la ficha más antigua (00243); las otras llevan a ella. */
const MOLDAVIA = "EODI-2025-00243";
const MOLDAVIA_UNIDAS = ["EODI-2025-00247", "EODI-2025-00328", "EODI-2025-00046"];
/** Fichas corregidas por el repaso de todo lo publicado (informe del control). */
const CORREGIDAS = (process.env.CORREGIDAS ?? "EODI-2025-00066,EODI-2025-00154,EODI-2026-00065,EODI-2026-00268,EODI-2025-00248")
  .split(",")
  .filter(Boolean);
const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];

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

async function dedo(pagina: Page, contexto: BrowserContext, chromium: boolean): Promise<CDPSession | null> {
  return chromium ? contexto.newCDPSession(pagina) : null;
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
  const cdp = await dedo(pagina, contexto, chromium);
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

/** La ficha a la que lleva la dirección de un identificador, según los datos publicados. */
async function queda(pagina: Page, id: string): Promise<string> {
  return destino(await publicados(pagina.request), id) ?? id;
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

/** Abre la ficha (o la que queda, si el repaso la unió a otra: e2e/publicados.ts). */
async function abrir(pagina: Page, contexto: BrowserContext, id: string, idioma: "es" | "en", chromium: boolean, tactil: boolean) {
  await pagina.goto(ruta(id, idioma), { waitUntil: "domcontentloaded" });
  await expect(pagina).toHaveURL(new RegExp(`${await queda(pagina, id)}$`), { timeout: 30_000 });
  await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
  await leerComoPersona(pagina, contexto, chromium, tactil);
  return pagina.locator("[data-ficha] article").first();
}

if (process.env.ANCHO !== undefined && process.env.ALTO !== undefined) {
  test.use({ viewport: { width: Number(process.env.ANCHO), height: Number(process.env.ALTO) } });
}

test.describe("Control de calidad de las fichas, como una persona", () => {
  for (const idioma of ["es", "en"] as const) {
    test(`Bulgaria y Núremberg unidas y los enlaces antiguos (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(300_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const chromium = browserName === "chromium";
      // Núremberg: en el aeropuerto, sin dron confirmado ni 2-10 drones.
      const nuremberg = await abrir(pagina, contexto, NUREMBERG, idioma, chromium, tactil);
      await expect(nuremberg).toContainText(idioma === "es" ? "Núremberg" : "Nuremberg");
      await expect(nuremberg).toContainText(idioma === "es" ? "Aeropuerto de Núremberg" : "Nuremberg Airport");
      await expect(nuremberg).not.toContainText(idioma === "es" ? "Dron confirmado" : "Drone confirmed");
      await expect(nuremberg).not.toContainText("2–10");
      expect(await enlacesInternos(pagina), "enlaces internos de Núremberg").toEqual([]);
      await capturar(pagina, errores, join(CAPTURAS, `${NUREMBERG}-${idioma}-${info.project.name}.png`));
      // Una cita traducida: el original se despliega con el dedo o el ratón.
      const traducida = nuremberg.locator("[data-cita-traducida]:visible").first();
      await expect(traducida).toBeAttached();
      const desplegable = traducida.locator("details").first();
      await expect(desplegable.locator("summary")).toHaveText(idioma === "es" ? "Ver original" : "Show original");
      await tocar(pagina, desplegable.locator("summary"), tactil);
      await expect(desplegable.locator("[data-cita-original]")).toBeVisible();
      await capturar(pagina, errores, join(CAPTURAS, `${NUREMBERG}-original-${idioma}-${info.project.name}.png`));
      // El enlace antiguo lleva a la ficha que queda.
      await pagina.goto(ruta(NUREMBERG_ANTIGUO, idioma), { waitUntil: "domcontentloaded" });
      await expect(pagina).toHaveURL(new RegExp(`${await queda(pagina, NUREMBERG_ANTIGUO)}$`), { timeout: 30_000 });
      // Bulgaria: una ficha, y los enlaces antiguos llevan a ella.
      const bulgaria = await abrir(pagina, contexto, BULGARIA, idioma, chromium, tactil);
      await expect(bulgaria).toBeVisible();
      expect(await enlacesInternos(pagina), "enlaces internos de Bulgaria").toEqual([]);
      await capturar(pagina, errores, join(CAPTURAS, `${BULGARIA}-${idioma}-${info.project.name}.png`));
      for (const antiguo of BULGARIA_ANTIGUOS) {
        await pagina.goto(ruta(antiguo, idioma), { waitUntil: "domcontentloaded" });
        await expect(pagina).toHaveURL(new RegExp(`${await queda(pagina, antiguo)}$`), { timeout: 30_000 });
      }
      // El ataque del 6 de octubre sigue siendo otra ficha.
      await pagina.goto(ruta(BULGARIA_6_OCTUBRE, idioma), { waitUntil: "domcontentloaded" });
      await expect(pagina).toHaveURL(new RegExp(`${await queda(pagina, BULGARIA_6_OCTUBRE)}$`), { timeout: 30_000 });
      expect(errores).toEqual([]);
    });

    test(`Moldavia, 28 de noviembre de 2025: una ficha, la más antigua (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(300_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const moldavia = await abrir(pagina, contexto, MOLDAVIA, idioma, browserName === "chromium", tactil);
      await expect(moldavia).toContainText(idioma === "es" ? "Moldavia" : "Moldova");
      expect(await enlacesInternos(pagina), "enlaces internos de Moldavia").toEqual([]);
      await capturar(pagina, errores, join(CAPTURAS, `${MOLDAVIA}-${idioma}-${info.project.name}.png`));
      // Los enlaces de las fichas unidas llevan a la más antigua.
      for (const antiguo of MOLDAVIA_UNIDAS) {
        await pagina.goto(ruta(antiguo, idioma), { waitUntil: "domcontentloaded" });
        await expect(pagina).toHaveURL(new RegExp(`${await queda(pagina, antiguo)}$`), { timeout: 30_000 });
      }
      expect(errores).toEqual([]);
    });

    test(`fichas corregidas por el repaso y sus citas (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(600_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const datos = await publicados(pagina.request);
      for (const id of CORREGIDAS) {
        if (destino(datos, id) === null) {
          expect((await pagina.request.get(ruta(id, idioma))).status(), `${id} retirada`).toBe(404);
          continue;
        }
        const ficha = await abrir(pagina, contexto, id, idioma, browserName === "chromium", tactil);
        await expect(ficha.locator("h2, h3").first()).toBeVisible();
        expect(await enlacesInternos(pagina), `${id} enlaces internos`).toEqual([]);
        const citas = ficha.locator("[data-cita-traducida]:visible");
        if ((await citas.count()) > 0) {
          const desplegable = citas.first().locator("details").first();
          await tocar(pagina, desplegable.locator("summary"), tactil);
          await expect(desplegable.locator("[data-cita-original]")).toBeVisible();
        }
        await capturar(pagina, errores, join(CAPTURAS, `${id}-${idioma}-${info.project.name}.png`));
      }
      expect(errores).toEqual([]);
    });
  }
});
