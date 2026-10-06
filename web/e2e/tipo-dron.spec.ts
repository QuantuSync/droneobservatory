// Tipo de dron en el teléfono (360, 390 y 412 px de ancho) y en escritorio: la fila «Tipo de dron»
// de un incidente identificado por la autoridad, de uno deducido y de uno sin base; el filtro por
// clase; cerrar la ficha sin que el mapa se mueva; y la página de texto sin ejecutar código.
// Deja capturas en CAPTURAS (por defecto, fuera del repositorio, en ../../eodi-tr-cap). Va contra
// producción por defecto; con BASE=http://localhost:…, contra el servidor local.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { APIRequestContext, BrowserContext, Page } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "..", "eodi-tr-cap");
const MAPA = "[data-mapa-listo=true]";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, movil: true },
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "412x915", width: 412, height: 915, movil: true },
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

interface Elegidos {
  autoridad: string;
  deducido: string;
  sinBase: string;
  claveDeducida: string;
}

/** Un incidente de cada clase, sacados del resumen publicado (con punto, para el mapa). */
async function elegir(request: APIRequestContext): Promise<Elegidos> {
  const resumen = (await (await request.get("/datos/resumen.json")).json()) as {
    incidentes: { id: string; punto: unknown; dron: string[]; presencia: string | null }[];
  };
  const conPunto = resumen.incidentes.filter((i) => i.punto !== null);
  const autoridad = conPunto.find((i) => i.dron.some((c) => c.startsWith("autoridad:")));
  const deducido = conPunto.find((i) => i.dron.some((c) => c.startsWith("deducido:")));
  const sinBase = conPunto.find((i) => i.dron.length === 0 && i.presencia === "confirmada");
  if (autoridad === undefined || deducido === undefined || sinBase === undefined) {
    throw new Error("faltan incidentes con tipo de dron en los datos publicados");
  }
  return {
    autoridad: autoridad.id,
    deducido: deducido.id,
    sinBase: sinBase.id,
    claveDeducida: deducido.dron[0] ?? "",
  };
}

async function cerrarFicha(pagina: Page) {
  await pagina.getByRole("button", { name: /Cerrar la ficha|Close the record/ }).first().click();
}

for (const tamano of TAMANOS) {
  test.describe(`tipo de dron en ${tamano.nombre}`, () => {
    test.use({ viewport: { width: tamano.width, height: tamano.height }, hasTouch: tamano.movil, isMobile: tamano.movil });

    test("la fila de lo identificado, de lo deducido y de lo que no tiene base; cerrar no mueve el mapa", async ({
      page,
      context,
      baseURL,
      request,
    }) => {
      await preparar(context, baseURL);
      const elegidos = await elegir(request);

      await page.goto(`/${elegidos.autoridad}`);
      await page.locator(MAPA).waitFor();
      const identificado = page.locator("[data-tipo-dron=autoridad]").first();
      await expect(identificado).toContainText(/según la autoridad/);
      await identificado.scrollIntoViewIfNeeded();
      await page.screenshot({ path: join(CAPTURAS, `tipo-identificado-${tamano.nombre}.png`) });

      await page.goto(`/${elegidos.deducido}`);
      await page.locator(MAPA).waitFor();
      const deducido = page.locator("[data-tipo-dron=deducido]").first();
      await expect(deducido).toHaveText("Compatible con");
      const fila = deducido.locator("xpath=ancestor::dd[1]");
      await expect(fila).toContainText(/\d de cada 10 \(\d+ %\)/);
      await expect(fila).not.toContainText(/Shahed|Geran|Gerbera/);
      await fila.getByText("Por qué").click();
      await expect(fila).toContainText(/casos de (frontera|del interior)/);
      await fila.getByText("Por qué").scrollIntoViewIfNeeded();
      await page.screenshot({ path: join(CAPTURAS, `tipo-deducido-${tamano.nombre}.png`) });
      const antes = await vista(page);
      await cerrarFicha(page);
      await page.waitForTimeout(800);
      expect(await vista(page)).toBe(antes);

      await page.goto(`/${elegidos.sinBase}`);
      await page.locator(MAPA).waitFor();
      await expect(page.locator("article").first()).toBeVisible();
      await expect(page.locator("[data-tipo-dron]")).toHaveCount(0);
      await page.screenshot({ path: join(CAPTURAS, `tipo-sin-base-${tamano.nombre}.png`) });
    });

    test("el filtro por clase separa lo identificado de lo deducido", async ({ page, context, baseURL, request }) => {
      await preparar(context, baseURL);
      const elegidos = await elegir(request);
      await page.goto("/");
      await page.locator(MAPA).waitFor();
      const antes = await vista(page);
      await page.locator("[data-botones-mapa] [data-boton-filtros] button").first().click();
      const filtro = page.locator("[data-filtro-dron]");
      await filtro.scrollIntoViewIfNeeded();
      await expect(filtro).toContainText("Identificado por la autoridad");
      await expect(filtro).toContainText("Deducido (compatible con)");
      const [origen] = elegidos.claveDeducida.split(":");
      const boton = filtro
        .locator("div", { hasText: origen === "deducido" ? "Deducido (compatible con)" : "Identificado" })
        .last()
        .getByRole("button")
        .first();
      await boton.click();
      await expect(boton).toHaveAttribute("aria-pressed", "true");
      await expect(page).toHaveURL(/dron=deducido(:|%3A)/);
      await page.screenshot({ path: join(CAPTURAS, `tipo-filtro-${tamano.nombre}.png`) });
      await page.keyboard.press("Escape");
      expect(await vista(page)).toBe(antes);
    });
  });
}

test("las páginas de texto dicen lo mismo sin ejecutar código", async ({ request }) => {
  const elegidos = await elegir(request);
  const deducido = await (await request.get(`/${elegidos.deducido}`)).text();
  expect(deducido).toContain('data-tipo-dron="deducido"');
  expect(deducido).toMatch(/de cada 10 \(\d+ %\)/);
  const identificado = await (await request.get(`/en/${elegidos.autoridad}`)).text();
  expect(identificado).toContain("according to the authority");
  const metodo = await (await request.get("/metodologia")).text();
  expect(metodo).toContain("Tipo de dron");
});
