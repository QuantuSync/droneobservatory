import type { Jornada } from "../datos/ucrania.ts";
import { jornadaEscrita, numero } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";

export type CifraAhora = "cierres" | "incidentes" | "drones" | "focos" | "gnss";
export const CIFRAS_AHORA: readonly CifraAhora[] = ["cierres", "incidentes", "drones", "focos", "gnss"];

/** Los drones de la última noche (o día) con cifra. */
export interface DronesAhora {
  lanzados: number;
  jornada: Jornada;
  /** Su último parte tiene más de 36 horas: ya no es «la última noche». */
  antiguo: boolean;
}

/** Las cifras del momento; null en la que no ha llegado su fichero. */
export interface CifrasAhora {
  cierres: number | null;
  incidentes: number | null;
  drones: DronesAhora | null;
  focos: number | null;
  /** Zonas con interferencia alta del último día publicado. */
  gnss: { zonas: number; dia: number } | null;
}

interface Props {
  t: Textos;
  idioma: Idioma;
  cifras: CifrasAhora;
  onIr: (cifra: CifraAhora) => void;
}

const SIN_DATO = "—";

/** El número de cada línea: siempre un número (o la raya si falta su fichero), nunca palabras. */
function valor(cifras: CifrasAhora, cifra: CifraAhora): number | null {
  switch (cifra) {
    case "cierres":
      return cifras.cierres;
    case "incidentes":
      return cifras.incidentes;
    case "drones":
      return cifras.drones?.lanzados ?? null;
    case "focos":
      return cifras.focos;
    case "gnss":
      return cifras.gnss?.zonas ?? null;
  }
}

/** Color de estado de una cifra: solo los cierres en curso y las zonas de interferencia alta. */
function claseDe(cifras: CifrasAhora, cifra: CifraAhora): string {
  if (cifra === "cierres" && (cifras.cierres ?? 0) > 0) return "text-notificado";
  if (cifra === "gnss" && (cifras.gnss?.zonas ?? 0) > 0) return "text-atribuido";
  return "text-texto";
}

/** El texto de cada línea; el de los drones depende de si el parte es de noche y de cuándo. */
function nombreDe(t: Textos, cifras: CifrasAhora, cifra: CifraAhora): string {
  const drones = cifras.drones;
  if (cifra !== "drones" || drones === null) return t.ahora[cifra];
  if (drones.antiguo) return t.ahora.dronesParte;
  return drones.jornada.tipo === "dia" ? t.ahora.dronesDia : t.ahora.drones;
}

/**
 * Detalle que acompaña al texto: lo que cubre el parte de los drones, escrito sin ambigüedad
 * («noche del 2 al 3 de octubre»), y «último parte: …» si ya tiene más de 36 horas.
 */
function detalle(t: Textos, cifras: CifrasAhora, cifra: CifraAhora): string | null {
  const drones = cifras.drones;
  if (cifra !== "drones" || drones === null) return null;
  const cuando = jornadaEscrita(t, drones.jornada);
  return drones.antiguo ? t.ahora.ultimoParte(cuando) : cuando;
}

/**
 * «Europa ahora»: cierres en curso, incidentes de 7 días, drones de la última noche, focos
 * térmicos de 7 días y zonas con interferencia GPS alta del día, una cifra por fila. Todas las
 * filas iguales: el número a la izquierda, alineado a la derecha en una columna fija en la que
 * caben cuatro cifras, y el texto a su derecha, que salta de línea dentro de su columna. Va
 * dentro del desplegable (escritorio) o de la hoja inferior (teléfono) que abre su botón. Cada
 * cifra lleva al sitio del mapa que la explica. Una cifra sin su fichero sale como «—».
 */
export function EuropaAhora({ t, idioma, cifras, onIr }: Props) {
  return (
    <ul aria-label={t.ahora.etiqueta} data-europa-ahora="" className="flex flex-col gap-1">
      {CIFRAS_AHORA.map((cifra) => {
        const n = valor(cifras, cifra);
        const texto = n === null ? null : numero(n, idioma);
        const nombre = nombreDe(t, cifras, cifra);
        const extra = detalle(t, cifras, cifra);
        return (
          <li key={cifra}>
            <button
              type="button"
              data-cifra={cifra}
              className="control grid min-h-11 w-full grid-cols-[3.25rem_minmax(0,1fr)] items-baseline justify-items-stretch gap-x-3 py-1.5 text-left text-sm esc:min-h-9"
              aria-label={`${t.ahora.ir(nombre)}: ${texto ?? t.ahora.sinDato}${extra === null ? "" : ` (${extra})`}`}
              onClick={() => onIr(cifra)}
            >
              <span
                data-numero=""
                className={`mono overflow-hidden text-right font-medium tabular-nums ${claseDe(cifras, cifra)}`}
              >
                {texto ?? SIN_DATO}
              </span>
              <span data-texto="" className="min-w-0 break-words text-secundario">
                {nombre}
                {extra !== null && ` · ${extra}`}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
