// @vitest-environment jsdom
// Colores de los estados: naranja notificado, rojo confirmado, rojo con bandera atribuido, gris
// discontinuo desmentido; el verde, solo para «datos al día». Y el pulso: solo las novedades.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BarraEstado } from "../src/componentes/BarraEstado.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { Simbolo } from "../src/componentes/Simbolo.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { novedadesQueLaten } from "../src/estado/novedades.ts";
import { textos } from "../src/i18n/index.ts";
import { COLOR_AVISO, COLOR_DE_GRUPO, estilo } from "../src/mapa/estilo.ts";
import { BANDERA } from "../src/mapa/iconos.ts";
import { COLOR_BANDERA, COLOR_ESTADO, PALETA, contraste } from "../src/paleta.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");

/** Matrices de Machado, Oliveira y Fernandes (2009), gravedad 1. */
const DALTONISMO: Record<string, number[][]> = {
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  tritanopia: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
};

function lineal(canal: number): number {
  const v = canal / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

function simular(hex: string, matriz: number[][]): string {
  const rgb = [1, 3, 5].map((i) => lineal(parseInt(hex.slice(i, i + 2), 16)));
  const salida = matriz.map((fila) => fila.reduce((s, m, k) => s + m * (rgb[k] ?? 0), 0));
  return `#${salida
    .map((v) => {
      const c = Math.min(1, Math.max(0, v));
      const s = c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
      return Math.round(s * 255)
        .toString(16)
        .padStart(2, "0");
    })
    .join("")}`;
}

function tono(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [
    number,
    number,
    number,
  ];
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return h * 60;
}

function diferenciaDeTono(a: string, b: string): number {
  const d = Math.abs(tono(a) - tono(b));
  return Math.min(d, 360 - d);
}

describe("colores de los estados", () => {
  it("naranja notificado, rojo confirmado y atribuido, gris el desmentido", () => {
    expect(COLOR_ESTADO).toEqual({
      notificado: "#ff9a2e",
      confirmado: "#f53a50",
      atribuido: "#f53a50",
      desmentido: PALETA.secundario,
    });
    // Naranja de verdad (entre 20° y 40°) y rojo (a menos de 15° del rojo puro): ni dorado ni
    // cian.
    expect(tono(COLOR_ESTADO.notificado)).toBeGreaterThan(20);
    expect(tono(COLOR_ESTADO.notificado)).toBeLessThan(40);
    expect(diferenciaDeTono(COLOR_ESTADO.confirmado, "#ff0000")).toBeLessThan(15);
  });

  it("el naranja y el rojo se distinguen por luminancia, también con daltonismo", () => {
    const { notificado, confirmado } = COLOR_ESTADO;
    // Medido: 1,77:1 con visión normal; 1,62 deuteranopía, 2,15 protanopía, 1,66 tritanopía.
    expect(contraste(notificado, confirmado)).toBeGreaterThanOrEqual(1.7);
    for (const [nombre, matriz] of Object.entries(DALTONISMO)) {
      const separacion = contraste(simular(notificado, matriz), simular(confirmado, matriz));
      expect(separacion, nombre).toBeGreaterThanOrEqual(1.6);
    }
  });

  it("los dos se leen sobre el fondo oscuro: AA de texto en todas las superficies", () => {
    for (const superficie of [PALETA.fondo, PALETA.panelSolido, PALETA.elevado]) {
      expect(contraste(COLOR_ESTADO.notificado, superficie)).toBeGreaterThanOrEqual(4.5);
      expect(contraste(COLOR_ESTADO.confirmado, superficie)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("el rojo de los estados no es el de la capa de guerra", () => {
    expect(PALETA.guerra).not.toBe(COLOR_ESTADO.confirmado);
    expect(diferenciaDeTono(PALETA.guerra, COLOR_ESTADO.confirmado)).toBeGreaterThanOrEqual(10);
    // Las capas de la guerra usan su propio color, no el de los estados.
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const guerra = layers.filter((c) => c.id.startsWith("ucrania-"));
    expect(guerra.length).toBeGreaterThan(0);
    expect(JSON.stringify(guerra)).not.toContain(COLOR_ESTADO.confirmado);
  });

  it("ningún estado de incidente es verde: el verde es solo el de «datos al día»", () => {
    const verde = PALETA.alDia;
    for (const color of Object.values(COLOR_ESTADO)) expect(color).not.toBe(verde);
    expect(JSON.stringify(COLOR_AVISO)).not.toContain(verde);
    expect(JSON.stringify(COLOR_DE_GRUPO)).not.toContain(verde);
  });

  it("un grupo es rojo si contiene algún confirmado o atribuido y naranja si todos son notificados", () => {
    expect(COLOR_DE_GRUPO).toEqual([
      "case",
      [">", ["+", ["get", "n_atribuidos"], ["get", "n_confirmados"]], 0],
      COLOR_ESTADO.confirmado,
      [">", ["get", "n_notificados"], 0],
      COLOR_ESTADO.notificado,
      COLOR_ESTADO.desmentido,
    ]);
  });

  it("los avisos en directo van en la misma escala, sin verde: naranja posible, rojo confirmado", () => {
    expect(COLOR_AVISO).toEqual([
      "match",
      ["get", "estado"],
      "posible_cierre",
      COLOR_ESTADO.notificado,
      "cierre_confirmado",
      COLOR_ESTADO.confirmado,
      PALETA.secundario,
    ]);
  });
});

describe("bandera de los atribuidos", () => {
  it("solo el atribuido lleva bandera, roja", () => {
    for (const estado of ["notificado", "confirmado", "desmentido"] as const) {
      const { container } = render(<Simbolo tipo="incursion" estado={estado} />);
      expect(container.querySelector("[data-bandera]"), estado).toBeNull();
      cleanup();
    }
    const { container } = render(<Simbolo tipo="incursion" estado="atribuido" />);
    const bandera = container.querySelector("[data-bandera]");
    expect(bandera).not.toBeNull();
    expect(bandera?.innerHTML).toContain(COLOR_BANDERA);
    expect(COLOR_BANDERA).toBe(COLOR_ESTADO.atribuido);
  });

  it("en el mapa, la bandera queda fuera de la forma del símbolo, que sigue diciendo el tipo", () => {
    // Icono de 28 px con la forma centrada en (14, 14): círculo de radio 7, rombo de 8,5 y
    // cuadrado de 6,5 de media anchura. Ningún punto de la bandera cae dentro de ninguna.
    const centro = 14;
    const puntos: (readonly [number, number])[] = [
      [BANDERA.mastil[0], BANDERA.mastil[1]],
      [BANDERA.mastil[2], BANDERA.mastil[3]],
      ...BANDERA.banderin,
    ];
    for (const [x, y] of puntos) {
      const dx = Math.abs(x - centro);
      const dy = Math.abs(y - centro);
      expect(Math.hypot(dx, dy), "círculo").toBeGreaterThan(7);
      expect(dx + dy, "rombo").toBeGreaterThan(8.5);
      expect(Math.max(dx, dy), "cuadrado").toBeGreaterThan(6.5);
    }
    // Y se distingue: unos 7 px de banderín sobre un mástil de 9,5.
    const ancho = Math.max(...BANDERA.banderin.map((p) => p[0])) - BANDERA.mastil[0];
    expect(ancho).toBeGreaterThanOrEqual(6);
  });

  it("la ficha dice «Confirmado · atribuido a…» con el actor y la autoridad", () => {
    const atribuido = detalleIncidente(
      incidente({
        estado: {
          actual: "atribuido",
          historial: [
            {
              estado: "atribuido",
              fecha: { valor: "2025-10-04T10:00Z", precision: "minuto" },
              fuente_id: "gdelt-0000000000000001",
            },
          ],
        },
        atribucion: {
          actor: "Rusia",
          autoridad: "Gobierno de Dinamarca",
          fecha: { valor: "2025-10-04T10:00Z", precision: "minuto" },
        },
      }),
    );
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={atribuido} />);
    const estado = container.querySelector("[data-estado-atribuido]");
    expect(estado?.textContent).toBe("Confirmado · atribuido a Rusia, según Gobierno de Dinamarca");
    expect(estado?.querySelector("[data-bandera]")).not.toBeNull();
    cleanup();
    const ingles = render(<FichaIncidente t={en} idioma="en" incidente={atribuido} />);
    expect(ingles.container.querySelector("[data-estado-atribuido]")?.textContent).toBe(
      "Confirmed · attributed to Rusia, according to Gobierno de Dinamarca",
    );
  });

  it("el verde de la barra de estado es el de «datos al día», no el de un estado", () => {
    const { container } = render(
      <BarraEstado
        t={es}
        actualizado="2026-10-03T10:17Z"
        sistema={null}
        ahora={new Date("2026-10-03T10:30:00Z")}
      />,
    );
    expect(container.innerHTML).toContain("bg-al-dia");
    expect(container.innerHTML).not.toContain("bg-confirmado");
  });
});

describe("pulso: solo las novedades desde la última visita", () => {
  const nuevos = ["EODI-2026-00001", "EODI-2026-00002"];
  const sinVer = { descartadas: false, recorridas: false, abiertos: new Set<string>() };

  it("laten los nuevos; en la primera visita no hay nuevos y no late nada", () => {
    expect([...novedadesQueLaten(nuevos, sinVer)]).toEqual(nuevos);
    expect(novedadesQueLaten([], sinVer).size).toBe(0);
  });

  it("se apagan al pulsar «Verlas» o «Descartar»", () => {
    expect(novedadesQueLaten(nuevos, { ...sinVer, recorridas: true }).size).toBe(0);
    expect(novedadesQueLaten(nuevos, { ...sinVer, descartadas: true }).size).toBe(0);
  });

  it("un incidente deja de latir al abrirlo; los demás siguen", () => {
    const abiertos = new Set([nuevos[0] ?? ""]);
    expect([...novedadesQueLaten(nuevos, { ...sinVer, abiertos })]).toEqual([nuevos[1]]);
  });
});
