// Iconos de los incidentes en el mapa, dibujados en un lienzo, iguales que el componente
// Simbolo de la leyenda y las fichas: un círculo relleno del color del estado, el desmentido
// con borde gris discontinuo y sin relleno. El tipo no cambia la forma: va escrito en la
// ficha, la lista y los filtros. Un atribuido es un círculo con aro rojo grueso y, dentro, la
// bandera del país al que se atribuye (o relleno rojo liso), con un punto fijo si es una
// persona, en su propia capa por encima de todo y centrado en el punto del incidente.

import type { Map as Mapa } from "maplibre-gl";

import type { Estado } from "../datos/tipos.ts";
import { ESTADOS } from "../datos/vocabulario.ts";
import { BANDERAS, VARIANTE_LISA, nombreIconoAtribuido, urlBandera } from "../banderas.ts";
import type { VarianteAtribuido } from "../banderas.ts";
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

/**
 * Un incidente con lugar aproximado: aro hueco del color de su estado, con un filo del color del
 * fondo por dentro y por fuera para leerse sobre cualquier cosa, y un punto en el centro.
 */
function dibujarAproximado(estado: Exclude<Estado, "atribuido">): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = LADO * DENSIDAD;
  lienzo.height = LADO * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
  const m = MARCA_APROXIMADA;
  const color = COLOR_ESTADO[estado];
  contexto.beginPath();
  contexto.arc(CENTRO, CENTRO, m.radio, 0, 2 * Math.PI);
  contexto.strokeStyle = PALETA.fondo;
  contexto.lineWidth = m.grosor + 2;
  contexto.stroke();
  contexto.strokeStyle = color;
  contexto.lineWidth = m.grosor;
  contexto.stroke();
  contexto.beginPath();
  contexto.arc(CENTRO, CENTRO, m.punto, 0, 2 * Math.PI);
  contexto.fillStyle = color;
  contexto.fill();
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/** Lado del icono de un atribuido (el marcador con su filo exterior) y densidad a la que se
 *  dibuja: más que los círculos, para que la bandera se lea en pantallas densas. */
export const LADO_ATRIBUIDO = 26;
const DENSIDAD_ATRIBUIDO = 3;
/** El marcador del incidente abierto: el mismo, algo más grande. */
export const ESCALA_ATRIBUIDO_ELEGIDO = 1.2;

function circuloLleno(contexto: CanvasRenderingContext2D, centro: number, radio: number, color: string): void {
  contexto.beginPath();
  contexto.arc(centro, centro, radio, 0, 2 * Math.PI);
  contexto.closePath();
  contexto.fillStyle = color;
  contexto.fill();
}

/**
 * Un atribuido en un lienzo de `lado` píxeles: filo exterior del color del fondo, aro rojo,
 * filo oscuro, la bandera recortada en círculo y centrada (o relleno rojo liso) y, si es una
 * persona, el punto oscuro con su aro rojo fino. El mismo dibujo que el SVG de Simbolo.tsx.
 */
export function pintarAtribuido(
  contexto: CanvasRenderingContext2D,
  lado: number,
  bandera: CanvasImageSource | null,
  persona: boolean,
): void {
  const c = lado / 2;
  const m = MARCA_ATRIBUIDO;
  circuloLleno(contexto, c, m.radio + m.halo, COLOR_FILO_ATRIBUIDO);
  circuloLleno(contexto, c, m.radio, COLOR_ARO_ATRIBUIDO);
  circuloLleno(contexto, c, m.radio - m.aro, COLOR_FILO_ATRIBUIDO);
  if (bandera === null) {
    circuloLleno(contexto, c, RADIO_BANDERA, COLOR_ARO_ATRIBUIDO);
  } else {
    contexto.save();
    contexto.beginPath();
    contexto.arc(c, c, RADIO_BANDERA, 0, 2 * Math.PI);
    contexto.closePath();
    contexto.clip();
    contexto.drawImage(bandera, c - RADIO_BANDERA, c - RADIO_BANDERA, 2 * RADIO_BANDERA, 2 * RADIO_BANDERA);
    contexto.restore();
  }
  if (persona) {
    circuloLleno(contexto, c, m.punto + m.aroPunto, COLOR_ARO_ATRIBUIDO);
    circuloLleno(contexto, c, m.punto, COLOR_FILO_ATRIBUIDO);
  }
}

