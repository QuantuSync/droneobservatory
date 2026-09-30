// Días UTC como enteros (días desde 1970-01-01) y su agrupación en semanas y meses.
// Todo el calendario de la web va en UTC, igual que los datos.

export type Granularidad = "dia" | "semana" | "mes";

export const MS_POR_DIA = 86_400_000;
const DIAS_POR_SEMANA = 7;
/** El 1 de enero de 1970 fue jueves: el lunes de esa semana es el día -3. */
const LUNES_DE_REFERENCIA = -3;

export function diaDeFecha(fecha: Date): number {
  return Math.floor(fecha.getTime() / MS_POR_DIA);
}

/** Día UTC de un instante del esquema («2026-09-30T12:42Z») o de una fecha («2026-09-30»). */
export function diaDeInstante(valor: string): number {
  const [anio, mes, dia] = valor.slice(0, 10).split("-").map(Number);
  if (anio === undefined || mes === undefined || dia === undefined) {
    throw new Error(`fecha no válida: ${valor}`);
  }
  const ms = Date.UTC(anio, mes - 1, dia);
  if (Number.isNaN(ms)) throw new Error(`fecha no válida: ${valor}`);
  return ms / MS_POR_DIA;
}

export function fechaDeDia(dia: number): Date {
  return new Date(dia * MS_POR_DIA);
}

/** Primer día del tramo (día, semana que empieza en lunes o mes) que contiene el día dado. */
export function inicioDeTramo(dia: number, granularidad: Granularidad): number {
  switch (granularidad) {
    case "dia":
      return dia;
    case "semana": {
      const desdeLunes = (((dia - LUNES_DE_REFERENCIA) % DIAS_POR_SEMANA) + DIAS_POR_SEMANA) % 7;
      return dia - desdeLunes;
    }
    case "mes": {
      const fecha = fechaDeDia(dia);
      return Date.UTC(fecha.getUTCFullYear(), fecha.getUTCMonth(), 1) / MS_POR_DIA;
    }
  }
}

/** Primer día del tramo siguiente al que contiene el día dado. */
export function inicioDeTramoSiguiente(dia: number, granularidad: Granularidad): number {
  const inicio = inicioDeTramo(dia, granularidad);
  switch (granularidad) {
    case "dia":
      return inicio + 1;
    case "semana":
      return inicio + DIAS_POR_SEMANA;
    case "mes": {
      const fecha = fechaDeDia(inicio);
      return Date.UTC(fecha.getUTCFullYear(), fecha.getUTCMonth() + 1, 1) / MS_POR_DIA;
    }
  }
}

export interface Tramo {
  /** Primer día del tramo. */
  inicio: number;
  /** Primer día del tramo siguiente. */
  fin: number;
  valor: number;
}

/**
 * Histograma de un dominio [desde, hasta] (los dos incluidos) con un tramo por día, semana
 * o mes, también los vacíos. `valores` da el peso de cada día con dato.
 */
export function histograma(
  valores: ReadonlyMap<number, number>,
  desde: number,
  hasta: number,
  granularidad: Granularidad,
): Tramo[] {
  const tramos: Tramo[] = [];
  const porInicio = new Map<number, Tramo>();
  for (let inicio = inicioDeTramo(desde, granularidad); inicio <= hasta; ) {
    const fin = inicioDeTramoSiguiente(inicio, granularidad);
    const tramo = { inicio, fin, valor: 0 };
    tramos.push(tramo);
    porInicio.set(inicio, tramo);
    inicio = fin;
  }
  for (const [dia, valor] of valores) {
    if (dia < desde || dia > hasta) continue;
    const tramo = porInicio.get(inicioDeTramo(dia, granularidad));
    if (tramo !== undefined) tramo.valor += valor;
  }
  return tramos;
}

/** Periodo elegido en la línea de tiempo: días UTC, los dos incluidos. */
export interface Periodo {
  desde: number;
  hasta: number;
}

export function enPeriodo(dia: number, periodo: Periodo): boolean {
  return dia >= periodo.desde && dia <= periodo.hasta;
}

export function acotar(valor: number, minimo: number, maximo: number): number {
  return Math.min(Math.max(valor, minimo), maximo);
}
