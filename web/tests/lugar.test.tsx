// @vitest-environment jsdom
// El lugar con su fuente y con los demás lugares que nombra la autoridad (lugar.fuente_punto y
// lugar.otros_lugares, opcionales): la validación los acepta con y sin punto y rechaza lo que no
// cumple; la ficha enseña «Lugar según» con el medio, la frase y el enlace de esa fuente, y
// «Otros lugares» con los nombres separados por comas, en español y en inglés.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente, detalleSinUbicacion } from "../src/datos/derivar.ts";
import type { PropiedadesSinUbicacion } from "../src/datos/tipos.ts";
import { validarColeccion, validarDetalleIncidente, validarSinUbicacion } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { fuente, incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");
const ENLACE = "https://www.presidency.ro/ro/media/comunicate-de-presa/galati";
const FRASE = "O dronă a căzut pe un bloc de locuințe din Galați.";
const OFICIAL = fuente({
  id: "oficial-ro-presidency-2026-09-20",
  enlace: ENLACE,
  medio: "Președintele României",
  idioma: "ro",
  fiabilidad: "A",
  frase_origen: FRASE,
});
const OTROS = [{ nombre: "Tulcea", punto: { lat: 45.18, lon: 28.8 } }, { nombre: "Isaccea" }];

function conLugar(lugar: Record<string, unknown> = {}) {
  const base = incidente();
  return incidente({
    fuentes: [...base.properties.fuentes, OFICIAL],
    lugar: { radio_km: 2, pais: "RO", localidad: "Galați", fuente_punto: OFICIAL.id, otros_lugares: OTROS, ...lugar },
  });
}

function sinUbicacion(lugar: Record<string, unknown> = {}): PropiedadesSinUbicacion {
  const { lugar: _lugar, ...resto } = conLugar().properties;
  void _lugar;
  return {
    ...resto,
    lugar: { pais: "RO", nivel: "region", region: "Galați", fuente_punto: OFICIAL.id, otros_lugares: OTROS, ...lugar },
  };
}

describe("lugar.fuente_punto y lugar.otros_lugares", () => {
  it("valida con punto, sin punto y en la ficha completa", () => {
    expect(validarColeccion({ type: "FeatureCollection", features: [conLugar()] }).ok).toBe(true);
    expect(validarSinUbicacion({ incidentes: [sinUbicacion()] }).ok).toBe(true);
    expect(validarDetalleIncidente(detalleIncidente(conLugar())).ok).toBe(true);
    expect(validarDetalleIncidente(detalleSinUbicacion(sinUbicacion())).ok).toBe(true);
    // Son opcionales: sin ellos, como antes.
    expect(validarColeccion({ type: "FeatureCollection", features: [incidente()] }).ok).toBe(true);
    expect(validarColeccion({ type: "FeatureCollection", features: [conLugar({ otros_lugares: [] })] }).ok).toBe(true);
  });

  it.each([
    ["fuente_punto vacía", { fuente_punto: "" }],
    ["fuente_punto que no es texto", { fuente_punto: 3 }],
    ["otros_lugares que no es lista", { otros_lugares: "Tulcea" }],
    ["otro lugar sin nombre", { otros_lugares: [{ punto: { lat: 45, lon: 28 } }] }],
    ["otro lugar con nombre vacío", { otros_lugares: [{ nombre: "" }] }],
    ["otro lugar con un campo desconocido", { otros_lugares: [{ nombre: "Tulcea", radio_km: 3 }] }],
    ["otro lugar con la latitud fuera de rango", { otros_lugares: [{ nombre: "Tulcea", punto: { lat: 95, lon: 28 } }] }],
    ["otro lugar con el punto incompleto", { otros_lugares: [{ nombre: "Tulcea", punto: { lat: 45 } }] }],
  ])("rechaza %s", (_caso, lugar) => {
    expect(validarColeccion({ type: "FeatureCollection", features: [conLugar(lugar)] }).ok).toBe(false);
    expect(validarSinUbicacion({ incidentes: [sinUbicacion(lugar)] }).ok).toBe(false);
  });

  it("la ficha dice según qué fuente va el punto y qué otros lugares nombra la autoridad", () => {
    for (const [t, idioma, segun, otros] of [
      [es, "es", "Lugar según", "Otros lugares"],
      [en, "en", "Location per", "Other places"],
    ] as const) {
      for (const detalle of [detalleIncidente(conLugar()), detalleSinUbicacion(sinUbicacion())]) {
        const { container, unmount } = render(<FichaIncidente t={t} idioma={idioma} incidente={detalle} />);
        const nombres = [...container.querySelectorAll("dt")].map((dt) => dt.textContent);
        expect(nombres).toContain(segun);
        expect(nombres).toContain(otros);
        const medio = container.querySelector("[data-lugar-segun]");
        expect(medio?.textContent).toBe("Președintele României");
        const fila = medio?.parentElement;
        const frase = fila?.querySelector("blockquote");
        expect(frase?.textContent).toBe(`«${FRASE}»`);
        expect(frase?.getAttribute("lang")).toBe("ro");
        expect(fila?.querySelector(`a[href="${ENLACE}"]`)?.textContent).toContain(t.ficha.verFuente);
        expect(container.querySelector("[data-otros-lugares]")?.textContent).toBe("Tulcea, Isaccea");
        unmount();
      }
    }
  });

  it("sin los campos, o con una fuente que no está entre las del incidente, no hay filas nuevas", () => {
    for (const detalle of [
      detalleIncidente(incidente()),
      detalleIncidente(conLugar({ fuente_punto: "no-existe", otros_lugares: [] })),
    ]) {
      const { container, unmount } = render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
      const nombres = [...container.querySelectorAll("dt")].map((dt) => dt.textContent);
      expect(nombres).not.toContain("Lugar según");
      expect(nombres).not.toContain("Otros lugares");
      unmount();
    }
  });
});

// Un lugar que no es el del dron (la casa alcanzada por un misil de la defensa) va entre los otros
// lugares con la frase de su fuente, y el punto anterior queda con su motivo (lugar.historial).
describe("lugar.otros_lugares[].fuente y lugar.historial", () => {
  const MISIL = fuente({
    id: "revisada-misil",
    enlace: "https://www.gov.pl/web/po-lublin/umorzenie",
    medio: "Prokuratura Okręgowa w Lublinie",
    idioma: "pl",
    fiabilidad: "A",
    frase_origen: "uderzyła w dach budynku mieszkalnego w miejscowości Wyryki Wola.",
  });
  const HISTORIAL = [
    {
      fecha: { valor: "2026-10-05T19:00Z", precision: "minuto" as const },
      anterior: { localidad: "Wyryki-Wola", punto: { lat: 51.5625, lon: 23.36389 }, radio_km: 2 },
      motivo: { es: "Un misil de la defensa, no un dron.", en: "A defence missile, not a drone." },
    },
  ];
  function corregido(lugar: Record<string, unknown> = {}) {
    const base = conLugar();
    return incidente({
      fuentes: [...base.properties.fuentes, MISIL],
      lugar: {
        ...base.properties.lugar,
        otros_lugares: [{ nombre: "Wyryki-Wola", punto: { lat: 51.5625, lon: 23.36389 }, fuente: MISIL.id }, ...OTROS],
        historial: HISTORIAL,
        ...lugar,
      },
    });
  }

  it("valida y rechaza lo que no cumple", () => {
    expect(validarColeccion({ type: "FeatureCollection", features: [corregido()] }).ok).toBe(true);
    for (const malo of [
      { otros_lugares: [{ nombre: "Wyryki-Wola", fuente: "" }] },
      { historial: [{ ...HISTORIAL[0], motivo: { es: "solo en español" } }] },
      { historial: [{ ...HISTORIAL[0], anterior: { localidad: "Wyryki-Wola" } }] },
    ]) {
      expect(validarColeccion({ type: "FeatureCollection", features: [corregido(malo)] }).ok).toBe(false);
    }
  });

  it("la ficha explica el lugar con su frase y dice el punto anterior con su motivo", () => {
    for (const [t, idioma, motivo] of [
      [es, "es", "Un misil de la defensa, no un dron."],
      [en, "en", "A defence missile, not a drone."],
    ] as const) {
      const { container, unmount } = render(
        <FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(corregido())} />,
      );
      const explicado = container.querySelector("[data-otro-lugar-explicado]");
      expect(explicado?.textContent).toContain("Wyryki-Wola");
      expect(explicado?.querySelector("blockquote")?.textContent).toBe(`«${MISIL.frase_origen}»`);
      expect(explicado?.querySelector(`a[href="${MISIL.enlace}"]`)).not.toBeNull();
      expect(container.querySelector("[data-otros-lugares]")?.textContent).toBe("Tulcea, Isaccea");
      const anterior = container.querySelector("[data-punto-anterior]")?.parentElement;
      expect(anterior?.textContent).toContain("Wyryki-Wola");
      expect(anterior?.textContent).toContain(motivo);
      unmount();
    }
  });
});
