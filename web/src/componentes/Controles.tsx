import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { IDIOMAS } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";

export interface Capas {
  incidentes: boolean;
  ucrania: boolean;
  densidad: boolean;
  presion: boolean;
  gnss: boolean;
}

export const CAPAS_INICIALES: Capas = {
  incidentes: true,
  ucrania: false,
  densidad: false,
  presion: false,
  gnss: false,
};

const ORDEN: readonly (keyof Capas)[] = ["incidentes", "ucrania", "densidad", "presion", "gnss"];

/**
 * Las capas en un solo control compacto; cada una se enciende y se apaga por separado.
 * `grande` da a cada opción al menos 44 px de alto, para el dedo.
 */
export function SelectorDeCapas({
  t,
  capas,
  onCapas,
  grande = false,
}: {
  t: Textos;
  capas: Capas;
  onCapas: (capas: Capas) => void;
  grande?: boolean;
}) {
  return (
    <div
      role="group"
      aria-label={t.controles.capas}
      className="flex rounded-sm border border-linea p-0.5"
    >
      {ORDEN.map((capa) => (
        <button
          key={capa}
          type="button"
          className={`control text-xs ${grande ? "min-h-11 flex-1 px-3" : "min-h-7 px-2"}`}
          aria-pressed={capas[capa]}
          onClick={() => onCapas({ ...capas, [capa]: !capas[capa] })}
        >
          {t.controles[capa]}
        </button>
      ))}
    </div>
  );
}

/** ES · EN, discreto: el idioma actual en blanco y el otro como enlace a la misma pantalla. */
export function SelectorDeIdioma({
  t,
  idioma,
  rutaOtroIdioma,
  grande = false,
}: {
  t: Textos;
  idioma: Idioma;
  rutaOtroIdioma: string;
  grande?: boolean;
}) {
  const medida = grande ? "min-h-11 min-w-11" : "min-h-7 min-w-7";
  return (
    <nav aria-label={t.controles.idioma} className="flex items-center text-xs">
      {IDIOMAS.map((codigo, i) => (
        <span key={codigo} className="flex items-center">
          {i > 0 && (
            <span aria-hidden="true" className="text-secundario">
              ·
            </span>
          )}
          {codigo === idioma ? (
            <span aria-current="true" className={`inline-flex items-center justify-center text-texto ${medida}`}>
              {codigo.toUpperCase()}
            </span>
          ) : (
            <Enlace
              a={rutaOtroIdioma}
              hrefLang={codigo}
              lang={codigo}
              aria-label={t.controles.cambiarIdioma}
              className={`inline-flex items-center justify-center text-secundario hover:text-texto ${medida}`}
            >
              {codigo.toUpperCase()}
            </Enlace>
          )}
        </span>
      ))}
    </nav>
  );
}

function Glifo({ trazo }: { trazo: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={14}
      height={14}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={trazo} />
    </svg>
  );
}

/** Zoom del mapa, solo en escritorio: en el teléfono se amplía con los dedos. */
export function Zoom({ t, onZoom }: { t: Textos; onZoom: (paso: number) => void }) {
  return (
    <div role="group" aria-label={t.controles.zoom} className="flotante flex flex-col p-0.5">
      <button type="button" className="control min-h-8 px-2" aria-label={t.controles.acercar} onClick={() => onZoom(1)}>
        <Glifo trazo="M8 3v10M3 8h10" />
      </button>
      <button type="button" className="control min-h-8 px-2" aria-label={t.controles.alejar} onClick={() => onZoom(-1)}>
        <Glifo trazo="M3 8h10" />
      </button>
    </div>
  );
}

/**
 * Atribuciones del mapa en una sola línea pequeña, siempre visibles. El detalle de fuentes y
 * licencias está en la metodología.
 */
export function Atribuciones({ t }: { t: Textos }) {
  // En el teléfono, cada enlace se puede tocar en 44 px de alto sin que la línea crezca.
  const enlace = (texto: string, direccion: string) => (
    <EnlaceExterno
      enlace={direccion}
      aviso={t.ficha.enlaceExterno}
      avisoNoValido={t.ficha.enlaceNoValido}
      className="tel:-my-4 tel:inline-block tel:py-4"
    >
      {texto}
    </EnlaceExterno>
  );
  return (
    <p
      aria-label={t.firma.atribuciones}
      className="flotante whitespace-nowrap px-2 py-0.5 text-[0.6875rem] text-secundario tel:text-[0.625rem]"
    >
      © {enlace("OpenStreetMap", "https://www.openstreetmap.org/copyright")} ·{" "}
      {enlace("Protomaps", "https://protomaps.com/")} ·{" "}
      {enlace("Natural Earth", "https://www.naturalearthdata.com/")}
    </p>
  );
}
