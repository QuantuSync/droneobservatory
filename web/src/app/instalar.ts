// «Instalar la app»: sin banners ni ventanas emergentes (pantalla limpia). El navegador avisa con
// «beforeinstallprompt» (Chrome y Edge en Android y escritorio) de que la web se puede instalar: se
// guarda el aviso (preventDefault quita la barrita de instalación de Chrome) y la entrada «Instalar
// la app» del menú lo lanza. En el iPhone y el iPad no hay aviso: la entrada enseña los dos pasos de
// Safari. La entrada no se ve con la app instalada ni abierta desde su icono.

import { useSyncExternalStore } from "react";

/** El aviso de Chrome y Edge (no está en los tipos de TypeScript). */
interface AvisoInstalacion extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export type ModoInstalacion = "nativo" | "iphone" | null;

export interface Entorno {
  /** La web abierta como app (display-mode standalone, o navigator.standalone en iOS). */
  abiertaComoApp: boolean;
  /** Si el navegador ha dado su aviso de instalación. */
  hayAviso: boolean;
  /** Si se acaba de instalar en esta visita. */
  instalada: boolean;
  agente: string;
  puntosTactiles: number;
}

/** iPhone, iPod o iPad (el iPad se presenta como un Mac con pantalla táctil). */
export function esIos(agente: string, puntosTactiles: number): boolean {
  return /iPhone|iPad|iPod/.test(agente) || (/Macintosh/.test(agente) && puntosTactiles > 1);
}

/** Qué ofrece la entrada «Instalar la app», o null si no se ve. */
export function modoDeInstalacion(e: Entorno): ModoInstalacion {
  if (e.abiertaComoApp || e.instalada) return null;
  if (e.hayAviso) return "nativo";
  if (esIos(e.agente, e.puntosTactiles)) return "iphone";
  return null;
}

let aviso: AvisoInstalacion | null = null;
let instalada = false;
let escuchando = false;
const oyentes = new Set<() => void>();
let instantanea: ModoInstalacion = null;

function abiertaComoApp(): boolean {
  if (typeof window === "undefined") return false;
  const ios = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return ios || (window.matchMedia?.("(display-mode: standalone)").matches ?? false);
}

function calcular(): void {
  instantanea = modoDeInstalacion({
    abiertaComoApp: abiertaComoApp(),
    hayAviso: aviso !== null,
    instalada,
    agente: navigator.userAgent,
    puntosTactiles: navigator.maxTouchPoints ?? 0,
  });
  for (const oyente of oyentes) oyente();
}

/** Empieza a escuchar el aviso del navegador: cuanto antes, porque llega pronto. */
export function escucharInstalacion(): void {
  if (escuchando || typeof window === "undefined") return;
  escuchando = true;
  window.addEventListener("beforeinstallprompt", (evento) => {
    evento.preventDefault();
    aviso = evento as AvisoInstalacion;
    calcular();
  });
  window.addEventListener("appinstalled", () => {
    aviso = null;
    instalada = true;
    calcular();
  });
  window.matchMedia?.("(display-mode: standalone)").addEventListener?.("change", calcular);
  calcular();
}

/** Lanza el diálogo del navegador. Devuelve si se ha instalado. */
export async function instalar(): Promise<boolean> {
  const actual = aviso;
  if (actual === null) return false;
  // El aviso solo vale una vez.
  aviso = null;
  try {
    await actual.prompt();
    const { outcome } = await actual.userChoice;
    if (outcome === "accepted") instalada = true;
    return outcome === "accepted";
  } catch {
    return false;
  } finally {
    calcular();
  }
}

function suscribir(oyente: () => void): () => void {
  escucharInstalacion();
  oyentes.add(oyente);
  return () => oyentes.delete(oyente);
}

/** El modo de la entrada «Instalar la app»; null en el servidor y mientras no haya nada que ofrecer. */
export function useInstalacion(): ModoInstalacion {
  return useSyncExternalStore(
    suscribir,
    () => instantanea,
    () => null,
  );
}

/** Si la web está abierta como app instalada (para las visitas y las pruebas). */
export { abiertaComoApp };
