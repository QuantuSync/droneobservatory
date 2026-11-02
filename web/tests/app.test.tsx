// La app instalable: el punto de instalación, dónde se registra el service worker, qué manda
// guardar la página, la barra «Sin conexión», los manifiestos de cada idioma y las visitas.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { esIos, modoDeInstalacion } from "../src/app/instalar.ts";
import type { Entorno } from "../src/app/instalar.ts";
import { direccionesAGuardar, sitioConApp } from "../src/app/registro.ts";
import { BarraEstado, textoSinConexion } from "../src/componentes/BarraEstado.tsx";
import { InstalarApp } from "../src/componentes/InstalarApp.tsx";
import { MANIFIESTOS, etiquetasDeCabecera } from "../src/cabecera.ts";
import { textos } from "../src/i18n/index.ts";
import { refrescarAlaVista } from "../src/tiempo/refresco.ts";

const PUBLICA = join(import.meta.dirname, "..", "public");
const ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36";
const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const IPAD = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";

const base: Entorno = { abiertaComoApp: false, hayAviso: false, instalada: false, agente: ANDROID, puntosTactiles: 5 };

describe("punto de instalación", () => {
  it("Android y escritorio: el diálogo del navegador solo cuando el navegador lo ofrece", () => {
    expect(modoDeInstalacion(base)).toBeNull();
    expect(modoDeInstalacion({ ...base, hayAviso: true })).toBe("nativo");
  });

  it("iPhone y iPad: los dos pasos de Safari", () => {
    expect(modoDeInstalacion({ ...base, agente: IPHONE })).toBe("iphone");
    expect(modoDeInstalacion({ ...base, agente: IPAD, puntosTactiles: 5 })).toBe("iphone");
    expect(esIos(IPAD, 0)).toBe(false);
  });

  it("desaparece con la app instalada o abierta desde su icono", () => {
    expect(modoDeInstalacion({ ...base, hayAviso: true, abiertaComoApp: true })).toBeNull();
    expect(modoDeInstalacion({ ...base, agente: IPHONE, abiertaComoApp: true })).toBeNull();
    expect(modoDeInstalacion({ ...base, hayAviso: true, instalada: true })).toBeNull();
  });

  it("en el prerenderizado no se pinta (sin banners ni nada que tape)", () => {
    expect(renderToString(<InstalarApp t={textos("es")} grande />)).toBe("");
  });

  it("textos en los dos idiomas", () => {
    expect(textos("es").app.instalar).toBe("Instalar la app");
    expect(textos("en").app.instalar).toBe("Install the app");
    expect(textos("es").app.versionNueva).toBe("Hay una versión nueva");
  });
});

describe("registro del service worker", () => {
  it("solo en droneobservatory.eu y en sus vistas previas", () => {
    expect(sitioConApp("droneobservatory.eu")).toBe(true);
    expect(sitioConApp("www.droneobservatory.eu")).toBe(true);
    expect(sitioConApp("droneobservatory-git-app-1102-lucas-projects-cc09a9dd.vercel.app")).toBe(true);
    expect(sitioConApp("droneobservatory-osr083zai-lucas-projects-cc09a9dd.vercel.app")).toBe(true);
    expect(sitioConApp("droneobservatory-abc123.vercel.app")).toBe(false);
    expect(sitioConApp("localhost")).toBe(false);
    expect(sitioConApp("otro.vercel.app")).toBe(false);
    expect(sitioConApp("droneobservatory.eu.ejemplo.com")).toBe(false);
  });

  it("manda guardar lo ya descargado de la web y la página, nunca /almacen/, /api/ ni otros sitios", () => {
    const origen = "https://droneobservatory.eu";
    const lista = direccionesAGuardar(
      [
        `${origen}/assets/index-1.js`,
        `${origen}/datos/resumen.json`,
        `${origen}/mapa/tierra.geojson`,
        `${origen}/almacen/europa-z14.pmtiles`,
        `${origen}/api/almacen?objeto=estado.json`,
        `${origen}/datos/versiones/2026-10/incidentes.csv`,
        "https://stats.droneobservatory.eu/count",
        "https://droneobservatory-reserva.hel1.your-objectstorage.com/estado.json",
        "no es una dirección",
      ],
      origen,
      "/en/EODI-2025-00001",
    );
    expect(lista).toEqual(["/en/EODI-2025-00001#pagina", "/assets/index-1.js", "/datos/resumen.json", "/mapa/tierra.geojson"]);
  });

  it("public/sw.js existe y la política de contenido no se ha ampliado", () => {
    expect(readFileSync(join(PUBLICA, "sw.js"), "utf8")).toContain('addEventListener("fetch"');
    const vercel = readFileSync(join(import.meta.dirname, "..", "..", "vercel.json"), "utf8");
    expect(vercel).toContain("worker-src 'self';");
  });
});

