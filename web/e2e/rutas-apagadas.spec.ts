// Con las rutas apagadas en la web (configuracion/rutas_en_la_web.json), en 390×844 y en
// escritorio: la capa de Ucrania ofrece «Corredores» y «Con satélite» y no «Rutas», aunque el
// enlace pida ?guerra=rutas; «Noche a noche» funciona sin rutas; no se pide ningún fichero de
// rutas; y la página de texto de Ucrania y la metodología no las mencionan. Con las rutas
// encendidas, se salta. Va contra producción por defecto; deja capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import ajuste from "../../configuracion/rutas_en_la_web.json" with { type: "json" };

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "..", "eodi-ra-cap");
const MAPA = "[data-mapa-listo=true]";
const TAMANOS = [
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "escritorio", width: 1440, height: 900, movil: false },
];

/** Apunta cada petición de un fichero de rutas del almacén. */
function vigilarRutas(pagina: Page): string[] {
  const pedidas: string[] = [];
  pagina.on("request", (peticion) => {
    const url = new URL(peticion.url());
    if (url.hostname.endsWith("your-objectstorage.com") && url.pathname.startsWith("/rutas/")) {
      pedidas.push(url.pathname);
    }
  });
  return pedidas;
}

for (const tamano of TAMANOS) {
  test.describe(`rutas apagadas en ${tamano.nombre}`, () => {
    test.skip(ajuste.mostrar, "las rutas están encendidas en la web");
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    test("sin «Rutas» en la capa de Ucrania, sin ficheros de rutas y «Noche a noche» funciona", async ({ page }) => {
      const pedidas = vigilarRutas(page);
      await page.goto("/?guerra=corredores,rutas");
      await page.locator(MAPA).waitFor();
      if (tamano.movil) await page.getByRole("button", { name: /Menú|Menu/ }).first().click();
      await expect(page.getByRole("button", { name: "Corredores" }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: /Con satélite/ }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Rutas", exact: true })).toHaveCount(0);
      await expect(page).not.toHaveURL(/guerra=[^&]*rutas/);
      await page.screenshot({ path: join(CAPTURAS, `capa-ucrania-${tamano.nombre}.png`) });
      await page.getByRole("button", { name: /Noche a noche|Night by night/ }).first().click();
      await expect(page.locator("[data-noche]")).toBeVisible();
      await page.waitForTimeout(3000);
      await expect(page.locator("[data-leyenda=rutas]")).toHaveCount(0);
      await expect(page.locator("[data-enlace-neptun]")).toHaveCount(0);
      await page.screenshot({ path: join(CAPTURAS, `noche-a-noche-${tamano.nombre}.png`) });
      expect(pedidas).toEqual([]);
    });

    test("el recorrido oficial de una incursión se sigue dibujando", async ({ page }) => {
      const pedidas = vigilarRutas(page);
      await page.goto("/EODI-2026-00193");
      await page.locator(MAPA).waitFor();
      await expect(page.locator("[data-recorrido]").first()).toBeVisible({ timeout: 20000 });
      const dibujado = await page.evaluate(async () => {
        const mapa = (document.querySelector(".maplibregl-map") as HTMLElement & {
          mapaDePruebas?: { querySourceFeatures: (fuente: string) => unknown[] };
        }).mapaDePruebas;
        await new Promise((listo) => setTimeout(listo, 1500));
        return mapa?.querySourceFeatures("recorrido").length ?? 0;
      });
      expect(dibujado).toBeGreaterThan(0);
      await page.screenshot({ path: join(CAPTURAS, `recorrido-${tamano.nombre}.png`) });
      expect(pedidas).toEqual([]);
    });
  });
}

test("la página de texto de Ucrania y la metodología no mencionan las rutas", async ({ request }) => {
  test.skip(ajuste.mostrar, "las rutas están encendidas en la web");
  for (const [ruta, prohibido] of [
    ["/ucrania", /Rutas de los drones sobre Ucrania|subcapa «Rutas»|NEPTUN/],
    ["/en/ukraine", /Drone routes over Ukraine|«Routes» sublayer|NEPTUN/],
    ["/metodologia", /Rutas de los drones sobre Ucrania|subcapa «Rutas»|NEPTUN/],
    ["/en/methodology", /Drone routes over Ukraine|«Routes» sublayer|NEPTUN/],
  ] as const) {
    const texto = await (await request.get(ruta)).text();
    expect(texto, ruta).not.toMatch(prohibido);
  }
  const metodo = await (await request.get("/metodologia")).text();
  expect(metodo).toContain("Recorrido de las incursiones");
});
