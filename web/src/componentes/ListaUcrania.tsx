import type { ReactNode } from "react";

import type { Corredor } from "../datos/guerraSatelite.ts";
import type { FilaImpacto } from "../datos/tipos.ts";
import { fechaDia, numero, region } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { letreroDeCorredor } from "./GuerraSatelite.tsx";

/**
 * Impactos que se listan: los más recientes. Los demás están en la ficha de su región (que los
 * lista todos), así nadie tiene que recorrer miles uno a uno.
 */
export const IMPACTOS_EN_LISTA = 30;

interface Props {
  t: Textos;
  idioma: Idioma;
  /** Ataques por región en el periodo (las de Ucrania y las de Rusia). */
  intensidad: ReadonlyMap<string, number> | null;
  /** Impactos con lugar del periodo. */
  impactos: readonly FilaImpacto[] | null;
  /** Corredores dibujados; null si la subcapa está apagada. */
  corredores: readonly Corredor[] | null;
  onRegion: (codigo: string) => void;
  onImpacto: (fila: FilaImpacto) => void;
  onCorredor: (corredor: Corredor) => void;
  /** En el teléfono, filas de 44 px para el dedo. */
  grande?: boolean;
}

function Grupo({ titulo, abierto, children }: { titulo: string; abierto: boolean; children: ReactNode }) {
  return (
    <details open={abierto} className="border-b border-linea last:border-b-0">
      <summary className="rotulo cursor-pointer px-3 py-2 text-texto">{titulo}</summary>
      <ul className="pb-1">{children}</ul>
    </details>
  );
}

function Fila({ onClick, alto, children }: { onClick: () => void; alto: string; children: ReactNode }) {
  return (
    <li>
      <button type="button" className={`w-full px-3 py-1.5 text-left text-sm hover:bg-elevado ${alto}`} onClick={onClick}>
        {children}
      </button>
    </li>
  );
}

/**
 * La capa de Ucrania en lista, para el teclado y el lector de pantalla: lo mismo que el mapa en
 * el periodo, agrupado (regiones de Ucrania y de Rusia de la más atacada a la menos, los últimos
 * impactos y los corredores encendidos). Elegir una fila abre su ficha, como tocarla en el mapa.
 */
export function ListaUcrania(props: Props) {
  const { t, idioma, intensidad, impactos, corredores, onRegion, onImpacto, onCorredor, grande = false } = props;
  const textos = t.capaUcrania;
  const alto = grande ? "min-h-11" : "";
  const regiones = [...(intensidad ?? [])]
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const deUcrania = regiones.filter(([codigo]) => codigo.startsWith("UA-"));
  const deRusia = regiones.filter(([codigo]) => !codigo.startsWith("UA-"));
  const recientes = [...(impactos ?? [])]
    .sort((a, b) => b[1] - a[1] || b[0].localeCompare(a[0]))
    .slice(0, IMPACTOS_EN_LISTA);
  const totalImpactos = impactos?.length ?? 0;
  const filaRegion = ([codigo, n]: [string, number]) => (
    <Fila key={codigo} alto={alto} onClick={() => onRegion(codigo)}>
      {textos.region(region(codigo, idioma), numero(n, idioma))}
    </Fila>
  );
  const vacia = regiones.length === 0 && totalImpactos === 0 && (corredores?.length ?? 0) === 0;
  return (
    <div data-lista-ucrania="">
      <p className="px-3 py-2 text-xs text-secundario">{textos.explicacion}</p>
      {vacia && <p className="px-3 pb-2 text-sm text-secundario">{textos.vacia}</p>}
      {deUcrania.length > 0 && (
        <Grupo titulo={textos.regionesUcrania(deUcrania.length)} abierto>
          {deUcrania.map(filaRegion)}
        </Grupo>
      )}
      {deRusia.length > 0 && (
        <Grupo titulo={textos.regionesRusia(deRusia.length)} abierto={false}>
          {deRusia.map(filaRegion)}
        </Grupo>
      )}
      {recientes.length > 0 && (
        <Grupo titulo={textos.impactos(recientes.length, totalImpactos)} abierto={false}>
          {recientes.map((fila) => (
            <Fila key={fila[0]} alto={alto} onClick={() => onImpacto(fila)}>
              {textos.impacto(region(fila[8], idioma), fechaDia(fila[1]), fila[6] === 1, fila[5] === 1)}
            </Fila>
          ))}
        </Grupo>
      )}
      {corredores !== null && corredores.length > 0 && (
        <Grupo titulo={textos.corredores(corredores.length)} abierto={false}>
          {corredores.map((c) => (
            <Fila key={c.clave} alto={alto} onClick={() => onCorredor(c)}>
              {letreroDeCorredor(t, idioma, c)}
            </Fila>
          ))}
        </Grupo>
      )}
    </div>
  );
}
