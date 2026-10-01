// Pasos del build sobre las páginas ya prerenderizadas: sacar a ficheros los scripts en
// línea (la política de seguridad solo admite scripts de este sitio) y escribir una página
// por incidente, igual que la portada pero con su título en los metadatos de compartir.

import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { aplicarCabecera, paginaDeIncidente } from "../src/cabecera.ts";
import type { Resumen } from "../src/datos/tipos.ts";
import { separarScriptsEnLinea } from "../src/seguridad/scripts.ts";
import { IDIOMAS, rutaDeFicha } from "../src/sitio.ts";
import type { Idioma } from "../src/sitio.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const SALIDA = join(WEB, "dist");
const CARPETA_SCRIPTS = "assets";
const LARGO_DE_HUELLA = 12;
const RESTO_DE_DATOS_DE_RUTA = "static-loader-data-manifest-";
/**
 * Las dos fuentes con las que se pinta lo primero que se ve (texto latino, peso variable).
 * Se piden desde la cabecera: si no, el navegador solo las descubre al leer la hoja de
 * estilos y la primera pintura con su letra llega tarde, sobre todo en móvil.
 */
export const FUENTES_PRECARGADAS = [
  "onest-latin-wght-normal-",
  "jetbrains-mono-latin-wght-normal-",
] as const;

/** Añade a la cabecera la petición anticipada de cada fuente (sin nada en línea). */
export function precargarFuentes(html: string, ficheros: readonly string[]): string {
  const enlaces = FUENTES_PRECARGADAS.flatMap((prefijo) => {
    const fichero = ficheros.find((f) => f.startsWith(prefijo) && f.endsWith(".woff2"));
    return fichero === undefined
      ? []
      : [
          `<link rel="preload" href="/${CARPETA_SCRIPTS}/${fichero}" as="font" type="font/woff2" crossorigin>`,
        ];
  });
  return html.replace("</head>", `${enlaces.join("")}</head>`);
}

/** Cada script en línea pasa a un fichero con su huella en el nombre. */
async function sacarScriptsEnLinea(html: string): Promise<string> {
  const { html: limpio, scripts } = separarScriptsEnLinea(html, (codigo) => {
    const huella = createHash("sha256").update(codigo).digest("hex").slice(0, LARGO_DE_HUELLA);
    return `/${CARPETA_SCRIPTS}/estado-${huella}.js`;
  });
  for (const { ruta, codigo } of scripts) {
    const destino = join(SALIDA, ruta);
    await mkdir(dirname(destino), { recursive: true });
    await writeFile(destino, codigo, "utf-8");
  }
  return limpio;
}

function portada(carpeta: string, idioma: Idioma): string {
  return idioma === "en" ? join(carpeta, "en", "index.html") : join(carpeta, "index.html");
}

/** Último paso del build: portadas sin scripts en línea y una página por incidente. */
export async function terminarPaginas(carpeta: string): Promise<void> {
  const resumen = JSON.parse(
    await readFile(join(WEB, "public", "datos", "resumen.json"), "utf-8"),
  ) as Resumen;
  const recursos = await readdir(join(carpeta, CARPETA_SCRIPTS));
  for (const idioma of IDIOMAS) {
    const plantilla = precargarFuentes(
      await sacarScriptsEnLinea(await readFile(portada(carpeta, idioma), "utf-8")),
      recursos,
    );
    await writeFile(portada(carpeta, idioma), plantilla, "utf-8");
    for (const incidente of resumen.incidentes) {
      const pagina = paginaDeIncidente(idioma, incidente.id, incidente.titulo[idioma]);
      const destino = join(carpeta, `${rutaDeFicha(incidente.id, idioma)}.html`);
      await mkdir(dirname(destino), { recursive: true });
      await writeFile(destino, aplicarCabecera(plantilla, pagina), "utf-8");
    }
  }
  // Restos del prerenderizado que la web no usa.
  await rm(join(carpeta, ".vite"), { recursive: true, force: true });
  for (const nombre of await readdir(carpeta)) {
    if (nombre.startsWith(RESTO_DE_DATOS_DE_RUTA)) await rm(join(carpeta, nombre));
  }
  console.log(`páginas: ${resumen.incidentes.length} incidentes en ${IDIOMAS.length} idiomas`);
}
