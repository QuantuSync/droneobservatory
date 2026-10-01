// La versión para el teléfono, en los tres tamaños de referencia y en las dos orientaciones:
// el mapa ocupa al menos el 80 % de la pantalla en reposo, ningún texto se corta con puntos
// suspensivos, todo lo que se toca mide al menos 44 px, los paneles son opacos, el contraste
// es AA y solo hay una hoja inferior a la vez. Deja capturas de cada tamaño.

import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import type { Resumen } from "../src/datos/tipos.ts";

const CAPTURAS = join(import.meta.dirname, "..", "..", "data", "capturas", "telefono");
const MAPA_LISTO = "[data-mapa-listo=true]";
const MS_DE_ASENTAMIENTO = 2000;
/** Lo que tarda el mapa en volar a una ficha, con margen. */
const MS_DE_VUELO = 2000;
const PARTE_MINIMA_DEL_MAPA = 0.8;
const LADO_TACTIL_MINIMO = 44;
/** Contraste AA: 4,5 para el texto normal y 3 para el grande (24 px, o 18,66 px en negrita). */
const CONTRASTE_NORMAL = 4.5;
const CONTRASTE_GRANDE = 3;
const TAMANOS = [
  { ancho: 360, alto: 800 },
  { ancho: 390, alto: 844 },
  { ancho: 412, alto: 915 },
];

const ACCESO: Record<string, string> =
  process.env.VERCEL_BYPASS === undefined
    ? {}
    : { "x-vercel-protection-bypass": process.env.VERCEL_BYPASS };

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await mkdir(CAPTURAS, { recursive: true });
  await pagina.screenshot({ path: join(CAPTURAS, `${nombre}.png`) });
}

/** Objetivos táctiles visibles de menos de 44 px (fuera del mapa, que se toca entero). */
async function objetivosPequenos(pagina: Page): Promise<string[]> {
  return pagina.evaluate((minimo) => {
    const selectores = "button, a[href], select, summary, [role=slider], [role=tab]";
    return [...document.querySelectorAll<HTMLElement | SVGElement>(selectores)]
      .filter((e) => {
        const caja = e.getBoundingClientRect();
        if (caja.width === 0 || caja.height === 0 || e.closest(".maplibregl-map") !== null) return false;
        const centro = document.elementFromPoint(caja.x + caja.width / 2, caja.y + caja.height / 2);
        // Lo que queda tapado por otra cosa no se puede tocar: no cuenta.
        if (centro === null || !(e.contains(centro) || centro.contains(e))) return false;
        // Los enlaces dentro de un texto corrido (las fuentes de una ficha) son la excepción
        // de WCAG para lo que va en línea con el texto.
        if (e instanceof HTMLAnchorElement && e.closest("p, li, blockquote") !== null && e.closest("[aria-label='Atribuciones del mapa']") === null) return false;
        return caja.height < minimo - 0.5 || caja.width < minimo - 0.5;
      })
      .map((e) => `${e.tagName} «${(e.textContent ?? "").trim().slice(0, 30)}» ${Math.round(e.getBoundingClientRect().width)}×${Math.round(e.getBoundingClientRect().height)}`);
  }, LADO_TACTIL_MINIMO);
}

/** Textos visibles cortados con puntos suspensivos. */
async function textosCortados(pagina: Page): Promise<string[]> {
  return pagina.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>("body *")]
      .filter((e) => {
        if (e.offsetParent === null) return false;
        const estilo = getComputedStyle(e);
        return estilo.textOverflow === "ellipsis" && e.scrollWidth > e.clientWidth;
      })
      .map((e) => (e.textContent ?? "").trim().slice(0, 40)),
  );
}

