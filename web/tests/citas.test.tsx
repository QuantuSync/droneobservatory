// @vitest-environment jsdom
// Citas en el idioma de la página (componentes/Cita.tsx, exportacion/citas.py): la traducción
// guardada con el original plegado debajo («Ver original» / «Show original»); sin traducción, o
// ya en el idioma de la página, el original tal cual. Y lo publicado con traducciones valida.

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Cita } from "../src/componentes/Cita.tsx";
import { traduccionParaMostrar } from "../src/datos/citas.ts";
import { textos } from "../src/i18n/index.ts";

const ORIGINAL = "allerdings konnte eine Drohne nicht gefunden werden.";
const TRADUCCION = { es: "sin embargo, no se pudo encontrar ningún dron.", en: "however, no drone could be found." };

afterEach(cleanup);

describe("Cita", () => {
  it("enseña la traducción y el original plegado", () => {
    const { container } = render(
      <Cita t={textos("es")} idioma="es" texto={ORIGINAL} idiomaOriginal="de" traduccion={TRADUCCION} />,
    );
    const traducida = container.querySelector("blockquote");
    expect(traducida?.textContent).toBe(`«${TRADUCCION.es}»`);
    expect(traducida?.getAttribute("lang")).toBe("es");
    const desplegable = container.querySelector("details");
    expect(desplegable?.querySelector("summary")?.textContent).toBe("Ver original");
    const original = desplegable?.querySelector("[data-cita-original]");
    expect(original?.textContent).toBe(`«${ORIGINAL}»`);
    expect(original?.getAttribute("lang")).toBe("de");
  });

  it("en inglés, «Show original»", () => {
    const { container } = render(
      <Cita t={textos("en")} idioma="en" texto={ORIGINAL} idiomaOriginal="de" traduccion={TRADUCCION} />,
    );
    expect(container.querySelector("blockquote")?.textContent).toBe(`«${TRADUCCION.en}»`);
    expect(container.querySelector("summary")?.textContent).toBe("Show original");
  });

  it("sin traducción o ya en el idioma de la página, el original", () => {
    const sin = render(<Cita t={textos("es")} idioma="es" texto={ORIGINAL} idiomaOriginal="de" />);
    expect(sin.container.querySelector("details")).toBeNull();
    expect(sin.container.querySelector("blockquote")?.textContent).toBe(`«${ORIGINAL}»`);
    cleanup();
    const mismo = render(
      <Cita t={textos("es")} idioma="es" texto="ningún dron" idiomaOriginal="es" traduccion={{ es: "ningún dron", en: "no drone" }} />,
    );
    expect(mismo.container.querySelector("details")).toBeNull();
  });

  it("una traducción vacía o igual al original no se enseña", () => {
    expect(traduccionParaMostrar("es", "x", "de", { es: " ", en: "y" })).toBeNull();
    expect(traduccionParaMostrar("en", "x", "de", { es: "z", en: "x" })).toBeNull();
    expect(traduccionParaMostrar("en", "x", "de", { es: "z", en: "y" })).toBe("y");
  });
});
