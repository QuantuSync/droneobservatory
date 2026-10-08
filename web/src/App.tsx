import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { LineaNovedades, RecorridoNovedades } from "./componentes/Novedades.tsx";
import { Ayuda } from "./componentes/Ayuda.tsx";
import { BarraEstado } from "./componentes/BarraEstado.tsx";
import { BotonAhora, BotonFiltros, BotonPrevision, Desplegable } from "./componentes/BotonesMapa.tsx";
import { Prevision } from "./componentes/Prevision.tsx";
import { BarraMovil, Cabecera } from "./componentes/Cabecera.tsx";
import {
  Atribuciones,
  CAPAS_INICIALES,
  SelectorDeCapas,
  SelectorDeIdioma,
  Zoom,
} from "./componentes/Controles.tsx";
import type { Capas } from "./componentes/Controles.tsx";
import { EuropaAhora } from "./componentes/EuropaAhora.tsx";
import type { CifraAhora } from "./componentes/EuropaAhora.tsx";
import { Feed } from "./componentes/Feed.tsx";
import type { Pestana } from "./componentes/Feed.tsx";
import { FichaAtaque } from "./componentes/FichaAtaque.tsx";
import { FichaAviso } from "./componentes/FichaAviso.tsx";
import { FichaCelda } from "./componentes/FichaCelda.tsx";
import { FichaImpacto } from "./componentes/FichaImpacto.tsx";
import { FichaIncidente } from "./componentes/FichaIncidente.tsx";
import { FichaPais } from "./componentes/FichaPais.tsx";
import { FichaRegion } from "./componentes/FichaRegion.tsx";
import {
  BotonSatelite,
  PanelSatelite,
  FichaAlumbrado,
  FichaCorredor,
  FichaLuz,
  ListaCorredores,
  cargarIndiceSatelite,
} from "./componentes/GuerraSatelite.tsx";
import { Filtros, textoDeSeleccion } from "./componentes/Filtros.tsx";
import { LeyendaCorredores, LeyendaGnss, LeyendaPresion } from "./componentes/Leyendas.tsx";
import type { EstadoGnss } from "./componentes/Leyendas.tsx";
import { Lista } from "./componentes/Lista.tsx";
import { Marcador } from "./componentes/Marcador.tsx";
import { MenuMovil, SeccionMenu } from "./componentes/MenuMovil.tsx";
import { Metodologia } from "./componentes/Metodologia.tsx";
import { CabeceraFicha, SegunCarga } from "./componentes/Panel.tsx";
import { ALTURAS, HojaInferior, PanelLateral } from "./componentes/Paneles.tsx";
import type { Altura } from "./componentes/Paneles.tsx";
import { SelectorPila } from "./componentes/SelectorPila.tsx";
import { Simbolo } from "./componentes/Simbolo.tsx";
import {
  CARGANDO,
  cargarAtaque,
  cargarEstadoSistema,
  cargarImpacto,
  cargarIncidente,
  cargarResumen,
  cargarResumenUcrania,
  cargarPrevision,
} from "./datos/carga.ts";
import { diaDeTexto, rachaDe } from "./datos/prevision.ts";
import type { Prevision as DatosPrevision, Racha } from "./datos/prevision.ts";
import type { Carga } from "./datos/carga.ts";
import { cifrasAhora } from "./datos/ahora.ts";
import { cargarDirecto, cierresEnCurso, ordenarAvisos } from "./datos/directo.ts";
import type { Directo } from "./datos/directo.ts";
import { agregar, cargarFicheroGnss, cargarIndiceGnss, ficherosDelPeriodo, zonasAltas } from "./datos/gnss.ts";
import type { Agregado, FicheroGnss, IndiceGnss } from "./datos/gnss.ts";
import { cifrasDePais, presionPorPais } from "./datos/presion.ts";
import { cifras } from "./datos/derivar.ts";
import { DRON_DE_LA_GUERRA, GRUPOS_DRON, ORIGENES_TIPO_DRON } from "./datos/vocabulario.ts";
import {
  cargarIndiceRutas,
  cargarNocheRutas,
  nocheDeDia,
  recorridoEnMapa,
  rutasEnMapa,
  nocheQueSeDibuja,
  recorridoDeClave,
} from "./datos/rutas.ts";
import type { IndiceRutas, NocheRutas } from "./datos/rutas.ts";
import { FichaRuta, LeyendaRutas } from "./componentes/Rutas.tsx";
import {
  OBJETO_ALUMBRADO,
  OBJETO_FOCOS_VIVOS,
  ciudadesSinLuz as ciudadesSinLuzDe,
  corredoresDelPeriodo,
  principales,
  lucesDelPeriodo,
  perdidaPorRegion,
  puntosConSatelite,
} from "./datos/guerraSatelite.ts";
import type {
  AlumbradoReducido,
  FocosVivos,
  IndiceSatelite,
  PuntoSatelite,
  TipoSatelite,
} from "./datos/guerraSatelite.ts";
import { conSubcapas, leerSubcapas } from "./estado/subcapas.ts";
import { validarAlumbrado, validarFocosVivos } from "./datos/validar.ts";
import { urlDelAlmacen } from "./almacenPublico.ts";
import type {
  Ataque,
  EstadoSistema,
  ImpactoGuerra,
  IncidenteDetalle,
  IncidenteResumen,
  Resumen,
  ResumenUcrania,
} from "./datos/tipos.ts";
import {
  ataquesPorRegion,
  centrosDeFocos,
  cifrasDeRegion,
  focosDelPeriodo,
  dominioUcrania,
  impactosDelPeriodo,
  nochesDeGuerra,
} from "./datos/ucrania.ts";
import { accionDe } from "./estado/atajos.ts";
import type { Accion } from "./estado/atajos.ts";
import {
  GRAVES,
  SIN_FILTROS,
  TODO,
  cuantosFiltros,
  escribirSeleccion,
  filtrar,
  leerFiltros,
  leerSeleccion,
  periodoDeSeleccion,
  soloGraves,
  ultimas24Horas,
} from "./estado/filtros.ts";
import type { Filtros as EstadoFiltros, SeleccionPeriodo } from "./estado/filtros.ts";
import {
  almacenLocal,
  incidentesDe,
  novedadesDesde,
  novedadesQueLaten,
  registrarVisita,
} from "./estado/novedades.ts";
import metaInicial from "./generado/meta.json";
import { fechaDia, jornadaEscrita, numero, textos } from "./i18n/index.ts";
import type { ApiMapa, Encuadre, Reserva, Vuelo } from "./mapa/Mapa.tsx";
import { ZOOM_DE_PAIS } from "./mapa/encuadre.ts";
import { useNavegacion } from "./navegacion.tsx";
import { analizarRuta } from "./rutas.ts";
import { RUTAS_EN_LA_WEB } from "./rutasEnLaWeb.ts";
import { ORIGEN, rutaDeFicha, rutaDeIdioma } from "./sitio.ts";
import type { Idioma } from "./sitio.ts";
import { diaDeInstante, enPeriodo, incidenteEnPeriodo } from "./tiempo/dias.ts";
import type { Periodo } from "./tiempo/dias.ts";

const Mapa = lazy(() => import("./mapa/Mapa.tsx"));

/** Cada cuánto se vuelve a calcular la antigüedad de los datos. */
const MS_ENTRE_COMPROBACIONES = 60_000;
/** Cada cuánto se vuelve a pedir estado.json, que la recogida publica cada hora. */
const MS_ENTRE_ESTADOS = 300_000;
/** Cada cuánto se vuelve a pedir directo.json mientras la pestaña está a la vista. */
const MS_ENTRE_DIRECTOS = 60_000;
/** Zoom al que vuela el mapa al abrir un aviso de aeropuerto. */
const ZOOM_DE_AVISO = 9;
/** Zoom al abrir un incidente con lugar aproximado: el país entero, la región o el mar. */
const ZOOM_APROXIMADO = { pais: ZOOM_DE_PAIS, region: 6.5, mar: 6 } as const;
/** Ritmo de la reproducción de la guerra: una noche en cada paso. */
const MS_POR_NOCHE = 420;
/** Espera máxima antes de cargar el mapa si el navegador no queda libre antes. */
const MS_ESPERA_MAXIMA_DEL_MAPA = 1500;
/**
 * Disposición de teléfono: menos de 768 px de ancho, o un teléfono en horizontal. Es la misma
 * condición que la variante «tel» de estilos.css.
 */
export const CONSULTA_MOVIL = "(max-width: 767.98px), (max-height: 500px) and (pointer: coarse)";
/** Anchos de los paneles laterales de escritorio: la ficha a la derecha y el directo a la izquierda. */
const ANCHO_FICHA_PX = 416;
const ANCHO_FEED_PX = 352;

type PanelLocal =
  | { clase: "region"; codigo: string }
  | { clase: "aviso"; id: string }
  | { clase: "celda"; h3: string }
  | { clase: "pais"; iso: string }
  | { clase: "pila"; ids: string[] }
  | { clase: "impacto"; id: string }
  | { clase: "corredor"; clave: string }
  | { clase: "corredores"; claves: string[] }
  | { clase: "luz"; clave: string }
  | { clase: "alumbrado"; clave: string }
  | { clase: "ruta"; clave: string }
  | null;

/** La búsqueda `nueva` con las subcapas que dice `actual` (los filtros no las pisan). */
function conSubcapasDe(nueva: string, actual: string): string {
  const subcapas = leerSubcapas(actual);
  return subcapas === null ? nueva : conSubcapas(nueva, subcapas);
}

/** Zoom al ir a un punto desde la lista de «Con satélite». */
const ZOOM_PUNTO_SATELITE = 9;

/** Cada cuánto se vuelven a pedir los focos de calor de 24 horas (el fichero cambia cada hora). */
const MS_FOCOS_VIVOS = 10 * 60 * 1000;

/** Regiones que se pueden abrir: las de Ucrania (con lo ocupado) y las de Rusia. */
const REGION_DE_LA_CAPA = /^(UA|RU)-[A-Z0-9]{1,3}$/;
/** Hojas del teléfono que no son una ficha: una sola a la vez. */
type HojaPropia = "filtros" | "ahora" | "prevision" | "directo" | null;
/** Desplegables de los botones sobre el mapa, en el escritorio: uno a la vez. */
type Desplegado = "filtros" | "ahora" | "prevision" | null;

/** Con el teléfono en horizontal apenas hay alto: una hoja a media altura no enseña nada. */
const ALTO_DE_TELEFONO_APAISADO = 500;
function alturaInicial(): Altura {
  return typeof window !== "undefined" && window.innerHeight <= ALTO_DE_TELEFONO_APAISADO ? "completa" : "media";
}

/** Alto de un elemento, que se sigue al cambiar (0 mientras no está). */
function useAlto(): [(elemento: HTMLElement | null) => void, number] {
  const [alto, setAlto] = useState(0);
  const observador = useRef<ResizeObserver | null>(null);
  const referencia = useCallback((elemento: HTMLElement | null) => {
    observador.current?.disconnect();
    if (elemento === null) {
      setAlto(0);
      return;
    }
    setAlto(elemento.offsetHeight);
    if (typeof ResizeObserver === "undefined") return;
    observador.current = new ResizeObserver(() => setAlto(elemento.offsetHeight));
    observador.current.observe(elemento);
  }, []);
  return [referencia, alto];
}

const VACIO: readonly never[] = [];
const SIN_NOVEDADES: ReadonlySet<string> = new Set();

function datos<T>(carga: Carga<T>): T | null {
  return carga.estado === "listo" ? carga.datos : null;
}

