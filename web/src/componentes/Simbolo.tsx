import type { Estado, Tipo } from "../datos/tipos.ts";
import {
  COLOR_BANDERA,
  COLOR_ESTADO,
  GROSOR_CONTORNO,
  OPACIDAD_RELLENO,
  PALETA,
  TRAZO_DESMENTIDO,
} from "../paleta.ts";

/** Con sitio arriba a la izquierda para la bandera de los atribuidos. */
const LADO = 20;
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
 * confirmado, rojo con bandera atribuido, contorno gris discontinuo desmentido. Es
 * decorativo: el tipo y el estado van siempre escritos al lado.
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
      {estado === "atribuido" && <Bandera />}
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

/** Bandera de los atribuidos: mástil y banderín rojos con un borde del color del fondo. */
export function Bandera() {
  const banderin = "M2.5 1L7.6 3L2.5 5Z";
  return (
    <g data-bandera="" strokeLinejoin="round">
      <path d={`M2 1V8${banderin}`} fill="none" stroke={PALETA.fondo} strokeWidth={2.2} />
      <path d="M2 1V8" stroke={COLOR_BANDERA} strokeWidth={1.1} />
      <path d={banderin} fill={COLOR_BANDERA} stroke={COLOR_BANDERA} strokeWidth={0.8} />
    </g>
  );
}

/** La bandera sola, para acompañar el rótulo de los atribuidos (contadores, leyendas). */
export function IconoBandera({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 9 9"
      width={9}
      height={9}
      aria-hidden="true"
      focusable="false"
      className={className}
      data-icono-bandera=""
    >
      <Bandera />
    </svg>
  );
}
