// HTML escrito a mano para las páginas de texto: todo lo que viene de los datos se escapa aquí.

import { escaparHtml } from "../cabecera.ts";

/** Fragmento de HTML ya seguro (escapado o escrito aquí). */
export class Html {
  readonly valor: string;
  constructor(valor: string) {
    this.valor = valor;
  }
  toString(): string {
    return this.valor;
  }
}

export type Hijo = Html | string | number | null | undefined | false | readonly Hijo[];

function aplanar(hijo: Hijo): string {
  if (hijo === null || hijo === undefined || hijo === false) return "";
  if (hijo instanceof Html) return hijo.valor;
  if (Array.isArray(hijo)) return (hijo as readonly Hijo[]).map(aplanar).join("");
  return escaparHtml(String(hijo));
}

/** Une hijos (escapando el texto) en un fragmento. */
export function html(...hijos: Hijo[]): Html {
  return new Html(hijos.map(aplanar).join(""));
}

export type Atributos = Record<string, string | number | boolean | null | undefined>;

const VACIOS = new Set(["img", "link", "meta", "br", "hr"]);

/** Una etiqueta con sus atributos (escapados) y sus hijos. */
export function e(nombre: string, atributos: Atributos | null, ...hijos: Hijo[]): Html {
  const partes = Object.entries(atributos ?? {}).flatMap(([clave, valor]) => {
    if (valor === null || valor === undefined || valor === false) return [];
    return valor === true ? [` ${clave}`] : [` ${clave}="${escaparHtml(String(valor))}"`];
  });
  const apertura = `<${nombre}${partes.join("")}>`;
  if (VACIOS.has(nombre)) return new Html(apertura);
  return new Html(`${apertura}${aplanar(hijos)}</${nombre}>`);
}

/** Datos estructurados en JSON-LD: un bloque de datos, que el navegador no ejecuta. «<» se
 *  escribe como < para que ningún texto cierre la etiqueta. */
export function jsonLd(datos: unknown): Html {
  const json = JSON.stringify(datos).replace(/</g, "\\u003c");
  return new Html(`<script type="application/ld+json">${json}</script>`);
}
