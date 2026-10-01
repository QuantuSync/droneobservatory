import type { PropiedadesIncidente, TraficoAereo } from "../datos/tipos.ts";
import { fechaHora, numero, rango } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Fila } from "./Panel.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  trafico: TraficoAereo;
  /** Lo que declaran las fuentes, para mostrarlo al lado si la medida difiere. */
  consecuencias: PropiedadesIncidente["consecuencias"];
}

/** Lo declarado por las fuentes sobre la duración del cierre y los desvíos, o null. */
export function declarado(
  t: Textos,
  idioma: Idioma,
  consecuencias: PropiedadesIncidente["consecuencias"],
): string | null {
  const partes: string[] = [];
  const minutos = rango(consecuencias?.cierre?.minutos, idioma);
  if (minutos !== null) partes.push(t.trafico.duracion(minutos));
  const desviados = rango(consecuencias?.vuelos_desviados, idioma);
  if (desviados !== null) partes.push(t.trafico.desviados(desviados));
  return partes.length > 0 ? partes.join(" · ") : null;
}

/**
 * Línea «Cierre medido con tráfico aéreo real»: horas UTC, duración, vuelos desviados y en
 * espera según el archivo de adsb.lol y, si difiere, lo que declaran las fuentes.
 */
export function LineaTrafico({ t, idioma, trafico, consecuencias }: Props) {
  const { cierre } = trafico;
  const segunFuentes = cierre.difiere_de_declarado ? declarado(t, idioma, consecuencias) : null;
  const datos = trafico.datos?.[0];
  return (
    <Fila nombre={t.trafico.rotulo}>
      <span data-trafico-aereo="">{t.trafico.cierreMedido}</span>
      <span className="mono block text-xs text-secundario">
        <span className="whitespace-nowrap">{fechaHora(cierre.inicio.valor)}</span> –{" "}
        <span className="whitespace-nowrap">{fechaHora(cierre.fin.valor)}</span> ·{" "}
        <span className="whitespace-nowrap">
          {t.trafico.duracion(numero(cierre.duracion_min, idioma))}
        </span>
      </span>
      <span className="block text-xs text-secundario">
        <span className="whitespace-nowrap">
          {t.trafico.desviados(numero(cierre.vuelos_desviados, idioma))}
        </span>{" "}
        ·{" "}
        <span className="whitespace-nowrap">
          {t.trafico.enEspera(numero(cierre.vuelos_en_espera, idioma))}
        </span>
      </span>
      {segunFuentes !== null && (
        <span className="block text-xs text-secundario" data-trafico-declarado="">
          {t.trafico.declarado}: {segunFuentes}
        </span>
      )}
      {datos !== undefined && (
        <EnlaceExterno
          enlace={datos}
          aviso={t.ficha.enlaceExterno}
          avisoNoValido={t.ficha.enlaceNoValido}
          className="text-xs"
        >
          {t.trafico.datos}
        </EnlaceExterno>
      )}
    </Fila>
  );
}
