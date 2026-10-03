// Interferencia GPS: celdas H3 de resolución 4 con la proporción de aeronaves cuya posición
// llega degradada. El servidor publica en el almacén público un fichero por día y otro por mes
// (gnss/dia/AAAA-MM-DD.json, gnss/mes/AAAA-MM.json) y un índice con los que hay
// (gnss/indice.json). La web suma por celda los del periodo elegido.

import { PREFIJO_GNSS, urlDelAlmacen } from "../almacenPublico.ts";
import { diaDeInstante, fechaDeDia } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";
import type { Carga, Descarga } from "./carga.ts";

export type NivelGnss = "sin" | "media" | "alta";
export const NIVELES_GNSS: readonly NivelGnss[] = ["sin", "media", "alta"];
const NIVEL_ALTO: NivelGnss = "alta";

/** Por debajo del 2 % no hay interferencia; del 2 al 10 %, media; por encima, alta (gpsjam.org). */
export const UMBRAL_MEDIA = 0.02;
export const UMBRAL_ALTA = 0.1;
/** Opacidad del relleno de las celdas en el mapa (y en la leyenda). */
export const OPACIDAD_GNSS = 0.55;
/** Con más días que estos, el periodo se dibuja con los ficheros mensuales. */
export const DIAS_MAXIMOS_DIARIOS = 7;
const VERSION = 1;
const PATRON_DIA = /^\d{4}-\d{2}-\d{2}$/;
const PATRON_MES = /^\d{4}-\d{2}$/;
const PATRON_H3 = /^[0-9a-f]{15}$/;

export interface CeldaGnss {
  h3: string;
  aeronaves: number;
  degradadas: number;
  proporcion: number;
  nivel: NivelGnss;
  /** Vértices [lon, lat] del hexágono. */
  contorno: [number, number][];
}

export interface ResumenGnss {
  celdas: number;
  celdas_media: number;
  celdas_alta: number;
  aeronaves: number;
  degradadas: number;
  proporcion: number;
  nivel: NivelGnss;
}

export interface FicheroGnss {
  version: 1;
  periodo: string;
  dias: number;
  resolucion_h3: number;
  resumen: ResumenGnss;
  celdas: CeldaGnss[];
}

export interface IndiceGnss {
  version: 1;
  generado: string;
  dias: string[];
  meses: string[];
}

/** Proporción como gpsjam.org: se resta una aeronave degradada, para que una sola averiada no tiña la celda. */
export function proporcion(aeronaves: number, degradadas: number): number {
  return aeronaves <= 0 ? 0 : Math.max(0, degradadas - 1) / aeronaves;
}

export function nivelDe(p: number): NivelGnss {
  if (p > UMBRAL_ALTA) return "alta";
  if (p >= UMBRAL_MEDIA) return "media";
  return "sin";
}

// ---- Validación ligera: lo que no cumple no se dibuja ----

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function entero(valor: unknown): valor is number {
  return typeof valor === "number" && Number.isInteger(valor) && valor >= 0;
}

function fraccion(valor: unknown): valor is number {
  return typeof valor === "number" && Number.isFinite(valor) && valor >= 0 && valor <= 1;
}

function esNivel(valor: unknown): valor is NivelGnss {
  return NIVELES_GNSS.includes(valor as NivelGnss);
}

function coordenada(valor: unknown): boolean {
  return (
    Array.isArray(valor) &&
    valor.length === 2 &&
    typeof valor[0] === "number" &&
    typeof valor[1] === "number" &&
    Math.abs(valor[0]) <= 180 &&
    Math.abs(valor[1]) <= 90
  );
}

function esCelda(valor: unknown): valor is CeldaGnss {
  return (
    esObjeto(valor) &&
    typeof valor.h3 === "string" &&
    PATRON_H3.test(valor.h3) &&
    entero(valor.aeronaves) &&
    entero(valor.degradadas) &&
    valor.degradadas <= valor.aeronaves &&
    fraccion(valor.proporcion) &&
    esNivel(valor.nivel) &&
    Array.isArray(valor.contorno) &&
    valor.contorno.length >= 5 &&
    valor.contorno.length <= 8 &&
    valor.contorno.every(coordenada)
  );
}

function esResumen(valor: unknown): valor is ResumenGnss {
  return (
    esObjeto(valor) &&
    entero(valor.celdas) &&
    entero(valor.celdas_media) &&
    entero(valor.celdas_alta) &&
    entero(valor.aeronaves) &&
    entero(valor.degradadas) &&
    fraccion(valor.proporcion) &&
    esNivel(valor.nivel)
  );
}

export function validarFicheroGnss(valor: unknown): FicheroGnss | null {
  if (
    !esObjeto(valor) ||
    valor.version !== VERSION ||
    typeof valor.periodo !== "string" ||
    !(PATRON_DIA.test(valor.periodo) || PATRON_MES.test(valor.periodo)) ||
    !entero(valor.dias) ||
    valor.resolucion_h3 !== 4 ||
    !esResumen(valor.resumen) ||
    !Array.isArray(valor.celdas) ||
    !valor.celdas.every(esCelda)
  ) {
    return null;
  }
  return valor as unknown as FicheroGnss;
}

export function validarIndiceGnss(valor: unknown): IndiceGnss | null {
  if (
    !esObjeto(valor) ||
    valor.version !== VERSION ||
    typeof valor.generado !== "string" ||
    !Array.isArray(valor.dias) ||
    !valor.dias.every((d) => typeof d === "string" && PATRON_DIA.test(d)) ||
    !Array.isArray(valor.meses) ||
    !valor.meses.every((m) => typeof m === "string" && PATRON_MES.test(m))
  ) {
    return null;
  }
  return valor as unknown as IndiceGnss;
}

