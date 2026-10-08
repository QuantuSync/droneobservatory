import type { TipoSatelite } from "../datos/guerraSatelite.ts";
import type { Accion } from "../estado/atajos.ts";
import type {
  CategoriaInstalacion,
  CategoriaObjetivo,
  CategoriaObjetivoGuerra,
  CategoriaObjetivoUcrania,
  Estado,
  EstadoDirecto,
  EstadoFuente,
  FuenteDelSistema,
  GrupoDron,
  Medida,
  MotivoZona,
  NivelUbicacion,
  Precision,
  PresenciaDron,
  RazonTipoDron,
  ResultadoRecogida,
  Sentido,
  Tipo,
} from "../datos/tipos.ts";
import type { EstadoAviso, FuenteDirecto, TipoConfirmacion } from "../datos/directo.ts";
import type { NivelGnss } from "../datos/gnss.ts";

/** Una fecha por partes, para escribirla en palabras (mes de 0 a 11). */
export interface FechaEscrita {
  dia: number;
  mes: number;
  anio: number;
}
import type { Sentido as SentidoTendencia } from "../datos/presion.ts";
import type { EstadoFrescura } from "../tiempo/frescura.ts";

/** Trozo de un párrafo: texto llano o un enlace. */
export type Trozo = string | { texto: string; enlace: string };

/** Marca gráfica que acompaña a una definición de la metodología. */
export type Marca = { estado: Estado };

export type Bloque =
  | { parrafo: Trozo[] }
  | { lista: { termino?: string; marca?: Marca; texto: Trozo[] }[] };

export interface Seccion {
  id: string;
  titulo: string;
  bloques: Bloque[];
}

