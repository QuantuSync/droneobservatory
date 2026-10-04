import type { Textos } from "../i18n/index.ts";

/**
 * Las novedades desde la visita anterior, como primera línea de «Europa ahora»: cuántas hay,
 * «Verlas» (abre la primera y permite recorrerlas) y «Descartar». Sobre el mapa solo queda el
 * número en el botón «Europa ahora»: nada fijo encima de los botones.
 */
export function LineaNovedades({
  t,
  cuantas,
  onVer,
  onDescartar,
}: {
  t: Textos;
  cuantas: number;
  onVer: () => void;
  onDescartar: () => void;
}) {
  if (cuantas === 0) return null;
  return (
    <div
      role="status"
      data-novedades=""
      className="mb-2 flex flex-wrap items-center gap-x-1 gap-y-1 border-b border-linea pb-2 text-sm"
    >
      <span aria-hidden="true" className="ml-1 size-2 shrink-0 rounded-full bg-acento" />
      <span className="mr-auto min-w-0 px-1 text-texto">{t.novedades.aviso(cuantas)}</span>
      <span className="flex gap-1">
        <button type="button" className="control control-principal min-h-9 text-xs" onClick={onVer}>
          {t.novedades.recorrer}
        </button>
        <button type="button" className="control min-h-9 text-xs" onClick={onDescartar}>
          {t.novedades.descartar}
        </button>
      </span>
    </div>
  );
}

/**
 * Recorrido de las novedades dentro de la ficha abierta: la posición y los pasos anterior y
 * siguiente. Va en la ficha (el panel lateral o la hoja inferior), no sobre el mapa.
 */
export function RecorridoNovedades({
  t,
  posicion,
  total,
  onIr,
}: {
  t: Textos;
  posicion: number;
  total: number;
  onIr: (posicion: number) => void;
}) {
  return (
    <nav
      aria-label={t.novedades.recorrido}
      data-recorrido=""
      className="flex items-center gap-1 border-b border-linea px-3 py-1 text-xs"
    >
      <span className="mr-auto text-secundario">{t.novedades.posicion(posicion + 1, total)}</span>
      <button
        type="button"
        className="control min-h-7 text-xs"
        disabled={posicion === 0}
        onClick={() => onIr(posicion - 1)}
      >
        {t.novedades.anterior}
      </button>
      <button
        type="button"
        className="control min-h-7 text-xs"
        disabled={posicion >= total - 1}
        onClick={() => onIr(posicion + 1)}
      >
        {t.novedades.siguiente}
      </button>
    </nav>
  );
}
