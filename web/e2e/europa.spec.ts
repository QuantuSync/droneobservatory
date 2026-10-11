// «Europa en directo» en un navegador real: panel «Europa ahora», avisos de cierre, capa de
// interferencia GPS y capa de presión por país, en escritorio y en tres teléfonos. Las
// peticiones al almacén público (directo.json y la interferencia) se sirven con ficheros de
// prueba, así que la prueba no depende de lo que haya publicado en ese momento.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { aviso, directo, ficheroGnss, indiceGnss } from "../tests/ejemplos-europa.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "data", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const MS_DE_ASENTAMIENTO = 2500;
const TELEFONOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "390x844", width: 390, height: 844 },
  { nombre: "412x915", width: 412, height: 915 },
];

/** Día de hoy (UTC) como AAAA-MM-DD: el fichero de interferencia de prueba es el de hoy. */
function hoy(): string {
  return new Date().toISOString().slice(0, 10);
}

/** El día anterior a hoy (UTC). */
function ayer(): string {
  return new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);
}

async function servirAlmacen(pagina: Page) {
  const avisos = [
    aviso(),
    aviso({
      id: "EBBR-hoy",
      oaci: "EBBR",
      nombre: "Brussels",
      pais: "BE",
      lat: 50.901,
      lon: 4.484,
      estado: "cierre_confirmado",
      confirmacion: { tipo: "oficial", incidente: null, hora: "2025-11-04T19:20Z" },
      primera_noticia: "2025-11-04T19:12Z",
      ventaja_min: 17,
    }),
  ];
  const json = (cuerpo: unknown) => ({
    status: 200,
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify(cuerpo),
  });
  // Las direcciones del almacén salen de configuracion/almacen_publico.json; aquí basta su final.
  await pagina.route("**/directo.json", (ruta) => ruta.fulfill(json(directo(avisos))));
  // El «hoy» de la web es el último día de los datos publicados, que de madrugada (UTC) aún es
  // el de ayer: la interferencia GPS se sirve para los dos días, cada fichero con el suyo.
  await pagina.route("**/gnss/indice.json", (ruta) => ruta.fulfill(json(indiceGnss([ayer(), hoy()]))));
  await pagina.route("**/gnss/dia/*.json", (ruta) => {
    const dia = /(\d{4}-\d{2}-\d{2})\.json$/.exec(ruta.request().url())?.[1] ?? hoy();
    return ruta.fulfill(json(ficheroGnss(dia)));
  });
}

/** Alfa del primer fondo pintado del elemento o de sus antepasados: 1 si el mapa no se ve a través. */
async function opacidadDelFondo(locator: Locator): Promise<number> {
  return locator.evaluate((elemento) => {
    for (let actual: Element | null = elemento; actual !== null; actual = actual.parentElement) {
      const color = getComputedStyle(actual).backgroundColor;
      const partes = /rgba?\(([^)]+)\)/.exec(color)?.[1]?.split(/[\s,/]+/).filter(Boolean) ?? [];
      const alfa = partes.length === 4 ? Number(partes[3]) : partes.length === 3 ? 1 : 0;
      if (alfa > 0) return alfa;
    }
    return 0;
  });
}

/**
 * Pone un número de cuatro cifras en cada línea de «Europa ahora» y mide sus cajas: el número
 * cabe en su columna y está alineado con los demás, el texto no se sale de la suya ni pisa el
 * número, y las líneas no se montan unas sobre otras. Devuelve los problemas encontrados.
 */
async function medirLineas(pagina: Page, ancho: number): Promise<string[]> {
  return pagina.locator("[data-europa-ahora]").evaluate((lista, ancho) => {
    const problemas: string[] = [];
    const filas = Array.from(lista.querySelectorAll<HTMLElement>("[data-cifra]"));
    if (filas.length !== 5) problemas.push(`${ancho}: ${filas.length} líneas`);
    for (const fila of filas) {
      const numero = fila.querySelector<HTMLElement>("[data-numero]");
      if (numero !== null) numero.textContent = "9,999";
    }
    let derechaNumeros: number | null = null;
    let anterior: DOMRect | null = null;
    for (const fila of filas) {
      const nombre = fila.dataset.cifra ?? "?";
      const numero = fila.querySelector<HTMLElement>("[data-numero]");
      const texto = fila.querySelector<HTMLElement>("[data-texto]");
      if (numero === null || texto === null) {
        problemas.push(`${ancho} ${nombre}: sin número o sin texto`);
        continue;
      }
      const caja = fila.getBoundingClientRect();
      const n = numero.getBoundingClientRect();
      const tx = texto.getBoundingClientRect();
      if (numero.scrollWidth > numero.clientWidth + 0.5) problemas.push(`${ancho} ${nombre}: el número no cabe`);
      if (derechaNumeros === null) derechaNumeros = n.right;
      else if (Math.abs(n.right - derechaNumeros) > 0.5) problemas.push(`${ancho} ${nombre}: número desalineado`);
      if (n.right > tx.left + 0.5) problemas.push(`${ancho} ${nombre}: el número pisa el texto`);
      if (tx.right > caja.right + 0.5 || texto.scrollWidth > texto.clientWidth + 0.5) {
        problemas.push(`${ancho} ${nombre}: el texto se sale de su columna`);
      }
      if (n.bottom > caja.bottom + 0.5 || tx.bottom > caja.bottom + 0.5) problemas.push(`${ancho} ${nombre}: se sale por abajo`);
      if (anterior !== null && caja.top < anterior.bottom - 0.5) problemas.push(`${ancho} ${nombre}: pisa la línea anterior`);
      if (caja.right > window.innerWidth + 0.5 || caja.left < -0.5) problemas.push(`${ancho} ${nombre}: fuera de la pantalla`);
      anterior = caja;
    }
    return problemas;
  }, ancho);
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await pagina.screenshot({ path: join(CAPTURAS, `europa-${nombre}.png`) });
}