export interface Textos {
  descripcion: string;
  saltarAlMapa: string;
  marcador: {
    etiqueta: string;
    incidentes: string;
    confirmados: string;
    atribuidos: string;
    paises: string;
  };
  firma: { metodologia: string; atribuciones: string };
  cabecera: { etiqueta: string; menu: string; cerrarMenu: string };
  hoja: { altura: (altura: string) => string; alturas: Record<"asomada" | "media" | "completa", string> };
  controles: {
    capas: string;
    incidentes: string;
    ucrania: string;
    densidad: string;
    presion: string;
    gnss: string;
    feed: string;
    ayuda: string;
    cambiarIdioma: string;
    idioma: string;
    zoom: string;
    paneles: string;
    acercar: string;
    alejar: string;
  };
  estadoDatos: {
    actualizado: string;
    etiqueta: Record<EstadoFrescura, string>;
    sinDatos: string;
    detalle: string;
    datosPublicados: string;
    ultimaRecogida: string;
    resultadoRotulo: string;
    siguienteRecogida: string;
    fuentes: string;
    resultado: Record<ResultadoRecogida, string>;
    fuente: Record<FuenteDelSistema, string>;
    estadoFuente: Record<EstadoFuente, string>;
    directo: string;
    estadoDirecto: Record<EstadoDirecto, string>;
    ultimoCiclo: string;
    ultimoDato: string;
    sinUltimoDato: string;
    nuncaCorrecta: string;
    siguienteEn: (minutos: number) => string;
  };
  avisos: {
    cargando: string;
    datosNoValidos: string;
    datosNoDisponibles: string;
    fichaNoEncontrada: string;
    fichaNoValida: string;
    mapaNoDisponible: string;
  };
  filtros: {
    periodos: Record<"todo" | "24h" | "7d" | "30d" | "1a" | "entre", string>;
    desde: string;
    hasta: string;
    entreFechas: (desde: string, hasta: string) => string;
    abrir: string;
    cerrar: string;
    volverATodo: (periodo: string) => string;
    titulo: string;
    graves: string;
    ultimas24h: string;
    ultimos7d: string;
    tipo: string;
    pais: string;
    todosLosPaises: string;
    estado: string;
    quitar: string;
    recientes: string;
    activos: (n: number) => string;
    zona: string;
    zonas: Record<"todas" | "frontera" | "interior", string>;
  };
  feed: {
    titulo: string;
    enDirecto: string;
    lista: string;
    abrir: string;
    cerrar: string;
    nuevo: string;
    nuevoYa: (estado: string) => string;
    paso: (estado: string) => string;
    vacio: string;
    /** Cuándo lo registró el observatorio: «registrado hace 3 h». */
    registrado: (hace: string) => string;
    /** Cuándo ocurrió el suceso: «ocurrió el 06/10/2026». */
    ocurrio: (dia: string) => string;
  };
  relativo: (minutos: number, fecha: string) => string;
  /** Panel «Europa ahora»: las cifras del momento, cada una con su sitio en el mapa. */
  ahora: {
    etiqueta: string;
    cierres: string;
    incidentes: string;
    drones: string;
    /** Cuando el último parte es de día. */
    dronesDia: string;
    /** Cuando el último parte tiene más de 36 horas. */
    dronesParte: string;
    ultimoParte: (cuando: string) => string;
    focos: string;
    gnss: string;
    sinDato: string;
    ir: (que: string) => string;
    abrir: string;
    cerrar: string;
    avisoCierres: (n: number) => string;
    avisoNovedades: (n: number) => string;
  };
  desplegable: {
    escape: string;
  };
  /** Detección en directo de cierres de aeropuerto. */
  directo: {
    etiqueta: string;
    estado: Record<EstadoAviso, string>;
    detectado: string;
    inicio: string;
    reanudado: string;
    evidencia: string;
    movimientos: (vistos: string, esperados: string) => string;
    llegadasPerdidas: (n: string) => string;
    salidasPerdidas: (n: string) => string;
    esperas: (n: string) => string;
    desvios: (n: string) => string;
    confirmacion: string;
    confirmacionTipo: Record<TipoConfirmacion, string>;
    primeraNoticia: string;
    ventaja: (minutos: number) => string;
    actualizado: string;
    fuente: string;
    fuentes: Record<FuenteDirecto, string>;
    vigilados: (n: string) => string;
  };
  /** Mapa de interferencia GPS. */
  gnss: {
    etiqueta: string;
    leyenda: string;
    niveles: Record<NivelGnss, string>;
    proporcion: string;
    aeronaves: string;
    degradadas: string;
    periodo: string;
    dias: (n: number) => string;
    zonasAltas: (n: number) => string;
    sinDatos: string;
    cargando: string;
    letrero: (proporcion: string) => string;
  };
  /** Presión por país. */
  prevision: {
    etiqueta: string;
    cerrar: string;
    cargando: string;
    noDisponible: string;
    /** «4 de cada 10 noches como esta (40 %)». */
    deCada10: (n: number, porcentaje: number) => string;
    calculada: (cuando: string) => string;
    frontera: {
      titulo: string;
      noche: (desde: string, hasta: string) => string;
      ninguno: string;
      /** Lo habitual: la misma cifra que la comprobación (noches con dron entre noches comprobadas). */
      habitual: (porcentaje: number) => string;
      dependeDe: string;
      lanzados: (media: string, anoche: string) => string;
      crimea: (noches: number) => string;
      incidentes: (n: number, pais: string) => string;
      efectos: Record<"sube" | "baja", string>;
      /** Ningún factor sube ni baja hoy el riesgo. */
      sinCambios: string;
      historial: (noches: string, desde: string, conDron: number, porcentaje: number, enAlto: number) => string;
      verHistorial: string;
      columnaDijo: string;
      columnaNoches: string;
      columnaConDron: string;
      tramo: (desde: number, hasta: number) => string;
      ultimas: string;
      conDron: string;
      enVivo: (puntuadas: number, conDron: number) => string;
    };
    segundaNoche: { titulo: string; aviso: (lanzados: string, probabilidad: string) => string };
    rachas: {
      titulo: string;
      ninguna: string;
      linea: (desde: string, n: number, habitual: string, veces: string, tendencia: string) => string;
      tendencia: Record<"crece" | "estable" | "se_apaga", string>;
      ir: (pais: string) => string;
      historial: (semanas: number, siguientes: number, normal: string) => string;
      enFicha: string;
    };
    grafica: {
      titulo: string;
      resumen: (semanas: number, incidentes: number, normal: string) => string;
      barra: (semana: string, n: number) => string;
      banda: (minimo: number, maximo: number) => string;
    };
    cambios: {
      titulo: string;
      periodo: (desde: string, hasta: string) => string;
      ambito: Record<"ucrania_objetivo" | "europa_tipo", string>;
      linea: (clase: string, reciente: number, habitual: number, casos: number, de: number, sentido: string) => string;
      sentido: Record<"sube" | "baja", string>;
      historial: (casos: number, sostenidos: number) => string;
    };
    /** El desplegable que guarda los párrafos de la comprobación. */
    comoSeComprueba: string;
  };
  /** Frontera o interior de un incidente, con la regla que lo decide. */
  zona: {
    titulo: string;
    grupo: Record<"frontera" | "interior", string>;
    motivo: (motivo: MotivoZona, distancia: number | null) => string;
  };
  presion: {
    etiqueta: string;
    /** Lo que cuenta la leyenda, con el periodo dicho en palabras. */
    leyenda: {
      todo: string;
      reciente: Record<"24h" | "7d" | "30d" | "1a", string>;
      entre: (intervalo: string) => string;
    };
    menos: string;
    mas: string;
    tendencia: Record<SentidoTendencia, string>;
    frente: (anterior: string) => string;
    sinComparacion: string;
    /** Con todo el periodo no hay periodo anterior con que comparar. */
    eligePeriodo: string;
    incidentes: (n: number) => string;
    porTipo: string;
    porEstado: string;
    lista: string;
    vacia: string;
    letrero: (pais: string, n: number) => string;
  };
  novedades: {
    aviso: (n: number) => string;
    recorrer: string;
    siguiente: string;
    anterior: string;
    descartar: string;
    posicion: (i: number, n: number) => string;
    recorrido: string;
  };
  ayuda: {
    titulo: string;
    cerrar: string;
    colores: string;
    areas: string;
    /** El marcador de lugar aproximado. */
    aproximado: string;
    lineas: string;
    numeros: string;
    pila: string;
    periodo: string;
    ahora: string;
    pulsos: string;
    reciente: string;
    novedad: string;
    ucrania: string;
    rusia: string;
    impactos: string;
    foco: string;
    directo: string;
    atajos: string;
    acciones: Record<Accion, string>;
  };
  pila: { titulo: (n: number) => string };
  imprecisa: {
    etiqueta: string;
    nivel: Record<NivelUbicacion, string>;
    /** «Lugar aproximado: región»: el nivel del marcador de lugar aproximado. */
    aproximado: (nivel: string) => string;
    niveles: Record<"pais" | "region" | "mar", string>;
    /** De dónde sale el marcador: qué nombra la fuente y dónde se ha puesto. */
    deDonde: (nivel: "pais" | "region" | "mar", zona: string) => string;
  };
  guerra: {
    reproducir: string;
    pausar: string;
    reanudar: string;
    detener: string;
    drones: string;
    sinCifra: string;
    /** «de ellos, Shahed: desde 60 · a reacción: desde 50», con lo que digan los partes. */
    mezcla: (shahed: string | null, reactivos: string | null) => string;
  };
  mapa: {
    etiqueta: string;
    instrucciones: string;
    grupo: (n: number) => string;
    pila: (n: number) => string;
    /** Varios atribuidos juntos en un marcador al alejar el mapa. */
    atribuidos: (n: number) => string;
    grupoImpactos: (n: number) => string;
    impacto: (parte: boolean, foco: boolean) => string;
  };
  tipo: Record<Tipo, string>;
  estado: Record<Estado, string>;
  /** Marcador de los atribuidos: texto alternativo y leyenda. */
  atribucion: {
    aEstado: (pais: string) => string;
    aEstadoSinPais: string;
    aPersonaDe: (gentilicio: string) => string;
    aPersonaDePais: (pais: string) => string;
    aPersona: string;
    /** El actor de una persona que la autoridad no nombra, dentro de una frase. */
    unaPersona: string;
    leyendaEstado: string;
    leyendaPersona: string;
    /** Qué es la bandera: la del país al que la autoridad lo atribuye. */
    bandera: string;
  };
  presencia: Record<PresenciaDron, string>;
  precision: Record<Precision, string>;
  categoria: Record<CategoriaObjetivo, string>;
  categoriaUcrania: Record<CategoriaObjetivoUcrania, string>;
  categoriaGuerra: Record<CategoriaObjetivoGuerra, string>;
  categoriaInstalacion: Record<CategoriaInstalacion, string>;
  medida: Record<Medida, string>;
  sentido: Record<Sentido, string>;
  ficha: {
    titulo: string;
    cerrar: string;
    copiarEnlace: string;
    enlaceCopiado: string;
    enlaceNoCopiado: string;
    estado: string;
    presenciaDron: string;
    fecha: string;
    lugar: string;
    /** Fila con la fuente oficial cuya frase nombra el lugar del punto. */
    lugarSegun: string;
    /** Fila con los demás lugares que nombra la autoridad. */
    otrosLugares: string;
    /** Fila con el punto anterior cuando una corrección lo cambió, y por qué. */
    puntoAnterior: string;
    radio: (km: string) => string;
    drones: string;
    duracion: string;
    efecto: string;
    respuesta: string;
    atribucion: string;
    /** Incursión que forma parte de un ataque ruso contra Ucrania. */
    parteDelAtaque: string;
    ataqueDeLa: (jornada: string) => string;
    porFuente: string;
    porFecha: string;
    confirmadoAtribuido: (actor: string, autoridad: string) => string;
    atribuidoA: (actor: string, autoridad: string) => string;
    investigacion: string;
    investiga: (autoridad: string) => string;
    verFuente: string;
    declaracionCitada: (autoridad: string, medio: string) => string;
    motivoDesmentido: string;
    desconocido: string;
    minutos: (n: string) => string;
    rangoDeFuentes: string;
    queDiceCadaFuente: (n: number) => string;
    valorSegun: string;
    cierreDe: (minutos: string) => string;
    cierreSinDuracion: string;
    sinCierre: string;
    cierreDesconocido: string;
    vuelosDesviados: string;
    vuelosCancelados: string;
    vuelosRetrasados: string;
    heridos: string;
    fallecidos: string;
    danos: Record<"ninguno" | "menores" | "graves" | "desconocido", string>;
    modelo: string;
    episodio: string;
    fuentes: (n: number) => string;
    masFuentes: (n: number) => string;
    menosFuentes: string;
    replicas: (n: number) => string;
    codigo: (codigo: string) => string;
    declaracionOficial: string;
    enlaceExterno: string;
    enlaceNoValido: string;
    historial: string;
    fuenteNoPublica: string;
    actualizada: string;
  };
  ataque: {
    etiqueta: string;
    reivindicacion: string;
    periodo: string;
    lanzados: string;
    /** Drones a reacción que el parte cuenta aparte (dentro de los Shahed y Geran). */
    reactivos: string;
    shahed: string;
    senuelos: string;
    otros: string;
    derribados: string;
    derribadosONeutralizados: string;
    guerraElectronica: string;
    localizacionesImpacto: string;
    localizacionesRestos: string;
    zonasLanzamiento: string;
    regiones: string;
    regionesMisiles: string;
    cruces: string;
    cruceDeclarado: string;
    incluidoEn: string;
    solapadoCon: string;
  };
  trafico: {
    /** Rótulo de la fila en las fichas. */
    rotulo: string;
    cierreMedido: string;
    duracion: (minutos: string) => string;
    desviados: (n: string) => string;
    enEspera: (n: string) => string;
    declarado: string;
    datos: string;
  };
  foco: {
    /** Rótulo de la fila en las fichas. */
    rotulo: string;
    detectado: string;
    distancia: (km: string) => string;
    visor: string;
  };
  region: {
    etiqueta: string;
    ataques: string;
    ataquesPorSentido: Record<Sentido, string>;
    derribados: string;
    ultimoAtaque: string;
    sinAtaques: string;
    listaAtaques: string;
    masAtaques: (n: number) => string;
    nota: string;
    fuenteCifras: (medio: string) => string;
    reivindicacion: string;
    impactos: string;
    listaImpactos: string;
  };
  impacto: {
    etiqueta: string;
    lugar: string;
    instalacionEn: (localidad: string) => string;
    radio: (km: string) => string;
    nivel: Record<"comunidad" | "distrito", string>;
    tipo: Record<"impacto" | "restos", string>;
    objetivo: string;
    sinObjetivo: string;
    fecha: string;
    publicado: string;
    diaAtaque: string;
    parteDiario: string;
    victimas: string;
    heridos: (n: string) => string;
    fallecidos: (n: string) => string;
    ataque: string;
    region: string;
    credibilidad: string;
    credibilidadTexto: Record<number, string>;
    reivindicacion: string;
    reivindicacionTexto: string;
    ocupacion: string;
    fuentes: (n: number) => string;
    cargando: string;
    noDisponible: string;
  };
  lista: {
    titulo: string;
    incidentes: (n: number) => string;
    vacia: string;
    regiones: string;
  };
  tiempo: {
    periodo: (desde: string, hasta: string) => string;
    /** Intervalo de días en palabras: «del 1 al 30 de noviembre de 2025». */
    intervalo: (desde: FechaEscrita, hasta: FechaEscrita) => string;
    /** Una noche de ataques: «noche del 2 al 3 de octubre». */
    noche: (desde: FechaEscrita, hasta: FechaEscrita) => string;
    /** Un parte de día: «día 1 de octubre». */
    dia: (fecha: FechaEscrita) => string;
  };

