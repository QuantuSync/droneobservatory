// Versiones de los datos abiertos depositadas en un repositorio de datos de investigación con su
// DOI (Discuss Data, una cada trimestre). No son los datos vivos de la web, que se rehacen cada
// hora: cada una es una copia fechada que no cambia. Salen de configuracion/versiones_archivadas.json,
// de la más nueva a la más vieja; si el fichero no tiene la forma esperada, la compilación falla
// aquí y no publica una cita a medias (tests/versiones-archivadas.test.ts lo comprueba).

import tabla from "../../../configuracion/versiones_archivadas.json" with { type: "json" };
import type { Idioma } from "../sitio.ts";

export interface LicenciaArchivada {
  nombre: string;
  url: string;
}

export interface VersionArchivada {
  /** Número de versión que da el repositorio (1.0, 1.1…). */
  version: string;
  /** Día del depósito, AAAA-MM-DD. */
  fecha: string;
  /** Hora de los datos publicados que lleva el paquete (UTC). */
  corte_datos: string;
  incidentes: number;
  paises: number;
  /** El DOI sin el https://doi.org/ delante. */
  doi: string;
  /** La página de la versión en el repositorio. */
  pagina: string;
  repositorio: string;
  institucion: Record<Idioma, string>;
  /** Archivos que guardan además una copia (Zenodo, DARIAH). */
  copias: string[];
  titulo: string;
  licencia: LicenciaArchivada;
  /** Licencia del fichero aparte del tráfico aéreo medido. */
  licencia_trafico: LicenciaArchivada;
  /** La cita tal como la da el repositorio. */
  cita: string;
}

const DOI = /^10\.\d{4,9}\/\S+$/;
const DIA = /^\d{4}-\d{2}-\d{2}$/;

function texto(x: unknown): x is string {
  return typeof x === "string" && x.trim() !== "";
}

function licencia(x: unknown): x is LicenciaArchivada {
  const l = x as Partial<LicenciaArchivada> | null;
  return typeof l === "object" && l !== null && texto(l.nombre) && texto(l.url) && l.url.startsWith("https://");
}

/** Los fallos de forma de la lista (vacía si está bien). */
export function erroresDeVersionesArchivadas(versiones: unknown): string[] {
  if (!Array.isArray(versiones)) return ["versiones no es una lista"];
  const errores: string[] = [];
  const vistas = new Set<string>();
  let anterior: string | null = null;
  for (const [i, x] of (versiones as unknown[]).entries()) {
    const v = x as Partial<VersionArchivada> | null;
    const donde = `versiones[${i}]`;
    if (typeof v !== "object" || v === null) {
      errores.push(`${donde} no es un objeto`);
      continue;
    }
    if (!texto(v.version)) errores.push(`${donde}.version`);
    else if (vistas.has(v.version)) errores.push(`${donde}.version repetida`);
    else vistas.add(v.version);
    if (!texto(v.fecha) || !DIA.test(v.fecha)) errores.push(`${donde}.fecha`);
    else {
      if (anterior !== null && v.fecha > anterior) errores.push(`${donde} no va de la más nueva a la más vieja`);
      anterior = v.fecha;
    }
    if (!texto(v.corte_datos) || Number.isNaN(Date.parse(v.corte_datos))) errores.push(`${donde}.corte_datos`);
    for (const campo of ["incidentes", "paises"] as const) {
      const n = v[campo];
      if (typeof n !== "number" || !Number.isInteger(n) || n <= 0) errores.push(`${donde}.${campo}`);
    }
    if (!texto(v.doi) || !DOI.test(v.doi)) errores.push(`${donde}.doi`);
    if (!texto(v.pagina) || !v.pagina.startsWith("https://")) errores.push(`${donde}.pagina`);
    for (const campo of ["repositorio", "titulo"] as const) if (!texto(v[campo])) errores.push(`${donde}.${campo}`);
    if (typeof v.institucion !== "object" || v.institucion === null || !texto(v.institucion.es) || !texto(v.institucion.en)) errores.push(`${donde}.institucion`);
    if (!Array.isArray(v.copias) || !v.copias.every(texto)) errores.push(`${donde}.copias`);
    if (!licencia(v.licencia)) errores.push(`${donde}.licencia`);
    if (!licencia(v.licencia_trafico)) errores.push(`${donde}.licencia_trafico`);
    if (!texto(v.cita) || !texto(v.doi) || !v.cita.includes(v.doi)) errores.push(`${donde}.cita no lleva el DOI`);
  }
  return errores;
}

function leer(): readonly VersionArchivada[] {
  const errores = erroresDeVersionesArchivadas(tabla.versiones);
  if (errores.length > 0) throw new Error(`configuracion/versiones_archivadas.json: ${errores.join("; ")}`);
  return tabla.versiones as VersionArchivada[];
}

/** Las versiones archivadas, de la más nueva a la más vieja. */
export const VERSIONES_ARCHIVADAS: readonly VersionArchivada[] = leer();

/** La dirección del DOI (la que se enlaza y se cita). */
export function urlDeDoi(doi: string): string {
  return `https://doi.org/${doi}`;
}
