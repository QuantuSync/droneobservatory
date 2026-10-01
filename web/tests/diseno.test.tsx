// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App.tsx";
import { Feed, haceCuanto } from "../src/componentes/Feed.tsx";
import { HojaInferior, alturaMasCercana, siguienteAltura } from "../src/componentes/Paneles.tsx";
import type { Altura } from "../src/componentes/Paneles.tsx";
import { detalleIncidente, resumir, resumirIncidente, resumirUcrania } from "../src/datos/derivar.ts";
import type { EventoResumen } from "../src/datos/tipos.ts";
import { accionDe } from "../src/estado/atajos.ts";
import {
  DIAS_RECIENTES,
  GRAVES,
  SIN_FILTROS,
  escribirBusqueda,
  escribirFiltros,
  filtrar,
  hayFiltros,
  leerFiltros,
  leerPeriodo,
} from "../src/estado/filtros.ts";
import {
  CLAVE_VISITA,
  incidentesDe,
  novedadesDesde,
  registrarVisita,
} from "../src/estado/novedades.ts";
import type { Almacen } from "../src/estado/novedades.ts";
import { textos } from "../src/i18n/index.ts";
import { ProveedorDeRuta } from "../src/navegacion.tsx";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { ataque, coleccion, incidente, publicacion } from "./ejemplos.ts";

vi.mock("../src/mapa/Mapa.tsx", () => ({
  default: ({ incidentes }: { incidentes: { id: string }[] }) => (
    <ul data-testid="mapa">
      {incidentes.map((i) => (
        <li key={i.id}>{i.id}</li>
      ))}
    </ul>
  ),
}));

const es = textos("es");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

// ---------------------------------------------------------------------------------------
describe("hoja inferior del teléfono", () => {
  it("al soltar el asa se queda en la altura más cercana de las tres", () => {
    expect(alturaMasCercana(0.1)).toBe("asomada");
    expect(alturaMasCercana(0.5)).toBe("media");
    expect(alturaMasCercana(0.8)).toBe("completa");
    expect(siguienteAltura("asomada")).toBe("media");
    expect(siguienteAltura("media")).toBe("completa");
    expect(siguienteAltura("completa")).toBe("asomada");
  });

  it("el asa es un botón: pulsada cambia de altura y con las flechas sube o baja", () => {
    let altura: Altura = "media";
    const onAltura = vi.fn((nueva: Altura) => {
      altura = nueva;
    });
    const { rerender } = render(
      <HojaInferior t={es} nombre="Ficha" altura={altura} onAltura={onAltura}>
        <p>contenido</p>
      </HojaInferior>,
    );
    const hoja = screen.getByRole("complementary", { name: "Ficha" });
    expect(hoja.dataset.altura).toBe("media");
    expect(document.activeElement).toBe(hoja);
    const asa = screen.getByRole("button", { name: /Hoja a media altura/ });
    fireEvent.click(asa);
    expect(onAltura).toHaveBeenLastCalledWith("completa");
    rerender(
      <HojaInferior t={es} nombre="Ficha" altura={altura} onAltura={onAltura}>
        <p>contenido</p>
      </HojaInferior>,
    );
    fireEvent.keyDown(screen.getByRole("button", { name: /pantalla completa/ }), { key: "ArrowDown" });
    expect(onAltura).toHaveBeenLastCalledWith("media");
  });
});

