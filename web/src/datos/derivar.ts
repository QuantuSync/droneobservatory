// Resúmenes que la web deriva de los ficheros públicos. Funciones puras: las usa el
// script del build (scripts/datos.ts) y se prueban sin red ni disco.

import { diaDeInstante } from "../tiempo/dias.ts";
import { lucesDeAtaques, origenesDeAtaques } from "./guerraSatelite.ts";
import { DRON_DE_LA_GUERRA } from "./vocabulario.ts";
import type {
  Ataque,
  Atribucion,
  AtribucionResumen,
  ColeccionIncidentes,
  EpisodioResumen,
  Estado,
  EventoResumen,
  FilaImpacto,
  FocoRegion,
  FuenteSentido,
  Instante,
  ImpactoGuerra,
  FeatureIncidente,
  PropiedadesSinUbicacion,
  PublicacionSinUbicacion,
  FilaAtaque,
  IncidenteDetalle,
  IncidenteResumen,
  Meta,
  PublicacionUcrania,
  RangoODesconocido,
  Resumen,
  ResumenUcrania,
  Sentido,
  TipoDron,
  ZonaResumen,
} from "./tipos.ts";

/** Marca de una cifra que ninguna fuente da, en las filas numéricas de los ataques. */
export const DESCONOCIDO = -1;

/** Prefijo ISO 3166-2 de las regiones que la web dibuja en la capa de Ucrania. */
export const PREFIJO_UCRANIA = "UA-";

/** Confirmados y atribuidos: lo que el mapa resalta y el filtro «lo confirmado» deja. */
const ESTADOS_GRAVES: ReadonlySet<Estado> = new Set<Estado>(["confirmado", "atribuido"]);

export function esGrave(estado: Estado): boolean {
  return ESTADOS_GRAVES.has(estado);
}

/**
 * El instante de un inicio cuya hora se conoce (precisión de minuto o de hora); null si solo
 * se conoce el día o si la fecha es aproximada (la de publicación de la noticia).
 */
function instanteConHora(inicio: Instante): number | null {
  if (inicio.precision !== "minuto" && inicio.precision !== "hora") return null;
  const ms = Date.parse(inicio.valor);
  return Number.isNaN(ms) ? null : ms;
}

/** Actor de una atribución a una persona que la autoridad no nombra (proceso/atribucion.py). */
export const ACTOR_SIN_NOMBRE = "persona sin nombre publicado";

/** Tipo de actor y país de un atribuido (null en los demás estados). */
export function atribucionResumida(p: {
  estado: { actual: Estado };
  atribucion?: Atribucion;
}): AtribucionResumen | null {
  if (p.estado.actual !== "atribuido") return null;
  return { tipo: p.atribucion?.tipo ?? null, pais: p.atribucion?.pais ?? null };
}

/**
 * Claves del tipo de dron para el filtro: «autoridad:<grupo>» si la autoridad lo identificó;
 * «deducido:guerra» si lo deducido es «compatible con un dron de largo alcance de la guerra»; y
 * «deducido:<grupo>» del grupo que destaca cuando se enseñan porcentajes.
 */
export function clavesDron(tipo: TipoDron | undefined): string[] {
  if (tipo === undefined) return [];
  if (tipo.identificado !== undefined) return [`autoridad:${tipo.identificado.grupo}`];
  const publicado = tipo.publicado;
  if (publicado === undefined) return [];
  if (publicado.presentacion === "compatible_guerra") return [`deducido:${DRON_DE_LA_GUERRA}`];
  const primero = publicado.compatible[0];
  return primero === undefined ? [] : [`deducido:${primero.grupo}`];
}

export function resumirIncidente(feature: FeatureIncidente): IncidenteResumen {
  const p = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  return {
    id: p.id,
    punto: { lon, lat, radio_km: p.lugar.radio_km },
    imprecisa: null,
    tipo: p.tipo,
    estado: p.estado.actual,
    presencia: p.presencia_dron ?? null,
    titulo: p.titulo,
    dia: diaDeInstante(p.tiempo.inicio.valor),
    inicio: instanteConHora(p.tiempo.inicio),
    pais: p.lugar.pais,
    objetivo: p.objetivo?.nombre ?? null,
    episodio: p.episodio ?? null,
    foco: p.foco_termico !== undefined,
    atribucion: atribucionResumida(p),
    zona: p.zona?.grupo ?? null,
    dron: clavesDron(p.tipo_dron),
    ...(p.tipo_dron?.identificado !== undefined && { modeloDron: p.tipo_dron.identificado.modelo }),
  };
}