/** Textos visibles sin contraste AA contra su fondo real (el primero opaco hacia arriba). */
async function contrasteInsuficiente(pagina: Page): Promise<string[]> {
  return pagina.evaluate(
    ({ normal, grande }) => {
      const rgb = (texto: string) => (texto.match(/[\d.]+/g) ?? []).map(Number);
      const luminancia = ([r = 0, g = 0, b = 0]: number[]) => {
        const canal = (c: number) => {
          const v = c / 255;
          return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
        };
        return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
      };
      const fondo = (e: Element | null): number[] => {
        for (let actual = e; actual !== null; actual = actual.parentElement) {
          const color = rgb(getComputedStyle(actual).backgroundColor);
          if (color.length >= 3 && (color[3] ?? 1) >= 0.99) return color;
        }
        return rgb(getComputedStyle(document.body).backgroundColor);
      };
      const fallos: string[] = [];
      const recorrido = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let nodo = recorrido.nextNode(); nodo !== null; nodo = recorrido.nextNode()) {
        const padre = nodo.parentElement;
        if (padre === null || (nodo.textContent ?? "").trim() === "") continue;
        if (padre.closest(".maplibregl-map, svg, .sr-only, [aria-hidden=true]") !== null) continue;
        const caja = padre.getBoundingClientRect();
        if (caja.width === 0 || padre.offsetParent === null) continue;
        const estilo = getComputedStyle(padre);
        const texto = rgb(estilo.color);
        const l1 = luminancia(texto);
        const l2 = luminancia(fondo(padre));
        const razon = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
        const cuerpo = parseFloat(estilo.fontSize);
        const esGrande = cuerpo >= 24 || (cuerpo >= 18.66 && Number(estilo.fontWeight) >= 700);
        if (razon < (esGrande ? grande : normal)) {
          fallos.push(`«${(nodo.textContent ?? "").trim().slice(0, 30)}» ${razon.toFixed(2)}`);
        }
      }
      return fallos;
    },
    { normal: CONTRASTE_NORMAL, grande: CONTRASTE_GRANDE },
  );
}

/** Parte de la pantalla en la que el mapa queda a la vista (sin barras ni hojas encima). */
async function parteDelMapa(pagina: Page): Promise<number> {
  return pagina.evaluate(() => {
    const tapan = [
      document.querySelector("header"),
      document.querySelector("section[aria-label='Línea de tiempo']"),
      document.querySelector("[aria-label='Atribuciones del mapa']"),
    ];
    const total = window.innerWidth * window.innerHeight;
    const tapado = tapan.reduce((suma, e) => {
      const caja = e?.getBoundingClientRect();
      return caja === undefined ? suma : suma + caja.width * caja.height;
    }, 0);
    return 1 - tapado / total;
  });
}

/** Un punto con varios incidentes en el mismo sitio exacto, si lo hay. */
async function pilaDeIncidentes(pagina: Page): Promise<string | null> {
  const respuesta = await pagina.request.get("/datos/resumen.json", { headers: ACCESO });
  const resumen = (await respuesta.json()) as Resumen;
  const porPunto = new Map<string, string[]>();
  for (const i of resumen.incidentes) {
    if (i.punto === null) continue;
    const clave = `${i.punto.lon},${i.punto.lat}`;
    porPunto.set(clave, [...(porPunto.get(clave) ?? []), i.id]);
  }
  return [...porPunto.values()].find((ids) => ids.length > 1)?.[0] ?? null;
}

