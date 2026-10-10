import { useEffect, useRef } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";

import type { Textos } from "../i18n/index.ts";

/** Alturas de la hoja inferior: asomada, media y completa, como fracción del hueco. */
export const ALTURAS = { asomada: 0.28, media: 0.55, completa: 1 } as const;
export type Altura = keyof typeof ALTURAS;
const ORDEN_ALTURAS: readonly Altura[] = ["asomada", "media", "completa"];

/** La altura más cercana a una fracción dada, al soltar el asa. */
export function alturaMasCercana(fraccion: number): Altura {
  return ORDEN_ALTURAS.reduce((mejor, altura) =>
    Math.abs(ALTURAS[altura] - fraccion) < Math.abs(ALTURAS[mejor] - fraccion) ? altura : mejor,
  );
}

/** La siguiente altura al tocar el asa: asomada → media → completa → media. Nunca cierra. */
export function siguienteAltura(actual: Altura): Altura {
  return actual === "asomada" ? "media" : actual === "media" ? "completa" : "media";
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
      data-ficha=""
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
  /** Cerrar la hoja: con la X o arrastrándola hacia abajo por debajo de la altura asomada. */
  onCerrar: () => void;
  children: ReactNode;
  /** Lleva una ficha (no los filtros, «Europa ahora» o una lista): al cerrarla vuelve el foco. */
  esFicha?: boolean;
}

/** Lo que se mueve el dedo antes de que cuente como arrastre y no como toque. */
const UMBRAL_ARRASTRE_PX = 6;
/** Cuánto se proyecta la velocidad del gesto al soltar, para decidir la altura. */
const PROYECCION_MS = 250;
/** Muestras del gesto que cuentan para la velocidad: las de los últimos milisegundos. */
const VENTANA_VELOCIDAD_MS = 100;
/** Por debajo de esta parte de la altura asomada, al soltar, la hoja se cierra. */
const FRACCION_DE_CIERRE = 0.6;
/** Margen tras soltar un arrastre con ratón en el que llega su clic, que no debe pulsar nada. */
export const MARGEN_CLIC_DE_ARRASTRE_MS = 350;

/** El clic que puede llegar al soltar un arrastre con ratón: de qué puntero y hasta cuándo. */
export interface ClicDeArrastre {
  puntero: number;
  hasta: number;
}

/**
 * Si un clic es el que cierra un arrastre con ratón y hay que descartarlo: del mismo puntero
 * (cuando el navegador lo dice) y dentro del margen. Con el dedo no llega ningún clic al soltar un
 * arrastre, así que un toque nunca se descarta por un arrastre anterior.
 */
export function esClicDeArrastre(pendiente: ClicDeArrastre | null, puntero: number | undefined, ahora: number): boolean {
  if (pendiente === null || ahora > pendiente.hasta) return false;
  return puntero === undefined || puntero === pendiente.puntero;
}

interface Gesto {
  inicioY: number;
  altoInicial: number;
  arrastrando: boolean;
  muestras: { y: number; t: number }[];
}

/** El elemento con desplazamiento propio más cercano al toque, dentro de la hoja. */
function desplazable(desde: EventTarget | null, hoja: HTMLElement): HTMLElement | null {
  for (let e = desde instanceof HTMLElement ? desde : null; e !== null && e !== hoja; e = e.parentElement) {
    const estilo = getComputedStyle(e);
    if (/(auto|scroll)/.test(estilo.overflowY) && e.scrollHeight > e.clientHeight) return e;
  }
  return null;
}

/**
 * Hoja inferior del teléfono, una sola a la vez (ficha, lista de un punto, línea de tiempo o
 * directo). Opaca y con tres alturas: asomada, media y completa.
 *
 * - Se arrastra con el dedo desde el asa y desde la cabecera, siguiéndolo sin saltos; al
 *   soltar se queda en la altura más cercana, teniendo en cuenta la velocidad del gesto.
 * - Un toque en el asa pasa a la siguiente altura (asomada → media → completa → media):
 *   nunca la cierra.
 * - Solo se cierra con la X o arrastrándola hacia abajo por debajo de la altura asomada.
 * - El contenido se desplaza con normalidad; arrastrar hacia abajo solo mueve la hoja cuando
 *   el contenido ya está arriba del todo.
 * - Los gestos que empiezan en la hoja no llegan al mapa.
 */
