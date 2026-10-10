import { rutasEn } from "./rutas.ts";
import { tipoDronEn } from "./tipoDron.ts";
import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, REPOSITORIO, citaRecomendada } from "../sitio.ts";
import { REGIONES_RUSIA_EN } from "./regionesRusia.ts";
import type { FechaEscrita, Textos } from "./tipos.ts";
import { UMBRALES_DIRECTO } from "./umbrales.ts";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

function diaMesAnio(f: FechaEscrita): string {
  return `${f.dia} ${MONTHS[f.mes]} ${f.anio}`;
}

export const en: Textos = {
  tipoDron: tipoDronEn,
  rutas: rutasEn,
  descripcion:
    "Open map and record of drone incidents in Europe: overflights, incursions and airport " +
    "disruptions, with their sources, status and level of confirmation.",
  saltarAlMapa: "Skip to the map",
  marcador: {
    etiqueta: "Figures for the selected period",
    incidentes: "incidents",
    confirmados: "confirmed",
    atribuidos: "attributed",
    paises: "countries",
  },
  firma: { metodologia: "Methodology and open data", atribuciones: "Map attributions" },
  cabecera: { etiqueta: "Header", menu: "Menu", cerrarMenu: "Close the menu" },
  hoja: {
    altura: (altura) => `Sheet ${altura}: tap or drag to change its height`,
    alturas: { asomada: "peeking", media: "at half height", completa: "full screen" },
  },
  controles: {
    capas: "Layers",
    incidentes: "Incidents",
    ucrania: "Ukraine",
    densidad: "Density",
    presion: "Pressure",
    gnss: "GPS",
    feed: "Live",
    ayuda: "Help",
    cambiarIdioma: "Versión en español",
    idioma: "Language",
    zoom: "Zoom",
    paneles: "More",
    acercar: "Zoom in",
    alejar: "Zoom out",
  },
  estadoDatos: {
    actualizado: "Updated",
    etiqueta: {
      al_dia: "data up to date",
      con_retraso: "data delayed",
      desactualizado: "data out of date",
    },
    sinDatos: "No data",
    detalle: "Collection status",
    datosPublicados: "Data published",
    ultimaRecogida: "Last collection",
    resultadoRotulo: "Result",
    siguienteRecogida: "Next collection",
    fuentes: "Sources",
    resultado: { correcta: "successful", con_avisos: "with warnings", fallida: "failed" },
    fuente: {
      fuerza_aerea_ua: "Ukrainian Air Force",
      mindef_ru: "Russian Ministry of Defence",
      gdelt: "News (GDELT)",
      oficiales: "Official statements",
      extractor: "Automatic extraction",
      firms: "Thermal hotspots (NASA FIRMS)",
      airprox: "Encounters with aircraft (UK Airprox Board)",
      parlamentos: "Parliamentary answers",
      investigaciones: "Investigation reports and court rulings",
      estadisticas_oficiales: "Official statistics",
      paginas_js: "Official statements (JavaScript sites)",
      ova_ua: "Ukrainian regional administrations",
      estado_mayor_ua: "Ukrainian General Staff",
      gobernadores_ru: "Russian governors",
      rosaviatsia: "Rosaviatsia",
      trafico_aereo: "Air traffic (adsb.lol)",
      condiciones: "Weather (Open-Meteo, METAR)",
    },
    estadoFuente: { leida: "read", con_aviso: "with warning", no_leida: "not read" },
    directo: "Live detection",
    estadoDirecto: { en_marcha: "running", con_respaldo: "on the backup source", parado: "stopped" },
    ultimoCiclo: "last good cycle",
    ultimoDato: "latest data",
    sinUltimoDato: "no data yet",
    nuncaCorrecta: "No successful collection",
    siguienteEn: (minutos) => (minutos <= 0 ? "running now" : `in ${minutos} min`),
  },
  avisos: {
    cargando: "Loading data…",
    datosNoValidos: "The data could not be read.",
    datosNoDisponibles: "The data could not be loaded.",
    fichaNoEncontrada: "There is no record with this identifier.",
    fichaNoDisponible: "This record could not be loaded.",
    mapaNoDisponible:
      "The map cannot be drawn in this browser. The incident list is still available.",
    sinRespuesta: "It was requested several times without an answer. Check your connection and press “Retry”.",
    webNueva: "The site has been updated since you opened this page: press “Retry” to load the new version.",
    reintentar: "Retry",
  },
  filtros: {
    titulo: "Filters",
    graves: "Only confirmed and attributed",
    ultimas24h: "Last 24 hours",
    ultimos7d: "Last 7 days",
    periodos: {
      todo: "All",
      "24h": "Last 24 hours",
      "7d": "Last 7 days",
      "30d": "Last 30 days",
      "1a": "Last year",
      entre: "Between dates",
    },
    desde: "From",
    hasta: "To",
    entreFechas: (desde, hasta) => `${desde} – ${hasta}`,
    abrir: "Open the filters",
    cerrar: "Close the filters",
    volverATodo: (periodo) => `Remove the period “${periodo}” and show everything`,
    tipo: "Type",
    pais: "Country",
    todosLosPaises: "All countries",
    estado: "Status",
    quitar: "Clear filters",
    aplicar: "Apply",
    sinResultados: "No results with these filters",
    nadaALaVista: "Nothing to show: turn on a layer",
    recientes: "Period",
    activos: (n) => `${n} active`,
    zona: "Where",
    zonas: { todas: "All", frontera: "Border", interior: "Interior" },
  },
  feed: {
    titulo: "Live",
    enDirecto: "Updates",
    lista: "List",
    abrir: "Open the live panel",
    cerrar: "Close the panel",
    nuevo: "New incident",
    nuevoYa: (estado) => `New, already ${estado.toLowerCase()}`,
    paso: (estado) => `Now ${estado.toLowerCase()}`,
    vacio: "Nothing to show with these filters.",
    registrado: (hace) => `registered ${hace}`,
    ocurrio: (dia) => `happened on ${dia}`,
  },
  relativo: (minutos, fecha) => {
    if (minutos < 1) return "just now";
    if (minutos < 60) return `${minutos} min ago`;
    const horas = Math.floor(minutos / 60);
    if (horas < 24) return `${horas} h ago`;
    const dias = Math.floor(horas / 24);
    return dias < 30 ? `${dias} ${dias === 1 ? "day" : "days"} ago` : `on ${fecha}`;
  },
  ahora: {
    etiqueta: "Europe now",
    cierres: "airport closures in progress",
    incidentes: "incidents in 7 days",
    drones: "drones launched last night",
    dronesDia: "drones launched in the latest daytime report",
    dronesParte: "drones launched",
    ultimoParte: (cuando) => `latest report: ${cuando}`,
    focos: "confirmed thermal hotspots in 7 days",
    gnss: "GPS interference zones today",
    sinDato: "no figure",
    ir: (que) => `Show on the map: ${que}`,
    abrir: "Open “Europe now”",
    cerrar: "Close “Europe now”",
    avisoCierres: (n) => (n === 1 ? "1 closure in progress" : `${n} closures in progress`),
    avisoNovedades: (n) => (n === 1 ? "1 update since your last visit" : `${n} updates since your last visit`),
  },
  desplegable: {
    escape: "Press Escape to close.",
  },
  capaUcrania: {
    regionesALaVista: (n) =>
      n === 1 ? "1 region with attacks in view (Ukraine layer)" : `${n} regions with attacks in view (Ukraine layer)`,
    region: (nombre, ataques) => `${nombre} · ${ataques} ${ataques === "1" ? "attack" : "attacks"} in the period`,
    impactosALaVista: (mostrados, total) =>
      mostrados === total
        ? `${total} ${total === 1 ? "place hit" : "places hit"} in view, most recent first`
        : `The ${mostrados} most recent places hit of the ${total} in view: zoom in or use the layer list to see others`,
    impacto: (region, fecha, parte, foco) =>
      `Place hit · ${region} · ${fecha}${parte ? " · claim by a party" : ""}${foco ? " · thermal hotspot" : ""}`,
    celdasALaVista: (mostradas, total) =>
      mostradas === total
        ? `${total} GPS interference ${total === 1 ? "cell" : "cells"} in view, most affected first`
        : `The ${mostradas} most affected GPS interference cells of the ${total} in view`,
    ciudadesALaVista: (n) => (n === 1 ? "1 city with night-light data in view" : `${n} cities with night-light data in view`),
    boton: "List",
    abrir: "Ukraine layer list",
    titulo: "Ukraine layer as a list",
    explicacion: "The same as the map for the selected period. Choosing an item opens its record and takes the map to it.",
    regionesUcrania: (n) => `Regions of Ukraine with attacks · ${n}`,
    regionesRusia: (n) => `Regions of Russia with attacks · ${n}`,
    impactos: (mostrados, total) =>
      mostrados === total ? `Places hit · ${total}` : `Latest places hit · ${mostrados} of ${total}`,
    corredores: (n) => `Corridors · ${n}`,
    vacia: "Nothing to show for the selected period.",
    fichaCerrada: "Record closed",
  },
  directo: {
    etiqueta: "Airport · live detection",
    estado: {
      posible_cierre: "Possible closure in progress",
      cierre_confirmado: "Closure confirmed",
      operacion_reanudada: "Operations resumed",
    },
    detectado: "Detected",
    inicio: "Start of the gap",
    reanudado: "Resumed",
    evidencia: "Evidence",
    movimientos: (vistos, esperados) => `${vistos} movements seen out of ${esperados} expected`,
    llegadasPerdidas: (n) => `${n} missing arrivals`,
    salidasPerdidas: (n) => `${n} missing departures`,
    esperas: (n) => `${n} aircraft holding`,
    desvios: (n) => `${n} diverted flights`,
    confirmacion: "Confirmation",
    confirmacionTipo: { incidente: "incident in the database", oficial: "official source" },
    primeraNoticia: "First news",
    ventaja: (minutos) =>
      minutos >= 0
        ? `detected ${minutos} min before the first news`
        : `detected ${-minutos} min after the first news`,
    actualizado: "Updated",
    fuente: "Real-time traffic",
    fuentes: { adsb_lol: "adsb.lol", adsb_fi: "adsb.fi" },
    vigilados: (n) => `${n} airports monitored`,
  },
  gnss: {
    etiqueta: "GPS interference",
    leyenda: "Aircraft with degraded position",
    niveles: { sin: "under 2%", media: "2 to 10%", alta: "over 10%" },
    proporcion: "Aircraft affected",
    aeronaves: "Aircraft",
    degradadas: "with degraded position",
    periodo: "Period",
    dias: (n) => (n === 1 ? "1 day with data" : `${n} days with data`),
    zonasAltas: (n) => (n === 1 ? "1 zone with high interference" : `${n} zones with high interference`),
    sinDatos: "No interference data for this period",
    cargando: "Loading interference…",
    letrero: (proporcion) => `GPS interference · ${proporcion} of aircraft`,
  },
  prevision: {
    etiqueta: "Forecast",
    cerrar: "Close the forecast",
    cargando: "Loading the forecast…",
    noDisponible: "The forecast could not be loaded.",
    noPublicada: "No forecast has been published yet.",
    anterior: (cuando) => `A more recent forecast could not be fetched. This is the latest one available, computed on ${cuando}.`,
    deCada10: (n, porcentaje) => `${n} in 10 nights like this one (${porcentaje}%)`,
    calculada: (cuando) => `Computed on ${cuando}.`,
    frontera: {
      titulo: "Tonight at the border",
      noche: (desde, hasta) => `Night of ${desde} to ${hasta}: a war drone crossing into or falling in the country`,
      ninguno: "Today no country has a checked forecast.",
      habitual: (porcentaje) => `Usual for this country: ${porcentaje} in 100 nights.`,
      dependeDe: "What it depends on today:",
      lanzados: (media, anoche) =>
        `drones launched at Ukraine: ${media} on average over the last three nights (last night, ${anoche})`,
      crimea: (noches) => `nights with drones launched from Crimea, the southern route: ${noches} of the last 7`,
      incidentes: (n, pais) => `border incidents in ${pais} in the last 7 days: ${n}`,
      efectos: { sube: "raises the risk", baja: "lowers the risk" },
      sinCambios: "Today none of the measured factors raises or lowers the risk.",
      historial: (noches, desde, conDron, porcentaje, enAlto) =>
        `Checked against ${noches} nights since ${desde}, each using only earlier data. There was a drone on ${conDron} (${porcentaje} in 100, the usual). Of the ${conDron} nights with a drone, ${enAlto} were among the quarter of nights with the highest risk.`,
      verHistorial: "Track record",
      columnaDijo: "When it said",
      columnaNoches: "Nights",
      columnaConDron: "With a drone",
      tramo: (desde, hasta) => `${desde} to ${hasta}%`,
      ultimas: "Last nights (reconstructed forecast and whether there was a drone):",
      conDron: "drone",
      enVivo: (puntuadas, conDron) => `Live forecasts already scored: ${puntuadas} nights, with a drone on ${conDron}.`,
    },
    segundaNoche: {
      titulo: "Second night",
      aviso: (lanzados, probabilidad) =>
        `Last night was a large wave (${lanzados} drones). That tonight is large too: ${probabilidad}.`,
    },
    rachas: {
      titulo: "Streaks by country",
      ninguna: "No country is above normal right now.",
      linea: (desde, n, habitual, veces, tendencia) =>
        `since ${desde}: ${n} incidents against ${habitual} usual (${veces} times) · ${tendencia}`,
      tendencia: { crece: "growing", estable: "steady", se_apaga: "fading" },
      ir: (pais) => `Show ${pais} on the map with the streak period`,
      historial: (semanas, siguientes, normal) =>
        `Checked against ${semanas} streak weeks since July 2025: the following week had ${siguientes} incidents where normal was ${normal}. It counts events, not news: each incident once, on the date it happened.`,
      enFicha: "Streak",
    },
    grafica: {
      titulo: "Incidents per week and the normal band",
      resumen: (semanas, incidentes, normal) =>
        `${incidentes} incidents in the last ${semanas} weeks; normal is ${normal} per week.`,
      barra: (semana, n) => `Week of ${semana}: ${n}`,
      banda: (minimo, maximo) => `Grey band: normal, ${minimo} to ${maximo} per week (8 in 10 weeks).`,
    },
    cambios: {
      titulo: "What has changed",
      periodo: (desde, hasta) => `${desde} to ${hasta}, against the previous twelve months. What has not changed is not listed.`,
      ambito: {
        ucrania_objetivo: "Ukraine, what is targeted (impacts with a known target, official channels with data throughout)",
        europa_tipo: "Europe, type of incident",
      },
      linea: (clase, reciente, habitual, casos, de, sentido) =>
        `${clase}: ${reciente}% (${casos} of ${de}), against ${habitual}% usually · ${sentido}`,
      sentido: { sube: "up", baja: "down" },
      historial: (casos, sostenidos) =>
        `Checked since September 2025: of ${casos} changes flagged, the following month went the same way in ${sostenidos}.`,
    },
    comoSeComprueba: "How it is checked",
  },
  zona: {
    titulo: "Border or interior",
    grupo: { frontera: "Border", interior: "Interior" },
    motivo: (motivo, distancia) => {
      const km = distancia === null ? "" : `, ${distancia} km from the border with Ukraine, Russia or Belarus`;
      switch (motivo) {
        case "ataque":
          return "linked to that night’s Russian attack on Ukraine";
        case "cerca_de_la_frontera":
          return `150 km or less from the border with Ukraine, Russia or Belarus${km}`;
        case "costa_mar_negro":
          return `on the Black Sea coast${km}`;
        case "lejos_de_la_frontera":
          return `more than 150 km from the border with Ukraine, Russia or Belarus and away from the Black Sea${km}`;
        case "incursion_en_pais_fronterizo":
          return "no known place; the drone came from outside into a border country";
        case "pais_dentro_de_la_banda":
          return "no known place; the whole country is 150 km or less from the border";
        case "sin_lugar":
          return "no known place and no link to an attack";
      }
    },
  },
  presion: {
    etiqueta: "Country · pressure",
    leyenda: {
      todo: "Incidents since the first record",
      reciente: {
        "24h": "Incidents in the last 24 hours",
        "7d": "Incidents in the last 7 days",
        "30d": "Incidents in the last 30 days",
        "1a": "Incidents in the last year",
      },
      entre: (intervalo) => `Incidents ${intervalo}`,
    },
    menos: "fewer",
    mas: "more",
    tendencia: { sube: "up", baja: "down", estable: "stable" },
    frente: (anterior) => `compared with ${anterior} in the previous period of equal length`,
    sinComparacion: "no previous period with data",
    eligePeriodo: "Choose a period to see the trend",
    incidentes: (n) => (n === 1 ? "1 incident" : `${n} incidents`),
    porTipo: "By type",
    porEstado: "By status",
    lista: "Incidents in the period",
    vacia: "No incidents in the selected period.",
    letrero: (pais, n) => `${pais} · ${n === 1 ? "1 incident" : `${n} incidents`}`,
  },
  novedades: {
    aviso: (n) => (n === 1 ? "1 update since your last visit" : `${n} updates since your last visit`),
    recorrer: "Show me",
    siguiente: "Next",
    anterior: "Previous",
    descartar: "Dismiss",
    posicion: (i, n) => `Update ${i} of ${n}`,
    recorrido: "Browse the updates",
  },
  ayuda: {
    titulo: "How to read the map",
    cerrar: "Close help",
    colores:
      "Each incident is a circle filled with the colour of its status: orange, reported; red, " +
      "confirmed. A denied incident is a grey circle with a dashed outline and no fill. An " +
      "attributed incident (a confirmed one that an authority attributes to a State or to a " +
      "person) is a slightly larger circle with a thick red ring and, inside, the flag of the " +
      "country it is attributed to; when attributed to a person, it also has a fixed dark dot in " +
      "the centre. It is always drawn on top and is never grouped with the circles. The type of " +
      "incident is written in the record, the list and the filters.",
    periodo:
      "The “Filters” button opens the period (everything, the last 24 hours, the last 7 or 30 " +
      "days, the last year or between two dates) and the status, type and country filters. " +
      "With a period chosen, the button shows it and its cross goes back to everything. The " +
      "map, the list, the figures, “Live” and every layer show that period. “Last 24 hours” " +
      "counts back from this moment: it includes what started in the previous 24 hours and, " +
      "when only the day is known, what happened today and yesterday.",
    ahora:
      "“Europe now” opens the figures of the moment; each one leads to the place on the map " +
      "that explains it. On the button, an orange number counts the airport closures in " +
      "progress and a white one the updates since your previous visit: inside, “Show me” " +
      "goes through them one by one and “Dismiss” clears them.",
    aproximado:
      "Hollow ring with a dot in the centre: approximate location. The source only names the country, the region or the sea, and the marker is at the centre of that area, not at the site of the event. Its colour is that of its status.",
    areas:
      "Each incident covers an area: the circle is the radius within which it is known to have " +
      "happened.",
    lineas: "A thin line joins the incidents of one episode: several targets on the same night.",
    numeros:
      "A circle with a number inside groups several incidents (a single incident is filled " +
      "and has no number): it grows with the number, and its ring " +
      "is red if it holds any confirmed incident and orange if all are reported. Zoom in and " +
      "they separate. Map names give way to the circles: they are shown whole or not at all.",
    pila: "If the incidents share the exact same spot, tap the circle to choose which one to open.",
    pulsos:
      "Only what is new since your last visit pulses (and the circle that holds it): it stops " +
      "when you press “Show me” or “Dismiss” or open the incident. With the system's reduced " +
      "motion setting, it gets a fixed ring instead. Reported incidents are dimmer.",
    reciente: "A soft glow marks what started in the last 24 hours.",
    novedad: "Nothing pulses on a first visit: there is no earlier visit to compare with yet.",
    ucrania:
      "In the Ukraine layer, each region is shaded violet by the attacks that name it in the " +
      "period: the colour of the whole war layer, distinct from the red and orange of incidents.",
    rusia:
      "Russian regions are muted violet with a dashed outline: their figures are those of the " +
      "Russian Ministry of Defence, a claim by a party to the war.",
    impactos:
      "A small violet dot is a specific place hit (a town or a facility; if the source only names " +
      "the community or the district, that one, with its radius) according to the regional " +
      "administrations, the Ukrainian General Staff or Russian governors. Filled: official " +
      "source; ring only: claim by a party. Zoomed out, they group with their count. Daily " +
      "front-line reports are in the downloadable data.",
    foco:
      "A light dot next to an incident, a place hit or a group of places, or at the centre of a Ukrainian region, marks a " +
      "thermal hotspot detected by satellite (NASA FIRMS) at its place and time: white on " +
      "incidents and light violet in the war layer.",
    directo:
      "A tag with the ICAO code inside and a point towards the airport is an alert from the " +
      "live detection, without pulse. Its border shows the status: orange, possible closure in " +
      "progress; red, closure confirmed; grey, operations resumed. It sits above the spot so " +
      "it never hides the number of a group.",
    atajos: "Keyboard shortcuts",
    acciones: {
      ayuda: "Open or close this help",
      cerrar: "Close what is open: the drop-down, the record or the panel",
      capaIncidentes: "Incidents layer",
      capaUcrania: "Ukraine layer",
      capaDensidad: "Density layer",
      capaSatelite: "Turn «With satellite» on or off",
      filtroGraves: "Confirmed and attributed only",
      filtro24h: "Last 24 hours",
      filtro7d: "Last 7 days",
      sinFiltros: "Clear filters",
      filtros: "Open or close the filters and the period",
      ahora: "Open or close “Europe now”",
      feed: "Open or close the live panel",
      lista: "Incident list",
      metodologia: "Methodology and open data",
    },
  },
  pila: { titulo: (n) => `${n} incidents at this spot` },
  imprecisa: {
    etiqueta: "approximate location",
    aproximado: (nivel) => `Approximate location: ${nivel}`,
    niveles: { pais: "country", region: "region", mar: "sea" },
    deDonde: (nivel, zona) => {
      switch (nivel) {
        case "pais":
          return `The source only names the country. The marker is at the centre of ${zona}, not at the site of the event.`;
        case "region":
          return `The source names the region (${zona}), not a place that can be located. The marker is at the centre of the region.`;
        case "mar":
          return `The source places the event at sea (${zona}). The marker is at sea off the coast, not at the exact site.`;
      }
    },
    nivel: {
      instalacion: "site not located",
      localidad: "town not located",
      region: "region only",
      pais: "country only",
    },
  },
  guerra: {
    reproducir: "Night by night",
    pausar: "Pause",
    reanudar: "Resume",
    detener: "Stop",
    drones: "drones launched against Ukraine",
    sinCifra: "no launch figure",
    mezcla: (shahed, reactivos) =>
      [shahed === null ? null : `Shahed and Geran: from ${shahed}`, reactivos === null ? null : `jet-powered: from ${reactivos}`]
        .filter((parte) => parte !== null)
        .join(" · ") + " (as the reports state)",
  },
  mapa: {
    etiqueta: "Map of Europe with the incidents of the selected period",
    instrucciones:
      "With focus on the map, the arrow keys pan and the plus and minus keys zoom. After the " +
      "map, the Tab key goes through the incidents in view, most recent first: each one is " +
      "marked on the map and Enter opens its record. The incident list opens the same records " +
      "without using the map. With the Ukraine layer on, before the incidents Tab goes through its " +
      "regions with attacks, its places hit and everything else that has a record, in the same way, " +
      "and the layer's «List» button gives the whole layer as a list.",
    aLaVista: (n) => (n === 1 ? "1 incident in view on the map" : `${n} incidents in view on the map`),
    grupo: (n) => (n === 1 ? "1 incident: zoom in to see it" : `${n} incidents: zoom in to see them`),
    pila: (n) => `${n} incidents at this exact spot: tap to choose one`,
    atribuidos: (n) => `${n} attributed incidents: zoom in to separate them`,
    grupoImpactos: (n) => `${n} places hit: zoom in to see them`,
    impacto: (parte, foco) =>
      `Place hit${parte ? " · claim by a party" : ""}${foco ? " · thermal hotspot" : ""}`,
  },
  tipo: {
    interrupcion_aeroportuaria: "Airport disruption",
    incursion: "Incursion",
    sobrevuelo: "Overflight",
  },
  estado: {
    notificado: "Reported",
    confirmado: "Confirmed",
    atribuido: "Attributed",
    desmentido: "Denied",
  },
  atribucion: {
    aEstado: (pais) => `Attributed to ${pais}`,
    aEstadoSinPais: "Attributed to a State",
    aPersonaDe: (gentilicio) => `Attributed to a person of ${gentilicio} nationality`,
    aPersonaDePais: (pais) => `Attributed to a person (nationality: ${pais})`,
    aPersona: "Attributed to a person",
    unaPersona: "a person",
    leyendaEstado: "Attributed by an authority to a State",
    leyendaPersona: "Attributed by an authority to a person",
    bandera:
      "Inside the red ring, the flag of the country to which the authority attributes the " +
      "incident (the State, or the person's nationality if the authority states it); it is not " +
      "a claim by the observatory. With no country, the ring is filled red. A person also has a " +
      "dark dot in the centre.",
  },
  presencia: {
    confirmada: "Drone confirmed",
    no_confirmada: "Drone not confirmed",
    descartada: "Drone ruled out",
  },
  precision: {
    minuto: "exact time",
    hora: "approximate time",
    dia: "day only",
    aproximada: "approximate date",
  },
  categoria: {
    aeropuerto: "Airport",
    base_militar: "Military base",
    puerto: "Port",
    energia: "Energy",
    presa: "Dam",
    estadio: "Stadium",
    industrial: "Industrial site",
    gubernamental: "Government building",
    otra: "Other place",
  },
  categoriaUcrania: {
    energia: "energy",
    residencial: "residential area",
    ferrocarril: "railway",
    puerto: "port",
    industrial: "industry",
    otra: "other",
  },
  categoriaGuerra: {
    energia: "energy",
    combustible: "fuel",
    residencial: "residential",
    ferrocarril: "railway",
    puerto: "port",
    industrial: "industry",
    aerodromo: "airfield",
  },
  categoriaInstalacion: {
    refineria: "refinery",
    deposito_combustible: "fuel depot",
    central: "power plant",
    subestacion: "substation",
    aerodromo: "airfield",
    puerto: "port",
    militar: "military site",
    ferrocarril: "railway station",
    industrial: "industrial plant",
  },
  medida: {
    cierre_espacio_aereo: "airspace closure",
    patrulla: "patrol",
    cazas: "fighter jets scrambled",
    derribo: "shootdown",
    inhibicion: "jamming",
    ninguna_conocida: "none known",
  },
  sentido: {
    RU_UA: "From Russia against Ukraine",
    UA_RU: "From Ukraine against Russia",
  },
  ficha: {
    titulo: "Record",
    cerrar: "Close the record",
    copiarEnlace: "Copy link",
    enlaceCopiado: "Link copied",
    enlaceNoCopiado: "Could not copy",
    estado: "Event status",
    presenciaDron: "Drone presence",
    fecha: "Date",
    lugar: "Place",
    lugarSegun: "Location per",
    otrosLugares: "Other places",
    puntoAnterior: "Previous point",
    radio: (km) => `area of ${km} km radius`,
    drones: "Drones",
    duracion: "Duration",
    efecto: "Effect",
    respuesta: "Response",
    atribucion: "Attribution",
    parteDelAtaque: "Part of the attack",
    ataqueDeLa: (jornada) => `Part of the Russian attack on Ukraine on the ${jornada}`,
    porFuente: "the source links it to the attack",
    porFecha: "same date, and it came from Ukraine",
    confirmadoAtribuido: (actor, autoridad) => `Confirmed · attributed to ${actor}, according to ${autoridad}`,
    atribuidoA: (actor, autoridad) => `${actor}, according to ${autoridad}`,
    investigacion: "Investigation under way",
    investiga: (autoridad) => `What ${autoridad} is investigating (this does not change the incident's status):`,
    verFuente: "see the source",
    declaracionCitada: (autoridad, medio) => `Statement by ${autoridad}, quoted in ${medio}`,
    motivoDesmentido: "Reason for the denial",
    desconocido: "No data",
    minutos: (n) => `${n} min`,
    rangoDeFuentes: "range across sources rated A–C",
    queDiceCadaFuente: (n) => (n === 1 ? "What the source says" : `What each source says (${n})`),
    valorSegun: "according to",
    cierreDe: (minutos) => `Closed for ${minutos} min`,
    cierreSinDuracion: "Closed, duration unknown",
    sinCierre: "No closure",
    cierreDesconocido: "Closure: unknown",
    vuelosDesviados: "flights diverted",
    vuelosCancelados: "flights cancelled",
    vuelosRetrasados: "flights delayed",
    heridos: "injured",
    fallecidos: "killed",
    danos: {
      ninguno: "No damage",
      menores: "Minor damage",
      graves: "Serious damage",
      desconocido: "Damage not confirmed",
    },
    modelo: "Model",
    episodio: "Episode",
    fuentes: (n) => (n === 1 ? "1 source" : `${n} sources`),
    masFuentes: (n) => `Show ${n} more`,
    menosFuentes: "Show fewer",
    replicas: (n) => (n === 1 ? "1 reprint" : `${n} reprints`),
    codigo: (codigo) => `Admiralty code ${codigo}`,
    declaracionOficial: "Official statement quoted",
    enlaceExterno: "external link, opens in a new tab",
    enlaceNoValido: "invalid link",
    historial: "Status history",
    fuenteNoPublica: "source not public",
    actualizada: "Record updated",
  },
  ataque: {
    etiqueta: "Attack · Ukraine layer",
    reivindicacion: "Figures from one of the warring parties, with no other source confirming them.",
    periodo: "Period",
    lanzados: "Drones launched",
    reactivos: "Of them, jet-powered",
    shahed: "Shahed / Geran",
    senuelos: "Gerbera and decoys",
    otros: "Other",
    derribados: "Shot down",
    derribadosONeutralizados: "Shot down or suppressed",
    guerraElectronica: "Lost to electronic warfare",
    localizacionesImpacto: "Locations hit",
    localizacionesRestos: "Locations with falling debris",
    zonasLanzamiento: "Launch areas",
    regiones: "Regions affected",
    regionesMisiles: "Regions named only for missiles",
    cruces: "Crossings into other countries",
    cruceDeclarado: "Declared by Ukraine; no incident from that country",
    incluidoEn: "Figures included in report",
    solapadoCon: "Overlaps with report",
  },
  trafico: {
    rotulo: "Air traffic",
    cierreMedido: "Closure measured with real air traffic",
    duracion: (minutos) => `${minutos} min`,
    desviados: (n) => `${n} diverted flights`,
    enEspera: (n) => `${n} holding`,
    declarado: "According to the sources",
    datos: "adsb.lol data",
  },
  foco: {
    rotulo: "Satellite",
    detectado: "Thermal hotspot detected by satellite",
    distancia: (km) => `${km} km away`,
    visor: "View in the NASA FIRMS viewer",
  },
  region: {
    etiqueta: "Region · Ukraine layer",
    ataques: "Attacks in the period",
    ataquesPorSentido: {
      RU_UA: "Russian attacks according to the Ukrainian Air Force",
      UA_RU: "Ukrainian attacks according to the Russian Ministry of Defence",
    },
    derribados: "Drones shot down over the region",
    ultimoAtaque: "Latest attack",
    sinAtaques: "No report names this region in the selected period.",
    listaAtaques: "Reports naming it",
    masAtaques: (n) => `Show ${n} more`,
    nota:
      "The figures are those each party gives in its statements. Shootdowns per region are " +
      "those each party breaks down by region.",
    fuenteCifras: (medio) => `Figures from ${medio}`,
    reivindicacion: "claim by a party to the war",
    impactos: "Places hit in the period",
    listaImpactos: "Places hit",
  },
  impacto: {
    etiqueta: "Place hit · war layer",
    lugar: "Place",
    instalacionEn: (localidad) => `in ${localidad}`,
    radio: (km) => `area of ${km} km radius`,
    nivel: {
      comunidad: "the source only names the community, not the town",
      distrito: "the source only names the district, not the town",
    },
    tipo: { impacto: "Hit", restos: "Debris of a downed drone fell" },
    objetivo: "Type of target",
    sinObjetivo: "not stated by the source",
    fecha: "Date",
    publicado: "published; the impact was earlier",
    diaAtaque: "day of the attack according to the message",
    parteDiario: "daily report of the administration: the 24 hours before it was published",
    victimas: "Casualties",
    heridos: (n) => `${n} injured`,
    fallecidos: (n) => `${n} killed`,
    ataque: "Attack that night",
    region: "Region",
    credibilidad: "Credibility",
    credibilidadTexto: {
      1: "confirmed",
      2: "probable",
      3: "possible",
      4: "doubtful",
      5: "improbable",
      6: "cannot be judged",
    },
    reivindicacion: "Claim by a party to the war",
    reivindicacionTexto:
      "Only one of the parties to the war says so, with no independent source or measured " +
      "data confirming it.",
    ocupacion: "authority installed by Russia",
    fuentes: (n) => (n === 1 ? "1 source" : `${n} sources`),
    cargando: "Loading the place hit…",
    noDisponible: "This place hit could not be loaded.",
  },
  lista: {
    titulo: "Incident list",
    incidentes: (n) => (n === 1 ? "1 incident in the period" : `${n} incidents in the period`),
    vacia: "No incidents in the selected period.",
    regiones: "War layer regions",
  },
  tiempo: {
    periodo: (desde, hasta) => `${desde} – ${hasta}`,
    intervalo: (a, b) => {
      if (a.anio !== b.anio) return `from ${diaMesAnio(a)} to ${diaMesAnio(b)}`;
      if (a.mes !== b.mes) return `from ${a.dia} ${MONTHS[a.mes]} to ${diaMesAnio(b)}`;
      if (a.dia !== b.dia) return `from ${a.dia} to ${diaMesAnio(b)}`;
      return `on ${diaMesAnio(a)}`;
    },
    noche: (a, b) =>
      a.mes === b.mes ? `night of ${a.dia} to ${b.dia} ${MONTHS[b.mes]}` : `night of ${a.dia} ${MONTHS[a.mes]} to ${b.dia} ${MONTHS[b.mes]}`,
    dia: (f) => `day of ${f.dia} ${MONTHS[f.mes]}`,
  },

  metodologia: {
    titulo: "Methodology",
    cerrar: "Close the methodology",
    secciones: [
      {
        id: "que",
        titulo: "What is recorded",
        bloques: [
          {
            parrafo: [
              `The ${NOMBRE} records drone incidents in Europe: unmanned aircraft that fly ` +
                "over a facility, enter an airspace from outside or disrupt the operation of " +
                "an airport.",
            ],
          },
          {
            parrafo: [
              "Drones only. Balloons, missiles, crewed aircraft, laser pointers and signal " +
                "interference without a drone are not recorded, and neither are authorised " +
                "flights or accidents involving a force's own drones during exercises.",
            ],
          },
          {
            parrafo: [
              "Each incident is placed as an area, a point with a radius, because the exact " +
                "position is almost never known. If the source only names the country, the " +
                "region or the sea, the incident is drawn with its own approximate-location " +
                "marker (a hollow ring with a dot) at the centre of that area, and its record " +
                "says the level and where it comes from. Every piece of data keeps who says it: for " +
                "each source we store the fact, a short source sentence in its own language " +
                "and the link, never the full text.",
            ],
          },
        ],
      },
      {
        id: "tipos",
        titulo: "Types",
        bloques: [
          {
            lista: [
              {
                termino: "Airport disruption",
                texto: [
                  "An airport closes or has flights diverted, cancelled or delayed. When it " +
                    "applies, this type takes precedence over the others.",
                ],
              },
              {
                termino: "Incursion",
                texto: [
                  "The drone enters from outside the country and its origin is proven by " +
                    "tracking or by debris. A sighting with no proven origin is never an " +
                    "incursion.",
                ],
              },
              {
                termino: "Overflight",
                texto: ["Any other drone flight over a facility or a town."],
              },
            ],
          },
        ],
      },
      {
        id: "estados",
        titulo: "Statuses",
        bloques: [
          {
            lista: [
              {
                termino: "Reported",
                marca: { estado: "notificado" },
                texto: ["The news reports it. It is the initial status of every incident. In orange."],
              },
              {
                termino: "Confirmed",
                marca: { estado: "confirmado" },
                texto: ["An authority states that the incident happened. In red."],
              },
              {
                termino: "Attributed",
                marca: { estado: "atribuido" },
                texto: [
                  "A confirmed incident for which a competent authority (government, ministry, armed " +
                    "forces, prosecutor or police) expressly states, in its own words, who is " +
                    "responsible: a State or a person. A news report saying so without the " +
                    "authority's own words is not enough, nor is an authority investigating, examining " +
                    "a possible link, not ruling it out, finding it possible or suspecting it: that " +
                    "goes in the record as an investigation under way and the incident stays " +
                    "confirmed. The perpetrator is never the authority making the statement. A person " +
                    "only if the authority has arrested, charged or convicted them, and their name only " +
                    "if the authority gives it. If an attribution no longer holds, it is withdrawn with " +
                    "a step in the history saying why. " +
                    "On the map, a circle with a thick red ring, larger than an incident's and drawn " +
                    "on top of everything, centred on the place: inside, the flag of the country the " +
                    "authority attributes it to, the State or the person's nationality (the latter " +
                    "only if the authority states it expressly; it is never inferred from the name, " +
                    "the place or the language). With no country, or a country without a flag on the " +
                    "site, the ring is filled red. When attributed to a person, it also has a fixed " +
                    "dark dot in the centre. The flag is the one the authority gives, not a claim by " +
                    "the observatory. Several attributed incidents together when zooming out are one " +
                    "marker with its number; if they belong to different countries, it is filled red, " +
                    "without a flag. The record shows it as “Confirmed · attributed to…”, with who " +
                    "attributes it and to whom.",
                ],
              },
              {
                termino: "Denied",
                marca: { estado: "desmentido" },
                texto: [
                  "An authority denies the incident. It stays published, with the reason. " +
                    "Only another authority of equal or higher reliability can return it to " +
                    "confirmed.",
                ],
              },
            ],
          },
          {
            parrafo: [
              "In the scoreboard, confirmed and attributed incidents are counted separately: an " +
                "attributed incident is no longer counted as confirmed. Status is always shown " +
                "with both colour and text. A circle that groups several incidents is red if it " +
                "holds any confirmed or attributed incident and orange if all are reported.",
            ],
          },
        ],
      },
      {
        id: "presencia",
        titulo: "Drone presence",
        bloques: [
          {
            parrafo: [
              "Event status says whether the incident happened; drone presence says whether " +
                "the authority attributes it to a drone. If the competent authority takes it " +
                "as a fact, it is confirmed: it is enough for the airport operator, the air " +
                "navigation service provider, the police, the armed forces, a ministry, the " +
                "public prosecutor or the civil aviation authority to act or state that the " +
                "event was caused by a drone (a closure because of a drone, a drone report it " +
                "passes on, a police response to a drone). No debris, footage or sensor " +
                "detection is required. It stays not confirmed if the authority itself leaves " +
                "it open («possible drone», «unidentified object», «investigating whether it " +
                "was a drone») or if only the press or witnesses report it. It is ruled out " +
                "when an authority denies it.",
            ],
          },
          {
            parrafo: [
              "The Liège case shows it. In November 2025 the air navigation service provider " +
                "halted traffic at the airport after a drone report: the authority attributes " +
                "the event to a drone and presence is confirmed. The headline of each record " +
                "says the same as this field: it states the drone when it is confirmed and " +
                "presents it as possible when it is not.",
            ],
          },
        ],
      },
      {
        id: "almirantazgo",
        titulo: "Admiralty code",
        bloques: [
          {
            parrafo: [
              "Each source carries a two-character code, for example B2. The letter rates " +
                "the reliability of the source, from A (authority with direct competence) to " +
                "F (cannot be judged). The number rates the credibility of the information, " +
                "from 1 (confirmed by independent sources) to 6 (cannot be judged).",
            ],
          },
          {
            lista: [
              { termino: "A", texto: ["Official statements from the competent authority."] },
              {
                termino: "B",
                texto: [
                  "Official statements quoted in a news report, and Ukrainian Air Force " +
                    "reports.",
                ],
              },
              { termino: "C", texto: ["News media."] },
              { termino: "D", texto: ["Russian Ministry of Defence statements."] },
            ],
          },
          {
            parrafo: [
              "Sources rated E and F are not published. When sources give different " +
                "figures, the record shows the range covered by sources rated A to C.",
            ],
          },
        ],
      },
      {
        id: "agrupacion",
        titulo: "How news reports are grouped",
        bloques: [
          {
            parrafo: [
              "News reports are read by automatic extraction validated by rules: a record " +
                "that does not match the schema, or whose source sentence is not in the " +
                "report, is discarded. Copies of the same story count once and are shown as " +
                "reprints.",
            ],
          },
          {
            parrafo: [
              "Two reports are the same incident if they refer to the same target, or to " +
                "points closer than the sum of their radii plus 10 km, and their start times " +
                "are less than 6 hours apart or, when only the day is known, fall on the " +
                "same day or the next. More than 12 hours without activity start a new " +
                "incident. Two closures of the same site on different nights are always two " +
                "incidents.",
            ],
          },
          {
            parrafo: [
              "An episode links the incidents at two or more targets in the same country " +
                "during the same night, from 16:00 to 06:00 UTC. On the map they are joined " +
                "by a thin line.",
            ],
          },
        ],
      },
      {
        id: "declaraciones",
        titulo: "Official statements quoted",
        bloques: [
          {
            parrafo: [
              "When a news report quotes an authority, the statement is recorded as a " +
                "source of its own, rated B, with the link to the report that carries it. It " +
                "confirms the incident if the authority states that it happened, and with it " +
                "drone presence, unless the authority itself leaves it open; and it denies " +
                "or attributes the incident if that is what it says.",
            ],
          },
        ],
      },
      {
        id: "historial",
        titulo: "Nothing is deleted",
        bloques: [
          {
            parrafo: [
              "No record is removed. Every change of status is added to the history with " +
                "its date and the source behind it, and a denial does not erase what came " +
                "before. If the change was caused by a source that is not published, the " +
                "history keeps the change and omits the source.",
            ],
          },
        ],
      },
      {
        id: "fuentes",
        titulo: "Sources",
        bloques: [
          {
            lista: [
              {
                termino: "European news",
                texto: [
                  "Found through the GKG files of ",
                  { texto: "GDELT", enlace: "https://www.gdeltproject.org/" },
                  " and linked to the original outlet.",
                ],
              },
              {
                termino: "Official statements",
                texto: [
                  "Police forces, air navigation providers, airports and defence ministries " +
                    "that publish their statements openly.",
                ],
              },
              {
                termino: "Ukraine layer",
                texto: [
                  "Ukrainian Air Force reports and Russian Ministry of Defence statements. " +
                    "They are claims by a party to the war: each attack aggregates what one " +
                    "of the two sides declares, usually per night, with no other source " +
                    "confirming it.",
                ],
              },
              {
                termino: "Places hit, from Russia against Ukraine",
                texto: [
                  "Official channels of the Ukrainian regional military administrations and " +
                    "of Kyiv, identified from each one's official website: reliability B, " +
                    "official source.",
                ],
              },
              {
                termino: "Places hit, from Ukraine against Russia",
                texto: [
                  "The Ukrainian General Staff channel (its claims of strikes on refineries, " +
                    "depots and airfields) and the channels of Russian governors and regional " +
                    "governments linked from their official websites (the damage they admit " +
                    "on their territory). They are parties to the war: reliability C, claim by " +
                    "a party. Areas occupied by Russia always carry their Ukrainian code; " +
                    "authorities installed by Russia are marked as such.",
                ],
              },
              {
                termino: "Scoring of a place hit",
                texto: [
                  "Messages from the same channel are not independent sources. A single " +
                    "official source gives \u201cprobable\u201d; a claim by a party, " +
                    "\u201cpossible\u201d. It rises if another independent source confirms " +
                    "it, if both sides say so (at least \u201cprobable\u201d) or if the " +
                    "satellite detects a new thermal hotspot at the place, which counts as " +
                    "measured data. The same treatment for both parties. Missiles and bombs " +
                    "in the same messages are not recorded.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "focos",
        titulo: "Thermal hotspots from satellites",
        bloques: [
          {
            parrafo: [
              "Each declared impact (a drone that exploded or crashed, with its place known " +
                "to within 10 km) is checked against the thermal anomalies detected by the " +
                "satellites of ",
              { texto: "NASA FIRMS", enlace: "https://www.earthdata.nasa.gov/firms" },
              " (VIIRS on Suomi NPP, NOAA-20 and NOAA-21, and MODIS on Terra and Aqua). The " +
                "mark means there were at least two hotspots within its precision radius " +
                "(between 2 and 10 km) from the start of the attack until 36 hours after it " +
                "ended.",
            ],
          },
          {
            parrafo: [
              "Refineries and plants have flares the satellites always see: a hotspot only " +
                "counts if it is new compared with the previous 30 days or more than four " +
                "times as powerful as usual for that spot. As some flares go unseen for months, " +
                "a new hotspot at a spot that already burned in the previous year only counts " +
                "if it is more than four times as powerful as that spot in the year, unless " +
                "one satellite pass sees three or more. Low-confidence hotspots are discarded. " +
                "Impacts known only by region are not assessed; places hit from the regional " +
                "channels and the General Staff are, except those in the daily front-line " +
                "reports and FPV attacks, where artillery causes hotspots every day. Nor is a " +
                "place assessed whose radius burned on half or more of the previous 30 days " +
                "at many spots: a new hotspot there says nothing.",
            ],
          },
          {
            parrafo: [
              "The satellites pass over each place several times a day and every pass leaves " +
                "its detections. The mark appears when there is a hotspot: a measured physical " +
                "fact, a fire within the radius in the attack window, shown alongside what the " +
                "sources say.",
            ],
          },
        ],
      },
      {
        id: "satelite",
        titulo: "War seen from space",
        bloques: [
          {
            parrafo: [
              "In the war layer, four pieces come from satellites and from the official " +
                "reports. Before and after images: for each strike with a detected thermal " +
                "hotspot and for each strike on an installation, the last cloud-free ",
              { texto: "Sentinel-2", enlace: "https://registry.opendata.aws/sentinel-2-l2a-cogs/" },
              " image before the attack and the first one after it, cropped over the site in " +
                "natural colour with the same brightness adjustment. Cloud is measured over the " +
                "crop itself with ESA's scene classification: an image with 3% cloud or less " +
                "over the installation is used even if the whole scene is cloudy. A pair is " +
                "published only if the change can be seen: both images are brought to the same " +
                "10 m grid, and the difference of the burn index (bands B8A and B12) and the " +
                "darkening in natural colour are measured, without clouds, shadows, snow or " +
                "water, and above what changes in the rest of the crop (season, crops, light). " +
                "The patch touching an 800 m circle around the strike counts, and the pair is " +
                "published if it reaches 10 hectares; if the first clear image after the attack " +
                "does not show it (smoke or thin cloud cover it), the next ones are tried for 15 " +
                "days. The changed area is outlined and the image is framed on it. Everything " +
                "from the satellite is switched on with «With satellite»; the corridors, with " +
                "their own button.",
            ],
          },
          {
            parrafo: [
              "Night lights: after each attack on energy targets (a strike on the power grid or " +
                "an official regional message naming it), the brightness of the affected " +
                "cities and regions in the VIIRS day-night band (NOAA-20), from the ",
              { texto: "NOAA open archive", enlace: "https://registry.opendata.aws/noaa-jpss/" },
              ". Brightness is the city's light above the surrounding background, measured in " +
                "the same satellite pass (which removes moonlight reflected by the ground); only " +
                "nights with 70% cloud cover or less count (Open-Meteo, at the time of the pass) " +
                "with the satellite close to overhead. The reference is the median of the valid " +
                "nights of the previous three weeks; there is a loss of light when two or more " +
                "nights of the following week lose half or more, in cities with a reference of " +
                "0.5 nW/(cm²·sr) or more. The thresholds were set with 20 documented blackouts " +
                "from 2024 to 2026, 9 controls and 411 windows without attacks (3 showed a loss).",
            ],
          },
          {
            parrafo: [
              "Permanently reduced street lighting: a city whose brightness stays below 0.5 " +
                "nW/(cm²·sr) above the background cannot show a blackout with this rule, so it is " +
                "marked on the map with its own sign instead. It is marked when the median of its " +
                "last 10 valid nights is below that minimum and, going back month by month (months " +
                "with 3 valid nights or more), the monthly median stays below it too; a single " +
                "month above (snow reflects the city light, as in January 2026) does not break the " +
                "run, two measured months in a row do. Its card gives the date since when (or «at " +
                "least since» the first night measured), the current brightness and the earliest " +
                "measured, each the median of 10 valid nights, and the number of nights it is " +
                "based on. It is computed from all the nights measured by NOAA-20.",
            ],
          },
          {
            parrafo: [
              "Confirmed fire hotspots: of the NASA FIRMS hotspots of the last 24 hours over " +
                "Ukraine and European Russia, with the same filters as the strike cross-check " +
                "(refinery flares and plants with habitual heat, low confidence and areas that " +
                "burn every day, such as front-line cities, are left out), only those within the " +
                "radius of a reported strike within 36 hours are published. In «With satellite» " +
                "they count as strikes with a hotspot as soon as they are confirmed, together with " +
                "those of the historical cross-check. The rest (crop burning, industry, wildfires) " +
                "are still downloaded and cross-checked, but not drawn.",
            ],
          },
          {
            parrafo: [
              "Attack corridors: arcs from the launch zones named by the Ukrainian Air Force " +
                "reports (with the point from the deduction engine's zone catalogue) to the " +
                "regions reached, with the width given by the drones of those attacks in the " +
                "selected period. For attacks on Russia, whose report gives shoot-downs by " +
                "region, the arc starts at the point of the Ukrainian border closest to each " +
                "region and its figure is those shoot-downs.",
            ],
          },
        ],
      },
      {
        id: "rutas",
        titulo: "Drone routes over Ukraine",
        bloques: [
          {
            parrafo: [
              "The «Routes» sublayer of the Ukraine layer draws where each group of drones came " +
                "in and where it went on one night: one line per group, faint at its origin, " +
                "stronger towards its end and with an arrowhead, inside a halo that is wider where " +
                "the position is less precise (2 to 15 km on each side). One night at a time: the " +
                "last finished one, or another chosen in “Night by night”. The 40 groups with the " +
                "most drones are drawn and the legend says how many of how many. A report that " +
                "only names a whole region is not drawn: it only joins the route if there are " +
                "precise positions before and after. Two segments are joined into a group only if " +
                "there is no doubt they are the same; if a group splits or merges, the line forks " +
                "or joins. They are published once the attack is over: after 12:00 UTC the next " +
                "day and two hours after the night's last report. Never live.",
            ],
          },
          {
            lista: [
              {
                termino: "With NEPTUN",
                texto: [
                  "Since 4 October 2026 the observatory keeps the stream of ",
                  { texto: "NEPTUN", enlace: "https://neptun.in.ua/" },
                  ", which estimates the position, heading, speed and number of each threat from " +
                    "reports (it is not a radar). Nights with that archive almost complete use its " +
                    "tracks, with the uncertainty radius NEPTUN gives and its visible link.",
                ],
              },
              {
                termino: "With the Ukrainian Air Force",
                texto: [
                  "For the other nights, since 2023, the route is reconstructed from the Air Force " +
                    "tracking messages: each message gives an area (a town, part of a region, a " +
                    "region or the sea) and sometimes a heading or a destination; two messages are " +
                    "linked if the drone could fly from one area to the other in that time and in " +
                    "that direction. A group is not identified from the text: it may split, merge " +
                    "or be unknown. Each segment keeps the messages it comes from.",
                ],
              },
              {
                termino: "Check",
                texto: [
                  "On the nights with NEPTUN, the route reconstructed only from the Air Force is " +
                    "compared with the NEPTUN tracks and with the straight line from the launch " +
                    "area to each of the night's impacts. Reconstructed routes are published only " +
                    "if they come clearly closer to NEPTUN than the straight line (median at least " +
                    "20% lower, and better on every night). The legend and each group's record say " +
                    "which source it comes from and its precision.",
                ],
              },
              {
                termino: "Incursions",
                texto: [
                  "For incidents in Romania, Moldova and Poland where the authority names the " +
                    "places the drone passed, the record draws that route when opened, with the " +
                    "sentence it comes from. When a night's route ends at a European incident of " +
                    "that night, the group's record links it.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "recorridos",
        titulo: "Route of the incursions",
        bloques: [
          {
            parrafo: [
              "For incidents in Romania, Moldova and Poland where the authority names the places " +
                "the drone passed, the record draws that route when opened, with the sentence it " +
                "comes from: the places in order, located with the gazetteer, and a band joining " +
                "each pair.",
            ],
          },
        ],
      },
      {
        id: "tipo-dron",
        titulo: "Drone type",
        bloques: [
          {
            parrafo: [
              "Each incident says which class of drone it may have been only when there is a " +
                "basis for it. If an authority names the model (for example, the debris of a " +
                "Gerbera identified by the army), the record says so and where it comes from. " +
                "Otherwise the observatory deduces it and shows it separately, as “compatible " +
                "with”, always with the reasons. When what has been published does not tell " +
                "the long-range attack drone from the decoy, the record only says “Compatible " +
                "with a long-range drone of the war (attack or decoy)”, without percentages.",
            ],
          },
          {
            lista: [
              {
                termino: "Described features",
                texto: [
                  "The sources’ sentences are read for the shape (multirotor, fixed-wing, delta " +
                    "wing), the sound (propeller, combustion engine, jet), the size, lights, the " +
                    "number of aircraft, duration, altitude, speed, time and behaviour " +
                    "(hovering, circling, passing through, in formation). Each feature keeps the " +
                    "literal sentence and its source. What the text does not say is not assumed.",
                ],
              },
              {
                termino: "Calculation",
                texto: [
                  "It starts from how often each class appears in the cases of the same area " +
                    "(border or inland) where an authority identified the drone. Each feature " +
                    "raises or lowers the classes according to what the performance catalogue " +
                    "says about them, and physical constraints weigh in: the distance to " +
                    "Ukraine, Russia and Belarus (and to the coast) against each class’s range; " +
                    "the wind and temperature at that time and place; duration and altitude " +
                    "against endurance and ceiling; and speed: below 230 km/h, propeller; above " +
                    "300 km/h, jet; in between it does not decide.",
                ],
              },
              {
                termino: "Check",
                texto: [
                  "The calculation is repeated with each case of known answer held out (debris " +
                    "and official statements in Romania, Moldova, Poland, Lithuania, Latvia, " +
                    "Bulgaria and Turkey, and drone encounters classified by the UK Airprox " +
                    "Board) and compared with always saying the most frequent class. Only " +
                    "classes with at least 5 checked cases that beat that reference and give " +
                    "probabilities that hold are published. On 6 October 2026 the propeller " +
                    "long-range attack drone and the long-range decoy pass, at the border. " +
                    "Percentages for each class are only shown if the most likely one doubles " +
                    "the second and, in the cases of known answer where the method said so, it " +
                    "was right at least 8 times in 10 (with 5 cases at least). On 7 October 2026 " +
                    "no border case passes: attack drone and decoy cannot be told apart, so no " +
                    "percentages are shown. What does pass is that it was one of the two: in 22 " +
                    "of 24 cases. The calculated probabilities remain in the data export. The " +
                    "figures for each class are in docs/informe_tipo_y_rutas.md in the repository.",
                ],
              },
              {
                termino: "No basis",
                texto: [
                  "Without features that weigh in or an entry from outside at the border, " +
                    "without any reason to show, with the drone unconfirmed or with a most likely " +
                    "class that has not passed the check, the row does not appear.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "trafico",
        titulo: "Measured air traffic",
        bloques: [
          {
            parrafo: [
              "For incidents at airports with scheduled flights, the closure is measured with " +
                "real traffic: the daily archive of ",
              { texto: "adsb.lol", enlace: "https://adsb.lol/" },
              ", an open network of ADS-B receivers. Landings and take-offs by airliners and " +
                "business jets are counted in 15-minute slots and compared with the same slot " +
                "on the same weekday of the four previous weeks. A measured closure is a " +
                "stretch with 30% or less of the usual traffic that matches the incident; its " +
                "start and end are the last movement before the gap and the first one after.",
            ],
          },
          {
            parrafo: [
              "A diverted flight is one that was descending towards the airport and landed " +
                "at another, or one that landed at another airport with a flight number that " +
                "arrived there at that time in previous weeks. A holding flight is one that " +
                "flew holding patterns, found with the detector of the open traffic library. " +
                "If the measurement differs from what the sources say, both are shown.",
            ],
          },
          {
            parrafo: [
              "Coverage: each day what adsb.lol sees at each airport is compared with " +
                "EUROCONTROL's reference IFR flights, and gaps are read at the airports and on " +
                "the days where half or more is seen. Each gap is checked against the airport's " +
                "METARs: those explained by the weather (fog, thunderstorm, snow, strong wind or " +
                "a contaminated runway) are set aside. The measured closure is shown next to " +
                "the incident it matches.",
            ],
          },
          {
            parrafo: [
              "The record carries the measured closure when the incident is at an airport with " +
                "scheduled flights, adsb.lol published the full day, coverage at that airport " +
                "that day is sufficient, there are four weeks of baseline and a gap matches the " +
                "incident. Every value comes from the measurement; none is estimated.",
            ],
          },
        ],
      },
      {
        id: "directo",
        titulo: "Live closure detection",
        bloques: [
          {
            parrafo: [
              `Every ${UMBRALES_DIRECTO.cicloS} seconds the positions of aircraft around the ` +
                "monitored airports (those with high coverage on all four days of their " +
                "baseline in the daily archive) are requested from ",
              { texto: "adsb.lol", enlace: "https://adsb.lol/" },
              "; if it does not answer, the service switches by itself to ",
              { texto: "adsb.fi", enlace: "https://adsb.fi/" },
              ". From those positions arrivals and departures are rebuilt, with the same rules " +
                `as the measured traffic and a delay of ${UMBRALES_DIRECTO.retrasoMin} minutes so that each ` +
                "movement is complete, and compared with the median of the same weekday and " +
                "the same local time over the four previous weeks.",
            ],
          },
          {
            lista: [
              {
                termino: "Possible closure in progress",
                texto: [
                  `Since the last movement at least ${UMBRALES_DIRECTO.esperadosMin} expected movements are ` +
                    `missing, at most ${UMBRALES_DIRECTO.fraccionVistos} of them are seen, the shortfall ` +
                    `grows by at least ${UMBRALES_DIRECTO.ritmo.replace(",", ".")} movements per minute of gap, no ` +
                    "aircraft is taking off or landing, all of it for " +
                    `${UMBRALES_DIRECTO.persistenciaMin} minutes, and no METAR since one hour ` +
                    "before explains it (fog, visibility, ceiling, thunderstorm, snow, strong wind " +
                    "or a contaminated runway).",
                ],
              },
              {
                termino: "Closure confirmed",
                texto: ["An official source or an incident in the database reports the closure."],
              },
              {
                termino: "Operations resumed",
                texto: [
                  `At least ${UMBRALES_DIRECTO.reanudacion} movements return and half or more of the ` +
                    "expected traffic is seen over the last half hour. The alert stays on the map " +
                    `for ${UMBRALES_DIRECTO.permanenciaH} hours.`,
                ],
              },
            ],
          },
          {
            parrafo: [
              "Each alert keeps its detection time, its evidence (expected and seen movements, " +
                "missing arrivals and departures, aircraft holding and diverted flights) and, " +
                "once it arrives, the time of the first news, which gives the detection's lead. " +
                "An alert triggers the directed news search; once confirmed, the incident " +
                "enters the database through the normal flow with the measured closure.",
            ],
          },
        ],
      },
      {
        id: "gnss",
        titulo: "GPS interference",
        bloques: [
          {
            parrafo: [
              "Every ADS-B position carries its integrity (NIC) and accuracy (NACp). An " +
                "aircraft has a degraded position in a zone on a day if any of its positions " +
                "there has NIC below 7 or NACp below 8, the minimums of the ADS-B Out rule. " +
                "Zones are H3 hexagons at resolution 4 (about 1,770 km²), the grid of " +
                "gpsjam.org. The share of aircraft affected subtracts one degraded aircraft, so " +
                "that a single faulty unit does not colour the zone: (degraded − 1) / aircraft.",
            ],
          },
          {
            parrafo: [
              "Each zone on the map gathers 20 or more aircraft in the day. Levels: under 2% " +
                "no interference, 2 to 10% medium and over 10% high, in grey that gets lighter " +
                "with the share and the high level in red. For a period, aircraft " +
                "and degraded aircraft are added up per zone over each day (each month for " +
                "periods longer than 7 days). It is computed on the server from the daily " +
                "adsb.lol archive. “Europe now” counts the zones with high " +
                "interference on the latest published day; the layer legend counts, with the " +
                "same calculation, those of the chosen period.",
            ],
          },
        ],
      },
      {
        id: "presion",
        titulo: "Pressure by country",
        bloques: [
          {
            parrafo: [
              "Each country is filled in grey by its incidents in the selected period, with " +
                "the active filters: five steps relative to the country with the most. The " +
                "trend compares with the previous period of the same length: stable if the " +
                "difference is zero, or one and no more than 10% of the previous figure; " +
                "otherwise up or down, with the figure. Tapping a country shows its figures by " +
                "type and by status and its incidents.",
            ],
          },
          {
            parrafo: [
              "The figures per country count the incidents recorded from what each country's " +
                "media and authorities publish openly, in the languages the collection reads.",
            ],
          },
        ],
      },
      {
        id: "frontera",
        titulo: "Border or interior",
        bloques: [
          {
            parrafo: [
              "The map shows two different things: war drones crossing or falling near the border with Ukraine, Russia (including Kaliningrad) or Belarus or on the Black Sea coast, and drones over airports, bases and facilities in the interior of Europe. The “Where” filter shows all of them, only border ones or only interior ones; the header figures follow it. Each incident shows its group and the rule that decides it.",
            ],
          },
          {
            lista: [
              { termino: "1. Attack", texto: ["If the incident is linked to that night’s Russian attack on Ukraine, it is a border incident."] },
              {
                termino: "2. Distance",
                texto: [
                  "With a point: border if it is 150 km or less from the land border with Ukraine, Russia or Belarus, or 50 km or less from the Black Sea coast; otherwise interior. The cut comes from the data: of the incidents with a point, those in the band reach 144 km (incursions into Poland, Romania and Lithuania) and the next one is at 191 km (Bucharest airport).",
                ],
              },
              { termino: "3. Named place", texto: ["Without a point, the same distance from the place in the country named by its locality, its region or its headline; a headline placing it in the Black Sea makes it a border incident."] },
              {
                termino: "4. No place",
                texto: [
                  "Border if the drone came from outside (incursion, entry from abroad or a state drone) into a country bordering Ukraine, Russia or Belarus or with a Black Sea coast, or if the whole country is 150 km or less from that border (Moldova). Otherwise interior.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "prevision",
        titulo: "Forecast and trends",
        bloques: [
          {
            parrafo: [
              "The “Forecast” button says what is happening more than usual and what is likely to happen. Only what has passed a check against the past is published: each figure is computed with the data before a date and compared with what happened afterwards, moving forward in time, never using future data. It is compared with two simple references, the country’s usual frequency and “tomorrow same as today”, and published only if it does better than both and the improvement holds when the check is repeated with randomly drawn weeks. What does not pass is not shown. With little data nothing is claimed.",
            ],
          },
          {
            lista: [
              {
                termino: "Tonight at the border",
                texto: [
                  "Probability that a war drone crosses into or falls in the country the next night (at least one border incident that night). It is computed before the night, using only what is already known: the drones launched at Ukraine on average over the last three nights (Ukrainian Air Force reports), how many of the last seven nights had drones launched from Crimea and the country’s border incidents in the previous seven days. It is a logistic regression refitted every month. It is said as “2 in 10 nights like this one (20%)”, with the country’s usual rate (nights with a drone among the nights checked, the same figure as in the check) and the factors that raise or lower today’s risk against their usual value; those that do not change it are not listed. The check says how many of the nights with a drone were among the quarter of nights with the highest risk, and is folded under “How it is checked”. It is shown for each country where it passes the check.",
                ],
              },
              {
                termino: "Second night",
                texto: [
                  "After a large wave over Ukraine (drones launched reach the 90th percentile of the previous 60 nights), the probability that the next night is large too. It is shown only on those nights and only while its check supports it.",
                ],
              },
              {
                termino: "Streaks by country",
                texto: [
                  "A country’s normal is the average of its weeks over the last year without the last four. There is a streak when the last four weeks add up to more than normal gives 1 time in 20 (negative binomial with the country’s own dispersion), with at least 3 incidents on 2 or more different days. It counts events, not news: each incident once, on the date it happened. A country with fewer than 5 incidents in its normal year has no streak. It says since when, how many incidents against the usual and whether it is growing (the last two weeks exceed the two before) or fading. The check: after a streak is flagged, the following week looks more like the streak than like normal.",
                ],
              },
              {
                termino: "What has changed",
                texto: [
                  "The share of each target type among the impacts on Ukraine with a known target (only from the official channels that give impacts in every quarter since January 2025, so that a channel that starts or stops naming places does not change the mix) and the share of each incident type in Europe, over the last three closed months against the previous twelve. Only what has really changed is listed: outside what the usual share gives 1 time in 20, with a difference of 3 points or more. The share is used, not the count, because the count for a month depends on how many sources are read. Check: after a change is flagged, the following month looks more like the recent months than like the usual. Not by region of Ukraine: each region is counted by a single channel, and a regional change cannot be told apart from a change in coverage.",
                ],
              },
              {
                termino: "Mix of each wave",
                texto: [
                  "In the Ukraine layer, each attack’s sheet and “Night by night” say how many of the drones launched were Shahed or Geran and how many were jet-powered when the Ukrainian Air Force report says so; the rest are Gerbera decoys and other types. They are minimums and come only from the official reports. The Ukraine text page has the mix month by month.",
                ],
              },
              {
                termino: "How it is scored",
                texto: [
                  "Probabilities with the Brier score (the squared error between the probability and what happened). In each part, “How it is checked” says how many nights or weeks it was checked against and, at the border, what happened in each probability band. Forecasts for the nights before publication are reconstructed as they would have been made then.",
                ],
              },
              {
                termino: "Live record",
                texto: [
                  "Since 6 October 2026 each forecast is stored with its time before the result is known (the border one, at the first update from 17:00 UTC) in a record that admits no changes or deletions, and scored once the result is known (3 days after the night). It is in the published file prevision.json and in the data export, with its method and date.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "licencias",
        titulo: "Licences and attributions",
        bloques: [
          {
            lista: [
              {
                termino: "Code",
                texto: [{ texto: "Apache-2.0", enlace: `${REPOSITORIO}/blob/main/LICENSE` }, "."],
              },
              {
                termino: "Data",
                texto: [
                  { texto: LICENCIA_DATOS, enlace: LICENCIA_DATOS_URL },
                  ". Source sentences belong to their authors and are reproduced as short " +
                    "quotations next to the link.",
                ],
              },
              {
                termino: "Base map",
                texto: [
                  "© ",
                  { texto: "OpenStreetMap", enlace: "https://www.openstreetmap.org/copyright" },
                  " contributors (ODbL), with tiles and style by ",
                  { texto: "Protomaps", enlace: "https://protomaps.com/" },
                  ".",
                ],
              },
              {
                termino: "Borders and regions",
                texto: [
                  { texto: "Natural Earth", enlace: "https://www.naturalearthdata.com/" },
                  ", public domain.",
                ],
              },
              {
                termino: "News",
                texto: [{ texto: "GDELT", enlace: "https://www.gdeltproject.org/" }, "."],
              },
              {
                termino: "Places",
                texto: [
                  { texto: "GeoNames", enlace: "https://www.geonames.org/" },
                  " (CC BY 4.0).",
                ],
              },
              {
                termino: "Air traffic",
                texto: [
                  "© adsb.lol contributors (",
                  { texto: "adsb.lol", enlace: "https://adsb.lol/" },
                  "), ",
                  { texto: "ODbL 1.0", enlace: "https://opendatacommons.org/licenses/odbl/1-0/" },
                  ". The air traffic block of the published files is derived from those data " +
                    "and is offered under the same licence. Airports and runways from ",
                  { texto: "OurAirports", enlace: "https://ourairports.com/data/" },
                  " (public domain); coverage reference from EUROCONTROL (Aviation " +
                    "Intelligence Portal), not published; holding patterns with the method of " +
                    "the ",
                  { texto: "traffic", enlace: "https://github.com/xoolive/traffic" },
                  " library (MIT, © Xavier Olive).",
                ],
              },
              {
                termino: "Real-time traffic",
                texto: [
                  "© adsb.lol contributors (",
                  { texto: "adsb.lol", enlace: "https://adsb.lol/" },
                  "), ",
                  { texto: "ODbL 1.0", enlace: "https://opendatacommons.org/licenses/odbl/1-0/" },
                  "; and, as backup, ",
                  { texto: "adsb.fi", enlace: "https://adsb.fi/" },
                  ".",
                ],
              },
              {
                termino: "Weather",
                texto: [
                  { texto: "Weather data by Open-Meteo.com", enlace: "https://open-meteo.com/" },
                  " (CC BY 4.0) and METARs from the ",
                  {
                    texto: "Iowa Environmental Mesonet",
                    enlace: "https://mesonet.agron.iastate.edu/",
                  },
                  " of Iowa State University.",
                ],
              },
              {
                termino: "Satellite images",
                texto: [
                  "Contains modified Copernicus Sentinel data (",
                  {
                    texto: "Sentinel-2 L2A on AWS",
                    enlace: "https://registry.opendata.aws/sentinel-2-l2a-cogs/",
                  },
                  "). Night lights: NOAA-20 VIIRS, ",
                  { texto: "NOAA Open Data Dissemination", enlace: "https://registry.opendata.aws/noaa-jpss/" },
                  ".",
                ],
              },
              {
                termino: "Thermal hotspots",
                texto: [
                  "We acknowledge the use of data and/or imagery from NASA's Fire " +
                    "Information for Resource Management System (FIRMS) (",
                  {
                    texto: "https://www.earthdata.nasa.gov/firms",
                    enlace: "https://www.earthdata.nasa.gov/firms",
                  },
                  "), part of NASA's Earth Science Data and Information System (ESDIS).",
                ],
              },
            ],
          },
        ],
      },
    ],
    descargas: {
      titulo: "Open data",
      intro:
        "The data can be downloaded and reused with attribution. It is rebuilt with " +
        "every update.",
      incidentes: "Incidents",
      ucrania: "Attacks in the Ukraine layer",
      sinUbicacion: "Incidents with an approximate location",
      version: (fecha) => `Version of ${fecha}`,
      licencia: "Licence",
      licenciaTexto:
        `The observatory’s compilation (the incidents, their statuses, their classifications and their figures) is published under the ${LICENCIA_DATOS} licence: it can be copied, transformed and reused, also for commercial purposes, citing the source as shown below. Quoted sentences remain their authors’ and are used as quotations, with their source and link. The measured air traffic block (trafico_aereo) derives from the adsb.lol archive and is offered under its licence, ODbL 1.0.`,
      citaTitulo: "Recommended citation",
      cita: (version) => citaRecomendada(version, "en"),
      autoriaTitulo: "Authorship",
      contacto: "Contact",
    },
    versiones: {
      titulo: "Citable versions",
      intro:
        "On the 1st of every month a version of the open data is frozen: the same files, with their date and fingerprint, at an address that does not change. A published version is never modified or deleted: it is there to cite exactly the data that was used.",
      ninguna: "The first citable version will be published as soon as it is generated.",
      linea: (version, fecha, incidentes) => `Version ${version}, frozen on ${fecha}, with ${incidentes} incidents`,
      citaTitulo: "How to cite this version",
      copiar: "Copy the citation",
      copiada: "Citation copied",
      tituloVersion: (version) => `Open data, version ${version}`,
      descripcionVersion: (version) => `Version ${version} of the open data of the ${NOMBRE}: frozen files with their SHA-256 fingerprint, their licence and how to cite it.`,
      congelada: (fecha, datos, incidentes) => `Frozen on ${fecha} with the data published on ${datos}: ${incidentes} incidents.`,
      fija: "This version does not change and is not deleted. Each file carries its SHA-256 fingerprint: if the file you have gives the same fingerprint, it is exactly the one in this version.",
      fichero: "File",
      bytes: "Bytes",
      huella: "SHA-256",
      comoComprobar: "To check a file: sha256sum <file> (Linux), shasum -a 256 <file> (macOS) or certutil -hashfile <file> SHA256 (Windows).",
      todas: "All versions",
    },
    sobre: "About the observatory",
  },
  compartir: {
    titulo: `${NOMBRE} · Drone incidents in Europe`,
    tituloIncidente: (titulo) => `${titulo} · ${NOMBRE}`,
    tituloAtaque: (id) => `Attack ${id} · ${NOMBRE}`,
    altImagen: `${NOMBRE} logo and name over the map of Europe with the recorded incidents`,
    lema: "Drone incidents in Europe, with their sources and level of confirmation",
  },
  regiones: {
    ...REGIONES_RUSIA_EN,
    "UA-05": "Vinnytsia",
    "UA-07": "Volyn",
    "UA-09": "Luhansk",
    "UA-12": "Dnipropetrovsk",
    "UA-14": "Donetsk",
    "UA-18": "Zhytomyr",
    "UA-21": "Zakarpattia",
    "UA-23": "Zaporizhzhia",
    "UA-26": "Ivano-Frankivsk",
    "UA-30": "Kyiv (city)",
    "UA-32": "Kyiv (region)",
    "UA-35": "Kirovohrad",
    "UA-40": "Sevastopol",
    "UA-43": "Crimea",
    "UA-46": "Lviv",
    "UA-48": "Mykolaiv",
    "UA-51": "Odesa",
    "UA-53": "Poltava",
    "UA-56": "Rivne",
    "UA-59": "Sumy",
    "UA-61": "Ternopil",
    "UA-63": "Kharkiv",
    "UA-65": "Kherson",
    "UA-68": "Khmelnytskyi",
    "UA-71": "Cherkasy",
    "UA-74": "Chernihiv",
    "UA-77": "Chernivtsi",
  },
  satelite: {
    capas: "War layer",
    corredores: "Corridors",
    principales: {
      principales: (n, total) => `${n} of ${total} corridors, those with the most drones; width and intensity show the drones.`,
      todos: (total) => `All ${total} corridors in the period; width and intensity show the drones.`,
      verTodos: (total) => `Show all ${total}`,
      verPrincipales: "Show only the main ones",
    },
    letreroCorredor: (origen, region, drones) => `${origen} → ${region} · ${drones} drones`,
    letreroAlumbrado: (ciudad) => `${ciudad} · permanently reduced street lighting`,
    letreroCiudad: (ciudad, perdida) => `${ciudad} · ${perdida}% less night light`,
    corredor: {
      etiqueta: "Attack corridor · war layer",
      origen: "Origin",
      destino: "Destination",
      desdeUcrania: "Ukraine",
      desdeUcraniaTexto:
        "The arc starts at the point of the Ukrainian border closest to the region; the figure " +
        "is the Russian report's shoot-downs for the region.",
      drones: "Drones in the period",
      dronesTexto: {
        RU_UA:
          "Drones launched in the attacks of the period that came from this zone (among others, " +
          "when the report names several) and reached this region, according to the Ukrainian " +
          "Air Force.",
        UA_RU: "Drones the Russian Ministry of Defence says it shot down over the region.",
      },
      ataques: (n) => (n === 1 ? "1 attack" : `${n} attacks`),
      periodo: "Period",
      varios: "Several corridors meet at that point. Choose one:",
      etiquetaVarios: "Corridors · war layer",
      lista: "Attack corridors in the period",
    },
    luzFicha: {
      etiqueta: "Night lights · war layer",
      rotulo: "Night lights",
      perdida: (pct) => `${pct}% less light`,
      peorNoche: (fecha) => `on the night of ${fecha}`,
      noches: (n) => (n === 1 ? "1 night with loss" : `${n} nights with loss`),
      referencia: (desde, hasta, n) =>
        `against the median of ${n} cloud-free nights from ${desde} to ${hasta}`,
      origen: "Measured by satellite",
      ataque: "Attack",
      region: "Region",
      regionEntera: "sum of its measured cities",
      sinPerdida: "No night-light loss measured in the period.",
      metodo:
        "Brightness above background in the VIIRS day-night band (NOAA-20), cloud-free nights. " +
        "Nights are dated by their evening; the satellite passes at about 01:30 local time.",
    },
    alumbradoFicha: {
      etiqueta: "Reduced lighting · war layer",
      titulo: "City with permanently reduced street lighting",
      desde: "Since",
      desdeTexto: (fecha, alMenos) => (alMenos ? `at least since ${fecha}` : fecha),
      porEncima: (mes) => `In ${mes} it was still above the minimum reference.`,
      actual: "Current brightness",
      referencia: "Reference brightness",
      brillo: (valor) => `${valor} nW/(cm²·sr)`,
      tramo: (desde, hasta, noches) =>
        `median of ${noches} valid nights from ${desde} to ${hasta}`,
      noches: "Nights measured",
      metodo:
        "Below 0.5 nW/(cm²·sr) above the background, sustained over time, the city is almost " +
        "dark and a blackout cannot be seen from the satellite. Reference brightness: the " +
        "earliest measured. VIIRS on NOAA-20; a single month above (snow) does not count.",
    },
    imagen: {
      rotulo: "Satellite image",
      antes: "Before",
      despues: "After",
      deslizador: "Compare the before and after images",
      escena: (id) => `scene ${id}`,
      nubes: (pct) => `${pct}% cloud over the crop`,
      producto: (lado) => `Sentinel-2 L2A, natural colour, 10 m per pixel, ${lado} km crop`,
      alt: (momento, fecha) => `Satellite image ${momento} the attack, ${fecha}`,
      descripcion: (lado, antes, despues, hectareas) =>
        `Two natural-colour satellite images of the same ${lado} km crop, one from ${antes} and one from ${despues}, ` +
        `overlaid with a slider. The area that changed between them, ${hectareas} hectares, is outlined.`,
      posicion: (despues) => `${100 - despues}% of the before image and ${despues}% of the after image in view`,
      zonaCambio: (hectareas, antes, despues) =>
        `Area with changes: ${hectareas} hectares · before ${antes} · after ${despues}`,
      ocultarContorno: "Hide outline",
      verContorno: "Show outline",
    },
    zona: (id, nombre) => ZONAS_EN[id] ?? nombre,
    ayudaCorredores:
      "A thin violet arc runs from a launch zone to a region reached: thicker means more drones " +
      "in the period. Towards Russia it starts at the nearest point of the Ukrainian border. " +
      "Moving the pointer or a finger close to an arc is enough: it lights up and takes " +
      "precedence over the region below; the Tab key goes through them one by one.",
    ayudaSubcapas:
      "The Ukraine layer shows its regions and strikes. «Corridors» and «With satellite» are " +
      "switched on with their own button (and off with it); turning the Ukraine layer off turns " +
      "them off too.",
    tipos: {
      cortinilla: "before and after",
      foco: "fire hotspot",
      apagon: "blackout",
      oscura: "darkened city",
    },
    leyendaTipos: {
      cortinilla: "Before and after with visible change",
      foco: "Fire hotspot matching a strike",
      apagon: "City that lost light after an attack",
      oscura: "City with permanently reduced lighting",
    },
    leyenda: "Legend",
    filtrar: "Filter the list by type",
    ayudaLuz:
      "With «With satellite»: a darkened region or city lost night light after an attack on the " +
      "power grid, measured by satellite (blackout): darker means a larger loss.",
    ayudaAlumbrado:
      "With «With satellite»: a ring with a light dot is a darkened city, with permanently " +
      "reduced street lighting: its night brightness has long been below the minimum needed to " +
      "measure a blackout.",
    ayudaSatelite:
      "A larger strike with a light rim has satellite information: a second ring means a " +
      "before-and-after image in which the change can be seen; the hotspot mark, a fire hotspot " +
      "matching it. Always on top of the rest; a cluster holding one has a light rim. «With " +
      "satellite» turns on the four types (before and after, hotspot, blackout and darkened " +
      "city), dims the rest and opens their legend and their list, which can be filtered by type.",
    conSatelite: (n) => `With satellite · ${n}`,
    verLista: (n) => `List · ${n}`,
    rotuloCapas: "Ukraine layer",
    listaSatelite: "Points with satellite information",
    abrirLista: "Open the list of points with satellite information",
    cerrarLista: "Close the list of points with satellite information",
    letreroSatelite: (imagen, foco) =>
      `Strike with satellite · ${[imagen ? "before and after" : null, foco ? "fire hotspot" : null]
        .filter((x) => x !== null)
        .join(" · ")}`,
  },
};

/** Zonas de lanzamiento (configuracion/zonas_lanzamiento.json) en inglés. */
const ZONAS_EN: Record<string, string> = {
  primorsko_akhtarsk_aerodromo: "Primorsko-Akhtarsk air base",
  primorsko_akhtarsk_droneport: "Primorsko-Akhtarsk, drone port by the air base",
  kursk_khalino: "Kursk (Khalino / Kursk-Vostochny)",
  oryol_yuzhny: "Oryol (Oryol-Yuzhny airfield)",
  tsymbulove: "Tsimbulova, Oryol region (large drone port)",
  bryansk: "Bryansk",
  millerovo: "Millerovo",
  hvardiiske: "Hvardiiske, occupied Crimea",
  cabo_chauda: "Cape Chauda, occupied Crimea (test range)",
  shatalovo: "Shatalovo",
  donetsk_ocupado: "Occupied Donetsk",
  donetsk_aeropuerto: "Donetsk international airport (occupied)",
  yeysk: "Yeysk (storage and launch preparation site by the air base)",
  balaklava: "Balaklava, occupied Crimea",
  kacha: "Kacha, occupied Crimea",
  seshcha: "Seshcha",
  dzhankoi: "Dzhankoi, occupied Crimea",
  belbek: "Belbek, occupied Crimea",
  engels: "Engels",
  berdiansk: "Berdiansk (occupied)",
  prymorsk: "Prymorsk, Zaporizhzhia province (occupied)",
  navlia: "Navlya, Bryansk region",
};
