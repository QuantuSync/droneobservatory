import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import type { Resumen, ResumenUcrania } from "../src/datos/tipos.ts";
import { RUTA_SECURITY_TXT } from "../src/seguridad/securityTxt.ts";
import { CONTACTO_SEGURIDAD, DESCARGAS, NOMBRE } from "../src/sitio.ts";

/** Las capturas quedan fuera de git, en data/capturas. */
const CAPTURAS = join(import.meta.dirname, "..", "..", "data", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const ESTADOS_DE_FRESCURA = ["al_dia", "con_retraso", "desactualizado"];
/** Tiempo para que el mapa termine de pintar teselas antes de una captura. */
const MS_DE_ASENTAMIENTO = 2500;

/** Anota los errores de consola y las violaciones de la política de contenido. */
function vigilar(pagina: Page): string[] {
  const problemas: string[] = [];
  // Mientras la recogida no publique estado.json, el navegador anota su 404 en la consola;
  // la web lo sabe llevar (vuelve a medir desde el cambio de datos) y no cuenta como fallo.
  let estadoSinPublicar = 0;
  pagina.on("response", (respuesta) => {
    if (respuesta.url().endsWith("/estado.json") && respuesta.status() === 404) {
      estadoSinPublicar += 1;
    }
  });
  pagina.on("console", (mensaje) => {
    if (mensaje.type() !== "error") return;
    if (estadoSinPublicar > 0 && mensaje.text().includes("status of 404")) {
      estadoSinPublicar -= 1;
      return;
    }
    problemas.push(mensaje.text());
  });
  pagina.on("pageerror", (error) => problemas.push(error.message));
  return problemas;
}

async function capturar(pagina: Page, proyecto: string, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await pagina.screenshot({ path: join(CAPTURAS, `${proyecto}-${nombre}.png`) });
}

async function datos<T>(pagina: Page, ruta: string): Promise<T> {
  const respuesta = await pagina.request.get(ruta);
  expect(respuesta.ok()).toBe(true);
  return (await respuesta.json()) as T;
}

test("carga el mapa sin errores ni violaciones de la política de contenido", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await expect(page.locator("h1")).toContainText("EODI");
  await expect(page.locator("h1")).toContainText(NOMBRE);
  await page.waitForSelector(MAPA_LISTO);
  const barra = page.locator("[data-frescura]");
  await expect(barra).toContainText("ACTUALIZADO");
  expect(ESTADOS_DE_FRESCURA).toContain(await barra.getAttribute("data-frescura"));
  const resumen = await datos<Resumen>(page, "/datos/resumen.json");
  await expect(page.getByLabel("Cifras del periodo elegido")).toContainText(
    `Incidentes${resumen.incidentes.length}`,
  );
  await capturar(page, info.project.name, "inicio");
  expect(problemas).toEqual([]);
});

test("cambia de capas: Ucrania y densidad", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await page.getByLabel("Ucrania").check();
  await expect(page.getByText("Drones lanzados contra Ucrania")).toBeVisible();
  await page.getByLabel("Densidad").check();
  await page.getByLabel("Incidentes", { exact: true }).uncheck();
  await capturar(page, info.project.name, "capas");
  // La lista da acceso a las regiones sin usar el mapa.
  await page.getByRole("button", { name: "Lista" }).click();
  await page.getByRole("button", { name: "Járkov" }).click();
  await expect(page.getByRole("complementary", { name: /UA-63/ })).toContainText(
    "Ataques en el periodo",
  );
  await capturar(page, info.project.name, "region");
  expect(problemas).toEqual([]);
});

test("la dirección de un incidente abre su ficha y sobrevive a recargar", async ({ page }, info) => {
  const problemas = vigilar(page);
  const resumen = await datos<Resumen>(page, "/datos/resumen.json");
  const incidente = resumen.incidentes[resumen.incidentes.length - 1];
  if (incidente === undefined) throw new Error("no hay incidentes publicados");
  const respuesta = await page.goto(`/${incidente.id}`);
  expect(respuesta?.status()).toBe(200);
  // La página propia lleva el título del incidente en los metadatos de compartir.
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    `${incidente.titulo.es} · ${NOMBRE}`,
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    "https://droneobservatory.eu/compartir.png",
  );
  const ficha = page.getByRole("complementary", { name: new RegExp(incidente.id) });
  await expect(ficha).toContainText(incidente.titulo.es);
  await expect(ficha.getByRole("heading", { name: "Historial de estados" })).toBeVisible();
  await expect(ficha.getByRole("button", { name: "Copiar enlace" })).toBeVisible();
  await page.waitForSelector(MAPA_LISTO);
  await capturar(page, info.project.name, "ficha");
  await page.reload();
  await expect(page.getByRole("complementary", { name: new RegExp(incidente.id) })).toContainText(
    incidente.titulo.es,
  );
  // Todo enlace a una fuente se abre aparte y sin referencia.
  for (const enlace of await ficha.locator('a[href^="http"]').all()) {
    await expect(enlace).toHaveAttribute("target", "_blank");
    await expect(enlace).toHaveAttribute("rel", "noopener noreferrer");
  }
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/$/);
  expect(problemas).toEqual([]);
});

