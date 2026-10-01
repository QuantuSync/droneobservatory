import type { ReactNode } from "react";

import { ESTADOS, TIPOS } from "../datos/vocabulario.ts";
import { SIN_FILTROS, alternar, hayFiltros } from "../estado/filtros.ts";
import type { Filtros as EstadoFiltros, Reciente } from "../estado/filtros.ts";
import { pais } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { Simbolo } from "./Simbolo.tsx";

const RECIENTES: readonly Reciente[] = ["24h", "7d"];
/** El símbolo de cada estado en los filtros: la forma no importa aquí, solo el color. */
const TIPO_DE_MUESTRA = "sobrevuelo";

interface Props {
  t: Textos;
  idioma: Idioma;
  filtros: EstadoFiltros;
  onFiltros: (filtros: EstadoFiltros) => void;
  /** Países con algún incidente, para el selector. */
  paises: readonly string[];
  /** Apilado y con controles de 44 px, para el menú del teléfono; si no, una barra. */
  apilado?: boolean;
}

function Grupo({ rotulo, apilado, children }: { rotulo: string; apilado: boolean; children: ReactNode }) {
  return (
    <fieldset className={apilado ? "flex flex-col gap-1.5" : "flex items-center gap-1.5"}>
      <legend className={`text-xs text-secundario ${apilado ? "mb-1.5" : "float-left mr-1"}`}>
        {rotulo}
      </legend>
      <div className="flex flex-wrap items-center gap-1">{children}</div>
    </fieldset>
  );
}

function Opcion({
  activa,
  onClick,
  apilado,
  children,
}: {
  activa: boolean;
  onClick: () => void;
  apilado: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`control rounded-sm border border-linea text-xs ${apilado ? "min-h-11 px-3" : "min-h-7 px-2"}`}
      aria-pressed={activa}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

/**
 * Filtros rápidos en su contenedor, agrupados por categoría con su rótulo: estado, tipo,
 * periodo rápido y país. Todos los controles miden lo mismo y «Quitar filtros» aparece en
 * cuanto hay alguno puesto. Se guardan en la dirección.
 */
export function Filtros({ t, idioma, filtros, onFiltros, paises, apilado = false }: Props) {
  const ordenados = [...paises].sort((a, b) => pais(a, idioma).localeCompare(pais(b, idioma), idioma));
  const elegido = filtros.paises[0] ?? "";
  return (
    <div
      role="group"
      aria-label={t.filtros.titulo}
      className={
        apilado
          ? "flex flex-col gap-4"
          : "flex flex-wrap items-center gap-x-5 gap-y-1.5"
      }
    >
      <Grupo rotulo={t.filtros.estado} apilado={apilado}>
        {ESTADOS.map((estado) => (
          <Opcion
            key={estado}
            apilado={apilado}
            activa={filtros.estados.includes(estado)}
            onClick={() => onFiltros({ ...filtros, estados: alternar(filtros.estados, estado) })}
          >
            <Simbolo tipo={TIPO_DE_MUESTRA} estado={estado} />
            {t.estado[estado]}
          </Opcion>
        ))}
      </Grupo>
      <Grupo rotulo={t.filtros.tipo} apilado={apilado}>
        {TIPOS.map((tipo) => (
          <Opcion
            key={tipo}
            apilado={apilado}
            activa={filtros.tipos.includes(tipo)}
            onClick={() => onFiltros({ ...filtros, tipos: alternar(filtros.tipos, tipo) })}
          >
            <Simbolo tipo={tipo} estado="notificado" />
            {t.tipo[tipo]}
          </Opcion>
        ))}
      </Grupo>
      <Grupo rotulo={t.filtros.recientes} apilado={apilado}>
        {RECIENTES.map((opcion) => (
          <Opcion
            key={opcion}
            apilado={apilado}
            activa={filtros.reciente === opcion}
            onClick={() =>
              onFiltros({ ...filtros, reciente: filtros.reciente === opcion ? null : opcion })
            }
          >
            {opcion === "24h" ? t.filtros.ultimas24h : t.filtros.ultimos7d}
          </Opcion>
        ))}
      </Grupo>
      <label className={apilado ? "flex flex-col gap-1.5 text-xs" : "flex items-center gap-1.5 text-xs"}>
        <span className="text-secundario">{t.filtros.pais}</span>
        <select
          className={`control rounded-sm border border-linea text-xs text-texto ${
            apilado ? "min-h-11 w-full" : "min-h-7 px-2"
          }`}
          value={elegido}
          onChange={(evento) =>
            onFiltros({
              ...filtros,
              paises: evento.target.value === "" ? [] : [evento.target.value],
            })
          }
        >
          <option value="" className="bg-panel-solido">
            {t.filtros.todosLosPaises}
          </option>
          {ordenados.map((codigo) => (
            <option key={codigo} value={codigo} className="bg-panel-solido">
              {pais(codigo, idioma)}
            </option>
          ))}
        </select>
      </label>
      {hayFiltros(filtros) && (
        <button
          type="button"
          className={`control text-xs text-texto underline underline-offset-2 ${apilado ? "min-h-11" : "min-h-7"}`}
          onClick={() => onFiltros(SIN_FILTROS)}
        >
          {t.filtros.quitar}
        </button>
      )}
    </div>
  );
}
