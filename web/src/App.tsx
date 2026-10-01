import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AvisoNovedades } from "./componentes/AvisoNovedades.tsx";
import { Ayuda } from "./componentes/Ayuda.tsx";
import { BarraEstado } from "./componentes/BarraEstado.tsx";
import { BarraMovil, Cabecera } from "./componentes/Cabecera.tsx";
import {
  Atribuciones,
  CAPAS_INICIALES,
  SelectorDeCapas,
  SelectorDeIdioma,
  Zoom,
} from "./componentes/Controles.tsx";
import type { Capas } from "./componentes/Controles.tsx";
import { Feed } from "./componentes/Feed.tsx";
import type { Pestana } from "./componentes/Feed.tsx";
import { FichaAtaque } from "./componentes/FichaAtaque.tsx";
import { FichaIncidente } from "./componentes/FichaIncidente.tsx";
import { FichaRegion } from "./componentes/FichaRegion.tsx";
import { Filtros } from "./componentes/Filtros.tsx";
import { LineaTiempo } from "./componentes/LineaTiempo.tsx";
import type { EstadoReproduccion } from "./componentes/LineaTiempo.tsx";
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
  cargarIncidente,
  cargarResumen,
  cargarResumenUcrania,
} from "./datos/carga.ts";
import type { Carga } from "./datos/carga.ts";
import { PREFIJO_UCRANIA, cifras, esGrave } from "./datos/derivar.ts";
import type {
  Ataque,
  EstadoSistema,
  IncidenteDetalle,
  IncidenteResumen,
  Resumen,
  ResumenUcrania,
} from "./datos/tipos.ts";
import {
  ataquesPorRegion,
  cifrasDeRegion,
  dominioUcrania,
  lanzamientosPorNoche,
  nochesDeGuerra,
} from "./datos/ucrania.ts";
import { accionDe } from "./estado/atajos.ts";
import type { Accion } from "./estado/atajos.ts";
import {
  GRAVES,
  SIN_FILTROS,
  escribirBusqueda,
  filtrar,
  leerFiltros,
  leerPeriodo,
  soloGraves,
} from "./estado/filtros.ts";
import type { Filtros as EstadoFiltros } from "./estado/filtros.ts";
import { almacenLocal, incidentesDe, novedadesDesde, registrarVisita } from "./estado/novedades.ts";
import metaInicial from "./generado/meta.json";
import { fechaDia, numero, textos } from "./i18n/index.ts";
import type { ApiMapa, Encuadre, Reserva } from "./mapa/Mapa.tsx";
import { ZOOM_DE_PAIS } from "./mapa/encuadre.ts";
import { useNavegacion } from "./navegacion.tsx";
import { analizarRuta } from "./rutas.ts";
import { ORIGEN, rutaDeFicha, rutaDeIdioma } from "./sitio.ts";
import type { Idioma } from "./sitio.ts";
import { diaDeInstante, enPeriodo, inicioDeTramoSiguiente } from "./tiempo/dias.ts";
import type { Granularidad, Periodo } from "./tiempo/dias.ts";

const Mapa = lazy(() => import("./mapa/Mapa.tsx"));

/** Cada cuánto se vuelve a calcular la antigüedad de los datos. */
const MS_ENTRE_COMPROBACIONES = 60_000;
/** Cada cuánto se vuelve a pedir estado.json, que la recogida publica cada hora. */
const MS_ENTRE_ESTADOS = 300_000;
/** Ritmo de la reproducción: un tramo de la línea de tiempo en cada paso. */
const MS_POR_PASO = 450;
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
/**
 * Cambios de periodo seguidos (un arrastre, las flechas) cuentan como uno solo en el
 * historial: el botón atrás deshace el gesto entero, no cada paso.
 */
const MS_DE_GESTO = 800;
const GRANULARIDAD_INICIAL: Granularidad = "semana";

