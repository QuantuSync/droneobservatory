// Página «Registro de correcciones» / «Corrections log»: cada corrección de un incidente ya
// publicado, de la más reciente a la más antigua, con su fecha, el incidente, lo que cambió y el
// motivo. Sale sola de correcciones.json (exportacion/correcciones.py), que la recogida saca de
// lo que la base ya guarda. Es una página de texto: se lee sin ejecutar código. Se enlaza desde
// «Correcciones», desde «Metodología y datos abiertos» y desde el pie de las páginas de texto;
// nunca desde la pantalla del mapa.

import { anclaDeCorreccion, enlaceACorreccion, RUTAS_REGISTRO } from "../datos/correcciones.ts";
import type { CambioCorregido, Correccion, LugarCorregido, RegistroCorrecciones } from "../datos/correcciones.ts";
import { fecha, pais, textos } from "../i18n/index.ts";
import { NOMBRE, rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import type { Hijo, Html } from "./html.ts";

export { enlaceACorreccion, RUTAS_REGISTRO };

interface TextosRegistro {
  titulo: string;
  enlace: string;
  descripcion: string;
  intro: string;
  criterioTitulo: string;
  criterio: readonly string[];
  noEntra: string;
  comoSeHace: string;
  generado: (cuando: string, n: number) => string;
  vacio: string;
  indice: string;
  incidente: string;
  sinPagina: string;
  motivo: string;
  aMano: string;
  regla: string;
  aviso: string;
  titular: string;
  antes: string;
  ahora: string;
  estado: string;
  presencia: string;
  lugar: string;
  atribucionRetirada: string;
  atribucionCambiada: string;
  unido: string;
  retirado: string;
  sinValor: string;
  de: (antes: string, despues: string) => string;
  meses: readonly string[];
  /** Enlace desde la página «Correcciones». */
  verRegistro: string;
}

const ES: TextosRegistro = {
  titulo: "Registro de correcciones",
  enlace: "Registro de correcciones",
  descripcion: `Qué ha corregido el ${NOMBRE} en los incidentes que ya había publicado: cuándo, en qué incidente, qué cambió y por qué.`,
  intro: "Cada corrección de un incidente que ya estaba publicado, de la más reciente a la más antigua: cuándo se hizo, en qué incidente, qué cambió y por qué. Nada se borra: lo que se retira o se une a otro incidente queda marcado con su motivo.",
  criterioTitulo: "Qué entra en este registro",
  criterio: [
    "Entra cada cambio en un incidente que ya se había publicado, hecho al revisar su contenido (a mano o con una regla de revisión aplicada a lo ya publicado) y guardado con su motivo, que cambia lo que el observatorio decía de él: el titular, el estado, el lugar, la atribución o la presencia del dron, su unión con otro incidente o su retirada.",
    "«Ya publicado» quiere decir que el incidente salió en una publicación anterior a la del cambio: estaba en los datos al terminar una recogida anterior.",
  ],
  noEntra: "No entran los datos nuevos (fuentes y citas nuevas, una autoridad que confirma o atribuye un suceso, las noticias que se unen a su suceso al registrarlas) ni lo que la recogida recalcula cada hora (frontera o interior, episodios, tipo de dron, mediciones). Este criterio se aplica igual a todo el historial.",
  comoSeHace: "El registro sale solo de lo que la base de datos ya guarda: el historial de cada incidente con su motivo, las retiradas y las uniones. Se rehace con cada recogida.",
  generado: (cuando, n) => `${n} correcciones; la más reciente, del ${cuando}.`,
  vacio: "Todavía no hay ninguna corrección.",
  indice: "Meses",
  incidente: "Incidente",
  sinPagina: "ya no se publica",
  motivo: "Motivo",
  aMano: "Revisión a mano",
  regla: "Regla de revisión",
  aviso: "A raíz de un aviso de un lector.",
  titular: "Titular",
  antes: "antes",
  ahora: "ahora",
  estado: "Estado",
  presencia: "Presencia del dron",
  lugar: "Lugar",
  atribucionRetirada: "Atribución retirada",
  atribucionCambiada: "Atribución corregida",
  unido: "Unido a otro incidente del mismo suceso:",
  retirado: "Retirado: deja de publicarse",
  sinValor: "sin dato",
  de: (antes, despues) => `de ${antes} a ${despues}`,
  meses: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
  verRegistro: "Todas las correcciones hechas, con su fecha y su motivo, están en el registro de correcciones.",
};

const EN: TextosRegistro = {
  titulo: "Corrections log",
  enlace: "Corrections log",
  descripcion: `What the ${NOMBRE} has corrected in incidents it had already published: when, in which incident, what changed and why.`,
  intro: "Every correction to an incident that had already been published, most recent first: when it was made, in which incident, what changed and why. Nothing is deleted: whatever is withdrawn or joined to another incident stays marked with its reason.",
  criterioTitulo: "What goes into this log",
  criterio: [
    "Every change to an incident that had already been published goes in, when it was made by reviewing its content (by hand or with a review rule applied to what was already published), was stored with its reason, and changes what the observatory said about it: the headline, the status, the place, the attribution or the drone's presence, its joining with another incident or its withdrawal.",
    "«Already published» means the incident was in a publication before the change: it was in the data at the end of an earlier collection run.",
  ],
  noEntra: "New data does not go in (new sources and quotes, an authority confirming or attributing an event, reports joined to their event when they are recorded), nor what the collection recalculates every hour (border or inland, episodes, drone type, measurements). This rule is applied in the same way to the whole history.",
  comoSeHace: "The log comes only from what the database already keeps: each incident's history with its reason, the withdrawals and the joins. It is rebuilt with every collection run.",
  generado: (cuando, n) => `${n} corrections; the most recent on ${cuando}.`,
  vacio: "There are no corrections yet.",
  indice: "Months",
  incidente: "Incident",
  sinPagina: "no longer published",
  motivo: "Reason",
  aMano: "Reviewed by hand",
  regla: "Review rule",
  aviso: "Following a reader's report.",
  titular: "Headline",
  antes: "before",
  ahora: "now",
  estado: "Status",
  presencia: "Drone presence",
  lugar: "Place",
  atribucionRetirada: "Attribution withdrawn",
  atribucionCambiada: "Attribution corrected",
  unido: "Joined to another incident of the same event:",
  retirado: "Withdrawn: no longer published",
  sinValor: "no data",
  de: (antes, despues) => `from ${antes} to ${despues}`,
  meses: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  verRegistro: "Every correction made, with its date and its reason, is in the corrections log.",
};

export function textosRegistro(idioma: Idioma): TextosRegistro {
  return idioma === "en" ? EN : ES;
}

/** El día de un instante UTC, dd/mm/aaaa. */
export function diaDeCorreccion(instante: string): string {
  return fecha(new Date(instante));
}

function nombreLugar(lugar: LugarCorregido | null, idioma: Idioma, t: TextosRegistro): string {
  if (lugar === null) return t.sinValor;
  const nombrePais = lugar.pais === null ? null : pais(lugar.pais, idioma);
  if (lugar.nombre === undefined) return nombrePais ?? t.sinValor;
  return nombrePais === null ? lugar.nombre : `${lugar.nombre} (${nombrePais})`;
}

function cambio(c: CambioCorregido, idioma: Idioma, publicados: ReadonlySet<string>): Html {
  const t = textosRegistro(idioma);
  const tx = textos(idioma);
  switch (c.campo) {
    case "titulo":
      return e(
        "li",
        { "data-cambio": "titulo" },
        `${t.titular}: `,
        t.antes,
        " «",
        c.antes?.[idioma] ?? t.sinValor,
        "»; ",
        t.ahora,
        " «",
        c.despues?.[idioma] ?? t.sinValor,
        "».",
      );
    case "estado":
      return e("li", { "data-cambio": "estado" }, `${t.estado}: `, t.de(c.antes === null ? t.sinValor : tx.estado[c.antes], c.despues === null ? t.sinValor : tx.estado[c.despues]), ".");
    case "presencia_dron":
      return e("li", { "data-cambio": "presencia_dron" }, `${t.presencia}: `, t.de(c.antes === null ? t.sinValor : tx.presencia[c.antes], c.despues === null ? t.sinValor : tx.presencia[c.despues]), ".");
    case "lugar":
      return e("li", { "data-cambio": "lugar" }, `${t.lugar}: `, t.de(nombreLugar(c.antes, idioma, t), nombreLugar(c.despues, idioma, t)), ".");
    case "atribucion":
      return e("li", { "data-cambio": "atribucion" }, c.retirada ? t.atribucionRetirada : t.atribucionCambiada, ".");
    case "union":
      return e("li", { "data-cambio": "union" }, t.unido, " ", publicados.has(c.destino) ? e("a", { href: rutaDeFicha(c.destino, idioma) }, c.destino) : c.destino, ".");
    case "retirada":
      return e("li", { "data-cambio": "retirada" }, t.retirado, ".");
  }
}

function entrada(c: Correccion, idioma: Idioma, publicados: ReadonlySet<string>, ancla: boolean): Html {
  const t = textosRegistro(idioma);
  const conPagina = c.enlace !== null && publicados.has(c.enlace);
  const cabecera: Hijo[] = [
    e("time", { datetime: c.fecha }, diaDeCorreccion(c.fecha)),
    " · ",
    conPagina && c.enlace === c.incidente ? e("a", { href: rutaDeFicha(c.incidente, idioma) }, c.incidente) : c.incidente,
  ];
  if (!conPagina) cabecera.push(` (${t.sinPagina})`);
  return e(
    "article",
    { class: "texto-correccion", id: ancla && c.enlace !== null ? anclaDeCorreccion(c.enlace) : null, "data-incidente": c.incidente },
    e("h3", null, cabecera),
    c.titulo !== undefined && e("p", null, c.titulo[idioma]),
    e("ul", null, c.cambios.map((x) => cambio(x, idioma, publicados))),
    e("p", null, e("strong", null, `${t.motivo}: `), conMayuscula(c.motivo[idioma])),
    e("p", { class: "mono" }, c.revision === "a_mano" ? t.aMano : t.regla, c.a_raiz_de_un_aviso === true ? html(" · ", t.aviso) : null),
  );
}

function conMayuscula(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function mes(instante: string, idioma: Idioma): { clave: string; nombre: string } {
  const f = new Date(instante);
  const t = textosRegistro(idioma);
  const nombre = t.meses[f.getUTCMonth()] ?? "";
  return { clave: instante.slice(0, 7), nombre: idioma === "en" ? `${nombre} ${f.getUTCFullYear()}` : `${nombre} de ${f.getUTCFullYear()}` };
}

/** El cuerpo de la página: criterio, índice por meses y las entradas. */
export function cuerpoRegistro(registro: RegistroCorrecciones | null, idioma: Idioma, publicados: ReadonlySet<string>): Html {
  const t = textosRegistro(idioma);
  const correcciones = registro?.correcciones ?? [];
  const meses = new Map<string, { nombre: string; entradas: Correccion[] }>();
  for (const c of correcciones) {
    const m = mes(c.fecha, idioma);
    const grupo = meses.get(m.clave) ?? { nombre: m.nombre, entradas: [] };
    grupo.entradas.push(c);
    meses.set(m.clave, grupo);
  }
  // El ancla de cada incidente, en su entrada más reciente (la primera, porque van de la más
  // reciente a la más antigua).
  const conAncla = new Set<string>();
  const primeras = new Set<Correccion>();
  for (const c of correcciones) {
    if (c.enlace !== null && !conAncla.has(c.enlace)) {
      conAncla.add(c.enlace);
      primeras.add(c);
    }
  }
  return html(
    e("h1", null, t.titulo),
    e("p", null, t.intro),
    e(
      "section",
      { id: "criterio" },
      e("h2", null, t.criterioTitulo),
      t.criterio.map((p) => e("p", null, p)),
      e("p", null, t.noEntra),
      e("p", null, t.comoSeHace),
    ),
    registro === null || correcciones.length === 0
      ? e("p", null, t.vacio)
      : html(
          e("p", { class: "mono" }, t.generado(diaDeCorreccion(correcciones[0]?.fecha ?? ""), correcciones.length)),
          e("nav", { "aria-label": t.indice }, e("ul", { class: "texto-enlaces" }, [...meses].map(([clave, g]) => e("li", null, e("a", { href: `#mes-${clave}` }, g.nombre))))),
          [...meses].map(([clave, g]) =>
            e("section", { id: `mes-${clave}` }, e("h2", null, g.nombre), g.entradas.map((c) => entrada(c, idioma, publicados, primeras.has(c)))),
          ),
        ),
  );
}
