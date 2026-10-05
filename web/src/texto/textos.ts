// Textos de las páginas que se leen sin ejecutar código (src/texto/paginas.ts), en los dos
// idiomas. Lo que ya dice la web (estados, tipos, ficha, metodología, ayuda) sale de src/i18n;
// aquí solo lo propio de estas páginas: navegación, títulos y rótulos de las listas.

import type { Estado, PresenciaDron } from "../datos/tipos.ts";
import { NOMBRE } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";

export interface TextosPagina {
  saltar: string;
  navegacion: string;
  /** Rótulos del menú de las páginas. */
  nav: { mapa: string; incidentes: string; paises: string; ucrania: string; metodologia: string; ayuda: string };
  otroIdioma: string;
  datosDe: (fecha: string) => string;
  licencia: string;
  codigo: string;
  portada: {
    titulo: string;
    descripcion: string;
    que: string[];
    cifras: string;
    incidentes: string;
    confirmados: string;
    atribuidos: string;
    paises: string;
    actualizado: string;
    ultimos: string;
    todos: string;
    mas: string;
    porAnio: string;
    porPais: string;
    descargas: string;
  };
  lista: {
    titulo: string;
    descripcion: (n: number) => string;
    anio: (anio: string) => string;
    descripcionAnio: (anio: string, n: number) => string;
    anios: string;
    numero: (n: number) => string;
    sinIncidentes: string;
  };
  pais: {
    titulo: string;
    descripcion: (n: number) => string;
    tituloDe: (pais: string) => string;
    descripcionDe: (pais: string, n: number) => string;
    cifras: string;
    lista: string;
    otros: string;
  };
  incidente: {
    descripcion: (estado: string, fecha: string, lugar: string) => string;
    significa: string;
    tipo: string;
    objetivo: string;
    verEnMapa: string;
    volver: string;
    todasLasFuentes: string;
    codigoFuente: string;
    sinFuentes: string;
    punto: string;
  };
  /** Qué quiere decir cada estado y cada presencia: el principio de su definición en la metodología. */
  estado: Record<Estado, string>;
  presencia: Record<PresenciaDron, string>;
  ucrania: {
    titulo: string;
    descripcion: string;
    capa: string;
    comoSeObtiene: string;
    fuentesDeLosPartes: string;
    sentido: { RU_UA: string; UA_RU: string };
    reivindicacion: string;
    totales: string;
    partes: string;
    lanzados: string;
    derribados: string;
    derribadosUaRu: string;
    impactos: string;
    porRegion: string;
    region: string;
    ataquesQueLaCitan: string;
    derribadosEnLaRegion: string;
    porMes: string;
    mes: string;
    corredores: string;
    corredoresIntro: string;
    origen: string;
    destino: string;
    drones: string;
    ataques: string;
    sinOrigen: string;
    metodologiaSatelite: string;
    periodo: (desde: string, hasta: string) => string;
  };
  metodologia: { titulo: string; descripcion: string; indice: string };
  ayuda: { titulo: string; descripcion: string; atajos: string; tecla: string; accion: string };
  noEncontrada: { titulo: string; texto: string; volver: string };
}

