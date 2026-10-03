import { useState } from "react";

import type { CifrasPais, PresionPais } from "../datos/presion.ts";
import { ESTADOS, TIPOS } from "../datos/vocabulario.ts";
import { fechaDia, numero, pais } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { Fila } from "./Panel.tsx";
import { Simbolo } from "./Simbolo.tsx";

/** Incidentes que se listan antes de pedir «ver más». */
const VISIBLES = 15;

interface Props {
  t: Textos;
  idioma: Idioma;
  iso: string;
  presion: PresionPais | null;
  cifras: CifrasPais;
  /** Periodo elegido, ya escrito. */
  periodo: string;
}

/** Texto de la tendencia con su cifra: «sube +4», «baja −2», «estable». */
export function textoTendencia(t: Textos, presion: PresionPais | null, idioma: Idioma): string {
  const tendencia = presion?.tendencia ?? null;
  if (tendencia === null) return t.presion.sinComparacion;
  const { sentido, diferencia } = tendencia;
  if (diferencia === 0) return t.presion.tendencia[sentido];
  const signo = diferencia > 0 ? "+" : "−";
  return `${t.presion.tendencia[sentido]} ${signo}${numero(Math.abs(diferencia), idioma)}`;
}

/** Un país en la capa de presión: incidentes del periodo, tendencia, cifras y lista. */
export function FichaPais({ t, idioma, iso, presion, cifras, periodo }: Props) {
  const [todos, setTodos] = useState(false);
  const p = t.presion;
  const total = cifras.lista.length;
  const visibles = todos ? cifras.lista : cifras.lista.slice(0, VISIBLES);
  const ocultos = total - VISIBLES;
  const tendencia = presion?.tendencia ?? null;
  return (
    <article data-pais={iso}>
      <h2 className="text-2xl font-semibold tracking-tight">{pais(iso, idioma)}</h2>
      <p className="mono mt-1 text-xs text-secundario">
        {iso} · {periodo}
      </p>
      <p className="cifra mt-2 text-xl" data-incidentes-pais={total}>
        {p.incidentes(total)}
      </p>
      <p className="text-sm" data-tendencia={tendencia?.sentido ?? "sin"}>
        {textoTendencia(t, presion, idioma)}
        {tendencia !== null && (
          <span className="block text-xs text-secundario">
            {p.frente(numero(tendencia.anterior, idioma))}
          </span>
        )}
      </p>
      {total === 0 ? (
        <p className="mt-3 text-secundario">{p.vacia}</p>
      ) : (
        <>
          <dl className="mt-3">
            <Fila nombre={p.porTipo}>
              <ul>
                {TIPOS.filter((tipo) => cifras.porTipo[tipo] > 0).map((tipo) => (
                  <li key={tipo}>
                    {t.tipo[tipo]}: <span className="mono">{numero(cifras.porTipo[tipo], idioma)}</span>
                  </li>
                ))}
              </ul>
            </Fila>
            <Fila nombre={p.porEstado}>
              <ul>
                {ESTADOS.filter((estado) => cifras.porEstado[estado] > 0).map((estado) => (
                  <li key={estado} className="flex items-center gap-2">
                    <Simbolo estado={estado} />
                    {t.estado[estado]}:{" "}
                    <span className="mono">{numero(cifras.porEstado[estado], idioma)}</span>
                  </li>
                ))}
              </ul>
            </Fila>
          </dl>
          <section className="mt-4">
            <h3 className="rotulo">{p.lista}</h3>
            <ul>
              {visibles.map((incidente) => (
                <li key={incidente.id} className="border-b border-linea py-1.5">
                  <Enlace a={rutaDeFicha(incidente.id, idioma)} className="enlace text-left">
                    {incidente.titulo[idioma]}
                  </Enlace>
                  <span className="mono block text-xs text-secundario">
                    {incidente.id} · {fechaDia(incidente.dia)} · {t.estado[incidente.estado]}
                  </span>
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
