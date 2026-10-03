// Detección en directo de cierres de aeropuerto: directo.json, que el servidor sube al
// almacén público en cada ciclo (cada minuto) sin pasar por git ni por un despliegue.

import { OBJETO_DIRECTO, urlDelAlmacen } from "../almacenPublico.ts";
import type { Carga, Descarga } from "./carga.ts";
import { PATRON_INSTANTE } from "./vocabulario.ts";

export type EstadoAviso = "posible_cierre" | "cierre_confirmado" | "operacion_reanudada";
export const ESTADOS_AVISO: readonly EstadoAviso[] = [
  "posible_cierre",
  "cierre_confirmado",
  "operacion_reanudada",
];
export type FuenteDirecto = "adsb_lol" | "adsb_fi";
export const FUENTES_DIRECTO: readonly FuenteDirecto[] = ["adsb_lol", "adsb_fi"];
export type TipoConfirmacion = "incidente" | "oficial";

export interface EvidenciaAviso {
  esperados: number;
  vistos: number;
  llegadas_perdidas: number;
  salidas_perdidas: number;
  esperas: number;
  desvios: number;
}

export interface Confirmacion {
  tipo: TipoConfirmacion;
  incidente: string | null;
  hora: string;
}

export interface Aviso {
  id: string;
  oaci: string;
  nombre: string;
  pais: string;
  lat: number;
  lon: number;
  estado: EstadoAviso;
  inicio: string;
  detectado: string;
  reanudado: string | null;
  evidencia: EvidenciaAviso;
  confirmacion: Confirmacion | null;
  primera_noticia: string | null;
  ventaja_min: number | null;
}

export interface Directo {
  version: 1;
  generado: string;
  fuente: FuenteDirecto;
  ciclo_s: number;
  aeropuertos_vigilados: number;
  avisos: Aviso[];
}

const PATRON_OACI = /^[A-Z0-9]{4}$/;
const PATRON_PAIS = /^[A-Z]{2}$/;
const PATRON_INCIDENTE = /^EODI-(?:UA-)?\d{4}-\d{4,5}$/;

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

/** Objeto con exactamente estas claves: un campo de más o de menos no vale (lista cerrada). */
function claves(valor: Record<string, unknown>, lista: readonly string[]): boolean {
  const propias = Object.keys(valor);
  return propias.length === lista.length && lista.every((clave) => clave in valor);
}

const CAMPOS_AVISO = [
  "id", "oaci", "nombre", "pais", "lat", "lon", "estado", "inicio", "detectado", "reanudado",
  "evidencia", "confirmacion", "primera_noticia", "ventaja_min",
] as const;
const CAMPOS_EVIDENCIA = [
  "esperados", "vistos", "llegadas_perdidas", "salidas_perdidas", "esperas", "desvios",
] as const;
const CAMPOS_CONFIRMACION = ["tipo", "incidente", "hora"] as const;
const CAMPOS_DIRECTO = [
  "version", "generado", "fuente", "ciclo_s", "aeropuertos_vigilados", "avisos",
] as const;

function instante(valor: unknown): boolean {
  return typeof valor === "string" && PATRON_INSTANTE.test(valor);
}

function noNegativo(valor: unknown): boolean {
  return typeof valor === "number" && Number.isFinite(valor) && valor >= 0;
}

function esEvidencia(valor: unknown): boolean {
  return (
    esObjeto(valor) &&
    claves(valor, CAMPOS_EVIDENCIA) &&
    CAMPOS_EVIDENCIA.every((clave) => noNegativo(valor[clave]))
  );
}

function esConfirmacion(valor: unknown): boolean {
  if (valor === null) return true;
  return (
    esObjeto(valor) &&
    claves(valor, CAMPOS_CONFIRMACION) &&
    (valor.tipo === "incidente" || valor.tipo === "oficial") &&
    (valor.incidente === null ||
      (typeof valor.incidente === "string" && PATRON_INCIDENTE.test(valor.incidente))) &&
    instante(valor.hora)
  );
}

