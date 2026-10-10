import type { ReactNode } from "react";

import { ESTADOS, TIPOS, ZONAS } from "../datos/vocabulario.ts";
import { RECIENTES, TODO, alternar, hayFiltros } from "../estado/filtros.ts";
import type { Filtros as EstadoFiltros, Reciente, SeleccionPeriodo } from "../estado/filtros.ts";
import { fechaDia, pais } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { fechaDeDia, diaDeInstante } from "../tiempo/dias.ts";
import type { Periodo } from "../tiempo/dias.ts";
import { Simbolo } from "./Simbolo.tsx";

type ClavePeriodo = "todo" | Reciente | "entre";
const CLAVES_PERIODO: readonly ClavePeriodo[] = ["todo", ...RECIENTES, "entre"];

interface Props {
  t: Textos;
  idioma: Idioma;
  filtros: EstadoFiltros;
  onFiltros: (filtros: EstadoFiltros) => void;
  seleccion: SeleccionPeriodo;
  onSeleccion: (seleccion: SeleccionPeriodo) => void;
  /** Primer y último día con datos: los límites de «Entre fechas». */
  dominio: Periodo | null;
  /** Países con algún incidente, para el selector. */
  paises: readonly string[];
  /** Quita los filtros y el periodo de una vez. */
  onQuitar: () => void;
}

function Grupo({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 text-xs text-secundario">{rotulo}</legend>
      <div className="flex flex-wrap items-center gap-1">{children}</div>
    </fieldset>
  );
}

