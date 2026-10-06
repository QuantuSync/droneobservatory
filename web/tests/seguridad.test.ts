import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

import {
  aplicarCabecera,
  escaparHtml,
  etiquetasDeCabecera,
  paginaDeIncidente,
  paginaDePortada,
} from "../src/cabecera.ts";
import {
  cabecerasDe,
  destinoDeReescritura,
  directivasCsp,
} from "../src/seguridad/despliegue.ts";
import type { ConfiguracionDespliegue } from "../src/seguridad/despliegue.ts";
import { enlaceSeguro } from "../src/seguridad/enlaces.ts";
import { contarScriptsEnLinea, separarScriptsEnLinea } from "../src/seguridad/scripts.ts";
import { RUTA_SECURITY_TXT, securityTxt } from "../src/seguridad/securityTxt.ts";
import { ORIGEN_ALMACEN } from "../src/almacenPublico.ts";
import { CONTACTO_SEGURIDAD, ORIGEN } from "../src/sitio.ts";
import { CARGAS_MALICIOSAS } from "./ejemplos.ts";

const WEB = join(import.meta.dirname, "..");
const vercel = JSON.parse(
  readFileSync(join(WEB, "..", "vercel.json"), "utf-8"),
) as ConfiguracionDespliegue;

describe("enlaces externos", () => {
  it.each([
    ["https://example.org/a?b=1#c", "https://example.org/a?b=1#c"],
    ["http://example.org", "http://example.org/"],
    ["  https://example.org/con-espacios  ", "https://example.org/con-espacios"],
    ["HTTPS://EXAMPLE.ORG/Ruta", "https://example.org/Ruta"],
  ])("acepta %j", (enlace, esperado) => {
    expect(enlaceSeguro(enlace)).toBe(esperado);
  });

  it.each([
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    " javascript:alert(1)",
    "java\nscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "ftp://example.org/x",
    "blob:https://example.org/uuid",
    "//example.org/sin-esquema",
    "/ruta/relativa",
    "example.org",
    "",
    "https://",
  ])("descarta %j", (enlace) => {
    expect(enlaceSeguro(enlace)).toBeNull();
  });

  it("descarta lo que no es texto", () => {
    for (const valor of [null, undefined, 3, {}, ["https://example.org"]]) {
      expect(enlaceSeguro(valor)).toBeNull();
    }
  });
});

describe("metadatos de cada página", () => {
  it("escapa los cinco caracteres que pueden abrir una etiqueta o un atributo", () => {
    expect(escaparHtml(`<a href="x" title='y'>&</a>`)).toBe(
      "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;",
    );
  });

  it.each(Object.entries(CARGAS_MALICIOSAS))("un título con %s no abre ninguna etiqueta", (_n, carga) => {
    const etiquetas = etiquetasDeCabecera(paginaDeIncidente("es", "EODI-2025-00210", carga));
    // Solo quedan las etiquetas que escribe la propia web: title, meta y link.
    const abiertas = [...etiquetas.matchAll(/<\/?([a-z]+)/g)].map((m) => m[1]);
    expect(new Set(abiertas)).toEqual(new Set(["title", "meta", "link"]));
    // Dentro de <title> el texto queda escapado entero: no hay ningún «<» suyo.
    expect(/<title>[^<]*<\/title>/.test(etiquetas)).toBe(true);
    // Cada atributo content sigue siendo uno solo: no hay comillas sin escapar dentro.
    for (const linea of etiquetas.split("\n").filter((l) => l.includes("content="))) {
      expect(linea.trim()).toMatch(/^<meta (name|property)="[^"]+" content="[^"]*">$/);
    }
  });

  it("da a cada incidente su título, su dirección y sus dos idiomas", () => {
    const etiquetas = etiquetasDeCabecera(paginaDeIncidente("en", "EODI-2025-00210", "Munich"));
    expect(etiquetas).toContain("<title>Munich · European Observatory of Drone Incidents</title>");
    expect(etiquetas).toContain(`<link rel="canonical" href="${ORIGEN}/en/EODI-2025-00210">`);
    expect(etiquetas).toContain(`hreflang="es" href="${ORIGEN}/EODI-2025-00210"`);
    // La imagen de compartir va en el idioma de la página.
    expect(etiquetas).toContain(`<meta property="og:image" content="${ORIGEN}/compartir-en.png">`);
    expect(etiquetas).toContain(`<meta name="twitter:image" content="${ORIGEN}/compartir-en.png">`);
    expect(etiquetasDeCabecera(paginaDeIncidente("es", "EODI-2025-00210", "Múnich"))).toContain(
      `<meta property="og:image" content="${ORIGEN}/compartir.png">`,
    );
    expect(etiquetas).toContain('<meta name="twitter:card" content="summary_large_image">');
  });

  it("el nombre del proyecto va en inglés en los dos idiomas", () => {
    for (const idioma of ["es", "en"] as const) {
      expect(paginaDePortada(idioma).titulo).toContain("European Observatory of Drone Incidents");
    }
  });

  it("sustituye el bloque de cabecera y el idioma del documento", () => {
    const html =
      '<html lang="es"><head><!--cabecera--><title>viejo</title><!--/cabecera--></head></html>';
    const nuevo = aplicarCabecera(html, paginaDePortada("en"));
    expect(nuevo).toContain('<html lang="en">');
    expect(nuevo).not.toContain("viejo");
    // Se puede volver a aplicar: así salen las páginas de incidente de la portada.
    const otraVez = aplicarCabecera(nuevo, paginaDeIncidente("es", "EODI-2025-00001", "Título"));
    expect(otraVez).toContain('<html lang="es">');
    expect(otraVez.match(/<title>/g)).toHaveLength(1);
    expect(() => aplicarCabecera("<html></html>", paginaDePortada("es"))).toThrow();
  });
});

