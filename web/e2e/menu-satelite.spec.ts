// «Con satélite» en el menú del teléfono y en el desplegable del escritorio: con la capa de
// Ucrania y «Con satélite» encendidos y la leyenda desplegada, la leyenda ocupa al menos el 80 %
// del ancho de su contenedor (el menú o el desplegable) y ningún botón ocupa más de una línea.
// Deja capturas de cada tamaño.

import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

const CAPTURAS = join(import.meta.dirname, "..", "..", "data", "capturas", "telefono");
const MAPA_LISTO = "[data-mapa-listo=true]";
const PARTE_MINIMA_DE_LA_LEYENDA = 0.8;
const TAMANOS = [
  { ancho: 360, alto: 800 },
  { ancho: 390, alto: 844 },
  { ancho: 412, alto: 915 },
];

/**
 * Botones visibles dentro de `zona` cuyo texto ocupa más de una línea. Las filas de la lista de
 * puntos quedan fuera: llevan a propósito el lugar en una línea y la fecha y el tipo en otra.
 */
async function botonesEnVariasLineas(zona: Locator): Promise<string[]> {
  return zona.evaluate((raiz) =>
    [...raiz.querySelectorAll<HTMLElement>("button")]
      .filter((boton) => boton.getClientRects().length > 0 && boton.closest("[data-lista-satelite]") === null)
      .filter((boton) => {
        const lineas = new Set<number>();
        const recorrido = document.createTreeWalker(boton, NodeFilter.SHOW_TEXT);
        for (let nodo = recorrido.nextNode(); nodo !== null; nodo = recorrido.nextNode()) {
          if ((nodo.textContent ?? "").trim() === "") continue;
          const rango = document.createRange();
          rango.selectNodeContents(nodo);
          for (const caja of rango.getClientRects()) {
            if (caja.width > 0) lineas.add(Math.round(caja.top + caja.height / 2));
          }
        }
        // Dos trozos de texto en la misma línea pueden diferir en un píxel de centro.
        const centros = [...lineas].sort((a, b) => a - b);
        return centros.some((c, i) => i > 0 && c - (centros[i - 1] ?? c) > 4);
      })
      .map((boton) => (boton.textContent ?? "").trim()),
  );
}

/** Ancho de la leyenda entre el ancho de su contenedor. */
async function parteDeLaLeyenda(leyenda: Locator, contenedor: Locator): Promise<number> {
  const caja = await leyenda.boundingBox();
  const total = await contenedor.boundingBox();
  if (caja === null || total === null) throw new Error("sin medidas");
  return caja.width / total.width;
}

async function capturar(pagina: Page, nombre: string) {
  await mkdir(CAPTURAS, { recursive: true });
  await pagina.screenshot({ path: join(CAPTURAS, `${nombre}.png`) });
}

for (const { ancho, alto } of TAMANOS) {
  test.describe(`${ancho}x${alto}`, () => {
    test.use({ viewport: { width: ancho, height: alto }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });

    test(`${ancho}x${alto}: menú con «Con satélite» y su leyenda a todo el ancho`, async ({ page }, info) => {
      test.skip(info.project.name !== "movil", "la versión de teléfono se comprueba una sola vez");
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO);
      await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
      const menu = page.getByRole("dialog", { name: "Menú" });
      await menu.getByRole("button", { name: "Ucrania", exact: true }).click();
      const bloque = menu.locator("[data-bloque-guerra]");
      await expect(bloque.getByText("Capa de Ucrania")).toBeVisible();
      const corredores = bloque.getByRole("button", { name: "Corredores", exact: true });
      const satelite = bloque.getByRole("button", { name: /^Con satélite · \d+$/ });
      await expect(corredores).toHaveAttribute("aria-pressed", "false");
      await expect(satelite).toHaveAttribute("aria-pressed", "false");
      // Los dos botones de la capa, uno al lado del otro y del mismo alto que los de las capas.
      const [a, b, capa] = await Promise.all([
        corredores.boundingBox(),
        satelite.boundingBox(),
        menu.getByRole("button", { name: "Ucrania", exact: true }).boundingBox(),
      ]);
      if (a === null || b === null || capa === null) throw new Error("sin medidas");
      expect(Math.abs(a.y - b.y)).toBeLessThan(1);
      expect(Math.abs(a.height - capa.height)).toBeLessThan(1);

      await satelite.click();
      await expect(satelite).toHaveAttribute("aria-pressed", "true");
      const panel = menu.locator("[data-panel-satelite]");
      await expect(panel.locator("[data-leyenda-satelite]")).toHaveCount(0);
      await panel.getByRole("button", { name: /^Leyenda/ }).click();
      const leyenda = panel.locator("[data-leyenda-satelite]");
      await expect(leyenda).toBeVisible();
      await expect(leyenda.getByRole("listitem")).toHaveCount(4);

      const contenido = menu.locator("[data-bloque-guerra]");
      expect(await parteDeLaLeyenda(leyenda, contenido)).toBeGreaterThanOrEqual(PARTE_MINIMA_DE_LA_LEYENDA);
      expect(await botonesEnVariasLineas(menu)).toEqual([]);
      // Cada entrada de la leyenda en una o dos líneas.
      const altos = await leyenda.getByRole("listitem").evaluateAll((filas) =>
        filas.map((fila) => fila.getBoundingClientRect().height / parseFloat(getComputedStyle(fila).lineHeight)),
      );
      for (const lineas of altos) expect(lineas).toBeLessThanOrEqual(2.2);
      await leyenda.scrollIntoViewIfNeeded();
      await capturar(page, `menu-satelite-${ancho}x${alto}`);
    });
  });
}

test("escritorio: el desplegable de «Con satélite» con su leyenda a todo el ancho", async ({ page }, info) => {
  test.skip(info.project.name !== "escritorio", "solo en escritorio");
  await page.goto("/?guerra=satelite");
  await page.waitForSelector(MAPA_LISTO);
  const grupo = page.locator("[data-capas-guerra]");
  await expect(grupo.getByRole("button", { name: "Corredores", exact: true })).toBeVisible();
  const desplegable = page.locator("[data-con-satelite] [data-panel-satelite]");
  // El enlace enciende «Con satélite»; su flecha abre el desplegable.
  const flecha = page.locator("[data-con-satelite] button[aria-expanded]");
  await expect(flecha).toBeVisible();
  if ((await flecha.getAttribute("aria-expanded")) !== "true") await flecha.click();
  await expect(desplegable).toBeVisible();
  await desplegable.getByRole("button", { name: /^Leyenda/ }).click();
  const leyenda = desplegable.locator("[data-leyenda-satelite]");
  await expect(leyenda).toBeVisible();
  expect(await parteDeLaLeyenda(leyenda, desplegable)).toBeGreaterThanOrEqual(PARTE_MINIMA_DE_LA_LEYENDA);
  expect(await botonesEnVariasLineas(grupo)).toEqual([]);
  await capturar(page, "menu-satelite-escritorio");
});
