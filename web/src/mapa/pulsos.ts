// Pulsos del mapa: el contorno de confirmados y atribuidos late despacio (los atribuidos,
// más), y los grupos que contienen alguno también. No los dibuja MapLibre: animar una capa
// obliga a repintar el mapa entero en cada fotograma y deja el hilo principal ocupado, de
// modo que la web tarda en responder al tacto. Cada pulso es un elemento sobre el mapa que
// anima solo su escala y su opacidad con CSS, algo que el navegador hace fuera del hilo
// principal (y que para con la pestaña en segundo plano o con movimiento reducido). Aquí
// solo se decide dónde va cada uno; se recoloca cuando el mapa se mueve.

import { radioDeGrupo } from "./estilo.ts";

/** Radio del contorno que late alrededor de un símbolo suelto. */
export const RADIO_PULSO = 11;
/** Separación del anillo de un grupo respecto a su círculo. */
export const SEPARACION_PULSO_GRUPO = 3;

export type EstadoDePulso = "confirmado" | "atribuido";

export interface Pulso {
  /** Identifica el pulso entre recolocaciones: el incidente, la pila o el grupo. */
  clave: string;
  x: number;
  y: number;
  radio: number;
  estado: EstadoDePulso;
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
 * Pulsos de los rasgos dibujados: los incidentes graves sueltos y los grupos (o pilas) con
 * algún confirmado o atribuido. Un rasgo puede llegar repetido (uno por tesela); sale una
 * vez.
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
    let pulso: Omit<Pulso, "x" | "y"> | null = null;
    if (esGrupo) {
      const atribuidos = numero(p.n_atribuidos);
      const confirmados = numero(p.n_confirmados);
      if (atribuidos + confirmados === 0) continue;
      const cuenta = "total" in p ? numero(p.total) : numero(p.n);
      pulso = {
        clave: "cluster_id" in p ? `grupo-${String(p.cluster_id)}` : `pila-${String(p.ids)}`,
        radio: radioDeGrupo(cuenta) + SEPARACION_PULSO_GRUPO,
        estado: atribuidos > 0 ? "atribuido" : "confirmado",
      };
    } else if (numero(p.grave) === 1) {
      pulso = {
        clave: String(p.id),
        radio: RADIO_PULSO,
        estado: numero(p.atribuido) === 1 ? "atribuido" : "confirmado",
      };
    }
    if (pulso === null || vistos.has(pulso.clave)) continue;
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
    if (sitio === undefined) {
      sitio = document.createElement("span");
      sitio.dataset.clave = pulso.clave;
      sitio.className = "pulso-sitio";
      sitio.append(document.createElement("span"));
      capa.append(sitio);
    }
    const anillo = sitio.firstElementChild;
    if (anillo instanceof HTMLElement) {
      const clase = `pulso pulso-${pulso.estado}`;
      if (anillo.className !== clase) anillo.className = clase;
      const lado = `${2 * pulso.radio}px`;
      anillo.style.width = lado;
      anillo.style.height = lado;
      anillo.style.margin = `${-pulso.radio}px 0 0 ${-pulso.radio}px`;
    }
    sitio.style.transform = `translate(${pulso.x.toFixed(1)}px, ${pulso.y.toFixed(1)}px)`;
  }
  for (const sobrante of previos.values()) sobrante.remove();
}
