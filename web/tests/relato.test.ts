// El párrafo de cada ficha (src/datos/relato.ts) con fichas reales publicadas (recortadas a las
// fuentes que usa su historial): qué pasó, cuándo, dónde, quién lo dijo, consecuencias y cómo consta
// hoy, en los dos idiomas; y que sin hora ni autoridad no se inventa ninguna de las dos.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { cuandoEscrito, estadoActual, estadoCorto, queDespues, relato, zonaDelSitio } from "../src/datos/relato.ts";
import type { IncidenteDetalle } from "../src/datos/tipos.ts";
import { anadirAutoridades } from "../src/i18n/autoridades.ts";

const CARPETA = join(dirname(fileURLToPath(import.meta.url)), "fixtures", "relato");
const HOY = "2026-10-27T07:17Z";

function ficha(id: string): IncidenteDetalle {
  const d = JSON.parse(readFileSync(join(CARPETA, `EODI-${id}.json`), "utf-8")) as IncidenteDetalle;
  if (d.autoridades !== undefined) anadirAutoridades(d.autoridades);
  return d;
}

const texto = (id: string, idioma: "es" | "en", conOficial = true) => relato(ficha(id), idioma, HOY, { conOficial }).join(" ");

describe("el párrafo de la ficha", () => {
  it("Aalborg: día sin hora, instalación con su nombre oficial, quién lo dijo, consecuencias y no acreditado", () => {
    const es = texto("2025-00228", "es");
    expect(es).toMatch(/^El 24 de septiembre de 2025, se notificó la presencia de entre 2 y 10 drones en el Aeropuerto de Aalborg \(Flyvestation Aalborg\), Dinamarca/u);
    expect(es).toContain("(declaración citada en ekstrabladet.dk)");
    expect(es).toContain("«El espacio aéreo sobre la Base Aérea de Aalborg está actualmente cerrado");
    expect(es).toContain("Hubo un cierre; se desviaron 3 vuelos y hubo patrullas.");
    expect(es).toMatch(/A 27 de octubre de 2026 el caso consta como no acreditado \(la presencia del dron no se acreditó\)\.$/u);
    // Sin hora en la ficha: ninguna hora en el párrafo.
    expect(es).not.toMatch(/\d{2}:\d{2}/u);
    const en = texto("2025-00228", "en");
    expect(en).toMatch(/^On 24 September 2025, between 2 and 10 drones were reported at Aalborg Airport \(Flyvestation Aalborg\), Denmark/u);
    expect(en).toMatch(/As of 27 October 2026, the case is recorded as not substantiated/u);
    // Sin historial de la presencia en la ficha: no se cuenta ningún cierre de la investigación.
    expect(queDespues(ficha("2025-00228"), "es")).toEqual([]);
    expect(es).not.toContain("investigación");
  });

  it("Copenhague: la noche, la hora local con la UTC, el cierre medido y la rectificación con fecha y motivo", () => {
    const es = texto("2025-00154", "es");
    expect(es).toMatch(/^La noche del 22 al 23 de septiembre de 2025, a las 20:30 hora local de Dinamarca \(18:30 UTC\)/u);
    expect(es).toContain("Hubo un cierre de 240 minutos; se desviaron 35 vuelos");
    expect(es).toContain("252 minutos sin movimientos en EKCH");
    expect(es).toContain(
      "consta como no acreditado (la presencia del dron no se acreditó); la policía de Dinamarca lo declaró el 25 de junio de 2026: no dispone de pruebas concluyentes",
    );
    const en = texto("2025-00154", "en");
    expect(en).toMatch(/^On the night of 22 to 23 September 2025, at 20:30 local time in Denmark \(18:30 UTC\)/u);
    expect(en).toContain("Danish Police stated it on 25 June 2026: it has no conclusive evidence");
    const despues = queDespues(ficha("2025-00154"), "es");
    expect(despues.map((p) => p.fecha)).toEqual(["25 de junio de 2026"]);
    expect(despues[0]?.texto).toMatch(/^Dron no acreditado, según la policía de Dinamarca: no dispone/u);
  });

  it("Auvere: incursión con hora de Estonia, la autoridad traducida y la investigación cerrada", () => {
    const es = texto("2026-00108", "es");
    expect(es).toMatch(/^La noche del 24 al 25 de marzo de 2026, a las 03:43 hora local de Estonia \(01:43 UTC\), se notificó la entrada de un dron en el espacio aéreo de Estonia, en la Central eléctrica de Auvere \(Auvere elektrijaam\)\./u);
    expect(es).toContain("Según el Servicio de Seguridad Interior de Estonia");
    expect(es).toContain("cerró la investigación el 23 de octubre de 2026");
    expect(estadoCorto(ficha("2026-00108"), "es", HOY)).toBe("confirmado por una autoridad a 27/10/2026");
    expect(texto("2026-00108", "en")).toContain("closed the investigation on 23 October 2026");
  });

  it("Solca: la noche de la jornada del ataque, sin repetir el país, y la cita del ministerio", () => {
    const es = texto("2026-00184", "es");
    expect(es).toMatch(/^La noche del 23 al 24 de septiembre de 2026, se notificó la entrada de un dron en el espacio aéreo de Rumanía, en Solca\./u);
    expect(es).toContain("Según el Ministerio de Defensa Nacional de Rumanía");
    expect(texto("2026-00184", "en")).toMatch(/^On the night of 23 to 24 September 2026, a drone was reported entering the airspace of Romania, at Solca\./u);
  });

  it("Vught (cárcel): sobrevuelo con el lugar de la ficha y la frase del ministerio", () => {
    const es = texto("2024-00003", "es");
    expect(es).toMatch(/^El 23 de diciembre de 2024, se notificó el sobrevuelo de drones sobre Vught, Países Bajos\./u);
    expect(es).toContain("Penitenciario");
    expect(texto("2024-00003", "en")).toMatch(/^On 23 December 2024, drones were reported flying over Vught, Netherlands\./u);
  });

  it("sin hora ni autoridad: ni hora, ni «según», ni consecuencias inventadas", () => {
    for (const idioma of ["es", "en"] as const) {
      const frases = relato(ficha("2025-00019"), idioma, HOY);
      expect(frases).toHaveLength(2);
      const junto = frases.join(" ");
      expect(junto).not.toMatch(/\d{2}:\d{2}|UTC|[Ss]egún|[Aa]ccording|declaró|stated/u);
    }
    expect(relato(ficha("2025-00019"), "es", HOY)[0]).toBe("Hacia el 1 de abril de 2025, se notificó el sobrevuelo de drones sobre el Reino Unido.");
    expect(estadoActual(ficha("2025-00019"), "en", HOY)).toBe(
      "As of 27 October 2026, the case is recorded as reported (the news reports it, without confirmation by an authority).",
    );
  });

  it("la ficha del mapa no lleva el nombre oficial en otro idioma", () => {
    expect(texto("2025-00228", "es", false)).not.toContain("Flyvestation");
    expect(texto("2026-00108", "en", false)).not.toContain("elektrijaam");
  });

  it("la hora local solo cuando la zona del sitio se sabe sin suponer", () => {
    expect(zonaDelSitio("ES", -15.4)).toBe("Atlantic/Canary");
    expect(zonaDelSitio("ES", -3.7)).toBe("Europe/Madrid");
    expect(zonaDelSitio("ES", null)).toBeNull();
    expect(zonaDelSitio("FR", 55.5)).toBeNull();
    const base = ficha("2025-00154");
    // Un país fuera de la tabla (el JSON quita los nombres, que dirían Dinamarca).
    const sinZona = JSON.parse(JSON.stringify({ ...base, nombres: undefined, lugar: { ...base.lugar, pais: "ZZ" } })) as IncidenteDetalle;
    expect(cuandoEscrito(sinZona, "es")).toBe("el 22 de septiembre de 2025, a las 18:30 UTC");
  });
});
