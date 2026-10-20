// El disparador de la vigilancia en Vercel (../../api/vigia.ts).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ALMACEN, decidirLanzar, diagnosticar, GET, horaria } from "../../api/vigia.ts";

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

  it("la web atrasada respecto a la última reconstrucción pedida avisa", () => {
    const salud = (reconstruccion: number, pendiente: number | null = null) => ({
      generado: hace(4),
      problemas: [],
      recogida: {
        ultima_publicacion: hace(10),
        ultima_reconstruccion: hace(reconstruccion),
        reconstruccion_pendiente_desde: pendiente === null ? null : hace(pendiente),
      },
    });
    const directo = { generado: hace(1) };
    // Lo no urgente se construye cada 3 horas: unos datos de hace 2 horas y media están bien.
    expect(diagnosticar(salud(150, 120), directo, AHORA, { actualizado: hace(170) }).problema).toBe(false);
    // Recién pedida, aún construyendo: no avisa.
    expect(diagnosticar(salud(5), directo, AHORA, { actualizado: hace(200) }).problema).toBe(false);
    expect(diagnosticar(salud(30), directo, AHORA, { actualizado: hace(200) }).motivos).toEqual([
      "la web no se actualiza (sus datos van más de 100 minutos por detrás de la última reconstrucción pedida)",
    ]);
    expect(diagnosticar(salud(300, 250), directo, AHORA, { actualizado: hace(320) }).motivos).toEqual([
      "la web lleva más de 4 horas con datos publicados sin reconstruir",
    ]);
  });

  it("sin la última reconstrucción, mide desde la última publicación con 260 minutos", () => {
    const salud = { generado: hace(4), problemas: [], recogida: { ultima_publicacion: hace(10) } };
    expect(diagnosticar(salud, { generado: hace(1) }, AHORA, { actualizado: hace(190) }).problema).toBe(false);
    expect(diagnosticar(salud, { generado: hace(1) }, AHORA, { actualizado: hace(300) }).motivos).toEqual([
      "la web no se actualiza (sus datos van más de 260 minutos por detrás de la última publicación)",
    ]);
  });

  it("sin problema lanza el vigía una vez por hora, para que cierre las incidencias", () => {
    expect(horaria(new Date("2026-10-08T07:00:50Z"))).toBe(true);
    expect(horaria(new Date("2026-10-08T07:10:50Z"))).toBe(false);
  });

  it("lanza también con una incidencia abierta o una pasada perdida", () => {
    const bien = { problema: false, motivos: [] };
    const a = new Date("2026-10-20T07:40:20Z");
    const hora = (iso: string) => Date.parse(iso);
    expect(decidirLanzar(bien, a, hora("2026-10-20T07:30:30Z"), [])).toEqual({ lanzar: false, motivo: "no hace falta" });
    expect(decidirLanzar(bien, a, hora("2026-10-20T07:30:30Z"), ["El servidor del observatorio necesita atención"]).lanzar).toBe(true);
    expect(decidirLanzar(bien, a, hora("2026-10-20T07:30:30Z"), ["Otra incidencia cualquiera"]).lanzar).toBe(false);
    expect(decidirLanzar(bien, a, hora("2026-10-20T06:30:00Z"), [])).toEqual({
      lanzar: true,
      motivo: "recupera una pasada perdida",
    });
    expect(decidirLanzar({ problema: true, motivos: ["x"] }, a, null, []).motivo).toBe("problema");
  });

  it("sin el secreto de la tarea programada no hace nada", async () => {
    const respuesta = await GET(new Request("https://x/api/vigia"));
    expect(respuesta.status).toBe(401);
  });
});
