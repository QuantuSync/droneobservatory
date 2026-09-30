import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";

import { BarraEstado } from "./componentes/BarraEstado.tsx";
import { Cabecera } from "./componentes/Cabecera.tsx";
import type { Contadores } from "./componentes/Cabecera.tsx";
import { EnlaceExterno } from "./componentes/EnlaceExterno.tsx";
import { FichaAtaque } from "./componentes/FichaAtaque.tsx";
import { FichaIncidente } from "./componentes/FichaIncidente.tsx";
import { FichaRegion } from "./componentes/FichaRegion.tsx";
import { Leyenda } from "./componentes/Leyenda.tsx";
import { LineaTiempo } from "./componentes/LineaTiempo.tsx";
import { Lista } from "./componentes/Lista.tsx";
import { Metodologia } from "./componentes/Metodologia.tsx";
import { Panel, SegunCarga } from "./componentes/Panel.tsx";
import { CAPAS_INICIALES, SelectorCapas } from "./componentes/SelectorCapas.tsx";
import type { Capas } from "./componentes/SelectorCapas.tsx";
import { Simbolo } from "./componentes/Simbolo.tsx";
import {
  CARGANDO,
  cargarAtaque,
  cargarIncidente,
  cargarResumen,
  cargarResumenUcrania,
} from "./datos/carga.ts";
import type { Carga } from "./datos/carga.ts";
import { PREFIJO_UCRANIA, esConfirmado } from "./datos/derivar.ts";
import type { Ataque, IncidenteDetalle, Resumen, ResumenUcrania } from "./datos/tipos.ts";
import {
  ataquesPorRegion,
  cifrasDeRegion,
  dominioUcrania,
  lanzamientosPorNoche,
} from "./datos/ucrania.ts";
import metaInicial from "./generado/meta.json";
import { fechaDia, textos } from "./i18n/index.ts";
import type { Encuadre } from "./mapa/Mapa.tsx";
import { useNavegacion } from "./navegacion.tsx";
import { analizarRuta } from "./rutas.ts";
import { ORIGEN, rutaDeFicha, rutaDeIdioma } from "./sitio.ts";
import type { Idioma } from "./sitio.ts";
import {
  diaDeInstante,
  enPeriodo,
  inicioDeTramoSiguiente,
} from "./tiempo/dias.ts";
import type { Granularidad, Periodo } from "./tiempo/dias.ts";

const Mapa = lazy(() => import("./mapa/Mapa.tsx"));

/** Cada cuánto se vuelve a calcular la antigüedad de los datos. */
const MS_ENTRE_COMPROBACIONES = 60_000;
/** Ritmo de la reproducción: un tramo de la línea de tiempo en cada paso. */
const MS_POR_PASO = 450;
/** Espera máxima antes de cargar el mapa si el navegador no queda libre antes. */
const MS_ESPERA_MAXIMA_DEL_MAPA = 1500;
/** Anchura por debajo de la cual la ficha pasa a panel inferior. */
const CONSULTA_MOVIL = "(max-width: 767px)";
const GRANULARIDAD_INICIAL: Granularidad = "semana";

type PanelLocal = { clase: "region"; codigo: string } | { clase: "lista" } | null;

const VACIO: readonly never[] = [];

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

