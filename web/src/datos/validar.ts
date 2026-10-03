// Validación de los datos contra el esquema 1.9.0 (campos públicos), escrita a mano para
// que no necesite generar código en el navegador. Se usa en el build, sobre los ficheros de
// publicacion/, y en la web al cargar cada fichero: un fichero que no valida no se pinta.

import type {
  EstadoSistema,
  PublicacionSinUbicacion,
  Ataque,
  ImpactoGuerra,
  ColeccionIncidentes,
  IncidenteDetalle,
  PublicacionUcrania,
  Resumen,
  ResumenUcrania,
} from "./tipos.ts";
import type { FocosVivos, IndiceSatelite } from "./guerraSatelite.ts";
import * as v from "./vocabulario.ts";

export type Resultado<T> = { ok: true; datos: T } | { ok: false; errores: string[] };

/** Con un fichero roto bastan los primeros errores para saber qué pasa. */
const MAX_ERRORES = 20;

type Comprobacion = (valor: unknown, ruta: string, errores: string[]) => void;

function anotar(errores: string[], ruta: string, mensaje: string): void {
  if (errores.length < MAX_ERRORES) errores.push(`${ruta || "raíz"}: ${mensaje}`);
}

function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function cadena(patron?: RegExp): Comprobacion {
  return (valor, ruta, errores) => {
    if (typeof valor !== "string" || valor.length === 0) {
      anotar(errores, ruta, "se esperaba un texto no vacío");
    } else if (patron !== undefined && !patron.test(valor)) {
      anotar(errores, ruta, "formato no válido");
    }
  };
}

function numero(minimo: number, maximo: number, entero = false): Comprobacion {
  return (valor, ruta, errores) => {
    if (typeof valor !== "number" || !Number.isFinite(valor)) {
      anotar(errores, ruta, "se esperaba un número");
    } else if (entero && !Number.isInteger(valor)) {
      anotar(errores, ruta, "se esperaba un entero");
    } else if (valor < minimo || valor > maximo) {
      anotar(errores, ruta, "número fuera de rango");
    }
  };
}

const enteroNoNegativo = numero(0, Number.MAX_SAFE_INTEGER, true);
const entero = numero(Number.MIN_SAFE_INTEGER, Number.MAX_SAFE_INTEGER, true);

function enumerado(valores: readonly unknown[]): Comprobacion {
  return (valor, ruta, errores) => {
    if (!valores.includes(valor)) anotar(errores, ruta, "valor fuera de la lista cerrada");
  };
}

function lista(elemento: Comprobacion, minimo = 0): Comprobacion {
  return (valor, ruta, errores) => {
    if (!Array.isArray(valor)) {
      anotar(errores, ruta, "se esperaba una lista");
      return;
    }
    if (valor.length < minimo) anotar(errores, ruta, "lista demasiado corta");
    valor.forEach((hijo, i) => {
      if (errores.length < MAX_ERRORES) elemento(hijo, `${ruta}[${i}]`, errores);
    });
  };
}

/** Objeto cerrado: faltar un campo obligatorio o traer uno desconocido es un error. */
function objeto(
  obligatorios: Record<string, Comprobacion>,
  opcionales: Record<string, Comprobacion> = {},
): Comprobacion {
  return (valor, ruta, errores) => {
    if (!esObjeto(valor)) {
      anotar(errores, ruta, "se esperaba un objeto");
      return;
    }
    for (const [clave, comprobar] of Object.entries(obligatorios)) {
      if (clave in valor) comprobar(valor[clave], `${ruta}.${clave}`, errores);
      else anotar(errores, `${ruta}.${clave}`, "falta un campo obligatorio");
    }
    for (const [clave, hijo] of Object.entries(valor)) {
      if (clave in obligatorios) continue;
      const comprobar = opcionales[clave];
      if (comprobar === undefined) anotar(errores, `${ruta}.${clave}`, "campo desconocido");
      else comprobar(hijo, `${ruta}.${clave}`, errores);
    }
  };
}

