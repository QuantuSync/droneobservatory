import type { IncidenteResumen } from "../datos/tipos.ts";
import { fechaDia, pais, region, textoAtribuido } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { Simbolo } from "./Simbolo.tsx";
import { Enlace } from "../navegacion.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  /** Incidentes del periodo elegido. */
  incidentes: readonly IncidenteResumen[];
  /** Regiones de Ucrania que se pueden abrir; vacío si la capa no está activa. */
  regiones: readonly string[];
  onRegion: (codigo: string) => void;
}

/**
 * Lista de los incidentes del periodo, del más reciente al más antiguo. Da con teclado y
 * lector de pantalla el mismo acceso a las fichas que el mapa.
 */
export function Lista({ t, idioma, incidentes, regiones, onRegion }: Props) {
  const ordenados = incidentes
    .slice()
    .sort((a, b) => b.dia - a.dia || b.id.localeCompare(a.id));
  return (
    <div>
      <h2 className="sr-only">{t.lista.titulo}</h2>
      <p className="mono px-1 pt-1 text-xs text-secundario">{t.lista.incidentes(ordenados.length)}</p>
      {ordenados.length === 0 && <p className="mt-3 text-secundario">{t.lista.vacia}</p>}
      <ul className="mt-2">
        {ordenados.map((incidente) => (
          <li key={incidente.id} className="border-b border-linea py-2">
            <Enlace
              a={rutaDeFicha(incidente.id, idioma)}
              className="flex items-start gap-2 rounded-sm px-1 py-0.5 hover:bg-elevado"
            >
              <Simbolo estado={incidente.estado} atribucion={incidente.atribucion} className="mt-0.5 shrink-0" />
              <span className="min-w-0">
                <span className="block">{incidente.titulo[idioma]}</span>
                <span className="mono block text-xs text-secundario">
                  {fechaDia(incidente.dia)} · {pais(incidente.pais, idioma)} ·{" "}
                  {incidente.estado === "atribuido"
                    ? textoAtribuido(t, idioma, incidente.atribucion)
                    : t.estado[incidente.estado]}
                  {incidente.punto === null && (
                    <span className="text-notificado"> · {t.imprecisa.etiqueta}</span>
                  )}
                </span>
              </span>
            </Enlace>
          </li>
        ))}
      </ul>
      {regiones.length > 0 && (
        <section className="mt-4">
          <h3 className="rotulo">{t.lista.regiones}</h3>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {regiones.map((codigo) => (
              <li key={codigo}>
                <button
                  type="button"
                  className="control min-h-7 text-xs"
                  onClick={() => onRegion(codigo)}
                >
                  {region(codigo, idioma)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
