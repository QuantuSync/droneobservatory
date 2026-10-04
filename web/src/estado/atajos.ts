// Atajos de teclado. La misma tabla sirve para atenderlos y para el panel de ayuda.

export type Accion =
  | "ayuda"
  | "cerrar"
  | "capaIncidentes"
  | "capaUcrania"
  | "capaDensidad"
  | "capaSatelite"
  | "filtroGraves"
  | "filtro24h"
  | "filtro7d"
  | "sinFiltros"
  | "filtros"
  | "ahora"
  | "feed"
  | "lista"
  | "metodologia";

/** Tecla y acción, en el orden en que las enseña la ayuda. */
export const ATAJOS: readonly (readonly [tecla: string, accion: Accion])[] = [
  ["?", "ayuda"],
  ["Escape", "cerrar"],
  ["1", "capaIncidentes"],
  ["2", "capaUcrania"],
  ["3", "capaDensidad"],
  ["4", "capaSatelite"],
  ["c", "filtroGraves"],
  ["h", "filtro24h"],
  ["s", "filtro7d"],
  ["0", "sinFiltros"],
  ["f", "filtros"],
  ["a", "ahora"],
  ["e", "feed"],
  ["l", "lista"],
  ["m", "metodologia"],
];

const POR_TECLA = new Map<string, Accion>(ATAJOS.map(([tecla, accion]) => [tecla, accion]));

interface Pulsacion {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  target: EventTarget | null;
}

function escribiendo(destino: EventTarget | null): boolean {
  if (typeof HTMLElement === "undefined" || !(destino instanceof HTMLElement)) return false;
  return (
    destino.isContentEditable ||
    ["INPUT", "SELECT", "TEXTAREA"].includes(destino.tagName) ||
    destino.getAttribute("role") === "slider"
  );
}

/**
 * Acción de una pulsación, o null. No hay atajos con Ctrl, Cmd o Alt (son del navegador)
 * ni mientras se escribe en un campo o se mueve un control deslizante.
 */
export function accionDe(pulsacion: Pulsacion): Accion | null {
  if (pulsacion.ctrlKey || pulsacion.metaKey || pulsacion.altKey) return null;
  if (pulsacion.key !== "Escape" && escribiendo(pulsacion.target)) return null;
  const tecla = pulsacion.key.length === 1 ? pulsacion.key.toLowerCase() : pulsacion.key;
  return POR_TECLA.get(tecla) ?? null;
}
