// Genera public/compartir.png, la imagen fija del mapa de Europa que acompaña a los
// enlaces al compartirlos. Se ejecuta a mano contra el servidor local (npm run build y
// npm run servir) cuando cambia el aspecto del mapa: «node scripts/imagen-compartir.ts».

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

import { IMAGEN_COMPARTIR, IMAGEN_COMPARTIR_ALTO, IMAGEN_COMPARTIR_ANCHO } from "../src/sitio.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const ORIGEN_LOCAL = process.env.ORIGEN ?? "http://localhost:4173";
/** Lo que no pertenece a una imagen fija: cifras que cambian, botones y controles. */
const OCULTOS = [
  "header dl",
  "header button",
  "header a[hreflang]",
  ".entre-lineas",
  "#mapa > div.absolute",
  "#mapa > p",
  "#mapa button",
];
const MS_DE_ASENTAMIENTO = 3000;
/** Altura de la línea de tiempo, que queda debajo del recorte: así el mapa no cambia de tamaño. */
const ALTO_BAJO_EL_RECORTE = 124;

const navegador = await chromium.launch();
const pagina = await navegador.newPage({
  viewport: { width: IMAGEN_COMPARTIR_ANCHO, height: IMAGEN_COMPARTIR_ALTO + ALTO_BAJO_EL_RECORTE },
  deviceScaleFactor: 1,
});
await pagina.goto(ORIGEN_LOCAL, { waitUntil: "load" });
await pagina.waitForSelector("[data-mapa-listo=true]");
await pagina.evaluate((selectores) => {
  for (const selector of selectores) {
    for (const elemento of document.querySelectorAll<HTMLElement>(selector)) {
      // El lienzo del mapa también es un div absoluto: se queda.
      if (elemento.querySelector("canvas") === null) elemento.hidden = true;
    }
  }
}, OCULTOS);
await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
await pagina.screenshot({
  path: join(WEB, "public", IMAGEN_COMPARTIR),
  clip: { x: 0, y: 0, width: IMAGEN_COMPARTIR_ANCHO, height: IMAGEN_COMPARTIR_ALTO },
});
await navegador.close();
console.log(`imagen: public${IMAGEN_COMPARTIR}`);
