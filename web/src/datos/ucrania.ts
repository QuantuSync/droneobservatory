// Agregados de la capa de Ucrania para un periodo: intensidad por región, cifras de una
// región y lanzamientos de cada noche.

import { enPeriodo } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";
import { DESCONOCIDO } from "./derivar.ts";
import type { FilaAtaque, Rango, ResumenUcrania, Sentido } from "./tipos.ts";

const SENTIDOS: readonly Sentido[] = ["RU_UA", "UA_RU"];

export function sentidoDeFila(fila: FilaAtaque): Sentido {
  return SENTIDOS[fila[2]] ?? "RU_UA";
}

/** Número de ataques del periodo que citan cada región, por código ISO 3166-2. */
export function ataquesPorRegion(ucrania: ResumenUcrania, periodo: Periodo): Map<string, number> {
  const cuenta = new Map<string, number>();
  for (const fila of ucrania.ataques) {
    if (!enPeriodo(fila[1], periodo)) continue;
    for (const [indice] of fila[8]) {
      const codigo = ucrania.regiones[indice];
      if (codigo !== undefined) cuenta.set(codigo, (cuenta.get(codigo) ?? 0) + 1);
    }
  }
  return cuenta;
}

export interface AtaqueDeRegion {
  id: string;
  dia: number;
  sentido: Sentido;
}

export interface CifrasRegion {
  ataques: Record<Sentido, number>;
  /** Suma de los derribos que los partes desglosan para la región; null si ninguno lo hace. */
  derribados: Rango | null;
  /** Ataques que citan la región, del más reciente al más antiguo. */
  lista: AtaqueDeRegion[];
}

export function cifrasDeRegion(
  ucrania: ResumenUcrania,
  codigo: string,
  periodo: Periodo,
): CifrasRegion {
  const indiceRegion = ucrania.regiones.indexOf(codigo);
  const cifras: CifrasRegion = { ataques: { RU_UA: 0, UA_RU: 0 }, derribados: null, lista: [] };
  if (indiceRegion === -1) return cifras;
  for (const fila of ucrania.ataques) {
    if (!enPeriodo(fila[1], periodo)) continue;
    const region = fila[8].find(([indice]) => indice === indiceRegion);
    if (region === undefined) continue;
    const sentido = sentidoDeFila(fila);
    cifras.ataques[sentido] += 1;
    cifras.lista.push({ id: fila[0], dia: fila[1], sentido });
    const [, minimo, maximo] = region;
    // Un tramo cuyas cifras ya están en otro parte no se vuelve a sumar.
    if (minimo !== DESCONOCIDO && fila[7] === 1) {
      cifras.derribados = {
        min: (cifras.derribados?.min ?? 0) + minimo,
        max: (cifras.derribados?.max ?? 0) + maximo,
      };
    }
  }
  cifras.lista.sort((a, b) => b.dia - a.dia || b.id.localeCompare(a.id));
  return cifras;
}

/**
 * Drones lanzados contra Ucrania por día de inicio del ataque (el máximo del rango que da
 * el parte). Los tramos ya incluidos en otro parte no se suman.
 */
export function lanzamientosPorNoche(ucrania: ResumenUcrania): Map<number, number> {
  const porDia = new Map<number, number>();
  for (const fila of ucrania.ataques) {
    const lanzados = fila[4];
    if (sentidoDeFila(fila) !== "RU_UA" || lanzados === DESCONOCIDO || fila[7] === 0) continue;
    porDia.set(fila[1], (porDia.get(fila[1]) ?? 0) + lanzados);
  }
  return porDia;
}

/** Primer y último día con ataques; null si no hay ninguno. */
export function dominioUcrania(ucrania: ResumenUcrania): Periodo | null {
  const primero = ucrania.ataques[0];
  const ultimo = ucrania.ataques[ucrania.ataques.length - 1];
  if (primero === undefined || ultimo === undefined) return null;
  return { desde: primero[1], hasta: ultimo[1] };
}
