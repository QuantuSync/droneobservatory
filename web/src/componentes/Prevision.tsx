// «Previsión»: lo que está pasando más de lo normal y lo que es probable que pase, con números
// comprobados con el pasado. De arriba abajo: esta noche en la frontera, el aviso de segunda
// noche (solo cuando toca), las rachas por país y qué ha cambiado. A la vista, solo el número y
// sus razones; cómo se comprobó cada parte va plegado en «Cómo se comprueba».

import type { ReactNode } from "react";

import type { Carga } from "../datos/carga.ts";
import {
  diaDeTexto,
  enVivo,
  factoresQueCuentan,
  habitualDe,
  probabilidadLlana,
  mesEscrito,
  textoCambio,
  textoFactor,
} from "../datos/prevision.ts";
import type { FronteraPais, GraficaRacha, Prevision as DatosPrevision, Racha } from "../datos/prevision.ts";
import { fechaDia, fechaHora, numero, pais } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { ErrorDeCarga, recargarPagina } from "./Panel.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  carga: Carga<DatosPrevision>;
  /** La última previsión que llegó bien en esta visita: se enseña, con su fecha, si la nueva no llega. */
  anterior?: DatosPrevision | null;
  /** Vuelve a pedir la previsión. */
  onReintentar?: () => void;
  /** Lleva el mapa al país con el periodo de la racha en los filtros. */
  onRacha: (racha: Racha) => void;
}

function Seccion({ titulo, children, id }: { titulo: string; children: ReactNode; id: string }) {
  return (
    <section className="border-t border-linea pt-2.5 first:border-t-0 first:pt-0" data-prevision-seccion={id}>
      <h3 className="rotulo mb-1.5">{titulo}</h3>
      {children}
    </section>
  );
}

/** «Cómo se comprueba»: los párrafos de la comprobación, plegados hasta que se tocan. */
export function ComoSeComprueba({ t, children }: { t: Textos; children: ReactNode }) {
  return (
    <details className="mt-1 text-xs text-secundario" data-como-se-comprueba="">
      <summary className="control min-h-11 cursor-pointer underline underline-offset-2 esc:min-h-7">
        {t.prevision.comoSeComprueba}
      </summary>
      <div className="mt-1 flex flex-col gap-1">{children}</div>
    </details>
  );
}

