// Iconos de los incidentes en el mapa, dibujados en un lienzo, iguales que el componente
// Simbolo de la leyenda y las fichas: un círculo relleno del color del estado, el desmentido
// con borde gris discontinuo y sin relleno. El tipo no cambia la forma: va escrito en la
// ficha, la lista y los filtros. Un atribuido es solo una bandera roja con su mástil y un
// contorno claro, en su propia capa por encima de todo: el pie del mástil es el punto del
// incidente (el mapa ancla el icono por ese pie), así que las líneas de los episodios y la
// selección llegan al pie.

import type { Map as Mapa } from "maplibre-gl";

import type { Estado } from "../datos/tipos.ts";
import { ESTADOS } from "../datos/vocabulario.ts";
import {
  BANDERA,
  COLOR_BANDERA,
  COLOR_ESTADO,
  COLOR_MASTIL,
  CONTORNO_BANDERA,
  GROSOR_CONTORNO,
  GROSOR_CONTORNO_BANDERA,
  GROSOR_MASTIL,
  GROSOR_PANO,
  PALETA,
  TRAZO_DESMENTIDO,
  trazadoMastil,
  trazadoPano,
} from "../paleta.ts";
import { nombreIcono } from "./geometria.ts";

/** Lado del icono en píxeles de pantalla (y de lo que se puede pulsar) y densidad a la que se
 *  dibuja. */
export const LADO = 28;
const DENSIDAD = 2;
const CENTRO = LADO / 2;
/** Radio del círculo de un incidente suelto: más pequeño que el de un grupo, que lleva número. */
export const RADIO_INCIDENTE = 6.5;

function dibujar(estado: Exclude<Estado, "atribuido">): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = LADO * DENSIDAD;
  lienzo.height = LADO * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
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

/** Nombre del icono de la bandera de un atribuido. */
export const ICONO_BANDERA = "bandera";
/** La bandera del incidente abierto: la misma, algo más grande, sin ningún borde. */
export const ESCALA_BANDERA_ELEGIDA = 1.2;
/**
 * Dónde va la caja de la bandera respecto al punto: el mapa la ancla por su esquina de abajo a
 * la izquierda y la desplaza para que el pie del mástil caiga en el punto exacto.
 */
export const DESPLAZAMIENTO_BANDERA: [number, number] = [-BANDERA.pie[0], BANDERA.alto - BANDERA.pie[1]];

/**
 * La bandera: primero el filo oscuro (el trazo de todo, un poco más ancho), encima el paño
 * relleno de rojo y el mástil en un rojo algo más oscuro. El filo asoma 1 px por fuera.
 */
function dibujarBandera(): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = BANDERA.ancho * DENSIDAD;
  lienzo.height = BANDERA.alto * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
  const mastil = new Path2D(trazadoMastil(BANDERA));
  const pano = new Path2D(trazadoPano(BANDERA));
  contexto.lineJoin = "round";
  contexto.lineCap = "round";
  contexto.strokeStyle = CONTORNO_BANDERA;
  contexto.fillStyle = CONTORNO_BANDERA;
  contexto.lineWidth = GROSOR_MASTIL + 2 * GROSOR_CONTORNO_BANDERA;
  contexto.stroke(mastil);
  contexto.lineWidth = GROSOR_PANO + 2 * GROSOR_CONTORNO_BANDERA;
  contexto.fill(pano);
  contexto.stroke(pano);
  contexto.fillStyle = COLOR_BANDERA;
  contexto.strokeStyle = COLOR_BANDERA;
  contexto.fill(pano);
  contexto.lineWidth = GROSOR_PANO;
  contexto.stroke(pano);
  contexto.strokeStyle = COLOR_MASTIL;
  contexto.lineWidth = GROSOR_MASTIL;
  contexto.stroke(mastil);
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/**
 * Obstáculo invisible del tamaño de cada marca: los nombres del mapa ceden ante él (o se ven
 * enteros o no se ven). El mapa lo escala al diámetro de cada círculo.
 */
export const ICONO_OBSTACULO = "obstaculo";
export const LADO_OBSTACULO = 16;

function dibujarObstaculo(): { width: number; height: number; data: Uint8Array } {
  return {
    width: LADO_OBSTACULO,
    height: LADO_OBSTACULO,
    data: new Uint8Array(LADO_OBSTACULO * LADO_OBSTACULO * 4),
  };
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
export function registrarIconos(mapa: Mapa): void {
  if (!mapa.hasImage(ICONO_BANDERA)) {
    const imagen = dibujarBandera();
    if (imagen !== null) mapa.addImage(ICONO_BANDERA, imagen, { pixelRatio: DENSIDAD });
  }
  if (!mapa.hasImage(ICONO_OBSTACULO)) mapa.addImage(ICONO_OBSTACULO, dibujarObstaculo());
  for (const estado of ESTADOS) {
    if (estado === "atribuido") continue;
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
