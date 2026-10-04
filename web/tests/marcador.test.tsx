// @vitest-environment jsdom
// Las cifras del periodo: con 0 atribuidos esa cifra no se muestra (ni el número ni su círculo)
// y las otras tres se reparten el sitio; con uno o más, vuelve.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Marcador } from "../src/componentes/Marcador.tsx";
import { textos } from "../src/i18n/index.ts";

const es = textos("es");
const CIFRAS = { incidentes: 592, confirmados: 218, atribuidos: 0, paises: 28 };

afterEach(cleanup);

describe("cifras del periodo", () => {
  it("sin atribuidos, tres cifras; en el menú, en tres columnas", () => {
    for (const forma of ["linea", "rejilla"] as const) {
      const { container, unmount } = render(
        <Marcador t={es} idioma="es" cifras={CIFRAS} animar={false} forma={forma} />,
      );
      expect(container.querySelectorAll("dt")).toHaveLength(3);
      expect(container.textContent).not.toContain(es.marcador.atribuidos);
      expect(container.querySelector("[data-marca-cifra]")).toBeNull();
      if (forma === "rejilla") expect(container.querySelector("dl")?.className).toContain("grid-cols-3");
      unmount();
    }
  });

  it("con un atribuido o más, la cifra vuelve con su círculo", () => {
    const { container } = render(
      <Marcador t={es} idioma="es" cifras={{ ...CIFRAS, atribuidos: 2 }} animar={false} forma="rejilla" />,
    );
    expect(container.querySelectorAll("dt")).toHaveLength(4);
    expect(container.textContent).toContain(es.marcador.atribuidos);
    expect(container.querySelector("[data-marca-cifra]")).not.toBeNull();
    expect(container.querySelector("dl")?.className).toContain("grid-cols-2");
  });
});
