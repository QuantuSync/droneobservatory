import { describe, expect, it } from "vitest";

import { diaDeInstante, enPeriodo, fechaDeDia } from "../src/tiempo/dias.ts";
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

  it("un periodo incluye sus dos extremos", () => {
    const periodo = { desde: 10, hasta: 12 };
    expect([9, 10, 12, 13].map((d) => enPeriodo(d, periodo))).toEqual([false, true, true, false]);
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
