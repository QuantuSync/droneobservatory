// Pasos del build sobre las páginas ya prerenderizadas: sacar a ficheros los scripts en
// línea (la política de seguridad solo admite scripts de este sitio) y escribir todas las
// páginas con su contenido en texto (src/texto/paginas.ts): la portada y cada incidente con el
// mapa encima, y las listas, los países, la guerra en Ucrania, la metodología y la ayuda como
// texto. Además, el sitemap, llms.txt, la página 404 y la lista que lee la función del borde
// (../../api/borde.ts): las redirecciones de los incidentes unidos a otro y los ataques que
// existen. Todo sale de los datos publicados: con cada actualización de los datos se
// vuelve a construir la web y las páginas quedan al día.

import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { aplicarCabecera } from "../src/cabecera.ts";
import type { Prevision } from "../src/datos/prevision.ts";
import type { ColeccionIncidentes, IncidenteDetalle, Resumen, ResumenUcrania } from "../src/datos/tipos.ts";
import { RUTA_LISTA_BORDE } from "../../api/borde.ts";
import type { RutasBorde } from "../../api/borde.ts";
import { separarScriptsEnLinea } from "../src/seguridad/scripts.ts";
import { IDIOMAS, rutaDeFicha } from "../src/sitio.ts";
import type { Idioma } from "../src/sitio.ts";
import { e, html } from "../src/texto/html.ts";
import { jsonLd, marco, paginas } from "../src/texto/paginas.ts";
import type { PaginaTexto } from "../src/texto/paginas.ts";
import { llmsTxt, noEncontrada, redirecciones, sitemap } from "../src/texto/salidas.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const SALIDA = join(WEB, "dist");
const DATOS = join(WEB, "public", "datos");
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

/** Fichero que sirve una dirección (el despliegue quita la extensión .html). */
export function ficheroDeRuta(ruta: string): string {
  if (ruta === "/") return "index.html";
  if (ruta === "/en") return join("en", "index.html");
  return `${ruta.slice(1)}.html`;
}

function cabeceraDe(pagina: PaginaTexto) {
  return {
    idioma: pagina.idioma,
    id: null,
    titulo: pagina.titulo,
    descripcion: pagina.descripcion,
    rutas: pagina.rutas,
  };
}

function bloqueDeTexto(pagina: PaginaTexto, actualizado: string): string {
  return e("div", { class: "texto-pagina", lang: pagina.idioma }, marco(pagina, actualizado)).valor;
}

function conDatosEstructurados(documento: string, pagina: PaginaTexto): string {
  const bloques = html(pagina.estructurados.map((d) => jsonLd(d))).valor;
  return documento.replace("</head>", `${bloques}</head>`);
}

/**
 * Página con el mapa: la portada prerenderizada con sus metadatos y, detrás de la aplicación,
 * el texto. Con el código del navegador activo, el texto no se pinta (estilos.css); sin él, no
 * se pinta la aplicación y queda el texto.
 */
export function paginaConMapa(plantilla: string, pagina: PaginaTexto, actualizado: string): string {
  const documento = conDatosEstructurados(aplicarCabecera(plantilla, cabeceraDe(pagina)), pagina);
  return documento.replace("</body>", `${bloqueDeTexto(pagina, actualizado)}</body>`);
}

/** Página solo de texto: la misma cabecera y la misma hoja de estilos, sin la aplicación. */
export function paginaSoloTexto(plantilla: string, pagina: PaginaTexto, actualizado: string): string {
  const conCabecera = conDatosEstructurados(aplicarCabecera(plantilla, cabeceraDe(pagina)), pagina);
  const finCabecera = conCabecera.indexOf("</head>");
  const cabecera = conCabecera
    .slice(0, finCabecera)
    .replace(/<script\b[^>]*\bsrc="[^"]*"[^>]*><\/script>/g, "")
    .replace(/<link rel="modulepreload"[^>]*>/g, "");
  return `${cabecera}</head>\n  <body class="pagina-texto">${bloqueDeTexto(pagina, actualizado)}</body>\n</html>\n`;
}

