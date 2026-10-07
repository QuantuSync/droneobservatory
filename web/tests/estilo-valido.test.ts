// El estilo del mapa cumple la especificación de MapLibre: una capa mal escrita deja el mapa sin
// cargar, sin ningún error a la vista.
import { validateStyleMin } from "@maplibre/maplibre-gl-style-spec";
import { describe, expect, it } from "vitest";

import { estilo } from "../src/mapa/estilo.ts";

describe("estilo del mapa", () => {
  it("cumple la especificación de MapLibre", () => {
    const errores = validateStyleMin(estilo("es", "https://ejemplo.org", "#ffffff") as never).map((e) => e.message);
    expect(errores).toEqual([]);
  });
});