function Frontera({ t, idioma, p }: { t: Textos; idioma: Idioma; p: FronteraPais }) {
  const f = t.prevision.frontera;
  const c = p.comprobacion;
  const nombre = pais(p.pais, idioma);
  const vivas = p.ultimas;
  const factores = factoresQueCuentan(p);
  return (
    <div className="mb-2.5" data-frontera={p.pais}>
      <p className="text-sm text-texto">
        <span className="font-medium">{nombre}</span>:{" "}
        <span data-probabilidad={p.probabilidad}>{probabilidadLlana(t, p.probabilidad, p.de_cada_10)}</span>
      </p>
      <p className="text-xs text-secundario" data-habitual={habitualDe(c)}>
        {f.habitual(habitualDe(c))}
      </p>
      {factores.length === 0 ? (
        <p className="mt-1 text-xs text-secundario">{f.sinCambios}</p>
      ) : (
        <>
          <p className="mt-1 text-xs text-secundario">{f.dependeDe}</p>
          <ul className="list-disc pl-4 text-xs text-secundario" data-factores="">
            {factores.map(({ factor, efecto }) => (
              <li key={factor} data-efecto={efecto}>
                {textoFactor(t, idioma, p, factor, efecto)}
              </li>
            ))}
          </ul>
        </>
      )}
      <ComoSeComprueba t={t}>
        <p data-historial-frontera="">
          {f.historial(
            numero(c.noches, idioma),
            fechaDia(diaDeTexto(c.desde)),
            c.noches_con_dron,
            habitualDe(c),
            c.con_dron_en_riesgo_alto,
          )}
        </p>
        <table className="w-full">
          <caption className="sr-only">{f.verHistorial}</caption>
          <thead>
            <tr>
              <th className="text-left font-normal">{f.columnaDijo}</th>
              <th className="text-right font-normal">{f.columnaNoches}</th>
              <th className="text-right font-normal">{f.columnaConDron}</th>
            </tr>
          </thead>
          <tbody>
            {c.tramos.map((tramo) => (
              <tr key={tramo.desde}>
                <td>{f.tramo(Math.round(tramo.desde * 100), Math.round(tramo.hasta * 100))}</td>
                <td className="mono text-right">{numero(tramo.noches, idioma)}</td>
                <td className="mono text-right">{numero(tramo.con_dron, idioma)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>{f.ultimas}</p>
        <ul className="mono flex flex-wrap gap-x-2">
          {vivas.slice(-14).map((n) => (
            <li key={n.noche}>
              {fechaDia(diaDeTexto(n.noche))}: {Math.round(n.probabilidad * 100)} %{n.con_dron ? ` · ${f.conDron}` : ""}
            </li>
          ))}
        </ul>
      </ComoSeComprueba>
    </div>
  );
}

/** Incidentes por semana con la banda de lo normal: una sola serie, barras finas. */
export function GraficaSemanal({ t, idioma, grafica }: { t: Textos; idioma: Idioma; grafica: GraficaRacha }) {
  const ancho = 260;
  const alto = 64;
  const n = grafica.incidentes.length;
  const maximo = Math.max(1, grafica.banda[1], ...grafica.incidentes);
  const y = (v: number) => alto - 2 - (v / maximo) * (alto - 6);
  const paso = ancho / Math.max(1, n);
  const barra = Math.max(2, paso - 2);
  const resumen = t.prevision.grafica.resumen(
    n,
    grafica.incidentes.reduce((a, b) => a + b, 0),
    numero(grafica.normal, idioma),
  );
  return (
    <figure className="mt-2" data-grafica-racha="">
      <figcaption className="text-xs text-secundario">{t.prevision.grafica.titulo}</figcaption>
      <svg
        role="img"
        aria-label={resumen}
        viewBox={`0 0 ${ancho} ${alto}`}
        width="100%"
        height={alto}
        className="mt-1 max-w-[20rem]"
      >
        <rect
          x={0}
          y={y(grafica.banda[1])}
          width={ancho}
          height={Math.max(1, y(grafica.banda[0]) - y(grafica.banda[1]))}
          fill="currentColor"
          className="text-linea"
          opacity={0.6}
        />
        {grafica.incidentes.map((v, i) => (
          <rect
            key={grafica.semanas[i]}
            x={i * paso + 1}
            y={v === 0 ? alto - 3 : y(v)}
            width={barra}
            height={v === 0 ? 1 : alto - 2 - y(v)}
            rx={v === 0 ? 0 : 1.5}
            fill="currentColor"
            className={v > grafica.banda[1] ? "text-texto" : "text-secundario"}
          >
            <title>{t.prevision.grafica.barra(fechaDia(diaDeTexto(grafica.semanas[i] ?? "1970-01-01")), v)}</title>
          </rect>
        ))}
      </svg>
      <p className="text-xs text-secundario">{t.prevision.grafica.banda(grafica.banda[0], grafica.banda[1])}</p>
    </figure>
  );
}

/** La línea de una racha: país, desde cuándo, cuántos frente a lo habitual y si crece. */
export function textoRacha(t: Textos, idioma: Idioma, r: Racha): string {
  return t.prevision.rachas.linea(
    fechaDia(diaDeTexto(r.desde)),
    r.incidentes,
    numero(r.habitual, idioma),
    numero(r.veces, idioma),
    t.prevision.rachas.tendencia[r.tendencia],
  );
}

export function Prevision({ t, idioma, carga, anterior = null, onReintentar = () => undefined, onRacha }: Props) {
  const p = t.prevision;
  const d = carga.estado === "listo" ? carga.datos : anterior;
  if (d === null) {
    if (carga.estado === "cargando") return <p className="text-xs text-secundario">{p.cargando}</p>;
    if (carga.estado === "listo") return null;
    return (
      <ErrorDeCarga
        t={t}
        className="text-sm"
        mensaje={carga.estado === "no_encontrado" ? p.noPublicada : p.noDisponible}
        estado={carga.estado}
        onReintentar={onReintentar}
      />
    );
  }
  // La nueva no ha llegado: la última que hay, con su fecha, y la opción de volver a pedirla.
  const deAntes = carga.estado !== "listo" && carga.estado !== "cargando";
  return (
    <div className="flex flex-col gap-3">
      {deAntes && (
        <div className="flex flex-col items-start gap-2 text-xs text-secundario" role="status" data-prevision-anterior="">
          <p>{p.anterior(fechaHora(d.calculado))}</p>
          <button
            type="button"
            className="control min-h-11 rounded border border-linea px-3 text-texto esc:min-h-8"
            onClick={carga.estado === "no_valido" ? recargarPagina : onReintentar}
            data-reintentar=""
          >
            {t.avisos.reintentar}
          </button>
        </div>
      )}
      <ContenidoPrevision t={t} idioma={idioma} d={d} onRacha={onRacha} />
    </div>
  );
}

function ContenidoPrevision({ t, idioma, d, onRacha }: { t: Textos; idioma: Idioma; d: DatosPrevision; onRacha: (racha: Racha) => void }) {
  const p = t.prevision;
  const vivas = enVivo(d, "frontera").filter((e) => e.con_dron !== undefined);
  const aviso = d.segunda_noche?.aviso;
  return (
    <div className="flex flex-col gap-3 text-sm" data-prevision="">
      <Seccion titulo={p.frontera.titulo} id="frontera">
        <p className="mb-1.5 text-xs text-secundario">
          {p.frontera.noche(fechaDia(diaDeTexto(d.frontera.noche.desde)), fechaDia(diaDeTexto(d.frontera.noche.hasta)))}
        </p>
        {d.frontera.paises.length === 0 ? (
          <p className="text-xs text-secundario">{p.frontera.ninguno}</p>
        ) : (
          d.frontera.paises.map((pf) => <Frontera key={pf.pais} t={t} idioma={idioma} p={pf} />)
        )}
        {vivas.length > 0 && (
          <ComoSeComprueba t={t}>
            <p data-en-vivo-frontera="">
              {p.frontera.enVivo(vivas.length, vivas.filter((e) => e.con_dron === true).length)}
            </p>
          </ComoSeComprueba>
        )}
      </Seccion>
      {aviso !== undefined && (
        <Seccion titulo={p.segundaNoche.titulo} id="segunda-noche">
          <p className="text-xs text-texto">
            {p.segundaNoche.aviso(numero(aviso.lanzados, idioma), probabilidadLlana(t, aviso.probabilidad, aviso.de_cada_10))}
          </p>
        </Seccion>
      )}
      {d.rachas !== undefined && (
        <Seccion titulo={p.rachas.titulo} id="rachas">
          {d.rachas.activas.length === 0 ? (
            <p className="text-xs text-secundario">{p.rachas.ninguna}</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {d.rachas.activas.map((r) => (
                <li key={`${r.pais}-${r.grupo}`}>
                  <button
                    type="button"
                    className="control min-h-11 w-full flex-col items-start text-left esc:min-h-8"
                    data-racha={r.pais}
                    aria-label={p.rachas.ir(pais(r.pais, idioma))}
                    onClick={() => onRacha(r)}
                  >
                    <span className="text-sm text-texto">{pais(r.pais, idioma)}</span>
                    <span className="text-xs text-secundario">{textoRacha(t, idioma, r)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <ComoSeComprueba t={t}>
            <p data-historial-rachas="">
              {p.rachas.historial(
                d.rachas.comprobacion.semanas_en_racha,
                d.rachas.comprobacion.incidentes_semana_siguiente,
                numero(d.rachas.comprobacion.normal_semana_siguiente, idioma),
              )}
            </p>
          </ComoSeComprueba>
        </Seccion>
      )}
      {d.cambios !== undefined && d.cambios.ambitos.some((a) => a.cambios.length > 0) && (
        <Seccion titulo={p.cambios.titulo} id="cambios">
          <p className="mb-1 text-xs text-secundario">{p.cambios.periodo(mesEscrito(d.cambios.recientes.desde, idioma), mesEscrito(d.cambios.recientes.hasta, idioma))}</p>
          {d.cambios.ambitos
            .filter((a) => a.cambios.length > 0)
            .map((ambito) => (
              <div key={ambito.ambito} className="mb-1.5" data-cambios={ambito.ambito}>
                <p className="text-xs text-texto">{p.cambios.ambito[ambito.ambito]}</p>
                <ul className="list-disc pl-4 text-xs text-secundario">
                  {ambito.cambios.map((c) => (
                    <li key={c.clave}>{textoCambio(t, ambito, c)}</li>
                  ))}
                </ul>
                <ComoSeComprueba t={t}>
                  <p>{p.cambios.historial(ambito.comprobacion.casos, ambito.comprobacion.sostenidos)}</p>
                </ComoSeComprueba>
              </div>
            ))}
        </Seccion>
      )}
      <p className="border-t border-linea pt-2 text-xs text-secundario">
        {d.metodo[idioma]} {p.calculada(fechaHora(d.calculado))}
      </p>
    </div>
  );
}
