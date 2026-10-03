import type { Estado, Tipo } from "../datos/tipos.ts";
import {
  COLOR_BANDERA,
  COLOR_ESTADO,
  GROSOR_CONTORNO,
  OPACIDAD_RELLENO,
  PALETA,
  TRAZO_DESMENTIDO,
  bandera,
  trazadoBandera,
} from "../paleta.ts";

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
 * rombo, incursión; cuadrado, sobrevuelo) y el color, el estado: naranja notificado, rojo
 * confirmado, contorno gris discontinuo desmentido. El atribuido es solo una bandera roja con
 * su mástil, sin la forma del tipo. Es decorativo: el tipo y el estado van siempre escritos al
 * lado.
 */
export function Simbolo({ tipo, estado, className }: Props) {
  if (estado === "atribuido") return <IconoBandera className={className} lado={LADO} />;
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

/** La bandera de la leyenda y las fichas: en una caja de 16, con el pie abajo a la izquierda. */
export const BANDERA_SIMBOLO = bandera(16, [4, 15], 13);

/**
 * Bandera de los atribuidos, sola: mástil y banderín rojos, con un borde fino del color del
 * fondo para que se lea sobre cualquier cosa. Nada más: ni círculo ni forma ni punto en el pie.
 */
export function IconoBandera({
  className,
  lado = 16,
}: {
  className?: string | undefined;
  lado?: number;
}) {
  const trazado = trazadoBandera(BANDERA_SIMBOLO);
  return (
    <svg
      viewBox={`0 0 ${BANDERA_SIMBOLO.lado} ${BANDERA_SIMBOLO.lado}`}
      width={lado}
      height={lado}
      aria-hidden="true"
      focusable="false"
      className={className}
      data-bandera=""
    >
      <g strokeLinejoin="round" strokeLinecap="round">
        <path d={trazado} fill="none" stroke={PALETA.fondo} strokeWidth={3} />
        <path d={trazado} fill={COLOR_BANDERA} stroke={COLOR_BANDERA} strokeWidth={1.4} />
      </g>
    </svg>
  );
}
