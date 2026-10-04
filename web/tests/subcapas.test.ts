// Las subcapas de la capa de guerra salen apagadas; un enlace las abre como estaban (y los de
// las capas retiradas «Luz nocturna» y «Focos 24 h», en «Con satélite» con su filtro).

import { describe, expect, it } from "vitest";

import { CAPAS_INICIALES } from "../src/componentes/Controles.tsx";
import { ATAJOS } from "../src/estado/atajos.ts";
import { conSubcapas, leerSubcapas } from "../src/estado/subcapas.ts";

describe("subcapas de la capa de guerra", () => {
  it("apagadas al empezar: con Ucrania, solo regiones e impactos", () => {
    expect(CAPAS_INICIALES).toMatchObject({ ucrania: false, corredores: false, satelite: false });
    expect(Object.keys(CAPAS_INICIALES)).not.toContain("luz");
    expect(Object.keys(CAPAS_INICIALES)).not.toContain("focosVivos");
    expect(leerSubcapas("")).toBeNull();
    expect(leerSubcapas("?ultimos=7d")).toBeNull();
  });

  it("un enlace con «Corredores» encendido lo abre encendido", () => {
    expect(leerSubcapas("?guerra=corredores")).toEqual({
      corredores: true,
      satelite: false,
      filtro: [],
    });
    expect(leerSubcapas("?ultimos=7d&guerra=corredores,satelite&satelite=foco")).toEqual({
      corredores: true,
      satelite: true,
      filtro: ["foco"],
    });
  });

  it("los enlaces a «Luz nocturna» y «Focos 24 h» abren «Con satélite» con su filtro", () => {
    expect(leerSubcapas("?satelite=luz")).toEqual({
      corredores: false,
      satelite: true,
      filtro: ["apagon", "oscura"],
    });
    expect(leerSubcapas("?satelite=focos24h")?.filtro).toEqual(["foco"]);
  });

  it("se escriben sin pisar los filtros ni el periodo, y se quitan al apagarlas", () => {
    const con = conSubcapas("?ultimos=7d&tipo=avistamiento", {
      corredores: true,
      satelite: true,
      filtro: ["apagon"],
    });
    expect(con).toBe("?ultimos=7d&tipo=avistamiento&guerra=corredores,satelite&satelite=apagon");
    expect(conSubcapas(con, { corredores: false, satelite: false, filtro: [] })).toBe(
      "?ultimos=7d&tipo=avistamiento",
    );
  });

  it("«Con satélite» tiene su atajo de teclado", () => {
    expect(ATAJOS).toContainEqual(["4", "capaSatelite"]);
  });
});
