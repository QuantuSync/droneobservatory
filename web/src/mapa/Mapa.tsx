import { Map as MapaGL, addProtocol, setWorkerUrl } from "maplibre-gl";
import type {
  DataDrivenPropertyValueSpecification,
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

import { indiceBandera, varianteDe } from "../banderas.ts";
import type { Capas } from "../componentes/Controles.tsx";
import { avisosEnMapa } from "../datos/directo.ts";
import type { RutasEnMapa } from "../datos/rutas.ts";
import type { Aviso } from "../datos/directo.ts";
import { celdasEnMapa } from "../datos/gnss.ts";
import type { CeldaGnss } from "../datos/gnss.ts";
import { escalones } from "../datos/presion.ts";
import type { PresionPais } from "../datos/presion.ts";
import type {
  CiudadAlumbrado,
  CiudadSinLuz,
  Corredor,
  PuntoSatelite,
} from "../datos/guerraSatelite.ts";
import type {
  EpisodioResumen,
  FilaImpacto,
  FocoRegion,
  IncidenteResumen,
} from "../datos/tipos.ts";
import { fechaDia, pais as nombrePais, porcentaje, textoAtribuido } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { ESCALA_UCRANIA, acento } from "../paleta.ts";
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
  CAPAS_DE_AREAS,
  CAPAS_DE_PUNTOS_AL_TOQUE,
  CAPAS_DE_PUNTOS_DE_GUERRA,
  CAPA_CORREDORES_ZONA,
  CAPA_REALCE_ARCO,
  OPACIDAD_CORREDOR,
  OPACIDAD_CORREDOR_ATENUADO,
  ATENUADAS_SIN_SATELITE,
  CAPA_SATELITE,
  FUENTE_SATELITE,
  OPACIDAD_CORREDOR_SIN_SATELITE,
  CAPAS_PULSABLES,
  CAPA_ATRIBUIDOS,
  CAPA_DIRECTO,
  CAPA_GNSS,
  CAPAS_DE_LUZ,
  CAPA_CORREDORES,
  CAPA_LUZ_CIUDADES,
  CAPA_ALUMBRADO,
  CAPA_LUZ_REGIONES,
  CAPA_LUZ_REGIONES_RUSIA,
  FUENTE_CORREDORES,
  FUENTE_REALCE_ARCO,
  FUENTE_REALCE_PUNTO,
  FUENTE_LUZ_CIUDADES,
  FUENTE_ALUMBRADO,
  FUENTE_RUTAS,
  FUENTE_RUTAS_FLECHAS,
  FUENTE_RUTAS_FRANJAS,
  FUENTE_RECORRIDO,
  CAPA_RUTAS,
  CAPA_RUTAS_ZONA,
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
  FUENTE_ATRIBUIDOS,
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
  atribuidos,
  ciudadesSinLuzEnMapa,
  alumbradoEnMapa,
  impactosConSateliteEnMapa,
  corredoresEnMapa,
  focosDeRegiones,
  impactosEnMapa,
  lineasDeEpisodio,
  pilas,
  puntoEnMapa,
  sinAtribuidos,
} from "./geometria.ts";
import { precargarBanderas, registrarFlechaRuta, registrarIconos, trasBanderas } from "./iconos.ts";
import { colocarLetrero, hayRaton } from "./letrero.ts";
import { anchoZonaArco, distanciaALinea, elegir, ZONA_ARCO_DEDO_PX } from "./seleccion.ts";
import type { Candidato } from "./seleccion.ts";
import { letreroDeCorredor } from "../componentes/GuerraSatelite.tsx";
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
/** Lo que queda libre alrededor de un punto asomado: el marcador entero, con aire. */
const MARGEN_ASOMAR_PX = 32;

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

/** Un punto (con zoom), Ucrania entera o una caja [oeste, sur, este, norte] (un país). */
export type Encuadre =
  | { lon: number; lat: number; zoom?: number }
  | "ucrania"
  | { caja: [number, number, number, number] };

/**
 * Una petición de mover el mapa, que solo hace quien abre algo (nunca quien lo cierra):
 * - «ir»: a lo que el usuario no tenía a la vista (una lista, «Europa ahora», «Con satélite», un
 *   enlace, el recorrido de novedades);
 * - «asomar»: a lo que acaba de tocar en el mapa, solo lo justo para que la ficha no lo tape, sin
 *   cambiar el zoom; si ya se ve, nada.
 * `n` distingue dos peticiones al mismo sitio.
 */