export function resumirSinUbicacion(p: PropiedadesSinUbicacion): IncidenteResumen {
  return {
    id: p.id,
    punto: null,
    imprecisa: { nivel: p.lugar.nivel, region: p.lugar.region ?? null },
    tipo: p.tipo,
    estado: p.estado.actual,
    presencia: p.presencia_dron ?? null,
    titulo: p.titulo,
    dia: diaDeInstante(p.tiempo.inicio.valor),
    inicio: instanteConHora(p.tiempo.inicio),
    pais: p.lugar.pais,
    objetivo: p.objetivo?.nombre ?? null,
    episodio: p.episodio ?? null,
    foco: p.foco_termico !== undefined,
    atribucion: atribucionResumida(p),
    zona: p.zona?.grupo ?? null,
    dron: clavesDron(p.tipo_dron),
    ...(p.tipo_dron?.identificado !== undefined && { modeloDron: p.tipo_dron.identificado.modelo }),
  };
}

export function detalleIncidente(feature: FeatureIncidente): IncidenteDetalle {
  const [lon, lat] = feature.geometry.coordinates;
  return { ...feature.properties, lon, lat };
}

export function detalleSinUbicacion(p: PropiedadesSinUbicacion): IncidenteDetalle {
  return { ...p, lon: null, lat: null };
}

/**
 * Eventos del feed: cada paso del historial de estados. El primero es la aparición del
 * incidente; los siguientes, cambios de estado. Del más reciente al más antiguo.
 */
export function eventos(
  historiales: readonly { id: string; estado: { historial: PropiedadesSinUbicacion["estado"]["historial"] } }[],
): EventoResumen[] {
  const todos: EventoResumen[] = [];
  for (const incidente of historiales) {
    // Pasos con la misma fecha (un alta que ya llega confirmada) son un solo evento, con el
    // último estado de ese momento.
    const porFecha = new Map<string, EventoResumen>();
    incidente.estado.historial.forEach((paso, i) => {
      const anterior = porFecha.get(paso.fecha.valor);
      porFecha.set(paso.fecha.valor, {
        id: incidente.id,
        fecha: paso.fecha.valor,
        estado: paso.estado,
        nuevo: anterior?.nuevo ?? i === 0,
      });
    });
    todos.push(...porFecha.values());
  }
  return todos.sort(
    (a, b) =>
      b.fecha.localeCompare(a.fecha) ||
      b.id.localeCompare(a.id) ||
      Number(a.nuevo) - Number(b.nuevo),
  );
}

/** Episodios con sus incidentes en orden cronológico; un episodio de uno solo no une nada. */
export function episodios(incidentes: readonly IncidenteResumen[]): EpisodioResumen[] {
  const porEpisodio = new Map<string, IncidenteResumen[]>();
  for (const incidente of incidentes) {
    if (incidente.episodio === null) continue;
    const grupo = porEpisodio.get(incidente.episodio) ?? [];
    grupo.push(incidente);
    porEpisodio.set(incidente.episodio, grupo);
  }
  return [...porEpisodio.entries()]
    .filter(([, grupo]) => grupo.length > 1)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([id, grupo]) => ({
      id,
      incidentes: grupo
        .slice()
        .sort((a, b) => a.dia - b.dia || a.id.localeCompare(b.id))
        .map((i) => i.id),
    }));
}

function masReciente(instantes: Iterable<string>): string {
  let ultimo = "";
  for (const instante of instantes) {
    if (instante > ultimo) ultimo = instante;
  }
  return ultimo;
}

export function ultimaActualizacion(
  coleccion: ColeccionIncidentes,
  ucrania: PublicacionUcrania,
): string {
  return masReciente([
    ...coleccion.features.map((f) => f.properties.control.ultima_actualizacion.valor),
    ...ucrania.ataques.map((a) => a.control.ultima_actualizacion.valor),
  ]);
}

export function resumir(
  coleccion: ColeccionIncidentes,
  ucrania: PublicacionUcrania,
  sinUbicacion: PublicacionSinUbicacion | null = null,
): Resumen {
  const imprecisos = sinUbicacion?.incidentes ?? [];
  const incidentes = [
    ...coleccion.features.map(resumirIncidente),
    ...imprecisos.map(resumirSinUbicacion),
  ].sort((a, b) => a.id.localeCompare(b.id));
  const actualizaciones = [
    ultimaActualizacion(coleccion, ucrania),
    ...imprecisos.map((p) => p.control.ultima_actualizacion.valor),
  ];
  return {
    actualizado: actualizaciones.reduce((a, b) => (b > a ? b : a)),
    incidentes,
    episodios: episodios(incidentes),
    eventos: eventos([...coleccion.features.map((f) => f.properties), ...imprecisos]),
  };
}

export interface Cifras {
  incidentes: number;
  confirmados: number;
  atribuidos: number;
  paises: number;
}

/**
 * Cifras del marcador. Un atribuido es por fuerza un confirmado (una autoridad, además de
 * confirmarlo, dice quién es el responsable): los confirmados los incluyen, y los atribuidos son
 * una parte de ellos. Así cuadran con cualquier filtro («4 confirmados · 4 atribuidos» con el
 * filtro de atribuidos).
 */
