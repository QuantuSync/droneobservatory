// Las páginas se leen y se recorren sin ejecutar código, y con el código activo la web es la de
// siempre: el texto no se pinta nunca, ni siquiera antes de que llegue la aplicación.

import { expect, test } from "@playwright/test";

import { ORIGEN_ALMACEN } from "../src/almacenPublico.ts";
import { NOMBRE } from "../src/sitio.ts";

const MAPA_LISTO = "[data-mapa-listo=true]";
const TEXTO = ".texto-pagina";

test.describe("sin ejecutar código", () => {
  test.use({ javaScriptEnabled: false });

  test("de la portada a un incidente y vuelta, con enlaces normales", async ({ page }) => {
    const respuesta = await page.goto("/");
    expect(respuesta?.status()).toBe(200);
    await expect(page.locator("#root")).toBeHidden();
    await expect(page.locator(`${TEXTO} h1`)).toHaveText(NOMBRE);
    await expect(page.locator("[data-cifra=incidentes]")).toBeVisible();

    // El primero de los últimos incidentes.
    const enlace = page.locator(`${TEXTO} main ul.texto-lista a`).first();
    const titular = (await enlace.textContent()) ?? "";
    await enlace.click();
    await expect(page).toHaveURL(/\/EODI-\d{4}-\d{5}$/);
    await expect(page.locator(`${TEXTO} [data-titular]`)).toHaveText(titular);
    await expect(page.locator(`${TEXTO} [data-estado]`)).toBeVisible();
    await expect(page.locator(`${TEXTO} [data-datos-de]`)).toBeVisible();

    // A la lista completa y de vuelta a la portada por la navegación.
    await page.locator(`${TEXTO} main a`, { hasText: "Todos los incidentes" }).click();
    await expect(page).toHaveURL(/\/incidentes$/);
    await page.goBack();
    await expect(page.locator(`${TEXTO} [data-titular]`)).toHaveText(titular);
    await page.locator(`${TEXTO} header nav a`, { hasText: "Mapa" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator(`${TEXTO} h1`)).toHaveText(NOMBRE);

    // La versión inglesa.
    await page.locator(`${TEXTO} a[hreflang=en]`).click();
    await expect(page).toHaveURL(/\/en$/);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  });

  test("una dirección que no existe da 404", async ({ page }) => {
    const respuesta = await page.goto("/EODI-2099-99999");
    expect(respuesta?.status()).toBe(404);
    await expect(page.locator(`${TEXTO} h1`)).toBeVisible();
  });
});

test.describe("con el código activo", () => {
  test("el texto no se pinta ni antes de que llegue la aplicación", async ({ page }) => {
    // Sin scripts que lleguen: lo que se ve es lo que pinta el HTML con su hoja de estilos.
    await page.route(/\.js($|\?)/, (ruta) => ruta.abort());
    for (const ruta of ["/", "/en"]) {
      await page.goto(ruta);
      await expect(page.locator(TEXTO)).toBeHidden();
      await expect(page.locator("#root")).toBeVisible();
    }
  });

  test("con la aplicación cargada, el mapa y nada más", async ({ page, baseURL }) => {
    if (baseURL?.includes("localhost") === true) {
      await page.route(`${ORIGEN_ALMACEN}/**`, (ruta) =>
        ruta.fulfill({ status: 404, headers: { "access-control-allow-origin": "*" }, body: "" }),
      );
    }
    await page.goto("/");
    await expect(page.locator(MAPA_LISTO)).toBeAttached({ timeout: 60_000 });
    await expect(page.locator(TEXTO)).toBeHidden();
    const alto = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
    expect(alto).toBeLessThanOrEqual(0);
  });
});
