// La bandera de los atribuidos desde el primer dibujado, en un navegador real, en el teléfono
// (390×844, con tacto) y en escritorio: con la caché vacía y la red lenta (cada petición de la
// web tarda y las banderas, mucho más), la primera vez que la capa de los atribuidos tiene algo
// que dibujar, el icono con la bandera de cada uno ya está en el mapa; nunca se ve el marcador
// liso que después cambia. Lo mismo con un atribuido abierto al entrar por su enlace. Va contra
// producción por defecto; con BASE=http://localhost:4173 contra el servidor local, reenviando el
// almacén público, que solo admite el dominio propio.
import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";
import type { Map as MapaGL } from "maplibre-gl";

import { BANDERAS } from "../src/banderas.ts";
import type { Resumen } from "../src/datos/tipos.ts";

const MAPA_LISTO = "[data-mapa-listo=true]";
const TELEFONO = { nombre: "390x844", width: 390, height: 844 };
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
/** Retraso de cada petición a la web y, aparte, de cada bandera. */
const RETRASO_MS = 150;
const RETRASO_BANDERA_MS = 3000;
const CAPAS = ["atribuidos", "seleccion-atribuido"] as const;

/** Lo que el mapa tenía la primera vez que cada capa dibujó algo. */
interface PrimerDibujado {
  /** Iconos que pedían sus marcas, según su bandera. */
  pedidos: string[];
  /** De esos, los que aún no estaban en el mapa. */
  ausentes: string[];
}

type Registro = Partial<Record<(typeof CAPAS)[number], PrimerDibujado>>;

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  // Red lenta: todo lo de la web tarda y las banderas aún más.
  await contexto.route(
    (url) => baseURL !== undefined && url.href.startsWith(baseURL),
    async (ruta) => {
      const bandera = new URL(ruta.request().url()).pathname.startsWith("/banderas/");
      await new Promise((listo) => setTimeout(listo, bandera ? RETRASO_BANDERA_MS : RETRASO_MS));
      await ruta.fallback();
    },
  );
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

/** Caché vacía: cada prueba lleva un contexto nuevo y, además, la página va sin caché. */
async function sinCache(contexto: BrowserContext, pagina: Page) {
  const cdp = await contexto.newCDPSession(pagina);
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
}

/**
 * Antes de que arranque la web: en cuanto el mapa se crea (Mapa.tsx lo deja en su elemento con
 * el navegador de pruebas), en cada fotograma se mira si cada capa ya dibuja algo y, la primera
 * vez, qué icono pide cada marca y si ya está en el mapa.
 */
async function vigilar(pagina: Page) {
  await pagina.addInitScript((capas) => {
    const registro: Record<string, unknown> = {};
    (window as unknown as { primerDibujado: Record<string, unknown> }).primerDibujado = registro;
    Object.defineProperty(HTMLElement.prototype, "mapaDePruebas", {
      configurable: true,
      set(this: HTMLElement, mapa: MapaGL) {
        Object.defineProperty(this, "mapaDePruebas", { value: mapa, configurable: true });
        mapa.on("render", () => {
          for (const capa of capas) {
            if (capa in registro || mapa.getLayer(capa) === undefined) continue;
            const rasgos = mapa.queryRenderedFeatures({ layers: [capa] });
            if (rasgos.length === 0) continue;
            // El mismo icono que pide ICONO_ATRIBUIDO (estilo.ts) para cada marca.
            const pedidos = rasgos.flatMap((rasgo) => {
              const p = rasgo.properties;
              const menor = Number(p.bandera_min ?? p.bandera);
              const mayor = Number(p.bandera_max ?? p.bandera);
              if (menor !== mayor || menor < 0) return [];
              return [`atribuido-${menor}${Number(p.persona_min ?? p.persona) === 1 ? "-p" : ""}`];
            });
            registro[capa] = { pedidos, ausentes: pedidos.filter((nombre) => !mapa.hasImage(nombre)) };
          }
        });
      },
    });
  }, CAPAS);
}

async function primerDibujado(pagina: Page, capa: (typeof CAPAS)[number]): Promise<PrimerDibujado> {
  await pagina.waitForFunction((c) => c in (window as unknown as { primerDibujado: Registro }).primerDibujado, capa, {
    timeout: 60_000,
  });
  const registro = await pagina.evaluate(() => (window as unknown as { primerDibujado: Registro }).primerDibujado);
  const dibujado = registro[capa];
  if (dibujado === undefined) throw new Error(`${capa} no ha dibujado nada`);
  return dibujado;
}

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

    test(`${nombre}: el primer dibujado de los atribuidos ya lleva su bandera`, async ({ page, context, baseURL }) => {
      const datos = (await (await page.request.get("/datos/resumen.json")).json()) as Resumen;
      const conBandera = datos.incidentes.filter(
        (i) => i.estado === "atribuido" && i.punto !== null && (BANDERAS as readonly string[]).includes(i.atribucion?.pais ?? ""),
      );
      expect(conBandera.length).toBeGreaterThan(0);
      await sinCache(context, page);
      await preparar(context, baseURL);
      await vigilar(page);
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO, { timeout: 60_000 });
      const dibujado = await primerDibujado(page, "atribuidos");
      // Alguna marca pedía bandera, y todas la tenían ya al dibujarse por primera vez.
      expect(dibujado.pedidos.length).toBeGreaterThan(0);
      expect(dibujado.ausentes).toEqual([]);

      // Al entrar por el enlace de un atribuido, su marcador abierto tampoco sale liso primero.
      const elegido = conBandera[0];
      if (elegido === undefined) throw new Error("sin atribuidos con bandera");
      const otra = await context.newPage();
      await sinCache(context, otra);
      await vigilar(otra);
      await otra.goto(`/${elegido.id}`);
      await otra.waitForSelector(MAPA_LISTO, { timeout: 60_000 });
      // (Los demás atribuidos suelen quedar fuera de la vista, ya acercada al abierto.)
      const abierto = await primerDibujado(otra, "seleccion-atribuido");
      expect(abierto.pedidos.length).toBeGreaterThan(0);
      expect(abierto.ausentes).toEqual([]);
      await otra.close();
    });
  });
}
