// Cómo se dice el cierre en la ficha. «desconocido» quiere decir que ninguna fuente habla
// de cierre: no se rotula, salvo en las interrupciones aeroportuarias, donde el cierre es
// lo que se espera saber.

import type { PropiedadesIncidente, Rango, Tipo } from "./tipos.ts";

export type Cierre =
  | { clase: "con_duracion"; minutos: Rango }
  | { clase: "sin_duracion" }
  | { clase: "sin_cierre" }
  | { clase: "desconocido" }
  | null;

export function cierre(tipo: Tipo, consecuencias: PropiedadesIncidente["consecuencias"]): Cierre {
  const dato = consecuencias?.cierre;
  if (dato?.valor === "si") {
    const minutos = dato.minutos;
    return minutos === undefined || minutos === "desconocido"
      ? { clase: "sin_duracion" }
      : { clase: "con_duracion", minutos };
  }
  if (dato?.valor === "no") return { clase: "sin_cierre" };
  return tipo === "interrupcion_aeroportuaria" ? { clase: "desconocido" } : null;
}
