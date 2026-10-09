// De dónde lee el build los datos publicados (configuracion/publicacion_web.json):
//
// - "github": la carpeta publicacion/ del repositorio, como siempre;
// - "almacen": el almacén público (configuracion/almacen_publico.json, prefijo publicacion/), donde
//   los deja la recogida (recogida/publicacion.py). Se baja primero el manifiesto y después cada
//   fichero, y cada uno se comprueba con la huella SHA-256 del manifiesto: si el almacén no
//   responde o algo no cuadra (por ejemplo, una recogida a medio subir), se reintenta y, al final,
//   el build falla y en producción sigue la versión anterior. Nunca se construye una web vacía.
//
// EODI_PUBLICACION, si está, manda sobre todo: una carpeta local con los mismos ficheros (pruebas
// y desarrollo con datos de ejemplo).

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const FICHEROS_PUBLICADOS = [
  "incidentes.geojson",
  "incidentes_sin_ubicacion.json",
  "ucrania.json",
  "prevision.json",
] as const;
export const PREFIJO = "publicacion/";
export const MANIFIESTO = "manifiesto.json";

export interface Manifiesto {
  version: number;
  generado: string;
  ficheros: Record<string, { bytes: number; sha256: string }>;
}

export type Leer = (url: string) => Promise<Uint8Array>;

async function leerHttp(url: string): Promise<Uint8Array> {
  const respuesta = await fetch(url, {
    headers: { "Cache-Control": "no-cache", "User-Agent": "EODI-web-build" },
    signal: AbortSignal.timeout(60_000),
  });
  if (!respuesta.ok) throw new Error(`${url}: HTTP ${respuesta.status}`);
  return new Uint8Array(await respuesta.arrayBuffer());
}

function sha256(datos: Uint8Array): string {
  return createHash("sha256").update(datos).digest("hex");
}

function esManifiesto(valor: unknown): valor is Manifiesto {
  if (typeof valor !== "object" || valor === null) return false;
  const ficheros = (valor as { ficheros?: unknown }).ficheros;
  return typeof ficheros === "object" && ficheros !== null;
}

/** Baja los ficheros del almacén a `destino`, comprobados con el manifiesto. */
export async function descargar(
  base: string,
  destino: string,
  leer: Leer = leerHttp,
  intentos = 3,
  esperaMs = 10_000,
): Promise<Manifiesto> {
  let ultimoError: unknown = null;
  for (let intento = 0; intento < intentos; intento++) {
    if (intento > 0) await new Promise((hecho) => setTimeout(hecho, esperaMs));
    try {
      const crudo = await leer(`${base}/${PREFIJO}${MANIFIESTO}`);
      const manifiesto: unknown = JSON.parse(new TextDecoder().decode(crudo));
      if (!esManifiesto(manifiesto)) throw new Error("el manifiesto no tiene ficheros");
      for (const nombre of ["incidentes.geojson", "ucrania.json"]) {
        if (!(nombre in manifiesto.ficheros)) throw new Error(`el manifiesto no trae ${nombre}`);
      }
      await mkdir(destino, { recursive: true });
      for (const [nombre, esperado] of Object.entries(manifiesto.ficheros)) {
        if (!(FICHEROS_PUBLICADOS as readonly string[]).includes(nombre)) continue;
        const datos = await leer(`${base}/${PREFIJO}${nombre}`);
        if (sha256(datos) !== esperado.sha256) {
          throw new Error(`${nombre} no coincide con el manifiesto (¿una recogida a medio subir?)`);
        }
        await writeFile(join(destino, nombre), datos);
      }
      return manifiesto;
    } catch (error) {
      ultimoError = error;
      console.warn(`publicación del almacén, intento ${intento + 1}: ${String(error)}`);
    }
  }
  throw new Error(
    `no se pudieron leer los datos publicados del almacén: ${String(ultimoError)}. ` +
      "El build falla y en producción sigue la versión anterior.",
  );
}

