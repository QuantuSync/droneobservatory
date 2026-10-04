// Cifras del panel «Europa ahora», con los ficheros que ya tiene la web: el resumen de
// incidentes, el de la capa de guerra, los avisos en directo y la interferencia GPS del último
// día publicado.

import type { CifrasAhora, DronesAhora } from "../componentes/EuropaAhora.tsx";
import { MS_POR_HORA, diaDeInstante } from "../tiempo/dias.ts";
import { cierresEnCurso } from "./directo.ts";
import type { Directo } from "./directo.ts";
import { agregar, zonasAltas } from "./gnss.ts";
import type { FicheroGnss } from "./gnss.ts";
import type { Resumen, ResumenUcrania } from "./tipos.ts";

/** Días que cuentan como «últimos 7 días», contando el último día con datos. */
export const DIAS_SEMANA = 7;
/** Un parte con más horas que estas desde su fin ya no es «la última noche». */
export const HORAS_PARTE_RECIENTE = 36;

export interface FuentesAhora {
  resumen: Resumen | null;
  ucrania: ResumenUcrania | null;
  /** null si directo.json no ha llegado o no valida. */
  directo: Directo | null;
  /** Último día de interferencia publicado; null si no ha llegado. */
  gnssHoy: FicheroGnss | null;
  /** Este momento (ms); null antes de montar, cuando aún no se sabe la hora. */
  ahora: number | null;
}

/** Los drones del último parte publicado, con los días que cubre y si ya tiene más de 36 h. */
export function dronesDelUltimoParte(ucrania: ResumenUcrania, ahora: number | null): DronesAhora | null {
  const parte = ucrania.ultimoParte ?? null;
  if (parte === null) return null;
  return {
    lanzados: parte.lanzados,
    desde: diaDeInstante(parte.inicio),
    hasta: diaDeInstante(parte.fin),
    antiguo: ahora !== null && ahora - Date.parse(parte.fin) > HORAS_PARTE_RECIENTE * MS_POR_HORA,
  };
}

export function cifrasAhora({ resumen, ucrania, directo, gnssHoy, ahora }: FuentesAhora): CifrasAhora {
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
    drones: ucrania === null ? null : dronesDelUltimoParte(ucrania, ahora),
    focos,
    gnss:
      gnssHoy === null
        ? null
        : { zonas: zonasAltas(agregar([gnssHoy])), dia: diaDeInstante(gnssHoy.periodo) },
  };
}
