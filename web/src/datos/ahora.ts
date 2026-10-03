// Cifras del panel «Europa ahora», con los ficheros que ya tiene la web: el resumen de
// incidentes, el de la capa de guerra, los avisos en directo y la interferencia GPS del último
// día publicado.

import type { CifrasAhora } from "../componentes/EuropaAhora.tsx";
import { diaDeInstante } from "../tiempo/dias.ts";
import { cierresEnCurso } from "./directo.ts";
import type { Directo } from "./directo.ts";
import type { FicheroGnss } from "./gnss.ts";
import type { Resumen, ResumenUcrania } from "./tipos.ts";
import { lanzamientosPorNoche } from "./ucrania.ts";

/** Días que cuentan como «últimos 7 días», contando el último día con datos. */
export const DIAS_SEMANA = 7;

export interface FuentesAhora {
  resumen: Resumen | null;
  ucrania: ResumenUcrania | null;
  /** null si directo.json no ha llegado o no valida. */
  directo: Directo | null;
  /** Último día de interferencia publicado; null si no ha llegado. */
  gnssHoy: FicheroGnss | null;
}

/** La noche más reciente con lanzamientos contra Ucrania y su cifra. */
export function ultimaNoche(ucrania: ResumenUcrania): { lanzados: number; dia: number } | null {
  let ultima: { lanzados: number; dia: number } | null = null;
  for (const [dia, lanzados] of lanzamientosPorNoche(ucrania)) {
    if (ultima === null || dia > ultima.dia) ultima = { lanzados, dia };
  }
  return ultima;
}

export function cifrasAhora({ resumen, ucrania, directo, gnssHoy }: FuentesAhora): CifrasAhora {
  const hoy = resumen === null ? null : diaDeInstante(resumen.actualizado);
  const desde = hoy === null ? null : hoy - (DIAS_SEMANA - 1);
  const enSemana = (dia: number) => desde !== null && hoy !== null && dia >= desde && dia <= hoy;
  let focos: number | null = null;
  if (resumen !== null) {
    focos = resumen.incidentes.filter((i) => i.foco && enSemana(i.dia)).length;
    if (ucrania !== null) {
      focos += ucrania.impactos.filter((f) => f[5] === 1 && enSemana(f[1])).length;
      focos += ucrania.focos.filter((f) => enSemana(f.dia)).length;
    }
  }
  return {
    cierres: directo === null ? null : cierresEnCurso(directo).length,
    incidentes: resumen === null ? null : resumen.incidentes.filter((i) => enSemana(i.dia)).length,
    drones: ucrania === null ? null : ultimaNoche(ucrania),
    focos,
    gnss:
      gnssHoy === null
        ? null
        : {
            nivel: gnssHoy.resumen.nivel,
            altas: gnssHoy.resumen.celdas_alta,
            dia: diaDeInstante(gnssHoy.periodo),
          },
  };
}
