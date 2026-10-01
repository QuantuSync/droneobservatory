// @vitest-environment jsdom
// Cierre medido con tráfico aéreo real (adsb.lol): datos y ficha del incidente.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { validarColeccion, validarEstadoSistema } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { coleccion, estadoSistema, incidente, traficoAereo } from "./ejemplos.ts";

const es = textos("es");
const en = textos("en");

afterEach(cleanup);

const DECLARADO = {
  cierre: { valor: "si" as const, minutos: { min: 240, max: 240 } },
  vuelos_desviados: { min: 35, max: 35 },
};

describe("datos", () => {
  it("valida el cierre medido", () => {
    expect(validarColeccion(coleccion([incidente({ trafico_aereo: traficoAereo() })])).ok).toBe(
      true,
    );
  });

  it("rechaza lo que no es un cierre medido o trae campos internos", () => {
    const base = traficoAereo();
    for (const malo of [
      { ...base, cierre: { ...base.cierre, resultado: "sin_interrupcion" } },
      { ...base, cierre: { ...base.cierre, llegadas_perdidas: 50 } },
      { ...base, cierre: { ...base.cierre, cobertura: { nivel: "alta" } } },
      { ...base, respuesta_militar: { resultado: "vistas" } },
      { ...base, interferencia_gnss: { resultado: "medida" } },
      { ...base, datos: ["https://example.org/otra"] },
    ]) {
      const coleccionMala = coleccion([incidente({ trafico_aereo: malo as never })]);
      expect(validarColeccion(coleccionMala).ok).toBe(false);
    }
  });

  it("estado.json trae el tráfico aéreo y las condiciones como fuentes", () => {
    expect(validarEstadoSistema(estadoSistema()).ok).toBe(true);
    const ids = estadoSistema().fuentes.map((f) => f.id);
    expect(ids.slice(-2)).toEqual(["trafico_aereo", "condiciones"]);
  });
});

describe("ficha", () => {
  it("muestra el cierre medido con sus horas, duración, desvíos y esperas", () => {
    const detalle = detalleIncidente(
      incidente({ trafico_aereo: traficoAereo(), consecuencias: DECLARADO }),
    );
    render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    const fila = screen.getByText("Cierre medido con tráfico aéreo real").closest("dd");
    expect(fila).not.toBeNull();
    const texto = fila?.textContent ?? "";
    expect(texto).toContain("22/09/2025 · 18:26 UTC – 22/09/2025 · 22:38 UTC · 252 min");
    expect(texto).toContain("31 vuelos desviados · 6 en espera");
    expect(texto).toContain("Según las fuentes: 240 min · 35 vuelos desviados");
    const enlace = within(fila as HTMLElement).getByRole("link", { name: /Datos de adsb.lol/ });
    expect(enlace.getAttribute("href")).toContain("github.com/adsblol/globe_history_2025");
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("si la medida no difiere, no repite lo declarado", () => {
    const detalle = detalleIncidente(
      incidente({
        trafico_aereo: traficoAereo({ difiere_de_declarado: false }),
        consecuencias: DECLARADO,
      }),
    );
    render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    expect(document.querySelector("[data-trafico-declarado]")).toBeNull();
  });

  it("en inglés", () => {
    const detalle = detalleIncidente(incidente({ trafico_aereo: traficoAereo() }));
    render(<FichaIncidente t={en} idioma="en" incidente={detalle} />);
    expect(screen.getByText("Closure measured with real air traffic")).toBeTruthy();
    expect(document.body.textContent).toContain("31 diverted flights · 6 holding");
  });

  it("sin medición no hay línea", () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(incidente())} />);
    expect(screen.queryByText("Cierre medido con tráfico aéreo real")).toBeNull();
  });
});
