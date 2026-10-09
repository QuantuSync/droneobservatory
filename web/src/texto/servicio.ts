// Páginas de servicio público, en los dos idiomas: aviso legal, privacidad, independencia y
// financiación, y accesibilidad. Son páginas de texto (src/texto/paginas.ts), sin el
// mapa; se enlazan desde «Metodología y datos abiertos» y desde el pie de las páginas de texto.
// Lo que dicen de los datos de los visitantes está comprobado en el código y en la configuración
// (vercel.json, src/estado/novedades.ts): si cambia algo de eso, cambia esta página.

import type { Seccion } from "../i18n/tipos.ts";
import { AUTOR_FIRMA, AUTOR_NOMBRE, CORREO_AUTOR, LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORCID, ORCID_URL, REPOSITORIO } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";

export const RESPONSABLE = AUTOR_NOMBRE;
export const CONTACTO = CORREO_AUTOR;
/** La cita recomendada, con la versión por rellenar (la da cada versión de los datos). */
const CITA_PLANTILLA = {
  es: `Alaniz Pintos, L. (2026). ${NOMBRE}. Versión AAAA-MM. https://droneobservatory.eu. Licencia ${LICENCIA_DATOS}.`,
  en: `Alaniz Pintos, L. (2026). ${NOMBRE}. Version YYYY-MM. https://droneobservatory.eu. Licence ${LICENCIA_DATOS}.`,
} as const;
const CORREO = `mailto:${CONTACTO}`;
/** Fecha de la última revisión de estas páginas (y de la de accesibilidad). */
export const REVISADAS = { es: "8 de octubre de 2026", en: "8 October 2026" } as const;

export type PaginaServicio = "avisoLegal" | "privacidad" | "independencia" | "accesibilidad";
export const PAGINAS_SERVICIO: readonly PaginaServicio[] = [
  "avisoLegal",
  "privacidad",
  "independencia",
  "accesibilidad",
];

export const RUTAS_SERVICIO: Record<PaginaServicio, Record<Idioma, string>> = {
  avisoLegal: { es: "/aviso-legal", en: "/en/legal-notice" },
  privacidad: { es: "/privacidad", en: "/en/privacy" },
  independencia: { es: "/independencia", en: "/en/independence" },
  accesibilidad: { es: "/accesibilidad", en: "/en/accessibility" },
};

/** El botón de la página de privacidad que borra la fecha de la última visita. */
export interface TextoBorrarVisita {
  boton: string;
  hecho: string;
  fallo: string;
  sinCodigo: string;
}

export const BORRAR_VISITA: Record<Idioma, TextoBorrarVisita> = {
  es: {
    boton: "Borrar mi última visita",
    hecho: "Hecho: se ha borrado la fecha de tu última visita de este navegador.",
    fallo: "Este navegador no deja borrar el dato desde la página: bórralo en la configuración del navegador (datos del sitio).",
    sinCodigo: "Para borrarla sin el botón, borra los datos de droneobservatory.eu en la configuración de tu navegador.",
  },
  en: {
    boton: "Delete my last visit",
    hecho: "Done: the date of your last visit has been deleted from this browser.",
    fallo: "This browser does not let the page delete it: delete it in your browser settings (site data).",
    sinCodigo: "To delete it without the button, clear the data for droneobservatory.eu in your browser settings.",
  },
};

/** El script del botón (web/public), servido desde la propia web. */
export const SCRIPT_BORRAR_VISITA = "/borrar-visita.js";

export interface TextoServicio {
  titulo: string;
  /** El nombre corto del enlace (pie y metodología). */
  enlace: string;
  descripcion: string;
  secciones: Seccion[];
}

