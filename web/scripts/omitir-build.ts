// Comprobación de Vercel para omitir un despliegue («Ignored Build Step»). Vercel solo
// entiende dos salidas: 0 omite el build y 1 lo hace; cualquier otra hace fallar el
// despliegue. Por eso aquí toda duda termina en 1: sin commit anterior, con un commit
// anterior que no está en el clon (Vercel clona sin historial completo y un push forzado
// lo borra) o ante cualquier error de git, se construye. Solo se omite cuando git dice
// con seguridad que nada de web/, publicacion/ ni vercel.json ha cambiado.
//
// Uso (desde la raíz del repositorio): node web/scripts/omitir-build.ts

import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const OMITIR = 0;
export const CONSTRUIR = 1;
export const RUTAS_QUE_DESPLIEGAN: readonly string[] = ["web", "publicacion", "vercel.json"];

/** Salida de git diff --quiet: 0 sin cambios, 1 con cambios, otra cosa es un error. */
const DIFF_SIN_CAMBIOS = 0;

export type Git = (argumentos: readonly string[]) => number | null;

function gitReal(directorio: string): Git {
  return (argumentos) => {
    const resultado = spawnSync("git", argumentos, { cwd: directorio, stdio: "ignore" });
    return resultado.error === undefined ? resultado.status : null;
  };
}

export function decidir(previo: string | undefined, git: Git): typeof OMITIR | typeof CONSTRUIR {
  if (previo === undefined || previo.trim().length === 0) return CONSTRUIR;
  try {
    if (git(["cat-file", "-e", `${previo.trim()}^{commit}`]) !== 0) return CONSTRUIR;
    const diferencias = git(["diff", "--quiet", previo.trim(), "HEAD", "--", ...RUTAS_QUE_DESPLIEGAN]);
    return diferencias === DIFF_SIN_CAMBIOS ? OMITIR : CONSTRUIR;
  } catch {
    return CONSTRUIR;
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const salida = decidir(process.env.VERCEL_GIT_PREVIOUS_SHA, gitReal(process.cwd()));
  console.log(salida === OMITIR ? "sin cambios en la web ni en los datos: se omite" : "se construye");
  process.exit(salida);
}
