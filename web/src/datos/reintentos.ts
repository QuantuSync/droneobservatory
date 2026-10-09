// Nada de lo que la web pide se rinde a la primera. Un fallo pasajero (la red del teléfono que se
// corta, un error 5xx, el tope de peticiones del almacén, la comprobación de navegador del
// alojamiento) se reintenta solo, varias veces y con espera creciente, antes de enseñar ningún
// error. Del segundo intento en adelante se pide sin la caché del navegador, por si guardaba una
// respuesta mala. Lo que de verdad no existe (404, o 403 del almacén, que es como responde a un
// objeto que no está) no se reintenta.
//
// Lo que viene del almacén (/almacen/…, almacenPublico.ts) tiene además otro camino: si la web no lo
// sirve a tiempo o falla, los intentos siguientes van a la copia pública de reserva de Helsinki.

import { reservaDe } from "../almacenPublico.ts";

/** Esperas entre intentos: cinco intentos en unos 7,5 segundos. */
export const ESPERAS_MS: readonly number[] = [500, 1000, 2000, 4000];

let esperas: readonly number[] = ESPERAS_MS;

/** Para las pruebas: otras esperas (por ejemplo, ceros). Sin argumento, las de siempre. */
export function fijarEsperas(nuevas: readonly number[] = ESPERAS_MS): void {
  esperas = nuevas;
}

/** Las esperas en vigor (las usan también las cargas que validan, datos/carga.ts). */
export function esperasEnVigor(): readonly number[] {
  return esperas;
}

/** Espera `ms`, o termina antes con el error de la señal si se aborta. */
export function esperar(ms: number, senal?: AbortSignal | null): Promise<void> {
  return new Promise((hecho, fallo) => {
    if (senal?.aborted === true) {
      fallo(senal.reason);
      return;
    }
    const temporizador = setTimeout(() => {
      senal?.removeEventListener("abort", alAbortar);
      hecho();
    }, ms);
    function alAbortar() {
      clearTimeout(temporizador);
      fallo(senal?.reason);
    }
    senal?.addEventListener("abort", alAbortar, { once: true });
  });
}

/**
 * Si una respuesta es un fallo pasajero: tiempo agotado, demasiadas peticiones, error del
 * servidor, o la comprobación de navegador del alojamiento (403 con `x-vercel-mitigated`).
 */
export function esPasajero(respuesta: Response): boolean {
  const s = respuesta.status;
  if (s === 408 || s === 425 || s === 429 || s >= 500) return true;
  return s === 403 && respuesta.headers.has("x-vercel-mitigated");
}

/** Lo que vale para reintentar: no una petición abortada a propósito. */
export function esAborto(error: unknown, senal?: AbortSignal | null): boolean {
  return senal?.aborted === true || (error instanceof DOMException && error.name === "AbortError");
}

/**
 * Lo que se espera a las cabeceras de un objeto del almacén servido por la web antes de pedirlo a la
 * reserva directamente: más que lo que puede tardar la propia función en probar el principal (3 s)
 * y después la reserva (10 s), api/almacen.ts.
 */
export const TOPE_ALMACEN_MS = 15_000;

/** Como fetch, pero si las cabeceras no llegan en `topeMs` se corta (y cuenta como fallo). */
async function pedirConTope(entrada: RequestInfo | URL, opciones: RequestInit, topeMs: number): Promise<Response> {
  const control = new AbortController();
  const senal = opciones.signal;
  const alAbortar = () => {
    control.abort(senal?.reason);
  };
  if (senal?.aborted === true) control.abort(senal.reason);
  senal?.addEventListener("abort", alAbortar, { once: true });
  const tope = setTimeout(() => {
    control.abort(new DOMException("sin respuesta a tiempo", "TimeoutError"));
  }, topeMs);
  try {
    return await fetch(entrada, { ...opciones, signal: control.signal });
  } finally {
    clearTimeout(tope);
    senal?.removeEventListener("abort", alAbortar);
  }
}

/** Las opciones del intento `n`: desde el segundo, sin la caché del navegador. */
export function opcionesDelIntento(opciones: RequestInit | undefined, n: number): RequestInit {
  return n === 0 ? (opciones ?? {}) : { ...opciones, cache: "no-cache" };
}

/**
 * Como `fetch`, pero con reintentos: devuelve la respuesta ya leída entera (si la conexión se
 * corta a mitad del cuerpo, también se reintenta), o la última respuesta o el último error si
 * ningún intento sale bien.
 */
export const descargarConReintentos: typeof fetch = async (entrada, opciones) => {
  const senal = opciones?.signal ?? null;
  const pausas = esperas;
  const reserva = typeof entrada === "string" ? reservaDe(entrada) : null;
  let actual: RequestInfo | URL = entrada;
  for (let n = 0; ; n += 1) {
    const ultimo = n >= pausas.length;
    try {
      const respuesta =
        reserva === null || actual === reserva
          ? await fetch(actual, opcionesDelIntento(opciones, n))
          : await pedirConTope(actual, opcionesDelIntento(opciones, n), TOPE_ALMACEN_MS);
      if (ultimo || !esPasajero(respuesta)) {
        // Se lee aquí, dentro del intento: un cuerpo cortado cuenta como fallo de la red.
        const sinCuerpo = respuesta.status === 204 || respuesta.status === 205 || respuesta.status === 304;
        const cuerpo = sinCuerpo ? null : await respuesta.arrayBuffer();
        return new Response(cuerpo, {
          status: respuesta.status,
          statusText: respuesta.statusText,
          headers: respuesta.headers,
        });
      }
    } catch (error) {
      if (ultimo || esAborto(error, senal)) throw error;
    }
    if (reserva !== null) actual = reserva;
    await esperar(pausas[n] ?? 0, senal);
  }
};

/** Evento con el que la web pide a public/arranque.js que recargue la página (o avise). */
export const EVENTO_FALLO_ARRANQUE = "eodi:fallo-arranque";

/**
 * Carga un trozo de código bajo demanda (el mapa). Si no llega, no se reintenta aquí: el navegador
 * recuerda el fallo de un módulo mientras dure la página. Se avisa a public/arranque.js, que
 * recarga la página con espera creciente o enseña el error con «Reintentar», y mientras tanto el
 * resto de la web sigue a la vista.
 */
export function importarOAvisar<T>(importar: () => Promise<T>): Promise<T> {
  return importar().catch(() => {
    globalThis.dispatchEvent?.(new Event(EVENTO_FALLO_ARRANQUE));
    return new Promise<T>(() => undefined);
  });
}

/** Prefijo de las direcciones que MapLibre pide (mapa/reintentos.ts) con reintentos («reintenta://https://…»). */
export const PROTOCOLO_REINTENTOS = "reintenta";

/**
 * Una dirección del estilo para que MapLibre la pida con reintentos. Va sin su «https://»
 * (MapLibre estropea un «://» dentro de otro): direccionReal lo vuelve a poner.
 */
export function conReintentos(url: string): string {
  return `${PROTOCOLO_REINTENTOS}://${url.replace(/^https?:\/\//, "")}`;
}

/** La dirección que hay detrás de una de conReintentos, con el esquema de la página. */
export function direccionReal(url: string, protocolo = globalThis.location?.protocol ?? "https:"): string {
  const resto = url.slice(PROTOCOLO_REINTENTOS.length + 3);
  return resto.startsWith("/") ? resto : `${protocolo}//${resto}`;
}
