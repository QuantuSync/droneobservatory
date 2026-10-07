// Textos de las rutas de los drones sobre Ucrania y del recorrido de las incursiones (es y en).
// Las rutas son franjas con su anchura de incertidumbre, nunca líneas exactas; lo derivado de
// NEPTUN lleva siempre su enlace.

import type { TextosRutas } from "./tipos.ts";

export const rutasEs: TextosRutas = {
  subcapa: "Rutas",
  leyenda: (n, total) =>
    n === total
      ? total === 1
        ? "Rutas de 1 noche"
        : `Rutas de ${total} noches`
      : `Rutas de las ${n} noches con más drones, de ${total} del periodo`,
  leyendaNoche: "Rutas de esta noche",
  sinRutas: "Ninguna noche del periodo tiene rutas publicadas.",
  cargando: "Cargando las rutas…",
  nota: "Franjas con su anchura de incertidumbre, no líneas exactas.",
  fuente: {
    neptun: "estimación de NEPTUN a partir de informes (no es un radar)",
    fuerza_aerea: "reconstruida con los mensajes de seguimiento de la Fuerza Aérea de Ucrania",
  },
  etiqueta: "Ruta · capa de Ucrania",
  noche: "Noche",
  grupo: "Grupo",
  grupoNumero: (n) => `n.º ${n}`,
  aparatos: "Aparatos",
  tipo: "Tipo",
  tipos: { ataque: "Dron de ataque", reaccion: "Dron a reacción", reconocimiento: "Dron de reconocimiento" },
  velocidad: "Velocidad",
  kmh: (n) => `${n} km/h`,
  origen: "Fuente",
  precision: "Precisión",
  precisionKm: (km) => `franja de ${km} km de radio`,
  tramo: "Tramo",
  clases: {
    enlace: "entre dos mensajes de seguimiento",
    hacia_destino: "hacia el destino que dice el mensaje",
    desde_lanzamiento: "desde la zona de lanzamiento de esa noche",
    neptun: "entre dos posiciones estimadas",
  },
  desde: "Desde",
  hasta: "Hasta",
  division: "El grupo se divide aquí.",
  union: "Aquí se unen dos grupos.",
  sinIdentidad: "Los grupos no se identifican por el texto: un tramo enlaza dos avisos, nada más.",
  mensajes: "Mensajes de la Fuerza Aérea",
  pista: "Pista de NEPTUN",
  incidentes: "Acaba en incidentes de esa noche",
  ataque: "Ataque de esa noche",
  recorrido: "Recorrido según la autoridad",
  recorridoNota: "Los lugares que nombra la autoridad, en orden; la franja une cada dos.",
};

export const rutasEn: TextosRutas = {
  subcapa: "Routes",
  leyenda: (n, total) =>
    n === total
      ? total === 1
        ? "Routes of 1 night"
        : `Routes of ${total} nights`
      : `Routes of the ${n} nights with the most drones, of ${total} in the period`,
  leyendaNoche: "Routes of this night",
  sinRutas: "No night in the period has published routes.",
  cargando: "Loading the routes…",
  nota: "Bands with their uncertainty width, not exact lines.",
  fuente: {
    neptun: "NEPTUN estimate from reports (not a radar)",
    fuerza_aerea: "reconstructed from the Ukrainian Air Force tracking messages",
  },
  etiqueta: "Route · Ukraine layer",
  noche: "Night",
  grupo: "Group",
  grupoNumero: (n) => `no. ${n}`,
  aparatos: "Aircraft",
  tipo: "Type",
  tipos: { ataque: "Attack drone", reaccion: "Jet-powered drone", reconocimiento: "Reconnaissance drone" },
  velocidad: "Speed",
  kmh: (n) => `${n} km/h`,
  origen: "Source",
  precision: "Precision",
  precisionKm: (km) => `band of ${km} km radius`,
  tramo: "Segment",
  clases: {
    enlace: "between two tracking messages",
    hacia_destino: "towards the destination the message gives",
    desde_lanzamiento: "from that night's launch area",
    neptun: "between two estimated positions",
  },
  desde: "From",
  hasta: "To",
  division: "The group splits here.",
  union: "Two groups join here.",
  sinIdentidad: "Groups are not identified from the text: a segment links two reports, nothing more.",
  mensajes: "Air Force messages",
  pista: "NEPTUN track",
  incidentes: "Ends at incidents that night",
  ataque: "That night's attack",
  recorrido: "Route according to the authority",
  recorridoNota: "The places the authority names, in order; the band joins each pair.",
};
