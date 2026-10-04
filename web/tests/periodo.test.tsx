// @vitest-environment jsdom
// «Últimas 24 horas» cuenta 24 horas hacia atrás desde este momento: un incidente con hora
// conocida entra si empezó dentro de ellas; uno que solo tiene día, si su día es hoy o ayer.
// Antes se contaba en días UTC enteros y a primera hora del día salía vacío. Los demás periodos
// siguen igual, y el mapa, la lista, las cifras, la presión y «En directo» cuentan lo mismo.
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App.tsx";
import { textoLeyendaPresion } from "../src/componentes/Leyendas.tsx";
import { cifrasDePais, periodoAnterior, presionPorPais } from "../src/datos/presion.ts";
import { resumir, resumirIncidente, resumirUcrania } from "../src/datos/derivar.ts";
import type { Precision } from "../src/datos/tipos.ts";
import {
  TODO,
  escribirSeleccion,
  leerSeleccion,
  periodoDeSeleccion,
  SIN_FILTROS,
  ultimas24Horas,
} from "../src/estado/filtros.ts";
import { textos } from "../src/i18n/index.ts";
import { ProveedorDeRuta } from "../src/navegacion.tsx";
import { MS_POR_DIA, MS_POR_HORA, diaDeInstante, incidenteEnPeriodo } from "../src/tiempo/dias.ts";
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
const MINUTO = 60_000;
const HORAS = ["00:30", "06:45", "23:30"] as const;
const DIA = "2026-10-04";

function iso(ms: number): string {
  return new Date(ms).toISOString().slice(0, 16) + "Z";
}

/**
 * Un incidente de prueba que empieza en `inicio` con su precisión, con un paso de historial
 * (el que lleva a «En directo») justo después.
 */
function caso(numero: number, inicio: string, precision: Precision) {
  return incidente(
    {
      id: `EODI-2026-${String(numero).padStart(5, "0")}`,
      tiempo: { inicio: { valor: inicio, precision } },
      estado: {
        actual: "notificado",
        historial: [{ estado: "notificado", fecha: { valor: inicio, precision: "minuto" }, fuente_id: "gdelt-0000000000000001" }],
      },
      control: { ultima_actualizacion: { valor: inicio, precision: "minuto" } },
    },
    [10 + numero / 10, 50],
  );
}

/** Los mismos casos a cualquier hora: qué entra y qué no. */
function casos(ahora: number) {
  const hoy = diaDeInstante(iso(ahora));
  const dia = (d: number) => `${new Date(d * MS_POR_DIA).toISOString().slice(0, 10)}T00:00Z`;
  return {
    dentro: [
      caso(1, iso(ahora - 30 * MINUTO), "minuto"),
      caso(2, iso(ahora - 23 * MS_POR_HORA - 59 * MINUTO), "minuto"),
      caso(3, iso(ahora - 5 * MS_POR_HORA), "hora"),
      caso(4, dia(hoy), "dia"),
      caso(5, dia(hoy - 1), "dia"),
      // Fecha aproximada (la de la noticia): cuenta solo su día, como el que solo tiene día.
      caso(6, `${dia(hoy - 1).slice(0, 10)}T00:05Z`, "aproximada"),
    ],
    fuera: [
      caso(7, iso(ahora - 24 * MS_POR_HORA - MINUTO), "minuto"),
      caso(8, dia(hoy - 2), "dia"),
      caso(9, iso(ahora - 3 * MS_POR_DIA), "hora"),
    ],
  };
}

const ids = (lista: readonly { properties: { id: string } }[]) => lista.map((f) => f.properties.id).sort();