function esAviso(valor: unknown): boolean {
  return (
    esObjeto(valor) &&
    claves(valor, CAMPOS_AVISO) &&
    typeof valor.id === "string" &&
    valor.id.length > 0 &&
    valor.id.length <= 64 &&
    typeof valor.oaci === "string" &&
    PATRON_OACI.test(valor.oaci) &&
    typeof valor.nombre === "string" &&
    valor.nombre.length <= 120 &&
    typeof valor.pais === "string" &&
    PATRON_PAIS.test(valor.pais) &&
    typeof valor.lat === "number" &&
    Math.abs(valor.lat) <= 90 &&
    typeof valor.lon === "number" &&
    Math.abs(valor.lon) <= 180 &&
    ESTADOS_AVISO.includes(valor.estado as EstadoAviso) &&
    instante(valor.inicio) &&
    instante(valor.detectado) &&
    (valor.reanudado === null || instante(valor.reanudado)) &&
    esEvidencia(valor.evidencia) &&
    esConfirmacion(valor.confirmacion) &&
    (valor.primera_noticia === null || instante(valor.primera_noticia)) &&
    (valor.ventaja_min === null ||
      (typeof valor.ventaja_min === "number" && Number.isInteger(valor.ventaja_min)))
  );
}

/** Validación ligera: un fichero que no cumple no se pinta. */
export function validarDirecto(valor: unknown): Directo | null {
  if (
    !esObjeto(valor) ||
    !claves(valor, CAMPOS_DIRECTO) ||
    valor.version !== 1 ||
    !instante(valor.generado) ||
    !FUENTES_DIRECTO.includes(valor.fuente as FuenteDirecto) ||
    !noNegativo(valor.ciclo_s) ||
    !noNegativo(valor.aeropuertos_vigilados) ||
    !Array.isArray(valor.avisos) ||
    !valor.avisos.every(esAviso)
  ) {
    return null;
  }
  return valor as unknown as Directo;
}

/** Los cierres en curso: posibles y confirmados que aún no han reanudado. */
export function cierresEnCurso(directo: Directo | null): Aviso[] {
  return (directo?.avisos ?? []).filter((a) => a.estado !== "operacion_reanudada");
}

/** Orden de gravedad para pintar y listar: confirmados, posibles y reanudados. */
const ORDEN: Record<EstadoAviso, number> = {
  cierre_confirmado: 0,
  posible_cierre: 1,
  operacion_reanudada: 2,
};

export function ordenarAvisos(avisos: readonly Aviso[]): Aviso[] {
  return [...avisos].sort(
    (a, b) => ORDEN[a.estado] - ORDEN[b.estado] || b.detectado.localeCompare(a.detectado),
  );
}

/** Avisos como GeoJSON de puntos para el mapa. */
export function avisosEnMapa(avisos: readonly Aviso[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: ordenarAvisos(avisos)
      .reverse()
      .map((a) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [a.lon, a.lat] },
        properties: { id: a.id, estado: a.estado, oaci: a.oaci },
      })),
  };
}

export const URL_DIRECTO: string =
  (import.meta.env.VITE_DIRECTO as string | undefined) ?? urlDelAlmacen(OBJETO_DIRECTO);

export async function cargarDirecto(descargar: Descarga, senal?: AbortSignal): Promise<Carga<Directo>> {
  try {
    const opciones: RequestInit = { cache: "no-cache" };
    if (senal !== undefined) opciones.signal = senal;
    const respuesta = await descargar(URL_DIRECTO, opciones);
    if (respuesta.status === 404 || respuesta.status === 403) return { estado: "no_encontrado" };
    if (!respuesta.ok) return { estado: "no_disponible" };
    const datos = validarDirecto(await respuesta.json());
    return datos === null
      ? { estado: "no_valido", errores: [URL_DIRECTO] }
      : { estado: "listo", datos };
  } catch {
    return { estado: "no_disponible" };
  }
}