function dibujarAtribuido(bandera: CanvasImageSource | null, persona: boolean): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = LADO_ATRIBUIDO * DENSIDAD_ATRIBUIDO;
  lienzo.height = LADO_ATRIBUIDO * DENSIDAD_ATRIBUIDO;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD_ATRIBUIDO, DENSIDAD_ATRIBUIDO);
  pintarAtribuido(contexto, LADO_ATRIBUIDO, bandera, persona);
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

function registrarAtribuido(mapa: Mapa, variante: VarianteAtribuido, bandera: CanvasImageSource | null): boolean {
  const nombre = nombreIconoAtribuido(variante);
  if (mapa.hasImage(nombre)) return false;
  const imagen = dibujarAtribuido(bandera, variante.persona);
  if (imagen === null) return false;
  mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD_ATRIBUIDO });
  return true;
}

/** Banderas ya pedidas: cada una se carga una vez por página. */
const cargadas = new Map<string, Promise<HTMLImageElement | null>>();
/** Países cuya bandera no ha cargado ni al reintentar: su marcador va liso desde el principio. */
const fallidas = new Set<string>();
const INTENTOS_BANDERA = 3;
const ESPERA_REINTENTO_MS = 600;

async function descargarBandera(pais: string): Promise<HTMLImageElement | null> {
  for (let intento = 1; intento <= INTENTOS_BANDERA; intento += 1) {
    const imagen = new Image();
    imagen.decoding = "async";
    imagen.src = urlBandera(pais);
    try {
      await imagen.decode();
      return imagen;
    } catch {
      if (intento < INTENTOS_BANDERA) {
        await new Promise((listo) => setTimeout(listo, ESPERA_REINTENTO_MS * intento));
      }
    }
  }
  fallidas.add(pais);
  return null;
}

function cargarBandera(pais: string): Promise<HTMLImageElement | null> {
  let promesa = cargadas.get(pais);
  if (promesa === undefined) {
    promesa = descargarBandera(pais);
    cargadas.set(pais, promesa);
  }
  return promesa;
}

function conBandera(paises: Iterable<string>): string[] {
  return [...new Set(paises)].filter((pais) => (BANDERAS as readonly string[]).includes(pais));
}

/** Empieza a cargar las banderas de esos países, antes de que el mapa las necesite. */
export function precargarBanderas(paises: Iterable<string>): void {
  for (const pais of conBandera(paises)) void cargarBandera(pais);
}

/** Si el marcador de esos países ya está en el mapa (o su bandera no ha podido cargar). */
function banderasListas(mapa: Mapa, paises: Iterable<string>): boolean {
  return conBandera(paises).every(
    (pais) => fallidas.has(pais) || mapa.hasImage(nombreIconoAtribuido({ bandera: pais, persona: false })),
  );
}

/** Registra en el mapa los marcadores con bandera de esos países (con y sin punto). Una
 *  bandera que no carga ni al reintentar deja el marcador liso. */
async function registrarBanderas(mapa: Mapa, paises: Iterable<string>): Promise<void> {
  const pedidas = conBandera(paises);
  const imagenes = await Promise.all(pedidas.map(async (pais) => [pais, await cargarBandera(pais)] as const));
  for (const [pais, imagen] of imagenes) {
    if (imagen === null) continue;
    for (const persona of [false, true]) registrarAtribuido(mapa, { bandera: pais, persona }, imagen);
  }
}

