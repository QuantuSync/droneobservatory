import type { Textos } from "../i18n/index.ts";

interface Props {
  t: Textos;
  /** Incidentes con novedades desde la visita anterior, del más reciente al más antiguo. */
  incidentes: readonly string[];
  /** Posición al recorrerlas; null si aún no se ha empezado. */
  posicion: number | null;
  onIr: (posicion: number) => void;
  onDescartar: () => void;
}

/** Aviso breve de lo que ha cambiado desde la visita anterior, con la opción de recorrerlo. */
export function AvisoNovedades({ t, incidentes, posicion, onIr, onDescartar }: Props) {
  const n = incidentes.length;
  if (n === 0) return null;
  return (
    <div role="status" className="animate-aparecer flex flex-wrap items-center gap-1 text-xs">
      <span aria-hidden="true" className="size-2 rounded-full bg-acento" />
      <span className="mr-2">{t.novedades.aviso(n)}</span>
      {posicion === null ? (
        <button type="button" className="control control-principal min-h-7 text-xs" onClick={() => onIr(0)}>
          {t.novedades.recorrer}
        </button>
      ) : (
        <>
          <button
            type="button"
            className="control min-h-7 text-xs"
            disabled={posicion === 0}
            onClick={() => onIr(posicion - 1)}
          >
            {t.novedades.anterior}
          </button>
          <span className="text-secundario">{t.novedades.posicion(posicion + 1, n)}</span>
          <button
            type="button"
            className="control min-h-7 text-xs"
            disabled={posicion >= n - 1}
            onClick={() => onIr(posicion + 1)}
          >
            {t.novedades.siguiente}
          </button>
        </>
      )}
      <button type="button" className="control min-h-7 text-xs text-secundario" onClick={onDescartar}>
        {t.novedades.descartar}
      </button>
    </div>
  );
}
