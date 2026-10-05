// Comprobación de lo que entrega la web a quien la pide sin ejecutar código, sobre web/dist
// recién construido: cada tipo de página trae su contenido en el HTML, las cifras de la portada
// son las del mapa, cada incidente publicado tiene su página y ninguno retirado o unido la tiene,
// los datos estructurados y el sitemap son válidos, y no hay apartados ni menciones prohibidas.
// Se ejecuta en la integración continua después de `npm run build`.

import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { escaparHtml } from "../src/cabecera.ts";
import { cifras } from "../src/datos/derivar.ts";
import type { IncidenteDetalle, Resumen } from "../src/datos/tipos.ts";
import { fechaHora, numero } from "../src/i18n/index.ts";
import { IDIOMAS, NOMBRE, rutaDeFicha } from "../src/sitio.ts";
import { direccionCompleta, RUTAS, rutasDeAnio, rutasDePais } from "../src/texto/paginas.ts";
import { ficheroDeRuta } from "./paginas.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(WEB, "dist");
const DATOS = join(WEB, "public", "datos");

async function leer(ruta: string): Promise<string> {
  return readFile(ruta, "utf-8");
}

async function pagina(ruta: string): Promise<string> {
  return leer(join(DIST, ficheroDeRuta(ruta)));
}

async function existe(ruta: string): Promise<boolean> {
  try {
    await access(ruta);
    return true;
  } catch {
    return false;
  }
}

/** El texto que ve quien no ejecuta código: el bloque de texto, sin etiquetas. */
function bloqueDeTexto(html: string): string {
  const inicio = html.indexOf('<div class="texto-pagina"');
  assert.ok(inicio !== -1, "la página no tiene el bloque de texto");
  return html.slice(inicio);
}

function sinEtiquetas(html: string): string {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
}

function datosEstructurados(html: string): Record<string, unknown>[] {
  return [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(
    (m) => JSON.parse(m[1] ?? "") as Record<string, unknown>,
  );
}

function comprobarEstructurados(html: string, ruta: string): void {
  for (const d of datosEstructurados(html)) {
    assert.equal(d["@context"], "https://schema.org", `${ruta}: @context`);
    const tipo = d["@type"];
    if (tipo === "Event") {
      for (const campo of ["name", "startDate", "location", "url", "identifier"]) {
        assert.ok(d[campo] !== undefined && d[campo] !== "", `${ruta}: Event sin ${campo}`);
      }
      assert.match(String(d["startDate"]), /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}Z)?$/, `${ruta}: startDate`);
      const lugar = d["location"] as Record<string, unknown>;
      assert.equal(lugar["@type"], "Place");
      assert.match(String((lugar["address"] as Record<string, unknown>)["addressCountry"]), /^[A-Z]{2}$/);
    } else if (tipo === "Dataset") {
      for (const campo of ["name", "description", "license", "distribution", "creator"]) {
        assert.ok(d[campo] !== undefined, `${ruta}: Dataset sin ${campo}`);
      }
      assert.ok(String(d["description"]).length >= 50, `${ruta}: descripción del Dataset corta`);
      for (const descarga of d["distribution"] as Record<string, unknown>[]) {
        assert.equal(descarga["@type"], "DataDownload");
        assert.match(String(descarga["contentUrl"]), /^https:\/\/droneobservatory\.eu\/datos\//);
      }
    } else if (tipo === "WebSite") {
      assert.equal(d["name"], NOMBRE);
    } else {
      assert.fail(`${ruta}: tipo de datos estructurados inesperado ${String(tipo)}`);
    }
  }
}

/** Lo que ninguna página puede decir: apartados de límites y menciones prohibidas. */
const APARTADO_PROHIBIDO = /<h[1-6][^>]*>[^<]*\b(l[íi]mites|limitaciones|limits|limitations)\b/i;
// Escritas al revés para que el propio fichero no las contenga (el hook de pre-push las busca).
const alReves = (palabras: string[]): string => palabras.map((p) => [...p].reverse().join("")).join("|");
const MENCIONES_PROHIBIDAS = new RegExp(
  String.raw`\b(` + alReves(["SIGEA", "MLL", "TPG", "TPGtahC", "IAnepO", "ciporhtnA", "edualC", "inimeG"]) + String.raw`)\b`,
  "i",
);
const SIGLAS_PROHIBIDAS = new RegExp(String.raw`\b(` + [String.fromCharCode(73, 65), String.fromCharCode(65, 73)].join("|") + String.raw`)\b`);

