// El refresco de una pestaña abierta (src/tiempo/refresco.ts): nada con la pestaña oculta, una
// petición al volver y, a la vista, una cada intervalo.

import { describe, expect, it } from "vitest";

import { MS_MINIMO_AL_VOLVER, refrescarAlaVista } from "../src/tiempo/refresco.ts";
import type { Documento, Reloj } from "../src/tiempo/refresco.ts";

function simulacion(visible: boolean) {
  let ahora = 0;
  const intervalos: { oyente: () => void; ms: number; siguiente: number }[] = [];
  const oyentes = new Set<() => void>();
  const documento: Documento = {
    visibilityState: visible ? "visible" : "hidden",
    addEventListener: (_tipo, oyente) => oyentes.add(oyente),
    removeEventListener: (_tipo, oyente) => oyentes.delete(oyente),
  };
  const reloj: Reloj = {
    ahora: () => ahora,
    cada: (oyente, ms) => intervalos.push({ oyente, ms, siguiente: ms }),
    parar: () => intervalos.splice(0),
  };
  return {
    documento,
    reloj,
    oyentes,
    avanzar(ms: number) {
      const fin = ahora + ms;
      for (;;) {
        const proximo = intervalos.find((i) => i.siguiente <= fin);
        if (proximo === undefined) break;
        ahora = proximo.siguiente;
        proximo.siguiente += proximo.ms;
        proximo.oyente();
      }
      ahora = fin;
    },
    cambiar(estado: DocumentVisibilityState) {
      documento.visibilityState = estado;
      for (const oyente of oyentes) oyente();
    },
  };
}

const DIEZ_MINUTOS = 10 * 60 * 1000;

describe("refresco a la vista", () => {
  it("a la vista: una al abrir y una cada diez minutos (7 en una hora)", () => {
    const s = simulacion(true);
    let pedidas = 0;
    refrescarAlaVista(() => (pedidas += 1), DIEZ_MINUTOS, s.documento, s.reloj);
    s.avanzar(60 * 60 * 1000);
    expect(pedidas).toBe(7);
  });

  it("oculta no pide nada; al volver pide una vez", () => {
    const s = simulacion(false);
    let pedidas = 0;
    refrescarAlaVista(() => (pedidas += 1), DIEZ_MINUTOS, s.documento, s.reloj);
    s.avanzar(3 * 60 * 60 * 1000);
    expect(pedidas).toBe(0);
    s.cambiar("visible");
    expect(pedidas).toBe(1);
    // Ir y volver enseguida no repite la petición.
    s.cambiar("hidden");
    s.avanzar(MS_MINIMO_AL_VOLVER - 1000);
    s.cambiar("visible");
    expect(pedidas).toBe(1);
  });

  it("al pararlo ya no pide ni escucha", () => {
    const s = simulacion(true);
    let pedidas = 0;
    const parar = refrescarAlaVista(() => (pedidas += 1), DIEZ_MINUTOS, s.documento, s.reloj);
    parar();
    s.avanzar(DIEZ_MINUTOS * 3);
    expect(pedidas).toBe(1);
    expect(s.oyentes.size).toBe(0);
  });
});
