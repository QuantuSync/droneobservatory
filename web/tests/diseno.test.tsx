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
import { textoDeSeleccion } from "../src/componentes/Filtros.tsx";
import {
  DIAS_RECIENTES,
  GRAVES,
  RECIENTES,
  SIN_FILTROS,
  TODO,
  escribirBusqueda,
  escribirFiltros,
  escribirSeleccion,
  filtrar,
  hayFiltros,
  leerFiltros,
  leerPeriodo,
  leerSeleccion,
  mismaSeleccion,
  periodoDeSeleccion,
} from "../src/estado/filtros.ts";
import type { Reciente, SeleccionPeriodo } from "../src/estado/filtros.ts";
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
  it("un clic en un botón de la cabecera de la hoja llega al botón (la X cierra)", () => {
    const onCerrar = vi.fn();
    render(
      <HojaInferior t={es} nombre="Ficha" altura="media" onAltura={() => undefined} onCerrar={onCerrar}>
        <div data-arrastre="">
          <button type="button" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </HojaInferior>,
    );
    const boton = screen.getByRole("button", { name: "Cerrar" });
    fireEvent.pointerDown(boton, { pointerId: 2, clientY: 300 });
    fireEvent.pointerUp(boton, { pointerId: 2, clientY: 300 });
    fireEvent.click(boton);
    expect(onCerrar).toHaveBeenCalledOnce();
  });

  it("un toque en el asa cambia de altura y nunca cierra la hoja", () => {
    const onAltura = vi.fn();
    const onCerrar = vi.fn();
    for (const altura of ["asomada", "media", "completa"] as const) {
      render(
        <HojaInferior t={es} nombre="Ficha" altura={altura} onAltura={onAltura} onCerrar={onCerrar}>
          <p>contenido</p>
        </HojaInferior>,
      );
      const asa = screen.getByRole("button", { name: /^Hoja / });
      fireEvent.pointerDown(asa, { pointerId: 1, clientY: 400 });
      fireEvent.pointerUp(asa, { pointerId: 1, clientY: 400 });
      fireEvent.click(asa);
      cleanup();
    }
    expect(onAltura.mock.calls.map(([a]) => a)).toEqual(["media", "completa", "media"]);
    expect(onCerrar).not.toHaveBeenCalled();
  });

  it("al soltar el asa se queda en la altura más cercana de las tres", () => {
    expect(alturaMasCercana(0.1)).toBe("asomada");
    expect(alturaMasCercana(0.5)).toBe("media");
    expect(alturaMasCercana(0.8)).toBe("completa");
    expect(siguienteAltura("asomada")).toBe("media");
    expect(siguienteAltura("media")).toBe("completa");
    // Un toque nunca cierra: desde completa vuelve a media.
    expect(siguienteAltura("completa")).toBe("media");
  });

  it("el asa es un botón: pulsada cambia de altura y con las flechas sube o baja", () => {
    let altura: Altura = "media";
    const onAltura = vi.fn((nueva: Altura) => {
      altura = nueva;
    });
    const onCerrar = vi.fn();
    const { rerender } = render(
      <HojaInferior t={es} nombre="Ficha" altura={altura} onAltura={onAltura} onCerrar={onCerrar}>
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
      <HojaInferior t={es} nombre="Ficha" altura={altura} onAltura={onAltura} onCerrar={onCerrar}>
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
      zona: null,
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
    expect(leerFiltros("?solo=todo&estado=roto,confirmado&ultimos=2a&tipo=globo,incursion&pais=de,xxx,<b>")).toEqual({
      estados: ["confirmado"],
      reciente: null,
      tipos: ["incursion"],
      paises: ["DE"],
      zona: null,
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

  it("filtran por estado, tipo y país; el periodo va aparte", () => {
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
    const ids = (filtros: Parameters<typeof filtrar>[1]) => filtrar(lista, filtros).map((i) => i.id);
    expect(ids({ ...SIN_FILTROS, estados: [...GRAVES] })).toEqual(["EODI-2026-00002"]);
    expect(ids({ ...SIN_FILTROS, estados: ["notificado"] })).toEqual(["EODI-2026-00001"]);
    expect(ids({ ...SIN_FILTROS, reciente: "24h" })).toHaveLength(2);
    expect(ids({ ...SIN_FILTROS, tipos: ["incursion"] })).toEqual(["EODI-2026-00002"]);
    expect(ids({ ...SIN_FILTROS, paises: ["DE"] })).toEqual(["EODI-2026-00001"]);
  });
});

// ---------------------------------------------------------------------------------------
describe("selector de periodo", () => {
  const hoy = diaDeInstante("2026-09-30");

  it("los periodos rápidos cuentan hasta el último día con datos, y por defecto se ve todo", () => {
    // «Últimas 24 horas» cuenta desde este momento (tests/periodo.test.tsx): aquí, el mediodía
    // del último día con datos; toca ese día y el anterior.
    const ahora = (hoy + 0.5) * 86_400_000;
    expect(leerSeleccion("")).toEqual(TODO);
    expect(periodoDeSeleccion(TODO, hoy, ahora)).toBeNull();
    const dias = (reciente: Reciente) => {
      const periodo = periodoDeSeleccion({ clase: "reciente", reciente }, hoy, ahora);
      return periodo === null ? null : [periodo.hasta - hoy, periodo.hasta - periodo.desde + 1];
    };
    expect(dias("24h")).toEqual([0, 2]);
    expect(dias("7d")).toEqual([0, 7]);
    expect(dias("30d")).toEqual([0, 30]);
    expect(dias("1a")).toEqual([0, 365]);
    expect(RECIENTES).toEqual(["24h", "7d", "30d", "1a"]);
    expect(DIAS_RECIENTES["30d"]).toBe(30);
  });

  it("cada periodo va en la dirección de una sola forma y se vuelve a leer igual", () => {
    const noviembre = { desde: diaDeInstante("2025-11-01"), hasta: diaDeInstante("2025-11-30") };
    const casos: [SeleccionPeriodo, string][] = [
      [TODO, ""],
      [{ clase: "reciente", reciente: "30d" }, "?ultimos=30d"],
      [{ clase: "reciente", reciente: "1a" }, "?ultimos=1a"],
      [{ clase: "entre", periodo: noviembre }, "?desde=2025-11-01&hasta=2025-11-30"],
    ];
    for (const [seleccion, busqueda] of casos) {
      expect(escribirSeleccion(SIN_FILTROS, seleccion)).toBe(busqueda);
      expect(mismaSeleccion(leerSeleccion(busqueda), seleccion)).toBe(true);
    }
    // Elegir un periodo rápido quita las fechas, y al revés.
    const conAmbos = "?ultimos=7d&desde=2025-11-01&hasta=2025-11-30";
    expect(leerSeleccion(conAmbos)).toEqual({ clase: "reciente", reciente: "7d" });
    expect(escribirSeleccion(leerFiltros(conAmbos), { clase: "entre", periodo: noviembre })).toBe(
      "?desde=2025-11-01&hasta=2025-11-30",
    );
    // Los enlaces de antes (?ultimos=24h, ?desde=…&hasta=…) siguen abriendo su periodo.
    expect(leerSeleccion("?ultimos=24h")).toEqual({ clase: "reciente", reciente: "24h" });
  });

  it("el periodo elegido se escribe como en el botón de filtros", () => {
    expect(textoDeSeleccion(es, TODO)).toBeNull();
    expect(textoDeSeleccion(es, { clase: "reciente", reciente: "30d" })).toBe("Últimos 30 días");
    expect(
      textoDeSeleccion(es, {
        clase: "entre",
        periodo: { desde: diaDeInstante("2025-11-01"), hasta: diaDeInstante("2025-11-30") },
      }),
    ).toBe("01/11/2025 – 30/11/2025");
    expect(textoDeSeleccion(textos("en"), { clase: "reciente", reciente: "1a" })).toBe("Last year");
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
    expect(pulsar("f")).toBe("filtros");
    expect(pulsar("a")).toBe("ahora");
    expect(pulsar("t")).toBeNull();
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

  async function abrirFiltros(usuario: ReturnType<typeof userEvent.setup>) {
    await usuario.click(screen.getByRole("button", { name: new RegExp(`^${es.filtros.abrir}`) }));
    const desplegable = await screen.findByRole("dialog", { name: es.filtros.titulo });
    return within(desplegable).getByRole("group", { name: es.filtros.titulo });
  }

  it("los filtros de la dirección filtran el mapa y los cambios quedan en la dirección", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/?solo=graves");
    const mapa = await screen.findByTestId("mapa");
    await waitFor(() => expect(within(mapa).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["EODI-2026-00007"]));
    const grupo = await abrirFiltros(usuario);
    expect(within(grupo).getByRole("button", { name: es.estado.confirmado }).getAttribute("aria-pressed")).toBe("true");
    await usuario.click(within(grupo).getByRole("button", { name: es.filtros.quitar }));
    await waitFor(() => expect(within(mapa).getAllByRole("listitem")).toHaveLength(3));
    expect(window.location.search).toBe("");
    expect(within(grupo).queryByRole("button", { name: es.filtros.quitar })).toBeNull();
    await usuario.selectOptions(within(grupo).getByRole("combobox", { name: es.filtros.recientes }), "7d");
    expect(window.location.search).toBe("?ultimos=7d");
    await usuario.click(within(grupo).getByRole("button", { name: es.estado.notificado }));
    expect(window.location.search).toBe("?estado=notificado&ultimos=7d");
  });

  it("al entrar no hay barras ni paneles: solo botones pequeños sobre el mapa", async () => {
    servir();
    abrir("/");
    await screen.findByTestId("mapa");
    expect(screen.queryByRole("group", { name: es.filtros.titulo })).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("slider")).toBeNull();
    expect(document.querySelector("[data-europa-ahora]")).toBeNull();
    const botones = document.querySelector<HTMLElement>("[data-botones-mapa]");
    if (botones === null) throw new Error("sin botones sobre el mapa");
    expect(within(botones).getAllByRole("button").map((b) => b.getAttribute("aria-expanded"))).toEqual([
      "false",
      "false",
      "false",
    ]);
  });

  it("los filtros se abren desde su botón, agrupados por categoría y cada opción con su texto", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    const grupo = await abrirFiltros(usuario);
    const grupos = within(grupo).getAllByRole("group").map((g) => g.querySelector("legend")?.textContent);
    expect(grupos).toEqual([es.filtros.estado, es.filtros.zona, es.filtros.tipo]);
    expect(within(grupo).getByRole("combobox", { name: es.filtros.recientes })).toBeTruthy();
    expect(within(grupo).getByRole("combobox", { name: es.filtros.pais })).toBeTruthy();
    for (const opcion of within(grupo).getAllByRole("button")) {
      expect(opcion.textContent?.trim().length).toBeGreaterThan(2);
      expect(opcion.getAttribute("aria-label")).toBeNull();
    }
    for (const nombre of [...Object.values(es.tipo), ...Object.values(es.estado)]) {
      expect(within(grupo).getByRole("button", { name: nombre })).toBeTruthy();
    }
    const periodos = within(grupo).getAllByRole("option").slice(0, 6).map((o) => o.textContent);
    expect(periodos).toEqual(Object.values(es.filtros.periodos));
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

  it("entre fechas: el periodo va a la dirección, el botón lo lleva escrito y su equis vuelve a todo", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    const mapa = await screen.findByTestId("mapa");
    await waitFor(() => expect(within(mapa).getAllByRole("listitem")).toHaveLength(3));
    const grupo = await abrirFiltros(usuario);
    await usuario.selectOptions(within(grupo).getByRole("combobox", { name: es.filtros.recientes }), "entre");
    const desde = within(grupo).getByLabelText(es.filtros.desde);
    const hasta = within(grupo).getByLabelText(es.filtros.hasta);
    fireEvent.change(desde, { target: { value: "2026-09-13" } });
    await waitFor(() => expect(window.location.search).toMatch(/^\?desde=2026-09-13&hasta=/));
    fireEvent.change(within(grupo).getByLabelText(es.filtros.hasta), { target: { value: "2026-09-13" } });
    await waitFor(() => expect(window.location.search).toBe("?desde=2026-09-13&hasta=2026-09-13"));
    expect(hasta).toBeTruthy();
    // Solo el incidente de ese día: el mapa, la lista y las cifras siguen el periodo.
    await waitFor(() =>
      expect(within(mapa).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["EODI-2026-00007"]),
    );
    const boton = screen.getByRole("button", { name: new RegExp(`^${es.filtros.abrir}`) });
    expect(boton.textContent).toContain("13/09/2026 – 13/09/2026");
    // El botón atrás deshace el cambio de periodo.
    window.history.back();
    await waitFor(() => expect(window.location.search).toMatch(/^\?desde=2026-09-13&hasta=(?!2026-09-13)/));
    window.history.forward();
    await waitFor(() => expect(window.location.search).toBe("?desde=2026-09-13&hasta=2026-09-13"));
    await usuario.click(screen.getByRole("button", { name: es.filtros.volverATodo("13/09/2026 – 13/09/2026") }));
    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.queryByRole("button", { name: /Quitar el periodo/ })).toBeNull();
  });

  it("un enlace con periodo lo abre, y uno a una ficha la abre aunque quede fuera", async () => {
    servir();
    abrir("/EODI-2026-00007?ultimos=24h");
    const mapa = await screen.findByTestId("mapa");
    await waitFor(() => expect(within(mapa).queryAllByRole("listitem")).toHaveLength(0));
    expect(await screen.findByRole("complementary", { name: /EODI-2026-00007/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: new RegExp(`^${es.filtros.abrir}`) }).textContent).toContain(
      es.filtros.periodos["24h"],
    );
  });

  it("el desplegable se abre y se cierra con su botón, la equis, Escape y pulsando fuera", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    const boton = screen.getByRole("button", { name: es.ahora.etiqueta });
    expect(boton.getAttribute("aria-haspopup")).toBe("dialog");
    // Abrir y cerrar con el mismo botón.
    await usuario.click(boton);
    const desplegable = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    expect(boton.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(desplegable);
    expect(within(desplegable).getAllByRole("button", { name: /^Ver en el mapa/ })).toHaveLength(5);
    await usuario.click(boton);
    expect(screen.queryByRole("dialog")).toBeNull();
    // La equis devuelve el foco al botón.
    await usuario.click(boton);
    await usuario.click(within(screen.getByRole("dialog")).getByRole("button", { name: es.ahora.cerrar }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(boton);
    // Escape.
    await usuario.click(boton);
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(boton);
    // Pulsar fuera.
    await usuario.click(boton);
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
    // Con el teclado: la tecla «a» lo abre y lo cierra.
    fireEvent.keyDown(window, { key: "a" });
    expect(await screen.findByRole("dialog", { name: es.ahora.etiqueta })).toBeTruthy();
    fireEvent.keyDown(window, { key: "a" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("pulsar una cifra de «Europa ahora» lleva a su sitio y cierra el desplegable", async () => {
    servir();
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    await usuario.click(screen.getByRole("button", { name: es.ahora.etiqueta }));
    const desplegable = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    await usuario.click(within(desplegable).getByRole("button", { name: new RegExp(es.ahora.incidentes) }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.location.search).toBe("?ultimos=7d");
  });

  it("«noche a noche» se pausa, se reanuda y se detiene, también con Escape", async () => {
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
    fireEvent.keyDown(window, { key: "Escape" });
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
    // Solo el logo, «EODI», el estado, «Avisos» (a la vista, fuera del menú) y el menú; sobre el
    // mapa, dos botones pequeños de 44 px.
    await waitFor(() =>
      expect(within(barra).getAllByRole("button").map((b) => b.textContent)).toEqual([
        expect.stringMatching(/hace/),
        "Avisos",
        es.cabecera.menu,
      ]),
    );
    const botones = document.querySelector<HTMLElement>("[data-botones-mapa]");
    if (botones === null) throw new Error("sin botones sobre el mapa");
    for (const boton of within(botones).getAllByRole("button")) {
      expect(boton.className).toContain("min-h-11");
    }
    expect(screen.queryByRole("group", { name: es.filtros.titulo })).toBeNull();
    expect(screen.queryByRole("button", { name: es.controles.acercar })).toBeNull();
    await usuario.click(within(barra).getByRole("button", { name: es.cabecera.menu }));
    const menu = document.querySelector<HTMLElement>('dialog[aria-labelledby="menu-titulo"]');
    if (menu === null) throw new Error("sin menú");
    const secciones = within(menu).getAllByRole("heading", { level: 3, hidden: true }).map((h) => h.textContent);
    expect(secciones).toEqual([
      es.marcador.etiqueta,
      es.controles.capas,
      es.controles.paneles,
      es.controles.idioma,
    ]);
    await usuario.click(within(menu).getByRole("button", { name: es.controles.feed, hidden: true }));
    expect(await screen.findByRole("complementary", { name: es.feed.titulo })).toBeTruthy();
    // Una sola hoja a la vez: «Europa ahora» sustituye al panel en directo.
    fireEvent.keyDown(window, { key: "a" });
    const hoja = await screen.findByRole("complementary", { name: es.ahora.etiqueta });
    expect(screen.queryByRole("complementary", { name: es.feed.titulo })).toBeNull();
    for (const cifra of within(hoja).getAllByRole("button", { name: /^Ver en el mapa/ })) {
      expect(cifra.className).toContain("min-h-11");
    }
    await usuario.click(within(hoja).getByRole("button", { name: es.ahora.cerrar }));
    await waitFor(() => expect(screen.queryByRole("complementary", { name: es.ahora.etiqueta })).toBeNull());
    // Los filtros, en otra hoja, desde su botón.
    await usuario.click(screen.getByRole("button", { name: new RegExp(`^${es.filtros.abrir}`) }));
    const filtros = await screen.findByRole("complementary", { name: es.filtros.titulo });
    expect(within(filtros).getByRole("combobox", { name: es.filtros.recientes })).toBeTruthy();
    // Un toque dentro no la cierra; uno fuera (en el mapa), sí.
    await usuario.click(within(filtros).getByRole("combobox", { name: es.filtros.recientes }));
    expect(screen.getByRole("complementary", { name: es.filtros.titulo })).toBeTruthy();
    await usuario.click(screen.getByTestId("mapa"));
    await waitFor(() => expect(screen.queryByRole("complementary", { name: es.filtros.titulo })).toBeNull());
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
    const usuario = userEvent.setup();
    window.localStorage.setItem("eodi.ultima-visita", "2026-09-01T00:00:00.000Z");
    abrir("/");
    // Sobre el mapa, solo el número en el botón «Europa ahora»: ningún aviso suelto.
    const boton = await screen.findByRole("button", { name: `${es.ahora.etiqueta} · ${es.ahora.avisoNovedades(1)}` });
    expect(boton.querySelector("[data-indicador=novedades]")?.textContent).toBe("1");
    expect(screen.queryByText(es.novedades.aviso(1))).toBeNull();
    // Dentro, la línea con «Verlas» y «Descartar».
    await usuario.click(boton);
    const panel = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    expect(within(panel).getByText(es.novedades.aviso(1))).toBeTruthy();
    await usuario.click(within(panel).getByRole("button", { name: es.novedades.recorrer }));
    // «Verlas» abre la primera, con su recorrido en la ficha, y el número se apaga.
    const ficha = await screen.findByRole("complementary", { name: /EODI-/ });
    expect(within(ficha).getByText(es.novedades.posicion(1, 1))).toBeTruthy();
    await waitFor(() => expect(boton.querySelector("[data-indicador]")).toBeNull());
    // «Descartar» quita la línea.
    await usuario.click(boton);
    const otraVez = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    await usuario.click(within(otraVez).getByRole("button", { name: es.novedades.descartar }));
    expect(within(otraVez).queryByText(es.novedades.aviso(1))).toBeNull();
    cleanup();
    vi.stubGlobal("localStorage", undefined);
    servir();
    abrir("/");
    await screen.findByTestId("mapa");
    expect(screen.getByRole("button", { name: es.ahora.etiqueta }).querySelector("[data-indicador]")).toBeNull();
  });
});
