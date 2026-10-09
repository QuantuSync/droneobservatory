// Las capas del mapa tampoco se rinden a la primera (datos/reintentos.ts): las teselas del fondo
// (PMTiles, del almacén público) y los GeoJSON y las letras que MapLibre pide por su cuenta. Sin
// esto, un corte pasajero de la red dejaba un trozo del mapa o una capa vacíos hasta recargar.

import { addProtocol } from "maplibre-gl";
import { EtagMismatch, FetchSource, PMTiles, Protocol } from "pmtiles";
import type { RangeResponse, Source } from "pmtiles";

import { PROTOCOLO_REINTENTOS, descargarConReintentos, direccionReal, esAborto, esperar, esperasEnVigor } from "../datos/reintentos.ts";

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

let registrado = false;

/** Registra en MapLibre las teselas de `urlTeselas` y el protocolo de reintentos (una vez). */
export function registrarProtocolos(urlTeselas: string): void {
  if (registrado) return;
  registrado = true;
  const teselas = new Protocol();
  teselas.add(new PMTiles(new FuenteConReintentos(urlTeselas)));
  addProtocol("pmtiles", teselas.tile);
  addProtocol(PROTOCOLO_REINTENTOS, async (peticion, control) => {
    const url = direccionReal(peticion.url);
    const respuesta = await descargarConReintentos(url, { signal: control.signal });
    if (!respuesta.ok) throw new Error(`${url}: HTTP ${respuesta.status}`);
    return { data: peticion.type === "json" ? ((await respuesta.json()) as object) : await respuesta.arrayBuffer() };
  });
}
