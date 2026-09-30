// Prepara los datos de la web a partir de ../publicacion: valida los dos ficheros públicos
// contra el esquema, los copia como descargas, genera sus versiones CSV, los resúmenes que
// carga la web, una ficha por incidente y por ataque, y security.txt. Si un fichero no
// valida, el build falla y la versión anterior de la web sigue publicada.

import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { csvAtaques, csvIncidentes } from "../src/datos/csv.ts";
import { detalleIncidente, meta, resumir, resumirUcrania } from "../src/datos/derivar.ts";
import { validarColeccion, validarPublicacionUcrania } from "../src/datos/validar.ts";
import type { Resultado } from "../src/datos/validar.ts";
import { RUTA_SECURITY_TXT, securityTxt } from "../src/seguridad/securityTxt.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const PUBLICACION = join(WEB, "..", "publicacion");
const PUBLICO = join(WEB, "public");
const DATOS = join(PUBLICO, "datos");
const GENERADO = join(WEB, "src", "generado");

async function leerJson(ruta: string): Promise<unknown> {
  return JSON.parse(await readFile(ruta, "utf-8")) as unknown;
}

function exigir<T>(nombre: string, resultado: Resultado<T>): T {
  if (!resultado.ok) {
    throw new Error(`${nombre} no cumple el esquema:\n  ${resultado.errores.join("\n  ")}`);
  }
  return resultado.datos;
}

async function escribir(ruta: string, contenido: string): Promise<void> {
  await mkdir(dirname(ruta), { recursive: true });
  await writeFile(ruta, contenido, "utf-8");
}

async function principal(): Promise<void> {
  const rutaIncidentes = join(PUBLICACION, "incidentes.geojson");
  const rutaUcrania = join(PUBLICACION, "ucrania.json");
  const coleccion = exigir("incidentes.geojson", validarColeccion(await leerJson(rutaIncidentes)));
  const ucrania = exigir("ucrania.json", validarPublicacionUcrania(await leerJson(rutaUcrania)));

  await rm(DATOS, { recursive: true, force: true });

  // Descargas: los ficheros publicados tal cual y sus versiones CSV.
  await escribir(join(DATOS, "incidentes.geojson"), await readFile(rutaIncidentes, "utf-8"));
  await escribir(join(DATOS, "ucrania.json"), await readFile(rutaUcrania, "utf-8"));
  await escribir(join(DATOS, "incidentes.csv"), csvIncidentes(coleccion));
  await escribir(join(DATOS, "ucrania.csv"), csvAtaques(ucrania));

  const resumen = resumir(coleccion, ucrania);
  await escribir(join(DATOS, "resumen.json"), JSON.stringify(resumen));
  await escribir(join(DATOS, "ucrania-resumen.json"), JSON.stringify(resumirUcrania(ucrania)));
  for (const feature of coleccion.features) {
    const detalle = JSON.stringify(detalleIncidente(feature));
    await escribir(join(DATOS, "incidentes", `${feature.id}.json`), detalle);
  }
  for (const ataque of ucrania.ataques) {
    await escribir(join(DATOS, "ataques", `${ataque.id}.json`), JSON.stringify(ataque));
  }

  await escribir(join(GENERADO, "meta.json"), JSON.stringify(meta(resumen)));
  await escribir(join(PUBLICO, RUTA_SECURITY_TXT), securityTxt(new Date()));

  console.log(
    `datos: ${coleccion.features.length} incidentes y ${ucrania.ataques.length} ataques, ` +
      `actualizados a ${resumen.actualizado}`,
  );
}

await principal();