describe("sin conexión", () => {
  const t = textos("es");

  it("«Sin conexión · datos de las 12:17 UTC» en lugar del punto verde", () => {
    const ahora = new Date("2026-11-02T12:40:00Z");
    expect(textoSinConexion(t, "2026-11-02T12:17:00Z", ahora)).toBe("Sin conexión · datos de las 12:17 UTC");
    expect(textoSinConexion(textos("en"), "2026-11-02T12:17:00Z", ahora)).toBe("Offline · data from 12:17 UTC");
    expect(textoSinConexion(t, "2026-11-01T22:17:00Z", ahora)).toContain("Sin conexión · datos del ");
    const html = renderToString(
      <BarraEstado t={t} actualizado="2026-11-02T12:17:00Z" sistema={null} ahora={ahora} sinConexion />,
    );
    expect(html).toContain("data-sin-conexion");
    expect(html).toContain("Sin conexión · datos de las 12:17 UTC");
    expect(html).not.toContain("bg-al-dia");
  });

  it("al volver la conexión, los datos se piden solos", () => {
    const oyentes = new Map<string, () => void>();
    vi.stubGlobal("addEventListener", (tipo: string, oyente: () => void) => {
      oyentes.set(tipo, oyente);
    });
    vi.stubGlobal("removeEventListener", (tipo: string) => {
      oyentes.delete(tipo);
    });
    const pedir = vi.fn();
    const parar = refrescarAlaVista(
      pedir,
      600_000,
      { visibilityState: "visible", addEventListener: () => undefined, removeEventListener: () => undefined },
      { ahora: () => 0, cada: () => 1, parar: () => undefined },
    );
    expect(pedir).toHaveBeenCalledTimes(1);
    oyentes.get("online")?.();
    expect(pedir).toHaveBeenCalledTimes(2);
    parar();
    expect(oyentes.has("online")).toBe(false);
    vi.unstubAllGlobals();
  });
});

describe("manifiestos", () => {
  it.each([
    ["es", "/manifest.webmanifest", "/", "Observatorio Europeo de Incidentes con Drones"],
    ["en", "/manifest-en.webmanifest", "/en", "European Observatory of Drone Incidents"],
  ] as const)("%s: standalone, id, scope, portada del idioma e iconos", (idioma, ruta, inicio, nombre) => {
    expect(MANIFIESTOS[idioma]).toBe(ruta);
    const m = JSON.parse(readFileSync(join(PUBLICA, ruta.slice(1)), "utf8")) as {
      id: string;
      name: string;
      lang: string;
      start_url: string;
      scope: string;
      display: string;
      icons: { src: string; sizes: string; purpose?: string }[];
    };
    expect(m.display).toBe("standalone");
    expect(m.id).toBe(inicio);
    expect(m.start_url).toBe(inicio);
    expect(m.scope).toBe("/");
    expect(m.lang).toBe(idioma);
    expect(m.name).toBe(nombre);
    expect(m.icons.some((i) => i.sizes === "192x192")).toBe(true);
    expect(m.icons.some((i) => i.sizes === "512x512" && i.purpose === "maskable")).toBe(true);
    for (const icono of m.icons) expect(readFileSync(join(PUBLICA, icono.src.slice(1))).length).toBeGreaterThan(0);
    const cabecera = etiquetasDeCabecera({ idioma, id: null, titulo: "x", descripcion: "y" } as never);
    expect(cabecera).toContain(`<link rel="manifest" href="${ruta}">`);
  });

  it("la página sin barra del navegador en el iPhone, sin el manifiesto fijo en la plantilla", () => {
    const html = readFileSync(join(import.meta.dirname, "..", "index.html"), "utf8");
    expect(html).toContain('name="apple-mobile-web-app-capable" content="yes"');
    expect(html).toContain("viewport-fit=cover");
    expect(html).not.toContain('rel="manifest"');
  });
});

describe("visitas", () => {
  it("la app instalada se marca con utm_source=app y sin conexión no se cuenta", () => {
    const codigo = readFileSync(join(PUBLICA, "visitas.js"), "utf8");
    expect(codigo).toContain('"(display-mode: standalone)"');
    expect(codigo).toContain('quedan.append("utm_source", "app")');
    expect(codigo).toContain("navigator.onLine === false");
  });
});

describe("capturas del diálogo de instalación", () => {
  it.each(["manifest.webmanifest", "manifest-en.webmanifest"])("%s: una estrecha y una ancha, con su tamaño real", (fichero) => {
    const m = JSON.parse(readFileSync(join(PUBLICA, fichero), "utf8")) as {
      screenshots: { src: string; sizes: string; form_factor: string }[];
    };
    expect(m.screenshots.map((c) => c.form_factor).sort()).toEqual(["narrow", "wide"]);
    for (const c of m.screenshots) {
      const png = readFileSync(join(PUBLICA, c.src.slice(1)));
      expect(`${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`).toBe(c.sizes);
    }
  });
});
