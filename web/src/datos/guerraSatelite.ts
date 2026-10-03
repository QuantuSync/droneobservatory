// Guerra por satélite en la capa de guerra: pérdidas de luz nocturna tras los ataques contra la
// red eléctrica, corredores de ataque desde las zonas de lanzamiento, focos de calor de las
// últimas 24 horas e imágenes de antes y después de las instalaciones alcanzadas. Funciones
// puras: las usan el build (resúmenes) y la web (agregados del periodo).

import { diaDeInstante, enPeriodo } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";
import type {
  LuzResumen,
  PublicacionUcrania,
  ResumenUcrania,
  Sentido,
  ZonaResumen,
} from "./tipos.ts";

// ---- Pérdidas de luz -----------------------------------------------------------------

/** Las pérdidas de luz de todos los ataques, por orden de día. */
export function lucesDeAtaques(ucrania: PublicacionUcrania): LuzResumen[] {
  const luces: LuzResumen[] = [];
  for (const ataque of ucrania.ataques) {
    for (const p of ataque.perdida_luz ?? []) {
      luces.push({
        ataque: ataque.id,
        dia: diaDeInstante(ataque.periodo.inicio.valor),
        zona: p.zona,
        region: p.region,
        ciudad:
          p.ciudad === undefined
            ? null
            : { nombre: p.ciudad.nombre, lon: p.ciudad.punto.lon, lat: p.ciudad.punto.lat },
        perdida: p.perdida_pct,
        noche: p.noche,
        noches: p.noches,
        referencia: {
          desde: p.referencia.desde,
          hasta: p.referencia.hasta,
          noches: p.referencia.noches,
        },
      });
    }
  }
  return luces.sort((a, b) => a.dia - b.dia || a.ataque.localeCompare(b.ataque));
}

/** Pérdidas de luz de los ataques del periodo; de una región (y sus ciudades), si se da. */
export function lucesDelPeriodo(
  ucrania: ResumenUcrania,
  periodo: Periodo,
  region?: string,
): LuzResumen[] {
  return ucrania.luces.filter(
    (l) => enPeriodo(l.dia, periodo) && (region === undefined || l.region === region),
  );
}

/** Por región, la mayor pérdida del periodo (en %). */
export function perdidaPorRegion(luces: readonly LuzResumen[]): Map<string, number> {
  const resultado = new Map<string, number>();
  for (const l of luces) {
    if (l.zona !== "region") continue;
    resultado.set(l.region, Math.max(resultado.get(l.region) ?? 0, l.perdida));
  }
  return resultado;
}

export interface CiudadSinLuz {
  nombre: string;
  region: string;
  lon: number;
  lat: number;
  /** La mayor pérdida del periodo, en %. */
  perdida: number;
  /** Las pérdidas de la ciudad en el periodo, de la más reciente a la más antigua. */
  lista: LuzResumen[];
}

/** Ciudades con pérdida de luz en el periodo, una por ciudad. */
export function ciudadesSinLuz(luces: readonly LuzResumen[]): CiudadSinLuz[] {
  const porNombre = new Map<string, CiudadSinLuz>();
  for (const l of luces) {
    if (l.ciudad === null) continue;
    const clave = `${l.region}|${l.ciudad.nombre}`;
    const previa = porNombre.get(clave);
    if (previa === undefined) {
      porNombre.set(clave, { ...l.ciudad, region: l.region, perdida: l.perdida, lista: [l] });
    } else {
      previa.perdida = Math.max(previa.perdida, l.perdida);
      previa.lista.push(l);
    }
  }
  const ciudades = [...porNombre.values()];
  for (const c of ciudades) c.lista.sort((a, b) => b.dia - a.dia || b.noche.localeCompare(a.noche));
  return ciudades.sort((a, b) => b.perdida - a.perdida || a.nombre.localeCompare(b.nombre));
}

/** Opacidad del oscurecimiento según la pérdida: más pérdida, más oscuro. */
export function opacidadDePerdida(perdida: number): number {
  const fraccion = Math.min(1, Math.max(0, perdida / 100));
  return Math.round((0.18 + 0.6 * fraccion) * 100) / 100;
}

// ---- Zonas de lanzamiento -------------------------------------------------------------

/** Una zona de configuracion/zonas_lanzamiento.json (solo lo que hace falta aquí). */
export interface ZonaConfig {
  id: string;
  nombre: string;
  raices: string[];
  excluir?: string[];
  punto: { lat: number; lon: number } | null;
}

/** Las zonas que nombra un texto de un parte, como proceso/deduccion/catalogo.Zona.nombra. */
export function nombra(zona: ZonaConfig, texto: string): boolean {
  const minusculas = texto.toLowerCase();
  return (
    zona.raices.some((r) => minusculas.includes(r)) &&
    !(zona.excluir ?? []).some((e) => minusculas.includes(e))
  );
}

