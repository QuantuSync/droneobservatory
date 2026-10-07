import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { descargar } from "../scripts/publicacion.ts";

const BASE = "https://almacen.example";
const codificar = (texto: string) => new TextEncoder().encode(texto);
const huella = (texto: string) => createHash("sha256").update(texto).digest("hex");

function almacen(objetos: Record<string, string>, fallos = 0) {
  let pendientes = fallos;
  const pedidas: string[] = [];
  const leer = (url: string): Promise<Uint8Array> => {
    pedidas.push(url);
    if (pendientes > 0) {
      pendientes--;
      return Promise.reject(new Error("HTTP 503"));
    }
    const clave = url.slice(BASE.length + 1);
    const valor = objetos[clave];
    return valor === undefined ? Promise.reject(new Error("HTTP 403")) : Promise.resolve(codificar(valor));
  };
  return { leer, pedidas };
}

function manifiesto(ficheros: Record<string, string>): string {
  return JSON.stringify({
    version: 1,
    generado: "2026-10-07T14:33:00Z",
    ficheros: Object.fromEntries(
      Object.entries(ficheros).map(([n, t]) => [n, { bytes: t.length, sha256: huella(t) }]),
    ),
  });
}

describe("datos publicados desde el almacén", () => {
  let destino = "";
  afterEach(() => rmSync(destino, { recursive: true, force: true }));

  it("baja cada fichero comprobado con el manifiesto", async () => {
    destino = mkdtempSync(join(tmpdir(), "publicacion-"));
    const ficheros = { "incidentes.geojson": '{"features": []}', "ucrania.json": '{"ataques": []}' };
    const { leer } = almacen({
      "publicacion/manifiesto.json": manifiesto(ficheros),
      "publicacion/incidentes.geojson": ficheros["incidentes.geojson"],
      "publicacion/ucrania.json": ficheros["ucrania.json"],
    });
    const leido = await descargar(BASE, destino, leer, 3, 0);
    expect(leido.generado).toBe("2026-10-07T14:33:00Z");
    expect(readFileSync(join(destino, "ucrania.json"), "utf-8")).toBe('{"ataques": []}');
  });

  it("reintenta un fallo pasajero", async () => {
    destino = mkdtempSync(join(tmpdir(), "publicacion-"));
    const ficheros = { "incidentes.geojson": "{}", "ucrania.json": "{}" };
    const { leer, pedidas } = almacen(
      {
        "publicacion/manifiesto.json": manifiesto(ficheros),
        "publicacion/incidentes.geojson": "{}",
        "publicacion/ucrania.json": "{}",
      },
      1,
    );
    await descargar(BASE, destino, leer, 3, 0);
    expect(pedidas.length).toBe(4);
  });

  it("falla si un fichero no cuadra con el manifiesto o si el almacén no responde", async () => {
    destino = mkdtempSync(join(tmpdir(), "publicacion-"));
    const ficheros = { "incidentes.geojson": "{}", "ucrania.json": "{}" };
    const mezclado = almacen({
      "publicacion/manifiesto.json": manifiesto(ficheros),
      "publicacion/incidentes.geojson": "{}",
      "publicacion/ucrania.json": '{"de otra recogida": true}',
    });
    await expect(descargar(BASE, destino, mezclado.leer, 2, 0)).rejects.toThrow(/sigue la versión anterior/);
    await expect(descargar(BASE, destino, almacen({}, 0).leer, 2, 0)).rejects.toThrow(/no se pudieron leer/);
  });
});
