// Ficheros de ejemplo de la detección en directo y de la interferencia GPS, con la forma que
// publica el servidor en el almacén público. Los usan los tests, las pruebas en el navegador
// (que interceptan las peticiones al almacén) y las capturas locales.

import type { Aviso, Directo } from "../src/datos/directo.ts";
import type { CeldaGnss, FicheroGnss, IndiceGnss, NivelGnss } from "../src/datos/gnss.ts";

export function aviso(cambios: Partial<Aviso> = {}): Aviso {
  return {
    id: "EKCH-2025-09-22T1826",
    oaci: "EKCH",
    nombre: "Copenhagen Kastrup",
    pais: "DK",
    lat: 55.618,
    lon: 12.656,
    estado: "posible_cierre",
    inicio: "2025-09-22T18:26Z",
    detectado: "2025-09-22T18:41Z",
    reanudado: null,
    evidencia: {
      esperados: 24.5,
      vistos: 0,
      llegadas_perdidas: 12,
      salidas_perdidas: 12,
      esperas: 5,
      desvios: 3,
    },
    confirmacion: null,
    primera_noticia: null,
    ventaja_min: null,
    ...cambios,
  };
}

export function directo(avisos: Aviso[] = [aviso()], cambios: Partial<Directo> = {}): Directo {
  return {
    version: 1,
    generado: "2025-09-22T18:45Z",
    fuente: "adsb_lol",
    ciclo_s: 60,
    aeropuertos_vigilados: 112,
    avisos,
    ...cambios,
  };
}

/** Hexágono aproximado alrededor de un punto, como los contornos H3 que publica el servidor. */
function hexagono(lon: number, lat: number, radio = 0.2): [number, number][] {
  return Array.from({ length: 6 }, (_, k) => {
    const angulo = (Math.PI / 3) * k;
    return [
      Math.round((lon + radio * 1.6 * Math.cos(angulo)) * 1000) / 1000,
      Math.round((lat + radio * Math.sin(angulo)) * 1000) / 1000,
    ] as [number, number];
  });
}

function nivel(p: number): NivelGnss {
  return p > 0.1 ? "alta" : p >= 0.02 ? "media" : "sin";
}

export function celda(h3: string, lon: number, lat: number, aeronaves: number, degradadas: number): CeldaGnss {
  const proporcion = Math.max(0, degradadas - 1) / aeronaves;
  return { h3, aeronaves, degradadas, proporcion, nivel: nivel(proporcion), contorno: hexagono(lon, lat) };
}

/** Celdas de un día: el Báltico con interferencia alta, Polonia media y Alemania sin ella. */
export function celdasDeEjemplo(): CeldaGnss[] {
  return [
    celda("841f053ffffffff", 20.6, 55.4, 140, 60),
    celda("841f055ffffffff", 21.2, 56.1, 120, 40),
    celda("841f0e1ffffffff", 18.9, 54.6, 200, 12),
    celda("841f0e3ffffffff", 17.4, 52.5, 300, 1),
    celda("841fa47ffffffff", 11.6, 48.3, 420, 2),
  ];
}

export function ficheroGnss(periodo: string, celdas: CeldaGnss[] = celdasDeEjemplo(), dias = 1): FicheroGnss {
  const aeronaves = celdas.reduce((s, c) => s + c.aeronaves, 0);
  const degradadas = celdas.reduce((s, c) => s + c.degradadas, 0);
  const proporcion = celdas.reduce((s, c) => s + c.proporcion * c.aeronaves, 0) / aeronaves;
  return {
    version: 1,
    periodo,
    dias,
    resolucion_h3: 4,
    resumen: {
      celdas: celdas.length,
      celdas_media: celdas.filter((c) => c.nivel === "media").length,
      celdas_alta: celdas.filter((c) => c.nivel === "alta").length,
      aeronaves,
      degradadas,
      proporcion,
      nivel: nivel(proporcion),
    },
    celdas,
  };
}

export function indiceGnss(dias: string[], meses: string[] = []): IndiceGnss {
  return { version: 1, generado: "2026-10-03T08:20Z", dias, meses };
}
