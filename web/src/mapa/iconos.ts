// Iconos de los incidentes en el mapa, dibujados en un lienzo, iguales que el componente
// Simbolo de la leyenda y las fichas: un círculo relleno del color del estado, el desmentido
// con borde gris discontinuo y sin relleno. El tipo no cambia la forma: va escrito en la
// ficha, la lista y los filtros. Un atribuido es solo una bandera roja con su mástil: el pie
// del mástil está en el centro del icono, que es el punto del incidente (el ancla del símbolo
// es el centro), así que las líneas de los episodios y la selección llegan al pie. La caja del
// icono, que es lo que se puede pulsar, es la misma para todos.

import type { Map as Mapa } from "maplibre-gl";

import type { Estado } from "../datos/tipos.ts";
import { ESTADOS } from "../datos/vocabulario.ts";
import {
  COLOR_BANDERA,
  COLOR_ESTADO,
  GROSOR_CONTORNO,
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
/** Radio del círculo de un incidente suelto: más pequeño que el de un grupo, que lleva número. */
export const RADIO_INCIDENTE = 6.5;

function dibujar(estado: Estado): ImageData | null {
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
  contexto.beginPath();
  contexto.arc(CENTRO, CENTRO, RADIO_INCIDENTE, 0, 2 * Math.PI);
  contexto.closePath();
  if (estado === "desmentido") {
    contexto.setLineDash([...TRAZO_DESMENTIDO]);
    contexto.strokeStyle = color;
  } else {
    contexto.fillStyle = color;
    contexto.fill();
    // Un borde del color del fondo para que se lea sobre las áreas y sobre otro círculo.
    contexto.strokeStyle = PALETA.fondo;
  }
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

/**
 * Etiqueta de un aviso de la detección en directo: una píldora con fondo de panel opaco, borde
 * del color de su estado y el código OACI dentro (lo escribe el mapa encima), con una punta
 * abajo que señala el aeropuerto. Nada que ver con el círculo relleno de un incidente. Va
 * levantada `hueco` píxeles sobre el punto, para que la punta nunca pise el número de un
 * grupo que esté en el mismo sitio.
 */
export const ETIQUETA_AVISO = { ancho: 52, alto: 20, punta: 7, hueco: 10 } as const;
export const ESTADOS_AVISO = ["posible_cierre", "cierre_confirmado", "operacion_reanudada"] as const;
export type EstadoAviso = (typeof ESTADOS_AVISO)[number];
export const COLOR_DE_AVISO: Record<EstadoAviso, string> = {
  posible_cierre: PALETA.notificado,
  cierre_confirmado: PALETA.confirmado,
  operacion_reanudada: PALETA.secundario,
};
const GROSOR_ETIQUETA = 1.5;

export function nombreIconoAviso(estado: string): string {
  return `aviso-${estado}`;
}

/** El contorno de la etiqueta (píldora y punta) en una caja de ancho × (alto + punta). */
function trazarEtiqueta(contexto: CanvasRenderingContext2D): void {
  const { ancho, alto, punta } = ETIQUETA_AVISO;
  const m = GROSOR_ETIQUETA / 2 + 0.25;
  const radio = alto / 2 - m;
  const centro = ancho / 2;
  const abajo = alto - m;
  contexto.moveTo(m + radio, m);
  contexto.lineTo(ancho - m - radio, m);
  contexto.arc(ancho - m - radio, m + radio, radio, -Math.PI / 2, Math.PI / 2);
  contexto.lineTo(centro + 4, abajo);
  contexto.lineTo(centro, alto + punta - m);
  contexto.lineTo(centro - 4, abajo);
  contexto.lineTo(m + radio, abajo);
  contexto.arc(m + radio, m + radio, radio, Math.PI / 2, (3 * Math.PI) / 2);
  contexto.closePath();
}

function dibujarAviso(estado: EstadoAviso): ImageData | null {
  const { ancho, alto, punta } = ETIQUETA_AVISO;
  const lienzo = document.createElement("canvas");
  lienzo.width = ancho * DENSIDAD;
  lienzo.height = (alto + punta) * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
  contexto.beginPath();
  trazarEtiqueta(contexto);
  contexto.fillStyle = PALETA.panelSolido;
  contexto.fill();
  contexto.lineJoin = "round";
  contexto.strokeStyle = COLOR_DE_AVISO[estado];
  contexto.lineWidth = GROSOR_ETIQUETA;
  contexto.stroke();
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/** Registra en el mapa un icono por estado y una etiqueta por estado de aviso. */
export function registrarIconos(mapa: Mapa, acento: string): void {
  if (!mapa.hasImage(ICONO_BANDERA_ELEGIDA)) {
    const elegida = dibujarBanderaElegida(acento);
    if (elegida !== null) mapa.addImage(ICONO_BANDERA_ELEGIDA, elegida, { pixelRatio: DENSIDAD });
  }
  for (const estado of ESTADOS) {
    const nombre = nombreIcono(estado);
    if (mapa.hasImage(nombre)) continue;
    const imagen = dibujar(estado);
    if (imagen !== null) mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD });
  }
  for (const estado of ESTADOS_AVISO) {
    const nombre = nombreIconoAviso(estado);
    if (mapa.hasImage(nombre)) continue;
    const imagen = dibujarAviso(estado);
    if (imagen !== null) mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD });
  }
}
