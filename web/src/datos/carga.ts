// Carga de los ficheros de datos. Cada fichero se valida contra el esquema antes de usarlo:
// si no valida, no se pinta nada de él.

import { OBJETO_ESTADO, urlDelAlmacen } from "../almacenPublico.ts";
import type {
  Ataque,
  EstadoSistema,
  ImpactoGuerra,
  IncidenteDetalle,
  Resumen,
  ResumenUcrania,
} from "./tipos.ts";
import type { Prevision } from "./prevision.ts";
import {
  validarEstadoSistema,
  validarPrevision,
  validarAtaque,
  validarDetalleIncidente,
  validarImpacto,
  validarResumen,
  validarResumenUcrania,
} from "./validar.ts";
import type { Resultado } from "./validar.ts";
import { esAborto, esPasajero, esperar, esperasEnVigor, opcionesDelIntento } from "./reintentos.ts";

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

/** Un intento: su resultado y si vale la pena volver a intentarlo. */
async function intentar<T>(
  ruta: string,
  validar: Validador<T>,
  descargar: Descarga,
  opciones: RequestInit,
): Promise<{ carga: Carga<T>; otraVez: boolean }> {
  let contenido: unknown;
  try {
    const respuesta = await descargar(ruta, opciones);
    if (respuesta.status === NO_ENCONTRADO) return { carga: { estado: "no_encontrado" }, otraVez: false };
    if (!respuesta.ok) return { carga: { estado: "no_disponible" }, otraVez: esPasajero(respuesta) };
    contenido = await respuesta.json();
  } catch (error) {
    // Sin red, una respuesta cortada o que no es JSON (una página de comprobación del
    // alojamiento, por ejemplo): se vuelve a pedir, salvo que se haya abortado a propósito.
    return { carga: { estado: "no_disponible" }, otraVez: !esAborto(error, opciones.signal) };
  }
  const resultado = validar(contenido);
  return resultado.ok
    ? { carga: { estado: "listo", datos: resultado.datos }, otraVez: false }
    : // Puede ser una copia vieja en una caché: se pide otra vez sin ella.
      { carga: { estado: "no_valido", errores: resultado.errores }, otraVez: true };
}

/**
 * Pide un fichero y lo valida, con reintentos (datos/reintentos.ts): un fallo pasajero, una
 * respuesta cortada o que no valida se vuelven a pedir, con espera creciente y sin la caché del
 * navegador, antes de dar el error.
 */
async function cargar<T>(
  ruta: string,
  validar: Validador<T>,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<T>> {
  const pausas = esperasEnVigor();
  for (let n = 0; ; n += 1) {
    const { carga, otraVez } = await intentar(ruta, validar, descargar, opcionesDelIntento(senal === undefined ? {} : { signal: senal }, n));
    if (!otraVez || n >= pausas.length || senal?.aborted === true) return carga;
    try {
      await esperar(pausas[n] ?? 0, senal);
    } catch {
      return carga;
    }
  }
}

export function cargarResumen(descargar: Descarga, senal?: AbortSignal): Promise<Carga<Resumen>> {
  return cargar("/datos/resumen.json", validarResumen, descargar, senal);
}

/** La copia de la previsión que sube la recogida al almacén público (recogida/publicacion.py). */
export const URL_PREVISION_ALMACEN: string = urlDelAlmacen("publicacion/prevision.json");

/**
 * La previsión: se pide al abrir «Previsión» o la ficha de un país, nunca en la primera carga.
 * Si la de la web no llega tras sus reintentos, se pide la copia del almacén público.
 */
export async function cargarPrevision(descargar: Descarga, senal?: AbortSignal): Promise<Carga<Prevision>> {
  const web = await cargar("/datos/prevision.json", validarPrevision, descargar, senal);
  if (web.estado === "listo" || senal?.aborted === true) return web;
  const almacen = await cargar(URL_PREVISION_ALMACEN, validarPrevision, descargar, senal);
  return almacen.estado === "listo" ? almacen : web;
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
 * estado.json lo sube la recogida al almacén público cada hora, sin pasar por git.
 * Se pide sin caché del navegador: la cabecera del objeto ya da una caducidad corta.
 */
export const URL_ESTADO_SISTEMA: string =
  (import.meta.env.VITE_ESTADO as string | undefined) ?? urlDelAlmacen(OBJETO_ESTADO);

export function cargarEstadoSistema(
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<EstadoSistema>> {
  const sinCache: Descarga = (ruta, opciones) => descargar(ruta, { ...opciones, cache: "no-cache" });
  return cargar(URL_ESTADO_SISTEMA, validarEstadoSistema, sinCache, senal);
}
