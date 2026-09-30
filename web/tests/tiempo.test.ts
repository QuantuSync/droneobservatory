import { describe, expect, it } from "vitest";

import {
  diaDeInstante,
  enPeriodo,
  fechaDeDia,
  histograma,
  inicioDeTramo,
  inicioDeTramoSiguiente,
} from "../src/tiempo/dias.ts";
import { diaDeX, marcasDeEje, xDeDia } from "../src/tiempo/escala.ts";
import {
  HORAS_CON_RETRASO,
  HORAS_DESACTUALIZADO,
  frescura,
} from "../src/tiempo/frescura.ts";

const dia = diaDeInstante;

describe("días UTC", () => {
  it("convierte instantes y fechas del esquema en días", () => {
    expect(dia("1970-01-01T00:00Z")).toBe(0);
    expect(dia("2026-09-30T23:59Z")).toBe(dia("2026-09-30"));
    expect(fechaDeDia(dia("2025-10-03T01:00Z")).toISOString()).toBe("2025-10-03T00:00:00.000Z");
  });

  it("rechaza una fecha ilegible", () => {
    expect(() => dia("ayer")).toThrow();
  });

  it("la semana empieza en lunes", () => {
    // El 30 de septiembre de 2026 es miércoles.
    expect(inicioDeTramo(dia("2026-09-30"), "semana")).toBe(dia("2026-09-28"));
    expect(inicioDeTramo(dia("2026-09-28"), "semana")).toBe(dia("2026-09-28"));
    expect(inicioDeTramo(dia("2026-09-27"), "semana")).toBe(dia("2026-09-21"));
    expect(inicioDeTramoSiguiente(dia("2026-09-30"), "semana")).toBe(dia("2026-10-05"));
  });

  it("el mes respeta su longitud, también en bisiesto", () => {
    expect(inicioDeTramo(dia("2024-02-29"), "mes")).toBe(dia("2024-02-01"));
    expect(inicioDeTramoSiguiente(dia("2024-02-10"), "mes")).toBe(dia("2024-03-01"));
    expect(inicioDeTramoSiguiente(dia("2025-12-31"), "mes")).toBe(dia("2026-01-01"));
  });

  it("el histograma incluye los tramos vacíos y deja fuera los días ajenos al dominio", () => {
    const valores = new Map([
      [dia("2025-01-01"), 2],
      [dia("2025-01-02"), 1],
      [dia("2025-01-20"), 4],
      [dia("2025-03-01"), 9],
    ]);
    const tramos = histograma(valores, dia("2025-01-01"), dia("2025-02-28"), "mes");
    expect(tramos.map((t) => t.valor)).toEqual([7, 0]);
    expect(tramos[0]).toMatchObject({ inicio: dia("2025-01-01"), fin: dia("2025-02-01") });
    const porDia = histograma(valores, dia("2025-01-01"), dia("2025-01-03"), "dia");
    expect(porDia.map((t) => t.valor)).toEqual([2, 1, 0]);
  });

  it("un periodo incluye sus dos extremos", () => {
    const periodo = { desde: 10, hasta: 12 };
    expect([9, 10, 12, 13].map((d) => enPeriodo(d, periodo))).toEqual([false, true, true, false]);
  });
});

describe("escala de la línea de tiempo", () => {
  const dominio = { desde: 100, hasta: 199 };

  it("va y vuelve entre días y píxeles", () => {
    expect(xDeDia(100, 1000, dominio)).toBe(0);
    expect(xDeDia(200, 1000, dominio)).toBe(1000);
    expect(diaDeX(0, 1000, dominio)).toBe(100);
    expect(diaDeX(15, 1000, dominio)).toBe(101);
  });

  it("acota al dominio lo que cae fuera", () => {
    expect(diaDeX(-50, 1000, dominio)).toBe(100);
    expect(diaDeX(5000, 1000, dominio)).toBe(199);
    expect(diaDeX(10, 0, dominio)).toBe(100);
  });

  it("pone marcas en inicios de mes sin que se pisen", () => {
    const dosAnios = { desde: dia("2024-09-26"), hasta: dia("2026-09-30") };
    const marcas = marcasDeEje(dosAnios, 1400);
    expect(marcas.length).toBeGreaterThan(3);
    for (const marca of marcas) expect(fechaDeDia(marca.dia).getUTCDate()).toBe(1);
    const separaciones = marcas
      .slice(1)
      .map((marca, i) => xDeDia(marca.dia, 1400, dosAnios) - xDeDia(marcas[i]!.dia, 1400, dosAnios));
    expect(Math.min(...separaciones)).toBeGreaterThanOrEqual(60);
    expect(marcasDeEje(dosAnios, 0)).toEqual([]);
  });

  it("con un dominio largo etiqueta por años", () => {
    const largo = { desde: dia("2022-10-01"), hasta: dia("2026-09-30") };
    expect(marcasDeEje(largo, 320).every((marca) => /^\d{4}$/.test(marca.etiqueta))).toBe(true);
  });
});

describe("antigüedad de los datos", () => {
  const actualizado = "2026-09-30T12:00Z";
  const dentroDe = (horas: number) => new Date(Date.UTC(2026, 8, 30, 12, 0) + horas * 3_600_000);

  it("está al día con menos de dos horas", () => {
    expect(frescura(actualizado, dentroDe(0))).toBe("al_dia");
    expect(frescura(actualizado, dentroDe(HORAS_CON_RETRASO - 0.01))).toBe("al_dia");
  });

  it("va con retraso entre dos y seis horas", () => {
    expect(frescura(actualizado, dentroDe(HORAS_CON_RETRASO))).toBe("con_retraso");
    expect(frescura(actualizado, dentroDe(HORAS_DESACTUALIZADO - 0.01))).toBe("con_retraso");
  });

  it("está desactualizado desde las seis horas", () => {
    expect(frescura(actualizado, dentroDe(HORAS_DESACTUALIZADO))).toBe("desactualizado");
    expect(frescura(actualizado, dentroDe(500))).toBe("desactualizado");
  });

  it("una fecha ilegible nunca se da por reciente", () => {
    expect(frescura("no es una fecha", dentroDe(0))).toBe("desactualizado");
  });
});
