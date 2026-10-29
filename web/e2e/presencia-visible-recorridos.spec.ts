// «No acreditado» y «descartado», bien visibles, como los ve una persona: en un Android (Chromium,
// Pixel 7), un iPhone (WebKit, iPhone 14), una tableta táctil y el escritorio (Chromium y WebKit),
// en español y en inglés, con los datos publicados (sin tocarlos).
//
// Las fichas y lo que se espera de ellas (presencia, estado, punto del mapa) se leen de los datos
// publicados (e2e/publicados.ts); si una autoridad cambia la presencia de una, se prueba con otra.
//
// - Copenhague (EODI-2025-00154) y Oslo (EODI-2025-00042): la presencia lleva el círculo morado;
//   el «Historial de estados» acaba en «No acreditado» con su círculo, su fecha y su fuente
//   enlazada; el estado del suceso sigue «Confirmado».
// - Lakenheath (EODI-2025-00164): la presencia y el último paso del historial llevan el círculo
//   gris relleno de «Descartado».
// - En los tres, el motivo del último paso empieza con mayúscula.
// - Bruselas (EODI-2026-00293): confirmado por el control aéreo (skeyes), con el desmentido del
//   aeropuerto en su historial, con su fecha y su fuente.
// - El mapa: el punto de Copenhague (un grupo con confirmados) lleva el aro exterior morado, el
//   aro de selección es morado con la ficha abierta, y al tocar el punto la lista «N incidentes en
//   este punto» enseña a Copenhague con su círculo morado. Cerrar la ficha no mueve el mapa.
// - La leyenda de la ayuda explica las dos marcas: el incidente ocurrió.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "./base.ts";
import type { Locator, Page } from "@playwright/test";

import { textos } from "../src/i18n/index.ts";
import { destino, elegir, publicados } from "./publicados.ts";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "test-results", "capturas", "presencia-visible");
const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];
const MORADO = "#e81cf0";
const GRIS = "#93a0b4";
const COPENHAGUE_ID = "EODI-2025-00154";

function ruta(idioma: "es" | "en", id = ""): string {
  return idioma === "en" ? `/en/${id}` : `/${id}`;
}

function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("pageerror", (e) => {
    if (/access control checks/.test(e.message)) return;
    errores.push(`excepción: ${e.message}`);
  });
  return errores;
}

/** La vista cuando el mapa deja de moverse. */
async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  let anterior = "";
  for (let i = 0; i < 40; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior && !ahora.includes("null")) return ahora;
    anterior = ahora;
  }
  return anterior;
}

/** Toca el elemento con el dedo o lo pulsa con el ratón, en su centro. */
async function tocar(pagina: Page, elemento: Locator, tactil: boolean) {
  await elemento.scrollIntoViewIfNeeded();
  const caja = await elemento.boundingBox();
  if (caja === null) throw new Error("elemento sin caja");
  if (tactil) await pagina.touchscreen.tap(caja.x + caja.width / 2, caja.y + caja.height / 2);
  else await pagina.mouse.click(caja.x + caja.width / 2, caja.y + caja.height / 2);
}

/** Abre la ficha desde su dirección y, en el teléfono, sube la hoja. */
async function abrirFicha(pagina: Page, idioma: "es" | "en", id: string, tactil: boolean): Promise<Locator> {
  await pagina.goto(ruta(idioma, id), { waitUntil: "domcontentloaded" });
  await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
  const ficha = pagina.locator("[data-ficha] article").first();
  await expect(ficha).toBeVisible({ timeout: 30_000 });
  const asa = pagina.locator("aside[data-altura] button[data-arrastre]").first();
  if (tactil && (await asa.count()) > 0 && (await asa.isVisible())) await tocar(pagina, asa, tactil);
  return ficha;
}

/** Los pasos del «Historial de estados» de la ficha. */
function pasosDelHistorial(ficha: Locator, rotulo: string): Locator {
  return ficha.locator("section").filter({ has: ficha.page().locator("h3", { hasText: rotulo }) }).locator("ol > li");
}

