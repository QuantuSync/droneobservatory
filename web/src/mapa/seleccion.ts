// Qué recibe un clic o un toque en el mapa cuando bajo el puntero hay varias cosas: primero las
// marcas puntuales (incidentes, impactos, focos, ciudades), después los arcos de los corredores
// de ataque y por último las áreas (regiones, celdas, países). Los arcos son finos: su zona
// sensible es mucho más ancha que la línea que se ve, y de varios arcos gana el más cercano; si
// quedan casi a la misma distancia, se elige de una lista.

/** Ancho total de la zona sensible de un arco, con ratón y con el dedo. */
export const ZONA_ARCO_RATON_PX = 16;
export const ZONA_ARCO_DEDO_PX = 28;
/** Dos arcos a menos de esta diferencia de distancia se tienen por empatados. */
export const EMPATE_ARCOS_PX = 1;

export function anchoZonaArco(dedo: boolean): number {
  return dedo ? ZONA_ARCO_DEDO_PX : ZONA_ARCO_RATON_PX;
}

export type Clase = "marca" | "arco" | "area";

export interface Candidato<T> {
  clase: Clase;
  /** Distancia en píxeles del puntero a la cosa (0 si está encima). */
  distancia: number;
  valor: T;
}

export type Eleccion<T> =
  { tipo: "uno"; valor: T } | { tipo: "varios"; valores: T[] } | null;

type Punto = readonly [number, number];

/** Distancia de un punto a un segmento, en las mismas unidades (píxeles de pantalla). */
export function distanciaASegmento(p: Punto, a: Punto, b: Punto): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const largo = dx * dx + dy * dy;
  const t =
    largo === 0
      ? 0
      : Math.max(
          0,
          Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo),
        );
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/** Distancia de un punto a una línea quebrada. */
export function distanciaALinea(p: Punto, linea: readonly Punto[]): number {
  let minima = Infinity;
  let anterior: Punto | undefined;
  for (const punto of linea) {
    minima = Math.min(
      minima,
      anterior === undefined
        ? Math.hypot(p[0] - punto[0], p[1] - punto[1])
        : distanciaASegmento(p, anterior, punto),
    );
    anterior = punto;
  }
  return minima;
}

/** Lo que recibe la pulsación: la marca más cercana; si no hay, el arco más cercano (o los
 * empatados, para elegir); si tampoco, la primera área. A igual distancia, el primero dado. */
export function elegir<T>(
  candidatos: readonly Candidato<T>[],
  empate = EMPATE_ARCOS_PX,
): Eleccion<T> {
  const mas = (clase: Clase) =>
    candidatos
      .map((c, orden) => ({ ...c, orden }))
      .filter((c) => c.clase === clase)
      .sort((a, b) => a.distancia - b.distancia || a.orden - b.orden);
  const marca = mas("marca")[0];
  if (marca !== undefined) return { tipo: "uno", valor: marca.valor };
  const arcos = mas("arco");
  const primero = arcos[0];
  if (primero !== undefined) {
    const empatados = arcos.filter(
      (a) => a.distancia - primero.distancia < empate,
    );
    return empatados.length > 1
      ? { tipo: "varios", valores: empatados.map((a) => a.valor) }
      : { tipo: "uno", valor: primero.valor };
  }
  const area = mas("area")[0];
  return area === undefined ? null : { tipo: "uno", valor: area.valor };
}
