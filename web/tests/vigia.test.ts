// El disparador de la vigilancia en Vercel (../../api/vigia.ts).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ALMACEN, diagnosticar, GET, horaria } from "../../api/vigia.ts";

const AHORA = Date.parse("2026-10-07T18:00:00Z");
const hace = (min: number) => new Date(AHORA - min * 60_000).toISOString();

describe("disparador de la vigilancia", () => {
  it("la dirección del almacén es la de la configuración", () => {
    const configuracion = JSON.parse(
      readFileSync(join(import.meta.dirname, "..", "..", "configuracion", "almacen_publico.json"), "utf-8"),
    ) as { publico: string };
    expect(ALMACEN).toBe(configuracion.publico);
  });

  it("todo bien: no avisa", () => {
    const d = diagnosticar({ generado: hace(4), problemas: [] }, { generado: hace(1) }, AHORA);
    expect(d).toEqual({ problema: false, motivos: [] });
  });

  it("un problema, un servidor callado o la detección parada avisan", () => {
    expect(diagnosticar({ generado: hace(4), problemas: [{ id: "disco" }] }, { generado: hace(1) }, AHORA).motivos).toEqual([
      "problema: disco",
    ]);
    expect(diagnosticar({ generado: hace(25), problemas: [] }, { generado: hace(1) }, AHORA).problema).toBe(true);
    expect(diagnosticar(null, null, AHORA).motivos).toHaveLength(2);
    expect(diagnosticar({ generado: hace(4), problemas: [] }, { generado: hace(45) }, AHORA).problema).toBe(true);
  });

  it("la web atrasada respecto a la última publicación avisa", () => {
    const salud = { generado: hace(4), problemas: [], recogida: { ultima_publicacion: hace(10) } };
    expect(diagnosticar(salud, { generado: hace(1) }, AHORA, { actualizado: hace(26) }).problema).toBe(false);
    expect(diagnosticar(salud, { generado: hace(1) }, AHORA, { actualizado: hace(140) }).motivos).toEqual([
      "la web no se actualiza (sus datos van más de 100 minutos por detrás de la última publicación)",
    ]);
  });

  it("sin problema lanza el vigía una vez por hora, para que cierre las incidencias", () => {
    expect(horaria(new Date("2026-10-08T07:00:50Z"))).toBe(true);
    expect(horaria(new Date("2026-10-08T07:10:50Z"))).toBe(false);
  });

  it("sin el secreto de la tarea programada no hace nada", async () => {
    const respuesta = await GET(new Request("https://x/api/vigia"));
    expect(respuesta.status).toBe(401);
  });
});
