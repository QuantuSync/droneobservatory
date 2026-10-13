// Los nombres de lugar de la ficha en el idioma de la página. Los escribe la publicación
// (proceso/nombres_lugar.py, campo `nombres` de cada incidente): «Pafos, Chipre» en la versión
// española y «Paphos, Cyprus» en la inglesa, el aeropuerto como «Aeropuerto de Pafos» /
// «Paphos International Airport», Akrotiri como «RAF Akrotiri (base británica), Chipre». Sin ese
// campo (datos publicados antes del 13 de octubre de 2026), lo que ya hacía la web
// (i18n/nombresLugar.ts), sin pasar nunca otra escritura al alfabeto latino.

import { pais } from "../i18n/index.ts";
import { nombreDeLugar } from "../i18n/nombresLugar.ts";
import type { Idioma } from "../sitio.ts";
import type { NombresLugar } from "./tipos.ts";

/** Lo que la ficha necesita del incidente para escribir sus lugares. */
export interface ConNombres {
  nombres?: NombresLugar | undefined;
  lugar: {
    pais: string;
    localidad?: string | undefined;
    region?: string | undefined;
    otros_lugares?: readonly { nombre: string }[] | undefined;
    historial?: readonly { anterior: { localidad?: string | undefined } }[] | undefined;
  };
  objetivo?: { nombre?: string | undefined } | undefined;
}

/**
 * Países donde tiene sentido «Frontera o interior»: los que tienen frontera con Ucrania, Rusia
 * (también Kaliningrado) o Bielorrusia o costa en el mar Negro. En el resto de Europa y en
 * ultramar la ficha no enseña esa fila. La misma lista que «flanco_este» de
 * configuracion/nombres_lugar.json (un test lo comprueba).
 */
export const FLANCO_ESTE: ReadonlySet<string> = new Set([
  "BG", "BY", "EE", "FI", "HU", "LT", "LV", "MD", "NO", "PL", "RO", "RU", "SK", "UA",
]);

/** El país donde pasó, aunque los datos digan otro (Akrotiri: Chipre; Gibraltar: GI). */
export function paisGeografico(d: ConNombres): string {
  return d.nombres?.pais_geografico ?? d.lugar.pais;
}

/** Si la fila «Frontera o interior» tiene sentido para este lugar. */
export function enFlancoEste(d: ConNombres): boolean {
  return FLANCO_ESTE.has(paisGeografico(d));
}

/** La fila «Lugar»: localidad (o lo que se sepa) y país o territorio. */
export function lugarEscrito(d: ConNombres, idioma: Idioma, conRegion: boolean): string {
  if (d.nombres !== undefined) return d.nombres.lugar[idioma];
  const partes: string[] = [];
  const localidad = d.lugar.localidad === undefined ? null : nombreDeLugar(d.lugar.localidad, idioma);
  if (localidad !== null) partes.push(localidad);
  const region = conRegion && d.lugar.region !== undefined ? nombreDeLugar(d.lugar.region, idioma) : null;
  if (region !== null) partes.push(region);
  partes.push(pais(d.lugar.pais, idioma));
  return partes.join(", ");
}

/** La localidad sola (para los datos estructurados y los avisos), o null si no se conoce. */
export function localidadEscrita(d: ConNombres, idioma: Idioma): string | null {
  if (d.nombres !== undefined) return d.nombres.localidad?.[idioma] ?? null;
  return d.lugar.localidad === undefined ? null : nombreDeLugar(d.lugar.localidad, idioma);
}

/** El nombre del aeropuerto, la base o la instalación; null si no se puede escribir bien. */
export function objetivoEscrito(d: ConNombres, idioma: Idioma): string | null {
  if (d.nombres !== undefined) return d.nombres.objetivo?.[idioma] ?? null;
  const nombre = d.objetivo?.nombre;
  return nombre === undefined ? null : nombreDeLugar(nombre, idioma);
}

