import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";

import { fechaDia, numero } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Estado } from "../datos/tipos.ts";
import { COLOR_ESTADO, PALETA } from "../paleta.ts";
import type { Idioma } from "../sitio.ts";
import { acotar, histograma, inicioDeTramo, inicioDeTramoSiguiente } from "../tiempo/dias.ts";
import type { Granularidad, Periodo, Tramo } from "../tiempo/dias.ts";
import { diaDeX, marcasDeEje, xDeDia } from "../tiempo/escala.ts";

const GRANULARIDADES: readonly Granularidad[] = ["dia", "semana", "mes"];

/** Medidas del gráfico, en píxeles. */
const ALTO_BARRAS = 64;
const ALTO_EJE = 16;
const ALTO = ALTO_BARRAS + ALTO_EJE;
/** Alto de la franja plegada: el histograma pequeño, siempre visible, y los destellos. */
const ALTO_PLEGADA = 22;
const OPACIDAD_PLEGADA_DENTRO = 0.8;
const OPACIDAD_PLEGADA_FUERA = 0.35;
/** Destello de un confirmado o atribuido en el eje: punto y halo. */
const RADIO_DESTELLO = 2;
const RADIO_HALO = 4.5;
const OPACIDAD_HALO = 0.35;
const HUECO_ENTRE_BARRAS = 1;
/** Por debajo de esta anchura las barras van pegadas: el hueco se las comería. */
const ANCHO_MINIMO_CON_HUECO = 3;
const ALTO_MINIMO_BARRA = 1.5;
/** Anchura de la zona que se puede agarrar en cada extremo del periodo: 44 px con el dedo. */
const ANCHO_ASA = 14;
const ANCHO_ASA_TACTIL = 44;
const OPACIDAD_FUERA_DEL_PERIODO = 0.6;
/** Rótulos del eje: cuerpo, separación del tick y largo del tick. */
const CUERPO_ROTULO = 10;
const SEPARACION_ROTULO = 3;
const LARGO_MARCA = 3;
/** Tramos que salta un extremo con AvPág y RePág. */
const SALTO_DE_PAGINA = 5;

interface Props {
  t: Textos;
  idioma: Idioma;
  dominio: Periodo;
  periodo: Periodo;
  onPeriodo: (periodo: Periodo) => void;
  granularidad: Granularidad;
  onGranularidad: (granularidad: Granularidad) => void;
  /** Incidentes por día de inicio. */
  incidentesPorDia: ReadonlyMap<number, number>;
  /** Drones lanzados contra Ucrania por noche; null si la capa no está activa. */
  lanzamientosPorDia: ReadonlyMap<number, number> | null;
  reproduccion: EstadoReproduccion;
  /** Empieza o reanuda la reproducción. */
  onReproducir: () => void;
  onPausar: () => void;
  /** Detiene la reproducción y vuelve al periodo de antes de reproducir. */
  onDetener: () => void;
  /** Hay un periodo elegido o una reproducción: se ofrece «Ver todo». */
  hayQueVerTodo: boolean;
  onVerTodo: () => void;
  /** Doble clic en el histograma: quita la selección. */
  onQuitarSeleccion: () => void;
  /** Confirmados y atribuidos del periodo, que se marcan en el eje con un destello. */
  destellos: readonly { dia: number; estado: Estado }[];
  /** Desplegada a propósito (clic o tecla T); si no, se despliega al pasar por encima. */
  abierta: boolean;
  onAbierta: (abierta: boolean) => void;
  /**
   * «franja», la de escritorio, plegable; «barra», la plegada del teléfono (histograma en
   * miniatura y el botón «Periodo»); «hoja», la desplegada del teléfono, en la hoja inferior.
   */
  forma?: "franja" | "barra" | "hoja";
}

export type EstadoReproduccion = "parada" | "reproduciendo" | "pausada";

type Arrastre = { modo: "nuevo"; ancla: number } | { modo: "desde" } | { modo: "hasta" };

function maximo(tramos: readonly Tramo[]): number {
  return tramos.reduce((mayor, tramo) => Math.max(mayor, tramo.valor), 0);
}

