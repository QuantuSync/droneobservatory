// La presencia de dron cuando una autoridad la rectifica: cómo se dibuja el incidente, si cuenta
// entre los confirmados y su historial escrito. Funciones puras: las usan el mapa, las listas, la
// ficha, las cifras, las páginas de texto y el CSV.
//
// Rectificar la presencia no borra nada: el incidente ocurrió (si un aeropuerto cerró, cerró) y
// sigue en el mapa con su efecto y su historial entero. Lo que cambia es lo que se sabe del dron.

import { instante, textoAtribuido } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import type { AtribucionResumen, Estado, Fuente, MarcaIncidente, PasoPresencia, PresenciaDron } from "./tipos.ts";

/** Las marcas en el orden de la leyenda, los filtros y las cifras por estado. */
export const MARCAS: readonly MarcaIncidente[] = ["notificado", "confirmado", "atribuido", "no_acreditado", "desmentido"];

interface ConPresencia {
  estado: Estado;
  presencia: PresenciaDron | null;
}

/**
 * La marca de un incidente. Con la presencia «no acreditada» (la autoridad cerró su investigación
 * sin pruebas del dron o retiró su declaración sin decir que fuera otra cosa) va en morado, también
 * si estaba atribuido: la atribución se apoyaba en un dron que ya nadie acredita. Un desmentido
 * sigue gris (el incidente no ocurrió) y una presencia «descartada» no cambia la marca.
 */
export function marcaDe(i: ConPresencia): MarcaIncidente {
  return i.presencia === "no_acreditada" && i.estado !== "desmentido" ? "no_acreditado" : i.estado;
}

/** El nombre de una marca, en la leyenda, los filtros y las cifras por estado. */
export function rotuloDeMarca(t: Textos, marca: MarcaIncidente): string {
  return marca === "no_acreditado" ? t.noAcreditado.etiqueta : t.estado[marca];
}

/**
 * El estado escrito junto al símbolo (listas, letrero y lector de pantalla del mapa): «Atribuido a
 * Rusia» en un atribuido; con la presencia no acreditada, el estado y la presencia, para que el
 * círculo morado nunca vaya con un texto que solo diga «Confirmado».
 */
export function estadoEscrito(
  t: Textos,
  idioma: Idioma,
  i: ConPresencia & { atribucion: AtribucionResumen | null },
): string {
  if (marcaDe(i) === "no_acreditado") return `${t.estado[i.estado]} · ${t.presencia.no_acreditada}`;
  return i.estado === "atribuido" ? textoAtribuido(t, idioma, i.atribucion) : t.estado[i.estado];
}

/** Presencias que una autoridad rectificó: sin pruebas del dron, o fue otra cosa. */
const RECTIFICADAS: ReadonlySet<PresenciaDron> = new Set<PresenciaDron>(["no_acreditada", "descartada"]);

/**
 * Si cuenta entre los «confirmados por una autoridad» (el marcador, las páginas de texto y el
 * filtro «Solo confirmados y atribuidos»): confirmado o atribuido, con la presencia de dron sin
 * rectificar. Un no acreditado o un descartado sigue contando como incidente, no como confirmado.
 */
export function confirmadoPorAutoridad(i: ConPresencia): boolean {
  return (i.estado === "confirmado" || i.estado === "atribuido") && (i.presencia === null || !RECTIFICADAS.has(i.presencia));
}

/**
 * Los pasos del historial de la presencia, por orden de fecha; vacío si no hay o si no es una lista
 * (validar.ts vacía el que no valida: la ficha enseña entonces solo la presencia en vigor).
 */
export function historialDePresencia(p: { presencia_historial?: PasoPresencia[] | undefined }): PasoPresencia[] {
  const historial: unknown = p.presencia_historial;
  return Array.isArray(historial) ? [...(historial as PasoPresencia[])].sort((a, b) => a.fecha.valor.localeCompare(b.fecha.valor)) : [];
}

/** Un paso escrito: la frase que enlaza a su fuente y lo que la sigue (el motivo). */
export interface PasoPresenciaEscrito {
  valor: PresenciaDron;
  parcial: boolean;
  /** «Confirmado el 23/09/2025 por la policía de Copenhague», «Corrección parcial el …». */
  texto: string;
  /** «, tras la investigación: …» o «: …» en una corrección parcial; vacío sin motivo. */
  resto: string;
  /** La fuente del paso, si está entre las del incidente. */
  fuente: Fuente | undefined;
}

/** El historial de la presencia escrito en el idioma de la página, con la fuente de cada paso. */
export function pasosDePresencia(
  t: Textos,
  idioma: Idioma,
  incidente: { presencia_historial?: PasoPresencia[] | undefined; fuentes: readonly Fuente[] },
): PasoPresenciaEscrito[] {
  const porFuente = new Map(incidente.fuentes.map((f) => [f.id, f]));
  const p = t.presenciaHistorial;
  return historialDePresencia(incidente).map((paso) => {
    const parcial = paso.parcial === true;
    const quien = paso.quien?.[idioma] ?? null;
    const fecha = instante(paso.fecha);
    const motivo = paso.motivo?.[idioma];
    return {
      valor: paso.valor,
      parcial,
      texto: parcial ? p.parcial(fecha, quien) : p.paso(p.valor[paso.valor], fecha, quien),
      resto: motivo === undefined ? "" : parcial ? `: ${motivo}` : `, ${motivo}`,
      fuente: porFuente.get(paso.fuente_id),
    };
  });
}

/** El historial para una celda del CSV: «2025-09-23:confirmada|2026-06-25:no_acreditada». */
export function historialEnCelda(p: { presencia_historial?: PasoPresencia[] | undefined }): string | undefined {
  const pasos = historialDePresencia(p);
  if (pasos.length === 0) return undefined;
  return pasos.map((paso) => `${paso.fecha.valor.slice(0, 10)}:${paso.valor}${paso.parcial === true ? ":parcial" : ""}`).join("|");
}
