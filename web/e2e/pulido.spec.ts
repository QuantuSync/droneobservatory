// Los ocho arreglos del pulido de la web, en un navegador real: primero en el teléfono (360,
// 390 y 412 px de ancho, con tacto) y después en escritorio. Deja las capturas de cada punto
// en docs/capturas (CAPTURAS para otra carpeta). Va contra producción por defecto; con
// BASE=http://localhost:4173 contra el servidor local, reenviando el almacén público, que solo
// admite el dominio propio.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import { validarResumenUcrania } from "../src/datos/validar.ts";
import { nochesDeGuerra, ultimaNocheConCifra } from "../src/datos/ucrania.ts";
import type { Resumen, ResumenUcrania } from "../src/datos/tipos.ts";
import { jornadaEscrita, textos } from "../src/i18n/index.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const MS_DE_ASENTAMIENTO = 2500;
const TELEFONOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "390x844", width: 390, height: 844 },
  { nombre: "412x915", width: 412, height: 915 },
];
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
/** Una visita anterior lejana: todo lo publicado después cuenta como novedad. */
const VISITA_ANTIGUA = "2026-09-01T00:00:00.000Z";
const MS_POR_DIA = 86_400_000;
const MS_24H = 24 * 3_600_000;

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await pagina.screenshot({ path: join(CAPTURAS, `pulido-${nombre}.png`) });
}