// ---------------------------------------------------------------------------------------
describe("filtros y periodo en la dirección", () => {
  it("se leen y se escriben igual", () => {
    const filtros = {
      estados: [...GRAVES].reverse(),
      reciente: "7d" as const,
      tipos: ["sobrevuelo" as const],
      paises: ["DE", "PL"],
    };
    const busqueda = escribirFiltros(filtros);
    // Confirmados y atribuidos se escriben como antes, para no romper enlaces compartidos.
    expect(busqueda).toBe("?solo=graves&ultimos=7d&tipo=sobrevuelo&pais=DE,PL");
    expect(leerFiltros(busqueda)).toEqual({ ...filtros, estados: ["confirmado", "atribuido"] });
    expect(escribirFiltros(SIN_FILTROS)).toBe("");
    expect(hayFiltros(SIN_FILTROS)).toBe(false);
  });

  it("cualquier combinación de estados va en la dirección en un orden fijo", () => {
    const busqueda = escribirFiltros({ ...SIN_FILTROS, estados: ["desmentido", "notificado"] });
    expect(busqueda).toBe("?estado=notificado,desmentido");
    expect(leerFiltros(busqueda).estados).toEqual(["notificado", "desmentido"]);
  });

  it("lo que no se entiende se ignora", () => {
    expect(leerFiltros("?solo=todo&estado=roto,confirmado&ultimos=1a&tipo=globo,incursion&pais=de,xxx,<b>")).toEqual({
      estados: ["confirmado"],
      reciente: null,
      tipos: ["incursion"],
      paises: ["DE"],
    });
  });

  it("el periodo va en la dirección junto a los filtros y las fechas imposibles se ignoran", () => {
    const periodo = { desde: diaDeInstante("2026-01-01"), hasta: diaDeInstante("2026-03-31") };
    const busqueda = escribirBusqueda({ ...SIN_FILTROS, tipos: ["incursion"] }, periodo);
    expect(busqueda).toBe("?tipo=incursion&desde=2026-01-01&hasta=2026-03-31");
    expect(leerPeriodo(busqueda)).toEqual(periodo);
    expect(leerPeriodo("?desde=2026-02-30&hasta=2026-03-31")).toBeNull();
    expect(leerPeriodo("?desde=2026-04-01&hasta=2026-03-31")).toBeNull();
    expect(leerPeriodo("?desde=ayer&hasta=hoy")).toBeNull();
    expect(leerPeriodo("")).toBeNull();
  });

  it("filtran por estado, antigüedad, tipo y país", () => {
    const hoy = diaDeInstante("2026-09-30");
    const lista = [
      resumirIncidente(incidente({ id: "EODI-2026-00001", tiempo: { inicio: { valor: "2026-09-30T08:00Z", precision: "hora" } } })),
      resumirIncidente(
        incidente({
          id: "EODI-2026-00002",
          tipo: "incursion",
          estado: { actual: "atribuido", historial: [{ estado: "atribuido", fecha: { valor: "2026-09-25T00:00Z", precision: "dia" } }] },
          tiempo: { inicio: { valor: "2026-09-25T00:00Z", precision: "dia" } },
          lugar: { radio_km: 5, pais: "PL" },
        }),
      ),
    ];
    const ids = (filtros: Parameters<typeof filtrar>[1]) => filtrar(lista, filtros, hoy).map((i) => i.id);
    expect(ids({ ...SIN_FILTROS, estados: [...GRAVES] })).toEqual(["EODI-2026-00002"]);
    expect(ids({ ...SIN_FILTROS, estados: ["notificado"] })).toEqual(["EODI-2026-00001"]);
    expect(ids({ ...SIN_FILTROS, reciente: "24h" })).toEqual(["EODI-2026-00001"]);
    expect(ids({ ...SIN_FILTROS, reciente: "7d" })).toHaveLength(2);
    expect(ids({ ...SIN_FILTROS, tipos: ["incursion"] })).toEqual(["EODI-2026-00002"]);
    expect(ids({ ...SIN_FILTROS, paises: ["DE"] })).toEqual(["EODI-2026-00001"]);
    expect(DIAS_RECIENTES["24h"]).toBe(1);
  });
});