describe("«Últimas 24 horas» desde este momento", () => {
  for (const hora of HORAS) {
    it(`a las ${hora} UTC entran las 24 horas anteriores y, sin hora, hoy y ayer`, () => {
      const ahora = Date.parse(`${DIA}T${hora}Z`);
      const { dentro, fuera } = casos(ahora);
      const periodo = periodoDeSeleccion({ clase: "reciente", reciente: "24h" }, diaDeInstante(DIA), ahora);
      expect(periodo).toEqual(ultimas24Horas(ahora));
      expect(periodo?.ventana).toEqual({ desde: ahora - 24 * MS_POR_HORA, hasta: ahora });
      expect([periodo?.desde, periodo?.hasta]).toEqual([diaDeInstante(DIA) - 1, diaDeInstante(DIA)]);
      const resumidos = [...dentro, ...fuera].map(resumirIncidente);
      const entran = resumidos.filter((i) => periodo !== null && incidenteEnPeriodo(i, periodo)).map((i) => i.id);
      expect(entran.sort()).toEqual(ids(dentro));
    });
  }

  it("a las 00:30 entra la tarde anterior, que antes se quedaba fuera", () => {
    const ahora = Date.parse(`${DIA}T00:30Z`);
    const tarde = resumirIncidente(caso(1, "2026-10-03T19:40Z", "minuto"));
    expect(incidenteEnPeriodo(tarde, ultimas24Horas(ahora))).toBe(true);
  });

  it("los periodos de días, «Entre fechas» y «Todo» siguen como estaban", () => {
    const hoy = diaDeInstante(DIA);
    const ahora = Date.parse(`${DIA}T06:45Z`);
    expect(periodoDeSeleccion({ clase: "reciente", reciente: "7d" }, hoy, ahora)).toEqual({ desde: hoy - 6, hasta: hoy });
    expect(periodoDeSeleccion({ clase: "reciente", reciente: "30d" }, hoy, ahora)).toEqual({ desde: hoy - 29, hasta: hoy });
    const noviembre = { desde: diaDeInstante("2025-11-01"), hasta: diaDeInstante("2025-11-30") };
    expect(periodoDeSeleccion({ clase: "entre", periodo: noviembre }, hoy, ahora)).toEqual(noviembre);
    expect(periodoDeSeleccion(TODO, hoy, ahora)).toBeNull();
    // Sin ventana, cuenta el día, tenga hora o no.
    const conHora = resumirIncidente(caso(1, "2025-11-30T23:59Z", "minuto"));
    expect(incidenteEnPeriodo(conHora, noviembre)).toBe(true);
  });

  it("los enlaces compartidos con periodo abren lo mismo", () => {
    for (const busqueda of ["?ultimos=24h", "?ultimos=7d", "?ultimos=30d", "?desde=2025-11-01&hasta=2025-11-30", ""]) {
      expect(escribirSeleccion(SIN_FILTROS, leerSeleccion(busqueda))).toBe(busqueda);
    }
  });

  it("la presión compara las 24 horas con las 24 anteriores", () => {
    const ahora = Date.parse(`${DIA}T06:45Z`);
    const periodo = ultimas24Horas(ahora);
    const anterior = periodoAnterior(periodo);
    expect(anterior.ventana).toEqual({ desde: ahora - 48 * MS_POR_HORA, hasta: ahora - 24 * MS_POR_HORA - 1 });
    const { dentro, fuera } = casos(ahora);
    const resumidos = [...dentro, ...fuera].map(resumirIncidente);
    const presion = presionPorPais(resumidos, periodo, 0);
    expect(presion.get("DE")?.incidentes).toBe(dentro.length);
    // En el periodo anterior: el de hace 24 horas y un minuto y el que solo tiene día de
    // anteayer; el de hace tres días ya no.
    expect(presion.get("DE")?.tendencia?.anterior).toBe(2);
    expect(cifrasDePais(resumidos, "DE", periodo).lista).toHaveLength(dentro.length);
  });
});

describe("la leyenda de la presión dice el periodo", () => {
  it("en palabras, en los dos idiomas", () => {
    const en = textos("en");
    expect(textoLeyendaPresion(es, { clase: "reciente", reciente: "30d" })).toBe("Incidentes en los últimos 30 días");
    expect(textoLeyendaPresion(es, TODO)).toBe("Incidentes desde el primer dato");
    const noviembre = { clase: "entre", periodo: { desde: diaDeInstante("2025-11-01"), hasta: diaDeInstante("2025-11-30") } } as const;
    expect(textoLeyendaPresion(es, noviembre)).toBe("Incidentes del 1 al 30 de noviembre de 2025");
    expect(textoLeyendaPresion(en, noviembre)).toBe("Incidents from 1 to 30 November 2025");
    const cruce = { clase: "entre", periodo: { desde: diaDeInstante("2025-12-28"), hasta: diaDeInstante("2026-01-03") } } as const;
    expect(textoLeyendaPresion(es, cruce)).toBe("Incidentes del 28 de diciembre de 2025 al 3 de enero de 2026");
    const unDia = { clase: "entre", periodo: { desde: diaDeInstante("2026-10-03"), hasta: diaDeInstante("2026-10-03") } } as const;
    expect(textoLeyendaPresion(es, unDia)).toBe("Incidentes del 3 de octubre de 2026");
    expect(textoLeyendaPresion(en, unDia)).toBe("Incidents on 3 October 2026");
  });
});

