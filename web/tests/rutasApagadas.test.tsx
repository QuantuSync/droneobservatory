// @vitest-environment jsdom
// Con el interruptor de las rutas apagado (configuracion/rutas_en_la_web.json): la capa de Ucrania
// no ofrece «Rutas», la metodología y la página de Ucrania no las describen y el recorrido de las
// incursiones sigue explicado. Con él encendido, estas pruebas se saltan.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CAPAS_INICIALES, SelectorDeCapas } from "../src/componentes/Controles.tsx";
import { textos } from "../src/i18n/index.ts";
import { RUTAS_EN_LA_WEB, seccionesDeMetodologia } from "../src/rutasEnLaWeb.ts";

afterEach(cleanup);

describe.skipIf(RUTAS_EN_LA_WEB)("rutas apagadas en la web", () => {
  it("la capa de Ucrania ofrece corredores y no rutas", () => {
    const t = textos("es");
    render(<SelectorDeCapas t={t} capas={{ ...CAPAS_INICIALES, ucrania: true }} onCapas={() => undefined} />);
    expect(screen.getAllByRole("button", { name: "Corredores" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Rutas" })).toBeNull();
  });

  it("la metodología no describe las rutas y sí el recorrido de las incursiones", () => {
    for (const idioma of ["es", "en"] as const) {
      const ids = seccionesDeMetodologia(textos(idioma)).map((s) => s.id);
      expect(ids).not.toContain("rutas");
      expect(ids).toContain("recorridos");
      expect(JSON.stringify(seccionesDeMetodologia(textos(idioma)))).not.toMatch(/NEPTUN|«Rutas»|«Routes»/);
    }
  });
});
