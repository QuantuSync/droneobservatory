import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { Carga } from "../datos/carga.ts";
import type { Textos } from "../i18n/index.ts";

/** Tiempo que se muestra el resultado de copiar el enlace antes de volver al texto normal. */
const MS_AVISO_COPIA = 2500;

interface Props {
  t: Textos;
  /** Etiqueta técnica de la cabecera del panel. */
  etiqueta: ReactNode;
  /** Nombre accesible del panel. */
  nombre: string;
  /** Dirección propia de la ficha; sin ella no hay botón de copiar enlace. */
  enlace?: string;
  onCerrar: () => void;
  children: ReactNode;
}

/**
 * Panel lateral: a la derecha en escritorio y como panel inferior en móvil. Al abrirse
 * recibe el foco para que el teclado y el lector de pantalla entren en él.
 */
export function Panel({ t, etiqueta, nombre, enlace, onCerrar, children }: Props) {
  const raiz = useRef<HTMLElement>(null);
  const [copia, setCopia] = useState<"bien" | "mal" | null>(null);

  useEffect(() => {
    raiz.current?.focus({ preventScroll: true });
  }, [nombre]);

  // Escape cierra el panel, salvo que haya un diálogo abierto por encima (la metodología).
  useEffect(() => {
    function alPulsar(evento: KeyboardEvent) {
      if (evento.key === "Escape" && document.querySelector("dialog[open]") === null) onCerrar();
    }
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, [onCerrar]);

  useEffect(() => {
    if (copia === null) return undefined;
    const temporizador = window.setTimeout(() => setCopia(null), MS_AVISO_COPIA);
    return () => window.clearTimeout(temporizador);
  }, [copia]);

  async function copiar(direccion: string) {
    try {
      await navigator.clipboard.writeText(direccion);
      setCopia("bien");
    } catch {
      setCopia("mal");
    }
  }

  return (
    <aside
      ref={raiz}
      tabIndex={-1}
      aria-label={nombre}
      className="absolute inset-x-0 bottom-0 z-20 flex max-h-[62%] flex-col border-t border-borde bg-superficie-1 outline-none md:static md:max-h-none md:w-[26rem] md:shrink-0 md:border-l md:border-t-0"
    >
      <div className="flex items-center gap-2 border-b border-borde px-4 py-2">
        <div className="etiqueta mr-auto flex items-center gap-2">{etiqueta}</div>
        {enlace !== undefined && (
          <button
            type="button"
            className="boton boton-discreto min-h-7 text-xs"
            onClick={() => void copiar(enlace)}
          >
            {copia === null
              ? t.ficha.copiarEnlace
              : copia === "bien"
                ? t.ficha.enlaceCopiado
                : t.ficha.enlaceNoCopiado}
          </button>
        )}
        <button
          type="button"
          className="boton boton-discreto min-h-7 px-2 text-xs"
          aria-label={t.ficha.cerrar}
          onClick={onCerrar}
        >
          <span aria-hidden="true">✕</span>
        </button>
        <span className="sr-only" role="status">
          {copia === "bien" ? t.ficha.enlaceCopiado : copia === "mal" ? t.ficha.enlaceNoCopiado : ""}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3">{children}</div>
    </aside>
  );
}

interface PropsEstadoCarga<T> {
  t: Textos;
  carga: Carga<T>;
  children: (datos: T) => ReactNode;
}

/** Contenido de un panel que depende de un fichero: si no valida, se dice y no se pinta. */
export function SegunCarga<T>({ t, carga, children }: PropsEstadoCarga<T>) {
  switch (carga.estado) {
    case "listo":
      return <>{children(carga.datos)}</>;
    case "cargando":
      return <p className="text-secundario">{t.avisos.cargando}</p>;
    case "no_encontrado":
      return <p role="alert">{t.avisos.fichaNoEncontrada}</p>;
    case "no_valido":
      return <p role="alert">{t.avisos.fichaNoValida}</p>;
    case "no_disponible":
      return <p role="alert">{t.avisos.datosNoDisponibles}</p>;
  }
}

/** Fila de datos de una ficha. */
export function Fila({ nombre, children }: { nombre: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-x-3 border-b border-linea py-2">
      <dt className="etiqueta pt-0.5 text-[0.625rem]">{nombre}</dt>
      <dd className="min-w-0 break-words text-texto">{children}</dd>
    </div>
  );
}
