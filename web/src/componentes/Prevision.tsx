// «Previsión»: lo que está pasando más de lo normal y lo que es probable que pase, con números
// comprobados con el pasado. De arriba abajo: esta noche en la frontera, el aviso de segunda
// noche (solo cuando toca), las rachas por país y la semana que viene con su marcador. Cada
// parte lleva a la vista su historial de aciertos.

import { useState } from "react";
import type { ReactNode } from "react";

import type { Carga } from "../datos/carga.ts";
import { diaDeTexto, enVivo, marcadorSemanal, probabilidadLlana, mesEscrito, textoCambio } from "../datos/prevision.ts";
import type { FronteraPais, GraficaRacha, Prevision as DatosPrevision, Racha } from "../datos/prevision.ts";
import { fechaDia, fechaHora, numero, pais } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";

interface Props {
  t: Textos;
  idioma: Idioma;
  carga: Carga<DatosPrevision>;
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

function Frontera({ t, idioma, p }: { t: Textos; idioma: Idioma; p: FronteraPais }) {
  const [abierto, setAbierto] = useState(false);
  const f = t.prevision.frontera;
  const c = p.comprobacion;
  const nombre = pais(p.pais, idioma);
  const vivas = p.ultimas;
  return (
    <div className="mb-2.5" data-frontera={p.pais}>
      <p className="text-sm text-texto">
        <span className="font-medium">{nombre}</span>:{" "}
        <span data-probabilidad={p.probabilidad}>{probabilidadLlana(t, p.probabilidad, p.de_cada_10)}</span>
      </p>
      <p className="text-xs text-secundario">{f.habitual(Math.round(p.frecuencia_de_siempre * 100))}</p>
      <p className="mt-1 text-xs text-secundario">{f.dependeDe}</p>
      <ul className="list-disc pl-4 text-xs text-secundario">
        <li>
          {f.lanzados(numero(Math.round(p.factores.lanzados_tres_noches), idioma), numero(p.factores.lanzados_anoche, idioma))}{" "}
          · {f.efectos[p.efectos.lanzados_tres_noches]}
        </li>
        <li>
          {f.crimea(p.factores.noches_desde_crimea)} · {f.efectos[p.efectos.noches_desde_crimea]}
        </li>
        <li>
          {f.incidentes(p.factores.incidentes_siete_dias, nombre)} · {f.efectos[p.efectos.incidentes_siete_dias]}
        </li>
      </ul>
      <p className="mt-1 text-xs text-texto" data-historial-frontera="">
        {f.historial(
          numero(c.noches, idioma),
          fechaDia(diaDeTexto(c.desde)),
          c.noches_con_dron,
          c.con_dron_en_riesgo_alto,
          Math.round(c.mejora_sobre_frecuencia * 100),
        )}
      </p>
      <button
        type="button"
        className="control mt-1 min-h-11 text-xs underline underline-offset-2 esc:min-h-7"
        aria-expanded={abierto}
        onClick={() => setAbierto(!abierto)}
      >
        {f.verHistorial}
      </button>
      {abierto && (
        <div className="mt-1 text-xs text-secundario">
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
          <p className="mt-1">{f.ultimas}</p>
          <ul className="mono flex flex-wrap gap-x-2">
            {vivas.slice(-14).map((n) => (
              <li key={n.noche}>
                {fechaDia(diaDeTexto(n.noche))}: {Math.round(n.probabilidad * 100)} %{n.con_dron ? ` · ${f.conDron}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
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

export function Prevision({ t, idioma, carga, onRacha }: Props) {
  const p = t.prevision;
  if (carga.estado === "cargando") return <p className="text-xs text-secundario">{p.cargando}</p>;
  if (carga.estado !== "listo") return <p className="text-xs text-secundario">{p.noDisponible}</p>;
  const d = carga.datos;
  const marcador = marcadorSemanal(d);
  const dentro = marcador.filter((f) => f.dentro).length;
  const vivas = enVivo(d, "frontera").filter((e) => e.con_dron !== undefined);
  const semanaDesde = diaDeTexto(d.semana.semana);
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
          <p className="text-xs text-secundario" data-en-vivo-frontera="">
            {p.frontera.enVivo(vivas.length, vivas.filter((e) => e.con_dron === true).length)}
          </p>
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
          {d.rachas.terminadas.length > 0 && (
            <p className="mt-1.5 text-xs text-secundario" data-rachas-terminadas="">
              {p.rachas.terminadas(
                d.rachas.terminadas.map((r) => p.rachas.terminada(pais(r.pais, idioma), fechaDia(diaDeTexto(r.hasta))))
                  .join(", "),
              )}
            </p>
          )}
          <p className="mt-1.5 text-xs text-secundario" data-historial-rachas="">
            {p.rachas.historial(
              d.rachas.comprobacion.semanas_en_racha,
              d.rachas.comprobacion.incidentes_semana_siguiente,
              numero(d.rachas.comprobacion.normal_semana_siguiente, idioma),
            )}
          </p>
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
                <p className="text-xs text-secundario">
                  {p.cambios.historial(ambito.comprobacion.casos, ambito.comprobacion.sostenidos)}
                </p>
              </div>
            ))}
        </Seccion>
      )}
      <Seccion titulo={p.semana.titulo} id="semana">
        <p className="mb-1 text-xs text-secundario">
          {p.semana.cual(fechaDia(semanaDesde), fechaDia(semanaDesde + 6))}
          {d.semana.fijada ? "" : ` · ${p.semana.provisional}`}
        </p>
        {d.semana.paises.length === 0 ? (
          <p className="text-xs text-secundario">{p.semana.ninguno}</p>
        ) : (
          <ul className="text-sm">
            {d.semana.paises.map((s) => (
              <li key={s.pais} data-semana-pais={s.pais}>
                {pais(s.pais, idioma)}: {p.semana.fila(numero(s.esperado, idioma), s.minimo, s.maximo)}
              </li>
            ))}
          </ul>
        )}
        {marcador.length > 0 && (
          <details className="mt-1.5 text-xs">
            <summary className="control min-h-11 cursor-pointer text-secundario esc:min-h-7" data-marcador="">
              {p.semana.marcador(dentro, marcador.length)}
            </summary>
            <table className="mt-1 w-full text-secundario">
              <thead>
                <tr>
                  <th className="text-left font-normal">{p.semana.columnaSemana}</th>
                  <th className="text-left font-normal">{p.semana.columnaPais}</th>
                  <th className="text-right font-normal">{p.semana.columnaPrevisto}</th>
                  <th className="text-right font-normal">{p.semana.columnaReal}</th>
                </tr>
              </thead>
              <tbody>
                {marcador.map((f) => (
                  <tr key={`${f.pais}-${f.semana}`} data-tipo={f.tipo}>
                    <td className="mono">
                      {fechaDia(diaDeTexto(f.semana))}
                      {f.tipo === "reconstruida" ? " *" : ""}
                    </td>
                    <td>{f.pais}</td>
                    <td className="mono text-right">
                      {numero(f.esperado, idioma)} ({f.minimo}–{f.maximo})
                    </td>
                    <td className="mono text-right text-texto">
                      {f.real} {f.dentro ? "✓" : "✗"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-secundario">{p.semana.leyendaMarcador}</p>
          </details>
        )}
      </Seccion>
      <p className="border-t border-linea pt-2 text-xs text-secundario">
        {d.metodo[idioma]} {p.calculada(fechaHora(d.calculado))}
      </p>
    </div>
  );
}
