// @vitest-environment jsdom
// Filtros: lo elegido se distingue de un vistazo (claro con texto oscuro, con contraste medido) y
// «Aplicar» encuadra lo que queda a la vista en las capas encendidas.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BotonAplicar } from "../src/componentes/Filtros.tsx";
import type { IncidenteResumen } from "../src/datos/tipos.ts";
import { textos } from "../src/i18n/index.ts";
import { MEDIA_REGION_GRADOS, cajaDeLoVisible } from "../src/mapa/cajaVisible.ts";

const raiz = join(import.meta.dirname, "..", "src");

function luminancia(hex: string): number {
  const canales = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canales.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [number, number];
  return (l1 + 0.05) / (l2 + 0.05);
}

function incidente(lon: number, lat: number): IncidenteResumen {
  return { punto: { lon, lat, radio_km: 1 }, aproximado: null } as IncidenteResumen;
}

describe("selección en los filtros", () => {
  const css = readFileSync(join(raiz, "estilos.css"), "utf-8");
  const color = (nombre: string) => css.match(new RegExp(`${nombre}:\\s*(#[0-9a-f]{6})`, "i"))?.[1] ?? "";

  it("lo elegido va en claro con texto oscuro, para pulsados y desplegables con valor (regla común)", () => {
    const inicio = css.indexOf('.control:is([aria-pressed="true"]');
    expect(inicio).toBeGreaterThan(-1);
    const bloque = css.slice(inicio, css.indexOf("}", inicio));
    expect(bloque).toContain("[data-activo]");
    expect(bloque).toContain("color: var(--color-fondo)");
    expect(bloque).toContain("background-color: var(--acento)");
  });

  it("contraste: 3:1 entre los dos estados y 4,5:1 del texto en cada uno", () => {
    const [acento, fondo, panel, secundario, texto] = [
      color("--acento"),
      color("--color-fondo"),
      color("--color-panel-solido"),
      color("--color-secundario"),
      color("--color-texto"),
    ];
    expect(contraste(acento, panel)).toBeGreaterThanOrEqual(3);
    expect(contraste(fondo, acento)).toBeGreaterThanOrEqual(4.5);
    expect(contraste(fondo, texto)).toBeGreaterThanOrEqual(4.5);
    expect(contraste(secundario, panel)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("botón «Aplicar»", () => {
  it("dice solo «Aplicar» / «Apply», sin cifras", () => {
    const onAplicar = vi.fn();
    const { unmount } = render(<BotonAplicar t={textos("es")} onAplicar={onAplicar} />);
    const boton = screen.getByRole("button", { name: "Aplicar" });
    expect(boton.textContent).toBe("Aplicar");
    boton.click();
    expect(onAplicar).toHaveBeenCalledTimes(1);
    unmount();
    render(<BotonAplicar t={textos("en")} onAplicar={onAplicar} />);
    expect(screen.getByRole("button", { name: "Apply" }).textContent).toBe("Apply");
  });
});

describe("caja de lo que queda a la vista", () => {
  const nada = { incidentes: null, ucrania: null, gnss: null };

  it("sin nada a la vista no hay caja (el mapa no se mueve)", () => {
    expect(cajaDeLoVisible(nada)).toBeNull();
    expect(cajaDeLoVisible({ ...nada, incidentes: [] })).toBeNull();
  });

  it("un solo incidente da una caja de un punto (el tope de zoom lo pone el mapa)", () => {
    expect(cajaDeLoVisible({ ...nada, incidentes: [incidente(4, 50)] })).toEqual([4, 50, 4, 50]);
  });

  it("une los incidentes, las regiones con ataques, los impactos y los corredores", () => {
    const caja = cajaDeLoVisible({
      incidentes: [incidente(-3, 40), incidente(10, 55)],
      ucrania: {
        intensidad: new Map([
          ["UA-30", 5],
          ["UA-46", 0],
        ]),
        centros: { "UA-30": [30.5, 50.4], "UA-46": [24, 49.8] },
        impactos: [["i", 1, 0, 36.2, 49.9, 0, 0, 0, "UA-63"]],
        corredores: null,
      },
      gnss: null,
    });
    expect(caja).toEqual([-3, 40, 36.2, 55]);
  });

  it("solo la capa de Ucrania: sus regiones con margen alrededor del centro", () => {
    const caja = cajaDeLoVisible({
      ...nada,
      ucrania: { intensidad: new Map([["UA-30", 2]]), centros: { "UA-30": [30.5, 50.4] }, impactos: [], corredores: null },
    });
    const [lon, lat] = MEDIA_REGION_GRADOS;
    expect(caja).toEqual([30.5 - lon, 50.4 - lat, 30.5 + lon, 50.4 + lat]);
  });

  it("de la capa de Ucrania, las regiones rusas lejanas no entran en el encuadre (sí las fronterizas y Crimea)", () => {
    const caja = cajaDeLoVisible({
      ...nada,
      ucrania: {
        intensidad: new Map([
          ["UA-43", 3],
          ["RU-BRY", 4],
          ["RU-ROS", 1],
          ["RU-BA", 6],
          ["RU-MOW", 2],
        ]),
        centros: { "UA-43": [34.2, 45.3], "RU-BRY": [33.4, 52.9], "RU-ROS": [41.2, 47.7], "RU-BA": [56.5, 54.2], "RU-MOW": [37.6, 55.75] },
        impactos: [
          ["i", 1, 0, 36.2, 49.9, 0, 0, 0, "UA-63"],
          ["j", 1, 1, 55.9, 54.7, 0, 0, 0, "RU-BA"],
        ],
        corredores: [{ desde: [32.9, 54.3], hasta: [30.5, 50.4] } as never],
      },
    });
    const [lon, lat] = MEDIA_REGION_GRADOS;
    expect(caja).toEqual([30.5, 45.3 - lat, 41.2 + lon, 52.9 + lat]);
  });

  it("con incidentes de Europa a la vista, el encuadre los sigue incluyendo", () => {
    const caja = cajaDeLoVisible({
      incidentes: [incidente(4.5, 51)],
      ucrania: { intensidad: new Map([["RU-BA", 6], ["UA-30", 1]]), centros: { "RU-BA": [56.5, 54.2], "UA-30": [30.5, 50.4] }, impactos: [], corredores: null },
      gnss: null,
    });
    const [lon, lat] = MEDIA_REGION_GRADOS;
    expect(caja).toEqual([4.5, 50.4 - lat, 30.5 + lon, 50.4 + lat]);
  });
});
