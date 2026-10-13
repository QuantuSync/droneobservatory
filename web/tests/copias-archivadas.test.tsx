// @vitest-environment jsdom
// Copias archivadas de las fuentes (recogida/archivo_web.py): al lado del original, «copia
// archivada»; con el original caído, la copia es el enlace principal, se dice y el original sigue a
// la vista; caído y sin copia, el aviso. Igual en la ficha, en la lista de fuentes y en las páginas
// de texto, en español y en inglés; la validación acepta los dos campos y rechaza una copia que no
// es de Internet Archive.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EnlaceFuente } from "../src/componentes/EnlaceFuente.tsx";
import { ListaFuentes } from "../src/componentes/Fuentes.tsx";
import { validarColeccion } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { enlaceDeFuente } from "../src/texto/paginas.ts";
import { coleccion, fuente, incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");
const ORIGINAL = "https://news.yam.md/ro/story/62650046";
const COPIA = { enlace: `https://web.archive.org/web/20260909192419/${ORIGINAL}`, fecha: "2026-09-09T19:24:19Z" };

describe("enlace de una fuente con copia archivada", () => {
  it("vivo y con copia: el original primero y «copia archivada» al lado", () => {
    const { container } = render(
      <EnlaceFuente t={es} fuente={fuente({ enlace: ORIGINAL, copia_archivada: COPIA })}>
        news.yam.md
      </EnlaceFuente>,
    );
    const enlaces = [...container.querySelectorAll("a")];
    expect(enlaces.map((a) => a.getAttribute("href"))).toEqual([ORIGINAL, COPIA.enlace]);
    expect(enlaces[1]?.textContent).toContain("copia archivada");
    expect(enlaces[1]?.textContent).toContain("09/09/2026");
    expect(container.querySelector("[data-copia-principal]")).toBeNull();
  });

  it("caído y con copia: la copia es el enlace principal y se dice", () => {
    const { container } = render(
      <EnlaceFuente t={en} fuente={fuente({ enlace: ORIGINAL, copia_archivada: COPIA, enlace_caido: true })}>
        news.yam.md
      </EnlaceFuente>,
    );
    const enlaces = [...container.querySelectorAll("a")];
    expect(enlaces.map((a) => a.getAttribute("href"))).toEqual([COPIA.enlace, ORIGINAL]);
    expect(enlaces[0]?.textContent).toContain("news.yam.md");
    const nota = container.querySelector("[data-copia-principal]")?.textContent ?? "";
    expect(nota).toContain("archived copy from 09/09/2026");
    expect(nota).toContain("the original is no longer available");
    expect(enlaces[1]?.textContent).toContain("original link");
  });

  it("caído y sin copia: el original con el aviso", () => {
    const { container } = render(
      <EnlaceFuente t={es} fuente={fuente({ enlace: ORIGINAL, enlace_caido: true })}>
        news.yam.md
      </EnlaceFuente>,
    );
    expect([...container.querySelectorAll("a")].map((a) => a.getAttribute("href"))).toEqual([ORIGINAL]);
    expect(container.querySelector("[data-enlace-caido]")?.textContent).toContain("enlace caído, sin copia archivada");
  });

  it("sin datos de archivo: como siempre, un solo enlace", () => {
    const { container } = render(
      <EnlaceFuente t={es} fuente={fuente({ enlace: ORIGINAL })}>
        news.yam.md
      </EnlaceFuente>,
    );
    expect(container.querySelectorAll("a")).toHaveLength(1);
  });

  it("la lista de fuentes de la ficha lo usa", () => {
    const { container } = render(
      <ListaFuentes t={es} fuentes={[fuente({ enlace: ORIGINAL, copia_archivada: COPIA, enlace_caido: true })]} />,
    );
    expect(container.querySelector("a")?.getAttribute("href")).toBe(COPIA.enlace);
    expect(container.querySelector("[data-copia-principal]")).not.toBeNull();
  });

  it("las páginas de texto, igual en los dos idiomas", () => {
    const caida = fuente({ enlace: ORIGINAL, copia_archivada: COPIA, enlace_caido: true });
    const html = enlaceDeFuente(es, caida, "ver la fuente").valor;
    expect(html.indexOf(COPIA.enlace)).toBeLessThan(html.indexOf(`href="${ORIGINAL}"`));
    expect(html).toContain("el original ya no está disponible");
    const viva = enlaceDeFuente(en, fuente({ enlace: ORIGINAL, copia_archivada: COPIA }), "see the source").valor;
    expect(viva).toContain("archived copy");
    expect(viva.indexOf(`href="${ORIGINAL}"`)).toBeLessThan(viva.indexOf(COPIA.enlace));
  });

  it("la validación acepta los campos y rechaza una copia ajena", () => {
    const buena = coleccion([incidente({ fuentes: [fuente({ copia_archivada: COPIA, enlace_caido: true })] })]);
    expect(validarColeccion(buena).ok).toBe(true);
    const mala = coleccion([
      incidente({ fuentes: [fuente({ copia_archivada: { enlace: "https://otra.example/copia", fecha: COPIA.fecha } })] }),
    ]);
    expect(validarColeccion(mala).ok).toBe(false);
  });
});
