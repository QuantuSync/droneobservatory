// Guerra por satélite: pérdida de luz, corredores de ataque (arcos y grosor), focos de calor de
// 24 horas e índice de imágenes de antes y después.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { resumirUcrania } from "../src/datos/derivar.ts";
import {
  ANCHO_MAXIMO_CORREDOR,
  ANCHO_MINIMO_CORREDOR,
  anchoDeCorredor,
  arco,
  casarZonas,
  ciudadesSinLuz,
  corredoresDelPeriodo,
  lucesDelPeriodo,
  opacidadDePerdida,
  perdidaPorRegion,
  puntoMasCercano,
} from "../src/datos/guerraSatelite.ts";
import type { ZonaConfig } from "../src/datos/guerraSatelite.ts";
import type { PerdidaLuz } from "../src/datos/tipos.ts";
import {
  validarAtaque,
  validarFocosVivos,
  validarIndiceSatelite,
  validarResumenUcrania,
} from "../src/datos/validar.ts";
import { corredoresEnMapa, focosVivosEnMapa } from "../src/mapa/geometria.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { ataque, publicacion } from "./ejemplos.ts";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const ZONAS = (
  JSON.parse(readFileSync(join(RAIZ, "configuracion", "zonas_lanzamiento.json"), "utf-8")) as {
    zonas: ZonaConfig[];
  }
).zonas;

function perdida(cambios: Partial<PerdidaLuz> = {}): PerdidaLuz {
  return {
    zona: "ciudad",
    region: "UA-63",
    ciudad: { id: "katotth:UA63120270010096107", nombre: "Харків", punto: { lat: 49.99, lon: 36.23 } },
    perdida_pct: 87,
    noche: "2024-03-22",
    noches: ["2024-03-22", "2024-03-23"],
    referencia: { desde: "2024-02-29", hasta: "2024-03-20", noches: 6, brillo: 5.1 },
    brillo: 0.66,
    origen: "medido",
    ...cambios,
  };
}

const TODO = { desde: -1e6, hasta: 1e6 };

describe("pérdida de luz nocturna", () => {
  // La de la región entera no lleva ciudad: el validador es cerrado.
  const deRegion: Partial<PerdidaLuz> = perdida({ zona: "region", perdida_pct: 64 });
  delete deRegion.ciudad;
  const conLuz = ataque({ perdida_luz: [perdida(), deRegion as PerdidaLuz] });

  it("valida en el ataque con su origen medido y rechaza otro origen", () => {
    expect(validarAtaque(conLuz).ok).toBe(true);
    const roto = ataque({ perdida_luz: [{ ...perdida(), origen: "prensa" as "medido" }] });
    expect(validarAtaque(roto).ok).toBe(false);
    expect(validarAtaque(ataque({ perdida_luz: [{ ...perdida(), interno: 1 } as PerdidaLuz] })).ok).toBe(
      false,
    );
  });

  it("se resume, se filtra por periodo y oscurece según la pérdida", () => {
    const resumen = resumirUcrania(publicacion([conLuz]));
    expect(validarResumenUcrania(resumen).ok).toBe(true);
    expect(resumen.luces).toHaveLength(2);
    const dia = diaDeInstante("2026-09-29T15:00Z");
    expect(lucesDelPeriodo(resumen, { desde: dia, hasta: dia })).toHaveLength(2);
    expect(lucesDelPeriodo(resumen, { desde: dia + 1, hasta: dia + 9 })).toHaveLength(0);
    expect(perdidaPorRegion(resumen.luces)).toEqual(new Map([["UA-63", 64]]));
    const ciudades = ciudadesSinLuz(resumen.luces);
    expect(ciudades.map((c) => [c.nombre, c.perdida])).toEqual([["Харків", 87]]);
    expect(opacidadDePerdida(100)).toBeGreaterThan(opacidadDePerdida(50));
    expect(opacidadDePerdida(0)).toBeGreaterThan(0);
  });
});