function tupla(elementos: readonly Comprobacion[]): Comprobacion {
  return (valor, ruta, errores) => {
    if (!Array.isArray(valor) || valor.length !== elementos.length) {
      anotar(errores, ruta, `se esperaba una lista de ${elementos.length} elementos`);
      return;
    }
    elementos.forEach((comprobar, i) => comprobar(valor[i], `${ruta}[${i}]`, errores));
  };
}

function nulable(comprobar: Comprobacion): Comprobacion {
  return (valor, ruta, errores) => {
    if (valor !== null) comprobar(valor, ruta, errores);
  };
}

function constante(esperado: unknown): Comprobacion {
  return enumerado([esperado]);
}

/** Objeto de claves libres (que cumplen `clave`) con valores que cumplen `elemento`. */
function diccionario(clave: Comprobacion, elemento: Comprobacion): Comprobacion {
  return (valor, ruta, errores) => {
    if (!esObjeto(valor)) {
      anotar(errores, ruta, "se esperaba un objeto");
      return;
    }
    for (const [nombre, hijo] of Object.entries(valor)) {
      if (errores.length >= MAX_ERRORES) return;
      clave(nombre, `${ruta}.${nombre}`, errores);
      elemento(hijo, `${ruta}.${nombre}`, errores);
    }
  };
}

/** Vale si cumple alguna de las alternativas; si no cumple ninguna, se dan los errores de la primera. */
function alguna(...alternativas: Comprobacion[]): Comprobacion {
  return (valor, ruta, errores) => {
    const intentos = alternativas.map((comprobar) => {
      const propios: string[] = [];
      comprobar(valor, ruta, propios);
      return propios;
    });
    if (intentos.some((propios) => propios.length === 0)) return;
    for (const error of intentos[0] ?? []) anotar(errores, "", error);
  };
}

/** Cualquier valor JSON: el de una afirmación tiene el tipo de su campo, que varía. */
const cualquiera: Comprobacion = () => undefined;

const instante = objeto({
  valor: cadena(v.PATRON_INSTANTE),
  precision: enumerado(v.PRECISIONES),
});

const rango = objeto({ min: enteroNoNegativo, max: enteroNoNegativo });

const rangoODesconocido: Comprobacion = (valor, ruta, errores) => {
  if (valor !== "desconocido") rango(valor, ruta, errores);
};

const titulo = objeto({ es: cadena(), en: cadena() });

const estadoHistorial = objeto({
  actual: enumerado(v.ESTADOS),
  historial: lista(
    objeto({ estado: enumerado(v.ESTADOS), fecha: instante }, { fuente_id: cadena() }),
    1,
  ),
});

const fuente = objeto({
  id: cadena(),
  enlace: cadena(v.PATRON_ENLACE),
  medio: cadena(),
  fecha: instante,
  idioma: cadena(v.PATRON_IDIOMA),
  fiabilidad: enumerado(v.FIABILIDADES),
  credibilidad: numero(v.CREDIBILIDAD_MIN, v.CREDIBILIDAD_MAX, true),
  // La frase de origen es una cita ajena: solo se exige que sea texto.
  frase_origen: cadena(),
  replicas: enteroNoNegativo,
});

const control = objeto({ ultima_actualizacion: instante }, { motivo_desmentido: cadena() });

/** Foco térmico de FIRMS: solo el detectado es público. */
const focoTermico = objeto({
  resultado: constante(v.RESULTADO_FOCO_PUBLICO),
  primer_foco: instante,
  satelite: enumerado(v.SATELITES_FIRMS),
  instrumento: enumerado(v.INSTRUMENTOS_FIRMS),
  distancia_km: numero(0, v.RADIO_FOCO_MAX_KM),
  numero_focos: numero(1, Number.MAX_SAFE_INTEGER, true),
});