/** La carpeta con los ficheros publicados que usa el build. */
export async function carpetaPublicacion(raiz: string, web: string): Promise<string> {
  const local = process.env.EODI_PUBLICACION;
  if (local !== undefined && local.length > 0) return local;
  const configuracion = JSON.parse(
    await readFile(join(raiz, "configuracion", "publicacion_web.json"), "utf-8"),
  ) as { origen: string };
  if (configuracion.origen === "github") return join(raiz, "publicacion");
  if (configuracion.origen !== "almacen") {
    throw new Error(`configuracion/publicacion_web.json: origen desconocido ${configuracion.origen}`);
  }
  const almacen = JSON.parse(
    await readFile(join(raiz, "configuracion", "almacen_publico.json"), "utf-8"),
  ) as { publico: string };
  const destino = join(web, ".publicacion");
  const manifiesto = await descargar(almacen.publico.replace(/\/$/, ""), destino);
  console.log(`datos publicados del almacén, generados el ${manifiesto.generado}`);
  return destino;
}

/** Pide un objeto del almacén: null si no está (el almacén responde 403 a lo que no existe). */
export type LeerSiExiste = (url: string) => Promise<Uint8Array | null>;

async function leerSiExisteHttp(url: string): Promise<Uint8Array | null> {
  const respuesta = await fetch(url, {
    headers: { "Cache-Control": "no-cache", "User-Agent": "EODI-web-build" },
    signal: AbortSignal.timeout(60_000),
  });
  if (respuesta.status === 403 || respuesta.status === 404) return null;
  if (!respuesta.ok) throw new Error(`${url}: HTTP ${respuesta.status}`);
  return new Uint8Array(await respuesta.arrayBuffer());
}

/**
 * Las versiones citables de los datos abiertos (recogida/versiones.py): el índice del almacén y
 * el metadatos.json de cada versión, comprobado con la huella del índice. Sin índice todavía, una
 * lista vacía; si el almacén falla o algo no cuadra, el build falla (y sigue la web anterior).
 * Con EODI_PUBLICACION, el fichero versiones.json de esa carpeta (pruebas), si está.
 */
export async function leerVersiones(raiz: string, leer: LeerSiExiste = leerSiExisteHttp): Promise<unknown> {
  const local = process.env.EODI_PUBLICACION;
  if (local !== undefined && local.length > 0) {
    try {
      return JSON.parse(await readFile(join(local, "versiones.json"), "utf-8")) as unknown;
    } catch {
      return { versiones: [] };
    }
  }
  const almacen = JSON.parse(
    await readFile(join(raiz, "configuracion", "almacen_publico.json"), "utf-8"),
  ) as { publico: string };
  const conf = JSON.parse(
    await readFile(join(raiz, "configuracion", "versiones_datos.json"), "utf-8"),
  ) as { prefijo: string; indice: string };
  const base = almacen.publico.replace(/\/$/, "");
  const indice = await leer(`${base}/${conf.indice}`);
  if (indice === null) return { versiones: [] };
  const entradas = (JSON.parse(new TextDecoder().decode(indice)) as {
    versiones: { version: string; metadatos_sha256: string }[];
  }).versiones;
  const versiones: unknown[] = [];
  for (const entrada of entradas) {
    const datos = await leer(`${base}/${conf.prefijo}${entrada.version}/metadatos.json`);
    if (datos === null) throw new Error(`versión ${entrada.version}: falta su metadatos.json`);
    if (sha256(datos) !== entrada.metadatos_sha256) {
      throw new Error(`versión ${entrada.version}: metadatos.json no coincide con el índice`);
    }
    versiones.push(JSON.parse(new TextDecoder().decode(datos)));
  }
  return { versiones };
}

// Uso: node scripts/publicacion.ts — escribe la carpeta con los datos publicados de verdad (los
// baja si la web los lee del almacén). Lo usa el trabajo «datos-publicados» de la integración
// continua.
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const web = join(dirname(fileURLToPath(import.meta.url)), "..");
  console.log(await carpetaPublicacion(join(web, ".."), web));
}