function Opcion({
  activa,
  onClick,
  children,
}: {
  activa: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className="control min-h-11 rounded-sm border border-linea px-3 text-xs esc:min-h-8"
      aria-pressed={activa}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function claveDe(seleccion: SeleccionPeriodo): ClavePeriodo {
  return seleccion.clase === "todo" ? "todo" : seleccion.clase === "entre" ? "entre" : seleccion.reciente;
}

/** Día (número) como AAAA-MM-DD, para los campos de fecha. */
export function textoDeDia(dia: number): string {
  return fechaDeDia(dia).toISOString().slice(0, 10);
}

/** El periodo elegido, escrito: «Últimos 7 días», «01/11/2025 – 30/11/2025»; null si es todo. */
export function textoDeSeleccion(t: Textos, seleccion: SeleccionPeriodo): string | null {
  if (seleccion.clase === "todo") return null;
  if (seleccion.clase === "reciente") return t.filtros.periodos[seleccion.reciente];
  return t.filtros.entreFechas(fechaDia(seleccion.periodo.desde), fechaDia(seleccion.periodo.hasta));
}

/**
 * Los filtros, apilados por categoría con su rótulo: periodo (todo, los rápidos o entre dos
 * fechas), estado, tipo y país, con controles de 44 px en el teléfono. «Quitar filtros» aparece
 * en cuanto hay alguno puesto. Todo va a la dirección.
 */
export function Filtros(props: Props) {
  const { t, idioma, filtros, onFiltros, seleccion, onSeleccion, dominio, paises, onQuitar } = props;
  const ordenados = [...paises].sort((a, b) => pais(a, idioma).localeCompare(pais(b, idioma), idioma));
  const elegido = filtros.paises[0] ?? "";
  const clave = claveDe(seleccion);
  const limites = {
    min: dominio === null ? undefined : textoDeDia(dominio.desde),
    max: dominio === null ? undefined : textoDeDia(dominio.hasta),
  };
  const entre: Periodo | null =
    seleccion.clase === "entre"
      ? seleccion.periodo
      : dominio === null
        ? null
        : { desde: Math.max(dominio.desde, dominio.hasta - 29), hasta: dominio.hasta };

  function elegirClave(nueva: ClavePeriodo) {
    if (nueva === "todo") onSeleccion(TODO);
    else if (nueva === "entre") {
      if (entre !== null) onSeleccion({ clase: "entre", periodo: entre });
    } else onSeleccion({ clase: "reciente", reciente: nueva });
  }

  function cambiarFecha(extremo: "desde" | "hasta", texto: string) {
    if (entre === null || !/^\d{4}-\d{2}-\d{2}$/.test(texto)) return;
    const dia = diaDeInstante(texto);
    const nuevo = { ...entre, [extremo]: dia };
    if (nuevo.hasta < nuevo.desde) {
      if (extremo === "desde") nuevo.hasta = dia;
      else nuevo.desde = dia;
    }
    onSeleccion({ clase: "entre", periodo: nuevo });
  }

  const campo = "control min-h-11 rounded-sm border border-linea px-2 text-xs text-texto esc:min-h-8";
  // Un desplegable con valor va en claro (estilos.css): sin el color de texto claro del campo.
  const campoActivo = (activo: boolean) => (activo ? campo.replace(" text-texto", "") : campo);
  return (
    <div role="group" aria-label={t.filtros.titulo} className="flex flex-col gap-4" data-filtros="">
      <div className="flex flex-col gap-1.5">
        <label className="flex flex-col gap-1.5 text-xs">
          <span className="text-secundario">{t.filtros.recientes}</span>
          <select
            className={`${campoActivo(clave !== "todo")} w-full`}
            value={clave}
            data-activo={clave !== "todo" ? "" : undefined}
            data-periodo=""
            onChange={(evento) => elegirClave(evento.target.value as ClavePeriodo)}
          >
            {CLAVES_PERIODO.map((opcion) => (
              <option key={opcion} value={opcion} className="bg-panel-solido text-texto">
                {t.filtros.periodos[opcion]}
              </option>
            ))}
          </select>
        </label>
        {clave === "entre" && entre !== null && (
          <div className="flex flex-wrap gap-2">
            <label className="flex flex-1 flex-col gap-1 text-xs">
              <span className="text-secundario">{t.filtros.desde}</span>
              <input
                type="date"
                className={campo}
                value={textoDeDia(entre.desde)}
                {...limites}
                data-desde=""
                onChange={(evento) => cambiarFecha("desde", evento.target.value)}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-xs">
              <span className="text-secundario">{t.filtros.hasta}</span>
              <input
                type="date"
                className={campo}
                value={textoDeDia(entre.hasta)}
                {...limites}
                data-hasta=""
                onChange={(evento) => cambiarFecha("hasta", evento.target.value)}
              />
            </label>
          </div>
        )}
      </div>
      <Grupo rotulo={t.filtros.estado}>
        {ESTADOS.map((estado) => (
          <Opcion
            key={estado}
            activa={filtros.estados.includes(estado)}
            onClick={() => onFiltros({ ...filtros, estados: alternar(filtros.estados, estado) })}
          >
            <Simbolo estado={estado} />
            {t.estado[estado]}
          </Opcion>
        ))}
      </Grupo>
      <Grupo rotulo={t.filtros.zona}>
        <Opcion activa={filtros.zona === null} onClick={() => onFiltros({ ...filtros, zona: null })}>
          {t.filtros.zonas.todas}
        </Opcion>
        {ZONAS.map((zona) => (
          <Opcion
            key={zona}
            activa={filtros.zona === zona}
            onClick={() => onFiltros({ ...filtros, zona: filtros.zona === zona ? null : zona })}
          >
            {t.filtros.zonas[zona]}
          </Opcion>
        ))}
      </Grupo>
      <Grupo rotulo={t.filtros.tipo}>
        {TIPOS.map((tipo) => (
          <Opcion
            key={tipo}
            activa={filtros.tipos.includes(tipo)}
            onClick={() => onFiltros({ ...filtros, tipos: alternar(filtros.tipos, tipo) })}
          >
            {t.tipo[tipo]}
          </Opcion>
        ))}
      </Grupo>
      <label className="flex flex-col gap-1.5 text-xs">
        <span className="text-secundario">{t.filtros.pais}</span>
        <select
          className={`${campoActivo(elegido !== "")} w-full`}
          value={elegido}
          data-activo={elegido !== "" ? "" : undefined}
          onChange={(evento) =>
            onFiltros({
              ...filtros,
              paises: evento.target.value === "" ? [] : [evento.target.value],
            })
          }
        >
          <option value="" className="bg-panel-solido text-texto">
            {t.filtros.todosLosPaises}
          </option>
          {ordenados.map((codigo) => (
            <option key={codigo} value={codigo} className="bg-panel-solido text-texto">
              {pais(codigo, idioma)}
            </option>
          ))}
        </select>
      </label>
      {(hayFiltros(filtros) || seleccion.clase !== "todo") && (
        <button
          type="button"
          className="control min-h-11 self-start text-xs text-texto underline underline-offset-2 esc:min-h-8"
          onClick={onQuitar}
        >
          {t.filtros.quitar}
        </button>
      )}
    </div>
  );
}

/**
 * «Aplicar», al pie del panel de filtros y fuera de lo que se desplaza: los filtros ya se aplican
 * mientras se eligen; el botón cierra el panel y encuadra lo que queda a la vista. Sin cifras: los
 * filtros también cambian otras capas (la de Ucrania) y un número solo de incidentes confundiría.
 */
export function BotonAplicar({ t, onAplicar }: { t: Textos; onAplicar: () => void }) {
  return (
    <button
      type="button"
      className="control control-principal min-h-11 w-full rounded-sm px-4 text-sm esc:min-h-9"
      onClick={onAplicar}
      data-aplicar=""
    >
      {t.filtros.aplicar}
    </button>
  );
}
