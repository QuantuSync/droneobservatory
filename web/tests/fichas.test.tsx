// @vitest-environment jsdom
// Repaso de todas las fichas: cada incidente publicado se dibuja en español y en inglés y se mira
// lo que ve quien la abre. Corre con los datos de prueba y, en la integración continua, con los
// publicados (EODI_PUBLICACION). Los nombres y los titulares los revisa además la prueba de Python
// tests/test_nombres_publicados.py (formas de la otra versión, palabras de otro idioma).
//
// Fuera de las citas (blockquote, q y lo que dice cada fuente, que van en su lengua), ninguna fila
// lleva otro alfabeto ni palabras de otro idioma; «Lugar» dice la localidad cuando se conoce;
// «Frontera o interior» solo sale en el flanco este; ninguna fila sale vacía; el modelo de dron
// solo si es un nombre de modelo; ninguna autoridad sale con su nombre en otro idioma (la de la
// tabla, la traducida en los datos o «una autoridad»; tests/autoridades-idioma.test.tsx).

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FichaImpacto } from "../src/componentes/FichaImpacto.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { detalleIncidente, detalleSinUbicacion } from "../src/datos/derivar.ts";
import { enFlancoEste, FLANCO_ESTE, localidadDeImpacto, lugarDeImpacto, modeloEscrito } from "../src/datos/nombres.ts";
import type { IncidenteDetalle } from "../src/datos/tipos.ts";
import { validarColeccion, validarPublicacionUcrania, validarSinUbicacion } from "../src/datos/validar.ts";
import { AUTORIDADES, autoridadEscrita, medioEscrito } from "../src/i18n/autoridades.ts";
import { textos } from "../src/i18n/index.ts";
import type { Idioma } from "../src/sitio.ts";

const RAIZ = join(import.meta.dirname, "..", "..");
const CARPETA = process.env.EODI_PUBLICACION ?? join(RAIZ, "tests", "fixtures", "publicacion");
const CONFIGURACION = JSON.parse(
  readFileSync(join(RAIZ, "configuracion", "nombres_lugar.json"), "utf-8"),
) as { flanco_este: string[]; palabras_ajenas: { tercer_idioma: string[]; ingles: string[]; espanol: string[] } };

function leer(nombre: string): unknown {
  return JSON.parse(readFileSync(resolve(CARPETA, nombre), "utf-8")) as unknown;
}

function exigir<T>(resultado: { ok: true; datos: T } | { ok: false; errores: string[] }): T {
  if (!resultado.ok) throw new Error(resultado.errores.join("; "));
  return resultado.datos;
}

const incidentes: IncidenteDetalle[] = [
  ...exigir(validarColeccion(leer("incidentes.geojson"))).features.map(detalleIncidente),
  ...exigir(validarSinUbicacion(leer("incidentes_sin_ubicacion.json"))).incidentes.map(detalleSinUbicacion),
];