  metodologia: {
    titulo: string;
    cerrar: string;
    secciones: Seccion[];
    descargas: {
      titulo: string;
      intro: string;
      incidentes: string;
      ucrania: string;
      sinUbicacion: string;
      version: (fecha: string) => string;
      licencia: string;
      citaTitulo: string;
      cita: (fecha: string) => string;
    };
  };
  compartir: {
    titulo: string;
    tituloIncidente: (titulo: string) => string;
    tituloAtaque: (id: string) => string;
    altImagen: string;
    lema: string;
  };
  regiones: Record<string, string>;
  satelite: TextosSatelite;
  tipoDron: TextosTipoDron;
  rutas: TextosRutas;
}

/** Rutas de los drones sobre Ucrania y recorrido de las incursiones. */
export interface TextosRutas {
  subcapa: string;
  /** «40 de 183 grupos, los de más drones». */
  leyenda: (mostrados: number, total: number) => string;
  sinRutas: string;
  cargando: string;
  comoSeLee: string;
  otraNoche: string;
  nota: string;
  fuente: { neptun: string; fuerza_aerea: string };
  etiqueta: string;
  noche: string;
  grupo: string;
  grupoNumero: (n: number) => string;
  aparatos: string;
  tipo: string;
  tipos: { ataque: string; reaccion: string; reconocimiento: string };
  velocidad: string;
  kmh: (n: number) => string;
  origen: string;
  precision: string;
  precisionKm: (km: string) => string;
  precisionEntre: (min: string, max: string) => string;
  recorridoGrupo: string;
  longitud: (km: string) => string;
  tramo: string;
  clases: { enlace: string; hacia_destino: string; desde_lanzamiento: string; neptun: string };
  desde: string;
  hasta: string;
  division: string;
  union: string;
  sinIdentidad: string;
  mensajes: string;
  pista: string;
  incidentes: string;
  ataque: string;
  recorrido: string;
  recorridoNota: string;
}