function dominioDe(resumen: Resumen, ucrania: ResumenUcrania | null): Periodo {
  const hasta = diaDeInstante(resumen.actualizado);
  let desde = resumen.incidentes.reduce((minimo, i) => Math.min(minimo, i.dia), hasta);
  const guerra = ucrania === null ? null : dominioUcrania(ucrania);
  if (guerra !== null) desde = Math.min(desde, guerra.desde);
  return { desde, hasta };
}

function acotarPeriodo(periodo: Periodo | null, dominio: Periodo): Periodo {
  if (periodo === null) return dominio;
  const desde = Math.min(Math.max(periodo.desde, dominio.desde), dominio.hasta);
  const hasta = Math.max(Math.min(periodo.hasta, dominio.hasta), desde);
  return { ...periodo, desde, hasta };
}

type Centro = { lon: number; lat: number };

/** Interferencia GPS del periodo elegido, sumada por celda; null mientras no se pide. */
type GnssDelPeriodo = { clave: string; estado: "cargando" } | { clave: string; estado: "listo"; agregado: Agregado | null };

/** Centro de cada país (Natural Earth), para anclar las fichas de ubicación imprecisa. */
function useCentrosDePais(activo: boolean): ReadonlyMap<string, Centro> | null {
  const [centros, setCentros] = useState<Map<string, Centro> | null>(null);
  useEffect(() => {
    if (!activo || centros !== null) return undefined;
    const control = new AbortController();
    fetch("/mapa/paises.geojson", { signal: control.signal })
      .then(
        (respuesta) =>
          respuesta.json() as Promise<{ features: { properties: Record<string, unknown> }[] }>,
      )
      .then((geojson) => {
        const mapa = new Map<string, Centro>();
        for (const { properties: p } of geojson.features) {
          if (typeof p.iso === "string" && typeof p.lx === "number" && typeof p.ly === "number") {
            mapa.set(p.iso, { lon: p.lx, lat: p.ly });
          }
        }
        setCentros(mapa);
      })
      .catch(() => undefined);
    return () => control.abort();
  }, [activo, centros]);
  return centros;
}

