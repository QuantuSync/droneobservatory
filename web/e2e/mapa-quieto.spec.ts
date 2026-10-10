// Cerrar una ficha nunca mueve el mapa, en el teléfono (390 × 844, con tacto) y en escritorio.
// Se abre un incidente aislado de Bélgica por su enlace (el mapa va a él), se cierra y, con esa
// vista guardada, se abre tocando su marcador y se cierra de cada forma posible: la equis, tocar
// fuera, la tecla Escape y, en el teléfono, arrastrar la hoja hacia abajo. El centro y el zoom
// tienen que ser los de antes. Lo mismo con la capa «Ucrania» y con «Corredores» y «Con
// satélite», y abriendo y cerrando diez fichas seguidas. Deja capturas de antes y después en
// docs/capturas (CAPTURAS para otra carpeta). Va contra producción por defecto; con
// BASE=http://localhost:4173, contra el servidor local.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import type { IncidenteResumen, Resumen } from "../src/datos/tipos.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas");
const MAPA = "[data-mapa-listo=true]";
const TELEFONO = { nombre: "390x844", width: 390, height: 844 };
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
/** Distancia mínima a cualquier otro incidente: su marcador no se agrupa ni se pisa. */
const AISLADO_KM = 25;
const TOLERANCIA_GRADOS = 1e-5;
const TOLERANCIA_ZOOM = 1e-3;

interface Vista {
  lon: number;
  lat: number;
  zoom: number;
}

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com|tiles\.droneobservatory\.eu/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

function km(a: { lon: number; lat: number }, b: { lon: number; lat: number }) {
  const x = (a.lon - b.lon) * Math.cos(((a.lat + b.lat) / 2) * (Math.PI / 180));
  return Math.hypot(x, a.lat - b.lat) * 111.2;
}

/** Un incidente de Bélgica con punto, lejos de todos los demás. */
async function aislado(pagina: Page): Promise<IncidenteResumen> {
  const datos = (await (await pagina.request.get("/datos/resumen.json")).json()) as Resumen;
  const conPunto = datos.incidentes.filter((i) => i.punto !== null);
  const elegido = conPunto.find((i) => {
    const punto = i.punto;
    return (
      i.pais === "BE" &&
      punto !== null &&
      conPunto.every((otro) => otro.id === i.id || otro.punto === null || km(otro.punto, punto) > AISLADO_KM)
    );
  });
  if (elegido === undefined) throw new Error("ningún incidente aislado en Bélgica");
  return elegido;
}

/** La vista cuando el mapa deja de moverse (el centro no cambia en un segundo). */
async function asentada(pagina: Page): Promise<Vista> {
  const mapa = pagina.locator(MAPA);
  let anterior = "";
  for (let i = 0; i < 40; i += 1) {
    await pagina.waitForTimeout(500);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior && !ahora.includes("null")) break;
    anterior = ahora;
  }
  const [lon = Number.NaN, lat = Number.NaN] = ((await mapa.getAttribute("data-centro")) ?? "").split(",").map(Number);
  return { lon, lat, zoom: Number(await mapa.getAttribute("data-zoom")) };
}

/** La vista cuando el mapa ha llegado al incidente (el vuelo empieza un poco después de abrir). */
async function llegada(pagina: Page, incidente: IncidenteResumen): Promise<Vista> {
  const punto = incidente.punto;
  if (punto === null) throw new Error("sin punto");
  await expect
    .poll(async () => {
      const [lon = Number.NaN, lat = Number.NaN] = ((await pagina.locator(MAPA).getAttribute("data-centro")) ?? "")
        .split(",")
        .map(Number);
      return Math.abs(lon - punto.lon) < 1 && Math.abs(lat - punto.lat) < 1;
    }, { timeout: 20_000 })
    .toBe(true);
  return asentada(pagina);
}

function igual(antes: Vista, despues: Vista, que: string) {
  expect(Math.abs(despues.lon - antes.lon), `${que}: longitud`).toBeLessThan(TOLERANCIA_GRADOS);
  expect(Math.abs(despues.lat - antes.lat), `${que}: latitud`).toBeLessThan(TOLERANCIA_GRADOS);
  expect(Math.abs(despues.zoom - antes.zoom), `${que}: zoom`).toBeLessThan(TOLERANCIA_ZOOM);
}

