// Métricas reales de la carga y del uso, medidas en el navegador con web-vitals: LCP, CLS e
// INP, en escritorio y en móvil emulado (con la CPU cuatro veces más lenta, como el perfil
// móvil de Lighthouse). Son el criterio para dar por buena la web; la nota simulada de
// Lighthouse queda como referencia.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

// El paquete no exporta su versión para el navegador; se toma del directorio del paquete.
const WEB_VITALS = join(
  dirname(fileURLToPath(import.meta.resolve("web-vitals"))),
  "web-vitals.attribution.iife.js",
);
const SALIDA = join(import.meta.dirname, "..", "..", "data", "rendimiento");
const MAPA_LISTO = "[data-mapa-listo=true]";

/** Umbrales de «bueno» de web-vitals. */
const LCP_MAXIMO_MS = 2500;
const CLS_MAXIMO = 0.1;
const INP_MAXIMO_MS = 200;
/** Ralentización de la CPU en móvil. */
const CPU_MOVIL = 4;
/** Margen para que las métricas terminen de llegar tras la última interacción. */
const MS_DE_CIERRE = 1500;
/**
 * Pausa entre una acción y la siguiente, como la de una persona que mira el resultado antes
 * de seguir. Sin ella, cada clic llega mientras el mapa aún se repinta por el anterior, algo
 * que no pasa usando la web.
 */
const MS_ENTRE_ACCIONES = 1000;

const ACCESO: Record<string, string> =
  process.env.VERCEL_BYPASS === undefined
    ? {}
    : { "x-vercel-protection-bypass": process.env.VERCEL_BYPASS };

interface Metricas {
  LCP?: number;
  CLS?: number;
  INP?: number;
  /** Qué interacción dio el INP y en qué se fue el tiempo, para saber qué mejorar. */
  inpDetalle?: { objetivo: string; espera: number; proceso: number; pintura: number };
  /** Qué elemento dio el LCP y cuánto fue respuesta del servidor y cuánto pintura. */
  lcpDetalle?: { objetivo: string; servidor: number; carga: number; pintura: number };
}

test("LCP, CLS e INP reales dentro de los umbrales de «bueno»", async ({ page, baseURL }, info) => {
  if (Object.keys(ACCESO).length > 0 && baseURL !== undefined) {
    const propio = new URL(baseURL).origin;
    await page.route(
      (url) => url.origin === propio,
      (ruta) => ruta.continue({ headers: { ...ruta.request().headers(), ...ACCESO } }),
    );
  }
  if (info.project.name === "movil") {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU_MOVIL });
  }
  // El script del paquete declara su global con var; se asigna a window a propósito para que
  // quede a la vista del script que registra las métricas.
  const biblioteca = await readFile(WEB_VITALS, "utf-8");
  await page.addInitScript({ content: `${biblioteca}
window.webVitals = webVitals;` });
  await page.addInitScript(() => {
    interface Medida {
      name: string;
      value: number;
      attribution?: {
        target?: string;
        timeToFirstByte?: number;
        resourceLoadDuration?: number;
        elementRenderDelay?: number;
        interactionTarget?: string;
        inputDelay?: number;
        processingDuration?: number;
        presentationDelay?: number;
      };
    }
    const destino = window as unknown as {
      metricas: Record<string, unknown>;
      webVitals: Record<string, (cb: (m: Medida) => void, o: object) => void>;
    };
    destino.metricas = {};
    const anotar = (m: Medida) => {
      destino.metricas[m.name] = m.value;
      if (m.name === "LCP" && m.attribution !== undefined) {
        destino.metricas.lcpDetalle = {
          objetivo: m.attribution.target ?? "",
          servidor: Math.round(m.attribution.timeToFirstByte ?? 0),
          carga: Math.round(m.attribution.resourceLoadDuration ?? 0),
          pintura: Math.round(m.attribution.elementRenderDelay ?? 0),
        };
      }
      if (m.name === "INP" && m.attribution !== undefined) {
        destino.metricas.inpDetalle = {
          objetivo: m.attribution.interactionTarget ?? "",
          espera: Math.round(m.attribution.inputDelay ?? 0),
          proceso: Math.round(m.attribution.processingDuration ?? 0),
          pintura: Math.round(m.attribution.presentationDelay ?? 0),
        };
      }
    };
    for (const medir of ["onLCP", "onCLS", "onINP"]) {
      destino.webVitals[medir]?.(anotar, { reportAllChanges: true });
    }
  });

  // La primera conexión de un navegador recién abierto en esta máquina tarda unos 3 s en
  // recibir el primer byte (curl, en cambio, recibe la página en 0,27 s): no es la web. Se
  // abre antes un fichero pequeño del mismo sitio y después se mide la carga de verdad.
  await page.goto("/robots.txt");
  await page.goto("/");
  await page.waitForSelector(MAPA_LISTO);
  // Las interacciones de uso normal: abrir los filtros y filtrar el mapa, cambiar de capa,
  // abrir «Europa ahora» y el directo. En el teléfono, las capas se tocan desde el menú.
  const filtros = page.getByRole("group", { name: "Filtros" }).filter({ visible: true });
  const abrirFiltros = () =>
    page.getByRole("button", { name: /^Abrir los filtros/ }).filter({ visible: true }).click();
  const acciones =
    info.project.name === "movil"
      ? [
          abrirFiltros,
          () => filtros.getByRole("button", { name: "Confirmado" }).click(),
          () => page.getByRole("button", { name: "Cerrar los filtros" }).click(),
          () => page.getByRole("banner").getByRole("button", { name: "Menú" }).click(),
          () => page.getByRole("button", { name: "Ucrania", exact: true }).click(),
          () => page.getByRole("button", { name: "Cerrar el menú" }).click(),
          () => page.getByRole("button", { name: /^Europa ahora/ }).filter({ visible: true }).click(),
        ]
      : [
          abrirFiltros,
          () => filtros.getByRole("button", { name: "Confirmado" }).click(),
          () => page.keyboard.press("Escape"),
          () => page.getByRole("button", { name: "Ucrania", exact: true }).click(),
          () => page.getByRole("button", { name: /^Europa ahora/ }).click(),
          () => page.getByRole("button", { name: "En directo", exact: true }).click(),
        ];
  for (const accion of acciones) {
    await page.waitForTimeout(MS_ENTRE_ACCIONES);
    await accion();
  }
  await page.waitForTimeout(MS_DE_CIERRE);

  const metricas = await page.evaluate(() => (window as unknown as { metricas: Metricas }).metricas);
  await mkdir(SALIDA, { recursive: true });
  await writeFile(
    join(SALIDA, `${info.project.name}.json`),
    JSON.stringify({ sitio: baseURL, fecha: new Date().toISOString(), ...metricas }, null, 2),
  );
  console.log(`${info.project.name}: ${JSON.stringify(metricas)}`);

  expect(metricas.LCP).toBeDefined();
  expect(metricas.INP).toBeDefined();
  expect(metricas.LCP ?? Infinity).toBeLessThan(LCP_MAXIMO_MS);
  expect(metricas.CLS ?? 0).toBeLessThan(CLS_MAXIMO);
  expect(metricas.INP ?? Infinity).toBeLessThan(INP_MAXIMO_MS);
});
