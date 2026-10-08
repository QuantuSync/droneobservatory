// @vitest-environment jsdom
// Páginas de servicio público (aviso legal, privacidad, independencia, correcciones y
// accesibilidad), la licencia dentro de los ficheros descargables y en llms.txt.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

import { describe, expect, it } from "vitest";

import { conLicencia, metadatosLicencia } from "../src/datos/licencia.ts";
import { CLAVE_VISITA, registrarVisita } from "../src/estado/novedades.ts";
import type { Resumen } from "../src/datos/tipos.ts";
import { LICENCIA_DATOS_URL } from "../src/sitio.ts";
import { html } from "../src/texto/html.ts";
import { marco, paginaServicio } from "../src/texto/paginas.ts";
import { llmsTxt } from "../src/texto/salidas.ts";
import {
  BORRAR_VISITA,
  CONTACTO,
  PAGINAS_SERVICIO,
  RESPONSABLE,
  RUTAS_SERVICIO,
  SCRIPT_BORRAR_VISITA,
  textoServicio,
} from "../src/texto/servicio.ts";

const ACTUALIZADO = "2026-10-08T12:17Z";

function todoElTexto(pagina: (typeof PAGINAS_SERVICIO)[number], idioma: "es" | "en"): string {
  return JSON.stringify(textoServicio(pagina, idioma));
}

describe("páginas de servicio público", () => {
  it("existen en los dos idiomas con las mismas secciones", () => {
    for (const pagina of PAGINAS_SERVICIO) {
      const es = textoServicio(pagina, "es");
      const en = textoServicio(pagina, "en");
      expect(es.secciones.map((s) => s.id)).toEqual(en.secciones.map((s) => s.id));
      expect(RUTAS_SERVICIO[pagina].en.startsWith("/en/")).toBe(true);
      expect(RUTAS_SERVICIO[pagina].es.startsWith("/en/")).toBe(false);
    }
  });

  it("el aviso legal da el responsable y el contacto; correcciones y privacidad, el correo", () => {
    for (const idioma of ["es", "en"] as const) {
      const aviso = todoElTexto("avisoLegal", idioma);
      expect(aviso).toContain(RESPONSABLE);
      expect(aviso).toContain(CONTACTO);
      expect(todoElTexto("correcciones", idioma)).toContain(CONTACTO);
      expect(todoElTexto("privacidad", idioma)).toContain("eodi.ultima-visita");
    }
  });

  it("no hablan de límites ni nombran otros proyectos", () => {
    for (const pagina of PAGINAS_SERVICIO) {
      for (const idioma of ["es", "en"] as const) {
        expect(todoElTexto(pagina, idioma)).not.toMatch(/l[ií]mite|limitaci|limitation|\blimits?\b/i);
      }
    }
  });

  it("el pie de cada página de texto enlaza las cinco", () => {
    const pagina = {
      idioma: "en" as const,
      rutas: { es: "/ayuda", en: "/en/help" },
      titulo: "t",
      descripcion: "d",
      cuerpo: html("x"),
      estructurados: [],
      conMapa: false,
      modificada: ACTUALIZADO,
    };
    const texto = marco(pagina, ACTUALIZADO).toString();
    for (const p of PAGINAS_SERVICIO) expect(texto).toContain(`href="${RUTAS_SERVICIO[p].en}"`);
  });
});

