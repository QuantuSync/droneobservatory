// El número de un grupo de incidentes siempre se lee, aunque al lado haya el marcador de un
// atribuido, en un navegador real, en el teléfono (390×844, con tacto) y en escritorio, con los
// datos publicados: sobre Alemania (Leipzig), Rumanía (Galați) y el Øresund (Malmö y
// Copenhague), a varios zooms, se mide en la pantalla la caja del número de cada grupo visible y
// el círculo de cada atribuido (map.project) y, donde se pisan, se compara el número dibujado con
// y sin los atribuidos: cada píxel de sus cifras sigue igual, nada lo tapa. Va contra producción
// por defecto; con BASE=http://localhost:4173 contra el servidor local, reenviando el almacén
// público, que solo admite el dominio propio.
import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";
import type { Map as MapaGL } from "maplibre-gl";

import { MARCA_ATRIBUIDO } from "../src/paleta.ts";

// Las capas y medidas de estilo.ts e iconos.ts, que no se pueden importar fuera de Vite.
const CAPA_NUMERO_GRUPOS = "grupos-numero";
const CAPA_ATRIBUIDOS = "atribuidos";
const CAPA_NUMERO_ATRIBUIDOS = "atribuidos-numero";
const CAPA_FOCOS_ATRIBUIDOS = "focos-termicos-atribuidos";
const CAPA_SELECCION_ATRIBUIDO = "seleccion-atribuido";
const TAMANO_NUMERO_GRUPO = 12;
const ESCALA_ATRIBUIDO_ELEGIDO = 1.2;

const MAPA_LISTO = "[data-mapa-listo=true]";
const TELEFONO = { nombre: "390x844", width: 390, height: 844 };
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
const LUGARES = [
  { nombre: "Leipzig", centro: [12.37, 51.34] },
  { nombre: "Galați", centro: [28.05, 45.43] },
  { nombre: "Øresund", centro: [12.8, 55.65] },
] as const;
const ZOOMS = [3, 3.5, 4, 4.5, 5, 6, 7, 8];
const CAPAS_DE_ATRIBUIDOS = [CAPA_ATRIBUIDOS, CAPA_NUMERO_ATRIBUIDOS, CAPA_FOCOS_ATRIBUIDOS, CAPA_SELECCION_ATRIBUIDO];
/** Caja del número: el ancho de cada cifra y el halo, en píxeles de pantalla. */
const ANCHO_CIFRA = 0.6 * TAMANO_NUMERO_GRUPO;
const HALO = 2;
/** Radio del marcador de un atribuido con su filo, el del abierto algo mayor. */
const RADIO_MARCADOR = (MARCA_ATRIBUIDO.radio + MARCA_ATRIBUIDO.halo) * ESCALA_ATRIBUIDO_ELEGIDO;
/** Un píxel de una cifra: el color del texto, claro en los tres canales. */
const CANAL_DE_CIFRA = 150;
const TOLERANCIA = 40;

interface Caja {
  x: number;
  y: number;
  ancho: number;
  alto: number;
}

interface Pisado {
  numero: string;
  caja: Caja;
}

type ElementoDelMapa = HTMLElement & { mapaDePruebas?: MapaGL };

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

/** Lleva el mapa a ese sitio y zoom y devuelve los números de grupo que pisa un atribuido. */
async function pisados(pagina: Page, centro: readonly [number, number], zoom: number): Promise<Pisado[]> {
  return pagina.evaluate(
    async ({ centro, zoom, capaNumero, capasAtribuidos, anchoCifra, halo, tamano, radio }) => {
      const elemento = document.querySelector<ElementoDelMapa>(".maplibregl-map");
      const mapa = elemento?.mapaDePruebas;
      if (mapa === undefined) throw new Error("sin mapa");
      mapa.jumpTo({ center: [centro[0], centro[1]], zoom });
      await new Promise((listo) => mapa.once("idle", listo));
      const lienzo = mapa.getCanvas();
      const marcadores = mapa
        .queryRenderedFeatures({ layers: capasAtribuidos.filter((c) => mapa.getLayer(c) !== undefined) })
        .flatMap((rasgo) => (rasgo.geometry.type === "Point" ? [mapa.project(rasgo.geometry.coordinates as [number, number])] : []));
      const resultado: { numero: string; caja: { x: number; y: number; ancho: number; alto: number } }[] = [];
      for (const rasgo of mapa.queryRenderedFeatures({ layers: [capaNumero] })) {
        if (rasgo.geometry.type !== "Point") continue;
        const p = mapa.project(rasgo.geometry.coordinates as [number, number]);
        const numero = String(rasgo.properties.total ?? rasgo.properties.n);
        const ancho = numero.length * anchoCifra + 2 * halo;
        const alto = tamano + 2 * halo;
        const caja = { x: p.x - ancho / 2, y: p.y - alto / 2, ancho, alto };
        // Solo los que se ven: dentro de la pantalla y sin un panel de la web encima.
        if (caja.x < 0 || caja.y < 0 || caja.x + ancho > window.innerWidth || caja.y + alto > window.innerHeight) continue;
        if (document.elementFromPoint(p.x, p.y) !== lienzo) continue;
        // ¿Algún marcador de atribuido entra en la caja? (círculo contra rectángulo)
        const pisa = marcadores.some((m) => {
          const dx = Math.max(caja.x - m.x, 0, m.x - (caja.x + ancho));
          const dy = Math.max(caja.y - m.y, 0, m.y - (caja.y + alto));
          return Math.hypot(dx, dy) < radio;
        });
        if (pisa) resultado.push({ numero, caja });
      }
      return resultado;
    },
    {
      centro,
      zoom,
      capaNumero: CAPA_NUMERO_GRUPOS,
      capasAtribuidos: CAPAS_DE_ATRIBUIDOS,
      anchoCifra: ANCHO_CIFRA,
      halo: HALO,
      tamano: TAMANO_NUMERO_GRUPO,
      radio: RADIO_MARCADOR,
    },
  );
}