export interface Vuelo {
  encuadre: Encuadre;
  modo: "ir" | "asomar";
  n: number;
}

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
  /** Ciudades con alumbrado reducido de forma permanente; null si no se han cargado. */
  alumbrado: readonly CiudadAlumbrado[] | null;
  elegido: IncidenteResumen | null;
  paisResaltado: string | null;
  regionesElegidas: readonly string[];
  novedades: ReadonlySet<string>;
  /** Las últimas 24 horas, para el destello de lo reciente (lo mismo que el filtro). */
  recientes: Periodo;
  vuelo: Vuelo | null;
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
  /** Varios arcos casi a la misma distancia del punto pulsado. */
  onCorredores: (claves: string[]) => void;
  /** Corredor con la ficha abierta: su arco sigue realzado. */
  corredorElegido: string | null;
  /** Puntos con información de satélite del periodo; null sin la capa. */
  puntosSatelite: readonly PuntoSatelite[] | null;
  /** «Con satélite»: solo esos puntos, lo demás de la capa de guerra atenuado. */
  soloSatelite: boolean;
  onCiudadLuz: (clave: string) => void;
  onAlumbrado: (clave: string) => void;
  onListo: (api: ApiMapa) => void;
  onFallo: () => void;
  /** Un toque en el mapa fuera de todo: cierra lo abierto, sin mover el mapa. */
  onVacio: () => void;
  /** Recorridos de la noche que se dibuja (la última terminada o la de «Noche a noche»); null sin
   * rutas. Mientras se ven, los impactos y el relleno de las regiones se atenúan. */
  rutas: RutasEnMapa | null;
  onRuta: (clave: string) => void;
  /** Recorrido de la incursión con la ficha abierta; null si no hay. */
  recorrido: GeoJSON.FeatureCollection | null;
}

/** Radio del aro que señala en el mapa el incidente enfocado con el teclado. */
const RADIO_ARO_PX = 14;

/** Lo que anuncia el lector de pantalla de un incidente del mapa: título, estado y fecha. */
export function textoDeIncidente(t: Textos, idioma: Idioma, i: IncidenteResumen): string {
  return `${i.titulo[idioma]} · ${t.estado[i.estado]} · ${fechaDia(i.dia)}`;
}

/** Capas de las rutas que se pueden tocar: el halo y la zona sensible de la línea. */
const CAPAS_DE_RUTA: readonly string[] = [CAPA_RUTAS, CAPA_RUTAS_ZONA];
/** Parte del relleno de las regiones que queda con las rutas a la vista. */
const FACTOR_REGIONES_CON_RUTAS = 0.35;

/**
 * Opacidad del relleno de una región según sus ataques, en los escalones de la leyenda. Las
 * regiones de Ucrania y las de Rusia se escalan cada una con su máximo: los partes rusos citan
 * muchas más regiones cada noche y apagarían a las ucranianas.
 */
function opacidadPorRegion(
  todas: ReadonlyMap<string, number>,
  rusas: boolean,
  factor = 1,
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
    pares.push(codigo, (ESCALA_UCRANIA[escalon] ?? 0) * factor);
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
const CAPAS_DE_MARCAS = [CAPA_DIRECTO, CAPA_ATRIBUIDOS, CAPA_INCIDENTES_GRAVES, CAPA_INCIDENTES_DISCRETOS, CAPA_GRUPOS];

function punteroGrueso(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)").matches;
}

/** La marca (incidente, grupo o aviso) más cercana a un punto dentro del objetivo táctil. */
function marcaMasCercana(
  mapa: MapaGL,
  x: number,
  y: number,
  entre: readonly string[] = CAPAS_DE_MARCAS,
  objetivo: number = OBJETIVO_TACTIL_PX,
): MapGeoJSONFeature | undefined {
  const medio = objetivo / 2;
  const capas = entre.filter(
    (id) => mapa.getLayer(id) !== undefined && mapa.getLayoutProperty(id, "visibility") !== "none",
  );
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
    const d = Math.hypot(p.x - x, p.y - y);
    if (d < distancia) {
      distancia = d;
      mejor = rasgo;
    }
  }
  return mejor;
}

/** El punto del incidente abierto, con lo que necesita su marca de selección (un atribuido,
 *  su marcador: la bandera y si es de una persona). */
function seleccionDe(elegido: IncidenteResumen | null): GeoJSON.FeatureCollection<GeoJSON.Point> {
  const punto = elegido === null ? null : puntoEnMapa(elegido);
  if (elegido === null || punto === null) return { type: "FeatureCollection", features: [] };
  const marcador = varianteDe(elegido.atribucion);
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [punto.lon, punto.lat] },
        properties: {
          estado: elegido.estado,
          bandera: indiceBandera(marcador.bandera),
          persona: marcador.persona ? 1 : 0,
        },
      },
    ],
  };
}

/** El elemento del mapa con el mapa a mano para las pruebas de navegador. */
type ElementoDelMapa = HTMLDivElement & { mapaDePruebas?: MapaGL };

