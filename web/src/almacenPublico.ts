// Almacén público de la web (Hetzner Object Storage): teselas del mapa de fondo, estado.json y las
// capas que publica el servidor. La web no lo pide directamente: lo pide a su propio dominio, en
// /almacen/<objeto>, donde lo sirve la función api/almacen.ts con la caché de Vercel delante (una
// avalancha de visitas no llega al almacén) y con la copia de reserva de Helsinki si el principal
// no responde. Si la propia función fallara, la web pide a la reserva directamente
// (urlDeLaReserva). Las direcciones salen de configuracion/almacen_publico.json, las mismas que
// usan la subida del servidor y la vigilancia; el origen de la reserva está también en la política
// de seguridad de contenido de vercel.json (tests/seguridad.test.ts lo comprueba).

import almacen from "../../configuracion/almacen_publico.json" with { type: "json" };

/** Ruta de la web por la que se sirve el almacén (vercel.json la lleva a api/almacen.ts). */
export const RUTA_ALMACEN: string = almacen.en_la_web;
export const ORIGEN_ALMACEN: string = new URL(almacen.publico).origin;
export const ORIGEN_RESERVA: string = new URL(almacen.reserva.publico).origin;

/**
 * Dirección de un objeto del almacén. En desarrollo, VITE_ALMACEN puede apuntar a una copia
 * servida por el servidor local (scripts/servidor-local.ts).
 */
export function urlDelAlmacen(objeto: string): string {
  const local = import.meta.env.VITE_ALMACEN as string | undefined;
  return `${local ?? RUTA_ALMACEN}/${objeto}`;
}

/** El mismo objeto en la copia pública de reserva, pedido directamente. */
export function urlDeLaReserva(objeto: string): string {
  return `${ORIGEN_RESERVA}/${objeto}`;
}

/**
 * Si `url` es un objeto del almacén servido por la web, su dirección en la reserva; si no, null.
 * Vale para la ruta sola (/almacen/…) y para la dirección entera del propio dominio.
 */
export function reservaDe(url: string): string | null {
  const prefijo = `${RUTA_ALMACEN}/`;
  let ruta = url;
  if (!url.startsWith("/")) {
    const origen = globalThis.location?.origin;
    if (origen === undefined || !url.startsWith(`${origen}/`)) return null;
    ruta = url.slice(origen.length);
  }
  return ruta.startsWith(prefijo) ? urlDeLaReserva(ruta.slice(prefijo.length)) : null;
}

export const OBJETO_TESELAS: string = almacen.objetos.teselas;
export const OBJETO_ESTADO: string = almacen.objetos.estado;
/** Avisos de la detección en directo de cierres de aeropuerto, renovados cada minuto. */
export const OBJETO_DIRECTO: string = almacen.objetos.directo;
/** Carpeta de los ficheros diarios y mensuales de interferencia GPS. */
export const PREFIJO_GNSS: string = almacen.objetos.gnss;
