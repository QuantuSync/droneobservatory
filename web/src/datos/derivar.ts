// Resúmenes que la web deriva de los ficheros públicos. Funciones puras: las usa el
// script del build (scripts/datos.ts) y se prueban sin red ni disco.

import { diaDeInstante } from "../tiempo/dias.ts";
import type {
  Ataque,
  ColeccionIncidentes,
  EpisodioResumen,
  Estado,
  FeatureIncidente,
  FilaAtaque,
  IncidenteDetalle,
  IncidenteResumen,
  Meta,
  PublicacionUcrania,
  RangoODesconocido,
  Resumen,
  ResumenUcrania,
} from "./tipos.ts";

/** Marca de una cifra que ninguna fuente da, en las filas numéricas de los ataques. */
export const DESCONOCIDO = -1;

/** Prefijo ISO 3166-2 de las regiones que la web dibuja en la capa de Ucrania. */
export const PREFIJO_UCRANIA = "UA-";

/** Un incidente atribuido ha pasado antes por confirmado: cuenta como confirmado. */
const ESTADOS_CONFIRMADOS: ReadonlySet<Estado> = new Set<Estado>(["confirmado", "atribuido"]);

export function esConfirmado(estado: Estado): boolean {
  return ESTADOS_CONFIRMADOS.has(estado);
}

export function resumirIncidente(feature: FeatureIncidente): IncidenteResumen {
  const p = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  return {
    id: p.id,
    lon,
    lat,
    radio_km: p.lugar.radio_km,
    tipo: p.tipo,
    estado: p.estado.actual,
    presencia: p.presencia_dron ?? null,
    titulo: p.titulo,
    dia: diaDeInstante(p.tiempo.inicio.valor),
    pais: p.lugar.pais,
    objetivo: p.objetivo?.nombre ?? null,
    episodio: p.episodio ?? null,
  };
}

export function detalleIncidente(feature: FeatureIncidente): IncidenteDetalle {
  const [lon, lat] = feature.geometry.coordinates;
  return { ...feature.properties, lon, lat };
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

export function resumir(coleccion: ColeccionIncidentes, ucrania: PublicacionUcrania): Resumen {
  const incidentes = coleccion.features.map(resumirIncidente);
  return {
    actualizado: ultimaActualizacion(coleccion, ucrania),
    incidentes,
    episodios: episodios(incidentes),
  };
}

export function meta(resumen: Resumen): Meta {
  return {
    actualizado: resumen.actualizado,
    incidentes: resumen.incidentes.length,
    confirmados: resumen.incidentes.filter((i) => esConfirmado(i.estado)).length,
    paises: new Set(resumen.incidentes.map((i) => i.pais)).size,
  };
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
  const yaSumado = ataque.incluido_en !== undefined || ataque.solapado_con !== undefined;
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
  ];
}

export function resumirUcrania(ucrania: PublicacionUcrania): ResumenUcrania {
  const codigos = new Set<string>();
  for (const ataque of ucrania.ataques) {
    for (const region of ataque.regiones ?? []) {
      if (region.region.startsWith(PREFIJO_UCRANIA)) codigos.add(region.region);
    }
  }
  const regiones = [...codigos].sort();
  const indiceRegion = new Map(regiones.map((codigo, i) => [codigo, i]));
  const ataques = ucrania.ataques
    .map((ataque) => filaAtaque(ataque, indiceRegion))
    .sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]));
  return { regiones, ataques };
}