const ES: Record<PaginaServicio, TextoServicio> = {
  avisoLegal: {
    titulo: "Aviso legal",
    enlace: "Aviso legal",
    descripcion: `Quién es responsable del ${NOMBRE}, cómo contactar y cómo se pueden usar sus datos.`,
    secciones: [
      {
        id: "responsable",
        titulo: "Responsable",
        bloques: [
          {
            lista: [
              { termino: "Responsable", texto: [`${RESPONSABLE}, como persona física.`] },
              { termino: "Autor", texto: [AUTOR_FIRMA.es] },
              { termino: "ORCID", texto: [{ texto: ORCID, enlace: ORCID_URL }] },
              { termino: "Contacto", texto: [{ texto: CONTACTO, enlace: CORREO }] },
              { termino: "Sitio", texto: [`${NOMBRE} (droneobservatory.eu).`] },
            ],
          },
        ],
      },
      {
        id: "que-es",
        titulo: "Qué es",
        bloques: [
          {
            parrafo: [
              `El ${NOMBRE} es un registro público de los incidentes con drones en Europa, cada uno con sus fuentes y su grado de confirmación, y de los ataques con drones contra Ucrania según los partes oficiales. Es un proyecto independiente y sin ánimo de lucro. No representa a ningún gobierno ni organismo, y no es un sistema de alerta: ante una emergencia, sigue las indicaciones de las autoridades.`,
            ],
          },
        ],
      },
      {
        id: "uso-de-los-datos",
        titulo: "Cómo se usan los datos",
        bloques: [
          {
            parrafo: [
              `Los datos del observatorio (los incidentes, sus estados, sus clasificaciones y sus cifras) se pueden descargar y reutilizar con la licencia `,
              { texto: LICENCIA_DATOS, enlace: LICENCIA_DATOS_URL },
              ", citando la fuente; ",
              { texto: "la página de datos abiertos", enlace: "/metodologia#datos-abiertos" },
              " dice cómo. Las frases citadas son de sus autores y se reproducen como cita, con su fuente y su enlace. El código es abierto (",
              { texto: "Apache-2.0", enlace: `${REPOSITORIO}/blob/main/LICENSE` },
              ").",
            ],
          },
          {
            lista: [{ termino: "Cita recomendada", texto: [CITA_PLANTILLA.es, " (AAAA-MM: la versión de los datos usados)."] }],
          },
          {
            parrafo: [
              "La información se ofrece tal cual, con su fuente y su fecha. Cada dato dice quién lo afirma y en qué estado está; puede cambiar cuando las autoridades o la prensa publiquen algo nuevo. Si ves un error, escribe a ",
              { texto: CONTACTO, enlace: CORREO },
              " con el identificador del incidente (por ejemplo, EODI-2026-00123, el que aparece en su ficha) y, si puedes, la fuente que lo corrige.",
            ],
          },
        ],
      },
    ],
  },
  privacidad: {
    titulo: "Privacidad",
    enlace: "Privacidad",
    descripcion: `Qué datos de los visitantes recoge el ${NOMBRE}: ninguna cookie propia, ninguna analítica, ninguna publicidad.`,
    secciones: [
      {
        id: "resumen",
        titulo: "En pocas palabras",
        bloques: [
          {
            parrafo: [
              "El observatorio no usa cookies propias, ni analítica, ni publicidad, ni herramientas de terceros que sigan a los visitantes. No hay cuentas ni formularios. Las letras, las banderas y el mapa se sirven desde la propia web y desde su almacén de datos, no desde otros sitios.",
            ],
          },
        ],
      },
      {
        id: "navegador",
        titulo: "Lo que se guarda en tu navegador",
        bloques: [
          {
            parrafo: [
              "Un solo dato, en el almacenamiento local de tu navegador, con la clave «eodi.ultima-visita»: la fecha y la hora de tu última visita al mapa.",
            ],
          },
          {
            lista: [
              { termino: "Para qué sirve", texto: ["Para marcar en el mapa los incidentes nuevos o que han cambiado desde tu visita anterior y contar las novedades en «Europa ahora»."] },
              { termino: "Dónde está", texto: ["Solo en tu navegador. No se envía a ningún servidor del observatorio ni a terceros."] },
              { termino: "Qué dice de ti", texto: ["Nada: es solo una fecha. No identifica a nadie ni sirve para seguir a nadie, y no es una cookie."] },
              { termino: "Cuánto dura", texto: ["Cada visita al mapa la sustituye por la fecha de esa visita. Dura hasta que la borres con el botón de abajo o borres los datos del sitio en tu navegador; en una ventana privada, el navegador la borra al cerrarla."] },
              { termino: "Sin ella", texto: ["La web funciona igual. En la primera visita, o después de borrarla, no se marca nada como nuevo: las novedades empiezan a contar desde esa visita."] },
            ],
          },
        ],
      },
      {
        id: "registros",
        titulo: "Registros técnicos",
        bloques: [
          {
            parrafo: [
              "Como cualquier web, al pedir una página o un fichero tu navegador envía su dirección IP, la dirección pedida y su tipo. Los reciben la empresa que aloja la web, con sede en Estados Unidos, y la que guarda los ficheros de datos y del mapa, en Alemania, para servirlos y protegerlos de abusos. El observatorio no usa esos registros para analítica ni para conocer a los visitantes, no guarda copia de ellos y no los cruza con nada.",
            ],
          },
          {
            parrafo: [
              "Si el alojamiento detecta un tráfico anómalo, puede pedir al navegador que supere una comprobación automática y guardar una cookie técnica de esa comprobación. Sirve solo para la seguridad del sitio.",
            ],
          },
        ],
      },
      {
        id: "correo",
        titulo: "Si escribes",
        bloques: [
          {
            parrafo: [
              "Si escribes al correo de contacto, tu dirección y tu mensaje se usan solo para responderte y, si es el caso, para corregir un dato. No se ceden a nadie y se borran cuando ya no hacen falta.",
            ],
          },
        ],
      },
      {
        id: "derechos",
        titulo: "Tus derechos",
        bloques: [
          {
            parrafo: [
              `Puedes pedir acceso, rectificación o supresión de tus datos, u oponerte a su uso, escribiendo a `,
              { texto: CONTACTO, enlace: CORREO },
              `. Responsable: ${RESPONSABLE}. También puedes reclamar ante la autoridad de protección de datos de tu país.`,
            ],
          },
        ],
      },
    ],
  },
  independencia: {
    titulo: "Independencia, autoría y financiación",
    enlace: "Independencia",
    descripcion: `Quién hace el ${NOMBRE}, cómo se financia y con qué criterio se publica.`,
    secciones: [
      {
        id: "autoria",
        titulo: "Quién lo hace",
        bloques: [
          {
            parrafo: [
              `El ${NOMBRE} lo hace ${RESPONSABLE}, a título personal. Es un proyecto independiente: no depende de ningún gobierno, partido, empresa ni organismo, y nadie revisa ni aprueba lo que se publica antes de publicarlo.`,
            ],
          },
          {
            lista: [
              { termino: "Autor", texto: [AUTOR_FIRMA.es] },
              { termino: "ORCID", texto: [{ texto: ORCID, enlace: ORCID_URL }] },
              { termino: "Contacto", texto: [{ texto: CONTACTO, enlace: CORREO }] },
              { termino: "Cita recomendada", texto: [CITA_PLANTILLA.es, " (AAAA-MM: la versión de los datos usados)."] },
            ],
          },
        ],
      },
      {
        id: "financiacion",
        titulo: "Financiación",
        bloques: [
          {
            parrafo: [
              "Se financia con medios propios. No tiene publicidad ni financiación de terceros, y no acepta pagos por incluir, cambiar o retirar ningún dato.",
            ],
          },
        ],
      },
      {
        id: "criterio",
        titulo: "Criterio editorial",
        bloques: [
          {
            lista: [
              { termino: "Fuentes", texto: ["Fuentes oficiales y de prensa, cada dato con su enlace y una frase breve de la fuente."] },
              { termino: "Estados", texto: ["Notificado, confirmado o desmentido según lo que declara la autoridad competente, nunca por deducción propia."] },
              { termino: "Atribución", texto: ["Solo con una declaración oficial literal que diga quién es el responsable."] },
              { termino: "Cambios", texto: ["Nada se borra: lo corregido o retirado queda anotado con su motivo."] },
            ],
          },
        ],
      },
    ],
  },
  accesibilidad: {
    titulo: "Declaración de accesibilidad",
    enlace: "Accesibilidad",
    descripcion: `Qué cumple el ${NOMBRE} de las pautas de accesibilidad WCAG 2.1 de nivel AA y qué queda pendiente.`,
    secciones: [
      {
        id: "estado",
        titulo: "Situación",
        bloques: [
          {
            parrafo: [
              `El ${NOMBRE} quiere ser accesible para todos. Se ha revisado con las pautas `,
              { texto: "WCAG 2.1", enlace: "https://www.w3.org/TR/WCAG21/" },
              ` de nivel AA el ${REVISADAS.es}, con una comprobación automática de cada pantalla (la portada, la ficha de un incidente, los filtros, «Europa ahora», «Previsión», el menú, la ayuda y las páginas de texto, en teléfono y en escritorio), sin ningún fallo, y con un recorrido con el teclado. Es parcialmente conforme: lo pendiente va abajo, con su fecha prevista.`,
            ],
          },
        ],
      },
      {
        id: "cumple",
        titulo: "Lo que cumple",
        bloques: [
          {
            lista: [
              { termino: "Contraste", texto: ["Los colores de los textos, de los estados y de la capa de guerra tienen un contraste de 4,5 a 1 o más, comprobado en cada cambio; los estados se distinguen también por luminancia, para el daltonismo. Los nombres de lugares del mapa de fondo, medidos capa a capa, llegan a 4,5 a 1 contra su halo y contra la tierra y el agua (antes, los más tenues se quedaban en 3,1 a 1)."] },
              { termino: "Teclado", texto: ["Todo se maneja con el teclado: un enlace para saltar al mapa, el foco siempre visible, Escape cierra cada panel y devuelve el foco al botón que lo abrió, y el mapa se mueve con las flechas y se acerca con más y menos."] },
              { termino: "Marcadores del mapa", texto: ["Después del mapa, el tabulador recorre los incidentes a la vista, del más reciente al más antiguo: el lector de pantalla anuncia su título, su estado y su fecha, el enfocado se señala en el mapa con un aro y su letrero, e Intro abre su ficha. Con el ratón o el dedo, el mapa se usa como siempre."] },
              { termino: "Lectores de pantalla", texto: ["Cada botón y cada control llevan su nombre; los paneles se anuncian con su título; las gráficas llevan un resumen en texto."] },
              { termino: "Textos alternativos", texto: ["Las imágenes de satélite dicen qué son y su fecha, y la superficie cambiada va escrita; los adornos se marcan como tales."] },
              { termino: "Sin el mapa", texto: ["La lista de incidentes y las páginas de texto (todas las fichas, los países, la guerra en Ucrania, la previsión, la metodología y la ayuda) dan lo mismo que el mapa y se leen sin ejecutar código."] },
              { termino: "Tamaño", texto: ["En el teléfono, los botones miden 44 píxeles de alto o más."] },
              { termino: "Idioma", texto: ["Toda la web está en español y en inglés, y cada página declara su idioma."] },
            ],
          },
        ],
      },
      {
        id: "pendiente",
        titulo: "Lo que queda pendiente",
        bloques: [
          {
            lista: [
              {
                termino: "Capa de la guerra en Ucrania",
                texto: ["Las regiones, los impactos y las celdas de interferencia de GPS del mapa no se recorren uno a uno con el teclado (los corredores sí); sus datos están en la página de texto de la guerra en Ucrania. Arreglo: recorrerlos con el tabulador como los incidentes. Fecha prevista: 31 de diciembre de 2026."],
              },
            ],
          },
        ],
      },
      {
        id: "contacto",
        titulo: "Si algo no te funciona",
        bloques: [
          {
            parrafo: [
              "Escribe a ",
              { texto: CONTACTO, enlace: CORREO },
              " diciendo qué página y qué parte, y con qué navegador o lector de pantalla. Se contesta y se arregla lo antes posible.",
            ],
          },
        ],
      },
    ],
  },
};

