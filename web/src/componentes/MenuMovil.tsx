import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import type { Textos } from "../i18n/index.ts";

interface Props {
  t: Textos;
  abierto: boolean;
  onCerrar: () => void;
  children: ReactNode;
}

/** Una sección del menú, con su rótulo. */
export function SeccionMenu({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-linea px-4 py-4">
      <h3 className="text-xs text-secundario">{rotulo}</h3>
      {children}
    </section>
  );
}

/**
 * Menú del teléfono: una hoja a pantalla completa con las cifras, las capas, los filtros, el
 * directo, la ayuda, la metodología y el idioma. Es un diálogo modal nativo (Escape lo cierra)
 * y respeta las zonas seguras de la pantalla.
 */
export function MenuMovil({ t, abierto, onCerrar, children }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const elemento = dialogo.current;
    if (elemento === null || typeof elemento.showModal !== "function") return;
    if (abierto && !elemento.open) elemento.showModal();
    if (!abierto && elemento.open) elemento.close();
  }, [abierto]);

  return (
    <dialog
      ref={dialogo}
      aria-labelledby="menu-titulo"
      onClose={onCerrar}
      className="m-0 h-dvh max-h-none w-full max-w-none bg-panel-solido p-0 pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)] text-texto"
    >
      <div className="sticky top-0 z-10 flex min-h-11 items-center border-b border-linea bg-panel-solido pl-4 pr-1">
        <h2 id="menu-titulo" className="mr-auto text-base font-semibold">
          {t.cabecera.menu}
        </h2>
        <button
          type="button"
          className="control min-h-11 min-w-11 text-texto"
          aria-label={t.cabecera.cerrarMenu}
          onClick={onCerrar}
        >
          <span aria-hidden="true">✕</span>
        </button>
      </div>
      {children}
    </dialog>
  );
}
