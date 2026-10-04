import { useRef } from "react";
import type { ReactNode } from "react";

import type { EventoResumen, IncidenteResumen } from "../datos/tipos.ts";
import { fecha as fechaCorta } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { Simbolo } from "./Simbolo.tsx";

const MS_POR_MINUTO = 60_000;
/** Eventos que se muestran: el feed es lo último, no el archivo entero. */
export const EVENTOS_EN_FEED = 60;

export type Pestana = "directo" | "lista";

interface Props {
  t: Textos;
  idioma: Idioma;
  pestana: Pestana;
  onPestana: (pestana: Pestana) => void;
  /** Eventos que pasan los filtros, del más reciente al más antiguo. */
  eventos: readonly EventoResumen[];
  porId: ReadonlyMap<string, IncidenteResumen>;
  novedades: ReadonlySet<string>;
  ahora: Date | null;
  onAbrir: (id: string) => void;
  onCerrar: () => void;
  /** Contenido de la pestaña de lista. */
  lista: ReactNode;
  /** Dentro de la hoja inferior del teléfono, que ya pone el marco y el nombre. */
  enHoja?: boolean;
}

/** «hace 12 min», «hace 3 h», «hace 2 días» o la fecha si es más antiguo. */
function clave(evento: EventoResumen): string {
  return `${evento.id}-${evento.fecha}-${evento.estado}`;
}

export function haceCuanto(t: Textos, instante: string, ahora: Date): string {
  const minutos = Math.max(0, Math.floor((ahora.getTime() - new Date(instante).getTime()) / MS_POR_MINUTO));
  return t.relativo(minutos, fechaCorta(new Date(instante)));
}

/**
 * Panel en directo: los incidentes nuevos, los cambios de estado y las confirmaciones, del
 * historial de estados de los datos publicados. Al pulsar una entrada, el mapa vuela al
 * incidente y abre su ficha. Una segunda pestaña lista los incidentes del periodo.
 */
export function Feed({
  t,
  idioma,
  pestana,
  onPestana,
  eventos,
  porId,
  novedades,
  ahora,
  onAbrir,
  onCerrar,
  lista,
  enHoja = false,
}: Props) {
  const visibles = eventos.slice(0, EVENTOS_EN_FEED);
  // Al abrir el panel, lo que ya había sale sin más; solo aparece suavemente lo que llega
  // con el panel abierto.
  const iniciales = useRef<ReadonlySet<string> | null>(null);
  iniciales.current ??= new Set(visibles.map(clave));
  return (
    <aside
      aria-label={enHoja ? undefined : t.feed.titulo}
      className={enHoja ? "flex min-h-0 flex-1 flex-col" : "flotante flex h-full w-[21rem] max-w-[calc(100vw-1.5rem)] flex-col"}
    >
      <div className="flex items-center gap-1 border-b border-linea px-2 py-1.5">
        <div role="tablist" aria-label={t.feed.titulo} className="mr-auto flex gap-1">
          {(["directo", "lista"] as const).map((opcion) => (
            <button
              key={opcion}
              type="button"
              role="tab"
              aria-selected={pestana === opcion}
              className="control min-h-7 text-xs"
              onClick={() => onPestana(opcion)}
            >
              {opcion === "directo" ? t.feed.enDirecto : t.feed.lista}
            </button>
          ))}
        </div>
        <button type="button" className="control min-h-7 px-2 text-xs" aria-label={t.feed.cerrar} onClick={onCerrar}>
          <span aria-hidden="true">✕</span>
        </button>
      </div>
      <div role="tabpanel" className="flex-1 overflow-y-auto px-2 py-1">
        {pestana === "lista" ? (
          lista
        ) : visibles.length === 0 ? (
          <p className="p-2 text-secundario">{t.feed.vacio}</p>
        ) : (
          <ol>
            {visibles.map((evento) => {
              const incidente = porId.get(evento.id);
              if (incidente === undefined) return null;
              return (
                <li
                  key={clave(evento)}
                  className={iniciales.current?.has(clave(evento)) ? undefined : "animate-aparecer"}
                >
                  <button
                    type="button"
                    className="flex w-full cursor-pointer items-start gap-2 rounded-sm px-2 py-2 text-left hover:bg-elevado"
                    data-id={evento.id}
                    onClick={() => onAbrir(evento.id)}
                  >
                    <Simbolo estado={evento.estado} className="mt-0.5 shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline gap-2 text-xs text-secundario">
                        <span className={novedades.has(evento.id) ? "text-acento" : ""}>
                          {evento.nuevo
                            ? evento.estado === "notificado"
                              ? t.feed.nuevo
                              : t.feed.nuevoYa(t.estado[evento.estado])
                            : t.feed.paso(t.estado[evento.estado])}
                        </span>
                        {ahora !== null && (
                          <time dateTime={evento.fecha} className="ml-auto shrink-0">
                            {haceCuanto(t, evento.fecha, ahora)}
                          </time>
                        )}
                      </span>
                      <span className="block leading-snug">{incidente.titulo[idioma]}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </aside>
  );
}
