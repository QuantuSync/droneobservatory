import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import type { Resumen, ResumenUcrania } from "../src/datos/tipos.ts";
import { numero as formatear } from "../src/i18n/index.ts";
import { OBJETO_ESTADO, ORIGEN_ALMACEN, urlDelAlmacen } from "../src/almacenPublico.ts";
import { RUTA_SECURITY_TXT } from "../src/seguridad/securityTxt.ts";
import { CONTACTO_SEGURIDAD, DESCARGAS, NOMBRE } from "../src/sitio.ts";
import { directo, indiceGnss } from "../tests/ejemplos-europa.ts";

/** Las capturas quedan fuera de git, en data/capturas. */
const CAPTURAS = join(import.meta.dirname, "..", "..", "data", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const ESTADOS_DE_FRESCURA = ["al_dia", "con_retraso", "desactualizado"];
/** Lo que tarda el mapa en volar a una ficha, con margen. */
const MS_DE_VUELO = 2000;
/** Tiempo para que el mapa termine de pintar teselas antes de una captura. */
const MS_DE_ASENTAMIENTO = 2500;
/** Por encima de esta croma un color ya no es un gris: solo pueden serlo los de estado. */
const CROMA_DE_UN_GRIS = 0.2;

/** El estado de la recogida que publica el servidor; en local no existe. */
const ESTADO_PUBLICADO = urlDelAlmacen(OBJETO_ESTADO);

/** Una cifra como la escribe el marcador en español. */
function numero(n: number): string {
  return formatear(n, "es");
}


/**
 * Las vistas previas de Vercel van protegidas: el acceso para pruebas automatizadas va en
 * una cabecera, con la clave en la variable VERCEL_BYPASS (nunca en el repositorio). Solo se
 * añade a las peticiones al propio sitio: las teselas no la admiten en su política CORS.
 */
const ACCESO: Record<string, string> =
  process.env.VERCEL_BYPASS === undefined
    ? {}
    : { "x-vercel-protection-bypass": process.env.VERCEL_BYPASS };

test.beforeEach(async ({ page, baseURL }) => {
  // En local, el almacén público no admite el origen (su CORS es el del sitio publicado): sus
  // ficheros se sirven aquí, estado.json sin publicar y la detección en directo sin avisos.
  if (baseURL?.includes("localhost") === true) {
    const cors = { "access-control-allow-origin": "*" };
    await page.route(`${ORIGEN_ALMACEN}/**`, (ruta) => {
      const camino = new URL(ruta.request().url()).pathname;
      if (camino.endsWith("/directo.json")) {
        return ruta.fulfill({ status: 200, headers: cors, contentType: "application/json", body: JSON.stringify(directo([])) });
      }
      if (camino.endsWith("/gnss/indice.json")) {
        return ruta.fulfill({ status: 200, headers: cors, contentType: "application/json", body: JSON.stringify(indiceGnss([])) });
      }
      return ruta.fulfill({ status: 404, headers: cors, body: "" });
    });
  }
  if (Object.keys(ACCESO).length === 0 || baseURL === undefined) return;
  const propio = new URL(baseURL).origin;
  await page.route(
    (url) => url.origin === propio,
    (ruta) => ruta.continue({ headers: { ...ruta.request().headers(), ...ACCESO } }),
  );
});

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
  const respuesta = await pagina.request.get(ruta, { headers: ACCESO });
  expect(respuesta.ok()).toBe(true);
  return (await respuesta.json()) as T;
}

/** En el teléfono casi todo está en el menú: lo abre si hace falta y devuelve cómo cerrarlo. */
async function menu(pagina: Page, proyecto: string): Promise<() => Promise<void>> {
  if (proyecto !== "movil") return async () => undefined;
  await pagina.getByRole("banner").getByRole("button", { name: /^(Menú|Menu)$/ }).click();
  const dialogo = pagina.getByRole("dialog", { name: /^(Menú|Menu)$/ });
  await expect(dialogo).toBeVisible();
  return async () => {
    if (await dialogo.isVisible()) await dialogo.getByRole("button", { name: /^(Cerrar el menú|Close the menu)$/ }).click();
  };
}

