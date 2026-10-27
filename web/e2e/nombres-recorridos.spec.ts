// Nombres de lugar y fichas (docs/nombres_lugar.md), como los ve una persona: en un Android
// (Chromium, Pixel 7), un iPhone (WebKit, iPhone 14), una tableta táctil y el escritorio (Chromium
// y WebKit), en español y en inglés. Se abre la ficha por su dirección; en el teléfono se sube la
// hoja con el dedo y se desplaza su contenido antes de leerla. Se comprueba el título, «Lugar»,
// que «Frontera o interior» solo sale en el flanco este, que nada sale en otro alfabeto fuera de
// las citas, que no hay errores de consola y que los enlaces internos de la ficha responden.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "./base.ts";
import type { BrowserContext, CDPSession, Page } from "@playwright/test";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "nombres");
const OTRO_ALFABETO = /[Ͱ-ϿЀ-ӿ]/;

interface Caso {
  id: string;
  que: string;
  titulo?: { es: string; en: string };
  lugar?: { es: string; en: string };
  /** Si la fila «Frontera o interior» tiene que salir. */
  zona: boolean;
}

const CASOS: Caso[] = [
  {
    id: "EODI-2026-00002",
    que: "Pafos",
    titulo: { es: "Aeropuerto de Pafos", en: "Paphos International Airport" },
    lugar: { es: "Pafos, Chipre", en: "Paphos, Cyprus" },
    zona: false,
  },
  {
    id: "EODI-2025-00057",
    que: "Lárnaca",
    titulo: { es: "Aeropuerto de Lárnaca", en: "Larnaca International Airport" },
    lugar: { es: "Lárnaca, Chipre", en: "Larnaca, Cyprus" },
    zona: false,
  },
  {
    id: "EODI-2026-00268",
    que: "Akrotiri",
    titulo: { es: "RAF Akrotiri", en: "RAF Akrotiri" },
    lugar: { es: "Akrotiri (base británica), Chipre", en: "Akrotiri (British base), Cyprus" },
    zona: false,
  },
  {
    id: "EODI-2025-00088",
    que: "Gibraltar",
    titulo: { es: "RAF Gibraltar", en: "RAF Gibraltar" },
    lugar: { es: "Gibraltar (Reino Unido)", en: "Gibraltar (United Kingdom)" },
    zona: false,
  },
  // El control de las fichas afina el lugar con lo que dice la fuente («Evros» o «río Maritsa», el
  // mismo río): basta el país en su idioma.
  { id: "EODI-2026-00050", que: "Grecia", lugar: { es: ", Grecia", en: ", Greece" }, zona: false },
  {
    id: "EODI-2025-00124",
    que: "Bulgaria",
    titulo: { es: "Aeropuerto de Sofía", en: "Sofia Airport" },
    lugar: { es: "Sofía, Bulgaria", en: "Sofia, Bulgaria" },
    zona: true,
  },
  {
    id: "EODI-2025-00399",
    que: "Canarias (ultramar)",
    titulo: { es: "Aeropuerto de Lanzarote", en: "Lanzarote Airport" },
    lugar: { es: "Lanzarote, España", en: "Lanzarote, Spain" },
    zona: false,
  },
  { id: "EODI-2025-00295", que: "Polonia", lugar: { es: "Cześniki, Polonia", en: "Cześniki, Poland" }, zona: true },
];

/** Un impacto de la capa de guerra en Ucrania (comunidad de Khotin, Sumy). */
const UCRANIA = { id: "EODI-IG-2024-00001" };

function ruta(id: string, idioma: "es" | "en"): string {
  return idioma === "en" ? `/en/${id}` : `/${id}`;
}

