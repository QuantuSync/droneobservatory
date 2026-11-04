// La caché del mapa de fondo de los recorridos (e2e/teselas.ts y e2e/base.ts): qué trozo es cada
// petición, qué se guarda, cuándo se recorta; que ninguna prueba se la salte importando `test` de
// @playwright/test, y que los navegadores de las pruebas se identifiquen sin dejar de ser el
// dispositivo que son (src/avisos.ts).

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { SUFIJO_AGENTE } from "../e2e/agente.ts";
import {
  CARPETAS_PUBLICAS,
  OBJETIVO_BYTES,
  OBJETIVO_FIJOS_BYTES,
  PUBLICOS_SUELTOS,
  TOPE_BYTES,
  TOPE_FIJOS_BYTES,
  cabecerasAGuardar,
  claveDePublico,
  codigoGuardable,
  fijoDe,
  sobrantes,
  trozoDe,
} from "../e2e/teselas.ts";
import configuracion from "../playwright.config.ts";
import { dispositivoDe } from "../src/avisos.ts";

const E2E = join(import.meta.dirname, "..", "e2e");
const MB = 1024 * 1024;

describe("trozo del mapa de fondo", () => {
  it("por la web: la clave son o y l, y se responde con 200", () => {
    expect(trozoDe("https://droneobservatory.eu/almacen/europa-z14.pmtiles?o=0&l=127", undefined)).toEqual({
      camino: "web",
      clave: "web-o0-l127",
      estado: 200,
    });
    expect(trozoDe("https://vista-previa.vercel.app/almacen/europa-z14.pmtiles?l=16384&o=99", "bytes=1-2")?.clave).toBe(
      "web-o99-l16384",
    );
  });

  it("directo al almacén (principal o reserva): la clave es el rango, y se responde con 206", () => {
    for (const origen of [
      "https://droneobservatory-almacen.nbg1.your-objectstorage.com",
      "https://droneobservatory-reserva.hel1.your-objectstorage.com",
    ]) {
      expect(trozoDe(`${origen}/europa-z14.pmtiles`, "bytes=127-16510")).toEqual({
        camino: "almacen",
        clave: "rango-127-16510",
        estado: 206,
      });
    }
  });

  it("lo que no es un trozo conocido va a la red", () => {
    expect(trozoDe("https://droneobservatory.eu/almacen/europa-z14.pmtiles", undefined)).toBeNull();
    expect(trozoDe("https://droneobservatory.eu/almacen/europa-z14.pmtiles?o=../x&l=1", undefined)).toBeNull();
    expect(trozoDe("https://droneobservatory.eu/almacen/estado.json", undefined)).toBeNull();
    expect(trozoDe("https://droneobservatory-almacen.nbg1.your-objectstorage.com/europa-z14.pmtiles", undefined)).toBeNull();
    expect(trozoDe("https://droneobservatory-almacen.nbg1.your-objectstorage.com/europa-z14.pmtiles", "bytes=0-")).toBeNull();
    expect(trozoDe("https://droneobservatory-almacen.nbg1.your-objectstorage.com/estado.json", "bytes=0-9")).toBeNull();
    expect(trozoDe("https://otro.example/europa-z14.pmtiles", "bytes=0-9")).toBeNull();
    expect(trozoDe("no es una dirección", undefined)).toBeNull();
  });

  it("el nombre del fichero es seguro: solo letras, números y guiones", () => {
    const t = trozoDe("https://droneobservatory.eu/almacen/europa-z14.pmtiles?o=123456789012&l=7", undefined);
    expect(t?.clave).toMatch(/^[a-z0-9-]+$/);
    expect(trozoDe("https://droneobservatory.eu/almacen/europa-z14.pmtiles?o=1234567890123&l=7", undefined)).toBeNull();
  });
});

