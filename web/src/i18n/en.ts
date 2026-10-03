import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN, REPOSITORIO } from "../sitio.ts";
import { REGIONES_RUSIA_EN } from "./regionesRusia.ts";
import type { Textos } from "./tipos.ts";
import { UMBRALES_DIRECTO } from "./umbrales.ts";

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
  ahora: {
    etiqueta: "Europe now",
    cierres: "airport closures in progress",
    incidentes: "incidents in 7 days",
    drones: "drones launched last night",
    focos: "confirmed thermal hotspots in 7 days",
    gnss: "GPS interference today",
    cortos: {
      cierres: "closures",
      incidentes: "7 days",
      drones: "last night",
      focos: "hotspots 7 d",
      gnss: "GPS",
    },
    nivel: { sin: "no interference", media: "medium", alta: "high" },
    celdasAltas: (n) => (n === 1 ? "1 high cell" : `${n} high cells`),
    sinDato: "no figure",
    ir: (que) => `Show on the map: ${que}`,
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
    sinDatos: "No interference data for this period",
    cargando: "Loading interference…",
    letrero: (proporcion) => `GPS interference · ${proporcion} of aircraft`,
  },
  presion: {
    etiqueta: "Country · pressure",
    leyenda: "Incidents in the period",
    menos: "fewer",
    mas: "more",
    tendencia: { sube: "up", baja: "down", estable: "stable" },
    frente: (anterior) => `compared with ${anterior} in the previous period of equal length`,
    sinComparacion: "no previous period with data",
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
    posicion: (i, n) => `${i} of ${n}`,
  },
  ayuda: {
    titulo: "How to read the map",
    cerrar: "Close help",
    formas: "The shape shows the type of incident.",
    colores:
      "The colour shows the status: orange, reported; red, confirmed; red with a small flag, " +
      "attributed (a confirmed incident whose perpetrator a government has named). Denied " +
      "incidents have a dashed grey outline and no fill.",
    areas: "Each incident covers an area: the circle is the radius within which it is known to have happened.",
    lineas: "A thin line joins the incidents of one episode: several targets on the same night.",
    numeros:
      "A circle with a number groups several incidents: it grows with the number, and its ring " +
      "is red if it holds any confirmed or attributed incident and orange if all are reported. " +
      "Zoom in and they separate.",
    pila: "If the incidents share the exact same spot, tap the circle to choose which one to open.",
    pulsos:
      "Only what is new since your last visit pulses (and the circle that holds it): it stops " +
      "when you press “Show me” or “Dismiss” or open the incident. With the system's reduced " +
      "motion setting, it gets a fixed ring instead. Reported incidents are dimmer.",
    reciente: "A soft glow marks what started in the last 24 hours.",
    novedad: "Nothing pulses on a first visit: there is no earlier visit to compare with yet.",
    ucrania: "In the Ukraine layer, each region is shaded by the attacks that name it in the period.",
    rusia:
      "Russian regions are grey with a dashed outline: their figures are those of the " +
      "Russian Ministry of Defence, a claim by a party to the war.",
    impactos:
      "A small dot is a specific place hit (a town or a facility) according to the regional " +
      "administrations, the Ukrainian General Staff or Russian governors. Filled: official " +
      "source; ring only: claim by a party. Zoomed out, they group with their count. Daily " +
      "front-line reports are in the downloadable data.",
    foco:
      "A light dot next to an incident, a place hit or a group of places, or at the centre of a Ukrainian region, marks a " +
      "thermal hotspot detected by satellite (NASA FIRMS) at its place and time.",
    directo:
      "A dot with a ring and the ICAO code is an airport in the live detection, without pulse: " +
      "orange, possible closure in progress; red, closure confirmed; grey, operations resumed.",
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
    confirmadoAtribuido: (actor, autoridad) => `Confirmed · attributed to ${actor}, according to ${autoridad}`,
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
                  "A confirmed incident for which an authority names a government as " +
                    "responsible: red, with a small flag on the symbol. The record shows it as " +
                    "“Confirmed · attributed to…”, with who attributes it and to whom.",
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
                "aircraft has a degraded position in a cell on a day if any of its positions " +
                "there has NIC below 7 or NACp below 8, the minimums of the ADS-B Out rule. " +
                "Cells are H3 hexagons at resolution 4 (about 1,770 km²), the grid of " +
                "gpsjam.org. The share of aircraft affected subtracts one degraded aircraft, so " +
                "that a single faulty unit does not colour the cell: (degraded − 1) / aircraft.",
            ],
          },
          {
            parrafo: [
              "Each cell on the map gathers 20 or more aircraft in the day. Levels: under 2% " +
                "no interference, 2 to 10% medium and over 10% high, in grey that gets lighter " +
                "with the share and the high level in red. For a period, aircraft " +
                "and degraded aircraft are added up per cell over each day (each month for " +
                "periods longer than 7 days). It is computed on the server from the daily " +
                "adsb.lol archive. The level of the day in the “Europe now” strip is the one " +
                "reached by one cell in ten (the 90th percentile), next to the number of high cells.",
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
};
