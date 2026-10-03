// «Europa en directo» en un navegador real: panel «Europa ahora», avisos de cierre, capa de
// interferencia GPS y capa de presión por país, en escritorio y en tres teléfonos. Las
// peticiones al almacén público (directo.json y la interferencia) se sirven con ficheros de
// prueba, así que la prueba no depende de lo que haya publicado en ese momento.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { aviso, directo, ficheroGnss, indiceGnss } from "../tests/ejemplos-europa.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "data", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const MS_DE_ASENTAMIENTO = 2500;
const TELEFONOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "390x844", width: 390, height: 844 },
  { nombre: "412x915", width: 412, height: 915 },
];

/** Día de hoy (UTC) como AAAA-MM-DD: el fichero de interferencia de prueba es el de hoy. */
function hoy(): string {
  return new Date().toISOString().slice(0, 10);
}

async function servirAlmacen(pagina: Page) {
  const avisos = [
    aviso(),
    aviso({
      id: "EBBR-hoy",
      oaci: "EBBR",
      nombre: "Brussels",
      pais: "BE",
      lat: 50.901,
      lon: 4.484,
      estado: "cierre_confirmado",
      confirmacion: { tipo: "oficial", incidente: null, hora: "2025-11-04T19:20Z" },
      primera_noticia: "2025-11-04T19:12Z",
      ventaja_min: 17,
    }),
  ];
  const json = (cuerpo: unknown) => ({
    status: 200,
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify(cuerpo),
  });
  // Las direcciones del almacén salen de configuracion/almacen_publico.json; aquí basta su final.
  await pagina.route("**/directo.json", (ruta) => ruta.fulfill(json(directo(avisos))));
  await pagina.route("**/gnss/indice.json", (ruta) => ruta.fulfill(json(indiceGnss([hoy()]))));
  await pagina.route("**/gnss/dia/*.json", (ruta) => ruta.fulfill(json(ficheroGnss(hoy()))));
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await pagina.screenshot({ path: join(CAPTURAS, `europa-${nombre}.png`) });
}

test.describe("escritorio", () => {
  test.skip(({ isMobile }) => isMobile, "solo escritorio");

  test("panel, aviso en directo, interferencia GPS y presión por país", async ({ page }) => {
    const errores: string[] = [];
    page.on("pageerror", (error) => errores.push(error.message));
    await servirAlmacen(page);
    await page.goto("/");
    await page.waitForSelector(MAPA_LISTO);
    // Al entrar está cerrado; el botón avisa con el número de cierres en curso.
    await expect(page.locator("[data-europa-ahora]")).toHaveCount(0);
    const boton = page.getByRole("button", { name: /^Europa ahora/ });
    await expect(boton.locator("[data-indicador=numero]")).toHaveText("2");
    await boton.click();
    const panel = page.getByRole("dialog", { name: "Europa ahora" });
    const cierres = panel.locator('[data-cifra="cierres"]');
    await expect(cierres).toContainText("2");
    await capturar(page, "escritorio-panel");

    await cierres.click();
    const ficha = page.getByRole("complementary", { name: /EBBR/ });
    await expect(ficha).toContainText("Cierre confirmado");
    await expect(ficha).toContainText("17 min antes de la primera noticia");
    await capturar(page, "escritorio-aviso");
    await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();

    await boton.click();
    await page.getByRole("dialog", { name: "Europa ahora" }).locator('[data-cifra="gnss"]').click();
    await expect(page.getByRole("button", { name: "GPS", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('[data-leyenda="gnss"]')).toContainText("1 día con datos");
    await capturar(page, "escritorio-gnss");

    await page.getByRole("button", { name: "GPS", exact: true }).click();
    await page.getByRole("button", { name: "Presión", exact: true }).click();
    await expect(page.locator('[data-leyenda="presion"]')).toBeVisible();
    await page.getByRole("button", { name: "Ver todo" }).click().catch(() => undefined);
    await capturar(page, "escritorio-presion");
    expect(errores).toEqual([]);
  });
});

test.describe("teléfono", () => {
  test.skip(({ isMobile }) => !isMobile, "solo teléfono");

  for (const tamano of TELEFONOS) {
    test(`${tamano.nombre}: «Europa ahora» se abre en una hoja y lleva a la ficha`, async ({ page }) => {
      await page.setViewportSize({ width: tamano.width, height: tamano.height });
      await servirAlmacen(page);
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO);
      const boton = page.getByRole("button", { name: /^Europa ahora/ }).filter({ visible: true });
      await expect(boton.locator("[data-indicador=numero]")).toHaveText("2");
      await boton.click();
      const panel = page.getByRole("complementary", { name: "Europa ahora" });
      await expect(panel.locator('[data-cifra="cierres"]')).toContainText("2");
      await capturar(page, `${tamano.nombre}-panel`);
      await panel.locator('[data-cifra="cierres"]').click();
      const hoja = page.getByRole("complementary", { name: /EBBR/ });
      await expect(hoja).toContainText("Cierre confirmado");
      // Pulsar una cifra cierra «Europa ahora» y abre la ficha; con una hoja abierta, los
      // botones sobre el mapa no se pintan, así que nada tapa la hoja.
      await expect(panel).toBeHidden();
      await expect(page.locator("[data-botones-mapa]:visible")).toHaveCount(0);
      await capturar(page, `${tamano.nombre}-aviso`);
    });
  }
});

test.describe("pulso de las novedades", () => {
  test("solo laten las novedades desde la última visita y se apagan al descartarlas", async ({ page }) => {
    // Primera visita: no hay visita anterior y no late nada.
    await page.goto("/");
    await page.waitForSelector(MAPA_LISTO);
    await page.waitForTimeout(MS_DE_ASENTAMIENTO);
    await expect(page.locator(".pulso")).toHaveCount(0);

    // Con una visita anterior de hace un mes, laten las novedades (y solo ellas).
    await page.evaluate(() => {
      const hace = new Date(Date.now() - 30 * 86400 * 1000).toISOString();
      window.localStorage.setItem("eodi.ultima-visita", hace);
    });
    await page.reload();
    await page.waitForSelector(MAPA_LISTO);
    await page.waitForTimeout(MS_DE_ASENTAMIENTO);
    const aviso = page.getByRole("status").filter({ hasText: /novedad/ });
    await expect(aviso).toBeVisible();
    expect(await page.locator(".pulso").count()).toBeGreaterThan(0);
    await aviso.getByRole("button", { name: "Descartar" }).click();
    await expect(page.locator(".pulso")).toHaveCount(0);
  });
});