/** Tipo de dron: lo que identificó la autoridad o lo deducido («compatible con»). */
export interface TextosTipoDron {
  /** Rótulo de la fila de la ficha y del grupo del filtro. */
  fila: string;
  grupos: Record<GrupoDron, string>;
  /** «Gerbera, según la autoridad»: el modelo tal como lo escribe. */
  identificado: (modelo: string) => string;
  grupoDe: (grupo: string) => string;
  compatibleCon: string;
  /** Lo deducido cuando ningún grupo destaca: una sola frase, sin porcentajes. */
  compatibleGuerra: string;
  /** «4 de cada 10 (42 %)». */
  probabilidad: (porcentaje: number) => string;
  otras: (porcentaje: number) => string;
  deducido: string;
  porQue: string;
  /** Lo que da la frecuencia de partida: casos de la misma zona con el dron identificado. */
  base: (casos: number, zona: string) => string;
  zonas: { frontera: string; interior: string };
  razon: (razon: RazonTipoDron) => string;
  filtroAutoridad: string;
  filtroDeducido: string;
  filtroGuerra: string;
}

/** Guerra por satélite: corredores, focos en vivo, luz nocturna e imágenes de antes y después. */
export interface TextosSatelite {
  /** Rótulo del grupo de capas de la guerra. */
  capas: string;
  corredores: string;
  principales: {
    principales: (n: number, total: number) => string;
    todos: (total: number) => string;
    verTodos: (total: number) => string;
    verPrincipales: string;
  };
  letreroCorredor: (origen: string, region: string, drones: string) => string;
  letreroCiudad: (ciudad: string, perdida: string) => string;
  letreroAlumbrado: (ciudad: string) => string;
  corredor: {
    etiqueta: string;
    origen: string;
    destino: string;
    desdeUcrania: string;
    desdeUcraniaTexto: string;
    drones: string;
    dronesTexto: Record<Sentido, string>;
    ataques: (n: number) => string;
    periodo: string;
    /** Rótulo de la lista para elegir entre varios arcos. */
    varios: string;
    etiquetaVarios: string;
    /** Nombre de la lista de corredores que se recorre con el teclado. */
    lista: string;
  };
  luzFicha: {
    etiqueta: string;
    rotulo: string;
    perdida: (pct: string) => string;
    peorNoche: (fecha: string) => string;
    noches: (n: number) => string;
    referencia: (desde: string, hasta: string, n: number) => string;
    origen: string;
    ataque: string;
    region: string;
    regionEntera: string;
    sinPerdida: string;
    metodo: string;
  };
  alumbradoFicha: {
    etiqueta: string;
    titulo: string;
    desde: string;
    desdeTexto: (fecha: string, alMenos: boolean) => string;
    porEncima: (mes: string) => string;
    actual: string;
    referencia: string;
    brillo: (valor: string) => string;
    tramo: (desde: string, hasta: string, noches: number) => string;
    noches: string;
    metodo: string;
  };
  imagen: {
    rotulo: string;
    antes: string;
    despues: string;
    deslizador: string;
    escena: (id: string) => string;
    nubes: (pct: string) => string;
    producto: (lado: string) => string;
    alt: (momento: string, fecha: string) => string;
    /** «Zona con cambios: N hectáreas», con las fechas de las dos imágenes. */
    zonaCambio: (hectareas: string, antes: string, despues: string) => string;
    ocultarContorno: string;
    verContorno: string;
  };
  zona: (id: string, nombre: string) => string;
  /** Lo que dice la ayuda del mapa de cada marca. */
  ayudaCorredores: string;
  /** Las subcapas de la de Ucrania se encienden con su botón. */
  ayudaSubcapas: string;
  ayudaLuz: string;
  ayudaAlumbrado: string;
  /** El marcador de los puntos con información de satélite y el botón «Con satélite». */
  ayudaSatelite: string;
  conSatelite: (n: string) => string;
  /** Botón que abre la lista de «Con satélite» en el menú del teléfono, con los puntos que da. */
  verLista: (n: string) => string;
  /** Rótulo de la fila de subcapas en el menú del teléfono. */
  rotuloCapas: string;
  listaSatelite: string;
  abrirLista: string;
  cerrarLista: string;
  /** Los cuatro tipos de «Con satélite»: su nombre corto, lo que dice de cada uno la leyenda,
   * el rótulo de la leyenda y el del filtro. */
  tipos: Record<TipoSatelite, string>;
  leyendaTipos: Record<TipoSatelite, string>;
  leyenda: string;
  filtrar: string;
  letreroSatelite: (imagen: boolean, foco: boolean) => string;
}
