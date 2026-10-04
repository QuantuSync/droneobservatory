import { Map as MapaGL, addProtocol, setWorkerUrl } from "maplibre-gl";
import type {
  ExpressionSpecification,
  GeoJSONSource,
  MapGeoJSONFeature,
  MapMouseEvent,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// El trabajador de MapLibre se sirve desde este mismo sitio, empaquetado con el resto.
import urlTrabajador from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import { useEffect, useRef, useState } from "react";

import type { Capas } from "../componentes/Controles.tsx";
import { avisosEnMapa } from "../datos/directo.ts";
import type { Aviso } from "../datos/directo.ts";
import { celdasEnMapa } from "../datos/gnss.ts";
import type { CeldaGnss } from "../datos/gnss.ts";
import { escalones } from "../datos/presion.ts";
import type { PresionPais } from "../datos/presion.ts";
import type { CiudadSinLuz, Corredor, FocoVivo } from "../datos/guerraSatelite.ts";
import type {
  EpisodioResumen,
  FilaImpacto,
  FocoRegion,
  IncidenteResumen,
} from "../datos/tipos.ts";
import { pais as nombrePais, porcentaje } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { BANDERA, ESCALA_UCRANIA, acento } from "../paleta.ts";
import { opacidadDePerdida } from "../datos/guerraSatelite.ts";
import type { Idioma } from "../sitio.ts";
import type { Periodo } from "../tiempo/dias.ts";
import { movimientoReducido } from "./animacion.ts";
import {
  CAPAS_DE_CORREDORES,
  CAPAS_DE_DENSIDAD,
  CAPAS_DE_GNSS,
  CAPAS_DE_INCIDENTES,
  CAPAS_DE_PRESION,
  CAPAS_DE_UCRANIA,
  CAPAS_PULSABLES,
  CAPA_BANDERAS,
  CAPA_DIRECTO,
  CAPA_GNSS,
  CAPAS_DE_FOCOS_VIVOS,
  CAPAS_DE_LUZ,
  CAPA_CORREDORES,
  CAPA_FOCOS_VIVOS_IMPACTO,
  CAPA_LUZ_CIUDADES,
  CAPA_LUZ_REGIONES,
  CAPA_LUZ_REGIONES_RUSIA,
  FUENTE_CORREDORES,
  FUENTE_FOCOS_VIVOS,
  FUENTE_LUZ_CIUDADES,
  CAPA_GRUPOS,
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_INCIDENTES_GRAVES,
  CAPA_PRESION,
  CAPA_PRESION_LINEA,
  CAPA_PAIS,
  CAPA_IMPACTOS,
  CAPA_IMPACTOS_GRUPOS,
  CAPA_REGIONES,
  CAPA_REGIONES_RUSIA,
  CAPA_REGION_ELEGIDA,
  CAPA_REGION_ELEGIDA_RUSIA,
  FUENTE_AREAS,
  FUENTE_BANDERAS,
  FUENTE_DIRECTO,
  FUENTE_GNSS,
  FUENTE_IMPACTOS,
  FUENTE_EPISODIOS,
  FUENTE_FOCOS_UCRANIA,
  FUENTE_PUNTOS,
  FUENTE_PUNTOS_SUELTOS,
  FUENTE_SELECCION,
  ZOOM_MAXIMO_AGRUPADO,
  capasBase,
  estilo,
} from "./estilo.ts";
import {
  areas,
  banderas,
  ciudadesSinLuzEnMapa,
  corredoresEnMapa,
  focosDeRegiones,
  focosVivosEnMapa,
  impactosEnMapa,
  lineasDeEpisodio,
  pilas,
  sinAtribuidos,
} from "./geometria.ts";
import { registrarIconos } from "./iconos.ts";
import { colocarLetrero, hayRaton } from "./letrero.ts";
import { colocarPulsos, pulsosDe } from "./pulsos.ts";

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
/** Zoom al que vuela el mapa al abrir la ficha de un incidente, si estaba más lejos. */
const ZOOM_DE_FICHA = 8;
const DURACION_VUELO_MS = 1100;
/** Caja de Ucrania para encuadrar un ataque o una región. */
const CAJA_UCRANIA: [number, number, number, number] = [22.1, 44.3, 40.3, 52.4];
const MARGEN_ENCUADRE_PX = 40;

/**
 * Deja que el navegador pinte primero la respuesta a un clic (el botón pulsado, el filtro
 * marcado) y cambia el mapa justo después: repintarlo es lo que más cuesta en un móvil, y
 * hacerlo en el mismo fotograma retrasa la respuesta. Devuelve cómo cancelarlo.
 */
function trasPintar(tarea: () => void): () => void {
  let temporizador: ReturnType<typeof setTimeout> | undefined;
  const cuadro = window.requestAnimationFrame(() => {
    temporizador = setTimeout(tarea, 0);
  });
  return () => {
    window.cancelAnimationFrame(cuadro);
    if (temporizador !== undefined) clearTimeout(temporizador);
  };
}

function margenes(reserva: Reserva, margen: number) {
  return {
    top: reserva.arriba + margen,
    right: reserva.derecha + margen,
    bottom: reserva.abajo + margen,
    left: reserva.izquierda + margen,
  };
}

export type Encuadre = { lon: number; lat: number; zoom?: number } | "ucrania";

export interface ApiMapa {
  /** Posición en pantalla (relativa al contenedor del mapa) de una coordenada. */
  proyectar: (lon: number, lat: number) => { x: number; y: number };
  /** Avisa en cada fotograma en que el mapa se mueve; devuelve cómo dejar de avisar. */
  alMover: (aviso: () => void) => () => void;
  /** Acerca (paso positivo) o aleja el mapa. */
  zoom: (paso: number) => void;
  /** Vuelve a la vista inicial: Europa entera, en el hueco que deja libre la interfaz. */
  vistaInicial: () => void;
  /** Vuela a un punto o a Ucrania, como al abrir una ficha. */
  volar: (destino: Encuadre) => void;
}

/** Lo que tapa el mapa por cada lado (cabecera, filtros, paneles, hoja inferior), en px. */
export interface Reserva {
  arriba: number;
  derecha: number;
  abajo: number;
  izquierda: number;
}

export interface PropsMapa {
  t: Textos;
  idioma: Idioma;
  /** Incidentes que pasan los filtros y el periodo. */
  incidentes: readonly IncidenteResumen[];
  porId: ReadonlyMap<string, IncidenteResumen>;
  episodios: readonly EpisodioResumen[];
  capas: Capas;
  /** Ataques por región de Ucrania en el periodo; null si la capa no está cargada. */
  intensidad: ReadonlyMap<string, number> | null;
  /** Intensidad de una sola noche mientras se reproduce la guerra noche a noche. */
  noche: ReadonlyMap<string, number> | null;
  /** Regiones de Ucrania con foco térmico detectado en el periodo; null sin la capa. */
  focosUcrania: readonly FocoRegion[] | null;
  /** Impactos con lugar de la capa de guerra en el periodo; null sin la capa. */
  impactos: readonly FilaImpacto[] | null;
  /** Celdas de interferencia GPS del periodo; null sin la capa o sin datos. */
  gnss: readonly CeldaGnss[] | null;
  /** Incidentes por país del periodo y su tendencia; null sin la capa. */
  presion: ReadonlyMap<string, PresionPais> | null;
  /** Avisos de la detección en directo. */
  avisos: readonly Aviso[];
  /** Corredores de ataque del periodo; null sin la capa. */
  corredores: readonly Corredor[] | null;
  /** Mayor pérdida de luz (en %) de cada región en el periodo; null sin la capa. */
  luzRegiones: ReadonlyMap<string, number> | null;
  /** Ciudades que perdieron luz en el periodo; null sin la capa. */
  ciudadesSinLuz: readonly CiudadSinLuz[] | null;
  /** Focos de calor de las últimas 24 horas; null si no se han cargado. */
  focosVivos: readonly FocoVivo[] | null;
  elegido: IncidenteResumen | null;
  paisResaltado: string | null;
  regionesElegidas: readonly string[];
  novedades: ReadonlySet<string>;
  /** Las últimas 24 horas, para el destello de lo reciente (lo mismo que el filtro). */
  recientes: Periodo;
  encuadre: Encuadre | null;
  /** Lo que tapa el mapa: al volar a una ficha, lo abierto queda en el hueco libre. */
  reserva: Reserva;
  onIncidente: (id: string) => void;
  onPila: (ids: string[]) => void;
  onRegion: (codigo: string) => void;
  onImpacto: (id: string) => void;
  onAviso: (id: string) => void;
  onCelda: (h3: string) => void;
  onPais: (iso: string) => void;
  onCorredor: (clave: string) => void;
  onCiudadLuz: (clave: string) => void;
  onListo: (api: ApiMapa) => void;
  onFallo: () => void;
}

/**
 * Opacidad del relleno de una región según sus ataques, en los escalones de la leyenda. Las
 * regiones de Ucrania y las de Rusia se escalan cada una con su máximo: los partes rusos citan
 * muchas más regiones cada noche y apagarían a las ucranianas.
 */
function opacidadPorRegion(
  todas: ReadonlyMap<string, number>,
  rusas: boolean,
): ExpressionSpecification | number {
  const intensidad = new Map(
    [...todas].filter(([codigo]) => codigo.startsWith("RU-") === rusas),
  );
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

/** Oscurecimiento de las regiones con pérdida de luz: más pérdida, más oscuro. */
function opacidadDeLuz(perdidas: ReadonlyMap<string, number>): ExpressionSpecification | number {
  if (perdidas.size === 0) return 0;
  const pares: (string | number)[] = [];
  for (const [codigo, perdida] of perdidas) pares.push(codigo, opacidadDePerdida(perdida));
  return ["match", ["get", "iso"], ...pares, 0] as unknown as ExpressionSpecification;
}

function fuente(mapa: MapaGL, id: string): GeoJSONSource | undefined {
  return mapa.getSource<GeoJSONSource>(id);
}

/** Objetivo táctil de una marca del mapa, como el resto de controles en el teléfono. */
export const OBJETIVO_TACTIL_PX = 44;
const CAPAS_DE_MARCAS = [CAPA_DIRECTO, CAPA_BANDERAS, CAPA_INCIDENTES_GRAVES, CAPA_INCIDENTES_DISCRETOS, CAPA_GRUPOS];

function punteroGrueso(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)").matches;
}

/** La marca (incidente, grupo o aviso) más cercana a un punto dentro del objetivo táctil. */
function marcaMasCercana(mapa: MapaGL, x: number, y: number): MapGeoJSONFeature | undefined {
  const medio = OBJETIVO_TACTIL_PX / 2;
  const capas = CAPAS_DE_MARCAS.filter((id) => mapa.getLayer(id) !== undefined);
  const rasgos = mapa.queryRenderedFeatures(
    [
      [x - medio, y - medio],
      [x + medio, y + medio],
    ],
    { layers: capas },
  );
  let mejor: MapGeoJSONFeature | undefined;
  let distancia = Infinity;
  for (const rasgo of rasgos) {
    if (rasgo.geometry.type !== "Point") continue;
    const [lon, lat] = rasgo.geometry.coordinates as [number, number];
    const p = mapa.project([lon, lat]);
    // Una bandera se toca por lo que se ve: el centro del paño y el mástil, no solo el pie.
    const alto = rasgo.layer.id === CAPA_BANDERAS ? BANDERA.mastil / 2 : 0;
    const d = Math.hypot(p.x - x, p.y - alto - y);
    if (d < distancia) {
      distancia = d;
      mejor = rasgo;
    }
  }
  return mejor;
}

function capasActivas(mapa: MapaGL): string[] {
  return CAPAS_PULSABLES.filter((id) => mapa.getLayer(id) !== undefined);
}

export default function Mapa(props: PropsMapa) {
  const { t, idioma, incidentes, episodios, capas, intensidad, noche, elegido } = props;
  const { focosUcrania, impactos, gnss, presion, avisos } = props;
  const { corredores, luzRegiones, ciudadesSinLuz, focosVivos } = props;
  const { paisResaltado, regionesElegidas, novedades, recientes, encuadre, reserva } = props;
  // El vuelo lee la reserva del momento, pero no se repite porque cambie (al arrastrar una hoja).
  const reservaActual = useRef(reserva);
  reservaActual.current = reserva;
  const contenedor = useRef<HTMLDivElement>(null);
  const letrero = useRef<HTMLDivElement>(null);
  const textoLetrero = useRef<HTMLSpanElement>(null);
  const capaPulsos = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<MapaGL | null>(null);
  const volar = useRef<((destino: Encuadre) => void) | null>(null);
  const [listo, setListo] = useState(false);
  const [iconos, setIconos] = useState("");
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
        style: estilo(idiomaInicial.current, window.location.origin, acento()),
        bounds: VISTA_INICIAL,
        fitBoundsOptions: { padding: margenes(reservaActual.current, MARGEN_VISTA_INICIAL_PX) },
        minZoom: ZOOM_MINIMO,
        maxZoom: ZOOM_MAXIMO,
        maxBounds: LIMITES,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
      });
    } catch {
      // Sin WebGL no hay mapa; la lista y el feed siguen funcionando.
      manejadores.current.onFallo();
      return undefined;
    }
    mapaRef.current = mapa;
    mapa.touchZoomRotate.disableRotation();
    mapa.keyboard.disableRotation();

    function volarA(destino: Encuadre) {
      const animate = !movimientoReducido();
      if (destino === "ucrania") {
        mapa.fitBounds(CAJA_UCRANIA, {
          padding: margenes(reservaActual.current, MARGEN_ENCUADRE_PX),
          animate,
          duration: DURACION_VUELO_MS,
        });
        return;
      }
      mapa.flyTo({
        center: [destino.lon, destino.lat],
        zoom: destino.zoom ?? Math.max(mapa.getZoom(), ZOOM_DE_FICHA),
        // El símbolo queda en el hueco que dejan a la vista la cabecera y la ficha.
        padding: margenes(reservaActual.current, 0),
        duration: DURACION_VUELO_MS,
        animate,
      });
    }
    volar.current = volarA;

    mapa.on("load", () => {
      const delMapaBase = new Set(mapa.listImages());
      registrarIconos(mapa, acento());
      // Los iconos que la web pone en el mapa (sin los del mapa de fondo), a la vista en el
      // documento para comprobarlos desde fuera.
      setIconos(
        mapa
          .listImages()
          .filter((nombre) => !delMapaBase.has(nombre))
          .sort()
          .join(" "),
      );
      setListo(true);
      manejadores.current.onListo({
        proyectar: (lon, lat) => mapa.project([lon, lat]),
        zoom: (paso) =>
          mapa.easeTo({ zoom: mapa.getZoom() + paso, animate: !movimientoReducido() }),
        vistaInicial: () =>
          mapa.fitBounds(VISTA_INICIAL, {
            padding: margenes(reservaActual.current, MARGEN_VISTA_INICIAL_PX),
            animate: !movimientoReducido(),
            duration: DURACION_VUELO_MS,
          }),
        volar: volarA,
        alMover: (aviso) => {
          mapa.on("move", aviso);
          mapa.on("resize", aviso);
          return () => {
            mapa.off("move", aviso);
            mapa.off("resize", aviso);
          };
        },
      });
    });

    function primeroBajo(evento: MapMouseEvent): MapGeoJSONFeature | undefined {
      const exacto = mapa.queryRenderedFeatures(evento.point, { layers: capasActivas(mapa) })[0];
      if (exacto !== undefined || !punteroGrueso()) return exacto;
      // Con el dedo, el objetivo de cada marca es de 44 px: la más cercana dentro de ese cuadro.
      return marcaMasCercana(mapa, evento.point.x, evento.point.y);
    }

    function textoDeLetrero(rasgo: MapGeoJSONFeature): string | null {
      const { t: textos, idioma: lengua, porId } = manejadores.current;
      const p = rasgo.properties;
      if (rasgo.layer.id === CAPA_GRUPOS) {
        return "point_count" in p ? textos.mapa.grupo(Number(p.total)) : textos.mapa.pila(Number(p.n));
      }
      if (rasgo.layer.id === CAPA_REGIONES || rasgo.layer.id === CAPA_REGIONES_RUSIA) {
        return textos.regiones[String(p.iso)] ?? String(p.iso);
      }
      if (rasgo.layer.id === CAPA_IMPACTOS_GRUPOS) {
        return textos.mapa.grupoImpactos(Number(p.point_count));
      }
      if (rasgo.layer.id === CAPA_IMPACTOS) {
        return textos.mapa.impacto(Number(p.parte) === 1, Number(p.foco) === 1);
      }
      if (rasgo.layer.id === CAPA_DIRECTO) {
        const aviso = manejadores.current.avisos.find((a) => a.id === String(p.id));
        return aviso === undefined
          ? null
          : `${aviso.nombre} (${aviso.oaci}) · ${textos.directo.estado[aviso.estado]}`;
      }
      if (rasgo.layer.id === CAPA_GNSS) {
        return textos.gnss.letrero(porcentaje(Number(p.proporcion), lengua));
      }
      if (rasgo.layer.id === CAPA_PRESION) {
        const iso = String(p.iso);
        const cuenta = manejadores.current.presion?.get(iso)?.incidentes ?? 0;
        return textos.presion.letrero(nombrePais(iso, lengua), cuenta);
      }
      if (rasgo.layer.id === CAPA_CORREDORES) {
        const corredor = manejadores.current.corredores?.find((c) => c.clave === String(p.clave));
        if (corredor === undefined) return null;
        const origen =
          corredor.origen === null
            ? textos.satelite.corredor.desdeUcrania
            : textos.satelite.zona(corredor.clave.split("|")[0] ?? "", corredor.origen);
        return textos.satelite.letreroCorredor(
          origen,
          textos.regiones[corredor.region] ?? corredor.region,
          new Intl.NumberFormat(lengua).format(corredor.drones),
        );
      }
      if (rasgo.layer.id === CAPA_LUZ_CIUDADES) {
        return textos.satelite.letreroCiudad(String(p.nombre), String(p.perdida));
      }
      if (rasgo.layer.id === CAPA_FOCOS_VIVOS_IMPACTO) {
        return textos.satelite.letreroFoco(String(p.hora).slice(11, 16), true);
      }
      const incidente = porId.get(String(p.id));
      if (incidente === undefined) return null;
      return `${textos.tipo[incidente.tipo]} · ${textos.estado[incidente.estado]} · ${
        incidente.titulo[lengua]
      }`;
    }

    function esconderLetrero() {
      if (letrero.current !== null) letrero.current.hidden = true;
    }

    mapa.on("click", (evento: MapMouseEvent) => {
      // Al abrir una ficha (o tocar el mapa), el letrero desaparece.
      esconderLetrero();
      const primero = primeroBajo(evento);
      if (primero === undefined) return;
      const propiedades = primero.properties;
      if (primero.layer.id === CAPA_GRUPOS && Number(propiedades.n) > 1) {
        // Varios incidentes en el mismo punto exacto: se elige cuál abrir.
        manejadores.current.onPila(String(propiedades.ids).split(","));
      } else if (primero.layer.id === CAPA_GRUPOS) {
        // Un grupo se separa al acercar: se va al zoom en que deja de agruparse.
        mapa.easeTo({
          center: evento.lngLat,
          zoom: Math.max(mapa.getZoom() + 1.5, ZOOM_MAXIMO_AGRUPADO + 0.5),
          animate: !movimientoReducido(),
        });
      } else if (primero.layer.id === CAPA_IMPACTOS_GRUPOS) {
        // Un grupo de impactos se abre al zoom en que se separa.
        const fuenteImpactos = fuente(mapa, FUENTE_IMPACTOS);
        void fuenteImpactos
          ?.getClusterExpansionZoom(Number(propiedades.cluster_id))
          .then((zoom) =>
            mapa.easeTo({ center: evento.lngLat, zoom, animate: !movimientoReducido() }),
          );
      } else if (primero.layer.id === CAPA_IMPACTOS) {
        manejadores.current.onImpacto(String(propiedades.id));
      } else if (primero.layer.id === CAPA_DIRECTO) {
        manejadores.current.onAviso(String(propiedades.id));
      } else if (primero.layer.id === CAPA_GNSS) {
        manejadores.current.onCelda(String(propiedades.h3));
      } else if (primero.layer.id === CAPA_PRESION) {
        manejadores.current.onPais(String(propiedades.iso));
      } else if (primero.layer.id === CAPA_FOCOS_VIVOS_IMPACTO) {
        manejadores.current.onImpacto(String(propiedades.impacto));
      } else if (primero.layer.id === CAPA_CORREDORES) {
        manejadores.current.onCorredor(String(propiedades.clave));
      } else if (primero.layer.id === CAPA_LUZ_CIUDADES) {
        manejadores.current.onCiudadLuz(String(propiedades.clave));
      } else if (
        primero.layer.id === CAPA_REGIONES || primero.layer.id === CAPA_REGIONES_RUSIA
      ) {
        manejadores.current.onRegion(String(propiedades.iso));
      } else {
        manejadores.current.onIncidente(String(propiedades.id));
      }
    });

    // Letrero al pasar el ratón: qué es cada símbolo, sin leyenda fija. Solo con ratón: en
    // una pantalla táctil el navegador simula un paso del ratón al tocar y el letrero se
    // quedaba fijo encima del mapa.
    mapa.on("mousemove", (evento: MapMouseEvent) => {
      const caja = letrero.current;
      if (caja === null) return;
      if (!hayRaton()) {
        caja.hidden = true;
        return;
      }
      const primero = primeroBajo(evento);
      mapa.getCanvas().style.cursor = primero === undefined ? "" : "pointer";
      const texto = primero === undefined ? null : textoDeLetrero(primero);
      if (texto === null) {
        caja.hidden = true;
        return;
      }
      if (textoLetrero.current !== null) textoLetrero.current.textContent = texto;
      caja.hidden = false;
      // Nunca se sale del mapa: se mide ya con su texto y se recoloca.
      const { x, y } = colocarLetrero(
        evento.point,
        { ancho: caja.offsetWidth, alto: caja.offsetHeight },
        { ancho: mapa.getContainer().clientWidth, alto: mapa.getContainer().clientHeight },
      );
      caja.style.transform = `translate(${x}px, ${y}px)`;
    });
    mapa.on("mouseout", esconderLetrero);
    mapa.on("touchstart", esconderLetrero);

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

  // Incidentes: un símbolo por punto, áreas de precisión y líneas de episodio.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      const opciones = { recientes, novedades };
      fuente(mapa, FUENTE_PUNTOS)?.setData(pilas(sinAtribuidos(incidentes), opciones));
      fuente(mapa, FUENTE_BANDERAS)?.setData(banderas(incidentes, opciones));
      fuente(mapa, FUENTE_PUNTOS_SUELTOS)?.setData(pilas(incidentes, opciones));
      fuente(mapa, FUENTE_AREAS)?.setData(areas(incidentes));
      fuente(mapa, FUENTE_EPISODIOS)?.setData(lineasDeEpisodio(episodios, incidentes));
    });
  }, [listo, incidentes, episodios, recientes, novedades]);

  // Con una ficha abierta, el letrero de ayuda no se queda encima.
  useEffect(() => {
    if (elegido !== null && letrero.current !== null) letrero.current.hidden = true;
  }, [elegido]);

  // Anillo del incidente elegido.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const punto = elegido?.punto ?? null;
    fuente(mapa, FUENTE_SELECCION)?.setData({
      type: "FeatureCollection",
      features:
        punto === null
          ? []
          : [
              {
                type: "Feature",
                geometry: { type: "Point", coordinates: [punto.lon, punto.lat] },
                properties: { estado: elegido?.estado ?? "notificado" },
              },
            ],
    });
  }, [listo, elegido]);

  // País de un incidente sin punto, resaltado de forma tenue.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    mapa.setFilter(CAPA_PAIS, ["==", ["get", "iso"], paisResaltado ?? ""]);
  }, [listo, paisResaltado]);

  // Capas visibles según los controles.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      const grupos: [readonly string[], boolean][] = [
        [CAPAS_DE_INCIDENTES, capas.incidentes],
        [CAPAS_DE_UCRANIA, capas.ucrania],
        [CAPAS_DE_DENSIDAD, capas.densidad],
        [CAPAS_DE_PRESION, capas.presion],
        [CAPAS_DE_GNSS, capas.gnss],
        [CAPAS_DE_CORREDORES, capas.ucrania && capas.corredores],
        [CAPAS_DE_LUZ, capas.ucrania && capas.luz],
        [CAPAS_DE_FOCOS_VIVOS, capas.ucrania && capas.focosVivos],
      ];
      for (const [ids, visible] of grupos) {
        for (const id of ids) {
          mapa.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
        }
      }
    });
  }, [listo, capas]);

  // Regiones de Ucrania: intensidad del periodo, o la de una noche durante la reproducción.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const actual = noche ?? intensidad;
    mapa.setPaintProperty(
      CAPA_REGIONES,
      "fill-opacity",
      actual === null ? 0 : opacidadPorRegion(actual, false),
    );
    // Durante la reproducción noche a noche (solo ataques contra Ucrania), Rusia se apaga.
    mapa.setPaintProperty(
      CAPA_REGIONES_RUSIA,
      "fill-opacity",
      noche !== null || intensidad === null ? 0 : opacidadPorRegion(intensidad, true),
    );
  }, [listo, intensidad, noche]);

  // Impactos con lugar de la capa de guerra.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      fuente(mapa, FUENTE_IMPACTOS)?.setData(impactosEnMapa(impactos ?? []));
    });
  }, [listo, impactos]);

  // Interferencia GPS del periodo.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      fuente(mapa, FUENTE_GNSS)?.setData(celdasEnMapa(gnss ?? []));
    });
  }, [listo, gnss]);

  // Presión por país: opacidad del gris según sus incidentes, y contorno de los que tienen.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const opacidades = presion === null ? new Map<string, number>() : escalones(presion);
    const pares = [...opacidades].flatMap(([iso, opacidad]) => [iso, opacidad]);
    mapa.setPaintProperty(
      CAPA_PRESION,
      "fill-opacity",
      pares.length === 0
        ? 0
        : (["match", ["get", "iso"], ...pares, 0] as unknown as ExpressionSpecification),
    );
    mapa.setFilter(CAPA_PRESION_LINEA, ["in", ["get", "iso"], ["literal", [...opacidades.keys()]]]);
  }, [listo, presion]);

  // Avisos de la detección en directo.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    fuente(mapa, FUENTE_DIRECTO)?.setData(avisosEnMapa(avisos));
  }, [listo, avisos]);

  // Corredores de ataque del periodo.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      fuente(mapa, FUENTE_CORREDORES)?.setData(corredoresEnMapa(corredores ?? []));
    });
  }, [listo, corredores]);

  // Pérdida de luz nocturna: regiones oscurecidas y ciudades.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      const regiones = luzRegiones ?? new Map<string, number>();
      const rusas = new Map([...regiones].filter(([c]) => c.startsWith("RU-")));
      const ucranianas = new Map([...regiones].filter(([c]) => !c.startsWith("RU-")));
      mapa.setPaintProperty(CAPA_LUZ_REGIONES, "fill-opacity", opacidadDeLuz(ucranianas));
      mapa.setPaintProperty(CAPA_LUZ_REGIONES_RUSIA, "fill-opacity", opacidadDeLuz(rusas));
      fuente(mapa, FUENTE_LUZ_CIUDADES)?.setData(ciudadesSinLuzEnMapa(ciudadesSinLuz ?? []));
    });
  }, [listo, luzRegiones, ciudadesSinLuz]);

  // Focos de calor de las últimas 24 horas.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    fuente(mapa, FUENTE_FOCOS_VIVOS)?.setData(focosVivosEnMapa(focosVivos ?? []));
  }, [listo, focosVivos]);

  // Focos térmicos de las regiones de Ucrania, en el centro de cada región.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    fuente(mapa, FUENTE_FOCOS_UCRANIA)?.setData(focosDeRegiones(focosUcrania ?? []));
  }, [listo, focosUcrania]);

  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const filtro: ExpressionSpecification = [
      "in", ["get", "iso"], ["literal", [...regionesElegidas]],
    ];
    mapa.setFilter(CAPA_REGION_ELEGIDA, filtro);
    mapa.setFilter(CAPA_REGION_ELEGIDA_RUSIA, filtro);
  }, [listo, regionesElegidas]);

  // Pulsos: solo los incidentes nuevos desde la última visita (y los grupos que los
  // contienen). Van fuera del mapa (ver pulsos.ts) y se recolocan cuando el mapa se mueve o
  // cambia lo dibujado.
  useEffect(() => {
    const mapa = mapaRef.current;
    const capa = capaPulsos.current;
    if (!listo || mapa === null || capa === null) return undefined;
    const recolocar = () => {
      const capas = [CAPA_GRUPOS, CAPA_INCIDENTES_GRAVES, CAPA_INCIDENTES_DISCRETOS, CAPA_BANDERAS].filter(
        (id) => mapa.getLayoutProperty(id, "visibility") !== "none",
      );
      const rasgos = capas.length === 0 ? [] : mapa.queryRenderedFeatures({ layers: capas });
      colocarPulsos(
        capa,
        pulsosDe(rasgos, (lon, lat) => mapa.project([lon, lat])),
      );
    };
    mapa.on("move", recolocar);
    mapa.on("idle", recolocar);
    recolocar();
    return () => {
      mapa.off("move", recolocar);
      mapa.off("idle", recolocar);
    };
  }, [listo]);

  // Vuelo suave al abrir una ficha.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null || encuadre === null) return;
    volar.current?.(encuadre);
  }, [listo, encuadre]);

  return (
    <div className="absolute inset-0">
      <div ref={contenedor} className="size-full" data-mapa-listo={listo} data-iconos={iconos} />
      <div ref={capaPulsos} aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden" />
      <div
        ref={letrero}
        hidden
        data-letrero=""
        className="flotante pointer-events-none absolute left-0 top-0 z-30 max-w-72 px-2 py-1 text-xs text-texto"
      >
        {/* El recorte a dos líneas va dentro: con el relleno de la caja asomaría la tercera. */}
        <span ref={textoLetrero} className="line-clamp-2" />
      </div>
    </div>
  );
}