/** La región que nombra la fuente; null si no se puede escribir bien. */
export function regionEscrita(d: ConNombres, idioma: Idioma): string | null {
  if (d.nombres !== undefined) return d.nombres.region?.[idioma] ?? null;
  return d.lugar.region === undefined ? null : nombreDeLugar(d.lugar.region, idioma);
}

/** El nombre del i-ésimo de los demás lugares; null si no se puede escribir bien. */
export function otroLugarEscrito(d: ConNombres, indice: number, idioma: Idioma): string | null {
  if (d.nombres?.otros !== undefined) return d.nombres.otros[indice]?.[idioma] ?? null;
  const nombre = d.lugar.otros_lugares?.[indice]?.nombre;
  return nombre === undefined ? null : nombreDeLugar(nombre, idioma);
}

/** La localidad del i-ésimo punto anterior; null si no se puede escribir bien. */
export function anteriorEscrito(d: ConNombres, indice: number, idioma: Idioma): string | null {
  if (d.nombres?.anteriores !== undefined) return d.nombres.anteriores[indice]?.[idioma] ?? null;
  const nombre = d.lugar.historial?.[indice]?.anterior.localidad;
  return nombre === undefined ? null : nombreDeLugar(nombre, idioma);
}

/**
 * El modelo de dron, solo si es un nombre de modelo («Shahed 136», «Gerbera», «Geran-2»): lo que
 * la fuente describe en su lengua («drone russe», «крило», «10ft») no se enseña.
 */
export function modeloEscrito(modelo: string | undefined): string | null {
  if (modelo === undefined) return null;
  return /^[A-Z][A-Za-z]*(?:[ -]?[A-Za-z0-9]+)*$/.test(modelo) ? modelo : null;
}

// --- Capa de guerra ---------------------------------------------------------------------------

type Bilingue = { es: string; en: string };

/**
 * Ciudades de Ucrania y Rusia con nombre propio en español o en inglés, por su nombre en alfabeto
 * latino de los datos (el de la prensa inglesa). Lo demás, con ese nombre.
 */
const EXONIMOS_GUERRA: Readonly<Record<string, Bilingue>> = {
  Kyiv: { es: "Kiev", en: "Kyiv" },
  Kharkiv: { es: "Járkov", en: "Kharkiv" },
  Odesa: { es: "Odesa", en: "Odesa" },
  Lviv: { es: "Leópolis", en: "Lviv" },
  Dnipro: { es: "Dnipró", en: "Dnipro" },
  Zaporizhzhia: { es: "Zaporiyia", en: "Zaporizhzhia" },
  Kherson: { es: "Jersón", en: "Kherson" },
  Mykolaiv: { es: "Mikoláiv", en: "Mykolaiv" },
  Chernihiv: { es: "Chernígov", en: "Chernihiv" },
  Izmail: { es: "Izmaíl", en: "Izmail" },
  Moskva: { es: "Moscú", en: "Moscow" },
  Moscow: { es: "Moscú", en: "Moscow" },
  "Sankt-Peterburg": { es: "San Petersburgo", en: "Saint Petersburg" },
  Novorossiysk: { es: "Novorosíisk", en: "Novorossiysk" },
  Bryansk: { es: "Briansk", en: "Bryansk" },
  Belgorod: { es: "Bélgorod", en: "Belgorod" },
};

/**
 * Lugares e instalaciones de la capa de guerra que los datos solo dan en cirílico (sin nombre en
 * alfabeto latino), escritos a mano (13 de octubre de 2026).
 */