/**
 * Hace `tarea` (poner en el mapa los atribuidos de esos países) solo con sus banderas ya en el
 * mapa: al momento si ya están; si no, en cuanto lleguen. Así un atribuido nunca se dibuja liso
 * para pasar después a llevar su bandera. Devuelve cómo cancelarlo.
 */
export function trasBanderas(mapa: Mapa, paises: readonly string[], tarea: () => void): () => void {
  if (banderasListas(mapa, paises)) {
    tarea();
    return () => {};
  }
  let vigente = true;
  void registrarBanderas(mapa, paises).then(() => {
    if (vigente) tarea();
  });
  return () => {
    vigente = false;
  };
}

/** Punta de flecha de una ruta: un triángulo violeta claro que apunta al norte (el mapa la gira
 *  con el rumbo del final del recorrido), con un filo oscuro para leerse sobre cualquier fondo. */
export const ICONO_FLECHA_RUTA = "ruta-flecha";
const LADO_FLECHA = 14;

function dibujarFlechaRuta(): ImageData | null {
  const lienzo = document.createElement("canvas");
  lienzo.width = LADO_FLECHA * DENSIDAD;
  lienzo.height = LADO_FLECHA * DENSIDAD;
  const contexto = lienzo.getContext("2d");
  if (contexto === null) return null;
  contexto.scale(DENSIDAD, DENSIDAD);
  contexto.beginPath();
  contexto.moveTo(LADO_FLECHA / 2, 1);
  contexto.lineTo(LADO_FLECHA - 2, LADO_FLECHA - 2);
  contexto.lineTo(LADO_FLECHA / 2, LADO_FLECHA - 5);
  contexto.lineTo(2, LADO_FLECHA - 2);
  contexto.closePath();
  contexto.fillStyle = PALETA.guerraClaro;
  contexto.fill();
  contexto.lineJoin = "round";
  contexto.lineWidth = 1;
  contexto.strokeStyle = PALETA.fondo;
  contexto.stroke();
  return contexto.getImageData(0, 0, lienzo.width, lienzo.height);
}

/** Registra la punta de flecha de las rutas (aparte de los iconos de los incidentes). */
export function registrarFlechaRuta(mapa: Mapa): void {
  if (mapa.hasImage(ICONO_FLECHA_RUTA)) return;
  const flecha = dibujarFlechaRuta();
  if (flecha !== null) mapa.addImage(ICONO_FLECHA_RUTA, flecha, { pixelRatio: DENSIDAD });
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

/** Registra en el mapa un icono por estado, los atribuidos sin bandera y una etiqueta por
 *  estado de aviso. */
export function registrarIconos(mapa: Mapa): void {
  // Los atribuidos sin bandera (con y sin punto); los de bandera, al cargarla.
  registrarAtribuido(mapa, VARIANTE_LISA, null);
  registrarAtribuido(mapa, { bandera: null, persona: true }, null);
  if (!mapa.hasImage(ICONO_OBSTACULO)) mapa.addImage(ICONO_OBSTACULO, dibujarObstaculo());
  for (const estado of ESTADOS) {
    if (estado === "atribuido") continue;
    const nombre = nombreIcono(estado);
    if (!mapa.hasImage(nombre)) {
      const imagen = dibujar(estado);
      if (imagen !== null) mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD });
    }
    const aproximado = nombreIcono(estado, true);
    if (!mapa.hasImage(aproximado)) {
      const imagen = dibujarAproximado(estado);
      if (imagen !== null) mapa.addImage(aproximado, imagen, { pixelRatio: DENSIDAD });
    }
  }
  for (const estado of ESTADOS_AVISO) {
    const nombre = nombreIconoAviso(estado);
    if (mapa.hasImage(nombre)) continue;
    const imagen = dibujarAviso(estado);
    if (imagen !== null) mapa.addImage(nombre, imagen, { pixelRatio: DENSIDAD });
  }
}
