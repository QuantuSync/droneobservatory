// La ventana de los avisos del observatorio (public/anuncio.js) como la usa una persona, en
// Android, iPhone, tableta y escritorio (Chromium y WebKit): sale en el mapa y en las páginas de
// texto en su idioma, su enlace lleva al aviso completo con su ancla, se cierra con el botón (con un
// toque en el teléfono) y con Escape, cerrada no vuelve, no impide usar el mapa y no choca con la
// política de seguridad. Los datos de la ventana se sirven aquí con fechas alrededor de ahora (los
// textos y el enlace son los de public/anuncios.json): la prueba no caduca con el aviso real. El
// resto de recorridos la llevan apagada (e2e/base.ts).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { Page, TestInfo } from "@playwright/test";

import { expect, test } from "./base.ts";

test.use({ anuncios: true, serviceWorkers: "block" });

interface Anuncio {
  id: string;
  ventana: { desde: string; hasta: string; texto: Record<"es" | "en", string>; enlace: { texto: Record<"es" | "en", string>; ruta: Record<"es" | "en", string> } };
}

const DATOS = JSON.parse(
  readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "public", "anuncios.json"), "utf-8"),
) as { anuncios: Anuncio[] };
const REAL = DATOS.anuncios[0];
if (REAL?.ventana === undefined) throw new Error("public/anuncios.json sin aviso con ventana");
const AVISO: Anuncio = REAL;
const VENTANA = "[data-anuncio]";
const MAPA_LISTO = "[data-mapa-listo=true]";

/** Sirve los datos de los avisos con la ventana vigente (o ya caducada). */
async function servirAvisos(page: Page, caducado = false): Promise<void> {
  const ahora = Date.now();
  const hora = 3_600_000;
  const anuncio = {
    ...AVISO,
    ventana: {
      ...AVISO.ventana,
      desde: new Date(ahora - 2 * hora).toISOString(),
      hasta: new Date(caducado ? ahora - hora : ahora + hora).toISOString(),
    },
  };
  await page.route("**/anuncios.json", (ruta) =>
    ruta.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ anuncios: [anuncio] }) }),
  );
}

/** Los avisos de la política de seguridad que da la página. */
function vigilarPolitica(page: Page): string[] {
  const avisos: string[] = [];
  page.on("console", (m) => {
    if (/Content[- ]Security[- ]Policy|Refused to (apply|execute|load)/i.test(m.text())) avisos.push(m.text());
  });
  return avisos;
}

const tactil = (info: TestInfo): boolean => info.project.use.hasTouch === true;

test("en el mapa sale en español, no impide usarlo y, cerrada con el botón, no vuelve", async ({ page }, info) => {
  const politica = vigilarPolitica(page);
  await servirAvisos(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  const ventana = page.locator(VENTANA);
  await expect(ventana).toBeVisible();
  await expect(ventana).toHaveAttribute("aria-label", "Aviso del observatorio");
  await expect(ventana.locator("p")).toHaveText(AVISO.ventana.texto.es);
  const enlace = ventana.getByRole("link", { name: AVISO.ventana.enlace.texto.es, exact: true });
  await expect(enlace).toHaveAttribute("href", AVISO.ventana.enlace.ruta.es);

  // Dentro de la pantalla y ocupando poco: el mapa sigue a la vista y se usa.
  const caja = await ventana.boundingBox();
  const pantalla = page.viewportSize();
  expect(caja).not.toBeNull();
  expect(pantalla).not.toBeNull();
  if (caja !== null && pantalla !== null) {
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(pantalla.width);
    expect(caja.y + caja.height).toBeLessThanOrEqual(pantalla.height);
    expect(caja.height).toBeLessThan(pantalla.height * 0.3);
  }
  // No tapa los botones del mapa ni su centro: lo que hay ahí sigue recibiendo el toque.
  const botones = page.getByRole("button", { name: /^Abrir los filtros/ }).filter({ visible: true });
  const boton = await botones.first().boundingBox();
  if (caja !== null && boton !== null) {
    const separados =
      boton.x + boton.width <= caja.x || caja.x + caja.width <= boton.x || boton.y + boton.height <= caja.y || caja.y + caja.height <= boton.y;
    expect(separados).toBe(true);
  }
  const enElCentro = await page.evaluate(() => {
    const el = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2);
    return el !== null && el.closest("[data-anuncio]") === null;
  });
  expect(enElCentro).toBe(true);

  // Cerrar no mueve el mapa: la dirección no cambia.
  const direccion = page.url();
  const cerrar = ventana.getByRole("button", { name: "Cerrar el aviso" });
  await expect(cerrar).toBeVisible();
  if (tactil(info)) await cerrar.tap();
  else await cerrar.click();
  await expect(ventana).toHaveCount(0);
  expect(page.url()).toBe(direccion);

  await page.reload();
  await page.waitForSelector(MAPA_LISTO);
  await page.waitForTimeout(500);
  await expect(page.locator(VENTANA)).toHaveCount(0);
  expect(politica).toEqual([]);
});

test("en inglés sale en inglés y se cierra con Escape", async ({ page }) => {
  test.skip(test.info().project.use.hasTouch === true, "Escape es del teclado: en el teléfono se cierra con el botón");
  await servirAvisos(page);
  await page.goto("/en");
  await page.waitForSelector(MAPA_LISTO);
  const ventana = page.locator(VENTANA);
  await expect(ventana.locator("p")).toHaveText(AVISO.ventana.texto.en);
  await expect(ventana.getByRole("link", { name: AVISO.ventana.enlace.texto.en, exact: true })).toHaveAttribute(
    "href",
    AVISO.ventana.enlace.ruta.en,
  );
  // Con el teclado: es lo primero de la página; Escape la cierra.
  await ventana.getByRole("button", { name: "Close the notice" }).focus();
  await page.keyboard.press("Escape");
  await expect(ventana).toHaveCount(0);
  await page.goto("/en/methodology");
  await page.waitForTimeout(500);
  await expect(page.locator(VENTANA)).toHaveCount(0);
});

test("en una página de texto, el enlace lleva al aviso completo en «Avisos»", async ({ page }, info) => {
  const politica = vigilarPolitica(page);
  await servirAvisos(page);
  await page.goto("/metodologia");
  const ventana = page.locator(VENTANA);
  await expect(ventana).toBeVisible();
  const enlace = ventana.getByRole("link", { name: AVISO.ventana.enlace.texto.es, exact: true });
  if (tactil(info)) await enlace.tap();
  else await enlace.click();
  await expect(page).toHaveURL(new RegExp(`${AVISO.ventana.enlace.ruta.es}$`));
  const articulo = page.locator(`article#${AVISO.id}`);
  await expect(articulo).toBeVisible();
  await expect(articulo).toBeInViewport();
  expect(politica).toEqual([]);

  await page.goto("/en/alerts");
  await expect(page.locator(`article#${AVISO.id}`)).toBeVisible();
});

test("caducada, no sale", async ({ page }) => {
  await servirAvisos(page, true);
  await page.goto("/ayuda");
  await page.waitForTimeout(800);
  await expect(page.locator(VENTANA)).toHaveCount(0);
});
