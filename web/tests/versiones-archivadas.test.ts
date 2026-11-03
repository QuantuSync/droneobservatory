// Versiones archivadas con DOI (configuracion/versiones_archivadas.json): la lista tiene la forma
// esperada, la metodología las enseña con su DOI, su repositorio, sus cifras y su cita en los dos
// idiomas, y el Dataset de schema.org lleva el DOI como identifier y cada versión como parte.

import { describe, expect, it } from "vitest";

import { erroresDeVersionesArchivadas, urlDeDoi, VERSIONES_ARCHIVADAS } from "../src/datos/versionesArchivadas.ts";
import type { VersionArchivada } from "../src/datos/versionesArchivadas.ts";
import { conjuntoDeDatos } from "../src/texto/paginas.ts";
import { jsonLd } from "../src/texto/html.ts";
import { seccionArchivadas } from "../src/texto/versiones.ts";

const DOI = "10.48320/F2CA4AE9-B2D3-4B0F-8F58-6CFBDE30D39F";
const ACTUALIZADO = "2026-11-03T08:17:00Z";

function primera(): VersionArchivada {
  const v = VERSIONES_ARCHIVADAS.at(-1);
  if (v === undefined) throw new Error("sin versiones archivadas");
  return v;
}

describe("versiones archivadas con DOI", () => {
  it("el fichero de configuración tiene la forma esperada y la 1.0 es la depositada el 2/11/2026", () => {
    expect(erroresDeVersionesArchivadas(VERSIONES_ARCHIVADAS)).toEqual([]);
    const v = primera();
    expect(v).toMatchObject({ version: "1.0", fecha: "2026-11-02", corte_datos: "2026-11-02T10:17:00Z", incidentes: 383, paises: 26, doi: DOI, repositorio: "Discuss Data" });
    expect(v.cita).toBe(
      "Lucas Alaniz Pintos (2026): European Observatory of Drone Incidents (EODI): drone incidents in Europe – Open register of drone incidents with sources, literal quotations and official status, version 2026-11-02, v. 1.0, Discuss Data, https://doi.org/10.48320/F2CA4AE9-B2D3-4B0F-8F58-6CFBDE30D39F",
    );
  });

  it("rechaza una lista mal hecha: DOI raro, cita sin DOI, versión repetida o fuera de orden", () => {
    const v = primera();
    expect(erroresDeVersionesArchivadas([{ ...v, doi: "doi.org/x" }]).join()).toContain(".doi");
    expect(erroresDeVersionesArchivadas([{ ...v, cita: "sin el identificador" }]).join()).toContain("cita no lleva el DOI");
    expect(erroresDeVersionesArchivadas([v, v]).join()).toContain("repetida");
    expect(erroresDeVersionesArchivadas([v, { ...v, version: "1.1", fecha: "2027-01-05" }]).join()).toContain("más nueva");
    expect(erroresDeVersionesArchivadas({})).toEqual(["versiones no es una lista"]);
  });

  it("la metodología enseña cada versión con su DOI enlazado, el repositorio, las cifras y la cita", () => {
    const comprobar = { es: ["Versión archivada con DOI", "cada hora", "cada trimestre", "383 incidentes en 26 países", "Universidad de Bremen", "Zenodo y DARIAH", "ODbL 1.0", "10:17"], en: ["Archived version with DOI", "every hour", "every quarter", "383 incidents in 26 countries", "University of Bremen", "Zenodo and DARIAH", "ODbL 1.0", "10:17"] } as const;
    for (const idioma of ["es", "en"] as const) {
      const seccion = seccionArchivadas(VERSIONES_ARCHIVADAS, idioma);
      if (seccion === false) throw new Error("sin sección");
      const texto = seccion.valor;
      expect(texto).toContain('id="archivadas"');
      expect(texto).toContain(`href="${urlDeDoi(DOI)}"`);
      expect(texto).toContain('href="https://discuss-data.net/dataset/f2ca4ae9-b2d3-4b0f-8f58-6cfbde30d39f/"');
      expect(texto).toContain('data-cita-archivada="1.0"');
      expect(texto).toContain("version 2026-11-02, v. 1.0, Discuss Data");
      for (const frase of comprobar[idioma]) expect(texto).toContain(frase);
    }
    expect(seccionArchivadas([], "es")).toBe(false);
  });

  it("varias versiones salen todas, la más nueva primero", () => {
    const nueva = { ...primera(), version: "1.1", fecha: "2027-01-04", doi: "10.48320/AAAA", cita: "Cita 1.1, https://doi.org/10.48320/AAAA" };
    const lista = [nueva, primera()];
    expect(erroresDeVersionesArchivadas(lista)).toEqual([]);
    const seccion = seccionArchivadas(lista, "en");
    if (seccion === false) throw new Error("sin sección");
    const texto = seccion.valor;
    expect(texto.indexOf('data-doi="10.48320/AAAA"')).toBeGreaterThan(0);
    expect(texto.indexOf('data-doi="10.48320/AAAA"')).toBeLessThan(texto.indexOf(`data-doi="${DOI}"`));
    const datos = conjuntoDeDatos(ACTUALIZADO, "en", lista);
    expect((datos.hasPart as unknown[]).length).toBe(2);
    expect(JSON.stringify(datos.identifier)).toContain("10.48320/AAAA");
  });

  it("el Dataset de schema.org lleva el DOI como identifier y la versión como parte, con lo que pide Google", () => {
    for (const idioma of ["es", "en"] as const) {
      // Lo que va en la página, leído de vuelta como JSON.
      const etiqueta = jsonLd(conjuntoDeDatos(ACTUALIZADO, idioma)).valor;
      const contenido = /^<script type="application\/ld\+json">([\s\S]*)<\/script>$/.exec(etiqueta)?.[1];
      if (contenido === undefined) throw new Error(`etiqueta inesperada: ${etiqueta.slice(0, 80)}`);
      const d = JSON.parse(contenido) as Record<string, unknown>;
      expect(d["@context"]).toBe("https://schema.org");
      expect(d["@type"]).toBe("Dataset");
      expect(typeof d.name).toBe("string");
      expect((d.description as string).length).toBeGreaterThanOrEqual(50);
      expect(d.license).toBe("https://creativecommons.org/licenses/by/4.0/");
      const identificadores = d.identifier as unknown[];
      expect(identificadores[0]).toBe(urlDeDoi(DOI));
      expect(identificadores[1]).toEqual({ "@type": "PropertyValue", propertyID: "DOI", value: DOI, url: urlDeDoi(DOI) });
      expect(d.citation).toContain(primera().cita);
      const [parte] = d.hasPart as Record<string, unknown>[];
      if (parte === undefined) throw new Error("sin hasPart");
      expect(parte["@type"]).toBe("Dataset");
      expect(parte["@id"]).toBe(urlDeDoi(DOI));
      expect(parte.sameAs).toEqual([urlDeDoi(DOI)]);
      expect(parte.url).toBe(primera().pagina);
      expect(parte.version).toBe("1.0");
      expect(parte.datePublished).toBe("2026-11-02");
      expect(typeof parte.name).toBe("string");
      expect((parte.description as string).length).toBeGreaterThanOrEqual(50);
      expect((parte.creator as Record<string, unknown>)["@type"]).toBe("Person");
      // Las descargas vivas de la web siguen siendo la distribución del conjunto.
      expect((d.distribution as Record<string, unknown>[]).every((x) => x["@type"] === "DataDownload")).toBe(true);
    }
  });
});