describe("cabeceras guardadas", () => {
  it("solo las del contenido y la caché, en minúsculas", () => {
    expect(
      cabecerasAGuardar({
        "Content-Type": "application/octet-stream",
        ETag: '"abc"',
        "content-range": "bytes 0-126/24600000000",
        "accept-ranges": "bytes",
        "cache-control": "public, max-age=31536000",
        "access-control-allow-origin": "https://droneobservatory.eu",
        "set-cookie": "x=1",
        date: "Tue, 27 Oct 2026 13:00:00 GMT",
        "x-vercel-cache": "HIT",
      }),
    ).toEqual({
      "content-type": "application/octet-stream",
      etag: '"abc"',
      "content-range": "bytes 0-126/24600000000",
      "accept-ranges": "bytes",
      "cache-control": "public, max-age=31536000",
      "access-control-allow-origin": "https://droneobservatory.eu",
    });
  });
});

describe("recorte de la caché", () => {
  it("por debajo del tope no se quita nada", () => {
    expect(sobrantes([{ nombre: "a", bytes: TOPE_BYTES, fecha: 1 }])).toEqual([]);
  });

  it("por encima, se quita lo más antiguo hasta bajar del objetivo", () => {
    const ficheros = [
      { nombre: "nuevo", bytes: 100 * MB, fecha: 3 },
      { nombre: "viejo", bytes: 150 * MB, fecha: 1 },
      { nombre: "medio", bytes: 100 * MB, fecha: 2 },
    ];
    const fuera = sobrantes(ficheros);
    expect(fuera).toEqual(["viejo", "medio"]);
    const queda = ficheros.filter((f) => !fuera.includes(f.nombre)).reduce((s, f) => s + f.bytes, 0);
    expect(queda).toBeLessThan(OBJETIVO_BYTES);
  });
});

describe("ficheros fijos de la web", () => {
  const SITIO = "droneobservatory.eu";
  const web = (camino: string) => `https://${SITIO}${camino}`;
  const PUBLICA = join(import.meta.dirname, "..", "public");

  it("el código con huella en el nombre: la clave es el nombre", () => {
    expect(fijoDe(web("/assets/app-DuKEQFg-.js"), SITIO)).toEqual({
      tipo: "codigo",
      camino: "/assets/app-DuKEQFg-.js",
      clave: "codigo-app-DuKEQFg-_js",
    });
    expect(fijoDe(web("/assets/onest-latin-wght-normal-Dun_Rd-l.woff2"), SITIO)?.tipo).toBe("codigo");
    // Los scripts de scripts/paginas.ts: huella sha256 de 12 caracteres.
    expect(fijoDe(web("/assets/estado-6e706d9ba6da.js"), SITIO)?.clave).toBe("codigo-estado-6e706d9ba6da_js");
  });

  it("sin huella clara, con parámetros o de otro sitio, a la red", () => {
    for (const camino of [
      "/assets/build-viejo.js",
      "/assets/estilo-principal.js",
      "/assets/graficos-abcdefgh.js",
      "/assets/app-DuKEQFg-.js?reintento=1",
      "/assets/app.js",
      "/assets/../datos/app-DuKEQFg-.js",
    ]) {
      expect(fijoDe(web(camino), SITIO), camino).toBeNull();
    }
    expect(fijoDe("https://otro.example/assets/app-DuKEQFg-.js", SITIO)).toBeNull();
    expect(fijoDe("no es una dirección", SITIO)).toBeNull();
  });

  it("los ficheros públicos del mapa, la marca, las banderas y los iconos, sin clave propia", () => {
    for (const camino of ["/mapa/paises.geojson", "/mapa/sprites/dark.json", "/iconos/icono-192.png"]) {
      expect(fijoDe(web(camino), SITIO), camino).toEqual({ tipo: "publico", camino });
    }
    // Las fuentes, en carpetas con espacios: el camino es el del fichero.
    expect(fijoDe(web("/mapa/fuentes/Noto%20Sans%20Regular/0-255.pbf"), SITIO)).toEqual({
      tipo: "publico",
      camino: "/mapa/fuentes/Noto Sans Regular/0-255.pbf",
    });
    expect(fijoDe(web("/mapa/%2e%2e/datos/resumen.json"), SITIO)).toBeNull();
    expect(fijoDe(web("/mapa/%ZZ.json"), SITIO)).toBeNull();
    expect(fijoDe(web("/banderas/ua.svg"), SITIO)).toEqual({ tipo: "publico", camino: "/banderas/ua.svg" });
    expect(fijoDe(web("/favicon.svg"), SITIO)?.tipo).toBe("publico");
    for (const camino of ["/mapa/", "/datos/resumen.json", "/sw.js", "/manifest.webmanifest", "/", "/EODI-2026-00057"]) {
      expect(fijoDe(web(camino), SITIO), camino).toBeNull();
    }
  });

  it("cada carpeta y fichero público existe en web/public", () => {
    for (const carpeta of CARPETAS_PUBLICAS) expect(readdirSync(join(PUBLICA, carpeta)).length, carpeta).toBeGreaterThan(0);
    for (const fichero of PUBLICOS_SUELTOS) expect(readFileSync(join(PUBLICA, fichero)).length, fichero).toBeGreaterThan(0);
  });

  it("la clave de un público es su huella; el código solo se guarda si no es una página", () => {
    expect(claveDePublico("a".repeat(64))).toBe(`publico-${"a".repeat(64)}`);
    expect(codigoGuardable(200, { "Content-Type": "text/javascript; charset=utf-8" })).toBe(true);
    expect(codigoGuardable(200, { "content-type": "text/html; charset=utf-8" })).toBe(false);
    expect(codigoGuardable(200, {})).toBe(false);
    expect(codigoGuardable(404, { "content-type": "text/javascript" })).toBe(false);
    expect(TOPE_FIJOS_BYTES).toBeGreaterThan(OBJETIVO_FIJOS_BYTES);
  });
});

