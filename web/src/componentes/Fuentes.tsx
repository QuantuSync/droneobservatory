import { useState } from "react";

import { conMayuscula } from "../datos/presencia.ts";
import type { PasoDelHistorial } from "../datos/presencia.ts";
import type { AtribucionResumen, Estado, Fuente, FuenteImpacto, PasoHistorial } from "../datos/tipos.ts";
import { autoridadEscrita, medioEnFrase, medioEscrito } from "../i18n/autoridades.ts";
import { instante } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { Cita } from "./Cita.tsx";
import { EnlaceFuente } from "./EnlaceFuente.tsx";
import { Simbolo } from "./Simbolo.tsx";

/** Fuentes que se muestran antes de pedir «ver más»: algunos incidentes tienen cientos. */
export const FUENTES_VISIBLES = 5;

/** Las declaraciones oficiales que cita una noticia llevan esta marca en su identificador. */
const MARCA_DECLARACION = "-declaracion-";

export function esDeclaracionOficial(fuente: Fuente): boolean {
  return fuente.id.includes(MARCA_DECLARACION);
}

/** Primero las fuentes más fiables; a igual fiabilidad, las más antiguas. */
export function ordenarFuentes<F extends Fuente>(fuentes: readonly F[]): F[] {
  return fuentes
    .slice()
    .sort(
      (a, b) =>
        a.fiabilidad.localeCompare(b.fiabilidad) ||
        a.fecha.valor.localeCompare(b.fecha.valor) ||
        a.id.localeCompare(b.id),
    );
}

/** El nombre de una fuente en la ficha: una declaración oficial citada, con su autoridad escrita
 *  en el idioma de la web; las demás, tal cual. */
export function nombreDeFuente(t: Textos, medio: string, idioma: Idioma | undefined): string {
  return idioma === undefined ? medio : medioEscrito(medio, idioma, t.ficha.declaracionCitada);
}

/** La fuente dentro de una frase («según el Ministerio…»), en el idioma de la web. */
export function fuenteEnFrase(t: Textos, medio: string, idioma: Idioma | undefined): string {
  return idioma === undefined ? medio : medioEnFrase(medio, idioma, t.ficha.declaracionCitada);
}

/** Una autoridad en el idioma de la web, o tal cual si no se sabe el idioma. */
export function nombreDeAutoridad(autoridad: string, idioma: Idioma | undefined): string {
  return idioma === undefined ? autoridad : autoridadEscrita(autoridad, idioma);
}

function FichaFuente({ t, fuente, idioma }: { t: Textos; fuente: FuenteImpacto; idioma: Idioma | undefined }) {
  const codigo = `${fuente.fiabilidad}${fuente.credibilidad}`;
  return (
    <li className="border-b border-linea py-2">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <EnlaceFuente t={t} fuente={fuente} className="font-medium">
          {nombreDeFuente(t, fuente.medio, idioma)}
        </EnlaceFuente>
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
      {fuente.autoridad_ocupacion === true && (
        <p className="rotulo mt-1 text-xs">{t.impacto.ocupacion}</p>
      )}
      {idioma === undefined ? (
        <blockquote lang={fuente.idioma} className="mt-1 border-l border-acento pl-2 text-secundario">
          {fuente.frase_origen}
        </blockquote>
      ) : (
        <Cita
          t={t}
          idioma={idioma}
          texto={fuente.frase_origen}
          idiomaOriginal={fuente.idioma}
          traduccion={fuente.traduccion}
          comillas={false}
          className="mt-1 border-l border-acento pl-2 text-secundario"
        />
      )}
      {fuente.replicas > 0 && (
        <p className="mono mt-1 text-xs text-secundario">{t.ficha.replicas(fuente.replicas)}</p>
      )}
    </li>
  );
}

