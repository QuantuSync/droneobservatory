// Presión por país: incidentes de cada país en el periodo elegido y su tendencia frente al
// periodo anterior de la misma duración. Se calcula en el navegador con los datos publicados y
// los filtros activos.

import type { Periodo } from "../tiempo/dias.ts";
import { incidenteEnPeriodo } from "../tiempo/dias.ts";
import type { Estado, IncidenteResumen, Tipo } from "./tipos.ts";
import { ESTADOS, TIPOS } from "./vocabulario.ts";

export type Sentido = "sube" | "baja" | "estable";

export interface Tendencia {
  sentido: Sentido;
  /** Diferencia con el periodo anterior (actual − anterior). */
  diferencia: number;
  anterior: number;
}

export interface PresionPais {
  pais: string;
  incidentes: number;
  /** null cuando el periodo anterior queda entero antes del primer dato. */
  tendencia: Tendencia | null;
}

/** Diferencia que se lee como estable: ninguna, o una sola que no llega al 10 % de lo anterior. */
export const DIFERENCIA_ESTABLE = 1;
export const FRACCION_ESTABLE = 0.1;

/** El periodo inmediatamente anterior de igual duración (las 24 horas anteriores, en su caso). */
export function periodoAnterior(periodo: Periodo): Periodo {
  const largo = periodo.hasta - periodo.desde + 1;
  const anterior: Periodo = { desde: periodo.desde - largo, hasta: periodo.desde - 1 };
  if (periodo.ventana === undefined) return anterior;
  const duracion = periodo.ventana.hasta - periodo.ventana.desde;
  return {
    ...anterior,
    ventana: { desde: periodo.ventana.desde - duracion, hasta: periodo.ventana.desde - 1 },
  };
}

export function sentidoDe(actual: number, anterior: number): Sentido {
  const diferencia = actual - anterior;
  if (diferencia === 0) return "estable";
  if (Math.abs(diferencia) <= DIFERENCIA_ESTABLE && Math.abs(diferencia) <= FRACCION_ESTABLE * anterior) {
    return "estable";
  }
  return diferencia > 0 ? "sube" : "baja";
}

function contar(incidentes: readonly IncidenteResumen[], periodo: Periodo): Map<string, number> {
  const cuenta = new Map<string, number>();
  for (const i of incidentes) {
    if (incidenteEnPeriodo(i, periodo)) cuenta.set(i.pais, (cuenta.get(i.pais) ?? 0) + 1);
  }
  return cuenta;
}

/**
 * Por país, los incidentes del periodo y la tendencia frente al anterior de igual duración.
 * `incidentes` son los que pasan los filtros, sin recortar por periodo; `primerDia` es el
 * primer día con datos.
 */
export function presionPorPais(
  incidentes: readonly IncidenteResumen[],
  periodo: Periodo,
  primerDia: number,
): Map<string, PresionPais> {
  const anterior = periodoAnterior(periodo);
  const comparable = anterior.hasta >= primerDia;
  const actuales = contar(incidentes, periodo);
  const previos = contar(incidentes, anterior);
  const paises = new Set([...actuales.keys(), ...(comparable ? previos.keys() : [])]);
  const resultado = new Map<string, PresionPais>();
  for (const pais of paises) {
    const n = actuales.get(pais) ?? 0;
    const antes = previos.get(pais) ?? 0;
    resultado.set(pais, {
      pais,
      incidentes: n,
      tendencia: comparable
        ? { sentido: sentidoDe(n, antes), diferencia: n - antes, anterior: antes }
        : null,
    });
  }
  return resultado;
}

/** Escalones de gris del relleno, de menos a más incidentes. */
export const ESCALA_PRESION: readonly number[] = [0.08, 0.16, 0.25, 0.35, 0.46];

/** Escalón de cada país según su cuenta frente al máximo del periodo; los que no tienen ninguno no se rellenan. */
export function escalones(presion: ReadonlyMap<string, PresionPais>): Map<string, number> {
  const tope = Math.max(0, ...[...presion.values()].map((p) => p.incidentes));
  const resultado = new Map<string, number>();
  if (tope === 0) return resultado;
  for (const p of presion.values()) {
    if (p.incidentes === 0) continue;
    const escalon = Math.min(
      ESCALA_PRESION.length - 1,
      Math.floor((p.incidentes / tope) * ESCALA_PRESION.length),
    );
    resultado.set(p.pais, ESCALA_PRESION[escalon] ?? 0);
  }
  return resultado;
}

export interface CifrasPais {
  porTipo: Record<Tipo, number>;
  porEstado: Record<Estado, number>;
  /** Incidentes del país en el periodo, del más reciente al más antiguo. */
  lista: IncidenteResumen[];
}

export function cifrasDePais(
  incidentes: readonly IncidenteResumen[],
  pais: string,
  periodo: Periodo,
): CifrasPais {
  const porTipo = Object.fromEntries(TIPOS.map((t) => [t, 0])) as Record<Tipo, number>;
  const porEstado = Object.fromEntries(ESTADOS.map((e) => [e, 0])) as Record<Estado, number>;
  const lista = incidentes.filter((i) => i.pais === pais && incidenteEnPeriodo(i, periodo));
  for (const i of lista) {
    porTipo[i.tipo] += 1;
    porEstado[i.estado] += 1;
  }
  lista.sort((a, b) => b.dia - a.dia || b.id.localeCompare(a.id));
  return { porTipo, porEstado, lista };
}
