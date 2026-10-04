import { useState } from "react";
import type { FilaImpacto, FocoRegion, FuenteSentido, LuzResumen, Sentido } from "../datos/tipos.ts";
import type { CifrasRegion } from "../datos/ucrania.ts";
import { fechaDia, jornadaEscrita, numero, rango, region } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { LineaFoco, ZOOM_VISOR_REGION } from "./FocoTermico.tsx";
import { ListaLuz } from "./GuerraSatelite.tsx";
import { Fila } from "./Panel.tsx";
import { PALETA } from "../paleta.ts";
import { Enlace } from "../navegacion.tsx";

/** Partes que se listan antes de pedir «ver más». */
const ATAQUES_VISIBLES = 12;

const SENTIDOS: readonly Sentido[] = ["RU_UA", "UA_RU"];

interface Props {
  t: Textos;
  idioma: Idioma;
  codigo: string;
  cifras: CifrasRegion;
  /** Periodo elegido, ya escrito. */
  periodo: string;
  /** Focos térmicos detectados en la región en el periodo, del más reciente al más antiguo. */
  focos?: readonly FocoRegion[];
  /** La fuente de las cifras de cada sentido, con su puntuación. */
  fuentes?: Record<Sentido, FuenteSentido | null>;
  /** Impactos con lugar de la región en el periodo, del más reciente al más antiguo. */
  impactos?: readonly FilaImpacto[];
  /** Pérdidas de luz nocturna de la región en el periodo (la región entera). */
  luces?: readonly LuzResumen[];
  /** Abre la ficha de un impacto de la lista. */
  onImpacto?: (id: string) => void;
}

/** Línea con la fuente de las cifras de un sentido: medio, puntuación y, si lo es, la marca. */
function LineaFuente({ t, fuente }: { t: Textos; fuente: FuenteSentido }) {
  const codigo = `${fuente.fiabilidad}${fuente.credibilidad}`;
  return (
    <span className="block text-xs text-secundario" data-fuente-cifras="">
      {t.region.fuenteCifras(fuente.medio)}{" "}
      <span className="mono rounded-sm border border-linea px-1 text-acento">
        <span className="sr-only">{t.ficha.codigo(codigo)}</span>
        <span aria-hidden="true" title={t.ficha.codigo(codigo)}>
          {codigo}
        </span>
      </span>
      {fuente.reivindicacion && <> · {t.region.reivindicacion}</>}
    </span>
  );
}

/** Cifras de una región de Ucrania en el periodo elegido, con los partes que la citan. */
export function FichaRegion(props: Props) {
  const { t, idioma, codigo, cifras, periodo, focos = [], fuentes, impactos = [] } = props;
  const { onImpacto, luces = [] } = props;
  const [todos, setTodos] = useState(false);
  const total = cifras.ataques.RU_UA + cifras.ataques.UA_RU;
  const visibles = todos ? cifras.lista : cifras.lista.slice(0, ATAQUES_VISIBLES);
  const ocultos = cifras.lista.length - ATAQUES_VISIBLES;
  const ultimo = cifras.lista[0];
  return (
    <article>
      <h2 className="text-xl font-semibold tracking-tight text-2xl">{region(codigo, idioma)}</h2>
      <p className="mono mt-1 text-xs text-secundario">
        {codigo} · {periodo}
      </p>
      {total === 0 ? (
        <p className="mt-3 text-secundario">{t.region.sinAtaques}</p>
      ) : (
        <>
          {/* Lo que se ve desde el satélite, lo primero bajo el título: focos de calor y luz
              nocturna. Sin ello, nada. */}
          {(focos.length > 0 || luces.length > 0) && (
            <dl className="mt-3" data-satelite-arriba="">
              {focos.map((f) => (
                <LineaFoco
                  key={f.ataque}
                  t={t}
                  idioma={idioma}
                  foco={f.foco}
                  lon={f.centro[0]}
                  lat={f.centro[1]}
                  zoom={ZOOM_VISOR_REGION}
                  ataque={f.ataque}
                  color={PALETA.guerraClaro}
                />
              ))}
              {luces.length > 0 && (
                <Fila nombre={t.satelite.luzFicha.rotulo}>
                  <ListaLuz t={t} idioma={idioma} luces={[...luces].reverse()} />
                </Fila>
              )}
            </dl>
          )}
          <dl className="mt-3">
            <Fila nombre={t.region.ataques}>
              <span className="mono">{numero(total, idioma)}</span>
              <ul className="text-xs text-secundario">
                {SENTIDOS.filter((sentido) => cifras.ataques[sentido] > 0).map((sentido) => (
                  <li key={sentido}>
                    {t.region.ataquesPorSentido[sentido]}:{" "}
                    <span className="mono">{numero(cifras.ataques[sentido], idioma)}</span>
                    {fuentes?.[sentido] !== undefined && fuentes[sentido] !== null && (
                      <LineaFuente t={t} fuente={fuentes[sentido]} />
                    )}
                  </li>
                ))}
              </ul>
            </Fila>
            {cifras.derribados !== null && (
              <Fila nombre={t.region.derribados}>
                <span className="mono">{rango(cifras.derribados, idioma)}</span>
              </Fila>
            )}
            {ultimo !== undefined && (
              <Fila nombre={t.region.ultimoAtaque}>
                <span>{jornadaEscrita(t, ultimo.jornada)}</span>
              </Fila>
            )}
          </dl>
          <p className="mt-2 text-xs text-secundario">{t.region.nota}</p>
          {impactos.length > 0 && (
            <section className="mt-4" data-impactos-region="">
              <h3 className="rotulo">
                {t.region.impactos}: <span className="mono">{numero(impactos.length, idioma)}</span>
              </h3>
              <ul>
                {impactos.slice(0, ATAQUES_VISIBLES).map(([id, dia, , , , foco, parte]) => (
                  <li key={id} className="border-b border-linea py-1.5">
                    <button
                      type="button"
                      className="enlace mono text-left"
                      onClick={() => onImpacto?.(id)}
                    >
                      {id}
                    </button>
                    <span className="mono ml-2 text-xs text-secundario">{fechaDia(dia)}</span>
                    {parte === 1 && (
                      <span className="block text-xs text-secundario">{t.region.reivindicacion}</span>
                    )}
                    {foco === 1 && (
                      <span className="block text-xs text-secundario">{t.foco.detectado}</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className="mt-4">
            <h3 className="rotulo">{t.region.listaAtaques}</h3>
            <ul>
              {visibles.map((ataque) => (
                <li key={ataque.id} className="border-b border-linea py-1.5">
                  <Enlace a={rutaDeFicha(ataque.id, idioma)} className="enlace mono">
                    {ataque.id}
                  </Enlace>
                  <span className="ml-2 text-xs text-secundario">{jornadaEscrita(t, ataque.jornada)}</span>
                  <span className="block text-xs text-secundario">{t.sentido[ataque.sentido]}</span>
                </li>
              ))}
            </ul>
            {ocultos > 0 && (
              <button
                type="button"
                className="control mt-2 min-h-7 text-xs"
                aria-expanded={todos}
                onClick={() => setTodos(!todos)}
              >
                {todos ? t.ficha.menosFuentes : t.region.masAtaques(ocultos)}
              </button>
            )}
          </section>
        </>
      )}
    </article>
  );
}
