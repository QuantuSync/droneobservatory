// Agregados de la capa de Ucrania para un periodo: intensidad por región, cifras de una
// región y lanzamientos de cada noche.

import { diaDeFecha, enPeriodo } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";
import { DESCONOCIDO } from "./derivar.ts";
import type {
  FilaAtaque,
  FilaImpacto,
  FocoRegion,
  Rango,
  ResumenUcrania,
  Sentido,
} from "./tipos.ts";

const SENTIDOS: readonly Sentido[] = ["RU_UA", "UA_RU"];

export function sentidoDeFila(fila: FilaAtaque): Sentido {
  return SENTIDOS[fila[2]] ?? "RU_UA";
}

/**
 * Lo que cubre un parte: una noche (empieza un día y acaba al siguiente: «noche del 3 al 4 de
 * octubre») o un día (empieza y acaba el mismo día UTC: «día 1 de octubre»). Días UTC.
 */
export interface Jornada {
  tipo: "noche" | "dia";
  desde: number;
  hasta: number;
}

/**
 * La única regla para saber a qué noche (o día) pertenece un parte, a partir del día en que
 * empieza y del instante en que acaba. La usan «Europa ahora», «Noche a noche», la capa de
 * Ucrania, los corredores y las fichas: todas dan la misma noche para el mismo parte. Un
 * parte que acaba más de un día después (un error de la fuente) cuenta en la noche de su
 * comienzo.
 */
export function jornada(desde: number, fin: number): Jornada {
  const diaFin = diaDeFecha(new Date(fin));
  return diaFin > desde ? { tipo: "noche", desde, hasta: desde + 1 } : { tipo: "dia", desde, hasta: desde };
}

export function jornadaDeParte(fila: FilaAtaque): Jornada {
  return jornada(fila[1], fila[9]);
}

/** El día por el que un parte entra en un periodo: el de comienzo de su noche o su día. */
export function diaDeParte(fila: FilaAtaque): number {
  return jornadaDeParte(fila).desde;
}

function claveDeJornada(j: Jornada): string {
  return `${j.desde}-${j.tipo}`;
}

/** Orden en el tiempo: por día y, el mismo día, el parte de día antes que la noche. */
export function compararJornadas(a: Jornada, b: Jornada): number {
  return a.desde - b.desde || (a.tipo === b.tipo ? 0 : a.tipo === "dia" ? -1 : 1);
}

/** Número de ataques del periodo que citan cada región, por código ISO 3166-2. */
export function ataquesPorRegion(ucrania: ResumenUcrania, periodo: Periodo): Map<string, number> {
  const cuenta = new Map<string, number>();
  for (const fila of ucrania.ataques) {
    if (!enPeriodo(diaDeParte(fila), periodo)) continue;
    for (const [indice] of fila[8]) {
      const codigo = ucrania.regiones[indice];
      if (codigo !== undefined) cuenta.set(codigo, (cuenta.get(codigo) ?? 0) + 1);
    }
  }
  return cuenta;
}

export interface AtaqueDeRegion {
  id: string;
  jornada: Jornada;
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
    if (!enPeriodo(diaDeParte(fila), periodo)) continue;
    const region = fila[8].find(([indice]) => indice === indiceRegion);
    if (region === undefined) continue;
    const sentido = sentidoDeFila(fila);
    cifras.ataques[sentido] += 1;
    cifras.lista.push({ id: fila[0], jornada: jornadaDeParte(fila), sentido });
    const [, minimo, maximo] = region;
    // Un tramo cuyas cifras ya están en otro parte no se vuelve a sumar.
    if (minimo !== DESCONOCIDO && fila[7] === 1) {
      cifras.derribados = {
        min: (cifras.derribados?.min ?? 0) + minimo,
        max: (cifras.derribados?.max ?? 0) + maximo,
      };
    }
  }
  cifras.lista.sort((a, b) => compararJornadas(b.jornada, a.jornada) || b.id.localeCompare(a.id));
  return cifras;
}

/** Focos térmicos detectados en regiones de Ucrania en el periodo; de una región, si se da. */
export function focosDelPeriodo(
  ucrania: ResumenUcrania,
  periodo: Periodo,
  codigo?: string,
): FocoRegion[] {
  return ucrania.focos.filter(
    (f) => enPeriodo(f.dia, periodo) && (codigo === undefined || f.region === codigo),
  );
}

