import type { ReactNode } from "react";

import type { Textos } from "../i18n/index.ts";
import { NOMBRE } from "../sitio.ts";

/** El logo simplificado, para tamaños pequeños (cabecera e iconos). */
export const LOGO_PEQUENO = "/marca/eodi-simplificado.svg";

export function LogoPequeno({ lado }: { lado: number }) {
  return <img src={LOGO_PEQUENO} alt="" width={lado} height={lado} className="shrink-0" />;
}

interface Props {
  t: Textos;
  /** Cifras del periodo y estado de los datos, en el centro. */
  centro: ReactNode;
  /** Capas, noche a noche, en directo, ayuda, metodología e idioma, a la derecha. */
  derecha: ReactNode;
}

/**
 * Cabecera fina de escritorio, a todo lo ancho y en una sola línea: el logo y el nombre a la
 * izquierda, las cifras y el estado en el centro y los controles a la derecha. Cada control
 * se entiende por su rótulo, sin flechas ni adornos.
 */
export function Cabecera({ t, centro, derecha }: Props) {
  return (
    <header
      aria-label={t.cabecera.etiqueta}
      className="superficie flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 border-b px-3 py-1 max-[1439px]:[&_.control]:text-[0.6875rem] max-[1439px]:[&_dt]:text-[0.6875rem]"
    >
      <div className="flex shrink-0 items-center gap-2">
        <LogoPequeno lado={24} />
        {/* En pantallas de menos de 1536 px el nombre va en dos líneas cortas, para que la
            cabecera siga siendo una sola barra. */}
        <h1 className="text-[0.8125rem] font-medium leading-tight text-texto max-2xl:w-[9.5rem] max-2xl:text-[0.6875rem] 2xl:whitespace-nowrap">
          {NOMBRE}
        </h1>
      </div>
      <div className="flex flex-1 items-center justify-center gap-3">{centro}</div>
      {/* Si no cabe en la línea (tableta), lo de la derecha pasa a la siguiente sin cortarse. */}
      <div className="flex max-w-full shrink-0 flex-wrap items-center gap-x-0.5 gap-y-1">{derecha}</div>
    </header>
  );
}

/**
 * Barra compacta del teléfono: logo y «EODI», el estado, el botón «Avisos» (a la vista, fuera del
 * menú) y el botón del menú. Nada más.
 */
export function BarraMovil({
  t,
  estado,
  menuAbierto,
  onMenu,
  avisos,
}: {
  t: Textos;
  estado: ReactNode;
  menuAbierto: boolean;
  onMenu: () => void;
  avisos?: ReactNode;
}) {
  return (
    <header aria-label={t.cabecera.etiqueta} className="superficie border-b pt-[env(safe-area-inset-top)]">
      <div className="flex min-h-11 items-center gap-2 pl-3 pr-1">
        <LogoPequeno lado={24} />
        {/* El nombre completo va siempre en inglés; en la barra del teléfono se ve la sigla. */}
        <h1 className="text-sm font-semibold text-texto">
          <span aria-hidden="true">EODI</span>
          <span className="sr-only">{NOMBRE}</span>
        </h1>
        <div className="ml-auto min-w-0">{estado}</div>
        {avisos}
        <button
          type="button"
          className="control min-h-11 min-w-11 text-sm text-texto"
          aria-haspopup="dialog"
          aria-expanded={menuAbierto}
          onClick={onMenu}
        >
          {t.cabecera.menu}
        </button>
      </div>
    </header>
  );
}