async function tocar(pagina: Page, telefono: boolean, x: number, y: number) {
  if (telefono) await pagina.touchscreen.tap(x, y);
  else await pagina.mouse.click(x, y);
}

/**
 * Un punto del mapa (relativo a su caja) desde la altura dada hacia abajo, a la izquierda, sin
 * ninguna marca de la web (lo que no es del mapa de fondo ni un área) en el cuadro de 44 px del dedo.
 */
async function puntoVacio(pagina: Page, desde: number): Promise<{ x: number; y: number }> {
  const punto = await pagina.evaluate((y0) => {
    const mapa = document.querySelector<HTMLElement & { mapaDePruebas?: { queryRenderedFeatures: (caja: [[number, number], [number, number]]) => { source: string; layer: { type: string } }[] } }>(".maplibregl-map")?.mapaDePruebas;
    if (mapa === undefined) return null;
    for (let y = y0; y < y0 + 300; y += 12) {
      for (let x = 24; x < 200; x += 12) {
        const rasgos = mapa.queryRenderedFeatures([[x - 22, y - 22], [x + 22, y + 22]]);
        // Las áreas (países, regiones, tierra) no son marcas: tocarlas con una ficha abierta la cierra.
        if (rasgos.every((r) => r.source === "protomaps" || r.layer.type === "fill")) return { x, y };
      }
    }
    return null;
  }, desde);
  if (punto === null) throw new Error("ningún punto vacío bajo la cabecera");
  return punto;
}

/** Dónde queda en la pantalla el incidente abierto. */
async function posicion(pagina: Page): Promise<{ x: number; y: number }> {
  const mapa = pagina.locator(MAPA);
  const caja = await mapa.boundingBox();
  const [x = Number.NaN, y = Number.NaN] = ((await mapa.getAttribute("data-elegido")) ?? "").split(",").map(Number);
  if (caja === null) throw new Error("sin mapa");
  return { x: caja.x + x, y: caja.y + y };
}

const VARIANTES = [
  { nombre: "incidentes", busqueda: "", ucrania: false },
  { nombre: "ucrania", busqueda: "", ucrania: true },
  { nombre: "corredores-satelite", busqueda: "?guerra=corredores,satelite", ucrania: false },
];