const ES: TextosPagina = {
  saltar: "Saltar al contenido",
  navegacion: "Secciones",
  nav: {
    mapa: "Mapa",
    incidentes: "Incidentes",
    paises: "Países",
    ucrania: "Guerra en Ucrania",
    metodologia: "Metodología y datos abiertos",
    ayuda: "Ayuda",
  },
  otroIdioma: "English",
  datosDe: (fecha) => `Datos publicados a ${fecha}`,
  licencia: "Datos con licencia",
  codigo: "Código abierto",
  portada: {
    titulo: `${NOMBRE} · Incidentes con drones en Europa`,
    descripcion:
      "Mapa y registro abierto de incidentes con drones en Europa: sobrevuelos, incursiones e " +
      "interrupciones de aeropuertos, con sus fuentes, su estado y su grado de confirmación.",
    que: [
      `El ${NOMBRE} registra incidentes con drones en Europa: aparatos no tripulados que ` +
        "sobrevuelan una instalación, entran en un espacio aéreo desde fuera o interrumpen el " +
        "funcionamiento de un aeropuerto.",
      "Cada incidente lleva sus fuentes con la frase de origen y el enlace, su estado " +
        "(notificado, confirmado, atribuido o desmentido) y el historial de cambios. Los datos " +
        "se actualizan cada hora y se pueden descargar.",
    ],
    cifras: "Cifras",
    incidentes: "Incidentes",
    confirmados: "Confirmados",
    atribuidos: "Atribuidos",
    paises: "Países",
    actualizado: "Última actualización",
    ultimos: "Últimos incidentes",
    todos: "Todos los incidentes",
    mas: "Más",
    porAnio: "Incidentes por año",
    porPais: "Incidentes por país",
    descargas: "Descargar los datos",
  },
  lista: {
    titulo: "Todos los incidentes",
    descripcion: (n) => `Los ${n} incidentes con drones en Europa publicados, del más reciente al más antiguo.`,
    anio: (anio) => `Incidentes de ${anio}`,
    descripcionAnio: (anio, n) => `Los ${n} incidentes con drones en Europa publicados de ${anio}.`,
    anios: "Por año",
    numero: (n) => (n === 1 ? "1 incidente" : `${n} incidentes`),
    sinIncidentes: "No hay incidentes publicados.",
  },
  pais: {
    titulo: "Incidentes por país",
    descripcion: (n) => `Los ${n} países con incidentes con drones publicados.`,
    tituloDe: (pais) => `Incidentes con drones en ${pais}`,
    descripcionDe: (pais, n) => `Los ${n} incidentes con drones publicados en ${pais}, con su estado y sus fuentes.`,
    cifras: "Cifras",
    lista: "Incidentes",
    otros: "Otros países",
  },
  incidente: {
    descripcion: (estado, fecha, lugar) => `${estado}. ${fecha}. ${lugar}.`,
    significa: "Qué significa",
    tipo: "Tipo",
    objetivo: "Instalación",
    verEnMapa: "Ver en el mapa",
    volver: "Todos los incidentes",
    todasLasFuentes: "Fuentes y citas",
    codigoFuente: "código del Almirantazgo",
    sinFuentes: "Sin fuentes públicas.",
    punto: "Punto",
  },
  estado: {
    notificado: "Lo cuentan las noticias. Es el estado inicial de todo incidente.",
    confirmado: "Una autoridad afirma que el incidente ocurrió.",
    atribuido:
      "Un confirmado del que una autoridad competente (gobierno, ministerio, fuerzas armadas, " +
      "fiscalía o policía) afirma expresamente, con sus propias palabras, quién es el " +
      "responsable: un Estado o una persona.",
    desmentido: "Una autoridad niega el incidente.",
  },
  presencia: {
    confirmada: "La autoridad competente atribuye el suceso a un dron.",
    no_confirmada: "La autoridad lo deja abierto, o solo lo cuentan la prensa o los testigos.",
    descartada: "Una autoridad niega que fuera un dron.",
  },
  ucrania: {
    titulo: "La guerra en Ucrania",
    descripcion:
      "Ataques con drones de Rusia contra Ucrania y de Ucrania contra Rusia según los partes " +
      "oficiales: cifras por región y por mes, impactos con lugar y corredores de ataque.",
    capa: "Qué muestra la capa",
    comoSeObtiene: "Cómo se obtiene",
    fuentesDeLosPartes: "Fuente de los partes de cada sentido:",
    sentido: { RU_UA: "De Rusia contra Ucrania", UA_RU: "De Ucrania contra Rusia" },
    reivindicacion: "reivindicación de parte",
    totales: "Totales",
    partes: "Partes publicados",
    lanzados: "Drones lanzados contra Ucrania",
    derribados: "Drones derribados en Ucrania",
    derribadosUaRu: "Drones que el parte ruso dice derribados en Rusia",
    impactos: "Impactos con lugar",
    porRegion: "Por región",
    region: "Región",
    ataquesQueLaCitan: "Partes que la citan",
    derribadosEnLaRegion: "Derribados en la región",
    porMes: "Por mes",
    mes: "Mes",
    corredores: "Corredores de ataque",
    corredoresIntro:
      "Cada corredor une una zona de lanzamiento que nombra el parte con una región alcanzada. " +
      "De Rusia contra Ucrania: drones lanzados en los ataques que salieron (entre otras zonas) " +
      "de esa zona y alcanzaron la región. De Ucrania contra Rusia: drones que el parte ruso dice " +
      "derribados en la región.",
    origen: "Origen",
    destino: "Región",
    drones: "Drones",
    ataques: "Ataques",
    sinOrigen: "Ucrania",
    metodologiaSatelite: "Guerra por satélite",
    periodo: (desde, hasta) => `Partes del ${desde} al ${hasta}.`,
  },
  metodologia: {
    titulo: "Metodología y datos abiertos",
    descripcion:
      "Qué registra el observatorio, cómo se clasifican y se confirman los incidentes, de dónde " +
      "salen los datos y cómo descargarlos.",
    indice: "Contenido",
  },
  ayuda: {
    titulo: "Cómo leer el mapa",
    descripcion: "Qué significa cada marca del mapa, cómo se eligen el periodo y las capas, y los atajos de teclado.",
    atajos: "Atajos de teclado",
    tecla: "Tecla",
    accion: "Acción",
  },
  noEncontrada: {
    titulo: "Página no encontrada",
    texto: "Esta dirección no existe en el observatorio.",
    volver: "Ir a la portada",
  },
};

