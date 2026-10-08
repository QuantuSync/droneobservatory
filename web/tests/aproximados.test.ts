// Incidentes con lugar aproximado: los que no tienen punto se dibujan en el centro del país, de
// la región o del mar que nombra la fuente, y todo lo de las últimas 24 horas que enseña
// «Novedades» está también en el mapa con el filtro de 24 horas. Corre con los datos de prueba y,
// en la integración continua, con los publicados (EODI_PUBLICACION).

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { resumir } from "../src/datos/derivar.ts";
import { enElMar, lugarAproximado } from "../src/datos/lugarAproximado.ts";
import type { ColeccionIncidentes, IncidenteResumen, PublicacionSinUbicacion, PublicacionUcrania } from "../src/datos/tipos.ts";
import { validarColeccion, validarPublicacionUcrania, validarSinUbicacion } from "../src/datos/validar.ts";
import { filtrar, SIN_FILTROS, ultimas24Horas } from "../src/estado/filtros.ts";
import { pilas } from "../src/mapa/geometria.ts";
import { MS_POR_DIA, MS_POR_HORA, diaDeInstante, incidenteEnPeriodo } from "../src/tiempo/dias.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const CARPETA = process.env.EODI_PUBLICACION ?? join(RAIZ, "tests", "fixtures", "publicacion");

function leer(nombre: string): unknown {
  return JSON.parse(readFileSync(resolve(CARPETA, nombre), "utf-8")) as unknown;
}

function exigir<T>(resultado: { ok: true; datos: T } | { ok: false; errores: string[] }): T {
  if (!resultado.ok) throw new Error(resultado.errores.join("; "));
  return resultado.datos;
}

const coleccion: ColeccionIncidentes = exigir(validarColeccion(leer("incidentes.geojson")));
const ucrania: PublicacionUcrania = exigir(validarPublicacionUcrania(leer("ucrania.json")));
const sinUbicacion: PublicacionSinUbicacion = exigir(validarSinUbicacion(leer("incidentes_sin_ubicacion.json")));
const resumen = resumir(coleccion, ucrania, sinUbicacion);

/** Los incidentes que el mapa dibuja (en un círculo, un grupo o con su marcador propio). */
function enElMapa(incidentes: readonly IncidenteResumen[]): Set<string> {
  const sin = new Set<string>();
  const opciones = { recientes: ultimas24Horas(Date.now()), novedades: sin };
  return new Set(pilas(incidentes, opciones).features.flatMap((f) => f.properties.ids.split(",")));
}

describe("lugar aproximado", () => {
  it("todo incidente publicado tiene sitio en el mapa: su punto o su lugar aproximado", () => {
    const sinSitio = resumen.incidentes.filter((i) => i.punto === null && i.aproximado === null).map((i) => i.id);
    expect(sinSitio).toEqual([]);
    expect(enElMapa(resumen.incidentes).size).toBe(resumen.incidentes.length);
  });

  it("los de lugar aproximado no tienen punto y su marcador es el propio", () => {
    const aproximados = resumen.incidentes.filter((i) => i.aproximado !== null);
    expect(aproximados.length).toBe(sinUbicacion.incidentes.length);
    const sueltos = pilas(aproximados, { recientes: ultimas24Horas(Date.now()), novedades: new Set() });
    for (const f of sueltos.features) {
      expect(f.properties.aproximado).toBe(1);
      expect(f.properties.icono).toMatch(/-aproximado$/);
    }
  });

  it("país, región y mar frente a la costa", () => {
    const titulo = { es: "Dron sobre el país", en: "Drone over the country" };
    expect(lugarAproximado({ pais: "MD" }, titulo)).toMatchObject({ nivel: "pais", nombre: null });
    expect(lugarAproximado({ pais: "LV", region: "Latgale" }, titulo)).toMatchObject({ nivel: "region", nombre: "Latgale" });
    // Una región que no está en la tabla deja el marcador en el país.
    expect(lugarAproximado({ pais: "RO", region: "Nowhere" }, titulo)).toMatchObject({ nivel: "pais" });
    const barcos = {
      es: "Drones atacan dos barcos en la zona económica exclusiva de Bulgaria",
      en: "Drones strike two ships in Bulgaria's exclusive economic zone",
    };
    expect(enElMar(barcos)).toBe(true);
    const enDobrich = lugarAproximado({ pais: "BG", region: "Dobrich" }, barcos);
    expect(enDobrich).toMatchObject({ nivel: "mar", nombre: "Dobrich" });
    // En el mar: al este de la costa de Dobrich (Kaliakra, 28,47° E).
    expect(enDobrich?.lon ?? 0).toBeGreaterThan(28.5);
    expect(lugarAproximado({ pais: "GR", region: "Αιγαίο" }, titulo)).toMatchObject({ nivel: "mar" });
  });
});

describe("«Novedades» y el filtro de 24 horas", () => {
  const ahora = Date.parse(resumen.actualizado);
  const periodo = ultimas24Horas(ahora);
  const del24h = filtrar(resumen.incidentes, SIN_FILTROS).filter((i) => incidenteEnPeriodo(i, periodo));

  it("toda novedad de las últimas 24 horas está en el mapa con el filtro de 24 horas", () => {
    // Lo que enseña «Novedades» con el filtro: los eventos de los incidentes que pasan el filtro.
    const visibles = new Set(del24h.map((i) => i.id));
    const novedades = new Set(resumen.eventos.filter((e) => visibles.has(e.id)).map((e) => e.id));
    const dibujados = enElMapa(del24h);
    for (const id of novedades) expect(dibujados.has(id), id).toBe(true);
    // Y todo lo del filtro sale en «Novedades».
    for (const i of del24h) expect(novedades.has(i.id), i.id).toBe(true);
  });

  it("un incidente fechado solo por día entra si ese día toca las últimas 24 horas", () => {
    const ahoraFijo = Date.parse("2026-10-08T09:30:00Z");
    const p = ultimas24Horas(ahoraFijo);
    const hoy = diaDeInstante("2026-10-08");
    const conDia = (dia: number) => ({ dia, inicio: null });
    expect(incidenteEnPeriodo(conDia(hoy), p)).toBe(true);
    // Ayer toca las 24 horas (de las 09:30 de ayer a medianoche).
    expect(incidenteEnPeriodo(conDia(hoy - 1), p)).toBe(true);
    expect(incidenteEnPeriodo(conDia(hoy - 2), p)).toBe(false);
    // Con hora conocida manda la hora exacta.
    const ayerTemprano = hoy * MS_POR_DIA - 20 * MS_POR_HORA;
    expect(incidenteEnPeriodo({ dia: hoy - 1, inicio: ayerTemprano }, p)).toBe(false);
  });
});
