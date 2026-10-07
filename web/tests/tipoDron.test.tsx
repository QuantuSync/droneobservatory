// @vitest-environment jsdom
// Tipo de dron: la fila de la ficha (identificado por la autoridad o deducido, y nada sin base),
// el filtro por clase y la misma fila en la página de texto.

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { Filtros } from "../src/componentes/Filtros.tsx";
import { clavesDron, detalleIncidente, resumir, resumirIncidente } from "../src/datos/derivar.ts";
import type { TipoDron } from "../src/datos/tipos.ts";
import { validarColeccion, validarResumen } from "../src/datos/validar.ts";
import { SIN_FILTROS, TODO, escribirFiltros, filtrar, leerFiltros } from "../src/estado/filtros.ts";
import { textos } from "../src/i18n/index.ts";
import { filaTipoDron } from "../src/texto/paginas.ts";
import { coleccion, fuente, incidente, publicacion } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");

const DEDUCIDO: TipoDron = {
  version: "tipo-dron-1.0.0",
  publicado: {
    presentacion: "probabilidades",
    compatible: [
      { grupo: "largo_alcance_helice", probabilidad: 0.49 },
      { grupo: "senuelo", probabilidad: 0.42 },
    ],
    otras: 0.09,
    casos_referencia: 26,
  },
  razones: [
    {
      tipo: "rasgo",
      clave: "tamano:pequeno",
      datos: { rasgo: "tamano", valor: "pequeno", cita: "un aparat zburător de mici dimensiuni", fuente: "f1" },
    },
    { tipo: "restriccion", clave: "distancia", datos: { distancia_km: 64.2, mas_de_600_km: false, entrada_exterior: true } },
  ],
};
// Lo de casi todos los incidentes de la frontera: ataque y señuelo no se distinguen.
const GUERRA: TipoDron = {
  version: "tipo-dron-1.1.0",
  publicado: {
    presentacion: "compatible_guerra",
    compatible: [{ grupo: "largo_alcance_helice" }, { grupo: "senuelo" }],
    casos_referencia: 26,
  },
  razones: [
    {
      tipo: "restriccion",
      clave: "entrada_exterior",
      datos: { distancia_km: 12.4, mas_de_600_km: false, costa_km: 300, entrada_exterior: true },
    },
  ],
};
// Lo que se publicaba antes sin ninguna razón: ya no tiene fila.
const SIN_RAZON: TipoDron = { ...GUERRA, razones: [] };
const IDENTIFICADO: TipoDron = {
  version: "tipo-dron-1.0.0",
  identificado: { modelo: "Gerbera", grupo: "senuelo", cita: "Două drone UAV, tip Gerbera", fuente: "f1" },
};

function con(tipo: TipoDron | undefined) {
  return incidente({
    ...(tipo === undefined ? {} : { tipo_dron: tipo }),
    zona: { grupo: "frontera", motivo: "cerca_de_la_frontera" },
    fuentes: [fuente({ id: "f1", medio: "MApN" })],
  });
}

