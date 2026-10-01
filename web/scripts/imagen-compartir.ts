// Genera las imágenes de la vista previa al compartir (Open Graph y Twitter), una por idioma:
// el logo completo, el nombre del observatorio y el mapa de Europa con los incidentes. Se
// ejecuta a mano contra el servidor local (npm run build y npm run servir) cuando cambia el
// aspecto del mapa o de la marca: «node scripts/imagen-compartir.ts».

import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

import { textos } from "../src/i18n/index.ts";
import {
  IDIOMAS,
  IMAGEN_COMPARTIR,
  IMAGEN_COMPARTIR_ALTO,
  IMAGEN_COMPARTIR_ANCHO,
  NOMBRE,
  rutaDeIdioma,
} from "../src/sitio.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const ORIGEN_LOCAL = process.env.ORIGEN ?? "http://localhost:4173";
const MS_DE_ASENTAMIENTO = 3000;
const LOGO = join(WEB, "public", "marca", "logo-384.png");
const FUENTE = createRequire(import.meta.url).resolve(
  "@fontsource-variable/onest/files/onest-latin-wght-normal.woff2",
);
/** Tamaños de la composición, en píxeles de la imagen de 1200 × 630. */
const LADO_LOGO = 250;
const MARGEN = 64;
const CUERPO_NOMBRE = 54;
const CUERPO_LEMA = 24;

function comoDato(tipo: string, contenido: Buffer): string {
  return `data:${tipo};base64,${contenido.toString("base64")}`;
}

/** Composición de la imagen: fuera de la web, solo para hacer la captura. */
function composicion(mapa: string, logo: string, fuente: string, lema: string): string {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: Onest; src: url(${fuente}) format("woff2"); font-weight: 100 900; }
html, body { margin: 0; width: ${IMAGEN_COMPARTIR_ANCHO}px; height: ${IMAGEN_COMPARTIR_ALTO}px; }
body { position: relative; overflow: hidden; background: #060a12 url(${mapa}) center / cover;
  font-family: Onest, sans-serif; color: #f4f7fb; }
.velo { position: absolute; inset: 0;
  background: linear-gradient(90deg, rgb(6 10 18 / 0.97) 0%, rgb(6 10 18 / 0.9) 46%, rgb(6 10 18 / 0.2) 78%); }
.contenido { position: absolute; inset: 0; display: flex; align-items: center; gap: 40px;
  padding: 0 ${MARGEN}px; }
img { width: ${LADO_LOGO}px; height: ${LADO_LOGO}px; flex: none; }
h1 { margin: 0; max-width: 560px; font-size: ${CUERPO_NOMBRE}px; line-height: 1.05; font-weight: 650;
  letter-spacing: -0.01em; }
p { margin: 18px 0 0; max-width: 520px; font-size: ${CUERPO_LEMA}px; line-height: 1.35; color: #93a0b4; }
</style></head><body><div class="velo"></div><div class="contenido">
<img src="${logo}" alt=""><div><h1>${NOMBRE}</h1><p>${lema}</p></div></div></body></html>`;
}

const navegador = await chromium.launch();
const tamano = { width: IMAGEN_COMPARTIR_ANCHO, height: IMAGEN_COMPARTIR_ALTO };
const logo = comoDato("image/png", await readFile(LOGO));
const fuente = comoDato("font/woff2", await readFile(FUENTE));
for (const idioma of IDIOMAS) {
  const pagina = await navegador.newPage({ viewport: tamano, deviceScaleFactor: 1 });
  await pagina.goto(`${ORIGEN_LOCAL}${rutaDeIdioma(idioma)}`, { waitUntil: "load" });
  await pagina.waitForSelector("[data-mapa-listo=true]");
  // Solo el mapa: se oculta todo lo que flota o se acopla sobre él.
  await pagina.evaluate(() => {
    const mapa = document.getElementById("mapa");
    for (const elemento of mapa?.parentElement?.children ?? []) {
      if (elemento !== mapa && elemento instanceof HTMLElement) elemento.style.visibility = "hidden";
    }
    for (const elemento of document.querySelectorAll<HTMLElement>(".maplibregl-control-container")) {
      elemento.hidden = true;
    }
  });
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  const mapa = comoDato("image/png", await pagina.screenshot({ clip: { x: 0, y: 0, ...tamano } }));
  await pagina.close();
  // La composición va en una pestaña en blanco: en la del sitio mandaría su política de
  // contenido, que no admite imágenes ni estilos en línea.
  const lienzo = await navegador.newPage({ viewport: tamano, deviceScaleFactor: 1 });
  await lienzo.setContent(composicion(mapa, logo, fuente, textos(idioma).compartir.lema));
  await lienzo.evaluate(() => document.fonts.ready);
  await lienzo.screenshot({ path: join(WEB, "public", IMAGEN_COMPARTIR[idioma]), clip: { x: 0, y: 0, ...tamano } });
  await lienzo.close();
  console.log(`imagen: public${IMAGEN_COMPARTIR[idioma]}`);
}
await navegador.close();
