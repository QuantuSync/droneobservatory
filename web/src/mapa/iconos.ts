// Iconos de los incidentes en el mapa, dibujados en un lienzo: la forma dice el tipo y el
// color, el estado, igual que el componente Simbolo de la leyenda y las fichas. Un atribuido
// es solo una bandera roja con su mástil, sin la forma del tipo: el pie del mástil está en el
// centro del icono, que es el punto del incidente (el ancla del símbolo es el centro), así que
// las líneas de los episodios y la selección llegan al pie. La caja del icono, que es lo que
// se puede pulsar, es la misma que la de los demás.

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
  bandera,
} from "../paleta.ts";
import type { FormaBandera } from "../paleta.ts";
import { nombreIcono } from "./geometria.ts";

/** Lado del icono en píxeles de pantalla (y de lo que se puede pulsar) y densidad a la que se
 *  dibuja. */
export const LADO = 28;
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
  if (estado === "atribuido") {
    pintarBandera(contexto, BANDERA, COLOR_BANDERA);
    return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
  }
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
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/** La bandera en el icono del mapa: pie en el centro de la caja, 13 px de mástil. */
export const BANDERA: FormaBandera = bandera(LADO, [CENTRO, CENTRO], 13);
/** Nombre del icono de la bandera elegida (la selección del incidente abierto). */
export const ICONO_BANDERA_ELEGIDA = "bandera-elegida";

function pintarBandera(
  contexto: CanvasRenderingContext2D,
  forma: FormaBandera,
  color: string,
  borde: string = PALETA.fondo,
  grosorBorde = 3,
): void {
  const trazar = () => {
    contexto.beginPath();
    contexto.moveTo(forma.pie[0], forma.pie[1]);
    contexto.lineTo(forma.tope[0], forma.tope[1]);
    const [a, b, c] = forma.banderin as [
      readonly [number, number],
      readonly [number, number],
      readonly [number, number],
    ];
    contexto.moveTo(a[0], a[1]);
    contexto.lineTo(b[0], b[1]);
    contexto.lineTo(c[0], c[1]);
    contexto.closePath();
  };
  contexto.setLineDash([]);
  contexto.lineJoin = "round";
  contexto.lineCap = "round";
  trazar();
  contexto.strokeStyle = borde;
  contexto.lineWidth = grosorBorde;
  contexto.stroke();
  trazar();
  contexto.fillStyle = color;
  contexto.fill();
  contexto.strokeStyle = color;
  contexto.lineWidth = 1.6;
  contexto.stroke();
}

/** La bandera del incidente abierto: la misma, con un contorno del acento en lugar de un aro. */
function dibujarBanderaElegida(acento: string): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = LADO * DENSIDAD;
  lienzo.height = LADO * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
  pintarBandera(contexto, BANDERA, COLOR_BANDERA, acento, 4.5);
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/** Registra en el mapa un icono por cada combinación de tipo y estado. */
export function registrarIconos(mapa: Mapa, acento: string): void {
  if (!mapa.hasImage(ICONO_BANDERA_ELEGIDA)) {
    const elegida = dibujarBanderaElegida(acento);
    if (elegida !== null) mapa.addImage(ICONO_BANDERA_ELEGIDA, elegida, { pixelRatio: DENSIDAD });
  }
  for (const tipo of TIPOS) {
    for (const estado of ESTADOS) {
      const nombre = nombreIcono(tipo, estado);
      if (mapa.hasImage(nombre)) continue;
      const imagen = dibujar(tipo, estado);
      if (imagen !== null) mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD });
    }
  }
}