// ---- Qué ficheros cubren un periodo y cómo se suman ----

function mesDeDia(dia: number): string {
  return fechaDeDia(dia).toISOString().slice(0, 7);
}

/**
 * Objetos del almacén que hay que pedir para un periodo: los diarios que hay en el índice si
 * el periodo tiene 7 días o menos; si no, los mensuales que lo solapan.
 */
export function ficherosDelPeriodo(indice: IndiceGnss, periodo: Periodo): string[] {
  const largo = periodo.hasta - periodo.desde + 1;
  if (largo <= DIAS_MAXIMOS_DIARIOS) {
    return indice.dias
      .filter((d) => {
        const dia = diaDeInstante(d);
        return dia >= periodo.desde && dia <= periodo.hasta;
      })
      .map((d) => `dia/${d}.json`);
  }
  const desde = mesDeDia(periodo.desde);
  const hasta = mesDeDia(periodo.hasta);
  return indice.meses.filter((m) => m >= desde && m <= hasta).map((m) => `mes/${m}.json`);
}

export interface Agregado {
  celdas: CeldaGnss[];
  resumen: ResumenGnss;
  /** Días con datos que entran en la suma. */
  dias: number;
}

/** Suma por celda las aeronaves y las degradadas de varios ficheros y recalcula proporción y nivel. */
export function agregar(ficheros: readonly FicheroGnss[]): Agregado {
  const porCelda = new Map<string, CeldaGnss>();
  let dias = 0;
  for (const fichero of ficheros) {
    dias += fichero.dias;
    for (const celda of fichero.celdas) {
      const previa = porCelda.get(celda.h3);
      if (previa === undefined) {
        porCelda.set(celda.h3, { ...celda });
      } else {
        previa.aeronaves += celda.aeronaves;
        previa.degradadas += celda.degradadas;
      }
    }
  }
  const celdas = [...porCelda.values()].map((c) => {
    const p = proporcion(c.aeronaves, c.degradadas);
    return { ...c, proporcion: p, nivel: nivelDe(p) };
  });
  const aeronaves = celdas.reduce((s, c) => s + c.aeronaves, 0);
  const degradadas = celdas.reduce((s, c) => s + c.degradadas, 0);
  const total = celdas.reduce((s, c) => s + c.proporcion * c.aeronaves, 0);
  const media = aeronaves === 0 ? 0 : total / aeronaves;
  return {
    celdas,
    dias,
    resumen: {
      celdas: celdas.length,
      celdas_media: celdas.filter((c) => c.nivel === "media").length,
      celdas_alta: celdas.filter((c) => c.nivel === NIVEL_ALTO).length,
      aeronaves,
      degradadas,
      proporcion: media,
      nivel: nivelDe(media),
    },
  };
}

/**
 * Zonas (celdas H3) con interferencia alta, más del 10 %: la misma cuenta para «Europa ahora»
 * (sobre el último día publicado) y para la leyenda de la capa (sobre el periodo elegido).
 */
export function zonasAltas(agregado: Agregado): number {
  return agregado.celdas.filter((c) => c.nivel === NIVEL_ALTO).length;
}

/** Celdas como GeoJSON para el mapa: polígonos cerrados con su proporción y su nivel. */
export function celdasEnMapa(celdas: readonly CeldaGnss[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: celdas.map((c) => {
      const anillo = [...c.contorno];
      const primero = anillo[0];
      const ultimo = anillo[anillo.length - 1];
      if (primero !== undefined && ultimo !== undefined && (primero[0] !== ultimo[0] || primero[1] !== ultimo[1])) {
        anillo.push(primero);
      }
      return {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [anillo] },
        properties: { h3: c.h3, proporcion: c.proporcion, nivel: c.nivel },
      };
    }),
  };
}

// ---- Carga ----

/** Base de los ficheros de interferencia: el almacén público, o otra para pruebas locales. */
export const BASE_GNSS: string =
  (import.meta.env.VITE_GNSS as string | undefined) ?? urlDelAlmacen(PREFIJO_GNSS);

async function pedir<T>(
  ruta: string,
  validar: (valor: unknown) => T | null,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<T>> {
  try {
    const respuesta = await descargar(ruta, senal === undefined ? {} : { signal: senal });
    if (respuesta.status === 404) return { estado: "no_encontrado" };
    // Un objeto que no existe en el almacén responde 403 (no se pueden listar sus objetos).
    if (respuesta.status === 403) return { estado: "no_encontrado" };
    if (!respuesta.ok) return { estado: "no_disponible" };
    const datos = validar(await respuesta.json());
    return datos === null ? { estado: "no_valido", errores: [ruta] } : { estado: "listo", datos };
  } catch {
    return { estado: "no_disponible" };
  }
}

export function cargarIndiceGnss(descargar: Descarga, senal?: AbortSignal): Promise<Carga<IndiceGnss>> {
  const sinCache: Descarga = (ruta, opciones) => descargar(ruta, { ...opciones, cache: "no-cache" });
  return pedir(`${BASE_GNSS}/indice.json`, validarIndiceGnss, sinCache, senal);
}

export function cargarFicheroGnss(
  objeto: string,
  descargar: Descarga,
  senal?: AbortSignal,
): Promise<Carga<FicheroGnss>> {
  return pedir(`${BASE_GNSS}/${objeto}`, validarFicheroGnss, descargar, senal);
}