export function cifras(incidentes: readonly IncidenteResumen[]): Cifras {
  return {
    incidentes: incidentes.length,
    confirmados: incidentes.filter((i) => i.estado === "confirmado" || i.estado === "atribuido").length,
    atribuidos: incidentes.filter((i) => i.estado === "atribuido").length,
    paises: new Set(incidentes.map((i) => i.pais)).size,
  };
}

export function meta(resumen: Resumen, sinUbicacion: boolean): Meta {
  return { actualizado: resumen.actualizado, ...cifras(resumen.incidentes), sinUbicacion };
}

function par(rango: RangoODesconocido | undefined): [number, number] {
  if (rango === undefined || rango === "desconocido") return [DESCONOCIDO, DESCONOCIDO];
  return [rango.min, rango.max];
}

function filaAtaque(ataque: Ataque, indiceRegion: Map<string, number>): FilaAtaque {
  const [lanzadosMin, lanzadosMax] = par(ataque.lanzados?.total);
  const [derribadosMin, derribadosMax] = par(ataque.derribados);
  const regiones: FilaAtaque[8] = [];
  for (const region of ataque.regiones ?? []) {
    const indice = indiceRegion.get(region.region);
    if (indice === undefined) continue;
    regiones.push([indice, ...par(region.derribados)]);
  }
  const yaSumado =
    ataque.incluido_en !== undefined ||
    ataque.solapado_con !== undefined ||
    ataque.resumen === true;
  return [
    ataque.id,
    diaDeInstante(ataque.periodo.inicio.valor),
    ataque.sentido === "RU_UA" ? 0 : 1,
    lanzadosMin,
    lanzadosMax,
    derribadosMin,
    derribadosMax,
    yaSumado ? 0 : 1,
    regiones,
    Date.parse(ataque.periodo.fin.valor),
    minimoDeclarado(ataque.lanzados?.shahed_geran),
    minimoDeclarado(ataque.lanzados?.reactivos),
  ];
}

/** El mínimo que da el parte de un modelo contado aparte; -1 si no da ninguno (mínimo 0). */
function minimoDeclarado(rango: RangoODesconocido | undefined): number {
  if (rango === undefined || rango === "desconocido" || rango.min <= 0) return DESCONOCIDO;
  return rango.min;
}

type Anillo = [number, number][];
type Poligono = Anillo[];

/** Centro (centroide del área) del anillo exterior de mayor área de una región. */
export function centroDe(poligonos: readonly Poligono[]): [number, number] | null {
  let mejor: { area: number; centro: [number, number] } | null = null;
  for (const [exterior] of poligonos) {
    if (exterior === undefined || exterior.length < 3) continue;
    let area = 0;
    let x = 0;
    let y = 0;
    for (let i = 0; i < exterior.length - 1; i += 1) {
      const [x0, y0] = exterior[i] as [number, number];
      const [x1, y1] = exterior[i + 1] as [number, number];
      const cruce = x0 * y1 - x1 * y0;
      area += cruce;
      x += (x0 + x1) * cruce;
      y += (y0 + y1) * cruce;
    }
    if (area === 0) continue;
    const centro: [number, number] = [x / (3 * area), y / (3 * area)];
    if (mejor === null || Math.abs(area) > mejor.area) mejor = { area: Math.abs(area), centro };
  }
  return mejor === null ? null : mejor.centro;
}

/** Contornos de las regiones de Ucrania (public/mapa/ucrania-regiones.geojson) por código. */
export interface ContornosRegiones {
  features: {
    properties: { iso: string };
    geometry:
      | { type: "Polygon"; coordinates: Poligono }
      | { type: "MultiPolygon"; coordinates: Poligono[] };
  }[];
}

export function centrosDeRegiones(contornos: ContornosRegiones): Map<string, [number, number]> {
  const centros = new Map<string, [number, number]>();
  for (const { properties, geometry } of contornos.features) {
    const poligonos = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    const centro = centroDe(poligonos);
    if (centro !== null) {
      centros.set(properties.iso, [
        Math.round(centro[0] * 1e4) / 1e4,
        Math.round(centro[1] * 1e4) / 1e4,
      ]);
    }
  }
  return centros;
}

/** Regiones con foco térmico detectado de cada ataque, con el centro de la región. */
export function focosDeRegiones(
  ucrania: PublicacionUcrania,
  centros: ReadonlyMap<string, [number, number]>,
): FocoRegion[] {
  const focos: FocoRegion[] = [];
  for (const ataque of ucrania.ataques) {
    for (const region of ataque.regiones ?? []) {
      const centro = centros.get(region.region);
      if (region.foco_termico === undefined || centro === undefined) continue;
      focos.push({
        ataque: ataque.id,
        dia: diaDeInstante(ataque.periodo.inicio.valor),
        region: region.region,
        foco: region.foco_termico,
        centro,
      });
    }
  }
  return focos.sort((a, b) => b.dia - a.dia || a.ataque.localeCompare(b.ataque));
}

