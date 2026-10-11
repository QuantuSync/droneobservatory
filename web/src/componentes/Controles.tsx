import type { ReactNode } from "react";

import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { IDIOMAS } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { RUTAS_EN_LA_WEB } from "../rutasEnLaWeb.ts";

export interface Capas {
  incidentes: boolean;
  ucrania: boolean;
  densidad: boolean;
  presion: boolean;
  gnss: boolean;
  /** Subcapas de la de Ucrania: se ven si ella se ve, y solo si se encienden con su botón. */
  corredores: boolean;
  /** «Con satélite»: cortinillas con cambio, focos confirmados, apagones y ciudades a oscuras. */
  satelite: boolean;
  /** Rutas de los drones: franjas por noche, que se descargan al encenderla. */
  rutas: boolean;
}

export const CAPAS_INICIALES: Capas = {
  incidentes: true,
  ucrania: false,
  densidad: false,
  presion: false,
  gnss: false,
  corredores: false,
  satelite: false,
  rutas: false,
};

const ORDEN: readonly ("incidentes" | "ucrania" | "densidad" | "presion" | "gnss")[] = [
  "incidentes",
  "ucrania",
  "densidad",
  "presion",
  "gnss",
];
// «Rutas» solo con su interruptor encendido (rutasEnLaWeb.ts).
const ORDEN_GUERRA: readonly ("corredores" | "rutas")[] = RUTAS_EN_LA_WEB ? ["corredores", "rutas"] : ["corredores"];

/**
 * Las capas en un solo control compacto; cada una se enciende y se apaga por separado. Con la
 * capa de Ucrania encendida aparecen al lado sus subcapas, apagadas hasta que se pulsan:
 * corredores y «Con satélite». `grande` (el menú del teléfono) da a cada opción al
 * menos 44 px de alto, para el dedo, y las pone en una rejilla de tres columnas: las cinco
 * capas caben con holgura desde 360 px. Ahí las subcapas van debajo, con su rótulo, en una
 * fila propia de dos botones iguales a los de las capas, y bajo ella `panelGuerra` (la leyenda,
 * el filtro y la lista de «Con satélite») a todo el ancho.
 */
export function SelectorDeCapas({
  t,
  capas,
  onCapas,
  grande = false,
  extraGuerra = null,
  panelGuerra = null,
}: {
  t: Textos;
  capas: Capas;
  onCapas: (capas: Capas) => void;
  grande?: boolean;
  /** Al final del grupo de la guerra (el botón «Con satélite»). */
  extraGuerra?: ReactNode;
  /** En el teléfono, bajo la fila de las subcapas y a todo el ancho. */
  panelGuerra?: ReactNode;
}) {
  const boton = `control ${grande ? "min-h-11 px-2 text-sm" : "min-h-7 px-2 text-xs"}`;
  const rejilla = grande ? "grid grid-cols-3 gap-0.5" : "flex";
  const etiquetas: Record<(typeof ORDEN_GUERRA)[number], string> = {
    corredores: t.satelite.corredores,
    rutas: t.rutas.subcapa,
  };
  return (
    <div className={`flex gap-1 ${grande ? "flex-col" : "items-center"}`}>
      <div
        role="group"
        aria-label={t.controles.capas}
        className={`rounded-sm border border-linea p-0.5 ${rejilla}`}
      >
        {ORDEN.map((capa) => (
          <button
            key={capa}
            type="button"
            className={boton}
            aria-pressed={capas[capa]}
            onClick={() => onCapas({ ...capas, [capa]: !capas[capa] })}
          >
            {t.controles[capa]}
          </button>
        ))}
      </div>
      {capas.ucrania && grande && (
        <div className="mt-2 flex flex-col gap-1" data-bloque-guerra="">
          <p className="text-xs text-secundario">{t.satelite.rotuloCapas}</p>
          <div
            role="group"
            aria-label={t.satelite.capas}
            className="grid grid-cols-3 gap-0.5 rounded-sm border border-linea p-0.5"
            data-capas-guerra=""
          >
            {ORDEN_GUERRA.map((capa) => (
              <button
                key={capa}
                type="button"
                className={`${boton} whitespace-nowrap`}
                aria-pressed={capas[capa]}
                onClick={() => onCapas({ ...capas, [capa]: !capas[capa] })}
              >
                {etiquetas[capa]}
              </button>
            ))}
            {extraGuerra}
          </div>
          {panelGuerra !== null && (
            <div className="rounded-sm border border-linea">{panelGuerra}</div>
          )}
        </div>
      )}
      {capas.ucrania && !grande && (
        <div
          role="group"
          aria-label={t.satelite.capas}
          className="flex rounded-sm border border-linea/70 p-0.5"
          data-capas-guerra=""
        >
          {ORDEN_GUERRA.map((capa) => (
            <button
              key={capa}
              type="button"
              className={`${boton} whitespace-nowrap`}
              aria-pressed={capas[capa]}
              onClick={() => onCapas({ ...capas, [capa]: !capas[capa] })}
            >
              {etiquetas[capa]}
            </button>
          ))}
          {extraGuerra}
        </div>
      )}
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
  const medida = grande ? "min-h-11 min-w-11" : "min-h-7 min-w-7 tactil:min-w-11";
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
      className="tel:-my-4 tel:inline-block tel:py-4 tactil:-my-4 tactil:inline-block tactil:py-4"
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
