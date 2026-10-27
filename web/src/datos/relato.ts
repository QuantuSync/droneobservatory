// La ficha contada en un párrafo, en español y en inglés, para quien lee la página entera (y para
// los buscadores y asistentes, que eligen párrafos y no campos): qué pasó, cuándo, dónde, quién lo
// dijo, qué consecuencias tuvo y cómo consta hoy. Todo sale de la ficha publicada: si un dato no
// está, su frase no se escribe; nunca se rellena ni se califica. Funciones puras: las usan la
// ficha del mapa (componentes/FichaIncidente.tsx) y las páginas de texto (texto/paginas.ts).

import { autoridadEscrita, medioEnFrase } from "../i18n/autoridades.ts";
import { numero, pais } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { traduccionParaMostrar } from "./citas.ts";
import { marcaDe } from "./presencia.ts";
import { historialDePresencia } from "./presencia.ts";
import { lugarEscrito, localidadEscrita, objetivoEscrito, paisGeografico, regionEscrita } from "./nombres.ts";
import type { CategoriaObjetivo, Fuente, IncidenteDetalle, Instante, PasoPresencia, RangoODesconocido } from "./tipos.ts";

const MESES: Record<Idioma, readonly string[]> = {
  es: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
};

/** Palabras como mucho de una cita para que vaya en el párrafo. */
export const PALABRAS_DE_CITA = 30;

/**
 * La zona horaria de cada país, para escribir la hora local. Los países con más de una zona en
 * Europa se deciden por la longitud del punto (Canarias, Azores, Madeira, Kaliningrado); sin punto,
 * o fuera de la tabla, solo se da la hora UTC.
 */
const ZONAS: Readonly<Record<string, string>> = {
  AD: "Europe/Andorra", AL: "Europe/Tirane", AT: "Europe/Vienna", BA: "Europe/Sarajevo", BE: "Europe/Brussels",
  BG: "Europe/Sofia", BY: "Europe/Minsk", CH: "Europe/Zurich", CY: "Asia/Nicosia", CZ: "Europe/Prague",
  DE: "Europe/Berlin", DK: "Europe/Copenhagen", EE: "Europe/Tallinn", FI: "Europe/Helsinki", FO: "Atlantic/Faroe",
  GB: "Europe/London", GI: "Europe/Gibraltar", GR: "Europe/Athens", HR: "Europe/Zagreb", HU: "Europe/Budapest",
  IE: "Europe/Dublin", IS: "Atlantic/Reykjavik", IT: "Europe/Rome", LI: "Europe/Vaduz", LT: "Europe/Vilnius",
  LU: "Europe/Luxembourg", LV: "Europe/Riga", MC: "Europe/Monaco", MD: "Europe/Chisinau", ME: "Europe/Podgorica",
  MK: "Europe/Skopje", MT: "Europe/Malta", NL: "Europe/Amsterdam", NO: "Europe/Oslo", PL: "Europe/Warsaw",
  RO: "Europe/Bucharest", RS: "Europe/Belgrade", SE: "Europe/Stockholm", SI: "Europe/Ljubljana", SK: "Europe/Bratislava",
  SM: "Europe/San_Marino", TR: "Europe/Istanbul", UA: "Europe/Kyiv", VA: "Europe/Vatican", XK: "Europe/Belgrade",
};

/** La zona horaria del sitio, o null si no se puede saber sin suponer. */
export function zonaDelSitio(codigo: string, lon: number | null): string | null {
  if (codigo === "ES") return lon === null ? null : lon < -12 ? "Atlantic/Canary" : "Europe/Madrid";
  if (codigo === "PT") return lon === null ? null : lon < -22 ? "Atlantic/Azores" : lon < -15 ? "Atlantic/Madeira" : "Europe/Lisbon";
  if (codigo === "FR") return lon === null ? null : lon > -6 && lon < 10 ? "Europe/Paris" : null;
  if (codigo === "RU") return lon === null ? null : lon < 23 ? "Europe/Kaliningrad" : lon < 50 ? "Europe/Moscow" : null;
  return ZONAS[codigo] ?? null;
}

interface Partes {
  anio: number;
  mes: number;
  dia: number;
  hora: number;
  minuto: number;
}

