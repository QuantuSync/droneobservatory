// Los nombres que se escriben igual en más de un país llegan en los datos publicados con su país
// (proceso/autoridades.con_pais): «Ministerul Apărării (MD)». Hasta el 2 de noviembre de 2026 la
// ficha EODI-2026-00728 (Viișoara, Moldavia) decía «Lo declaró el Ministerio de Defensa Nacional
// de Rumanía».
import { describe, expect, it } from "vitest";

import { autoridadEscrita, medioEnFrase, medioEscrito } from "../src/i18n/autoridades.ts";

const citada = (a: string, m: string) => `Declaración de ${a}, citada en ${m}`;

describe("autoridades de varios países", () => {
  it("00728: el Ministerio de Defensa de Moldavia, con el nombre original sin el país", () => {
    const medio = "Ministerul Apărării (MD) (declaración oficial citada en timpul.md)";
    expect(medioEscrito(medio, "es", citada)).toBe(
      "Declaración de el Ministerio de Defensa de Moldavia (Ministerul Apărării), citada en timpul.md",
    );
    expect(medioEnFrase(medio, "en", (a) => a)).toBe("the Moldovan Ministry of Defence (Ministerul Apărării)");
    expect(autoridadEscrita("Ministerul Apărării (MD)", "es")).not.toContain("Rumanía");
  });

  it("la ficha rumana sigue rumana", () => {
    expect(autoridadEscrita("Ministerul Apărării Naționale", "es")).toBe(
      "el Ministerio de Defensa Nacional de Rumanía (Ministerul Apărării Naționale)",
    );
    expect(autoridadEscrita("Ministerul Apărării (RO)", "en")).toBe(
      "the Romanian Ministry of National Defence (Ministerul Apărării)",
    );
  });

  it("sin país, el nombre suelto no nombra ninguno", () => {
    expect(autoridadEscrita("Ministerul Apărării", "es")).toBe("el Ministerio de Defensa (Ministerul Apărării)");
    expect(autoridadEscrita("Forsvaret (DK)", "es")).toBe("las Fuerzas Armadas de Dinamarca (Forsvaret)");
  });
});
