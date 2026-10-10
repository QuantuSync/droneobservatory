// Posicionamiento en buscadores y asistentes (docs/posicionamiento.md): robots.txt deja pasar a los
// rastreadores, el sitemap se sirve como XML legible en el navegador, cada página dice su versión
// en el otro idioma y la de por defecto, las páginas con el mapa precargan sus datos, llms.txt
// enlaza los avisos, y la clave de IndexNow está publicada.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { etiquetasDeCabecera, paginaDeIncidente, paginaDePortada } from "../src/cabecera.ts";
import type { Resumen } from "../src/datos/tipos.ts";
import { cabecerasDe, directivasCsp } from "../src/seguridad/despliegue.ts";
import type { ConfiguracionDespliegue } from "../src/seguridad/despliegue.ts";
import { llmsTxt, sitemap } from "../src/texto/salidas.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const vercel = JSON.parse(readFileSync(join(RAIZ, "vercel.json"), "utf-8")) as ConfiguracionDespliegue;
const RASTREADORES = [
  "Googlebot",
  "Bingbot",
  "Google-Extended",
  "GPTBot",
  "OAI-SearchBot",
  "ChatGPT-User",
  "PerplexityBot",
  "ClaudeBot",
  "Applebot",
  "Applebot-Extended",
];

/** Las reglas de robots.txt que se aplican a un agente (su grupo, o el de «*»). */
function reglasPara(robots: string, agente: string): string[] {
  const grupos: { agentes: string[]; reglas: string[] }[] = [];
  let actual: { agentes: string[]; reglas: string[] } | null = null;
  for (const linea of robots.split("\n").map((l) => l.replace(/#.*/, "").trim())) {
    const [campo = "", ...resto] = linea.split(":");
    const valor = resto.join(":").trim();
    if (campo.toLowerCase() === "user-agent") {
      if (actual === null || actual.reglas.length > 0) {
        actual = { agentes: [], reglas: [] };
        grupos.push(actual);
      }
      actual.agentes.push(valor.toLowerCase());
    } else if (/^(allow|disallow)$/i.test(campo) && actual !== null) {
      actual.reglas.push(`${campo.toLowerCase()}:${valor}`);
    }
  }
  const propio = grupos.find((g) => g.agentes.includes(agente.toLowerCase()));
  return (propio ?? grupos.find((g) => g.agentes.includes("*")))?.reglas ?? [];
}

describe("robots.txt", () => {
  const robots = readFileSync(join(RAIZ, "web", "public", "robots.txt"), "utf-8");

  it.each(RASTREADORES)("%s puede rastrear todo", (agente) => {
    const reglas = reglasPara(robots, agente);
    expect(reglas).toContain("allow:/");
    expect(reglas.filter((r) => r.startsWith("disallow:") && r !== "disallow:")).toEqual([]);
    // Con su propio grupo, para que se vea que está permitido a propósito.
    expect(robots).toMatch(new RegExp(`^User-agent: ${agente}$`, "m"));
  });

  it("cualquier otro también, y el sitemap está indicado", () => {
    expect(reglasPara(robots, "OtroBuscador")).toEqual(["allow:/"]);
    expect(robots).toContain("Sitemap: https://droneobservatory.eu/sitemap.xml");
  });
});

describe("sitemap.xml en la web", () => {
  it("se sirve como XML, con la política estricta de la web y su hoja de estilo del propio sitio", () => {
    const cabeceras = cabecerasDe(vercel, "/sitemap.xml");
    expect(cabeceras.get("Content-Type")).toBe("application/xml; charset=utf-8");
    expect(directivasCsp(cabeceras.get("Content-Security-Policy") ?? "").get("style-src")).toEqual(["'self'"]);
    const xml = sitemap([]);
    expect(xml.split("\n")[1]).toBe('<?xml-stylesheet type="text/css" href="/sitemap.css"?>');
    expect(readFileSync(join(RAIZ, "web", "public", "sitemap.css"), "utf-8")).toContain("urlset");
  });
});

describe("cabecera de cada página", () => {
  it("dice su versión en cada idioma y la de por defecto (x-default, la española)", () => {
    const html = etiquetasDeCabecera(paginaDeIncidente("en", "EODI-2026-00500", "Drone"));
    expect(html).toContain('<link rel="canonical" href="https://droneobservatory.eu/en/EODI-2026-00500">');
    expect(html).toContain('<link rel="alternate" hreflang="es" href="https://droneobservatory.eu/EODI-2026-00500">');
    expect(html).toContain('<link rel="alternate" hreflang="en" href="https://droneobservatory.eu/en/EODI-2026-00500">');
    expect(html).toContain('<link rel="alternate" hreflang="x-default" href="https://droneobservatory.eu/EODI-2026-00500">');
    expect(html).toContain('<meta name="twitter:card" content="summary_large_image">');
    expect(html).toContain('<meta property="og:image" content="https://droneobservatory.eu/compartir-en.png">');
  });

  it("precarga los datos que pide la página con el mapa, en el modo del fetch() de la web", () => {
    const html = etiquetasDeCabecera({ ...paginaDePortada("es"), precargas: ["/datos/resumen.json"] });
    expect(html).toContain('<link rel="preload" href="/datos/resumen.json" as="fetch" crossorigin>');
    expect(etiquetasDeCabecera(paginaDePortada("es"))).not.toContain("preload");
  });
});

describe("llms.txt", () => {
  it("enlaza los avisos, la metodología, los datos abiertos con su licencia y cómo citar", () => {
    const resumen: Resumen = { actualizado: "2026-10-10T12:17Z", incidentes: [], episodios: [], eventos: [] };
    const texto = llmsTxt(resumen);
    expect(texto).toContain("## Alerts");
    expect(texto).toContain("drones-europe");
    expect(texto).toContain("https://droneobservatory.eu/en/alerts");
    expect(texto).toContain("https://droneobservatory.eu/avisos");
    expect(texto).toContain("https://droneobservatory.eu/en/methodology");
    expect(texto).toContain("https://creativecommons.org/licenses/by/4.0/");
    expect(texto).toContain("How to cite:");
    expect(texto).toContain("Cómo citar:");
  });
});
