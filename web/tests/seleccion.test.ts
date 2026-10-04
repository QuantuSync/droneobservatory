// Corredores fáciles de seleccionar: zona sensible de los arcos, prioridad de la pulsación
// (marcas, arcos, áreas) y lista para elegir cuando dos arcos quedan a la misma distancia.

import { describe, expect, it } from "vitest";

import {
  CAPAS_DE_AREAS,
  CAPAS_DE_CORREDORES,
  CAPAS_DE_PUNTOS_AL_TOQUE,
  CAPAS_DE_PUNTOS_DE_GUERRA,
  CAPAS_PULSABLES,
  CAPA_IMPACTOS_GRUPOS,
  CAPA_CORREDORES,
  CAPA_CORREDORES_ZONA,
  CAPA_REALCE_ARCO,
  CAPA_REALCE_PUNTO,
  FUENTE_CORREDORES,
  estilo,
} from "../src/mapa/estilo.ts";
import {
  EMPATE_ARCOS_PX,
  ZONA_ARCO_DEDO_PX,
  ZONA_ARCO_RATON_PX,
  anchoZonaArco,
  distanciaALinea,
  distanciaASegmento,
  elegir,
} from "../src/mapa/seleccion.ts";
import type { Candidato } from "../src/mapa/seleccion.ts";
import { PALETA } from "../src/paleta.ts";

describe("zona sensible de los arcos", () => {
  it("mide al menos 16 px con ratón y 28 px con el dedo", () => {
    expect(ZONA_ARCO_RATON_PX).toBeGreaterThanOrEqual(16);
    expect(ZONA_ARCO_DEDO_PX).toBeGreaterThanOrEqual(28);
    expect(anchoZonaArco(false)).toBe(ZONA_ARCO_RATON_PX);
    expect(anchoZonaArco(true)).toBe(ZONA_ARCO_DEDO_PX);
  });

  it("es una capa invisible y ancha sobre la misma geometría, sin cambiar el arco en reposo", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const capa = (id: string) => layers.find((c) => c.id === id);
    const zona = capa(CAPA_CORREDORES_ZONA);
    const arco = capa(CAPA_CORREDORES);
    expect(zona?.type).toBe("line");
    expect(zona && "source" in zona ? zona.source : null).toBe(FUENTE_CORREDORES);
    expect(zona?.paint).toMatchObject({
      "line-opacity": 0,
      "line-width": ["+", ["get", "ancho"], ZONA_ARCO_RATON_PX],
    });
    expect(arco?.paint).toMatchObject({ "line-color": PALETA.guerra, "line-width": ["get", "ancho"] });
    // El realce: violeta claro de lo resaltado, más grueso que el arco.
    expect(capa(CAPA_REALCE_ARCO)?.paint).toMatchObject({ "line-color": PALETA.guerraClaro });
    expect(capa(CAPA_REALCE_PUNTO)?.paint).toMatchObject({ "circle-stroke-color": PALETA.guerraClaro });
    expect(CAPAS_DE_CORREDORES).toEqual(
      expect.arrayContaining([CAPA_CORREDORES, CAPA_CORREDORES_ZONA, CAPA_REALCE_ARCO]),
    );
    // Encima del arco y de las regiones, por debajo de los puntos de la capa de guerra.
    const orden = layers.map((c) => c.id);
    expect(orden.indexOf(CAPA_CORREDORES_ZONA)).toBeGreaterThan(orden.indexOf(CAPA_CORREDORES));
    expect(orden.indexOf(CAPA_REALCE_PUNTO)).toBeGreaterThan(orden.indexOf(CAPA_REALCE_ARCO));
  });

  it("con el dedo, los grupos de impactos no ganan a un arco que pasa a su lado", () => {
    expect(CAPAS_DE_PUNTOS_AL_TOQUE).not.toContain(CAPA_IMPACTOS_GRUPOS);
    expect(CAPAS_DE_PUNTOS_AL_TOQUE).toEqual(
      CAPAS_DE_PUNTOS_DE_GUERRA.filter((id) => id !== CAPA_IMPACTOS_GRUPOS),
    );
  });

  it("los arcos no se pulsan por su línea fina: van por su zona; las áreas, al final", () => {
    expect(CAPAS_PULSABLES).not.toContain(CAPA_CORREDORES);
    for (const area of CAPAS_DE_AREAS) {
      for (const punto of CAPAS_DE_PUNTOS_DE_GUERRA) {
        expect(CAPAS_PULSABLES.indexOf(punto)).toBeLessThan(CAPAS_PULSABLES.indexOf(area));
      }
    }
  });
});

describe("distancias en la pantalla", () => {
  it("de un punto a un segmento y a una línea quebrada", () => {
    expect(distanciaASegmento([5, 6], [0, 0], [10, 0])).toBe(6);
    expect(distanciaASegmento([-3, 4], [0, 0], [10, 0])).toBe(5);
    expect(distanciaASegmento([1, 1], [2, 2], [2, 2])).toBeCloseTo(Math.SQRT2);
    const linea = [
      [0, 0],
      [10, 0],
      [10, 10],
    ] as const;
    expect(distanciaALinea([13, 5], linea)).toBe(3);
    expect(distanciaALinea([0, 0], [])).toBe(Infinity);
  });
});

describe("prioridad de la pulsación", () => {
  const region: Candidato<string> = { clase: "area", distancia: 0, valor: "UA-63" };
  const arco = (valor: string, distancia: number): Candidato<string> => ({
    clase: "arco",
    distancia,
    valor,
  });

  it("un clic a 6 px de un arco abre el corredor, no la región de debajo", () => {
    expect(elegir([region, arco("Kursk|UA-63", 6)])).toEqual({ tipo: "uno", valor: "Kursk|UA-63" });
  });

  it("lejos de cualquier arco, la región", () => {
    expect(elegir([region])).toEqual({ tipo: "uno", valor: "UA-63" });
    expect(elegir([])).toBeNull();
  });

  it("una marca puntual gana al arco y a la región", () => {
    const impacto: Candidato<string> = { clase: "marca", distancia: 3, valor: "EODI-IG-2026-03486" };
    expect(elegir([region, arco("Kursk|UA-63", 1), impacto])).toEqual({
      tipo: "uno",
      valor: "EODI-IG-2026-03486",
    });
  });

  it("de varios arcos, el más cercano; casi a la misma distancia, la lista para elegir", () => {
    expect(elegir([arco("Kursk|UA-63", 7), arco("Oriol|UA-63", 2)])).toEqual({
      tipo: "uno",
      valor: "Oriol|UA-63",
    });
    expect(elegir([arco("Kursk|UA-63", 4), arco("Oriol|UA-63", 4 + EMPATE_ARCOS_PX / 2), region])).toEqual({
      tipo: "varios",
      valores: ["Kursk|UA-63", "Oriol|UA-63"],
    });
  });
});
