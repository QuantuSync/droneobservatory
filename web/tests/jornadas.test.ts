// La noche de un parte con la misma regla en los datos y en la web: los casos de
// tests/fixtures/jornadas.json los comprueba también proceso/ataques.jornada, y la que trae cada
// ataque publicado tiene que ser la que calcula la web.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { Ataque } from "../src/datos/tipos.ts";
import { jornada } from "../src/datos/ucrania.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";

interface Caso {
  inicio: string;
  fin: string;
  jornada: { tipo: "noche" | "dia"; desde: string; hasta: string };
}

const raiz = join(import.meta.dirname, "..", "..");
const casos = (
  JSON.parse(readFileSync(join(raiz, "tests", "fixtures", "jornadas.json"), "utf-8")) as {
    casos: Caso[];
  }
).casos;

function enDias(j: Caso["jornada"]): { tipo: string; desde: number; hasta: number } {
  return { tipo: j.tipo, desde: diaDeInstante(`${j.desde}T00:00Z`), hasta: diaDeInstante(`${j.hasta}T00:00Z`) };
}

describe("una sola regla para la noche de un parte", () => {
  it("los casos compartidos con los datos", () => {
    for (const caso of casos) {
      expect(jornada(diaDeInstante(caso.inicio), Date.parse(caso.fin))).toEqual(enDias(caso.jornada));
    }
  });

  it("la noche que publican los datos es la que calcula la web", () => {
    const ruta = join(raiz, "publicacion", "ucrania.json");
    if (!existsSync(ruta)) return;
    const { ataques } = JSON.parse(readFileSync(ruta, "utf-8")) as { ataques: Ataque[] };
    for (const ataque of ataques) {
      if (ataque.jornada === undefined) continue;
      const calculada = jornada(diaDeInstante(ataque.periodo.inicio.valor), Date.parse(ataque.periodo.fin.valor));
      expect(calculada, ataque.id).toEqual(enDias(ataque.jornada));
    }
  });
});