/** Tráfico aéreo medido: solo el cierre medido es público. */
const traficoAereo = objeto(
  {
    cierre: objeto(
      {
        resultado: constante(v.RESULTADO_TRAFICO_PUBLICO),
        aeropuerto: cadena(v.PATRON_OACI),
        inicio: instante,
        fin: instante,
        duracion_min: enteroNoNegativo,
        vuelos_desviados: enteroNoNegativo,
        vuelos_en_espera: enteroNoNegativo,
      },
      { difiere_de_declarado: enumerado([true, false]) },
    ),
  },
  { datos: lista(cadena(v.PATRON_DATOS_ADSBLOL)) },
);

const longitud = numero(-v.LONGITUD_MAX, v.LONGITUD_MAX);
const latitud = numero(-v.LATITUD_MAX, v.LATITUD_MAX);
const radio = numero(v.RADIO_KM_MIN, v.RADIO_KM_MAX);

const CAMPOS_INCIDENTE_OBLIGATORIOS: Record<string, Comprobacion> = {
  id: cadena(v.PATRON_ID_INCIDENTE),
  tipo: enumerado(v.TIPOS),
  estado: estadoHistorial,
  titulo,
  tiempo: objeto({ inicio: instante }, { fin: instante, duracion_min: enteroNoNegativo }),
  lugar: objeto({ radio_km: radio, pais: cadena(v.PATRON_PAIS) }, { localidad: cadena() }),
  fuentes: lista(fuente, 1),
  control,
};

/** Lugar de un incidente sin punto: el país y hasta dónde se conoce, sin radio. */
const lugarSinUbicacion = objeto(
  { pais: cadena(v.PATRON_PAIS), nivel: enumerado(v.NIVELES_UBICACION) },
  { region: cadena(), localidad: cadena() },
);

const afirmacionPublica = objeto(
  {
    campo: cadena(),
    fuente_id: cadena(),
    medio: cadena(),
    fiabilidad: enumerado(v.FIABILIDADES_PUBLICAS),
    credibilidad: numero(v.CREDIBILIDAD_MIN, v.CREDIBILIDAD_MAX, true),
    fecha: instante,
    valor: cualquiera,
  },
  { cita: cadena() },
);

const CAMPOS_INCIDENTE_OPCIONALES: Record<string, Comprobacion> = {
  afirmaciones_publicas: lista(afirmacionPublica),
  episodio: cadena(v.PATRON_ID_EPISODIO),
  presencia_dron: enumerado(v.PRESENCIAS),
  objetivo: objeto(
    { categoria: enumerado(v.CATEGORIAS_OBJETIVO) },
    { nombre: cadena(), oaci: cadena(v.PATRON_OACI), uso: enumerado(v.USOS) },
  ),
  drones: objeto(
    {},
    { numero: rangoODesconocido, clase: enumerado(v.CLASES_DRON), modelo: cadena() },
  ),
  consecuencias: objeto(
    {},
    {
      cierre: objeto({ valor: enumerado(v.CIERRES) }, { minutos: rangoODesconocido }),
      vuelos_desviados: rangoODesconocido,
      vuelos_cancelados: rangoODesconocido,
      vuelos_retrasados: rangoODesconocido,
      danos: objeto({ nivel: enumerado(v.NIVELES_DANOS) }, { frase: cadena() }),
      heridos: rangoODesconocido,
      fallecidos: rangoODesconocido,
    },
  ),
  respuesta: objeto({}, { medidas: lista(enumerado(v.MEDIDAS)) }),
  atribucion: objeto({ actor: cadena(), autoridad: cadena(), fecha: instante }),
  foco_termico: focoTermico,
  trafico_aereo: traficoAereo,
};

const propiedadesIncidente = objeto(CAMPOS_INCIDENTE_OBLIGATORIOS, CAMPOS_INCIDENTE_OPCIONALES);

const incidenteSinUbicacion = objeto(
  { ...CAMPOS_INCIDENTE_OBLIGATORIOS, lugar: lugarSinUbicacion },
  CAMPOS_INCIDENTE_OPCIONALES,
);

