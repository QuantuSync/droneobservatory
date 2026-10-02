// Almacén público de la web (Hetzner Object Storage): teselas del mapa de fondo y estado.json
// de la recogida. La dirección no se escribe aquí: sale de configuracion/almacen_publico.json,
// la misma que usan la subida del servidor y la vigilancia. Su origen está también en la
// política de seguridad de contenido de vercel.json (tests/seguridad.test.ts lo comprueba).

import almacen from "../../configuracion/almacen_publico.json";

export const ORIGEN_ALMACEN: string = new URL(almacen.publico).origin;

/** Dirección pública de un objeto del almacén. */
export function urlDelAlmacen(objeto: string): string {
  return `${ORIGEN_ALMACEN}/${objeto}`;
}

export const OBJETO_TESELAS: string = almacen.objetos.teselas;
export const OBJETO_ESTADO: string = almacen.objetos.estado;
