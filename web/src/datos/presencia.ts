// La presencia de dron cuando una autoridad la rectifica: cómo se dibuja el incidente, si cuenta
// entre los confirmados y su historial escrito. Funciones puras: las usan el mapa, las listas, la
// ficha, las cifras, las páginas de texto y el CSV.
//
// Rectificar la presencia no borra nada: el incidente ocurrió (si un aeropuerto cerró, cerró) y
// sigue en el mapa con su efecto y su historial entero. Lo que cambia es lo que se sabe del dron.

import { instante, textoAtribuido } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import type { AtribucionResumen, Estado, Fuente, MarcaIncidente, PasoHistorial, PasoPresencia, PresenciaDron } from "./tipos.ts";

/** Las marcas en el orden de la leyenda, los filtros y las cifras por estado. */
export const MARCAS: readonly MarcaIncidente[] = ["notificado", "confirmado", "atribuido", "no_acreditado", "descartado", "desmentido"];

interface ConPresencia {
  estado: Estado;
  presencia: PresenciaDron | null;
}

/**
 * La marca de una presencia de dron rectificada: morado «no acreditado» (la autoridad cerró su
 * investigación sin pruebas del dron o retiró su declaración sin decir que fuera otra cosa) o gris
 * relleno «descartado» (la autoridad dice que fue otra cosa); null si no se rectificó.
 */
export function marcaDePresencia(presencia: PresenciaDron | null | undefined): "no_acreditado" | "descartado" | null {
  return presencia === "no_acreditada" ? "no_acreditado" : presencia === "descartada" ? "descartado" : null;
}

/**
 * La marca de un incidente. Con la presencia rectificada manda la presencia: morado si no está
 * acreditada, gris relleno si está descartada, también si estaba atribuido (la atribución se
 * apoyaba en un dron que ya nadie acredita). El incidente ocurrió igual: su estado y su efecto no
 * cambian. Un desmentido sigue como desmentido (el incidente no ocurrió).
 */
export function marcaDe(i: ConPresencia): MarcaIncidente {
  if (i.estado === "desmentido") return i.estado;
  return marcaDePresencia(i.presencia) ?? i.estado;
}

/** El nombre de una marca, en la leyenda, los filtros y las cifras por estado. */
export function rotuloDeMarca(t: Textos, marca: MarcaIncidente): string {
  if (marca === "no_acreditado") return t.noAcreditado.etiqueta;
  if (marca === "descartado") return t.descartado.etiqueta;
  return t.estado[marca];
}

/**
 * El estado escrito junto al símbolo (listas, letrero y lector de pantalla del mapa): «Atribuido a
 * Rusia» en un atribuido; con la presencia no acreditada o descartada, el estado y la presencia,
 * para que el círculo morado o gris nunca vaya con un texto que solo diga «Confirmado».
 */
export function estadoEscrito(
  t: Textos,
  idioma: Idioma,
  i: ConPresencia & { atribucion: AtribucionResumen | null },
): string {
  const marca = marcaDe(i);
  if (marca === "no_acreditado") return `${t.estado[i.estado]} · ${t.presencia.no_acreditada}`;
  if (marca === "descartado") return `${t.estado[i.estado]} · ${t.presencia.descartada}`;
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
  /** Una nota que no cambia el valor: una corrección parcial o una investigación cerrada sin cambio. */
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
    const cierre = paso.cierre === true;
    const parcial = paso.parcial === true || cierre;
    const quien = paso.quien?.[idioma] ?? null;
    const fecha = instante(paso.fecha);
    const motivo = paso.motivo?.[idioma];
    return {
      valor: paso.valor,
      parcial,
      texto: cierre ? p.cierre(fecha, quien) : parcial ? p.parcial(fecha, quien) : p.paso(p.valor[paso.valor], fecha, quien),
      resto: motivo === undefined ? "" : parcial ? `: ${motivo}` : `, ${motivo}`,
      fuente: porFuente.get(paso.fuente_id),
    };
  });
}

/** El historial para una celda del CSV: «2025-09-23:confirmada|2026-06-25:no_acreditada» (una nota
 * lleva «:parcial» o «:cierre»). */
