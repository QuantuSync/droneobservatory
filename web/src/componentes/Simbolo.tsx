import type { Estado } from "../datos/tipos.ts";
import {
  COLOR_BANDERA,
  COLOR_ESTADO,
  GROSOR_CONTORNO,
  PALETA,
  TRAZO_DESMENTIDO,
  bandera,
  trazadoBandera,
} from "../paleta.ts";

const LADO = 16;
const CENTRO = LADO / 2;
const RADIO = 5.5;

interface Props {
  estado: Estado;
  className?: string;
}

/**
 * Símbolo de un incidente, igual que en el mapa: un círculo relleno del color del estado
 * (naranja notificado, rojo confirmado), un círculo gris de borde discontinuo el desmentido y
 * solo una bandera roja con su mástil el atribuido. Es decorativo: el estado (y el tipo) van
 * siempre escritos al lado.
 */
export function Simbolo({ estado, className }: Props) {
  if (estado === "atribuido") return <IconoBandera className={className} lado={LADO} />;
  const color = COLOR_ESTADO[estado];
  const desmentido = estado === "desmentido";
  return (
    <svg
      viewBox={`0 0 ${LADO} ${LADO}`}
      width={LADO}
      height={LADO}
      aria-hidden="true"
      focusable="false"
      className={className}
      data-circulo={estado}
    >
      <circle
        cx={CENTRO}
        cy={CENTRO}
        r={RADIO}
        fill={desmentido ? "none" : color}
        stroke={desmentido ? color : PALETA.fondo}
        strokeWidth={GROSOR_CONTORNO}
        {...(desmentido ? { strokeDasharray: TRAZO_DESMENTIDO.join(" ") } : {})}
      />
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