type PanelLocal = { clase: "region"; codigo: string } | { clase: "pila"; ids: string[] } | null;
/** Hojas del teléfono que no son una ficha: una sola a la vez. */
type HojaPropia = "tiempo" | "directo" | null;
/** Reproducción de la línea de tiempo en marcha o en pausa, con su periodo. */
interface Reproduccion {
  estado: Exclude<EstadoReproduccion, "parada">;
  periodo: Periodo;
}

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
  const periodoDeDireccion = useMemo(() => leerPeriodo(busqueda), [busqueda]);

  // La primera pintura es igual a la prerenderizada: la ficha de la ruta y todo lo que
  // depende del navegador (hora, anchura, almacenamiento) entran después de montar.
  const [montado, setMontado] = useState(false);
  const [ahora, setAhora] = useState<Date | null>(null);
  const [movil, setMovil] = useState(false);
  // Altos de lo que tapa el mapa arriba (cabecera y filtros) y abajo (línea de tiempo), en
  // cada disposición.
  const [refArribaEsc, altoArribaEsc] = useAlto();
  const [refAbajoEsc, altoAbajoEsc] = useAlto();
  const [refArribaTel, altoArribaTel] = useAlto();
  const [refAbajoTel, altoAbajoTel] = useAlto();
  const [resumen, setResumen] = useState<Carga<Resumen>>(CARGANDO);
  const [ucrania, setUcrania] = useState<Carga<ResumenUcrania>>(CARGANDO);
  const [sistema, setSistema] = useState<EstadoSistema | null>(null);
  const [incidente, setIncidente] = useState<Carga<IncidenteDetalle>>(CARGANDO);
  const [ataque, setAtaque] = useState<Carga<Ataque>>(CARGANDO);
  const [capas, setCapas] = useState<Capas>(CAPAS_INICIALES);
  const [granularidad, setGranularidad] = useState<Granularidad>(GRANULARIDAD_INICIAL);
  const [reproduccion, setReproduccion] = useState<Reproduccion | null>(null);
  const [panelLocal, setPanelLocal] = useState<PanelLocal>(null);
  const [feedAbierto, setFeedAbierto] = useState(false);
  const [pestana, setPestana] = useState<Pestana>("directo");
  const [metodologia, setMetodologia] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  const [lineaAbierta, setLineaAbierta] = useState(false);
  const [noche, setNoche] = useState<number | null>(null);
  const [nochePausada, setNochePausada] = useState(false);
  const [menu, setMenu] = useState(false);
  const [hojaPropia, setHojaPropia] = useState<HojaPropia>(null);
  const [altura, setAltura] = useState<Altura>("media");
  const ultimoCambioDePeriodo = useRef(0);
  const [mapaFallido, setMapaFallido] = useState(false);
  const [mapaPermitido, setMapaPermitido] = useState(false);
  const [api, setApi] = useState<ApiMapa | null>(null);
  const [visitaAnterior, setVisitaAnterior] = useState<string | null>(null);
  const [recorrido, setRecorrido] = useState<number | null>(null);
  const [novedadesDescartadas, setNovedadesDescartadas] = useState(false);

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
      dominio === null
        ? null
        : acotarPeriodo(reproduccion?.periodo ?? periodoDeDireccion, dominio),
    [dominio, reproduccion, periodoDeDireccion],
  );
  const porId = useMemo(
    () => new Map((datosResumen?.incidentes ?? VACIO).map((i) => [i.id, i])),
    [datosResumen],
  );
  const filtrados = useMemo(
    () =>
      datosResumen === null || hoy === null
        ? VACIO
        : filtrar(datosResumen.incidentes, filtros, hoy),
    [datosResumen, filtros, hoy],
  );
  const delPeriodo = useMemo(
    () => (periodo === null ? VACIO : filtrados.filter((i) => enPeriodo(i.dia, periodo))),
    [filtrados, periodo],
  );
  const incidentesPorDia = useMemo(() => {
    const porDia = new Map<number, number>();
    for (const i of filtrados) porDia.set(i.dia, (porDia.get(i.dia) ?? 0) + 1);
    return porDia;
  }, [filtrados]);
  const destellos = useMemo(
    () =>
      filtrados.filter((i) => esGrave(i.estado)).map((i) => ({ dia: i.dia, estado: i.estado })),
    [filtrados],
  );
  const eventos = useMemo(() => {
    const visibles = new Set(filtrados.map((i) => i.id));
    return (datosResumen?.eventos ?? VACIO).filter((evento) => visibles.has(evento.id));
  }, [datosResumen, filtrados]);
  const lanzamientos = useMemo(
    () => (ucraniaActiva === null ? null : lanzamientosPorNoche(ucraniaActiva)),
    [ucraniaActiva],
  );
  const intensidad = useMemo(
    () =>
      ucraniaActiva === null || periodo === null ? null : ataquesPorRegion(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );
  const noches = useMemo(
    () => (ucraniaActiva === null ? VACIO : nochesDeGuerra(ucraniaActiva)),
    [ucraniaActiva],
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

  const contadores = datosResumen === null ? metaInicial : cifras(delPeriodo);

  const cambiarFiltros = useCallback(
    (nuevos: EstadoFiltros) => cambiarBusqueda(escribirBusqueda(nuevos, periodoDeDireccion)),
    [cambiarBusqueda, periodoDeDireccion],
  );

  /**
   * Pone el periodo en la dirección. Cada gesto deja una entrada en el historial, para que el
   * botón atrás lo deshaga; el periodo completo es no tener periodo.
   */
  const ponerPeriodo = useCallback(
    (nuevo: Periodo | null) => {
      const completo =
        nuevo === null ||
        (dominio !== null && nuevo.desde <= dominio.desde && nuevo.hasta >= dominio.hasta);
      const ahoraMs = Date.now();
      const mismoGesto = ahoraMs - ultimoCambioDePeriodo.current < MS_DE_GESTO;
      ultimoCambioDePeriodo.current = ahoraMs;
      cambiarBusqueda(escribirBusqueda(filtros, completo ? null : nuevo), !mismoGesto);
    },
    [cambiarBusqueda, filtros, dominio],
  );

  // Reproducción de la línea de tiempo: el final del periodo avanza un tramo en cada paso. Al
  // llegar al final queda en pausa; detenerla vuelve al periodo de antes de reproducir, que
  // sigue en la dirección.
  const reproduciendo = reproduccion?.estado === "reproduciendo";
  useEffect(() => {
    if (!reproduciendo || dominio === null) return undefined;
    const temporizador = window.setInterval(() => {
      setReproduccion((anterior) => {
        if (anterior === null) return null;
        const actual = acotarPeriodo(anterior.periodo, dominio);
        const hasta = Math.min(
          dominio.hasta,
          inicioDeTramoSiguiente(actual.hasta + 1, granularidad) - 1,
        );
        return {
          estado: hasta >= dominio.hasta ? "pausada" : "reproduciendo",
          periodo: { desde: actual.desde, hasta },
        };
      });
    }, MS_POR_PASO);
    return () => window.clearInterval(temporizador);
  }, [reproduciendo, dominio, granularidad]);

  const reproducir = useCallback(() => {
    if (dominio === null || periodo === null) return;
    setReproduccion((anterior) => {
      if (anterior !== null) return { ...anterior, estado: "reproduciendo" };
      // Empieza por el primer tramo del periodo y lo va ampliando hasta el final de los datos.
      return {
        estado: "reproduciendo",
        periodo: {
          desde: periodo.desde,
          hasta: Math.min(dominio.hasta, inicioDeTramoSiguiente(periodo.desde, granularidad) - 1),
        },
      };
    });
  }, [dominio, periodo, granularidad]);
  const pausar = useCallback(
    () => setReproduccion((anterior) => (anterior === null ? null : { ...anterior, estado: "pausada" })),
    [],
  );
  const detener = useCallback(() => setReproduccion(null), []);
  const alternarReproduccion = useCallback(() => {
    if (reproduciendo) pausar();
    else reproducir();
  }, [reproduciendo, pausar, reproducir]);

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

  const elegirPeriodo = useCallback(
    (nuevo: Periodo) => {
      setReproduccion(null);
      ponerPeriodo(nuevo);
    },
    [ponerPeriodo],
  );
  /** Quita el periodo elegido y para las reproducciones (Escape, doble clic). */
  const quitarSeleccion = useCallback(() => {
    setReproduccion(null);
    detenerNoches();
    if (periodoDeDireccion !== null) ponerPeriodo(null);
  }, [detenerNoches, periodoDeDireccion, ponerPeriodo]);
  const hayQueVerTodo = periodoDeDireccion !== null || reproduccion !== null || noche !== null;

  const fichaActiva = montado ? fichaDeRuta : null;
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

  const encuadre = useMemo<Encuadre | null>(() => {
    if (elegido?.punto) return { lon: elegido.punto.lon, lat: elegido.punto.lat };
    if (centroPais !== null) return { ...centroPais, zoom: ZOOM_DE_PAIS };
    if (fichaActiva?.clase === "ataque") return "ucrania";
    return null;
  }, [elegido, centroPais, fichaActiva]);

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
      if (!codigo.startsWith(PREFIJO_UCRANIA)) return;
      setHojaPropia(null);
      setAltura(alturaInicial());
      setPanelLocal({ clase: "region", codigo });
      if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
    },
    [navegar, idioma],
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
  /** «Ver todo»: el periodo completo, sin reproducciones y con la vista inicial del mapa. */
  const verTodo = useCallback(() => {
    quitarSeleccion();
    api?.vistaInicial();
  }, [quitarSeleccion, api]);

  const irANovedad = useCallback(
    (posicion: number) => {
      const id = incidentesNuevos[posicion];
      if (id === undefined) return;
      setRecorrido(posicion);
      abrirIncidente(id);
    },
    [incidentesNuevos, abrirIncidente],
  );

  // Atajos de teclado.
  const hayFicha = fichaActiva !== null || panelLocal !== null;
  const ejecutar = useCallback(
    (accion: Accion) => {
      switch (accion) {
        case "ayuda":
          setAyuda((abierta) => !abierta);
          return;
        case "cerrar":
          // Primero lo abierto (ficha, hoja, directo); después, la selección de periodo.
          if (hayFicha) cerrarFicha();
          else if (hojaPropia !== null) setHojaPropia(null);
          else if (feedAbierto) setFeedAbierto(false);
          else if (hayQueVerTodo) quitarSeleccion();
          else if (lineaAbierta) setLineaAbierta(false);
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
          cambiarFiltros({ ...filtros, reciente: filtros.reciente === "24h" ? null : "24h" });
          return;
        case "filtro7d":
          cambiarFiltros({ ...filtros, reciente: filtros.reciente === "7d" ? null : "7d" });
          return;
        case "sinFiltros":
          cambiarFiltros(SIN_FILTROS);
          return;
        case "lineaTiempo":
          if (movil) abrirHoja("tiempo");
          else setLineaAbierta((abierta) => !abierta);
          return;
        case "reproducir":
          alternarReproduccion();
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
      hayFicha,
      cerrarFicha,
      hojaPropia,
      feedAbierto,
      hayQueVerTodo,
      quitarSeleccion,
      lineaAbierta,
      cambiarFiltros,
      filtros,
      alternarReproduccion,
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
              {(detalle) => <FichaAtaque t={t} idioma={idioma} ataque={detalle} />}
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
  const filtrosDeLaPantalla = (apilado: boolean) => (
    <Filtros
      t={t}
      idioma={idioma}
      filtros={filtros}
      onFiltros={cambiarFiltros}
      paises={paisesConIncidentes}
      apilado={apilado}
    />
  );
  const lineaDeTiempo = (forma: "franja" | "barra" | "hoja") =>
    dominio !== null &&
    periodo !== null && (
      <LineaTiempo
        t={t}
        idioma={idioma}
        dominio={dominio}
        periodo={periodo}
        onPeriodo={elegirPeriodo}
        granularidad={granularidad}
        onGranularidad={setGranularidad}
        incidentesPorDia={incidentesPorDia}
        lanzamientosPorDia={lanzamientos}
        reproduccion={reproduccion?.estado ?? "parada"}
        onReproducir={reproducir}
        onPausar={pausar}
        onDetener={detener}
        hayQueVerTodo={hayQueVerTodo}
        onVerTodo={verTodo}
        onQuitarSeleccion={quitarSeleccion}
        destellos={destellos}
        abierta={forma === "barra" ? false : lineaAbierta}
        onAbierta={forma === "barra" ? () => abrirHoja("tiempo") : setLineaAbierta}
        forma={forma}
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
  const avisos = (
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
              <span className="cifra block text-xl text-atribuido">
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
          <Simbolo tipo="incursion" estado="atribuido" />
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
              elegido={elegido}
              paisResaltado={paisImpreciso}
              regionesElegidas={regionesElegidas}
              novedades={novedades}
              hoy={hoy}
              encuadre={encuadre}
              reserva={reserva}
              onIncidente={abrirIncidente}
              onPila={abrirPila}
              onRegion={abrirRegion}
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
            <div className="superficie border-b px-3 py-1.5">{filtrosDeLaPantalla(false)}</div>
            {avisos}
          </div>
          <div className="flex min-h-0 flex-1">
            {feedAbierto && (
              <div className="pointer-events-auto w-[22rem] shrink-0 p-3 pr-0">{feed(false)}</div>
            )}
            <div className="relative min-w-0 flex-1">
              <div ref={refAbajoEsc} className="absolute inset-x-3 bottom-3 flex flex-col gap-2">
                <div className="pointer-events-auto flex items-end gap-2 self-end">
                  <Atribuciones t={t} />
                  <Zoom t={t} onZoom={(paso) => api?.zoom(paso)} />
                </div>
                <div className="pointer-events-auto">{lineaDeTiempo("franja")}</div>
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
              onPeriodo={() => abrirHoja("tiempo")}
            />
            {avisos}
          </div>
          <div className="relative min-h-0 flex-1">
            {/* Con una hoja abierta, la barra de abajo queda tapada: no se pinta. */}
            {!hojaAbierta && (
              <div
                ref={refAbajoTel}
                className="absolute inset-x-0 bottom-0 flex flex-col items-end gap-1 pb-[env(safe-area-inset-bottom)]"
              >
                <div className="pointer-events-auto mr-2">
                  <Atribuciones t={t} />
                </div>
                <div className="pointer-events-auto w-full">{lineaDeTiempo("barra")}</div>
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
            {movil && ficha === null && hojaPropia === "tiempo" && (
              <div className="pointer-events-auto">
                <HojaInferior
                  t={t}
                  nombre={t.tiempo.titulo}
                  altura={altura}
                  onAltura={setAltura}
                  onCerrar={() => setHojaPropia(null)}
                >
                  <div className="min-h-0 flex-1 overflow-y-auto">{lineaDeTiempo("hoja")}</div>
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
          <SeccionMenu rotulo={t.filtros.titulo}>
            <div className="rounded-sm border border-linea bg-elevado/40 p-3">
              {filtrosDeLaPantalla(true)}
            </div>
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
