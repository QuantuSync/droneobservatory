// @vitest-environment jsdom
// Los nombres de las autoridades, siempre en el idioma de la página: los de la tabla revisada
// (configuracion/autoridades.json); los que no están, con la traducción que traen los datos
// publicados (`autoridades`, exportacion/citas.py), que se apunta al validarlos; y si aún no hay
// traducción, «una autoridad», nunca el nombre en otro idioma. El 14 de octubre de 2026 la ficha
// EODI-2026-00532 decía en español «Declaración de Defense Ministry of Romania».
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { validarColeccion } from "../src/datos/validar.ts";
import { autoridadEscrita, medioEnFrase, medioEscrito } from "../src/i18n/autoridades.ts";
import { textos } from "../src/i18n/index.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const TRADUCIDA = "Agentia de Test pentru Drone";
const SIN_TRADUCIR = "Ufficio Sconosciuto di Prova";

function conDeclaraciones() {
  const base = incidente();
  const [fuente] = base.properties.fuentes;
  if (fuente === undefined) throw new Error("sin fuente");
  const declaracion = (n: number, autoridad: string, idioma: string) => ({
    ...fuente,
    id: `gdelt-0000000000000001-declaracion-${n}`,
    medio: `${autoridad} (declaración oficial citada en news.az)`,
    idioma,
    frase_origen: "Three drones were detected near the border.",
  });
  return incidente({
    fuentes: [
      fuente,
      declaracion(1, "Defense Ministry of Romania", "en"),
      declaracion(2, TRADUCIDA, "ro"),
      declaracion(3, SIN_TRADUCIR, "it"),
    ],
    autoridades: {
      [TRADUCIDA]: { es: "la Agencia de Pruebas de Drones de Rumanía", en: "the Romanian Drone Test Agency" },
    },
  });
}

function validado() {
  const resultado = validarColeccion({ type: "FeatureCollection", features: [conDeclaraciones()] });
  if (!resultado.ok) throw new Error(resultado.errores.join("; "));
  const [feature] = resultado.datos.features;
  if (feature === undefined) throw new Error("sin incidente");
  return detalleIncidente(feature);
}

describe("autoridades en el idioma de la página", () => {
  it("la de la tabla, la traducida en los datos y la que aún no tiene traducción", () => {
    validado();
    const es = textos("es");
    const en = textos("en");
    expect(medioEscrito("Defense Ministry of Romania (declaración oficial citada en news.az)", "es", es.ficha.declaracionCitada)).toBe(
      "Declaración del Ministerio de Defensa Nacional de Rumanía, citada en news.az",
    );
    expect(autoridadEscrita(TRADUCIDA, "es")).toBe("la Agencia de Pruebas de Drones de Rumanía");
    expect(autoridadEscrita(TRADUCIDA, "en")).toBe("the Romanian Drone Test Agency");
    expect(medioEscrito(`${SIN_TRADUCIR} (declaración oficial citada en news.az)`, "en", en.ficha.declaracionCitada)).toBe(
      "Statement by an authority, quoted in news.az",
    );
    // Un medio con dominio sigue siendo su nombre.
    expect(medioEscrito("news.az", "es", es.ficha.declaracionCitada)).toBe("news.az");
    // Dentro de una frase («según…», «Cifras de…»), también traducida y sin la mayúscula.
    expect(medioEnFrase("Ministerul Apărării", "es", es.ficha.declaracionCitada)).toBe(
      "el Ministerio de Defensa Nacional de Rumanía",
    );
    expect(medioEnFrase("Ministerul Apărării (declaración oficial citada en moldpres.md)", "en", en.ficha.declaracionCitada)).toBe(
      "statement by the Romanian Ministry of National Defence, quoted in moldpres.md",
    );
    expect(medioEnFrase("news.az", "es", es.ficha.declaracionCitada)).toBe("news.az");
    expect(es.region.fuenteCifras(medioEnFrase("Ministerul Apărării", "es", es.ficha.declaracionCitada))).toBe(
      "Cifras del Ministerio de Defensa Nacional de Rumanía",
    );
  });

  for (const idioma of ["es", "en"] as const) {
    it(`la ficha no enseña ningún nombre de autoridad en otro idioma (${idioma})`, () => {
      const detalle = validado();
      const { container } = render(<FichaIncidente t={textos(idioma)} idioma={idioma} incidente={detalle} />);
      const texto = container.textContent ?? "";
      expect(texto).not.toContain("Defense Ministry of Romania");
      expect(texto).not.toContain(TRADUCIDA);
      expect(texto).not.toContain(SIN_TRADUCIR);
      expect(texto).toContain(idioma === "es" ? "la Agencia de Pruebas de Drones de Rumanía" : "the Romanian Drone Test Agency");
      expect(texto).toContain(idioma === "es" ? "Declaración de una autoridad" : "Statement by an authority");
    });
  }
});
