import type { CeldaGnss } from "../datos/gnss.ts";
import { numero, porcentaje } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { Fila } from "./Panel.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  celda: CeldaGnss;
  /** Periodo elegido, ya escrito. */
  periodo: string;
  /** Días con datos que suma el periodo. */
  dias: number;
}

/** Una celda de interferencia GPS: proporción de aeronaves afectadas y cuántas había. */
export function FichaCelda({ t, idioma, celda, periodo, dias }: Props) {
  const g = t.gnss;
  return (
    <article data-celda={celda.h3}>
      <h2 className="text-2xl font-semibold tracking-tight">{porcentaje(celda.proporcion, idioma)}</h2>
      <p className="mt-1 text-secundario">
        {g.proporcion} · <span data-nivel-gnss={celda.nivel}>{g.niveles[celda.nivel]}</span>
      </p>
      <dl className="mt-3">
        <Fila nombre={g.aeronaves}>
          <span className="mono">{numero(celda.aeronaves, idioma)}</span>
          <span className="block text-xs text-secundario">
            <span className="mono">{numero(celda.degradadas, idioma)}</span> {g.degradadas}
          </span>
        </Fila>
        <Fila nombre={g.periodo}>
          <span className="mono">{periodo}</span>
          <span className="block text-xs text-secundario">{g.dias(dias)}</span>
        </Fila>
      </dl>
      <p className="mono mt-3 text-xs text-secundario">H3 {celda.h3}</p>
    </article>
  );
}
