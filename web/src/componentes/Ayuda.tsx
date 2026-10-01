import { useEffect, useRef } from "react";

import { ESTADOS, TIPOS } from "../datos/vocabulario.ts";
import { ATAJOS } from "../estado/atajos.ts";
import type { Textos } from "../i18n/index.ts";
import { Simbolo } from "./Simbolo.tsx";

interface Props {
  t: Textos;
  abierta: boolean;
  onCerrar: () => void;
}

/** Nombre legible de una tecla en el panel de ayuda. */
function tecla(nombre: string): string {
  return nombre === "Escape" ? "Esc" : nombre.toUpperCase();
}

/**
 * Ayuda (tecla ?): qué significa cada forma, color, área, línea y número del mapa, y los
 * atajos de teclado. Sustituye a la leyenda fija. Es un diálogo modal nativo.
 */
export function Ayuda({ t, abierta, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const elemento = dialogo.current;
    if (elemento === null || typeof elemento.showModal !== "function") return;
    if (abierta && !elemento.open) elemento.showModal();
    if (!abierta && elemento.open) elemento.close();
  }, [abierta]);

  const a = t.ayuda;
  return (
    // El diálogo nativo ya atiende al teclado (Escape); el clic fuera del panel lo cierra.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={dialogo}
      aria-labelledby="ayuda-titulo"
      onClose={onCerrar}
      onClick={(evento) => {
        if (evento.target === dialogo.current) onCerrar();
      }}
      className="flotante m-auto max-h-[86vh] w-[min(92vw,40rem)] overflow-y-auto p-0 backdrop:bg-fondo/60"
    >
      <div className="flex items-center border-b border-linea px-5 py-3">
        <h2 id="ayuda-titulo" className="mr-auto text-lg font-semibold tracking-tight">
          {a.titulo}
        </h2>
        <button type="button" className="control px-2 text-xs" aria-label={a.cerrar} onClick={onCerrar}>
          <span aria-hidden="true">✕</span>
        </button>
      </div>
      <div className="grid gap-5 px-5 py-4 sm:grid-cols-2">
        <section>
          <p className="text-secundario">{a.formas}</p>
          <ul className="mt-2 flex flex-col gap-1">
            {TIPOS.map((tipo) => (
              <li key={tipo} className="flex items-center gap-2">
                <Simbolo tipo={tipo} estado="notificado" />
                {t.tipo[tipo]}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <p className="text-secundario">{a.colores}</p>
          <ul className="mt-2 flex flex-col gap-1">
            {ESTADOS.map((estado) => (
              <li key={estado} className="flex items-center gap-2">
                <Simbolo tipo="interrupcion_aeroportuaria" estado={estado} />
                {t.estado[estado]}
              </li>
            ))}
          </ul>
        </section>
        <ul className="flex flex-col gap-2 text-secundario sm:col-span-2">
          {[a.areas, a.lineas, a.numeros, a.pila, a.pulsos, a.reciente, a.novedad, a.ucrania].map(
            (texto) => (
              <li key={texto}>{texto}</li>
            ),
          )}
        </ul>
        <section className="sm:col-span-2">
          <h3 className="font-medium">{a.atajos}</h3>
          <dl className="mt-2 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5">
            {ATAJOS.map(([nombre, accion]) => (
              <div key={nombre} className="contents">
                <dt>
                  <kbd className="tecla">{tecla(nombre)}</kbd>
                </dt>
                <dd className="text-secundario">{a.acciones[accion]}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </dialog>
  );
}
