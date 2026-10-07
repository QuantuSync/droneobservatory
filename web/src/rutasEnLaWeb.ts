// Interruptor de las rutas de los drones sobre Ucrania en la web (configuracion/rutas_en_la_web.json,
// el mismo que lee el servidor para publicarlas o no). Apagado: sin subcapa «Rutas», sin pedir
// ningún fichero de rutas y sin describirlas en la metodología ni en la página de Ucrania. El
// código del dibujo se queda: encenderlas es cambiar el ajuste y desplegar. Los recorridos
// oficiales de las incursiones no dependen de él.

import ajuste from "../../configuracion/rutas_en_la_web.json" with { type: "json" };

import type { Textos } from "./i18n/index.ts";

export const RUTAS_EN_LA_WEB: boolean = ajuste.mostrar;

/** Las secciones de la metodología que se enseñan: con las rutas apagadas, en lugar de la de las
 * rutas va la del recorrido de las incursiones, que sigue a la vista. */
export function seccionesDeMetodologia(t: Textos): Textos["metodologia"]["secciones"] {
  return t.metodologia.secciones.filter((s) => s.id !== (RUTAS_EN_LA_WEB ? "recorridos" : "rutas"));
}
