import type { Estado, Tipo } from "../datos/tipos.ts";
import { COLOR_ESTADO, GROSOR_CONTORNO, OPACIDAD_RELLENO, TRAZO_DESMENTIDO } from "../paleta.ts";

const LADO = 16;
const CENTRO = LADO / 2;
/** Media anchura de cada forma, para que las tres pesen lo mismo a la vista. */
const RADIO_CIRCULO = 5.5;
const MEDIO_ROMBO = 6.5;
const MEDIO_CUADRADO = 5;

interface Props {
  tipo: Tipo;
  estado: Estado;
  className?: string;
}

/**
 * Símbolo de un incidente: la forma dice el tipo (círculo, interrupción aeroportuaria;
 * rombo, incursión; cuadrado, sobrevuelo) y el color, el estado. Es decorativo: el tipo y
 * el estado van siempre escritos al lado.
 */
export function Simbolo({ tipo, estado, className }: Props) {
  const color = COLOR_ESTADO[estado];
  const desmentido = estado === "desmentido";
  const trazo = {
    fill: desmentido ? "none" : color,
    fillOpacity: OPACIDAD_RELLENO,
    stroke: color,
    strokeWidth: GROSOR_CONTORNO,
    ...(desmentido ? { strokeDasharray: TRAZO_DESMENTIDO.join(" ") } : {}),
  };
  return (
    <svg
      viewBox={`0 0 ${LADO} ${LADO}`}
      width={LADO}
      height={LADO}
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {tipo === "interrupcion_aeroportuaria" && (
        <circle cx={CENTRO} cy={CENTRO} r={RADIO_CIRCULO} {...trazo} />
      )}
      {tipo === "incursion" && (
        <path
          d={`M${CENTRO} ${CENTRO - MEDIO_ROMBO}L${CENTRO + MEDIO_ROMBO} ${CENTRO}L${CENTRO} ${
            CENTRO + MEDIO_ROMBO
          }L${CENTRO - MEDIO_ROMBO} ${CENTRO}Z`}
          {...trazo}
        />
      )}
      {tipo === "sobrevuelo" && (
        <rect
          x={CENTRO - MEDIO_CUADRADO}
          y={CENTRO - MEDIO_CUADRADO}
          width={MEDIO_CUADRADO * 2}
          height={MEDIO_CUADRADO * 2}
          {...trazo}
        />
      )}
    </svg>
  );
}
