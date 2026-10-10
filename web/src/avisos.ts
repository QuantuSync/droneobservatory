// Canal público de avisos con ntfy (docs/avisos.md): los canales, sus enlaces y los textos que
// comparten la página de texto «Avisos» (src/texto/avisos.ts) y el panel del mapa
// (componentes/Avisos.tsx). Los canales salen de configuracion/avisos.json, la misma lista que usan
// el servidor (servidor/ntfy.sh) y el envío (recogida/avisos.py). Los códigos QR se generan como
// imágenes estáticas en el build (scripts/paginas.ts), en /avisos/qr/<canal>.svg.

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
  /** Nombre del tema en ntfy: «general» o el país en inglés, en minúsculas y con guiones. */
  tema: string;
  nombre: string;
  general: boolean;
}

/** El canal general primero; después los países por orden alfabético en el idioma de la página. */
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

export interface TextoAvisos {
  titulo: string;
  /** Nombre corto del enlace (pie, ayuda) y del botón de la cabecera. */
  enlace: string;
  descripcion: string;
  queSeAvisa: string;
  avisa: string[];
  queNo: string;
  sinCuenta: string;
  canales: string;
  general: string;
  android: string;
  suscribirAndroid: string;
  sinAplicacion: string;
  iphone: string;
  instalarIphone: string;
  pasosIphone: (tema: string) => string[];
  ordenador: string;
  abrirNavegador: string;
  notaNavegador: string;
  qr: (nombre: string) => string;
  paginaCompleta: string;
  /** Rótulo del botón de la cabecera para el lector de pantalla (abre el panel). */
  abrir: string;
  cerrar: string;
}

export const TEXTO_AVISOS: Record<Idioma, TextoAvisos> = {
  es: {
    titulo: "Avisos",
    enlace: "Avisos",
    descripcion:
      "Avisos en el móvil o en el ordenador de los sucesos importantes con drones en Europa, sin cuenta: un canal general y uno por país.",
    queSeAvisa: "Qué se avisa",
    avisa: [
      "Un incidente nuevo en Europa confirmado o atribuido, o notificado por una fuente oficial (autoridad, ministerio, gestor aeroportuario o de navegación aérea).",
      "El cierre o la suspensión de un aeropuerto por drones que consta como incidente registrado.",
      "Con prioridad alta, la incursión desde la guerra en el espacio aéreo o el territorio de un país de la OTAN o de Moldavia, con confirmación oficial.",
    ],
    queNo:
      "No se avisa de noticias de prensa sin fuente oficial, de la capa de guerra de Ucrania y Rusia (son miles de impactos) ni de las actualizaciones de un incidente ya avisado: un solo aviso por incidente.",
    sinCuenta:
      "No hace falta cuenta ni dar ningún dato. Los avisos llegan con la aplicación gratuita ntfy, en Android o en iPhone, o en el navegador, desde el servidor del observatorio (ntfy.droneobservatory.eu). Cada aviso va al canal general y al de su país; al tocarlo se abre el incidente en el mapa.",
    canales: "Canales",
    general: "General: todos los avisos",
    android: "Android",
    suscribirAndroid: "Suscribirse en la aplicación",
    sinAplicacion: "¿Sin la aplicación? Instálala desde",
    iphone: "iPhone",
    instalarIphone: "Instalar ntfy desde la App Store",
    pasosIphone: (tema) => [
      "Abre ntfy y toca «+».",
      `En «Topic name» escribe: ${tema}`,
      `Activa «Use another server» y escribe: ${SERVIDOR_AVISOS}`,
      "Toca «Subscribe».",
    ],
    ordenador: "Ordenador",
    abrirNavegador: "Abrir el canal en el navegador",
    notaNavegador: "En esa página, permite las notificaciones cuando el navegador lo pregunte.",
    qr: (nombre) => `Código QR del canal ${nombre}`,
    paginaCompleta: "Página completa de avisos",
    abrir: "Avisos: suscribirse a los avisos en el móvil o en el ordenador",
    cerrar: "Cerrar los avisos",
  },
  en: {
    titulo: "Alerts",
    enlace: "Alerts",
    descripcion:
      "Alerts on your phone or computer about major drone events in Europe, with no account: one general channel and one per country.",
    queSeAvisa: "What is alerted",
    avisa: [
      "A new incident in Europe that is confirmed or attributed, or reported by an official source (authority, ministry, airport or air navigation operator).",
      "The closure or suspension of an airport because of drones, when it is a registered incident.",
      "With high priority, an incursion from the war into the airspace or territory of a NATO country or Moldova, with official confirmation.",
    ],
    queNo:
      "There are no alerts for press reports without an official source, for the Ukraine and Russia war layer (thousands of impacts) or for updates of an incident already alerted: one alert per incident.",
    sinCuenta:
      "No account and no personal data are needed. Alerts arrive through the free ntfy app, on Android or iPhone, or in the browser, from the observatory's own server (ntfy.droneobservatory.eu). Each alert goes to the general channel and to its country's channel; tapping it opens the incident on the map.",
    canales: "Channels",
    general: "General: all alerts",
    android: "Android",
    suscribirAndroid: "Subscribe in the app",
    sinAplicacion: "No app yet? Install it from",
    iphone: "iPhone",
    instalarIphone: "Install ntfy from the App Store",
    pasosIphone: (tema) => [
      "Open ntfy and tap “+”.",
      `In “Topic name” type: ${tema}`,
      `Turn on “Use another server” and type: ${SERVIDOR_AVISOS}`,
      "Tap “Subscribe”.",
    ],
    ordenador: "Computer",
    abrirNavegador: "Open the channel in the browser",
    notaNavegador: "On that page, allow notifications when the browser asks.",
    qr: (nombre) => `QR code of the ${nombre} channel`,
    paginaCompleta: "Full alerts page",
    abrir: "Alerts: subscribe to alerts on your phone or computer",
    cerrar: "Close alerts",
  },
};
