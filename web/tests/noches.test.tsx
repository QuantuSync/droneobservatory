// @vitest-environment jsdom
// Cada parte cuenta una sola vez y en su noche (o su día), con una sola regla para «Europa
// ahora», «Noche a noche», la capa de Ucrania y las fichas. Los partes son los publicados entre
// el 30 de septiembre y el 4 de octubre de 2026, con sus cifras reales.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EuropaAhora } from "../src/componentes/EuropaAhora.tsx";
import { cifrasAhora } from "../src/datos/ahora.ts";
import { resumirUcrania } from "../src/datos/derivar.ts";
import type { Ataque } from "../src/datos/tipos.ts";
import {
  cifrasDeRegion,
  diaDeParte,
  jornada,
  jornadaDeParte,
  nochesDeGuerra,
} from "../src/datos/ucrania.ts";
import { jornadaEscrita, textos } from "../src/i18n/index.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { ataque, publicacion } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");
const dia = diaDeInstante;

function parte(id: string, inicio: string, fin: string, lanzados: number, cambios: Partial<Ataque> = {}): Ataque {
  return ataque({
    id,
    periodo: { inicio: { valor: inicio, precision: "minuto" }, fin: { valor: fin, precision: "minuto" } },
    lanzados: { total: { min: lanzados, max: lanzados } },
    regiones: [{ region: "UA-32", derribados: { min: 1, max: 1 } }],
    ...cambios,
  });
}

/** Partes del Ministerio de Defensa ruso: uno de día y otro de noche que empiezan el mismo día. */
function parteRuso(id: string, inicio: string, fin: string, derribados: number): Ataque {
  return ataque({
    id,
    sentido: "UA_RU",
    periodo: { inicio: { valor: inicio, precision: "minuto" }, fin: { valor: fin, precision: "minuto" } },
    lanzados: { total: "desconocido" },
    derribados: { min: derribados, max: derribados },
    regiones: [{ region: "RU-BEL", derribados: { min: derribados, max: derribados } }],
  });
}

const PARTES = [
  parte("EODI-UA-2026-1017", "2026-09-30T15:00Z", "2026-10-01T05:00Z", 107),
  // De día, de 06:30 a 18:00 (hora de Kiev), el 1 de octubre.
  parte("EODI-UA-2026-1019", "2026-10-01T03:30Z", "2026-10-01T15:00Z", 97),
  // La noche del 1 al 2: empieza el mismo día que el parte de día; antes se sumaban (205).
  parte("EODI-UA-2026-1021", "2026-10-01T15:00Z", "2026-10-02T05:00Z", 108),
  parte("EODI-UA-2026-1024", "2026-10-02T15:00Z", "2026-10-03T06:00Z", 157),
  // Un tramo que ya cuenta el parte de la noche: no se suma.
  parte("EODI-UA-2026-1026", "2026-10-02T21:00Z", "2026-10-03T03:00Z", 40, { incluido_en: "EODI-UA-2026-1024" }),
  parte("EODI-UA-2026-1027", "2026-10-03T15:00Z", "2026-10-04T05:30Z", 135),
  // Otro parte de la misma noche que se solapa con el anterior: tampoco se suma.
  parte("EODI-UA-2026-1028", "2026-10-03T16:00Z", "2026-10-04T05:00Z", 130, { solapado_con: "EODI-UA-2026-1027" }),
  parteRuso("EODI-UA-2026-1023", "2026-10-02T05:00Z", "2026-10-02T17:00Z", 209),
  parteRuso("EODI-UA-2026-1025", "2026-10-02T17:00Z", "2026-10-03T05:00Z", 218),
];
const ucrania = resumirUcrania(publicacion(PARTES));

/** «Europa ahora» como se habría visto justo después de publicarse el parte que acaba en `fin`. */
function europaAhoraTras(fin: string) {
  const hasta = PARTES.filter((a) => a.periodo.fin.valor <= fin);
  return cifrasAhora({
    resumen: null,
    ucrania: resumirUcrania(publicacion(hasta)),
    directo: null,
    gnssHoy: null,
    ahora: Date.parse(fin) + 60_000,
  }).drones;
}

function nocheDe(desde: string, tipo: "noche" | "dia" = "noche") {
  return nochesDeGuerra(ucrania).find((n) => n.jornada.desde === dia(desde) && n.jornada.tipo === tipo);
}

