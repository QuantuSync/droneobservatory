// Páginas de servicio público, en los dos idiomas: aviso legal, privacidad, independencia y
// financiación, correcciones y accesibilidad. Son páginas de texto (src/texto/paginas.ts), sin el
// mapa; se enlazan desde «Metodología y datos abiertos» y desde el pie de las páginas de texto.
// Lo que dicen de los datos de los visitantes está comprobado en el código y en la configuración
// (vercel.json, src/estado/novedades.ts): si cambia algo de eso, cambia esta página.

import type { Seccion } from "../i18n/tipos.ts";
import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, REPOSITORIO } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";

export const RESPONSABLE = "Lucas Alaniz Pintos";
export const CONTACTO = "lucasalanizpintos@gmail.com";
const CORREO = `mailto:${CONTACTO}`;
/** Fecha de la última revisión de estas páginas (y de la de accesibilidad). */
export const REVISADAS = { es: "8 de octubre de 2026", en: "8 October 2026" } as const;

export type PaginaServicio = "avisoLegal" | "privacidad" | "independencia" | "correcciones" | "accesibilidad";
export const PAGINAS_SERVICIO: readonly PaginaServicio[] = [
  "avisoLegal",
  "privacidad",
  "independencia",
  "correcciones",
  "accesibilidad",
];

export const RUTAS_SERVICIO: Record<PaginaServicio, Record<Idioma, string>> = {
  avisoLegal: { es: "/aviso-legal", en: "/en/legal-notice" },
  privacidad: { es: "/privacidad", en: "/en/privacy" },
  independencia: { es: "/independencia", en: "/en/independence" },
  correcciones: { es: "/correcciones", en: "/en/corrections" },
  accesibilidad: { es: "/accesibilidad", en: "/en/accessibility" },
};

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
            parrafo: [
              "La información se ofrece tal cual, con su fuente y su fecha. Cada dato dice quién lo afirma y en qué estado está; puede cambiar cuando las autoridades o la prensa publiquen algo nuevo. Si ves un error, ",
              { texto: "la página de correcciones", enlace: "/correcciones" },
              " dice cómo señalarlo.",
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
              "Un solo dato, en el almacenamiento local del navegador: la fecha de tu última visita (clave «eodi.ultima-visita»), para señalar lo nuevo desde entonces. No sale de tu equipo ni se envía a ningún sitio. Se borra al borrar los datos del sitio en el navegador; en una ventana privada, el navegador lo borra al cerrarla.",
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
  correcciones: {
    titulo: "Correcciones",
    enlace: "Correcciones",
    descripcion: `Cómo señalar un error en el ${NOMBRE}.`,
    secciones: [
      {
        id: "como",
        titulo: "Cómo señalar un error",
        bloques: [
          {
            parrafo: [
              "Si ves un error, escribe a ",
              { texto: CONTACTO, enlace: CORREO },
              " con el identificador del incidente (por ejemplo, EODI-2026-00123, el que aparece en su ficha) y, si puedes, la fuente que lo corrige. Se revisa con las fuentes; lo que se corrige queda anotado en la ficha con su motivo y lo que se retira queda marcado con su motivo, nunca se borra.",
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
              { termino: "Contraste", texto: ["Los colores de los textos, de los estados y de la capa de guerra tienen un contraste de 4,5 a 1 o más, comprobado en cada cambio; los estados se distinguen también por luminancia, para el daltonismo."] },
              { termino: "Teclado", texto: ["Todo se maneja con el teclado: un enlace para saltar al mapa, el foco siempre visible, Escape cierra cada panel y devuelve el foco al botón que lo abrió, y el mapa se mueve con las flechas y se acerca con más y menos."] },
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
                termino: "Marcadores del mapa",
                texto: ["Los incidentes del mapa no se recorren uno a uno con el teclado ni los anuncia el lector de pantalla; hoy se llega a ellos por la lista de incidentes, que da las mismas fichas. Arreglo: que el foco recorra los marcadores visibles y cada uno se anuncie con su título y su estado. Fecha prevista: 31 de diciembre de 2026."],
              },
              {
                termino: "Nombres del mapa base",
                texto: ["El contraste de los nombres de lugares del mapa de fondo no se ha medido uno a uno. Arreglo: medirlo con cada estilo del mapa y ajustar los que no lleguen a 4,5 a 1. Fecha prevista: 30 de noviembre de 2026."],
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
            parrafo: [
              "The information is provided as is, with its source and its date. Each piece of data says who states it and what status it has; it may change when the authorities or the press publish something new. If you see a mistake, ",
              { texto: "the corrections page", enlace: "/en/corrections" },
              " says how to report it.",
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
              "A single item, in the browser’s local storage: the date of your last visit (key “eodi.ultima-visita”), to highlight what is new since then. It never leaves your device and is not sent anywhere. It is deleted when you clear the site’s data in your browser; in a private window, the browser deletes it when the window is closed.",
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
  correcciones: {
    titulo: "Corrections",
    enlace: "Corrections",
    descripcion: `How to report a mistake in the ${NOMBRE}.`,
    secciones: [
      {
        id: "como",
        titulo: "How to report a mistake",
        bloques: [
          {
            parrafo: [
              "If you see a mistake, write to ",
              { texto: CONTACTO, enlace: CORREO },
              " with the incident identifier (for example, EODI-2026-00123, the one shown in its record) and, if you can, the source that corrects it. It is checked against the sources; what is corrected is recorded in the incident record with its reason and what is withdrawn is marked with its reason, never deleted.",
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
              { termino: "Contrast", texto: ["Text, status and war-layer colours have a contrast of 4.5 to 1 or more, checked on every change; statuses also differ in luminance, for colour blindness."] },
              { termino: "Keyboard", texto: ["Everything works with the keyboard: a link to skip to the map, focus always visible, Escape closes each panel and returns focus to the button that opened it, and the map moves with the arrow keys and zooms with plus and minus."] },
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
                termino: "Map markers",
                texto: ["The incidents on the map cannot be stepped through one by one with the keyboard and are not announced by screen readers; today they are reached through the incident list, which gives the same records. Fix: let focus move through the visible markers and announce each with its title and status. Planned date: 31 December 2026."],
              },
              {
                termino: "Base map names",
                texto: ["The contrast of place names on the background map has not been measured one by one. Fix: measure it in each map style and adjust those below 4.5 to 1. Planned date: 30 November 2026."],
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
