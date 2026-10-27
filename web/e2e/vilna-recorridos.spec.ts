// Sucesos separados y mapa con la posición de la Unión Europea (docs/sucesos_mezclados.md), como
// los ve una persona: en un Android (Chromium, Pixel 7), un iPhone (WebKit, iPhone 14), una tableta
// táctil y el escritorio (Chromium y WebKit), en español y en inglés.
//
// - Las dos fichas de Vilna (el cierre del 13 de septiembre de 2026 y el derribo de la noche del 14
//   al 15) se enlazan entre sí con «Suceso relacionado»; se sigue el enlace con el dedo o el ratón y
//   se vuelve por el de la otra. El enlace antiguo de EODI-2026-00072 lleva a la ficha del cierre.
// - El mapa en Chipre, Moldavia, Georgia, Crimea y el Donbás, a varios zooms: ningún rótulo de las
//   entidades que la Unión Europea no reconoce.
// - Sin errores de consola y con los enlaces internos de las fichas respondiendo.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "./base.ts";
import type { BrowserContext, CDPSession, Page } from "@playwright/test";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "vilna");
const CIERRE = "EODI-2026-00007";
const DERRIBO = "EODI-2026-00179";
const ANTIGUO = "EODI-2026-00072";
const PROHIBIDOS =
  /Northern Cyprus|Norte de Chipre|Kuzey Kıbrıs|Transnistr|Pridnestrov|Приднестров|Abkhaz|Abjasia|Аҧсны|Абхаз|South Ossetia|Osetia del Sur|Южная Осетия|Хуссар|Donetsk People|Luhansk People|Lugansk People|República Popular|Народная Республика|ДНР|ЛНР|Республика Крым/;

const ZONAS = [
  { nombre: "chipre", centro: [33.4, 35.2], zooms: [6, 8, 10] },
  { nombre: "moldavia", centro: [29.5, 46.9], zooms: [6, 8, 10] },
  { nombre: "georgia", centro: [42.5, 42.6], zooms: [6, 8] },
  { nombre: "crimea", centro: [34.1, 45.3], zooms: [6, 8, 10] },
  { nombre: "donbas", centro: [38.3, 48.2], zooms: [6, 8, 10] },
] as const;

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

/** Lleva el enlace a la vista y lo toca (o lo pulsa con el ratón). */
async function tocar(pagina: Page, enlace: ReturnType<Page["locator"]>, tactil: boolean) {
  await enlace.scrollIntoViewIfNeeded();
  const caja = await enlace.boundingBox();
  if (caja === null) throw new Error("enlace sin caja");
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

/** Los rótulos que el mapa dibuja ahora mismo (todas sus variantes de nombre). */
async function rotulos(pagina: Page, centro: readonly [number, number], zoom: number): Promise<string[]> {
  return pagina.evaluate(
    ([lo, la, z]) =>
      new Promise<string[]>((listo) => {
        const elemento = document.querySelector(".maplibregl-map") as HTMLElement & {
          mapaDePruebas?: {
            once: (e: string, f: () => void) => void;
            jumpTo: (o: object) => void;
            queryRenderedFeatures: () => { layer: { type: string }; properties: Record<string, unknown> }[];
          };
        };
        const mapa = elemento.mapaDePruebas;
        if (mapa === undefined) throw new Error("sin mapa de pruebas");
        mapa.once("idle", () => {
          const nombres = mapa
            .queryRenderedFeatures()
            .filter((f) => f.layer.type === "symbol")
            .flatMap((f) => Object.entries(f.properties).filter(([k]) => k.startsWith("name")).map(([, v]) => String(v)));
          listo([...new Set(nombres)]);
        });
        mapa.jumpTo({ center: [lo, la], zoom: z });
      }),
    [centro[0], centro[1], zoom] as const,
  );
}

const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];

if (process.env.ANCHO !== undefined && process.env.ALTO !== undefined) {
  test.use({ viewport: { width: Number(process.env.ANCHO), height: Number(process.env.ALTO) } });
}

test.describe("Vilna en dos fichas y mapa con la posición de la UE, como una persona", () => {
  test.beforeEach(({ browserName }, info) => {
    void browserName;
    test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
  });

  for (const idioma of ["es", "en"] as const) {
    test(`las dos fichas de Vilna, sus enlaces y el enlace antiguo (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.setTimeout(300_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const fila = idioma === "es" ? "Suceso relacionado" : "Related incident";
      for (const [desde, hacia] of [[CIERRE, DERRIBO], [DERRIBO, CIERRE]] as const) {
        await pagina.goto(ruta(desde, idioma), { waitUntil: "domcontentloaded" });
        await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
        await leerComoPersona(pagina, contexto, browserName === "chromium", tactil);
        const articulo = pagina.locator("[data-ficha] article").first();
        await expect(articulo.locator("dt", { hasText: fila })).toBeVisible();
        const relacionado = articulo.locator(`[data-suceso-relacionado="${hacia}"]`);
        await expect(relacionado).toContainText(idioma === "es" ? "Vilna" : "Vilnius");
        expect(await enlacesInternos(pagina), `${desde} enlaces internos`).toEqual([]);
        await capturar(pagina, errores, join(CAPTURAS, `${desde}-${idioma}-${info.project.name}.png`));
        // Se sigue el enlace a la otra ficha.
        await tocar(pagina, relacionado.locator("a").first(), tactil);
        await expect(pagina).toHaveURL(new RegExp(`${hacia}$`), { timeout: 20_000 });
        await expect(pagina.locator("[data-ficha] article").first().locator(`[data-suceso-relacionado="${desde}"]`)).toBeAttached({ timeout: 30_000 });
      }
      // El enlace antiguo lleva a la ficha del cierre.
      await pagina.goto(ruta(ANTIGUO, idioma), { waitUntil: "domcontentloaded" });
      await expect(pagina).toHaveURL(new RegExp(`${CIERRE}$`), { timeout: 30_000 });
      await expect(pagina.locator("[data-ficha] article").first()).toBeVisible({ timeout: 60_000 });
      await capturar(pagina, errores, join(CAPTURAS, `${ANTIGUO}-${idioma}-${info.project.name}.png`));
      expect(errores).toEqual([]);
    });

    test(`el mapa en Chipre, Moldavia, Georgia, Crimea y el Donbás (${idioma})`, async ({ page: pagina }, info) => {
      test.setTimeout(300_000);
      const errores = vigilar(pagina);
      await pagina.goto(idioma === "en" ? "/en" : "/", { waitUntil: "domcontentloaded" });
      await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
      for (const zona of ZONAS) {
        for (const zoom of zona.zooms) {
          const nombres = await rotulos(pagina, zona.centro, zoom);
          await pagina.waitForTimeout(500);
          const malos = nombres.filter((n) => PROHIBIDOS.test(n));
          expect(malos, `${zona.nombre} z${zoom}`).toEqual([]);
          await capturar(pagina, errores, join(CAPTURAS, `mapa-${zona.nombre}-z${zoom}-${idioma}-${info.project.name}.png`));
        }
      }
      // Kosovo sigue rotulado como país.
      const kosovo = await rotulos(pagina, [20.9, 42.6], 7);
      expect(kosovo.some((n) => /Kosovo/.test(n)), "Kosovo").toBe(true);
      expect(errores).toEqual([]);
    });
  }
});
