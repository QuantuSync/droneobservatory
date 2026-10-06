// Previsión y tendencias (publicacion/prevision.json, proceso/prevision): solo lo que ha pasado
// la comprobación con el pasado, cada parte con su historial de aciertos, y el registro de las
// previsiones hechas en vivo con su resultado.

import type { Textos } from "../i18n/index.ts";

export type Efecto = "sube" | "baja" | "nada";
export type Tendencia = "crece" | "estable" | "se_apaga";

export interface TramoAcierto {
  desde: number;
  hasta: number;
  noches: number;
  con_dron: number;
  prevista_media: number;
}

export interface ComprobacionFrontera {
  pais: string;
  desde: string;
  noches: number;
  noches_con_dron: number;
  area_bajo_curva: number | null;
  mejora_sobre_frecuencia: number;
  mejora_sobre_persistencia: number;
  mejora_cota: number;
  con_dron_en_riesgo_alto: number;
  tramos: TramoAcierto[];
  publicable: true;
}

export interface FronteraPais {
  pais: string;
  probabilidad: number;
  de_cada_10: number;
  frecuencia_de_siempre: number;
  factores: {
    lanzados_anoche: number;
    lanzados_tres_noches: number;
    noches_desde_crimea: number;
    incidentes_siete_dias: number;
  };
  efectos: {
    lanzados_tres_noches: Efecto;
    noches_desde_crimea: Efecto;
    incidentes_siete_dias: Efecto;
  };
  comprobacion: ComprobacionFrontera;
  ultimas: { noche: string; probabilidad: number; con_dron: boolean }[];
}

export interface ComprobacionSemana {
  pais: string;
  grupo: "todo" | "frontera" | "interior";
  semanas: number;
  mejora_sobre_frecuencia: number;
  mejora_sobre_persistencia: number;
  mejora_cota: number;
  dentro_del_margen: number;
  publicable: true;
}

export interface SemanaPais {
  pais: string;
  esperado: number;
  minimo: number;
  maximo: number;
  comprobacion: ComprobacionSemana;
}

export interface FilaMarcador {
  semana: string;
  pais: string;
  esperado: number;
  minimo: number;
  maximo: number;
  real: number;
  dentro: boolean;
  tipo: "reconstruida" | "en_vivo";
}

export interface Racha {
  pais: string;
  grupo: "todo" | "frontera" | "interior";
  desde: string;
  hasta: string;
  semanas: number;
  incidentes: number;
  habitual: number;
  veces: number;
  tendencia: Tendencia;
}

export interface GraficaRacha {
  semanas: string[];
  incidentes: number[];
  normal: number;
  banda: [number, number];
}

export interface EntradaRegistro {
  id: string;
  tipo: "frontera" | "semana" | "segunda_noche";
  pais: string;
  objetivo: string;
  emitida: string;
  metodo: string;
  probabilidad?: number;
  esperado?: number;
  minimo?: number;
  maximo?: number;
  con_dron?: boolean;
  real?: number;
  dentro?: boolean;
  grande?: boolean;
}

export interface Prevision {
  version_esquema: "1.0.0";
  version: string;
  calculado: string;
  datos_hasta: string;
  metodo: { es: string; en: string };
  frontera: { version: string; noche: { desde: string; hasta: string }; paises: FronteraPais[] };
  semana: { version: string; semana: string; fijada: boolean; paises: SemanaPais[]; marcador: FilaMarcador[] };
  segunda_noche?: {
    comprobacion: Record<string, unknown>;
    aviso?: { tras_noche: string; lanzados: number; probabilidad: number; de_cada_10: number };
  };
  rachas?: {
    version: string;
    modo: "todo" | "por_grupo";
    comprobacion: {
      semanas_en_racha: number;
      incidentes_semana_siguiente: number;
      normal_semana_siguiente: number;
      mejora_sobre_normal: number;
      mejora_cota: number;
      publicable: true;
    };
    activas: Racha[];
    terminadas: { pais: string; grupo: "todo" | "frontera" | "interior"; hasta: string }[];
    graficas: Record<string, GraficaRacha>;
  };
  cajas: Record<string, [number, number, number, number]>;
  registro: EntradaRegistro[];
}

/** La racha de un país, si la tiene, con su gráfica. */
export function rachaDe(
  prevision: Prevision | null,
  pais: string,
): { racha: Racha; grafica: GraficaRacha | null } | null {
  const racha = prevision?.rachas?.activas.find((r) => r.pais === pais);
  if (racha === undefined || prevision?.rachas === undefined) return null;
  return { racha, grafica: prevision.rachas.graficas[pais] ?? null };
}

/** Las previsiones hechas en vivo de un tipo y su resultado. */
export function enVivo(prevision: Prevision, tipo: EntradaRegistro["tipo"], pais?: string): EntradaRegistro[] {
  return prevision.registro.filter((e) => e.tipo === tipo && (pais === undefined || e.pais === pais));
}

/** El marcador de la semana con las previsiones en vivo ya puntuadas en lugar de las reconstruidas. */
export function marcadorSemanal(prevision: Prevision): FilaMarcador[] {
  const vivas = new Map<string, FilaMarcador>();
  for (const e of enVivo(prevision, "semana")) {
    if (e.real === undefined || e.esperado === undefined || e.minimo === undefined || e.maximo === undefined) {
      continue;
    }
    vivas.set(`${e.pais}:${e.objetivo}`, {
      semana: e.objetivo,
      pais: e.pais,
      esperado: e.esperado,
      minimo: e.minimo,
      maximo: e.maximo,
      real: e.real,
      dentro: e.dentro ?? false,
      tipo: "en_vivo",
    });
  }
  const filas = prevision.semana.marcador.map((f) => vivas.get(`${f.pais}:${f.semana}`) ?? f);
  for (const [clave, fila] of vivas) {
    if (!filas.some((f) => `${f.pais}:${f.semana}` === clave)) filas.push(fila);
  }
  return filas.sort((a, b) => b.semana.localeCompare(a.semana) || a.pais.localeCompare(b.pais));
}

/** Probabilidad en palabras y con su número: «4 de cada 10 noches como esta (40 %)». */
export function probabilidadLlana(t: Textos, p: number, deCada10: number): string {
  return t.prevision.deCada10(deCada10, Math.round(p * 100));
}

/** Días desde el 1 de enero de 1970 de un texto AAAA-MM-DD. */
export function diaDeTexto(texto: string): number {
  return Math.round(Date.UTC(Number(texto.slice(0, 4)), Number(texto.slice(5, 7)) - 1, Number(texto.slice(8, 10))) / 86400000);
}
