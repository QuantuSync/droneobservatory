// Citas de las fuentes en el idioma de la página (exportacion/citas.py): la traducción guardada y
// el original plegado debajo. Lo usan la ficha (componentes/Cita.tsx) y las páginas de texto.

import type { Traduccion } from "./tipos.ts";
import type { Idioma } from "../sitio.ts";

/** La traducción que se enseña en la página, o null si se enseña el original: la cita ya está
 *  en el idioma de la página, no hay traducción o es igual al original. */
export function traduccionParaMostrar(
  idioma: Idioma,
  texto: string,
  idiomaOriginal: string | undefined,
  traduccion: Traduccion | undefined,
): string | null {
  if (traduccion === undefined || idiomaOriginal === idioma) return null;
  const traducida = traduccion[idioma].trim();
  if (traducida === "" || traducida === texto.trim()) return null;
  return traducida;
}