for (const { ancho, alto } of TAMANOS) {
  for (const vertical of [true, false]) {
    const viewport = vertical ? { width: ancho, height: alto } : { width: alto, height: ancho };
    const nombre = `${ancho}x${alto}-${vertical ? "vertical" : "horizontal"}`;

    test.describe(nombre, () => {
      test.use({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });

      test(`${nombre}: pantalla, menú, ficha, punto con varios y línea de tiempo`, async ({ page, baseURL }, info) => {
        test.skip(info.project.name !== "movil", "la versión de teléfono se comprueba una sola vez");
        if (Object.keys(ACCESO).length > 0 && baseURL !== undefined) {
          const propio = new URL(baseURL).origin;
          await page.route(
            (url) => url.origin === propio,
            (ruta) => ruta.continue({ headers: { ...ruta.request().headers(), ...ACCESO } }),
          );
        }
        await page.goto("/");
        await page.waitForSelector(MAPA_LISTO);
        await capturar(page, `${nombre}-inicio`);

        // En reposo: el mapa a la vista, nada cortado, todo tocable y con contraste.
        expect(await parteDelMapa(page)).toBeGreaterThanOrEqual(PARTE_MINIMA_DEL_MAPA);
        expect(await textosCortados(page)).toEqual([]);
        expect(await objetivosPequenos(page)).toEqual([]);
        expect(await contrasteInsuficiente(page)).toEqual([]);
        await expect(page.getByRole("button", { name: "Acercar" })).toHaveCount(0);
        // Las zonas seguras (muesca y barras del navegador) se respetan.
        await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /viewport-fit=cover/);
        const margenSeguro = await page.evaluate(() =>
          [...document.styleSheets].some((hoja) =>
            [...hoja.cssRules].some((regla) => regla.cssText.includes("safe-area-inset-top")),
          ),
        );
        expect(margenSeguro).toBe(true);

        // El menú: una hoja a pantalla completa, opaca, con todo.
        await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
        const menu = page.getByRole("dialog", { name: "Menú" });
        await expect(menu).toBeVisible();
        for (const seccion of ["Cifras del periodo elegido", "Capas", "Filtros", "Más", "Idioma"]) {
          await expect(menu.getByRole("heading", { name: seccion, exact: true })).toBeVisible();
        }
        expect(await menu.evaluate((e) => getComputedStyle(e).backgroundColor)).toMatch(/^rgb\(/);
        await capturar(page, `${nombre}-menu`);
        expect(await objetivosPequenos(page)).toEqual([]);
        expect(await textosCortados(page)).toEqual([]);
        expect(await contrasteInsuficiente(page)).toEqual([]);
        await menu.getByRole("button", { name: "Cerrar el menú" }).click();

        // La ficha de un punto con varios incidentes; después, el punto con su lista.
        const primero = await pilaDeIncidentes(page);
        if (primero === null) throw new Error("no hay ningún punto con varios incidentes");
        await page.goto(`/${primero}`);
        await page.waitForSelector(MAPA_LISTO);
        const ficha = page.getByRole("complementary", { name: new RegExp(primero) });
        await expect(ficha).toBeVisible();
        await page.waitForTimeout(MS_DE_VUELO);
        expect(await ficha.evaluate((e) => getComputedStyle(e).backgroundColor)).toMatch(/^rgb\(/);
        await capturar(page, `${nombre}-ficha`);
        expect(await objetivosPequenos(page)).toEqual([]);
        expect(await textosCortados(page)).toEqual([]);
        // El incidente queda en el hueco entre la barra y la ficha: ahí se toca su punto.
        const barra = await page.locator("header").boundingBox();
        const hoja = await ficha.boundingBox();
        if (barra === null || hoja === null) throw new Error("sin medidas");
        const punto = { x: viewport.width / 2, y: (barra.y + barra.height + hoja.y) / 2 };
        await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
        await expect(ficha).toBeHidden();
        await page.touchscreen.tap(punto.x, punto.y);
        const pila = page.getByRole("complementary", { name: /incidentes en este (mismo )?punto/ });
        await expect(pila).toBeVisible();
        const elemento = pila.getByRole("listitem").first();
        const caja = await elemento.boundingBox();
        const cajaHoja = await pila.boundingBox();
        if (caja === null || cajaHoja === null) throw new Error("sin medidas");
        // El primer elemento, entero y a la vista, sin nada encima.
        expect(caja.y).toBeGreaterThanOrEqual(cajaHoja.y);
        expect(caja.y + caja.height).toBeLessThanOrEqual(cajaHoja.y + cajaHoja.height);
        const encima = await page.evaluate(
          ({ x, y }) => document.elementFromPoint(x, y)?.closest("li")?.textContent ?? null,
          { x: caja.x + caja.width / 2, y: caja.y + caja.height / 2 },
        );
        expect(encima).toBe(await elemento.textContent());
        expect(await pila.evaluate((e) => getComputedStyle(e).backgroundColor)).toMatch(/^rgb\(/);
        await capturar(page, `${nombre}-pila`);

        // La línea de tiempo en su hoja: al abrirla se cierra la anterior.
        await page.goto("/");
        await page.waitForSelector(MAPA_LISTO);
        await page.getByRole("button", { name: /^Periodo/ }).filter({ visible: true }).click();
        const tiempo = page.getByRole("complementary", { name: "Línea de tiempo" });
        await expect(tiempo).toBeVisible();
        await tiempo.getByRole("radio", { name: "Mes" }).click();
        await tiempo.getByRole("slider", { name: "Fin del periodo" }).focus();
        await page.keyboard.press("ArrowLeft");
        await expect(tiempo.getByRole("button", { name: "Ver todo" })).toBeVisible();
        for (const control of ["Reproducir", "Día", "Semana", "Mes", "Ver todo"]) {
          const caja = await tiempo.getByRole(control === "Reproducir" || control === "Ver todo" ? "button" : "radio", { name: control }).boundingBox();
          expect(caja?.height ?? 0, control).toBeGreaterThanOrEqual(LADO_TACTIL_MINIMO - 0.5);
        }
        await capturar(page, `${nombre}-tiempo`);
        expect(await objetivosPequenos(page)).toEqual([]);
        await tiempo.getByRole("button", { name: "Ver todo" }).click();
        await expect(page).toHaveURL(/\/$/);
      });
    });
  }
}
