// Contador de visitas propio (public/visitas.js, interno: visitas) en un navegador real: la web
// envía la visita en el mapa, en las páginas de texto y al abrir una ficha, nunca por cambiar
// filtros; sin el contador la web funciona igual; fuera de producción y en un navegador excluido
// no envía nada. Cada envío se intercepta: ninguna prueba llega al contador de verdad.

import { expect, test } from "./base.ts";
import type { Page } from "@playwright/test";

const CONTADOR = "https://stats.droneobservatory.eu/count**";
const MAPA_LISTO = "[data-mapa-listo=true]";

/** Las visitas que la página envía al contador, con sus parámetros. */
async function interceptar(page: Page, responder: "si" | "caido" = "si"): Promise<URLSearchParams[]> {
  const enviadas: URLSearchParams[] = [];
  await page.route(CONTADOR, async (ruta) => {
    enviadas.push(new URL(ruta.request().url()).searchParams);
    if (responder === "caido") await ruta.abort("connectionrefused");
    else await ruta.fulfill({ status: 200, body: "" });
  });
  return enviadas;
}

/** En local y en las vistas previas no se cuenta: la prueba lo activa con su clave. */
async function contarFueraDeProduccion(page: Page): Promise<void> {
  await page.addInitScript(() => window.localStorage.setItem("eodi.visitas.prueba", "1"));
}

/** El envío número `i`, que la prueba ya ha esperado. */
function envio(enviadas: URLSearchParams[], i: number): URLSearchParams {
  const parametros = enviadas[i];
  if (parametros === undefined) throw new Error(`no llegó el envío ${i}`);
  return parametros;
}

function rutas(enviadas: URLSearchParams[]): string[] {
  return enviadas.map((p) => p.get("p") ?? "");
}

test("el mapa cuenta la portada y cada ficha abierta, no los filtros", async ({ page }, info) => {
  const enviadas = await interceptar(page);
  await contarFueraDeProduccion(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await expect.poll(() => rutas(enviadas)).toEqual(["/"]);
  const primera = envio(enviadas, 0);
  // Lo mismo que envía count.js, sin cookies ni nada que identifique.
  expect(primera.get("t")).toBeTruthy();
  expect(primera.get("s")).toMatch(/^\d+,\d+,[\d.]+$/);
  expect(primera.get("b")).toBe("153"); // un navegador manejado por un programa: GoatCounter lo descarta

  // Cambiar filtros (la búsqueda de la dirección) no cuenta.
  await page.getByRole("button", { name: /^Abrir los filtros/ }).filter({ visible: true }).click();
  const filtros = page.getByRole("group", { name: "Filtros" }).filter({ visible: true });
  await filtros.getByRole("button", { name: "Confirmado" }).click();
  await expect(page).toHaveURL(/\?estado=|\?solo=/);
  const equis = page.getByRole("button", { name: "Cerrar los filtros" }).filter({ visible: true });
  if ((await equis.count()) > 0) await equis.first().click();
  await page.keyboard.press("Escape");
  await page.waitForTimeout(1000);
  expect(rutas(enviadas)).toEqual(["/"]);

  // Abrir una ficha desde «En directo» cuenta su página, con su título y sin los filtros.
  if (info.project.name === "movil") {
    await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
    await page.getByRole("dialog", { name: "Menú" }).getByRole("button", { name: "En directo", exact: true }).click();
  } else {
    await page.getByRole("button", { name: "En directo", exact: true }).click();
  }
  const feed = page.getByRole("complementary", { name: "En directo" });
  await feed.getByRole("listitem").first().getByRole("button").click();
  await expect(page).toHaveURL(/\/EODI-\d{4}-\d{5}\?(estado|solo)=/);
  const id = new URL(page.url()).pathname;
  await expect.poll(() => rutas(enviadas)).toEqual(["/", id]);
  // Con el título de la ficha, no el de la portada.
  expect(envio(enviadas, 1).get("t")).not.toBe(primera.get("t"));
  // La procedencia y las campañas solo van con la primera página de la carga.
  expect(envio(enviadas, 1).get("r")).toBe("");
  expect(envio(enviadas, 1).get("q")).toBe("");
});

test("las páginas de texto cuentan en español y en inglés", async ({ page }) => {
  const enviadas = await interceptar(page);
  await contarFueraDeProduccion(page);
  for (const ruta of ["/metodologia", "/en/methodology", "/privacidad", "/en/privacy", "/incidentes"]) {
    await page.goto(ruta);
    await expect.poll(() => rutas(enviadas).at(-1)).toBe(ruta);
  }
  // La página de privacidad lo explica en una frase.
  await page.goto("/privacidad");
  await expect(page.locator("main")).toContainText("Cuenta las visitas de forma anónima, sin cookies y sin guardar direcciones IP");
  await page.goto("/en/privacy");
  await expect(page.locator("main")).toContainText("It counts visits anonymously, without cookies and without storing IP addresses");
});

test("sin el contador la web funciona igual", async ({ page }) => {
  const errores: string[] = [];
  page.on("pageerror", (error) => errores.push(error.message));
  const enviadas = await interceptar(page, "caido");
  await contarFueraDeProduccion(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await expect.poll(() => enviadas.length).toBe(1);
  await expect(page.getByRole("banner")).toBeVisible();
  await page.goto("/metodologia");
  await expect(page.locator("main h1")).toBeVisible();
  // Con el script del contador bloqueado del todo, tampoco pasa nada.
  await page.route("**/visitas.js", (ruta) => ruta.abort());
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  expect(errores).toEqual([]);
});

test("fuera de producción y en un navegador excluido no se envía nada", async ({ page }) => {
  const enviadas = await interceptar(page);
  await page.goto("/metodologia");
  await expect(page.locator("main h1")).toBeVisible();
  await page.waitForTimeout(500);
  if (new URL(page.url()).hostname !== "droneobservatory.eu") expect(enviadas).toEqual([]);

  // El mecanismo de GoatCounter: #toggle-goatcounter excluye este navegador (y avisa).
  await contarFueraDeProduccion(page);
  page.on("dialog", (dialogo) => void dialogo.accept());
  await page.goto("/ayuda#toggle-goatcounter");
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("skipgc"))).toBe("t");
  const antes = enviadas.length;
  await page.goto("/metodologia");
  await expect(page.locator("main h1")).toBeVisible();
  await page.waitForTimeout(500);
  expect(enviadas).toHaveLength(antes);
});
