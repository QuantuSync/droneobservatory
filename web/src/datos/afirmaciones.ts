// Quién dice qué: los valores de cada campo según cada fuente pública, cuando el fichero
// publicado los trae (afirmaciones_publicas). Sin ellos, la ficha usa el valor del campo.

import { FIABILIDADES_DEL_RANGO } from "./vocabulario.ts";
import type { AfirmacionPublica, IncidenteDetalle, Rango, RangoODesconocido } from "./tipos.ts";

export function afirmacionesDe(
  incidente: IncidenteDetalle,
  campos: readonly string[],
): AfirmacionPublica[] {
  return (incidente.afirmaciones_publicas ?? [])
    .filter((afirmacion) => campos.includes(afirmacion.campo))
    .sort(
      (a, b) =>
        a.fiabilidad.localeCompare(b.fiabilidad) ||
        a.fecha.valor.localeCompare(b.fecha.valor) ||
        a.fuente_id.localeCompare(b.fuente_id),
    );
}

function esRango(valor: unknown): valor is Rango {
  if (typeof valor !== "object" || valor === null) return false;
  const { min, max } = valor as Record<string, unknown>;
  return typeof min === "number" && typeof max === "number";
}

/**
 * Rango que cubren las fuentes de fiabilidad A a C: del menor mínimo al mayor máximo. Si
 * ninguna de ellas da una cifra, se queda el valor publicado del campo.
 */
export function rangoDeFuentes(
  afirmaciones: readonly AfirmacionPublica[],
  publicado: RangoODesconocido | undefined,
): RangoODesconocido | undefined {
  const cifras = afirmaciones
    .filter((afirmacion) => FIABILIDADES_DEL_RANGO.includes(afirmacion.fiabilidad))
    .map((afirmacion) => afirmacion.valor)
    .filter(esRango);
  if (cifras.length === 0) return publicado;
  return {
    min: Math.min(...cifras.map((cifra) => cifra.min)),
    max: Math.max(...cifras.map((cifra) => cifra.max)),
  };
}

export type ValorLegible =
  | { clase: "rango"; rango: Rango }
  | { clase: "instante"; valor: string; precision: string }
  | { clase: "desconocido" }
  | { clase: "texto"; texto: string };

/** Forma de mostrar un valor de afirmación; nunca se interpreta como HTML. */
export function valorLegible(valor: unknown): ValorLegible {
  if (valor === "desconocido" || valor === null || valor === undefined) {
    return { clase: "desconocido" };
  }
  if (esRango(valor)) return { clase: "rango", rango: valor };
  if (typeof valor === "object" && !Array.isArray(valor)) {
    const { valor: instante, precision } = valor as Record<string, unknown>;
    if (typeof instante === "string" && typeof precision === "string") {
      return { clase: "instante", valor: instante, precision };
    }
  }
  if (Array.isArray(valor)) return { clase: "texto", texto: valor.map(String).join(" · ") };
  if (typeof valor === "object") return { clase: "texto", texto: JSON.stringify(valor) };
  return { clase: "texto", texto: String(valor) };
}
