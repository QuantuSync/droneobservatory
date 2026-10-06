// @vitest-environment jsdom
// Mezcla de cada oleada, solo con lo que dicen los partes: Shahed y Geran contados aparte y drones
// a reacción, en la ficha del ataque, en «Noche a noche» y por mes en la página de Ucrania.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaAtaque } from "../src/componentes/FichaAtaque.tsx";
import { resumirUcrania } from "../src/datos/derivar.ts";
import { nochesDeGuerra } from "../src/datos/ucrania.ts";
import { validarResumenUcrania } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { ataque, publicacion } from "./ejemplos.ts";

const es = textos("es");
const en = textos("en");

afterEach(cleanup);

describe("mezcla de la oleada", () => {
  const conReactivos = ataque({
    lanzados: { total: { min: 173, max: 173 }, shahed_geran: { min: 120, max: 173 }, reactivos: { min: 50, max: 173 } },
  });

  it("la fila de cada ataque lleva los Shahed y los reactivos que da el parte, o -1", () => {
    const resumen = resumirUcrania(publicacion([conReactivos]));
    expect(validarResumenUcrania(resumen).ok).toBe(true);
    const fila = resumen.ataques[0];
    expect(fila?.[10]).toBe(120);
    expect(fila?.[11]).toBe(50);
    const sin = resumirUcrania(publicacion([ataque({ lanzados: { total: { min: 90, max: 90 } } })])).ataques[0];
    expect(sin?.[10]).toBe(-1);
    expect(sin?.[11]).toBe(-1);
  });

  it("«Noche a noche» suma lo que dicen los partes de la noche", () => {
    const [noche] = nochesDeGuerra(resumirUcrania(publicacion([conReactivos])));
    expect(noche?.shahed).toBe(120);
    expect(noche?.reactivos).toBe(50);
    expect(es.guerra.mezcla("120", "50")).toBe("Shahed y Geran: desde 120 · a reacción: desde 50 (según los partes)");
    expect(en.guerra.mezcla(null, "50")).toBe("jet-powered: from 50 (as the reports state)");
  });

  it("la ficha del ataque enseña los reactivos solo si el parte da la cifra", () => {
    render(<FichaAtaque t={es} idioma="es" ataque={conReactivos} />);
    expect(document.body.textContent).toContain("De ellos, a reacción");
    cleanup();
    render(<FichaAtaque t={es} idioma="es" ataque={ataque()} />);
    expect(document.body.textContent).not.toContain("De ellos, a reacción");
  });
});