test("la dirección de un ataque de Ucrania abre su ficha", async ({ page }, info) => {
  const problemas = vigilar(page);
  const ucrania = await datos<ResumenUcrania>(page, "/datos/ucrania-resumen.json");
  const ataque = ucrania.ataques[ucrania.ataques.length - 1];
  if (ataque === undefined) throw new Error("no hay ataques publicados");
  await page.goto(`/en/${ataque[0]}`);
  const ficha = page.getByRole("complementary", { name: new RegExp(ataque[0]) });
  await expect(ficha.getByRole("heading", { name: ataque[0] })).toBeVisible();
  await expect(ficha).toContainText("Figures from one of the warring parties");
  await expect(page.getByRole("checkbox", { name: "Ukraine" })).toBeChecked();
  await page.waitForSelector(MAPA_LISTO);
  await capturar(page, info.project.name, "ataque");
  expect(problemas).toEqual([]);
});

test("la línea de tiempo acota el periodo con el teclado y se reproduce", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  const contadores = page.getByLabel("Cifras del periodo elegido");
  const todos = await contadores.textContent();
  await page.getByRole("radio", { name: "Mes" }).click();
  const fin = page.getByRole("slider", { name: "Fin del periodo" });
  await fin.focus();
  for (let i = 0; i < 6; i += 1) await page.keyboard.press("ArrowLeft");
  await expect(contadores).not.toHaveText(todos ?? "");
  await capturar(page, info.project.name, "periodo");
  await page.getByRole("button", { name: "Reproducir" }).click();
  await expect(page.getByRole("button", { name: "Pausar" })).toBeVisible();
  // Al llegar al último día la reproducción se para sola y el periodo vuelve a ser todo.
  await expect(page.getByRole("button", { name: "Reproducir" })).toBeVisible({ timeout: 30_000 });
  await expect(contadores).toHaveText(todos ?? "");
  expect(problemas).toEqual([]);
});

test("cambia de idioma sin perder la pantalla", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await page.getByRole("link", { name: "Cambiar a inglés" }).click();
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("[data-frescura]")).toContainText("UPDATED");
  await expect(page.locator("h1")).toContainText(NOMBRE);
  await expect(page.getByRole("button", { name: "Methodology" })).toBeVisible();
  await capturar(page, info.project.name, "ingles");
  // La versión inglesa tiene su propia página prerenderizada.
  const respuesta = await page.request.get("/en");
  expect(await respuesta.text()).toContain('<html lang="en"');
  expect(problemas).toEqual([]);
});

test("la metodología se abre como panel y ofrece los datos abiertos", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Metodología" }).click();
  const panel = page.getByRole("dialog", { name: "Metodología" });
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("extracción automática validada por reglas");
  await expect(panel).toContainText("Cita recomendada");
  await expect(panel).toContainText("CC BY 4.0");
  await capturar(page, info.project.name, "metodologia");
  for (const ruta of Object.values(DESCARGAS)) {
    await expect(panel.locator(`a[href="${ruta}"]`)).toBeVisible();
    const respuesta = await page.request.head(ruta);
    expect(respuesta.status(), ruta).toBe(200);
  }
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  expect(problemas).toEqual([]);
});

test("todas las rutas llevan las cabeceras de seguridad", async ({ page }) => {
  for (const ruta of ["/", "/en", "/datos/resumen.json", RUTA_SECURITY_TXT]) {
    const cabeceras = (await page.request.get(ruta)).headers();
    expect(cabeceras["strict-transport-security"], ruta).toBe(
      "max-age=31536000; includeSubDomains; preload",
    );
    expect(cabeceras["x-content-type-options"], ruta).toBe("nosniff");
    expect(cabeceras["referrer-policy"], ruta).toBe("strict-origin-when-cross-origin");
    expect(cabeceras["x-frame-options"], ruta).toBe("DENY");
    expect(cabeceras["permissions-policy"], ruta).toContain("geolocation=()");
    expect(cabeceras["content-security-policy"], ruta).toContain("default-src 'self'");
    expect(cabeceras["content-security-policy"], ruta).not.toContain("unsafe");
    expect(cabeceras["set-cookie"], ruta).toBeUndefined();
  }
  const texto = await (await page.request.get(RUTA_SECURITY_TXT)).text();
  expect(texto).toContain(`Contact: mailto:${CONTACTO_SEGURIDAD}`);
  expect(texto).toMatch(/Expires: \d{4}-\d{2}-\d{2}T/);
});

test("el mapa solo habla con este sitio y con el subdominio de teselas", async ({ page }) => {
  const origenes = new Set<string>();
  page.on("request", (peticion) => origenes.add(new URL(peticion.url()).origin));
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await page.waitForTimeout(MS_DE_ASENTAMIENTO);
  const propio = new URL(page.url()).origin;
  const ajenos = [...origenes].filter(
    (origen) => origen !== propio && origen !== "https://tiles.droneobservatory.eu",
  );
  expect(ajenos).toEqual([]);
});