const detalleIncidente = alguna(
  objeto(
    { ...CAMPOS_INCIDENTE_OBLIGATORIOS, lon: longitud, lat: latitud },
    CAMPOS_INCIDENTE_OPCIONALES,
  ),
  objeto(
    {
      ...CAMPOS_INCIDENTE_OBLIGATORIOS,
      lugar: lugarSinUbicacion,
      lon: constante(null),
      lat: constante(null),
    },
    CAMPOS_INCIDENTE_OPCIONALES,
  ),
);

const publicacionSinUbicacion = objeto({ incidentes: lista(incidenteSinUbicacion) });

const featureIncidente = objeto({
  type: constante("Feature"),
  id: cadena(v.PATRON_ID_INCIDENTE),
  geometry: objeto({ type: constante("Point"), coordinates: tupla([longitud, latitud]) }),
  properties: propiedadesIncidente,
});

const coleccion = objeto({
  type: constante("FeatureCollection"),
  features: lista(featureIncidente),
});

const regionAtaque = objeto(
  { region: cadena(v.PATRON_REGION) },
  {
    derribados: rangoODesconocido,
    impactos: rangoODesconocido,
    caida_restos: rangoODesconocido,
    categorias_objetivo: lista(enumerado(v.CATEGORIAS_OBJETIVO_UCRANIA)),
    heridos: rangoODesconocido,
    fallecidos: rangoODesconocido,
    foco_termico: focoTermico,
  },
);

const DIA = /^\d{4}-\d{2}-\d{2}$/;

/** Pérdida de luz nocturna medida por satélite (esquema: comun.perdida_luz). */
const perdidaLuz = objeto(
  {
    zona: enumerado(["region", "ciudad"]),
    region: cadena(v.PATRON_REGION),
    perdida_pct: numero(0, 100, true),
    noche: cadena(DIA),
    noches: lista(cadena(DIA), 1),
    referencia: objeto({
      desde: cadena(DIA),
      hasta: cadena(DIA),
      noches: numero(1, Number.MAX_SAFE_INTEGER, true),
      brillo: numero(0, Number.MAX_SAFE_INTEGER),
    }),
    brillo: numero(0, Number.MAX_SAFE_INTEGER),
    origen: constante("medido"),
  },
  {
    ciudad: objeto({
      id: cadena(),
      nombre: cadena(),
      punto: objeto({ lat: latitud, lon: longitud }),
    }),
  },
);

const ataque = objeto(
  {
    id: cadena(v.PATRON_ID_ATAQUE),
    tipo: constante("ataque_guerra"),
    periodo: objeto({ inicio: instante, fin: instante }),
    sentido: enumerado(v.SENTIDOS),
    estado: estadoHistorial,
    fuentes: lista(fuente, 1),
    control,
  },
  {
    reivindicacion_de_parte: constante(true),
    lanzados: objeto(
      {},
      {
        shahed_geran: rangoODesconocido,
        gerbera_senuelos: rangoODesconocido,
        otros: rangoODesconocido,
        total: rangoODesconocido,
      },
    ),
    zonas_lanzamiento: lista(cadena()),
    tipos_dron: lista(enumerado(v.TIPOS_DRON_ATAQUE)),
    derribados: rangoODesconocido,
    derribados_categoria: enumerado(v.CATEGORIAS_DERRIBADOS),
    perdidos_guerra_electronica: rangoODesconocido,
    localizaciones_impacto: rangoODesconocido,
    localizaciones_restos: rangoODesconocido,
    lugares_impacto: lista(cadena()),
    lugares_restos: lista(cadena()),
    cruces: lista(objeto({ pais: cadena(v.PATRON_PAIS), numero: rangoODesconocido })),
    regiones: lista(regionAtaque),
    regiones_misiles: lista(cadena(v.PATRON_REGION)),
    incluido_en: cadena(v.PATRON_ID_ATAQUE),
    solapado_con: cadena(v.PATRON_ID_ATAQUE),
    perdida_luz: lista(perdidaLuz),
  },
);

