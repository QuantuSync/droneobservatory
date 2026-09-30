import type {
  CategoriaObjetivo,
  CategoriaObjetivoUcrania,
  Estado,
  Medida,
  Precision,
  PresenciaDron,
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
  cabecera: {
    incidentes: string;
    confirmados: string;
    paises: string;
    contadores: string;
    metodologia: string;
    cambiarIdioma: string;
    otroIdioma: string;
  };
  estadoDatos: {
    actualizado: string;
    etiqueta: Record<EstadoFrescura, string>;
    antiguedad: (horas: number) => string;
    sinDatos: string;
  };
  avisos: {
    cargando: string;
    datosNoValidos: string;
    datosNoDisponibles: string;
    fichaNoEncontrada: string;
    fichaNoValida: string;
    mapaNoDisponible: string;
  };
  capas: {
    titulo: string;
    incidentes: string;
    ucrania: string;
    densidad: string;
    lista: string;
  };
  leyenda: {
    titulo: string;
    forma: string;
    color: string;
    precision: string;
    episodio: string;
    agrupacion: string;
    ucrania: string;
    menos: string;
    mas: string;
    densidad: string;
  };
  mapa: {
    etiqueta: string;
    instrucciones: string;
    acercar: string;
    alejar: string;
    atribucion: string;
  };
  tipo: Record<Tipo, string>;
  estado: Record<Estado, string>;
  presencia: Record<PresenciaDron, string>;
  precision: Record<Precision, string>;
  categoria: Record<CategoriaObjetivo, string>;
  categoriaUcrania: Record<CategoriaObjetivoUcrania, string>;
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
    cierre: Record<"si" | "no" | "desconocido", string>;
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
    todo: string;
    desde: string;
    hasta: string;
    periodo: (desde: string, hasta: string) => string;
    incidentesPorTramo: string;
    lanzamientosPorNoche: string;
    instrucciones: string;
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
  };
  regiones: Record<string, string>;
}
