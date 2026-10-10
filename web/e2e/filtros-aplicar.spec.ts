// Filtros: lo elegido se ve en claro y «Aplicar» cierra el panel y encuadra lo que queda a la
// vista, en 360 × 800, 768 × 1024, 1366 × 768 y 1920 × 1080. Casos: un país, solo la capa de
// Ucrania, sin resultados (el mapa no se mueve y se avisa) y sin filtros. Cerrar con la equis o
// con Escape no mueve el mapa; tras aplicar, el foco vuelve a «Filtros»; el panel tiene una sola
// barra de desplazamiento. Deja capturas en docs/capturas/filtros (CAPTURAS para otra carpeta).
// Va contra producción por defecto; con BASE=http://localhost:4173, contra el servidor local; con
// BASE=<vista previa> y BYPASS=<clave>, contra una vista previa protegida.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import type { Resumen } from "../src/datos/tipos.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "filtros");
const MAPA = "[data-mapa-listo=true]";
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, tactil: true },
  { nombre: "768x1024", width: 768, height: 1024, tactil: true },
  { nombre: "1366x768", width: 1366, height: 768, tactil: false },
  { nombre: "1920x1080", width: 1920, height: 1080, tactil: false },
] as const;

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com|tiles\.droneobservatory\.eu/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  // El centro se anota al acabar cada movimiento: se deja empezar y acabar el vuelo.
  await pagina.waitForTimeout(1600);
  let anterior = "";
  for (let i = 0; i < 30; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior) break;
    anterior = ahora;
  }
  return anterior;
}

/** El botón «Filtros» de la disposición que se ve. */
function botonFiltros(pagina: Page) {
  return pagina.locator("[data-botones-mapa] button:visible").first();
}

async function abrir(pagina: Page) {
  await botonFiltros(pagina).click();
  await expect(pagina.locator("[data-filtros]:visible")).toBeVisible();
}

