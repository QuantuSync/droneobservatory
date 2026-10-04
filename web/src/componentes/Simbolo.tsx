import type { Estado } from "../datos/tipos.ts";
import {
  BANDERA,
  COLOR_BANDERA,
  COLOR_ESTADO,
  CONTORNO_BANDERA,
  GROSOR_CONTORNO,
  GROSOR_CONTORNO_BANDERA,
  GROSOR_MASTIL,
  PALETA,
  TRAZO_DESMENTIDO,
  trazadoBandera,
  trazadoMastil,
  trazadoPano,
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

/**
 * Bandera de los atribuidos, sola: la misma forma que en el mapa (mástil y paño rojos con un
 * contorno claro), a `lado` píxeles de alto. Nada más: ni círculo ni forma ni punto en el pie.
 */
export function IconoBandera({
  className,
  lado = 16,
}: {
  className?: string | undefined;
  lado?: number;
}) {
  // Recortada a lo que ocupa la bandera, para que a poco tamaño no sobre caja vacía.
  const margen = GROSOR_CONTORNO_BANDERA + GROSOR_MASTIL;
  const x = BANDERA.pie[0] - margen;
  const y = BANDERA.pie[1] - BANDERA.mastil - BANDERA.pano.onda - margen;
  const ancho = BANDERA.pano.ancho + 2 * margen;
  const alto = BANDERA.mastil + BANDERA.pano.onda + 2 * margen;
  return (
    <svg
      viewBox={`${x} ${y} ${ancho} ${alto}`}
      width={Math.round((lado * ancho) / alto)}
      height={lado}
      aria-hidden="true"
      focusable="false"
      className={className}
      data-bandera=""
    >
      <g strokeLinejoin="round" strokeLinecap="round">
        <path
          d={trazadoBandera(BANDERA)}
          fill={CONTORNO_BANDERA}
          stroke={CONTORNO_BANDERA}
          strokeWidth={GROSOR_MASTIL + 2 * GROSOR_CONTORNO_BANDERA}
        />
        <path d={trazadoPano(BANDERA)} fill={COLOR_BANDERA} stroke={COLOR_BANDERA} strokeWidth={1} />
        <path d={trazadoMastil(BANDERA)} fill="none" stroke={COLOR_BANDERA} strokeWidth={GROSOR_MASTIL} />
      </g>
    </svg>
  );
}
