// La compilación de la web nunca falla por el contenido de los datos publicados (desde el 14 de
// octubre de 2026: ese día la de producción falló porque los datos traían un campo, `traduccion`,
// que el código de main aún no conocía). Lo que no se entiende se ignora y queda en el registro de
// la compilación, con líneas que empiezan por «AVISO DE DATOS»:
//
// - un campo desconocido se ignora (la web se muestra sin él; validar.ts, tolerarCamposNuevos);
// - un elemento que no cumple el esquema (un incidente, un ataque, un impacto...) se quita de la
//   web, y los demás se publican;
// - si un fichero entero no se puede leer o no se arregla quitando elementos, se usa el de la
//   compilación anterior, el que sirve ahora la web (https://droneobservatory.eu/datos/...); y si
//   el fichero es opcional (la previsión), se publica sin él.
//
// Solo falla si no hay forma de tener los datos (ni los publicados ni los de la web anterior): en
// ese caso, en producción sigue la versión anterior, que es lo mejor que se puede hacer.

import { camposIgnorados } from "../src/datos/validar.ts";
import type { Resultado } from "../src/datos/validar.ts";

export const WEB_ANTERIOR = "https://droneobservatory.eu/datos";
export const AVISO = "AVISO DE DATOS";

export type Validar<T> = (valor: unknown) => Resultado<T>;
export type LeerAnterior = (nombre: string) => Promise<unknown>;

/** «.features[12].properties.fuentes[3].traduccion» → «.features[].properties.fuentes[].traduccion». */
export function patronDeRuta(ruta: string): string {
  return ruta.replace(/\[\d+\]/g, "[]").replace(/\.(EODI-[\w-]+|\d{4}-\d{2}-\d{2})\b/g, ".*");
}

/** Los campos ignorados, agrupados por su patrón y con cuántas veces. */
export function resumirIgnorados(rutas: readonly string[]): string[] {
  const cuenta = new Map<string, number>();
  for (const ruta of rutas) {
    const patron = patronDeRuta(ruta);
    cuenta.set(patron, (cuenta.get(patron) ?? 0) + 1);
  }
  return [...cuenta].map(([patron, n]) => `${patron} (${n} ${n === 1 ? "vez" : "veces"})`);
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

/**
 * El dato validado; si no valida, quita de sus listas (`listas`) los elementos que no validan
 * solos y vuelve a validar. null si ni así vale. Cada cosa que se ignora o se quita, a `avisos`.
 */
export function depurar<T>(
  nombre: string,
  valor: unknown,
  validar: Validar<T>,
  listas: readonly string[],
  avisos: string[],
): T | null {
  const entero = validar(valor);
  const ignorados = camposIgnorados();
  if (entero.ok) {
    for (const linea of resumirIgnorados(ignorados)) {
      avisos.push(`${nombre}: campo que la web no conoce, ignorado: ${linea}`);
    }
    return entero.datos;
  }
  if (!esObjeto(valor)) {
    avisos.push(`${nombre}: no es un objeto JSON (${entero.errores[0] ?? "sin detalle"})`);
    return null;
  }
  const vacias = Object.fromEntries(
    listas.filter((l) => Array.isArray(valor[l])).map((l) => [l, [] as unknown[]]),
  );
  const depurado: Record<string, unknown> = { ...valor };
  for (const lista of listas) {
    const elementos = valor[lista];
    if (!Array.isArray(elementos)) continue;
    depurado[lista] = elementos.filter((elemento, i) => {
      const solo = validar({ ...valor, ...vacias, [lista]: [elemento] });
      camposIgnorados();
      if (solo.ok) return true;
      const id = esObjeto(elemento) && typeof elemento.id === "string" ? ` ${elemento.id}` : "";
      avisos.push(
        `${nombre}: ${lista}[${i}]${id} no cumple el esquema y no se publica en la web: ` +
          solo.errores.slice(0, 3).join("; "),
      );
      return false;
    });
  }
  const final = validar(depurado);
  for (const linea of resumirIgnorados(camposIgnorados())) {
    avisos.push(`${nombre}: campo que la web no conoce, ignorado: ${linea}`);
  }
  if (final.ok) return final.datos;
  avisos.push(`${nombre}: no se arregla quitando elementos: ${final.errores.slice(0, 3).join("; ")}`);
  return null;
}

async function leerAnteriorHttp(nombre: string): Promise<unknown> {
  const base = process.env.EODI_WEB_ANTERIOR ?? WEB_ANTERIOR;
  const respuesta = await fetch(`${base}/${nombre}`, {
    headers: { "Cache-Control": "no-cache", "User-Agent": "EODI-web-build" },
    signal: AbortSignal.timeout(60_000),
  });
  if (!respuesta.ok) throw new Error(`${base}/${nombre}: HTTP ${respuesta.status}`);
  return (await respuesta.json()) as unknown;
}

/**
 * Los datos de un fichero publicado, sin que su contenido pueda parar la compilación: el leído
 * (`leer`, que puede fallar si no es JSON), depurado; si no vale, el de la web anterior, depurado;
 * si tampoco, null (y quien llama decide: un fichero opcional se omite, uno obligatorio falla).
 */
export async function aceptar<T>(
  nombre: string,
  leer: () => Promise<unknown>,
  validar: Validar<T>,
  listas: readonly string[],
  avisos: string[],
  anterior: LeerAnterior = leerAnteriorHttp,
): Promise<{ datos: T; origen: "publicado" | "anterior" } | null> {
  try {
    const datos = depurar(nombre, await leer(), validar, listas, avisos);
    if (datos !== null) return { datos, origen: "publicado" };
  } catch (error) {
    avisos.push(`${nombre}: no se puede leer: ${String(error).slice(0, 200)}`);
  }
  try {
    const datos = depurar(`${nombre} (web anterior)`, await anterior(nombre), validar, listas, avisos);
    if (datos !== null) {
      avisos.push(`${nombre}: se publica el de la compilación anterior`);
      return { datos, origen: "anterior" };
    }
  } catch (error) {
    avisos.push(`${nombre}: tampoco se puede leer el de la web anterior: ${String(error).slice(0, 200)}`);
  }
  return null;
}
