import { describe, expect, it } from "vitest";

import { FUENTES_PRECARGADAS, precargarFuentes } from "../scripts/paginas.ts";

const HTML = "<html><head><title>x</title></head><body></body></html>";

describe("fuentes pedidas desde la cabecera", () => {
  it("pide cada fuente de la primera pintura por su nombre con huella", () => {
    const ficheros = [
      "onest-latin-wght-normal-Dun_Rd-l.woff2",
      "onest-cyrillic-wght-normal-AAAA.woff2",
      "jetbrains-mono-latin-wght-normal-B9CIFXIH.woff2",
      "app-123.js",
    ];
    const html = precargarFuentes(HTML, ficheros);
    expect(html).toContain(
      '<link rel="preload" href="/assets/onest-latin-wght-normal-Dun_Rd-l.woff2" as="font" type="font/woff2" crossorigin>',
    );
    expect(html).toContain('href="/assets/jetbrains-mono-latin-wght-normal-B9CIFXIH.woff2"');
    expect(html).not.toContain("cyrillic");
    expect(html.match(/rel="preload"/g)).toHaveLength(FUENTES_PRECARGADAS.length);
    expect(html.indexOf("preload")).toBeLessThan(html.indexOf("</head>"));
  });

  it("sin la fuente en el build no añade nada", () => {
    expect(precargarFuentes(HTML, ["app-123.js"])).toBe(HTML);
  });
});