async function escribirPagina(carpeta: string, ruta: string, contenido: string): Promise<void> {
  const destino = join(carpeta, ficheroDeRuta(ruta));
  await mkdir(dirname(destino), { recursive: true });
  await writeFile(destino, contenido, "utf-8");
}

async function leerJson<T>(ruta: string): Promise<T> {
  return JSON.parse(await readFile(ruta, "utf-8")) as T;
}

/** Último paso del build: todas las páginas, el sitemap, llms.txt, la 404 y la lista del borde. */
export async function terminarPaginas(carpeta: string): Promise<void> {
  const resumen = await leerJson<Resumen>(join(DATOS, "resumen.json"));
  const ucrania = await leerJson<ResumenUcrania>(join(DATOS, "ucrania-resumen.json"));
  const coleccion = await leerJson<ColeccionIncidentes>(join(DATOS, "incidentes.geojson"));
  const detalles = new Map<string, IncidenteDetalle>();
  for (const incidente of resumen.incidentes) {
    detalles.set(incidente.id, await leerJson<IncidenteDetalle>(join(DATOS, "incidentes", `${incidente.id}.json`)));
  }
  const recursos = await readdir(join(carpeta, CARPETA_SCRIPTS));
  const plantillas = new Map<Idioma, string>();
  for (const idioma of IDIOMAS) {
    plantillas.set(
      idioma,
      precargarFuentes(await sacarScriptsEnLinea(await readFile(portada(carpeta, idioma), "utf-8")), recursos),
    );
  }
  // La previsión, si está publicada (scripts/datos.ts la valida y la copia).
  const rutaPrevision = join(DATOS, "prevision.json");
  const prevision = existsSync(rutaPrevision) ? await leerJson<Prevision>(rutaPrevision) : null;
  const todas = paginas({ resumen, detalles, ucrania, prevision });
  for (const pagina of todas) {
    const plantilla = plantillas.get(pagina.idioma);
    if (plantilla === undefined) throw new Error(`sin portada en ${pagina.idioma}`);
    const contenido = pagina.conMapa
      ? paginaConMapa(plantilla, pagina, resumen.actualizado)
      : paginaSoloTexto(plantilla, pagina, resumen.actualizado);
    await escribirPagina(carpeta, pagina.rutas[pagina.idioma], contenido);
  }
  const plantillaEs = plantillas.get("es");
  if (plantillaEs === undefined) throw new Error("sin portada en español");
  await writeFile(join(carpeta, "404.html"), paginaSoloTexto(plantillaEs, noEncontrada(), resumen.actualizado), "utf-8");
  await writeFile(join(carpeta, "sitemap.xml"), sitemap(todas), "utf-8");
  await writeFile(join(carpeta, "llms.txt"), llmsTxt(resumen), "utf-8");
  const publicados = new Set(resumen.incidentes.map((i) => i.id));
  // Lo que lee la función del borde: una regla para todos los unidos en los dos idiomas (sin
  // gastar capacidad de redirecciones de Vercel) y los ataques que existen (los demás, 404).
  const lista = redirecciones(coleccion.unidos ?? {}, publicados);
  const borde: RutasBorde = {
    redirecciones: Object.fromEntries(lista.map((r) => [r.source, r.destination])),
    ataques: ucrania.ataques.map((a) => a[0]),
  };
  await writeFile(join(carpeta, RUTA_LISTA_BORDE.slice(1)), JSON.stringify(borde), "utf-8");
  // Restos del prerenderizado que la web no usa.
  await rm(join(carpeta, ".vite"), { recursive: true, force: true });
  for (const nombre of await readdir(carpeta)) {
    if (nombre.startsWith(RESTO_DE_DATOS_DE_RUTA)) await rm(join(carpeta, nombre));
  }
  const fichas = resumen.incidentes.length * IDIOMAS.length;
  console.log(
    `páginas: ${todas.length} (${fichas} de incidentes) en ${IDIOMAS.length} idiomas; ` +
      `${lista.length} redirecciones de incidentes unidos y ${borde.ataques.length} ataques en ` +
      `${RUTA_LISTA_BORDE}; ejemplo ${rutaDeFicha(resumen.incidentes[0]?.id ?? "", "es")}`,
  );
}
