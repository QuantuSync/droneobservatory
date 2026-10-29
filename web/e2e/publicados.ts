// Lo que los recorridos esperan de una ficha, leído de los datos publicados y no escrito a mano.
//
// El repaso une fichas (el enlace antiguo lleva a la que queda), retira otras y cambia titulares:
// el 29 de octubre de 2026 el recorrido del mar Negro esperaba que la 00538 llevara a sí misma y el
// repaso la había unido en la 00541 (incidencia «Los recorridos fallan en producción»). Con estas
// funciones el recorrido pregunta a los datos de la propia web adónde lleva cada identificador y
// qué fichas cumplen lo que quiere probar.

import type { APIRequestContext } from "@playwright/test";

import type { ColeccionIncidentes, PropiedadesIncidente, PropiedadesSinUbicacion, PublicacionSinUbicacion } from "../src/datos/tipos.ts";

export type Ficha = PropiedadesIncidente | PropiedadesSinUbicacion;

export interface Publicados {
  /** Fichas publicadas (con lugar y sin él), por identificador. */
  fichas: Map<string, Ficha>;
  /** Identificador unido -> el que queda. */
  unidos: Record<string, string>;
  /** El punto del mapa de las fichas con lugar ([lon, lat]). */
  puntos: Map<string, [number, number]>;
}

let guardados: Promise<Publicados> | null = null;

/** Los datos publicados de la web a la que va el recorrido (una vez por proceso). */
export function publicados(peticiones: APIRequestContext): Promise<Publicados> {
  guardados ??= (async () => {
    const coleccion = (await (await peticiones.get("/datos/incidentes.geojson")).json()) as ColeccionIncidentes;
    const sinLugar = (await (await peticiones.get("/datos/incidentes_sin_ubicacion.json")).json()) as PublicacionSinUbicacion;
    const fichas = new Map<string, Ficha>();
    const puntos = new Map<string, [number, number]>();
    for (const f of coleccion.features) {
      fichas.set(f.properties.id, f.properties);
      puntos.set(f.properties.id, f.geometry.coordinates);
    }
    for (const f of sinLugar.incidentes) fichas.set(f.id, f);
    return { fichas, unidos: coleccion.unidos ?? {}, puntos };
  })();
  return guardados;
}

/**
 * Adónde lleva la dirección de un identificador: a su propia ficha si está publicada, a la que
 * queda si se unió (siguiendo uniones encadenadas) o null si no está (retirada: responde 404).
 */
export function destino(datos: Publicados, id: string): string | null {
  let actual = id;
  for (let saltos = 0; saltos < 20; saltos += 1) {
    if (datos.fichas.has(actual)) return actual;
    const siguiente = datos.unidos[actual];
    if (siguiente === undefined) return null;
    actual = siguiente;
  }
  return null;
}

/**
 * La ficha con la que probar algo: la preferida (o la que queda si se unió) si aún cumple lo que se
 * quiere probar; si no, la primera de los datos que lo cumpla, por identificador; null si ninguna
 * (la prueba se salta con su motivo: los datos ya no tienen ese caso).
 */
export function elegir(datos: Publicados, preferido: string, cumple: (f: Ficha) => boolean): string | null {
  const queda = destino(datos, preferido);
  const suya = queda === null ? undefined : datos.fichas.get(queda);
  if (queda !== null && suya !== undefined && cumple(suya)) return queda;
  return [...datos.fichas.keys()].sort().find((id) => cumple(datos.fichas.get(id) as Ficha)) ?? null;
}
