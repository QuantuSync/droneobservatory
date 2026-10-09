// Textos del tipo de dron (es y en): la fila de la ficha y las razones de lo
// deducido. Lo deducido se dice siempre como «compatible con»: con porcentajes solo si un grupo
// destaca de verdad; si no, «compatible con un dron de largo alcance de la guerra». El modelo solo
// sale cuando lo nombra la autoridad.

import type { RazonTipoDron } from "../datos/tipos.ts";
import type { TextosTipoDron } from "./tipos.ts";

function redondo(n: number, idioma: "es" | "en"): string {
  return new Intl.NumberFormat(idioma, { maximumFractionDigits: 0 }).format(n);
}

function cita(razon: RazonTipoDron, idioma: "es" | "en"): string {
  const texto = razon.datos?.cita;
  if (!texto) return "";
  return idioma === "es" ? `: «${texto}»` : `: “${texto}”`;
}

const RASGOS_ES: Record<string, string> = {
  "forma:multirrotor": "Descrito como multirrotor (varias hélices)",
  "forma:ala_fija": "Descrito como de ala fija",
  "forma:ala_delta": "Descrito con ala en delta",
  "ruido:reaccion": "Descrito como de reacción",
  "ruido:combustion": "Descrito con ruido de motor de combustión",
  "ruido:helice": "Descrito con hélice",
  "tamano:pequeno": "Descrito como pequeño",
  "tamano:grande": "Descrito como grande",
  "comportamiento:estatico": "Descrito quieto en el aire",
  "comportamiento:merodeo": "Descrito dando vueltas sobre el sitio",
};
const RASGOS_EN: Record<string, string> = {
  "forma:multirrotor": "Described as a multirotor (several rotors)",
  "forma:ala_fija": "Described as fixed-wing",
  "forma:ala_delta": "Described with a delta wing",
  "ruido:reaccion": "Described as jet-powered",
  "ruido:combustion": "Described with a combustion-engine sound",
  "ruido:helice": "Described with a propeller",
  "tamano:pequeno": "Described as small",
  "tamano:grande": "Described as large",
  "comportamiento:estatico": "Described hovering in place",
  "comportamiento:merodeo": "Described circling over the site",
};

function razonEs(r: RazonTipoDron): string {
  const d = r.datos ?? {};
  if (r.tipo === "rasgo") return `${RASGOS_ES[r.clave] ?? r.clave}${cita(r, "es")}`;
  if (r.clave === "entrada_exterior") {
    return `Entró desde fuera, a ${redondo(d.distancia_km ?? 0, "es")} km de Ucrania, Rusia o Bielorrusia: dentro del alcance de los drones de largo alcance que se lanzan en la guerra`;
  }
  if (r.clave === "distancia") {
    const lejos = d.mas_de_600_km
      ? "a más de 600 km de Ucrania, Rusia y Bielorrusia"
      : `a ${redondo(d.distancia_km ?? 0, "es")} km de Ucrania, Rusia o Bielorrusia`;
    const entrada = d.entrada_exterior ? ", entrado desde fuera," : "";
    return `Lugar ${lejos}${entrada} frente al alcance de cada clase: las que no llegan pierden probabilidad`;
  }
  if (r.clave === "velocidad") {
    return `Velocidad de ${redondo(d.kmh ?? 0, "es")} km/h${cita(r, "es")}. Por debajo de 230 km/h, hélice; por encima de 300 km/h, reacción; entre medias no decide`;
  }
  if (r.clave === "altura") {
    return `Altura de ${redondo(d.metros ?? 0, "es")} m${cita(r, "es")}, frente al techo de cada clase`;
  }
  if (r.clave === "duracion") {
    return `Vuelo de ${redondo(d.minutos ?? 0, "es")} min${cita(r, "es")}, frente a la autonomía de cada clase`;
  }
  if (r.clave === "meteorologia") {
    return "Viento y temperatura de esa hora y ese lugar, frente a lo que aguanta cada clase";
  }
  return `Regla física «${r.clave}» del motor de deducción`;
}