const escapar = (palabra: string) => palabra.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function patron(palabras: readonly string[]): RegExp {
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${palabras.map(escapar).join("|")})(?![\\p{L}\\p{N}])`, "u");
}
const AJENAS: Record<Idioma, RegExp> = {
  es: patron([...CONFIGURACION.palabras_ajenas.tercer_idioma, ...CONFIGURACION.palabras_ajenas.ingles]),
  en: patron([...CONFIGURACION.palabras_ajenas.tercer_idioma, ...CONFIGURACION.palabras_ajenas.espanol]),
};
const OTRO_ALFABETO = /[^\p{Script=Latin}\p{Script=Common}\p{Script=Inherited}]/u;

/** El texto de un nodo sin las citas: lo que dicen las fuentes va en su lengua. */
function sinCitas(nodo: Element): string {
  const copia = nodo.cloneNode(true) as Element;
  copia.querySelectorAll("blockquote, q, details, [lang]").forEach((cita) => cita.remove());
  // Las citas dentro de una frase van entre comillas («…», “…”): también en su lengua.
  const texto = copia.textContent?.replace(/«[^»]*»|“[^”]*”/g, "") ?? "";
  return texto.replace(/\s+/g, " ").trim();
}

const ORIGINALES = Object.entries(AUTORIDADES)
  .filter(([, autoridad]) => autoridad.original === true)
  .map(([original]) => `(${original})`)
  .sort((a, b) => b.length - a.length);

function sinOriginales(texto: string): string {
  return ORIGINALES.reduce((resto, original) => resto.split(original).join(""), texto.normalize("NFC"));
}

const DECLARACION = /^(.+) \(declaración oficial citada en .+\)$/;

/** Las autoridades que enseña una ficha (declaraciones citadas, fuentes oficiales sin dominio, la
 *  que atribuye y las que investigan), como las guardan los datos. */
function autoridadesDe(datos: {
  fuentes: readonly { medio: string }[];
  atribucion?: { autoridad: string };
  investigacion?: readonly { autoridad: string }[];
}): string[] {
  const nombres = new Set<string>();
  for (const fuente of datos.fuentes) {
    const declaracion = DECLARACION.exec(fuente.medio);
    if (declaracion?.[1] !== undefined) nombres.add(declaracion[1]);
    else if (!fuente.medio.includes(".")) nombres.add(fuente.medio);
  }
  if (datos.atribucion !== undefined) nombres.add(datos.atribucion.autoridad);
  for (const entrada of datos.investigacion ?? []) nombres.add(entrada.autoridad);
  return [...nombres];
}

/** Los nombres de autoridad que salen tal como los guardan los datos y no como se escriben en la
 *  página (fuera de las citas y del nombre oficial entre paréntesis tras la traducción). */
function autoridadesSinTraducir(nombres: readonly string[], texto: string, idioma: Idioma): string[] {
  // Fuera lo que ya sale bien escrito (también en mayúscula, como nombre de fuente): así un nombre
  // que va dentro de otro («Ministry of National Defence» en «the Romanian Ministry of National
  // Defence») no cuenta. Se compara en forma compuesta.
  const escritas = nombres.map((nombre) => autoridadEscrita(nombre, idioma).normalize("NFC"));
  let resto = texto.normalize("NFC");
  for (const escrita of [...escritas].sort((a, b) => b.length - a.length)) {
    for (const forma of [escrita, escrita.charAt(0).toUpperCase() + escrita.slice(1)]) resto = resto.split(forma).join(" ");
  }
  resto = sinOriginales(resto);
  return nombres.filter((nombre, i) => {
    const original = nombre.normalize("NFC");
    return !(escritas[i] ?? "").includes(original) && resto.includes(original);
  });
}

function filas(ficha: Element): Map<string, Element> {
  const salida = new Map<string, Element>();
  ficha.querySelectorAll("dt").forEach((dt) => {
    const dd = dt.nextElementSibling;
    if (dd !== null) salida.set(dt.textContent?.trim() ?? "", dd);
  });
  return salida;
}

function contexto(texto: string, posicion: number): string {
  return texto.slice(Math.max(0, posicion - 40), posicion + 40);
}

/** Lo que está mal en la ficha de un incidente en un idioma. */
function problemas(incidente: IncidenteDetalle, idioma: Idioma): string[] {
  const t = textos(idioma);
  const { container } = render(<FichaIncidente t={t} idioma={idioma} incidente={incidente} />);
  const salida: string[] = [];
  const titular = container.querySelector("h2")?.textContent?.trim() ?? "";
  if (titular === "") salida.push("sin título");
  const deFilas = filas(container);
  // Toda la ficha (filas, fuentes, historial), sin las citas y sin el nombre oficial que sigue
  // entre paréntesis a una institución traducida («el Gobierno federal alemán (Bundesregierung)»).
  const visibles = [titular, ...[...deFilas.values()].map(sinCitas), sinOriginales(sinCitas(container))];
  const sinTitular = sinCitas(container).replace(titular, "");
  for (const nombre of autoridadesSinTraducir(autoridadesDe(incidente), sinTitular, idioma)) {
    salida.push(`autoridad sin traducir: «${nombre}»`);
  }
  for (const texto of visibles) {
    const otro = OTRO_ALFABETO.exec(texto);
    if (otro !== null) salida.push(`otro alfabeto: «${contexto(texto, otro.index)}»`);
    const ajena = AJENAS[idioma].exec(texto);
    if (ajena !== null) salida.push(`palabra de otro idioma «${ajena[0]}»: «${contexto(texto, ajena.index)}»`);
  }
  for (const [nombre, dd] of deFilas) {
    if ((dd.textContent ?? "").trim() === "") salida.push(`fila vacía: ${nombre}`);
  }
  const lugar = deFilas.get(t.ficha.lugar)?.querySelector("[data-lugar]")?.textContent ?? "";
  if (incidente.nombres !== undefined && lugar !== incidente.nombres.lugar[idioma]) {
    salida.push(`«Lugar» no es el publicado: «${lugar}»`);
  }
  const localidad = incidente.nombres?.localidad?.[idioma];
  if (localidad !== undefined && !lugar.startsWith(localidad)) salida.push(`«Lugar» sin su localidad: «${lugar}»`);
  const conZona = deFilas.has(t.zona.titulo);
  if (conZona && !enFlancoEste(incidente)) salida.push("«Frontera o interior» fuera del flanco este");
  if (!conZona && incidente.zona !== undefined && enFlancoEste(incidente)) {
    salida.push("sin «Frontera o interior» en el flanco este");
  }
  cleanup();
  return salida;
}

afterEach(cleanup);

describe("todas las fichas, en español y en inglés", () => {
  it("hay incidentes que revisar", () => {
    expect(incidentes.length).toBeGreaterThan(0);
  });

  it("el flanco este es el de la configuración", () => {
    expect([...FLANCO_ESTE].sort()).toEqual([...CONFIGURACION.flanco_este].sort());
  });

  it("solo los nombres de modelo se enseñan como modelo", () => {
    expect(modeloEscrito("Shahed 136")).toBe("Shahed 136");
    expect(modeloEscrito("Geran-2")).toBe("Geran-2");
    expect(modeloEscrito("drone russe")).toBeNull();
    expect(modeloEscrito("крило")).toBeNull();
    expect(modeloEscrito("10ft")).toBeNull();
  });

  it("ninguna ficha enseña nada mal escrito, fuera de lugar o vacío", { timeout: 300_000 }, () => {
    const malas: Record<string, string[]> = {};
    for (const incidente of incidentes) {
      for (const idioma of ["es", "en"] as const) {
        const encontrados = problemas(incidente, idioma);
        if (encontrados.length > 0) malas[`${incidente.id} ${idioma}`] = encontrados;
      }
    }
    expect(malas).toEqual({});
  });

  it("la capa de guerra: cada lugar y cada fuente en el idioma de la página, nunca en cirílico", () => {
    const ucrania = exigir(validarPublicacionUcrania(leer("ucrania.json")));
    const malos = new Set<string>();
    for (const idioma of ["es", "en"] as const) {
      const t = textos(idioma);
      for (const impacto of ucrania.impactos ?? []) {
        const nombre = lugarDeImpacto(impacto.lugar, idioma);
        if (nombre !== null && OTRO_ALFABETO.test(nombre)) malos.add(`${impacto.id}: ${nombre}`);
        const localidad = impacto.lugar.localidad;
        if (localidad !== undefined && localidadDeImpacto(localidad, idioma) === null) malos.add(`${impacto.id}: ${localidad}`);
        for (const fuente of impacto.fuentes) {
          const medio = medioEscrito(fuente.medio, idioma, t.ficha.declaracionCitada);
          if (OTRO_ALFABETO.test(medio)) malos.add(`${impacto.id}: ${medio}`);
        }
      }
      for (const ataque of ucrania.ataques) {
        for (const fuente of ataque.fuentes) {
          const medio = medioEscrito(fuente.medio, idioma, t.ficha.declaracionCitada);
          if (OTRO_ALFABETO.test(medio)) malos.add(`${ataque.id}: ${medio}`);
        }
      }
    }
    expect([...malos]).toEqual([]);
  });

  it("las fichas de impactos de la capa de guerra no enseñan nada en cirílico fuera de las citas", () => {
    const ucrania = exigir(validarPublicacionUcrania(leer("ucrania.json")));
    // Uno de cada fuente distinta: la ficha cambia con el lugar y con la fuente.
    const porFuente = new Map<string, NonNullable<typeof ucrania.impactos>[number]>();
    for (const impacto of ucrania.impactos ?? []) {
      const clave = `${impacto.fuentes[0]?.medio ?? ""}|${impacto.lugar.nivel}`;
      if (!porFuente.has(clave)) porFuente.set(clave, impacto);
    }
    const malos: string[] = [];
    for (const idioma of ["es", "en"] as const) {
      for (const impacto of porFuente.values()) {
        const { container } = render(<FichaImpacto t={textos(idioma)} idioma={idioma} impacto={impacto} />);
        const texto = sinCitas(container);
        for (const nombre of autoridadesSinTraducir(autoridadesDe(impacto), texto, idioma)) {
          malos.push(`${impacto.id} ${idioma}: autoridad sin traducir «${nombre}»`);
        }
        const otro = OTRO_ALFABETO.exec(texto);
        if (otro !== null) malos.push(`${impacto.id} ${idioma}: ${contexto(texto, otro.index)}`);
        cleanup();
      }
    }
    expect(malos).toEqual([]);
  });
});
