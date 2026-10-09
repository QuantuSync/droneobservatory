// El almacén servido por la web (../../api/almacen.ts): qué se puede pedir, cuánto lo guarda la caché
// de Vercel, el paso a la copia de reserva cuando el principal no responde, y que sus direcciones
// son las de configuracion/almacen_publico.json. Y el lado del navegador: el mapa de fondo por
// trozos cacheables (mapa/reintentos.ts) y los ficheros del almacén con la reserva
// (datos/reintentos.ts).

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import { GET, OBJETO_TESELAS, ORIGENES, leerPedido, olvidarCaidas, segundosEnCache } from "../../api/almacen.ts";
import { ORIGEN_RESERVA, RUTA_ALMACEN, reservaDe, urlDelAlmacen } from "../src/almacenPublico.ts";
import { descargarConReintentos, fijarEsperas } from "../src/datos/reintentos.ts";
import { FuenteAlmacen } from "../src/mapa/reintentos.ts";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const configuracion = JSON.parse(readFileSync(join(RAIZ, "configuracion", "almacen_publico.json"), "utf-8")) as {
  publico: string;
  en_la_web: string;
  objetos: { teselas: string };
  reserva: { publico: string };
};
const vercel = JSON.parse(readFileSync(join(RAIZ, "vercel.json"), "utf-8")) as {
  rewrites: { source: string; destination: string }[];
  functions: Record<string, { regions?: string[] }>;
};
const [NBG, HEL] = [ORIGENES[0].url, ORIGENES[1].url];

function pedido(consulta: string, metodo = "GET"): Request {
  return new Request(`https://droneobservatory.eu/api/almacen?${consulta}`, { method: metodo });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  olvidarCaidas();
  fijarEsperas();
});

describe("la función del almacén", () => {
  it("usa las direcciones y el mapa de fondo de la configuración", () => {
    expect(NBG).toBe(configuracion.publico);
    expect(HEL).toBe(configuracion.reserva.publico);
    expect(OBJETO_TESELAS).toBe(configuracion.objetos.teselas);
    expect(RUTA_ALMACEN).toBe(configuracion.en_la_web);
    expect(vercel.rewrites).toContainEqual({ source: "/almacen/:objeto*", destination: "/api/almacen?objeto=:objeto*" });
    // Junto al almacén de Núremberg: el primer visitante de cada región tarda poco más.
    expect(vercel.functions["api/almacen.ts"]?.regions).toEqual(["fra1"]);
  });

  it("solo sirve los objetos que usa la web, y el mapa de fondo solo por trozos", () => {
    expect(leerPedido(new URL("https://x/api?objeto=estado.json"))).toEqual({ objeto: "estado.json", rango: null });
    expect(leerPedido(new URL("https://x/api?objeto=gnss/2026-10-09.json"))?.objeto).toBe("gnss/2026-10-09.json");
    expect(leerPedido(new URL("https://x/api?objeto=europa-z14.pmtiles&o=16384&l=3617"))).toEqual({
      objeto: "europa-z14.pmtiles",
      rango: { desde: 16384, largo: 3617 },
    });
    for (const malo of [
      "objeto=europa-z14.pmtiles",
      "objeto=europa-z14.pmtiles&o=0&l=999999999",
      "objeto=europa-z14.pmtiles&o=-1&l=10",
      "objeto=salud.json&o=0&l=10",
      "objeto=../secreto",
      "objeto=gnss/../../x",
      "objeto=otra-cosa.json",
      "objeto=",
    ]) {
      expect(leerPedido(new URL(`https://x/api?${malo}`)), malo).toBeNull();
    }
  });

  it("la caché guarda el mapa de fondo un año y lo que cambia cada minuto, segundos", () => {
    expect(segundosEnCache("europa-z14.pmtiles")).toBe(31_536_000);
    expect(segundosEnCache("directo.json")).toBe(30);
    expect(segundosEnCache("publicacion/prevision.json")).toBe(60);
    expect(segundosEnCache("gnss/indice.json")).toBe(300);
  });

  it("sirve un trozo con 200 y caché larga, pidiéndolo con Range al principal", async () => {
    const pedidos: [string, string | null][] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      pedidos.push([url, new Headers(init.headers).get("range")]);
      return Promise.resolve(new Response(new Uint8Array([1, 2, 3]), { status: 206 }));
    });
    const r = await GET(pedido("objeto=europa-z14.pmtiles&o=10&l=3"));
    expect(r.status).toBe(200);
    expect(new Uint8Array(await r.arrayBuffer())).toEqual(new Uint8Array([1, 2, 3]));
    expect(pedidos).toEqual([[`${NBG}/europa-z14.pmtiles`, "bytes=10-12"]]);
    expect(r.headers.get("cdn-cache-control")).toContain("max-age=31536000");
    expect(r.headers.get("x-almacen")).toBe("principal");
  });

  it("si el principal falla o no contesta, sirve la reserva y deja de insistir un rato", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    const pedidos: string[] = [];
    vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
      pedidos.push(url);
      if (url.startsWith(NBG)) {
        // El principal no contesta nunca: lo corta el tope.
        return new Promise((_hecho, fallo) => {
          init.signal?.addEventListener("abort", () => {
            fallo(new DOMException("corte", "AbortError"));
          });
        });
      }
      return Promise.resolve(new Response('{"ok":true}', { status: 200, headers: { "content-type": "application/json" } }));
    });
    const respuesta = GET(pedido("objeto=directo.json"));
    await vi.advanceTimersByTimeAsync(3100);
    const r = await respuesta;
    expect(r.status).toBe(200);
    expect(r.headers.get("x-almacen")).toBe("reserva");
    expect(r.headers.get("cdn-cache-control")).toContain("stale-if-error");
    expect(await r.text()).toBe('{"ok":true}');
    // El siguiente va directo a la reserva.
    await GET(pedido("objeto=estado.json"));
    expect(pedidos).toEqual([`${NBG}/directo.json`, `${HEL}/directo.json`, `${HEL}/estado.json`]);
  });

  it("si el principal da 503, va a la reserva; si ninguno responde, 502 sin guardar en caché", async () => {
    vi.stubGlobal("fetch", () => Promise.resolve(new Response("SlowDown", { status: 503 })));
    const r = await GET(pedido("objeto=estado.json"));
    expect(r.status).toBe(502);
    expect(r.headers.get("cdn-cache-control")).toBe("no-store");
  });

  it("lo que no existe da 404 (el almacén responde 403), tras preguntar a la reserva", async () => {
    const pedidos: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      pedidos.push(url);
      return Promise.resolve(new Response("AccessDenied", { status: 403 }));
    });
    const r = await GET(pedido("objeto=gnss/2020-01-01.json"));
    expect(r.status).toBe(404);
    expect(pedidos).toHaveLength(2);
    expect((await GET(pedido("objeto=nada"))).status).toBe(404);
  });

  it("un 200 a una petición por trozos (el fichero entero) no se sirve", async () => {
    let cancelados = 0;
    vi.stubGlobal("fetch", () => {
      const cuerpo = new ReadableStream({
        cancel() {
          cancelados += 1;
        },
      });
      return Promise.resolve(new Response(cuerpo, { status: 200 }));
    });
    const r = await GET(pedido("objeto=europa-z14.pmtiles&o=0&l=10"));
    expect(r.status).toBe(502);
    expect(cancelados).toBe(2);
  });
});

