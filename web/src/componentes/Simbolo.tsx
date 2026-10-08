import { useId } from "react";

import { urlBandera, varianteDe, VARIANTE_LISA } from "../banderas.ts";
import type { VarianteAtribuido } from "../banderas.ts";
import type { AtribucionResumen, Estado } from "../datos/tipos.ts";
import {
  COLOR_ARO_ATRIBUIDO,
  COLOR_ESTADO,
  COLOR_FILO_ATRIBUIDO,
  GROSOR_CONTORNO,
  MARCA_APROXIMADA,
  MARCA_ATRIBUIDO,
  PALETA,
  RADIO_BANDERA,
  TRAZO_DESMENTIDO,
} from "../paleta.ts";

const LADO = 16;
const CENTRO = LADO / 2;
const RADIO = 5.5;
/** Lado del marcador de un atribuido en las listas, la ficha, la leyenda y los filtros. */
export const LADO_ATRIBUIDO_TEXTO = 20;

interface Props {
  estado: Estado;
  /** En un atribuido, a quién se atribuye: decide su bandera y su punto. */
  atribucion?: AtribucionResumen | null;
  /** Texto para el lector de pantalla; sin él, el símbolo es decorativo. */
  etiqueta?: string;
  className?: string;
  /** Lugar aproximado: el aro hueco con un punto, como en el mapa. */
  aproximado?: boolean;
}

/**
 * Símbolo de un incidente, igual que en el mapa: un círculo relleno del color del estado
 * (naranja notificado, rojo confirmado), un círculo gris de borde discontinuo el desmentido y
 * el marcador de los atribuidos (aro rojo con la bandera dentro). Es decorativo salvo que
 * lleve `etiqueta`: el estado (y el tipo) van siempre escritos al lado.
 */
export function Simbolo({ estado, atribucion = null, etiqueta, className, aproximado = false }: Props) {
  if (estado === "atribuido") {
    return <MarcaAtribuido variante={varianteDe(atribucion)} etiqueta={etiqueta} className={className} />;
  }
  const color = COLOR_ESTADO[estado];
  if (aproximado) {
    const m = MARCA_APROXIMADA;
    return (
      <svg
        viewBox={`0 0 ${LADO} ${LADO}`}
        width={LADO}
        height={LADO}
        aria-hidden="true"
        focusable="false"
        className={className}
        data-circulo={estado}
        data-aproximado=""
      >
        <circle cx={CENTRO} cy={CENTRO} r={m.radio} fill="none" stroke={color} strokeWidth={m.grosor} />
        <circle cx={CENTRO} cy={CENTRO} r={m.punto} fill={color} />
      </svg>
    );
  }
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
 * El marcador de un atribuido, el mismo dibujo que el del mapa (iconos.ts): filo exterior del
 * color del fondo, aro rojo grueso, filo oscuro, la bandera recortada en círculo (o relleno
 * rojo liso) y, si es una persona, el punto oscuro con su aro rojo. A `lado` píxeles.
 */
export function MarcaAtribuido({
  variante = VARIANTE_LISA,
  lado = LADO_ATRIBUIDO_TEXTO,
  etiqueta,
  className,
}: {
  variante?: VarianteAtribuido;
  lado?: number;
  etiqueta?: string | undefined;
  className?: string | undefined;
}) {
  const recorte = `bandera-${useId().replace(/[^\w-]/g, "")}`;
  const m = MARCA_ATRIBUIDO;
  const total = m.radio + m.halo;
  const c = total;
  const accesible = etiqueta === undefined ? { "aria-hidden": true as const } : { role: "img", "aria-label": etiqueta };
  return (
    <svg
      viewBox={`0 0 ${2 * total} ${2 * total}`}
      width={lado}
      height={lado}
      focusable="false"
      // Nunca encoge junto a un texto largo: la bandera tiene que verse.
      className={className === undefined ? "shrink-0" : `shrink-0 ${className}`}
      data-atribuido={variante.bandera ?? "liso"}
      data-persona={variante.persona ? "" : undefined}
      {...accesible}
    >
      <circle cx={c} cy={c} r={total} fill={COLOR_FILO_ATRIBUIDO} />
      <circle cx={c} cy={c} r={m.radio} fill={COLOR_ARO_ATRIBUIDO} />
      <circle cx={c} cy={c} r={m.radio - m.aro} fill={COLOR_FILO_ATRIBUIDO} />
      {variante.bandera === null ? (
        <circle cx={c} cy={c} r={RADIO_BANDERA} fill={COLOR_ARO_ATRIBUIDO} />
      ) : (
        <>
          <clipPath id={recorte}>
            <circle cx={c} cy={c} r={RADIO_BANDERA} />
          </clipPath>
          <image
            href={urlBandera(variante.bandera)}
            x={c - RADIO_BANDERA}
            y={c - RADIO_BANDERA}
            width={2 * RADIO_BANDERA}
            height={2 * RADIO_BANDERA}
            preserveAspectRatio="xMidYMid slice"
            clipPath={`url(#${recorte})`}
          />
        </>
      )}
      {variante.persona && (
        <>
          <circle cx={c} cy={c} r={m.punto + m.aroPunto} fill={COLOR_ARO_ATRIBUIDO} />
          <circle cx={c} cy={c} r={m.punto} fill={COLOR_FILO_ATRIBUIDO} data-punto="" />
        </>
      )}
    </svg>
  );
}