export function App() {
  const { ruta: rutaActual, navegar } = useNavegacion();
  const ruta = analizarRuta(rutaActual);
  const idioma: Idioma = ruta.idioma;
  const t = textos(idioma);
  const fichaDeRuta = ruta.ficha;
  const idFicha = fichaDeRuta?.id ?? null;
  const claseFicha = fichaDeRuta?.clase ?? null;

  // La primera pintura es igual a la prerenderizada: la ficha de la ruta y todo lo que
  // depende del navegador (hora, anchura) entran después de montar.
  const [montado, setMontado] = useState(false);
  const [ahora, setAhora] = useState<Date | null>(null);
  const [movil, setMovil] = useState(false);
  const [resumen, setResumen] = useState<Carga<Resumen>>(CARGANDO);
  const [ucrania, setUcrania] = useState<Carga<ResumenUcrania>>(CARGANDO);
  const [incidente, setIncidente] = useState<Carga<IncidenteDetalle>>(CARGANDO);
  const [ataque, setAtaque] = useState<Carga<Ataque>>(CARGANDO);
  const [capas, setCapas] = useState<Capas>(CAPAS_INICIALES);
  const [granularidad, setGranularidad] = useState<Granularidad>(GRANULARIDAD_INICIAL);
  const [periodoElegido, setPeriodoElegido] = useState<Periodo | null>(null);
  const [panelLocal, setPanelLocal] = useState<PanelLocal>(null);
  const [metodologia, setMetodologia] = useState(false);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [mapaFallido, setMapaFallido] = useState(false);
  const [mapaPermitido, setMapaPermitido] = useState(false);

  useEffect(() => {
    setMontado(true);
    setAhora(new Date());
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

  const dominio = useMemo(
    () => (datosResumen === null ? null : dominioDe(datosResumen, ucraniaActiva)),
    [datosResumen, ucraniaActiva],
  );
  const periodo = useMemo(
    () => (dominio === null ? null : acotarPeriodo(periodoElegido, dominio)),
    [dominio, periodoElegido],
  );

  const incidentesDelPeriodo = useMemo(
    () =>
      datosResumen === null || periodo === null
        ? VACIO
        : datosResumen.incidentes.filter((i) => enPeriodo(i.dia, periodo)),
    [datosResumen, periodo],
  );
  const incidentesPorDia = useMemo(() => {
    const porDia = new Map<number, number>();
    for (const i of datosResumen?.incidentes ?? VACIO) {
      porDia.set(i.dia, (porDia.get(i.dia) ?? 0) + 1);
    }
    return porDia;
  }, [datosResumen]);
  const lanzamientos = useMemo(
    () => (ucraniaActiva === null ? null : lanzamientosPorNoche(ucraniaActiva)),
    [ucraniaActiva],
  );
  const intensidad = useMemo(
    () =>
      ucraniaActiva === null || periodo === null ? null : ataquesPorRegion(ucraniaActiva, periodo),
    [ucraniaActiva, periodo],
  );

  const contadores: Contadores =
    datosResumen === null
      ? metaInicial
      : {
          incidentes: incidentesDelPeriodo.length,
          confirmados: incidentesDelPeriodo.filter((i) => esConfirmado(i.estado)).length,
          paises: new Set(incidentesDelPeriodo.map((i) => i.pais)).size,
        };

  // Reproducción: el final del periodo avanza un tramo en cada paso hasta el último día.
  useEffect(() => {
    if (!reproduciendo || dominio === null) return undefined;
    const temporizador = window.setInterval(() => {
      setPeriodoElegido((anterior) => {
        const actual = acotarPeriodo(anterior, dominio);
        const hasta = Math.min(
          dominio.hasta,
          inicioDeTramoSiguiente(actual.hasta + 1, granularidad) - 1,
        );
        return { desde: actual.desde, hasta };
      });
    }, MS_POR_PASO);
    return () => window.clearInterval(temporizador);
  }, [reproduciendo, dominio, granularidad]);

  useEffect(() => {
    if (reproduciendo && dominio !== null && periodo !== null && periodo.hasta >= dominio.hasta) {
      setReproduciendo(false);
    }
  }, [reproduciendo, dominio, periodo]);

  function alternarReproduccion() {
    if (reproduciendo || dominio === null || periodo === null) {
      setReproduciendo(false);
      return;
    }
    // Si el periodo ya llega al final, la reproducción vuelve a empezar desde su inicio.
    if (periodo.hasta >= dominio.hasta) {
      setPeriodoElegido({
        desde: periodo.desde,
        hasta: Math.min(dominio.hasta, inicioDeTramoSiguiente(periodo.desde, granularidad) - 1),
      });
    }
    setReproduciendo(true);
  }

  const elegirPeriodo = useCallback((nuevo: Periodo) => {
    setReproduciendo(false);
    setPeriodoElegido(nuevo);
  }, []);

  const fichaActiva = montado ? fichaDeRuta : null;
  const elegido = useMemo(
    () =>
      fichaActiva?.clase === "incidente"
        ? (datosResumen?.incidentes.find((i) => i.id === fichaActiva.id) ?? null)
        : null,
    [fichaActiva, datosResumen],
  );
  const encuadre = useMemo<Encuadre | null>(() => {
    if (elegido !== null) return { lon: elegido.lon, lat: elegido.lat };
    if (fichaActiva?.clase === "ataque") return "ucrania";
    return null;
  }, [elegido, fichaActiva]);

  const regionesDelAtaque = useMemo(() => {
    const actual = datos(ataque);
    return fichaActiva?.clase === "ataque" && actual !== null && actual.id === fichaActiva.id
      ? (actual.regiones ?? []).map((r) => r.region)
      : VACIO;
  }, [ataque, fichaActiva]);
  const regionLocal = fichaActiva === null && panelLocal?.clase === "region" ? panelLocal.codigo : null;
  const regionesElegidas = useMemo(
    () => (regionLocal === null ? regionesDelAtaque : [regionLocal]),
    [regionLocal, regionesDelAtaque],
  );

  const abrirIncidente = useCallback(
    (id: string) => {
      setPanelLocal(null);
      navegar(rutaDeFicha(id, idioma));
    },
    [navegar, idioma],
  );
  const abrirRegion = useCallback(
    (codigo: string) => {
      if (!codigo.startsWith(PREFIJO_UCRANIA)) return;
      setPanelLocal({ clase: "region", codigo });
      if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
    },
    [navegar, idioma],
  );
  const cerrarPanel = useCallback(() => {
    setPanelLocal(null);
    if (analizarRuta(window.location.pathname).ficha !== null) navegar(rutaDeIdioma(idioma));
  }, [navegar, idioma]);
  const fallarMapa = useCallback(() => setMapaFallido(true), []);

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

  const actualizado = datosResumen?.actualizado ?? (resumen.estado === "cargando" ? metaInicial.actualizado : null);
  const avisoDeDatos =
    resumen.estado === "no_valido" || (capas.ucrania && ucrania.estado === "no_valido")
      ? t.avisos.datosNoValidos
      : resumen.estado === "no_disponible" ||
          resumen.estado === "no_encontrado" ||
          (capas.ucrania && (ucrania.estado === "no_disponible" || ucrania.estado === "no_encontrado"))
        ? t.avisos.datosNoDisponibles
        : null;
  const textoPeriodo =
    periodo === null ? "" : t.tiempo.periodo(fechaDia(periodo.desde), fechaDia(periodo.hasta));
  const rutaOtroIdioma = (otro: Idioma) =>
    fichaDeRuta === null ? rutaDeIdioma(otro) : rutaDeFicha(fichaDeRuta.id, otro);

  let panel = null;
  if (fichaActiva?.clase === "incidente") {
    panel = (
      <Panel
        t={t}
        nombre={`${t.ficha.titulo} ${fichaActiva.id}`}
        etiqueta={t.ficha.titulo}
        enlace={ORIGEN + rutaDeFicha(fichaActiva.id, idioma)}
        onCerrar={cerrarPanel}
      >
        <SegunCarga t={t} carga={incidente}>
          {(detalle) => <FichaIncidente t={t} idioma={idioma} incidente={detalle} />}
        </SegunCarga>
      </Panel>
    );
  } else if (fichaActiva?.clase === "ataque") {
    panel = (
      <Panel
        t={t}
        nombre={`${t.ataque.etiqueta} ${fichaActiva.id}`}
        etiqueta={t.ataque.etiqueta}
        enlace={ORIGEN + rutaDeFicha(fichaActiva.id, idioma)}
        onCerrar={cerrarPanel}
      >
        <SegunCarga t={t} carga={ataque}>
          {(detalle) => <FichaAtaque t={t} idioma={idioma} ataque={detalle} />}
        </SegunCarga>
      </Panel>
    );
  } else if (panelLocal?.clase === "region" && datosUcrania !== null && periodo !== null) {
    panel = (
      <Panel
        t={t}
        nombre={`${t.region.etiqueta} ${panelLocal.codigo}`}
        etiqueta={t.region.etiqueta}
        onCerrar={cerrarPanel}
      >
        <FichaRegion
          key={panelLocal.codigo}
          t={t}
          idioma={idioma}
          codigo={panelLocal.codigo}
          cifras={cifrasDeRegion(datosUcrania, panelLocal.codigo, periodo)}
          periodo={textoPeriodo}
        />
      </Panel>
    );
  } else if (panelLocal?.clase === "lista") {
    panel = (
      <Panel t={t} nombre={t.lista.titulo} etiqueta={t.lista.titulo} onCerrar={cerrarPanel}>
        <Lista
          t={t}
          idioma={idioma}
          incidentes={incidentesDelPeriodo}
          regiones={ucraniaActiva?.regiones ?? VACIO}
          onRegion={abrirRegion}
        />
      </Panel>
    );
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <a
        href="#mapa"
        className="boton boton-solido sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50"
      >
        {t.saltarAlMapa}
      </a>
      <Cabecera
        idioma={idioma}
        t={t}
        contadores={contadores}
        rutaOtroIdioma={rutaOtroIdioma(idioma === "es" ? "en" : "es")}
        onMetodologia={() => setMetodologia(true)}
      />
      <BarraEstado t={t} actualizado={actualizado} ahora={ahora} />
      <main className="relative flex min-h-0 flex-1">
        <div id="mapa" tabIndex={-1} className="relative min-w-0 flex-1 bg-fondo outline-none">
          {mapaPermitido && !mapaFallido && avisoDeDatos === null && (
            <Suspense fallback={null}>
              <Mapa
                t={t}
                idioma={idioma}
                incidentes={incidentesDelPeriodo}
                episodios={datosResumen?.episodios ?? VACIO}
                capas={capas}
                intensidad={intensidad}
                elegido={elegido}
                regionesElegidas={regionesElegidas}
                encuadre={encuadre}
                panelInferior={movil && panel !== null}
                onIncidente={abrirIncidente}
                onRegion={abrirRegion}
                onFallo={fallarMapa}
              />
            </Suspense>
          )}
          <p className="sr-only">{t.mapa.instrucciones}</p>
          {(avisoDeDatos !== null || mapaFallido) && (
            <p
              role="alert"
              className="panel absolute left-1/2 top-1/3 z-10 w-[min(90%,28rem)] -translate-x-1/2 border-atribuido p-4"
            >
              <span className="etiqueta mb-1 flex items-center gap-2 text-texto">
                <Simbolo tipo="incursion" estado="atribuido" />
                {avisoDeDatos ?? t.avisos.mapaNoDisponible}
              </span>
            </p>
          )}
          <div className="absolute left-3 top-3 z-10">
            <SelectorCapas
              t={t}
              capas={capas}
              onCambio={setCapas}
              listaAbierta={fichaActiva === null && panelLocal?.clase === "lista"}
              onLista={() => {
                if (fichaActiva === null && panelLocal?.clase === "lista") {
                  setPanelLocal(null);
                } else {
                  setPanelLocal({ clase: "lista" });
                  if (fichaActiva !== null) navegar(rutaDeIdioma(idioma));
                }
              }}
            />
          </div>
          <div className="absolute bottom-7 left-3 z-10 hidden sm:block">
            <Leyenda t={t} capas={capas} />
          </div>
          <p
            aria-label={t.mapa.atribucion}
            className="absolute bottom-0 right-0 z-10 bg-fondo/80 px-2 py-0.5 text-[0.6875rem] text-secundario"
          >
            ©{" "}
            <EnlaceExterno
              enlace="https://www.openstreetmap.org/copyright"
              aviso={t.ficha.enlaceExterno}
              avisoNoValido={t.ficha.enlaceNoValido}
            >
              OpenStreetMap
            </EnlaceExterno>{" "}
            ·{" "}
            <EnlaceExterno
              enlace="https://protomaps.com/"
              aviso={t.ficha.enlaceExterno}
              avisoNoValido={t.ficha.enlaceNoValido}
            >
              Protomaps
            </EnlaceExterno>{" "}
            ·{" "}
            <EnlaceExterno
              enlace="https://www.naturalearthdata.com/"
              aviso={t.ficha.enlaceExterno}
              avisoNoValido={t.ficha.enlaceNoValido}
            >
              Natural Earth
            </EnlaceExterno>
          </p>
        </div>
        {panel}
      </main>
      <div className="min-h-[10.3125rem] md:min-h-[8.0625rem]">
        {dominio !== null && periodo !== null && (
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
            reproduciendo={reproduciendo}
            onReproducir={alternarReproduccion}
          />
        )}
      </div>
      <Metodologia
        t={t}
        abierta={metodologia}
        actualizado={actualizado}
        onCerrar={() => setMetodologia(false)}
      />
    </div>
  );
}
