// Pulsos del mapa: solo laten los incidentes nuevos desde la última visita del visitante (los
// que cuenta el aviso «N novedades desde tu última visita»), y los grupos o pilas que
// contienen alguno. Ningún estado late por sí mismo. No los dibuja MapLibre: animar una capa
// obliga a repintar el mapa entero en cada fotograma y deja el hilo principal ocupado, de
// modo que la web tarda en responder al tacto. Cada pulso es un elemento sobre el mapa que
// anima solo su opacidad con CSS, algo que el navegador hace fuera del hilo
// principal (y que para con la pestaña en segundo plano o con movimiento reducido). Aquí
// solo se decide dónde va cada uno; se recoloca cuando el mapa se mueve.

import { BANDERA, trazadoBandera } from "../paleta.ts";
import { radioDeGrupo } from "./estilo.ts";

/** Radio del contorno que late alrededor de un símbolo suelto. */
export const RADIO_PULSO = 11;
/** Separación del anillo de un grupo respecto a su círculo. */
export const SEPARACION_PULSO_GRUPO = 3;

export interface Pulso {
  /** Identifica el pulso entre recolocaciones: el incidente, la pila o el grupo. */
  clave: string;
  x: number;
  y: number;
  radio: number;
  /** Un atribuido suelto late con la forma de su bandera, no con un anillo. */
  forma: "anillo" | "bandera";
}

/** Lo que devuelve MapLibre de cada símbolo o grupo dibujado, en lo que aquí importa. */
export interface RasgoDibujado {
  properties: Record<string, unknown>;
  geometry: { type: string; coordinates?: unknown };
}

function numero(valor: unknown): number {
  const n = Number(valor);
  return Number.isFinite(n) ? n : 0;
}

function coordenadas(rasgo: RasgoDibujado): [number, number] | null {
  const c = rasgo.geometry.coordinates;
  if (rasgo.geometry.type !== "Point" || !Array.isArray(c)) return null;
  const [lon, lat] = c as unknown[];
  return typeof lon === "number" && typeof lat === "number" ? [lon, lat] : null;
}

/**
 * Pulsos de los rasgos dibujados: los incidentes nuevos sueltos y los grupos (o pilas) que
 * contienen alguno nuevo (`novedad` en un incidente o una pila, `n_novedades` en un grupo).
 * Un rasgo puede llegar repetido (uno por tesela); sale una vez.
 */
export function pulsosDe(
  rasgos: readonly RasgoDibujado[],
  proyectar: (lon: number, lat: number) => { x: number; y: number },
): Pulso[] {
  const vistos = new Map<string, Pulso>();
  for (const rasgo of rasgos) {
    const p = rasgo.properties;
    const lugar = coordenadas(rasgo);
    if (lugar === null) continue;
    const esGrupo = "point_count" in p || numero(p.n) > 1;
    const nuevo = "point_count" in p ? numero(p.n_novedades) > 0 : numero(p.novedad) === 1;
    if (!nuevo) continue;
    let pulso: Omit<Pulso, "x" | "y">;
    if (esGrupo) {
      const cuenta = "total" in p ? numero(p.total) : numero(p.n);
      pulso = {
        clave: "cluster_id" in p ? `grupo-${String(p.cluster_id)}` : `pila-${String(p.ids)}`,
        radio: radioDeGrupo(cuenta) + SEPARACION_PULSO_GRUPO,
        forma: "anillo",
      };
    } else if (numero(p.atribuido) === 1) {
      pulso = { clave: String(p.id), radio: BANDERA.mastil, forma: "bandera" };
    } else {
      pulso = { clave: String(p.id), radio: RADIO_PULSO, forma: "anillo" };
    }
    if (vistos.has(pulso.clave)) continue;
    const { x, y } = proyectar(lugar[0], lugar[1]);
    vistos.set(pulso.clave, { ...pulso, x, y });
  }
  return [...vistos.values()];
}

/**
 * Pone en `capa` un elemento por pulso, reutilizando los que ya estaban: un envoltorio que
 * se coloca con transform y, dentro, el anillo que late con una animación de CSS.
 */
export function colocarPulsos(capa: HTMLElement, pulsos: readonly Pulso[]): void {
  const previos = new Map<string, HTMLElement>();
  for (const hijo of Array.from(capa.children)) {
    if (hijo instanceof HTMLElement && hijo.dataset.clave !== undefined) {
      previos.set(hijo.dataset.clave, hijo);
    }
  }
  for (const pulso of pulsos) {
    let sitio = previos.get(pulso.clave);
    previos.delete(pulso.clave);
    if (sitio !== undefined && sitio.dataset.forma !== pulso.forma) {
      sitio.remove();
      sitio = undefined;
    }
    if (sitio === undefined) {
      sitio = document.createElement("span");
      sitio.dataset.clave = pulso.clave;
      sitio.dataset.forma = pulso.forma;
      sitio.className = "pulso-sitio";
      sitio.append(pulso.forma === "bandera" ? banderaQueLate() : document.createElement("span"));
      capa.append(sitio);
    }
    const marca = sitio.firstElementChild;
    if (marca instanceof HTMLElement && pulso.forma === "anillo") {
      if (marca.className !== "pulso") marca.className = "pulso";
      const lado = `${2 * pulso.radio}px`;
      marca.style.width = lado;
      marca.style.height = lado;
      marca.style.margin = `${-pulso.radio}px 0 0 ${-pulso.radio}px`;
    }
    sitio.style.transform = `translate(${pulso.x.toFixed(1)}px, ${pulso.y.toFixed(1)}px)`;
  }
  for (const sobrante of previos.values()) sobrante.remove();
}

const SVG = "http://www.w3.org/2000/svg";

/** La silueta de la bandera, del tamaño del icono y con el pie en el punto, que late. */
function banderaQueLate(): SVGSVGElement {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "pulso-bandera");
  svg.setAttribute("viewBox", `0 0 ${BANDERA.ancho} ${BANDERA.alto}`);
  svg.setAttribute("width", String(BANDERA.ancho));
  svg.setAttribute("height", String(BANDERA.alto));
  // El pie del mástil, en el punto del sitio.
  svg.style.left = `${-BANDERA.pie[0]}px`;
  svg.style.top = `${-BANDERA.pie[1]}px`;
  const trazo = document.createElementNS(SVG, "path");
  trazo.setAttribute("d", trazadoBandera(BANDERA));
  svg.append(trazo);
  return svg;
}
