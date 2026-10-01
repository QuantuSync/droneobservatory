import { useState } from "react";

import type { Estado, Fuente, PasoHistorial, Tipo } from "../datos/tipos.ts";
import { instante } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Simbolo } from "./Simbolo.tsx";

/** Fuentes que se muestran antes de pedir «ver más»: algunos incidentes tienen cientos. */
export const FUENTES_VISIBLES = 5;

/** Las declaraciones oficiales que cita una noticia llevan esta marca en su identificador. */
const MARCA_DECLARACION = "-declaracion-";

export function esDeclaracionOficial(fuente: Fuente): boolean {
  return fuente.id.includes(MARCA_DECLARACION);
}

/** Primero las fuentes más fiables; a igual fiabilidad, las más antiguas. */
export function ordenarFuentes(fuentes: readonly Fuente[]): Fuente[] {
  return fuentes
    .slice()
    .sort(
      (a, b) =>
        a.fiabilidad.localeCompare(b.fiabilidad) ||
        a.fecha.valor.localeCompare(b.fecha.valor) ||
        a.id.localeCompare(b.id),
    );
}

function FichaFuente({ t, fuente }: { t: Textos; fuente: Fuente }) {
  const codigo = `${fuente.fiabilidad}${fuente.credibilidad}`;
  return (
    <li className="border-b border-linea py-2">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <EnlaceExterno
          enlace={fuente.enlace}
          aviso={t.ficha.enlaceExterno}
          avisoNoValido={t.ficha.enlaceNoValido}
          className="font-medium"
        >
          {fuente.medio}
        </EnlaceExterno>
        <span className="mono rounded-sm border border-linea px-1 text-xs text-acento">
          <span className="sr-only">{t.ficha.codigo(codigo)}</span>
          <span aria-hidden="true" title={t.ficha.codigo(codigo)}>
            {codigo}
          </span>
        </span>
        <span className="mono text-xs text-secundario">{instante(fuente.fecha)}</span>
      </div>
      {esDeclaracionOficial(fuente) && (
        <p className="rotulo mt-1 text-xs">{t.ficha.declaracionOficial}</p>
      )}
      <blockquote lang={fuente.idioma} className="mt-1 border-l border-acento pl-2 text-secundario">
        {fuente.frase_origen}
      </blockquote>
      {fuente.replicas > 0 && (
        <p className="mono mt-1 text-xs text-secundario">{t.ficha.replicas(fuente.replicas)}</p>
      )}
    </li>
  );
}

export function ListaFuentes({ t, fuentes }: { t: Textos; fuentes: readonly Fuente[] }) {
  const [todas, setTodas] = useState(false);
  const ordenadas = ordenarFuentes(fuentes);
  const visibles = todas ? ordenadas : ordenadas.slice(0, FUENTES_VISIBLES);
  const ocultas = ordenadas.length - FUENTES_VISIBLES;
  return (
    <section className="mt-4">
      <h3 className="rotulo">{t.ficha.fuentes(fuentes.length)}</h3>
      <ul>
        {visibles.map((fuente) => (
          <FichaFuente key={fuente.id} t={t} fuente={fuente} />
        ))}
      </ul>
      {ocultas > 0 && (
        <button
          type="button"
          className="control mt-2 min-h-7 text-xs"
          aria-expanded={todas}
          onClick={() => setTodas(!todas)}
        >
          {todas ? t.ficha.menosFuentes : t.ficha.masFuentes(ocultas)}
        </button>
      )}
    </section>
  );
}

interface PropsHistorial {
  t: Textos;
  historial: readonly PasoHistorial[];
  fuentes: readonly Fuente[];
  /** Forma con la que se dibuja el estado: la del tipo del incidente. */
  tipo: Tipo;
}

export function Historial({ t, historial, fuentes, tipo }: PropsHistorial) {
  const medios = new Map(fuentes.map((fuente) => [fuente.id, fuente.medio]));
  return (
    <section className="mt-4">
      <h3 className="rotulo">{t.ficha.historial}</h3>
      <ol className="mt-1">
        {historial.map((paso, i) => (
          <li key={i} className="flex flex-wrap items-center gap-x-2 border-b border-linea py-1.5">
            <EstadoConTexto t={t} tipo={tipo} estado={paso.estado} />
            <span className="mono text-xs text-secundario">{instante(paso.fecha)}</span>
            <span className="w-full text-xs text-secundario">
              {paso.fuente_id === undefined
                ? t.ficha.fuenteNoPublica
                : (medios.get(paso.fuente_id) ?? paso.fuente_id)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** El estado, siempre con su símbolo y su nombre: nunca solo con color. */
export function EstadoConTexto({ t, tipo, estado }: { t: Textos; tipo: Tipo; estado: Estado }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Simbolo tipo={tipo} estado={estado} />
      {t.estado[estado]}
    </span>
  );
}