describe("scripts en línea", () => {
  it("saca a ficheros los scripts ejecutables y deja los de datos", () => {
    const html =
      '<script type="module" src="/a.js"></script><script>window.x = 1</script>' +
      '<script type="application/ld+json">{"a":1}</script><script nonce="n">y()</script>';
    const { html: limpio, scripts } = separarScriptsEnLinea(html, (codigo) => `/s-${codigo.length}.js`);
    expect(scripts).toEqual([
      { ruta: "/s-12.js", codigo: "window.x = 1" },
      { ruta: "/s-3.js", codigo: "y()" },
    ]);
    expect(limpio).toContain('<script src="/s-12.js" defer></script>');
    expect(limpio).toContain('<script type="application/ld+json">{"a":1}</script>');
    expect(contarScriptsEnLinea(limpio)).toBe(0);
  });
});

describe("cabeceras del despliegue", () => {
  const RUTAS = ["/", "/en", "/EODI-2025-00210", "/datos/resumen.json", "/assets/app.js"];

  it.each(RUTAS)("%s lleva todas las cabeceras de seguridad", (ruta) => {
    const cabeceras = cabecerasDe(vercel, ruta);
    expect(cabeceras.get("Strict-Transport-Security")).toBe(
      "max-age=31536000; includeSubDomains; preload",
    );
    expect(cabeceras.get("X-Content-Type-Options")).toBe("nosniff");
    expect(cabeceras.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(cabeceras.get("X-Frame-Options")).toBe("DENY");
    expect(cabeceras.get("Permissions-Policy")).toBe(
      "camera=(), microphone=(), geolocation=(), accelerometer=(), gyroscope=(), " +
        "magnetometer=(), payment=()",
    );
    expect(cabeceras.has("Content-Security-Policy")).toBe(true);
  });

  it("la política de contenido solo admite este sitio y el almacén público", () => {
    const csp = directivasCsp(cabecerasDe(vercel, "/").get("Content-Security-Policy") ?? "");
    expect(csp.get("default-src")).toEqual(["'self'"]);
    expect(csp.get("script-src")).toEqual(["'self'"]);
    expect(csp.get("style-src")).toEqual(["'self'"]);
    expect(csp.get("font-src")).toEqual(["'self'"]);
    expect(csp.get("connect-src")).toEqual(["'self'", ORIGEN_ALMACEN]);
    expect(ORIGEN_ALMACEN).toBe("https://droneobservatory-almacen.nbg1.your-objectstorage.com");
    // Nada se sirve ya desde Cloudflare.
    const politica = cabecerasDe(vercel, "/").get("Content-Security-Policy") ?? "";
    expect(politica).not.toContain("tiles.droneobservatory.eu");
    expect(politica).not.toMatch(/cloudflare|r2\.dev/);
    expect(csp.get("object-src")).toEqual(["'none'"]);
    expect(csp.get("base-uri")).toEqual(["'self'"]);
    expect(csp.get("form-action")).toEqual(["'none'"]);
    expect(csp.get("frame-ancestors")).toEqual(["'none'"]);
    for (const [, origenes] of csp) {
      expect(origenes).not.toContain("'unsafe-inline'");
      expect(origenes).not.toContain("'unsafe-eval'");
      expect(origenes).not.toContain("*");
    }
    // Ni scripts ni trabajadores ni imágenes salen de blob: o de data:. Las imágenes de
    // satélite de antes y después vienen del almacén público.
    for (const directiva of ["script-src", "worker-src", "child-src"]) {
      expect(csp.get(directiva)).toEqual(["'self'"]);
    }
    expect(csp.get("img-src")).toEqual(["'self'", ORIGEN_ALMACEN]);
  });

  it("las fichas que no son un fichero van a la función del borde, y nada más", () => {
    // Vercel sirve antes los ficheros: un incidente publicado nunca llega a la reescritura. Lo
    // demás (un ataque, un unido, uno inventado) lo decide api/borde.ts.
    expect(destinoDeReescritura(vercel, "/EODI-UA-2026-1014")).toBe("/api/borde?id=:id");
    expect(destinoDeReescritura(vercel, "/en/EODI-UA-2026-1014")).toBe("/api/borde?id=:id&idioma=en");
    expect(destinoDeReescritura(vercel, "/EODI-2025-00210")).toBe("/api/borde?id=:id");
    expect(destinoDeReescritura(vercel, "/otra/EODI-2025-00210")).toBeNull();
    expect(destinoDeReescritura(vercel, "/metodologia")).toBeNull();
  });
});

describe("security.txt", () => {
  const texto = securityTxt(new Date("2026-09-30T16:16:34.123Z"));

  it("da el contacto, la dirección canónica y caduca al año", () => {
    expect(texto.split("\n")).toEqual([
      `Contact: mailto:${CONTACTO_SEGURIDAD}`,
      "Expires: 2027-09-30T16:16:34Z",
      "Preferred-Languages: es, en",
      `Canonical: ${ORIGEN}${RUTA_SECURITY_TXT}`,
      "",
    ]);
    expect(RUTA_SECURITY_TXT).toBe("/.well-known/security.txt");
  });
});

describe("regla contra la inserción de HTML", () => {
  const eslint = new ESLint({ cwd: WEB });
  const revisar = async (codigo: string) => {
    const [resultado] = await eslint.lintText(codigo, { filePath: join(WEB, "src", "prueba.tsx") });
    return (resultado?.messages ?? []).map((m) => m.ruleId);
  };

  it.each([
    ["dangerouslySetInnerHTML", "export const X = () => <p dangerouslySetInnerHTML={{ __html: a }} />;"],
    ["props con dangerouslySetInnerHTML", "export const p = { dangerouslySetInnerHTML: { __html: a } };"],
    ["innerHTML", "document.body.innerHTML = a;"],
    ["outerHTML", "document.body.outerHTML = a;"],
    ["insertAdjacentHTML", 'document.body.insertAdjacentHTML("beforeend", a);'],
    ["document.write", "document.write(a);"],
    ["srcDoc", "export const X = () => <iframe title=\"x\" srcDoc={a} />;"],
    ["eval", "eval(a);"],
    ["new Function", "export const f = new Function(a);"],
  ])("el lint rechaza %s", async (_nombre, codigo) => {
    const reglas = await revisar(`declare const a: string;\n${codigo}\n`);
    expect(
      reglas.some((regla) =>
        ["no-restricted-syntax", "no-eval", "no-new-func", "no-implied-eval"].includes(regla ?? ""),
      ),
    ).toBe(true);
  }, 60_000);

  it("ningún fichero de la web usa esas formas ni desactiva la regla", () => {
    const PROHIBIDO =
      /dangerouslySetInnerHTML|\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|srcDoc|no-restricted-syntax/;
    const ficheros = (carpeta: string): string[] =>
      readdirSync(carpeta, { withFileTypes: true }).flatMap((entrada) =>
        entrada.isDirectory()
          ? ficheros(join(carpeta, entrada.name))
          : /\.(ts|tsx)$/.test(entrada.name)
            ? [join(carpeta, entrada.name)]
            : [],
      );
    for (const carpeta of ["src", "scripts"]) {
      for (const fichero of ficheros(join(WEB, carpeta))) {
        expect(PROHIBIDO.test(readFileSync(fichero, "utf-8")), fichero).toBe(false);
      }
    }
  });
});