const SIN_LATINO_GUERRA: Readonly<Record<string, Bilingue>> = {
  "Саратовский нефтеперерабатывающий завод": { es: "Refinería de Sarátov", en: "Saratov Oil Refinery" },
  Адріанівка: { es: "Adrianivka", en: "Adrianivka" },
  Семенівка: { es: "Semenivka", en: "Semenivka" },
  Прикордонне: { es: "Prykordonne", en: "Prykordonne" },
  "Военный аэродром Саки": { es: "Base aérea de Saki", en: "Saki Air Base" },
  "Нефтегавань Шесхарис": { es: "Terminal petrolera de Sheskharis", en: "Sheskharis Oil Terminal" },
  "порт Темрюк": { es: "Puerto de Temriuk", en: "Port of Temryuk" },
  Незламне: { es: "Nezlamne", en: "Nezlamne" },
  Нафтобаза: { es: "Depósito de combustible", en: "Fuel depot" },
  "порт Выборг": { es: "Puerto de Víborg", en: "Port of Vyborg" },
  Шесхариз: { es: "Terminal petrolera de Sheskharis", en: "Sheskharis Oil Terminal" },
  "Асфальто-бетонный завод": { es: "Planta de asfalto", en: "Asphalt plant" },
  Галицьке: { es: "Halytske", en: "Halytske" },
  "Лозівський ковальсько-механічний завод (ЛКМЗ)": { es: "Planta de forja de Lozova", en: "Lozova Forging and Mechanical Plant" },
  Високе: { es: "Vysoke", en: "Vysoke" },
  Радуга: { es: "Planta Raduga", en: "Raduga plant" },
};

/** Las localidades de las instalaciones de la capa de guerra, que los datos dan en cirílico. */
const LOCALIDADES_GUERRA: Readonly<Record<string, Bilingue>> = {
  Саратовъ: { es: "Sarátov", en: "Saratov" },
  Высоцк: { es: "Vysotsk", en: "Vysotsk" },
  Туапсэ: { es: "Tuapsé", en: "Tuapse" },
  Кириши: { es: "Kirishi", en: "Kirishi" },
  Донецьк: { es: "Donetsk", en: "Donetsk" },
  Темрюк: { es: "Temriuk", en: "Temryuk" },
  Новороссийск: { es: "Novorosíisk", en: "Novorossiysk" },
  Курчатов: { es: "Kurchátov", en: "Kurchatov" },
  Орёл: { es: "Oriol", en: "Oryol" },
  Прилуки: { es: "Prilukí", en: "Pryluky" },
  Саки: { es: "Saki", en: "Saki" },
  Одеса: { es: "Odesa", en: "Odesa" },
  Семенівка: { es: "Semenivka", en: "Semenivka" },
  Київ: { es: "Kiev", en: "Kyiv" },
  "Одеський район": { es: "distrito de Odesa", en: "Odesa district" },
  "Лозівський район": { es: "distrito de Lozova", en: "Lozova district" },
};

/**
 * El nombre del lugar de un impacto de la capa de guerra en el idioma de la página: la ciudad
 * con su nombre español o inglés, la comunidad («comunidad de Khotin» / «Khotin community») o el
 * distrito, o el nombre en alfabeto latino. Nunca el cirílico ni una transcripción hecha aquí; si
 * no hay nombre latino, null (la ficha pone la región).
 */
export function lugarDeImpacto(
  lugar: { nombre: string; nombre_latino?: string | undefined; nivel: string },
  idioma: Idioma,
): string | null {
  const escrito = SIN_LATINO_GUERRA[lugar.nombre.normalize("NFC")];
  if (escrito !== undefined) return escrito[idioma];
  const latino = lugar.nombre_latino;
  if (latino === undefined || latino === "") return null;
  const exonimo = EXONIMOS_GUERRA[latino];
  if (exonimo !== undefined) return exonimo[idioma];
  const comunidad = /^(.+) hromada$/.exec(latino);
  if (comunidad?.[1] !== undefined) return idioma === "es" ? `comunidad de ${comunidad[1]}` : `${comunidad[1]} community`;
  const distrito = /^(.+) raion$/.exec(latino);
  if (distrito?.[1] !== undefined) return idioma === "es" ? `distrito de ${distrito[1]}` : `${distrito[1]} district`;
  return latino;
}

/** La localidad de una instalación de la capa de guerra; null si no se sabe escribir bien. */
export function localidadDeImpacto(localidad: string, idioma: Idioma): string | null {
  const escrita = LOCALIDADES_GUERRA[localidad.normalize("NFC")];
  if (escrita !== undefined) return escrita[idioma];
  return /^[\p{Script=Latin}\p{Script=Common}]+$/u.test(localidad) ? localidad : null;
}
