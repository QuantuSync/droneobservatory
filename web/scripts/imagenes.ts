// Las imágenes de la vista previa al compartir (Open Graph y Twitter), hechas en cada build con los
// datos publicados y sin ningún servicio de fuera: el contorno de Europa (Natural Earth,
// public/mapa/paises.geojson) con los puntos, el nombre del observatorio y, en la de cada ficha, su
// punto, su titular y cómo consta hoy. El texto lo convierte en trazos satori (con la letra Onest
// de la web) y resvg lo pasa a PNG, todo dentro del build. Si una imagen falla, en su lugar va la
// general: ninguna página se queda sin imagen.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { crc32, deflateSync } from "node:zlib";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { Resvg, initWasm } from "@resvg/resvg-wasm";
import satori from "satori";

import { constaCorto, diaEscrito } from "../src/datos/relato.ts";
import { marcaDe } from "../src/datos/presencia.ts";
import type { IncidenteDetalle, IncidenteResumen, MarcaIncidente } from "../src/datos/tipos.ts";
import { textos } from "../src/i18n/index.ts";
import { COLOR_MARCA, PALETA } from "../src/paleta.ts";
import {
  IDIOMAS,
  IMAGEN_COMPARTIR,
  IMAGEN_COMPARTIR_ALTO as ALTO,
  IMAGEN_COMPARTIR_ANCHO as ANCHO,
  NOMBRE,
  imagenDeFicha,
} from "../src/sitio.ts";
import type { Idioma } from "../src/sitio.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const requerir = createRequire(import.meta.url);

/** Europa en la imagen: de las Azores a los Urales, de Chipre al cabo Norte (Mercator). */
const CAJA = { oeste: -25, este: 45, sur: 33.5, norte: 71.5 } as const;
/** El mapa ocupa la parte derecha; el texto va encima de la izquierda, sobre un velo. */
const MAPA_X = 470;
const MARGEN = 56;
const ANCHO_TEXTO = 600;
const LARGO_TITULAR = 130;

function mercatorY(lat: number): number {
  return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
}

const ESCALA = ALTO / (mercatorY(CAJA.norte) - mercatorY(CAJA.sur));

/** Un punto [lon, lat] en píxeles de la imagen. */
export function proyectar(lon: number, lat: number): [number, number] {
  const x = MAPA_X + ((lon - CAJA.oeste) * Math.PI) / 180 * ESCALA;
  const y = (mercatorY(CAJA.norte) - mercatorY(lat)) * ESCALA;
  return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
}

type Anillo = [number, number][];
interface Geometria {
  type: "Polygon" | "MultiPolygon";
  coordinates: Anillo[] | Anillo[][];
}

/** Los países como un solo trazo SVG (los anillos que caen fuera de la imagen no se dibujan). */
export function trazoDePaises(geometrias: readonly Geometria[]): string {
  const partes: string[] = [];
  for (const g of geometrias) {
    const poligonos = (g.type === "Polygon" ? [g.coordinates] : g.coordinates) as Anillo[][];
    for (const poligono of poligonos) {
      for (const anillo of poligono) {
        const puntos = anillo.map(([lon, lat]) => proyectar(lon, Math.max(-85, Math.min(85, lat))));
        if (puntos.every(([x]) => x > ANCHO + 200) || puntos.every(([, y]) => y > ALTO + 200 || y < -200)) continue;
        let anterior = "";
        const texto: string[] = [];
        for (const [x, y] of puntos) {
          const par = `${Math.round(x)},${Math.round(y)}`;
          if (par !== anterior) texto.push(par);
          anterior = par;
        }
        if (texto.length >= 3) partes.push(`M${texto.join("L")}Z`);
      }
    }
  }
  return partes.join("");
}

/** Dónde se dibuja un incidente: su punto o el de su lugar aproximado; null sin ninguno. */
function lugarDe(i: IncidenteResumen): [number, number] | null {
  if (i.punto !== null) return proyectar(i.punto.lon, i.punto.lat);
  if (i.aproximado !== null) return proyectar(i.aproximado.lon, i.aproximado.lat);
  return null;
}

