import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN, REPOSITORIO } from "../sitio.ts";
import type { Textos } from "./tipos.ts";

export const en: Textos = {
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
    },
    estadoFuente: { leida: "read", con_aviso: "with warning", no_leida: "not read" },
    ultimoDato: "latest data",
    sinUltimoDato: "no data yet",
    nuncaCorrecta: "No successful collection",
    siguienteEn: (minutos) => (minutos <= 0 ? "running now" : `in ${minutos} min`),
  },
  avisos: {
    cargando: "Loading data…",
    datosNoValidos:
      "The published data does not match the schema and is not shown. It will be shown " +
      "again once the next update fixes it.",
    datosNoDisponibles: "The data could not be loaded. Please try again later.",
    fichaNoEncontrada: "There is no record with this identifier.",
    fichaNoValida: "This record does not match the schema and is not shown.",
    mapaNoDisponible:
      "The map cannot be drawn in this browser. The incident list is still available.",
  },
  filtros: {
    titulo: "Filters",
    graves: "Only confirmed and attributed",
    ultimas24h: "Last 24 hours",
    ultimos7d: "Last 7 days",
    tipo: "Type",
    pais: "Country",
    todosLosPaises: "All countries",
    estado: "Status",
    quitar: "Clear filters",
    recientes: "Period",
    activos: (n) => `${n} active`,
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
  },
  relativo: (minutos, fecha) => {
    if (minutos < 1) return "just now";
    if (minutos < 60) return `${minutos} min ago`;
    const horas = Math.floor(minutos / 60);
    if (horas < 24) return `${horas} h ago`;
    const dias = Math.floor(horas / 24);
    return dias < 30 ? `${dias} ${dias === 1 ? "day" : "days"} ago` : `on ${fecha}`;
  },
  novedades: {
    aviso: (n) => (n === 1 ? "1 update since your last visit" : `${n} updates since your last visit`),
    recorrer: "Show me",
    siguiente: "Next",
    anterior: "Previous",
    descartar: "Dismiss",
    posicion: (i, n) => `${i} of ${n}`,
  },
  ayuda: {
    titulo: "How to read the map",
    cerrar: "Close help",
    formas: "The shape shows the type of incident.",
    colores: "The colour shows the status. Denied incidents have a dashed outline and no fill.",
    areas: "Each incident covers an area: the circle is the radius within which it is known to have happened.",
    lineas: "A thin line joins the incidents of one episode: several targets on the same night.",
    numeros:
      "A circle with a number groups several incidents: it grows with the number, and its ring " +
      "takes the colour of the most serious status inside. Zoom in and they separate.",
    pila: "If the incidents share the exact same spot, tap the circle to choose which one to open.",
    pulsos:
      "Confirmed and attributed incidents pulse slowly; attributed ones a little more. " +
      "Reported incidents are dimmer.",
    reciente: "A soft glow marks what started in the last 24 hours.",
    novedad: "A ring in the interface colour marks what has changed since your last visit.",
    ucrania: "In the Ukraine layer, each region is shaded by the attacks that name it in the period.",
    atajos: "Keyboard shortcuts",
    acciones: {
      ayuda: "Open or close this help",
      cerrar: "Close the record or the open panel, or clear the selected period",
      capaIncidentes: "Incidents layer",
      capaUcrania: "Ukraine layer",
      capaDensidad: "Density layer",
      filtroGraves: "Confirmed and attributed only",
      filtro24h: "Last 24 hours",
      filtro7d: "Last 7 days",
      sinFiltros: "Clear filters",
      lineaTiempo: "Open or close the timeline",
      reproducir: "Play the timeline",
      feed: "Open or close the live panel",
      lista: "Incident list",
      metodologia: "Methodology and open data",
    },
  },
  pila: { titulo: (n) => `${n} incidents at this spot` },
  imprecisa: {
    etiqueta: "imprecise location",
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
    noche: (fecha) => `Night of ${fecha}`,
    drones: "drones launched against Ukraine",
    sinCifra: "no launch figure",
  },
  mapa: {
    etiqueta: "Map of Europe with the incidents of the selected period",
    instrucciones:
      "With focus on the map, the arrow keys pan and the plus and minus keys zoom. The " +
      "incident list opens the same records without using the map.",
    grupo: (n) => (n === 1 ? "1 incident: zoom in to see it" : `${n} incidents: zoom in to see them`),
    pila: (n) => `${n} incidents at this exact spot: tap to choose one`,
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
    estado: "Status",
    presenciaDron: "Drone presence",
    fecha: "Date",
    lugar: "Place",
    radio: (km) => `area of ${km} km radius`,
    drones: "Drones",
    duracion: "Duration",
    efecto: "Effect",
    respuesta: "Response",
    atribucion: "Attribution",
    atribuidoA: (actor, autoridad) => `${actor}, according to ${autoridad}`,
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
    incluidoEn: "Figures included in report",
    solapadoCon: "Overlaps with report",
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
      "only counted when the report breaks them down.",
  },
  lista: {
    titulo: "Incident list",
    incidentes: (n) => (n === 1 ? "1 incident in the period" : `${n} incidents in the period`),
    vacia: "No incidents in the selected period.",
    regiones: "Regions of Ukraine",
  },
  tiempo: {
    titulo: "Timeline",
    granularidad: "Group by",
    porGranularidad: { dia: "Day", semana: "Week", mes: "Month" },
    reproducir: "Play",
    pausar: "Pause",
    reanudar: "Resume",
    detener: "Stop",
    verTodo: "Show all",
    periodoBoton: "Period",
    desde: "Start of the period",
    hasta: "End of the period",
    periodo: (desde, hasta) => `${desde} – ${hasta}`,
    incidentesPorTramo: "Incidents",
    lanzamientosPorNoche: "Drones launched against Ukraine",
    instrucciones:
      "Drag across the histogram to choose a period, or move either end with the arrow keys.",
    plegar: "Collapse",
    desplegar: "Expand",
    acotado: "period narrowed",
    maximo: (n) => `max ${n}`,
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
                "position is almost never known. Every piece of data keeps who says it: for " +
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
                marca: { tipo: "interrupcion_aeroportuaria" },
                texto: [
                  "An airport closes or has flights diverted, cancelled or delayed. When it " +
                    "applies, this type takes precedence over the others.",
                ],
              },
              {
                termino: "Incursion",
                marca: { tipo: "incursion" },
                texto: [
                  "The drone enters from outside the country and its origin is proven by " +
                    "tracking or by debris. A sighting with no proven origin is never an " +
                    "incursion.",
                ],
              },
              {
                termino: "Overflight",
                marca: { tipo: "sobrevuelo" },
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
                texto: ["The news reports it. It is the initial status of every incident."],
              },
              {
                termino: "Confirmed",
                marca: { estado: "confirmado" },
                texto: ["An authority states that the incident happened."],
              },
              {
                termino: "Attributed",
                marca: { estado: "atribuido" },
                texto: [
                  "An authority names a government as responsible. The record says who " +
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
                "with both colour and text.",
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
              "Status says whether the incident happened; drone presence says whether a " +
                "drone is known to have been there. They are two different questions. " +
                "Presence is confirmed when there is debris, radar tracking or an authority " +
                "that states it explicitly; not confirmed when there are only sightings; and " +
                "ruled out when an authority denies it.",
            ],
          },
          {
            parrafo: [
              "The Copenhagen case shows the difference. In September 2025 the airport " +
                "closed for several hours after drones were reported. The closure is a fact " +
                "the authority confirms, but that what was seen were drones is a separate " +
                "claim: without debris or tracking, an incident can be confirmed while drone " +
                "presence remains unconfirmed.",
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
                "incident.",
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
                "confirms the incident if the authority states that it happened; it confirms " +
                "drone presence only if it states there were drones, not if it refers to " +
                "reports received; and it denies or attributes the incident if that is what " +
                "it says.",
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
            ],
          },
        ],
      },
      {
        id: "sesgo",
        titulo: "Coverage bias",
        bloques: [
          {
            parrafo: [
              "The number of incidents in a country depends on how much its media publish, " +
                "on which languages are read best and on whether its authorities report " +
                "openly. A country with more records does not necessarily have more " +
                "incidents: it has more news. The figures cannot be used to compare " +
                "countries without taking this into account.",
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
      sinUbicacion: "Incidents with an imprecise location",
      version: (fecha) => `Version of ${fecha}`,
      licencia: "Licence",
      citaTitulo: "Recommended citation",
      cita: (fecha) =>
        `${NOMBRE} (EODI). Drone incidents in Europe, version of ${fecha}. ` +
        `${ORIGEN}. Licence ${LICENCIA_DATOS}.`,
    },
  },
  compartir: {
    titulo: `${NOMBRE} · Drone incidents in Europe`,
    tituloIncidente: (titulo) => `${titulo} · ${NOMBRE}`,
    tituloAtaque: (id) => `Attack ${id} · ${NOMBRE}`,
    altImagen: `${NOMBRE} logo and name over the map of Europe with the recorded incidents`,
    lema: "Drone incidents in Europe, with their sources and level of confirmation",
  },
  regiones: {
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
};