test("carga el mapa sin errores ni violaciones de la política de contenido", async ({ page, baseURL }, info) => {
  const problemas = vigilar(page);
  const movil = info.project.name === "movil";
  await page.goto("/");
  await expect(page.locator("h1:visible")).toContainText(NOMBRE);
  await page.waitForSelector(MAPA_LISTO);
  const barra = page.locator("[data-frescura]");
  await expect(barra).toContainText(movil ? /hace|ahora mismo/ : /Actualizado|hace|ahora mismo/);
  expect(ESTADOS_DE_FRESCURA).toContain(await barra.getAttribute("data-frescura"));
  // El marcador cuadra con los ficheros publicados: los del mapa más los de ubicación
  // imprecisa, que no se dibujan como punto pero cuentan.
  const mapa = await datos<{ features: { properties: { estado: { actual: string } } }[] }>(
    page,
    "/datos/incidentes.geojson",
  );
  const imprecisos = await datos<{ incidentes: { estado: { actual: string } }[] }>(
    page,
    "/datos/incidentes_sin_ubicacion.json",
  );
  const estados = [
    ...mapa.features.map((f) => f.properties.estado.actual),
    ...imprecisos.incidentes.map((i) => i.estado.actual),
  ];
  const cuenta = (estado: string) => estados.filter((e) => e === estado).length;
  const marcador = page.getByLabel("Cifras del periodo elegido");
  await expect(marcador).toContainText(`incidentes${numero(estados.length)}`);
  await expect(marcador).toContainText(`confirmados${numero(cuenta("confirmado"))}`);
  await expect(marcador).toContainText(`atribuidos${numero(cuenta("atribuido"))}`);
  const resumen = await datos<Resumen>(page, "/datos/resumen.json");
  expect(resumen.incidentes.filter((i) => i.punto !== null)).toHaveLength(mapa.features.length);
  await capturar(page, info.project.name, "inicio");
  // La cabecera, a tamaño real (un píxel de pantalla por píxel CSS).
  await page.locator("header:visible").screenshot({
    path: join(CAPTURAS, `${info.project.name}-cabecera.png`),
    scale: "css",
  });
  // Contra el sitio publicado, la antigüedad se mide desde estado.json y su detalle lista
  // cada fuente.
  if (baseURL !== undefined && !baseURL.includes("localhost")) {
    const estado = await page.request.get(ESTADO_PUBLICADO);
    if (estado.ok()) {
      const sistema = (await estado.json()) as { fuentes: unknown[] };
      await expect(barra).toHaveAttribute("data-fuente-frescura", "recogida");
      await barra.getByRole("button").click();
      await expect(barra.locator("li")).toHaveCount(sistema.fuentes.length);
      await capturar(page, info.project.name, "estado");
      await page.keyboard.press("Escape");
    }
  }
  expect(problemas).toEqual([]);
});

test("cambia de capas y reproduce la guerra noche a noche", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  let cerrar = await menu(page, info.project.name);
  const ucrania = page.getByRole("button", { name: "Ucrania", exact: true });
  await ucrania.click();
  await expect(ucrania).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Densidad", exact: true }).click();
  await cerrar();
  await page.keyboard.press("t");
  await expect(page.getByText("Drones lanzados contra Ucrania")).toBeVisible();
  await page.keyboard.press("Escape");
  await capturar(page, info.project.name, "capas");
  cerrar = await menu(page, info.project.name);
  await page.getByRole("button", { name: "Noche a noche" }).click();
  await cerrar();
  const noche = page.getByRole("status").filter({ hasText: /^Noche del / });
  await expect(noche).toBeVisible();
  await noche.getByRole("button", { name: "Pausar" }).click();
  await expect(noche.getByRole("button", { name: "Reanudar" })).toBeVisible();
  await capturar(page, info.project.name, "guerra");
  await noche.getByRole("button", { name: "Detener" }).click();
  await expect(noche).toBeHidden();
  // El panel en directo da acceso a las regiones sin usar el mapa.
  await menu(page, info.project.name);
  await page.getByRole("button", { name: "En directo", exact: true }).click();
  await page.getByRole("tab", { name: "Lista" }).click();
  await page.getByRole("button", { name: "Járkov" }).click();
  await expect(page.getByRole("complementary", { name: /UA-63/ })).toContainText(
    "Ataques en el periodo",
  );
  expect(problemas).toEqual([]);
});