/** Un país con incidentes y otro par (país, estado) sin ninguno. */
async function casos(pagina: Page) {
  const datos = (await (await pagina.request.get("/datos/resumen.json")).json()) as Resumen;
  const cuenta = new Map<string, number>();
  for (const i of datos.incidentes) if (i.punto !== null) cuenta.set(i.pais, (cuenta.get(i.pais) ?? 0) + 1);
  const pais = [...cuenta.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "PL";
  const paises = [...new Set(datos.incidentes.map((i) => i.pais))];
  const vacio = paises.find((p) => !datos.incidentes.some((i) => i.pais === p && i.estado === "desmentido"));
  return { pais, vacio };
}

for (const tamano of TAMANOS) {
  test(`aplicar filtros en ${tamano.nombre}`, async ({ browser, baseURL, browserName }, info) => {
    test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
    const contexto = await browser.newContext({
      viewport: { width: tamano.width, height: tamano.height },
      hasTouch: tamano.tactil,
      ...(baseURL === undefined ? {} : { baseURL }),
      // Vista previa protegida: la clave de acceso de Vercel en BYPASS.
      ...(process.env.BYPASS === undefined ? {} : { extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } }),
    });
    await preparar(contexto, baseURL);
    const pagina = await contexto.newPage();
    const { pais, vacio } = await casos(pagina);
    await pagina.goto("/", { waitUntil: "domcontentloaded" });
    await pagina.locator(MAPA).waitFor({ timeout: 60_000 });
    const inicial = await vista(pagina);

    // Selección clara: lo pulsado en claro con texto oscuro.
    await abrir(pagina);
    const filtros = pagina.locator("[data-filtros]:visible");
    const confirmado = filtros.locator("button[aria-pressed]").nth(1);
    await confirmado.click();
    await expect(confirmado).toHaveAttribute("aria-pressed", "true");
    // Fuera del puntero (el «hover» lo aclara aún más) y pasada la transición.
    await pagina.mouse.move(1, 1);
    await expect
      .poll(() => confirmado.evaluate((e) => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]))
      .toEqual(["rgb(244, 247, 251)", "rgb(6, 10, 18)"]);
    // Una sola barra: el panel en sí no desplaza, solo su contenido; «Aplicar» a la vista.
    const aplicar = pagina.locator("[data-aplicar]:visible");
    await expect(aplicar).toBeInViewport({ ratio: 1 });
    const desplazables = await pagina.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("[data-filtros]")]
        .filter((f) => f.offsetParent !== null)
        .flatMap((f) => {
          const lista: string[] = [];
          for (let e: HTMLElement | null = f; e !== null && e !== document.body; e = e.parentElement) {
            const estilo = getComputedStyle(e);
            if (/(auto|scroll)/.test(estilo.overflowY) && e.scrollHeight > e.clientHeight + 1) lista.push(e.className);
          }
          return lista;
        }),
    );
    expect(desplazables.length).toBeLessThanOrEqual(1);
    await filtros.locator("button[aria-pressed]").nth(1).click();

    // La equis y Escape no mueven el mapa.
    await pagina.getByRole("button", { name: /Cerrar los filtros/ }).locator("visible=true").click();
    expect(await vista(pagina)).toBe(inicial);
    await abrir(pagina);
    await pagina.keyboard.press("Escape");
    await expect(pagina.locator("[data-filtros]:visible")).toHaveCount(0);
    expect(await vista(pagina)).toBe(inicial);

    // Un país: encuadra, cierra y devuelve el foco a «Filtros».
    await abrir(pagina);
    await pagina.locator("[data-filtros]:visible select").last().selectOption(pais);
    await expect(pagina.locator("[data-filtros]:visible select").last()).toHaveAttribute("data-activo", "");
    await expect
      .poll(() => pagina.locator("[data-filtros]:visible select").last().evaluate((e) => getComputedStyle(e).color))
      .toBe("rgb(6, 10, 18)");
    if (tamano.nombre === "360x800") await pagina.screenshot({ path: join(CAPTURAS, `despues-panel-${tamano.nombre}.png`) });
    // Con el teclado: Tab hasta «Aplicar» y Espacio.
    await pagina.locator("[data-aplicar]:visible").focus();
    await pagina.keyboard.press("Space");
    await expect(pagina.locator("[data-filtros]:visible")).toHaveCount(0);
    const trasPais = await vista(pagina);
    expect(trasPais).not.toBe(inicial);
    expect(Number(trasPais.split("|")[1])).toBeLessThanOrEqual(8.0001);
    expect(await botonFiltros(pagina).evaluate((e) => e === document.activeElement)).toBe(true);
    await pagina.screenshot({ path: join(CAPTURAS, `despues-mapa-pais-${tamano.nombre}.png`) });

    // Sin resultados: el mapa no se mueve y aparece el aviso.
    if (vacio !== undefined) {
      await pagina.goto(`/?pais=${vacio}&estado=desmentido`, { waitUntil: "domcontentloaded" });
      await pagina.locator(MAPA).waitFor({ timeout: 60_000 });
      const antes = await vista(pagina);
      await abrir(pagina);
      await pagina.locator("[data-aplicar]:visible").click();
      await expect(pagina.locator("[data-sin-resultados]")).toBeVisible();
      await expect(pagina.locator("[data-sin-resultados]")).toHaveText(/Ningún resultado con estos filtros/);
      expect(await vista(pagina)).toBe(antes);
      await pagina.screenshot({ path: join(CAPTURAS, `despues-sin-resultados-${tamano.nombre}.png`) });

      // Lo mismo con la capa de Ucrania encendida: queda solo ella y se encuadra lo que dibuja
      // (Ucrania y las regiones de Rusia atacadas), no Europa.
      await pagina.locator("body").press("2");
      await pagina.waitForTimeout(2500);
      await abrir(pagina);
      await pagina.locator("[data-aplicar]:visible").click();
      const trasUcrania = await vista(pagina);
      const [lon = 0, lat = 0] = (trasUcrania.split("|")[0] ?? "").split(",").map(Number);
      expect(lon).toBeGreaterThan(22);
      expect(lon).toBeLessThan(70);
      expect(lat).toBeGreaterThan(43);
      expect(lat).toBeLessThan(62);
      await pagina.screenshot({ path: join(CAPTURAS, `despues-solo-ucrania-${tamano.nombre}.png`) });
    }

    // Sin filtros: encuadra todo lo que se ve.
    await pagina.goto("/", { waitUntil: "domcontentloaded" });
    await pagina.locator(MAPA).waitFor({ timeout: 60_000 });
    await vista(pagina);
    await abrir(pagina);
    await pagina.locator("[data-aplicar]:visible").click();
    await expect(pagina.locator("[data-sin-resultados]")).toHaveCount(0);
    await pagina.screenshot({ path: join(CAPTURAS, `despues-sin-filtros-${tamano.nombre}.png`) });
    await contexto.close();
  });
}
