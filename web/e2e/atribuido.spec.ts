// El marcador de los atribuidos en un navegador real, en el teléfono (360, 390 y 412 px de
// ancho, con tacto) y en escritorio: en el mapa, la ficha, el historial, la leyenda, los
// filtros y las cifras, y ninguna bandera con mástil en toda la web. Deja las capturas en
// docs/capturas (CAPTURAS para otra carpeta), con una ampliada de cada atribuido. Va contra
// producción por defecto; con BASE=http://localhost:4173 contra el servidor local, reenviando
// el almacén público, que solo admite el dominio propio.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import { varianteDe } from "../src/banderas.ts";
import type { IncidenteResumen, Resumen } from "../src/datos/tipos.ts";
import { textoAtribuido, textos } from "../src/i18n/index.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const MS_DE_ASENTAMIENTO = 2500;
const TELEFONOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "390x844", width: 390, height: 844 },
  { nombre: "412x915", width: 412, height: 915 },
];
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
const CHISINAU = "EODI-2026-00074";
/** Una visita anterior lejana: todo lo publicado después cuenta como novedad y late. */
const VISITA_ANTIGUA = "2026-09-01T00:00:00.000Z";
const ES = textos("es");

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await pagina.screenshot({ path: join(CAPTURAS, `atribuido-${nombre}.png`) });
}

async function entrar(pagina: Page, ruta: string, novedades = false) {
  await pagina.addInitScript(
    ({ visita, con }) => {
      if (con) window.localStorage.setItem("eodi.ultima-visita", visita);
      else window.localStorage.removeItem("eodi.ultima-visita");
    },
    { visita: VISITA_ANTIGUA, con: novedades },
  );
  await pagina.goto(ruta);
  await pagina.waitForSelector(MAPA_LISTO);
}

async function atribuidos(pagina: Page): Promise<IncidenteResumen[]> {
  const datos = (await (await pagina.request.get("/datos/resumen.json")).json()) as Resumen;
  return datos.incidentes.filter((i) => i.estado === "atribuido" && i.punto !== null);
}

/** Lo que debe llevar el marcador de un atribuido en el documento. */
function esperado(incidente: IncidenteResumen) {
  const variante = varianteDe(incidente.atribucion);
  return { bandera: variante.bandera ?? "liso", persona: variante.persona, texto: textoAtribuido(ES, "es", incidente.atribucion) };
}

/** Ninguna bandera con mástil: ni en el documento, ni en los estilos, ni en los iconos del mapa. */
async function sinMastil(pagina: Page) {
  expect(await pagina.locator("[data-bandera]").count()).toBe(0);
  expect(await pagina.locator(".pulso-bandera").count()).toBe(0);
  const iconos = (await pagina.locator(MAPA_LISTO).getAttribute("data-iconos")) ?? "";
  expect(iconos).not.toMatch(/\bbandera\b/);
}

