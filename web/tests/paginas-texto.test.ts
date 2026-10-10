// Piezas de las páginas que se leen sin ejecutar código (src/texto): el HTML escapa lo que viene
// de los datos, los datos estructurados no pueden cerrar su etiqueta, las redirecciones solo van
// de un unido a un publicado y el sitemap lleva cada página con su versión en el otro idioma.
import { describe, expect, it } from "vitest";

import { e, html, jsonLd } from "../src/texto/html.ts";
import { RUTAS, rutasDePais } from "../src/texto/paginas.ts";
import type { PaginaTexto } from "../src/texto/paginas.ts";
import { fechaSitemap, redirecciones, sitemap } from "../src/texto/salidas.ts";
import { textosPagina } from "../src/texto/textos.ts";
import { textos } from "../src/i18n/index.ts";

describe("páginas de texto", () => {
  it("escapa el texto y los atributos que vienen de los datos", () => {
    const fragmento = e("a", { href: 'x" onclick="y' }, "<script>alert(1)</script>", e("b", null, "ok"));
    expect(fragmento.valor).toBe(
      '<a href="x&quot; onclick=&quot;y">&lt;script&gt;alert(1)&lt;/script&gt;<b>ok</b></a>',
    );
  });

  it("los datos estructurados no cierran su etiqueta", () => {
    expect(jsonLd({ name: "</script><script>x" }).valor).not.toContain("</script><script>");
  });

  it("redirige un unido a uno publicado, en los dos idiomas, nunca desde uno publicado", () => {
    const publicados = new Set(["EODI-2025-00295", "EODI-2025-00001"]);
    const lista = redirecciones(
      { "EODI-2025-00270": "EODI-2025-00295", "EODI-2025-00001": "EODI-2025-00295", "EODI-2025-00002": "EODI-2025-00099" },
      publicados,
    );
    expect(lista).toEqual([
      { source: "/EODI-2025-00270", destination: "/EODI-2025-00295", statusCode: 308 },
      { source: "/en/EODI-2025-00270", destination: "/en/EODI-2025-00295", statusCode: 308 },
    ]);
  });

  it("el sitemap lleva cada página con su última modificación y su otro idioma", () => {
    const pagina: PaginaTexto = {
      idioma: "es",
      rutas: rutasDePais("PL"),
      titulo: "",
      descripcion: "",
      cuerpo: html(),
      estructurados: [],
      conMapa: false,
      modificada: "2026-10-05T17:17Z",
    };
    const xml = sitemap([pagina]);
    // Con segundos, como pide el esquema de los sitemaps, y con la versión por defecto.
    expect(xml).toContain("<loc>https://droneobservatory.eu/paises/pl</loc><lastmod>2026-10-05T17:17:00Z</lastmod>");
    expect(xml).toContain('hreflang="en" href="https://droneobservatory.eu/en/countries/pl"');
    expect(xml).toContain('hreflang="x-default" href="https://droneobservatory.eu/paises/pl"');
    expect(sitemap([{ ...pagina, modificada: "" }])).not.toContain("<lastmod>");
  });

  it("las fechas del sitemap siguen el formato W3C Datetime", () => {
    expect(fechaSitemap("2026-10-05")).toBe("2026-10-05");
    expect(fechaSitemap("2026-10-05T17:17Z")).toBe("2026-10-05T17:17:00Z");
    expect(fechaSitemap("2026-10-09T00:00:00Z")).toBe("2026-10-09T00:00:00Z");
    expect(fechaSitemap("2026-10-01T03:00:12.345Z")).toBe("2026-10-01T03:00:12Z");
    expect(fechaSitemap("")).toBeNull();
    expect(fechaSitemap("ayer")).toBeNull();
  });

  it("cada página tiene su dirección en los dos idiomas", () => {
    for (const rutas of Object.values(RUTAS)) {
      expect(rutas.es.startsWith("/")).toBe(true);
      expect(rutas.en.startsWith("/en/")).toBe(true);
    }
  });

  it("lo que significa cada estado es el principio de su definición en la metodología", () => {
    for (const idioma of ["es", "en"] as const) {
      const estados = textos(idioma).metodologia.secciones.find((s) => s.id === "estados");
      const lista = estados?.bloques.find((b) => "lista" in b);
      const definiciones = lista !== undefined && "lista" in lista ? lista.lista : [];
      for (const [estado, significado] of Object.entries(textosPagina(idioma).estado)) {
        const definicion = definiciones.find((d) => d.termino === textos(idioma).estado[estado as keyof typeof textos]);
        expect(String(definicion?.texto[0] ?? "").startsWith(significado)).toBe(true);
      }
    }
  });
});
