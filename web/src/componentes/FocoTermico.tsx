import type { FocoTermico } from "../datos/tipos.ts";
import { fechaHora } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { PALETA } from "../paleta.ts";
import type { Idioma } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Fila } from "./Panel.tsx";

/** Visor de NASA FIRMS. Solo se enlaza: la web no carga nada de terceros. */
export const VISOR_FIRMS = "https://firms.modaps.eosdis.nasa.gov/map/";
/** Zoom del visor: de cerca para un punto; más lejos para el centro de una región. */
export const ZOOM_VISOR_PUNTO = 11;
export const ZOOM_VISOR_REGION = 8;

/** El visor de FIRMS en el día del primer foco y en la posición dada. */
export function enlaceVisorFirms(primerFoco: string, lon: number, lat: number, zoom: number): string {
  const dia = primerFoco.slice(0, 10);
  return `${VISOR_FIRMS}#d:${dia}..${dia};@${lon.toFixed(3)},${lat.toFixed(3)},${zoom.toFixed(1)}z`;
}

/** Marca del foco térmico: un punto claro con borde oscuro, igual que en el mapa. */
export function MarcaFoco({ tamano = 10, color = PALETA.texto }: { tamano?: number; color?: string }) {
  return (
    <svg
      aria-hidden="true"
      width={tamano}
      height={tamano}
      viewBox="0 0 10 10"
      className="inline-block shrink-0"
      data-marca-foco=""
    >
      <circle cx="5" cy="5" r="3.6" fill={color} stroke={PALETA.fondo} strokeWidth="1.4" />
    </svg>
  );
}

interface Props {
  t: Textos;
  idioma: Idioma;
  foco: FocoTermico;
  /** Dónde abrir el visor: el punto del impacto o el centro de su región. */
  lon: number;
  lat: number;
  zoom: number;
  /** Para la ficha de una región: el ataque al que pertenece el foco. */
  ataque?: string;
  /** Color de la marca: blanco en los incidentes, el violeta claro en la capa de guerra. */
  color?: string;
}

/** Línea «Foco térmico detectado por satélite» con su hora, instrumento, distancia y enlace. */
export function LineaFoco({ t, idioma, foco, lon, lat, zoom, ataque, color }: Props) {
  const distancia = new Intl.NumberFormat(idioma, { maximumFractionDigits: 1 }).format(
    foco.distancia_km,
  );
  return (
    <Fila nombre={t.foco.rotulo}>
      <span className="flex items-center gap-1.5" data-foco-termico="">
        <MarcaFoco {...(color === undefined ? {} : { color })} />
        {t.foco.detectado}
      </span>
      <span className="mono block text-xs text-secundario">
        {ataque !== undefined && <>{ataque} · </>}
        <span className="whitespace-nowrap">{fechaHora(foco.primer_foco.valor)}</span> ·{" "}
        <span className="whitespace-nowrap">
          {foco.instrumento} ({foco.satelite})
        </span>{" "}
        · <span className="whitespace-nowrap">{t.foco.distancia(distancia)}</span>
      </span>
      <EnlaceExterno
        enlace={enlaceVisorFirms(foco.primer_foco.valor, lon, lat, zoom)}
        aviso={t.ficha.enlaceExterno}
        avisoNoValido={t.ficha.enlaceNoValido}
        className="text-xs"
      >
        {t.foco.visor}
      </EnlaceExterno>
    </Fila>
  );
}