/**
 * Impactos con lugar del periodo, de los dos sentidos; de una región, si se da. Del más
 * reciente al más antiguo cuando se pide una región (para su lista).
 */
export function impactosDelPeriodo(
  ucrania: ResumenUcrania,
  periodo: Periodo,
  codigo?: string,
): FilaImpacto[] {
  const filas = ucrania.impactos.filter(
    (f) => enPeriodo(f[1], periodo) && (codigo === undefined || f[8] === codigo),
  );
  return codigo === undefined ? filas : filas.slice().reverse();
}

/** Centro de cada región con foco térmico, para abrir el visor de FIRMS desde un ataque. */
export function centrosDeFocos(ucrania: ResumenUcrania): Map<string, [number, number]> {
  return new Map(ucrania.focos.map((f) => [f.region, f.centro]));
}

/** Primer y último día con ataques; null si no hay ninguno. */
export function dominioUcrania(ucrania: ResumenUcrania): Periodo | null {
  const primero = ucrania.ataques[0];
  const ultimo = ucrania.ataques[ucrania.ataques.length - 1];
  if (primero === undefined || ultimo === undefined) return null;
  return { desde: diaDeParte(primero), hasta: diaDeParte(ultimo) };
}

export interface NocheDeGuerra {
  jornada: Jornada;
  /** Peso de cada región esa noche: derribos desglosados si los hay; si no, 1 por parte. */
  regiones: Map<string, number>;
  /** Drones lanzados contra Ucrania esa noche; null si ningún parte da la cifra. */
  lanzados: number | null;
  /** De ellos, Shahed y Geran que los partes cuentan aparte (mínimo); null si no lo dicen. */
  shahed: number | null;
  /** De ellos, drones a reacción que los partes cuentan aparte (mínimo); null si no lo dicen. */
  reactivos: number | null;
  /** El fin más tardío de sus partes (ms), para saber cuánto hace. */
  fin: number;
}

/**
 * Noches (y días) de ataques contra Ucrania, en orden, para reproducir la guerra noche a
 * noche y para «Europa ahora»: cada parte cuenta una sola vez y en su noche (jornadaDeParte);
 * un parte de día no se suma a la noche siguiente aunque empiecen el mismo día. Los tramos
 * cuyas cifras ya están en otro parte (incluidos o solapados) no se suman dos veces.
 */
export function nochesDeGuerra(ucrania: ResumenUcrania): NocheDeGuerra[] {
  const porJornada = new Map<string, NocheDeGuerra>();
  for (const fila of ucrania.ataques) {
    if (sentidoDeFila(fila) !== "RU_UA") continue;
    const cual = jornadaDeParte(fila);
    const clave = claveDeJornada(cual);
    const noche = porJornada.get(clave) ?? {
      jornada: cual,
      regiones: new Map(),
      lanzados: null,
      shahed: null,
      reactivos: null,
      fin: fila[9],
    };
    noche.fin = Math.max(noche.fin, fila[9]);
    const suma = fila[7] === 1;
    if (suma && fila[4] !== DESCONOCIDO) noche.lanzados = (noche.lanzados ?? 0) + fila[4];
    if (suma && fila[10] > 0) noche.shahed = (noche.shahed ?? 0) + fila[10];
    if (suma && fila[11] > 0) noche.reactivos = (noche.reactivos ?? 0) + fila[11];
    for (const [indice, , derribadosMax] of fila[8]) {
      const codigo = ucrania.regiones[indice];
      if (codigo === undefined) continue;
      const peso = suma && derribadosMax !== DESCONOCIDO && derribadosMax > 0 ? derribadosMax : 1;
      noche.regiones.set(codigo, (noche.regiones.get(codigo) ?? 0) + peso);
    }
    porJornada.set(clave, noche);
  }
  return [...porJornada.values()].sort((a, b) => compararJornadas(a.jornada, b.jornada));
}

/** La última noche (o día) con cifra de lanzados: la que enseña «Europa ahora». */
export function ultimaNocheConCifra(ucrania: ResumenUcrania): NocheDeGuerra | null {
  return nochesDeGuerra(ucrania).findLast((n) => n.lanzados !== null) ?? null;
}
