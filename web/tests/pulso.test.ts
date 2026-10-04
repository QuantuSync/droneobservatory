// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ACENTO_POR_DEFECTO } from "../src/paleta.ts";
import {
  RADIO_GRUPO_MAXIMO,
  RADIO_GRUPO_MINIMO,
  estilo,
  radioDeGrupo,
} from "../src/mapa/estilo.ts";
import {
  RADIO_PULSO,
  RADIO_PULSO_ATRIBUIDO,
  SEPARACION_PULSO_GRUPO,
  colocarPulsos,
  pulsosDe,
} from "../src/mapa/pulsos.ts";
import { MARCA_ATRIBUIDO } from "../src/paleta.ts";
import type { RasgoDibujado } from "../src/mapa/pulsos.ts";

const css = readFileSync(join(import.meta.dirname, "..", "src", "estilos.css"), "utf8");

const proyectar = (lon: number, lat: number) => ({ x: lon * 10, y: lat * 10 });

function punto(propiedades: Record<string, unknown>, lon = 1, lat = 2): RasgoDibujado {
  return { properties: propiedades, geometry: { type: "Point", coordinates: [lon, lat] } };
}

describe("pulso del mapa", () => {
  it("solo laten los incidentes nuevos desde la última visita, sea cual sea su estado", () => {
    const pulsos = pulsosDe(
      [
        punto({ id: "A", grave: 1, atribuido: 0, novedad: 0 }),
        punto({ id: "B", grave: 1, atribuido: 1, novedad: 0 }, 3, 4),
        punto({ id: "C", grave: 0, atribuido: 0, novedad: 1 }, 5, 6),
      ],
      proyectar,
    );
    expect(pulsos).toEqual([{ clave: "C", x: 50, y: 60, radio: RADIO_PULSO }]);
  });

  it("los grupos y las pilas laten si contienen algún incidente nuevo", () => {
    const pulsos = pulsosDe(
      [
        punto({ point_count: 5, cluster_id: 7, total: 9, n_atribuidos: 1, n_novedades: 0 }),
        punto({ point_count: 3, cluster_id: 8, total: 3, n_confirmados: 0, n_novedades: 2 }),
        punto({ n: 2, ids: "X,Y", n_confirmados: 2, novedad: 0 }),
        punto({ n: 2, ids: "Z,W", n_confirmados: 0, novedad: 1 }),
      ],
      proyectar,
    );
    expect(pulsos.map((p) => p.clave)).toEqual(["grupo-8", "pila-Z,W"]);
    expect(pulsos[0]?.radio).toBe(radioDeGrupo(3) + SEPARACION_PULSO_GRUPO);
    expect(pulsos[1]?.radio).toBe(radioDeGrupo(2) + SEPARACION_PULSO_GRUPO);
  });

  it("sin novedades (primera visita, o ya vistas o descartadas) no late nada", () => {
    expect(
      pulsosDe(
        [
          punto({ id: "A", grave: 1, atribuido: 1 }),
          punto({ point_count: 4, cluster_id: 9, total: 4, n_atribuidos: 2, n_novedades: 0 }),
        ],
        proyectar,
      ),
    ).toEqual([]);
  });

  it("varios atribuidos juntos laten con un anillo alrededor de su marcador", () => {
    const pulsos = pulsosDe(
      [punto({ point_count: 2, cluster_id: 7, total: 2, atribuido: 1, n_novedades: 1 })],
      proyectar,
    );
    expect(pulsos).toEqual([{ clave: "atribuidos-7", x: 10, y: 20, radio: RADIO_PULSO_ATRIBUIDO }]);
  });

  it("un rasgo repetido en dos teselas da un solo pulso", () => {
    const rasgo = punto({ id: "A", grave: 1, atribuido: 0, novedad: 1 });
    expect(pulsosDe([rasgo, rasgo], proyectar)).toHaveLength(1);
  });

  it("recoloca reutilizando los elementos y quita los que sobran", () => {
    const capa = document.createElement("div");
    colocarPulsos(capa, [
      { clave: "A", x: 1, y: 2, radio: 11 },
      { clave: "B", x: 3, y: 4, radio: 11 },
    ]);
    const primero = capa.children[0];
    expect(capa.querySelectorAll(".pulso")).toHaveLength(2);
    colocarPulsos(capa, [{ clave: "A", x: 5, y: 6, radio: 11 }]);
    expect(capa.children).toHaveLength(1);
    expect(capa.children[0]).toBe(primero);
    expect((capa.children[0] as HTMLElement).style.transform).toBe("translate(5.0px, 6.0px)");
  });

  it("un atribuido nuevo late igual que los demás: un anillo por fuera de su marcador", () => {
    const pulsos = pulsosDe([punto({ id: "F", grave: 1, atribuido: 1, novedad: 1 })], proyectar);
    expect(pulsos).toEqual([{ clave: "F", x: 10, y: 20, radio: RADIO_PULSO_ATRIBUIDO }]);
    // El anillo va por fuera del marcador, sin taparlo, con la separación de los grupos.
    expect(RADIO_PULSO_ATRIBUIDO).toBe(MARCA_ATRIBUIDO.radio + MARCA_ATRIBUIDO.halo + SEPARACION_PULSO_GRUPO);
    const capa = document.createElement("div");
    colocarPulsos(capa, pulsos);
    const anillo = capa.querySelector(".pulso") as HTMLElement | null;
    expect(anillo?.style.width).toBe(`${2 * RADIO_PULSO_ATRIBUIDO}px`);
    // Nada de siluetas de bandera.
    expect(capa.querySelector("svg")).toBeNull();
    expect(css).not.toContain("pulso-bandera");
    // Si deja de ser nuevo, desaparece.
    colocarPulsos(capa, []);
    expect(capa.children).toHaveLength(0);
  });

  it("el pulso es sutil: solo cambia la opacidad del anillo, y con movimiento reducido queda fijo", () => {
    const latido = /@keyframes latido \{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";
    expect(latido).toContain("opacity");
    expect(latido).not.toMatch(/transform|scale|width|height|margin/);
    expect(css).not.toContain("latido-fuerte");
    expect(css).not.toContain("pulso-atribuido");
    const reducido =
      /@media \(prefers-reduced-motion: reduce\) \{\s*\.pulso \{([^}]*)\}/.exec(
        css,
      )?.[1] ?? "";
    expect(reducido).toContain("animation: none");
    expect(reducido).toMatch(/opacity: 0\.\d+/);
  });

  it("el mapa ya no dibuja su propio anillo de novedades: lo hace el pulso", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", ACENTO_POR_DEFECTO);
    expect(layers.some((c) => c.id === "novedades")).toBe(false);
  });

  it("el mapa no anima nada: ninguna capa de pulso que repintar en cada fotograma", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", ACENTO_POR_DEFECTO);
    expect(layers.some((c) => c.id.includes("pulso"))).toBe(false);
  });

  it("el radio de un grupo crece con la raíz de su cuenta, entre un mínimo y un máximo", () => {
    expect(radioDeGrupo(1)).toBe(RADIO_GRUPO_MINIMO);
    expect(radioDeGrupo(100)).toBe(RADIO_GRUPO_MAXIMO);
    expect(radioDeGrupo(10_000)).toBe(RADIO_GRUPO_MAXIMO);
    expect(radioDeGrupo(9)).toBeGreaterThan(radioDeGrupo(4));
  });

  it("un solo sistema de marcas: nada de «×n», lo agrupado va en círculos con su número", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", ACENTO_POR_DEFECTO);
    expect(JSON.stringify(layers)).not.toContain("×");
    const grupos = layers.find((c) => c.id === "grupos");
    // Los grupos incluyen las pilas de un mismo punto (n > 1), y crecen con la cuenta.
    expect(JSON.stringify(grupos && "filter" in grupos ? grupos.filter : null)).toContain('"n"');
    expect(JSON.stringify(grupos?.paint)).toContain('"sqrt"');
    expect(JSON.stringify(grupos?.paint)).toContain(String(RADIO_GRUPO_MINIMO));
    expect(JSON.stringify(grupos?.paint)).toContain(String(RADIO_GRUPO_MAXIMO));
  });
});
