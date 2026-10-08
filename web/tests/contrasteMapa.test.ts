// Contraste de los nombres del mapa de fondo (src/mapa/estilo.ts): cada capa de nombres llega a
// 4,5 a 1 (WCAG 2.1 AA para texto) contra su halo y contra las superficies del mapa sobre las que
// se pinta (tierra, sus matices y el agua).

import { describe, expect, it } from "vitest";

import { capasBase, SUPERFICIES_BASE } from "../src/mapa/estilo.ts";
import { contraste } from "../src/paleta.ts";

const AA_TEXTO = 4.5;

describe("nombres del mapa de fondo", () => {
  it("cumplen el contraste AA contra su halo y contra cada superficie", () => {
    const capas = capasBase("es").filter((c) => c.type === "symbol");
    expect(capas.length).toBeGreaterThan(5);
    let medidas = 0;
    for (const capa of capas) {
      const pintura = (capa.paint ?? {}) as Record<string, unknown>;
      const texto = pintura["text-color"];
      if (typeof texto !== "string") continue;
      medidas += 1;
      const halo = pintura["text-halo-color"];
      if (typeof halo === "string") {
        expect(contraste(texto, halo), `${capa.id}: ${texto} sobre su halo ${halo}`).toBeGreaterThanOrEqual(AA_TEXTO);
      }
      for (const superficie of SUPERFICIES_BASE) {
        expect(contraste(texto, superficie), `${capa.id}: ${texto} sobre ${superficie}`).toBeGreaterThanOrEqual(AA_TEXTO);
      }
    }
    expect(medidas).toBeGreaterThan(5);
  });
});
