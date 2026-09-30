import { ESTADOS, TIPOS } from "../datos/vocabulario.ts";
import type { Textos } from "../i18n/index.ts";
import { ESCALA_UCRANIA, PALETA } from "../paleta.ts";
import type { Capas } from "./SelectorCapas.tsx";
import { Simbolo } from "./Simbolo.tsx";

const LADO_MUESTRA = 12;

interface Props {
  t: Textos;
  capas: Capas;
}

/** Leyenda del mapa: forma por tipo y color por estado, siempre con su texto. */
export function Leyenda({ t, capas }: Props) {
  return (
    <details className="panel max-w-56 p-2 text-xs" open>
      <summary className="etiqueta cursor-pointer text-[0.625rem]">{t.leyenda.titulo}</summary>
      {capas.incidentes && (
        <div className="mt-2 flex flex-col gap-2">
          <div>
            <p className="text-secundario">{t.leyenda.forma}</p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {TIPOS.map((tipo) => (
                <li key={tipo} className="flex items-center gap-2">
                  <Simbolo tipo={tipo} estado="notificado" />
                  {t.tipo[tipo]}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-secundario">{t.leyenda.color}</p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {ESTADOS.map((estado) => (
                <li key={estado} className="flex items-center gap-2">
                  <Simbolo tipo="interrupcion_aeroportuaria" estado={estado} />
                  {t.estado[estado]}
                </li>
              ))}
            </ul>
          </div>
          <ul className="flex flex-col gap-0.5 text-secundario">
            <li>{t.leyenda.precision}</li>
            <li>{t.leyenda.episodio}</li>
            <li>{t.leyenda.agrupacion}</li>
          </ul>
        </div>
      )}
      {capas.ucrania && (
        <div className="mt-2">
          <p className="text-secundario">{t.leyenda.ucrania}</p>
          <div className="mt-1 flex items-center gap-2">
            <span>{t.leyenda.menos}</span>
            <svg
              width={LADO_MUESTRA * ESCALA_UCRANIA.length}
              height={LADO_MUESTRA}
              aria-hidden="true"
              focusable="false"
            >
              {ESCALA_UCRANIA.map((opacidad, i) => (
                <rect
                  key={opacidad}
                  x={i * LADO_MUESTRA}
                  width={LADO_MUESTRA}
                  height={LADO_MUESTRA}
                  fill={PALETA.atribuido}
                  fillOpacity={opacidad}
                />
              ))}
            </svg>
            <span>{t.leyenda.mas}</span>
          </div>
        </div>
      )}
      {capas.densidad && <p className="mt-2 text-secundario">{t.leyenda.densidad}</p>}
    </details>
  );
}
