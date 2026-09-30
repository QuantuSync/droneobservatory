import { Map as MapaGL, addProtocol, setWorkerUrl } from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// El trabajador de MapLibre se sirve desde este mismo sitio, empaquetado con el resto.
import urlTrabajador from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import { useEffect, useRef, useState } from "react";

import type { Capas } from "../componentes/SelectorCapas.tsx";
import type { EpisodioResumen, IncidenteResumen } from "../datos/tipos.ts";
import type { Textos } from "../i18n/index.ts";
import { ESCALA_UCRANIA } from "../paleta.ts";
import type { Idioma } from "../sitio.ts";
import {
  CAPAS_DE_DENSIDAD,
  CAPAS_DE_INCIDENTES,
  CAPAS_DE_UCRANIA,
  CAPA_GRUPOS,
  CAPA_INCIDENTES,
  CAPA_REGIONES,
  CAPA_REGION_ELEGIDA,
  FUENTE_AREAS,
  FUENTE_EPISODIOS,
  FUENTE_PUNTOS,
  FUENTE_PUNTOS_SUELTOS,
  FUENTE_SELECCION,
  ZOOM_MAXIMO_AGRUPADO,
  capasBase,
  estilo,
} from "./estilo.ts";
import { areas, lineasDeEpisodio, puntos } from "./geometria.ts";
import { registrarIconos } from "./iconos.ts";

setWorkerUrl(urlTrabajador);
addProtocol("pmtiles", new Protocol().tile);

/** Vista inicial: Europa entera, de Portugal a los Urales y de Creta al cabo Norte. */
const VISTA_INICIAL: [number, number, number, number] = [-11, 35, 41, 69];
const MARGEN_VISTA_INICIAL_PX = 12;
const ZOOM_MINIMO = 2.2;
/** Dos niveles por encima del zoom 14 de las teselas: MapLibre amplía las vectoriales. */
const ZOOM_MAXIMO = 16;
/**
 * Límites del desplazamiento. Son mucho más anchos que Europa porque MapLibre no deja ver
 * nada fuera de ellos: en una pantalla ancha, unos límites ajustados obligarían a acercar
 * el mapa hasta cortar el continente por arriba y por abajo.
 */
const LIMITES: [number, number, number, number] = [-75, 12, 105, 83];
/** Zoom al que se acerca el mapa al abrir la ficha de un incidente, si estaba más lejos. */
const ZOOM_DE_FICHA = 7.5;
/** Caja de Ucrania para encuadrar un ataque o una región. */
const CAJA_UCRANIA: [number, number, number, number] = [22.1, 44.3, 40.3, 52.4];
const MARGEN_ENCUADRE_PX = 40;
/** Parte de la altura que tapa el panel inferior en móvil al abrir una ficha. */
const FRACCION_PANEL_MOVIL = 0.6;

export type Encuadre = { lon: number; lat: number } | "ucrania";

export interface PropsMapa {
  t: Textos;
  idioma: Idioma;
  /** Incidentes del periodo elegido. */
  incidentes: readonly IncidenteResumen[];
  episodios: readonly EpisodioResumen[];
  capas: Capas;
  /** Ataques por región de Ucrania en el periodo; null si la capa no está cargada. */
  intensidad: ReadonlyMap<string, number> | null;
  /** Incidente con la ficha abierta. */
  elegido: IncidenteResumen | null;
  /** Regiones de Ucrania resaltadas: la elegida o las de un ataque. */
  regionesElegidas: readonly string[];
  /** Lo que el mapa debe centrar; cambia cada vez que se abre una ficha. */
  encuadre: Encuadre | null;
  /** El panel de la ficha tapa la parte inferior del mapa (móvil). */
  panelInferior: boolean;
  onIncidente: (id: string) => void;
  onRegion: (codigo: string) => void;
  onFallo: () => void;
}

/** Opacidad del relleno de una región según sus ataques, en los escalones de la leyenda. */
function opacidadPorRegion(intensidad: ReadonlyMap<string, number>): ExpressionSpecification | number {
  const tope = Math.max(0, ...intensidad.values());
  if (tope === 0) return 0;
  const pares: (string | number)[] = [];
  for (const [codigo, ataques] of intensidad) {
    const escalon = Math.min(
      ESCALA_UCRANIA.length - 1,
      Math.floor((ataques / tope) * ESCALA_UCRANIA.length),
    );
    pares.push(codigo, ESCALA_UCRANIA[escalon] ?? 0);
  }
  return ["match", ["get", "iso"], ...pares, 0] as unknown as ExpressionSpecification;
}

function fuente(mapa: MapaGL, id: string): GeoJSONSource | undefined {
  return mapa.getSource<GeoJSONSource>(id);
}