// ---------------------------------------------------------------------------------------
describe("nuevo desde tu última visita", () => {
  function memoria(inicial: Record<string, string> = {}): Almacen & { datos: Record<string, string> } {
    const datos = { ...inicial };
    return {
      datos,
      getItem: (clave) => datos[clave] ?? null,
      setItem: (clave, valor) => {
        datos[clave] = valor;
      },
    };
  }
  const eventos: EventoResumen[] = [
    { id: "EODI-2026-00002", fecha: "2026-09-30T10:00Z", estado: "confirmado", nuevo: false },
    { id: "EODI-2026-00003", fecha: "2026-09-29T09:00Z", estado: "notificado", nuevo: true },
    { id: "EODI-2026-00002", fecha: "2026-09-28T09:00Z", estado: "notificado", nuevo: true },
  ];

  it("la primera visita no resalta nada y apunta la fecha", () => {
    const almacen = memoria();
    expect(registrarVisita(almacen, new Date("2026-09-30T12:00:00Z"))).toBeNull();
    expect(almacen.datos[CLAVE_VISITA]).toBe("2026-09-30T12:00:00.000Z");
  });

  it("la siguiente devuelve la anterior y resalta lo posterior", () => {
    const almacen = memoria({ [CLAVE_VISITA]: "2026-09-29T00:00:00.000Z" });
    const anterior = registrarVisita(almacen, new Date("2026-09-30T12:00:00Z"));
    expect(anterior).toBe("2026-09-29T00:00:00.000Z");
    const nuevos = novedadesDesde(eventos, anterior);
    expect(nuevos).toHaveLength(2);
    expect(incidentesDe(nuevos)).toEqual(["EODI-2026-00002", "EODI-2026-00003"]);
  });

  it("sin almacenamiento, o con uno roto, la web sigue sin resaltar nada", () => {
    expect(registrarVisita(null, new Date())).toBeNull();
    const roto: Almacen = {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    };
    expect(registrarVisita(roto, new Date())).toBeNull();
    expect(registrarVisita(memoria({ [CLAVE_VISITA]: "<script>" }), new Date())).toBeNull();
    expect(novedadesDesde(eventos, null)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------
describe("atajos de teclado", () => {
  const pulsar = (key: string, extra: Partial<{ ctrlKey: boolean; target: EventTarget | null }> = {}) =>
    accionDe({ key, ctrlKey: false, metaKey: false, altKey: false, target: null, ...extra });

  it("cada tecla tiene su acción", () => {
    expect(pulsar("?")).toBe("ayuda");
    expect(pulsar("Escape")).toBe("cerrar");
    expect(pulsar("2")).toBe("capaUcrania");
    expect(pulsar("C")).toBe("filtroGraves");
    expect(pulsar("t")).toBe("lineaTiempo");
    expect(pulsar("x")).toBeNull();
  });

  it("no se roban teclas al navegador ni a los campos", () => {
    expect(pulsar("c", { ctrlKey: true })).toBeNull();
    const campo = document.createElement("input");
    expect(pulsar("c", { target: campo })).toBeNull();
    expect(pulsar("Escape", { target: campo })).toBe("cerrar");
  });
});

// ---------------------------------------------------------------------------------------
describe("panel en directo", () => {
  const ahora = new Date("2026-09-30T12:00:00Z");
  const munich = resumirIncidente(incidente());

  it("dice la hora relativa", () => {
    expect(haceCuanto(es, "2026-09-30T11:48Z", ahora)).toBe("hace 12 min");
    expect(haceCuanto(es, "2026-09-30T09:00Z", ahora)).toBe("hace 3 h");
    expect(haceCuanto(es, "2026-09-28T12:00Z", ahora)).toBe("hace 2 días");
    expect(haceCuanto(es, "2025-01-10T12:00Z", ahora)).toBe("el 10/01/2025");
  });

  it("lista los eventos y al pulsar uno abre su incidente", async () => {
    const onAbrir = vi.fn();
    render(
      <Feed
        t={es}
        idioma="es"
        pestana="directo"
        onPestana={() => undefined}
        eventos={[
          { id: munich.id, fecha: "2026-09-30T11:48Z", estado: "confirmado", nuevo: false },
          { id: munich.id, fecha: "2026-09-30T09:00Z", estado: "notificado", nuevo: true },
        ]}
        porId={new Map([[munich.id, munich]])}
        novedades={new Set([munich.id])}
        ahora={ahora}
        onAbrir={onAbrir}
        onCerrar={() => undefined}
        lista={null}
      />,
    );
    const entradas = screen.getAllByRole("listitem");
    expect(entradas[0]?.textContent).toContain("Pasa a confirmado");
    expect(entradas[0]?.textContent).toContain("hace 12 min");
    expect(entradas[1]?.textContent).toContain("Nuevo incidente");
    await userEvent.click(within(entradas[0]!).getByRole("button"));
    expect(onAbrir).toHaveBeenCalledWith(munich.id);
  });
});

// ---------------------------------------------------------------------------------------
describe("aplicación con el diseño nuevo", () => {
  const { lugar: _lugar, ...resto } = incidente({ id: "EODI-2026-00300" }).properties;
  const incidentes = coleccion([
    incidente(),
    incidente({
      id: "EODI-2026-00007",
      estado: {
        actual: "confirmado",
        historial: [{ estado: "confirmado", fecha: { valor: "2026-09-13T08:00Z", precision: "hora" } }],
      },
      tiempo: { inicio: { valor: "2026-09-13T00:00Z", precision: "dia" } },
      lugar: { radio_km: 5, pais: "LT" },
      titulo: { es: "Cierre del aeropuerto de Vilna", en: "Vilnius airport closed" },
    }),
  ]);
  const imprecisos = {
    incidentes: [
      {
        ...resto,
        titulo: { es: "Drones sobre una base sin situar", en: "Drones over an unlocated base" },
        lugar: { pais: "PL" as const, nivel: "region" as const, region: "Lublin" },
      },
    ],
  };
  const resumen = resumir(incidentes, publicacion([ataque()]), imprecisos);

  function servir() {
    vi.stubGlobal(
      "fetch",
      vi.fn((ruta: string) => {
        const ficheros: Record<string, unknown> = {
          "/datos/resumen.json": resumen,
          "/datos/ucrania-resumen.json": resumirUcrania(publicacion([ataque()])),
          "/datos/incidentes/EODI-2026-00007.json": detalleIncidente(incidentes.features[1]!),
        };
        const cuerpo = ficheros[ruta];
        return Promise.resolve(
          cuerpo === undefined
            ? new Response("no", { status: 404 })
            : new Response(JSON.stringify(cuerpo), { status: 200 }),
        );
      }),
    );
  }

  beforeEach(() => {
    vi.stubGlobal("matchMedia", (consulta: string) => ({
      matches: consulta.includes("reduced-motion"),
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
  });

  function abrir(ruta: string) {
    window.history.replaceState(null, "", ruta);
    return render(
      <ProveedorDeRuta inicial={window.location.pathname}>
        <App />
      </ProveedorDeRuta>,
    );
  }

  it("los filtros de la dirección filtran el mapa y los cambios quedan en la dirección", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/?solo=graves");
    const mapa = await screen.findByTestId("mapa");
    await waitFor(() => expect(within(mapa).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["EODI-2026-00007"]));
    const barra = screen.getByRole("group", { name: es.filtros.titulo });
    expect(within(barra).getByRole("button", { name: es.estado.confirmado }).getAttribute("aria-pressed")).toBe("true");
    await usuario.click(within(barra).getByRole("button", { name: es.filtros.quitar }));
    await waitFor(() => expect(within(mapa).getAllByRole("listitem")).toHaveLength(3));
    expect(window.location.search).toBe("");
    expect(within(barra).queryByRole("button", { name: es.filtros.quitar })).toBeNull();
    await usuario.click(within(barra).getByRole("button", { name: es.filtros.ultimos7d }));
    expect(window.location.search).toBe("?ultimos=7d");
    await usuario.click(within(barra).getByRole("button", { name: es.estado.notificado }));
    expect(window.location.search).toBe("?estado=notificado&ultimos=7d");
  });

  it("los filtros van en su barra, agrupados por categoría y cada opción con su texto", async () => {
    servir();
    abrir("/");
    await screen.findByTestId("mapa");
    const barra = screen.getByRole("group", { name: es.filtros.titulo });
    const grupos = within(barra).getAllByRole("group").map((g) => g.querySelector("legend")?.textContent);
    expect(grupos).toEqual([es.filtros.estado, es.filtros.tipo, es.filtros.recientes]);
    expect(within(barra).getByRole("combobox", { name: es.filtros.pais })).toBeTruthy();
    for (const opcion of within(barra).getAllByRole("button")) {
      expect(opcion.textContent?.trim().length).toBeGreaterThan(2);
      expect(opcion.getAttribute("aria-label")).toBeNull();
    }
    for (const nombre of [...Object.values(es.tipo), ...Object.values(es.estado)]) {
      expect(within(barra).getByRole("button", { name: nombre })).toBeTruthy();
    }
  });

  it("la cabecera es una sola barra: nombre, cifras, estado y controles, sin flechas", async () => {
    servir();
    abrir("/");
    await screen.findByTestId("mapa");
    const cabecera = screen.getByRole("banner", { name: es.cabecera.etiqueta });
    expect(within(cabecera).getByRole("heading", { level: 1 }).textContent).toBe(
      "European Observatory of Drone Incidents",
    );
    expect(cabecera.querySelector('img[src="/marca/eodi-simplificado.svg"]')).not.toBeNull();
    expect(within(cabecera).getByLabelText(es.marcador.etiqueta)).toBeTruthy();
    expect(within(cabecera).getByRole("button", { name: /^Actualizado/ })).toBeTruthy();
    expect(within(cabecera).getByRole("group", { name: es.controles.capas })).toBeTruthy();
    for (const nombre of [es.guerra.reproducir, es.controles.feed, es.controles.ayuda, es.firma.metodologia]) {
      expect(within(cabecera).getByRole("button", { name: nombre })).toBeTruthy();
    }
    expect(within(cabecera).getByRole("navigation", { name: es.controles.idioma })).toBeTruthy();
    expect(cabecera.textContent).not.toMatch(/[▾▴»]/);
    // La monoespaciada va solo en cifras y horas, nunca con palabras.
    for (const cifra of cabecera.querySelectorAll(".mono, .cifra")) {
      expect(cifra.textContent).toMatch(/^[\d.,/ ·:]+( UTC)?$/);
    }
  });

  it("el periodo queda en la dirección, atrás lo deshace y «Ver todo» o Escape lo quitan", async () => {
    // jsdom no mide: la línea de tiempo necesita un ancho para dibujar el histograma.
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1000);
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    expect(screen.queryByRole("button", { name: es.tiempo.verTodo })).toBeNull();
    fireEvent.keyDown(window, { key: "t" });
    const fin = await screen.findByRole("slider", { name: es.tiempo.hasta });
    fireEvent.keyDown(fin, { key: "Home" });
    await waitFor(() => expect(window.location.search).toMatch(/^\?desde=\d{4}-\d{2}-\d{2}&hasta=/));
    const elegido = window.location.search;
    // El botón atrás del navegador deshace el último cambio de periodo.
    window.history.back();
    await waitFor(() => expect(window.location.search).toBe(""));
    window.history.forward();
    await waitFor(() => expect(window.location.search).toBe(elegido));
    await usuario.click(screen.getAllByRole("button", { name: es.tiempo.verTodo })[0]!);
    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.queryByRole("button", { name: es.tiempo.verTodo })).toBeNull();
    fireEvent.keyDown(screen.getByRole("slider", { name: es.tiempo.hasta }), { key: "Home" });
    await waitFor(() => expect(window.location.search).not.toBe(""));
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("la reproducción se pausa, se reanuda y al detenerla vuelve al periodo de antes", async () => {
    // jsdom no mide: la línea de tiempo necesita un ancho para dibujar el histograma.
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1000);
    servir();
    const usuario = userEvent.setup();
    abrir("/?desde=2026-09-13&hasta=2026-09-13");
    await screen.findByTestId("mapa");
    fireEvent.keyDown(window, { key: "t" });
    const fin = await screen.findByRole("slider", { name: es.tiempo.hasta });
    expect(fin.getAttribute("aria-valuetext")).toBe("13/09/2026");
    await usuario.click(screen.getByRole("button", { name: es.tiempo.reproducir }));
    await usuario.click(screen.getByRole("button", { name: es.tiempo.pausar }));
    expect(screen.getByRole("button", { name: es.tiempo.reanudar })).toBeTruthy();
    await usuario.click(screen.getByRole("button", { name: es.tiempo.detener }));
    expect(screen.queryByRole("button", { name: es.tiempo.detener })).toBeNull();
    expect(window.location.search).toBe("?desde=2026-09-13&hasta=2026-09-13");
    expect(screen.getByRole("slider", { name: es.tiempo.hasta }).getAttribute("aria-valuetext")).toBe(
      "13/09/2026",
    );
  });

  it("«noche a noche» se pausa, se reanuda y se detiene, también con «Ver todo»", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    const cabecera = screen.getByRole("banner", { name: es.cabecera.etiqueta });
    await usuario.click(within(cabecera).getByRole("button", { name: es.guerra.reproducir }));
    const noche = await screen.findByRole("status");
    expect(noche.textContent).toMatch(/^Noche del /);
    await usuario.click(within(noche).getByRole("button", { name: es.guerra.pausar }));
    expect(within(noche).getByRole("button", { name: es.guerra.reanudar })).toBeTruthy();
    await usuario.click(within(noche).getByRole("button", { name: es.guerra.detener }));
    await waitFor(() => expect(screen.queryByText(/^Noche del /)).toBeNull());
    await usuario.click(within(cabecera).getByRole("button", { name: es.guerra.reproducir }));
    await screen.findByText(/^Noche del /);
    await usuario.click(screen.getAllByRole("button", { name: es.tiempo.verTodo })[0]!);
    await waitFor(() => expect(screen.queryByText(/^Noche del /)).toBeNull());
  });

  it("en el teléfono: barra compacta, menú con todo y una sola hoja a la vez", async () => {
    vi.stubGlobal("matchMedia", (consulta: string) => ({
      matches: consulta.includes("reduced-motion") || consulta.includes("max-width: 767.98px"),
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    const barra = await screen.findByRole("banner", { name: es.cabecera.etiqueta });
    // Solo el logo, «EODI», el estado y el menú (y «Periodo», que el CSS solo muestra con el
    // teléfono en horizontal): nada de capas ni filtros a la vista.
    await waitFor(() => expect(within(barra).getAllByRole("button").map((b) => b.textContent)).toEqual([
      expect.stringMatching(/hace/),
      es.tiempo.periodoBoton,
      es.cabecera.menu,
    ]));
    expect(screen.queryByRole("group", { name: es.filtros.titulo })).toBeNull();
    expect(screen.queryByRole("button", { name: es.controles.acercar })).toBeNull();
    await usuario.click(within(barra).getByRole("button", { name: es.cabecera.menu }));
    const menu = document.querySelector<HTMLElement>('dialog[aria-labelledby="menu-titulo"]');
    if (menu === null) throw new Error("sin menú");
    const secciones = within(menu).getAllByRole("heading", { level: 3, hidden: true }).map((h) => h.textContent);
    expect(secciones).toEqual([
      es.marcador.etiqueta,
      es.controles.capas,
      es.filtros.titulo,
      es.controles.paneles,
      es.controles.idioma,
    ]);
    await usuario.click(within(menu).getByRole("button", { name: es.controles.feed, hidden: true }));
    expect(await screen.findByRole("complementary", { name: es.feed.titulo })).toBeTruthy();
    fireEvent.keyDown(window, { key: "t" });
    expect(await screen.findByRole("complementary", { name: es.tiempo.titulo })).toBeTruthy();
    expect(screen.queryByRole("complementary", { name: es.feed.titulo })).toBeNull();
    expect(screen.getByRole("button", { name: es.tiempo.reproducir })).toBeTruthy();
  });

  it("los atajos abren la ayuda y aplican filtros", async () => {
    servir();
    abrir("/");
    await screen.findByTestId("mapa");
    fireEvent.keyDown(window, { key: "c" });
    await waitFor(() => expect(window.location.search).toBe("?solo=graves"));
    fireEvent.keyDown(window, { key: "0" });
    await waitFor(() => expect(window.location.search).toBe(""));
    fireEvent.keyDown(window, { key: "e" });
    expect(await screen.findByRole("complementary", { name: es.feed.titulo })).toBeTruthy();
  });

  it("los incidentes sin punto salen en el feed y en la lista como ubicación imprecisa", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    await usuario.click(screen.getByRole("button", { name: es.controles.feed }));
    const feed = await screen.findByRole("complementary", { name: es.feed.titulo });
    expect(within(feed).getByText("Drones sobre una base sin situar")).toBeTruthy();
    await usuario.click(within(feed).getByRole("tab", { name: es.feed.lista }));
    expect(within(feed).getByText(es.imprecisa.etiqueta, { exact: false })).toBeTruthy();
  });

  it("avisa de lo nuevo desde la visita anterior, y sin almacenamiento no avisa", async () => {
    servir();
    window.localStorage.setItem("eodi.ultima-visita", "2026-09-01T00:00:00.000Z");
    abrir("/");
    expect(await screen.findByText(es.novedades.aviso(1))).toBeTruthy();
    cleanup();
    vi.stubGlobal("localStorage", undefined);
    servir();
    abrir("/");
    await screen.findByTestId("mapa");
    expect(screen.queryByText(/novedad(es)? desde tu última visita/)).toBeNull();
  });
});