describe("corredores de ataque", () => {
  const { zonas, casar } = casarZonas(ZONAS);

  it("casan los nombres de los partes con una zona con punto", () => {
    const orel = casar("Орел");
    expect(orel).not.toBeNull();
    expect(zonas[orel ?? -1]?.id).toBe("oryol_yuzhny");
    // «Донецьк» es el aeropuerto; el territorio ocupado de la provincia es una zona sin punto
    // en el catálogo y no tiene arco.
    expect(zonas[casar("Донецьк") ?? -1]?.id).toBe("donetsk_aeropuerto");
    expect(casar("ТОТ Донецької обл.")).toBeNull();
    expect(casar("Невідомо")).toBeNull();
  });

  const geografia = {
    zonas,
    casar,
    centros: new Map<string, [number, number]>([
      ["UA-32", [30.3, 50.3]],
      ["UA-63", [36.5, 49.6]],
      ["RU-BRY", [33.4, 52.8]],
    ]),
    fronteraUcrania: new Map<string, [number, number]>([["RU-BRY", [33.0, 52.3]]]),
  };
  const rusos = [
    ataque({ zonas_lanzamiento: ["Брянськ", "Орел"] }),
    ataque({
      id: "EODI-UA-2026-1014",
      zonas_lanzamiento: ["Брянськ"],
      lanzados: { total: { min: 50, max: 50 } },
      regiones: [{ region: "UA-63" }],
    }),
  ];
  const ucraniano = ataque({
    id: "EODI-UA-2026-1015",
    sentido: "UA_RU",
    zonas_lanzamiento: [],
    regiones: [{ region: "RU-BRY", derribados: { min: 30, max: 30 } }],
  });
  delete ucraniano.lanzados;

  it("suman en los dos sentidos los drones del periodo", () => {
    const resumen = resumirUcrania(publicacion([...rusos, ucraniano]), new Map(), geografia);
    expect(validarResumenUcrania(resumen).ok).toBe(true);
    const corredores = corredoresDelPeriodo(resumen, TODO);
    const por = new Map(corredores.map((c) => [c.clave, c]));
    // Briansk → Járkov: los 188 del primer ataque y los 50 del segundo.
    expect(por.get("bryansk|UA-63")?.drones).toBe(238);
    expect(por.get("bryansk|UA-63")?.ataques).toBe(2);
    expect(por.get("oryol_yuzhny|UA-32")?.drones).toBe(188);
    // Contra Rusia: desde la frontera, con los derribos del parte ruso.
    const ruso = por.get("UA|RU-BRY");
    expect(ruso?.sentido).toBe("UA_RU");
    expect(ruso?.drones).toBe(30);
    expect(ruso?.desde).toEqual([33.0, 52.3]);
    // El periodo sin ataques no tiene corredores.
    expect(corredoresDelPeriodo(resumen, { desde: 0, hasta: 1 })).toEqual([]);
  });

  it("un tramo ya sumado en otro parte no vuelve a sumar drones ni dibuja arcos sin cifra", () => {
    const resumen = resumirUcrania(
      publicacion([ataque({ zonas_lanzamiento: ["Брянськ"], incluido_en: "EODI-UA-2026-1001" })]),
      new Map(),
      geografia,
    );
    expect(corredoresDelPeriodo(resumen, TODO)).toEqual([]);
  });

  it("el grosor crece con los drones, del mínimo al máximo", () => {
    expect(anchoDeCorredor(0, 100)).toBe(ANCHO_MINIMO_CORREDOR);
    expect(anchoDeCorredor(100, 100)).toBe(ANCHO_MAXIMO_CORREDOR);
    expect(anchoDeCorredor(25, 100)).toBeGreaterThan(anchoDeCorredor(10, 100));
    const resumen = resumirUcrania(publicacion([...rusos, ucraniano]), new Map(), geografia);
    const mapa = corredoresEnMapa(corredoresDelPeriodo(resumen, TODO));
    const anchos = mapa.features.map((f) => f.properties.ancho);
    // Los gruesos al final, encima de los finos.
    expect([...anchos].sort((a, b) => a - b)).toEqual(anchos);
    expect(Math.max(...anchos)).toBe(ANCHO_MAXIMO_CORREDOR);
  });

  it("el arco va de un extremo al otro, curvado y sin salirse", () => {
    const puntos = arco([38.2, 46.06], [36.5, 49.6]);
    expect(puntos[0]).toEqual([38.2, 46.06]);
    expect(puntos.at(-1)).toEqual([36.5, 49.6]);
    const medio = puntos[Math.floor(puntos.length / 2)] ?? [0, 0];
    // No está sobre la recta: es un arco.
    expect(Math.abs(medio[0] - 37.35) + Math.abs(medio[1] - 47.83)).toBeGreaterThan(0.1);
  });

  it("el punto de la frontera más cercano", () => {
    const linea: [number, number][] = [
      [30, 50],
      [32, 50],
      [32, 52],
    ];
    expect(puntoMasCercano([linea], [31, 50.2])).toEqual([31, 50]);
    expect(puntoMasCercano([linea], [33, 51])).toEqual([32, 51]);
  });
});

