// @vitest-environment jsdom
// Nada de lo que la web pide se rinde a la primera (src/datos/reintentos.ts): fallos pasajeros
// que se recuperan solos, el error con «Reintentar» cuando no, la última previsión con su fecha y
// los campos nuevos de los datos que no rompen una pestaña abierta con una versión anterior.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Prevision } from "../src/componentes/Prevision.tsx";
import { cargarPrevision, cargarResumen, URL_PREVISION_ALMACEN } from "../src/datos/carga.ts";
import { resumir } from "../src/datos/derivar.ts";
import type { Prevision as DatosPrevision } from "../src/datos/prevision.ts";
import { descargarConReintentos } from "../src/datos/reintentos.ts";
import { tolerarCamposNuevos, validarPrevision } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { incidente, coleccion } from "./ejemplos.ts";

afterEach(() => {
  cleanup();
  tolerarCamposNuevos(false);
});

const es = textos("es");
const en = textos("en");

function prevision(): DatosPrevision {
  const ruta = join(__dirname, "..", "..", "tests", "fixtures", "publicacion", "prevision.json");
  const resultado = validarPrevision(JSON.parse(readFileSync(ruta, "utf-8")));
  if (!resultado.ok) throw new Error(resultado.errores.join("; "));
  return resultado.datos;
}

/** Una descarga que responde, por orden, lo que se le da: un número es un estado HTTP sin cuerpo,
 * «red» es un corte de la conexión y un objeto es un 200 con ese JSON. */
function secuencia(...respuestas: (number | "red" | object)[]) {
  const pedidas: { url: string; cache: RequestCache | undefined }[] = [];
  const descargar = ((url: string, opciones?: RequestInit) => {
    pedidas.push({ url, cache: opciones?.cache });
    const r = respuestas.shift() ?? 500;
    if (r === "red") return Promise.reject(new TypeError("Failed to fetch"));
    if (typeof r === "number") return Promise.resolve(new Response("", { status: r }));
    return Promise.resolve(new Response(JSON.stringify(r), { status: 200 }));
  }) as typeof fetch;
  return { descargar, pedidas };
}

describe("reintentos", () => {
  it("un error del servidor y un corte de la red no se ven: a la tercera, el fichero", async () => {
    const resumen = resumir(coleccion([incidente()]), { ataques: [] } as never);
    const { descargar, pedidas } = secuencia(503, "red", resumen);
    await expect(cargarResumen(descargar)).resolves.toEqual({ estado: "listo", datos: resumen });
    expect(pedidas).toHaveLength(3);
    // Desde el segundo intento, sin la caché del navegador.
    expect(pedidas.map((p) => p.cache)).toEqual([undefined, "no-cache", "no-cache"]);
  });

  it("lo que no existe no se reintenta; lo que no responde, cinco veces antes del error", async () => {
    const noExiste = secuencia(404);
    await expect(cargarResumen(noExiste.descargar)).resolves.toEqual({ estado: "no_encontrado" });
    expect(noExiste.pedidas).toHaveLength(1);
    const caido = secuencia();
    await expect(cargarResumen(caido.descargar)).resolves.toEqual({ estado: "no_disponible" });
    expect(caido.pedidas).toHaveLength(5);
  });

  it("la previsión, si la de la web no llega, se pide al almacén público", async () => {
    const d = prevision();
    const { descargar, pedidas } = secuencia(500, 500, 500, 500, 500, d);
    await expect(cargarPrevision(descargar)).resolves.toEqual({ estado: "listo", datos: d });
    expect(pedidas.at(-1)?.url).toBe(URL_PREVISION_ALMACEN);
  });

  it("descargarConReintentos reintenta los 5xx y no los 404", async () => {
    const original = globalThis.fetch;
    const respuestas = [new Response("", { status: 502 }), new Response("{}", { status: 200 })];
    globalThis.fetch = vi.fn(() => Promise.resolve(respuestas.shift() ?? new Response("", { status: 404 }))) as typeof fetch;
    try {
      const r = await descargarConReintentos("/x.json");
      expect(r.status).toBe(200);
      expect(await r.json()).toEqual({});
      expect((await descargarConReintentos("/y.json")).status).toBe(404);
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe("campos nuevos en los datos", () => {
  it("en el navegador no invalidan un fichero; en el build, sí", () => {
    const conCamposNuevos = { ...prevision(), campoFuturo: 1, frontera: { ...prevision().frontera, otroCampo: "x" } };
    expect(validarPrevision(conCamposNuevos).ok).toBe(false);
    tolerarCamposNuevos();
    expect(validarPrevision(conCamposNuevos).ok).toBe(true);
    // Lo que sí falta o está mal sigue sin valer.
    const { frontera: _, ...sinFrontera } = prevision();
    expect(validarPrevision(sinFrontera).ok).toBe(false);
  });
});

describe("«Previsión» cuando no llega", () => {
  it("sin ninguna anterior: qué pasa y «Reintentar», en los dos idiomas", async () => {
    const reintentar = vi.fn();
    render(<Prevision t={es} idioma="es" carga={{ estado: "no_disponible" }} onReintentar={reintentar} onRacha={() => undefined} />);
    const alerta = screen.getByRole("alert");
    expect(alerta.textContent).toContain("No se ha podido cargar la previsión.");
    expect(alerta.textContent).toContain(es.avisos.sinRespuesta);
    await userEvent.setup().click(screen.getByRole("button", { name: "Reintentar" }));
    expect(reintentar).toHaveBeenCalledOnce();
    cleanup();
    render(<Prevision t={en} idioma="en" carga={{ estado: "no_disponible" }} onRacha={() => undefined} />);
    expect(screen.getByRole("alert").textContent).toContain("The forecast could not be loaded.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("con una anterior: la enseña con su fecha, en vez de un error", () => {
    const d = prevision();
    render(<Prevision t={es} idioma="es" carga={{ estado: "no_disponible" }} anterior={d} onRacha={() => undefined} />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.querySelector("[data-prevision]")).not.toBeNull();
    const nota = document.querySelector("[data-prevision-anterior]")?.textContent ?? "";
    expect(nota).toContain("Esta es la última que hay, calculada el");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeTruthy();
  });

  it("mientras carga una nueva, sigue a la vista la anterior, sin aviso", () => {
    render(<Prevision t={es} idioma="es" carga={{ estado: "cargando" }} anterior={prevision()} onRacha={() => undefined} />);
    expect(document.querySelector("[data-prevision]")).not.toBeNull();
    expect(document.querySelector("[data-prevision-anterior]")).toBeNull();
  });
});