/** Lo que dibuja el mapa en una capa alrededor de un punto: propiedades de cada rasgo. */
async function rasgosEn(pagina: Page, capa: string, lon: number, lat: number): Promise<Record<string, unknown>[]> {
  return pagina.evaluate(
    ([c, lo, la]) => {
      const elemento = document.querySelector(".maplibregl-map") as HTMLElement & {
        mapaDePruebas?: {
          project: (p: [number, number]) => { x: number; y: number };
          queryRenderedFeatures: (caja: [[number, number], [number, number]], o: { layers: string[] }) => { properties: Record<string, unknown> }[];
        };
      };
      const mapa = elemento.mapaDePruebas;
      if (mapa === undefined) throw new Error("sin mapa de pruebas");
      const p = mapa.project([lo, la]);
      return mapa.queryRenderedFeatures([[p.x - 30, p.y - 30], [p.x + 30, p.y + 30]], { layers: [c] }).map((r) => r.properties);
    },
    [capa, lon, lat] as const,
  );
}

if (process.env.ANCHO !== undefined && process.env.ALTO !== undefined) {
  test.use({ viewport: { width: Number(process.env.ANCHO), height: Number(process.env.ALTO) } });
}

test.describe("No acreditado y descartado, bien visibles, como una persona", () => {
  for (const idioma of ["es", "en"] as const) {
    const t = textos(idioma);

    for (const caso of [
      { id: "EODI-2025-00154", nombre: "Copenhague", marca: "no_acreditado", presencia: "no_acreditada", color: MORADO, rotulo: t.noAcreditado.etiqueta, fecha: "25/06/2026" },
      { id: "EODI-2025-00042", nombre: "Oslo", marca: "no_acreditado", presencia: "no_acreditada", color: MORADO, rotulo: t.noAcreditado.etiqueta, fecha: null },
      { id: "EODI-2025-00164", nombre: "Lakenheath", marca: "descartado", presencia: "descartada", color: GRIS, rotulo: t.descartado.etiqueta, fecha: null },
    ] as const) {
      test(`${caso.nombre}: la presencia y el historial con su círculo y su fuente (${idioma})`, async ({ page: pagina }, info) => {
        test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
        test.setTimeout(180_000);
        const errores = vigilar(pagina);
        const tactil = info.project.use.hasTouch === true;
        // La ficha y lo que se espera de ella, de los datos publicados: si una autoridad cambia la
        // presencia de la preferida, se prueba con otra que la tenga (e2e/publicados.ts).
        const datos = await publicados(pagina.request);
        const id = elegir(datos, caso.id, (f) => f.presencia_dron === caso.presencia && (f.presencia_historial?.length ?? 0) > 0);
        test.skip(id === null, `ninguna ficha publicada con la presencia ${caso.presencia}`);
        const datosFicha = datos.fichas.get(id as string);
        const ficha = await abrirFicha(pagina, idioma, id as string, tactil);
        const estado = t.estado[datosFicha?.estado.actual ?? "confirmado"];
        // Arriba, el círculo lleva su nombre al lado: no se lee como el color del tipo.
        const arriba = ficha.locator("[data-marca-ficha]");
        await expect(arriba).toHaveAttribute("data-marca-ficha", caso.marca);
        await expect(arriba).toContainText(caso.rotulo);
        // El estado del suceso no cambia.
        await expect(ficha).toContainText(estado);
        // La presencia: el círculo de su marca, del mismo tamaño que los de los estados.
        const presencia = ficha.locator("[data-presencia]");
        await presencia.scrollIntoViewIfNeeded();
        const circulo = presencia.locator("xpath=..").locator(`svg[data-circulo=${caso.marca}]`).first();
        await expect(circulo.locator("circle")).toHaveAttribute("fill", caso.color);
        const lado = await circulo.getAttribute("width");
        await expect(ficha.locator("section svg[data-circulo]").first()).toHaveAttribute("width", lado ?? "");
        // El historial de estados acaba en el cambio de la presencia, con su círculo y su fuente.
        const pasos = pasosDelHistorial(ficha, t.ficha.historial);
        const ultimo = ficha.locator(`[data-historial-presencia=${caso.marca}]`).last();
        await ultimo.scrollIntoViewIfNeeded();
        await expect(ultimo).toBeVisible();
        await expect(ultimo).toContainText(caso.rotulo);
        if (caso.fecha !== null && id === caso.id) await expect(ultimo).toContainText(caso.fecha);
        await expect(ultimo.locator(`svg[data-circulo=${caso.marca}] circle`)).toHaveAttribute("fill", caso.color);
        await expect(ultimo.locator("a[href]").first()).toBeVisible();
        // Debajo, el motivo, que empieza con mayúscula aunque el dato venga en minúscula.
        const motivo = ultimo.locator("[data-motivo-historial]");
        await expect(motivo).toBeVisible();
        expect(((await motivo.textContent()) ?? "").trim()).toMatch(/^[«"“]?\p{Lu}/u);
        // En orden de fecha: va después de los pasos del estado.
        const total = await pasos.count();
        expect(total).toBeGreaterThanOrEqual(2);
        await expect(pasos.nth(total - 1)).toHaveAttribute("data-historial-presencia", caso.marca);
        await pagina.screenshot({ path: join(CAPTURAS, `${caso.nombre}-${idioma}-${info.project.name}.png`), fullPage: false });
        // Cerrar la ficha no mueve el mapa.
        const antes = await vista(pagina);
        await tocar(pagina, pagina.getByRole("button", { name: t.ficha.cerrar }).first(), tactil);
        await expect(pagina.locator("[data-ficha] article")).toHaveCount(0);
        expect(await vista(pagina)).toBe(antes);
        expect(errores).toEqual([]);
      });
    }

    test(`Bruselas 12/09/2026: confirmado por skeyes, con el desmentido del aeropuerto en el historial (${idioma})`, async ({ page: pagina }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(180_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const datos = await publicados(pagina.request);
      const id = destino(datos, "EODI-2026-00293");
      const bruselas = id === null ? undefined : datos.fichas.get(id);
      test.skip(
        bruselas?.estado.actual !== "confirmado" || !bruselas.estado.historial.some((p) => p.estado === "desmentido"),
        "la ficha de Bruselas ya no está confirmada con el desmentido en su historial",
      );
      const ficha = await abrirFicha(pagina, idioma, id as string, tactil);
      await expect(ficha.locator("dl")).toContainText(t.estado.confirmado);
      const pasos = pasosDelHistorial(ficha, t.ficha.historial);
      await pasos.first().scrollIntoViewIfNeeded();
      // El desmentido del aeropuerto sigue en el historial, con su fecha y su motivo, y el último
      // paso es el confirmado de skeyes.
      const desmentido = pasos.filter({ has: pagina.locator("svg[data-circulo=desmentido]") });
      await expect(desmentido).toHaveCount(1);
      await expect(desmentido).toContainText("2026");
      const total = await pasos.count();
      await expect(pasos.nth(total - 1).locator("svg[data-circulo=confirmado]")).toHaveCount(1);
      // El motivo va con mayúscula: «Skeyes, …» en inglés, «… skeyes» en español.
      await expect(pasos.nth(total - 1)).toContainText(/skeyes/i);
      await pagina.screenshot({ path: join(CAPTURAS, `bruselas-${idioma}-${info.project.name}.png`) });
      expect(errores).toEqual([]);
    });

    test(`el mapa: aro morado en el punto de Copenhague, selección morada y la lista del punto (${idioma})`, async ({ page: pagina }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(180_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const datos = await publicados(pagina.request);
      const id = destino(datos, COPENHAGUE_ID);
      const lugar = id === null ? undefined : datos.puntos.get(id);
      test.skip(
        id === null || lugar === undefined || datos.fichas.get(id)?.presencia_dron !== "no_acreditada",
        "la ficha de Copenhague ya no está en el mapa con la presencia no acreditada",
      );
      const COPENHAGUE = { id: id as string, lon: (lugar as [number, number])[0], lat: (lugar as [number, number])[1] };
      await abrirFicha(pagina, idioma, COPENHAGUE.id, tactil);
      await vista(pagina);
      // Con la ficha abierta, el aro de selección es de la marca: morado.
      await expect
        .poll(async () => (await rasgosEn(pagina, "seleccion", COPENHAGUE.lon, COPENHAGUE.lat)).map((r) => r.estado), { timeout: 20_000 })
        .toContain("no_acreditado");
      // Cerrar la ficha no mueve el mapa.
      const antes = await vista(pagina);
      await tocar(pagina, pagina.getByRole("button", { name: t.ficha.cerrar }).first(), tactil);
      await expect(pagina.locator("[data-ficha] article")).toHaveCount(0);
      expect(await vista(pagina)).toBe(antes);
      // El punto de Copenhague, de cerca: un grupo con su aro exterior morado.
      const punto = await pagina.evaluate(
        ([lo, la]) =>
          new Promise<{ x: number; y: number }>((listo) => {
            const elemento = document.querySelector(".maplibregl-map") as HTMLElement & {
              mapaDePruebas?: { once: (e: string, f: () => void) => void; jumpTo: (o: object) => void; project: (c: [number, number]) => { x: number; y: number } };
            };
            const mapa = elemento.mapaDePruebas;
            if (mapa === undefined) throw new Error("sin mapa de pruebas");
            mapa.once("idle", () => {
              const caja = elemento.getBoundingClientRect();
              const p = mapa.project([lo, la]);
              listo({ x: caja.left + p.x, y: caja.top + p.y });
            });
            mapa.jumpTo({ center: [lo, la], zoom: 12 });
          }),
        [COPENHAGUE.lon, COPENHAGUE.lat] as const,
      );
      await expect
        .poll(async () => (await rasgosEn(pagina, "grupos-presencia", COPENHAGUE.lon, COPENHAGUE.lat)).map((r) => String(r.ids ?? "")).join(";"), { timeout: 20_000 })
        .toContain(COPENHAGUE.id);
      await pagina.screenshot({ path: join(CAPTURAS, `mapa-${idioma}-${info.project.name}.png`) });
      // Al tocarlo, la lista del punto enseña a Copenhague con su círculo morado.
      if (tactil) await pagina.touchscreen.tap(punto.x, punto.y);
      else await pagina.mouse.click(punto.x, punto.y);
      const entrada = pagina.locator("li:visible").filter({ has: pagina.locator(`a[href$="${COPENHAGUE.id}"]`) });
      await expect(entrada).toBeVisible({ timeout: 20_000 });
      await expect(entrada.locator("svg[data-circulo=no_acreditado] circle")).toHaveAttribute("fill", MORADO);
      await expect(entrada).toContainText(t.presencia.no_acreditada);
      expect(errores).toEqual([]);
    });

    test(`la leyenda explica no acreditado y descartado (${idioma})`, async ({ page: pagina }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(180_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      await pagina.goto(ruta(idioma), { waitUntil: "domcontentloaded" });
      await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
      const inicial = await vista(pagina);
      if (await pagina.locator("[data-boton-menu]").isVisible()) {
        await tocar(pagina, pagina.locator("[data-boton-menu]"), tactil);
        await tocar(pagina, pagina.locator("dialog[open]").getByRole("button", { name: t.controles.ayuda, exact: true }), tactil);
      } else {
        await tocar(pagina, pagina.locator("header").getByRole("button", { name: t.controles.ayuda, exact: true }), tactil);
      }
      const ayuda = pagina.getByRole("dialog", { name: t.ayuda.titulo });
      await expect(ayuda).toBeVisible();
      for (const [selector, marca, color, textosMarca] of [
        ["[data-leyenda-no-acreditado]", "no_acreditado", MORADO, t.noAcreditado],
        ["[data-leyenda-descartado]", "descartado", GRIS, t.descartado],
      ] as const) {
        const entrada = ayuda.locator(selector);
        await entrada.scrollIntoViewIfNeeded();
        await expect(entrada).toBeVisible();
        await expect(entrada).toContainText(textosMarca.etiqueta);
        await expect(entrada).toContainText(textosMarca.leyenda);
        await expect(entrada.locator(`svg[data-circulo=${marca}] circle`)).toHaveAttribute("fill", color);
      }
      await pagina.screenshot({ path: join(CAPTURAS, `leyenda-${idioma}-${info.project.name}.png`) });
      await tocar(pagina, ayuda.getByRole("button", { name: t.ayuda.cerrar }), tactil);
      await expect(ayuda).toBeHidden();
      expect(await vista(pagina)).toBe(inicial);
      expect(errores).toEqual([]);
    });
  }
});