describe("focos de calor de 24 horas", () => {
  const fichero = {
    generado: "2026-10-03T09:36Z",
    desde: "2026-10-02T09:36Z",
    ultimo_foco: "2026-10-03T01:12Z",
    fuente: "NASA FIRMS",
    atribucion: "NASA FIRMS",
    zona: { oeste: 22, sur: 43, este: 60, norte: 61 },
    descartados: { baja_confianza: 3, fuentes_habituales: 12, fuego_frecuente: 40 },
    focos: [
      [36.231, 49.992, "2026-10-03T01:12Z", "N21", "EODI-IG-2026-03500"],
      [30.1, 50.2, "2026-10-02T23:40Z", "N20", null],
    ],
  };

  it("validan y se dibujan, resaltados los que coinciden con un impacto", () => {
    const resultado = validarFocosVivos(fichero);
    expect(resultado.ok).toBe(true);
    if (!resultado.ok) return;
    const mapa = focosVivosEnMapa(resultado.datos.focos);
    expect(mapa.features.map((f) => f.properties.impacto)).toEqual(["EODI-IG-2026-03500", ""]);
  });

  it("rechazan un foco mal formado", () => {
    expect(validarFocosVivos({ ...fichero, focos: [[36.2, 49.9, "ayer", "N21", null]] }).ok).toBe(false);
  });
});

describe("índice de imágenes de antes y después", () => {
  const indice = {
    generado: "2026-10-03T06:33Z",
    fuente: "Copernicus Sentinel-2 L2A",
    atribucion: "Contains modified Copernicus Sentinel data 2025",
    parejas: {
      "EODI-IG-2025-02569": {
        recorte: { lat: 59.49, lon: 32.08, lado_m: 4300 },
        antes: {
          fecha: "2025-09-11T09:14:10Z",
          escena: "S2C_36VVL_20250911_1_L2A",
          objeto: "satelite/EODI-IG-2025-02569/antes-20250911-S2C_36VVL_20250911_1_L2A.jpg",
          nubes_recorte: 0,
        },
        despues: null,
      },
    },
  };

  it("valida con una pareja a medias", () => {
    expect(validarIndiceSatelite(indice).ok).toBe(true);
  });

  it("no acepta objetos fuera de su carpeta", () => {
    const antes = { ...indice.parejas["EODI-IG-2025-02569"].antes, objeto: "../otra/cosa.jpg" };
    const roto = {
      ...indice,
      parejas: { "EODI-IG-2025-02569": { ...indice.parejas["EODI-IG-2025-02569"], antes } },
    };
    expect(validarIndiceSatelite(roto).ok).toBe(false);
  });
});
