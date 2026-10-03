// Iconos de los incidentes en el mapa, dibujados en un lienzo: la forma dice el tipo y el
// color, el estado, igual que el componente Simbolo de la leyenda y las fichas. Los
// atribuidos llevan además una bandera roja pequeña arriba a la izquierda, fuera de la forma
// (arriba a la derecha va la marca del foco térmico).

import type { Map as Mapa } from "maplibre-gl";

import type { Estado, Tipo } from "../datos/tipos.ts";
import { ESTADOS, TIPOS } from "../datos/vocabulario.ts";
import {
  COLOR_BANDERA,
  COLOR_ESTADO,
  GROSOR_CONTORNO,
  OPACIDAD_RELLENO,
  PALETA,
  TRAZO_DESMENTIDO,
} from "../paleta.ts";
import { nombreIcono } from "./geometria.ts";

/** Lado del icono en píxeles de pantalla y densidad a la que se dibuja (con sitio para la
 *  bandera de los atribuidos alrededor de la forma, que no cambia de tamaño). */
const LADO = 28;
const DENSIDAD = 2;
const CENTRO = LADO / 2;
const RADIO_CIRCULO = 7;
const MEDIO_ROMBO = 8.5;
const MEDIO_CUADRADO = 6.5;
/** En el mapa el relleno va algo más opaco que en la leyenda para leerse sobre las áreas. */
const OPACIDAD_RELLENO_MAPA = OPACIDAD_RELLENO + 0.2;

function trazar(contexto: CanvasRenderingContext2D, tipo: Tipo): void {
  contexto.beginPath();
  if (tipo === "interrupcion_aeroportuaria") {
    contexto.arc(CENTRO, CENTRO, RADIO_CIRCULO, 0, 2 * Math.PI);
  } else if (tipo === "incursion") {
    contexto.moveTo(CENTRO, CENTRO - MEDIO_ROMBO);
    contexto.lineTo(CENTRO + MEDIO_ROMBO, CENTRO);
    contexto.lineTo(CENTRO, CENTRO + MEDIO_ROMBO);
    contexto.lineTo(CENTRO - MEDIO_ROMBO, CENTRO);
  } else {
    contexto.rect(
      CENTRO - MEDIO_CUADRADO,
      CENTRO - MEDIO_CUADRADO,
      MEDIO_CUADRADO * 2,
      MEDIO_CUADRADO * 2,
    );
  }
  contexto.closePath();
}

function dibujar(tipo: Tipo, estado: Estado): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = LADO * DENSIDAD;
  lienzo.height = LADO * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
  const color = COLOR_ESTADO[estado];
  trazar(contexto, tipo);
  if (estado === "desmentido") {
    contexto.setLineDash([...TRAZO_DESMENTIDO]);
  } else {
    contexto.globalAlpha = OPACIDAD_RELLENO_MAPA;
    contexto.fillStyle = color;
    contexto.fill();
    contexto.globalAlpha = 1;
  }
  contexto.strokeStyle = color;
  contexto.lineWidth = GROSOR_CONTORNO;
  contexto.stroke();
  if (estado === "atribuido") bandera(contexto);
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/** Mástil y banderín, con un borde del color del fondo que los separa del mapa y la forma. */
export const BANDERA = {
  mastil: [3, 1.5, 3, 11] as const,
  banderin: [
    [3.6, 1.5],
    [10.5, 4.2],
    [3.6, 6.9],
  ] as const,
};

function bandera(contexto: CanvasRenderingContext2D): void {
  const [x0, y0, x1, y1] = BANDERA.mastil;
  const trazar = () => {
    contexto.beginPath();
    contexto.moveTo(x0, y0);
    contexto.lineTo(x1, y1);
    const [a, b, c] = BANDERA.banderin;
    contexto.moveTo(a[0], a[1]);
    contexto.lineTo(b[0], b[1]);
    contexto.lineTo(c[0], c[1]);
    contexto.closePath();
  };
  contexto.setLineDash([]);
  contexto.lineJoin = "round";
  trazar();
  contexto.strokeStyle = PALETA.fondo;
  contexto.lineWidth = 2.6;
  contexto.stroke();
  trazar();
  contexto.fillStyle = COLOR_BANDERA;
  contexto.fill();
  contexto.strokeStyle = COLOR_BANDERA;
  contexto.lineWidth = 1.2;
  contexto.stroke();
}

/** Registra en el mapa un icono por cada combinación de tipo y estado. */
export function registrarIconos(mapa: Mapa): void {
  for (const tipo of TIPOS) {
    for (const estado of ESTADOS) {
      const nombre = nombreIcono(tipo, estado);
      if (mapa.hasImage(nombre)) continue;
      const imagen = dibujar(tipo, estado);
      if (imagen !== null) mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD });
    }
  }
}
