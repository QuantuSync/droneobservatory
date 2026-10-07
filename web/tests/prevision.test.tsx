// @vitest-environment jsdom
// Previsión y tendencias, el filtro frontera/interior y los contadores con cualquier filtro.
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LeyendaCorredores, LeyendaPresion } from "../src/componentes/Leyendas.tsx";
import { GraficaSemanal, Prevision } from "../src/componentes/Prevision.tsx";
import { cifras } from "../src/datos/derivar.ts";
import { principales } from "../src/datos/guerraSatelite.ts";
import type { Corredor } from "../src/datos/guerraSatelite.ts";
import { marcadorSemanal, rachaDe } from "../src/datos/prevision.ts";
import type { Prevision as DatosPrevision } from "../src/datos/prevision.ts";
import type { Estado, IncidenteResumen, Zona } from "../src/datos/tipos.ts";
import { validarPrevision } from "../src/datos/validar.ts";
import { ESTADOS, ZONAS } from "../src/datos/vocabulario.ts";
import { escribirFiltros, filtrar, leerFiltros, SIN_FILTROS } from "../src/estado/filtros.ts";
import { textos } from "../src/i18n/index.ts";

const es = textos("es");
const en = textos("en");

const RAIZ = join(__dirname, "..", "..");

function publicada(): DatosPrevision {
  const carpeta = process.env.EODI_PUBLICACION ?? join(RAIZ, "tests", "fixtures", "publicacion");
  const valor: unknown = JSON.parse(readFileSync(resolve(carpeta, "prevision.json"), "utf-8"));
  const resultado = validarPrevision(valor);
  if (!resultado.ok) throw new Error(resultado.errores.join("; "));
  return resultado.datos;
}

afterEach(cleanup);

describe("prevision.json", () => {
  it("el fichero publicado cumple su esquema y solo trae lo comprobado", () => {
    const d = publicada();
    for (const p of d.frontera.paises) {
      expect(p.comprobacion.publicable).toBe(true);
      expect(p.comprobacion.mejora_cota).toBeGreaterThan(0);
      expect(p.de_cada_10).toBe(Math.round(p.probabilidad * 10));
    }
    for (const s of d.semana.paises) expect(s.minimo).toBeLessThanOrEqual(s.maximo);
  });

  it("un campo desconocido o una probabilidad fuera de 0-1 no valida", () => {
    const d = publicada();
    expect(validarPrevision({ ...d, otra: 1 }).ok).toBe(false);
    const mala = structuredClone(d);
    const primero = mala.frontera.paises[0];
    if (primero !== undefined) {
      primero.probabilidad = 1.5;
      expect(validarPrevision(mala).ok).toBe(false);
    }
  });

  it("el marcador pone las previsiones en vivo puntuadas en lugar de las reconstruidas", () => {
    const d = publicada();
    const fila = d.semana.marcador[0];
    if (fila === undefined) return;
    const viva = {
      id: `semana:${fila.pais}:${fila.semana}`,
      tipo: "semana" as const,
      pais: fila.pais,
      objetivo: fila.semana,
      emitida: "2026-01-01T00:17Z",
      metodo: "semana-1.0.0",
      esperado: 9,
      minimo: 1,
      maximo: 20,
      real: fila.real,
      dentro: true,
    };
    const marcador = marcadorSemanal({ ...d, registro: [viva] });
    const misma = marcador.find((f) => f.pais === fila.pais && f.semana === fila.semana);
    expect(misma?.tipo).toBe("en_vivo");
    expect(misma?.esperado).toBe(9);
  });
});

describe("panel «Previsión»", () => {
  it("dice la probabilidad en palabras y con su número, y el historial de aciertos", () => {
    const d = publicada();
    render(<Prevision t={es} idioma="es" carga={{ estado: "listo", datos: d }} onRacha={() => {}} />);
    for (const p of d.frontera.paises) {
      const texto = document.querySelector(`[data-frontera="${p.pais}"]`)?.textContent ?? "";
      expect(texto).toContain(`${p.de_cada_10} de cada 10 noches como esta`);
      expect(texto).toContain(`(${Math.round(p.probabilidad * 100)} %)`);
    }
    expect(document.querySelector("[data-historial-frontera]")).not.toBeNull();
    // Sin aviso de segunda noche, no ocupa sitio.
    expect(document.querySelector('[data-prevision-seccion="segunda-noche"]')).toBeNull();
  });

  it("tocar una racha la pide con su país y su periodo", async () => {
    const d = publicada();
    const racha = d.rachas?.activas[0];
    if (racha === undefined) return;
    const onRacha = vi.fn();
    render(<Prevision t={en} idioma="en" carga={{ estado: "listo", datos: d }} onRacha={onRacha} />);
    await userEvent.setup().click(screen.getAllByRole("button", { name: /Show .* on the map/ })[0] as HTMLElement);
    expect(onRacha).toHaveBeenCalledWith(racha);
    expect(rachaDe(d, racha.pais)?.racha).toEqual(racha);
  });

  it("la gráfica de la ficha tiene su texto y una barra por semana", () => {
    render(
      <GraficaSemanal t={es} idioma="es" grafica={{ semanas: ["2026-09-21", "2026-09-28"], incidentes: [0, 4], normal: 0.5, banda: [0, 2] }} />,
    );
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain("4 incidentes");
    expect(document.querySelectorAll("[data-grafica-racha] rect")).toHaveLength(3);
  });
});