describe("en la aplicación, con la hora puesta", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", (consulta: string) => ({
      matches: consulta.includes("reduced-motion"),
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  function servir(ahora: number) {
    const { dentro, fuera } = casos(ahora);
    const ucrania = publicacion([ataque()]);
    // Los datos se publicaron diez minutos antes.
    const resumen = { ...resumir(coleccion([...dentro, ...fuera]), ucrania), actualizado: iso(ahora - 10 * MINUTO) };
    vi.stubGlobal(
      "fetch",
      vi.fn((ruta: string) => {
        const ficheros: Record<string, unknown> = {
          "/datos/resumen.json": resumen,
          "/datos/ucrania-resumen.json": resumirUcrania(ucrania),
        };
        const cuerpo = ficheros[ruta];
        return Promise.resolve(
          cuerpo === undefined ? new Response("no", { status: 404 }) : new Response(JSON.stringify(cuerpo), { status: 200 }),
        );
      }),
    );
    return { dentro, fuera };
  }

  for (const hora of HORAS) {
    it(`a las ${hora} UTC el mapa, las cifras y «En directo» dan lo mismo`, async () => {
      const ahora = Date.parse(`${DIA}T${hora}Z`);
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(ahora);
      const { dentro } = servir(ahora);
      const esperados = ids(dentro);
      window.history.replaceState(null, "", "/?ultimos=24h");
      render(
        <ProveedorDeRuta inicial="/">
          <App />
        </ProveedorDeRuta>,
      );
      const mapa = await screen.findByTestId("mapa");
      await waitFor(() =>
        expect(within(mapa).getAllByRole("listitem").map((li) => li.textContent).sort()).toEqual(esperados),
      );
      const cifras = screen.getAllByRole("definition")[0];
      expect(cifras?.textContent).toBe(String(esperados.length));
      // «En directo» muestra los mismos incidentes.
      await userEvent.setup().click(screen.getByRole("button", { name: es.controles.feed }));
      const feed = await screen.findByRole("complementary", { name: es.feed.titulo });
      const enDirecto = within(feed)
        .getAllByRole("button")
        .map((b) => b.getAttribute("data-id"))
        .filter((id): id is string => id !== null);
      expect([...new Set(enDirecto)].sort()).toEqual(esperados);
    });
  }

  it("al encender la presión con «Todo», el periodo pasa a los últimos 30 días", async () => {
    const ahora = Date.parse(`${DIA}T06:45Z`);
    servir(ahora);
    const usuario = userEvent.setup();
    render(
      <ProveedorDeRuta inicial="/">
        <App />
      </ProveedorDeRuta>,
    );
    await screen.findByTestId("mapa");
    await usuario.click(screen.getByRole("button", { name: es.controles.presion }));
    await waitFor(() => expect(window.location.search).toBe("?ultimos=30d"));
    expect(document.querySelector("[data-periodo-leyenda]")?.textContent).toBe("Incidentes en los últimos 30 días");
    // El botón de filtros lo muestra como periodo activo.
    expect(document.querySelector("[data-periodo-escrito]")?.textContent).toContain(es.filtros.periodos["30d"]);
  });

  it("con otro periodo elegido, encender la presión no lo cambia", async () => {
    servir(Date.parse(`${DIA}T06:45Z`));
    const usuario = userEvent.setup();
    window.history.replaceState(null, "", "/?ultimos=7d");
    render(
      <ProveedorDeRuta inicial="/">
        <App />
      </ProveedorDeRuta>,
    );
    await screen.findByTestId("mapa");
    await usuario.click(screen.getByRole("button", { name: es.controles.presion }));
    await waitFor(() => expect(document.querySelector("[data-periodo-leyenda]")?.textContent).toBe("Incidentes en los últimos 7 días"));
    expect(window.location.search).toBe("?ultimos=7d");
  });
});
