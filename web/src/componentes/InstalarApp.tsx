import { useEffect, useId, useRef, useState } from "react";

import { instalar, useInstalacion } from "../app/instalar.ts";
import type { Textos } from "../i18n/index.ts";

interface Props {
  t: Textos;
  /** En el menú del teléfono: a todo el ancho. En escritorio: pequeño, junto a «Metodología». */
  grande?: boolean;
}

/** Un paso de Safari, con su número a la vista (el mismo estilo que los pasos de «Avisos»). */
function Paso({ numero, titulo, nota }: { numero: number; titulo: string; nota: string }) {
  return (
    <li className="flex flex-col gap-1" data-paso-instalar={numero}>
      <span className="flex items-center gap-2 text-sm font-semibold text-texto">
        <span
          aria-hidden="true"
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-linea text-xs"
        >
          {numero}
        </span>
        {titulo}
      </span>
      <span className="pl-8 text-xs text-secundario">{nota}</span>
    </li>
  );
}

/**
 * La entrada «Instalar la app» (app/instalar.ts). En Android y escritorio lanza el diálogo del
 * navegador; en el iPhone y el iPad despliega los dos pasos de Safari. No se ve si la app ya está
 * instalada, si se ha abierto desde su icono o si el navegador no ofrece instalarla.
 */
export function InstalarApp({ t, grande = false }: Props) {
  const modo = useInstalacion();
  const [pasos, setPasos] = useState(false);
  const idPasos = useId();
  const cajaPasos = useRef<HTMLDivElement>(null);
  // Al abrirse, los pasos se desplazan a la vista dentro del menú: en el teléfono quedaban bajo el
  // pie fijo de «Aplicar». Solo se desplaza el menú, nunca el mapa.
  useEffect(() => {
    if (pasos) cajaPasos.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [pasos]);
  if (modo === null) return null;
  const clase = grande
    ? "control w-full justify-start text-sm text-texto"
    : "control min-h-7 px-1.5 text-xs";
  if (modo === "nativo") {
    return (
      <button type="button" className={clase} data-instalar-app="nativo" onClick={() => void instalar()}>
        {t.app.instalar}
      </button>
    );
  }
  return (
    <div className={grande ? "flex flex-col gap-2" : "relative"}>
      <button
        type="button"
        className={clase}
        data-instalar-app="iphone"
        aria-expanded={pasos}
        aria-controls={idPasos}
        onClick={() => setPasos(!pasos)}
      >
        {t.app.instalar}
      </button>
      {pasos && (
        <div
          id={idPasos}
          ref={cajaPasos}
          className={grande ? "scroll-mb-20 px-1" : "flotante absolute right-0 top-full z-40 mt-1 w-72 p-3"}
          data-pasos-instalar=""
        >
          <p className="mb-2 text-xs text-secundario">{t.app.pasosIphone}</p>
          <ol className="flex flex-col gap-2">
            <Paso numero={1} titulo={t.app.pasoCompartir} nota={t.app.notaCompartir} />
            <Paso numero={2} titulo={t.app.pasoAnadir} nota={t.app.notaAnadir} />
          </ol>
        </div>
      )}
    </div>
  );
}
