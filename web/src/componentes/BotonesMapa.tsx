// Botones pequeños sobre el mapa: «Filtros» (con el periodo escrito y una equis cuando no es
// todo) y «Europa ahora» (con un número o un punto cuando hay algo en curso). Lo que abren es
// un desplegable en el escritorio y una hoja inferior en el teléfono: nada queda fijo sobre
// el mapa hasta que se pide.

import { useEffect, useId, useRef } from "react";
import type { ReactNode, RefObject } from "react";

import type { Textos } from "../i18n/index.ts";

const CLASE_BOTON = "control flotante min-h-11 px-3 text-xs text-texto esc:min-h-8 esc:px-2.5";

export function BotonFiltros({
  t,
  cuantos,
  periodo,
  abierto,
  onAbrir,
  onTodo,
  referencia,
}: {
  t: Textos;
  /** Filtros de estado, tipo y país puestos. */
  cuantos: number;
  /** El periodo escrito si no es el de por defecto (todo). */
  periodo: string | null;
  abierto: boolean;
  onAbrir: () => void;
  /** Vuelve al periodo por defecto. */
  onTodo: () => void;
  referencia?: RefObject<HTMLButtonElement | null> | undefined;
}) {
  return (
    <span className="inline-flex items-stretch" data-boton-filtros="">
      <button
        ref={referencia}
        type="button"
        className={`${CLASE_BOTON} ${periodo === null ? "" : "rounded-r-none"}`}
        aria-haspopup="dialog"
        aria-expanded={abierto}
        aria-label={[t.filtros.abrir, periodo, cuantos > 0 ? t.filtros.activos(cuantos) : null]
          .filter((parte) => parte !== null)
          .join(" · ")}
        onClick={onAbrir}
      >
        {t.filtros.titulo}
        {cuantos > 0 && <span className="mono ml-1 text-secundario">{cuantos}</span>}
        {periodo !== null && (
          <span className="ml-1.5 text-secundario" data-periodo-escrito="">
            · {periodo}
          </span>
        )}
      </button>
      {periodo !== null && (
        <button
          type="button"
          className={`${CLASE_BOTON} rounded-l-none border-l border-linea px-2`}
          aria-label={t.filtros.volverATodo(periodo)}
          data-volver-a-todo=""
          onClick={onTodo}
        >
          <span aria-hidden="true">✕</span>
        </button>
      )}
    </span>
  );
}

export function BotonAhora({
  t,
  abierto,
  onAbrir,
  cierres,
  novedades,
  referencia,
}: {
  t: Textos;
  abierto: boolean;
  onAbrir: () => void;
  /** Cierres de aeropuerto en curso (posibles o confirmados). */
  cierres: number;
  /** Novedades desde la última visita que el visitante aún no ha visto. */
  novedades: number;
  referencia?: RefObject<HTMLButtonElement | null> | undefined;
}) {
  const aviso =
    cierres > 0 ? t.ahora.avisoCierres(cierres) : novedades > 0 ? t.ahora.avisoNovedades(novedades) : null;
  return (
    <button
      ref={referencia}
      type="button"
      className={`${CLASE_BOTON} relative`}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      aria-label={aviso === null ? t.ahora.etiqueta : `${t.ahora.etiqueta} · ${aviso}`}
      data-boton-ahora=""
      onClick={onAbrir}
    >
      {t.ahora.etiqueta}
      {cierres > 0 ? (
        <span
          aria-hidden="true"
          data-indicador="numero"
          className="mono ml-1.5 inline-flex min-w-4 items-center justify-center rounded-full bg-notificado px-1 text-[0.65rem] leading-4 text-fondo"
        >
          {cierres}
        </span>
      ) : (
        novedades > 0 && (
          <span aria-hidden="true" data-indicador="punto" className="ml-1.5 size-2 rounded-full bg-acento" />
        )
      )}
    </button>
  );
}

/**
 * Desplegable bajo un botón (escritorio): se cierra con la equis, con Escape, pulsando fuera o
 * con el mismo botón. Al abrirse lleva el foco dentro; al cerrarse con Escape o la equis, lo
 * devuelve al botón.
 */
export function Desplegable({
  t,
  titulo,
  onCerrar,
  boton,
  children,
  cerrar,
}: {
  t: Textos;
  titulo: string;
  onCerrar: () => void;
  /** El botón que lo abre: pulsarlo no cuenta como «fuera». */
  boton: RefObject<HTMLButtonElement | null>;
  children: ReactNode;
  /** Texto de la equis. */
  cerrar: string;
}) {
  const caja = useRef<HTMLDivElement>(null);
  const idTitulo = useId();
  const cerrarRef = useRef(onCerrar);
  cerrarRef.current = onCerrar;

  useEffect(() => {
    caja.current?.focus({ preventScroll: true });
    const alPulsar = (evento: PointerEvent) => {
      const objetivo = evento.target as Node | null;
      if (objetivo === null) return;
      if (caja.current?.contains(objetivo) || boton.current?.contains(objetivo)) return;
      cerrarRef.current();
    };
    const alTeclear = (evento: KeyboardEvent) => {
      if (evento.key !== "Escape") return;
      evento.preventDefault();
      evento.stopPropagation();
      cerrarRef.current();
      boton.current?.focus();
    };
    document.addEventListener("pointerdown", alPulsar);
    document.addEventListener("keydown", alTeclear, true);
    return () => {
      document.removeEventListener("pointerdown", alPulsar);
      document.removeEventListener("keydown", alTeclear, true);
    };
  }, [boton]);

  return (
    <div
      ref={caja}
      role="dialog"
      aria-labelledby={idTitulo}
      tabIndex={-1}
      data-desplegable=""
      className="flotante absolute left-0 top-full z-30 mt-1.5 max-h-[70vh] w-[22rem] overflow-y-auto p-3 outline-none"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 id={idTitulo} className="rotulo">
          {titulo}
        </h2>
        <button
          type="button"
          className="control px-2 text-xs"
          aria-label={cerrar}
          onClick={() => {
            onCerrar();
            boton.current?.focus();
          }}
        >
          <span aria-hidden="true">✕</span>
        </button>
      </div>
      {children}
      <span className="sr-only">{t.desplegable.escape}</span>
    </div>
  );
}
