// Versiones CSV de los datos abiertos. Funciones puras que usa el build.

import { ORIGEN } from "../sitio.ts";
import type { ColeccionIncidentes, PublicacionUcrania, RangoODesconocido } from "./tipos.ts";

type Celda = string | number | undefined;

const SEPARADOR_LISTA = "|";
/** Una hoja de cálculo interpreta como fórmula la celda que empieza por estos caracteres. */
const INICIO_DE_FORMULA = /^[=+\-@\t\r]/;

/** Celda CSV (RFC 4180). Un texto que empezaría una fórmula se neutraliza con un apóstrofo. */
export function celda(valor: Celda): string {
  if (valor === undefined) return "";
  if (typeof valor === "number") return String(valor);
  const seguro = INICIO_DE_FORMULA.test(valor) ? `'${valor}` : valor;
  return /[",\r\n]/.test(seguro) ? `"${seguro.replaceAll('"', '""')}"` : seguro;
}

export function csv(cabecera: readonly string[], filas: readonly Celda[][]): string {
  const lineas = [cabecera.map(celda), ...filas.map((fila) => fila.map(celda))];
  return lineas.map((linea) => linea.join(",")).join("\r\n") + "\r\n";
}

function minimo(rango: RangoODesconocido | undefined): Celda {
  return rango === undefined || rango === "desconocido" ? undefined : rango.min;
}

function maximo(rango: RangoODesconocido | undefined): Celda {
  return rango === undefined || rango === "desconocido" ? undefined : rango.max;
}

export const COLUMNAS_INCIDENTES = [
  "id",
  "tipo",
  "estado",
  "presencia_dron",
  "titulo_es",
  "titulo_en",
  "inicio",
  "inicio_precision",
  "fin",
  "duracion_min",
  "latitud",
  "longitud",
  "radio_km",
  "pais",
  "localidad",
  "objetivo_categoria",
  "objetivo_nombre",
  "objetivo_oaci",
  "drones_min",
  "drones_max",
  "cierre",
  "medidas",
  "atribucion_actor",
  "atribucion_autoridad",
  "episodio",
  "fuentes",
  "ultima_actualizacion",
  "enlace",
] as const;

export function csvIncidentes(coleccion: ColeccionIncidentes): string {
  const filas = coleccion.features.map((feature): Celda[] => {
    const p = feature.properties;
    const [lon, lat] = feature.geometry.coordinates;
    return [
      p.id,
      p.tipo,
      p.estado.actual,
      p.presencia_dron,
      p.titulo.es,
      p.titulo.en,
      p.tiempo.inicio.valor,
      p.tiempo.inicio.precision,
      p.tiempo.fin?.valor,
      p.tiempo.duracion_min,
      lat,
      lon,
      p.lugar.radio_km,
      p.lugar.pais,
      p.lugar.localidad,
      p.objetivo?.categoria,
      p.objetivo?.nombre,
      p.objetivo?.oaci,
      minimo(p.drones?.numero),
      maximo(p.drones?.numero),
      p.consecuencias?.cierre?.valor,
      p.respuesta?.medidas?.join(SEPARADOR_LISTA),
      p.atribucion?.actor,
      p.atribucion?.autoridad,
      p.episodio,
      p.fuentes.length,
      p.control.ultima_actualizacion.valor,
      `${ORIGEN}/${p.id}`,
    ];
  });
  return csv(COLUMNAS_INCIDENTES, filas);
}

export const COLUMNAS_ATAQUES = [
  "id",
  "sentido",
  "inicio",
  "fin",
  "lanzados_total_min",
  "lanzados_total_max",
  "shahed_geran_min",
  "shahed_geran_max",
  "gerbera_senuelos_min",
  "gerbera_senuelos_max",
  "derribados_min",
  "derribados_max",
  "derribados_categoria",
  "perdidos_guerra_electronica_min",
  "perdidos_guerra_electronica_max",
  "regiones",
  "incluido_en",
  "solapado_con",
  "fuente",
  "ultima_actualizacion",
  "enlace",
] as const;

export function csvAtaques(ucrania: PublicacionUcrania): string {
  const filas = ucrania.ataques.map((a): Celda[] => [
    a.id,
    a.sentido,
    a.periodo.inicio.valor,
    a.periodo.fin.valor,
    minimo(a.lanzados?.total),
    maximo(a.lanzados?.total),
    minimo(a.lanzados?.shahed_geran),
    maximo(a.lanzados?.shahed_geran),
    minimo(a.lanzados?.gerbera_senuelos),
    maximo(a.lanzados?.gerbera_senuelos),
    minimo(a.derribados),
    maximo(a.derribados),
    a.derribados_categoria,
    minimo(a.perdidos_guerra_electronica),
    maximo(a.perdidos_guerra_electronica),
    (a.regiones ?? []).map((r) => r.region).join(SEPARADOR_LISTA),
    a.incluido_en,
    a.solapado_con,
    a.fuentes[0]?.enlace,
    a.control.ultima_actualizacion.valor,
    `${ORIGEN}/${a.id}`,
  ]);
  return csv(COLUMNAS_ATAQUES, filas);
}
