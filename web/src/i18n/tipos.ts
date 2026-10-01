import type { Accion } from "../estado/atajos.ts";
import type {
  CategoriaInstalacion,
  CategoriaObjetivo,
  CategoriaObjetivoGuerra,
  CategoriaObjetivoUcrania,
  Estado,
  EstadoFuente,
  FuenteDelSistema,
  Medida,
  NivelUbicacion,
  Precision,
  PresenciaDron,
  ResultadoRecogida,
  Sentido,
  Tipo,
} from "../datos/tipos.ts";
import type { EstadoFrescura } from "../tiempo/frescura.ts";
import type { Granularidad } from "../tiempo/dias.ts";

/** Trozo de un párrafo: texto llano o un enlace. */
export type Trozo = string | { texto: string; enlace: string };

/** Marca gráfica que acompaña a una definición de la metodología. */
export type Marca = { tipo: Tipo } | { estado: Estado };

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
  };
  relativo: (minutos: number, fecha: string) => string;
  novedades: {
    aviso: (n: number) => string;
    recorrer: string;
    siguiente: string;
    anterior: string;
    descartar: string;
    posicion: (i: number, n: number) => string;
  };
  ayuda: {
    titulo: string;
    cerrar: string;
    formas: string;
    colores: string;
    areas: string;
    lineas: string;
    numeros: string;
    pila: string;
    pulsos: string;
    reciente: string;
    novedad: string;
    ucrania: string;
    rusia: string;
    impactos: string;
    foco: string;
    atajos: string;
    acciones: Record<Accion, string>;
  };
  pila: { titulo: (n: number) => string };
  imprecisa: { etiqueta: string; nivel: Record<NivelUbicacion, string> };
  guerra: {
    reproducir: string;
    pausar: string;
    reanudar: string;
    detener: string;
    noche: (fecha: string) => string;
    drones: string;
    sinCifra: string;
  };
  mapa: {
    etiqueta: string;
    instrucciones: string;
    grupo: (n: number) => string;
    pila: (n: number) => string;
    grupoImpactos: (n: number) => string;
    impacto: (parte: boolean, foco: boolean) => string;
  };
  tipo: Record<Tipo, string>;
  estado: Record<Estado, string>;
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
    radio: (km: string) => string;
    drones: string;
    duracion: string;
    efecto: string;
    respuesta: string;
    atribucion: string;
    atribuidoA: (actor: string, autoridad: string) => string;
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
    titulo: string;
    granularidad: string;
    porGranularidad: Record<Granularidad, string>;
    reproducir: string;
    pausar: string;
    reanudar: string;
    detener: string;
    verTodo: string;
    periodoBoton: string;
    desde: string;
    hasta: string;
    periodo: (desde: string, hasta: string) => string;
    incidentesPorTramo: string;
    lanzamientosPorNoche: string;
    instrucciones: string;
    plegar: string;
    desplegar: string;
    acotado: string;
    maximo: (n: string) => string;
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
}