/** Línea escalonada de una serie, de la altura de las barras. */
function escalones(tramos: readonly Tramo[], ancho: number, dominio: Periodo): string {
  const tope = maximo(tramos);
  if (tope === 0) return "";
  return tramos
    .map((tramo, i) => {
      const x0 = Math.max(0, xDeDia(tramo.inicio, ancho, dominio));
      const x1 = Math.min(ancho, xDeDia(tramo.fin, ancho, dominio));
      const y = ALTO_BARRAS - (tramo.valor / tope) * ALTO_BARRAS;
      return `${i === 0 ? "M" : "L"}${x0.toFixed(1)} ${y.toFixed(1)}H${x1.toFixed(1)}`;
    })
    .join("");
}

function useAncho(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [ancho, setAncho] = useState(0);
  useEffect(() => {
    const elemento = ref.current;
    if (elemento === null) return undefined;
    setAncho(elemento.clientWidth);
    if (typeof ResizeObserver === "undefined") return undefined;
    const observador = new ResizeObserver(() => setAncho(elemento.clientWidth));
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);
  return [ref, ancho];
}

/**
 * Línea de tiempo: histograma por día, semana o mes. El periodo se elige arrastrando sobre
 * el histograma o moviendo sus dos extremos, también con el teclado, y el mapa muestra solo
 * ese periodo. Con la capa de Ucrania, una línea da los drones lanzados cada noche.
 */
export function LineaTiempo({
  t,
  idioma,
  dominio,
  periodo,
  onPeriodo,
  granularidad,
  onGranularidad,
  incidentesPorDia,
  lanzamientosPorDia,
  reproduccion,
  onReproducir,
  onPausar,
  onDetener,
  hayQueVerTodo,
  onVerTodo,
  onQuitarSeleccion,
  destellos,
  abierta,
  onAbierta,
  forma = "franja",
}: Props) {
  const [encima, setEncima] = useState(false);
  const reproduciendo = reproduccion === "reproduciendo";
  const desplegada =
    forma === "hoja" || (forma === "franja" && (abierta || encima || reproduccion !== "parada"));
  // En el teléfono los controles miden al menos 44 px, para el dedo.
  const alto = forma === "franja" ? "min-h-7" : "min-h-11";
  const anchoAsa = forma === "franja" ? ANCHO_ASA : ANCHO_ASA_TACTIL;
  const [contenedor, ancho] = useAncho();
  const arrastre = useRef<Arrastre | null>(null);
  const idInstrucciones = useId();

  const tramos = histograma(incidentesPorDia, dominio.desde, dominio.hasta, granularidad);
  const tope = maximo(tramos);
  const tramosUcrania =
    lanzamientosPorDia === null
      ? null
      : histograma(lanzamientosPorDia, dominio.desde, dominio.hasta, granularidad);
  const xDesde = xDeDia(periodo.desde, ancho, dominio);
  const xHasta = xDeDia(periodo.hasta + 1, ancho, dominio);
  const completo = periodo.desde === dominio.desde && periodo.hasta === dominio.hasta;

  function diaDeEvento(evento: PointerEvent<SVGElement>): number {
    const caja = evento.currentTarget.ownerSVGElement ?? evento.currentTarget;
    return diaDeX(evento.clientX - caja.getBoundingClientRect().left, ancho, dominio);
  }

  function empezar(evento: PointerEvent<SVGElement>, modo: Arrastre) {
    evento.stopPropagation();
    evento.currentTarget.setPointerCapture(evento.pointerId);
    arrastre.current = modo;
    if (modo.modo === "nuevo") onPeriodo({ desde: modo.ancla, hasta: modo.ancla });
  }

  function mover(evento: PointerEvent<SVGElement>) {
    const actual = arrastre.current;
    if (actual === null) return;
    const dia = diaDeEvento(evento);
    if (actual.modo === "nuevo") {
      onPeriodo({ desde: Math.min(actual.ancla, dia), hasta: Math.max(actual.ancla, dia) });
    } else if (actual.modo === "desde") {
      onPeriodo({ desde: Math.min(dia, periodo.hasta), hasta: periodo.hasta });
    } else {
      onPeriodo({ desde: periodo.desde, hasta: Math.max(dia, periodo.desde) });
    }
  }

  function terminar(evento: PointerEvent<SVGElement>) {
    const actual = arrastre.current;
    arrastre.current = null;
    if (actual?.modo !== "nuevo") return;
    // Un clic sin arrastrar elige el tramo entero que contiene ese día.
    if (diaDeEvento(evento) === actual.ancla) {
      onPeriodo({
        desde: Math.max(dominio.desde, inicioDeTramo(actual.ancla, granularidad)),
        hasta: Math.min(dominio.hasta, inicioDeTramoSiguiente(actual.ancla, granularidad) - 1),
      });
    }
  }

  function tecla(evento: KeyboardEvent<SVGGElement>, extremo: "desde" | "hasta") {
    const pasos: Record<string, number> = {
      ArrowLeft: -1,
      ArrowDown: -1,
      ArrowRight: 1,
      ArrowUp: 1,
      PageDown: -SALTO_DE_PAGINA,
      PageUp: SALTO_DE_PAGINA,
    };
    let dia = periodo[extremo];
    if (evento.key === "Home") dia = dominio.desde;
    else if (evento.key === "End") dia = dominio.hasta;
    else {
      const paso = pasos[evento.key];
      if (paso === undefined) return;
      for (let i = 0; i < Math.abs(paso); i += 1) {
        if (extremo === "desde") {
          dia = paso > 0 ? inicioDeTramoSiguiente(dia, granularidad) : inicioDeTramo(dia - 1, granularidad);
        } else {
          dia =
            paso > 0
              ? inicioDeTramoSiguiente(dia + 1, granularidad) - 1
              : inicioDeTramo(dia, granularidad) - 1;
        }
      }
    }
    evento.preventDefault();
    onPeriodo(
      extremo === "desde"
        ? { desde: acotar(dia, dominio.desde, periodo.hasta), hasta: periodo.hasta }
        : { desde: periodo.desde, hasta: acotar(dia, periodo.desde, dominio.hasta) },
    );
  }

  function asa(extremo: "desde" | "hasta", x: number) {
    return (
      <g
        role="slider"
        tabIndex={0}
        aria-label={extremo === "desde" ? t.tiempo.desde : t.tiempo.hasta}
        aria-valuemin={dominio.desde}
        aria-valuemax={dominio.hasta}
        aria-valuenow={periodo[extremo]}
        aria-valuetext={fechaDia(periodo[extremo])}
        aria-describedby={idInstrucciones}
        onKeyDown={(evento) => tecla(evento, extremo)}
        onPointerDown={(evento) => empezar(evento, { modo: extremo })}
        onPointerMove={mover}
        onPointerUp={terminar}
        className="cursor-ew-resize"
      >
        <rect x={x - anchoAsa / 2} y={0} width={anchoAsa} height={ALTO_BARRAS} fill="transparent" />
        <line x1={x} x2={x} y1={0} y2={ALTO_BARRAS} className="stroke-acento" strokeWidth={1.5} />
      </g>
    );
  }

  const grafico = (
    <div
      ref={contenedor}
      className={`w-full touch-none select-none ${
        forma === "barra" ? "h-[22px] apaisado:h-3" : desplegada ? "mt-1 h-20" : "mt-1 h-[22px]"
      }`}
    >
      {ancho > 0 && !desplegada && (
        <svg
          width={ancho}
          height="100%"
          viewBox={`0 0 ${ancho} ${ALTO_PLEGADA}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {tope > 0 &&
            tramos.map((tramo) => {
              if (tramo.valor === 0) return null;
              const alto = Math.max(ALTO_MINIMO_BARRA, (tramo.valor / tope) * ALTO_PLEGADA);
              const x = Math.max(0, xDeDia(tramo.inicio, ancho, dominio));
              const dentro = tramo.fin > periodo.desde && tramo.inicio <= periodo.hasta;
              return (
                <rect
                  key={tramo.inicio}
                  x={x}
                  y={ALTO_PLEGADA - alto}
                  width={Math.max(1, xDeDia(tramo.fin, ancho, dominio) - x - HUECO_ENTRE_BARRAS)}
                  height={alto}
                  fill={PALETA.secundario}
                  fillOpacity={dentro ? OPACIDAD_PLEGADA_DENTRO : OPACIDAD_PLEGADA_FUERA}
                />
              );
            })}
          {destellos.map((destello, i) => (
            <circle
              key={i}
              cx={xDeDia(destello.dia, ancho, dominio)}
              cy={ALTO_PLEGADA - RADIO_DESTELLO}
              r={RADIO_DESTELLO}
              fill={COLOR_ESTADO[destello.estado]}
            />
          ))}
        </svg>
      )}
      {ancho > 0 && desplegada && (
        <svg width={ancho} height={ALTO} role="group" aria-label={t.tiempo.titulo}>
          <rect
            x={0}
            y={0}
            width={ancho}
            height={ALTO_BARRAS}
            fill="transparent"
            className="cursor-crosshair"
            onDoubleClick={onQuitarSeleccion}
            onPointerDown={(evento) =>
              empezar(evento, { modo: "nuevo", ancla: diaDeEvento(evento) })
            }
            onPointerMove={mover}
            onPointerUp={terminar}
          />
          <g aria-hidden="true" pointerEvents="none">
            {tope > 0 &&
              tramos.map((tramo) => {
                if (tramo.valor === 0) return null;
                const x = Math.max(0, xDeDia(tramo.inicio, ancho, dominio));
                const anchoTramo = Math.min(ancho, xDeDia(tramo.fin, ancho, dominio)) - x;
                const hueco = anchoTramo >= ANCHO_MINIMO_CON_HUECO ? HUECO_ENTRE_BARRAS : 0;
                const alto = Math.max(ALTO_MINIMO_BARRA, (tramo.valor / tope) * ALTO_BARRAS);
                const dentro = tramo.fin > periodo.desde && tramo.inicio <= periodo.hasta;
                return (
                  <rect
                    key={tramo.inicio}
                    x={x}
                    y={ALTO_BARRAS - alto}
                    width={Math.max(anchoTramo - hueco, 1)}
                    height={alto}
                    fill={PALETA.elevado}
                    stroke={dentro ? PALETA.secundario : PALETA.linea}
                    strokeWidth={1}
                  />
                );
              })}
            {tramosUcrania !== null && (
              <path
                d={escalones(tramosUcrania, ancho, dominio)}
                fill="none"
                stroke={PALETA.atribuido}
                strokeWidth={1}
              />
            )}
            <rect
              x={0}
              width={Math.max(xDesde, 0)}
              height={ALTO_BARRAS}
              fill={PALETA.fondo}
              fillOpacity={OPACIDAD_FUERA_DEL_PERIODO}
            />
            <rect
              x={xHasta}
              width={Math.max(ancho - xHasta, 0)}
              height={ALTO_BARRAS}
              fill={PALETA.fondo}
              fillOpacity={OPACIDAD_FUERA_DEL_PERIODO}
            />
            <line x1={0} x2={ancho} y1={ALTO_BARRAS} y2={ALTO_BARRAS} stroke={PALETA.linea} />
            {destellos.map((destello, i) => {
              const x = xDeDia(destello.dia, ancho, dominio);
              const color = COLOR_ESTADO[destello.estado];
              return (
                <g key={i}>
                  <circle cx={x} cy={ALTO_BARRAS} r={RADIO_HALO} fill={color} opacity={OPACIDAD_HALO} />
                  <circle cx={x} cy={ALTO_BARRAS} r={RADIO_DESTELLO} fill={color} />
                </g>
              );
            })}
            {marcasDeEje(dominio, ancho).map((marca) => {
              const x = xDeDia(marca.dia, ancho, dominio);
              return (
                <g key={marca.dia}>
                  <line
                    x1={x}
                    x2={x}
                    y1={ALTO_BARRAS}
                    y2={ALTO_BARRAS + LARGO_MARCA}
                    stroke={PALETA.linea}
                  />
                  <text
                    x={x + SEPARACION_ROTULO}
                    y={ALTO - SEPARACION_ROTULO}
                    fill={PALETA.secundario}
                    fontSize={CUERPO_ROTULO}
                    className="mono"
                  >
                    {marca.etiqueta}
                  </text>
                </g>
              );
            })}
          </g>
          {asa("desde", xDesde)}
          {asa("hasta", xHasta)}
        </svg>
      )}
    </div>
  );

  return (
    // El envoltorio solo escucha el paso del ratón y el foco para desplegar la franja; con
    // teclado se despliega con el botón de la franja o con la tecla T.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      onMouseEnter={() => setEncima(true)}
      onMouseLeave={() => setEncima(false)}
      onFocus={() => setEncima(true)}
      onBlur={(evento) => {
        if (!evento.currentTarget.contains(evento.relatedTarget as Node | null)) setEncima(false);
      }}
    >
    <section
      aria-label={t.tiempo.titulo}
      className={
        forma === "hoja"
          ? "px-3 pb-2"
          : forma === "barra"
            ? "flotante rounded-none px-2 apaisado:bg-transparent apaisado:px-0 apaisado:shadow-none"
            : "flotante px-3 pb-1.5 pt-1.5"
      }
    >
      {!desplegada && forma !== "barra" && (
        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            className={`flex flex-1 cursor-pointer items-center gap-2 rounded-sm px-1 hover:bg-elevado ${alto}`}
            aria-expanded={false}
            onClick={() => onAbierta(true)}
          >
            <span className="text-texto">{t.tiempo.titulo}</span>
            {!completo && <span className="text-secundario">· {t.tiempo.acotado}</span>}
          </button>
          {hayQueVerTodo && (
            <button type="button" className={`control text-xs text-texto ${alto}`} onClick={onVerTodo}>
              {t.tiempo.verTodo}
            </button>
          )}
          {forma === "franja" && (
            <button
              type="button"
              className={`control text-xs ${alto}`}
              aria-expanded={false}
              onClick={() => onAbierta(true)}
            >
              {t.tiempo.desplegar}
            </button>
          )}
        </div>
      )}
      {desplegada && (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {reproduciendo ? (
          <button type="button" className={`control control-principal text-xs ${alto}`} onClick={onPausar}>
            <span aria-hidden="true">❚❚</span>
            {t.tiempo.pausar}
          </button>
        ) : (
          <button type="button" className={`control control-principal text-xs ${alto}`} onClick={onReproducir}>
            <span aria-hidden="true">▶</span>
            {reproduccion === "pausada" ? t.tiempo.reanudar : t.tiempo.reproducir}
          </button>
        )}
        {reproduccion !== "parada" && (
          <button type="button" className={`control text-xs text-texto ${alto}`} onClick={onDetener}>
            <span aria-hidden="true">■</span>
            {t.tiempo.detener}
          </button>
        )}
        <div role="radiogroup" aria-label={t.tiempo.granularidad} className="flex gap-1">
          {GRANULARIDADES.map((opcion) => (
            <button
              key={opcion}
              type="button"
              role="radio"
              aria-checked={granularidad === opcion}
              className={`control text-xs ${alto}`}
              onClick={() => onGranularidad(opcion)}
            >
              {t.tiempo.porGranularidad[opcion]}
            </button>
          ))}
        </div>
        {hayQueVerTodo && (
          <button type="button" className={`control text-xs text-texto ${alto}`} onClick={onVerTodo}>
            {t.tiempo.verTodo}
          </button>
        )}
        <p className="mono text-xs text-texto" aria-live="off">
          {t.tiempo.periodo(fechaDia(periodo.desde), fechaDia(periodo.hasta))}
        </p>
        <p className="ml-auto flex flex-wrap gap-x-3 text-xs text-secundario">
          <span>
            {t.tiempo.incidentesPorTramo} · {t.tiempo.maximo(numero(tope, idioma))}
          </span>
          {tramosUcrania !== null && (
            <span>
              <span aria-hidden="true" className="text-atribuido">
                —{" "}
              </span>
              {t.tiempo.lanzamientosPorNoche} ·{" "}
              {t.tiempo.maximo(numero(maximo(tramosUcrania), idioma))}
            </span>
          )}
        </p>
        {forma === "franja" && abierta && (
          <button
            type="button"
            className={`control text-xs ${alto}`}
            aria-expanded={true}
            onClick={() => onAbierta(false)}
          >
            {t.tiempo.plegar}
          </button>
        )}
      </div>
      )}
      <p id={idInstrucciones} className="sr-only">
        {t.tiempo.instrucciones}
      </p>
      {forma === "barra" ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="control text-xs text-texto apaisado:hidden"
            aria-expanded={false}
            onClick={() => onAbierta(true)}
          >
            {t.tiempo.periodoBoton}
            {!completo && <span className="text-secundario">· {t.tiempo.acotado}</span>}
          </button>
          <div className="min-w-0 flex-1">{grafico}</div>
          {hayQueVerTodo && (
            <button type="button" className="control text-xs text-texto apaisado:hidden" onClick={onVerTodo}>
              {t.tiempo.verTodo}
            </button>
          )}
        </div>
      ) : (
        grafico
      )}
    </section>
    </div>
  );
}
