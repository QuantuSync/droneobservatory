import { traduccionParaMostrar } from "../datos/citas.ts";
import type { Traduccion } from "../datos/tipos.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";

export { traduccionParaMostrar };

/**
 * Una cita de una fuente en el idioma de la página: la traducción guardada (exportacion/citas.py)
 * y, debajo y plegado, el original («Ver original» / «Show original»). Si la cita ya está en el
 * idioma de la página o no hay traducción, el original tal cual.
 */
export function Cita({
  t,
  idioma,
  texto,
  idiomaOriginal,
  traduccion,
  como = "blockquote",
  className = "",
  comillas = true,
  datos = {},
}: {
  t: Textos;
  idioma: Idioma;
  texto: string;
  idiomaOriginal?: string | undefined;
  traduccion?: Traduccion | undefined;
  como?: "blockquote" | "q";
  className?: string;
  comillas?: boolean;
  datos?: Record<string, string>;
}) {
  const Elemento = como;
  const escrito = (valor: string) => (comillas && como === "blockquote" ? `«${valor}»` : valor);
  const traducida = traduccionParaMostrar(idioma, texto, idiomaOriginal, traduccion);
  if (traducida === null) {
    return (
      <Elemento lang={idiomaOriginal} className={className} {...datos}>
        {escrito(texto)}
      </Elemento>
    );
  }
  return (
    <span className="block" data-cita-traducida="">
      <Elemento lang={idioma} className={className} {...datos}>
        {escrito(traducida)}
      </Elemento>
      <details className="mt-0.5 text-xs text-secundario">
        <summary className="cursor-pointer text-acento tel:flex tel:min-h-11 tel:items-center">
          {t.ficha.verOriginal}
        </summary>
        <span lang={idiomaOriginal} className="block pl-2" data-cita-original="">
          {escrito(texto)}
        </span>
      </details>
    </span>
  );
}
