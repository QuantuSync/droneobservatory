// Metadatos de cada página (título, descripción, vista previa al compartir). Se escriben
// en el build, dentro del bloque marcado de index.html. Los títulos de los incidentes
// vienen de fuera: todo valor se escapa antes de entrar en el HTML.

import { textos } from "./i18n/index.ts";
import {
  IDIOMAS,
  IMAGEN_COMPARTIR,
  IMAGEN_COMPARTIR_ALTO,
  IMAGEN_COMPARTIR_ANCHO,
  NOMBRE,
  ORIGEN,
  rutaDeFicha,
  rutaDeIdioma,
} from "./sitio.ts";
import type { Idioma } from "./sitio.ts";

export const INICIO_CABECERA = "<!--cabecera-->";
export const FIN_CABECERA = "<!--/cabecera-->";

const ENTIDADES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escaparHtml(texto: string): string {
  return texto.replace(/[&<>"']/g, (caracter) => ENTIDADES[caracter] ?? caracter);
}

export interface Pagina {
  idioma: Idioma;
  /** Identificador del incidente o del ataque, o null en la portada. */
  id: string | null;
  titulo: string;
  descripcion: string;
  /** Dirección en cada idioma, para las páginas que no son la portada ni una ficha. */
  rutas?: Record<Idioma, string>;
}

export function paginaDePortada(idioma: Idioma): Pagina {
  const t = textos(idioma);
  return { idioma, id: null, titulo: t.compartir.titulo, descripcion: t.descripcion };
}

export function paginaDeIncidente(idioma: Idioma, id: string, titulo: string): Pagina {
  const t = textos(idioma);
  return {
    idioma,
    id,
    titulo: t.compartir.tituloIncidente(titulo),
    descripcion: t.descripcion,
  };
}

function direccion(pagina: Pagina, idioma: Idioma): string {
  const ruta =
    pagina.rutas !== undefined
      ? pagina.rutas[idioma]
      : pagina.id === null
        ? rutaDeIdioma(idioma)
        : rutaDeFicha(pagina.id, idioma);
  return ORIGEN + (ruta === "/" ? "/" : ruta);
}

const LOCALES: Record<Idioma, string> = { es: "es_ES", en: "en_GB" };

export function etiquetasDeCabecera(pagina: Pagina): string {
  const t = textos(pagina.idioma);
  const titulo = escaparHtml(pagina.titulo);
  const descripcion = escaparHtml(pagina.descripcion);
  const url = escaparHtml(direccion(pagina, pagina.idioma));
  const imagen = escaparHtml(ORIGEN + IMAGEN_COMPARTIR[pagina.idioma]);
  const alternativas = IDIOMAS.map(
    (idioma) =>
      `<link rel="alternate" hreflang="${idioma}" href="${escaparHtml(direccion(pagina, idioma))}">`,
  );
  return [
    `<title>${titulo}</title>`,
    `<meta name="description" content="${descripcion}">`,
    `<link rel="canonical" href="${url}">`,
    ...alternativas,
    `<meta property="og:type" content="website">`,
    `<meta property="og:site_name" content="${escaparHtml(NOMBRE)}">`,
    `<meta property="og:locale" content="${LOCALES[pagina.idioma]}">`,
    `<meta property="og:title" content="${titulo}">`,
    `<meta property="og:description" content="${descripcion}">`,
    `<meta property="og:url" content="${url}">`,
    `<meta property="og:image" content="${imagen}">`,
    `<meta property="og:image:width" content="${IMAGEN_COMPARTIR_ANCHO}">`,
    `<meta property="og:image:height" content="${IMAGEN_COMPARTIR_ALTO}">`,
    `<meta property="og:image:alt" content="${escaparHtml(t.compartir.altImagen)}">`,
    `<meta name="twitter:card" content="summary_large_image">`,
    `<meta name="twitter:title" content="${titulo}">`,
    `<meta name="twitter:description" content="${descripcion}">`,
    `<meta name="twitter:image" content="${imagen}">`,
    `<meta name="twitter:image:alt" content="${escaparHtml(t.compartir.altImagen)}">`,
  ].join("\n    ");
}

/** Sustituye el bloque de cabecera de una página y el idioma declarado en <html>. */
export function aplicarCabecera(html: string, pagina: Pagina): string {
  const inicio = html.indexOf(INICIO_CABECERA);
  const fin = html.indexOf(FIN_CABECERA);
  if (inicio === -1 || fin === -1 || fin < inicio) {
    throw new Error("la página no tiene el bloque de cabecera");
  }
  const conCabecera =
    html.slice(0, inicio + INICIO_CABECERA.length) +
    "\n    " +
    etiquetasDeCabecera(pagina) +
    "\n    " +
    html.slice(fin);
  return conCabecera.replace(/<html lang="[a-z]{2}"/, `<html lang="${pagina.idioma}"`);
}
