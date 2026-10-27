// Copias archivadas de las fuentes, como una persona: abre la ficha de un incidente cuyas fuentes
// tienen copia en Internet Archive, despliega todas las fuentes con un toque (o un clic) y comprueba
// que al lado del original sale «copia archivada» (o, con el original caído, que la copia es el
// enlace principal y se dice), en español y en inglés, en la ficha del mapa y en la página de texto,
// sin errores de consola ni enlaces internos rotos. Elige el incidente de los datos que sirve la web
// (/datos/incidentes.geojson), así vale en producción y con datos de ensayo en local.

import { expect, test } from "./base.ts";
import type { Page } from "@playwright/test";

interface FuenteDatos {
  enlace: string;
  copia_archivada?: { enlace: string; fecha: string };
  enlace_caido?: true;
}
interface Coleccion {
  features: { id: string; properties: { fuentes: FuenteDatos[] } }[];
}

const LOCAL = /localhost|127\.0\.0\.1/.test(process.env.BASE ?? "");
const COPIA = /^https:\/\/web\.archive\.org\/web\/\d{14}\//;
const TEXTOS = {
  es: { copia: "copia archivada", caido: "el original ya no está disponible", prefijo: "" },
  en: { copia: "archived copy", caido: "the original is no longer available", prefijo: "/en" },
};

function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("console", (m) => {
    if (m.type() === "error" && !/ntfy:|intent:/.test(m.text())) errores.push(`consola: ${m.text()}`);
  });
  // En local, el almacén lo sirve una función de Vercel que el servidor local no tiene.
  if (LOCAL) pagina.on("response", (r) => r.url().includes("/almacen/") && r.status() === 404 && errores.push(""));
  pagina.on("pageerror", (e) => errores.push(`excepción: ${e.message}`));
  return errores;
}

async function elegir(pagina: Page): Promise<{ conCopia: string; caido: string | null }> {
  const respuesta = await pagina.request.get("/datos/incidentes.geojson");
  expect(respuesta.ok()).toBe(true);
  const datos = (await respuesta.json()) as Coleccion;
  const conCopia = datos.features.find((f) => f.properties.fuentes.some((x) => x.copia_archivada !== undefined));
  const caido = datos.features.find((f) =>
    f.properties.fuentes.some((x) => x.enlace_caido === true && x.copia_archivada !== undefined),
  );
  if (conCopia === undefined) throw new Error("ningún incidente con copia archivada");
  return { conCopia: conCopia.id, caido: caido?.id ?? null };
}

/** Despliega todas las fuentes de la ficha con el gesto del dispositivo. */
async function verTodas(pagina: Page, tactil: boolean) {
  const mas = pagina.locator("[data-ficha] button[aria-expanded=false]").filter({ hasText: /Ver \d+ más|Show \d+ more/ });
  // Las fuentes llegan con el detalle del incidente, después de abrirse la ficha.
  await expect(pagina.locator("[data-ficha] li").first()).toBeAttached({ timeout: 30_000 });
  if ((await mas.count()) === 0) return;
  await mas.first().scrollIntoViewIfNeeded();
  if (tactil) await mas.first().tap();
  else await mas.first().click();
  await expect(pagina.locator("[data-ficha] button[aria-expanded=true]").first()).toBeVisible();
}

for (const idioma of ["es", "en"] as const) {
  test(`copias archivadas en la ficha y en la página de texto (${idioma})`, async ({ page: pagina, context: contexto }, info) => {
    test.setTimeout(150_000);
    const tactil = info.project.use.hasTouch === true;
    const t = TEXTOS[idioma];
    const errores = vigilar(pagina);
    const { conCopia, caido } = await elegir(pagina);

    // Ficha del mapa.
    await pagina.goto(`${t.prefijo}/${conCopia}`, { waitUntil: "domcontentloaded" });
    await expect(pagina.locator("[data-ficha]:visible").first()).toBeVisible({ timeout: 60_000 });
    await verTodas(pagina, tactil);
    const copias = pagina.locator("[data-ficha] [data-copia-archivada] a, [data-ficha] a[href^='https://web.archive.org/web/']");
    await expect(copias.first()).toBeAttached({ timeout: 30_000 });
    const href = await copias.first().getAttribute("href");
    expect(href ?? "").toMatch(COPIA);
    expect(await pagina.locator("[data-ficha]").first().textContent()).toContain(t.copia);
    // El enlace a la copia se abre fuera, sin dar acceso a esta página.
    expect(await copias.first().getAttribute("rel")).toContain("noopener");
    expect(await copias.first().getAttribute("target")).toBe("_blank");

    if (caido !== null) {
      // En otra pestaña, como quien abre un segundo enlace: la primera sigue cargando el mapa sin
      // cortes (WebKit avisa de las teselas que se cortan al salir a mitad de carga).
      const otra = await contexto.newPage();
      const erroresOtra = vigilar(otra);
      await otra.goto(`${t.prefijo}/${caido}`, { waitUntil: "domcontentloaded" });
      await expect(otra.locator("[data-ficha]:visible").first()).toBeVisible({ timeout: 60_000 });
      await verTodas(otra, tactil);
      const nota = otra.locator("[data-ficha] [data-copia-principal]").first();
      await expect(nota).toBeAttached({ timeout: 30_000 });
      expect(await nota.textContent()).toContain(t.caido);
      await expect(otra.locator("[data-mapa-listo=true]")).toBeAttached({ timeout: 60_000 });
      errores.push(...erroresOtra);
    }

    // Página de texto del incidente (sin código): el mismo enlace y la misma nota.
    const texto = await pagina.request.get(`${t.prefijo}/${conCopia}`);
    const html = await texto.text();
    expect(html).toContain("web.archive.org/web/");
    expect(html).toContain(t.copia);

    // Enlaces internos de la ficha, sin romper.
    const internos = await pagina.evaluate(() =>
      [...new Set([...document.querySelectorAll<HTMLAnchorElement>("a[href^='/']")].map((a) => a.getAttribute("href") ?? ""))]
        .filter((h) => h !== "" && !h.startsWith("//")),
    );
    const rotos: string[] = [];
    for (const ruta of internos.slice(0, 40)) {
      const r = await pagina.request.get(ruta, { maxRedirects: 3 });
      if (r.status() >= 400) rotos.push(`${ruta} ${r.status()}`);
    }
    expect(rotos, "enlaces internos rotos").toEqual([]);
    // Las respuestas 404 del almacén en local dejan su línea de consola; se descuentan.
    const ajenas = errores.filter((e) => e === "").length;
    const reales = errores.filter((e) => e !== "");
    const sin404 = reales.filter((e) => !/status of 404/.test(e));
    expect(sin404).toEqual([]);
    expect(reales.length - sin404.length).toBeLessThanOrEqual(ajenas);
  });
}
