// La ficha que estuvo publicada y se retiró (miembro `retirados` de incidentes.geojson): el
// validador lo acepta, cada retirada no publicada tiene su página en los dos idiomas (con el
// identificador, la fecha y el motivo, que viene de los datos y se escapa) y esa página no entra
// en los buscadores.
import { describe, expect, it } from "vitest";

import { etiquetasDeCabecera } from "../src/cabecera.ts";
import type { Retirada } from "../src/datos/tipos.ts";
import { validarColeccion } from "../src/datos/validar.ts";
import { marco } from "../src/texto/paginas.ts";
import { retirada, retiradas, rutaDeRetirada } from "../src/texto/salidas.ts";

const ID = "EODI-2026-00765";
const DETALLE: Retirada = {
  fecha: "2026-11-09T11:17Z",
  motivo: { es: "No es un suceso nuevo: repite otro ya publicado.", en: "Not a new event: it repeats one already published." },
};
const coleccion = (retirados: unknown) => ({ type: "FeatureCollection", features: [], retirados });

describe("ficha retirada", () => {
  it("el validador acepta la colección con retirados y rechaza los mal formados", () => {
    expect(validarColeccion(coleccion({ [ID]: DETALLE })).ok).toBe(true);
    expect(validarColeccion(coleccion({})).ok).toBe(true);
    expect(validarColeccion({ type: "FeatureCollection", features: [] }).ok).toBe(true);
    const rotos: unknown[] = [
      { [ID]: { fecha: DETALLE.fecha, motivo: { es: DETALLE.motivo.es } } },
      { [ID]: { fecha: DETALLE.fecha, motivo: { es: DETALLE.motivo.es, en: "" } } },
      { [ID]: { fecha: "ayer", motivo: DETALLE.motivo } },
      { [ID]: { motivo: DETALLE.motivo } },
      { "EODI-UA-2026-1014": DETALLE },
      { [ID]: "retirado" },
      [ID],
    ];
    for (const roto of rotos) expect(validarColeccion(coleccion(roto)).ok).toBe(false);
  });

  it("la página de la retirada tiene su propia dirección en cada idioma", () => {
    expect(rutaDeRetirada(ID, "es")).toBe(`/retiradas/${ID}`);
    expect(rutaDeRetirada(ID, "en")).toBe(`/en/withdrawn/${ID}`);
  });

  it("solo las retiradas que no están publicadas, en los dos idiomas y en orden", () => {
    const lista = retiradas(
      { "EODI-2026-00900": DETALLE, [ID]: DETALLE, "EODI-2026-00001": DETALLE },
      new Set(["EODI-2026-00001"]),
    );
    expect(lista).toEqual([
      { source: `/${ID}`, destination: `/retiradas/${ID}` },
      { source: `/en/${ID}`, destination: `/en/withdrawn/${ID}` },
      { source: "/EODI-2026-00900", destination: "/retiradas/EODI-2026-00900" },
      { source: "/en/EODI-2026-00900", destination: "/en/withdrawn/EODI-2026-00900" },
    ]);
    expect(retiradas({}, new Set())).toEqual([]);
  });

  it("dice qué ficha era, cuándo se retiró y por qué, en el idioma de la dirección", () => {
    const es = retirada(ID, DETALLE, "es");
    expect(es.idioma).toBe("es");
    expect(es.conMapa).toBe(false);
    expect(es.estructurados).toEqual([]);
    expect(es.modificada).toBe("");
    expect(es.titulo).toContain("Ficha retirada");
    expect(es.titulo).toContain(ID);
    expect(es.cuerpo.valor).toContain("<h1>Ficha retirada</h1>");
    expect(es.cuerpo.valor).toContain(`>${ID}</p>`);
    expect(es.cuerpo.valor).toContain("se retiró el 09/11/2026 · 11:17 UTC.");
    expect(es.cuerpo.valor).toContain("<h2>Motivo</h2>");
    expect(es.cuerpo.valor).toContain(DETALLE.motivo.es);
    expect(es.cuerpo.valor).not.toContain(DETALLE.motivo.en);
    expect(es.cuerpo.valor).toContain('<a href="/">Ir a la portada</a>');

    const en = retirada(ID, DETALLE, "en");
    expect(en.idioma).toBe("en");
    expect(en.cuerpo.valor).toContain("<h1>Record withdrawn</h1>");
    expect(en.cuerpo.valor).toContain("was withdrawn on 09/11/2026 · 11:17 UTC.");
    expect(en.cuerpo.valor).toContain("<h2>Reason</h2>");
    expect(en.cuerpo.valor).toContain(DETALLE.motivo.en);
    expect(en.cuerpo.valor).not.toContain(DETALLE.motivo.es);
    expect(en.cuerpo.valor).toContain('<a href="/en">Go to the home page</a>');
  });

  it("el motivo entra como texto: su HTML se escapa", () => {
    const hostil: Retirada = {
      fecha: DETALLE.fecha,
      motivo: { es: '<script>alert(1)</script><img src=x onerror="y">', en: "<b>x</b>" },
    };
    const cuerpo = retirada(ID, hostil, "es").cuerpo.valor;
    expect(cuerpo).not.toContain("<script");
    expect(cuerpo).not.toContain("<img");
    expect(cuerpo).toContain("&lt;script&gt;alert(1)&lt;/script&gt;&lt;img src=x onerror=&quot;y&quot;&gt;");
    expect(retirada(ID, hostil, "en").cuerpo.valor).toContain("&lt;b&gt;x&lt;/b&gt;");
  });

  it("sus direcciones son las de la ficha: el otro idioma lleva a la retirada en ese idioma", () => {
    const pagina = retirada(ID, DETALLE, "es");
    expect(pagina.rutas).toEqual({ es: `/${ID}`, en: `/en/${ID}` });
    expect(marco(pagina, "2026-11-10T08:17Z").valor).toContain(`class="texto-idioma" href="/en/${ID}"`);
  });

  it("no entra en los buscadores; las demás páginas no cambian", () => {
    const pagina = retirada(ID, DETALLE, "en");
    const cabecera = { idioma: pagina.idioma, id: null, titulo: pagina.titulo, descripcion: pagina.descripcion, rutas: pagina.rutas };
    expect(pagina.sinIndexar).toBe(true);
    expect(etiquetasDeCabecera({ ...cabecera, sinIndexar: true })).toContain('<meta name="robots" content="noindex">');
    expect(etiquetasDeCabecera(cabecera)).not.toContain("robots");
  });
});
