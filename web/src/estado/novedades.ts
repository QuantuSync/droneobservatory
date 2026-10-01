// «Nuevo desde tu última visita». La fecha de la visita anterior se guarda solo en el
// almacenamiento local del navegador: sin cookies y sin salir del equipo. Si el navegador
// no deja guardar (modo privado, almacenamiento bloqueado), la web funciona igual y no
// resalta nada.

import type { EventoResumen } from "../datos/tipos.ts";

export const CLAVE_VISITA = "eodi.ultima-visita";

/** Lo mínimo que se usa del almacenamiento: así se prueba sin navegador. */
export interface Almacen {
  getItem(clave: string): string | null;
  setItem(clave: string, valor: string): void;
}

/** El almacenamiento local, o null si no existe o el navegador lo bloquea. */
export function almacenLocal(): Almacen | null {
  try {
    const almacen = window.localStorage;
    const prueba = `${CLAVE_VISITA}.prueba`;
    almacen.setItem(prueba, "1");
    almacen.removeItem(prueba);
    return almacen;
  } catch {
    return null;
  }
}

const PATRON_FECHA = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?Z$/;

/** Lee la visita anterior y apunta la actual. Devuelve la anterior, o null si no la hay. */
export function registrarVisita(almacen: Almacen | null, ahora: Date): string | null {
  if (almacen === null) return null;
  let anterior: string | null = null;
  try {
    const guardada = almacen.getItem(CLAVE_VISITA);
    anterior = guardada !== null && PATRON_FECHA.test(guardada) ? guardada : null;
    almacen.setItem(CLAVE_VISITA, ahora.toISOString());
  } catch {
    // Lleno o bloqueado a mitad: se sigue sin novedades.
  }
  return anterior;
}

/** Eventos posteriores a la visita anterior, del más reciente al más antiguo. */
export function novedadesDesde(
  eventos: readonly EventoResumen[],
  anterior: string | null,
): EventoResumen[] {
  if (anterior === null) return [];
  const desde = new Date(anterior).getTime();
  return eventos.filter((evento) => new Date(evento.fecha).getTime() > desde);
}

/** Incidentes distintos de una lista de eventos, en el orden en que aparecen. */
export function incidentesDe(eventos: readonly EventoResumen[]): string[] {
  return [...new Set(eventos.map((evento) => evento.id))];
}