export function App() {
  const { ruta: rutaActual, busqueda, navegar, cambiarBusqueda } = useNavegacion();
  const ruta = analizarRuta(rutaActual);
  const idioma: Idioma = ruta.idioma;
  const t = textos(idioma);
  const fichaDeRuta = ruta.ficha;
  const idFicha = fichaDeRuta?.id ?? null;
  const claseFicha = fichaDeRuta?.clase ?? null;
  const filtros = useMemo(() => leerFiltros(busqueda), [busqueda]);
  const seleccion = useMemo(() => leerSeleccion(busqueda), [busqueda]);

  // La primera pintura es igual a la prerenderizada: la ficha de la ruta y todo lo que
  // depende del navegador (hora, anchura, almacenamiento) entran después de montar.
  const [montado, setMontado] = useState(false);
  const [ahora, setAhora] = useState<Date | null>(null);
  const [movil, setMovil] = useState(false);
  // Altos de lo que tapa el mapa arriba (cabecera) y abajo (atribuciones y leyendas), en cada
  // disposición.
  const [refArribaEsc, altoArribaEsc] = useAlto();
  const [refAbajoEsc, altoAbajoEsc] = useAlto();
  const [refArribaTel, altoArribaTel] = useAlto();
  const [refAbajoTel, altoAbajoTel] = useAlto();
  const [resumen, setResumen] = useState<Carga<Resumen>>(CARGANDO);
  const [ucrania, setUcrania] = useState<Carga<ResumenUcrania>>(CARGANDO);
  const [sistema, setSistema] = useState<EstadoSistema | null>(null);
  const [directo, setDirecto] = useState<Directo | null>(null);
  const [indiceGnss, setIndiceGnss] = useState<IndiceGnss | null>(null);
  const [gnssHoy, setGnssHoy] = useState<FicheroGnss | null>(null);
  const [gnssPeriodo, setGnssPeriodo] = useState<GnssDelPeriodo | null>(null);
  // Los ficheros de interferencia ya pedidos: cambiar de periodo no los vuelve a descargar.
  const ficherosGnss = useRef(new Map<string, Promise<FicheroGnss | null>>());
  const [incidente, setIncidente] = useState<Carga<IncidenteDetalle>>(CARGANDO);
  const [ataque, setAtaque] = useState<Carga<Ataque>>(CARGANDO);
  const [capas, setCapas] = useState<Capas>(CAPAS_INICIALES);
  const [panelLocal, setPanelLocal] = useState<PanelLocal>(null);
  const [impacto, setImpacto] = useState<Carga<ImpactoGuerra>>(CARGANDO);
  const idImpacto = panelLocal?.clase === "impacto" ? panelLocal.id : null;
  useEffect(() => {
    if (idImpacto === null) return undefined;
    const control = new AbortController();
    setImpacto(CARGANDO);
    void cargarImpacto(idImpacto, fetch, control.signal).then((carga) => {
      if (!control.signal.aborted) setImpacto(carga);
    });
    return () => control.abort();
  }, [idImpacto]);
  // Focos de calor de las últimas 24 horas que coinciden con un impacto (del almacén público):
  // cuentan en «Con satélite» como impactos con foco en cuanto se confirman.
  const [focosVivos, setFocosVivos] = useState<FocosVivos | null>(null);
  const verFocosVivos = capas.ucrania;
  useEffect(() => {
    if (!verFocosVivos) return undefined;
    const control = new AbortController();
    const pedir = () => {
      void fetch(urlDelAlmacen(OBJETO_FOCOS_VIVOS), { signal: control.signal, cache: "no-cache" })
        .then(async (respuesta) => {
          if (!respuesta.ok) return;
          const resultado = validarFocosVivos(await respuesta.json());
          if (resultado.ok && !control.signal.aborted) setFocosVivos(resultado.datos);
        })
        .catch(() => undefined);
    };
    pedir();
    const intervalo = window.setInterval(pedir, MS_FOCOS_VIVOS);
    return () => {
      control.abort();
      window.clearInterval(intervalo);
    };
  }, [verFocosVivos]);
  // Ciudades con alumbrado reducido de forma permanente: del almacén público, una vez por visita
  // y con la capa de Ucrania (el fichero cambia como mucho cada hora).
  const [alumbrado, setAlumbrado] = useState<AlumbradoReducido | null>(null);
  const verAlumbrado = capas.ucrania;
  useEffect(() => {
    if (!verAlumbrado || alumbrado !== null) return undefined;
    const control = new AbortController();
    void fetch(urlDelAlmacen(OBJETO_ALUMBRADO), { signal: control.signal })
      .then(async (respuesta) => {
        if (!respuesta.ok) return;
        const resultado = validarAlumbrado(await respuesta.json());
        if (resultado.ok && !control.signal.aborted) setAlumbrado(resultado.datos);
      })
      .catch(() => undefined);
    return () => control.abort();
  }, [verAlumbrado, alumbrado]);
  const [feedAbierto, setFeedAbierto] = useState(false);
  const [pestana, setPestana] = useState<Pestana>("directo");
  const [metodologia, setMetodologia] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  const [desplegado, setDesplegado] = useState<Desplegado>(null);
  const botonFiltros = useRef<HTMLButtonElement>(null);
  const botonAhora = useRef<HTMLButtonElement>(null);
  const botonPrevision = useRef<HTMLButtonElement>(null);
  const [noche, setNoche] = useState<number | null>(null);
  const [nochePausada, setNochePausada] = useState(false);
  const [menu, setMenu] = useState(false);
  const [hojaPropia, setHojaPropia] = useState<HojaPropia>(null);
  const [altura, setAltura] = useState<Altura>("media");
  const [mapaFallido, setMapaFallido] = useState(false);
  const [mapaPermitido, setMapaPermitido] = useState(false);
  const [api, setApi] = useState<ApiMapa | null>(null);
  const [visitaAnterior, setVisitaAnterior] = useState<string | null>(null);
  const [recorrido, setRecorrido] = useState<number | null>(null);
  const [novedadesDescartadas, setNovedadesDescartadas] = useState(false);
  // El pulso de las novedades se apaga al recorrerlas («Verlas»), al descartarlas o, una a
  // una, al abrir cada incidente.
  const [novedadesVistas, setNovedadesVistas] = useState(false);
  const [abiertos, setAbiertos] = useState<ReadonlySet<string>>(SIN_NOVEDADES);

  useEffect(() => {
    setMontado(true);
    setAhora(new Date());
    setVisitaAnterior(registrarVisita(almacenLocal(), new Date()));
    const reloj = window.setInterval(() => setAhora(new Date()), MS_ENTRE_COMPROBACIONES);
    const consulta = window.matchMedia(CONSULTA_MOVIL);
    const alCambiar = () => setMovil(consulta.matches);
    alCambiar();
    consulta.addEventListener("change", alCambiar);
    // El mapa (MapLibre) es lo más pesado: se carga cuando la página ya está pintada.
    const conInactividad = typeof window.requestIdleCallback === "function";
    const espera = conInactividad
      ? window.requestIdleCallback(() => setMapaPermitido(true), {
          timeout: MS_ESPERA_MAXIMA_DEL_MAPA,
        })
      : window.setTimeout(() => setMapaPermitido(true), 0);
    return () => {
      if (conInactividad) window.cancelIdleCallback(espera);
      else window.clearTimeout(espera);
      window.clearInterval(reloj);
      consulta.removeEventListener("change", alCambiar);
    };
  }, []);

  useEffect(() => {
    const control = new AbortController();
    void cargarResumen(fetch, control.signal).then((carga) => {
      if (!control.signal.aborted) setResumen(carga);
    });
    void cargarResumenUcrania(fetch, control.signal).then((carga) => {
      if (!control.signal.aborted) setUcrania(carga);
    });
    return () => control.abort();
  }, []);

  // La previsión no entra en la primera carga: se pide al abrir «Previsión» o la ficha de un país.
  const [prevision, setPrevision] = useState<Carga<DatosPrevision>>(CARGANDO);
  const [pidePrevision, setPidePrevision] = useState(false);
  // En el teléfono «Previsión» es una pestaña de «Europa ahora»: con un periodo elegido, un
  // tercer botón no cabe en 360 px y bajaría a otra fila sobre el mapa.
  const [pestanaAhora, setPestanaAhora] = useState<"ahora" | "prevision">("ahora");
  useEffect(() => {
    if (!pidePrevision) return;
    const control = new AbortController();
    void cargarPrevision(fetch, control.signal).then((carga) => {
      if (!control.signal.aborted) setPrevision(carga);
    });
    return () => control.abort();
  }, [pidePrevision]);

  // Estado del sistema: si no está publicado o no valida, la barra usa el cambio de datos.
  useEffect(() => {
    const control = new AbortController();
    const pedir = () =>
      void cargarEstadoSistema(fetch, control.signal).then((carga) => {
        if (!control.signal.aborted) setSistema(carga.estado === "listo" ? carga.datos : null);
      });
    pedir();
    const temporizador = window.setInterval(pedir, MS_ENTRE_ESTADOS);
    return () => {
      control.abort();
      window.clearInterval(temporizador);
    };
  }, []);

  // Detección en directo: directo.json cada minuto mientras la pestaña está a la vista, y
  // en cuanto vuelve a estarlo.
  useEffect(() => {
    const control = new AbortController();
    const pedir = () => {
      if (document.visibilityState === "hidden") return;
      void cargarDirecto(fetch, control.signal).then((carga) => {
        if (control.signal.aborted) return;
        if (carga.estado === "listo") setDirecto(carga.datos);
        else if (carga.estado !== "no_disponible") setDirecto(null);
      });
    };
    pedir();
    const temporizador = window.setInterval(pedir, MS_ENTRE_DIRECTOS);
    document.addEventListener("visibilitychange", pedir);
    return () => {
      control.abort();
      window.clearInterval(temporizador);
      document.removeEventListener("visibilitychange", pedir);
    };
  }, []);

  // Índice de la interferencia GPS y el último día publicado (para «Europa ahora»).
  const pedirGnss = useCallback((objeto: string): Promise<FicheroGnss | null> => {
    const guardado = ficherosGnss.current.get(objeto);
    if (guardado !== undefined) return guardado;
    const promesa = cargarFicheroGnss(objeto, fetch).then((carga) =>
      carga.estado === "listo" ? carga.datos : null,
    );
    ficherosGnss.current.set(objeto, promesa);
    return promesa;
  }, []);
  useEffect(() => {
    const control = new AbortController();
    void cargarIndiceGnss(fetch, control.signal).then((carga) => {
      if (control.signal.aborted) return;
      if (carga.estado !== "listo") {
        // Sin índice no hay ningún periodo con datos.
        setIndiceGnss({ version: 1, generado: "", dias: [], meses: [] });
        return;
      }
      setIndiceGnss(carga.datos);
      const ultimo = carga.datos.dias[carga.datos.dias.length - 1];
      if (ultimo === undefined) return;
      void pedirGnss(`dia/${ultimo}.json`).then((fichero) => {
        if (!control.signal.aborted) setGnssHoy(fichero);
      });
    });
    return () => control.abort();
  }, [pedirGnss]);

  // Ficha de la ruta: se carga y se valida su fichero.
  useEffect(() => {
    if (idFicha === null || claseFicha === null) return undefined;
    const control = new AbortController();
    if (claseFicha === "incidente") {
      setIncidente(CARGANDO);
      void cargarIncidente(idFicha, fetch, control.signal).then((carga) => {
        if (!control.signal.aborted) setIncidente(carga);
      });
    } else {
      setAtaque(CARGANDO);
      // Un ataque solo tiene sentido con su capa a la vista.
      setCapas((actuales) => ({ ...actuales, ucrania: true }));
      void cargarAtaque(idFicha, fetch, control.signal).then((carga) => {
        if (!control.signal.aborted) setAtaque(carga);
      });
    }
    return () => control.abort();
  }, [idFicha, claseFicha]);

  const datosResumen = datos(resumen);
  const datosUcrania = datos(ucrania);
  const ucraniaActiva = capas.ucrania ? datosUcrania : null;
  const hoy = datosResumen === null ? null : diaDeInstante(datosResumen.actualizado);
  // «Últimas 24 horas» se cuenta desde este momento (el de los datos, antes de montar).
  const instanteActual =
    ahora?.getTime() ?? (datosResumen === null ? null : Date.parse(datosResumen.actualizado));
  const es24Horas = seleccion.clase === "reciente" && seleccion.reciente === "24h";
  const instanteDelPeriodo = es24Horas ? instanteActual : null;

  const dominio = useMemo(
    () => (datosResumen === null ? null : dominioDe(datosResumen, ucraniaActiva)),
    [datosResumen, ucraniaActiva],
  );
  const periodo = useMemo(
    () =>
      dominio === null || hoy === null
        ? null
        : acotarPeriodo(periodoDeSeleccion(seleccion, hoy, instanteDelPeriodo ?? 0), dominio),
    [dominio, hoy, seleccion, instanteDelPeriodo],
  );
  const porId = useMemo(
    () => new Map((datosResumen?.incidentes ?? VACIO).map((i) => [i.id, i])),
    [datosResumen],
  );
  const filtrados = useMemo(
    () =>
      datosResumen === null || hoy === null
        ? VACIO
        : filtrar(datosResumen.incidentes, filtros),
    [datosResumen, filtros, hoy],
  );
  const delPeriodo = useMemo(
    () => (periodo === null ? VACIO : filtrados.filter((i) => incidenteEnPeriodo(i, periodo))),
    [filtrados, periodo],
  );
  // Interferencia GPS del periodo: los ficheros diarios (o mensuales) que lo cubren, sumados.
  const objetosGnss = useMemo(
    () => (capas.gnss && indiceGnss !== null && periodo !== null ? ficherosDelPeriodo(indiceGnss, periodo) : null),
    [capas.gnss, indiceGnss, periodo],
  );
  const claveGnss = objetosGnss === null ? null : objetosGnss.join("|");
  useEffect(() => {
    if (objetosGnss === null || claveGnss === null) return undefined;
    let vigente = true;
    setGnssPeriodo({ clave: claveGnss, estado: "cargando" });
    void Promise.all(objetosGnss.map(pedirGnss)).then((ficheros) => {
      if (!vigente) return;
      const validos = ficheros.filter((f): f is FicheroGnss => f !== null);
      setGnssPeriodo({
        clave: claveGnss,
        estado: "listo",
        agregado: validos.length === 0 ? null : agregar(validos),
      });
    });
    return () => {
      vigente = false;
    };
    // La clave resume la lista de ficheros: no se vuelve a pedir si no cambia.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claveGnss, pedirGnss]);
  const gnssActual =
    gnssPeriodo !== null && gnssPeriodo.clave === claveGnss && gnssPeriodo.estado === "listo"
      ? gnssPeriodo.agregado
      : null;
  const estadoGnss: EstadoGnss =
    indiceGnss === null
      ? "cargando"
      : gnssPeriodo === null || gnssPeriodo.clave !== claveGnss || gnssPeriodo.estado === "cargando"
        ? objetosGnss !== null && objetosGnss.length === 0
          ? "sin_datos"
          : "cargando"
        : gnssActual === null
          ? "sin_datos"
          : { dias: gnssActual.dias, zonas: zonasAltas(gnssActual) };
  const presion = useMemo(
    () =>
      capas.presion && periodo !== null && dominio !== null
        ? presionPorPais(filtrados, periodo, dominio.desde)
        : null,
    [capas.presion, periodo, dominio, filtrados],
  );
  const avisos = directo?.avisos ?? VACIO;

  // «En directo» enseña lo mismo que el mapa y la lista: los incidentes del periodo elegido.
  const eventos = useMemo(() => {
    const visibles = new Set(delPeriodo.map((i) => i.id));
    return (datosResumen?.eventos ?? VACIO).filter((evento) => visibles.has(evento.id));
  }, [datosResumen, delPeriodo]);
  /** Lo que lleva el destello de lo reciente en el mapa: lo mismo que «Últimas 24 horas». */
  const recientes = useMemo(
    () => (instanteActual === null ? null : ultimas24Horas(instanteActual)),
    [instanteActual],
  );
  const intensidad = useMemo(
    () =>
      ucraniaActiva === null || periodo === null ? null : ataquesPorRegion(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );
  const focosUcrania = useMemo(
    () =>
      ucraniaActiva === null || periodo === null ? null : focosDelPeriodo(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );
  // Impactos con lugar de los dos sentidos en el periodo: «Ver todo» los muestra todos.
  const impactos = useMemo(
    () =>
      ucraniaActiva === null || periodo === null ? null : impactosDelPeriodo(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );
  // «Noche a noche» recorre las noches del periodo elegido (con «Todo», todas).
  const noches = useMemo(
    () =>
      ucraniaActiva === null
        ? VACIO
        : nochesDeGuerra(ucraniaActiva).filter(
            (n) => seleccion.clase === "todo" || periodo === null || enPeriodo(n.jornada.desde, periodo),
          ),
    [ucraniaActiva, seleccion.clase, periodo],
  );
  // Guerra por satélite: corredores y pérdida de luz del periodo.
  const corredores = useMemo(
    () =>
      ucraniaActiva === null || periodo === null
        ? null
        : corredoresDelPeriodo(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );
  // Con muchos corredores, solo los principales, salvo que se pidan todos.
  const [todosLosCorredores, setTodosLosCorredores] = useState(false);
  const corredoresPrincipales = useMemo(() => (corredores === null ? null : principales(corredores)), [corredores]);
  const corredoresEnMapa = todosLosCorredores ? corredores : corredoresPrincipales;
  const lucesPeriodo = useMemo(
    () => (ucraniaActiva === null || periodo === null ? null : lucesDelPeriodo(ucraniaActiva, periodo)),
    [ucraniaActiva, periodo],
  );
  const luzRegiones = useMemo(
    () => (lucesPeriodo === null ? null : perdidaPorRegion(lucesPeriodo)),
    [lucesPeriodo],
  );
  const ciudadesSinLuz = useMemo(
    () => (lucesPeriodo === null ? null : ciudadesSinLuzDe(lucesPeriodo)),
    [lucesPeriodo],
  );
  // Puntos con información de satélite (imagen de antes y después, foco de calor, luz
  // nocturna): el índice de imágenes del almacén público se pide con la capa de guerra.
  const [indiceSatelite, setIndiceSatelite] = useState<IndiceSatelite | null>(null);
  useEffect(() => {
    if (!capas.ucrania || indiceSatelite !== null) return undefined;
    let vigente = true;
    void cargarIndiceSatelite().then((indice) => {
      if (vigente && indice !== null) setIndiceSatelite(indice);
    });
    return () => {
      vigente = false;
    };
  }, [capas.ucrania, indiceSatelite]);
  const puntosSatelite = useMemo(
    () =>
      capas.ucrania
        ? puntosConSatelite(
            impactos,
            indiceSatelite,
            ciudadesSinLuz,
            alumbrado?.ciudades ?? null,
            (fecha) => diaDeInstante(`${fecha}T00:00Z`),
            new Set(
              (focosVivos?.focos ?? []).flatMap(([, , , , impacto]) => (impacto ? [impacto] : [])),
            ),
          )
        : null,
    [capas.ucrania, impactos, indiceSatelite, ciudadesSinLuz, alumbrado, focosVivos],
  );
  // Filtro y despliegue de la lista de «Con satélite» (se abren también desde «Europa ahora» y
  // desde un enlace).
  const [filtroSatelite, setFiltroSatelite] = useState<TipoSatelite[]>([]);
  const [listaSatelite, setListaSatelite] = useState(false);
  // Lo único que mueve el mapa por sí solo: abrir algo (src/mapa/Mapa.tsx, Vuelo).
  const [vuelo, setVuelo] = useState<Vuelo | null>(null);
  // Lo que se acaba de abrir tocando el mapa («incidente:<id>», «aviso:<id>»): se asoma.
  const abiertoDesdeMapa = useRef<string | null>(null);
  const ultimoDestino = useRef<string | null>(null);
  const nocheActual = noche === null ? null : (noches[noche] ?? null);
  // Rutas de los drones: el índice y las noches se piden solo con la subcapa encendida (o al
  // reproducir noche a noche), del almacén público. Una noche cada vez: la última terminada, o la
  // que se está mostrando en «Noche a noche».
  const verRutas = RUTAS_EN_LA_WEB && capas.ucrania && capas.rutas;
  const [indiceRutas, setIndiceRutas] = useState<IndiceRutas | null>(null);
  const [nochesRutas, setNochesRutas] = useState<ReadonlyMap<string, NocheRutas>>(new Map());
  const [rutasPendientes, setRutasPendientes] = useState(0);
  useEffect(() => {
    // Con el interruptor apagado no se pide ningún fichero de rutas, tampoco en «Noche a noche».
    if (!RUTAS_EN_LA_WEB || (!verRutas && nocheActual === null) || indiceRutas !== null) return undefined;
    const control = new AbortController();
    void cargarIndiceRutas(control.signal).then((indice) => {
      if (indice !== null && !control.signal.aborted) setIndiceRutas(indice);
    });
    return () => control.abort();
  }, [verRutas, nocheActual, indiceRutas]);
  const nocheDeRutas = nocheActual === null ? null : nocheDeDia(nocheActual.jornada.desde);
  const nocheQueDibujar = useMemo(() => {
    if (indiceRutas === null) return null;
    if (nocheDeRutas !== null) return nocheQueSeDibuja(indiceRutas, nocheDeRutas);
    return verRutas ? nocheQueSeDibuja(indiceRutas, null) : null;
  }, [indiceRutas, nocheDeRutas, verRutas]);
  // Noches que no se pudieron leer: no se vuelven a pedir en bucle.
  const nochesFallidas = useRef(new Set<string>());
  useEffect(() => {
    const noche = nocheQueDibujar;
    if (noche === null || nochesRutas.has(noche) || nochesFallidas.current.has(noche)) return undefined;
    const control = new AbortController();
    setRutasPendientes(1);
    void cargarNocheRutas(noche, control.signal).then((cargada) => {
      if (control.signal.aborted) return;
      setRutasPendientes(0);
      if (cargada === null) {
        nochesFallidas.current.add(noche);
        return;
      }
      setNochesRutas((actual) => new Map(actual).set(cargada.noche, cargada));
    });
    return () => control.abort();
  }, [nocheQueDibujar, nochesRutas]);
  const rutasDibujadas = nocheQueDibujar === null ? null : (nochesRutas.get(nocheQueDibujar) ?? null);
  const rutasEnElMapa = useMemo(
    () => (rutasDibujadas === null ? null : rutasEnMapa(rutasDibujadas)),
    [rutasDibujadas],
  );

  // Novedades desde la visita anterior: se resaltan y se pueden recorrer.
  const eventosNuevos = useMemo(
    () => novedadesDesde(datosResumen?.eventos ?? VACIO, visitaAnterior),
    [datosResumen, visitaAnterior],
  );
  const incidentesNuevos = useMemo(() => incidentesDe(eventosNuevos), [eventosNuevos]);
  const novedades = useMemo(
    () => (novedadesDescartadas ? SIN_NOVEDADES : new Set(incidentesNuevos)),
    [incidentesNuevos, novedadesDescartadas],
  );

  /** Lo que late en el mapa: las novedades que el visitante aún no ha visto. */
  const latentes = useMemo(
    () =>
      novedadesQueLaten(incidentesNuevos, {
        descartadas: novedadesDescartadas,
        recorridas: novedadesVistas,
        abiertos,
      }),
    [incidentesNuevos, novedadesDescartadas, novedadesVistas, abiertos],
  );

  const contadores = datosResumen === null ? metaInicial : cifras(delPeriodo);

  // La previsión hace falta con su panel abierto o con la ficha de un país (su racha).
  useEffect(() => {
    if (
      hojaPropia === "prevision" ||
      desplegado === "prevision" ||
      (hojaPropia === "ahora" && pestanaAhora === "prevision") ||
      panelLocal?.clase === "pais"
    ) {
      setPidePrevision(true);
    }
  }, [hojaPropia, desplegado, panelLocal, pestanaAhora]);
  const cambiarFiltros = useCallback(
    (nuevos: EstadoFiltros) =>
      cambiarBusqueda(conSubcapasDe(escribirSeleccion(nuevos, seleccion), busqueda)),
    [cambiarBusqueda, seleccion, busqueda],
  );
  /**
   * Pone el periodo en la dirección (el de por defecto, todo, es no tener periodo). Cada cambio
   * deja una entrada en el historial: el botón atrás lo deshace.
   */
  const elegirSeleccion = useCallback(
    (nueva: SeleccionPeriodo) =>
      cambiarBusqueda(conSubcapasDe(escribirSeleccion(filtros, nueva), busqueda), true),
    [cambiarBusqueda, filtros, busqueda],
  );
  // Cambia las capas. Ninguna capa enciende nada por su cuenta: al apagar la de Ucrania, sus
  // subcapas se apagan y al volver a encenderla salen apagadas.
  const cambiarCapas = useCallback((nuevas: Capas) => {
    setCapas(nuevas.ucrania ? nuevas : { ...nuevas, corredores: false, satelite: false, rutas: false });
  }, []);
  // Un enlace con subcapas encendidas las abre encendidas (y con la capa de Ucrania). Se leen de
  // la dirección del navegador al montar: la búsqueda de la navegación llega vacía en la primera
  // pintura (la del prerenderizado) y se rellena justo después.
  const subcapasLeidas = useRef(false);
  useEffect(() => {
    subcapasLeidas.current = true;
    const delEnlace = leerSubcapas(window.location.search);
    if (delEnlace === null) return;
    setCapas((c) => ({
      ...c,
      ucrania: true,
      corredores: delEnlace.corredores,
      satelite: delEnlace.satelite,
      rutas: RUTAS_EN_LA_WEB && delEnlace.rutas,
    }));
    setFiltroSatelite(delEnlace.filtro);
    if (delEnlace.filtro.length > 0) setListaSatelite(true);
  }, []);
  // Las subcapas encendidas, en la dirección (una vez leída la del enlace).
  useEffect(() => {
    if (!subcapasLeidas.current || busqueda !== window.location.search) return;
    const nueva = conSubcapas(busqueda, {
      corredores: capas.ucrania && capas.corredores,
      satelite: capas.ucrania && capas.satelite,
      rutas: capas.ucrania && capas.rutas,
      filtro: filtroSatelite,
    });
    if (nueva !== busqueda) cambiarBusqueda(nueva);
  }, [capas.ucrania, capas.corredores, capas.satelite, capas.rutas, filtroSatelite, busqueda, cambiarBusqueda]);
  const quitarFiltros = useCallback(
    () => cambiarBusqueda(conSubcapasDe(escribirSeleccion(SIN_FILTROS, TODO), busqueda)),
    [cambiarBusqueda, busqueda],
  );

  // Reproducción de la guerra noche a noche: se puede pausar, reanudar y detener. Al llegar a
  // la última noche se queda en ella, en pausa; reanudar desde ahí vuelve a empezar.
  useEffect(() => {
    if (noche === null || nochePausada) return undefined;
    const temporizador = window.setTimeout(() => {
      if (noche + 1 >= noches.length) setNochePausada(true);
      else setNoche(noche + 1);
    }, MS_POR_NOCHE);
    return () => window.clearTimeout(temporizador);
  }, [noche, nochePausada, noches.length]);
  const empezarNoches = useCallback(() => {
    setCapas((actuales) => ({ ...actuales, ucrania: true }));
    setNochePausada(false);
    setNoche(0);
  }, []);
  const detenerNoches = useCallback(() => {
    setNoche(null);
    setNochePausada(false);
  }, []);

  const fichaActiva = montado ? fichaDeRuta : null;
  const idAbierto = fichaActiva?.clase === "incidente" ? fichaActiva.id : null;
  const recorridoAbierto = useMemo(
    () =>
      idAbierto !== null && incidente.estado === "listo" && incidente.datos.id === idAbierto
        ? recorridoEnMapa(incidente.datos.recorrido)
        : null,
    [idAbierto, incidente],
  );
  useEffect(() => {
    if (idAbierto !== null) setAbiertos((previos) => new Set([...previos, idAbierto]));
  }, [idAbierto]);
  const elegido =
    fichaActiva?.clase === "incidente" ? (porId.get(fichaActiva.id) ?? null) : null;
  const paisImpreciso = elegido !== null && elegido.punto === null ? elegido.pais : null;
  const centros = useCentrosDePais(paisImpreciso !== null);
  const centroPais = paisImpreciso === null ? null : (centros?.get(paisImpreciso) ?? null);

  const pila = useMemo(
    () =>
      panelLocal?.clase === "pila"
        ? panelLocal.ids
            .map((id) => porId.get(id))
            .filter((i): i is IncidenteResumen => i !== undefined)
        : VACIO,
    [panelLocal, porId],
  );

  const avisoAbierto =
    panelLocal?.clase === "aviso" ? (avisos.find((a) => a.id === panelLocal.id) ?? null) : null;
  // Lo abierto que tiene sitio en el mapa, con su clave. Al cerrarlo no hay destino y el mapa no
  // se mueve: antes, el destino caía en el último punto elegido en «Con satélite» (en el este) y
  // el mapa volaba allí al cerrar cualquier ficha.
  const destino = useMemo<{ clave: string; encuadre: Encuadre } | null>(() => {
    if (elegido?.punto) {
      return { clave: `incidente:${elegido.id}`, encuadre: { lon: elegido.punto.lon, lat: elegido.punto.lat } };
    }
    if (elegido?.aproximado) {
      // Lugar aproximado: se ve la zona entera que nombra la fuente, no un sitio concreto.
      const { lon, lat, nivel } = elegido.aproximado;
      return { clave: `incidente:${elegido.id}`, encuadre: { lon, lat, zoom: ZOOM_APROXIMADO[nivel] } };
    }
    if (avisoAbierto !== null) {
      return {
        clave: `aviso:${avisoAbierto.id}`,
        encuadre: { lon: avisoAbierto.lon, lat: avisoAbierto.lat, zoom: ZOOM_DE_AVISO },
      };
    }
    if (elegido !== null && centroPais !== null) {
      return { clave: `incidente:${elegido.id}`, encuadre: { ...centroPais, zoom: ZOOM_DE_PAIS } };
    }
    if (fichaActiva?.clase === "ataque") return { clave: `ataque:${fichaActiva.id}`, encuadre: "ucrania" };
    return null;
    // El destino depende del aviso abierto, no de que directo.json se renueve cada minuto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elegido, centroPais, fichaActiva, avisoAbierto?.id]);
  // Una sola petición por cada cosa que se abre; cerrar no pide nada.
  useEffect(() => {
    if (destino === null) {
      ultimoDestino.current = null;
      return;
    }
    if (destino.clave === ultimoDestino.current) return;
    ultimoDestino.current = destino.clave;
    const modo = abiertoDesdeMapa.current === destino.clave ? "asomar" : "ir";
    abiertoDesdeMapa.current = null;
    setVuelo((anterior) => ({ encuadre: destino.encuadre, modo, n: (anterior?.n ?? 0) + 1 }));
  }, [destino]);

  const regionesDelAtaque = useMemo(() => {
    const actual = datos(ataque);
    return fichaActiva?.clase === "ataque" && actual !== null && actual.id === fichaActiva.id
      ? (actual.regiones ?? []).map((r) => r.region)
      : VACIO;
  }, [ataque, fichaActiva]);
  const regionLocal =
    fichaActiva === null && panelLocal?.clase === "region" ? panelLocal.codigo : null;
  const regionesElegidas = useMemo(
    () => (regionLocal === null ? regionesDelAtaque : [regionLocal]),
    [regionLocal, regionesDelAtaque],
  );

  const abrirIncidente = useCallback(
    (id: string) => {
      setPanelLocal(null);
      setHojaPropia(null);
      setAltura(alturaInicial());
      navegar(rutaDeFicha(id, idioma));
    },
    [navegar, idioma],
  );
  const abrirPila = useCallback(
    (ids: string[]) => {
      setHojaPropia(null);
      setAltura(alturaInicial());
      setPanelLocal({ clase: "pila", ids });
      if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
    },
    [navegar, idioma],
  );
  const abrirRegion = useCallback(
    (codigo: string) => {
      if (!REGION_DE_LA_CAPA.test(codigo)) return;
      setHojaPropia(null);
      setAltura(alturaInicial());
      setPanelLocal({ clase: "region", codigo });
      if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
    },
    [navegar, idioma],
  );
  const abrirImpacto = useCallback(
    (id: string) => {
      setHojaPropia(null);
      setAltura(alturaInicial());
      setPanelLocal({ clase: "impacto", id });
      if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
    },
    [navegar, idioma],
  );
  const abrirLocal = useCallback(
    (panel: Exclude<PanelLocal, null>) => {
      setHojaPropia(null);
      setAltura(alturaInicial());
      setPanelLocal(panel);
      if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
    },
    [navegar, idioma],
  );
  const abrirAviso = useCallback((id: string) => abrirLocal({ clase: "aviso", id }), [abrirLocal]);
  /** Lo que se abre tocando el mapa: ya está a la vista, solo se asoma. */
  const abrirIncidenteDesdeMapa = useCallback(
    (id: string) => {
      abiertoDesdeMapa.current = `incidente:${id}`;
      abrirIncidente(id);
    },
    [abrirIncidente],
  );
  const elegirDeLaPila = useCallback((id: string) => {
    abiertoDesdeMapa.current = `incidente:${id}`;
  }, []);
  const abrirAvisoDesdeMapa = useCallback(
    (id: string) => {
      abiertoDesdeMapa.current = `aviso:${id}`;
      abrirAviso(id);
    },
    [abrirAviso],
  );
  const abrirCelda = useCallback((h3: string) => abrirLocal({ clase: "celda", h3 }), [abrirLocal]);
  const abrirPais = useCallback((iso: string) => abrirLocal({ clase: "pais", iso }), [abrirLocal]);
  // Abrir algo de una subcapa (un corredor, un apagón, una ciudad a oscuras) la enciende.
  const abrirCorredor = useCallback(
    (clave: string) => {
      setCapas((c) => ({ ...c, ucrania: true, corredores: true }));
      abrirLocal({ clase: "corredor", clave });
    },
    [abrirLocal],
  );
  const abrirRuta = useCallback(
    (clave: string) => abrirLocal({ clase: "ruta", clave }),
    [abrirLocal],
  );
  const abrirCiudadLuz = useCallback(
    (clave: string) => {
      setCapas((c) => ({ ...c, ucrania: true, satelite: true }));
      abrirLocal({ clase: "luz", clave });
    },
    [abrirLocal],
  );
  const abrirCorredores = useCallback(
    (claves: string[]) => abrirLocal({ clase: "corredores", claves }),
    [abrirLocal],
  );
  const abrirAlumbrado = useCallback(
    (clave: string) => {
      setCapas((c) => ({ ...c, ucrania: true, satelite: true }));
      abrirLocal({ clase: "alumbrado", clave });
    },
    [abrirLocal],
  );
  // Una fila de la lista de «Con satélite»: el mapa va al punto y se abre su ficha.
  const elegirSatelite = useCallback(
    (punto: PuntoSatelite) => {
      setMenu(false);
      // Ir a él: se ha elegido en una lista.
      setVuelo((anterior) => ({
        encuadre: { lon: punto.lon, lat: punto.lat, zoom: ZOOM_PUNTO_SATELITE },
        modo: "ir",
        n: (anterior?.n ?? 0) + 1,
      }));
      if (punto.clase === "impacto") abrirImpacto(punto.clave);
      else if (punto.clase === "luz") abrirCiudadLuz(punto.clave);
      else abrirAlumbrado(punto.clave);
    },
    [abrirImpacto, abrirCiudadLuz, abrirAlumbrado],
  );
  const botonSatelite = (grande: boolean) =>
    puntosSatelite === null ? null : (
      <BotonSatelite
        t={t}
        idioma={idioma}
        puntos={puntosSatelite}
        activo={capas.satelite}
        onActivo={(activo) => {
          setCapas((c) => ({ ...c, satelite: activo }));
          if (!activo) setListaSatelite(false);
        }}
        abierta={listaSatelite}
        onAbierta={setListaSatelite}
        filtro={filtroSatelite}
        onFiltro={setFiltroSatelite}
        onElegir={elegirSatelite}
        grande={grande}
      />
    );
  const cerrarFicha = useCallback(() => {
    setPanelLocal(null);
    if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
  }, [navegar, idioma]);
  const fallarMapa = useCallback(() => setMapaFallido(true), []);

  /** En el teléfono, una sola hoja a la vez: abrir una cierra la ficha o la anterior. */
  const abrirHoja = useCallback(
    (hoja: Exclude<HojaPropia, null>) => {
      cerrarFicha();
      setMenu(false);
      setAltura(alturaInicial());
      setHojaPropia((actual) => (actual === hoja ? null : hoja));
    },
    [cerrarFicha],
  );
  const cifrasDelMomento = useMemo(
    () => cifrasAhora({ resumen: datosResumen, ucrania: datosUcrania, directo, gnssHoy, ahora: ahora?.getTime() ?? null }),
    [datosResumen, datosUcrania, directo, gnssHoy, ahora],
  );
  /** Cada cifra de «Europa ahora» lleva al sitio del mapa que la explica. */
  const irACifra = useCallback(
    (cifra: CifraAhora) => {
      setMenu(false);
      setDesplegado(null);
      setHojaPropia(null);
      switch (cifra) {
        case "cierres": {
          const primero = ordenarAvisos(cierresEnCurso(directo))[0];
          if (primero !== undefined) abrirAviso(primero.id);
          else api?.vistaInicial();
          return;
        }
        case "incidentes":
          setCapas((c) => ({ ...c, incidentes: true }));
          elegirSeleccion({ clase: "reciente", reciente: "7d" });
          api?.vistaInicial();
          return;
        case "drones": {
          // Los ataques entran en un periodo por el día en que empieza su noche.
          const parte = cifrasDelMomento.drones?.jornada ?? null;
          setCapas((c) => ({ ...c, ucrania: true }));
          if (parte !== null) {
            elegirSeleccion({ clase: "entre", periodo: { desde: parte.desde, hasta: parte.desde } });
          }
          api?.volar("ucrania");
          return;
        }
        case "focos":
          setCapas((c) => ({ ...c, ucrania: true, satelite: true }));
          setFiltroSatelite(["foco"]);
          setListaSatelite(true);
          // Sin tocar el periodo: la lista, de la más reciente a la más antigua, empieza por los
          // focos de la semana y sigue con los anteriores.
          api?.vistaInicial();
          return;
        case "gnss":
          setCapas((c) => ({ ...c, gnss: true }));
          if (cifrasDelMomento.gnss !== null) {
            const dia = cifrasDelMomento.gnss.dia;
            elegirSeleccion({ clase: "entre", periodo: { desde: dia, hasta: dia } });
          }
          api?.vistaInicial();
          return;
      }
    },
    [directo, abrirAviso, api, elegirSeleccion, cifrasDelMomento],
  );

  const irARacha = useCallback(
    (racha: Racha) => {
      setMenu(false);
      setDesplegado(null);
      setHojaPropia(null);
      setCapas((c) => ({ ...c, incidentes: true }));
      const periodo = { desde: diaDeTexto(racha.desde), hasta: diaDeTexto(racha.hasta) };
      cambiarBusqueda(
        conSubcapasDe(
          escribirSeleccion({ ...filtros, paises: [racha.pais] }, { clase: "entre", periodo }),
          busqueda,
        ),
        true,
      );
      const caja = prevision.estado === "listo" ? prevision.datos.cajas[racha.pais] : undefined;
      if (caja !== undefined) {
        setVuelo((anterior) => ({ encuadre: { caja }, modo: "ir", n: (anterior?.n ?? 0) + 1 }));
      }
    },
    [cambiarBusqueda, filtros, busqueda, prevision],
  );

  const irANovedad = useCallback(
    (posicion: number) => {
      const id = incidentesNuevos[posicion];
      if (id === undefined) return;
      setNovedadesVistas(true);
      setRecorrido(posicion);
      setDesplegado(null);
      abrirIncidente(id);
    },
    [incidentesNuevos, abrirIncidente],
  );

  // En el teléfono, las hojas de los filtros y de «Europa ahora» se cierran tocando fuera
  // (un toque, no un arrastre: se puede mover el mapa con ellas abiertas).
  useEffect(() => {
    if (!movil || (hojaPropia !== "filtros" && hojaPropia !== "ahora" && hojaPropia !== "prevision")) return;
    const alTocar = (evento: MouseEvent) => {
      const objetivo = evento.target;
      if (objetivo instanceof Element && objetivo.closest("[data-hoja-propia]") !== null) return;
      setHojaPropia(null);
    };
    document.addEventListener("click", alTocar, true);
    return () => document.removeEventListener("click", alTocar, true);
  }, [movil, hojaPropia]);

  // Atajos de teclado.
  const hayFicha = fichaActiva !== null || panelLocal !== null;
  /** Tocar el mapa fuera de todo cierra la ficha abierta; el mapa no se mueve. */
  const tocarFuera = useCallback(() => {
    if (hayFicha) cerrarFicha();
  }, [hayFicha, cerrarFicha]);
  const ejecutar = useCallback(
    (accion: Accion) => {
      switch (accion) {
        case "ayuda":
          setAyuda((abierta) => !abierta);
          return;
        case "cerrar":
          // Primero lo abierto: desplegable, ficha, hoja, directo; y la reproducción de noches.
          if (desplegado !== null) setDesplegado(null);
          else if (hayFicha) cerrarFicha();
          else if (hojaPropia !== null) setHojaPropia(null);
          else if (feedAbierto) setFeedAbierto(false);
          else if (noche !== null) detenerNoches();
          return;
        case "capaIncidentes":
          setCapas((c) => ({ ...c, incidentes: !c.incidentes }));
          return;
        case "capaUcrania":
          setCapas((c) =>
            c.ucrania
              ? { ...c, ucrania: false, corredores: false, satelite: false, rutas: false }
              : { ...c, ucrania: true },
          );
          return;
        case "capaSatelite":
          setCapas((c) => ({ ...c, ucrania: true, satelite: !c.satelite }));
          return;
        case "capaDensidad":
          setCapas((c) => ({ ...c, densidad: !c.densidad }));
          return;
        case "filtroGraves":
          cambiarFiltros({ ...filtros, estados: soloGraves(filtros.estados) ? [] : [...GRAVES] });
          return;
        case "filtro24h":
          elegirSeleccion(filtros.reciente === "24h" ? TODO : { clase: "reciente", reciente: "24h" });
          return;
        case "filtro7d":
          elegirSeleccion(filtros.reciente === "7d" ? TODO : { clase: "reciente", reciente: "7d" });
          return;
        case "sinFiltros":
          quitarFiltros();
          return;
        case "filtros":
          if (movil) abrirHoja("filtros");
          else setDesplegado((actual) => (actual === "filtros" ? null : "filtros"));
          return;
        case "ahora":
          if (movil) abrirHoja("ahora");
          else setDesplegado((actual) => (actual === "ahora" ? null : "ahora"));
          return;
        case "feed":
          if (movil) abrirHoja("directo");
          else setFeedAbierto((abierto) => !abierto);
          return;
        case "lista":
          if (movil) abrirHoja("directo");
          else setFeedAbierto(true);
          setPestana("lista");
          return;
        case "metodologia":
          setMetodologia(true);
          return;
      }
    },
    [
      desplegado,
      hayFicha,
      cerrarFicha,
      hojaPropia,
      feedAbierto,
      noche,
      detenerNoches,
      cambiarFiltros,
      elegirSeleccion,
      quitarFiltros,
      filtros,
      movil,
      abrirHoja,
    ],
  );

  useEffect(() => {
    function alPulsar(evento: KeyboardEvent) {
      // Con un diálogo abierto (ayuda, metodología) manda el diálogo.
      if (document.querySelector("dialog[open]") !== null) return;
      const accion = accionDe(evento);
      if (accion === null) return;
      evento.preventDefault();
      ejecutar(accion);
    }
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, [ejecutar]);

  // Título de la pestaña e idioma del documento, que cambian sin recargar la página.
  const tituloIncidente =
    fichaActiva?.clase === "incidente" ? (elegido?.titulo[idioma] ?? fichaActiva.id) : null;
  const tituloPagina =
    fichaActiva === null
      ? t.compartir.titulo
      : fichaActiva.clase === "ataque"
        ? t.compartir.tituloAtaque(fichaActiva.id)
        : t.compartir.tituloIncidente(tituloIncidente ?? fichaActiva.id);
  useEffect(() => {
    document.documentElement.lang = idioma;
    document.title = tituloPagina;
  }, [idioma, tituloPagina]);

  const actualizado =
    datosResumen?.actualizado ?? (resumen.estado === "cargando" ? metaInicial.actualizado : null);
  const avisoDeDatos =
    resumen.estado === "no_valido" || (capas.ucrania && ucrania.estado === "no_valido")
      ? t.avisos.datosNoValidos
      : resumen.estado === "no_disponible" ||
          resumen.estado === "no_encontrado" ||
          (capas.ucrania &&
            (ucrania.estado === "no_disponible" || ucrania.estado === "no_encontrado"))
        ? t.avisos.datosNoDisponibles
        : null;
  const textoPeriodo =
    periodo === null ? "" : t.tiempo.periodo(fechaDia(periodo.desde), fechaDia(periodo.hasta));
  const otro: Idioma = idioma === "es" ? "en" : "es";
  const rutaOtroIdioma =
    fichaDeRuta === null ? rutaDeIdioma(otro) : rutaDeFicha(fichaDeRuta.id, otro);
  const paisesConIncidentes = useMemo(
    () => [...new Set((datosResumen?.incidentes ?? VACIO).map((i) => i.pais))],
    [datosResumen],
  );
  // Tipos de dron con algún incidente, en el orden de los grupos: las opciones del filtro. Lo
  // deducido sin porcentajes va en una sola opción, «compatible con dron de la guerra».
  const dronConIncidentes = useMemo(() => {
    const presentes = new Set((datosResumen?.incidentes ?? VACIO).flatMap((i) => i.dron));
    return ORIGENES_TIPO_DRON.flatMap((origen) =>
      [...(origen === "deducido" ? [DRON_DE_LA_GUERRA] : []), ...GRUPOS_DRON]
        .map((grupo) => `${origen}:${grupo}`)
        .filter((clave) => presentes.has(clave)),
    );
  }, [datosResumen]);
  // Modelos que nombra la autoridad en cada clase identificada («autoridad:senuelo» → Gerbera).
  const modelosDron = useMemo(() => {
    const modelos: Record<string, string[]> = {};
    for (const i of datosResumen?.incidentes ?? VACIO) {
      const clave = i.dron[0];
      if (i.modeloDron === undefined || clave === undefined) continue;
      const lista = (modelos[clave] ??= []);
      if (!lista.includes(i.modeloDron)) lista.push(i.modeloDron);
    }
    return modelos;
  }, [datosResumen]);

  // La ficha abierta es una de las novedades que se están recorriendo: lleva su recorrido.
  const posicionEnRecorrido =
    recorrido !== null && !novedadesDescartadas && idAbierto !== null && incidentesNuevos[recorrido] === idAbierto
      ? recorrido
      : null;
  let ficha: { nombre: string; contenido: React.ReactNode } | null = null;
  if (fichaActiva?.clase === "incidente") {
    ficha = {
      nombre: `${t.ficha.titulo} ${fichaActiva.id}`,
      contenido: (
        <>
          <CabeceraFicha
            t={t}
            etiqueta={<span className="mono">{fichaActiva.id}</span>}
            enlace={ORIGEN + rutaDeFicha(fichaActiva.id, idioma)}
            onCerrar={cerrarFicha}
          />
          {posicionEnRecorrido !== null && (
            <RecorridoNovedades
              t={t}
              posicion={posicionEnRecorrido}
              total={incidentesNuevos.length}
              onIr={irANovedad}
            />
          )}
          <div className="overflow-y-auto px-4 py-3">
            <SegunCarga t={t} carga={incidente}>
              {(detalle) => <FichaIncidente t={t} idioma={idioma} incidente={detalle} />}
            </SegunCarga>
          </div>
        </>
      ),
    };
  } else if (fichaActiva?.clase === "ataque") {
    ficha = {
      nombre: `${t.ataque.etiqueta} ${fichaActiva.id}`,
      contenido: (
        <>
          <CabeceraFicha
            t={t}
            etiqueta={t.ataque.etiqueta}
            enlace={ORIGEN + rutaDeFicha(fichaActiva.id, idioma)}
            onCerrar={cerrarFicha}
          />
          <div className="overflow-y-auto px-4 py-3">
            <SegunCarga t={t} carga={ataque}>
              {(detalle) => (
                <FichaAtaque
                  t={t}
                  idioma={idioma}
                  ataque={detalle}
                  centros={datosUcrania === null ? undefined : centrosDeFocos(datosUcrania)}
                />
              )}
            </SegunCarga>
          </div>
        </>
      ),
    };
  } else if (panelLocal?.clase === "region" && datosUcrania !== null && periodo !== null) {
    ficha = {
      nombre: `${t.region.etiqueta} ${panelLocal.codigo}`,
      contenido: (
        <>
          <CabeceraFicha t={t} etiqueta={t.region.etiqueta} onCerrar={cerrarFicha} />
          <div className="overflow-y-auto px-4 py-3">
            <FichaRegion
              key={panelLocal.codigo}
              t={t}
              idioma={idioma}
              codigo={panelLocal.codigo}
              cifras={cifrasDeRegion(datosUcrania, panelLocal.codigo, periodo)}
              periodo={textoPeriodo}
              focos={focosDelPeriodo(datosUcrania, periodo, panelLocal.codigo)}
              fuentes={datosUcrania.fuentes}
              impactos={impactosDelPeriodo(datosUcrania, periodo, panelLocal.codigo)}
              luces={lucesDelPeriodo(datosUcrania, periodo, panelLocal.codigo).filter(
                (l) => l.zona === "region",
              )}
              onImpacto={abrirImpacto}
            />
          </div>
        </>
      ),
    };
  } else if (panelLocal?.clase === "impacto") {
    ficha = {
      nombre: `${t.impacto.etiqueta} ${panelLocal.id}`,
      contenido: (
        <>
          <CabeceraFicha t={t} etiqueta={t.impacto.etiqueta} onCerrar={cerrarFicha} />
          <div className="overflow-y-auto px-4 py-3">
            <SegunCarga t={t} carga={impacto}>
              {(detalle) => <FichaImpacto t={t} idioma={idioma} impacto={detalle} />}
            </SegunCarga>
          </div>
        </>
      ),
    };
  } else if (panelLocal?.clase === "aviso" && avisoAbierto !== null && directo !== null) {
    ficha = {
      nombre: `${t.directo.etiqueta} ${avisoAbierto.oaci}`,
      contenido: (
        <>
          <CabeceraFicha t={t} etiqueta={t.directo.etiqueta} onCerrar={cerrarFicha} />
          <div className="overflow-y-auto px-4 py-3">
            <FichaAviso t={t} idioma={idioma} aviso={avisoAbierto} directo={directo} />
          </div>
        </>
      ),
    };
  } else if (panelLocal?.clase === "celda" && gnssActual !== null) {
    const celda = gnssActual.celdas.find((c) => c.h3 === panelLocal.h3);
    if (celda !== undefined) {
      ficha = {
        nombre: `${t.gnss.etiqueta} ${celda.h3}`,
        contenido: (
          <>
            <CabeceraFicha t={t} etiqueta={t.gnss.etiqueta} onCerrar={cerrarFicha} />
            <div className="overflow-y-auto px-4 py-3">
              <FichaCelda t={t} idioma={idioma} celda={celda} periodo={textoPeriodo} dias={gnssActual.dias} />
            </div>
          </>
        ),
      };
    }
  } else if (panelLocal?.clase === "corredor" && corredores !== null) {
    const corredor = corredores.find((c) => c.clave === panelLocal.clave);
    if (corredor !== undefined) {
      ficha = {
        nombre: t.satelite.corredor.etiqueta,
        contenido: (
          <>
            <CabeceraFicha t={t} etiqueta={t.satelite.corredor.etiqueta} onCerrar={cerrarFicha} />
            <div className="overflow-y-auto px-4 py-3">
              <FichaCorredor t={t} idioma={idioma} corredor={corredor} periodo={textoPeriodo} />
            </div>
          </>
        ),
      };
    }
  } else if (panelLocal?.clase === "ruta") {
    const elegida = recorridoDeClave(nochesRutas, panelLocal.clave);
    if (elegida !== null) {
      ficha = {
        nombre: t.rutas.etiqueta,
        contenido: (
          <>
            <CabeceraFicha t={t} etiqueta={t.rutas.etiqueta} onCerrar={cerrarFicha} />
            <div className="overflow-y-auto px-4 py-3">
              <FichaRuta t={t} idioma={idioma} noche={elegida.noche} recorrido={elegida.recorrido} />
            </div>
          </>
        ),
      };
    }
  } else if (panelLocal?.clase === "luz" && ciudadesSinLuz !== null) {
    const ciudad = ciudadesSinLuz.find((c) => `${c.region}|${c.nombre}` === panelLocal.clave);
    if (ciudad !== undefined) {
      ficha = {
        nombre: `${t.satelite.luzFicha.etiqueta} ${ciudad.nombre}`,
        contenido: (
          <>
            <CabeceraFicha t={t} etiqueta={t.satelite.luzFicha.etiqueta} onCerrar={cerrarFicha} />
            <div className="overflow-y-auto px-4 py-3">
              <FichaLuz t={t} idioma={idioma} ciudad={ciudad} periodo={textoPeriodo} />
            </div>
          </>
        ),
      };
    }
  } else if (panelLocal?.clase === "corredores" && corredores !== null) {
    const elegibles = panelLocal.claves.flatMap((clave) =>
      corredores.filter((c) => c.clave === clave),
    );
    ficha = {
      nombre: t.satelite.corredor.etiquetaVarios,
      contenido: (
        <>
          <CabeceraFicha t={t} etiqueta={t.satelite.corredor.etiquetaVarios} onCerrar={cerrarFicha} />
          <div className="overflow-y-auto px-4 py-3">
            <ListaCorredores t={t} corredores={elegibles} onElegir={abrirCorredor} />
          </div>
        </>
      ),
    };
  } else if (panelLocal?.clase === "alumbrado" && alumbrado !== null) {
    const ciudad = alumbrado.ciudades.find((c) => c.ciudad.id === panelLocal.clave);
    if (ciudad !== undefined) {
      ficha = {
        nombre: `${t.satelite.alumbradoFicha.etiqueta} ${ciudad.ciudad.nombre}`,
        contenido: (
          <>
            <CabeceraFicha t={t} etiqueta={t.satelite.alumbradoFicha.etiqueta} onCerrar={cerrarFicha} />
            <div className="overflow-y-auto px-4 py-3">
              <FichaAlumbrado t={t} idioma={idioma} ciudad={ciudad} />
            </div>
          </>
        ),
      };
    }
  } else if (panelLocal?.clase === "pais" && periodo !== null) {
    ficha = {
      nombre: `${t.presion.etiqueta} ${panelLocal.iso}`,
      contenido: (
        <>
          <CabeceraFicha t={t} etiqueta={t.presion.etiqueta} onCerrar={cerrarFicha} />
          <div className="overflow-y-auto px-4 py-3">
            <FichaPais
              key={panelLocal.iso}
              t={t}
              idioma={idioma}
              iso={panelLocal.iso}
              presion={presion?.get(panelLocal.iso) ?? null}
              cifras={cifrasDePais(filtrados, panelLocal.iso, periodo)}
              periodo={textoPeriodo}
              racha={rachaDe(prevision.estado === "listo" ? prevision.datos : null, panelLocal.iso)}
              sinComparacion={seleccion.clase === "todo"}
            />
          </div>
        </>
      ),
    };
  } else if (panelLocal?.clase === "pila" && pila.length > 0) {
    ficha = {
      nombre: t.pila.titulo(pila.length),
      contenido: (
        <>
          <CabeceraFicha t={t} etiqueta={t.pila.titulo(pila.length)} onCerrar={cerrarFicha} />
          <SelectorPila t={t} idioma={idioma} incidentes={pila} alElegir={elegirDeLaPila} />
        </>
      ),
    };
  }


  const lista = (
    <Lista
      t={t}
      idioma={idioma}
      incidentes={delPeriodo}
      regiones={ucraniaActiva?.regiones ?? VACIO}
      onRegion={abrirRegion}
    />
  );

  // Las dos disposiciones van en el HTML prerenderizado y el CSS muestra la que toca antes de
  // que llegue el script (sin saltos al cargar); ya en el navegador solo queda la que se usa.
  const verEscritorio = !montado || !movil;
  const verTelefono = !montado || movil;
  const hojaAbierta = movil && (ficha !== null || hojaPropia !== null);
  const reserva: Reserva = movil
    ? {
        arriba: altoArribaTel,
        derecha: 0,
        abajo: hojaAbierta
          ? Math.round((window.innerHeight - altoArribaTel) * ALTURAS[altura])
          : altoAbajoTel,
        izquierda: 0,
      }
    : {
        arriba: altoArribaEsc,
        derecha: ficha === null ? 0 : ANCHO_FICHA_PX,
        abajo: altoAbajoEsc,
        izquierda: feedAbierto ? ANCHO_FEED_PX : 0,
      };

  const estadoDatos = (corta: boolean) => (
    <BarraEstado
      t={t}
      actualizado={actualizado}
      sistema={sistema}
      ahora={ahora}
      corta={corta}
      alinear={corta ? "derecha" : "izquierda"}
    />
  );
  const filtrosDeLaPantalla = (
    <Filtros
      t={t}
      idioma={idioma}
      filtros={filtros}
      onFiltros={cambiarFiltros}
      seleccion={seleccion}
      onSeleccion={elegirSeleccion}
      dominio={dominio}
      paises={paisesConIncidentes}
      dron={dronConIncidentes}
      modelosDron={modelosDron}
      onQuitar={quitarFiltros}
    />
  );
  const feed = (enHoja: boolean) => (
    <Feed
      t={t}
      idioma={idioma}
      pestana={pestana}
      onPestana={setPestana}
      eventos={eventos}
      porId={porId}
      novedades={novedades}
      ahora={ahora}
      onAbrir={abrirIncidente}
      onCerrar={() => (enHoja ? setHojaPropia(null) : setFeedAbierto(false))}
      lista={lista}
      enHoja={enHoja}
    />
  );
  const hayCorredores =
    capas.ucrania &&
    capas.corredores &&
    corredores !== null &&
    corredoresPrincipales !== null &&
    corredores.length > 0;
  const hayRutas = (verRutas && indiceRutas !== null) || (nocheActual !== null && rutasDibujadas !== null);
  const leyendas = (capas.gnss || capas.presion || hayCorredores || hayRutas) && (
    <div className="flex flex-col items-start gap-1.5" data-leyendas="">
      {hayRutas && indiceRutas !== null && (
        <LeyendaRutas
          t={t}
          noche={nocheQueDibujar}
          mostrados={rutasEnElMapa?.mostrados ?? 0}
          total={rutasEnElMapa?.total ?? 0}
          conNeptun={rutasDibujadas?.fuente === "neptun"}
          atribucion={indiceRutas.atribucion_neptun}
          cargando={rutasPendientes > 0}
        />
      )}
      {hayCorredores && corredores !== null && corredoresPrincipales !== null && (
        <LeyendaCorredores
          t={t}
          principales={corredoresPrincipales.length}
          total={corredores.length}
          todos={todosLosCorredores}
          onTodos={() => setTodosLosCorredores((actual) => !actual)}
        />
      )}
      {capas.presion && <LeyendaPresion t={t} seleccion={seleccion} />}
      {capas.gnss && <LeyendaGnss t={t} estado={estadoGnss} />}
    </div>
  );
  const europaAhora = (
    <>
      {!novedadesDescartadas && (
        <LineaNovedades
          t={t}
          cuantas={incidentesNuevos.length}
          onVer={() => irANovedad(0)}
          onDescartar={() => setNovedadesDescartadas(true)}
        />
      )}
      <EuropaAhora t={t} idioma={idioma} cifras={cifrasDelMomento} onIr={irACifra} />
    </>
  );
  const previsionEnPantalla = <Prevision t={t} idioma={idioma} carga={prevision} onRacha={irARacha} />;
  const periodoEscrito = textoDeSeleccion(t, seleccion);
  const cierresActivos = cierresEnCurso(directo).length;
  const novedadesPendientes = latentes.size;
  /** Los botones pequeños sobre el mapa: filtros y «Europa ahora». */
  const botonesMapa = (enTelefono: boolean) => (
    <div className="pointer-events-auto relative flex flex-wrap items-start gap-1.5" data-botones-mapa="">
      <BotonFiltros
        t={t}
        cuantos={cuantosFiltros(filtros)}
        periodo={periodoEscrito}
        abierto={enTelefono ? hojaPropia === "filtros" : desplegado === "filtros"}
        onAbrir={() =>
          enTelefono
            ? abrirHoja("filtros")
            : setDesplegado((actual) => (actual === "filtros" ? null : "filtros"))
        }
        onTodo={() => elegirSeleccion(TODO)}
        referencia={enTelefono === movil ? botonFiltros : undefined}
      />
      <BotonAhora
        t={t}
        abierto={enTelefono ? hojaPropia === "ahora" : desplegado === "ahora"}
        onAbrir={() =>
          enTelefono ? abrirHoja("ahora") : setDesplegado((actual) => (actual === "ahora" ? null : "ahora"))
        }
        cierres={cierresActivos}
        novedades={novedadesPendientes}
        referencia={enTelefono === movil ? botonAhora : undefined}
      />
      {!enTelefono && (
        <BotonPrevision
          t={t}
          abierto={desplegado === "prevision"}
          onAbrir={() => setDesplegado((actual) => (actual === "prevision" ? null : "prevision"))}
          referencia={movil ? undefined : botonPrevision}
        />
      )}
      {!enTelefono && desplegado === "filtros" && (
        <Desplegable
          t={t}
          titulo={t.filtros.titulo}
          cerrar={t.filtros.cerrar}
          boton={botonFiltros}
          onCerrar={() => setDesplegado(null)}
        >
          {filtrosDeLaPantalla}
        </Desplegable>
      )}
      {!enTelefono && desplegado === "ahora" && (
        <Desplegable
          t={t}
          titulo={t.ahora.etiqueta}
          cerrar={t.ahora.cerrar}
          boton={botonAhora}
          onCerrar={() => setDesplegado(null)}
        >
          {europaAhora}
        </Desplegable>
      )}
      {!enTelefono && desplegado === "prevision" && (
        <Desplegable
          t={t}
          titulo={t.prevision.etiqueta}
          cerrar={t.prevision.cerrar}
          boton={botonPrevision}
          onCerrar={() => setDesplegado(null)}
        >
          {previsionEnPantalla}
        </Desplegable>
      )}
    </div>
  );
  // «Noche a noche» es una vista (una reproducción), no una capa: en el teléfono va en «Más»,
  // con «En directo», y con su mismo estilo.
  const botonNoches = (grande: boolean) => (
    <button
      type="button"
      className={`control ${grande ? "w-full justify-start text-sm text-texto" : "min-h-7 px-1.5 text-xs"}`}
      aria-pressed={noche !== null}
      onClick={() => {
        // En el teléfono, el menú se cierra para que se vea la reproducción.
        if (grande) setMenu(false);
        if (noche === null) empezarNoches();
        else detenerNoches();
      }}
    >
      {t.guerra.reproducir}
    </button>
  );
  // Lo que aparece bajo los botones del mapa, centrado: la noche de la guerra y los avisos. Va
  // en la misma columna que los botones, debajo de ellos: nunca se montan.
  const hayAvisosArriba = nocheActual !== null || avisoDeDatos !== null || mapaFallido;
  const avisosArriba = hayAvisosArriba && (
    <div className="pointer-events-none flex flex-col items-center gap-2 self-stretch" data-avisos-arriba="">
      {nocheActual !== null && (
        <div role="status" data-noche="" className="flotante pointer-events-auto flex flex-col items-center gap-1 px-4 py-2 text-center">
          <span className="block text-sm">{jornadaEscrita(t, nocheActual.jornada, true)}</span>
          {nocheActual.lanzados === null ? (
            <span className="block text-sm text-secundario">{t.guerra.sinCifra}</span>
          ) : (
            <>
              <span className="cifra block text-xl text-guerra">
                {numero(nocheActual.lanzados, idioma)}
              </span>
              <span className="block text-xs text-secundario">{t.guerra.drones}</span>
              {(nocheActual.shahed !== null || nocheActual.reactivos !== null) && (
                <span className="block text-xs text-secundario" data-mezcla-noche="">
                  {t.guerra.mezcla(
                    nocheActual.shahed === null ? null : numero(nocheActual.shahed, idioma),
                    nocheActual.reactivos === null ? null : numero(nocheActual.reactivos, idioma),
                  )}
                </span>
              )}
            </>
          )}
          <span className="mt-1 flex gap-1">
            <button
              type="button"
              className="control min-h-7 text-xs text-texto"
              onClick={() => {
                if (nochePausada && noche !== null && noche + 1 >= noches.length) setNoche(0);
                setNochePausada(!nochePausada);
              }}
            >
              {nochePausada ? t.guerra.reanudar : t.guerra.pausar}
            </button>
            <button type="button" className="control min-h-7 text-xs text-texto" onClick={detenerNoches}>
              {t.guerra.detener}
            </button>
          </span>
        </div>
      )}
      {(avisoDeDatos !== null || mapaFallido) && (
        <p role="alert" className="flotante pointer-events-auto flex max-w-md items-center gap-2 p-4">
          <Simbolo estado="confirmado" />
          {avisoDeDatos ?? t.avisos.mapaNoDisponible}
        </p>
      )}
    </div>
  );

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-fondo">
      <a
        href="#mapa"
        className="control control-principal sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50"
      >
        {t.saltarAlMapa}
      </a>
      <div id="mapa" tabIndex={-1} className="absolute inset-0 outline-none">
        {mapaPermitido && !mapaFallido && avisoDeDatos === null && recientes !== null && (
          <Suspense fallback={null}>
            <Mapa
              t={t}
              idioma={idioma}
              incidentes={delPeriodo}
              porId={porId}
              episodios={datosResumen?.episodios ?? VACIO}
              capas={capas}
              intensidad={intensidad}
              noche={nocheActual?.regiones ?? null}
              focosUcrania={focosUcrania}
              impactos={impactos}
              gnss={gnssActual?.celdas ?? null}
              presion={presion}
              avisos={avisos}
              corredores={corredoresEnMapa}
              luzRegiones={luzRegiones}
              ciudadesSinLuz={ciudadesSinLuz}
              alumbrado={verAlumbrado ? (alumbrado?.ciudades ?? null) : null}
              elegido={elegido}
              paisResaltado={paisImpreciso}
              regionesElegidas={regionesElegidas}
              novedades={latentes}
              recientes={recientes}
              vuelo={vuelo}
              reserva={reserva}
              onIncidente={abrirIncidenteDesdeMapa}
              onPila={abrirPila}
              onRegion={abrirRegion}
              onImpacto={abrirImpacto}
              onAviso={abrirAvisoDesdeMapa}
              onCelda={abrirCelda}
              onPais={abrirPais}
              onCorredor={abrirCorredor}
              rutas={rutasEnElMapa}
              onRuta={abrirRuta}
              recorrido={recorridoAbierto}
              onCorredores={abrirCorredores}
              corredorElegido={panelLocal?.clase === "corredor" ? panelLocal.clave : null}
              puntosSatelite={puntosSatelite}
              soloSatelite={capas.ucrania && capas.satelite}
              onCiudadLuz={abrirCiudadLuz}
              onAlumbrado={abrirAlumbrado}
              onListo={setApi}
              onFallo={fallarMapa}
              onVacio={tocarFuera}
            />
          </Suspense>
        )}
        <p className="sr-only">{t.mapa.instrucciones}</p>
      </div>

      {verEscritorio && (
        <div className="pointer-events-none relative z-10 flex h-full flex-col tel:hidden">
          <div ref={refArribaEsc} className="pointer-events-auto relative">
            <Cabecera
              t={t}
              centro={
                <>
                  <Marcador t={t} idioma={idioma} cifras={contadores} animar={datosResumen !== null} />
                  {estadoDatos(false)}
                </>
              }
              derecha={
                <>
                  <SelectorDeCapas
                    t={t}
                    capas={capas}
                    onCapas={cambiarCapas}
                    extraGuerra={botonSatelite(false)}
                  />
                  {botonNoches(false)}
                  <button
                    type="button"
                    className="control min-h-7 px-1.5 text-xs"
                    aria-expanded={feedAbierto}
                    onClick={() => setFeedAbierto(!feedAbierto)}
                  >
                    {t.controles.feed}
                  </button>
                  <button
                    type="button"
                    className="control min-h-7 px-1.5 text-xs"
                    aria-haspopup="dialog"
                    onClick={() => setAyuda(true)}
                  >
                    {t.controles.ayuda}
                  </button>
                  <button
                    type="button"
                    className="control min-h-7 px-1.5 text-xs"
                    aria-haspopup="dialog"
                    onClick={() => setMetodologia(true)}
                  >
                    {t.firma.metodologia}
                  </button>
                  <SelectorDeIdioma t={t} idioma={idioma} rutaOtroIdioma={rutaOtroIdioma} />
                </>
              }
            />
          </div>
          <div className="flex min-h-0 flex-1">
            {feedAbierto && (
              <div className="pointer-events-auto w-[22rem] shrink-0 p-3 pr-0">{feed(false)}</div>
            )}
            <div className="relative min-w-0 flex-1">
              <div className="pointer-events-none absolute inset-x-3 top-3 z-20 flex flex-col items-start gap-2">
                {botonesMapa(false)}
                {avisosArriba}
              </div>
              <div ref={refAbajoEsc} className="absolute inset-x-3 bottom-3 flex flex-col gap-2">
                <div className="flex items-end justify-between gap-2">
                  <div className="pointer-events-auto">{leyendas}</div>
                  <div className="pointer-events-auto flex items-end gap-2">
                    <Atribuciones t={t} />
                    <Zoom t={t} onZoom={(paso) => api?.zoom(paso)} />
                  </div>
                </div>
              </div>
            </div>
            {ficha !== null && (
              <div className="pointer-events-auto h-full shrink-0">
                <PanelLateral nombre={ficha.nombre}>{ficha.contenido}</PanelLateral>
              </div>
            )}
          </div>
        </div>
      )}

      {verTelefono && (
        <div className="pointer-events-none relative z-10 flex h-full flex-col esc:hidden">
          <div ref={refArribaTel} className="pointer-events-auto relative">
            <BarraMovil
              t={t}
              estado={estadoDatos(true)}
              menuAbierto={menu}
              onMenu={() => setMenu(true)}
            />
          </div>
          <div className="relative min-h-0 flex-1">
            <div className="pointer-events-none absolute inset-x-2 top-2 z-20 flex flex-col items-start gap-2">
              {!hojaAbierta && botonesMapa(true)}
              {avisosArriba}
            </div>
            {/* Con una hoja abierta, lo de abajo queda tapado: no se pinta. */}
            {!hojaAbierta && (
              <div
                ref={refAbajoTel}
                className="absolute inset-x-0 bottom-0 flex flex-col items-end gap-1 pb-[env(safe-area-inset-bottom)]"
              >
                {/* En el teléfono la leyenda y las atribuciones no caben en una fila: compartiéndola,
                    la fila era más ancha que la pantalla y, alineada a la derecha, la leyenda se
                    salía por la izquierda. Van una encima de otra. */}
                {leyendas !== false && <div className="pointer-events-auto w-full px-2">{leyendas}</div>}
                <div className="flex w-full justify-end px-2">
                  <div className="pointer-events-auto max-w-full">
                    <Atribuciones t={t} />
                  </div>
                </div>
              </div>
            )}
            {movil && ficha !== null && (
              <div className="pointer-events-auto">
                <HojaInferior
                  t={t}
                  nombre={ficha.nombre}
                  altura={altura}
                  onAltura={setAltura}
                  onCerrar={cerrarFicha}
                >
                  {ficha.contenido}
                </HojaInferior>
              </div>
            )}
            {movil && ficha === null && hojaPropia === "filtros" && (
              <div className="pointer-events-auto" data-hoja-propia="">
                <HojaInferior
                  t={t}
                  nombre={t.filtros.titulo}
                  altura={altura}
                  onAltura={setAltura}
                  onCerrar={() => setHojaPropia(null)}
                >
                  <CabeceraFicha
                    t={t}
                    etiqueta={t.filtros.titulo}
                    onCerrar={() => setHojaPropia(null)}
                    cerrar={t.filtros.cerrar}
                  />
                  <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">{filtrosDeLaPantalla}</div>
                </HojaInferior>
              </div>
            )}
            {movil && ficha === null && hojaPropia === "ahora" && (
              <div className="pointer-events-auto" data-hoja-propia="">
                <HojaInferior
                  t={t}
                  nombre={t.ahora.etiqueta}
                  altura={altura}
                  onAltura={setAltura}
                  onCerrar={() => setHojaPropia(null)}
                >
                  <CabeceraFicha
                    t={t}
                    etiqueta={t.ahora.etiqueta}
                    onCerrar={() => setHojaPropia(null)}
                    cerrar={t.ahora.cerrar}
                  />
                  <div role="tablist" aria-label={t.ahora.etiqueta} className="flex gap-1 px-3 pt-2" data-pestanas-ahora="">
                    {(["ahora", "prevision"] as const).map((pestana) => (
                      <button
                        key={pestana}
                        type="button"
                        role="tab"
                        aria-selected={pestanaAhora === pestana}
                        className="control min-h-11 flex-1 rounded-sm border border-linea px-3 text-sm"
                        data-pestana={pestana}
                        onClick={() => setPestanaAhora(pestana)}
                      >
                        {pestana === "ahora" ? t.ahora.etiqueta : t.prevision.etiqueta}
                      </button>
                    ))}
                  </div>
                  <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
                    {pestanaAhora === "ahora" ? europaAhora : previsionEnPantalla}
                  </div>
                </HojaInferior>
              </div>
            )}
            {movil && ficha === null && hojaPropia === "prevision" && (
              <div className="pointer-events-auto" data-hoja-propia="">
                <HojaInferior
                  t={t}
                  nombre={t.prevision.etiqueta}
                  altura={altura}
                  onAltura={setAltura}
                  onCerrar={() => setHojaPropia(null)}
                >
                  <CabeceraFicha
                    t={t}
                    etiqueta={t.prevision.etiqueta}
                    onCerrar={() => setHojaPropia(null)}
                    cerrar={t.prevision.cerrar}
                  />
                  <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">{previsionEnPantalla}</div>
                </HojaInferior>
              </div>
            )}
            {movil && ficha === null && hojaPropia === "directo" && (
              <div className="pointer-events-auto">
                <HojaInferior
                  t={t}
                  nombre={t.feed.titulo}
                  altura={altura}
                  onAltura={setAltura}
                  onCerrar={() => setHojaPropia(null)}
                >
                  {feed(true)}
                </HojaInferior>
              </div>
            )}
          </div>
        </div>
      )}

      {movil && (
        <MenuMovil t={t} abierto={menu} onCerrar={() => setMenu(false)}>
          <SeccionMenu rotulo={t.marcador.etiqueta}>
            <Marcador
              t={t}
              idioma={idioma}
              cifras={contadores}
              animar={false}
              forma="rejilla"
            />
          </SeccionMenu>
          <SeccionMenu rotulo={t.controles.capas}>
            <SelectorDeCapas
              t={t}
              capas={capas}
              onCapas={cambiarCapas}
              grande
              extraGuerra={botonSatelite(true)}
              panelGuerra={
                capas.satelite && puntosSatelite !== null ? (
                  <PanelSatelite
                    t={t}
                    idioma={idioma}
                    puntos={puntosSatelite}
                    abierta={listaSatelite}
                    onAbierta={setListaSatelite}
                    filtro={filtroSatelite}
                    onFiltro={setFiltroSatelite}
                    onElegir={elegirSatelite}
                    acceso
                  />
                ) : null
              }
            />
          </SeccionMenu>
          <SeccionMenu rotulo={t.controles.paneles}>
            <button type="button" className="control w-full justify-start text-sm text-texto" onClick={() => abrirHoja("directo")}>
              {t.controles.feed}
            </button>
            {botonNoches(true)}
            <button
              type="button"
              className="control w-full justify-start text-sm text-texto"
              aria-haspopup="dialog"
              onClick={() => {
                setMenu(false);
                setAyuda(true);
              }}
            >
              {t.controles.ayuda}
            </button>
            <button
              type="button"
              className="control w-full justify-start text-sm text-texto"
              aria-haspopup="dialog"
              onClick={() => {
                setMenu(false);
                setMetodologia(true);
              }}
            >
              {t.firma.metodologia}
            </button>
          </SeccionMenu>
          <SeccionMenu rotulo={t.controles.idioma}>
            <SelectorDeIdioma t={t} idioma={idioma} rutaOtroIdioma={rutaOtroIdioma} grande />
          </SeccionMenu>
        </MenuMovil>
      )}

      <Metodologia
        t={t}
        abierta={metodologia}
        actualizado={actualizado}
        sinUbicacion={metaInicial.sinUbicacion}
        onCerrar={() => setMetodologia(false)}
      />
      <Ayuda t={t} abierta={ayuda} onCerrar={() => setAyuda(false)} />
    </div>
  );
}