test("la dirección de un incidente abre su ficha en el panel y sobrevive a recargar", async ({ page }, info) => {
  const problemas = vigilar(page);
  const resumen = await datos<Resumen>(page, "/datos/resumen.json");
  const incidente = [...resumen.incidentes].reverse().find((i) => i.punto !== null);
  if (incidente === undefined) throw new Error("no hay incidentes publicados");
  const respuesta = await page.goto(`/${incidente.id}`);
  expect(respuesta?.status()).toBe(200);
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
  // En escritorio, panel lateral pegado al borde derecho y de altura completa bajo la
  // cabecera; en el teléfono, hoja inferior a todo lo ancho.
  const caja = await ficha.boundingBox();
  const ventana = page.viewportSize();
  if (caja === null || ventana === null) throw new Error("sin medidas");
  if (info.project.name === "movil") {
    expect(Math.round(caja.width)).toBe(ventana.width);
    expect(Math.round(caja.y + caja.height)).toBe(ventana.height);
  } else {
    expect(Math.round(caja.x + caja.width)).toBe(ventana.width);
    expect(Math.round(caja.y + caja.height)).toBe(ventana.height);
  }
  await expect(page.locator("line")).toHaveCount(0);
  await capturar(page, info.project.name, "ficha");
  await page.reload();
  await expect(page.getByRole("complementary", { name: new RegExp(incidente.id) })).toContainText(
    incidente.titulo.es,
  );
  for (const enlace of await ficha.locator('a[href^="http"]').all()) {
    await expect(enlace).toHaveAttribute("target", "_blank");
    await expect(enlace).toHaveAttribute("rel", "noopener noreferrer");
  }
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/$/);
  expect(problemas).toEqual([]);
});

test("en escritorio el letrero nunca se sale de la pantalla y desaparece al abrir la ficha", async ({ page }, info) => {
  test.skip(info.project.name !== "escritorio", "con el dedo no hay letrero: se comprueba en hoja.spec.ts");
  const problemas = vigilar(page);
  await page.goto("/EODI-2025-00247");
  await page.waitForSelector(MAPA_LISTO);
  const ficha = page.getByRole("complementary", { name: /EODI-2025-00247/ });
  await expect(ficha).toBeVisible();
  await page.waitForTimeout(MS_DE_VUELO);
  // El mapa ha volado al incidente: queda en el centro del hueco libre.
  const arriba = await page.locator("header").first().boundingBox();
  // Arriba, lo que tapa el mapa acaba en la franja «Europa ahora», bajo los filtros.
  const filtros = await page.locator('[data-europa-ahora="franja"]').boundingBox();
  // Abajo, lo que tapa el mapa empieza en la fila del zoom y las atribuciones.
  const abajo = await page.getByRole("group", { name: "Zoom" }).boundingBox();
  const panel = await ficha.boundingBox();
  if (arriba === null || filtros === null || abajo === null || panel === null) throw new Error("sin medidas");
  const simbolo = { x: panel.x / 2, y: (filtros.y + filtros.height + abajo.y) / 2 };
  await page.keyboard.press("Escape");
  await expect(ficha).toBeHidden();
  const letrero = page.locator("[data-letrero]");
  const dentro = async () => {
    const caja = await letrero.boundingBox();
    const ventana = page.viewportSize();
    if (caja === null || ventana === null) throw new Error("sin letrero");
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(ventana.width);
    expect(caja.y + caja.height).toBeLessThanOrEqual(ventana.height);
    // Dos líneas como máximo: el texto largo se recorta.
    const lineas = await letrero.evaluate((e) => e.clientHeight / parseFloat(getComputedStyle(e).lineHeight));
    expect(lineas).toBeLessThanOrEqual(2 + 0.75);
  };
  await page.mouse.move(simbolo.x, simbolo.y);
  await expect(letrero).toBeVisible();
  await dentro();
  // Con el símbolo pegado al borde derecho, el letrero se recoloca a su izquierda.
  const ventana = page.viewportSize();
  if (ventana === null) throw new Error("sin ventana");
  const destino = { x: ventana.width - 12, y: simbolo.y };
  await page.mouse.move(simbolo.x + 30, simbolo.y);
  await page.mouse.down();
  await page.mouse.move(destino.x + 30, destino.y, { steps: 20 });
  await page.mouse.up();
  await page.waitForTimeout(MS_DE_ASENTAMIENTO);
  await page.mouse.move(destino.x - 1, destino.y);
  await page.mouse.move(destino.x, destino.y);
  await expect(letrero).toBeVisible();
  await dentro();
  await capturar(page, info.project.name, "letrero-borde");
  // Al abrir la ficha, el letrero desaparece.
  await page.mouse.click(destino.x, destino.y);
  await expect(page.getByRole("complementary", { name: /EODI-|incidentes en este/ })).toBeVisible();
  await expect(letrero).toBeHidden();
  expect(problemas).toEqual([]);
});