/** Muestra u oculta las capas de los atribuidos y espera a que el mapa se haya vuelto a dibujar. */
async function verAtribuidos(pagina: Page, ver: boolean) {
  await pagina.evaluate(
    async ({ capas, ver }) => {
      const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
      if (mapa === undefined) throw new Error("sin mapa");
      for (const capa of capas) {
        if (mapa.getLayer(capa) !== undefined) mapa.setLayoutProperty(capa, "visibility", ver ? "visible" : "none");
      }
      await new Promise((listo) => mapa.once("idle", listo));
    },
    { capas: CAPAS_DE_ATRIBUIDOS, ver },
  );
}

/**
 * Para cada número, de los píxeles de sus cifras sin atribuidos (claros, del color del texto),
 * cuántos siguen iguales con ellos. Las dos capturas se leen en la propia página.
 */
async function cifrasIntactas(pagina: Page, con: Buffer, sin: Buffer, cajas: Caja[]) {
  return pagina.evaluate(
    async ({ con, sin, cajas, canal, tolerancia }) => {
      async function pixeles(base64: string) {
        const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
        const mapa = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
        const lienzo = new OffscreenCanvas(mapa.width, mapa.height);
        const contexto = lienzo.getContext("2d");
        if (contexto === null) throw new Error("sin lienzo");
        contexto.drawImage(mapa, 0, 0);
        return contexto.getImageData(0, 0, mapa.width, mapa.height);
      }
      const [a, b] = await Promise.all([pixeles(con), pixeles(sin)]);
      const escala = a.width / window.innerWidth;
      return cajas.map((caja) => {
        let cifra = 0;
        let iguales = 0;
        for (let y = Math.floor(caja.y * escala); y < Math.ceil((caja.y + caja.alto) * escala); y += 1) {
          for (let x = Math.floor(caja.x * escala); x < Math.ceil((caja.x + caja.ancho) * escala); x += 1) {
            const i = (y * a.width + x) * 4;
            const r = b.data[i] ?? 0;
            const g = b.data[i + 1] ?? 0;
            const az = b.data[i + 2] ?? 0;
            if (Math.min(r, g, az) < canal) continue;
            cifra += 1;
            const diferencia = Math.max(
              Math.abs(r - (a.data[i] ?? 0)),
              Math.abs(g - (a.data[i + 1] ?? 0)),
              Math.abs(az - (a.data[i + 2] ?? 0)),
            );
            if (diferencia <= tolerancia) iguales += 1;
          }
        }
        return { cifra, iguales };
      });
    },
    { con: con.toString("base64"), sin: sin.toString("base64"), cajas, canal: CANAL_DE_CIFRA, tolerancia: TOLERANCIA },
  );
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

    test(`${nombre}: ningún atribuido tapa el número de un grupo, a ningún zoom`, async ({ page, context, baseURL }) => {
      test.setTimeout(240_000);
      await preparar(context, baseURL);
      await page.addInitScript(() => window.localStorage.removeItem("eodi.ultima-visita"));
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO);
      // El número de los grupos se dibuja por encima de todas las capas de los atribuidos.
      const orden = await page.evaluate(() => {
        const mapa = document.querySelector<ElementoDelMapa>(".maplibregl-map")?.mapaDePruebas;
        return mapa?.getStyle().layers.map((capa) => capa.id) ?? [];
      });
      for (const capa of CAPAS_DE_ATRIBUIDOS) {
        expect(orden.indexOf(CAPA_NUMERO_GRUPOS), capa).toBeGreaterThan(orden.indexOf(capa));
      }
      let comprobados = 0;
      const tapados: string[] = [];
      for (const lugar of LUGARES) {
        for (const zoom of ZOOMS) {
          const lista = await pisados(page, lugar.centro, zoom);
          if (lista.length === 0) continue;
          const con = await page.screenshot();
          await verAtribuidos(page, false);
          const sin = await page.screenshot();
          await verAtribuidos(page, true);
          const medidas = await cifrasIntactas(page, con, sin, lista.map((p) => p.caja));
          lista.forEach((pisado, i) => {
            const { cifra, iguales } = medidas[i] ?? { cifra: 0, iguales: 0 };
            const donde = `${lugar.nombre} z${zoom}: el ${pisado.numero} en ${Math.round(pisado.caja.x)},${Math.round(pisado.caja.y)}`;
            // Las cifras se ven sin los atribuidos y siguen iguales con ellos.
            if (cifra < 3) tapados.push(`${donde} sin cifras que medir`);
            else if (iguales / cifra < 0.97) tapados.push(`${donde}: ${cifra - iguales} de ${cifra} píxeles tapados`);
            comprobados += 1;
          });
        }
      }
      // Hay grupos con un atribuido al lado (si no, la prueba no mediría nada) y ninguno tapado.
      expect(comprobados).toBeGreaterThan(0);
      expect(tapados).toEqual([]);
    });
  });
}
