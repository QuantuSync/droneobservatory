// La función del borde (../../api/borde.ts), a la que Vercel solo manda las fichas que no son un
// fichero: un unido redirige en su idioma, un ataque de la capa de Ucrania que existe abre la
// portada y lo demás da 404; y la comprobación de capacidad de Vercel avisa al pasar del 80 %.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { decidirBorde, rutaPedida } from "../../api/borde.ts";
import type { RutasBorde } from "../../api/borde.ts";
import { capacidadesAlLimite, patronDeRuta, usoDeCapacidad } from "../src/seguridad/despliegue.ts";
import type { ConfiguracionDespliegue } from "../src/seguridad/despliegue.ts";

const RUTAS: RutasBorde = {
  redirecciones: { "/EODI-2025-00296": "/EODI-2025-00295", "/en/EODI-2025-00296": "/en/EODI-2025-00295" },
  ataques: ["EODI-UA-2026-1014"],
};
const ATAQUES = new Set(RUTAS.ataques);
const vercel = JSON.parse(
  readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "..", "vercel.json"), "utf-8"),
) as ConfiguracionDespliegue;

describe("función del borde", () => {
  it("redirige un unido a la ficha del que lo absorbió, en su idioma", () => {
    expect(decidirBorde("/EODI-2025-00296", RUTAS, ATAQUES)).toEqual({ tipo: "redirigir", destino: "/EODI-2025-00295" });
    expect(decidirBorde("/en/EODI-2025-00296", RUTAS, ATAQUES)).toEqual({
      tipo: "redirigir",
      destino: "/en/EODI-2025-00295",
    });
  });

  it("un ataque que existe abre la portada de su idioma; uno inventado no existe", () => {
    expect(decidirBorde("/EODI-UA-2026-1014", RUTAS, ATAQUES)).toEqual({ tipo: "portada", ruta: "/" });
    expect(decidirBorde("/en/EODI-UA-2026-1014", RUTAS, ATAQUES)).toEqual({ tipo: "portada", ruta: "/en" });
    expect(decidirBorde("/EODI-UA-2026-9999", RUTAS, ATAQUES)).toEqual({ tipo: "no_existe" });
    expect(decidirBorde("/en/EODI-UA-2026-9999", RUTAS, ATAQUES)).toEqual({ tipo: "no_existe" });
  });

  it("un incidente que no es un fichero ni un unido no existe", () => {
    expect(decidirBorde("/EODI-2099-00001", RUTAS, ATAQUES)).toEqual({ tipo: "no_existe" });
  });

  it("solo llegan las fichas: las reescrituras de vercel.json y la ruta que reconstruye", () => {
    const [es, en] = (vercel.rewrites ?? []).map((r) => patronDeRuta(r.source));
    expect(es?.test("/EODI-UA-2026-1014") === true && en?.test("/en/EODI-2025-00296") === true).toBe(true);
    expect(es?.test("/metodologia") === true || es?.test("/datos/resumen.json") === true).toBe(false);
    expect(rutaPedida(new URL("https://x/api/borde?id=EODI-2025-00296&idioma=en"))).toBe("/en/EODI-2025-00296");
    expect(rutaPedida(new URL("https://x/api/borde?id=EODI-UA-2026-1014"))).toBe("/EODI-UA-2026-1014");
    expect(rutaPedida(new URL("https://x/api/borde?id=../secreto"))).toBeNull();
  });
});

describe("capacidad de Vercel", () => {
  it("el proyecto no gasta redirecciones masivas y queda lejos del aviso", () => {
    expect(vercel.bulkRedirectsPath).toBeUndefined();
    expect(capacidadesAlLimite(usoDeCapacidad(vercel, 0))).toEqual([]);
  });

  it("avisa al pasar del 80 % con un texto claro", () => {
    expect(capacidadesAlLimite(usoDeCapacidad(vercel, 800))).toEqual([]);
    const aviso = capacidadesAlLimite(usoDeCapacidad(vercel, 801));
    expect(aviso).toHaveLength(1);
    expect(aviso[0]).toContain("redirecciones masivas: 801 de 1000");
  });
});