function incidente(estado: Estado, zona: Zona | null, pais = "RO"): IncidenteResumen {
  return {
    id: `EODI-2026-${Math.random().toString().slice(2, 7)}`,
    punto: null,
    imprecisa: null,
    tipo: "sobrevuelo",
    estado,
    presencia: null,
    titulo: { es: "a", en: "a" },
    dia: 20000,
    inicio: null,
    pais,
    objetivo: null,
    episodio: null,
    foco: false,
    atribucion: null,
    zona,
    dron: [],
  };
}

describe("filtro frontera / interior y contadores", () => {
  const todos = [
    ...ESTADOS.flatMap((estado) => ZONAS.map((zona) => incidente(estado, zona))),
    incidente("confirmado", null, "DE"),
  ];

  it("va en la dirección y por defecto son todos", () => {
    expect(leerFiltros("").zona).toBeNull();
    expect(leerFiltros("?zona=frontera").zona).toBe("frontera");
    expect(leerFiltros("?zona=otra").zona).toBeNull();
    expect(escribirFiltros({ ...SIN_FILTROS, zona: "interior" })).toBe("?zona=interior");
  });

  it("los confirmados incluyen a los atribuidos con cualquier combinación de filtros", () => {
    const combinaciones = [
      SIN_FILTROS,
      { ...SIN_FILTROS, estados: ["atribuido" as const] },
      { ...SIN_FILTROS, estados: ["confirmado" as const] },
      { ...SIN_FILTROS, zona: "frontera" as const },
      { ...SIN_FILTROS, zona: "interior" as const, estados: ["atribuido" as const, "notificado" as const] },
      { ...SIN_FILTROS, paises: ["DE"] },
    ];
    for (const filtros of combinaciones) {
      const vistos = filtrar(todos, filtros);
      const c = cifras(vistos);
      expect(c.incidentes).toBe(vistos.length);
      expect(c.confirmados).toBe(vistos.filter((i) => i.estado === "confirmado" || i.estado === "atribuido").length);
      expect(c.atribuidos).toBeLessThanOrEqual(c.confirmados);
      expect(c.confirmados).toBeLessThanOrEqual(c.incidentes);
    }
    expect(cifras(filtrar(todos, { ...SIN_FILTROS, estados: ["atribuido"] }))).toMatchObject({ confirmados: 2, atribuidos: 2 });
  });

  it("frontera más interior son todos los que tienen grupo", () => {
    const frontera = filtrar(todos, { ...SIN_FILTROS, zona: "frontera" }).length;
    const interior = filtrar(todos, { ...SIN_FILTROS, zona: "interior" }).length;
    expect(frontera + interior).toBe(todos.filter((i) => i.zona !== null).length);
  });
});

describe("leyendas", () => {
  it("Presión con todo el periodo pide elegir un periodo para ver la tendencia", () => {
    render(<LeyendaPresion t={es} seleccion={{ clase: "todo" }} />);
    expect(document.querySelector("[data-elige-periodo]")?.textContent).toBe("Elige un periodo para ver la tendencia");
    cleanup();
    render(<LeyendaPresion t={en} seleccion={{ clase: "reciente", reciente: "7d" }} />);
    expect(document.querySelector("[data-elige-periodo]")).toBeNull();
  });

  it("con muchos corredores solo se dibujan los principales y se pueden ver todos", async () => {
    const corredor = (i: number, drones: number): Corredor => ({
      clave: `z${i}|UA-${i}`,
      sentido: "RU_UA",
      origen: `z${i}`,
      desde: [37, 47],
      region: `UA-${i}`,
      hasta: [30, 50],
      drones,
      ataques: 1,
    });
    const muchos = Array.from({ length: 200 }, (_, i) => ({
      ...corredor(i, 1000 - i * 4),
      sentido: i % 3 === 0 ? ("UA_RU" as const) : ("RU_UA" as const),
    }));
    const elegidos = principales(muchos);
    // Los 50 de más drones en total, sumando los dos sentidos.
    expect(elegidos.length).toBe(50);
    expect(elegidos[0]?.drones).toBe(1000);
    expect(elegidos[49]?.drones).toBe(1000 - 49 * 4);
    expect(new Set(elegidos.map((c) => c.sentido)).size).toBe(2);
    const onTodos = vi.fn();
    render(<LeyendaCorredores t={es} principales={50} total={200} todos={false} onTodos={onTodos} />);
    expect(screen.getByText(/^50 de 200 corredores/)).toBeTruthy();
    await userEvent.setup().click(screen.getByRole("button", { name: "Ver los 200" }));
    expect(onTodos).toHaveBeenCalled();
  });

  it("con 50 corredores o menos, la leyenda los cuenta y no ofrece ver todos", () => {
    render(<LeyendaCorredores t={en} principales={23} total={23} todos={false} onTodos={() => undefined} />);
    expect(screen.getByText(/^All 23 corridors in the period/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