describe("el navegador y el almacén", () => {
  it("pide el almacén a la propia web y sabe dónde está cada objeto en la reserva", () => {
    expect(urlDelAlmacen("estado.json")).toBe("/almacen/estado.json");
    expect(reservaDe("/almacen/gnss/indice.json")).toBe(`${ORIGEN_RESERVA}/gnss/indice.json`);
    expect(reservaDe("/datos/resumen.json")).toBeNull();
    expect(reservaDe("https://otro.example/almacen/estado.json")).toBeNull();
  });

  it("un fichero del almacén que la web no sirve llega de la reserva", async () => {
    fijarEsperas([0, 0, 0, 0]);
    const pedidos: string[] = [];
    vi.stubGlobal("fetch", (url: string) => {
      pedidos.push(url);
      if (url.startsWith("/almacen/")) return Promise.resolve(new Response("", { status: 502 }));
      return Promise.resolve(new Response('{"de":"reserva"}', { status: 200 }));
    });
    const r = await descargarConReintentos("/almacen/directo.json");
    expect(await r.json()).toEqual({ de: "reserva" });
    expect(pedidos).toEqual(["/almacen/directo.json", `${ORIGEN_RESERVA}/directo.json`]);
  });

  it("el mapa de fondo se pide por trozos cacheables y, si la web falla, con Range a la reserva", async () => {
    const pedidos: [string, string | null][] = [];
    let webCaida = false;
    vi.stubGlobal("fetch", (entrada: string | Request, init?: RequestInit) => {
      const url = typeof entrada === "string" ? entrada : entrada.url;
      const rango = new Headers(typeof entrada === "string" ? init?.headers : entrada.headers).get("range");
      pedidos.push([url, rango]);
      if (url.startsWith("/almacen/")) {
        return Promise.resolve(webCaida ? new Response("", { status: 502 }) : new Response(new Uint8Array(4), { status: 200 }));
      }
      return Promise.resolve(
        new Response(new Uint8Array(4), { status: 206, headers: { "Content-Range": "bytes 100-103/1000" } }),
      );
    });
    const fuente = new FuenteAlmacen("europa-z14.pmtiles");
    expect(fuente.getKey()).toBe("/almacen/europa-z14.pmtiles");
    expect((await fuente.getBytes(100, 4)).data.byteLength).toBe(4);
    expect(pedidos.at(-1)).toEqual(["/almacen/europa-z14.pmtiles?o=100&l=4", null]);
    webCaida = true;
    expect((await fuente.getBytes(100, 4)).data.byteLength).toBe(4);
    expect(pedidos.at(-1)?.[0]).toBe(`${ORIGEN_RESERVA}/europa-z14.pmtiles`);
    expect(pedidos.at(-1)?.[1]).toBe("bytes=100-103");
    // Durante un rato, los siguientes van directos a la reserva.
    const antes = pedidos.length;
    await fuente.getBytes(200, 4);
    expect(pedidos.length).toBe(antes + 1);
    expect(pedidos.at(-1)?.[0]).toBe(`${ORIGEN_RESERVA}/europa-z14.pmtiles`);
  });
});