export function HojaInferior({ t, nombre, altura, onAltura, onCerrar, children, esFicha = false }: PropsHoja) {
  const hoja = useRef<HTMLElement>(null);
  const gesto = useRef<Gesto | null>(null);
  // Un arrastre con ratón termina con un clic: ese clic no debe pulsar nada más (ni la X). Solo
  // ese, y solo si llega enseguida: con el dedo no hay tal clic y nada queda pendiente.
  const clicDeArrastre = useRef<ClicDeArrastre | null>(null);
  const puntero = useRef<number | null>(null);
  const manejadores = useRef({ onAltura, onCerrar, altura });
  manejadores.current = { onAltura, onCerrar, altura };

  useEffect(() => {
    hoja.current?.focus({ preventScroll: true });
  }, [nombre]);

  // El arrastre desde el contenido va con eventos táctiles, que dejan decidir en cada
  // movimiento si el dedo desplaza el contenido o mueve la hoja.
  useEffect(() => {
    const elemento = hoja.current;
    if (elemento === null) return undefined;
    let contenido: HTMLElement | null = null;
    const alEmpezar = (evento: TouchEvent) => {
      const toque = evento.touches[0];
      if (toque === undefined || esZonaDeArrastre(evento.target)) return;
      contenido = desplazable(evento.target, elemento);
      gesto.current = nuevoGesto(toque.clientY);
    };
    const alMover = (evento: TouchEvent) => {
      const actual = gesto.current;
      const toque = evento.touches[0];
      if (actual === null || toque === undefined) return;
      const hacia = toque.clientY - actual.inicioY;
      if (!actual.arrastrando) {
        const arriba = contenido === null || contenido.scrollTop <= 0;
        // Solo hacia abajo y con el contenido arriba del todo; lo demás es desplazar.
        if (!(arriba && hacia > UMBRAL_ARRASTRE_PX)) return;
        actual.arrastrando = true;
        actual.inicioY = toque.clientY;
      }
      evento.preventDefault();
      seguir(toque.clientY);
    };
    const alTerminar = () => {
      if (gesto.current?.arrastrando === true) soltar();
      gesto.current = null;
    };
    elemento.addEventListener("touchstart", alEmpezar, { passive: true });
    elemento.addEventListener("touchmove", alMover, { passive: false });
    elemento.addEventListener("touchend", alTerminar);
    elemento.addEventListener("touchcancel", alTerminar);
    return () => {
      elemento.removeEventListener("touchstart", alEmpezar);
      elemento.removeEventListener("touchmove", alMover);
      elemento.removeEventListener("touchend", alTerminar);
      elemento.removeEventListener("touchcancel", alTerminar);
    };
    // Las funciones del gesto solo leen referencias: basta con instalarlas una vez.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Alto del hueco de la hoja: el del bloque posicionado que la contiene (el de sus %). */
  function hueco(): number {
    const contenedor = hoja.current?.offsetParent;
    return contenedor instanceof HTMLElement ? contenedor.clientHeight : 1;
  }
  function nuevoGesto(y: number): Gesto {
    const alto = hoja.current?.getBoundingClientRect().height ?? 0;
    return { inicioY: y, altoInicial: alto, arrastrando: false, muestras: [{ y, t: performance.now() }] };
  }
  function seguir(y: number) {
    const actual = gesto.current;
    const elemento = hoja.current;
    if (actual === null || elemento === null) return;
    const alto = Math.min(hueco(), Math.max(0, actual.altoInicial + actual.inicioY - y));
    elemento.style.height = `${alto}px`;
    const ahora = performance.now();
    actual.muestras = [...actual.muestras.filter((m) => ahora - m.t < VENTANA_VELOCIDAD_MS), { y, t: ahora }];
  }
  function soltar() {
    const actual = gesto.current;
    const elemento = hoja.current;
    if (actual === null || elemento === null) return;
    const alto = elemento.getBoundingClientRect().height;
    const primera = actual.muestras[0];
    const ultima = actual.muestras[actual.muestras.length - 1];
    // Velocidad en px/ms, positiva hacia arriba (la hoja crece).
    const velocidad =
      primera !== undefined && ultima !== undefined && ultima.t > primera.t
        ? (primera.y - ultima.y) / (ultima.t - primera.t)
        : 0;
    const proyectada = (alto + velocidad * PROYECCION_MS) / hueco();
    elemento.style.height = "";
    if (proyectada < ALTURAS.asomada * FRACCION_DE_CIERRE) manejadores.current.onCerrar();
    else manejadores.current.onAltura(alturaMasCercana(proyectada));
  }

  // El asa y la cabecera se arrastran con eventos de puntero (dedo o ratón).
  function alApretar(evento: PointerEvent<HTMLElement>) {
    clicDeArrastre.current = null;
    if (!esZonaDeArrastre(evento.target)) return;
    gesto.current = nuevoGesto(evento.clientY);
    puntero.current = evento.pointerId;
  }
  function alArrastrar(evento: PointerEvent<HTMLElement>) {
    const actual = gesto.current;
    if (actual === null || puntero.current !== evento.pointerId) return;
    if (!actual.arrastrando) {
      if (Math.abs(evento.clientY - actual.inicioY) <= UMBRAL_ARRASTRE_PX) return;
      actual.arrastrando = true;
      // El puntero se captura solo cuando ya es un arrastre: así el arrastre sigue aunque el
      // dedo salga del asa, y un toque sin moverse sigue pulsando el botón de debajo (la X).
      evento.currentTarget.setPointerCapture?.(evento.pointerId);
    }
    seguir(evento.clientY);
  }
  function alSoltar(evento: PointerEvent<HTMLElement>) {
    if (puntero.current !== evento.pointerId) return;
    puntero.current = null;
    if (gesto.current?.arrastrando === true) {
      if (evento.pointerType !== "touch") {
        clicDeArrastre.current = { puntero: evento.pointerId, hasta: performance.now() + MARGEN_CLIC_DE_ARRASTRE_MS };
      }
      soltar();
    }
    gesto.current = null;
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
    // La hoja escucha el arrastre de su asa y su cabecera; los controles de dentro siguen
    // siendo botones con su teclado.
    <aside
      ref={hoja}
      tabIndex={-1}
      aria-label={nombre}
      data-ficha={esFicha ? "" : undefined}
      data-altura={altura}
      onPointerDown={alApretar}
      onPointerMove={alArrastrar}
      onPointerUp={alSoltar}
      onPointerCancel={alSoltar}
      onClickCapture={(evento) => {
        const pendiente = clicDeArrastre.current;
        clicDeArrastre.current = null;
        // El clic es un PointerEvent en los navegadores actuales; si no, basta el margen.
        const id = "pointerId" in evento.nativeEvent ? Number(evento.nativeEvent.pointerId) : undefined;
        if (!esClicDeArrastre(pendiente, id, performance.now())) return;
        evento.preventDefault();
        evento.stopPropagation();
      }}
      className={`absolute inset-x-0 bottom-0 z-30 flex flex-col border-t border-linea bg-panel-solido pb-[env(safe-area-inset-bottom)] shadow-panel outline-none ${clasesAltura[altura]}`}
    >
      <button
        type="button"
        data-arrastre=""
        className="flex min-h-11 w-full shrink-0 cursor-ns-resize touch-none items-center justify-center"
        aria-label={t.hoja.altura(t.hoja.alturas[altura])}
        onClick={() => onAltura(siguienteAltura(altura))}
        onKeyDown={tecla}
      >
        <span aria-hidden="true" className="h-1 w-10 rounded-full bg-secundario" />
      </button>
      <div className="flex min-h-0 flex-1 flex-col overscroll-contain">{children}</div>
    </aside>
  );
}

/** El asa y lo marcado como cabecera de la hoja (data-arrastre) arrastran la hoja. */
function esZonaDeArrastre(objetivo: EventTarget | null): boolean {
  return objetivo instanceof Element && objetivo.closest("[data-arrastre]") !== null;
}
