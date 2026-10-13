// @vitest-environment jsdom
// Un incidente que juntaba dos sucesos se separa (recogida/revisados.separar): cada ficha enlaza a
// la otra con «Suceso relacionado» / «Related incident» y la nota del motivo en su idioma.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { rutaDeFicha } from "../src/sitio.ts";
import { validarColeccion } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const NOTA = {
  es: "juntaba el cierre del aeropuerto de Vilna del 13 de septiembre y el derribo de la noche del 14 al 15",
  en: "it merged the Vilnius airport closure of 13 September and the shoot-down on the night of 14 to 15",
};

function cierre() {
  return incidente({
    id: "EODI-2026-00007",
    relacionados: [{ id: "EODI-2026-00179", separado_de: "EODI-2026-00072", nota: NOTA }],
  });
}

describe("suceso relacionado", () => {
  it("valida con el esquema", () => {
    expect(validarColeccion({ type: "FeatureCollection", features: [cierre()] }).ok).toBe(true);
  });

  it("la ficha enlaza a la otra en los dos idiomas", () => {
    for (const idioma of ["es", "en"] as const) {
      const t = textos(idioma);
      const { container, getByText } = render(
        <FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(cierre())} />,
      );
      expect(getByText(t.ficha.sucesoRelacionado)).toBeTruthy();
      const fila = container.querySelector('[data-suceso-relacionado="EODI-2026-00179"]');
      expect(fila?.textContent).toContain(NOTA[idioma]);
      const enlace = fila?.querySelector("a");
      expect(enlace?.getAttribute("href")).toBe(rutaDeFicha("EODI-2026-00179", idioma));
      cleanup();
    }
    expect(textos("es").ficha.sucesoRelacionado).toBe("Suceso relacionado");
    expect(textos("en").ficha.sucesoRelacionado).toBe("Related incident");
  });
});
