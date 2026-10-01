import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import type { Carga } from "../datos/carga.ts";
import type { Textos } from "../i18n/index.ts";

/** Tiempo que se muestra el resultado de copiar el enlace antes de volver al texto normal. */
const MS_AVISO_COPIA = 2500;

interface PropsCabecera {
  t: Textos;
  etiqueta: ReactNode;
  /** Dirección propia de la ficha; sin ella no hay botón de copiar enlace. */
  enlace?: string;
  onCerrar: () => void;
}

/** Cabecera de una ficha: qué es, copiar su enlace y cerrarla. */
export function CabeceraFicha({ t, etiqueta, enlace, onCerrar }: PropsCabecera) {
  const [copia, setCopia] = useState<"bien" | "mal" | null>(null);

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
    // En la hoja del teléfono, la cabecera también arrastra la hoja (data-arrastre).
    <div data-arrastre="" className="flex touch-none items-center gap-1 border-b border-linea px-4 py-1.5">
      <div className="rotulo mr-auto flex items-center gap-2">{etiqueta}</div>
      {enlace !== undefined && (
        <button type="button" className="control min-h-7 text-xs" onClick={() => void copiar(enlace)}>
          {copia === null
            ? t.ficha.copiarEnlace
            : copia === "bien"
              ? t.ficha.enlaceCopiado
              : t.ficha.enlaceNoCopiado}
        </button>
      )}
      <button
        type="button"
        className="control min-h-7 px-2 text-xs"
        aria-label={t.ficha.cerrar}
        onClick={onCerrar}
      >
        <span aria-hidden="true">✕</span>
      </button>
      <span className="sr-only" role="status">
        {copia === "bien" ? t.ficha.enlaceCopiado : copia === "mal" ? t.ficha.enlaceNoCopiado : ""}
      </span>
    </div>
  );
}

interface PropsEstadoCarga<T> {
  t: Textos;
  carga: Carga<T>;
  children: (datos: T) => ReactNode;
}

/** Contenido de una ficha que depende de un fichero: si no valida, se dice y no se pinta. */
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
    <div className="grid grid-cols-[6.5rem_1fr] gap-x-3 border-b border-linea/70 py-2 last:border-b-0">
      <dt className="rotulo pt-0.5">{nombre}</dt>
      <dd className="min-w-0 break-words text-texto">{children}</dd>
    </div>
  );
}
