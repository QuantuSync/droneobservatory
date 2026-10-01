// Carga de los ficheros de datos. Cada fichero se valida contra el esquema antes de usarlo:
// si no valida, no se pinta nada de él.

import type {
  Ataque,
  EstadoSistema,
  ImpactoGuerra,
  IncidenteDetalle,
  Resumen,
  ResumenUcrania,
} from "./tipos.ts";
import {
  validarEstadoSistema,
  validarAtaque,
  validarDetalleIncidente,
  validarImpacto,
  validarResumen,
  validarResumenUcrania,
} from "./validar.ts";
import type { Resultado } from "./validar.ts";

export type Carga<T> =
  | { estado: "cargando" }
  | { estado: "listo"; datos: T }
  | { estado: "no_valido"; errores: string[] }
  | { estado: "no_encontrado" }
  | { estado: "no_disponible" };

export const CARGANDO: Carga<never> = { estado: "cargando" };

const NO_ENCONTRADO = 404;

type Validador<T> = (valor: unknown) => Resultado<T>;
export type Descarga = typeof fetch;

async function cargar<T>(
  ruta: string,
  validar: Validador<T>,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<T>> {
  let contenido: unknown;
  try {
    const respuesta = await descargar(ruta, senal === undefined ? {} : { signal: senal });
    if (respuesta.status === NO_ENCONTRADO) return { estado: "no_encontrado" };
    if (!respuesta.ok) return { estado: "no_disponible" };
    contenido = await respuesta.json();
  } catch {
    // Sin red, o una respuesta que no es JSON (una ruta desconocida devuelve HTML).
    return { estado: "no_disponible" };
  }
  const resultado = validar(contenido);
  return resultado.ok
    ? { estado: "listo", datos: resultado.datos }
    : { estado: "no_valido", errores: resultado.errores };
}

export function cargarResumen(descargar: Descarga, senal?: AbortSignal): Promise<Carga<Resumen>> {
  return cargar("/datos/resumen.json", validarResumen, descargar, senal);
}

export function cargarResumenUcrania(
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<ResumenUcrania>> {
  return cargar("/datos/ucrania-resumen.json", validarResumenUcrania, descargar, senal);
}

export function cargarIncidente(
  id: string,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<IncidenteDetalle>> {
  return cargar(`/datos/incidentes/${id}.json`, validarDetalleIncidente, descargar, senal);
}

export function cargarAtaque(
  id: string,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<Ataque>> {
  return cargar(`/datos/ataques/${id}.json`, validarAtaque, descargar, senal);
}

export function cargarImpacto(
  id: string,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<ImpactoGuerra>> {
  return cargar(`/datos/impactos/${id}.json`, validarImpacto, descargar, senal);
}

/**
 * estado.json lo sube la recogida al bucket de teselas cada hora, sin pasar por git.
 * Se pide sin caché del navegador: la cabecera del bucket ya da una caducidad corta.
 */
export const URL_ESTADO_SISTEMA: string =
  (import.meta.env.VITE_ESTADO as string | undefined) ??
  "https://tiles.droneobservatory.eu/estado.json";

export function cargarEstadoSistema(
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<EstadoSistema>> {
  const sinCache: Descarga = (ruta, opciones) => descargar(ruta, { ...opciones, cache: "no-cache" });
  return cargar(URL_ESTADO_SISTEMA, validarEstadoSistema, sinCache, senal);
}
