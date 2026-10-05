import type { IncidenteResumen } from "../datos/tipos.ts";
import { fechaDia, textoAtribuido } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { Simbolo } from "./Simbolo.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  /** Incidentes que comparten punto, del más grave al menos. */
  incidentes: readonly IncidenteResumen[];
  /** Antes de abrir el elegido: la pila sale de un punto del mapa, que ya está a la vista. */
  alElegir?: (id: string) => void;
}

/** Varios incidentes en el mismo sitio: se elige cuál abrir. */
export function SelectorPila({ t, idioma, incidentes, alElegir }: Props) {
  return (
    <div className="overflow-y-auto px-4 py-3">
      {/* El título ya va en la cabecera del panel: aquí solo para los lectores de pantalla. */}
      <h2 className="sr-only">{t.pila.titulo(incidentes.length)}</h2>
      <ul className="mt-2">
        {incidentes.map((incidente) => (
          <li key={incidente.id} className="border-b border-linea/70 last:border-b-0">
            <Enlace
              a={rutaDeFicha(incidente.id, idioma)}
              onClick={() => alElegir?.(incidente.id)}
              className="flex items-start gap-2 rounded-sm px-1 py-2 hover:bg-elevado"
            >
              <Simbolo estado={incidente.estado} atribucion={incidente.atribucion} className="mt-0.5 shrink-0" />
              <span className="min-w-0">
                <span className="block leading-snug">{incidente.titulo[idioma]}</span>
                <span className="mono block text-xs text-secundario">
                  {fechaDia(incidente.dia)} · {incidente.estado === "atribuido"
                    ? textoAtribuido(t, idioma, incidente.atribucion)
                    : t.estado[incidente.estado]}
                </span>
              </span>
            </Enlace>
          </li>
        ))}
      </ul>
    </div>
  );
}
