// La hoja inferior del teléfono con gestos táctiles de verdad (eventos de toque del
// navegador), en los tres tamaños de referencia en vertical: se arrastra siguiendo el dedo,
// se ajusta a la altura más cercana teniendo en cuenta la velocidad, un toque en el asa nunca
// la cierra, el contenido se desplaza antes de arrastrar la hoja y el mapa no recibe los
// gestos que empiezan en ella. Deja capturas de la ficha a sus tres alturas.

import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { CDPSession, Locator, Page } from "@playwright/test";

const CAPTURAS = join(import.meta.dirname, "..", "..", "data", "capturas", "hoja");
const MAPA_LISTO = "[data-mapa-listo=true]";
/** El incidente del aviso: en un móvil real dejaba la etiqueta fija encima del mapa. */
const INCIDENTE = "EODI-2025-00247";
const MS_DE_VUELO = 2000;
const MS_DE_ASENTAMIENTO = 800;
/** Un gesto lento (para seguir al dedo) y uno rápido (para la velocidad). */
const PASOS_LENTOS = 20;
const MS_PASO_LENTO = 25;
const PASOS_RAPIDOS = 4;
const MS_PASO_RAPIDO = 8;
const TOLERANCIA_PX = 3;
/** Veces que se espera a que el mapa deje de cambiar antes de compararlo. */
const INTENTOS_DE_REPOSO = 8;
const TAMANOS = [
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 412, height: 915 },
];

const ACCESO: Record<string, string> =
  process.env.VERCEL_BYPASS === undefined
    ? {}
    : { "x-vercel-protection-bypass": process.env.VERCEL_BYPASS };

/** Un dedo que baja en (x, desde), se mueve hasta (x, hasta) y se levanta. */
async function deslizar(
  cdp: CDPSession,
  x: number,
  desde: number,
  hasta: number,
  { pasos = PASOS_LENTOS, msPorPaso = MS_PASO_LENTO, soltar = true } = {},
): Promise<void> {
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: desde }] });
  for (let i = 1; i <= pasos; i += 1) {
    const y = desde + ((hasta - desde) * i) / pasos;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y }] });
    await new Promise((r) => setTimeout(r, msPorPaso));
  }
  if (soltar) await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

async function caja(locator: Locator) {
  const medida = await locator.boundingBox();
  if (medida === null) throw new Error("sin medidas");
  return medida;
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await mkdir(CAPTURAS, { recursive: true });
  await pagina.screenshot({ path: join(CAPTURAS, `${nombre}.png`) });
}

