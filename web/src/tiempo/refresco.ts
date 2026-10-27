// Cómo vuelve a pedir datos una pestaña abierta: cada cierto tiempo solo mientras está a la vista,
// nada con la pestaña oculta y una petición al volver a ella (si la última es de hace más de un
// minuto). Los datos cambian una vez por hora (la recogida publica en el minuto 17): pedirlos con
// la pestaña de fondo solo gasta peticiones. Las peticiones van con «no-cache»: el navegador
// pregunta con If-None-Match y, si nada ha cambiado, la respuesta es un 304 sin cuerpo.

/** Lo mínimo entre dos peticiones al volver a la pestaña. */
export const MS_MINIMO_AL_VOLVER = 60_000;

export interface Documento {
  visibilityState: DocumentVisibilityState;
  addEventListener(tipo: "visibilitychange", oyente: () => void): void;
  removeEventListener(tipo: "visibilitychange", oyente: () => void): void;
}

export interface Reloj {
  ahora(): number;
  cada(oyente: () => void, ms: number): number;
  parar(id: number): void;
}

const RELOJ_DEL_NAVEGADOR: Reloj = {
  ahora: () => Date.now(),
  cada: (oyente, ms) => window.setInterval(oyente, ms),
  parar: (id) => window.clearInterval(id),
};

/**
 * Pide ya (si la pestaña se ve), después cada `ms` mientras se vea, y otra vez al volver a ella.
 * Devuelve la función que lo para.
 */
export function refrescarAlaVista(
  pedir: () => void,
  ms: number,
  documento: Documento = document,
  reloj: Reloj = RELOJ_DEL_NAVEGADOR,
): () => void {
  let ultima: number | null = null;
  const siSeVe = (minimo: number) => {
    if (documento.visibilityState === "hidden") return;
    const ahora = reloj.ahora();
    if (ultima !== null && ahora - ultima < minimo) return;
    ultima = ahora;
    pedir();
  };
  // El intervalo deja un margen de un segundo: un temporizador que llega un poco antes no se salta.
  const temporizador = reloj.cada(() => siSeVe(ms - 1000), ms);
  const alCambiar = () => siSeVe(MS_MINIMO_AL_VOLVER);
  documento.addEventListener("visibilitychange", alCambiar);
  siSeVe(0);
  return () => {
    reloj.parar(temporizador);
    documento.removeEventListener("visibilitychange", alCambiar);
  };
}
