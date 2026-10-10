// @vitest-environment jsdom
// Canal público de avisos (src/avisos.ts): los canales en orden, el enlace que abre la aplicación
// de Android ya suscrita, la página de texto enlazada desde el pie, el mapa del sitio y llms.txt,
// los códigos QR del build y el panel del mapa en tres pasos, con un solo botón por dispositivo.

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  RUTAS_AVISOS,
  SERVIDOR_AVISOS,
  TEXTO_AVISOS,
  TIENDAS,
  canales,
  dispositivoDe,
  enlaceAndroid,
  enlaceWeb,
  filtrarCanales,
  rutaQr,
} from "../src/avisos.ts";
import { Avisos, BotonAvisos } from "../src/componentes/Avisos.tsx";
import type { Resumen } from "../src/datos/tipos.ts";
import { paginaAvisos } from "../src/texto/avisos.ts";
import { llmsTxt, sitemap } from "../src/texto/salidas.ts";
import { enlacesSobre } from "../src/texto/servicio.ts";
import { svgQr } from "../scripts/qr-avisos.ts";

afterEach(cleanup);

const RESUMEN: Resumen = { actualizado: "2026-10-10T12:17Z", incidentes: [], episodios: [], eventos: [] };

function panel(): HTMLElement {
  const elemento = document.querySelector("[data-panel-avisos]");
  if (!(elemento instanceof HTMLElement)) throw new Error("sin panel");
  return elemento;
}

describe("canales de avisos", () => {
  it("toda Europa primero y los países por orden alfabético en cada idioma, con nombres que se entienden solos", () => {
    for (const idioma of ["es", "en"] as const) {
      const lista = canales(idioma);
      expect(lista[0]).toMatchObject({ tema: "drones-europe", general: true });
      const nombres = lista.slice(1).map((c) => c.nombre);
      expect(nombres).toEqual([...nombres].sort((a, b) => a.localeCompare(b, idioma)));
      expect(lista).toHaveLength(43);
      for (const c of lista) expect(c.tema).toMatch(/^drones-[a-z-]+$/);
    }
    expect(canales("es")[0]?.nombre).toBe("Toda Europa");
    expect(canales("es").find((c) => c.tema === "drones-slovakia")?.nombre).toBe("Eslovaquia");
    expect(canales("en").find((c) => c.tema === "drones-united-kingdom")?.nombre).toBe("United Kingdom");
  });

  it("enlaces: aplicación de Android ya suscrita, navegador y QR", () => {
    const eslovaquia = canales("es").find((c) => c.tema === "drones-slovakia");
    if (eslovaquia === undefined) throw new Error("sin Eslovaquia");
    expect(SERVIDOR_AVISOS).toBe("https://ntfy.droneobservatory.eu");
    expect(enlaceAndroid(eslovaquia)).toBe("ntfy://ntfy.droneobservatory.eu/drones-slovakia?display=EODI+%C2%B7+Eslovaquia");
    expect(enlaceWeb(eslovaquia)).toBe("https://ntfy.droneobservatory.eu/drones-slovakia");
    expect(rutaQr(eslovaquia)).toBe("/avisos/qr/drones-slovakia.svg");
  });

  it("el buscador no distingue tildes ni mayúsculas", () => {
    const lista = canales("es");
    expect(filtrarCanales(lista, "").length).toBe(43);
    expect(filtrarCanales(lista, "ESLOVA").map((c) => c.nombre)).toEqual(["Eslovaquia"]);
    expect(filtrarCanales(lista, "rumania").map((c) => c.nombre)).toEqual(["Rumanía"]);
    expect(filtrarCanales(lista, "zzz")).toEqual([]);
  });

  it("reconoce Android, iPhone (también el iPad que se presenta como Mac) y el ordenador", () => {
    expect(dispositivoDe("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile")).toBe("android");
    expect(dispositivoDe("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15")).toBe("iphone");
    expect(dispositivoDe("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15", 5)).toBe("iphone");
    expect(dispositivoDe("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15", 0)).toBe("ordenador");
    expect(dispositivoDe("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0")).toBe("ordenador");
  });

  it("el código QR es un SVG en negro sobre blanco con el margen de la norma", () => {
    const svg = svgQr("https://ntfy.droneobservatory.eu/drones-europe", "drones-europe");
    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg).toContain('fill="#fff"');
    expect(svg).toContain('fill="#000"');
    const lado = Number(/viewBox="0 0 (\d+) /.exec(svg)?.[1]);
    expect(lado).toBeGreaterThanOrEqual(21 + 8);
  });
});

