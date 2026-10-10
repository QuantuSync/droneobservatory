// «Previsión» se recupera sola de un fallo pasajero de su fichero: la web reintenta, con espera
// creciente, antes de enseñar ningún error (src/datos/reintentos.ts). Si aun así no llega, dice
// qué pasa y ofrece «Reintentar», que la trae en cuanto vuelve a responder. En el teléfono (390 px)
// y en escritorio. Va contra producción por defecto; con BASE=http://localhost:…, contra el
// servidor local.
import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

const MAPA = "[data-mapa-listo=true]";
const PREVISION_WEB = "**/datos/prevision.json";
// La copia del almacén se pide por la propia web (/almacen/…, api/almacen.ts) desde el #193; en
// local (VITE_ALMACEN), directamente al almacén.
const PREVISION_ALMACEN = /(\/almacen|your-objectstorage\.com)\/publicacion\/prevision\.json/;
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
  test.describe(`previsión con fallos pasajeros en ${tamano.nombre}`, () => {
    test.afterEach(async ({ context }) => {
      await context.unrouteAll({ behavior: "ignoreErrors" });
    });
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    test("dos fallos seguidos del fichero no se ven: se recupera sola", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      let pedidas = 0;
      // Primero un error del servidor, luego la conexión cortada; a la tercera, el fichero de verdad.
      await page.route(PREVISION_WEB, async (ruta) => {
        pedidas += 1;
        if (pedidas === 1) await ruta.fulfill({ status: 503, body: "" });
        else if (pedidas === 2) await ruta.abort("connectionreset");
        else await ruta.continue();
      });
      await page.goto("/");
      await page.locator(MAPA).waitFor();
      await abrirPrevision(page, tamano.movil);
      await expect(page.locator("[data-prevision]")).toBeVisible({ timeout: 20_000 });
      await expect(page.locator("[data-prevision]")).toContainText(/de cada 10 noches como esta/);
      await expect(page.locator("[data-error-carga]")).toHaveCount(0);
      await expect(page.locator("[data-prevision-anterior]")).toHaveCount(0);
      expect(pedidas).toBe(3);
    });

    test("si no responde nunca, lo dice y «Reintentar» la trae cuando vuelve", async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      let caido = true;
      const fallar = async (ruta: Parameters<Parameters<Page["route"]>[1]>[0]) => {
        if (caido) await ruta.abort("internetdisconnected");
        else await ruta.fallback();
      };
      await page.route(PREVISION_WEB, fallar);
      await page.route(PREVISION_ALMACEN, fallar);
      await page.goto("/");
      await page.locator(MAPA).waitFor();
      await abrirPrevision(page, tamano.movil);
      const error = page.locator("[data-error-carga]");
      await expect(error).toBeVisible({ timeout: 40_000 });
      await expect(error).toContainText("No se ha podido cargar la previsión.");
      await expect(error).toContainText("Comprueba la conexión");
      caido = false;
      await error.getByRole("button", { name: "Reintentar" }).click();
      await expect(page.locator("[data-prevision]")).toContainText(/de cada 10 noches como esta/, { timeout: 20_000 });
      await expect(page.locator("[data-error-carga]")).toHaveCount(0);
    });
  });
}
