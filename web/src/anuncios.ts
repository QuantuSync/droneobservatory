// Los avisos del observatorio (un parón, un cambio que conviene contar): sus datos están en
// public/anuncios.json, el más reciente primero. Cada uno sale entero en la página «Avisos» (/avisos,
// /en/alerts) con su ancla (#<id>) y, si lleva «ventana», también en la ventana de todas las
// páginas (public/anuncio.js) entre ventana.desde y ventana.hasta. Para otro aviso basta con
// añadirlo arriba en el JSON: ni este fichero ni la ventana cambian.

import datos from "../public/anuncios.json" with { type: "json" };
import type { Idioma } from "./sitio.ts";

export interface Anuncio {
  /** Ancla en la página «Avisos» y clave con que el navegador recuerda que se cerró. */
  id: string;
  /** Día del aviso, AAAA-MM-DD. */
  fecha: string;
  titulo: Record<Idioma, string>;
  parrafos: Record<Idioma, string[]>;
  ventana?: {
    /** Desde cuándo y hasta cuándo sale la ventana, en UTC (ISO 8601 con «Z»). */
    desde: string;
    hasta: string;
    /** El texto de la ventana; la última vez que sale enlace.texto va con el enlace. */
    texto: Record<Idioma, string>;
    enlace: { texto: Record<Idioma, string>; ruta: Record<Idioma, string> };
  };
}

const ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const FECHA = /^\d{4}-\d{2}-\d{2}$/;
const INSTANTE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z$/;

function enLosDos(valor: Record<Idioma, string>, que: string): string[] {
  return (["es", "en"] as const).flatMap((i) => (typeof valor[i] === "string" && valor[i].trim() !== "" ? [] : [`${que} sin ${i}`]));
}

/** Los fallos de los datos de los avisos (lista vacía si están bien). */
export function fallosDeAnuncios(lista: readonly Anuncio[]): string[] {
  const fallos: string[] = [];
  const vistos = new Set<string>();
  for (const a of lista) {
    const n = a.id;
    if (!ID.test(n)) fallos.push(`id no válido: ${n}`);
    if (vistos.has(n)) fallos.push(`id repetido: ${n}`);
    vistos.add(n);
    if (!FECHA.test(a.fecha)) fallos.push(`${n}: fecha no válida`);
    fallos.push(...enLosDos(a.titulo, `${n}: título`));
    for (const i of ["es", "en"] as const) {
      if (!Array.isArray(a.parrafos[i]) || a.parrafos[i].length === 0) fallos.push(`${n}: párrafos sin ${i}`);
    }
    const v = a.ventana;
    if (v === undefined) continue;
    if (!INSTANTE.test(v.desde) || !INSTANTE.test(v.hasta)) fallos.push(`${n}: ventana con fechas no válidas`);
    else if (Date.parse(v.hasta) <= Date.parse(v.desde)) fallos.push(`${n}: la ventana acaba antes de empezar`);
    fallos.push(...enLosDos(v.texto, `${n}: texto de la ventana`), ...enLosDos(v.enlace.texto, `${n}: texto del enlace`));
    for (const i of ["es", "en"] as const) {
      if (typeof v.texto[i] === "string" && !v.texto[i].includes(v.enlace.texto[i])) {
        fallos.push(`${n}: el texto ${i} de la ventana no contiene «${v.enlace.texto[i]}»`);
      }
      if (typeof v.enlace.ruta[i] !== "string" || !v.enlace.ruta[i].startsWith("/") || !v.enlace.ruta[i].endsWith(`#${n}`)) {
        fallos.push(`${n}: el enlace ${i} no lleva a /…#${n}`);
      }
    }
  }
  return fallos;
}

export const ANUNCIOS: readonly Anuncio[] = datos.anuncios;

/** Fecha del aviso como en la página: 28/11/2026. */
export function fechaDeAnuncio(fecha: string): string {
  const [anio, mes, dia] = fecha.split("-");
  return `${dia}/${mes}/${anio}`;
}
