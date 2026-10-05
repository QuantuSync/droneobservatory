// @vitest-environment jsdom
// Un incidente atribuido por la declaración de una autoridad leída en su página oficial: la ficha
// dice a quién se atribuye (el país por su código), qué autoridad lo atribuye (traducida, con el
// original entre paréntesis), su cita literal con el enlace y la investigación en curso.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { validarColeccion } from "../src/datos/validar.ts";
import { autoridadEscrita } from "../src/i18n/autoridades.ts";
import { textos } from "../src/i18n/index.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");
const ENLACE = "https://www.bundesregierung.de/breg-de/service/fragen-und-anworten/reaktion-angriff-leipzig-2451522";
const CITA =
  "Die Bundesregierung weist die Verantwortung für den versuchten Anschlag auf den Flughafen Leipzig/Halle vom 4. August 2026 eindeutig Russland zu.";
const ERMITTLUNGEN =
  "Unabhängig davon sind die strafrechtlichen Ermittlungen und juristischen Verfahren in der Angelegenheit noch nicht abgeschlossen und laufen weiter.";

function atribuido() {
  const base = incidente();
  const [fuente] = base.properties.fuentes;
  if (fuente === undefined) throw new Error("sin fuente");
  const oficial = {
    ...fuente,
    id: "oficial-de-bundesregierung-2026-09-04-autoria",
    enlace: ENLACE,
    medio: "Bundesregierung",
    fecha: { valor: "2026-09-04T00:00Z", precision: "dia" as const },
    idioma: "de",
    fiabilidad: "A" as const,
    frase_origen: CITA,
  };
  const investigacion = { ...oficial, id: "oficial-de-bundesregierung-2026-09-04-ermittlungen", frase_origen: ERMITTLUNGEN };
  return incidente({
    fuentes: [fuente, oficial, investigacion],
    estado: {
      actual: "atribuido",
      historial: [
        { estado: "notificado", fecha: { valor: "2026-08-05T05:30Z", precision: "minuto" }, fuente_id: fuente.id },
        { estado: "confirmado", fecha: { valor: "2026-08-05T05:30Z", precision: "minuto" }, fuente_id: fuente.id },
        { estado: "atribuido", fecha: oficial.fecha, fuente_id: oficial.id },
      ],
    },
    atribucion: { actor: "Russland", autoridad: "Bundesregierung", fecha: oficial.fecha, tipo: "estado", pais: "RU" },
    investigacion: [{ autoridad: "Bundesregierung", cita: ERMITTLUNGEN, fuente_id: investigacion.id, fecha: oficial.fecha }],
  });
}

describe("atribución por una declaración oficial", () => {
  it("valida con el esquema", () => {
    expect(validarColeccion({ type: "FeatureCollection", features: [atribuido()] }).ok).toBe(true);
  });

  it("la ficha dice a quién, según quién, la cita literal con su enlace y lo que se investiga", () => {
    for (const [t, idioma, pais, autoridad] of [
      [es, "es", "Rusia", "el Gobierno federal alemán (Bundesregierung)"],
      [en, "en", "Russia", "the German Federal Government (Bundesregierung)"],
    ] as const) {
      const { container } = render(<FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(atribuido())} />);
      expect(container.querySelector("[data-estado-atribuido]")?.textContent).toContain(pais);
      expect(container.textContent).toContain(t.ficha.atribuidoA(pais, autoridad));
      expect(container.textContent).not.toContain("Russland,");
      const cita = container.querySelector("[data-cita-atribucion]");
      expect(cita?.textContent).toBe(`«${CITA}»`);
      expect(cita?.getAttribute("lang")).toBe("de");
      const enlace = cita?.parentElement?.querySelector(`a[href="${ENLACE}"]`);
      expect(enlace?.textContent).toContain(t.ficha.verFuente);
      expect(container.querySelector("[data-investigacion]")?.textContent).toContain(ERMITTLUNGEN);
    }
  });

  it("las autoridades de las atribuciones se escriben traducidas con el original", () => {
    expect(autoridadEscrita("Försvarsmakten", "es")).toBe("las Fuerzas Armadas de Suecia (Försvarsmakten)");
    expect(autoridadEscrita("Ministerstwo Obrony Narodowej", "es")).toBe(
      "el Ministerio de Defensa Nacional de Polonia (Ministerstwo Obrony Narodowej)",
    );
    expect(autoridadEscrita("Kancelaria Prezesa Rady Ministrów", "en")).toBe(
      "the Chancellery of the Prime Minister of Poland (Kancelaria Prezesa Rady Ministrów)",
    );
    expect(autoridadEscrita("Președintele României", "es")).toBe(
      "el presidente de Rumanía (Președintele României)",
    );
    expect(autoridadEscrita("Generalbundesanwalt", "en")).toBe(
      "the German Federal Prosecutor General (Generalbundesanwalt)",
    );
  });
});
