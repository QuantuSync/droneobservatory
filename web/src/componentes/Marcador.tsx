import { useEffect, useRef, useState } from "react";

import type { Cifras } from "../datos/derivar.ts";
import { numero } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { movimientoReducido } from "../mapa/animacion.ts";
import type { Idioma } from "../sitio.ts";

/** Lo que tarda una cifra en contar hacia arriba al cargar. */
const MS_CUENTA = 900;

/**
 * Cuenta hacia arriba la primera vez que la cifra llega en el navegador; después cambia sin
 * animación. En el HTML prerenderizado y con movimiento reducido, la cifra sale ya hecha.
 */
function useCifraAnimada(valor: number, activa: boolean): number {
  const [mostrada, setMostrada] = useState(valor);
  const contada = useRef(false);
  useEffect(() => {
    const sinAnimacion = typeof window.requestAnimationFrame !== "function";
    if (!activa || contada.current || movimientoReducido() || sinAnimacion) {
      setMostrada(valor);
      return undefined;
    }
    contada.current = true;
    let pedido = 0;
    const inicio = performance.now();
    const paso = (ahora: number) => {
      const avance = Math.min(1, (ahora - inicio) / MS_CUENTA);
      // Salida suave: rápido al principio y despacio al llegar.
      setMostrada(Math.round(valor * (1 - (1 - avance) ** 3)));
      if (avance < 1) pedido = window.requestAnimationFrame(paso);
    };
    pedido = window.requestAnimationFrame(paso);
    return () => window.cancelAnimationFrame(pedido);
  }, [valor, activa]);
  return mostrada;
}

export type Forma = "linea" | "rejilla";

function Cifra({
  valor,
  rotulo,
  idioma,
  activa,
  color,
  forma,
}: {
  valor: number;
  rotulo: string;
  idioma: Idioma;
  activa: boolean;
  color?: string;
  forma: Forma;
}) {
  const mostrada = useCifraAnimada(valor, activa);
  const tono = color ?? "text-texto";
  // En línea: la cifra y su rótulo uno tras otro, en pequeño. En rejilla: la cifra encima.
  return forma === "linea" ? (
    <div className="flex flex-row-reverse items-baseline gap-1">
      <dt className="text-xs text-secundario">{rotulo}</dt>
      <dd className={`cifra text-sm font-medium ${tono}`}>{numero(mostrada, idioma)}</dd>
    </div>
  ) : (
    <div className="flex flex-col-reverse gap-1">
      <dt className="text-xs text-secundario">{rotulo}</dt>
      <dd className={`cifra text-2xl font-medium leading-none ${tono}`}>{numero(mostrada, idioma)}</dd>
    </div>
  );
}

interface Props {
  t: Textos;
  idioma: Idioma;
  cifras: Cifras;
  /** Hay datos del navegador: las cifras pueden contar hacia arriba. */
  animar: boolean;
  forma?: Forma;
}

/** Cifras del periodo elegido (incidentes, confirmados, atribuidos y países), con su rótulo. */
export function Marcador({ t, idioma, cifras, animar, forma = "linea" }: Props) {
  return (
    <dl
      aria-label={t.marcador.etiqueta}
      className={forma === "linea" ? "flex items-baseline gap-2.5" : "grid grid-cols-2 gap-4"}
    >
      <Cifra valor={cifras.incidentes} rotulo={t.marcador.incidentes} idioma={idioma} activa={animar} forma={forma} />
      <Cifra
        valor={cifras.confirmados}
        rotulo={t.marcador.confirmados}
        idioma={idioma}
        activa={animar}
        forma={forma}
        color="text-confirmado"
      />
      <Cifra
        valor={cifras.atribuidos}
        rotulo={t.marcador.atribuidos}
        idioma={idioma}
        activa={animar}
        forma={forma}
        color="text-atribuido"
      />
      <Cifra valor={cifras.paises} rotulo={t.marcador.paises} idioma={idioma} activa={animar} forma={forma} />
    </dl>
  );
}