/**
 * Zonas de lanzamiento con punto y, para cada nombre de los partes, cuál representa: la
 * primera de la configuración que lo nombra y tiene punto (Orel: el aeródromo; Donetsk: el
 * aeropuerto, porque la zona de la ciudad no lo tiene).
 */
export function casarZonas(configuracion: readonly ZonaConfig[]): {
  zonas: ZonaResumen[];
  casar: (nombre: string) => number | null;
} {
  const zonas: ZonaResumen[] = [];
  const indice = new Map<string, number>();
  const casar = (nombre: string): number | null => {
    const zona = configuracion.find((z) => z.punto !== null && nombra(z, nombre));
    if (zona === undefined || zona.punto === null) return null;
    let i = indice.get(zona.id);
    if (i === undefined) {
      i = zonas.length;
      zonas.push({
        id: zona.id,
        nombre: zona.nombre,
        lon: Math.round(zona.punto.lon * 1e4) / 1e4,
        lat: Math.round(zona.punto.lat * 1e4) / 1e4,
      });
      indice.set(zona.id, i);
    }
    return i;
  };
  return { zonas, casar };
}

/** Zonas de lanzamiento (índices) declaradas por cada ataque que nombra alguna con punto. */
export function origenesDeAtaques(
  ucrania: PublicacionUcrania,
  casar: (nombre: string) => number | null,
): Record<string, number[]> {
  const origenes: Record<string, number[]> = {};
  for (const ataque of ucrania.ataques) {
    const indices = new Set<number>();
    for (const nombre of ataque.zonas_lanzamiento ?? []) {
      const i = casar(nombre);
      if (i !== null) indices.add(i);
    }
    if (indices.size > 0) origenes[ataque.id] = [...indices].sort((a, b) => a - b);
  }
  return origenes;
}

type Anillo = [number, number][];

/** El punto de los anillos más cercano a `punto` (en grados, corregida la longitud). */
export function puntoMasCercano(anillos: readonly Anillo[], punto: [number, number]): [number, number] {
  const coseno = Math.cos((punto[1] * Math.PI) / 180);
  let mejor: [number, number] = punto;
  let distancia = Number.POSITIVE_INFINITY;
  for (const anillo of anillos) {
    for (let i = 0; i < anillo.length - 1; i += 1) {
      const [x0, y0] = anillo[i] as [number, number];
      const [x1, y1] = anillo[i + 1] as [number, number];
      const dx = (x1 - x0) * coseno;
      const dy = y1 - y0;
      const largo = dx * dx + dy * dy;
      const t =
        largo === 0
          ? 0
          : Math.min(1, Math.max(0, (((punto[0] - x0) * coseno) * dx + (punto[1] - y0) * dy) / largo));
      const x = x0 + (x1 - x0) * t;
      const y = y0 + (y1 - y0) * t;
      const d = ((x - punto[0]) * coseno) ** 2 + (y - punto[1]) ** 2;
      if (d < distancia) {
        distancia = d;
        mejor = [Math.round(x * 1e4) / 1e4, Math.round(y * 1e4) / 1e4];
      }
    }
  }
  return mejor;
}

// ---- Corredores -----------------------------------------------------------------------

/** Un arco del periodo: de una zona de lanzamiento (o de Ucrania) a una región. */
export interface Corredor {
  /** Clave estable: «<zona o UA>|<región>». */
  clave: string;
  sentido: Sentido;
  /** Nombre de la zona de lanzamiento; null en los ataques contra Rusia (sale de Ucrania). */
  origen: string | null;
  desde: [number, number];
  region: string;
  hasta: [number, number];
  /**
   * RU→UA: drones lanzados en los ataques del periodo que salieron (entre otras zonas) de esa
   * zona y alcanzaron la región. UA→RU: drones que el parte ruso dice derribados en la región.
   */
  drones: number;
  ataques: number;
}

