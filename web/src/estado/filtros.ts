// Filtros rápidos y periodo. Van en la dirección (?estado=…&ultimos=7d&tipo=…&pais=…&desde=…
// &hasta=…) para poder compartir una vista filtrada y para que el botón atrás del navegador
// deshaga el último cambio de periodo; lo que no se entiende se ignora.

import type { Estado, IncidenteResumen, Tipo } from "../datos/tipos.ts";
import { ESTADOS, PATRON_PAIS, TIPOS } from "../datos/vocabulario.ts";
import { diaDeInstante, fechaDeDia } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";

export type Reciente = "24h" | "7d";

export interface Filtros {
  /** Estados que se muestran; vacío es todos. */
  estados: Estado[];
  /** Solo lo de las últimas 24 horas o los últimos 7 días (por día de inicio). */
  reciente: Reciente | null;
  /** Tipos que se muestran; vacío es todos. */
  tipos: Tipo[];
  /** Países que se muestran (ISO 3166-1); vacío es todos. */
  paises: string[];
}

export const SIN_FILTROS: Filtros = { estados: [], reciente: null, tipos: [], paises: [] };

/** Lo confirmado y lo atribuido: el filtro rápido más usado, con su tecla. */
export const GRAVES: readonly Estado[] = ["confirmado", "atribuido"];

const PARAMETRO = {
  graves: "solo",
  estados: "estado",
  reciente: "ultimos",
  tipos: "tipo",
  paises: "pais",
  desde: "desde",
  hasta: "hasta",
} as const;
/** Las direcciones compartidas antes de haber filtro por estado decían ?solo=graves. */
const VALOR_GRAVES = "graves";
const SEPARADOR = ",";
const PATRON_DIA = /^\d{4}-\d{2}-\d{2}$/;
const LARGO_DIA = 10;
/** Días que cubre cada filtro de lo reciente, contando el último día con datos. */
export const DIAS_RECIENTES: Record<Reciente, number> = { "24h": 1, "7d": 7 };
const RECIENTES = Object.keys(DIAS_RECIENTES) as Reciente[];

function lista(valor: string | null): string[] {
  return (valor ?? "").split(SEPARADOR).filter((parte) => parte.length > 0);
}

function sinRepetir<T>(valores: T[]): T[] {
  return [...new Set(valores)];
}

/** Estados en el orden del vocabulario, para que la dirección no dependa del orden de uso. */
function ordenar(estados: readonly Estado[]): Estado[] {
  return ESTADOS.filter((estado) => estados.includes(estado));
}

export function soloGraves(estados: readonly Estado[]): boolean {
  const ordenados = ordenar(estados);
  return ordenados.length === GRAVES.length && GRAVES.every((e) => ordenados.includes(e));
}

export function leerFiltros(busqueda: string): Filtros {
  const parametros = new URLSearchParams(busqueda);
  const reciente = parametros.get(PARAMETRO.reciente);
  const estados =
    parametros.get(PARAMETRO.graves) === VALOR_GRAVES
      ? [...GRAVES]
      : lista(parametros.get(PARAMETRO.estados)).filter((estado): estado is Estado =>
          (ESTADOS as readonly string[]).includes(estado),
        );
  return {
    estados: ordenar(sinRepetir(estados)),
    reciente: RECIENTES.find((opcion) => opcion === reciente) ?? null,
    tipos: sinRepetir(
      lista(parametros.get(PARAMETRO.tipos)).filter((tipo): tipo is Tipo =>
        (TIPOS as readonly string[]).includes(tipo),
      ),
    ),
    paises: sinRepetir(
      lista(parametros.get(PARAMETRO.paises))
        .map((pais) => pais.toUpperCase())
        .filter((pais) => PATRON_PAIS.test(pais)),
    ),
  };
}

function diaDeTexto(texto: string | null): number | null {
  if (texto === null || !PATRON_DIA.test(texto)) return null;
  const dia = diaDeInstante(texto);
  // Date.UTC da por buenas fechas imposibles (el 45 de un mes): se exige que vuelva igual.
  return textoDeDia(dia) === texto ? dia : null;
}

function textoDeDia(dia: number): string {
  return fechaDeDia(dia).toISOString().slice(0, LARGO_DIA);
}

/** Periodo elegido en la dirección, o null si no hay (se ve todo). */
export function leerPeriodo(busqueda: string): Periodo | null {
  const parametros = new URLSearchParams(busqueda);
  const desde = diaDeTexto(parametros.get(PARAMETRO.desde));
  const hasta = diaDeTexto(parametros.get(PARAMETRO.hasta));
  if (desde === null || hasta === null || hasta < desde) return null;
  return { desde, hasta };
}

/** Parte de búsqueda de la dirección («?…») con los filtros y el periodo, o texto vacío. */
export function escribirBusqueda(filtros: Filtros, periodo: Periodo | null): string {
  const parametros = new URLSearchParams();
  if (soloGraves(filtros.estados)) parametros.set(PARAMETRO.graves, VALOR_GRAVES);
  else if (filtros.estados.length > 0) {
    parametros.set(PARAMETRO.estados, ordenar(filtros.estados).join(SEPARADOR));
  }
  if (filtros.reciente !== null) parametros.set(PARAMETRO.reciente, filtros.reciente);
  if (filtros.tipos.length > 0) parametros.set(PARAMETRO.tipos, [...filtros.tipos].sort().join(SEPARADOR));
  if (filtros.paises.length > 0) {
    parametros.set(PARAMETRO.paises, [...filtros.paises].sort().join(SEPARADOR));
  }
  if (periodo !== null) {
    parametros.set(PARAMETRO.desde, textoDeDia(periodo.desde));
    parametros.set(PARAMETRO.hasta, textoDeDia(periodo.hasta));
  }
  const texto = parametros.toString().replaceAll("%2C", SEPARADOR);
  return texto.length === 0 ? "" : `?${texto}`;
}

/** La búsqueda con solo los filtros, sin periodo. */
export function escribirFiltros(filtros: Filtros): string {
  return escribirBusqueda(filtros, null);
}

/** Cuántos filtros hay puestos: cada estado, tipo y país cuentan por separado. */
export function cuantosFiltros(filtros: Filtros): number {
  return (
    filtros.estados.length +
    Number(filtros.reciente !== null) +
    filtros.tipos.length +
    filtros.paises.length
  );
}

export function hayFiltros(filtros: Filtros): boolean {
  return cuantosFiltros(filtros) > 0;
}

/** Incidentes que pasan los filtros; «hoy» es el último día con datos. */
export function filtrar(
  incidentes: readonly IncidenteResumen[],
  filtros: Filtros,
  hoy: number,
): IncidenteResumen[] {
  const desde = filtros.reciente === null ? null : hoy - DIAS_RECIENTES[filtros.reciente] + 1;
  return incidentes.filter(
    (i) =>
      (filtros.estados.length === 0 || filtros.estados.includes(i.estado)) &&
      (desde === null || i.dia >= desde) &&
      (filtros.tipos.length === 0 || filtros.tipos.includes(i.tipo)) &&
      (filtros.paises.length === 0 || filtros.paises.includes(i.pais)),
  );
}

export function alternar<T>(lista: readonly T[], valor: T): T[] {
  return lista.includes(valor) ? lista.filter((v) => v !== valor) : [...lista, valor];
}
