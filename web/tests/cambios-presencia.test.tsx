// @vitest-environment jsdom
// El historial público de la presencia del dron (esquema 1.21.0, presencia_cambios): cada cambio
// desde que la ficha salió en la web, con su fecha y hora, de qué valor a qué valor, el motivo y la
// frase de la fuente con su enlace, en el «Historial de estados» de la ficha y en su página de
// texto, en español y en inglés. Caso real: EODI-2026-01008 (Ludza, Letonia), que pasó de «no
// confirmada» a «confirmada» a las 07:32 UTC del 27/11/2026 con la nota ampliada del ejército letón.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { cambiosDePresencia, historialCompleto } from "../src/datos/presencia.ts";
import type { CambioPresencia, FeatureIncidente } from "../src/datos/tipos.ts";
import { CAMPOS_INCIDENTE, tolerarCamposNuevos, validarColeccion } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { coleccion, fuente, incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");

const NBS = fuente({
  id: "gdelt-12f6f4a3c5a862e4-declaracion-1",
  enlace: "https://ogrenet.lv/drosiba/latvijas-gaisa-telpa-sonakt-ielidoja-drons-tika-aktivizeti-nato-iznicinataji-22523",
  medio: "Nacionālie bruņotie spēki (NBS) (declaración oficial citada en ogrenet.lv)",
  fecha: { valor: "2026-11-27T06:00Z", precision: "aproximada" },
  idioma: "lv",
});
const FRASE = "NBS informē, ka konstatēja bezpilota lidaparāta pārvietošanos tiešā Latvijas valsts robežas tuvumā.";
const LUDZA: CambioPresencia = {
  fecha: { valor: "2026-11-27T07:32Z", precision: "minuto" },
  de: "no_confirmada",
  a: "confirmada",
  motivo: { es: "una autoridad afirma que hubo un dron", en: "an authority states there was a drone" },
  frase: FRASE,
  fuente_id: NBS.id,
  medio: NBS.medio,
  enlace: NBS.enlace,
};

function ludza(cambios: CambioPresencia[] | null = [LUDZA]): FeatureIncidente {
  return incidente({
    id: "EODI-2026-01008",
    presencia_dron: "confirmada",
    fuentes: [fuente(), NBS],
    ...(cambios === null ? {} : { presencia_cambios: cambios }),
  });
}

describe("historial de la presencia del dron", () => {
  it("el cambio sale en el historial, con la flecha, la hora, el motivo y la frase con su enlace", () => {
    for (const [t, idioma, rotulo, motivo] of [
      [es, "es", "Dron no confirmado → Dron confirmado", "Una autoridad afirma que hubo un dron"],
      [en, "en", "Drone not confirmed → Drone confirmed", "An authority states there was a drone"],
    ] as const) {
      const { container, unmount } = render(<FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(ludza())} />);
      const paso = container.querySelector("[data-cambio-presencia=confirmada]");
      expect(paso, idioma).not.toBeNull();
      expect(paso?.textContent).toContain(rotulo);
      expect(paso?.textContent).toContain("07:32");
      expect(paso?.querySelector("[data-motivo-historial]")?.textContent).toBe(motivo);
      expect(paso?.querySelector("[data-frase-cambio] q")?.textContent).toBe(FRASE);
      expect(paso?.querySelector("[data-frase-cambio] a")?.getAttribute("href")).toBe(NBS.enlace);
      unmount();
    }
  });

  it("sin cambios guardados no se enseña ninguno", () => {
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(ludza(null))} />);
    expect(container.querySelector("[data-cambio-presencia]")).toBeNull();
    expect(historialCompleto(es, "es", detalleIncidente(ludza(null))).some((p) => p.clase === "cambio")).toBe(false);
  });

  it("una bajada sin frase se enseña sin frase; el cambio que ya cuenta una rectificación no se repite", () => {
    const bajada: CambioPresencia = {
      fecha: { valor: "2026-11-21T21:32Z", precision: "minuto" },
      de: "confirmada",
      a: "no_confirmada",
      motivo: { es: "ninguna autoridad afirma que hubiera un dron", en: "no authority states there was a drone" },
    };
    const rectificada: CambioPresencia = { ...bajada, a: "no_acreditada", fecha: { valor: "2026-11-22T10:00Z", precision: "minuto" } };
    const detalle = detalleIncidente(
      incidente({
        presencia_dron: "no_acreditada",
        presencia_cambios: [rectificada, bajada],
        presencia_historial: [
          { valor: "confirmada", fecha: { valor: "2026-11-01T00:00Z", precision: "dia" }, fuente_id: "gdelt-0000000000000001" },
          { valor: "no_acreditada", fecha: { valor: "2026-11-22T00:00Z", precision: "dia" }, fuente_id: "gdelt-0000000000000001" },
        ],
      }),
    );
    expect(cambiosDePresencia(detalle).map((c) => c.a)).toEqual(["no_confirmada"]);
    const { container } = render(<FichaIncidente t={en} idioma="en" incidente={detalle} />);
    const paso = container.querySelector("[data-cambio-presencia=no_confirmada]");
    expect(paso?.textContent).toContain("Drone confirmed → Drone not confirmed");
    expect(paso?.querySelector("[data-frase-cambio]")).toBeNull();
  });

  it("la rectificación va donde la web la aplicó: el historial acaba en ella, no en «→ Dron confirmado»", () => {
    // EODI-2025-00154 (Copenhague): la policía la da por no acreditada el 25/06/2026; la ficha
    // pasó a «confirmada» el 1/10 y la web aplicó la rectificación el 16/10.
    const subida: CambioPresencia = {
      fecha: { valor: "2026-10-01T10:47Z", precision: "minuto" },
      de: "no_confirmada",
      a: "confirmada",
      motivo: { es: "cambio anterior al registro de sus motivos: el motivo no se guardó", en: "change made before reasons were recorded: the reason was not saved" },
    };
    const aplicada: CambioPresencia = {
      fecha: { valor: "2026-10-16T00:31Z", precision: "minuto" },
      de: "confirmada",
      a: "no_acreditada",
      motivo: { es: "rectificación oficial de la autoridad", en: "official correction by the authority" },
    };
    const detalle = detalleIncidente(
      incidente({
        id: "EODI-2025-00154",
        presencia_dron: "no_acreditada",
        presencia_cambios: [subida, aplicada],
        presencia_historial: [
          { valor: "confirmada", fecha: { valor: "2025-09-22T20:15Z", precision: "minuto" }, fuente_id: "gdelt-0000000000000001" },
          { valor: "no_acreditada", fecha: { valor: "2026-06-25T00:00Z", precision: "dia" }, fuente_id: "gdelt-0000000000000001" },
        ],
      }),
    );
    const pasos = historialCompleto(es, "es", detalle);
    const ultimo = pasos.at(-1);
    expect(ultimo?.clase).toBe("presencia");
    expect(ultimo?.fecha).toBe("2026-06-25T00:00Z");
    expect(pasos.filter((p) => p.clase === "cambio").map((p) => (p.clase === "cambio" ? p.paso.a : null))).toEqual(["confirmada"]);
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    const items = [...container.querySelectorAll("ol > li")];
    expect(items.at(-1)?.getAttribute("data-historial-presencia")).toBe("no_acreditado");
  });

  it("valida, y si viene roto la ficha se pinta igual sin él", () => {
    expect(CAMPOS_INCIDENTE).toContain("presencia_cambios");
    expect(validarColeccion(coleccion([ludza()])).ok).toBe(true);
    const roto = ludza([{ ...LUDZA, a: "quizas" as CambioPresencia["a"] }]);
    expect(validarColeccion(coleccion([roto])).ok).toBe(false);
    tolerarCamposNuevos(true);
    try {
      const resultado = validarColeccion(coleccion([ludza([{ ...LUDZA, a: "quizas" as CambioPresencia["a"] }])]));
      expect(resultado.ok).toBe(true);
      if (resultado.ok) expect(resultado.datos.features[0]?.properties.presencia_cambios).toBeUndefined();
    } finally {
      tolerarCamposNuevos(false);
    }
  });
});