test.describe("escritorio", () => {
  test.skip(({ isMobile }) => isMobile, "solo escritorio");

  test("panel, aviso en directo, interferencia GPS y presión por país", async ({ page }) => {
    const errores: string[] = [];
    page.on("pageerror", (error) => errores.push(error.message));
    await servirAlmacen(page);
    await page.goto("/");
    await page.waitForSelector(MAPA_LISTO);
    // Al entrar está cerrado; el botón avisa con el número de cierres en curso.
    await expect(page.locator("[data-europa-ahora]")).toHaveCount(0);
    const boton = page.getByRole("button", { name: /^Europa ahora/ });
    await expect(boton.locator("[data-indicador=cierres]")).toHaveText("2");
    await boton.click();
    const panel = page.getByRole("dialog", { name: "Europa ahora" });
    const cierres = panel.locator('[data-cifra="cierres"]');
    await expect(cierres).toContainText("2");
    await capturar(page, "escritorio-panel");

    await cierres.click();
    const ficha = page.getByRole("complementary", { name: /EBBR/ });
    await expect(ficha).toContainText("Cierre confirmado");
    await expect(ficha).toContainText("17 min antes de la primera noticia");
    await capturar(page, "escritorio-aviso");
    await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();

    await boton.click();
    // El número GPS del panel es el mismo que cuenta la leyenda de la capa para ese día.
    const lineaGnss = page.getByRole("dialog", { name: "Europa ahora" }).locator('[data-cifra="gnss"]');
    const enPanel = (await lineaGnss.locator("[data-numero]").innerText()).trim();
    expect(enPanel).toMatch(/^\d+$/);
    await lineaGnss.click();
    await expect(page.getByRole("button", { name: "GPS", exact: true })).toHaveAttribute("aria-pressed", "true");
    const leyenda = page.locator('[data-leyenda="gnss"]');
    await expect(leyenda).toContainText("1 día con datos");
    await expect(leyenda.locator("[data-zonas-altas]")).toHaveAttribute("data-zonas-altas", enPanel);
    await expect(leyenda.locator("[data-zonas-altas]")).toHaveText(
      `${enPanel} ${enPanel === "1" ? "zona" : "zonas"} con interferencia alta`,
    );
    expect(await opacidadDelFondo(leyenda)).toBe(1);
    await capturar(page, "escritorio-gnss");

    await page.getByRole("button", { name: "GPS", exact: true }).click();
    await page.getByRole("button", { name: "Presión", exact: true }).click();
    await expect(page.locator('[data-leyenda="presion"]')).toBeVisible();
    await page.getByRole("button", { name: "Ver todo" }).click().catch(() => undefined);
    await capturar(page, "escritorio-presion");
    expect(errores).toEqual([]);
  });
});

test.describe("líneas de «Europa ahora»", () => {
  test("cuatro cifras sin desbordes ni solapes, columna de números y fondo opaco", async ({ page, isMobile }) => {
    await servirAlmacen(page);
    const anchos = isMobile
      ? [
          { width: 360, height: 800 },
          { width: 390, height: 844 },
          { width: 412, height: 915 },
        ]
      : [
          { width: 1440, height: 900 },
          { width: 1920, height: 1080 },
          { width: 1024, height: 768 },
        ];
    const problemas: string[] = [];
    for (const tamano of anchos) {
      await page.setViewportSize(tamano);
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO);
      await page.getByRole("button", { name: /^Europa ahora/ }).filter({ visible: true }).click();
      const caja = isMobile
        ? page.getByRole("complementary", { name: "Europa ahora" })
        : page.getByRole("dialog", { name: "Europa ahora" });
      await expect(caja.locator("[data-cifra]")).toHaveCount(5);
      // Columna izquierda: solo números (o la raya si falta un fichero), nunca palabras.
      for (const numero of await caja.locator("[data-numero]").allInnerTexts()) {
        expect(numero.trim()).toMatch(/^([\d.,]+|—)$/);
      }
      expect(await opacidadDelFondo(caja.locator("[data-europa-ahora]"))).toBe(1);
      problemas.push(...(await medirLineas(page, tamano.width)));
      await page.screenshot({ path: join(CAPTURAS, `europa-lineas-${tamano.width}.png`) });
      await page.keyboard.press("Escape");
      // Y el desplegable o la hoja de los filtros, también opacos.
      await page.getByRole("button", { name: /^Abrir los filtros/ }).filter({ visible: true }).click();
      const filtros = page.getByRole("group", { name: "Filtros" }).filter({ visible: true });
      await expect(filtros).toBeVisible();
      expect(await opacidadDelFondo(filtros)).toBe(1);
      await page.keyboard.press("Escape");
    }
    expect(problemas).toEqual([]);
  });
});