/** Fuente de un impacto con lugar: puede ser una autoridad instalada por Rusia. */
const fuenteImpacto = objeto(
  {
    id: cadena(),
    enlace: cadena(v.PATRON_ENLACE),
    medio: cadena(),
    fecha: instante,
    idioma: cadena(v.PATRON_IDIOMA),
    fiabilidad: enumerado(v.FIABILIDADES),
    credibilidad: numero(v.CREDIBILIDAD_MIN, v.CREDIBILIDAD_MAX, true),
    frase_origen: cadena(),
    replicas: enteroNoNegativo,
  },
  { autoridad_ocupacion: constante(true) },
);

const impactoGuerra = objeto(
  {
    id: cadena(v.PATRON_ID_IMPACTO),
    tipo: constante("impacto_guerra"),
    sentido: enumerado(v.SENTIDOS),
    region: cadena(v.PATRON_REGION),
    lugar: objeto(
      {
        id: cadena(v.PATRON_ID_LUGAR),
        nombre: cadena(),
        nivel: enumerado(v.NIVELES_LUGAR_GUERRA),
        punto: objeto({ lat: latitud, lon: longitud }),
        radio_km: numero(0, v.RADIO_LUGAR_GUERRA_MAX_KM),
      },
      {
        nombre_latino: cadena(),
        categoria: enumerado(v.CATEGORIAS_INSTALACION),
        localidad: cadena(),
      },
    ),
    impacto: enumerado(v.TIPOS_IMPACTO),
    fecha: instante,
    credibilidad: numero(v.CREDIBILIDAD_MIN, v.CREDIBILIDAD_MAX, true),
    fuentes: lista(fuenteImpacto, 1),
    control: objeto({ ultima_actualizacion: instante }),
  },
  {
    ataque: cadena(v.PATRON_ID_ATAQUE),
    categorias_objetivo: lista(enumerado(v.CATEGORIAS_OBJETIVO_GUERRA)),
    dia: cadena(/^\d{4}-\d{2}-\d{2}$/),
    parte_diario: constante(true),
    heridos: rangoODesconocido,
    fallecidos: rangoODesconocido,
    reivindicacion_de_parte: constante(true),
    foco_termico: focoTermico,
  },
);

const publicacionUcrania = objeto({ ataques: lista(ataque) }, { impactos: lista(impactoGuerra) });

const resumen = objeto({
  actualizado: cadena(v.PATRON_INSTANTE),
  incidentes: lista(
    objeto({
      id: cadena(v.PATRON_ID_INCIDENTE),
      punto: nulable(objeto({ lon: longitud, lat: latitud, radio_km: radio })),
      imprecisa: nulable(
        objeto({ nivel: enumerado(v.NIVELES_UBICACION), region: nulable(cadena()) }),
      ),
      tipo: enumerado(v.TIPOS),
      estado: enumerado(v.ESTADOS),
      presencia: nulable(enumerado(v.PRESENCIAS)),
      titulo,
      dia: entero,
      pais: cadena(v.PATRON_PAIS),
      objetivo: nulable(cadena()),
      episodio: nulable(cadena(v.PATRON_ID_EPISODIO)),
      foco: enumerado([true, false]),
    }),
  ),
  episodios: lista(
    objeto({
      id: cadena(v.PATRON_ID_EPISODIO),
      incidentes: lista(cadena(v.PATRON_ID_INCIDENTE), 1),
    }),
  ),
  eventos: lista(
    objeto({
      id: cadena(v.PATRON_ID_INCIDENTE),
      fecha: cadena(v.PATRON_INSTANTE),
      estado: enumerado(v.ESTADOS),
      nuevo: enumerado([true, false]),
    }),
  ),
});

/** Una cifra de la fila de un ataque: un entero no negativo o la marca de desconocido (-1). */
const cifra = numero(-1, Number.MAX_SAFE_INTEGER, true);
const bandera = enumerado([0, 1]);

const fuenteSentido = objeto({
  medio: cadena(),
  fiabilidad: enumerado(v.FIABILIDADES),
  credibilidad: numero(v.CREDIBILIDAD_MIN, v.CREDIBILIDAD_MAX, true),
  reivindicacion: enumerado([true, false]),
});

