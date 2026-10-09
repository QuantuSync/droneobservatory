// Las capas del mapa tampoco se rinden a la primera (datos/reintentos.ts): las teselas del fondo
// (PMTiles, del almacén público) y los GeoJSON y las letras que MapLibre pide por su cuenta. Sin
// esto, un corte pasajero de la red dejaba un trozo del mapa o una capa vacíos hasta recargar.

import { addProtocol } from "maplibre-gl";
import { EtagMismatch, FetchSource, PMTiles, Protocol } from "pmtiles";
import type { RangeResponse, Source } from "pmtiles";

import { RUTA_ALMACEN, urlDeLaReserva } from "../almacenPublico.ts";
import {
  PROTOCOLO_REINTENTOS,
  TOPE_ALMACEN_MS,
  descargarConReintentos,
  direccionReal,
  esAborto,
  esperar,
  esperasEnVigor,
} from "../datos/reintentos.ts";

/** Un error de la librería de teselas que no es pasajero: el servidor dijo que no existe (4xx). */
function definitivo(error: unknown): boolean {
  const codigo = /Bad response code: (\d+)/.exec(error instanceof Error ? error.message : "")?.[1];
  if (codigo === undefined) return false;
  const s = Number(codigo);
  return s >= 400 && s < 500 && s !== 408 && s !== 425 && s !== 429;
}

/** Fuente de PMTiles que reintenta cada rango que falla (no si se aborta o cambia el fichero). */
export class FuenteConReintentos implements Source {
  private readonly fuente: Source;

  constructor(url: string, fuente: Source = new FetchSource(url)) {
    this.fuente = fuente;
  }

  getKey(): string {
    return this.fuente.getKey();
  }

  async getBytes(offset: number, length: number, senal?: AbortSignal, etag?: string): Promise<RangeResponse> {
    const pausas = esperasEnVigor();
    for (let n = 0; ; n += 1) {
      try {
        return await this.fuente.getBytes(offset, length, senal, etag);
      } catch (error) {
        // Un fichero de teselas que ha cambiado lo resuelve la propia librería, pidiendo de nuevo
        // su cabecera.
        if (n >= pausas.length || esAborto(error, senal) || error instanceof EtagMismatch || definitivo(error)) {
          throw error;
        }
      }
      await esperar(pausas[n] ?? 0, senal);
    }
  }
}

/** Tras un fallo de la web al servir el mapa de fondo, cuánto tiempo se pide directo a la reserva. */
export const PAUSA_RESERVA_MS = 60_000;

/**
 * El mapa de fondo servido por la web (api/almacen.ts): cada trozo se pide como
 * /almacen/<fichero>?o=<desde>&l=<largo>, que la caché de Vercel guarda (una petición con Range no
 * la guardaría). Si la web no lo sirve a tiempo o falla, el trozo se pide con Range a la copia
 * pública de reserva, y durante PAUSA_RESERVA_MS los siguientes también.
 */
export class FuenteAlmacen implements Source {
  private readonly url: string;
  private readonly reserva: FetchSource;
  private reservaHasta = 0;

  constructor(objeto: string, url = `${RUTA_ALMACEN}/${objeto}`, reserva = urlDeLaReserva(objeto)) {
    this.url = url;
    this.reserva = new FetchSource(reserva);
  }

  getKey(): string {
    return this.url;
  }

  async getBytes(offset: number, length: number, senal?: AbortSignal): Promise<RangeResponse> {
    if (Date.now() >= this.reservaHasta) {
      const control = new AbortController();
      const alAbortar = () => {
        control.abort(senal?.reason);
      };
      senal?.addEventListener("abort", alAbortar, { once: true });
      const tope = setTimeout(() => {
        control.abort(new DOMException("sin respuesta a tiempo", "TimeoutError"));
      }, TOPE_ALMACEN_MS);
      try {
        const respuesta = await fetch(`${this.url}?o=${offset}&l=${length}`, { signal: control.signal });
        if (respuesta.ok) return { data: await respuesta.arrayBuffer() };
        // Lo que no existe no está tampoco en la reserva.
        if (respuesta.status === 404) throw new Error(`Bad response code: ${respuesta.status}`);
      } catch (error) {
        if (esAborto(error, senal) || (error instanceof Error && error.message.startsWith("Bad response code"))) {
          throw error;
        }
      } finally {
        clearTimeout(tope);
        senal?.removeEventListener("abort", alAbortar);
      }
      this.reservaHasta = Date.now() + PAUSA_RESERVA_MS;
    }
    // Sin ETag: la reserva es otra copia del mismo fichero (el nombre cambia si cambia el mapa).
    const { data } = await this.reserva.getBytes(offset, length, senal);
    return { data };
  }
}

let registrado = false;

/** Registra en MapLibre las teselas de `urlTeselas` y el protocolo de reintentos (una vez). */
export function registrarProtocolos(urlTeselas: string): void {
  if (registrado) return;
  registrado = true;
  const teselas = new Protocol();
  // Servido por la web (/almacen/…): por trozos cacheables y con la reserva. Una copia local de
  // desarrollo o de las pruebas (VITE_TESELAS, VITE_ALMACEN) se pide como siempre, con Range.
  const prefijo = `${RUTA_ALMACEN}/`;
  const fuente = urlTeselas.startsWith(prefijo)
    ? new FuenteAlmacen(urlTeselas.slice(prefijo.length))
    : new FetchSource(urlTeselas);
  teselas.add(new PMTiles(new FuenteConReintentos(urlTeselas, fuente)));
  addProtocol("pmtiles", teselas.tile);
  addProtocol(PROTOCOLO_REINTENTOS, async (peticion, control) => {
    const url = direccionReal(peticion.url);
    const respuesta = await descargarConReintentos(url, { signal: control.signal });
    if (!respuesta.ok) throw new Error(`${url}: HTTP ${respuesta.status}`);
    return { data: peticion.type === "json" ? ((await respuesta.json()) as object) : await respuesta.arrayBuffer() };
  });
}