function colorDe(marca: MarcaIncidente): string {
  return COLOR_MARCA[marca];
}

/** El fondo: el mapa, el velo que deja leer el texto y los puntos (el destacado, encima y grande). */
function fondo(trazo: string, puntos: readonly { xy: [number, number]; color: string }[], destacado: { xy: [number, number]; color: string } | null): string {
  const circulos = puntos.map(({ xy: [x, y], color }) => `<circle cx="${x}" cy="${y}" r="3.2" fill="${color}" fill-opacity="${destacado === null ? 0.85 : 0.35}"/>`).join("");
  const marca =
    destacado === null
      ? ""
      : `<circle cx="${destacado.xy[0]}" cy="${destacado.xy[1]}" r="26" fill="none" stroke="${destacado.color}" stroke-width="3" stroke-opacity="0.7"/>` +
        `<circle cx="${destacado.xy[0]}" cy="${destacado.xy[1]}" r="11" fill="${destacado.color}" stroke="#f4f7fb" stroke-width="3"/>`;
  return (
    `<rect width="${ANCHO}" height="${ALTO}" fill="${PALETA.fondo}"/>` +
    `<path d="${trazo}" fill="#16233a" stroke="#34496b" stroke-width="1" stroke-linejoin="round" shape-rendering="crispEdges"/>` +
    circulos +
    `<defs><linearGradient id="velo" x1="0" x2="1" y1="0" y2="0">` +
    `<stop offset="0" stop-color="${PALETA.fondo}" stop-opacity="0.97"/><stop offset="0.42" stop-color="${PALETA.fondo}" stop-opacity="0.9"/>` +
    `<stop offset="0.62" stop-color="${PALETA.fondo}" stop-opacity="0.15"/><stop offset="1" stop-color="${PALETA.fondo}" stop-opacity="0"/></linearGradient></defs>` +
    `<rect width="${ANCHO}" height="${ALTO}" fill="url(#velo)"/>` +
    marca
  );
}

interface Nodo {
  type: string;
  props: { style?: Record<string, unknown>; children?: (Nodo | string)[] | Nodo | string; src?: string; width?: number; height?: number };
}

function div(style: Record<string, unknown>, ...children: (Nodo | string)[]): Nodo {
  return { type: "div", props: { style: { display: "flex", ...style }, children } };
}

function recortar(texto: string, largo: number): string {
  return texto.length <= largo ? texto : `${texto.slice(0, largo - 1).replace(/\s+\S*$/u, "")}…`;
}

interface Herramientas {
  fuentes: { name: string; data: Buffer; weight: 400 | 700; style: "normal" }[];
  trazo: string;
  logo: string;
}

/** El texto (en trazos) como el contenido de un <svg> de satori, sin su etiqueta de fuera. */
async function capaDeTexto(h: Herramientas, nodo: Nodo): Promise<string> {
  const svg = await satori(nodo as never, { width: ANCHO, height: ALTO, fonts: h.fuentes });
  return svg.replace(/^<svg[^>]*>/u, "").replace(/<\/svg>\s*$/u, "");
}

/** Bits por canal que se guardan: con 6, la imagen pesa menos de la mitad y no se nota a la vista. */
const BITS = 6;

function trozo(tipo: string, datos: Buffer): Buffer {
  const cabecera = Buffer.alloc(8);
  cabecera.writeUInt32BE(datos.length, 0);
  cabecera.write(tipo, 4, "ascii");
  const cola = Buffer.alloc(4);
  cola.writeUInt32BE(crc32(Buffer.concat([cabecera.subarray(4), datos])) >>> 0, 0);
  return Buffer.concat([cabecera, datos, cola]);
}

/**
 * PNG en color verdadero sin transparencia, con los canales recortados a BITS y el mejor filtro de
 * cada fila (ninguno, izquierda o arriba): el que deja menos que comprimir.
 */
