import { useEffect, useRef } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";

import type { Textos } from "../i18n/index.ts";

/** Alturas de la hoja inferior: asomada, media y completa, como fracción del hueco. */
export const ALTURAS = { asomada: 0.28, media: 0.55, completa: 1 } as const;
export type Altura = keyof typeof ALTURAS;
const ORDEN_ALTURAS: readonly Altura[] = ["asomada", "media", "completa"];
/** Lo que hay que arrastrar, como fracción del hueco, para que cuente como gesto. */
const UMBRAL_ARRASTRE = 0.02;

/** La altura más cercana a una fracción dada, al soltar el asa. */
export function alturaMasCercana(fraccion: number): Altura {
  return ORDEN_ALTURAS.reduce((mejor, altura) =>
    Math.abs(ALTURAS[altura] - fraccion) < Math.abs(ALTURAS[mejor] - fraccion) ? altura : mejor,
  );
}

/** La siguiente altura al pulsar el asa: sube hasta completa y vuelve a asomada. */
export function siguienteAltura(actual: Altura): Altura {
  const i = ORDEN_ALTURAS.indexOf(actual);
  return ORDEN_ALTURAS[(i + 1) % ORDEN_ALTURAS.length] ?? "media";
}

interface PropsLateral {
  /** Nombre accesible del panel. */
  nombre: string;
  children: ReactNode;
}

/**
 * Panel lateral derecho de escritorio, de altura completa bajo la cabecera. Recibe el foco al
 * abrirse; el mapa se aparta para que lo abierto quede a la vista a su izquierda.
 */
export function PanelLateral({ nombre, children }: PropsLateral) {
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.focus({ preventScroll: true });
  }, [nombre]);
  return (
    <aside
      ref={panel}
      tabIndex={-1}
      aria-label={nombre}
      className="superficie flex h-full w-[26rem] flex-col border-l outline-none"
    >
      {children}
    </aside>
  );
}

interface PropsHoja {
  t: Textos;
  nombre: string;
  altura: Altura;
  onAltura: (altura: Altura) => void;
  children: ReactNode;
}

/**
 * Hoja inferior del teléfono, una sola a la vez (ficha, lista de un punto, línea de tiempo o
 * directo): opaca, con un asa que se arrastra entre tres alturas (asomada, media y completa)
 * y que, pulsada, pasa a la siguiente. Recibe el foco al abrirse.
 */
export function HojaInferior({ t, nombre, altura, onAltura, children }: PropsHoja) {
  const hoja = useRef<HTMLElement>(null);
  const arrastre = useRef<{ inicioY: number; fraccion: number; movida: boolean } | null>(null);
  // Un arrastre termina con un clic: ese clic no debe cambiar además de altura.
  const huboArrastre = useRef(false);

  useEffect(() => {
    hoja.current?.focus({ preventScroll: true });
  }, [nombre]);

  function hueco(): number {
    return hoja.current?.parentElement?.clientHeight ?? 1;
  }
  function empezar(evento: PointerEvent<HTMLButtonElement>) {
    evento.currentTarget.setPointerCapture(evento.pointerId);
    arrastre.current = { inicioY: evento.clientY, fraccion: ALTURAS[altura], movida: false };
  }
  function mover(evento: PointerEvent<HTMLButtonElement>) {
    const actual = arrastre.current;
    const elemento = hoja.current;
    if (actual === null || elemento === null) return;
    const delta = (actual.inicioY - evento.clientY) / hueco();
    if (Math.abs(delta) > UMBRAL_ARRASTRE) actual.movida = true;
    const fraccion = Math.min(ALTURAS.completa, Math.max(ALTURAS.asomada, actual.fraccion + delta));
    elemento.style.height = `${fraccion * 100}%`;
  }
  function soltar(evento: PointerEvent<HTMLButtonElement>) {
    const actual = arrastre.current;
    arrastre.current = null;
    const elemento = hoja.current;
    if (actual === null || elemento === null) return;
    elemento.style.height = "";
    huboArrastre.current = actual.movida;
    if (!actual.movida) return;
    const delta = (actual.inicioY - evento.clientY) / hueco();
    onAltura(alturaMasCercana(actual.fraccion + delta));
  }
  function tecla(evento: KeyboardEvent<HTMLButtonElement>) {
    const i = ORDEN_ALTURAS.indexOf(altura);
    const destino =
      evento.key === "ArrowUp" ? ORDEN_ALTURAS[i + 1] : evento.key === "ArrowDown" ? ORDEN_ALTURAS[i - 1] : undefined;
    if (destino === undefined) return;
    evento.preventDefault();
    onAltura(destino);
  }

  const clasesAltura: Record<Altura, string> = {
    asomada: "h-[28%]",
    media: "h-[55%]",
    completa: "h-full",
  };
  return (
    <aside
      ref={hoja}
      tabIndex={-1}
      aria-label={nombre}
      data-altura={altura}
      className={`absolute inset-x-0 bottom-0 z-30 flex flex-col border-t border-linea bg-panel-solido pb-[env(safe-area-inset-bottom)] shadow-panel outline-none ${clasesAltura[altura]}`}
    >
      <button
        type="button"
        className="flex min-h-11 w-full shrink-0 cursor-ns-resize touch-none items-center justify-center"
        aria-label={t.hoja.altura(t.hoja.alturas[altura])}
        onPointerDown={empezar}
        onPointerMove={mover}
        onPointerUp={soltar}
        onClick={() => {
          if (huboArrastre.current) {
            huboArrastre.current = false;
            return;
          }
          onAltura(siguienteAltura(altura));
        }}
        onKeyDown={tecla}
      >
        <span aria-hidden="true" className="h-1 w-10 rounded-full bg-secundario" />
      </button>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </aside>
  );
}