for (const tamano of [TELEFONO, ESCRITORIO]) {
  const telefono = tamano === TELEFONO;
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
    test.afterEach(async ({ context }) => {
      await context.unrouteAll({ behavior: "ignoreErrors" });
    });

    for (const variante of VARIANTES) {
      test(`${nombre}, ${variante.nombre}: cerrar una ficha no mueve el mapa`, async ({ page, context, baseURL }) => {
        test.setTimeout(240_000);
        await preparar(context, baseURL);
        const incidente = await aislado(page);
        const ficha = page.getByRole("complementary", { name: new RegExp(incidente.id) });
        const metodos = ["equis", "fuera", "escape", ...(telefono ? ["arrastrar"] : [])];
        for (const metodo of metodos) {
          // Por su enlace: el mapa va al incidente. Al cerrar con la equis, se queda ahí.
          await page.goto(`/${incidente.id}${variante.busqueda}`);
          await page.waitForSelector(MAPA);
          await expect(ficha).toBeVisible();
          let vista = await llegada(page, incidente);
          if (variante.ucrania) {
            // Cambiar de capa no mueve el mapa.
            await page.keyboard.press("2");
            const conUcrania = await asentada(page);
            igual(vista, conUcrania, "encender la capa de Ucrania");
            vista = conUcrania;
          }
          const marcador = await posicion(page);
          await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
          await expect(ficha).toBeHidden();
          const antes = await asentada(page);
          igual(vista, antes, "cerrar la ficha abierta por su enlace");
          await page.screenshot({ path: join(CAPTURAS, `mapa-quieto-${nombre}-${variante.nombre}-${metodo}-antes.png`) });
          // Tocando su marcador: ya se ve, el mapa no se mueve al abrir.
          await tocar(page, telefono, marcador.x, marcador.y);
          await expect(ficha).toBeVisible();
          igual(antes, await asentada(page), `abrir tocando el marcador (${metodo})`);
          if (metodo === "equis") {
            await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
          } else if (metodo === "escape") {
            await page.keyboard.press("Escape");
          } else if (metodo === "fuera") {
            // Un punto del mapa sin nada, bajo los botones de la cabecera: sin ninguna marca de la
            // web en el cuadro de 44 px que cubre el dedo (si no, el toque abre esa marca, como
            // pasaba con un incidente de Malinas junto al punto fijo de antes).
            const caja = await page.locator(MAPA).boundingBox();
            const cabecera = await page.locator("header").filter({ visible: true }).first().boundingBox();
            if (caja === null || cabecera === null) throw new Error("sin medidas");
            const vacio = await puntoVacio(page, cabecera.y + cabecera.height + 70 - caja.y);
            await tocar(page, telefono, caja.x + vacio.x, caja.y + vacio.y);
          } else {
            // Arrastrar la hoja por su asa hasta abajo.
            const caja = await ficha.boundingBox();
            if (caja === null) throw new Error("sin hoja");
            const x = caja.x + caja.width / 2;
            await page.mouse.move(x, caja.y + 8);
            await page.mouse.down();
            for (let paso = 1; paso <= 10; paso += 1) {
              await page.mouse.move(x, caja.y + 8 + ((tamano.height - caja.y) * paso) / 10);
            }
            await page.mouse.up();
          }
          await expect(ficha).toBeHidden();
          const despues = await asentada(page);
          await page.screenshot({ path: join(CAPTURAS, `mapa-quieto-${nombre}-${variante.nombre}-${metodo}-despues.png`) });
          igual(antes, despues, `cerrar con ${metodo}`);
        }
      });
    }

    test(`${nombre}: tras elegir un punto de «Con satélite», cerrar otra ficha no vuelve a él`, async ({
      page,
      context,
      baseURL,
    }) => {
      // El fallo que se veía: el mapa volaba al último punto elegido en «Con satélite» (en el
      // este) al cerrar cualquier ficha. La causa estaba en la lógica común (App.tsx); la lista de
      // «Con satélite» se abre aquí en escritorio.
      test.skip(telefono, "la lista de «Con satélite» del teléfono va dentro del menú");
      test.setTimeout(240_000);
      await preparar(context, baseURL);
      const incidente = await aislado(page);
      await page.goto("/?satelite=foco");
      await page.waitForSelector(MAPA);
      const lista = page.getByRole("list", { name: "Puntos con información de satélite" }).filter({ visible: true });
      await lista.getByRole("button").first().click();
      await asentada(page);
      // A Bélgica por un enlace de la propia web (el mapa va al incidente).
      await page.evaluate((id) => {
        window.history.pushState(null, "", `/${id}`);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }, incidente.id);
      const ficha = page.getByRole("complementary", { name: new RegExp(incidente.id) });
      await expect(ficha).toBeVisible();
      const antes = await llegada(page, incidente);
      await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
      await expect(ficha).toBeHidden();
      igual(antes, await asentada(page), "cerrar después de «Con satélite»");
    });

    test(`${nombre}: diez fichas seguidas, el mapa no se va desplazando`, async ({ page, context, baseURL }) => {
      test.setTimeout(240_000);
      await preparar(context, baseURL);
      const incidente = await aislado(page);
      const ficha = page.getByRole("complementary", { name: new RegExp(incidente.id) });
      await page.goto(`/${incidente.id}`);
      await page.waitForSelector(MAPA);
      await llegada(page, incidente);
      const marcador = await posicion(page);
      await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
      const antes = await asentada(page);
      for (let vez = 0; vez < 10; vez += 1) {
        await tocar(page, telefono, marcador.x, marcador.y);
        await expect(ficha).toBeVisible();
        await ficha.getByRole("button", { name: "Cerrar la ficha" }).click();
        await expect(ficha).toBeHidden();
        igual(antes, await asentada(page), `ficha ${vez + 1} de 10`);
      }
    });
  });
}
