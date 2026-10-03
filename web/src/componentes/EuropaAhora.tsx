import type { NivelGnss } from "../datos/gnss.ts";
import { fechaDia, numero } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";

export type CifraAhora = "cierres" | "incidentes" | "drones" | "focos" | "gnss";
export const CIFRAS_AHORA: readonly CifraAhora[] = ["cierres", "incidentes", "drones", "focos", "gnss"];

/** Las cifras del momento; null en la que no ha llegado su fichero. */
export interface CifrasAhora {
  cierres: number | null;
  incidentes: number | null;
  drones: { lanzados: number; dia: number } | null;
  focos: number | null;
  gnss: { nivel: NivelGnss; altas: number; dia: number } | null;
}

interface Props {
  t: Textos;
  idioma: Idioma;
  cifras: CifrasAhora;
  onIr: (cifra: CifraAhora) => void;
}

const SIN_DATO = "—";

function valor(t: Textos, idioma: Idioma, cifras: CifrasAhora, cifra: CifraAhora): string | null {
  switch (cifra) {
    case "cierres":
      return cifras.cierres === null ? null : numero(cifras.cierres, idioma);
    case "incidentes":
      return cifras.incidentes === null ? null : numero(cifras.incidentes, idioma);
    case "drones":
      return cifras.drones === null ? null : numero(cifras.drones.lanzados, idioma);
    case "focos":
      return cifras.focos === null ? null : numero(cifras.focos, idioma);
    case "gnss":
      return cifras.gnss === null ? null : t.ahora.nivel[cifras.gnss.nivel];
  }
}

/** Color de estado de una cifra: solo los cierres en curso y la interferencia alta lo llevan. */
function claseDe(cifras: CifrasAhora, cifra: CifraAhora): string {
  if (cifra === "cierres" && (cifras.cierres ?? 0) > 0) return "text-notificado";
  if (cifra === "gnss" && cifras.gnss?.nivel === "alta") return "text-atribuido";
  return "text-texto";
}

/** Detalle que acompaña a una cifra: la noche de los drones, las celdas altas del día. */
function detalle(t: Textos, cifras: CifrasAhora, cifra: CifraAhora): string | null {
  if (cifra === "drones" && cifras.drones !== null) return fechaDia(cifras.drones.dia);
  if (cifra === "gnss" && cifras.gnss !== null && cifras.gnss.altas > 0) {
    return t.ahora.celdasAltas(cifras.gnss.altas);
  }
  return null;
}

/**
 * «Europa ahora»: cierres en curso, incidentes de 7 días, drones de la última noche, focos
 * térmicos de 7 días e interferencia GPS del día, una cifra por fila. Va dentro del desplegable
 * (escritorio) o de la hoja inferior (teléfono) que abre su botón. Cada cifra lleva al sitio
 * del mapa que la explica. Una cifra sin su fichero sale como «—».
 */
export function EuropaAhora({ t, idioma, cifras, onIr }: Props) {
  return (
    <ul aria-label={t.ahora.etiqueta} data-europa-ahora="" className="flex flex-col gap-1">
      {CIFRAS_AHORA.map((cifra) => {
        const texto = valor(t, idioma, cifras, cifra);
        const nombre = t.ahora[cifra];
        const extra = detalle(t, cifras, cifra);
        return (
          <li key={cifra}>
            <button
              type="button"
              data-cifra={cifra}
              className="control min-h-11 w-full justify-start gap-2 text-left text-sm esc:min-h-9"
              aria-label={`${t.ahora.ir(nombre)}: ${texto ?? t.ahora.sinDato}${extra === null ? "" : ` (${extra})`}`}
              onClick={() => onIr(cifra)}
            >
              <span className={`mono min-w-10 text-right font-medium ${claseDe(cifras, cifra)}`}>
                {texto ?? SIN_DATO}
              </span>
              <span className="text-secundario">
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
