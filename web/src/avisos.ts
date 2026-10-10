// Canal público de avisos con ntfy (docs/avisos.md): los canales, sus enlaces y los textos que
// comparten la página de texto «Avisos» (src/texto/avisos.ts) y el panel del mapa
// (componentes/Avisos.tsx). Los canales salen de configuracion/avisos.json, la misma lista que usan
// el servidor (servidor/ntfy.sh) y el envío (recogida/avisos.py). Los códigos QR se generan como
// imágenes estáticas en el build (scripts/paginas.ts), en /avisos/qr/<canal>.svg.
//
// Todo va en tres pasos: qué recibirás, qué quieres recibir (toda Europa o un país) y suscríbete,
// con un solo botón y las instrucciones del dispositivo que se está usando (Android, iPhone u
// ordenador). La aplicación ntfy solo admite los enlaces ntfy:// en Android (su documentación de
// suscripción desde el teléfono los describe solo ahí): en iPhone, App Store y tres pasos con la
// dirección del servidor y el nombre del canal para copiar.

import configuracion from "../../configuracion/avisos.json" with { type: "json" };
import type { Idioma } from "./sitio.ts";

/** Servidor ntfy del observatorio. */
export const SERVIDOR_AVISOS: string = configuracion.servidor;
export const HOST_AVISOS: string = new URL(configuracion.servidor).host;

export const RUTAS_AVISOS: Record<Idioma, string> = { es: "/avisos", en: "/en/alerts" };

/** Dónde se instala la aplicación ntfy (enlaces de su documentación oficial). */
export const TIENDAS = {
  googlePlay: "https://play.google.com/store/apps/details?id=io.heckel.ntfy",
  fdroid: "https://f-droid.org/packages/io.heckel.ntfy/",
  appStore: "https://apps.apple.com/app/ntfy/id1625396347",
} as const;

export interface Canal {
  /** Nombre del tema en ntfy: «drones-europe» o «drones-» y el país en inglés, con guiones. */
  tema: string;
  nombre: string;
  /** El de toda Europa, que recibe todos los avisos. */
  general: boolean;
}

/** Toda Europa primero; después los países por orden alfabético en el idioma de la página. */
export function canales(idioma: Idioma): Canal[] {
  const paises = Object.values(configuracion.paises)
    .map((p) => ({ tema: p.tema, nombre: p[idioma], general: false }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, idioma));
  return [{ tema: configuracion.general.tema, nombre: configuracion.general[idioma], general: true }, ...paises];
}

/** Enlace que abre la aplicación de Android ya suscrita al canal (ntfy://<servidor>/<tema>). */
export function enlaceAndroid(canal: Canal): string {
  const nombre = `EODI · ${canal.nombre}`;
  return `ntfy://${HOST_AVISOS}/${canal.tema}?display=${encodeURIComponent(nombre).replace(/%20/g, "+")}`;
}

/** El canal en el navegador (la aplicación web de ntfy), donde se activan las notificaciones. */
export function enlaceWeb(canal: Canal): string {
  return `${SERVIDOR_AVISOS}/${canal.tema}`;
}

/** Imagen del código QR del canal (lleva a enlaceWeb), generada en el build. */
export function rutaQr(canal: Canal): string {
  return `/avisos/qr/${canal.tema}.svg`;
}

export type Dispositivo = "android" | "iphone" | "ordenador";

/**
 * El dispositivo por el agente de usuario. Un iPad moderno se presenta como Mac: se reconoce por
 * la pantalla táctil (puntos de contacto), y va con el iPhone porque usa la misma aplicación.
 */
export function dispositivoDe(agente: string, puntosTactiles = 0): Dispositivo {
  if (/android/i.test(agente)) return "android";
  if (/iphone|ipad|ipod/i.test(agente) || (/macintosh/i.test(agente) && puntosTactiles > 1)) return "iphone";
  return "ordenador";
}

/** El dispositivo de quien mira la página (en el build y en las pruebas sin navegador, ordenador). */
export function dispositivoActual(): Dispositivo {
  if (typeof navigator === "undefined") return "ordenador";
  return dispositivoDe(navigator.userAgent, navigator.maxTouchPoints);
}

