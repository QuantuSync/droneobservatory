// Escala horizontal de la línea de tiempo y sus marcas de eje.

import { MS_POR_DIA, acotar, fechaDeDia } from "./dias.ts";
import type { Periodo } from "./dias.ts";

/** Número de días del dominio, con los dos extremos incluidos. */
export function diasDeDominio(dominio: Periodo): number {
  return dominio.hasta - dominio.desde + 1;
}

/** Posición horizontal del inicio de un día. El final del dominio cae en `ancho`. */
export function xDeDia(dia: number, ancho: number, dominio: Periodo): number {
  return ((dia - dominio.desde) / diasDeDominio(dominio)) * ancho;
}

/** Día que cae bajo una posición horizontal, acotado al dominio. */
export function diaDeX(x: number, ancho: number, dominio: Periodo): number {
  if (ancho <= 0) return dominio.desde;
  const dia = dominio.desde + Math.floor((x / ancho) * diasDeDominio(dominio));
  return acotar(dia, dominio.desde, dominio.hasta);
}

export interface Marca {
  dia: number;
  etiqueta: string;
}

/** Separación mínima entre dos marcas del eje para que sus etiquetas no se pisen. */
const SEPARACION_MINIMA_PX = 72;
/** Pasos posibles entre marcas, en meses. */
const PASOS_EN_MESES: readonly number[] = [1, 2, 3, 6, 12, 24, 60];
const MESES_POR_ANIO = 12;
const DIAS_POR_MES_MEDIO = 30.44;

/** Marcas del eje en inicios de mes, con el paso más fino que deja sitio a las etiquetas. */
export function marcasDeEje(dominio: Periodo, ancho: number): Marca[] {
  if (ancho <= 0) return [];
  const pxPorMes = (ancho / diasDeDominio(dominio)) * DIAS_POR_MES_MEDIO;
  const paso =
    PASOS_EN_MESES.find((meses) => meses * pxPorMes >= SEPARACION_MINIMA_PX) ??
    (PASOS_EN_MESES[PASOS_EN_MESES.length - 1] as number);
  const inicio = fechaDeDia(dominio.desde);
  const marcas: Marca[] = [];
  let anio = inicio.getUTCFullYear();
  let mes = Math.ceil(inicio.getUTCMonth() / paso) * paso;
  for (;;) {
    const dia = Date.UTC(anio, mes, 1) / MS_POR_DIA;
    if (dia > dominio.hasta) break;
    if (dia >= dominio.desde) {
      const fecha = fechaDeDia(dia);
      const numeroDeMes = String(fecha.getUTCMonth() + 1).padStart(2, "0");
      marcas.push({
        dia,
        etiqueta:
          paso >= MESES_POR_ANIO
            ? String(fecha.getUTCFullYear())
            : `${numeroDeMes}/${fecha.getUTCFullYear()}`,
      });
    }
    mes += paso;
    anio += Math.floor(mes / MESES_POR_ANIO);
    mes %= MESES_POR_ANIO;
  }
  return marcas;
}
