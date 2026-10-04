import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AvisoNovedades } from "./componentes/AvisoNovedades.tsx";
import { Ayuda } from "./componentes/Ayuda.tsx";
import { BarraEstado } from "./componentes/BarraEstado.tsx";
import { BotonAhora, BotonFiltros, Desplegable } from "./componentes/BotonesMapa.tsx";
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
import { FichaCorredor, FichaLuz } from "./componentes/GuerraSatelite.tsx";
import { Filtros, textoDeSeleccion } from "./componentes/Filtros.tsx";
import { LeyendaGnss, LeyendaPresion } from "./componentes/Leyendas.tsx";
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
} from "./datos/carga.ts";
import type { Carga } from "./datos/carga.ts";
import { cifrasAhora, ultimaNoche } from "./datos/ahora.ts";
import { cargarDirecto, cierresEnCurso, ordenarAvisos } from "./datos/directo.ts";
import type { Directo } from "./datos/directo.ts";
import { agregar, cargarFicheroGnss, cargarIndiceGnss, ficherosDelPeriodo, zonasAltas } from "./datos/gnss.ts";
import type { Agregado, FicheroGnss, IndiceGnss } from "./datos/gnss.ts";
import { cifrasDePais, presionPorPais } from "./datos/presion.ts";
import { cifras } from "./datos/derivar.ts";
import {
  OBJETO_FOCOS_VIVOS,
  ciudadesSinLuz as ciudadesSinLuzDe,
  corredoresDelPeriodo,
  lucesDelPeriodo,
  perdidaPorRegion,
} from "./datos/guerraSatelite.ts";
import type { FocosVivos } from "./datos/guerraSatelite.ts";
import { validarFocosVivos } from "./datos/validar.ts";
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
import { fechaDia, numero, textos } from "./i18n/index.ts";
import type { ApiMapa, Encuadre, Reserva } from "./mapa/Mapa.tsx";
import { ZOOM_DE_PAIS } from "./mapa/encuadre.ts";
import { useNavegacion } from "./navegacion.tsx";
import { analizarRuta } from "./rutas.ts";
import { ORIGEN, rutaDeFicha, rutaDeIdioma } from "./sitio.ts";
import type { Idioma } from "./sitio.ts";
import { diaDeInstante, enPeriodo } from "./tiempo/dias.ts";
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
  | { clase: "luz"; clave: string }
  | null;

/** Cada cuánto se vuelven a pedir los focos de calor de 24 horas (el fichero cambia cada hora). */
const MS_FOCOS_VIVOS = 10 * 60 * 1000;

