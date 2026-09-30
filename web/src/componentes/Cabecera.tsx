import { numero } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { NOMBRE, SIGLAS, rutaDeIdioma } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { Enlace } from "../navegacion.tsx";

export interface Contadores {
  incidentes: number;
  confirmados: number;
  paises: number;
}

interface Props {
  idioma: Idioma;
  t: Textos;
  contadores: Contadores;
  /** Ruta equivalente a la actual en el otro idioma. */
  rutaOtroIdioma: string;
  onMetodologia: () => void;
}

function Contador({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <dt className="etiqueta text-[0.625rem]">{etiqueta}</dt>
      <dd className="mono text-base text-texto">{valor}</dd>
    </div>
  );
}

export function Cabecera({ idioma, t, contadores, rutaOtroIdioma, onMetodologia }: Props) {
  const otro: Idioma = idioma === "es" ? "en" : "es";
  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2">
      <h1 className="flex items-baseline gap-3">
        <Enlace a={rutaDeIdioma(idioma)} className="flex items-baseline gap-2 no-underline">
          <span aria-hidden="true" className="font-titular text-2xl font-bold text-dorado">
            »
          </span>
          <span className="font-titular text-2xl font-bold tracking-wordmark text-texto">
            {SIGLAS}
          </span>
        </Enlace>
        <span className="etiqueta hidden sm:inline">{NOMBRE}</span>
        <span className="sr-only sm:hidden">{NOMBRE}</span>
      </h1>
      <dl aria-label={t.cabecera.contadores} className="ml-auto flex items-center gap-5">
        <Contador
          etiqueta={t.cabecera.incidentes}
          valor={numero(contadores.incidentes, idioma)}
        />
        <Contador
          etiqueta={t.cabecera.confirmados}
          valor={numero(contadores.confirmados, idioma)}
        />
        <Contador etiqueta={t.cabecera.paises} valor={numero(contadores.paises, idioma)} />
      </dl>
      <div className="flex items-center gap-2">
        <button type="button" className="boton" onClick={onMetodologia} aria-haspopup="dialog">
          {t.cabecera.metodologia}
        </button>
        <Enlace
          a={rutaOtroIdioma}
          className="boton mono"
          hrefLang={otro}
        >
          <span className={idioma === "es" ? "text-texto" : "text-secundario"}>ES</span>
          <span aria-hidden="true">·</span>
          <span className={idioma === "en" ? "text-texto" : "text-secundario"}>EN</span>
          <span className="sr-only"> ({t.cabecera.cambiarIdioma})</span>
        </Enlace>
      </div>
    </header>
  );
}
