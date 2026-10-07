// Textos de las rutas de los drones sobre Ucrania y del recorrido de las incursiones (es y en).
// Cada grupo es un recorrido de su origen a su final, con un halo de incertidumbre: nunca una
// línea exacta. Lo derivado de NEPTUN lleva siempre su enlace.

import type { TextosRutas } from "./tipos.ts";

export const rutasEs: TextosRutas = {
  subcapa: "Rutas",
  leyenda: (n, total) =>
    n === total
      ? total === 1
        ? "1 grupo"
        : `${total} grupos`
      : `${n} de ${total} grupos, los de más drones`,
  sinRutas: "Esta noche no tiene rutas publicadas.",
  cargando: "Cargando las rutas…",
  comoSeLee: "Por dónde entró cada grupo (tenue) y hacia dónde fue (flecha). El halo es la incertidumbre.",
  otraNoche: "Otra noche: «Noche a noche».",
  nota: "El halo es la incertidumbre de la posición, no una línea exacta.",
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
  precisionKm: (km) => `${km} km a cada lado`,
  precisionEntre: (min, max) => `de ${min} a ${max} km a cada lado`,
  recorridoGrupo: "Recorrido",
  longitud: (km) => `${km} km`,
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
  sinIdentidad:
    "Un grupo es lo que se sigue sin dudas: si no se sabe si dos tramos son el mismo grupo, no se unen.",
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
        ? "1 group"
        : `${total} groups`
      : `${n} of ${total} groups, those with the most drones`,
  sinRutas: "This night has no published routes.",
  cargando: "Loading the routes…",
  comoSeLee: "Where each group came in (faint) and where it went (arrow). The halo is the uncertainty.",
  otraNoche: "Another night: “Night by night”.",
  nota: "The halo is the position uncertainty, not an exact line.",
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
  precisionKm: (km) => `${km} km either side`,
  precisionEntre: (min, max) => `${min} to ${max} km either side`,
  recorridoGrupo: "Route",
  longitud: (km) => `${km} km`,
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
  sinIdentidad:
    "A group is what can be followed without doubt: if it is unclear whether two segments are the same group, they are not joined.",
  mensajes: "Air Force messages",
  pista: "NEPTUN track",
  incidentes: "Ends at incidents that night",
  ataque: "That night's attack",
  recorrido: "Route according to the authority",
  recorridoNota: "The places the authority names, in order; the band joins each pair.",
};
