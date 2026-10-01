import { useState } from "react";
import type { Sentido } from "../datos/tipos.ts";
import type { CifrasRegion } from "../datos/ucrania.ts";
import { fechaDia, numero, rango, region } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { Fila } from "./Panel.tsx";
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
}

/** Cifras de una región de Ucrania en el periodo elegido, con los partes que la citan. */
export function FichaRegion({ t, idioma, codigo, cifras, periodo }: Props) {
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
          <dl className="mt-3">
            <Fila nombre={t.region.ataques}>
              <span className="mono">{numero(total, idioma)}</span>
              <ul className="text-xs text-secundario">
                {SENTIDOS.filter((sentido) => cifras.ataques[sentido] > 0).map((sentido) => (
                  <li key={sentido}>
                    {t.region.ataquesPorSentido[sentido]}:{" "}
                    <span className="mono">{numero(cifras.ataques[sentido], idioma)}</span>
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
                <span className="mono">{fechaDia(ultimo.dia)}</span>
              </Fila>
            )}
          </dl>
          <p className="mt-2 text-xs text-secundario">{t.region.nota}</p>
          <section className="mt-4">
            <h3 className="rotulo">{t.region.listaAtaques}</h3>
            <ul>
              {visibles.map((ataque) => (
                <li key={ataque.id} className="border-b border-linea py-1.5">
                  <Enlace a={rutaDeFicha(ataque.id, idioma)} className="enlace mono">
                    {ataque.id}
                  </Enlace>
                  <span className="mono ml-2 text-xs text-secundario">{fechaDia(ataque.dia)}</span>
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
