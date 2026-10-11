// @vitest-environment jsdom
// Canal público de avisos (src/avisos.ts): los canales en orden, el enlace que abre la aplicación
// de Android ya suscrita, la página de texto enlazada desde el pie, el mapa del sitio y llms.txt,
// los códigos QR del build y el panel del mapa en tres pasos: en el teléfono, «Suscríbete» en dos
// pasos numerados (instalar ntfy y suscribirse al canal); el canal elegido se recuerda.

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  CLAVE_CANAL,
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

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

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
      // En el teléfono, dos pasos: instalar ntfy y suscribirse (en Android, con ntfy://), con la
      // frase de volver tras instalar.
      const paso3 = cuerpo.slice(pasos, dispositivos);
      expect(paso3.match(/class="texto-dos-pasos"/g)).toHaveLength(2);
      expect(paso3.split(t.instalar)).toHaveLength(3);
      expect(paso3.split(t.instalarNota)).toHaveLength(3);
      expect(paso3.split(t.suscribirCanal)).toHaveLength(3);
      expect(paso3).toContain(t.suscribirCanalNota.android);
      expect(paso3).toContain(t.suscribirCanalNota.iphone);
      expect(paso3).toContain(`href="${TIENDAS.googlePlay}"`);
      expect(paso3).toContain(`href="${TIENDAS.appStore}"`);
      const europa = canales(idioma)[0];
      if (europa === undefined) throw new Error("sin canales");
      expect(paso3.indexOf(t.instalar)).toBeLessThan(paso3.indexOf(enlaceAndroid(europa).replace(/&/g, "&amp;")));
      expect(paso3).not.toContain("intent:");
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

  it("en Android, dos botones en orden: 1 a Google Play y 2 a la aplicación ya suscrita con ntfy://, sin QR", () => {
    render(<Avisos idioma="en" dispositivo="android" />);
    const p = panel();
    const t = TEXTO_AVISOS.en;
    const enlaces = within(p.querySelector(":scope > ol > li:nth-child(3)") as HTMLElement).getAllByRole("link");
    expect(enlaces.map((a) => a.textContent)).toEqual(["1. Install the ntfy app", "2. Subscribe to the channel"]);
    expect(enlaces[0]?.getAttribute("href")).toBe(TIENDAS.googlePlay);
    expect(enlaces[1]?.getAttribute("href")).toBe("ntfy://ntfy.droneobservatory.eu/drones-europe?display=EODI+%C2%B7+All+of+Europe");
    expect(enlaces[0]?.className).toBe(enlaces[1]?.className);
    expect(within(p).getByText(t.instalarNota)).toBeTruthy();
    expect(within(p).getByText(t.suscribirCanalNota.android)).toBeTruthy();
    expect(within(p).queryByText(/No app yet/)).toBeNull();
    expect(p.querySelector("img")).toBeNull();
    fireEvent.change(within(p).getByRole("combobox", { name: "Channel" }), { target: { value: "drones-france" } });
    expect(within(p).getByRole("link", { name: t.suscribirCanal }).getAttribute("href")).toBe(
      "ntfy://ntfy.droneobservatory.eu/drones-france?display=EODI+%C2%B7+France",
    );
    expect(within(p).getByRole("link", { name: "More help" }).getAttribute("href")).toBe("/en/alerts");
  });

  it("en iPhone, 1 a la App Store y 2 con los pasos y el servidor y el canal para copiar, sin QR", () => {
    render(<Avisos idioma="es" dispositivo="iphone" />);
    const p = panel();
    const t = TEXTO_AVISOS.es;
    expect(within(p).getByRole("link", { name: "1. Instala la aplicación ntfy" }).getAttribute("href")).toBe(TIENDAS.appStore);
    expect(within(p).getByText("Gratis. Si ya la tienes, pasa al paso 2.")).toBeTruthy();
    const segundo = p.querySelector("[data-paso-telefono='2']") as HTMLElement;
    expect(within(segundo).getByRole("heading", { name: "2. Suscríbete al canal" })).toBeTruthy();
    expect(within(segundo).getByText("Si acabas de instalarla, vuelve aquí.")).toBeTruthy();
    expect(segundo.querySelectorAll("ol > li")).toHaveLength(t.pasos.iphone("drones-europe").length);
    expect(within(segundo).getByRole("button", { name: "Copiar el servidor" })).toBeTruthy();
    expect(within(segundo).getByRole("button", { name: "Copiar el canal" })).toBeTruthy();
    expect(within(segundo).getByText("drones-europe", { selector: "code" })).toBeTruthy();
    expect(p.querySelector("img")).toBeNull();
  });

  it("recuerda el último canal elegido en este navegador y no guarda nada sin elegir", () => {
    const { unmount } = render(<Avisos idioma="es" dispositivo="android" />);
    expect(window.localStorage.getItem(CLAVE_CANAL)).toBeNull();
    fireEvent.change(within(panel()).getByRole("combobox", { name: "Canal" }), { target: { value: "drones-poland" } });
    expect(window.localStorage.getItem(CLAVE_CANAL)).toBe("drones-poland");
    unmount();
    render(<Avisos idioma="en" dispositivo="ordenador" />);
    expect((within(panel()).getByRole("combobox", { name: "Channel" }) as HTMLSelectElement).value).toBe("drones-poland");
    cleanup();
    // Un canal que ya no existe no rompe nada: toda Europa.
    window.localStorage.setItem(CLAVE_CANAL, "drones-atlantida");
    render(<Avisos idioma="es" dispositivo="iphone" />);
    expect((within(panel()).getByRole("combobox", { name: "Canal" }) as HTMLSelectElement).value).toBe("drones-europe");
  });
});