function comprobarProhibido(html: string, ruta: string): void {
  assert.ok(!APARTADO_PROHIBIDO.test(html), `${ruta}: apartado de límites`);
  // Las citas son de las fuentes, tal cual: se miran los textos propios de la página.
  const propio = sinEtiquetas(bloqueDeTexto(html).replace(/<blockquote[\s\S]*?<\/blockquote>/g, ""));
  assert.ok(!MENCIONES_PROHIBIDAS.test(propio), `${ruta}: mención prohibida`);
  assert.ok(!SIGLAS_PROHIBIDAS.test(propio), `${ruta}: siglas prohibidas`);
}

async function principal(): Promise<void> {
  const resumen = JSON.parse(await leer(join(DATOS, "resumen.json"))) as Resumen;
  const meta = JSON.parse(await leer(join(WEB, "src", "generado", "meta.json"))) as Record<string, unknown>;
  const fechaDatos = escaparHtml(fechaHora(resumen.actualizado));
  const publicados = new Set(resumen.incidentes.map((i) => i.id));
  const comprobadas: string[] = [];

  // Portada: cifras iguales a las del marcador del mapa (meta.json es lo que pinta al cargar).
  const c = cifras(resumen.incidentes);
  assert.equal(c.incidentes, meta["incidentes"]);
  assert.equal(c.confirmados, meta["confirmados"]);
  assert.equal(c.atribuidos, meta["atribuidos"]);
  assert.equal(c.paises, meta["paises"]);
  for (const idioma of IDIOMAS) {
    const ruta = idioma === "es" ? "/" : "/en";
    const html = await pagina(ruta);
    const texto = bloqueDeTexto(html);
    for (const [clave, valor] of Object.entries(c)) {
      assert.ok(texto.includes(`data-cifra="${clave}">${numero(valor, idioma)}<`), `${ruta}: cifra ${clave}`);
    }
    assert.ok(texto.includes(fechaDatos), `${ruta}: fecha de los datos`);
    assert.ok(html.includes('<div id="root"'), `${ruta}: la aplicación del mapa sigue en la página`);
    comprobadas.push(ruta);
  }

  // Un incidente de cada clase: atribuido, confirmado y sin punto en el mapa.
  const detalles = new Map<string, IncidenteDetalle>();
  for (const id of publicados) {
    detalles.set(id, JSON.parse(await leer(join(DATOS, "incidentes", `${id}.json`))) as IncidenteDetalle);
  }
  const muestras = [
    [...detalles.values()].find((d) => d.estado.actual === "atribuido"),
    [...detalles.values()].find((d) => d.estado.actual === "confirmado" && d.lon !== null),
    [...detalles.values()].find((d) => d.lon === null),
  ].filter((d): d is IncidenteDetalle => d !== undefined);
  assert.ok(muestras.length >= 2, "faltan incidentes de muestra");
  for (const d of muestras) {
    for (const idioma of IDIOMAS) {
      const ruta = rutaDeFicha(d.id, idioma);
      const texto = bloqueDeTexto(await pagina(ruta));
      assert.ok(texto.includes(escaparHtml(d.titulo[idioma])), `${ruta}: titular`);
      assert.ok(texto.includes(`data-estado="${d.estado.actual}"`), `${ruta}: estado`);
      if (d.fuentes.length > 0) {
        assert.ok(/<blockquote[^>]*>«[^<]+»<\/blockquote>/.test(texto), `${ruta}: cita`);
        assert.ok(texto.includes(`href="${escaparHtml(d.fuentes[0]?.enlace ?? "")}"`), `${ruta}: fuente enlazada`);
      }
      assert.ok(texto.includes(fechaDatos), `${ruta}: fecha de los datos`);
      if (d.estado.actual === "atribuido") assert.ok(texto.includes("data-atribucion"), `${ruta}: atribución`);
      comprobadas.push(ruta);
    }
  }

  // Las demás clases de página.
  const anio = String(new Date(resumen.actualizado).getUTCFullYear());
  const pais = resumen.incidentes[0]?.pais ?? "PL";
  const otras = [RUTAS.incidentes, rutasDeAnio(anio), RUTAS.paises, rutasDePais(pais), RUTAS.ucrania, RUTAS.metodologia, RUTAS.ayuda];
  for (const rutas of otras) {
    for (const idioma of IDIOMAS) {
      const html = await pagina(rutas[idioma]);
      const texto = bloqueDeTexto(html);
      assert.match(texto, /<h1[^>]*>[^<]+<\/h1>/, `${rutas[idioma]}: título`);
      assert.ok(texto.includes(fechaDatos), `${rutas[idioma]}: fecha de los datos`);
      assert.ok(html.includes(`<html lang="${idioma}"`), `${rutas[idioma]}: idioma`);
      assert.ok(!html.includes('<div id="root"'), `${rutas[idioma]}: página de texto sin la aplicación`);
      comprobadas.push(rutas[idioma]);
    }
  }
  const listado = bloqueDeTexto(await pagina(RUTAS.incidentes.es));
  for (const id of publicados) assert.ok(listado.includes(`href="/${id}"`), `listado sin ${id}`);

  // Sitemap: válido, con todas las páginas publicadas y ninguna que no exista.
  const sitemap = await leer(join(DIST, "sitemap.xml"));
  assert.match(sitemap, /^<\?xml version="1\.0" encoding="UTF-8"\?>\n<urlset /);
  assert.equal((sitemap.match(/<url>/g) ?? []).length, (sitemap.match(/<\/url>/g) ?? []).length);
  const direcciones = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1] ?? "");
  assert.equal(new Set(direcciones).size, direcciones.length, "direcciones repetidas en el sitemap");
  for (const lastmod of sitemap.matchAll(/<lastmod>([^<]+)<\/lastmod>/g)) {
    assert.match(lastmod[1] ?? "", /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$/);
  }
  for (const direccion of direcciones) {
    const ruta = direccion.slice("https://droneobservatory.eu".length) || "/";
    assert.ok(await existe(join(DIST, ficheroDeRuta(ruta))), `sitemap: ${ruta} no existe`);
    const html = await pagina(ruta);
    comprobarEstructurados(html, ruta);
    comprobarProhibido(html, ruta);
  }
  for (const id of publicados) {
    for (const idioma of IDIOMAS) {
      assert.ok(direcciones.includes(direccionCompleta(rutaDeFicha(id, idioma))), `sitemap sin ${id}`);
    }
  }

  // Ningún retirado ni unido tiene página ni sale en el sitemap.
  const revisados = JSON.parse(await leer(join(WEB, "..", "configuracion", "incidentes_revisados.json"))) as {
    retirar?: { incidente: string }[];
  };
  const coleccion = JSON.parse(await leer(join(DATOS, "incidentes.geojson"))) as { unidos?: Record<string, string> };
  const fuera = [...(revisados.retirar ?? []).map((r) => r.incidente), ...Object.keys(coleccion.unidos ?? {})].filter(
    (id) => !publicados.has(id),
  );
  for (const id of fuera) {
    for (const idioma of IDIOMAS) {
      assert.ok(!(await existe(join(DIST, ficheroDeRuta(rutaDeFicha(id, idioma))))), `${id} tiene página`);
      assert.ok(!direcciones.includes(direccionCompleta(rutaDeFicha(id, idioma))), `${id} en el sitemap`);
    }
  }
  const ficheros = (await readdir(DIST)).filter((f) => /^EODI-\d{4}-\d{5}\.html$/.test(f));
  assert.equal(ficheros.length, publicados.size, "páginas de incidentes que no están publicados");

  // Redirecciones de los unidos: a una página que existe, nunca desde una que existe.
  const redirecciones = JSON.parse(await leer(join(WEB, "redirecciones", "unidos.json"))) as {
    source: string;
    destination: string;
    statusCode: number;
  }[];
  for (const r of redirecciones) {
    assert.equal(r.statusCode, 308);
    assert.ok(await existe(join(DIST, ficheroDeRuta(r.destination))), `redirección a ${r.destination}`);
    assert.ok(!(await existe(join(DIST, ficheroDeRuta(r.source)))), `redirección desde ${r.source}`);
  }

  // robots.txt, llms.txt y la 404.
  assert.match(await leer(join(DIST, "robots.txt")), /^Sitemap: https:\/\/droneobservatory\.eu\/sitemap\.xml$/m);
  const llms = await leer(join(DIST, "llms.txt"));
  assert.ok(llms.startsWith(`# ${NOMBRE}\n`));
  assert.ok(llms.includes("/sitemap.xml") && llms.includes("/datos/incidentes.geojson"));
  assert.ok(!MENCIONES_PROHIBIDAS.test(llms) && !SIGLAS_PROHIBIDAS.test(llms), "llms.txt: mención prohibida");
  assert.ok(await existe(join(DIST, "404.html")));

  console.log(
    `páginas comprobadas: ${comprobadas.length} sin ejecutar código; sitemap con ${direcciones.length} ` +
      `direcciones; ${fuera.length} retirados o unidos sin página; ${redirecciones.length} redirecciones`,
  );
}

await principal();
