// @vitest-environment jsdom
// Canal público de avisos (src/avisos.ts): los canales en orden, el enlace que abre la aplicación
// de Android ya suscrita, la página de texto enlazada desde el pie, el mapa del sitio y llms.txt,
// los códigos QR del build y el panel del mapa.

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RUTAS_AVISOS, SERVIDOR_AVISOS, TEXTO_AVISOS, canales, enlaceAndroid, enlaceWeb, rutaQr } from "../src/avisos.ts";
import { Avisos, BotonAvisos } from "../src/componentes/Avisos.tsx";
import type { Resumen } from "../src/datos/tipos.ts";
import { paginaAvisos } from "../src/texto/avisos.ts";
import { llmsTxt, sitemap } from "../src/texto/salidas.ts";
import { enlacesSobre } from "../src/texto/servicio.ts";
import { svgQr } from "../scripts/qr-avisos.ts";

const RESUMEN: Resumen = { actualizado: "2026-10-10T12:17Z", incidentes: [], episodios: [], eventos: [] };

describe("canales de avisos", () => {
  it("el general primero y los países por orden alfabético en cada idioma", () => {
    for (const idioma of ["es", "en"] as const) {
      const lista = canales(idioma);
      expect(lista[0]).toMatchObject({ tema: "general", general: true });
      const nombres = lista.slice(1).map((c) => c.nombre);
      expect(nombres).toEqual([...nombres].sort((a, b) => a.localeCompare(b, idioma)));
      expect(lista).toHaveLength(43);
    }
    expect(canales("es").find((c) => c.tema === "slovakia")?.nombre).toBe("Eslovaquia");
    expect(canales("en").find((c) => c.tema === "united-kingdom")?.nombre).toBe("United Kingdom");
  });

  it("enlaces: aplicación de Android ya suscrita, navegador y QR", () => {
    const eslovaquia = canales("es").find((c) => c.tema === "slovakia");
    if (eslovaquia === undefined) throw new Error("sin Eslovaquia");
    expect(SERVIDOR_AVISOS).toBe("https://ntfy.droneobservatory.eu");
    expect(enlaceAndroid(eslovaquia)).toBe("ntfy://ntfy.droneobservatory.eu/slovakia?display=EODI+%C2%B7+Eslovaquia");
    expect(enlaceWeb(eslovaquia)).toBe("https://ntfy.droneobservatory.eu/slovakia");
    expect(rutaQr(eslovaquia)).toBe("/avisos/qr/slovakia.svg");
  });

  it("el código QR es un SVG en negro sobre blanco con el margen de la norma", () => {
    const svg = svgQr("https://ntfy.droneobservatory.eu/general", "general");
    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg).toContain('fill="#fff"');
    expect(svg).toContain('fill="#000"');
    const lado = Number(/viewBox="0 0 (\d+) /.exec(svg)?.[1]);
    expect(lado).toBeGreaterThanOrEqual(21 + 8);
  });
});

describe("página «Avisos»", () => {
  it("en los dos idiomas, sin emoticonos, con qué se avisa y todos los canales", () => {
    for (const idioma of ["es", "en"] as const) {
      const pagina = paginaAvisos(idioma);
      expect(pagina.rutas).toEqual(RUTAS_AVISOS);
      const cuerpo = pagina.cuerpo.valor;
      for (const c of canales(idioma)) {
        expect(cuerpo).toContain(`id="canal-${c.tema}"`);
        expect(cuerpo).toContain(enlaceAndroid(c).replace(/&/g, "&amp;"));
        expect(cuerpo).toContain(rutaQr(c));
      }
      expect(cuerpo).toContain('<details class="texto-canal" id="canal-general" open>');
      expect(cuerpo).toContain("play.google.com");
      expect(cuerpo).toContain("f-droid.org");
      expect(cuerpo).toContain("apps.apple.com");
      expect(cuerpo).not.toMatch(/<script/);
      expect(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(cuerpo)).toBe(false);
    }
  });

  it("enlazada desde el pie, en el mapa del sitio y en llms.txt", () => {
    expect(enlacesSobre("es")[0]).toMatchObject({ ruta: "/avisos", texto: "Avisos" });
    expect(enlacesSobre("en")[0]).toMatchObject({ ruta: "/en/alerts", texto: "Alerts" });
    const texto = llmsTxt(RESUMEN);
    expect(texto).toContain("https://droneobservatory.eu/avisos");
    expect(texto).toContain("https://droneobservatory.eu/en/alerts");
    const mapa = sitemap([{ ...paginaAvisos("es"), estructurados: [], conMapa: false }]);
    expect(mapa).toContain("https://droneobservatory.eu/avisos");
  });
});

describe("panel «Avisos» del mapa", () => {
  it("botón con campana y estado anunciado; panel con los canales plegables y la página completa", () => {
    const { rerender } = render(<BotonAvisos idioma="es" abierto={false} onAbrir={() => undefined} />);
    const boton = screen.getByRole("button", { name: /^Avisos/ });
    expect(boton.getAttribute("aria-expanded")).toBe("false");
    expect(boton.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    rerender(<BotonAvisos idioma="es" abierto onAbrir={() => undefined} />);
    expect(screen.getByRole("button", { name: /^Avisos/ }).getAttribute("aria-expanded")).toBe("true");

    render(<Avisos idioma="en" />);
    const panel = document.querySelector("[data-panel-avisos]");
    if (!(panel instanceof HTMLElement)) throw new Error("sin panel");
    const detalles = panel.querySelectorAll("details");
    expect(detalles).toHaveLength(43);
    expect((detalles[0] as HTMLDetailsElement).open).toBe(true);
    expect((detalles[1] as HTMLDetailsElement).open).toBe(false);
    expect(within(panel).getByRole("link", { name: TEXTO_AVISOS.en.paginaCompleta }).getAttribute("href")).toBe("/en/alerts");
    expect(within(panel).getAllByRole("img", { name: /QR code of the/ })).toHaveLength(43);
  });
});