test("la dirección de un ataque de Ucrania abre su ficha", async ({ page }, info) => {
  const problemas = vigilar(page);
  const ucrania = await datos<ResumenUcrania>(page, "/datos/ucrania-resumen.json");
  const ataque = ucrania.ataques[ucrania.ataques.length - 1];
  if (ataque === undefined) throw new Error("no hay ataques publicados");
  await page.goto(`/en/${ataque[0]}`);
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    "https://droneobservatory.eu/compartir-en.png",
  );
  const ficha = page.getByRole("complementary", { name: new RegExp(ataque[0]) });
  await expect(ficha.getByRole("heading", { name: ataque[0] })).toBeVisible();
  await expect(ficha).toContainText("Figures from one of the warring parties");
  // En el teléfono las capas están en el menú, cerrado: el botón existe aunque no se vea.
  await expect(page.getByRole("button", { name: "Ukraine", exact: true, includeHidden: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.waitForSelector(MAPA_LISTO);
  await capturar(page, info.project.name, "ataque");
  expect(problemas).toEqual([]);
});

test("la línea de tiempo acota el periodo, atrás lo deshace y «Ver todo» vuelve a todo", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  const contadores = page.getByLabel("Cifras del periodo elegido");
  const todos = await contadores.textContent();
  await page.keyboard.press("t");
  await page.getByRole("radio", { name: "Mes" }).click();
  const fin = page.getByRole("slider", { name: "Fin del periodo" });
  await fin.focus();
  for (let i = 0; i < 6; i += 1) await page.keyboard.press("ArrowLeft");
  await expect(contadores).not.toHaveText(todos ?? "");
  await expect(page).toHaveURL(/\?desde=\d{4}-\d{2}-\d{2}&hasta=\d{4}-\d{2}-\d{2}$/);
  const verTodo = page.getByRole("button", { name: "Ver todo" }).first();
  await expect(verTodo).toBeVisible();
  await capturar(page, info.project.name, "periodo");
  // El botón atrás deshace el cambio de periodo; adelante lo rehace.
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(contadores).toHaveText(todos ?? "");
  await page.goForward();
  await expect(page).toHaveURL(/\?desde=/);
  await expect(contadores).not.toHaveText(todos ?? "");
  await verTodo.click();
  await expect(page).toHaveURL(/\/$/);
  await expect(contadores).toHaveText(todos ?? "");
  await expect(page.getByRole("button", { name: "Ver todo" })).toHaveCount(0);
  await capturar(page, info.project.name, "ver-todo");
  // Reproducir, pausar y detener: al detener vuelve al periodo de antes (el completo).
  await page.getByRole("button", { name: "Reproducir" }).click();
  await page.getByRole("button", { name: "Pausar" }).click();
  await expect(page.getByRole("button", { name: "Reanudar" })).toBeVisible();
  await expect(contadores).not.toHaveText(todos ?? "");
  await page.getByRole("button", { name: "Detener" }).click();
  await expect(contadores).toHaveText(todos ?? "");
  expect(problemas).toEqual([]);
});

test("los filtros quedan en la dirección y el feed abre fichas", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  let cerrar = await menu(page, info.project.name);
  const filtros = page.getByRole("group", { name: "Filtros" });
  await expect(filtros).toBeVisible();
  await filtros.getByRole("button", { name: "Confirmado" }).click();
  await filtros.getByRole("button", { name: "Atribuido" }).click();
  await expect(page).toHaveURL(/\?solo=graves$/);
  await expect(filtros.getByRole("button", { name: "Quitar filtros" })).toBeVisible();
  await capturar(page, info.project.name, "filtros");
  const resumen = await datos<Resumen>(page, "/datos/resumen.json");
  const graves = resumen.incidentes.filter((i) => ["confirmado", "atribuido"].includes(i.estado));
  await expect(page.getByLabel("Cifras del periodo elegido")).toContainText(
    `incidentes${numero(graves.length)}`,
  );
  await page.getByRole("button", { name: "En directo", exact: true }).click();
  await cerrar();
  const feed = page.getByRole("complementary", { name: "En directo" });
  await expect(feed.getByRole("listitem").first()).toBeVisible();
  await capturar(page, info.project.name, "feed");
  await feed.getByRole("listitem").first().getByRole("button").click();
  await expect(page).toHaveURL(/\/EODI-\d{4}-\d{5}\?solo=graves$/);
  // La dirección filtrada se puede compartir: al abrirla, el filtro sigue puesto.
  await page.goto("/?solo=graves");
  cerrar = await menu(page, info.project.name);
  await expect(page.getByRole("group", { name: "Filtros" }).getByRole("button", { name: "Confirmado" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await cerrar();
  expect(problemas).toEqual([]);
});

test("cambia de idioma sin perder la pantalla", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await menu(page, info.project.name);
  await page.getByRole("link", { name: "English version" }).click();
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("[data-frescura]")).toContainText(/Updated|ago|just now/);
  await expect(page.locator("h1:visible")).toContainText(NOMBRE);
  await capturar(page, info.project.name, "ingles");
  const respuesta = await page.request.get("/en", { headers: ACCESO });
  expect(await respuesta.text()).toContain('<html lang="en"');
  expect(problemas).toEqual([]);
});

test("la ayuda y la metodología se abren sin salir de la pantalla", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await menu(page, info.project.name);
  await page.getByRole("button", { name: "Ayuda", exact: true }).click();
  const ayuda = page.getByRole("dialog", { name: "Cómo leer el mapa" });
  await expect(ayuda).toContainText("Atajos de teclado");
  await capturar(page, info.project.name, "ayuda");
  await page.keyboard.press("Escape");
  await expect(ayuda).toBeHidden();
  await menu(page, info.project.name);
  await page.getByRole("button", { name: "Metodología y datos abiertos" }).click();
  const panel = page.getByRole("dialog", { name: "Metodología" });
  await expect(panel).toContainText("extracción automática validada por reglas");
  await expect(panel).toContainText("Cita recomendada");
  // El logo completo, en WebP con PNG de respaldo, nunca el original de 1,3 MB.
  await expect(panel.locator('picture source[type="image/webp"]')).toHaveAttribute("srcset", /logo-96\.webp/);
  await capturar(page, info.project.name, "metodologia");
  for (const ruta of [
    DESCARGAS.incidentesGeojson,
    DESCARGAS.incidentesCsv,
    DESCARGAS.ucraniaJson,
    DESCARGAS.ucraniaCsv,
  ]) {
    await expect(panel.locator(`a[href="${ruta}"]`)).toBeVisible();
    expect((await page.request.head(ruta, { headers: ACCESO })).status(), ruta).toBe(200);
  }
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  expect(problemas).toEqual([]);
});

