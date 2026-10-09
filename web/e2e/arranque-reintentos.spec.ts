// La web arranca aunque su código no llegue a la primera (public/arranque.js). Pasa unos segundos
// tras cada publicación: el despliegue nuevo sirve ya la página y la petición de su código llega
// aún al anterior, que responde 404. La página se recarga, con espera creciente; si no llega
// nunca, lo dice, con «Reintentar». También el código del mapa, que se pide aparte. En el teléfono (390 px) y en escritorio. Va contra producción por defecto; con
// BASE=http://localhost:…, contra el servidor local. Deja la captura del aviso en CAPTURAS (por
// defecto, fuera del repositorio).
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page, Route } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "..", "eodi-rl-cap");
const MAPA = "[data-mapa-listo=true]";
const CODIGO = /\/assets\/app-[^/]+\.js(\?.*)?$/;
const CODIGO_MAPA = /\/assets\/Mapa-[^/]+\.js(\?.*)?$/;
const TAMANOS = [
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "escritorio", width: 1440, height: 900, movil: false },
];

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    try {
      const respuesta = await ruta.fetch();
      await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
    } catch {
      // La prueba ya ha terminado: la petición en vuelo no importa.
    }
  });
}

async function abrirPrevision(pagina: Page, movil: boolean) {
  if (movil) {
    await pagina.locator("[data-botones-mapa] [data-boton-ahora]").first().click();
    await pagina.locator("[data-pestana=prevision]").click();
  } else {
    await pagina.locator("[data-botones-mapa] [data-boton-prevision]").first().click();
  }
}

for (const tamano of TAMANOS) {
  test.describe(`arranque con fallos pasajeros en ${tamano.nombre}`, () => {
    test.afterEach(async ({ context }) => {
      await context.unrouteAll({ behavior: "ignoreErrors" });
    });
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    test("el código de la página y el del mapa llegan tarde: arranca sola y abre «Previsión»", async ({
      page,
      context,
      baseURL,
    }) => {
      await preparar(context, baseURL);
      let codigo = 0;
      let codigoMapa = 0;
      // Un 404 (lo que da el despliegue anterior) y luego la conexión cortada; a la tercera, el fichero.
      await page.route(CODIGO, async (ruta) => {
        codigo += 1;
        if (codigo === 1) await ruta.fulfill({ status: 404, body: "" });
        else if (codigo === 2) await ruta.abort("connectionreset");
        else await ruta.continue();
      });
      await page.route(CODIGO_MAPA, async (ruta) => {
        codigoMapa += 1;
        if (codigoMapa === 1) await ruta.fulfill({ status: 404, body: "" });
        else await ruta.continue();
      });
      await page.goto("/");
      await page.locator(MAPA).waitFor({ timeout: 40_000 });
      // Tres recargas: dos por el código de la página y una por el del mapa.
      expect(codigo).toBe(4);
      expect(codigoMapa).toBe(2);
      await abrirPrevision(page, tamano.movil);
      await expect(page.locator("[data-prevision]")).toContainText(/de cada 10 noches como esta/, { timeout: 20_000 });
      await expect(page.locator("[data-error-carga]")).toHaveCount(0);
    });

    test("si el código no llega nunca, recarga cuatro veces, lo dice y «Reintentar» la trae", async ({
      page,
      context,
      baseURL,
    }) => {
      await preparar(context, baseURL);
      let caido = true;
      let cargas = 0;
      // Las peticiones de la página, no sus «load»: una recarga puede llegar antes de que termine.
      page.on("request", (peticion) => {
        if (peticion.isNavigationRequest() && peticion.frame() === page.mainFrame()) cargas += 1;
      });
      await page.route(CODIGO, async (ruta: Route) => {
        if (caido) await ruta.fulfill({ status: 404, body: "" });
        else await ruta.fallback();
      });
      await page.goto("/");
      const aviso = page.locator(".aviso-arranque");
      await expect(aviso).toBeVisible({ timeout: 40_000 });
      await expect(aviso).toContainText("No se ha podido cargar la web.");
      expect(cargas).toBe(5);
      await page.screenshot({ path: join(CAPTURAS, `arranque-aviso-${tamano.nombre}.png`) });
      caido = false;
      await aviso.getByRole("button", { name: "Reintentar" }).click();
      await page.locator(MAPA).waitFor({ timeout: 40_000 });
      await expect(page.locator(".aviso-arranque")).toHaveCount(0);
    });
  });
}
