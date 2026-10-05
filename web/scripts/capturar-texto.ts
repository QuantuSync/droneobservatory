// Capturas de las páginas de texto sin ejecutar código y de la web con código, en los tamaños
// de teléfono y en escritorio, para revisarlas a ojo: `node scripts/capturar-texto.ts <base>
// <carpeta> [ruta...]`. Con VERCEL_BYPASS, entra en una vista previa protegida.

import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const [base = "https://droneobservatory.eu", carpeta = "capturas", ...rutas] = process.argv.slice(2);
const TAMANOS = [
  { nombre: "360x800", width: 360, height: 800, movil: true },
  { nombre: "390x844", width: 390, height: 844, movil: true },
  { nombre: "412x915", width: 412, height: 915, movil: true },
  { nombre: "escritorio", width: 1440, height: 900, movil: false },
] as const;
const acceso = process.env.VERCEL_BYPASS;

await mkdir(carpeta, { recursive: true });
const navegador = await chromium.launch();
for (const tamano of TAMANOS) {
  for (const js of [false, true]) {
    const contexto = await navegador.newContext({
      viewport: { width: tamano.width, height: tamano.height },
      isMobile: tamano.movil,
      hasTouch: tamano.movil,
      javaScriptEnabled: js,
    });
    if (acceso !== undefined) {
      const propio = new URL(base).origin;
      await contexto.route(
        (url) => url.origin === propio,
        (r) => r.continue({ headers: { ...r.request().headers(), "x-vercel-protection-bypass": acceso } }),
      );
    }
    const pagina = await contexto.newPage();
    for (const ruta of rutas.length > 0 ? rutas : ["/"]) {
      await pagina.goto(base + ruta);
      if (js) await pagina.locator("[data-mapa-listo=true]").waitFor({ state: "attached", timeout: 60_000 }).catch(() => undefined);
      await pagina.waitForTimeout(js ? 2500 : 300);
      const nombre = `${ruta === "/" ? "portada" : ruta.replaceAll("/", "_").replace(/^_/, "")}-${js ? "con-codigo" : "sin-codigo"}-${tamano.nombre}.png`;
      await pagina.screenshot({ path: join(carpeta, nombre), fullPage: !js });
    }
    await contexto.close();
  }
}
await navegador.close();
console.log(`capturas en ${carpeta}`);
