// Días UTC como enteros (días desde 1970-01-01). Todo el calendario de la web va en UTC,
// igual que los datos.

export const MS_POR_DIA = 86_400_000;

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

/** Periodo elegido en los filtros: días UTC, los dos incluidos. */
export interface Periodo {
  desde: number;
  hasta: number;
}

export function enPeriodo(dia: number, periodo: Periodo): boolean {
  return dia >= periodo.desde && dia <= periodo.hasta;
}