function sinMovimiento(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function Mapa(props: PropsMapa) {
  const { t, idioma, incidentes, episodios, capas, intensidad, elegido, regionesElegidas } = props;
  const { encuadre, panelInferior } = props;
  const contenedor = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<MapaGL | null>(null);
  const [listo, setListo] = useState(false);
  // Los manejadores del mapa se registran una vez: leen siempre las funciones actuales.
  const manejadores = useRef(props);
  useEffect(() => {
    manejadores.current = props;
  });
  const idiomaInicial = useRef(idioma);

  useEffect(() => {
    const elemento = contenedor.current;
    if (elemento === null) return undefined;
    let mapa: MapaGL;
    try {
      mapa = new MapaGL({
        container: elemento,
        style: estilo(idiomaInicial.current, window.location.origin),
        bounds: VISTA_INICIAL,
        fitBoundsOptions: { padding: MARGEN_VISTA_INICIAL_PX },
        minZoom: ZOOM_MINIMO,
        maxZoom: ZOOM_MAXIMO,
        maxBounds: LIMITES,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
      });
    } catch {
      // Sin WebGL no hay mapa; la lista de incidentes sigue funcionando.
      manejadores.current.onFallo();
      return undefined;
    }
    mapaRef.current = mapa;
    mapa.touchZoomRotate.disableRotation();
    mapa.keyboard.disableRotation();

    mapa.on("load", () => {
      registrarIconos(mapa);
      setListo(true);
    });

    mapa.on("click", (evento: MapMouseEvent) => {
      const capasActivas = [CAPA_INCIDENTES, CAPA_GRUPOS, CAPA_REGIONES].filter(
        (id) => mapa.getLayer(id) !== undefined,
      );
      const [primero] = mapa.queryRenderedFeatures(evento.point, { layers: capasActivas });
      if (primero === undefined) return;
      if (primero.layer.id === CAPA_INCIDENTES) {
        manejadores.current.onIncidente(String(primero.properties.id));
      } else if (primero.layer.id === CAPA_GRUPOS) {
        // Un grupo se separa al acercar: se va al zoom en que deja de agruparse.
        mapa.easeTo({
          center: evento.lngLat,
          zoom: Math.max(mapa.getZoom() + 1.5, ZOOM_MAXIMO_AGRUPADO + 0.5),
        });
      } else {
        manejadores.current.onRegion(String(primero.properties.iso));
      }
    });

    mapa.on("mousemove", (evento: MapMouseEvent) => {
      const capasActivas = [CAPA_INCIDENTES, CAPA_GRUPOS, CAPA_REGIONES].filter(
        (id) => mapa.getLayer(id) !== undefined,
      );
      const hay = mapa.queryRenderedFeatures(evento.point, { layers: capasActivas }).length > 0;
      mapa.getCanvas().style.cursor = hay ? "pointer" : "";
    });

    return () => {
      mapaRef.current = null;
      mapa.remove();
    };
  }, []);

  // Rótulos de la base en el idioma de la web.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    for (const capa of capasBase(idioma)) {
      if (capa.type === "symbol" && capa.layout?.["text-field"] !== undefined) {
        mapa.setLayoutProperty(capa.id, "text-field", capa.layout["text-field"]);
      }
    }
    mapa.getCanvas().setAttribute("aria-label", t.mapa.etiqueta);
  }, [listo, idioma, t]);

  // Incidentes del periodo: puntos agrupables, áreas de precisión y líneas de episodio.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const coleccion = puntos(incidentes);
    fuente(mapa, FUENTE_PUNTOS)?.setData(coleccion);
    fuente(mapa, FUENTE_PUNTOS_SUELTOS)?.setData(coleccion);
    fuente(mapa, FUENTE_AREAS)?.setData(areas(incidentes));
    fuente(mapa, FUENTE_EPISODIOS)?.setData(lineasDeEpisodio(episodios, incidentes));
  }, [listo, incidentes, episodios]);

  // Anillo dorado del incidente elegido.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    fuente(mapa, FUENTE_SELECCION)?.setData(puntos(elegido === null ? [] : [elegido]));
  }, [listo, elegido]);

  // Capas visibles según el selector.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const grupos: [readonly string[], boolean][] = [
      [CAPAS_DE_INCIDENTES, capas.incidentes],
      [CAPAS_DE_UCRANIA, capas.ucrania],
      [CAPAS_DE_DENSIDAD, capas.densidad],
    ];
    for (const [ids, visible] of grupos) {
      for (const id of ids) {
        mapa.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      }
    }
  }, [listo, capas]);

  // Regiones de Ucrania coloreadas por intensidad en el periodo, y las resaltadas.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    mapa.setPaintProperty(
      CAPA_REGIONES,
      "fill-opacity",
      intensidad === null ? 0 : opacidadPorRegion(intensidad),
    );
  }, [listo, intensidad]);

  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    mapa.setFilter(CAPA_REGION_ELEGIDA, ["in", ["get", "iso"], ["literal", [...regionesElegidas]]]);
  }, [listo, regionesElegidas]);

  // Encuadre al abrir una ficha.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null || encuadre === null) return;
    const inferior = panelInferior ? mapa.getContainer().clientHeight * FRACCION_PANEL_MOVIL : 0;
    const padding = {
      top: MARGEN_ENCUADRE_PX,
      left: MARGEN_ENCUADRE_PX,
      right: MARGEN_ENCUADRE_PX,
      bottom: MARGEN_ENCUADRE_PX + inferior,
    };
    const animate = !sinMovimiento();
    if (encuadre === "ucrania") {
      mapa.fitBounds(CAJA_UCRANIA, { padding, animate });
    } else {
      mapa.easeTo({
        center: [encuadre.lon, encuadre.lat],
        zoom: Math.max(mapa.getZoom(), ZOOM_DE_FICHA),
        padding: { top: 0, left: 0, right: 0, bottom: inferior },
        animate,
      });
    }
  }, [listo, encuadre, panelInferior]);

  function zoom(paso: number) {
    mapaRef.current?.easeTo({ zoom: mapaRef.current.getZoom() + paso, animate: !sinMovimiento() });
  }

  return (
    <div className="absolute inset-0">
      <div ref={contenedor} className="size-full" data-mapa-listo={listo} />
      <div className="absolute right-3 top-3 z-10 flex flex-col gap-1">
        <button
          type="button"
          className="boton boton-discreto mono size-8 bg-superficie-1 p-0 text-base"
          aria-label={t.mapa.acercar}
          onClick={() => zoom(1)}
        >
          +
        </button>
        <button
          type="button"
          className="boton boton-discreto mono size-8 bg-superficie-1 p-0 text-base"
          aria-label={t.mapa.alejar}
          onClick={() => zoom(-1)}
        >
          −
        </button>
      </div>
    </div>
  );
}