for (const tamano of [...TELEFONOS, ESCRITORIO]) {
  const telefono = tamano !== ESCRITORIO;
  const nombre = tamano.nombre;

  test.describe(nombre, () => {
    test.use({
      viewport: { width: tamano.width, height: tamano.height },
      isMobile: telefono,
      hasTouch: telefono,
      deviceScaleFactor: telefono ? 2 : 1,
    });
    test.beforeEach(({ browserName }, info) => {
      test.skip(browserName !== "chromium" || info.project.name !== (telefono ? "movil" : "escritorio"));
    });
    // Las teselas que siguen en camino al acabar no cuentan como fallo de la prueba.
    test.afterEach(async ({ context }) => {
      await context.unrouteAll({ behavior: "ignoreErrors" });
    });

    test(`${nombre}: cada atribuido con su marcador en el mapa y en la ficha`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      const lista = await atribuidos(page);
      expect(lista.length).toBeGreaterThan(0);
      await entrar(page, "/");
      await expect(page.locator(MAPA_LISTO)).toHaveAttribute("data-iconos", /atribuido--1/);
      await sinMastil(page);
      await capturar(page, `mapa-${nombre}`);
      for (const incidente of lista) {
        await page.goto(`/${incidente.id}`);
        await page.waitForSelector(MAPA_LISTO);
        const ficha = page.getByRole("complementary", { name: new RegExp(incidente.id) });
        const { bandera, persona, texto } = esperado(incidente);
        // Junto al estado, el marcador con su texto para el lector de pantalla.
        const marca = ficha.locator("[data-estado-atribuido] svg[data-atribuido]");
        await expect(marca).toHaveAttribute("data-atribuido", bandera);
        await expect(marca).toHaveAttribute("aria-label", texto);
        expect(await marca.getAttribute("data-persona")).toBe(persona ? "" : null);
        // El mismo marcador en la cabecera de la ficha y en el historial.
        expect(await ficha.locator(`svg[data-atribuido="${bandera}"]`).count()).toBeGreaterThanOrEqual(3);
        await sinMastil(page);
        await capturar(page, `${incidente.id}-${nombre}`);
      }
    });

    test(`${nombre}: ampliada de cada atribuido, junto a los círculos`, async ({ browser, baseURL }) => {
      const contexto = await browser.newContext({
        viewport: { width: tamano.width, height: tamano.height },
        isMobile: telefono,
        hasTouch: telefono,
        deviceScaleFactor: 4,
        ...(baseURL === undefined ? {} : { baseURL }),
      });
      await preparar(contexto, baseURL);
      const pagina = await contexto.newPage();
      for (const incidente of await atribuidos(pagina)) {
        await entrar(pagina, `/${incidente.id}`);
        const ficha = pagina.getByRole("complementary", { name: new RegExp(incidente.id) });
        await expect(ficha).toBeVisible();
        await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
        // El mapa deja el incidente en el centro del hueco libre entre la cabecera y la ficha.
        const cabecera = await pagina.locator("header").filter({ visible: true }).first().boundingBox();
        const hoja = await ficha.boundingBox();
        if (cabecera === null || hoja === null) throw new Error("sin medidas");
        const arriba = cabecera.y + cabecera.height;
        const x = telefono ? tamano.width / 2 : hoja.x / 2;
        const y = telefono ? (arriba + hoja.y) / 2 : (arriba + tamano.height) / 2;
        await pagina.screenshot({
          path: join(CAPTURAS, `atribuido-ampliada-${incidente.id}-${nombre}.png`),
          clip: { x: x - 70, y: y - 45, width: 140, height: 90 },
        });
      }
      await contexto.unrouteAll({ behavior: "ignoreErrors" });
      await contexto.close();
    });

    test(`${nombre}: Chisináu alejado, un solo marcador con su número`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, `/${CHISINAU}`, true);
      const ficha = page.getByRole("complementary", { name: new RegExp(CHISINAU) });
      await expect(ficha).toBeVisible();
      await capturar(page, `chisinau-cerca-${nombre}`);
      await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
      await page.locator(".maplibregl-canvas").focus();
      for (let i = 0; i < 3; i += 1) {
        await page.keyboard.press("Minus");
        await page.waitForTimeout(700);
      }
      // Con novedades, el marcador late con un anillo, como los demás: nunca con una silueta.
      await sinMastil(page);
      await capturar(page, `chisinau-lejos-${nombre}`);
    });

    test(`${nombre}: leyenda, filtros, lista y cifras con el marcador nuevo`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      const lista = await atribuidos(page);
      await entrar(page, "/");
      // Cifras: un círculo pequeño con aro y relleno rojos, sin bandera, junto al número.
      if (telefono) await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
      const cifra = page.locator("[data-marca-cifra] svg[data-atribuido]").filter({ visible: true }).first();
      await expect(cifra).toHaveAttribute("data-atribuido", "liso");
      expect(await cifra.locator("image").count()).toBe(0);
      await capturar(page, `cifras-${nombre}`);
      // Leyenda de la ayuda: atribuido a un Estado y a una persona.
      await page.getByRole("button", { name: "Ayuda", exact: true }).click();
      const ayuda = page.getByRole("dialog", { name: "Cómo leer el mapa" });
      await expect(ayuda.locator("[data-leyenda-atribuido=estado]")).toHaveText(ES.atribucion.leyendaEstado);
      await expect(ayuda.locator("[data-leyenda-atribuido=persona]")).toHaveText(ES.atribucion.leyendaPersona);
      await expect(ayuda.locator("[data-leyenda-bandera]")).toHaveText(ES.atribucion.bandera);
      await ayuda.locator("[data-leyenda-estados]").scrollIntoViewIfNeeded();
      await capturar(page, `leyenda-${nombre}`);
      await sinMastil(page);
      await ayuda.getByRole("button", { name: "Cerrar la ayuda" }).click();
      // Filtros: «Atribuido» con su marcador.
      if (telefono && (await page.getByRole("dialog", { name: "Menú" }).isVisible())) {
        await page.getByRole("dialog", { name: "Menú" }).getByRole("button", { name: "Cerrar el menú" }).click();
      }
      await page.getByRole("button", { name: /^Abrir los filtros/ }).filter({ visible: true }).click();
      const filtros = page.getByRole("group", { name: "Filtros" }).filter({ visible: true });
      await expect(filtros.getByRole("button", { name: "Atribuido" }).locator("svg[data-atribuido]")).toBeVisible();
      await capturar(page, `filtros-${nombre}`);
      await page.keyboard.press("Escape");
      // Lista: cada atribuido con su marcador y a quién se atribuye, escrito.
      for (const incidente of lista) {
        await page.goto(`/${incidente.id}`);
        await page.waitForSelector(MAPA_LISTO);
        await expect(page.getByRole("complementary", { name: new RegExp(incidente.id) })).toContainText(
          ES.ficha.atribucion,
        );
      }
    });
  });
}
