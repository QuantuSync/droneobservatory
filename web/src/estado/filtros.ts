// Filtros y periodo. Van en la dirección (?estado=…&ultimos=7d&tipo=…&pais=…&desde=…&hasta=…)
// para poder compartir una vista filtrada y para que el botón atrás del navegador deshaga el
// último cambio; lo que no se entiende se ignora. El periodo es uno de los rápidos (las
// últimas 24 horas desde este momento; 7 días, 30 días o el último año, contados hasta el
// último día con datos), uno entre dos fechas o, sin nada en la dirección, todo.

import type { Estado, IncidenteResumen, Tipo } from "../datos/tipos.ts";
import { ESTADOS, PATRON_PAIS, TIPOS } from "../datos/vocabulario.ts";
import { MS_POR_HORA, diaDeFecha, diaDeInstante, fechaDeDia } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";

export type Reciente = "24h" | "7d" | "30d" | "1a";

export interface Filtros {
  /** Estados que se muestran; vacío es todos. */
  estados: Estado[];
  /** Periodo rápido: los últimos días hasta el último con datos (por día de inicio). */
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
/**
 * Días que cubre cada filtro de lo reciente, contando el último. Las 24 horas tocan dos días
 * (hoy y ayer): dentro de ellos manda la ventana exacta (ver periodoDeSeleccion).
 */
export const DIAS_RECIENTES: Record<Reciente, number> = { "24h": 2, "7d": 7, "30d": 30, "1a": 365 };
/** Lo que mide «Últimas 24 horas». */
export const MS_ULTIMAS_24H = 24 * MS_POR_HORA;
export const RECIENTES = Object.keys(DIAS_RECIENTES) as Reciente[];

/** Lo que se ve: todo (por defecto), un periodo rápido o uno entre dos fechas. */
export type SeleccionPeriodo =
  | { clase: "todo" }
  | { clase: "reciente"; reciente: Reciente }
  | { clase: "entre"; periodo: Periodo };

export const TODO: SeleccionPeriodo = { clase: "todo" };

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

/** El periodo elegido en la dirección: el rápido manda sobre las fechas. */
export function leerSeleccion(busqueda: string): SeleccionPeriodo {
  const reciente = leerFiltros(busqueda).reciente;
  if (reciente !== null) return { clase: "reciente", reciente };
  const periodo = leerPeriodo(busqueda);
  return periodo === null ? TODO : { clase: "entre", periodo };
}

/**
 * Los días que cubre una selección; null es todo. Los periodos de días cuentan hasta «hoy», el
 * último día con datos. «Últimas 24 horas» cuenta hacia atrás desde `ahora` (un instante): su
 * ventana va de 24 horas antes hasta ese momento y sus días son el de `ahora` y el anterior.
 */
export function periodoDeSeleccion(
  seleccion: SeleccionPeriodo,
  hoy: number,
  ahora: number,
): Periodo | null {
  if (seleccion.clase === "todo") return null;
  if (seleccion.clase === "entre") return seleccion.periodo;
  if (seleccion.reciente === "24h") return ultimas24Horas(ahora);
  return { desde: hoy - DIAS_RECIENTES[seleccion.reciente] + 1, hasta: hoy };
}

/** Las últimas 24 horas desde un instante, con sus dos días (el del instante y el anterior). */
export function ultimas24Horas(ahora: number): Periodo {
  const dia = diaDeFecha(new Date(ahora));
  return {
    desde: dia - DIAS_RECIENTES["24h"] + 1,
    hasta: dia,
    ventana: { desde: ahora - MS_ULTIMAS_24H, hasta: ahora },
  };
}

/** La dirección con los filtros y una selección de periodo (una sola de las dos formas). */
export function escribirSeleccion(filtros: Filtros, seleccion: SeleccionPeriodo): string {
  return escribirBusqueda(
    { ...filtros, reciente: seleccion.clase === "reciente" ? seleccion.reciente : null },
    seleccion.clase === "entre" ? seleccion.periodo : null,
  );
}

export function mismaSeleccion(a: SeleccionPeriodo, b: SeleccionPeriodo): boolean {
  if (a.clase === "todo" || b.clase === "todo") return a.clase === b.clase;
  if (a.clase === "reciente" && b.clase === "reciente") return a.reciente === b.reciente;
  if (a.clase === "entre" && b.clase === "entre") {
    return a.periodo.desde === b.periodo.desde && a.periodo.hasta === b.periodo.hasta;
  }
  return false;
}

/** La búsqueda con solo los filtros, sin periodo. */
export function escribirFiltros(filtros: Filtros): string {
  return escribirBusqueda(filtros, null);
}

/** Cuántos filtros hay puestos, sin contar el periodo: cada estado, tipo y país por separado. */
export function cuantosFiltros(filtros: Filtros): number {
  return filtros.estados.length + filtros.tipos.length + filtros.paises.length;
}

export function hayFiltros(filtros: Filtros): boolean {
  return cuantosFiltros(filtros) > 0;
}

/** Incidentes que pasan los filtros de estado, tipo y país (el periodo va aparte). */
export function filtrar(incidentes: readonly IncidenteResumen[], filtros: Filtros): IncidenteResumen[] {
  return incidentes.filter(
    (i) =>
      (filtros.estados.length === 0 || filtros.estados.includes(i.estado)) &&
      (filtros.tipos.length === 0 || filtros.tipos.includes(i.tipo)) &&
      (filtros.paises.length === 0 || filtros.paises.includes(i.pais)),
  );
}

export function alternar<T>(lista: readonly T[], valor: T): T[] {
  return lista.includes(valor) ? lista.filter((v) => v !== valor) : [...lista, valor];
}