const resumenUcrania: Comprobacion = (valor, ruta, errores) => {
  objeto({
    regiones: lista(cadena(v.PATRON_REGION)),
    ataques: lista(
      tupla([
        cadena(v.PATRON_ID_ATAQUE),
        entero,
        bandera,
        cifra,
        cifra,
        cifra,
        cifra,
        bandera,
        lista(tupla([enteroNoNegativo, cifra, cifra])),
      ]),
    ),
    focos: lista(
      objeto({
        ataque: cadena(v.PATRON_ID_ATAQUE),
        dia: entero,
        region: cadena(v.PATRON_REGION),
        foco: focoTermico,
        centro: tupla([longitud, latitud]),
      }),
    ),
    impactos: lista(
      tupla([
        cadena(v.PATRON_ID_IMPACTO),
        entero,
        bandera,
        longitud,
        latitud,
        bandera,
        bandera,
        bandera,
        cadena(v.PATRON_REGION),
      ]),
    ),
    fuentes: objeto({ RU_UA: nulable(fuenteSentido), UA_RU: nulable(fuenteSentido) }),
    luces: lista(
      objeto({
        ataque: cadena(v.PATRON_ID_ATAQUE),
        dia: entero,
        zona: enumerado(["region", "ciudad"]),
        region: cadena(v.PATRON_REGION),
        ciudad: nulable(objeto({ nombre: cadena(), lon: longitud, lat: latitud })),
        perdida: numero(0, 100, true),
        noche: cadena(DIA),
        noches: lista(cadena(DIA), 1),
        referencia: objeto({
          desde: cadena(DIA),
          hasta: cadena(DIA),
          noches: numero(1, Number.MAX_SAFE_INTEGER, true),
        }),
      }),
    ),
    zonas: lista(objeto({ id: cadena(), nombre: cadena(), lon: longitud, lat: latitud })),
    origenes: diccionario(cadena(v.PATRON_ID_ATAQUE), lista(enteroNoNegativo, 1)),
    centros: diccionario(cadena(v.PATRON_REGION), tupla([longitud, latitud])),
    fronteraUcrania: diccionario(cadena(v.PATRON_REGION), tupla([longitud, latitud])),
  })(valor, ruta, errores);
  if (errores.length > 0) return;
  // Cada región de un ataque tiene que existir en la tabla de regiones, y cada origen en la
  // tabla de zonas.
  const datos = valor as ResumenUcrania;
  for (const [id, indices] of Object.entries(datos.origenes)) {
    if (indices.some((i) => i >= datos.zonas.length)) {
      anotar(errores, `${ruta}.origenes.${id}`, "zona fuera de la tabla");
    }
  }
  datos.ataques.forEach((fila, i) => {
    for (const [indice] of fila[8]) {
      if (indice >= datos.regiones.length) {
        anotar(errores, `${ruta}.ataques[${i}]`, "región fuera de la tabla");
      }
    }
  });
};

function validar<T>(comprobar: Comprobacion, valor: unknown): Resultado<T> {
  const errores: string[] = [];
  comprobar(valor, "", errores);
  return errores.length === 0 ? { ok: true, datos: valor as T } : { ok: false, errores };
}

export function validarColeccion(valor: unknown): Resultado<ColeccionIncidentes> {
  return validar(coleccion, valor);
}

export function validarSinUbicacion(valor: unknown): Resultado<PublicacionSinUbicacion> {
  return validar(publicacionSinUbicacion, valor);
}

export function validarPublicacionUcrania(valor: unknown): Resultado<PublicacionUcrania> {
  return validar(publicacionUcrania, valor);
}

export function validarResumen(valor: unknown): Resultado<Resumen> {
  return validar(resumen, valor);
}

export function validarResumenUcrania(valor: unknown): Resultado<ResumenUcrania> {
  return validar(resumenUcrania, valor);
}

/** Nombres de los campos del incidente que acepta el validador. */
export const CAMPOS_INCIDENTE: readonly string[] = [
  ...Object.keys(CAMPOS_INCIDENTE_OBLIGATORIOS),
  ...Object.keys(CAMPOS_INCIDENTE_OPCIONALES),
];

