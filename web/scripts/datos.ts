// Prepara los datos de la web a partir de los datos publicados (scripts/publicacion.ts: la carpeta
// publicacion/ del repositorio o el almacén público): valida los ficheros públicos
// contra el esquema, los copia como descargas, genera sus versiones CSV, los resúmenes que
// carga la web, una ficha por incidente y por ataque, y security.txt. Si un fichero no
// valida, el build falla y la versión anterior de la web sigue publicada.

import { access, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { ultimasCorrecciones } from "../src/datos/correcciones.ts";
import { csvAtaques, csvIncidentes } from "../src/datos/csv.ts";
import { conLicencia } from "../src/datos/licencia.ts";
import {
  centrosDeRegiones,
  detalleIncidente,
  detalleSinUbicacion,
  meta,
  resumir,
  resumirUcrania,
} from "../src/datos/derivar.ts";
import type { ContornosRegiones } from "../src/datos/derivar.ts";
import { casarZonas, puntoMasCercano } from "../src/datos/guerraSatelite.ts";
import type { ZonaConfig } from "../src/datos/guerraSatelite.ts";
import type { PublicacionSinUbicacion } from "../src/datos/tipos.ts";
import {
  validarColeccion,
  validarPublicacionUcrania,
  validarCorrecciones,
  validarPrevision,
  validarSinUbicacion,
  validarVersiones,
} from "../src/datos/validar.ts";
import type { Resultado } from "../src/datos/validar.ts";
import { RUTA_SECURITY_TXT, securityTxt } from "../src/seguridad/securityTxt.ts";
import { carpetaPublicacion, leerVersiones } from "./publicacion.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const CONFIGURACION = join(WEB, "..", "configuracion");
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

async function existe(ruta: string): Promise<boolean> {
  try {
    await access(ruta);
    return true;
  } catch {
    return false;
  }
}

async function escribir(ruta: string, contenido: string): Promise<void> {
  await mkdir(dirname(ruta), { recursive: true });
  await writeFile(ruta, contenido, "utf-8");
}

async function principal(): Promise<void> {
  // EODI_PUBLICACION: otra carpeta con los mismos ficheros (pruebas en local con datos de ensayo).
  const PUBLICACION = await carpetaPublicacion(join(WEB, ".."), WEB);
  const rutaIncidentes = join(PUBLICACION, "incidentes.geojson");
  const rutaUcrania = join(PUBLICACION, "ucrania.json");
  const coleccion = exigir("incidentes.geojson", validarColeccion(await leerJson(rutaIncidentes)));
  const ucrania = exigir("ucrania.json", validarPublicacionUcrania(await leerJson(rutaUcrania)));
  // Los incidentes sin punto llegan en un fichero aparte, que puede no existir todavía.
  const rutaSinUbicacion = join(PUBLICACION, "incidentes_sin_ubicacion.json");
  const sinUbicacion: PublicacionSinUbicacion | null = (await existe(rutaSinUbicacion))
    ? exigir(
        "incidentes_sin_ubicacion.json",
        validarSinUbicacion(await leerJson(rutaSinUbicacion)),
      )
    : null;

  // El registro de correcciones (exportacion/correcciones.py), que puede no existir todavía: de
  // él salen su página de texto y la línea «Corregido el…» de cada ficha.
  const rutaCorrecciones = join(PUBLICACION, "correcciones.json");
  const correcciones = (await existe(rutaCorrecciones))
    ? exigir("correcciones.json", validarCorrecciones(await leerJson(rutaCorrecciones)))
    : null;
  const corregidos = correcciones === null ? new Map<string, string>() : ultimasCorrecciones(correcciones);
  const conCorreccion = <T extends object>(detalle: T, id: string): T => {
    const fecha = corregidos.get(id);
    return fecha === undefined ? detalle : { ...detalle, corregido: fecha };
  };

  await rm(DATOS, { recursive: true, force: true });

  const resumen = resumir(coleccion, ucrania, sinUbicacion);
  // Descargas: los ficheros publicados, con su licencia como primer miembro (datos/licencia.ts),
  // y sus versiones CSV, cuya licencia va en la cabecera HTTP de /datos (vercel.json).
  const publicado = async (ruta: string) => conLicencia(await readFile(ruta, "utf-8"), resumen.actualizado);
  await escribir(join(DATOS, "incidentes.geojson"), await publicado(rutaIncidentes));
  await escribir(join(DATOS, "ucrania.json"), await publicado(rutaUcrania));
  await escribir(join(DATOS, "incidentes.csv"), csvIncidentes(coleccion));
  await escribir(join(DATOS, "ucrania.csv"), csvAtaques(ucrania));

  if (sinUbicacion !== null) {
    await escribir(join(DATOS, "incidentes_sin_ubicacion.json"), await publicado(rutaSinUbicacion));
    for (const incidente of sinUbicacion.incidentes) {
      const detalle = JSON.stringify(conCorreccion(detalleSinUbicacion(incidente), incidente.id));
      await escribir(join(DATOS, "incidentes", `${incidente.id}.json`), detalle);
    }
  }

  await escribir(join(DATOS, "resumen.json"), JSON.stringify(resumen));
  // Las versiones citables (recogida/versiones.py): las listan la metodología y sus páginas.
  const versiones = exigir("versiones citables", validarVersiones(await leerVersiones(join(WEB, ".."))));
  await escribir(join(DATOS, "versiones.json"), JSON.stringify(versiones));
  if (correcciones !== null) {
    await escribir(join(DATOS, "correcciones.json"), await publicado(rutaCorrecciones));
  }
  // La previsión (proceso/prevision), validada: se sirve tal cual y la usan sus páginas de texto.
  const rutaPrevision = join(PUBLICACION, "prevision.json");
  if (await existe(rutaPrevision)) {
    exigir("prevision.json", validarPrevision(await leerJson(rutaPrevision)));
    await escribir(join(DATOS, "prevision.json"), await readFile(rutaPrevision, "utf-8"));
  }
  // El foco térmico de una región se marca en su centro: el parte no da el punto.
  const contornos = (await leerJson(
    join(PUBLICO, "mapa", "ucrania-regiones.geojson"),
  )) as ContornosRegiones;
  const centrosUcrania = centrosDeRegiones(contornos);
  // Corredores de ataque: las zonas de lanzamiento del catálogo y, para los ataques contra
  // Rusia (el parte no da el origen), el punto de la frontera de Ucrania más cercano.
  const contornosRusia = (await leerJson(
    join(PUBLICO, "mapa", "rusia-regiones.geojson"),
  )) as ContornosRegiones;
  const centrosRusia = centrosDeRegiones(contornosRusia);
  // El contorno exterior de Ucrania es una línea (o varias).
  const contornoUcrania = (await leerJson(join(PUBLICO, "mapa", "ucrania-contorno.geojson"))) as {
    features: {
      geometry:
        | { type: "LineString"; coordinates: [number, number][] }
        | { type: "MultiLineString"; coordinates: [number, number][][] };
    }[];
  };
  const anillosUcrania = contornoUcrania.features.flatMap(({ geometry }) =>
    geometry.type === "LineString" ? [geometry.coordinates] : geometry.coordinates,
  );
  const zonasConfig = (await leerJson(join(CONFIGURACION, "zonas_lanzamiento.json"))) as {
    zonas: ZonaConfig[];
  };
  const { zonas, casar } = casarZonas(zonasConfig.zonas);
  const resumenUcrania = resumirUcrania(ucrania, centrosUcrania, {
    zonas,
    casar,
    centros: new Map([...centrosUcrania, ...centrosRusia]),
    fronteraUcrania: new Map(
      [...centrosRusia].map(([codigo, centro]) => [codigo, puntoMasCercano(anillosUcrania, centro)]),
    ),
  });
  await escribir(join(DATOS, "ucrania-resumen.json"), JSON.stringify(resumenUcrania));
  for (const feature of coleccion.features) {
    const detalle = JSON.stringify(conCorreccion(detalleIncidente(feature), feature.id));
    await escribir(join(DATOS, "incidentes", `${feature.id}.json`), detalle);
  }
  for (const ataque of ucrania.ataques) {
    await escribir(join(DATOS, "ataques", `${ataque.id}.json`), JSON.stringify(ataque));
  }
  // Impactos con lugar de la capa de guerra: una ficha por impacto, que la web pide al pulsar.
  // Los partes diarios no se dibujan, así que nadie los pulsa: van solo en ucrania.json.
  for (const impacto of (ucrania.impactos ?? []).filter((i) => i.parte_diario !== true)) {
    await escribir(join(DATOS, "impactos", `${impacto.id}.json`), JSON.stringify(impacto));
  }

  await escribir(join(GENERADO, "meta.json"), JSON.stringify(meta(resumen, sinUbicacion !== null)));
  await escribir(join(PUBLICO, RUTA_SECURITY_TXT), securityTxt(new Date()));

  console.log(
    `datos: ${coleccion.features.length} incidentes en el mapa, ` +
      `${sinUbicacion?.incidentes.length ?? 0} con ubicación imprecisa y ` +
      `${ucrania.ataques.length} ataques, ${ucrania.impactos?.length ?? 0} impactos con lugar, ` +
      `${versiones.versiones.length} versiones citables, ` +
      `actualizados a ${resumen.actualizado}`,
  );
}

await principal();
