// Antigüedad de los datos para la barra de estado: nunca se da por buena sin comprobarla.

export type EstadoFrescura = "al_dia" | "con_retraso" | "desactualizado";

const MS_POR_HORA = 3_600_000;
/** Menos de dos horas: al día. La recogida es horaria, así que cabe una ejecución perdida. */
export const HORAS_CON_RETRASO = 2;
/** Desde seis horas: desactualizado. */
export const HORAS_DESACTUALIZADO = 6;

export function horasDesde(actualizado: string, ahora: Date): number {
  return (ahora.getTime() - new Date(actualizado).getTime()) / MS_POR_HORA;
}

/**
 * Desde cuándo se mide la antigüedad: la última recogida correcta si estado.json está
 * publicado; si no, el último cambio de los datos. Sin ninguna recogida correcta, null.
 */
export function referenciaDeFrescura(
  sistema: { ultima_correcta: string | null } | null,
  actualizado: string | null,
): string | null {
  return sistema === null ? actualizado : sistema.ultima_correcta;
}

export function frescura(actualizado: string, ahora: Date): EstadoFrescura {
  const horas = horasDesde(actualizado, ahora);
  // Una fecha ilegible no puede darse por reciente.
  if (Number.isNaN(horas) || horas >= HORAS_DESACTUALIZADO) return "desactualizado";
  if (horas >= HORAS_CON_RETRASO) return "con_retraso";
  return "al_dia";
}
