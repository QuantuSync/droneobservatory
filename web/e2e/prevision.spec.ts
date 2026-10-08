// «Previsión», el filtro frontera/interior y los arreglos del mismo paquete, en el teléfono (360,
// 390 y 412 px de ancho) y en escritorio. En el teléfono «Previsión» es una pestaña de «Europa
// ahora»; en escritorio, un botón propio. Abrir y cerrar no mueve el mapa; tocar una racha lleva
// el mapa al país con el periodo de la racha en los filtros. Deja capturas en docs/capturas
// (CAPTURAS para otra carpeta). Va contra producción por defecto; con BASE=http://localhost:…,
// contra el servidor local.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas");
const MAPA = "[data-mapa-listo=true]";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, movil: true },
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "412x915", width: 412, height: 915, movil: true },
  { nombre: "escritorio", width: 1440, height: 900, movil: false },
];

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com|tiles\.droneobservatory\.eu/, async (ruta) => {
    try {
      const respuesta = await ruta.fetch();
      await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
    } catch {
      // La prueba ya ha terminado o ha cambiado de página: la petición en vuelo no importa.
    }
  });
}

async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  let anterior = "";
  for (let i = 0; i < 30; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior && !ahora.includes("null")) return ahora;
    anterior = ahora;
  }
  return anterior;
}

async function abrirPrevision(pagina: Page, movil: boolean) {
  if (movil) {
    await pagina.locator("[data-botones-mapa] [data-boton-ahora]").first().click();
    await pagina.locator("[data-pestana=prevision]").click();
  } else {
    await pagina.locator("[data-botones-mapa] [data-boton-prevision]").first().click();
  }
  await expect(pagina.locator("[data-prevision]")).toBeVisible();
}

for (const tamano of TAMANOS) {
  test.describe(`previsión en ${tamano.nombre}`, () => {
    // Las teselas se piden al almacén de verdad: una petición aún en vuelo al terminar la prueba
    // no es un fallo de la web (así fallaron sin motivo dos ejecuciones del 6 de octubre de 2026).
    test.afterEach(async ({ context }) => {
      await context.unrouteAll({ behavior: "ignoreErrors" });
    });
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    test("se abre, enseña lo comprobado y se cierra sin mover el mapa", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/?ultimos=7d");
      await page.locator(MAPA).waitFor();
      const antes = await vista(page);
      // Los botones sobre el mapa caben en una fila y no se pisan.
      const cajas = await page.locator("[data-botones-mapa]:visible > *").evaluateAll((elementos) =>
        elementos.map((e) => e.getBoundingClientRect()).map((r) => ({ top: Math.round(r.top), right: r.right })),
      );
      expect(new Set(cajas.map((c) => c.top)).size).toBe(1);
      for (const caja of cajas) expect(caja.right).toBeLessThanOrEqual(tamano.width);
      await abrirPrevision(page, tamano.movil);
      const texto = (await page.locator("[data-prevision]").textContent()) ?? "";
      expect(texto).toMatch(/de cada 10 noches como esta \(\d+ %\)/);
      expect(texto).toContain("Comprobado con");
      await page.screenshot({ path: join(CAPTURAS, `prevision-${tamano.nombre}.png`) });
      await page.keyboard.press("Escape");
      // En el teléfono la hoja se cierra con Escape o con su equis.
      if ((await page.locator("[data-prevision]").count()) > 0) {
        await page.locator("[data-hoja-propia] button[aria-label]").first().click();
      }
      await expect(page.locator("[data-prevision]")).toHaveCount(0);
      expect(await vista(page)).toBe(antes);
    });

    test("tocar una racha lleva al país con el periodo de la racha", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/");
      await page.locator(MAPA).waitFor();
      await abrirPrevision(page, tamano.movil);
      const racha = page.locator("[data-racha]").first();
      if ((await racha.count()) === 0) test.skip(true, "hoy ningún país está en racha");
      const pais = await racha.getAttribute("data-racha");
      await racha.click();
      await expect(page).toHaveURL(new RegExp(`pais=${pais ?? ""}.*desde=\\d{4}-\\d{2}-\\d{2}&hasta=`));
      await expect(page.locator("[data-prevision]")).toHaveCount(0);
      await page.waitForTimeout(1500);
      await page.screenshot({ path: join(CAPTURAS, `prevision-racha-${tamano.nombre}.png`) });
    });

    test("frontera o interior en los filtros, y la cabecera cuadra", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/?estado=atribuido");
      await page.locator(MAPA).waitFor();
      // Con el filtro de atribuidos, los confirmados los incluyen.
      const confirmados = Number((await page.locator("[data-contador=confirmados]").first().getAttribute("data-valor")) ?? "-1");
      const atribuidos = Number((await page.locator("[data-contador=atribuidos]").first().getAttribute("data-valor")) ?? "-1");
      expect(confirmados).toBe(atribuidos);
      await page.goto("/?zona=frontera");
      await page.locator(MAPA).waitFor();
      await page.locator("[data-botones-mapa] [data-boton-filtros] button").first().click();
      await expect(page.getByRole("button", { name: "Frontera", exact: true })).toHaveAttribute("aria-pressed", "true");
      await page.screenshot({ path: join(CAPTURAS, `frontera-filtro-${tamano.nombre}.png`) });
    });

    test("corredores con «Todo» y la leyenda de Presión sin periodo", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await page.goto("/?guerra=corredores");
      await page.locator(MAPA).waitFor();
      await page.waitForTimeout(2000);
      const leyenda = page.locator("[data-leyenda=corredores]");
      if ((await leyenda.count()) > 0) {
        await expect(leyenda).toContainText(/corredores, los de más drones|corridors, those with the most drones/);
      }
      await page.screenshot({ path: join(CAPTURAS, `corredores-todo-${tamano.nombre}.png`) });
    });
  });
}

test("la página de texto de la previsión se lee sin ejecutar código", async ({ request }) => {
  for (const ruta of ["/prevision", "/en/forecast"]) {
    const respuesta = await request.get(ruta);
    expect(respuesta.status()).toBe(200);
    const html = await respuesta.text();
    expect(html).toMatch(/<h1>(Previsión y tendencias|Forecast and trends)<\/h1>/);
    expect(html).toMatch(/de cada 10 noches como esta|in 10 nights like this one/);
  }
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap).toContain("/prevision");
  expect(sitemap).toContain("/en/forecast");
  const llms = await (await request.get("/llms.txt")).text();
  expect(llms).toContain("/en/forecast");
});
