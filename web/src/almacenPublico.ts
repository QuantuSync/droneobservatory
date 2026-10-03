// Almacén público de la web (Hetzner Object Storage): teselas del mapa de fondo y estado.json
// de la recogida. La dirección no se escribe aquí: sale de configuracion/almacen_publico.json,
// la misma que usan la subida del servidor y la vigilancia. Su origen está también en la
// política de seguridad de contenido de vercel.json (tests/seguridad.test.ts lo comprueba).

import almacen from "../../configuracion/almacen_publico.json" with { type: "json" };

export const ORIGEN_ALMACEN: string = new URL(almacen.publico).origin;

/**
 * Dirección pública de un objeto del almacén. En desarrollo, VITE_ALMACEN puede apuntar a una
 * copia servida por el servidor local (scripts/servidor-local.ts).
 */
export function urlDelAlmacen(objeto: string): string {
  const local = import.meta.env.VITE_ALMACEN as string | undefined;
  return `${local ?? ORIGEN_ALMACEN}/${objeto}`;
}

export const OBJETO_TESELAS: string = almacen.objetos.teselas;
export const OBJETO_ESTADO: string = almacen.objetos.estado;
/** Avisos de la detección en directo de cierres de aeropuerto, renovados cada minuto. */
export const OBJETO_DIRECTO: string = almacen.objetos.directo;
/** Carpeta de los ficheros diarios y mensuales de interferencia GPS. */
export const PREFIJO_GNSS: string = almacen.objetos.gnss;