export function historialEnCelda(p: { presencia_historial?: PasoPresencia[] | undefined }): string | undefined {
  const pasos = historialDePresencia(p);
  if (pasos.length === 0) return undefined;
  return pasos.map((paso) => `${paso.fecha.valor.slice(0, 10)}:${paso.valor}${paso.parcial === true ? ":parcial" : paso.cierre === true ? ":cierre" : ""}`).join("|");
}

/** Un paso del «Historial de estados» de la ficha: un cambio de estado o uno de la presencia. */
export type PasoDelHistorial =
  | { clase: "estado"; paso: PasoHistorial; fecha: string }
  | {
      clase: "presencia";
      /** «no_acreditado» o «descartado»; null en una nota (corrección parcial o investigación
       * cerrada sin cambio: no cambia la presencia). */
      marca: "no_acreditado" | "descartado" | null;
      /** «No acreditado», «Descartado», «Corrección parcial» o «Investigación cerrada». */
      rotulo: string;
      /** Quién lo declara, sin artículo y con mayúscula: «Policía de Dinamarca». */
      quien: string | null;
      motivo: string | null;
      fuente: Fuente | undefined;
      paso: PasoPresencia;
      fecha: string;
    };

/** «la policía de Dinamarca» → «Policía de Dinamarca»; «the Copenhagen Police» → «Copenhagen Police». */
export function quienSinArticulo(quien: string): string {
  const sin = quien.replace(/^(?:la|el|los|las|the)\s+/i, "");
  return sin.charAt(0).toLocaleUpperCase() + sin.slice(1);
}

/**
 * El motivo de un paso del historial, que va solo en su línea: con la primera letra en mayúscula
 * (los motivos se escriben para seguir una frase: «tras la investigación: …», «al cerrar …»). Se
 * salta la comilla o el signo de apertura y no toca el resto: «á» → «Á», «“informe…”» → «“Informe…”».
 */
export function conMayuscula(motivo: string): string {
  return motivo.replace(/^([\s«"“‘'(¿¡]*)(\p{Ll})/u, (_, antes: string, letra: string) => antes + letra.toUpperCase());
}

/**
 * El «Historial de estados» entero, por orden de fecha: los cambios del estado del suceso y los
 * de la presencia de dron cuando una autoridad la rectificó (no acreditada, descartada o una
 * corrección parcial), con su marca, su fecha y su fuente. Los pasos de la presencia que solo
 * repiten lo que ya dice el estado (confirmada, no confirmada) no se añaden. A igual fecha, el
 * estado va antes: la rectificación siempre llega después de lo que rectifica.
 */
export function historialCompleto(
  t: Textos,
  idioma: Idioma,
  incidente: {
    estado: { historial: readonly PasoHistorial[] };
    presencia_historial?: PasoPresencia[] | undefined;
    fuentes: readonly Fuente[];
  },
): PasoDelHistorial[] {
  const porFuente = new Map(incidente.fuentes.map((f) => [f.id, f]));
  const estados: PasoDelHistorial[] = incidente.estado.historial.map((paso) => ({ clase: "estado", paso, fecha: paso.fecha.valor }));
  const presencia: PasoDelHistorial[] = historialDePresencia(incidente).flatMap((paso): PasoDelHistorial[] => {
    const cierre = paso.cierre === true;
    const parcial = paso.parcial === true || cierre;
    const marca = marcaDePresencia(paso.valor);
    if (!parcial && marca === null) return [];
    const quien = paso.quien?.[idioma];
    return [
      {
        clase: "presencia",
        marca: parcial ? null : marca,
        rotulo: cierre
          ? t.presenciaHistorial.investigacionCerrada
          : parcial
            ? t.presenciaHistorial.correccionParcial
            : rotuloDeMarca(t, marca ?? "no_acreditado"),
        quien: quien === undefined ? null : quienSinArticulo(quien),
        motivo: paso.motivo?.[idioma] === undefined ? null : conMayuscula(paso.motivo[idioma]),
        fuente: porFuente.get(paso.fuente_id),
        paso,
        fecha: paso.fecha.valor,
      },
    ];
  });
  // Orden estable: los del estado primero; luego, por fecha.
  return [...estados, ...presencia]
    .map((paso, i) => ({ paso, i }))
    .sort((a, b) => a.paso.fecha.localeCompare(b.paso.fecha) || a.i - b.i)
    .map(({ paso }) => paso);
}