describe("tipo de dron", () => {
  it("valida lo que publica la recogida", () => {
    expect(validarColeccion(coleccion([con(DEDUCIDO), con(IDENTIFICADO), con(GUERRA)])).ok).toBe(true);
    // El resumen que genera el build, con el modelo del identificado para el filtro, también.
    const resumen = resumir(coleccion([con(IDENTIFICADO)]), publicacion([]));
    expect(resumen.incidentes[0]?.modeloDron).toBe("Gerbera");
    expect(validarResumen(resumen).ok).toBe(true);
  });

  it("sin distinción dice una sola cosa, sin porcentajes, con su razón debajo", () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(con(GUERRA))} />);
    expect(document.querySelector("[data-tipo-dron='guerra']")?.textContent).toBe(
      "Compatible con un dron de largo alcance de la guerra (de ataque o señuelo)",
    );
    expect(document.querySelector("[data-razon='entrada_exterior']")?.textContent).toContain(
      "Entró desde fuera, a 12 km de Ucrania, Rusia o Bielorrusia",
    );
    expect(document.body.textContent).not.toMatch(/%|de cada 10/);
    cleanup();
    render(<FichaIncidente t={en} idioma="en" incidente={detalleIncidente(con(GUERRA))} />);
    expect(document.body.textContent).toContain("Compatible with a long-range drone of the war (attack or decoy)");
  });

  it("sin ninguna razón no hay fila", () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(con(SIN_RAZON))} />);
    expect(document.querySelector("[data-tipo-dron]")).toBeNull();
    expect(filaTipoDron(es, detalleIncidente(con(SIN_RAZON)))).toBe(false);
  });

  it("lo identificado por la autoridad dice el modelo y su fuente", () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(con(IDENTIFICADO))} />);
    expect(screen.getByText("Gerbera, según la autoridad")).toBeTruthy();
    expect(document.body.textContent).toContain("Două drone UAV, tip Gerbera");
    expect(document.body.textContent).toContain("según MApN");
    expect(document.body.textContent).not.toContain("Compatible con");
  });

  it("lo deducido dice «compatible con», su probabilidad y por qué", async () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(con(DEDUCIDO))} />);
    expect(document.querySelector("[data-tipo-dron='deducido']")?.textContent).toBe("Compatible con");
    expect(document.body.textContent).toContain("Dron de ataque de largo alcance de hélice");
    expect(document.body.textContent).toContain("5 de cada 10 (49 %)");
    expect(document.body.textContent).toContain("Otras clases: 9 %");
    expect(document.body.textContent).toContain("ninguna autoridad ha dicho qué dron era");
    await userEvent.setup().click(screen.getByText("Por qué"));
    expect(document.body.textContent).toContain("26 casos de frontera");
    expect(document.body.textContent).toContain("«un aparat zburător de mici dimensiuni»");
    expect(document.body.textContent).toContain("a 64 km de Ucrania, Rusia o Bielorrusia");
    // Nunca se nombra un modelo que la autoridad no ha nombrado.
    expect(document.body.textContent).not.toMatch(/Shahed|Geran|Gerbera/);
  });

  it("sin base la fila no aparece", () => {
    render(<FichaIncidente t={en} idioma="en" incidente={detalleIncidente(con(undefined))} />);
    expect(document.querySelector("[data-tipo-dron]")).toBeNull();
    expect(document.body.textContent).not.toContain("Drone type");
  });

  it("el filtro separa lo identificado de lo compatible con dron de la guerra y va en la dirección", async () => {
    const guerra = resumirIncidente(con(GUERRA));
    const identificado = { ...resumirIncidente(con(IDENTIFICADO)), id: "EODI-2025-00211" };
    const sin = { ...resumirIncidente(con(undefined)), id: "EODI-2025-00212" };
    expect(clavesDron(GUERRA)).toEqual(["deducido:guerra"]);
    // Con porcentajes, solo el grupo que destaca.
    expect(clavesDron(DEDUCIDO)).toEqual(["deducido:largo_alcance_helice"]);
    expect(identificado.dron).toEqual(["autoridad:senuelo"]);
    expect(identificado.modeloDron).toBe("Gerbera");
    const todos = [guerra, identificado, sin];
    expect(filtrar(todos, { ...SIN_FILTROS, dron: ["autoridad:senuelo"] }).map((i) => i.id)).toEqual([
      "EODI-2025-00211",
    ]);
    expect(filtrar(todos, { ...SIN_FILTROS, dron: ["deducido:guerra"] })).toHaveLength(1);
    const busqueda = escribirFiltros({ ...SIN_FILTROS, dron: ["deducido:guerra", "autoridad:senuelo"] });
    expect(busqueda).toBe("?dron=autoridad:senuelo,deducido:guerra");
    expect(leerFiltros(`${busqueda},deducido:otra,cosa`).dron).toEqual(["autoridad:senuelo", "deducido:guerra"]);

    const onFiltros = vi.fn();
    render(
      <Filtros
        t={es}
        idioma="es"
        filtros={SIN_FILTROS}
        onFiltros={onFiltros}
        seleccion={TODO}
        onSeleccion={() => undefined}
        dominio={null}
        paises={["RO"]}
        onQuitar={() => undefined}
        dron={["autoridad:senuelo", "deducido:guerra"]}
        modelosDron={{ "autoridad:senuelo": ["Gerbera"] }}
      />,
    );
    const filtro = document.querySelector("[data-filtro-dron]")?.textContent ?? "";
    expect(filtro).toContain("Identificado por la autoridad");
    expect(filtro).toContain("Compatible con dron de largo alcance de la guerra");
    // No se ofrecen clases que no se distinguen.
    expect(filtro).not.toContain("Dron de ataque de largo alcance de hélice");
    await userEvent.setup().click(screen.getByRole("button", { name: "Señuelo de largo alcance (Gerbera)" }));
    expect(onFiltros).toHaveBeenCalledWith({ ...SIN_FILTROS, dron: ["autoridad:senuelo"] });
  });

  it("la página de texto dice lo mismo que la ficha", () => {
    const deducido = String(filaTipoDron(es, detalleIncidente(con(DEDUCIDO))));
    expect(deducido).toContain("Compatible con");
    expect(deducido).toContain("5 de cada 10 (49 %)");
    expect(deducido).toContain("26 casos de frontera");
    const guerra = String(filaTipoDron(es, detalleIncidente(con(GUERRA))));
    expect(guerra).toContain("Compatible con un dron de largo alcance de la guerra (de ataque o señuelo)");
    expect(guerra).toContain("Entró desde fuera");
    expect(guerra).not.toContain("%");
    const identificado = String(filaTipoDron(en, detalleIncidente(con(IDENTIFICADO))));
    expect(identificado).toContain("Gerbera, according to the authority");
    expect(filaTipoDron(es, detalleIncidente(con(undefined)))).toBe(false);
  });
});
