import { NIVELES_GNSS, OPACIDAD_GNSS } from "../datos/gnss.ts";
import type { NivelGnss } from "../datos/gnss.ts";
import { ESCALA_PRESION } from "../datos/presion.ts";
import type { Textos } from "../i18n/index.ts";
import { PALETA } from "../paleta.ts";

/** Color de muestra de cada nivel, como lo pinta el mapa (gris según la proporción; alto, alerta). */
export const MUESTRA_GNSS: Record<NivelGnss, string> = {
  sin: "#333e51",
  media: "#98a0ad",
  alta: PALETA.atribuido,
};

/** Estado de la capa de interferencia para el periodo elegido. */
export type EstadoGnss = "cargando" | "sin_datos" | { dias: number };

function Muestra({ color, opacidad }: { color: string; opacidad: number }) {
  return (
    <svg aria-hidden="true" width="14" height="10" viewBox="0 0 14 10">
      <rect x="0.5" y="0.5" width="13" height="9" fill={color} fillOpacity={opacidad} stroke={PALETA.linea} />
    </svg>
  );
}

export function LeyendaGnss({ t, estado }: { t: Textos; estado: EstadoGnss }) {
  const g = t.gnss;
  return (
    <div className="flotante px-2.5 py-1.5 text-xs" data-leyenda="gnss">
      <p className="font-medium text-texto">{g.etiqueta}</p>
      <p className="text-secundario">{g.leyenda}</p>
      <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        {NIVELES_GNSS.map((nivel) => (
          <li key={nivel} className="flex items-center gap-1.5">
            <Muestra color={MUESTRA_GNSS[nivel]} opacidad={OPACIDAD_GNSS} />
            <span className="text-secundario">{g.niveles[nivel]}</span>
          </li>
        ))}
      </ul>
      <p className="mt-0.5 text-secundario" role="status">
        {estado === "cargando" ? g.cargando : estado === "sin_datos" ? g.sinDatos : g.dias(estado.dias)}
      </p>
    </div>
  );
}

export function LeyendaPresion({ t }: { t: Textos }) {
  const p = t.presion;
  return (
    <div className="flotante px-2.5 py-1.5 text-xs" data-leyenda="presion">
      <p className="font-medium text-texto">{t.controles.presion}</p>
      <p className="text-secundario">{p.leyenda}</p>
      <div className="mt-1 flex items-center gap-1.5 text-secundario">
        <span>{p.menos}</span>
        <span className="flex">
          {ESCALA_PRESION.map((opacidad) => (
            <Muestra key={opacidad} color={PALETA.texto} opacidad={opacidad} />
          ))}
        </span>
        <span>{p.mas}</span>
      </div>
    </div>
  );
}
