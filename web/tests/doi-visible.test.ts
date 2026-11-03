// El DOI se ve sin buscarlo (3 de noviembre de 2026): es la cita recomendada, lo primero de los
// datos abiertos de la metodología; el índice lleva «Citar con DOI»; el pie de todas las páginas
// de texto, «Datos archivados con DOI» junto a la licencia; la portada en texto, una línea con el
// DOI junto a las descargas. Todo apunta a la versión archivada más reciente.

import { describe, expect, it } from "vitest";

import { detalleIncidente, resumir, resumirUcrania } from "../src/datos/derivar.ts";
import { RUTA_CITAR, ULTIMA_ARCHIVADA, VERSIONES_ARCHIVADAS, urlDeDoi } from "../src/datos/versionesArchivadas.ts";
import { marco, paginas } from "../src/texto/paginas.ts";
import type { PaginaTexto } from "../src/texto/paginas.ts";
import { coleccion, incidente, publicacion } from "./ejemplos.ts";

const UNO = incidente({});
const ACTUALIZADO = "2026-11-03T17:17Z";
const TODAS = paginas({
  resumen: resumir(coleccion([UNO]), publicacion([])),
  detalles: new Map([[UNO.id, detalleIncidente(UNO)]]),
  ucrania: resumirUcrania(publicacion([])),
});

function pagina(idioma: "es" | "en", ruta: (p: PaginaTexto) => boolean): string {
  const encontrada = TODAS.find((p) => p.idioma === idioma && ruta(p));
  if (encontrada === undefined) throw new Error("sin página");
  return marco(encontrada, ACTUALIZADO).toString();
}

const ultima = (): NonNullable<typeof ULTIMA_ARCHIVADA> => {
  if (ULTIMA_ARCHIVADA === undefined) throw new Error("sin versión archivada");
  return ULTIMA_ARCHIVADA;
};

describe("el DOI se ve", () => {
  it("la más reciente es la primera de configuracion/versiones_archivadas.json", () => {
    expect(ULTIMA_ARCHIVADA).toBe(VERSIONES_ARCHIVADAS[0]);
    expect(RUTA_CITAR).toEqual({ es: "/metodologia#citar", en: "/en/methodology#citar" });
  });

  for (const idioma of ["es", "en"] as const) {
    const metodologia = pagina(idioma, (p) => p.rutas[idioma] === (idioma === "es" ? "/metodologia" : "/en/methodology"));
    const doi = urlDeDoi(ultima().doi);

    it(`la cita recomendada con el DOI enlazado va lo primero de los datos abiertos (${idioma})`, () => {
      const seccion = metodologia.slice(metodologia.indexOf('<section id="datos-abiertos">'));
      const cita = seccion.indexOf('id="citar"');
      expect(cita).toBeGreaterThan(0);
      expect(cita).toBeLessThan(seccion.indexOf("<ul>"));
      expect(seccion.indexOf(`<a href="${doi}"`)).toBeLessThan(seccion.indexOf("<ul>"));
      expect(seccion).toContain(`data-cita-recomendada="${ultima().version}"`);
      // Una sola cita recomendada en la página: la del DOI.
      expect(metodologia.split("data-cita-recomendada=").length).toBe(2);
    });

    it(`el índice enlaza directamente al apartado (${idioma})`, () => {
      const texto = idioma === "es" ? "Citar con DOI" : "Cite with DOI";
      expect(metodologia).toMatch(new RegExp(`<li data-citar-doi=""><a href="#citar"[^>]*>${texto}</a>`));
    });

    it(`el pie de las páginas de texto lleva «${idioma === "es" ? "Datos archivados con DOI" : "Data archived with DOI"}» (${idioma})`, () => {
      const texto = idioma === "es" ? "Datos archivados con DOI" : "Data archived with DOI";
      const ficha = pagina(idioma, (p) => p.rutas[idioma].endsWith(UNO.id));
      const otras = [ficha, metodologia, pagina(idioma, (p) => p.rutas.es === "/avisos")];
      for (const html of otras) {
        const pie = html.slice(html.indexOf('<footer class="texto-pie">'));
        expect(pie).toContain(`<a href="${doi}" rel="noopener" data-doi-pie="${ultima().doi}">${texto}</a>`);
      }
    });

    it(`la portada en texto da el DOI junto a las descargas (${idioma})`, () => {
      const portada = pagina(idioma, (p) => p.rutas[idioma] === (idioma === "es" ? "/" : "/en"));
      const linea = portada.slice(portada.indexOf("data-doi-portada"));
      expect(linea).toContain(`<a href="${doi}"`);
      expect(linea).toContain(`doi:${ultima().doi}`);
      expect(linea).toContain(`href="${RUTA_CITAR[idioma]}"`);
      expect(portada.indexOf("#datos-abiertos")).toBeLessThan(portada.indexOf("data-doi-portada"));
    });
  }
});
