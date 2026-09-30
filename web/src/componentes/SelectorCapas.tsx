import type { Textos } from "../i18n/index.ts";

export interface Capas {
  incidentes: boolean;
  ucrania: boolean;
  densidad: boolean;
}

export const CAPAS_INICIALES: Capas = { incidentes: true, ucrania: false, densidad: false };

const ORDEN: readonly (keyof Capas)[] = ["incidentes", "ucrania", "densidad"];

interface Props {
  t: Textos;
  capas: Capas;
  onCambio: (capas: Capas) => void;
  listaAbierta: boolean;
  onLista: () => void;
}

/** Selector de capas del mapa y acceso a la lista de incidentes, que no necesita el mapa. */
export function SelectorCapas({ t, capas, onCambio, listaAbierta, onLista }: Props) {
  return (
    <div className="panel flex flex-col gap-1 p-2">
      <fieldset className="flex flex-col gap-0.5">
        <legend className="etiqueta mb-1 text-[0.625rem]">{t.capas.titulo}</legend>
        {ORDEN.map((capa) => (
          <label key={capa} className="flex min-h-6 cursor-pointer items-center gap-2 text-xs text-texto">
            <input
              type="checkbox"
              className="size-4 accent-dorado"
              checked={capas[capa]}
              onChange={(evento) => onCambio({ ...capas, [capa]: evento.target.checked })}
            />
            {t.capas[capa]}
          </label>
        ))}
      </fieldset>
      <button
        type="button"
        className="boton boton-discreto mt-1 min-h-7 text-xs"
        aria-pressed={listaAbierta}
        onClick={onLista}
      >
        {t.capas.lista}
      </button>
    </div>
  );
}