export function codificarPng(rgba: Uint8Array, ancho: number, alto: number): Uint8Array {
  const mascara = (0xff << (8 - BITS)) & 0xff;
  const fila = ancho * 3;
  const filas: Buffer[] = [];
  let anterior = Buffer.alloc(fila);
  for (let y = 0; y < alto; y++) {
    const actual = Buffer.alloc(fila);
    for (let x = 0; x < ancho; x++) {
      for (let c = 0; c < 3; c++) actual[x * 3 + c] = (rgba[(y * ancho + x) * 4 + c] ?? 0) & mascara;
    }
    const candidatos: Buffer[] = [Buffer.concat([Buffer.from([0]), actual])];
    const izquierda = Buffer.alloc(fila + 1, 1);
    const arriba = Buffer.alloc(fila + 1, 2);
    for (let i = 0; i < fila; i++) {
      izquierda[i + 1] = ((actual[i] ?? 0) - (i >= 3 ? (actual[i - 3] ?? 0) : 0)) & 0xff;
      arriba[i + 1] = ((actual[i] ?? 0) - (anterior[i] ?? 0)) & 0xff;
    }
    candidatos.push(izquierda, arriba);
    const coste = (b: Buffer) => b.reduce((suma, v, i) => (i === 0 ? suma : suma + (v < 128 ? v : 256 - v)), 0);
    filas.push(candidatos.reduce((mejor, c) => (coste(c) < coste(mejor) ? c : mejor)));
    anterior = actual;
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(ancho, 0);
  ihdr.writeUInt32BE(alto, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    trozo("IHDR", ihdr),
    trozo("IDAT", deflateSync(Buffer.concat(filas), { level: 9 })),
    trozo("IEND", Buffer.alloc(0)),
  ]);
}

function png(svg: string): Uint8Array {
  const imagen = new Resvg(`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${ANCHO}" height="${ALTO}" viewBox="0 0 ${ANCHO} ${ALTO}">${svg}</svg>`, {
    fitTo: { mode: "width", value: ANCHO },
    font: { loadSystemFonts: false },
  }).render();
  return codificarPng(imagen.pixels, imagen.width, imagen.height);
}

/** La imagen general: los puntos actuales, el logo, el nombre y el lema. */
async function imagenGeneral(h: Herramientas, puntos: readonly { xy: [number, number]; color: string }[], idioma: Idioma): Promise<Uint8Array> {
  const texto = await capaDeTexto(
    h,
    div(
      { width: ANCHO, height: ALTO, alignItems: "center", padding: `0 ${MARGEN}px`, fontFamily: "Onest", color: "#f4f7fb" },
      { type: "img", props: { src: h.logo, width: 200, height: 200, style: { marginRight: 36 } } },
      div(
        { flexDirection: "column", width: 420 },
        div({ fontSize: 50, fontWeight: 700, lineHeight: 1.05 }, NOMBRE),
        div({ marginTop: 18, fontSize: 24, lineHeight: 1.35, color: "#93a0b4" }, textos(idioma).compartir.lema),
        div({ marginTop: 18, fontSize: 22, color: "#93a0b4" }, "droneobservatory.eu"),
      ),
    ),
  );
  return png(fondo(h.trazo, puntos, null) + texto);
}

