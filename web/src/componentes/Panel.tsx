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
  /** Texto de la equis; por defecto, «Cerrar la ficha». */
  cerrar?: string;
}

/** Cabecera de una ficha: qué es, copiar su enlace y cerrarla. */
export function CabeceraFicha({ t, etiqueta, enlace, onCerrar, cerrar }: PropsCabecera) {
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
        className="control min-h-11 min-w-11 px-2 text-xs esc:min-h-7 esc:min-w-0"
        aria-label={cerrar ?? t.ficha.cerrar}
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

/** Recarga la página: lo que hace «Reintentar» cuando la web abierta es más vieja que los datos. */
export function recargarPagina(): void {
  window.location.reload();
}

interface PropsErrorDeCarga {
  t: Textos;
  /** Qué no se ha podido cargar («No se ha podido cargar la previsión.»). */
  mensaje: string;
  /** Lo que salió del último intento. */
  estado: "no_disponible" | "no_valido" | "no_encontrado";
  /** Vuelve a pedirlo (no hace falta si el estado es «no_valido»: entonces se recarga la página). */
  onReintentar: () => void;
  className?: string;
}

/**
 * El error de una carga que no ha salido tras todos sus reintentos (datos/reintentos.ts): qué no
 * se ha podido cargar, por qué y un botón «Reintentar». Si el fichero no valida tras pedirlo de
 * nuevo, lo normal es que la web abierta sea más vieja que los datos: «Reintentar» recarga la
 * página para traer la versión nueva.
 */
export function ErrorDeCarga({ t, mensaje, estado, onReintentar, className }: PropsErrorDeCarga) {
  const motivo = estado === "no_valido" ? t.avisos.webNueva : estado === "no_disponible" ? t.avisos.sinRespuesta : null;
  return (
    <div role="alert" className={`flex flex-col items-start gap-2 ${className ?? ""}`} data-error-carga={estado}>
      <p>
        {mensaje}
        {motivo !== null && <span className="block text-xs text-secundario">{motivo}</span>}
      </p>
      <button
        type="button"
        className="control min-h-11 rounded border border-linea px-3 esc:min-h-8"
        onClick={estado === "no_valido" ? recargarPagina : onReintentar}
        data-reintentar=""
      >
        {t.avisos.reintentar}
      </button>
    </div>
  );
}

interface PropsEstadoCarga<T> {
  t: Textos;
  carga: Carga<T>;
  children: (datos: T) => ReactNode;
  /** Vuelve a pedir el fichero de la ficha. */
  onReintentar: () => void;
}

/** Contenido de una ficha que depende de un fichero: si no llega o no valida, se dice y no se pinta. */
export function SegunCarga<T>({ t, carga, children, onReintentar }: PropsEstadoCarga<T>) {
  switch (carga.estado) {
    case "listo":
      return <>{children(carga.datos)}</>;
    case "cargando":
      return <p className="text-secundario">{t.avisos.cargando}</p>;
    case "no_encontrado":
      return <p role="alert">{t.avisos.fichaNoEncontrada}</p>;
    case "no_valido":
    case "no_disponible":
      return <ErrorDeCarga t={t} mensaje={t.avisos.fichaNoDisponible} estado={carga.estado} onReintentar={onReintentar} />;
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