const EN: Record<PaginaServicio, TextoServicio> = {
  avisoLegal: {
    titulo: "Legal notice",
    enlace: "Legal notice",
    descripcion: `Who is responsible for the ${NOMBRE}, how to get in touch and how its data can be used.`,
    secciones: [
      {
        id: "responsable",
        titulo: "Responsible person",
        bloques: [
          {
            lista: [
              { termino: "Responsible", texto: [`${RESPONSABLE}, as a private individual.`] },
              { termino: "Author", texto: [AUTOR_FIRMA.en] },
              { termino: "ORCID", texto: [{ texto: ORCID, enlace: ORCID_URL }] },
              { termino: "Contact", texto: [{ texto: CONTACTO, enlace: CORREO }] },
              { termino: "Site", texto: [`${NOMBRE} (droneobservatory.eu).`] },
            ],
          },
        ],
      },
      {
        id: "que-es",
        titulo: "What it is",
        bloques: [
          {
            parrafo: [
              `The ${NOMBRE} is a public record of drone incidents in Europe, each with its sources and its level of confirmation, and of drone attacks on Ukraine according to official reports. It is an independent, not-for-profit project. It does not represent any government or body, and it is not an alert system: in an emergency, follow the instructions of the authorities.`,
            ],
          },
        ],
      },
      {
        id: "uso-de-los-datos",
        titulo: "How the data can be used",
        bloques: [
          {
            parrafo: [
              "The observatory’s data (the incidents, their statuses, their classifications and their figures) can be downloaded and reused under the ",
              { texto: LICENCIA_DATOS, enlace: LICENCIA_DATOS_URL },
              " licence, citing the source; ",
              { texto: "the open data page", enlace: "/en/methodology#datos-abiertos" },
              " says how. Quoted sentences belong to their authors and are reproduced as quotations, with their source and link. The code is open (",
              { texto: "Apache-2.0", enlace: `${REPOSITORIO}/blob/main/LICENSE` },
              ").",
            ],
          },
          {
            lista: [{ termino: "Recommended citation", texto: [CITA_PLANTILLA.en, " (YYYY-MM: the version of the data used)."] }],
          },
          {
            parrafo: [
              "The information is provided as is, with its source and its date. Each piece of data says who states it and what status it has; it may change when the authorities or the press publish something new. If you see a mistake, write to ",
              { texto: CONTACTO, enlace: CORREO },
              " with the incident identifier (for example, EODI-2026-00123, the one shown in its record) and, if you can, the source that corrects it.",
            ],
          },
        ],
      },
    ],
  },
  privacidad: {
    titulo: "Privacy",
    enlace: "Privacy",
    descripcion: `What visitor data the ${NOMBRE} collects: no cookies of its own, no analytics, no advertising.`,
    secciones: [
      {
        id: "resumen",
        titulo: "In short",
        bloques: [
          {
            parrafo: [
              "The observatory uses no cookies of its own, no analytics, no advertising and no third-party tools that follow visitors. There are no accounts and no forms. Fonts, flags and the map are served from the site itself and from its data store, not from other sites.",
            ],
          },
        ],
      },
      {
        id: "navegador",
        titulo: "What is stored in your browser",
        bloques: [
          {
            parrafo: [
              "A single item, in your browser’s local storage, under the key “eodi.ultima-visita”: the date and time of your last visit to the map.",
            ],
          },
          {
            lista: [
              { termino: "What it is for", texto: ["To mark on the map the incidents that are new or have changed since your previous visit and to count the updates in “Europe now”."] },
              { termino: "Where it is", texto: ["Only in your browser. It is not sent to any server of the observatory or to third parties."] },
              { termino: "What it says about you", texto: ["Nothing: it is just a date. It does not identify anyone or track anyone, and it is not a cookie."] },
              { termino: "How long it lasts", texto: ["Each visit to the map replaces it with the date of that visit. It lasts until you delete it with the button below or clear the site’s data in your browser; in a private window, the browser deletes it when the window is closed."] },
              { termino: "Without it", texto: ["The site works the same. On your first visit, or after deleting it, nothing is marked as new: updates start counting from that visit."] },
            ],
          },
        ],
      },
      {
        id: "registros",
        titulo: "Technical logs",
        bloques: [
          {
            parrafo: [
              "As with any website, when your browser requests a page or a file it sends its IP address, the address requested and its type. They are received by the company that hosts the site, based in the United States, and by the one that stores the data and map files, in Germany, in order to serve them and protect them from abuse. The observatory does not use these logs for analytics or to learn about visitors, keeps no copy of them and does not combine them with anything.",
            ],
          },
          {
            parrafo: [
              "If the hosting detects abnormal traffic, it may ask the browser to pass an automatic check and store a technical cookie for that check. It serves only the security of the site.",
            ],
          },
        ],
      },
      {
        id: "correo",
        titulo: "If you write",
        bloques: [
          {
            parrafo: [
              "If you write to the contact address, your address and your message are used only to reply and, where relevant, to correct a piece of data. They are not passed on to anyone and are deleted when no longer needed.",
            ],
          },
        ],
      },
      {
        id: "derechos",
        titulo: "Your rights",
        bloques: [
          {
            parrafo: [
              "You can request access to, rectification or erasure of your data, or object to its use, by writing to ",
              { texto: CONTACTO, enlace: CORREO },
              `. Responsible: ${RESPONSABLE}. You can also complain to the data protection authority of your country.`,
            ],
          },
        ],
      },
    ],
  },
  independencia: {
    titulo: "Independence, authorship and funding",
    enlace: "Independence",
    descripcion: `Who makes the ${NOMBRE}, how it is funded and what editorial criteria it follows.`,
    secciones: [
      {
        id: "autoria",
        titulo: "Who makes it",
        bloques: [
          {
            parrafo: [
              `The ${NOMBRE} is made by ${RESPONSABLE}, in a personal capacity. It is an independent project: it does not depend on any government, party, company or body, and nobody reviews or approves what is published before it is published.`,
            ],
          },
          {
            lista: [
              { termino: "Author", texto: [AUTOR_FIRMA.en] },
              { termino: "ORCID", texto: [{ texto: ORCID, enlace: ORCID_URL }] },
              { termino: "Contact", texto: [{ texto: CONTACTO, enlace: CORREO }] },
              { termino: "Recommended citation", texto: [CITA_PLANTILLA.en, " (YYYY-MM: the version of the data used)."] },
            ],
          },
        ],
      },
      {
        id: "financiacion",
        titulo: "Funding",
        bloques: [
          {
            parrafo: [
              "It is self-funded. It has no advertising and no third-party funding, and accepts no payment to include, change or remove any data.",
            ],
          },
        ],
      },
      {
        id: "criterio",
        titulo: "Editorial criteria",
        bloques: [
          {
            lista: [
              { termino: "Sources", texto: ["Official and press sources, each piece of data with its link and a short sentence from the source."] },
              { termino: "Statuses", texto: ["Reported, confirmed or denied according to what the competent authority declares, never by our own deduction."] },
              { termino: "Attribution", texto: ["Only with a literal official statement saying who is responsible."] },
              { termino: "Changes", texto: ["Nothing is deleted: what is corrected or withdrawn is recorded with its reason."] },
            ],
          },
        ],
      },
    ],
  },
  accesibilidad: {
    titulo: "Accessibility statement",
    enlace: "Accessibility",
    descripcion: `What the ${NOMBRE} meets of the WCAG 2.1 level AA accessibility guidelines and what is pending.`,
    secciones: [
      {
        id: "estado",
        titulo: "Status",
        bloques: [
          {
            parrafo: [
              `The ${NOMBRE} aims to be accessible to everyone. It was reviewed against `,
              { texto: "WCAG 2.1", enlace: "https://www.w3.org/TR/WCAG21/" },
              ` level AA on ${REVISADAS.en}, with an automatic check of each screen (the home page, an incident record, the filters, “Europe now”, “Forecast”, the menu, the help and the text pages, on phone and on desktop), with no failures, and a keyboard walkthrough. It is partially conformant: what is pending is listed below, with its planned date.`,
            ],
          },
        ],
      },
      {
        id: "cumple",
        titulo: "What it meets",
        bloques: [
          {
            lista: [
              { termino: "Contrast", texto: ["Text, status and war-layer colours have a contrast of 4.5 to 1 or more, checked on every change; statuses also differ in luminance, for colour blindness. Place names on the background map, measured layer by layer, reach 4.5 to 1 against their halo and against land and water (the faintest used to be 3.1 to 1)."] },
              { termino: "Keyboard", texto: ["Everything works with the keyboard: a link to skip to the map, focus always visible, Escape closes each panel and returns focus to the button that opened it, and the map moves with the arrow keys and zooms with plus and minus."] },
              { termino: "Map markers", texto: ["After the map, the Tab key goes through the incidents in view, most recent first: screen readers announce their title, status and date, the focused one is marked on the map with a ring and its label, and Enter opens its record. With a mouse or a finger, the map works as always."] },
              { termino: "Screen readers", texto: ["Every button and control has its name; panels are announced with their title; charts carry a text summary."] },
              { termino: "Text alternatives", texto: ["Satellite images say what they are and their date, and the changed area is written out; decorations are marked as such."] },
              { termino: "Without the map", texto: ["The incident list and the text pages (every record, the countries, the war in Ukraine, the forecast, the methodology and the help) give the same as the map and can be read without running code."] },
              { termino: "Size", texto: ["On phones, buttons are 44 pixels high or more."] },
              { termino: "Language", texto: ["The whole site is in Spanish and English, and every page declares its language."] },
            ],
          },
        ],
      },
      {
        id: "pendiente",
        titulo: "What is pending",
        bloques: [
          {
            lista: [
              {
                termino: "War in Ukraine layer",
                texto: ["The regions, impacts and GPS interference cells on the map cannot be stepped through one by one with the keyboard (the corridors can); their data is on the text page about the war in Ukraine. Fix: step through them with the Tab key like the incidents. Planned date: 31 December 2026."],
              },
            ],
          },
        ],
      },
      {
        id: "contacto",
        titulo: "If something does not work for you",
        bloques: [
          {
            parrafo: [
              "Write to ",
              { texto: CONTACTO, enlace: CORREO },
              " saying which page and which part, and with which browser or screen reader. You will get a reply and it will be fixed as soon as possible.",
            ],
          },
        ],
      },
    ],
  },
};

export function textoServicio(pagina: PaginaServicio, idioma: Idioma): TextoServicio {
  return (idioma === "en" ? EN : ES)[pagina];
}

/**
 * Los enlaces de «Sobre el observatorio»: las páginas de servicio. Los usan la metodología (web y
 * texto), el pie de las páginas de texto y llms.txt.
 */
export function enlacesSobre(idioma: Idioma): { ruta: string; texto: string; titulo: string }[] {
  return PAGINAS_SERVICIO.map((pagina) => {
    const texto = textoServicio(pagina, idioma);
    return { ruta: RUTAS_SERVICIO[pagina][idioma], texto: texto.enlace, titulo: texto.titulo };
  });
}