const estadoSistema = objeto(
  {
    version: constante(v.VERSION_ESTADO_SISTEMA),
    inicio: cadena(v.PATRON_INSTANTE),
    fin: cadena(v.PATRON_INSTANTE),
    resultado: enumerado(v.RESULTADOS_RECOGIDA),
    ultima_correcta: nulable(cadena(v.PATRON_INSTANTE)),
    siguiente: cadena(v.PATRON_INSTANTE),
    fuentes: lista(
      objeto({
        id: enumerado(v.FUENTES_DEL_SISTEMA),
        estado: enumerado(v.ESTADOS_FUENTE),
        ultimo_dato: nulable(cadena(v.PATRON_INSTANTE)),
      }),
    ),
  },
  // Fin de la última exportación semanal correcta y última ejecución correcta del motor de
  // deducción; la web no las muestra.
  {
    ultima_exportacion: nulable(cadena(v.PATRON_INSTANTE)),
    ultima_deduccion: nulable(cadena(v.PATRON_INSTANTE)),
    // Servicio de detección en directo de cierres de aeropuerto.
    directo: objeto({
      estado: enumerado(v.ESTADOS_DIRECTO),
      ultimo_ciclo_correcto: nulable(cadena(v.PATRON_INSTANTE)),
    }),
  },
);

export function validarEstadoSistema(valor: unknown): Resultado<EstadoSistema> {
  return validar(estadoSistema, valor);
}

export function validarDetalleIncidente(valor: unknown): Resultado<IncidenteDetalle> {
  return validar(detalleIncidente, valor);
}

export function validarImpacto(valor: unknown): Resultado<ImpactoGuerra> {
  return validar(impactoGuerra, valor);
}

export function validarAtaque(valor: unknown): Resultado<Ataque> {
  return validar(ataque, valor);
}

const focosVivos = objeto({
  generado: cadena(v.PATRON_INSTANTE),
  desde: cadena(v.PATRON_INSTANTE),
  ultimo_foco: nulable(cadena(v.PATRON_INSTANTE)),
  fuente: cadena(),
  atribucion: cadena(),
  zona: objeto({
    oeste: longitud,
    sur: latitud,
    este: longitud,
    norte: latitud,
  }),
  descartados: objeto({
    baja_confianza: enteroNoNegativo,
    fuentes_habituales: enteroNoNegativo,
    fuego_frecuente: enteroNoNegativo,
  }),
  focos: lista(
    tupla([longitud, latitud, cadena(v.PATRON_INSTANTE), cadena(), nulable(cadena(v.PATRON_ID_IMPACTO))]),
  ),
});

/** focos/ultimas24h.json del almacén público (recogida/focos_vivo.py). */
export function validarFocosVivos(valor: unknown): Resultado<FocosVivos> {
  return validar(focosVivos, valor);
}

const imagenSatelite = nulable(
  objeto({
    fecha: cadena(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/),
    escena: cadena(/^S2[A-D]_\w+_L2A$/),
    objeto: cadena(/^satelite\/EODI-IG-\d{4}-\d{5}\/(antes|despues)-\d{8}-S2[A-D]_\w+_L2A\.jpg$/),
    nubes_recorte: numero(0, 1),
  }),
);

const indiceSatelite = objeto({
  generado: cadena(v.PATRON_INSTANTE),
  fuente: cadena(),
  atribucion: cadena(),
  parejas: diccionario(
    cadena(v.PATRON_ID_IMPACTO),
    objeto({
      recorte: objeto({ lat: latitud, lon: longitud, lado_m: numero(100, 20000, true) }),
      antes: imagenSatelite,
      despues: imagenSatelite,
    }),
  ),
});

/** satelite/parejas.json del almacén público (recogida/satelite.py). */
export function validarIndiceSatelite(valor: unknown): Resultado<IndiceSatelite> {
  return validar(indiceSatelite, valor);
}