const EN: TextosPagina = {
  saltar: "Skip to content",
  navegacion: "Sections",
  nav: {
    mapa: "Map",
    incidentes: "Incidents",
    paises: "Countries",
    ucrania: "War in Ukraine",
    metodologia: "Methodology and open data",
    ayuda: "Help",
  },
  otroIdioma: "Español",
  datosDe: (fecha) => `Data published at ${fecha}`,
  licencia: "Data licence",
  codigo: "Open source",
  portada: {
    titulo: `${NOMBRE} · Drone incidents in Europe`,
    descripcion:
      "Open map and record of drone incidents in Europe: overflights, incursions and airport " +
      "disruptions, with their sources, status and level of confirmation.",
    que: [
      `The ${NOMBRE} records drone incidents in Europe: unmanned aircraft that fly over a ` +
        "facility, enter an airspace from outside or disrupt the operation of an airport.",
      "Each incident carries its sources with the original sentence and the link, its status " +
        "(reported, confirmed, attributed or denied) and the history of changes. The data are " +
        "updated every hour and can be downloaded.",
    ],
    cifras: "Figures",
    incidentes: "Incidents",
    confirmados: "Confirmed",
    atribuidos: "Attributed",
    paises: "Countries",
    actualizado: "Last update",
    ultimos: "Latest incidents",
    todos: "All incidents",
    mas: "More",
    porAnio: "Incidents by year",
    porPais: "Incidents by country",
    descargas: "Download the data",
  },
  lista: {
    titulo: "All incidents",
    descripcion: (n) => `The ${n} published drone incidents in Europe, from the most recent to the oldest.`,
    anio: (anio) => `Incidents in ${anio}`,
    descripcionAnio: (anio, n) => `The ${n} published drone incidents in Europe in ${anio}.`,
    anios: "By year",
    numero: (n) => (n === 1 ? "1 incident" : `${n} incidents`),
    sinIncidentes: "No incidents published.",
  },
  pais: {
    titulo: "Incidents by country",
    descripcion: (n) => `The ${n} countries with published drone incidents.`,
    tituloDe: (pais) => `Drone incidents in ${pais}`,
    descripcionDe: (pais, n) => `The ${n} published drone incidents in ${pais}, with their status and sources.`,
    cifras: "Figures",
    lista: "Incidents",
    otros: "Other countries",
  },
  incidente: {
    descripcion: (estado, fecha, lugar) => `${estado}. ${fecha}. ${lugar}.`,
    significa: "What it means",
    tipo: "Type",
    objetivo: "Facility",
    verEnMapa: "See on the map",
    volver: "All incidents",
    todasLasFuentes: "Sources and quotes",
    codigoFuente: "Admiralty code",
    sinFuentes: "No public sources.",
    punto: "Point",
  },
  estado: {
    notificado: "The news reports it. It is the initial status of every incident.",
    confirmado: "An authority states that the incident happened.",
    atribuido:
      "A confirmed incident for which a competent authority (government, ministry, armed " +
      "forces, prosecutor or police) expressly states, in its own words, who is responsible: a " +
      "State or a person.",
    desmentido: "An authority denies the incident.",
  },
  presencia: {
    confirmada: "The competent authority attributes the event to a drone.",
    no_confirmada: "The authority leaves it open, or only the press or witnesses report it.",
    descartada: "An authority denies that it was a drone.",
  },
  ucrania: {
    titulo: "The war in Ukraine",
    descripcion:
      "Drone attacks by Russia against Ukraine and by Ukraine against Russia according to the " +
      "official reports: figures by region and by month, located impacts and attack corridors.",
    capa: "What the layer shows",
    comoSeObtiene: "How it is obtained",
    fuentesDeLosPartes: "Source of the reports in each direction:",
    sentido: { RU_UA: "From Russia against Ukraine", UA_RU: "From Ukraine against Russia" },
    reivindicacion: "claim by a party",
    totales: "Totals",
    partes: "Published reports",
    lanzados: "Drones launched against Ukraine",
    derribados: "Drones shot down in Ukraine",
    derribadosUaRu: "Drones the Russian report says were shot down in Russia",
    impactos: "Located impacts",
    porRegion: "By region",
    region: "Region",
    ataquesQueLaCitan: "Reports that name it",
    derribadosEnLaRegion: "Shot down in the region",
    porMes: "By month",
    mes: "Month",
    corredores: "Attack corridors",
    corredoresIntro:
      "Each corridor joins a launch area named in the report with a region that was reached. " +
      "From Russia against Ukraine: drones launched in the attacks that left (among other areas) " +
      "from that area and reached the region. From Ukraine against Russia: drones the Russian " +
      "report says were shot down in the region.",
    origen: "Origin",
    destino: "Region",
    drones: "Drones",
    ataques: "Attacks",
    sinOrigen: "Ukraine",
    metodologiaSatelite: "War seen from space",
    periodo: (desde, hasta) => `Reports from ${desde} to ${hasta}.`,
  },
  metodologia: {
    titulo: "Methodology and open data",
    descripcion:
      "What the observatory records, how incidents are classified and confirmed, where the data " +
      "come from and how to download them.",
    indice: "Contents",
  },
  ayuda: {
    titulo: "How to read the map",
    descripcion: "What each mark on the map means, how to choose the period and the layers, and the keyboard shortcuts.",
    atajos: "Keyboard shortcuts",
    tecla: "Key",
    accion: "Action",
  },
  noEncontrada: {
    titulo: "Page not found",
    texto: "This address does not exist in the observatory.",
    volver: "Go to the home page",
  },
};

const TEXTOS: Record<Idioma, TextosPagina> = { es: ES, en: EN };

export function textosPagina(idioma: Idioma): TextosPagina {
  return TEXTOS[idioma];
}
