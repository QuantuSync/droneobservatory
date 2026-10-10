// @vitest-environment jsdom
// Capa de Ucrania sin ratón: lo que está a la vista se recorre con el teclado en orden (regiones
// de la más atacada a la menos, impactos del más reciente, con un tope) y la lista de la capa
// agrupa lo mismo; elegir una fila abre lo suyo. El antes y después por satélite lleva su
// descripción y el valor leído del deslizador.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ListaUcrania } from "../src/componentes/ListaUcrania.tsx";
import type { CeldaGnss } from "../src/datos/gnss.ts";
import type { FilaImpacto } from "../src/datos/tipos.ts";
import { textos } from "../src/i18n/index.ts";
import { MAXIMO_EN_TECLADO, centroDeCelda, ucraniaALaVista } from "../src/mapa/tecladoUcrania.ts";

const es = textos("es");

function impacto(id: string, dia: number, lon: number, lat: number, region = "UA-63"): FilaImpacto {
  return [id, dia, 0, lon, lat, 0, 0, 0, region];
}

const base = {
  ucrania: true,
  satelite: false,
  gnss: false,
  intensidad: new Map([
    ["UA-63", 12],
    ["UA-30", 40],
    ["RU-BEL", 7],
    ["UA-46", 0],
  ]),
  centros: { "UA-63": [36.2, 49.9], "UA-30": [30.5, 50.4], "RU-BEL": [37.5, 50.6], "UA-46": [24, 49.8] } as Record<
    string,
    [number, number]
  >,
  impactos: [impacto("a", 10, 36, 50), impacto("b", 30, 30, 50), impacto("c", 20, 10, 45)],
  celdas: null,
  ciudadesSinLuz: null,
  alumbrado: null,
};
const todo = () => true;
const soloEste = (lon: number) => lon > 25;

describe("lo que está a la vista, para el teclado", () => {
  it("regiones con ataques cuyo centro se ve, de la más atacada a la menos", () => {
    const vista = ucraniaALaVista(base, soloEste);
    expect(vista.regiones.map((r) => r.clave)).toEqual(["UA-30", "UA-63", "RU-BEL"]);
  });

  it("impactos a la vista del más reciente al más antiguo", () => {
    const vista = ucraniaALaVista(base, soloEste);
    expect(vista.impactos.map((i) => i.clave)).toEqual(["b", "a"]);
    expect(vista.totalImpactos).toBe(2);
  });

  it("con miles de impactos, solo los más recientes hasta el tope", () => {
    const muchos = Array.from({ length: 3000 }, (_, i) => impacto(`i${i}`, i, 30, 50));
    const vista = ucraniaALaVista({ ...base, impactos: muchos }, todo);
    expect(vista.impactos).toHaveLength(MAXIMO_EN_TECLADO);
    expect(vista.impactos[0]?.clave).toBe("i2999");
    expect(vista.totalImpactos).toBe(3000);
  });

  it("sin la capa, nada; las celdas de GPS solo con su capa", () => {
    expect(ucraniaALaVista({ ...base, ucrania: false }, todo).regiones).toEqual([]);
    const celda = { h3: "x", proporcion: 0.3, contorno: [[30, 50], [32, 50], [31, 52]] } as unknown as CeldaGnss;
    expect(centroDeCelda(celda)).toEqual([31, 50 + 2 / 3]);
    expect(ucraniaALaVista({ ...base, celdas: [celda] }, todo).celdas).toEqual([]);
    expect(ucraniaALaVista({ ...base, gnss: true, celdas: [celda] }, todo).celdas.map((c) => c.clave)).toEqual(["x"]);
  });
});

describe("lista de la capa de Ucrania", () => {
  it("agrupa regiones de Ucrania y de Rusia y los últimos impactos; elegir abre lo suyo", async () => {
    const onRegion = vi.fn();
    const onImpacto = vi.fn();
    render(
      <ListaUcrania
        t={es}
        idioma="es"
        intensidad={base.intensidad}
        impactos={base.impactos}
        corredores={null}
        onRegion={onRegion}
        onImpacto={onImpacto}
        onCorredor={vi.fn()}
      />,
    );
    const grupos = screen.getAllByRole("group");
    expect(grupos.map((g) => g.querySelector("summary")?.textContent)).toEqual([
      "Regiones de Ucrania con ataques · 2",
      "Regiones de Rusia con ataques · 1",
      "Impactos con lugar · 3",
    ]);
    const usuario = userEvent.setup();
    const primera = within(grupos[0] as HTMLElement).getAllByRole("button")[0] as HTMLElement;
    expect(primera.textContent).toMatch(/· 40 ataques en el periodo$/);
    await usuario.click(primera);
    expect(onRegion).toHaveBeenCalledWith("UA-30");
    await usuario.click(within(grupos[2] as HTMLElement).getAllByRole("button", { hidden: true })[0] as HTMLElement);
    expect(onImpacto).toHaveBeenCalledWith(base.impactos[1]);
  });
});