describe("página «Avisos»", () => {
  it("primero los tres pasos, después cada dispositivo y al final todos los canales con su QR", () => {
    for (const idioma of ["es", "en"] as const) {
      const t = TEXTO_AVISOS[idioma];
      const pagina = paginaAvisos(idioma);
      expect(pagina.rutas).toEqual(RUTAS_AVISOS);
      const cuerpo = pagina.cuerpo.valor;
      const pasos = cuerpo.indexOf('id="pasos"');
      const dispositivos = cuerpo.indexOf('id="dispositivos"');
      const lista = cuerpo.indexOf('id="canales"');
      expect(pasos).toBeGreaterThan(0);
      expect(dispositivos).toBeGreaterThan(pasos);
      expect(lista).toBeGreaterThan(dispositivos);
      expect(cuerpo).toContain(t.recibir);
      for (const c of canales(idioma)) {
        expect(cuerpo).toContain(`id="canal-${c.tema}"`);
        expect(cuerpo).toContain(enlaceAndroid(c).replace(/&/g, "&amp;"));
        expect(cuerpo).toContain(rutaQr(c));
      }
      expect(cuerpo.match(/<img /g)).toHaveLength(43);
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
  it("botón con campana y estado anunciado", () => {
    const { rerender } = render(<BotonAvisos idioma="es" abierto={false} onAbrir={() => undefined} />);
    const boton = screen.getByRole("button", { name: /^Avisos/ });
    expect(boton.getAttribute("aria-expanded")).toBe("false");
    expect(boton.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    rerender(<BotonAvisos idioma="es" abierto onAbrir={() => undefined} />);
    expect(screen.getByRole("button", { name: /^Avisos/ }).getAttribute("aria-expanded")).toBe("true");
  });

  it("tres pasos; toda Europa por defecto; en el ordenador un botón al navegador y un solo QR", () => {
    render(<Avisos idioma="es" dispositivo="ordenador" />);
    const p = panel();
    expect(p.querySelectorAll(":scope > ol > li")).toHaveLength(3);
    expect(within(p).getByText(TEXTO_AVISOS.es.recibir)).toBeTruthy();
    const selector = within(p).getByRole("combobox", { name: "Canal" });
    expect((selector as HTMLSelectElement).value).toBe("drones-europe");
    expect(selector.querySelectorAll("option")).toHaveLength(43);
    const botones = within(p).getAllByRole("link", { name: "Suscribirme" });
    expect(botones).toHaveLength(1);
    expect(botones[0]?.getAttribute("href")).toBe("https://ntfy.droneobservatory.eu/drones-europe");
    expect(within(p).getAllByRole("img", { name: /Código QR del canal/ })).toHaveLength(1);
    expect(within(p).getByText("Escanéalo con tu móvil")).toBeTruthy();
    expect(within(p).getByRole("link", { name: "Más ayuda" }).getAttribute("href")).toBe("/avisos");
  });

  it("el buscador elige el primer país que coincide y el botón y el QR siguen al canal elegido", () => {
    render(<Avisos idioma="es" dispositivo="ordenador" />);
    const p = panel();
    fireEvent.change(within(p).getByRole("searchbox", { name: "Buscar país" }), { target: { value: "polo" } });
    const selector = within(p).getByRole("combobox", { name: "Canal" }) as HTMLSelectElement;
    expect(selector.value).toBe("drones-poland");
    expect(selector.querySelectorAll("option")).toHaveLength(1);
    expect(within(p).getByRole("link", { name: "Suscribirme" }).getAttribute("href")).toBe(
      "https://ntfy.droneobservatory.eu/drones-poland",
    );
    expect(within(p).getByRole("img", { name: "Código QR del canal Polonia" }).getAttribute("src")).toBe(
      "/avisos/qr/drones-poland.svg",
    );
  });

  it("en Android, el botón abre la aplicación ya suscrita, enlace pequeño a Google Play y sin QR", () => {
    render(<Avisos idioma="en" dispositivo="android" />);
    const p = panel();
    const boton = within(p).getByRole("link", { name: "Subscribe" });
    expect(boton.getAttribute("href")).toMatch(/^ntfy:\/\/ntfy\.droneobservatory\.eu\/drones-europe\?display=/);
    expect(within(p).getByRole("link", { name: TEXTO_AVISOS.en.sinAplicacion }).getAttribute("href")).toBe(TIENDAS.googlePlay);
    expect(p.querySelector("img")).toBeNull();
    expect(p.querySelectorAll(":scope > ol > li:nth-child(3) ol > li").length).toBeLessThanOrEqual(3);
    expect(within(p).getByRole("link", { name: "More help" }).getAttribute("href")).toBe("/en/alerts");
  });

  it("en iPhone, App Store y tres pasos con el servidor y el canal para copiar, sin QR", () => {
    render(<Avisos idioma="es" dispositivo="iphone" />);
    const p = panel();
    expect(within(p).getByRole("link", { name: "Suscribirme" }).getAttribute("href")).toBe(TIENDAS.appStore);
    expect(p.querySelectorAll(":scope > ol > li:nth-child(3) ol > li")).toHaveLength(3);
    expect(within(p).getByRole("button", { name: "Copiar el servidor" })).toBeTruthy();
    expect(within(p).getByRole("button", { name: "Copiar el canal" })).toBeTruthy();
    expect(within(p).getByText("drones-europe", { selector: "code" })).toBeTruthy();
    expect(p.querySelector("img")).toBeNull();
  });
});