/** Para buscar países sin tener en cuenta mayúsculas ni tildes. */
export function normalizar(texto: string): string {
  return texto.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

/** Los canales cuyo nombre (o tema) contiene lo buscado; sin búsqueda, todos. */
export function filtrarCanales(lista: readonly Canal[], busqueda: string): Canal[] {
  const buscado = normalizar(busqueda);
  if (buscado === "") return [...lista];
  return lista.filter((c) => normalizar(c.nombre).includes(buscado) || c.tema.includes(buscado));
}

export interface TextoAvisos {
  titulo: string;
  /** Nombre corto del enlace (pie, ayuda) y del botón de la cabecera. */
  enlace: string;
  descripcion: string;
  /** Paso 1. */
  pasoRecibir: string;
  recibir: string;
  /** Paso 2. */
  pasoElegir: string;
  buscar: string;
  canal: string;
  sinResultados: string;
  /** Paso 3. */
  pasoSuscribir: string;
  suscribirme: string;
  /** Instrucciones de cada dispositivo para el canal elegido (como mucho tres pasos). */
  pasos: Record<Dispositivo, (canal: string) => string[]>;
  sinAplicacion: string;
  copiarServidor: string;
  copiarCanal: string;
  copiar: string;
  copiado: string;
  escanear: string;
  masAyuda: string;
  /** Página de texto. */
  nombreDispositivo: Record<Dispositivo, string>;
  detalle: string;
  detalleDispositivo: Record<Dispositivo, string[]>;
  queSeAvisa: string;
  avisa: string[];
  queNo: string;
  canales: string;
  canalesNota: string;
  /** Paso 2 en la página: «o el de tu país, en la lista de canales». */
  oPais: string;
  abrirNavegador: string;
  abrirAndroid: string;
  qr: (nombre: string) => string;
  /** Rótulo del botón de la cabecera para el lector de pantalla (abre el panel). */
  abrir: string;
  cerrar: string;
}

export const TEXTO_AVISOS: Record<Idioma, TextoAvisos> = {
  es: {
    titulo: "Avisos",
    enlace: "Avisos",
    descripcion:
      "Avisos al momento en el móvil o en el ordenador de incidentes confirmados con drones en Europa, cierres de aeropuertos e incursiones en países de la OTAN. Gratis y sin registro.",
    pasoRecibir: "Qué recibirás",
    recibir:
      "Te avisamos al momento de incidentes confirmados con drones en Europa, cierres de aeropuertos e incursiones en países de la OTAN. Gratis y sin registro.",
    pasoElegir: "Qué quieres recibir",
    buscar: "Buscar país",
    canal: "Canal",
    sinResultados: "Ningún país coincide con la búsqueda.",
    pasoSuscribir: "Suscríbete",
    suscribirme: "Suscribirme",
    pasos: {
      android: () => [
        "Toca «Suscribirme»: se abre la aplicación ntfy con el canal.",
        "Si la aplicación lo pregunta, confirma con «Subscribe».",
      ],
      iphone: (canal) => [
        "Toca «Suscribirme» e instala ntfy (o ábrela si ya la tienes).",
        `En ntfy toca «+», activa «Use another server» y pega el servidor: ${SERVIDOR_AVISOS}`,
        `En «Topic name» pega el canal, ${canal}, y toca «Subscribe».`,
      ],
      ordenador: () => [
        "Pulsa «Suscribirme»: el canal se abre en el navegador.",
        "Permite las notificaciones cuando el navegador lo pregunte.",
      ],
    },
    sinAplicacion: "¿No tienes la aplicación? Google Play",
    copiarServidor: "Copiar el servidor",
    copiarCanal: "Copiar el canal",
    copiar: "Copiar",
    copiado: "Copiado",
    escanear: "Escanéalo con tu móvil",
    masAyuda: "Más ayuda",
    nombreDispositivo: { android: "Android", iphone: "iPhone", ordenador: "Ordenador" },
    detalle: "Paso a paso en cada dispositivo",
    detalleDispositivo: {
      android: [
        "Instala la aplicación gratuita ntfy desde Google Play o F-Droid.",
        "Toca el botón «Suscribirme» del canal que quieras: la aplicación se abre con el canal ya puesto. Si lo pregunta, confirma con «Subscribe».",
        "Si el botón no abre la aplicación, añádelo a mano: en ntfy toca «+», escribe el nombre del canal, activa «Use another server», escribe el servidor https://ntfy.droneobservatory.eu y toca «Subscribe».",
      ],
      iphone: [
        "Instala la aplicación gratuita ntfy desde la App Store.",
        "Ábrela, toca «+», activa «Use another server» y escribe el servidor: https://ntfy.droneobservatory.eu",
        "En «Topic name» escribe el nombre del canal (por ejemplo, drones-europe) y toca «Subscribe». Permite las notificaciones cuando el iPhone lo pregunte.",
      ],
      ordenador: [
        "Abre el canal en el navegador con el botón «Suscribirme» (o la dirección https://ntfy.droneobservatory.eu/<canal>).",
        "Permite las notificaciones cuando el navegador lo pregunte. Llegan aunque la pestaña esté cerrada.",
        "Para recibirlos también en el móvil, escanea con su cámara el código QR del canal.",
      ],
    },
    queSeAvisa: "Qué se avisa",
    avisa: [
      "Un incidente nuevo en Europa confirmado o atribuido, o notificado por una fuente oficial (autoridad, ministerio, gestor aeroportuario o de navegación aérea).",
      "El cierre o la suspensión de un aeropuerto por drones que consta como incidente registrado.",
      "Con prioridad alta, la incursión desde la guerra en el espacio aéreo o el territorio de un país de la OTAN o de Moldavia, con confirmación oficial.",
    ],
    queNo:
      "No se avisa de noticias de prensa sin fuente oficial, de la capa de guerra de Ucrania y Rusia (son miles de impactos) ni de las actualizaciones de un incidente ya avisado: un solo aviso por incidente. Cada aviso va al canal de toda Europa y al de su país; al tocarlo se abre el incidente en el mapa. Llegan desde el servidor del observatorio (ntfy.droneobservatory.eu), sin cuenta ni ningún dato personal.",
    canales: "Canales",
    canalesNota: "Toda Europa recibe todos los avisos; el canal de un país, solo los de ese país.",
    oPais: "o el canal de tu país, en la lista de",
    abrirNavegador: "Abrir en el navegador",
    abrirAndroid: "Suscribirme en Android",
    qr: (nombre) => `Código QR del canal ${nombre}`,
    abrir: "Avisos: suscribirse a los avisos en el móvil o en el ordenador",
    cerrar: "Cerrar los avisos",
  },
  en: {
    titulo: "Alerts",
    enlace: "Alerts",
    descripcion:
      "Instant alerts on your phone or computer about confirmed drone incidents in Europe, airport closures and incursions into NATO countries. Free, no sign-up.",
    pasoRecibir: "What you will get",
    recibir:
      "We alert you instantly to confirmed drone incidents in Europe, airport closures and incursions into NATO countries. Free, no sign-up.",
    pasoElegir: "What you want to get",
    buscar: "Search country",
    canal: "Channel",
    sinResultados: "No country matches the search.",
    pasoSuscribir: "Subscribe",
    suscribirme: "Subscribe",
    pasos: {
      android: () => [
        "Tap “Subscribe”: the ntfy app opens with the channel.",
        "If the app asks, confirm with “Subscribe”.",
      ],
      iphone: (canal) => [
        "Tap “Subscribe” and install ntfy (or open it if you have it).",
        `In ntfy tap “+”, turn on “Use another server” and paste the server: ${SERVIDOR_AVISOS}`,
        `In “Topic name” paste the channel, ${canal}, and tap “Subscribe”.`,
      ],
      ordenador: () => [
        "Click “Subscribe”: the channel opens in the browser.",
        "Allow notifications when the browser asks.",
      ],
    },
    sinAplicacion: "No app yet? Google Play",
    copiarServidor: "Copy the server",
    copiarCanal: "Copy the channel",
    copiar: "Copy",
    copiado: "Copied",
    escanear: "Scan it with your phone",
    masAyuda: "More help",
    nombreDispositivo: { android: "Android", iphone: "iPhone", ordenador: "Computer" },
    detalle: "Step by step on each device",
    detalleDispositivo: {
      android: [
        "Install the free ntfy app from Google Play or F-Droid.",
        "Tap the “Subscribe” button of the channel you want: the app opens with the channel filled in. If it asks, confirm with “Subscribe”.",
        "If the button does not open the app, add it by hand: in ntfy tap “+”, type the channel name, turn on “Use another server”, type the server https://ntfy.droneobservatory.eu and tap “Subscribe”.",
      ],
      iphone: [
        "Install the free ntfy app from the App Store.",
        "Open it, tap “+”, turn on “Use another server” and type the server: https://ntfy.droneobservatory.eu",
        "In “Topic name” type the channel name (for example, drones-europe) and tap “Subscribe”. Allow notifications when the iPhone asks.",
      ],
      ordenador: [
        "Open the channel in the browser with the “Subscribe” button (or the address https://ntfy.droneobservatory.eu/<channel>).",
        "Allow notifications when the browser asks. They arrive even with the tab closed.",
        "To get them on your phone as well, scan the channel's QR code with its camera.",
      ],
    },
    queSeAvisa: "What is alerted",
    avisa: [
      "A new incident in Europe that is confirmed or attributed, or reported by an official source (authority, ministry, airport or air navigation operator).",
      "The closure or suspension of an airport because of drones, when it is a registered incident.",
      "With high priority, an incursion from the war into the airspace or territory of a NATO country or Moldova, with official confirmation.",
    ],
    queNo:
      "There are no alerts for press reports without an official source, for the Ukraine and Russia war layer (thousands of impacts) or for updates of an incident already alerted: one alert per incident. Each alert goes to the all-Europe channel and to its country's channel; tapping it opens the incident on the map. They come from the observatory's own server (ntfy.droneobservatory.eu), with no account and no personal data.",
    canales: "Channels",
    canalesNota: "All of Europe gets every alert; a country's channel, only that country's.",
    oPais: "or your country's channel, in the list of",
    abrirNavegador: "Open in the browser",
    abrirAndroid: "Subscribe on Android",
    qr: (nombre) => `QR code of the ${nombre} channel`,
    abrir: "Alerts: subscribe to alerts on your phone or computer",
    cerrar: "Close alerts",
  },
};