/** Arcos del periodo en los dos sentidos. */
export function corredoresDelPeriodo(ucrania: ResumenUcrania, periodo: Periodo): Corredor[] {
  const porClave = new Map<string, Corredor>();
  const sumar = (
    clave: string,
    base: Omit<Corredor, "drones" | "ataques">,
    drones: number,
  ): void => {
    const previo = porClave.get(clave);
    if (previo === undefined) porClave.set(clave, { ...base, drones, ataques: 1 });
    else {
      previo.drones += drones;
      previo.ataques += 1;
    }
  };
  for (const fila of ucrania.ataques) {
    if (!enPeriodo(fila[1], periodo)) continue;
    const suma = fila[7] === 1;
    if (fila[2] === 0) {
      const zonas = ucrania.origenes[fila[0]];
      if (zonas === undefined) continue;
      // Los tramos cuyas cifras ya están en otro parte no se vuelven a sumar.
      const drones = suma && fila[4] > 0 ? fila[4] : 0;
      for (const indiceZona of zonas) {
        const zona = ucrania.zonas[indiceZona];
        if (zona === undefined) continue;
        for (const [indiceRegion] of fila[8]) {
          const region = ucrania.regiones[indiceRegion];
          const hasta = region === undefined ? undefined : ucrania.centros[region];
          if (region === undefined || hasta === undefined) continue;
          sumar(
            `${zona.id}|${region}`,
            { clave: `${zona.id}|${region}`, sentido: "RU_UA", origen: zona.nombre, desde: [zona.lon, zona.lat], region, hasta },
            drones,
          );
        }
      }
    } else {
      for (const [indiceRegion, , derribadosMax] of fila[8]) {
        const region = ucrania.regiones[indiceRegion];
        if (region === undefined || !region.startsWith("RU-")) continue;
        const hasta = ucrania.centros[region];
        const desde = ucrania.fronteraUcrania[region];
        if (hasta === undefined || desde === undefined) continue;
        const drones = suma && derribadosMax > 0 ? derribadosMax : 0;
        sumar(`UA|${region}`, { clave: `UA|${region}`, sentido: "UA_RU", origen: null, desde, region, hasta }, drones);
      }
    }
  }
  // Sin cifra de drones no hay grosor que dar: esos arcos no se dibujan.
  return [...porClave.values()]
    .filter((c) => c.drones > 0)
    .sort((a, b) => b.drones - a.drones || a.clave.localeCompare(b.clave));
}

export const ANCHO_MINIMO_CORREDOR = 0.4;
export const ANCHO_MAXIMO_CORREDOR = 3;

/** Grosor del trazo: crece con la raíz de los drones, del mínimo al máximo del periodo. */
export function anchoDeCorredor(drones: number, maximo: number): number {
  if (maximo <= 0 || drones <= 0) return ANCHO_MINIMO_CORREDOR;
  const fraccion = Math.sqrt(Math.min(1, drones / maximo));
  const ancho = ANCHO_MINIMO_CORREDOR + (ANCHO_MAXIMO_CORREDOR - ANCHO_MINIMO_CORREDOR) * fraccion;
  return Math.round(ancho * 100) / 100;
}

/** Arco suave (curva cuadrática) entre dos puntos, curvado a la izquierda del sentido. */
export function arco(desde: [number, number], hasta: [number, number], pasos = 24): [number, number][] {
  const [x0, y0] = desde;
  const [x1, y1] = hasta;
  const coseno = Math.cos((((y0 + y1) / 2) * Math.PI) / 180);
  const dx = (x1 - x0) * coseno;
  const dy = y1 - y0;
  // Punto de control: el medio, desplazado en perpendicular un 18 % de la distancia.
  const cx = (x0 + x1) / 2 + (-dy * 0.18) / coseno;
  const cy = (y0 + y1) / 2 + dx * 0.18;
  const puntos: [number, number][] = [];
  for (let i = 0; i <= pasos; i += 1) {
    const t = i / pasos;
    const a = (1 - t) * (1 - t);
    const b = 2 * (1 - t) * t;
    const c = t * t;
    puntos.push([
      Math.round((a * x0 + b * cx + c * x1) * 1e4) / 1e4,
      Math.round((a * y0 + b * cy + c * y1) * 1e4) / 1e4,
    ]);
  }
  return puntos;
}

// ---- Focos de calor en vivo (almacén público: focos/ultimas24h.json) -------------------

/** [lon, lat, hora UTC, satélite, impacto con el que coincide o null] */
export type FocoVivo = [lon: number, lat: number, hora: string, satelite: string, impacto: string | null];

export interface FocosVivos {
  generado: string;
  desde: string;
  ultimo_foco: string | null;
  fuente: string;
  atribucion: string;
  zona: { oeste: number; sur: number; este: number; norte: number };
  descartados: { baja_confianza: number; fuentes_habituales: number; fuego_frecuente: number };
  focos: FocoVivo[];
}

export const OBJETO_FOCOS_VIVOS = "focos/ultimas24h.json";

// ---- Imágenes de antes y después (almacén público: satelite/parejas.json) --------------

export interface ImagenSatelite {
  fecha: string;
  escena: string;
  objeto: string;
  nubes_recorte: number;
}

export interface ParejaSatelite {
  recorte: { lat: number; lon: number; lado_m: number };
  antes: ImagenSatelite | null;
  despues: ImagenSatelite | null;
}

export interface IndiceSatelite {
  generado: string;
  fuente: string;
  atribucion: string;
  parejas: Record<string, ParejaSatelite>;
}

export const OBJETO_PAREJAS = "satelite/parejas.json";