for (const viewport of TAMANOS) {
  const nombre = `${viewport.width}x${viewport.height}`;
  test.describe(nombre, () => {
    test.use({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });

    test(`${nombre}: la hoja se arrastra con el dedo y nunca deja etiquetas encima`, async ({ page, baseURL }, info) => {
      test.skip(info.project.name !== "movil", "los gestos del teléfono se comprueban una sola vez");
      if (Object.keys(ACCESO).length > 0 && baseURL !== undefined) {
        const propio = new URL(baseURL).origin;
        await page.route(
          (url) => url.origin === propio,
          (ruta) => ruta.continue({ headers: { ...ruta.request().headers(), ...ACCESO } }),
        );
      }
      // Sin pulsos animados, para comparar el mapa antes y después de un gesto.
      await page.emulateMedia({ reducedMotion: "reduce" });
      const cdp = await page.context().newCDPSession(page);
      const letrero = page.locator("[data-letrero]");

      // Tocar el símbolo abre la ficha y no deja ninguna etiqueta encima.
      await page.goto(`/${INCIDENTE}`);
      await page.waitForSelector(MAPA_LISTO);
      let ficha = page.getByRole("complementary", { name: new RegExp(INCIDENTE) });
      await expect(ficha).toBeVisible();
      await page.waitForTimeout(MS_DE_VUELO);
      const barra = await caja(page.locator("header"));
      let hoja = await caja(ficha);
      const simbolo = { x: viewport.width / 2, y: (barra.y + barra.height + hoja.y) / 2 };
      await ficha.getByRole("button", { name: "Cerrar la ficha" }).tap();
      await expect(ficha).toBeHidden();
      await page.touchscreen.tap(simbolo.x, simbolo.y);
      ficha = page.getByRole("complementary", { name: /EODI-|incidentes en este/ });
      await expect(ficha).toBeVisible();
      await expect(letrero).toBeHidden();

      // Al abrir el incidente, la hoja va a media altura con el título y la descripción
      // enteros a la vista.
      await page.goto(`/${INCIDENTE}`);
      await page.waitForSelector(MAPA_LISTO);
      ficha = page.getByRole("complementary", { name: new RegExp(INCIDENTE) });
      await expect(ficha).toHaveAttribute("data-altura", "media");
      await page.waitForTimeout(MS_DE_VUELO);
      hoja = await caja(ficha);
      const titulo = await caja(ficha.getByRole("heading", { level: 2 }).first());
      const descripcion = await caja(ficha.locator("h2 + p").first());
      for (const parte of [titulo, descripcion]) {
        expect(parte.y).toBeGreaterThanOrEqual(hoja.y);
        expect(parte.y + parte.height).toBeLessThanOrEqual(hoja.y + hoja.height);
      }
      await expect(letrero).toBeHidden();
      await capturar(page, `${nombre}-${INCIDENTE}-media`);

      // Un toque en el asa nunca cierra: media → completa → media.
      const asa = ficha.getByRole("button", { name: /^Hoja / });
      await asa.tap();
      await expect(ficha).toHaveAttribute("data-altura", "completa");
      await capturar(page, `${nombre}-${INCIDENTE}-completa`);
      await ficha.getByRole("button", { name: /^Hoja / }).tap();
      await expect(ficha).toHaveAttribute("data-altura", "media");
      await expect(ficha).toBeVisible();

      // Arrastrar desde el asa sigue al dedo, y al soltar se queda en la altura más cercana.
      hoja = await caja(ficha);
      const centroAsa = await caja(ficha.getByRole("button", { name: /^Hoja / }));
      const x = viewport.width / 2;
      const yAsa = centroAsa.y + centroAsa.height / 2;
      const bajada = Math.round(hoja.height * 0.3);
      await deslizar(cdp, x, yAsa, yAsa + bajada, { soltar: false });
      const durante = await caja(ficha);
      expect(Math.abs(durante.height - (hoja.height - bajada))).toBeLessThanOrEqual(TOLERANCIA_PX);
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      await expect(ficha).toHaveAttribute("data-altura", "asomada");
      await capturar(page, `${nombre}-${INCIDENTE}-asomada`);

      // Desde la cabecera, un gesto corto pero rápido hacia arriba sube una altura entera.
      const cabecera = await caja(ficha.locator("[data-arrastre]").nth(1));
      const yCabecera = cabecera.y + cabecera.height / 2;
      await deslizar(cdp, x, yCabecera, yCabecera - 60, { pasos: PASOS_RAPIDOS, msPorPaso: MS_PASO_RAPIDO });
      await expect(ficha).not.toHaveAttribute("data-altura", "asomada");
      await expect(ficha).toBeVisible();

      // A altura completa, el contenido se desplaza antes de que la hoja se mueva.
      await ficha.getByRole("button", { name: /^Hoja / }).tap();
      if ((await ficha.getAttribute("data-altura")) !== "completa") {
        await ficha.getByRole("button", { name: /^Hoja / }).tap();
      }
      await expect(ficha).toHaveAttribute("data-altura", "completa");
      hoja = await caja(ficha);
      const contenido = ficha.locator(".overflow-y-auto").first();
      const medio = hoja.y + hoja.height * 0.6;
      await deslizar(cdp, x, medio, medio - 300);
      await page.waitForTimeout(MS_DE_ASENTAMIENTO);
      const desplazado = await contenido.evaluate((e) => e.scrollTop);
      expect(desplazado).toBeGreaterThan(0);
      await expect(ficha).toHaveAttribute("data-altura", "completa");
      // Bajar el dedo con el contenido desplazado lo devuelve arriba sin mover la hoja…
      await deslizar(cdp, x, medio - 200, medio - 200 + 120);
      await page.waitForTimeout(MS_DE_ASENTAMIENTO);
      expect(await contenido.evaluate((e) => e.scrollTop)).toBeLessThan(desplazado);
      await expect(ficha).toHaveAttribute("data-altura", "completa");
      await contenido.evaluate((e) => {
        e.scrollTop = 0;
      });
      // …y con el contenido arriba del todo, el mismo gesto ya arrastra la hoja.
      await deslizar(cdp, x, medio - 200, medio + 60);
      await expect(ficha).not.toHaveAttribute("data-altura", "completa");
      await expect(ficha).toBeVisible();

      // El mapa no recibe los gestos que empiezan dentro de la hoja.
      hoja = await caja(ficha);
      const zonaDelMapa = { x: 0, y: barra.y + barra.height, width: viewport.width, height: hoja.y - barra.y - barra.height - 4 };
      // Se espera a que el mapa termine de pintar: dos fotos seguidas iguales.
      let antes = await page.screenshot({ clip: zonaDelMapa });
      for (let intento = 0; intento < INTENTOS_DE_REPOSO; intento += 1) {
        await page.waitForTimeout(MS_DE_ASENTAMIENTO);
        const otra = await page.screenshot({ clip: zonaDelMapa });
        if (Buffer.compare(antes, otra) === 0) break;
        antes = otra;
      }
      const dentro = hoja.y + hoja.height * 0.7;
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: 60, y: dentro }] });
      for (let i = 1; i <= PASOS_LENTOS; i += 1) {
        await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: 60 + i * 10, y: dentro }] });
      }
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      await page.waitForTimeout(MS_DE_ASENTAMIENTO);
      expect(Buffer.compare(antes, await page.screenshot({ clip: zonaDelMapa }))).toBe(0);

      // Solo se cierra arrastrándola hacia abajo por debajo de la altura asomada (o con la X).
      const yAsaFinal = (await caja(ficha.getByRole("button", { name: /^Hoja / }))).y + 22;
      await deslizar(cdp, x, yAsaFinal, viewport.height - 4);
      await expect(ficha).toBeHidden();
      await expect(page).toHaveURL(/\/$/);
      await expect(letrero).toBeHidden();
    });
  });
}
