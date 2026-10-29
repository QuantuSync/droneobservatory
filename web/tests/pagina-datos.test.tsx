// @vitest-environment jsdom
// Un solo número por dato: la ficha de la web y su página de texto enseñan la cifra que publican
// los datos aunque alguna fuente diga otra. EODI-2026-00160 publica un dron (el que cruzó Lunga) y
// la página enseñaba 3, el «trei drone» del Ministerio de Exteriores, que es el total del día. Lo que
// dice cada fuente va aparte, en «Qué dice cada fuente»; la cifra la decide la recogida.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente, resumir, resumirUcrania } from "../src/datos/derivar.ts";
import type { RangoODesconocido } from "../src/datos/tipos.ts";
import { rango, textos } from "../src/i18n/index.ts";
import type { Idioma } from "../src/sitio.ts";
import { paginas } from "../src/texto/paginas.ts";
import { afirmacion, coleccion, incidente, publicacion } from "./ejemplos.ts";

afterEach(cleanup);

const DRONES = { min: 1, max: 1 };
const MINUTOS = { min: 60, max: 60 };
const DESVIADOS = { min: 2, max: 2 };

const LUNGA = incidente({
  id: "EODI-2026-00160",
  drones: { numero: DRONES },
  consecuencias: { cierre: { valor: "si", minutos: MINUTOS }, vuelos_desviados: DESVIADOS },
  afirmaciones_publicas: [
    afirmacion({ valor: { min: 3, max: 3 }, medio: "news.yam.md" }),
    afirmacion({ campo: "consecuencias.cierre.minutos", valor: { min: 30, max: 90 } }),
    afirmacion({
      campo: "consecuencias.vuelos_desviados",
      valor: { min: 5, max: 5 },
      fiabilidad: "B",
    }),
  ],
});

/** Lo que enseña una fila, sin el desplegable de lo que dice cada fuente. */
function filaDeLaFicha(contenedor: HTMLElement, nombre: string): string {
  const dt = [...contenedor.querySelectorAll("dt")].find((d) => d.textContent === nombre);
  const dd = dt?.nextElementSibling?.cloneNode(true) as Element | undefined;
  for (const desplegable of dd?.querySelectorAll("details") ?? []) desplegable.remove();
  return (dd?.textContent ?? "").replace(/\s+/g, " ").trim();
}

function filaDeLaPagina(cuerpo: string, nombre: string): string {
  const inicio = cuerpo.indexOf(`<dt>${nombre}</dt><dd>`);
  expect(inicio, nombre).toBeGreaterThanOrEqual(0);
  const resto = cuerpo.slice(inicio + `<dt>${nombre}</dt><dd>`.length);
  return resto.slice(0, resto.indexOf("</dd>")).replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

function cifra(valor: RangoODesconocido, idioma: Idioma): string {
  const texto = rango(valor, idioma);
  if (texto === null) throw new Error("sin cifra");
  return texto;
}

describe("la página enseña los datos publicados", () => {
  for (const idioma of ["es", "en"] as const) {
    const t = textos(idioma);

    it(`la ficha de la web da la cifra publicada, no la de una fuente (${idioma})`, () => {
      const { container } = render(
        <FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(LUNGA)} />,
      );
      expect(filaDeLaFicha(container, t.ficha.drones)).toBe(cifra(DRONES, idioma));
      const efecto = filaDeLaFicha(container, t.ficha.efecto);
      expect(efecto).toContain(t.ficha.cierreDe(cifra(MINUTOS, idioma)));
      expect(efecto).toContain(`${cifra(DESVIADOS, idioma)} ${t.ficha.vuelosDesviados}`);
      expect(efecto).not.toMatch(/30|90|\b5\b/);
    });

    it(`la página de texto da las mismas cifras (${idioma})`, () => {
      const todas = paginas({
        resumen: resumir(coleccion([LUNGA]), publicacion([])),
        detalles: new Map([[LUNGA.id, detalleIncidente(LUNGA)]]),
        ucrania: resumirUcrania(publicacion([])),
      });
      const pagina = todas.find((p) => p.idioma === idioma && p.rutas[idioma].endsWith(LUNGA.id));
      const cuerpo = String(pagina?.cuerpo ?? "");
      expect(filaDeLaPagina(cuerpo, t.ficha.drones)).toBe(cifra(DRONES, idioma));
      const efecto = filaDeLaPagina(cuerpo, t.ficha.efecto);
      expect(efecto).toContain(t.ficha.cierreDe(cifra(MINUTOS, idioma)));
      expect(efecto).toContain(`${cifra(DESVIADOS, idioma)} ${t.ficha.vuelosDesviados}`);
      expect(efecto).not.toMatch(/30|90|\b5\b/);
    });
  }
});