/** Un impacto con lugar reducido a su fila del resumen. */
export function filaImpacto(impacto: ImpactoGuerra): FilaImpacto {
  const dia = diaDeInstante(impacto.dia !== undefined ? `${impacto.dia}T00:00Z` : impacto.fecha.valor);
  return [
    impacto.id,
    dia,
    impacto.sentido === "RU_UA" ? 0 : 1,
    impacto.lugar.punto.lon,
    impacto.lugar.punto.lat,
    impacto.foco_termico !== undefined ? 1 : 0,
    impacto.reivindicacion_de_parte === true ? 1 : 0,
    impacto.lugar.nivel === "instalacion" ? 1 : 0,
    impacto.region,
  ];
}

/**
 * La fuente de las cifras de cada sentido (la Fuerza Aérea de Ucrania, el Ministerio de
 * Defensa ruso), con la puntuación que más se repite en sus partes: la ficha de una región
 * la da junto a sus cifras.
 */
export function fuentesPorSentido(ucrania: PublicacionUcrania): Record<Sentido, FuenteSentido | null> {
  const resultado: Record<Sentido, FuenteSentido | null> = { RU_UA: null, UA_RU: null };
  for (const sentido of ["RU_UA", "UA_RU"] as const) {
    const cuenta = new Map<string, { fuente: FuenteSentido; n: number }>();
    for (const ataque of ucrania.ataques) {
      if (ataque.sentido !== sentido) continue;
      for (const f of ataque.fuentes) {
        const clave = `${f.medio}|${f.fiabilidad}|${f.credibilidad}`;
        const previa = cuenta.get(clave);
        const fuente = {
          medio: f.medio,
          fiabilidad: f.fiabilidad,
          credibilidad: f.credibilidad,
          reivindicacion: ataque.reivindicacion_de_parte === true,
        };
        cuenta.set(clave, { fuente, n: (previa?.n ?? 0) + 1 });
      }
    }
    const mejor = [...cuenta.values()].sort((a, b) => b.n - a.n)[0];
    resultado[sentido] = mejor?.fuente ?? null;
  }
  return resultado;
}

/** Lo que el resumen de la capa de guerra necesita de la geografía (build: scripts/datos.ts). */
export interface GeografiaGuerra {
  /** Zonas de lanzamiento con punto y cómo casa un nombre de los partes con una de ellas. */
  zonas: ZonaResumen[];
  casar: (nombre: string) => number | null;
  /** Centro de cada región de Ucrania y de Rusia. */
  centros: ReadonlyMap<string, [number, number]>;
  /** Punto de la frontera de Ucrania más cercano a cada región rusa. */
  fronteraUcrania: ReadonlyMap<string, [number, number]>;
}

const SIN_GEOGRAFIA: GeografiaGuerra = {
  zonas: [],
  casar: () => null,
  centros: new Map(),
  fronteraUcrania: new Map(),
};

export function resumirUcrania(
  ucrania: PublicacionUcrania,
  centros: ReadonlyMap<string, [number, number]> = new Map(),
  geografia: GeografiaGuerra = SIN_GEOGRAFIA,
): ResumenUcrania {
  // Todas las regiones: las de Ucrania (con lo ocupado) y las de Rusia, donde se cuentan los
  // drones que el Ministerio de Defensa ruso dice haber derribado.
  const codigos = new Set<string>();
  for (const ataque of ucrania.ataques) {
    for (const region of ataque.regiones ?? []) codigos.add(region.region);
  }
  const regiones = [...codigos].sort();
  const indiceRegion = new Map(regiones.map((codigo, i) => [codigo, i]));
  const ataques = ucrania.ataques
    .map((ataque) => filaAtaque(ataque, indiceRegion))
    .sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]));
  // Los partes diarios (sobre todo ataques de corto alcance en el frente) se publican pero
  // no se dibujan: no son los ataques que cuenta la capa y taparían el resto.
  const impactos = (ucrania.impactos ?? [])
    .filter((impacto) => impacto.parte_diario !== true)
    .map(filaImpacto)
    .sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]));
  return {
    regiones,
    ataques,
    focos: focosDeRegiones(ucrania, centros),
    impactos,
    fuentes: fuentesPorSentido(ucrania),
    luces: lucesDeAtaques(ucrania),
    zonas: geografia.zonas,
    origenes: origenesDeAtaques(ucrania, geografia.casar),
    centros: Object.fromEntries(geografia.centros),
    fronteraUcrania: Object.fromEntries(geografia.fronteraUcrania),
  };
}
