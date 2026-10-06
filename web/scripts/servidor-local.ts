// Servidor local de web/dist que imita lo que hace el despliegue: aplica las redirecciones, las
// cabeceras y las reescrituras de ../vercel.json, después de los ficheros como Vercel, lo que
// decide la función del borde (../api/borde.ts, con la lista /rutas.json del build) y las
// direcciones sin extensión. Sirve además el
// recorte de teselas de desarrollo (../data/teselas, fuera de git) con peticiones Range.
// Sirve para comprobar en un navegador real la política de seguridad antes de desplegar.

import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import type { ServerResponse } from "node:http";
import { dirname, extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { RUTA_LISTA_BORDE, decidirBorde } from "../../api/borde.ts";
import type { DecisionBorde, RutasBorde } from "../../api/borde.ts";
import { cabecerasDe, destinoDeReescritura } from "../src/seguridad/despliegue.ts";
import type { ConfiguracionDespliegue } from "../src/seguridad/despliegue.ts";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const SALIDA = join(WEB, "dist");
const TESELAS = join(WEB, "..", "data", "teselas");
const RUTA_TESELAS = "/teselas/";
const PUERTO = Number(process.env.PUERTO ?? "4173");

const TIPOS: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".webmanifest": "application/manifest+json",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".pbf": "application/x-protobuf",
  ".pmtiles": "application/octet-stream",
};

const configuracion = JSON.parse(
  await readFile(join(WEB, "..", "vercel.json"), "utf-8"),
) as ConfiguracionDespliegue;

/** Las redirecciones de vercel.json, sin patrones (solo rutas exactas). */
const redirecciones = new Map(
  (configuracion.redirects ?? []).map((r) => [r.source, { destino: r.destination, codigo: r.permanent ? 308 : 307 }]),
);

/** La lista del middleware del borde que escribe el build. */
async function leerBorde(): Promise<RutasBorde> {
  try {
    return JSON.parse(await readFile(join(SALIDA, RUTA_LISTA_BORDE.slice(1)), "utf-8")) as RutasBorde;
  } catch {
    return { redirecciones: {}, ataques: [] };
  }
}
const borde = await leerBorde();
const ataques = new Set(borde.ataques);
const RUTA_DEL_BORDE = /^\/(?:en\/)?EODI-[A-Za-z0-9-]+$/;

async function esFichero(ruta: string): Promise<boolean> {
  try {
    return (await stat(ruta)).isFile();
  } catch {
    return false;
  }
}

/** Fichero que responde a una ruta, como en el despliegue: sin extensión .html. */
async function resolver(ruta: string): Promise<string | null> {
  const candidatas = [ruta, `${ruta}.html`, join(ruta, "index.html")];
  for (const candidata of candidatas) {
    const fichero = normalize(join(SALIDA, candidata));
    if (fichero.startsWith(SALIDA + sep) && (await esFichero(fichero))) return fichero;
  }
  return null;
}

async function servirTeselas(
  ruta: string,
  rango: string | undefined,
  respuesta: ServerResponse,
): Promise<void> {
  const fichero = normalize(join(TESELAS, ruta.slice(RUTA_TESELAS.length)));
  if (!fichero.startsWith(TESELAS + sep) || !(await esFichero(fichero))) {
    respuesta.writeHead(404).end();
    return;
  }
  const { size } = await stat(fichero);
  const partes = /^bytes=(\d+)-(\d*)$/.exec(rango ?? "");
  if (partes === null) {
    respuesta.writeHead(200, { "Content-Length": size, "Accept-Ranges": "bytes" });
    createReadStream(fichero).pipe(respuesta);
    return;
  }
  const inicio = Number(partes[1]);
  const fin = partes[2] === "" ? size - 1 : Math.min(Number(partes[2]), size - 1);
  respuesta.writeHead(206, {
    "Content-Range": `bytes ${inicio}-${fin}/${size}`,
    "Content-Length": fin - inicio + 1,
    "Accept-Ranges": "bytes",
    "Content-Type": "application/octet-stream",
  });
  createReadStream(fichero, { start: inicio, end: fin }).pipe(respuesta);
}

const servidor = createServer((peticion, respuesta) => {
  void (async () => {
    const ruta = decodeURIComponent(new URL(peticion.url ?? "/", "http://local").pathname);
    if (ruta.startsWith(RUTA_TESELAS)) {
      await servirTeselas(ruta, peticion.headers.range, respuesta);
      return;
    }
    // Como en el despliegue, las redirecciones van antes que todo lo demás.
    const redireccion = redirecciones.get(ruta);
    if (redireccion !== undefined) {
      respuesta.writeHead(redireccion.codigo, { Location: redireccion.destino }).end();
      return;
    }
    for (const [clave, valor] of cabecerasDe(configuracion, ruta)) {
      respuesta.setHeader(clave, valor);
    }
    // Los ficheros primero; una ficha que no es un fichero va a la función del borde.
    let fichero = await resolver(ruta);
    if (fichero === null && RUTA_DEL_BORDE.test(ruta)) {
      const decision: DecisionBorde = decidirBorde(ruta, borde, ataques);
      if (decision.tipo === "redirigir") {
        respuesta.writeHead(308, { Location: decision.destino }).end();
        return;
      }
      fichero = decision.tipo === "portada" ? await resolver(decision.ruta) : null;
    } else if (fichero === null) {
      fichero = await resolver(destinoDeReescritura(configuracion, ruta) ?? ruta);
    }
    if (fichero === null) {
      // La página 404 del sitio, con su código.
      const noEncontrada = await resolver("/404.html");
      respuesta.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
      if (noEncontrada === null) respuesta.end("404");
      else createReadStream(noEncontrada).pipe(respuesta);
      return;
    }
    respuesta.writeHead(200, {
      "Content-Type": TIPOS[extname(fichero)] ?? "application/octet-stream",
    });
    createReadStream(fichero).pipe(respuesta);
  })();
});

servidor.listen(PUERTO, () => {
  console.log(`http://localhost:${PUERTO}`);
});