describe("licencia de los datos abiertos", () => {
  it("va como primer miembro de cada JSON sin cambiar el resto", () => {
    const original = { type: "FeatureCollection", features: [{ id: "x" }], unidos: {} };
    const conElla = JSON.parse(conLicencia(JSON.stringify(original), ACTUALIZADO)) as Record<string, unknown>;
    expect(Object.keys(conElla)[0]).toBe("licencia");
    const { licencia, ...resto } = conElla;
    expect(resto).toEqual(original);
    expect(licencia).toEqual(metadatosLicencia(ACTUALIZADO));
    expect(metadatosLicencia(ACTUALIZADO).url).toBe(LICENCIA_DATOS_URL);
    expect(metadatosLicencia(ACTUALIZADO).alcance.es).toContain("ODbL");
  });

  it("llms.txt dice la licencia, cómo citar y enlaza las páginas nuevas", () => {
    const resumen: Resumen = { actualizado: ACTUALIZADO, incidentes: [], episodios: [], eventos: [] };
    const texto = llmsTxt(resumen);
    expect(texto).toContain(LICENCIA_DATOS_URL);
    expect(texto).toMatch(/How to cite: European Observatory of Drone Incidents/);
    expect(texto).toMatch(/Cómo citar: European Observatory of Drone Incidents/);
    for (const p of PAGINAS_SERVICIO) {
      expect(texto).toContain(RUTAS_SERVICIO[p].es);
      expect(texto).toContain(RUTAS_SERVICIO[p].en);
    }
  });
});

describe("«Borrar mi última visita» en la página de privacidad", () => {
  const SCRIPT = readFileSync(join(import.meta.dirname, "..", "public", SCRIPT_BORRAR_VISITA.slice(1)), "utf-8");

  it("el botón y su script solo están en la página de privacidad, en los dos idiomas", () => {
    for (const idioma of ["es", "en"] as const) {
      for (const p of PAGINAS_SERVICIO) {
        const pagina = paginaServicio(p, idioma);
        const html = pagina.cuerpo.toString();
        expect(html.includes("data-borrar-visita"), `${p} ${idioma}`).toBe(p === "privacidad");
        expect(pagina.scripts ?? []).toEqual(p === "privacidad" ? [SCRIPT_BORRAR_VISITA] : []);
      }
      const privacidad = paginaServicio("privacidad", idioma).cuerpo.toString();
      expect(privacidad).toContain(BORRAR_VISITA[idioma].boton);
      // Sin código, el botón no se ve y la página dice cómo borrarla desde el navegador.
      expect(privacidad).toMatch(/<button[^>]* hidden/);
      expect(privacidad).toContain(`<noscript><p>${BORRAR_VISITA[idioma].sinCodigo}</p></noscript>`);
    }
  });

  it("explica qué guarda, para qué, dónde, que no identifica y cuánto dura", () => {
    const es = JSON.stringify(textoServicio("privacidad", "es"));
    for (const frase of ["fecha y la hora de tu última visita", "Para qué sirve", "No se envía a ningún servidor", "No identifica a nadie", "Cuánto dura", "no se marca nada como nuevo"]) {
      expect(es).toContain(frase);
    }
    const en = JSON.stringify(textoServicio("privacidad", "en"));
    for (const frase of ["date and time of your last visit", "What it is for", "not sent to any server", "does not identify anyone", "How long it lasts", "nothing is marked as new"]) {
      expect(en).toContain(frase);
    }
  });

  it("el script borra la misma clave que guarda la web y dice que se ha borrado", () => {
    expect(SCRIPT).toContain(`"${CLAVE_VISITA}"`);
    const boton = document.createElement("button");
    boton.hidden = true;
    boton.dataset.borrarVisita = "";
    boton.dataset.hecho = "borrada";
    boton.dataset.fallo = "no";
    const estado = document.createElement("p");
    estado.dataset.borrarVisitaEstado = "";
    document.body.append(boton, estado);
    const ventana = window;
    ventana.localStorage.setItem(CLAVE_VISITA, "2026-10-01T10:00:00.000Z");
    ventana.localStorage.setItem("otra", "1");
    // El script tal cual, con el documento y el almacenamiento de la prueba.
    runInNewContext(SCRIPT, { window: ventana, document, HTMLButtonElement });
    expect(boton.hidden).toBe(false);
    boton.click();
    expect(ventana.localStorage.getItem(CLAVE_VISITA)).toBeNull();
    expect(ventana.localStorage.getItem("otra")).toBe("1");
    expect(estado.textContent).toBe("borrada");
    // Después de borrarla, la siguiente visita es como la primera: nada se marca como nuevo.
    expect(registrarVisita(ventana.localStorage, new Date("2026-10-08T12:00:00Z"))).toBeNull();
  });
});