function partesEn(valor: string, zona: string): Partes {
  const partes = new Intl.DateTimeFormat("en-GB", {
    timeZone: zona,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(valor));
  const de = (tipo: string) => Number(partes.find((p) => p.type === tipo)?.value ?? "0");
  return { anio: de("year"), mes: de("month") - 1, dia: de("day"), hora: de("hour"), minuto: de("minute") };
}

function dosCifras(n: number): string {
  return String(n).padStart(2, "0");
}

/** «24 de septiembre de 2025» / «24 September 2025». */
function diaMesAnio(p: { anio: number; mes: number; dia: number }, idioma: Idioma): string {
  return idioma === "es" ? `${p.dia} de ${MESES.es[p.mes]} de ${p.anio}` : `${p.dia} ${MESES.en[p.mes]} ${p.anio}`;
}

/** Un día escrito en palabras a partir de un instante ISO (su día UTC). */
export function diaEscrito(valor: string, idioma: Idioma): string {
  const f = new Date(valor);
  return diaMesAnio({ anio: f.getUTCFullYear(), mes: f.getUTCMonth(), dia: f.getUTCDate() }, idioma);
}

/** «la noche del 24 al 25 de septiembre de 2025» / «on the night of 24 to 25 September 2025». */
function nocheEscrita(desde: { anio: number; mes: number; dia: number }, hasta: { anio: number; mes: number; dia: number }, idioma: Idioma): string {
  if (idioma === "es") {
    return desde.mes === hasta.mes
      ? `la noche del ${desde.dia} al ${hasta.dia} de ${MESES.es[hasta.mes]} de ${hasta.anio}`
      : `la noche del ${desde.dia} de ${MESES.es[desde.mes]} al ${hasta.dia} de ${MESES.es[hasta.mes]} de ${hasta.anio}`;
  }
  return desde.mes === hasta.mes
    ? `on the night of ${desde.dia} to ${hasta.dia} ${MESES.en[hasta.mes]} ${hasta.anio}`
    : `on the night of ${desde.dia} ${MESES.en[desde.mes]} to ${hasta.dia} ${MESES.en[hasta.mes]} ${hasta.anio}`;
}

function diaAnterior(p: { anio: number; mes: number; dia: number }): { anio: number; mes: number; dia: number } {
  const f = new Date(Date.UTC(p.anio, p.mes, p.dia - 1));
  return { anio: f.getUTCFullYear(), mes: f.getUTCMonth(), dia: f.getUTCDate() };
}

function diaSiguiente(p: { anio: number; mes: number; dia: number }): { anio: number; mes: number; dia: number } {
  const f = new Date(Date.UTC(p.anio, p.mes, p.dia + 1));
  return { anio: f.getUTCFullYear(), mes: f.getUTCMonth(), dia: f.getUTCDate() };
}

function diaDeTexto(dia: string): { anio: number; mes: number; dia: number } {
  const [anio = "0", mes = "1", d = "1"] = dia.split("-");
  return { anio: Number(anio), mes: Number(mes) - 1, dia: Number(d) };
}

/**
 * Cuándo, como empieza la primera frase: «El 24 de septiembre de 2025», «La noche del 22 al 23 de
 * septiembre de 2025, a las 20:30 hora local de Dinamarca (18:30 UTC)». La noche sale de la jornada
 * del ataque de la guerra o de una hora local entre las 20:00 y las 6:00.
 */
export function cuandoEscrito(d: IncidenteDetalle, idioma: Idioma): string {
  const inicio: Instante = d.tiempo.inicio;
  const conHora = inicio.precision === "minuto" || inicio.precision === "hora";
  const zona = conHora ? zonaDelSitio(paisGeografico(d), d.lon) : null;
  const utc = new Date(inicio.valor);
  const horaUtc = `${dosCifras(utc.getUTCHours())}:${dosCifras(utc.getUTCMinutes())}`;
  const local = zona === null ? null : partesEn(inicio.valor, zona);
  const delDia = local ?? { anio: utc.getUTCFullYear(), mes: utc.getUTCMonth(), dia: utc.getUTCDate(), hora: utc.getUTCHours(), minuto: utc.getUTCMinutes() };
  let cuando: string;
  if (d.ataque?.jornada.tipo === "noche") {
    cuando = nocheEscrita(diaDeTexto(d.ataque.jornada.desde), diaDeTexto(d.ataque.jornada.hasta), idioma);
  } else if (local !== null && local.hora >= 20) {
    cuando = nocheEscrita(local, diaSiguiente(local), idioma);
  } else if (local !== null && local.hora < 6) {
    cuando = nocheEscrita(diaAnterior(local), local, idioma);
  } else {
    const dia = diaMesAnio(delDia, idioma);
    cuando = inicio.precision === "aproximada" ? (idioma === "es" ? `hacia el ${dia}` : `around ${dia}`) : idioma === "es" ? `el ${dia}` : `on ${dia}`;
  }
  if (conHora) {
    const aproximada = inicio.precision === "hora";
    if (local !== null) {
      const horaLocal = `${dosCifras(local.hora)}:${dosCifras(local.minuto)}`;
      const donde = pais(paisGeografico(d), idioma);
      cuando +=
        idioma === "es"
          ? `, ${aproximada ? "hacia las" : "a las"} ${horaLocal} hora local de ${donde} (${horaUtc} UTC)`
          : `, ${aproximada ? "around" : "at"} ${horaLocal} local time in ${donde} (${horaUtc} UTC)`;
    } else {
      cuando += idioma === "es" ? `, ${aproximada ? "hacia las" : "a las"} ${horaUtc} UTC` : `, ${aproximada ? "around" : "at"} ${horaUtc} UTC`;
    }
  }
  return cuando;
}

const PRISION = /prison|penitenci|gevangenis|c[aá]rcel|wi[eę]zieni|justizvollzug|\bjva\b|f[aä]ngelse|vankila|vangla|kal[eė]jim|cietum|zat?vor|penitenciar|börtön|fengsel/i;

/** La categoría para escribir la frase: la de la ficha, o «cárcel» si el nombre lo dice. */
type Clase = CategoriaObjetivo | "carcel";

function claseDe(d: IncidenteDetalle): Clase | null {
  const o = d.objetivo;
  if (o === undefined) return null;
  const nombres = [o.nombre, d.nombres?.objetivo?.es, d.nombres?.objetivo?.en].filter((n): n is string => n !== undefined);
  if ((o.categoria === "otra" || o.categoria === "gubernamental") && nombres.some((n) => PRISION.test(n))) return "carcel";
  return o.categoria;
}

/** Una instalación sin nombre que se pueda escribir: «un aeropuerto», «una base militar». */
const SIN_NOMBRE: Record<Clase, Record<Idioma, string>> = {
  aeropuerto: { es: "un aeropuerto", en: "an airport" },
  base_militar: { es: "una base militar", en: "a military base" },
  puerto: { es: "un puerto", en: "a port" },
  energia: { es: "una instalación de energía", en: "an energy facility" },
  presa: { es: "una presa", en: "a dam" },
  estadio: { es: "un estadio", en: "a stadium" },
  industrial: { es: "una instalación industrial", en: "an industrial facility" },
  gubernamental: { es: "una sede gubernamental", en: "a government building" },
  carcel: { es: "una cárcel", en: "a prison" },
  otra: { es: "", en: "" },
};

/** Los países que se escriben con artículo dentro de una frase. */
const PAISES_CON_ARTICULO: Readonly<Record<string, Record<Idioma, string>>> = {
  GB: { es: "el Reino Unido", en: "the United Kingdom" },
  NL: { es: "los Países Bajos", en: "the Netherlands" },
};

/** El país dentro de una frase: «el Reino Unido», «the Netherlands»; los demás, su nombre. */
export function paisEnFrase(codigo: string, idioma: Idioma): string {
  return PAISES_CON_ARTICULO[codigo]?.[idioma] ?? pais(codigo, idioma);
}

/** La preposición y el nombre, con la contracción del español («el Reino Unido» pasa a «dEL Reino Unido»). */
function deNombre(nombre: string, idioma: Idioma): string {
  if (idioma === "es") return nombre.startsWith("el ") ? `d${nombre}` : `de ${nombre}`;
  return `of ${nombre}`;
}

/** El artículo de las instalaciones que empiezan por un nombre común: «en el Aeropuerto de Aalborg». */
const ARTICULOS: Readonly<Record<string, "el" | "la">> = {
  aeropuerto: "el", aerodromo: "el", astillero: "el", base: "la", carcel: "la", central: "la", centro: "el",
  complejo: "el", deposito: "el", establecimiento: "el", estacion: "la", estadio: "el", fabrica: "la",
  helipuerto: "el", instalacion: "la", ministerio: "el", palacio: "el", parlamento: "el", penitenciaria: "la",
  planta: "la", presa: "la", prision: "la", puente: "el", puerto: "el", refineria: "la", subestacion: "la",
  terminal: "la",
};

/** En español, el nombre con su artículo si empieza por un nombre común; tal cual si no. */
export function conArticulo(nombre: string, idioma: Idioma): string {
  if (idioma !== "es") return nombre;
  const primera = normal(nombre.split(/\s+/u)[0] ?? "");
  const articulo = ARTICULOS[primera];
  return articulo === undefined ? nombre : `${articulo} ${nombre}`;
}

function normal(texto: string): string {
  return texto.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/**
 * Dónde: la instalación con el nombre como se busca y, entre paréntesis, su nombre oficial si es
 * otro («Aeropuerto de Aalborg (Flyvestation Aalborg), Dinamarca»), y el lugar de la ficha.
 */
/** Un nombre escrito solo con letras latinas (con sus tildes), cifras y signos. */
const LATINO = /^[\p{Script=Latin}\p{N}\p{P}\p{Zs}\p{Sk}]+$/u;

/**
 * Cómo se escribe el párrafo. `conOficial`: el nombre oficial de la instalación entre paréntesis
 * cuando es otro («Aalborg Lufthavn»), como lo busca la gente del país; solo en las páginas de
 * texto y solo en alfabeto latino. La ficha del mapa no enseña nombres en otro idioma.
 */
export interface OpcionesRelato {
  conOficial?: boolean;
}

export function dondeEscrito(d: IncidenteDetalle, idioma: Idioma, opciones: OpcionesRelato = {}): string {
  const escritoTalCual = lugarEscrito(d, idioma, d.lon === null);
  // Solo el país: con su artículo si lo lleva («sobre el Reino Unido»).
  const lugar = escritoTalCual === pais(paisGeografico(d), idioma) ? paisEnFrase(paisGeografico(d), idioma) : escritoTalCual;
  const clase = claseDe(d);
  if (clase === null || clase === "otra") return lugar;
  const objetivo = objetivoEscrito(d, idioma);
  const oficial = d.objetivo?.nombre;
  if (objetivo === null) {
    const generico = SIN_NOMBRE[clase][idioma];
    return generico === "" ? lugar : `${generico} ${idioma === "es" ? "en" : "in"} ${lugar}`;
  }
  const escrito = conArticulo(objetivo, idioma);
  const conOficial =
    opciones.conOficial === true && oficial !== undefined && LATINO.test(oficial) && normal(oficial) !== normal(objetivo)
      ? `${escrito} (${oficial})`
      : escrito;
  const localidad = localidadEscrita(d, idioma);
  const paisEscrito = pais(paisGeografico(d), idioma);
  // Si el nombre ya lleva la localidad, basta con el país; si no, el lugar entero.
  const resto = localidad !== null && normal(objetivo).includes(normal(localidad)) ? paisEscrito : lugar;
  return `${conOficial}, ${resto}`;
}

/** «un dron», «3 drones», «entre 2 y 10 drones», «drones». Con el número del verbo. */
function dronesEscritos(numeroDrones: RangoODesconocido | undefined, idioma: Idioma): { texto: string; uno: boolean } {
  if (numeroDrones === undefined || numeroDrones === "desconocido") return { texto: idioma === "es" ? "drones" : "drones", uno: false };
  const { min, max } = numeroDrones;
  if (min === 1 && max === 1) return { texto: idioma === "es" ? "un dron" : "a drone", uno: true };
  if (min === max) return { texto: `${numero(min, idioma)} drones`, uno: false };
  return { texto: idioma === "es" ? `entre ${numero(min, idioma)} y ${numero(max, idioma)} drones` : `between ${numero(min, idioma)} and ${numero(max, idioma)} drones`, uno: false };
}

function mayuscula(texto: string): string {
  return texto.charAt(0).toLocaleUpperCase() + texto.slice(1);
}

/** Qué pasó, cuándo y dónde, según el tipo y la instalación. */
function queCuandoDonde(d: IncidenteDetalle, idioma: Idioma, opciones: OpcionesRelato): string {
  const cuando = mayuscula(cuandoEscrito(d, idioma));
  const donde = dondeEscrito(d, idioma, opciones);
  const drones = dronesEscritos(d.drones?.numero, idioma);
  const fueron = drones.uno ? "was" : "were";
  if (d.tipo === "incursion") {
    const espacio = pais(paisGeografico(d), idioma);
    const delEspacio = deNombre(paisEnFrase(paisGeografico(d), idioma), idioma);
    // El sitio sin repetir el país del espacio aéreo: «en Solca», no «en Solca, Rumanía».
    const sitio =
      d.lon === null && localidadEscrita(d, idioma) === null && regionEscrita(d, idioma) === null
        ? ""
        : donde.endsWith(`, ${espacio}`)
          ? donde.slice(0, -`, ${espacio}`.length)
          : donde === espacio || donde === paisEnFrase(paisGeografico(d), idioma)
            ? ""
            : donde;
    if (idioma === "es") {
      return sitio === ""
        ? `${cuando}, se notificó la entrada de ${drones.texto} en el espacio aéreo ${delEspacio}.`
        : `${cuando}, se notificó la entrada de ${drones.texto} en el espacio aéreo ${delEspacio}, en ${sitio}.`;
    }
    return sitio === ""
      ? `${cuando}, ${drones.texto} ${fueron} reported entering the airspace ${delEspacio}.`
      : `${cuando}, ${drones.texto} ${fueron} reported entering the airspace ${delEspacio}, at ${sitio}.`;
  }
  if (d.tipo === "interrupcion_aeroportuaria") {
    return idioma === "es"
      ? `${cuando}, se notificó la presencia de ${drones.texto} en ${donde}, y su tráfico aéreo se interrumpió.`
      : `${cuando}, ${drones.texto} ${fueron} reported at ${donde}, and its air traffic was disrupted.`;
  }
  return idioma === "es"
    ? `${cuando}, se notificó el sobrevuelo de ${drones.texto} sobre ${donde}.`
    : `${cuando}, ${drones.texto} ${fueron} reported flying over ${donde}.`;
}

function contarPalabras(texto: string): number {
  return texto.trim().split(/\s+/u).filter((p) => p !== "").length;
}

const DECLARACION = /^(.+) \(declaración oficial citada en (.+)\)$/;

/** La frase de una fuente en el idioma de la página (su traducción, o el original si ya lo está). */
function fraseEnIdioma(f: Fuente, idioma: Idioma): string | null {
  const traducida = traduccionParaMostrar(idioma, f.frase_origen, f.idioma, f.traduccion);
  if (traducida !== null) return traducida;
  return f.idioma === idioma ? f.frase_origen : null;
}

/**
 * Quién lo dijo: la autoridad de la declaración que confirmó (o atribuyó) el incidente, con su
 * frase si es corta. Solo si la fuente es una declaración oficial: si la confirmación no tiene
 * autoridad que se pueda nombrar, la frase no se escribe.
 */
function quienLoDijo(d: IncidenteDetalle, idioma: Idioma): string | null {
  const paso =
    d.estado.historial.findLast((p) => p.estado === "atribuido" && p.fuente_id !== undefined) ??
    d.estado.historial.findLast((p) => p.estado === "confirmado" && p.fuente_id !== undefined);
  const fuente = paso?.fuente_id === undefined ? undefined : d.fuentes.find((f) => f.id === paso.fuente_id);
  if (fuente === undefined) return null;
  const partes = DECLARACION.exec(fuente.medio);
  let autoridad: string;
  let medio: string | null = null;
  if (partes !== null) {
    autoridad = autoridadEscrita(partes[1] ?? "", idioma);
    medio = partes[2] ?? null;
  } else if (!fuente.medio.includes(".")) {
    autoridad = medioEnFrase(fuente.medio, idioma, (a) => a);
  } else {
    return null;
  }
  const frase = fraseEnIdioma(fuente, idioma);
  const cita = frase !== null && contarPalabras(frase) <= PALABRAS_DE_CITA ? frase.replace(/[\s.]+$/u, "") : null;
  const citada = medio === null ? "" : idioma === "es" ? ` (declaración citada en ${medio})` : ` (statement quoted by ${medio})`;
  if (idioma === "es") {
    return cita === null ? `Lo declaró ${autoridad}${citada}.` : `Según ${autoridad}${citada}: «${cita}».`;
  }
  return cita === null ? `It was stated by ${autoridad}${citada}.` : `According to ${autoridad}${citada}: “${cita}”.`;
}

function rangoEscrito(r: RangoODesconocido | undefined, idioma: Idioma): string | null {
  if (r === undefined || r === "desconocido") return null;
  if (r.min === r.max) return numero(r.min, idioma);
  return idioma === "es" ? `entre ${numero(r.min, idioma)} y ${numero(r.max, idioma)}` : `between ${numero(r.min, idioma)} and ${numero(r.max, idioma)}`;
}

/** Las consecuencias que la ficha tiene, en una frase; null si no tiene ninguna. */
function consecuencias(d: IncidenteDetalle, idioma: Idioma): string | null {
  const c = d.consecuencias;
  const es = idioma === "es";
  const partes: string[] = [];
  if (c?.cierre?.valor === "si") {
    const minutos = rangoEscrito(c.cierre.minutos, idioma);
    partes.push(minutos === null ? (es ? "hubo un cierre" : "there was a closure") : es ? `hubo un cierre de ${minutos} minutos` : `there was a closure of ${minutos} minutes`);
  }
  const cifras: [RangoODesconocido | undefined, string, string][] = [
    [c?.vuelos_desviados, "se desviaron {n} vuelos", "{n} flights were diverted"],
    [c?.vuelos_cancelados, "se cancelaron {n} vuelos", "{n} flights were cancelled"],
    [c?.vuelos_retrasados, "se retrasaron {n} vuelos", "{n} flights were delayed"],
    [c?.heridos, "hubo {n} heridos", "{n} people were injured"],
    [c?.fallecidos, "hubo {n} fallecidos", "{n} people died"],
  ];
  for (const [valor, enEs, enEn] of cifras) {
    const n = rangoEscrito(valor, idioma);
    if (n === null) continue;
    const uno = valor !== undefined && valor !== "desconocido" && valor.min === 1 && valor.max === 1;
    let frase = (es ? enEs : enEn).replace("{n}", n);
    if (uno) {
      frase = es
        ? frase.replace("se desviaron 1 vuelos", "se desvió 1 vuelo").replace("se cancelaron 1 vuelos", "se canceló 1 vuelo").replace("se retrasaron 1 vuelos", "se retrasó 1 vuelo").replace("hubo 1 heridos", "hubo 1 herido").replace("hubo 1 fallecidos", "hubo 1 fallecido")
        : frase.replace("1 flights were", "1 flight was").replace("1 people were injured", "1 person was injured").replace("1 people died", "1 person died");
    }
    partes.push(frase);
  }
  const danos = c?.danos?.nivel;
  if (danos === "graves") partes.push(es ? "hubo daños graves" : "there was serious damage");
  if (danos === "menores") partes.push(es ? "hubo daños menores" : "there was minor damage");
  if (danos === "ninguno") partes.push(es ? "no hubo daños" : "there was no damage");
  const MEDIDAS: Record<string, Record<Idioma, string>> = {
    cierre_espacio_aereo: { es: "se cerró el espacio aéreo", en: "the airspace was closed" },
    cazas: { es: "despegaron cazas", en: "fighter jets were scrambled" },
    derribo: { es: "hubo un derribo", en: "there was a shootdown" },
    inhibicion: { es: "se usó la inhibición", en: "jamming was used" },
    patrulla: { es: "hubo patrullas", en: "there were patrols" },
  };
  for (const medida of d.respuesta?.medidas ?? []) {
    const frase = MEDIDAS[medida]?.[idioma];
    if (frase !== undefined && !(medida === "cierre_espacio_aereo" && c?.cierre?.valor === "si")) partes.push(frase);
  }
  const medido = d.trafico_aereo?.cierre;
  if (medido !== undefined) {
    partes.push(
      es
        ? `el tráfico aéreo medido (adsb.lol) muestra ${numero(medido.duracion_min, idioma)} minutos sin movimientos en ${medido.aeropuerto} y ${numero(medido.vuelos_desviados, idioma)} vuelos desviados`
        : `measured air traffic (adsb.lol) shows ${numero(medido.duracion_min, idioma)} minutes without movements at ${medido.aeropuerto} and ${numero(medido.vuelos_desviados, idioma)} diverted flights`,
    );
  }
  if (partes.length === 0) return null;
  const lista = partes.length === 1 ? partes[0] ?? "" : `${partes.slice(0, -1).join("; ")}${es ? " y " : " and "}${partes.at(-1) ?? ""}`;
  return `${mayuscula(lista)}.`;
}

/** El último paso del historial de la presencia que cambia algo o la cierra (no la confirmación). */
function ultimoPasoQueCuenta(d: IncidenteDetalle): PasoPresencia | null {
  const pasos = historialDePresencia(d).filter((p) => p.valor !== "confirmada" || p.cierre === true || p.parcial === true);
  return pasos.at(-1) ?? null;
}

/** El paso del historial de la presencia escrito en una frase: quién, cuándo y por qué. */
function pasoEnFrase(paso: PasoPresencia, idioma: Idioma): string {
  const quien = paso.quien?.[idioma] ?? null;
  const cuando = diaEscrito(paso.fecha.valor, idioma);
  const motivo = paso.motivo?.[idioma] ?? null;
  const es = idioma === "es";
  if (paso.cierre === true) {
    const base = es
      ? quien === null ? `la investigación se cerró el ${cuando}` : `${quien} cerró la investigación el ${cuando}`
      : quien === null ? `the investigation was closed on ${cuando}` : `${quien} closed the investigation on ${cuando}`;
    return motivo === null ? base : `${base}: ${motivo}`;
  }
  const base = es
    ? quien === null ? `según una declaración del ${cuando}` : `${quien} lo declaró el ${cuando}`
    : quien === null ? `according to a statement of ${cuando}` : `${quien} stated it on ${cuando}`;
  return motivo === null ? base : `${base}: ${motivo}`;
}

/** Cómo consta el caso, en palabras: lo que publica la ficha (estado y presencia de dron). */
function comoConsta(d: IncidenteDetalle, idioma: Idioma): string {
  const marca = marcaDe({ estado: d.estado.actual, presencia: d.presencia_dron ?? null });
  const es = idioma === "es";
  switch (marca) {
    case "no_acreditado":
      return es ? "no acreditado (la presencia del dron no se acreditó)" : "not substantiated (the drone's presence was not substantiated)";
    case "descartado":
      return es ? "descartado (una autoridad dice que no fue un dron)" : "ruled out (an authority says it was not a drone)";
    case "atribuido": {
      const a = d.atribucion;
      if (a === undefined) return es ? "atribuido" : "attributed";
      const actor = a.tipo === "estado" && a.pais !== undefined ? pais(a.pais, idioma) : a.tipo === "persona" ? (es ? "una persona" : "a person") : a.actor;
      return es ? `atribuido a ${actor} por ${autoridadEscrita(a.autoridad, idioma)}` : `attributed to ${actor} by ${autoridadEscrita(a.autoridad, idioma)}`;
    }
    case "confirmado":
      return es ? "confirmado por una autoridad" : "confirmed by an authority";
    case "desmentido":
      return es ? "desmentido (una autoridad niega el incidente)" : "denied (an authority denies the incident)";
    case "notificado":
      return es ? "notificado (lo cuentan las noticias, sin confirmación de una autoridad)" : "reported (the news reports it, without confirmation by an authority)";
  }
}

/**
 * La frase del estado actual con su fecha, la primera línea de la página y la última del
 * párrafo: «A 27 de octubre de 2026 el caso consta como no acreditado (…): la policía de
 * Dinamarca lo declaró el 25 de junio de 2026: no dispone de pruebas …».
 */
export function estadoActual(d: IncidenteDetalle, idioma: Idioma, aFecha: string): string {
  const fecha = diaEscrito(aFecha, idioma);
  const consta = comoConsta(d, idioma);
  const paso = ultimoPasoQueCuenta(d);
  const detalle = paso === null ? "" : `; ${pasoEnFrase(paso, idioma)}`;
  const motivoDesmentido = d.estado.actual === "desmentido" ? (d.control.motivo_desmentido_traduccion?.[idioma] ?? null) : null;
  const desmentido = motivoDesmentido === null ? "" : `: ${motivoDesmentido.replace(/[\s.]+$/u, "")}`;
  const frase = idioma === "es" ? `A ${fecha} el caso consta como ${consta}${detalle}${desmentido}` : `As of ${fecha}, the case is recorded as ${consta}${detalle}${desmentido}`;
  return `${frase.replace(/[\s.]+$/u, "")}.`;
}

/** El párrafo entero, frase a frase; las frases sin datos no están. */
export function relato(d: IncidenteDetalle, idioma: Idioma, aFecha: string, opciones: OpcionesRelato = {}): string[] {
  return [queCuandoDonde(d, idioma, opciones), quienLoDijo(d, idioma), consecuencias(d, idioma), estadoActual(d, idioma, aFecha)].filter(
    (f): f is string => f !== null,
  );
}

/** Un paso de «Qué pasó después»: su fecha y lo que dice el historial. */
export interface PasoDespues {
  /** El instante del paso (ISO), para ordenar. */
  instante: string;
  fecha: string;
  texto: string;
  fuenteId: string | null;
}

/**
 * «Qué pasó después»: los pasos del historial que llegan tras la noticia, tal como están en él:
 * los cambios de la presencia de dron (con quién y por qué), la atribución, el desmentido, los
 * cambios de estado con su motivo y los cambios del punto. Vacío si no hay ninguno.
 */
export function queDespues(d: IncidenteDetalle, idioma: Idioma): PasoDespues[] {
  const es = idioma === "es";
  const pasos: (Omit<PasoDespues, "instante"> & { orden: string })[] = [];
  const conPresencia = historialDePresencia(d);
  conPresencia.forEach((paso, i) => {
    // La primera confirmación ya es el estado del incidente: lo que cuenta es lo que viene después.
    if (i === 0 && paso.valor === "confirmada" && paso.cierre !== true && paso.parcial !== true) return;
    const valor: Record<string, Record<Idioma, string>> = {
      confirmada: { es: "Dron confirmado", en: "Drone confirmed" },
      no_confirmada: { es: "Dron no confirmado", en: "Drone not confirmed" },
      no_acreditada: { es: "Dron no acreditado", en: "Drone not substantiated" },
      descartada: { es: "Dron descartado", en: "Drone ruled out" },
    };
    const rotulo = paso.cierre === true ? (es ? "Investigación cerrada" : "Investigation closed") : paso.parcial === true ? (es ? "Corrección parcial" : "Partial correction") : valor[paso.valor]?.[idioma] ?? paso.valor;
    const quien = paso.quien?.[idioma] ?? null;
    const motivo = paso.motivo?.[idioma] ?? null;
    const segun = quien === null ? "" : es ? `, según ${quien}` : `, according to ${quien}`;
    pasos.push({
      orden: paso.fecha.valor,
      fecha: diaEscrito(paso.fecha.valor, idioma),
      texto: `${rotulo}${segun}${motivo === null ? "" : `: ${motivo}`}`,
      fuenteId: paso.fuente_id,
    });
  });
  for (const paso of d.estado.historial) {
    if (paso.estado !== "atribuido" && paso.estado !== "desmentido" && paso.motivo === undefined) continue;
    const nombre: Record<string, Record<Idioma, string>> = {
      notificado: { es: "Notificado", en: "Reported" },
      confirmado: { es: "Confirmado", en: "Confirmed" },
      atribuido: { es: "Atribuido", en: "Attributed" },
      desmentido: { es: "Desmentido", en: "Denied" },
    };
    const fuente = paso.fuente_id === undefined ? undefined : d.fuentes.find((f) => f.id === paso.fuente_id);
    const quien = fuente === undefined ? null : medioEnFrase(fuente.medio, idioma, (a, m) => (es ? `${a} (declaración citada en ${m})` : `${a} (statement quoted by ${m})`));
    const detalle = paso.motivo?.[idioma] ?? (quien === null ? null : es ? `según ${quien}` : `according to ${quien}`);
    pasos.push({
      orden: paso.fecha.valor,
      fecha: diaEscrito(paso.fecha.valor, idioma),
      texto: detalle === null ? nombre[paso.estado]?.[idioma] ?? paso.estado : `${nombre[paso.estado]?.[idioma] ?? paso.estado}: ${detalle}`,
      fuenteId: paso.fuente_id ?? null,
    });
  }
  for (const cambio of d.lugar.historial ?? []) {
    pasos.push({
      orden: cambio.fecha.valor,
      fecha: diaEscrito(cambio.fecha.valor, idioma),
      texto: `${es ? "Lugar corregido" : "Location corrected"}: ${cambio.motivo[idioma]}`,
      fuenteId: null,
    });
  }
  return pasos.sort((a, b) => a.orden.localeCompare(b.orden)).map(({ orden, fecha, texto, fuenteId }) => ({ instante: orden, fecha, texto, fuenteId }));
}

/** La fecha del estado para el título y la descripción: «27/10/2026». */
export function fechaCorta(aFecha: string): string {
  const f = new Date(aFecha);
  return `${dosCifras(f.getUTCDate())}/${dosCifras(f.getUTCMonth() + 1)}/${f.getUTCFullYear()}`;
}

/** Cómo consta, corto y sin fecha, para la imagen: «no acreditado», «atribuido a Rusia por …». */
export function constaCorto(d: IncidenteDetalle, idioma: Idioma): string {
  return comoConsta(d, idioma).replace(/ \(.*\)$/u, "");
}

/** Cómo consta, corto, para el título: «no acreditado a 27/10/2026». */
export function estadoCorto(d: IncidenteDetalle, idioma: Idioma, aFecha: string): string {
  const consta = constaCorto(d, idioma);
  return idioma === "es" ? `${consta} a ${fechaCorta(aFecha)}` : `${consta} as of ${fechaCorta(aFecha)}`;
}