function razonEn(r: RazonTipoDron): string {
  const d = r.datos ?? {};
  if (r.tipo === "rasgo") return `${RASGOS_EN[r.clave] ?? r.clave}${cita(r, "en")}`;
  if (r.clave === "entrada_exterior") {
    return `It entered from outside, ${redondo(d.distancia_km ?? 0, "en")} km from Ukraine, Russia or Belarus: within the range of the long-range drones launched in the war`;
  }
  if (r.clave === "distancia") {
    const lejos = d.mas_de_600_km
      ? "more than 600 km from Ukraine, Russia and Belarus"
      : `${redondo(d.distancia_km ?? 0, "en")} km from Ukraine, Russia or Belarus`;
    const entrada = d.entrada_exterior ? ", having entered from outside," : "";
    return `Location ${lejos}${entrada} against the range of each class: those that cannot reach it lose probability`;
  }
  if (r.clave === "velocidad") {
    return `Speed of ${redondo(d.kmh ?? 0, "en")} km/h${cita(r, "en")}. Below 230 km/h, propeller; above 300 km/h, jet; in between it does not decide`;
  }
  if (r.clave === "altura") {
    return `Altitude of ${redondo(d.metros ?? 0, "en")} m${cita(r, "en")}, against the ceiling of each class`;
  }
  if (r.clave === "duracion") {
    return `Flight of ${redondo(d.minutos ?? 0, "en")} min${cita(r, "en")}, against the endurance of each class`;
  }
  if (r.clave === "meteorologia") {
    return "Wind and temperature at that time and place, against what each class can withstand";
  }
  return `Physical rule “${r.clave}” of the deduction engine`;
}

export const tipoDronEs: TextosTipoDron = {
  fila: "Tipo de dron",
  grupos: {
    comercial_pequeno: "Multirrotor comercial pequeño o mediano",
    multirrotor_grande: "Multirrotor grande de carga",
    fpv: "Dron FPV",
    ala_fija_pequena: "Ala fija pequeña o táctica eléctrica",
    ala_fija_militar: "Ala fija militar de reconocimiento o munición merodeadora",
    largo_alcance_helice: "Dron de ataque de largo alcance de hélice",
    senuelo: "Señuelo de largo alcance",
    reaccion: "Dron de ataque a reacción",
  },
  identificado: (modelo) => `${modelo}, según la autoridad`,
  grupoDe: (grupo) => `Clase: ${grupo.toLowerCase()}`,
  compatibleCon: "Compatible con",
  compatibleGuerra: "Compatible con un dron de largo alcance de la guerra (de ataque o señuelo)",
  probabilidad: (p) => `${Math.round(p / 10)} de cada 10 (${p} %)`,
  otras: (p) => `Otras clases: ${p} %`,
  deducido: "Deducido por el observatorio a partir de lo publicado; ninguna autoridad ha dicho qué dron era.",
  porQue: "Por qué",
  base: (casos, zona) =>
    `Punto de partida: la frecuencia de cada clase en ${casos} casos ${zona} en que una autoridad identificó el dron.`,
  zonas: { frontera: "de frontera", interior: "del interior" },
  razon: razonEs,
};

export const tipoDronEn: TextosTipoDron = {
  fila: "Drone type",
  grupos: {
    comercial_pequeno: "Small or medium commercial multirotor",
    multirrotor_grande: "Large heavy-lift multirotor",
    fpv: "FPV drone",
    ala_fija_pequena: "Small or tactical electric fixed-wing",
    ala_fija_militar: "Military reconnaissance fixed-wing or loitering munition",
    largo_alcance_helice: "Propeller long-range attack drone",
    senuelo: "Long-range decoy",
    reaccion: "Jet-powered attack drone",
  },
  identificado: (modelo) => `${modelo}, according to the authority`,
  grupoDe: (grupo) => `Class: ${grupo.toLowerCase()}`,
  compatibleCon: "Compatible with",
  compatibleGuerra: "Compatible with a long-range drone of the war (attack or decoy)",
  probabilidad: (p) => `${Math.round(p / 10)} in 10 (${p}%)`,
  otras: (p) => `Other classes: ${p}%`,
  deducido: "Deduced by the observatory from what has been published; no authority has said which drone it was.",
  porQue: "Why",
  base: (casos, zona) =>
    `Starting point: how often each class appears in ${casos} ${zona} cases where an authority identified the drone.`,
  zonas: { frontera: "border", interior: "inland" },
  razon: razonEn,
};