// Vilna: quince incidentes en el punto del aeropuerto (un grupo con su número), un confirmado
// suelto a medio kilómetro y, aquí, un aviso de cierre confirmado en el mismo punto del grupo.
const VILNA = { lon: 25.28759, lat: 54.63488 };
const INCIDENTE_DE_VILNA = "EODI-2026-00007";

test.describe("Vilna", () => {
  test("el aviso de cierre es una etiqueta que no tapa el número del grupo", async ({ page, isMobile }) => {
    const errores: string[] = [];
    page.on("pageerror", (error) => errores.push(error.message));
    await servirAlmacen(page);
    const eyvi = aviso({
      id: "EYVI-hoy",
      oaci: "EYVI",
      nombre: "Vilnius",
      pais: "LT",
      lat: VILNA.lat,
      lon: VILNA.lon,
      estado: "cierre_confirmado",
    });
    await page.route("**/directo.json", (ruta) =>
      ruta.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify(directo([eyvi])),
      }),
    );
    if (isMobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/${INCIDENTE_DE_VILNA}`);
    await page.waitForSelector(MAPA_LISTO);
    await page.waitForTimeout(MS_DE_ASENTAMIENTO);
    await page.keyboard.press("Escape");
    // Las etiquetas de aviso están cargadas en el mapa.
    await expect(page.locator("[data-mapa-listo]")).toHaveAttribute("data-iconos", /aviso-cierre_confirmado/);
    await page.screenshot({ path: join(CAPTURAS, `europa-vilna-${isMobile ? "390x844" : "escritorio"}.png`) });
    expect(errores).toEqual([]);
  });
});

test.describe("teléfono", () => {
  test.skip(({ isMobile }) => !isMobile, "solo teléfono");

  for (const tamano of TELEFONOS) {
    test(`${tamano.nombre}: «Europa ahora» se abre en una hoja y lleva a la ficha`, async ({ page }) => {
      await page.setViewportSize({ width: tamano.width, height: tamano.height });
      await servirAlmacen(page);
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO);
      const boton = page.getByRole("button", { name: /^Europa ahora/ }).filter({ visible: true });
      await expect(boton.locator("[data-indicador=cierres]")).toHaveText("2");
      await boton.click();
      const panel = page.getByRole("complementary", { name: "Europa ahora" });
      await expect(panel.locator('[data-cifra="cierres"]')).toContainText("2");
      await capturar(page, `${tamano.nombre}-panel`);
      await panel.locator('[data-cifra="cierres"]').click();
      const hoja = page.getByRole("complementary", { name: /EBBR/ });
      await expect(hoja).toContainText("Cierre confirmado");
      // Pulsar una cifra cierra «Europa ahora» y abre la ficha; con una hoja abierta, los
      // botones sobre el mapa no se pintan, así que nada tapa la hoja.
      await expect(panel).toBeHidden();
      await expect(page.locator("[data-botones-mapa]:visible")).toHaveCount(0);
      await capturar(page, `${tamano.nombre}-aviso`);
    });
  }
});

test.describe("pulso de las novedades", () => {
  test("solo laten las novedades desde la última visita y se apagan al descartarlas", async ({ page }) => {
    // Primera visita: no hay visita anterior y no late nada.
    await page.goto("/");
    await page.waitForSelector(MAPA_LISTO);
    await page.waitForTimeout(MS_DE_ASENTAMIENTO);
    await expect(page.locator(".pulso")).toHaveCount(0);

    // Con una visita anterior de hace un mes, laten las novedades (y solo ellas).
    await page.evaluate(() => {
      const hace = new Date(Date.now() - 30 * 86400 * 1000).toISOString();
      window.localStorage.setItem("eodi.ultima-visita", hace);
    });
    await page.reload();
    await page.waitForSelector(MAPA_LISTO);
    await page.waitForTimeout(MS_DE_ASENTAMIENTO);
    // Desde el #87 el aviso va dentro de «Europa ahora»; el botón lleva la cuenta.
    await page.locator("[data-boton-ahora]:visible").first().click();
    const aviso = page.getByRole("status").filter({ hasText: /novedad/ });
    await expect(aviso).toBeVisible();
    expect(await page.locator(".pulso").count()).toBeGreaterThan(0);
    await aviso.getByRole("button", { name: "Descartar" }).click();
    await expect(page.locator(".pulso")).toHaveCount(0);
  });
});