export function ListaFuentes({
  t,
  fuentes,
  idioma,
}: {
  t: Textos;
  fuentes: readonly FuenteImpacto[];
  idioma?: Idioma;
}) {
  const [todas, setTodas] = useState(false);
  const ordenadas = ordenarFuentes(fuentes);
  const visibles = todas ? ordenadas : ordenadas.slice(0, FUENTES_VISIBLES);
  const ocultas = ordenadas.length - FUENTES_VISIBLES;
  return (
    <section className="mt-4">
      <h3 className="rotulo">{t.ficha.fuentes(fuentes.length)}</h3>
      <ul>
        {visibles.map((fuente) => (
          <FichaFuente key={fuente.id} t={t} fuente={fuente} idioma={idioma} />
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
  /** La atribución del incidente: el paso a atribuido lleva su marcador. */
  atribucion?: AtribucionResumen | null;
  idioma?: Idioma;
  /**
   * El historial con los cambios de la presencia de dron entre los del estado, por fecha
   * (datos/presencia.ts, historialCompleto). Sin él, solo los del estado.
   */
  pasos?: readonly PasoDelHistorial[];
}

export function Historial({ t, historial, fuentes, atribucion = null, idioma, pasos }: PropsHistorial) {
  const medios = new Map(fuentes.map((fuente) => [fuente.id, nombreDeFuente(t, fuente.medio, idioma)]));
  const todos: readonly PasoDelHistorial[] = pasos ?? historial.map((paso) => ({ clase: "estado", paso, fecha: paso.fecha.valor }));
  return (
    <section className="mt-4">
      <h3 className="rotulo">{t.ficha.historial}</h3>
      <ol className="mt-1">
        {todos.map((entrada, i) =>
          entrada.clase === "presencia" ? (
            // Un cambio de la presencia de dron: su círculo (morado o gris relleno), su fecha y
            // quién lo declara, con el enlace a la fuente; el motivo, debajo.
            <li
              key={i}
              className="flex flex-wrap items-center gap-x-2 border-b border-linea py-1.5"
              data-historial-presencia={entrada.marca ?? "parcial"}
            >
              <span className="inline-flex items-center gap-1.5">
                {entrada.marca !== null && <Simbolo estado={entrada.marca} />}
                {entrada.rotulo}
              </span>
              <span className="mono text-xs text-secundario">{instante(entrada.paso.fecha)}</span>
              <span className="w-full text-xs text-secundario">
                {entrada.fuente === undefined ? (
                  (entrada.quien ?? t.ficha.fuenteNoPublica)
                ) : (
                  <EnlaceFuente t={t} fuente={entrada.fuente}>
                    {entrada.quien ?? medios.get(entrada.fuente.id) ?? entrada.fuente.medio}
                  </EnlaceFuente>
                )}
              </span>
              {entrada.motivo !== null && (
                <span className="w-full text-xs text-texto" data-motivo-historial="">
                  {entrada.motivo}
                </span>
              )}
            </li>
          ) : (
            <PasoDeEstado key={i} t={t} paso={entrada.paso} medios={medios} atribucion={atribucion} idioma={idioma} />
          ),
        )}
      </ol>
    </section>
  );
}

function PasoDeEstado({
  t,
  paso,
  medios,
  atribucion,
  idioma,
}: {
  t: Textos;
  paso: PasoHistorial;
  medios: ReadonlyMap<string, string>;
  atribucion: AtribucionResumen | null;
  idioma: Idioma | undefined;
}) {
  return (
          <li className="flex flex-wrap items-center gap-x-2 border-b border-linea py-1.5">
            <EstadoConTexto t={t} estado={paso.estado} atribucion={atribucion} />
            <span className="mono text-xs text-secundario">{instante(paso.fecha)}</span>
            {paso.motivo === undefined ? (
              <span className="w-full text-xs text-secundario">
                {paso.fuente_id === undefined
                  ? t.ficha.fuenteNoPublica
                  : (medios.get(paso.fuente_id) ?? paso.fuente_id)}
              </span>
            ) : (
              // Una corrección, no una fuente: el motivo, a la vista.
              <span className="w-full text-xs text-texto" data-motivo-historial="">
                {conMayuscula(paso.motivo[idioma ?? "es"])}
              </span>
            )}
          </li>
  );
}

/** El estado, siempre con su símbolo y su nombre: nunca solo con color. */
export function EstadoConTexto({
  t,
  estado,
  atribucion = null,
}: {
  t: Textos;
  estado: Estado;
  atribucion?: AtribucionResumen | null;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <Simbolo estado={estado} atribucion={atribucion} />
      {t.estado[estado]}
    </span>
  );
}