describe("las pruebas de la web usan la caché", () => {
  it("ningún e2e/*.spec.ts importa `test` ni `expect` de @playwright/test (solo tipos)", () => {
    const especificaciones = readdirSync(E2E).filter((n) => n.endsWith(".spec.ts"));
    expect(especificaciones.length).toBeGreaterThan(10);
    for (const nombre of especificaciones) {
      const texto = readFileSync(join(E2E, nombre), "utf8");
      for (const m of texto.matchAll(/import\s+(type\s+)?\{([^}]*)\}\s+from\s+["']@playwright\/test["']/g)) {
        if (m[1] !== undefined) continue;
        const nombres = (m[2] ?? "").split(",").map((x) => x.trim().replace(/^type\s+/, ""));
        expect(nombres, nombre).not.toContain("test");
        expect(nombres, nombre).not.toContain("expect");
      }
      expect(texto, nombre).toMatch(/from "\.\/base\.ts"/);
    }
  });
});

describe("agente de usuario de las pruebas", () => {
  const esperado: Record<string, string> = {
    escritorio: "ordenador",
    movil: "android",
    android: "android",
    iphone: "iphone",
    tableta: "android",
    "escritorio-chromium": "ordenador",
    "escritorio-webkit": "ordenador",
  };

  it("cada proyecto lleva el sufijo y sigue siendo el dispositivo que es", () => {
    const proyectos = configuracion.projects ?? [];
    expect(proyectos.map((p) => p.name).sort()).toEqual(Object.keys(esperado).sort());
    for (const p of proyectos) {
      const agente = p.use?.userAgent ?? "";
      expect(agente.endsWith(SUFIJO_AGENTE), p.name).toBe(true);
      expect(agente.length, p.name).toBeGreaterThan(SUFIJO_AGENTE.length + 20);
      expect(dispositivoDe(agente, p.use?.hasTouch === true ? 5 : 0), p.name).toBe(esperado[p.name ?? ""]);
    }
  });
});