describe("la noche de un parte: una sola regla", () => {
  it("un parte que cruza la medianoche es una noche; uno que empieza y acaba el mismo día, un día", () => {
    expect(jornada(dia("2026-10-01"), Date.parse("2026-10-02T05:00Z"))).toEqual({ tipo: "noche", desde: dia("2026-10-01"), hasta: dia("2026-10-02") });
    expect(jornada(dia("2026-10-01"), Date.parse("2026-10-01T15:00Z"))).toEqual({ tipo: "dia", desde: dia("2026-10-01"), hasta: dia("2026-10-01") });
    // Un fin que la fuente da días después cuenta en la noche de su comienzo.
    expect(jornada(dia("2026-10-01"), Date.parse("2026-10-09T05:00Z")).hasta).toBe(dia("2026-10-02"));
    const fila = ucrania.ataques.find((f) => f[0] === "EODI-UA-2026-1021");
    if (fila === undefined) throw new Error("sin fila");
    expect(jornadaDeParte(fila)).toEqual({ tipo: "noche", desde: dia("2026-10-01"), hasta: dia("2026-10-02") });
    expect(diaDeParte(fila)).toBe(dia("2026-10-01"));
  });

  it("se escribe igual en todas partes", () => {
    const noche = { tipo: "noche", desde: dia("2026-10-03"), hasta: dia("2026-10-04") } as const;
    expect(jornadaEscrita(es, noche)).toBe("noche del 3 al 4 de octubre");
    expect(jornadaEscrita(es, noche, true)).toBe("Noche del 3 al 4 de octubre");
    expect(jornadaEscrita(en, noche)).toBe("night of 3 to 4 October");
    expect(jornadaEscrita(es, { tipo: "dia", desde: dia("2026-10-01"), hasta: dia("2026-10-01") })).toBe("día 1 de octubre");
  });
});

describe("cada parte cuenta una sola vez y en su noche", () => {
  it("la noche del 1 al 2 de octubre son 108 drones, no 205, en «Noche a noche» y en «Europa ahora»", () => {
    expect(nocheDe("2026-10-01")?.lanzados).toBe(108);
    expect(nocheDe("2026-10-01", "dia")?.lanzados).toBe(97);
    const ahora = europaAhoraTras("2026-10-02T05:00Z");
    expect(ahora?.lanzados).toBe(108);
    expect(ahora?.jornada).toEqual(nocheDe("2026-10-01")?.jornada);
  });

  it("tres noches más de control: las dos vistas dan lo mismo y nada se cuenta dos veces", () => {
    const casos: [string, string, number][] = [
      // Noche del 30 de septiembre al 1 de octubre, que cambia de mes.
      ["2026-09-30", "2026-10-01T05:00Z", 107],
      // Noche del 2 al 3, con un tramo incluido en su parte.
      ["2026-10-02", "2026-10-03T06:00Z", 157],
      // Noche del 3 al 4, con otro parte que se solapa.
      ["2026-10-03", "2026-10-04T05:30Z", 135],
    ];
    for (const [desde, fin, lanzados] of casos) {
      expect(nocheDe(desde)?.lanzados, desde).toBe(lanzados);
      const ahora = europaAhoraTras(fin);
      expect(ahora?.lanzados, desde).toBe(lanzados);
      expect(ahora?.jornada, desde).toEqual(nocheDe(desde)?.jornada);
    }
  });

  it("los dos partes rusos del 2 de octubre son un día y una noche: cada derribo cuenta una vez", () => {
    const rusos = ucrania.ataques.filter((f) => f[2] === 1).map(jornadaDeParte);
    expect(rusos.map((j) => j.tipo)).toEqual(["dia", "noche"]);
    // El 2 de octubre suma los dos partes, cada uno una vez: 209 + 218.
    const dos = { desde: dia("2026-10-02"), hasta: dia("2026-10-02") };
    expect(cifrasDeRegion(ucrania, "RU-BEL", dos).derribados).toEqual({ min: 427, max: 427 });
    expect(cifrasDeRegion(ucrania, "RU-BEL", dos).lista.map((a) => jornadaEscrita(es, a.jornada))).toEqual([
      "noche del 2 al 3 de octubre",
      "día 2 de octubre",
    ]);
    // Y no entran en «Noche a noche», que son los ataques contra Ucrania.
    expect(nochesDeGuerra(ucrania).every((n) => n.lanzados !== 209 && n.lanzados !== 218)).toBe(true);
  });

  it("«Europa ahora» escribe la noche igual que «Noche a noche»", () => {
    const drones = europaAhoraTras("2026-10-02T05:00Z");
    const { container } = render(
      <EuropaAhora t={es} idioma="es" cifras={{ cierres: 0, incidentes: 0, drones, focos: 0, gnss: null }} onIr={() => undefined} />,
    );
    expect(container.querySelector('[data-cifra="drones"] [data-numero]')?.textContent).toBe("108");
    expect(container.querySelector('[data-cifra="drones"] [data-texto]')?.textContent).toBe(
      `drones lanzados la última noche · ${jornadaEscrita(es, nocheDe("2026-10-01")?.jornada ?? { tipo: "dia", desde: 0, hasta: 0 })}`,
    );
  });
});