test("la interfaz no lleva color propio: solo el de los estados", async ({ page }, info) => {
  const problemas = vigilar(page);
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await menu(page, info.project.name);
  // Todo color saturado de un elemento de la interfaz (texto, fondo o borde) tiene que ser uno
  // de los de estado. El mapa, el logo y los gráficos van aparte.
  const saturados = await page.evaluate((CROMA_MAXIMA) => {
    const encontrados = new Set<string>();
    // Croma: cuánto se aparta el color del gris. Los grises azulados de la interfaz no pasan
    // de 0,13; los de estado rondan 0,42 y el cian de antes llegaba a 0,82.
    const croma = (texto: string) => {
      const [r, g, b] = (texto.match(/\d+(\.\d+)?/g) ?? []).map(Number);
      if (r === undefined || g === undefined || b === undefined) return 0;
      return (Math.max(r, g, b) - Math.min(r, g, b)) / 255;
    };
    for (const elemento of document.querySelectorAll<HTMLElement>("body *")) {
      if (elemento.closest("svg, canvas, picture, .maplibregl-map") !== null || elemento.tagName === "IMG") continue;
      if (elemento.offsetParent === null) continue;
      const estilo = getComputedStyle(elemento);
      for (const color of [estilo.color, estilo.backgroundColor, estilo.borderTopColor]) {
        if (!color.startsWith("rgba(0, 0, 0, 0)") && croma(color) > CROMA_MAXIMA) encontrados.add(color);
      }
    }
    return [...encontrados];
  }, CROMA_DE_UN_GRIS);
  const estados = ["rgb(86, 194, 113)", "rgb(237, 169, 58)", "rgb(242, 92, 79)"];
  expect(saturados.filter((color) => !estados.includes(color))).toEqual([]);
  await capturar(page, info.project.name, "sin-acento");
  expect(problemas).toEqual([]);
});