async function entrar(pagina: Page, ruta: string, novedades: boolean) {
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

/** Textos que no caben en su caja (cortados o tapados por el borde). */
async function textosQueNoCaben(pagina: Page, selector: string): Promise<string[]> {
  return pagina.locator(selector).evaluateAll((elementos) =>
    elementos
      .flatMap((e) => [e, ...e.querySelectorAll<HTMLElement>("*")])
      .filter((e) => e instanceof HTMLElement && e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1)
      .map((e) => (e.textContent ?? "").trim().slice(0, 40)),
  );
}

/** Lo que se dibuja encima de los botones del mapa: nada debe taparlos ni montarse. */
async function encimaDeLosBotones(pagina: Page): Promise<string[]> {
  return pagina.evaluate(() => {
    const botones = [...document.querySelectorAll<HTMLElement>("[data-boton-filtros] button, [data-boton-ahora]")].filter(
      (b) => b.offsetParent !== null,
    );
    const problemas: string[] = [];
    for (const boton of botones) {
      const caja = boton.getBoundingClientRect();
      if (caja.left < 0 || caja.right > window.innerWidth) problemas.push(`fuera: ${boton.textContent ?? ""}`);
      for (const [fx, fy] of [
        [0.15, 0.5],
        [0.5, 0.5],
        [0.85, 0.5],
      ] as const) {
        const encima = document.elementFromPoint(caja.left + caja.width * fx, caja.top + caja.height * fy);
        if (encima === null || !boton.contains(encima)) {
          problemas.push(`${boton.textContent ?? ""} tapado por ${encima?.textContent?.slice(0, 30) ?? "nada"}`);
        }
      }
    }
    // Ningún aviso sobre el mapa a la altura de los botones.
    const fila = document.querySelector("[data-botones-mapa]:not([hidden])");
    const avisos = document.querySelectorAll("[data-avisos-arriba], [data-novedades]");
    for (const aviso of avisos) {
      const a = (aviso as HTMLElement).getBoundingClientRect();
      const b = fila?.getBoundingClientRect();
      if ((aviso as HTMLElement).offsetParent === null || b === undefined || a.height === 0) continue;
      if (a.top < b.bottom && a.bottom > b.top && a.left < b.right && a.right > b.left) {
        problemas.push(`aviso montado: ${(aviso.textContent ?? "").slice(0, 30)}`);
      }
    }
    return problemas;
  });
}

const ES = textos("es");

/** El resumen de la capa de guerra publicado, validado igual que en la web. */
async function ucraniaPublicada(pagina: Page): Promise<ResumenUcrania> {
  const resultado = validarResumenUcrania(await (await pagina.request.get("/datos/ucrania-resumen.json")).json());
  if (!resultado.ok) throw new Error("ucrania-resumen.json no valida");
  return resultado.datos;
}

async function resumen(pagina: Page): Promise<Resumen> {
  return (await (await pagina.request.get("/datos/resumen.json")).json()) as Resumen;
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
    // Cada tamaño, una vez: los de teléfono con el proyecto móvil y el de escritorio con el suyo.
    test.beforeEach(({ browserName }, info) => {
      test.skip(browserName !== "chromium" || info.project.name !== (telefono ? "movil" : "escritorio"));
    });

    test(`${nombre}: 1. entrada con novedades y sin ellas, sin nada montado`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/", true);
      const boton = page.locator("[data-boton-ahora]").filter({ visible: true });
      await expect(boton.locator("[data-indicador=novedades]")).toBeVisible();
      await expect(boton).toHaveAttribute("aria-label", /novedad(es)? desde tu última visita/);
      expect(await encimaDeLosBotones(page)).toEqual([]);
      expect(await textosQueNoCaben(page, "[data-botones-mapa]")).toEqual([]);
      await capturar(page, `1-con-novedades-${nombre}`);
      // Dentro de «Europa ahora», la línea entera con «Verlas» y «Descartar».
      await boton.click();
      const linea = page.locator("[data-novedades]").filter({ visible: true });
      await expect(linea).toBeVisible();
      await expect(linea.getByRole("button", { name: "Verlas" })).toBeVisible();
      await expect(linea.getByRole("button", { name: "Descartar" })).toBeVisible();
      expect(await textosQueNoCaben(page, "[data-novedades]")).toEqual([]);
      await capturar(page, `1-novedades-abiertas-${nombre}`);
      await linea.getByRole("button", { name: "Verlas" }).click();
      const recorrido = page.locator("[data-recorrido]").filter({ visible: true });
      await expect(recorrido).toContainText(/Novedad 1 de \d+/);
      await capturar(page, `1-recorrido-${nombre}`);

      const sin = await context.newPage();
      await entrar(sin, "/", false);
      await expect(sin.locator("[data-boton-ahora] [data-indicador=novedades]")).toHaveCount(0);
      expect(await encimaDeLosBotones(sin)).toEqual([]);
      await capturar(sin, `1-sin-novedades-${nombre}`);
    });

    test(`${nombre}: 2 y 3. menú y cifras con la misma estructura`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/", false);
      if (telefono) {
        await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
        const menu = page.getByRole("dialog", { name: "Menú" });
        await expect(menu).toBeVisible();
        // Las cinco capas caben con holgura, cada una en su casilla.
        const capas = menu.getByRole("group", { name: "Capas" }).getByRole("button");
        await expect(capas).toHaveCount(5);
        const holguras = await capas.evaluateAll((botones) =>
          botones.map((b) => {
            const texto = document.createRange();
            texto.selectNodeContents(b);
            const t = texto.getBoundingClientRect();
            const c = b.getBoundingClientRect();
            return Math.min(t.left - c.left, c.right - t.right);
          }),
        );
        for (const holgura of holguras) expect(holgura).toBeGreaterThanOrEqual(6);
        // «Noche a noche» va en «Más», con el estilo de «En directo».
        const mas = menu.locator("section").filter({ has: page.getByRole("heading", { name: "Más", exact: true }) });
        const noches = mas.getByRole("button", { name: "Noche a noche" });
        await expect(noches).toBeVisible();
        expect(await noches.getAttribute("class")).toBe(await mas.getByRole("button", { name: "En directo" }).getAttribute("class"));
        await expect(menu.locator("section").filter({ has: page.getByRole("heading", { name: "Capas", exact: true }) }).getByRole("button", { name: "Noche a noche" })).toHaveCount(0);
        // Espacios iguales: de lo último de cada sección a su borde, lo mismo en todas.
        const margenes = await menu.locator("section").evaluateAll((secciones) =>
          secciones.map((s) => {
            const ultimo = s.lastElementChild?.getBoundingClientRect();
            return Math.round(s.getBoundingClientRect().bottom - (ultimo?.bottom ?? 0));
          }),
        );
        expect(new Set(margenes).size).toBe(1);
        await capturar(page, `2-menu-${nombre}`);
      }
      // Las cuatro cifras: el número arriba (o a la izquierda en la cabecera) y el texto después,
      // con el marcador de los atribuidos junto al número.
      const cifras = page.locator("dl[aria-label]").filter({ visible: true }).first();
      const estructura = await cifras.evaluate((dl) =>
        [...dl.children].map((par) => {
          const dd = par.querySelector("dd")?.getBoundingClientRect();
          const dt = par.querySelector("dt")?.getBoundingClientRect();
          const marca = par.querySelector("[data-atribuido]")?.getBoundingClientRect();
          return {
            numeroAntes: dd !== undefined && dt !== undefined && (dd.bottom <= dt.top + 1 || dd.right <= dt.left + 1),
            marcaEnElNumero:
              marca === undefined || (dd !== undefined && marca.top >= dd.top - 2 && marca.bottom <= dd.bottom + 2),
          };
        }),
      );
      expect(estructura).toHaveLength(4);
      for (const par of estructura) expect(par).toEqual({ numeroAntes: true, marcaEnElNumero: true });
      await capturar(page, `3-cifras-${nombre}`);
    });

    test(`${nombre}: 5. la leyenda de la presión dice el periodo`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/", false);
      if (telefono) await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
      await page.getByRole("button", { name: "Presión", exact: true }).filter({ visible: true }).click();
      if (telefono) await page.getByRole("button", { name: "Cerrar el menú" }).click();
      // Desde el #98 encender la presión no cambia el periodo: con «Todo», la leyenda lo dice y pide
      // elegir uno para ver la tendencia.
      await expect(page).not.toHaveURL(/ultimos=/);
      await expect(page.locator("[data-periodo-leyenda]").filter({ visible: true })).toHaveText(
        "Incidentes desde el primer dato",
      );
      await expect(page.locator("[data-elige-periodo]").filter({ visible: true })).toHaveText(
        "Elige un periodo para ver la tendencia",
      );
      await capturar(page, `5-presion-${nombre}`);
    });

    test(`${nombre}: 6. ningún nombre de país partido, en los tres zooms iniciales`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/", false);
      const mapa = page.locator(".maplibregl-canvas");
      const caja = await mapa.boundingBox();
      if (caja === null) throw new Error("sin mapa");
      for (let paso = 0; paso < 3; paso += 1) {
        await capturar(page, `6-zoom${paso}-${nombre}`);
        if (telefono) {
          // Doble toque: acerca un nivel.
          await page.touchscreen.tap(caja.x + caja.width / 2, caja.y + caja.height / 2);
          await page.waitForTimeout(80);
          await page.touchscreen.tap(caja.x + caja.width / 2, caja.y + caja.height / 2);
        } else {
          await page.getByRole("button", { name: "Acercar" }).click();
        }
        await page.waitForTimeout(800);
      }
    });

    test(`${nombre}: 7. los drones de la última noche dicen la noche`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/", false);
      const ultima = ultimaNocheConCifra(await ucraniaPublicada(page));
      if (ultima === null || ultima.lanzados === null) throw new Error("sin noche con cifra");
      await page.locator("[data-boton-ahora]").filter({ visible: true }).click();
      const linea = page.locator('[data-cifra="drones"]').filter({ visible: true });
      await expect(linea.locator("[data-numero]")).toHaveText(new Intl.NumberFormat("es").format(ultima.lanzados));
      const antiguo = Date.now() - ultima.fin > 36 * 3_600_000;
      const cuando = jornadaEscrita(ES, ultima.jornada);
      await expect(linea.locator("[data-texto]")).toContainText(antiguo ? `último parte: ${cuando}` : cuando);
      await capturar(page, `7-drones-${nombre}`);
    });

    test(`${nombre}: 7b. «Noche a noche» da la misma cifra que «Europa ahora»`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/", false);
      const noches = nochesDeGuerra(await ucraniaPublicada(page));
      const ultima = ultimaNocheConCifra(await ucraniaPublicada(page));
      const primeroDeOctubre = noches.find(
        (n) => n.jornada.tipo === "noche" && n.jornada.desde === Math.floor(Date.parse("2026-10-01T00:00Z") / MS_POR_DIA),
      );
      if (ultima === null || primeroDeOctubre === undefined) throw new Error("faltan noches");
      // La noche del 1 al 2 de octubre: 108 drones, no los 205 de sumarle el parte de día.
      expect(primeroDeOctubre.lanzados).toBe(108);
      for (const [nombreNoche, noche] of [
        ["1-oct", primeroDeOctubre],
        ["ultima", ultima],
      ] as const) {
        const diaTexto = new Date(noche.jornada.desde * MS_POR_DIA).toISOString().slice(0, 10);
        await page.goto(`/?desde=${diaTexto}&hasta=${diaTexto}`);
        await page.waitForSelector(MAPA_LISTO);
        if (telefono) {
          await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
          await page.getByRole("dialog", { name: "Menú" }).getByRole("button", { name: "Noche a noche" }).click();
        } else {
          await page.getByRole("button", { name: "Noche a noche" }).click();
        }
        // Recorre las noches del día elegido y se queda, en pausa, en la última.
        const panel = page.locator("[data-noche]").filter({ visible: true });
        await expect(panel.getByRole("button", { name: "Reanudar" })).toBeVisible({ timeout: 15_000 });
        await expect(panel).toContainText(jornadaEscrita(ES, noche.jornada, true));
        await expect(panel).toContainText(new Intl.NumberFormat("es").format(noche.lanzados ?? 0));
        await capturar(page, `7b-noche-a-noche-${nombreNoche}-${nombre}`);
      }
    });

    test(`${nombre}: 8. «Últimas 24 horas» cuenta 24 horas y coincide con «En directo»`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      const datos = await resumen(page);
      await entrar(page, "/?ultimos=24h", false);
      const ahora = await page.evaluate(() => Date.now());
      const hoy = Math.floor(ahora / MS_POR_DIA);
      const esperados = datos.incidentes
        .filter((i) =>
          i.inicio !== null ? i.inicio >= ahora - MS_24H && i.inicio <= ahora : i.dia === hoy || i.dia === hoy - 1,
        )
        .map((i) => i.id)
        .sort();
      if (telefono) await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
      const cifra = page.locator("dl[aria-label] dd").filter({ visible: true }).first();
      await expect(cifra).toHaveText(String(esperados.length));
      if (telefono) {
        await page.getByRole("dialog", { name: "Menú" }).getByRole("button", { name: "En directo" }).click();
      } else {
        await page.getByRole("button", { name: "En directo" }).click();
      }
      const enDirecto = await page
        .locator("[data-id]")
        .filter({ visible: true })
        .evaluateAll((entradas) => [...new Set(entradas.map((e) => e.getAttribute("data-id") ?? ""))].sort());
      expect(enDirecto.every((id) => esperados.includes(id))).toBe(true);
      if (esperados.length > 0) expect(enDirecto.length).toBeGreaterThan(0);
      await capturar(page, `8-24h-${nombre}`);
    });
  });
}
