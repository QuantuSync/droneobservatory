// @vitest-environment jsdom
// Una atribución retirada: la ficha enseña el estado nuevo, el historial con el motivo de la
// retirada y lo que la autoridad investiga, con la autoridad escrita en el idioma de la web.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { validarColeccion } from "../src/datos/validar.ts";
import { autoridadEscrita, medioEscrito } from "../src/i18n/autoridades.ts";
import { textos } from "../src/i18n/index.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");
const MOTIVO = {
  es: "Se retira la atribución: la autoridad examina una posible relación, no la afirma.",
  en: "Attribution withdrawn: the authority examines a possible link, it does not assert it.",
};
const CITA = "prüft die Bundesanwaltschaft einen möglichen Zusammenhang mit dem Drohnenvorfall am Flughafen Leipzig";

function retirado() {
  const base = incidente();
  const [fuente] = base.properties.fuentes;
  if (fuente === undefined) throw new Error("sin fuente");
  const declaracion = {
    ...fuente,
    id: "gdelt-0000000000000002-declaracion-1",
    medio: "Bundesanwaltschaft (declaración oficial citada en tagesspiegel.de)",
    frase_origen: CITA,
    idioma: "de",
  };
  return incidente({
    fuentes: [fuente, declaracion],
    estado: {
      actual: "confirmado",
      historial: [
        { estado: "notificado", fecha: { valor: "2026-09-18T10:15Z", precision: "aproximada" }, fuente_id: fuente.id },
        { estado: "confirmado", fecha: { valor: "2026-09-18T10:15Z", precision: "aproximada" }, fuente_id: declaracion.id },
        { estado: "atribuido", fecha: { valor: "2026-09-18T11:15Z", precision: "aproximada" }, fuente_id: declaracion.id },
        {
          estado: "confirmado",
          fecha: { valor: "2026-10-04T12:17Z", precision: "minuto" },
          fuente_id: declaracion.id,
          motivo: MOTIVO,
        },
      ],
    },
    investigacion: [
      {
        autoridad: "Bundesanwaltschaft",
        cita: CITA,
        fuente_id: declaracion.id,
        fecha: { valor: "2026-09-18T10:15Z", precision: "aproximada" },
      },
    ],
  });
}

describe("atribución retirada", () => {
  it("valida con el esquema: el motivo del paso y la investigación son públicos", () => {
    const resultado = validarColeccion({ type: "FeatureCollection", features: [retirado()] });
    expect(resultado.ok).toBe(true);
  });

  it("la ficha enseña el estado nuevo, el historial con el motivo y la investigación en curso", () => {
    for (const [t, idioma, autoridad] of [
      [es, "es", "la Fiscalía federal alemana (Bundesanwaltschaft)"],
      [en, "en", "the German Federal Prosecutor's Office (Bundesanwaltschaft)"],
    ] as const) {
      const { container } = render(<FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(retirado())} />);
      // Sin marcador de atribuido en ningún sitio salvo el paso del historial que lo fue.
      expect(container.querySelector("[data-estado-atribuido]")).toBeNull();
      expect(container.querySelectorAll("svg[data-atribuido]")).toHaveLength(1);
      // El último paso del historial dice por qué, en el idioma de la web.
      const motivos = [...container.querySelectorAll("[data-motivo-historial]")].map((m) => m.textContent);
      expect(motivos).toEqual([MOTIVO[idioma]]);
      // Lo que investiga la autoridad, con su nombre traducido y su cita literal.
      const investigacion = container.querySelector("[data-investigacion]");
      expect(investigacion?.textContent).toContain(t.ficha.investiga(autoridad));
      expect(investigacion?.textContent).toContain(`«${CITA}»`);
      cleanup();
    }
  });

  it("la autoridad, traducida con su nombre original entre paréntesis", () => {
    expect(autoridadEscrita("Bundesregierung", "es")).toBe("el Gobierno federal alemán (Bundesregierung)");
    expect(autoridadEscrita("Bundesregierung", "en")).toBe("the German Federal Government (Bundesregierung)");
    expect(autoridadEscrita("Pre\u0219edintele Maia Sandu", "es")).toBe("la presidenta de Moldavia, Maia Sandu");
    expect(autoridadEscrita("Prefectul I\u0061\u0219i", "es")).toBe("el prefecto de I\u0061\u0219i");
    // Una autoridad que no está en la tabla, tal cual.
    expect(autoridadEscrita("Københavns Politi", "es")).toBe("Københavns Politi");
    expect(medioEscrito("Bundesregierung (declaración oficial citada en come-on.de)", "en", en.ficha.declaracionCitada)).toBe(
      "Statement by the German Federal Government (Bundesregierung), quoted in come-on.de",
    );
    expect(medioEscrito("dr.dk", "es", es.ficha.declaracionCitada)).toBe("dr.dk");
  });
});