/** Países de los atribuidos, cuya bandera lleva su marcador. */
function paisesAtribuidos(incidentes: readonly IncidenteResumen[]): string[] {
  return incidentes.flatMap((i) => (i.estado === "atribuido" && i.atribucion?.pais ? [i.atribucion.pais] : []));
}

function capasActivas(mapa: MapaGL): string[] {
  return CAPAS_PULSABLES.filter((id) => mapa.getLayer(id) !== undefined);
}

/** Lo que hay bajo el puntero: un rasgo de una capa o un corredor por su clave. */
type Objetivo = { tipo: "rasgo"; rasgo: MapGeoJSONFeature } | { tipo: "corredor"; clave: string };

/** Un arco tal como se dibuja: su línea (lon, lat) y su grosor. */
interface ArcoDibujado {
  coordenadas: [number, number][];
  ancho: number;
}

const VACIA_REALCE: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export default function Mapa(props: PropsMapa) {
  const { t, idioma, incidentes, episodios, capas, intensidad, noche, elegido } = props;
  const [aLaVista, setALaVista] = useState<readonly IncidenteResumen[]>([]);
  const aroTeclado = useRef<HTMLDivElement>(null);
  const { focosUcrania, impactos, gnss, presion, avisos } = props;
  const { corredores, luzRegiones, ciudadesSinLuz, alumbrado, corredorElegido } = props;
  const { puntosSatelite, soloSatelite, rutas, recorrido } = props;
  const conRutas = (rutas?.mostrados ?? 0) > 0;
  const { paisResaltado, regionesElegidas, novedades, recientes, vuelo, reserva } = props;
  // El vuelo lee la reserva del momento, pero no se repite porque cambie (al arrastrar una hoja).
  const reservaActual = useRef(reserva);
  reservaActual.current = reserva;
  const contenedor = useRef<HTMLDivElement>(null);
  const letrero = useRef<HTMLDivElement>(null);
  const textoLetrero = useRef<HTMLSpanElement>(null);
  const capaPulsos = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<MapaGL | null>(null);
  const volar = useRef<((destino: Encuadre) => void) | null>(null);
  const asomar = useRef<((destino: Encuadre) => void) | null>(null);
  const [listo, setListo] = useState(false);
  const [iconos, setIconos] = useState("");
  // El incidente abierto, para volver a dibujar su marcador cuando llega su bandera.
  const elegidoActual = useRef<IncidenteResumen | null>(null);
  const anotar = useRef<(() => void) | null>(null);
  // Los manejadores del mapa se registran una vez: leen siempre las funciones actuales.
  const manejadores = useRef(props);
  useEffect(() => {
    manejadores.current = props;
  });
  const idiomaInicial = useRef(idioma);
  // Arcos dibujados por clave (para medir la distancia del puntero a cada uno), el señalado con el
  // ratón o el teclado y el de la ficha abierta.
  const arcos = useRef(new Map<string, ArcoDibujado>());
  const arcoSenalado = useRef<string | null>(null);
  const arcoElegido = useRef(corredorElegido);
  arcoElegido.current = corredorElegido;
  const soloConSatelite = useRef(soloSatelite);
  soloConSatelite.current = soloSatelite;
  // Valores de pintura de antes de atenuar con «Con satélite», para devolverlos.
  const pinturaOriginal = useRef(new Map<string, DataDrivenPropertyValueSpecification<number> | undefined>());

  /** Realza el arco señalado (o, si no hay, el de la ficha abierta) y atenúa los demás. */
  function pintarRealceArco() {
    const mapa = mapaRef.current;
    if (mapa === null || mapa.getLayer(CAPA_REALCE_ARCO) === undefined) return;
    const clave = arcoSenalado.current ?? arcoElegido.current;
    const arco = clave === null ? undefined : arcos.current.get(clave);
    fuente(mapa, FUENTE_REALCE_ARCO)?.setData(
      arco === undefined
        ? VACIA_REALCE
        : {
            type: "FeatureCollection",
            features: [
              {
                type: "Feature",
                geometry: { type: "LineString", coordinates: arco.coordenadas },
                properties: { ancho: arco.ancho },
              },
            ],
          },
    );
    mapa.setPaintProperty(
      CAPA_CORREDORES,
      "line-opacity",
      soloConSatelite.current
        ? OPACIDAD_CORREDOR_SIN_SATELITE
        : arco === undefined
          ? OPACIDAD_CORREDOR
          : OPACIDAD_CORREDOR_ATENUADO,
    );
  }

  /** El letrero junto a un punto de la pantalla (o escondido, con null). */
  function ponerLetrero(texto: string | null, punto: { x: number; y: number }) {
    const caja = letrero.current;
    const mapa = mapaRef.current;
    if (caja === null || mapa === null) return;
    if (texto === null) {
      caja.hidden = true;
      return;
    }
    if (textoLetrero.current !== null) textoLetrero.current.textContent = texto;
    caja.hidden = false;
    // Nunca se sale del mapa: se mide ya con su texto y se recoloca.
    const { x, y } = colocarLetrero(
      punto,
      { ancho: caja.offsetWidth, alto: caja.offsetHeight },
      { ancho: mapa.getContainer().clientWidth, alto: mapa.getContainer().clientHeight },
    );
    caja.style.transform = `translate(${x}px, ${y}px)`;
  }

  /** Dónde se dibuja un incidente: su punto o el de su lugar aproximado. */
  function posicionDe(i: IncidenteResumen): [number, number] | null {
    if (i.punto !== null) return [i.punto.lon, i.punto.lat];
    if (i.aproximado !== null) return [i.aproximado.lon, i.aproximado.lat];
    return null;
  }

  /**
   * Con el teclado: el incidente del botón enfocado, con un aro y su letrero junto a su marcador
   * (lo que se ve al pasar el ratón). Sin ratón ni dedo: el mapa no se mueve.
   */
  function enfocarIncidente(i: IncidenteResumen | null) {
    const mapa = mapaRef.current;
    const aro = aroTeclado.current;
    const posicion = i === null ? null : posicionDe(i);
    if (mapa === null || aro === null || i === null || posicion === null) {
      if (aro !== null) aro.hidden = true;
      ponerLetrero(null, { x: 0, y: 0 });
      return;
    }
    const punto = mapa.project(posicion);
    aro.hidden = false;
    aro.style.transform = `translate(${punto.x - RADIO_ARO_PX}px, ${punto.y - RADIO_ARO_PX}px)`;
    ponerLetrero(textoDeIncidente(t, idioma, i), punto);
  }

  /** Con el teclado: el arco del botón enfocado, realzado y con su letrero en su punto medio. */
  function enfocarArco(clave: string | null) {
    const mapa = mapaRef.current;
    arcoSenalado.current = clave;
    pintarRealceArco();
    const arco = clave === null ? undefined : arcos.current.get(clave);
    const corredor = clave === null ? undefined : corredores?.find((c) => c.clave === clave);
    if (mapa === null || arco === undefined || corredor === undefined) {
      ponerLetrero(null, { x: 0, y: 0 });
      return;
    }
    const medio = arco.coordenadas[Math.floor(arco.coordenadas.length / 2)];
    if (medio !== undefined) ponerLetrero(letreroDeCorredor(t, idioma, corredor), mapa.project(medio));
  }

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
    // Con el navegador manejado por las pruebas (navigator.webdriver), el mapa queda a mano en
    // su elemento: las de e2e/ miden en él dónde se dibuja cada marca.
    if (navigator.webdriver) (elemento as ElementoDelMapa).mapaDePruebas = mapa;
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
      if ("caja" in destino) {
        const [oeste, sur, este, norte] = destino.caja;
        mapa.fitBounds(
          [
            [oeste, sur],
            [este, norte],
          ],
          { padding: margenes(reservaActual.current, MARGEN_ENCUADRE_PX), animate, duration: DURACION_VUELO_MS },
        );
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

    /** Lo justo para que el punto quede fuera de lo que tapan la cabecera y la ficha: sin zoom. */
    function asomarA(destino: Encuadre) {
      if (destino === "ucrania" || "caja" in destino) return;
      const visible = margenes(reservaActual.current, MARGEN_ASOMAR_PX);
      const { clientWidth: ancho, clientHeight: alto } = mapa.getContainer();
      const punto = mapa.project([destino.lon, destino.lat]);
      const desplazamiento = (valor: number, desde: number, hasta: number) =>
        desde > hasta ? 0 : valor < desde ? valor - desde : valor > hasta ? valor - hasta : 0;
      const dx = desplazamiento(punto.x, visible.left, ancho - visible.right);
      const dy = desplazamiento(punto.y, visible.top, alto - visible.bottom);
      if (dx === 0 && dy === 0) return;
      mapa.panBy([dx, dy], { animate: !movimientoReducido(), duration: DURACION_VUELO_MS });
    }
    asomar.current = asomarA;

    // El centro, el zoom y dónde queda en pantalla el incidente abierto, a la vista en el
    // documento al acabar cada movimiento: así se comprueba desde fuera que el mapa no se mueve.
    const anotarVista = () => {
      const centro = mapa.getCenter();
      elemento.dataset.centro = `${centro.lng.toFixed(6)},${centro.lat.toFixed(6)}`;
      elemento.dataset.zoom = mapa.getZoom().toFixed(4);
      const actual = elegidoActual.current;
      const punto = actual === null ? null : puntoEnMapa(actual);
      if (punto === null) return;
      const enPantalla = mapa.project([punto.lon, punto.lat]);
      elemento.dataset.elegido = `${Math.round(enPantalla.x)},${Math.round(enPantalla.y)}`;
    };
    anotar.current = anotarVista;
    mapa.on("moveend", anotarVista);

    mapa.on("load", () => {
      anotarVista();
      const delMapaBase = new Set(mapa.listImages());
      registrarIconos(mapa);
      registrarFlechaRuta(mapa);
      // Con el dedo, la zona sensible de los arcos es más ancha.
      if (punteroGrueso()) {
        mapa.setPaintProperty(CAPA_CORREDORES_ZONA, "line-width", [
          "+",
          ["get", "ancho"],
          ZONA_ARCO_DEDO_PX,
        ]);
      }
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

    /** Todo lo que puede recibir la pulsación en ese punto, por clases (seleccion.ts). */
    function candidatos(punto: { x: number; y: number }): Candidato<Objetivo>[] {
      const lista: Candidato<Objetivo>[] = mapa
        .queryRenderedFeatures([punto.x, punto.y], { layers: capasActivas(mapa) })
        .map((rasgo) => ({
          clase: CAPAS_DE_AREAS.includes(rasgo.layer.id) ? "area" : "marca",
          distancia: 0,
          valor: { tipo: "rasgo", rasgo },
        }));
      const dedo = punteroGrueso();
      // Dentro de una franja de ruta, el dedo no busca la marca más cercana: la franja es lo
      // que se ha tocado (una marca justo debajo del dedo sigue ganando).
      const enRuta = lista.some((c) => c.valor.tipo === "rasgo" && CAPAS_DE_RUTA.includes(c.valor.rasgo.layer.id));
      if (dedo && !enRuta && !lista.some((c) => c.clase === "marca")) {
        // Con el dedo, el objetivo de cada marca es de 44 px: la más cercana dentro de ese cuadro.
        // Las de la capa de guerra, muy juntas a la escala de Ucrania, el de los arcos (28 px).
        const cercana =
          marcaMasCercana(mapa, punto.x, punto.y) ??
          marcaMasCercana(mapa, punto.x, punto.y, CAPAS_DE_PUNTOS_AL_TOQUE, ZONA_ARCO_DEDO_PX);
        if (cercana !== undefined) {
          lista.push({ clase: "marca", distancia: 1, valor: { tipo: "rasgo", rasgo: cercana } });
        }
      }
      if (
        mapa.getLayer(CAPA_CORREDORES_ZONA) !== undefined &&
        mapa.getLayoutProperty(CAPA_CORREDORES_ZONA, "visibility") !== "none"
      ) {
        const medio = anchoZonaArco(dedo) / 2;
        const cerca = mapa.queryRenderedFeatures(
          [
            [punto.x - medio, punto.y - medio],
            [punto.x + medio, punto.y + medio],
          ],
          { layers: [CAPA_CORREDORES_ZONA] },
        );
        const vistas = new Set<string>();
        for (const rasgo of cerca) {
          const clave = String(rasgo.properties.clave);
          const arco = arcos.current.get(clave);
          if (vistas.has(clave) || arco === undefined) continue;
          vistas.add(clave);
          const enPantalla = arco.coordenadas.map((c) => {
            const p = mapa.project(c);
            return [p.x, p.y] as const;
          });
          // Desde el borde del arco: los gruesos tienen la zona igual de ancha a cada lado.
          const distancia = Math.max(0, distanciaALinea([punto.x, punto.y], enPantalla) - arco.ancho / 2);
          if (distancia <= medio) {
            lista.push({ clase: "arco", distancia, valor: { tipo: "corredor", clave } });
          }
        }
      }
      return lista;
    }

    let senalado: string | null = null;
    /** Realce del arco o del punto de la capa de guerra bajo el ratón. */
    function realzar(objetivo: Objetivo | null) {
      const esPunto =
        objetivo?.tipo === "rasgo" &&
        CAPAS_DE_PUNTOS_DE_GUERRA.includes(objetivo.rasgo.layer.id) &&
        objetivo.rasgo.geometry.type === "Point";
      const clave =
        objetivo === null
          ? null
          : objetivo.tipo === "corredor"
            ? `c|${objetivo.clave}`
            : esPunto
              ? `p|${objetivo.rasgo.layer.id}|${JSON.stringify(objetivo.rasgo.geometry)}`
              : null;
      if (clave === senalado) return;
      senalado = clave;
      arcoSenalado.current = objetivo?.tipo === "corredor" ? objetivo.clave : null;
      pintarRealceArco();
      fuente(mapa, FUENTE_REALCE_PUNTO)?.setData(
        esPunto && objetivo.tipo === "rasgo"
          ? {
              type: "FeatureCollection",
              features: [{ type: "Feature", geometry: objetivo.rasgo.geometry, properties: {} }],
            }
          : VACIA_REALCE,
      );
    }

    function textoDeCorredor(clave: string): string | null {
      const { t: textos, idioma: lengua } = manejadores.current;
      const corredor = manejadores.current.corredores?.find((c) => c.clave === clave);
      return corredor === undefined ? null : letreroDeCorredor(textos, lengua, corredor);
    }

    function textoDeLetrero(rasgo: MapGeoJSONFeature): string | null {
      const { t: textos, idioma: lengua, porId } = manejadores.current;
      const p = rasgo.properties;
      if (rasgo.layer.id === CAPA_GRUPOS) {
        return "point_count" in p ? textos.mapa.grupo(Number(p.total)) : textos.mapa.pila(Number(p.n));
      }
      if (rasgo.layer.id === CAPA_ATRIBUIDOS && ("point_count" in p || Number(p.n) > 1)) {
        return "point_count" in p ? textos.mapa.atribuidos(Number(p.total)) : textos.mapa.pila(Number(p.n));
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
      if (rasgo.layer.id === CAPA_SATELITE) {
        return textos.satelite.letreroSatelite(Number(p.imagen) === 1, Number(p.foco) === 1);
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
      if (CAPAS_DE_RUTA.includes(rasgo.layer.id)) {
        return textos.rutas.etiqueta;
      }
      if (rasgo.layer.id === CAPA_LUZ_CIUDADES) {
        return textos.satelite.letreroCiudad(String(p.nombre), String(p.perdida));
      }
      if (rasgo.layer.id === CAPA_ALUMBRADO) {
        return textos.satelite.letreroAlumbrado(String(p.nombre));
      }
      const incidente = porId.get(String(p.id));
      if (incidente === undefined) return null;
      const estado =
        incidente.estado === "atribuido"
          ? textoAtribuido(textos, lengua, incidente.atribucion)
          : textos.estado[incidente.estado];
      return `${textos.tipo[incidente.tipo]} · ${estado} · ${incidente.titulo[lengua]}`;
    }

    function esconderLetrero() {
      if (letrero.current !== null) letrero.current.hidden = true;
    }

    mapa.on("click", (evento: MapMouseEvent) => {
      // Al abrir una ficha (o tocar el mapa), el letrero desaparece.
      esconderLetrero();
      const eleccion = elegir(candidatos(evento.point));
      if (eleccion === null) {
        manejadores.current.onVacio();
        return;
      }
      if (eleccion.tipo === "varios") {
        // Varios arcos casi a la misma distancia: se elige de una lista.
        manejadores.current.onCorredores(
          eleccion.valores.flatMap((v) => (v.tipo === "corredor" ? [v.clave] : [])),
        );
        return;
      }
      if (eleccion.valor.tipo === "corredor") {
        manejadores.current.onCorredor(eleccion.valor.clave);
        return;
      }
      const primero = eleccion.valor.rasgo;
      const propiedades = primero.properties;
      if (primero.layer.id === CAPA_ATRIBUIDOS && "point_count" in propiedades) {
        // Banderas juntas al alejar: se acerca hasta el zoom en que se separan.
        const fuenteBanderas = fuente(mapa, FUENTE_ATRIBUIDOS);
        void fuenteBanderas
          ?.getClusterExpansionZoom(Number(propiedades.cluster_id))
          .then((zoom) =>
            mapa.easeTo({ center: evento.lngLat, zoom, animate: !movimientoReducido() }),
          );
      } else if ((primero.layer.id === CAPA_GRUPOS || primero.layer.id === CAPA_ATRIBUIDOS) && Number(propiedades.n) > 1) {
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
      } else if (primero.layer.id === CAPA_IMPACTOS || primero.layer.id === CAPA_SATELITE) {
        manejadores.current.onImpacto(String(propiedades.id));
      } else if (primero.layer.id === CAPA_DIRECTO) {
        manejadores.current.onAviso(String(propiedades.id));
      } else if (CAPAS_DE_RUTA.includes(primero.layer.id)) {
        manejadores.current.onRuta(String(propiedades.clave));
      } else if (primero.layer.id === CAPA_GNSS) {
        manejadores.current.onCelda(String(propiedades.h3));
      } else if (primero.layer.id === CAPA_PRESION) {
        manejadores.current.onPais(String(propiedades.iso));
      } else if (primero.layer.id === CAPA_LUZ_CIUDADES) {
        manejadores.current.onCiudadLuz(String(propiedades.clave));
      } else if (primero.layer.id === CAPA_ALUMBRADO) {
        manejadores.current.onAlumbrado(String(propiedades.clave));
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
      if (!hayRaton()) {
        ponerLetrero(null, evento.point);
        return;
      }
      const eleccion = elegir(candidatos(evento.point));
      const objetivo =
        eleccion === null ? null : eleccion.tipo === "uno" ? eleccion.valor : (eleccion.valores[0] ?? null);
      realzar(objetivo);
      mapa.getCanvas().style.cursor = objetivo === null ? "" : "pointer";
      const texto =
        objetivo === null
          ? null
          : objetivo.tipo === "corredor"
            ? textoDeCorredor(objetivo.clave)
            : textoDeLetrero(objetivo.rasgo);
      ponerLetrero(texto, evento.point);
    });
    mapa.on("mouseout", () => {
      esconderLetrero();
      realzar(null);
    });
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
    let cancelarBanderas = () => {};
    const cancelar = trasPintar(() => {
      const opciones = { recientes, novedades };
      fuente(mapa, FUENTE_PUNTOS)?.setData(pilas(sinAtribuidos(incidentes), opciones));
      // Los atribuidos, solo con sus banderas ya en el mapa: nunca lisos primero y con la
      // bandera después.
      const marcadores = atribuidos(incidentes, opciones);
      cancelarBanderas = trasBanderas(mapa, paisesAtribuidos(incidentes), () => {
        fuente(mapa, FUENTE_ATRIBUIDOS)?.setData(marcadores);
      });
      fuente(mapa, FUENTE_PUNTOS_SUELTOS)?.setData(pilas(incidentes, opciones));
      fuente(mapa, FUENTE_AREAS)?.setData(areas(incidentes));
      fuente(mapa, FUENTE_EPISODIOS)?.setData(lineasDeEpisodio(episodios, incidentes));
    });
    return () => {
      cancelar();
      cancelarBanderas();
    };
  }, [listo, incidentes, episodios, recientes, novedades]);

  // Las banderas de los atribuidos se piden en cuanto llegan los datos, mientras el mapa
  // carga: así suelen estar ya cuando se dibujan los atribuidos.
  useEffect(() => {
    precargarBanderas(paisesAtribuidos(incidentes));
  }, [incidentes]);

  // Con una ficha abierta, el letrero de ayuda no se queda encima.
  useEffect(() => {
    if (elegido !== null && letrero.current !== null) letrero.current.hidden = true;
  }, [elegido]);

  // Anillo del incidente elegido.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    elegidoActual.current = elegido;
    anotar.current?.();
    // Un atribuido abierto, también con su bandera ya en el mapa.
    return trasBanderas(mapa, elegido === null ? [] : paisesAtribuidos([elegido]), () => {
      fuente(mapa, FUENTE_SELECCION)?.setData(seleccionDe(elegido));
      // Un atribuido abierto se dibuja solo con su marcador de selección, más grande: el normal
      // asomaría por debajo.
      mapa.setFilter(CAPA_ATRIBUIDOS, ["!=", ["get", "id"], elegido?.estado === "atribuido" ? elegido.id : ""]);
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
        // Apagones y ciudades a oscuras, dentro de «Con satélite».
        [CAPAS_DE_LUZ, capas.ucrania && capas.satelite],
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
    // Con las rutas a la vista, el relleno se queda en un fondo suave que no compite con ellas.
    const factor = conRutas ? FACTOR_REGIONES_CON_RUTAS : 1;
    mapa.setPaintProperty(
      CAPA_REGIONES,
      "fill-opacity",
      actual === null ? 0 : opacidadPorRegion(actual, false, factor),
    );
    // Durante la reproducción noche a noche (solo ataques contra Ucrania), Rusia se apaga.
    mapa.setPaintProperty(
      CAPA_REGIONES_RUSIA,
      "fill-opacity",
      noche !== null || intensidad === null ? 0 : opacidadPorRegion(intensidad, true, factor),
    );
  }, [listo, intensidad, noche, conRutas]);

  // Impactos con lugar de la capa de guerra.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      const conSatelite = new Set(
        (puntosSatelite ?? []).filter((p) => p.clase === "impacto").map((p) => p.clave),
      );
      fuente(mapa, FUENTE_IMPACTOS)?.setData(impactosEnMapa(impactos ?? [], conSatelite));
      fuente(mapa, FUENTE_SATELITE)?.setData(impactosConSateliteEnMapa(puntosSatelite ?? []));
    });
  }, [listo, impactos, puntosSatelite]);

  // «Con satélite», o las rutas a la vista: lo demás de la capa de guerra, atenuado.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    const atenuar = soloSatelite || conRutas;
    for (const [capa, propiedad, atenuado] of ATENUADAS_SIN_SATELITE) {
      if (mapa.getLayer(capa) === undefined) continue;
      const clave = `${capa}|${propiedad}`;
      if (!pinturaOriginal.current.has(clave)) {
        pinturaOriginal.current.set(clave, mapa.getPaintProperty(capa, propiedad));
      }
      mapa.setPaintProperty(
        capa,
        propiedad,
        atenuar ? atenuado : pinturaOriginal.current.get(clave),
      );
    }
    pintarRealceArco();
  }, [listo, soloSatelite, conRutas]);

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
      const coleccion = corredoresEnMapa(corredores ?? []);
      arcos.current = new Map(
        coleccion.features.map((f) => [
          f.properties.clave,
          { coordenadas: f.geometry.coordinates as [number, number][], ancho: f.properties.ancho },
        ]),
      );
      fuente(mapa, FUENTE_CORREDORES)?.setData(coleccion);
      pintarRealceArco();
    });
  }, [listo, corredores]);

  // Rutas de los drones: los recorridos de la noche que se dibuja.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return undefined;
    return trasPintar(() => {
      fuente(mapa, FUENTE_RUTAS)?.setData(rutas?.lineas ?? VACIA_REALCE);
      fuente(mapa, FUENTE_RUTAS_FRANJAS)?.setData(rutas?.franjas ?? VACIA_REALCE);
      fuente(mapa, FUENTE_RUTAS_FLECHAS)?.setData(rutas?.flechas ?? VACIA_REALCE);
    });
  }, [listo, rutas]);

  // Recorrido de la incursión abierta: se dibuja al abrir su ficha y se quita al cerrarla, sin
  // mover el mapa.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    fuente(mapa, FUENTE_RECORRIDO)?.setData(recorrido ?? VACIA_REALCE);
  }, [listo, recorrido]);

  // El arco del corredor con la ficha abierta sigue realzado.
  useEffect(() => {
    if (!listo) return;
    pintarRealceArco();
  }, [listo, corredorElegido]);

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

  // Ciudades con alumbrado reducido de forma permanente.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null) return;
    fuente(mapa, FUENTE_ALUMBRADO)?.setData(alumbradoEnMapa(alumbrado ?? []));
  }, [listo, alumbrado]);

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
      const capas = [CAPA_GRUPOS, CAPA_INCIDENTES_GRAVES, CAPA_INCIDENTES_DISCRETOS, CAPA_ATRIBUIDOS].filter(
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

  // Los incidentes a la vista, para recorrerlos con el teclado: se rehacen cuando el mapa termina
  // de moverse o cambian los filtros.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null || !capas.incidentes) {
      setALaVista([]);
      return undefined;
    }
    const actualizar = () => {
      const limites = mapa.getBounds();
      setALaVista(
        incidentes
          .filter((i) => {
            const posicion = posicionDe(i);
            return posicion !== null && limites.contains(posicion);
          })
          .sort((a, b) => b.dia - a.dia || (b.inicio ?? 0) - (a.inicio ?? 0) || b.id.localeCompare(a.id)),
      );
    };
    actualizar();
    mapa.on("moveend", actualizar);
    return () => {
      mapa.off("moveend", actualizar);
    };
  }, [listo, incidentes, capas.incidentes]);

  // Al abrir algo, según de dónde: ir a ello, o asomarlo si ya estaba a la vista. Cerrar no pide
  // nada: el mapa se queda donde está.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!listo || mapa === null || vuelo === null) return;
    (vuelo.modo === "ir" ? volar : asomar).current?.(vuelo.encuadre);
  }, [listo, vuelo]);

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
      <div
        ref={aroTeclado}
        hidden
        aria-hidden="true"
        data-aro-teclado=""
        className="pointer-events-none absolute left-0 top-0 z-20 rounded-full border-2 border-acento"
        style={{ width: RADIO_ARO_PX * 2, height: RADIO_ARO_PX * 2 }}
      />
      {/* Los incidentes a la vista, uno a uno con el tabulador (del más reciente al más antiguo): el
          lector de pantalla anuncia título, estado y fecha, el enfocado se señala en el mapa con un
          aro y su letrero, e Intro abre su ficha. Con el ratón o el dedo no se ve nada de esto. */}
      {listo && aLaVista.length > 0 && (
        <ul className="sr-only" aria-label={t.mapa.aLaVista(aLaVista.length)} data-incidentes-teclado="">
          {aLaVista.map((i) => (
            <li key={i.id}>
              <button
                type="button"
                onFocus={() => enfocarIncidente(i)}
                onBlur={() => enfocarIncidente(null)}
                onClick={() => props.onIncidente(i.id)}
              >
                {textoDeIncidente(t, idioma, i)}
              </button>
            </li>
          ))}
        </ul>
      )}
      {/* Los corredores, uno a uno con el tabulador: el enfocado se realza en el mapa con su
          letrero, e Intro abre su ficha. */}
      {listo && capas.ucrania && capas.corredores && corredores !== null && corredores.length > 0 && (
        <ul className="sr-only" aria-label={t.satelite.corredor.lista} data-corredores-teclado="">
          {corredores.map((c) => (
            <li key={c.clave}>
              <button
                type="button"
                onFocus={() => enfocarArco(c.clave)}
                onBlur={() => enfocarArco(null)}
                onClick={() => props.onCorredor(c.clave)}
              >
                {letreroDeCorredor(t, idioma, c)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
