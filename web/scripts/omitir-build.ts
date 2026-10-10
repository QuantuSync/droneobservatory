// Comprobación de Vercel para omitir un despliegue («Ignored Build Step»). Vercel solo
// entiende dos salidas: 0 omite el build y 1 lo hace; cualquier otra hace fallar el
// despliegue. Por eso aquí toda duda termina en 1: sin commit anterior, con un commit
// anterior que no está en el clon (Vercel clona sin historial completo y un push forzado
// lo borra) o ante cualquier error de git, se construye. Solo se omite cuando git dice
// con seguridad que nada de web/, publicacion/, vercel.json, api/ ni la dirección del almacén
// público ha cambiado.
//
// Uso (desde la raíz del repositorio): node web/scripts/omitir-build.ts

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const OMITIR = 0;
export const CONSTRUIR = 1;
export const RUTAS_QUE_DESPLIEGAN: readonly string[] = [
  "web",
  "publicacion",
  "vercel.json",
  // La función del borde (redirecciones de los unidos y 404 de los ataques que no existen).
  "api",
  // La dirección del almacén público (teselas y estado.json) la lee la web en el build.
  "configuracion/almacen_publico.json",
  // Los canales de avisos (página «Avisos», panel del mapa y sus códigos QR).
  "configuracion/avisos.json",
  // De dónde lee el build los datos publicados (repositorio o almacén).
  "configuracion/publicacion_web.json",
];
/** Rama de la que salen los despliegues de producción normales. */
export const RAMA_DE_PRODUCCION = "main";

export interface Entorno {
  /** VERCEL_ENV: production, preview o development. */
  destino?: string | undefined;
  /** VERCEL_GIT_COMMIT_REF: la rama del commit. */
  rama?: string | undefined;
  /** Si la web lee los datos del almacén (configuracion/publicacion_web.json). */
  datosDelAlmacen?: boolean | undefined;
}

/** Salida de git diff --quiet: 0 sin cambios, 1 con cambios, otra cosa es un error. */
const DIFF_SIN_CAMBIOS = 0;

export type Git = (argumentos: readonly string[]) => number | null;

function gitReal(directorio: string): Git {
  return (argumentos) => {
    const resultado = spawnSync("git", argumentos, { cwd: directorio, stdio: "ignore" });
    return resultado.error === undefined ? resultado.status : null;
  };
}

export function decidir(
  previo: string | undefined,
  git: Git,
  entorno: Entorno = {},
): typeof OMITIR | typeof CONSTRUIR {
  // Un despliegue de producción desde otra rama solo se hace a mano, para probar una rama en
  // el dominio real: siempre se construye, aunque su vista previa ya esté hecha.
  if (entorno.destino === "production" && entorno.rama !== undefined && entorno.rama !== RAMA_DE_PRODUCCION) {
    return CONSTRUIR;
  }
  // Con los datos en el almacén, producción se construye siempre: la recogida pide la
  // reconstrucción con el gancho de despliegue tras publicar, y el commit de main no dice si los
  // datos han cambiado. El 8 de octubre de 2026 un gancho llegó tras un commit solo de documentación
  // y se omitió: la web se quedó con los datos de la hora anterior.
  if (entorno.datosDelAlmacen === true && entorno.destino === "production") return CONSTRUIR;
  if (previo === undefined || previo.trim().length === 0) return CONSTRUIR;
  try {
    if (git(["cat-file", "-e", `${previo.trim()}^{commit}`]) !== 0) return CONSTRUIR;
    // El mismo commit que el despliegue anterior (o uno anterior a él) solo llega así cuando se
    // pide a propósito: el gancho de despliegue que lanza la recogida tras publicar los datos en el
    // almacén, o un nuevo despliegue a mano. Siempre se construye.
    if (git(["merge-base", "--is-ancestor", "HEAD", previo.trim()]) === 0) return CONSTRUIR;
    const diferencias = git(["diff", "--quiet", previo.trim(), "HEAD", "--", ...RUTAS_QUE_DESPLIEGAN]);
    return diferencias === DIFF_SIN_CAMBIOS ? OMITIR : CONSTRUIR;
  } catch {
    return CONSTRUIR;
  }
}

/** Si configuracion/publicacion_web.json dice que la web lee los datos del almacén. */
export function leeDelAlmacen(raiz: string): boolean {
  try {
    const texto = readFileSync(join(raiz, "configuracion", "publicacion_web.json"), "utf-8");
    return (JSON.parse(texto) as { origen?: string }).origen === "almacen";
  } catch {
    return false;
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const salida = decidir(process.env.VERCEL_GIT_PREVIOUS_SHA, gitReal(process.cwd()), {
    destino: process.env.VERCEL_ENV,
    rama: process.env.VERCEL_GIT_COMMIT_REF,
    datosDelAlmacen: leeDelAlmacen(process.cwd()),
  });
  console.log(salida === OMITIR ? "sin cambios en la web ni en los datos: se omite" : "se construye");
  process.exit(salida);
}