/** Regiones que se pueden abrir: las de Ucrania (con lo ocupado) y las de Rusia. */
const REGION_DE_LA_CAPA = /^(UA|RU)-[A-Z0-9]{1,3}$/;
/** Hojas del teléfono que no son una ficha: una sola a la vez. */
type HojaPropia = "filtros" | "ahora" | "directo" | null;
/** Desplegables de los botones sobre el mapa, en el escritorio: uno a la vez. */
type Desplegado = "filtros" | "ahora" | null;

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
  return { desde, hasta };
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
  // Focos de calor de las últimas 24 horas: del almacén público, mientras se ven.
  const [focosVivos, setFocosVivos] = useState<FocosVivos | null>(null);
  const verFocosVivos = capas.ucrania && capas.focosVivos;
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
  const [feedAbierto, setFeedAbierto] = useState(false);
  const [pestana, setPestana] = useState<Pestana>("directo");
  const [metodologia, setMetodologia] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  const [desplegado, setDesplegado] = useState<Desplegado>(null);
  const botonFiltros = useRef<HTMLButtonElement>(null);
  const botonAhora = useRef<HTMLButtonElement>(null);
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

  const dominio = useMemo(
    () => (datosResumen === null ? null : dominioDe(datosResumen, ucraniaActiva)),
    [datosResumen, ucraniaActiva],
  );
  const periodo = useMemo(
    () =>
      dominio === null || hoy === null
        ? null
        : acotarPeriodo(periodoDeSeleccion(seleccion, hoy), dominio),
    [dominio, hoy, seleccion],
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
    () => (periodo === null ? VACIO : filtrados.filter((i) => enPeriodo(i.dia, periodo))),
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

  const eventos = useMemo(() => {
    const visibles = new Set(filtrados.map((i) => i.id));
    return (datosResumen?.eventos ?? VACIO).filter((evento) => visibles.has(evento.id));
  }, [datosResumen, filtrados]);
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
  const noches = useMemo(
    () => (ucraniaActiva === null ? VACIO : nochesDeGuerra(ucraniaActiva)),
    [ucraniaActiva],
  );
  // Guerra por satélite: corredores y pérdida de luz del periodo.
  const corredores = useMemo(
    () =>
      ucraniaActiva === null || periodo === null
        ? null
        : corredoresDelPeriodo(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );
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
  const nocheActual = noche === null ? null : (noches[noche] ?? null);

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

  const cambiarFiltros = useCallback(
    (nuevos: EstadoFiltros) => cambiarBusqueda(escribirSeleccion(nuevos, seleccion)),
    [cambiarBusqueda, seleccion],
  );
  /**
   * Pone el periodo en la dirección (el de por defecto, todo, es no tener periodo). Cada cambio
   * deja una entrada en el historial: el botón atrás lo deshace.
   */
  const elegirSeleccion = useCallback(
    (nueva: SeleccionPeriodo) => cambiarBusqueda(escribirSeleccion(filtros, nueva), true),
    [cambiarBusqueda, filtros],
  );
  const quitarFiltros = useCallback(
    () => cambiarBusqueda(escribirSeleccion(SIN_FILTROS, TODO)),
    [cambiarBusqueda],
  );

  // Reproducción de la guerra noche a noche: se puede pausar, reanudar y detener.
  useEffect(() => {
    if (noche === null || nochePausada) return undefined;
    const temporizador = window.setTimeout(() => {
      setNoche((actual) => (actual === null || actual + 1 >= noches.length ? null : actual + 1));
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
  const encuadre = useMemo<Encuadre | null>(() => {
    if (elegido?.punto) return { lon: elegido.punto.lon, lat: elegido.punto.lat };
    if (avisoAbierto !== null) return { lon: avisoAbierto.lon, lat: avisoAbierto.lat, zoom: ZOOM_DE_AVISO };
    if (centroPais !== null) return { ...centroPais, zoom: ZOOM_DE_PAIS };
    if (fichaActiva?.clase === "ataque") return "ucrania";
    return null;
    // El vuelo depende del aviso abierto, no de que directo.json se renueve cada minuto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elegido, centroPais, fichaActiva, avisoAbierto?.id]);

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
  const abrirCelda = useCallback((h3: string) => abrirLocal({ clase: "celda", h3 }), [abrirLocal]);
  const abrirPais = useCallback((iso: string) => abrirLocal({ clase: "pais", iso }), [abrirLocal]);
  const abrirCorredor = useCallback(
    (clave: string) => abrirLocal({ clase: "corredor", clave }),
    [abrirLocal],
  );
  const abrirCiudadLuz = useCallback(
    (clave: string) => abrirLocal({ clase: "luz", clave }),
    [abrirLocal],
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
    () => cifrasAhora({ resumen: datosResumen, ucrania: datosUcrania, directo, gnssHoy }),
    [datosResumen, datosUcrania, directo, gnssHoy],
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
          const noche = datosUcrania === null ? null : ultimaNoche(datosUcrania);
          setCapas((c) => ({ ...c, ucrania: true }));
          if (noche !== null) {
            elegirSeleccion({ clase: "entre", periodo: { desde: noche.dia, hasta: noche.dia } });
          }
          api?.volar("ucrania");
          return;
        }
        case "focos":
          setCapas((c) => ({ ...c, incidentes: true, ucrania: true }));
          elegirSeleccion({ clase: "reciente", reciente: "7d" });
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
    [directo, abrirAviso, api, elegirSeleccion, datosUcrania, cifrasDelMomento],
  );

  const irANovedad = useCallback(
    (posicion: number) => {
      const id = incidentesNuevos[posicion];
      if (id === undefined) return;
      setNovedadesVistas(true);
      setRecorrido(posicion);
      abrirIncidente(id);
    },
    [incidentesNuevos, abrirIncidente],
  );

  // En el teléfono, las hojas de los filtros y de «Europa ahora» se cierran tocando fuera
  // (un toque, no un arrastre: se puede mover el mapa con ellas abiertas).
  useEffect(() => {
    if (!movil || (hojaPropia !== "filtros" && hojaPropia !== "ahora")) return;
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
          setCapas((c) => ({ ...c, ucrania: !c.ucrania }));
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
          <SelectorPila t={t} idioma={idioma} incidentes={pila} />
        </>
      ),
    };
  }

  const ultimoFoco =
    verFocosVivos && focosVivos !== null ? (
      <p
        className="flotante whitespace-nowrap px-2 py-0.5 text-[0.6875rem] text-secundario tel:text-[0.625rem]"
        data-focos-vivos=""
        role="status"
      >
        {focosVivos.ultimo_foco === null
          ? t.satelite.focosVacio
          : t.satelite.focosUltimo(focosVivos.ultimo_foco.slice(11, 16))}
      </p>
    ) : null;

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
  const leyendas = (capas.gnss || capas.presion) && (
    <div className="flex flex-col items-start gap-1.5" data-leyendas="">
      {capas.presion && <LeyendaPresion t={t} />}
      {capas.gnss && <LeyendaGnss t={t} estado={estadoGnss} />}
    </div>
  );
  const europaAhora = <EuropaAhora t={t} idioma={idioma} cifras={cifrasDelMomento} onIr={irACifra} />;
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
    </div>
  );
  const botonNoches = (grande: boolean) => (
    <button
      type="button"
      className={`control text-xs ${grande ? "w-full justify-start" : "min-h-7 px-1.5"}`}
      aria-pressed={noche !== null}
      onClick={noche === null ? empezarNoches : detenerNoches}
    >
      {t.guerra.reproducir}
    </button>
  );
  // Lo que aparece bajo la cabecera, centrado: las novedades, la noche de la guerra y los avisos.
  const avisosArriba = (
    <div className="pointer-events-none absolute inset-x-3 top-full z-10 mt-2 flex flex-col items-center gap-2">
      {!novedadesDescartadas && incidentesNuevos.length > 0 && (
        <div className="flotante pointer-events-auto px-3 py-1.5">
          <AvisoNovedades
            t={t}
            incidentes={incidentesNuevos}
            posicion={recorrido}
            onIr={irANovedad}
            onDescartar={() => setNovedadesDescartadas(true)}
          />
        </div>
      )}
      {nocheActual !== null && (
        <div role="status" className="flotante pointer-events-auto flex flex-col items-center gap-1 px-4 py-2 text-center">
          <span className="block text-sm">{t.guerra.noche(fechaDia(nocheActual.dia))}</span>
          {nocheActual.lanzados === null ? (
            <span className="block text-sm text-secundario">{t.guerra.sinCifra}</span>
          ) : (
            <>
              <span className="cifra block text-xl text-guerra">
                {numero(nocheActual.lanzados, idioma)}
              </span>
              <span className="block text-xs text-secundario">{t.guerra.drones}</span>
            </>
          )}
          <span className="mt-1 flex gap-1">
            <button
              type="button"
              className="control min-h-7 text-xs text-texto"
              onClick={() => setNochePausada(!nochePausada)}
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
        {mapaPermitido && !mapaFallido && avisoDeDatos === null && hoy !== null && (
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
              corredores={corredores}
              luzRegiones={luzRegiones}
              ciudadesSinLuz={ciudadesSinLuz}
              focosVivos={focosVivos?.focos ?? null}
              elegido={elegido}
              paisResaltado={paisImpreciso}
              regionesElegidas={regionesElegidas}
              novedades={latentes}
              hoy={hoy}
              encuadre={encuadre}
              reserva={reserva}
              onIncidente={abrirIncidente}
              onPila={abrirPila}
              onRegion={abrirRegion}
              onImpacto={abrirImpacto}
              onAviso={abrirAviso}
              onCelda={abrirCelda}
              onPais={abrirPais}
              onCorredor={abrirCorredor}
              onCiudadLuz={abrirCiudadLuz}
              onListo={setApi}
              onFallo={fallarMapa}
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
                  <SelectorDeCapas t={t} capas={capas} onCapas={setCapas} />
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
            {avisosArriba}
          </div>
          <div className="flex min-h-0 flex-1">
            {feedAbierto && (
              <div className="pointer-events-auto w-[22rem] shrink-0 p-3 pr-0">{feed(false)}</div>
            )}
            <div className="relative min-w-0 flex-1">
              <div className="absolute left-3 top-3 z-20">{botonesMapa(false)}</div>
              <div ref={refAbajoEsc} className="absolute inset-x-3 bottom-3 flex flex-col gap-2">
                <div className="flex items-end justify-between gap-2">
                  <div className="pointer-events-auto">{leyendas}</div>
                  <div className="pointer-events-auto flex items-end gap-2">
                    {ultimoFoco}
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
            {avisosArriba}
          </div>
          <div className="relative min-h-0 flex-1">
            {!hojaAbierta && <div className="absolute left-2 top-2 z-20">{botonesMapa(true)}</div>}
            {/* Con una hoja abierta, lo de abajo queda tapado: no se pinta. */}
            {!hojaAbierta && (
              <div
                ref={refAbajoTel}
                className="absolute inset-x-0 bottom-0 flex flex-col items-end gap-1 pb-[env(safe-area-inset-bottom)]"
              >
                {ultimoFoco !== null && (
                  <div className="pointer-events-auto mr-2 self-end">{ultimoFoco}</div>
                )}
                <div className="flex w-full items-end justify-between gap-2 px-2">
                  <div className="pointer-events-auto">{leyendas}</div>
                  <div className="pointer-events-auto">
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
                  <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">{europaAhora}</div>
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
            <SelectorDeCapas t={t} capas={capas} onCapas={setCapas} grande />
            {botonNoches(true)}
          </SeccionMenu>
          <SeccionMenu rotulo={t.controles.paneles}>
            <button type="button" className="control w-full justify-start text-sm text-texto" onClick={() => abrirHoja("directo")}>
              {t.controles.feed}
            </button>
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