test("los iconos y las imágenes de compartir se sirven y el logo original no", async ({ page }) => {
  const tipos: Record<string, string> = {
    "/favicon.ico": "image/",
    "/favicon.svg": "image/svg+xml",
    "/apple-touch-icon.png": "image/png",
    "/iconos/icono-192.png": "image/png",
    "/iconos/icono-512.png": "image/png",
    "/iconos/icono-maskable-512.png": "image/png",
    "/manifest.webmanifest": "application/manifest+json",
    "/marca/eodi-simplificado.svg": "image/svg+xml",
    "/marca/logo-96.webp": "image/webp",
    "/compartir.png": "image/png",
    "/compartir-en.png": "image/png",
  };
  for (const [ruta, tipo] of Object.entries(tipos)) {
    const respuesta = await page.request.get(ruta, { headers: ACCESO });
    expect(respuesta.status(), ruta).toBe(200);
    expect(respuesta.headers()["content-type"], ruta).toContain(tipo);
  }
  const manifiesto = (await (await page.request.get("/manifest.webmanifest", { headers: ACCESO })).json()) as {
    icons: { purpose?: string }[];
  };
  expect(manifiesto.icons.some((icono) => icono.purpose === "maskable")).toBe(true);
  expect((await page.request.get("/marca/logo_eodi_original.png", { headers: ACCESO })).status()).toBe(404);
});

test("todas las rutas llevan las cabeceras de seguridad", async ({ page }) => {
  for (const ruta of ["/", "/en", "/datos/resumen.json", RUTA_SECURITY_TXT]) {
    const cabeceras = (await page.request.get(ruta, { headers: ACCESO })).headers();
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
  const texto = await (await page.request.get(RUTA_SECURITY_TXT, { headers: ACCESO })).text();
  expect(texto).toContain(`Contact: mailto:${CONTACTO_SEGURIDAD}`);
  expect(texto).toMatch(/Expires: \d{4}-\d{2}-\d{2}T/);
});

test("el mapa solo habla con este sitio y con el almacén público", async ({ page }) => {
  const origenes = new Set<string>();
  page.on("request", (peticion) => origenes.add(new URL(peticion.url()).origin));
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  await page.waitForTimeout(MS_DE_ASENTAMIENTO);
  const propio = new URL(page.url()).origin;
  const ajenos = [...origenes].filter(
    (origen) => origen !== propio && origen !== ORIGEN_ALMACEN,
  );
  expect(ajenos).toEqual([]);
});