/** La imagen de una ficha: su punto destacado, el titular, cómo consta hoy, la fecha y el lugar. */
async function imagenDeIncidente(
  h: Herramientas,
  puntos: readonly { xy: [number, number]; color: string }[],
  i: IncidenteResumen,
  d: IncidenteDetalle,
  idioma: Idioma,
): Promise<Uint8Array> {
  const marca = marcaDe({ estado: i.estado, presencia: i.presencia });
  const color = colorDe(marca);
  const xy = lugarDe(i);
  const t = textos(idioma);
  const lugar = i.lugar?.[idioma] ?? "";
  const texto = await capaDeTexto(
    h,
    div(
      { width: ANCHO, height: ALTO, flexDirection: "column", justifyContent: "space-between", padding: `${MARGEN - 8}px ${MARGEN}px`, fontFamily: "Onest", color: "#f4f7fb" },
      div(
        { alignItems: "center", fontSize: 22, color: "#93a0b4" },
        { type: "img", props: { src: h.logo, width: 44, height: 44, style: { marginRight: 14 } } },
        `${NOMBRE} · droneobservatory.eu`,
      ),
      div(
        { flexDirection: "column", width: ANCHO_TEXTO },
        div({ fontSize: 22, color: "#93a0b4", textTransform: "uppercase", letterSpacing: 1 }, t.tipo[d.tipo]),
        div({ marginTop: 10, fontSize: 44, fontWeight: 700, lineHeight: 1.12 }, recortar(i.titulo[idioma], LARGO_TITULAR)),
        div(
          { marginTop: 22, alignItems: "center", fontSize: 28, fontWeight: 700, color },
          div({ width: 18, height: 18, borderRadius: 9, backgroundColor: color, marginRight: 12 }),
          // Sin fecha: la imagen solo cambia cuando cambia la ficha.
          constaCorto(d, idioma),
        ),
      ),
      div({ fontSize: 24, color: "#c9d2df" }, [diaEscrito(d.tiempo.inicio.valor, idioma), lugar].filter((p) => p !== "").join(" · "), `  ·  ${i.id}`),
    ),
  );
  return png(fondo(h.trazo, puntos, xy === null ? null : { xy, color }) + texto);
}

async function preparar(): Promise<Herramientas> {
  await initWasm(await readFile(requerir.resolve("@resvg/resvg-wasm/index_bg.wasm")));
  const fuente = (nombre: string) => readFile(requerir.resolve(`@fontsource/onest/files/${nombre}`));
  const fuentes: Herramientas["fuentes"] = [];
  for (const tramo of ["latin", "latin-ext", "cyrillic"]) {
    for (const peso of [400, 700] as const) {
      fuentes.push({ name: "Onest", data: await fuente(`onest-${tramo}-${peso}-normal.woff`), weight: peso, style: "normal" });
    }
  }
  const paises = JSON.parse(await readFile(join(WEB, "public", "mapa", "paises.geojson"), "utf-8")) as { features: { geometry: Geometria }[] };
  const logo = `data:image/png;base64,${(await readFile(join(WEB, "public", "marca", "logo-384.png"))).toString("base64")}`;
  return { fuentes, trazo: trazoDePaises(paises.features.map((f) => f.geometry)), logo };
}

/** Escribe la imagen general de cada idioma y la de cada ficha en la carpeta del build. */
export async function escribirImagenes(
  carpeta: string,
  incidentes: readonly IncidenteResumen[],
  detalles: ReadonlyMap<string, IncidenteDetalle>,
): Promise<void> {
  const inicio = Date.now();
  const h = await preparar();
  const puntos = incidentes.flatMap((i) => {
    const xy = lugarDe(i);
    return xy === null ? [] : [{ xy, color: colorDe(marcaDe({ estado: i.estado, presencia: i.presencia })) }];
  });
  const generales = new Map<Idioma, Uint8Array>();
  for (const idioma of IDIOMAS) {
    const imagen = await imagenGeneral(h, puntos, idioma);
    generales.set(idioma, imagen);
    await writeFile(join(carpeta, IMAGEN_COMPARTIR[idioma].slice(1)), imagen);
  }
  await mkdir(join(carpeta, "compartir"), { recursive: true });
  let fallidas = 0;
  for (const i of incidentes) {
    const d = detalles.get(i.id);
    for (const idioma of IDIOMAS) {
      let imagen: Uint8Array | undefined;
      try {
        if (d !== undefined) imagen = await imagenDeIncidente(h, puntos, i, d, idioma);
      } catch (error) {
        console.warn(`imagen de ${i.id} (${idioma}): ${String(error)}; va la general`);
      }
      if (imagen === undefined) fallidas += 1;
      await writeFile(join(carpeta, imagenDeFicha(i.id, idioma).slice(1)), imagen ?? generales.get(idioma) ?? new Uint8Array());
    }
  }
  console.log(
    `imágenes: ${IDIOMAS.length} generales y ${incidentes.length * IDIOMAS.length} de fichas (${fallidas} con la general) en ${Math.round((Date.now() - inicio) / 1000)} s`,
  );
}
