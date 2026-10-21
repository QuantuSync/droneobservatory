// @vitest-environment jsdom
// La cabecera de la ficha: el nombre de la instalación solo si es una de verdad (aeropuerto,
// base…), con el titular debajo; con un objetivo «otra» (EODI-2026-00648, «Józefów · Otro
// lugar»), el titular, una sola vez. En español y en inglés.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { textos } from "../src/i18n/index.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const JOZEFOW = {
  es: "Dron de prácticas de un instituto militar polaco cae en Józefów, cerca de Varsovia",
  en: "Training drone from a Polish military institute falls in Józefów, near Warsaw",
};

function cabecera(detalle: ReturnType<typeof detalleIncidente>, idioma: "es" | "en") {
  const { container, unmount } = render(<FichaIncidente t={textos(idioma)} idioma={idioma} incidente={detalle} />);
  const h2 = container.querySelector("h2")?.textContent ?? "";
  const texto = container.textContent ?? "";
  unmount();
  return { h2, texto };
}

describe("la cabecera de la ficha", () => {
  it("con un objetivo «otra» es el titular, sin repetirlo", () => {
    const detalle = detalleIncidente(
      incidente({
        id: "EODI-2026-00648",
        tipo: "sobrevuelo",
        titulo: JOZEFOW,
        lugar: { radio_km: 5, pais: "PL", localidad: "Józefów" },
        objetivo: { categoria: "otra", nombre: "Józefów" },
      }),
    );
    for (const idioma of ["es", "en"] as const) {
      const { h2, texto } = cabecera(detalle, idioma);
      expect(h2).toBe(JOZEFOW[idioma]);
      expect(texto.split(JOZEFOW[idioma]).length - 1).toBe(1);
    }
  });

  it("con un aeropuerto es el aeropuerto, con el titular debajo", () => {
    const detalle = detalleIncidente(incidente());
    for (const [idioma, titulo] of [
      ["es", "Cierre del aeropuerto de Múnich"],
      ["en", "Munich airport closure"],
    ] as const) {
      const { h2, texto } = cabecera(detalle, idioma);
      expect(h2).not.toBe(titulo);
      expect(h2.length).toBeGreaterThan(0);
      expect(texto).toContain(titulo);
    }
  });
});