function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("console", (m) => {
    // Chromium avisa (no es un error de la web) cuando el dedo de la prueba arrastra sobre un
    // contenido que aún se desplaza; WebKit rechaza el estilo que mete Playwright para la captura.
    if (m.type() !== "error" || /ntfy:|intent:|Ignored attempt to cancel a touchmove/.test(m.text())) return;
    errores.push(`consola: ${m.text()}`);
  });
  pagina.on("pageerror", (e) => {
    // WebKit corta las lecturas de teselas en curso al cambiar de página (no es de la web).
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

/**
 * Una captura. En WebKit, Playwright mete un estilo en la página para hacerla y la política de
 * seguridad de la web lo rechaza con un error de consola: ese error es de la captura, no de la web.
 */
async function capturar(pagina: Page, errores: string[], ruta: string) {
  const antes = errores.length;
  await pagina.screenshot({ path: ruta, caret: "initial" });
  await pagina.waitForTimeout(200);
  const despues = errores.splice(antes).filter((e) => !/Refused to apply a stylesheet/.test(e));
  errores.push(...despues);
}

/** El dedo: toques y arrastres táctiles de bajo nivel en Chromium, la pantalla táctil en WebKit. */
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

/** En el teléfono, sube la hoja con el dedo y desplaza la ficha hasta abajo y otra vez arriba. */
async function leerComoPersona(pagina: Page, contexto: BrowserContext, chromium: boolean, tactil: boolean) {
  const ficha = pagina.locator("[data-ficha] article").first();
  await expect(ficha).toBeVisible({ timeout: 30_000 });
  if (!tactil) {
    const caja = await ficha.boundingBox();
    if (caja !== null) {
      await pagina.mouse.move(caja.x + caja.width / 2, caja.y + Math.min(caja.height / 2, 300));
      await pagina.mouse.wheel(0, 800);
      await pagina.waitForTimeout(400);
      await pagina.mouse.wheel(0, -800);
    }
    return;
  }
  const cdp = await dedo(pagina, contexto, chromium);
  const asa = pagina.locator("aside[data-altura] button[data-arrastre]").first();
  if ((await asa.count()) > 0 && (await asa.isVisible())) {
    const caja = await asa.boundingBox();
    if (caja !== null) await arrastrar(pagina, cdp, caja.x + caja.width / 2, caja.y + caja.height / 2, -350);
  }
  const caja = await ficha.boundingBox();
  if (caja !== null && cdp !== null) {
    await arrastrar(pagina, cdp, caja.x + caja.width / 2, Math.min(caja.y + caja.height / 2, 600), -300);
    await arrastrar(pagina, cdp, caja.x + caja.width / 2, Math.min(caja.y + caja.height / 2, 600), 300);
  } else {
    await ficha.evaluate((e) => {
      for (let a: HTMLElement | null = e as HTMLElement; a !== null; a = a.parentElement) {
        if (/(auto|scroll)/.test(getComputedStyle(a).overflowY) && a.scrollHeight > a.clientHeight) {
          a.scrollBy(0, 600);
          a.scrollBy(0, -600);
          return;
        }
      }
    });
  }
}

/** Las filas de la ficha: nombre → texto, sin las citas. */
async function filas(pagina: Page): Promise<Record<string, string>> {
  return pagina.locator("[data-ficha] article").first().evaluate((articulo) => {
    const salida: Record<string, string> = {};
    for (const dt of articulo.querySelectorAll("dt")) {
      const dd = dt.nextElementSibling;
      if (dd === null) continue;
      const copia = dd.cloneNode(true) as Element;
      copia.querySelectorAll("blockquote, q, details, [lang]").forEach((c) => c.remove());
      salida[dt.textContent?.trim() ?? ""] = (copia.textContent ?? "").replace(/\s+/g, " ").trim();
    }
    return salida;
  });
}

/** Los enlaces internos de la ficha responden (sin seguir los externos de las fuentes). */
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

const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];

// Con ANCHO y ALTO, en otra pantalla (360 × 800 en el Android, por ejemplo).
if (process.env.ANCHO !== undefined && process.env.ALTO !== undefined) {
  test.use({ viewport: { width: Number(process.env.ANCHO), height: Number(process.env.ALTO) } });
}

test.describe("nombres de lugar y fichas, como una persona", () => {
  test.beforeEach(({ browserName }, info) => {
    void browserName;
    test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
  });

  for (const idioma of ["es", "en"] as const) {
    test(`las fichas de Chipre, Gibraltar, Grecia, Bulgaria, Canarias y Polonia (${idioma})`, async ({ page: pagina, context: contexto, browserName }, info) => {
      test.setTimeout(400_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const t = idioma === "es"
        ? { lugar: "Lugar", zona: "Frontera o interior" }
        : { lugar: "Place", zona: "Border or interior" };
      for (const caso of CASOS) {
        await pagina.goto(ruta(caso.id, idioma), { waitUntil: "domcontentloaded" });
        await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
        await leerComoPersona(pagina, contexto, browserName === "chromium", tactil);
        const titulo = (await pagina.locator("[data-ficha] article h2").first().textContent())?.trim() ?? "";
        if (caso.titulo !== undefined) expect(titulo, `${caso.id} título`).toBe(caso.titulo[idioma]);
        expect(OTRO_ALFABETO.test(titulo), `${caso.id} título sin otro alfabeto`).toBe(false);
        const deFilas = await filas(pagina);
        if (caso.lugar !== undefined) expect(deFilas[t.lugar] ?? "", `${caso.id} lugar`).toContain(caso.lugar[idioma]);
        expect(t.zona in deFilas, `${caso.id} ${t.zona}`).toBe(caso.zona);
        for (const [nombre, texto] of Object.entries(deFilas)) {
          expect(OTRO_ALFABETO.test(texto), `${caso.id} «${nombre}»: ${texto}`).toBe(false);
        }
        expect(await enlacesInternos(pagina), `${caso.id} enlaces internos`).toEqual([]);
        await capturar(pagina, errores, join(CAPTURAS, `${caso.id}-${idioma}-${info.project.name}.png`));
      }
      // Un impacto de la capa de guerra en Ucrania: se abre tocando su punto en el mapa.
      await pagina.goto(idioma === "en" ? "/en" : "/", { waitUntil: "domcontentloaded" });
      await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
      const ucrania = (await (await pagina.request.get("/datos/ucrania.json")).json()) as {
        impactos: { id: string; lugar: { punto: { lat: number; lon: number } } }[];
      };
      const impacto = ucrania.impactos.find((i) => i.id === UCRANIA.id) ?? ucrania.impactos[0];
      if (impacto === undefined) throw new Error("sin impactos");
      await pagina.locator(".maplibregl-canvas").focus();
      await pagina.keyboard.press("2");
      const { lat, lon } = impacto.lugar.punto;
      const punto = await pagina.evaluate(
        ([la, lo]) =>
          new Promise<{ x: number; y: number }>((listo) => {
            const elemento = document.querySelector(".maplibregl-map") as HTMLElement & {
              mapaDePruebas?: { once: (e: string, f: () => void) => void; jumpTo: (o: object) => void; project: (c: [number, number]) => { x: number; y: number } };
            };
            const mapa = elemento.mapaDePruebas;
            if (mapa === undefined) throw new Error("sin mapa de pruebas");
            mapa.once("idle", () => {
              const caja = elemento.getBoundingClientRect();
              const p = mapa.project([lo, la]);
              listo({ x: caja.left + p.x, y: caja.top + p.y });
            });
            mapa.jumpTo({ center: [lo, la], zoom: 12 });
          }),
        [lat, lon] as const,
      );
      await pagina.waitForTimeout(1500);
      if (tactil) await pagina.touchscreen.tap(punto.x, punto.y);
      else await pagina.mouse.click(punto.x, punto.y);
      await pagina.waitForTimeout(1500);
      const enLista = pagina.locator("[data-ficha] button").filter({ hasText: /EODI-IG-|·/ }).first();
      if ((await pagina.locator("[data-ficha] article h2").count()) === 0 && (await enLista.isVisible().catch(() => false))) {
        await enLista.click();
      }
      const articulo = pagina.locator("[data-ficha] article").first();
      await expect(articulo).toBeVisible({ timeout: 20_000 });
      await leerComoPersona(pagina, contexto, browserName === "chromium", tactil);
      const texto = await articulo.evaluate((a) => {
        const c = a.cloneNode(true) as Element;
        c.querySelectorAll("blockquote, q, [lang]").forEach((x) => x.remove());
        return c.textContent ?? "";
      });
      expect(OTRO_ALFABETO.test(texto), `impacto: ${texto.slice(0, 200)}`).toBe(false);
      await capturar(pagina, errores, join(CAPTURAS, `ucrania-${idioma}-${info.project.name}.png`));
      expect(errores).toEqual([]);
    });
  }
});
