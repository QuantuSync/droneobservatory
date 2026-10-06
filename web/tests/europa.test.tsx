// @vitest-environment jsdom
// Europa en directo: detección de cierres, interferencia GPS, presión por país y panel
// «Europa ahora». Sin red: los ficheros del almacén se sirven con un fetch simulado.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App.tsx";
import { BarraEstado } from "../src/componentes/BarraEstado.tsx";
import { EuropaAhora } from "../src/componentes/EuropaAhora.tsx";
import type { CifrasAhora } from "../src/componentes/EuropaAhora.tsx";
import { FichaAviso } from "../src/componentes/FichaAviso.tsx";
import { FichaPais, textoTendencia } from "../src/componentes/FichaPais.tsx";
import { LeyendaGnss } from "../src/componentes/Leyendas.tsx";
import { cifrasAhora } from "../src/datos/ahora.ts";
import { resumir, resumirUcrania } from "../src/datos/derivar.ts";
import {
  URL_DIRECTO,
  avisosEnMapa,
  cierresEnCurso,
  ordenarAvisos,
  validarDirecto,
} from "../src/datos/directo.ts";
import {
  BASE_GNSS,
  agregar,
  celdasEnMapa,
  ficherosDelPeriodo,
  nivelDe,
  proporcion,
  validarFicheroGnss,
  validarIndiceGnss,
  zonasAltas,
} from "../src/datos/gnss.ts";
import {
  cifrasDePais,
  escalones,
  periodoAnterior,
  presionPorPais,
  sentidoDe,
} from "../src/datos/presion.ts";
import type { IncidenteResumen } from "../src/datos/tipos.ts";
import { validarEstadoSistema } from "../src/datos/validar.ts";
import { textos } from "../src/i18n/index.ts";
import { ProveedorDeRuta } from "../src/navegacion.tsx";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { ataque, coleccion, estadoSistema, incidente, publicacion } from "./ejemplos.ts";
import { aviso, celda, directo, ficheroGnss, indiceGnss } from "./ejemplos-europa.ts";

vi.mock("../src/mapa/Mapa.tsx", () => ({
  default: ({ avisos }: { avisos: { id: string }[] }) => (
    <ul data-testid="mapa">
      {avisos.map((a) => (
        <li key={a.id}>{a.id}</li>
      ))}
    </ul>
  ),
}));

const es = textos("es");
const en = textos("en");

afterEach(cleanup);

const dia = (texto: string) => diaDeInstante(texto);

describe("interferencia GPS", () => {
  it("proporción como gpsjam.org y niveles del 2 y el 10 %", () => {
    expect(proporcion(100, 1)).toBe(0);
    expect(proporcion(100, 3)).toBeCloseTo(0.02);
    expect(proporcion(0, 0)).toBe(0);
    expect(nivelDe(0.019)).toBe("sin");
    expect(nivelDe(0.02)).toBe("media");
    expect(nivelDe(0.1)).toBe("media");
    expect(nivelDe(0.101)).toBe("alta");
  });

  it("valida los ficheros y rechaza lo que no cumple", () => {
    expect(validarFicheroGnss(ficheroGnss("2025-09-22"))).not.toBeNull();
    expect(validarFicheroGnss(ficheroGnss("2025-09"))).not.toBeNull();
    expect(validarIndiceGnss(indiceGnss(["2025-09-22"], ["2025-09"]))).not.toBeNull();
    const bueno = ficheroGnss("2025-09-22");
    for (const malo of [
      { ...bueno, version: 2 },
      { ...bueno, periodo: "22/09/2025" },
      { ...bueno, celdas: [{ ...bueno.celdas[0], nivel: "extrema" }] },
      { ...bueno, celdas: [{ ...bueno.celdas[0], degradadas: 999 }] },
      { ...bueno, celdas: [{ ...bueno.celdas[0], contorno: [[0, 0]] }] },
      { ...bueno, celdas: [{ ...bueno.celdas[0], h3: "<script>" }] },
      { ...bueno, resumen: { ...bueno.resumen, proporcion: 3 } },
    ]) {
      expect(validarFicheroGnss(malo)).toBeNull();
    }
    expect(validarIndiceGnss({ version: 1, generado: "x", dias: ["ayer"], meses: [] })).toBeNull();
  });

  it("suma por celda los días del periodo y recalcula proporción y nivel", () => {
    const a = ficheroGnss("2025-09-22", [celda("841f053ffffffff", 20, 55, 100, 2)]);
    const b = ficheroGnss("2025-09-23", [
      celda("841f053ffffffff", 20, 55, 100, 30),
      celda("841fa47ffffffff", 11, 48, 50, 0),
    ]);
    const total = agregar([a, b]);
    expect(total.dias).toBe(2);
    expect(total.celdas).toHaveLength(2);
    const baltico = total.celdas.find((c) => c.h3 === "841f053ffffffff");
    expect(baltico?.aeronaves).toBe(200);
    expect(baltico?.degradadas).toBe(32);
    expect(baltico?.proporcion).toBeCloseTo(31 / 200);
    expect(baltico?.nivel).toBe("alta");
    expect(total.resumen.celdas_alta).toBe(1);
    expect(total.resumen.aeronaves).toBe(250);
  });

  it("elige los ficheros diarios hasta 7 días y los mensuales por encima", () => {
    const indice = indiceGnss(["2025-09-20", "2025-09-22", "2025-10-01"], ["2025-08", "2025-09", "2025-10"]);
    expect(ficherosDelPeriodo(indice, { desde: dia("2025-09-21"), hasta: dia("2025-09-22") })).toEqual([
      "dia/2025-09-22.json",
    ]);
    expect(ficherosDelPeriodo(indice, { desde: dia("2025-09-16"), hasta: dia("2025-09-22") })).toEqual([
      "dia/2025-09-20.json",
      "dia/2025-09-22.json",
    ]);
    expect(ficherosDelPeriodo(indice, { desde: dia("2025-09-15"), hasta: dia("2025-10-01") })).toEqual([
      "mes/2025-09.json",
      "mes/2025-10.json",
    ]);
  });

  it("las celdas van al mapa como polígonos cerrados con su nivel", () => {
    const coleccionMapa = celdasEnMapa(ficheroGnss("2025-09-22").celdas);
    const primera = coleccionMapa.features[0];
    expect(primera?.geometry.type).toBe("Polygon");
    const anillo = (primera?.geometry as GeoJSON.Polygon).coordinates[0] ?? [];
    expect(anillo[0]).toEqual(anillo[anillo.length - 1]);
    expect(primera?.properties).toMatchObject({ h3: "841f053ffffffff", nivel: "alta" });
  });

  it("la leyenda dice si carga, si no hay datos o cuántos días suma", () => {
    const { rerender } = render(<LeyendaGnss t={es} estado="cargando" />);
    expect(screen.getByRole("status").textContent).toBe(es.gnss.cargando);
    rerender(<LeyendaGnss t={es} estado="sin_datos" />);
    expect(screen.getByRole("status").textContent).toBe(es.gnss.sinDatos);
    expect(document.querySelector("[data-zonas-altas]")).toBeNull();
    rerender(<LeyendaGnss t={en} estado={{ dias: 3, zonas: 12 }} />);
    expect(screen.getByRole("status").textContent).toBe("3 days with data");
    expect(document.body.textContent).toContain("over 10%");
    expect(document.querySelector("[data-zonas-altas]")?.textContent).toBe("12 zones with high interference");
  });
});

function resumenDe(cambios: { pais: string; dia: number; estado?: IncidenteResumen["estado"] }[]) {
  return cambios.map(
    (c, i): IncidenteResumen => ({
      id: `EODI-2026-${String(i + 1).padStart(5, "0")}`,
      punto: null,
      imprecisa: null,
      tipo: "sobrevuelo",
      estado: c.estado ?? "notificado",
      presencia: null,
      titulo: { es: `Incidente ${i + 1}`, en: `Incident ${i + 1}` },
      dia: c.dia,
      inicio: null,
      pais: c.pais,
      objetivo: null,
      episodio: null,
      foco: false,
      atribucion: null,
      zona: null,
    }),
  );
}

describe("presión por país", () => {
  const d0 = dia("2026-09-01");
  const periodo = { desde: d0 + 7, hasta: d0 + 13 };

  it("el periodo anterior tiene la misma duración y acaba justo antes", () => {
    expect(periodoAnterior(periodo)).toEqual({ desde: d0, hasta: d0 + 6 });
  });

  it("estable si no cambia, o si cambia en uno y no llega al 10 %", () => {
    expect(sentidoDe(4, 4)).toBe("estable");
    expect(sentidoDe(11, 10)).toBe("estable");
    expect(sentidoDe(5, 4)).toBe("sube");
    expect(sentidoDe(2, 4)).toBe("baja");
    expect(sentidoDe(1, 0)).toBe("sube");
  });

  it("cuenta los incidentes del periodo y la tendencia por país", () => {
    const incidentes = resumenDe([
      { pais: "DK", dia: d0 + 8 },
      { pais: "DK", dia: d0 + 9 },
      { pais: "DK", dia: d0 + 10 },
      { pais: "DK", dia: d0 + 2 },
      { pais: "DE", dia: d0 + 1 },
      { pais: "DE", dia: d0 + 3 },
      { pais: "PL", dia: d0 + 12 },
      { pais: "PL", dia: d0 + 5 },
    ]);
    const presion = presionPorPais(incidentes, periodo, d0);
    expect(presion.get("DK")).toEqual({
      pais: "DK",
      incidentes: 3,
      tendencia: { sentido: "sube", diferencia: 2, anterior: 1 },
    });
    expect(presion.get("DE")?.tendencia).toEqual({ sentido: "baja", diferencia: -2, anterior: 2 });
    expect(presion.get("PL")?.tendencia?.sentido).toBe("estable");
    const opacidades = escalones(presion);
    expect(opacidades.has("DE")).toBe(false);
    expect(opacidades.get("DK")).toBeGreaterThan(opacidades.get("PL") ?? 1);
    expect(textoTendencia(es, presion.get("DK") ?? null, "es")).toBe("sube +2");
    expect(textoTendencia(es, presion.get("DE") ?? null, "es")).toBe("baja −2");
    expect(textoTendencia(en, presion.get("PL") ?? null, "en")).toBe("stable");
  });

  it("sin datos antes del periodo no hay tendencia", () => {
    const incidentes = resumenDe([{ pais: "DK", dia: d0 + 8 }]);
    const presion = presionPorPais(incidentes, periodo, d0 + 7);
    expect(presion.get("DK")?.tendencia).toBeNull();
    expect(textoTendencia(es, presion.get("DK") ?? null, "es")).toBe(es.presion.sinComparacion);
  });

  it("la ficha del país da sus cifras por tipo y estado y sus incidentes", () => {
    const incidentes = resumenDe([
      { pais: "DK", dia: d0 + 8, estado: "confirmado" },
      { pais: "DK", dia: d0 + 9 },
      { pais: "DE", dia: d0 + 9 },
    ]);
    const cifras = cifrasDePais(incidentes, "DK", periodo);
    expect(cifras.porEstado.confirmado).toBe(1);
    expect(cifras.porTipo.sobrevuelo).toBe(2);
    render(
      <ProveedorDeRuta inicial="/">
        <FichaPais
          t={es}
          idioma="es"
          iso="DK"
          presion={presionPorPais(incidentes, periodo, d0).get("DK") ?? null}
          cifras={cifras}
          periodo="08/09/2026 – 14/09/2026"
        />
      </ProveedorDeRuta>,
    );
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Dinamarca");
    expect(document.body.textContent).toContain("2 incidentes");
    expect(document.body.textContent).toContain("Confirmado: 1");
    const enlaces = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(enlaces).toEqual(["/EODI-2026-00002", "/EODI-2026-00001"]);
  });
});

describe("detección en directo", () => {
  it("valida directo.json y rechaza lo que no cumple", () => {
    expect(validarDirecto(directo())).not.toBeNull();
    for (const malo of [
      { ...directo(), version: 2 },
      { ...directo(), fuente: "otra" },
      directo([aviso({ estado: "cerrado" as never })]),
      directo([aviso({ detectado: "ayer" })]),
      directo([aviso({ oaci: "<b>" })]),
      directo([aviso({ confirmacion: { tipo: "incidente", incidente: "x", hora: "2025-09-22T19:00Z" } })]),
      directo([aviso({ evidencia: { ...aviso().evidencia, vistos: -1 } })]),
      // Lista cerrada: lo interno del servicio no sale.
      directo([{ ...aviso(), motivos_meteorologicos: [] } as never]),
      directo([{ ...aviso(), fuente: "adsb_lol" } as never]),
      directo([{ ...aviso(), factor: 0.9 } as never]),
      directo([{ ...aviso(), regla: "directo-1.0.0" } as never]),
      directo([aviso({ evidencia: { ...aviso().evidencia, factor: 1 } as never })]),
      { ...directo(), extra: 1 },
    ]) {
      expect(validarDirecto(malo)).toBeNull();
    }
  });

  it("los cierres en curso son los posibles y los confirmados, los más graves primero", () => {
    const avisos = [
      aviso({ id: "a", estado: "operacion_reanudada", reanudado: "2025-09-22T22:38Z" }),
      aviso({ id: "b", estado: "posible_cierre" }),
      aviso({ id: "c", estado: "cierre_confirmado" }),
    ];
    expect(cierresEnCurso(directo(avisos)).map((a) => a.id)).toEqual(["b", "c"]);
    expect(ordenarAvisos(avisos).map((a) => a.id)).toEqual(["c", "b", "a"]);
    expect(avisosEnMapa(avisos).features.map((f) => f.properties?.id)).toEqual(["a", "b", "c"]);
    expect(cierresEnCurso(null)).toEqual([]);
  });

  it("la ficha de un posible cierre da horas, evidencia y la fuente con su licencia", () => {
    render(
      <ProveedorDeRuta inicial="/">
        <FichaAviso t={es} idioma="es" aviso={aviso()} directo={directo()} />
      </ProveedorDeRuta>,
    );
    expect(screen.getByText("Posible cierre en curso").className).toContain("text-notificado");
    const texto = document.body.textContent ?? "";
    expect(texto).toContain("22/09/2025 · 18:41 UTC");
    expect(texto).toContain("0 movimientos vistos de 24,5 esperados");
    expect(texto).toContain("12 llegadas perdidas");
    expect(texto).toContain("5 aviones en espera");
    expect(texto).toContain("3 vuelos desviados");
    expect(texto).toContain("© adsb.lol contributors");
    expect(texto).toContain("ODbL 1.0");
    expect(screen.getByRole("link", { name: /adsb\.lol/ }).getAttribute("href")).toBe("https://adsb.lol/");
  });

  it("confirmado: enlace al incidente, primera noticia y ventaja; con el respaldo, adsb.fi", () => {
    const confirmado = aviso({
      estado: "cierre_confirmado",
      confirmacion: { tipo: "incidente", incidente: "EODI-2025-00154", hora: "2025-09-22T19:30Z" },
      primera_noticia: "2025-09-22T19:04Z",
      ventaja_min: 23,
    });
    render(
      <ProveedorDeRuta inicial="/">
        <FichaAviso t={en} idioma="en" aviso={confirmado} directo={directo([confirmado], { fuente: "adsb_fi" })} />
      </ProveedorDeRuta>,
    );
    expect(screen.getByText("Closure confirmed").className).toContain("text-confirmado");
    expect(screen.getByRole("link", { name: "EODI-2025-00154" }).getAttribute("href")).toBe(
      "/en/EODI-2025-00154",
    );
    expect(document.body.textContent).toContain("detected 23 min before the first news");
    const fuente = document.querySelector("[data-fuente-directo]");
    expect(fuente?.getAttribute("data-fuente-directo")).toBe("adsb_fi");
    expect(within(fuente as HTMLElement).getByRole("link").getAttribute("href")).toBe("https://adsb.fi/");
  });

  it("reanudada: lleva la hora de vuelta del tráfico", () => {
    render(
      <ProveedorDeRuta inicial="/">
        <FichaAviso
          t={es}
          idioma="es"
          aviso={aviso({ estado: "operacion_reanudada", reanudado: "2025-09-22T22:38Z" })}
          directo={directo()}
        />
      </ProveedorDeRuta>,
    );
    expect(screen.getByText("Operación reanudada")).toBeTruthy();
    expect(document.body.textContent).toContain("22/09/2025 · 22:38 UTC");
  });
});

describe("estado del servicio en estado.json", () => {
  it("acepta el bloque opcional del servicio y lo muestra con su último ciclo correcto", async () => {
    const sistema = estadoSistema({
      directo: { estado: "con_respaldo", ultimo_ciclo_correcto: "2026-10-03T08:20Z" },
    });
    expect(validarEstadoSistema(sistema).ok).toBe(true);
    expect(validarEstadoSistema(estadoSistema()).ok).toBe(true);
    expect(
      validarEstadoSistema({ ...sistema, directo: { estado: "roto", ultimo_ciclo_correcto: null } }).ok,
    ).toBe(false);
    const usuario = userEvent.setup();
    render(
      <BarraEstado t={es} actualizado="2026-10-03T07:17Z" sistema={sistema} ahora={new Date("2026-10-03T08:21Z")} />,
    );
    await usuario.click(screen.getByRole("button"));
    const fila = document.querySelector("[data-servicio-directo]");
    expect(fila?.getAttribute("data-servicio-directo")).toBe("con_respaldo");
    expect(fila?.textContent).toContain("Detección en directo");
    expect(fila?.textContent).toContain("03/10/2026 · 08:20 UTC");
  });
});

describe("panel «Europa ahora»", () => {
  const incidentes = coleccion([
    incidente({
      id: "EODI-2026-00007",
      tiempo: { inicio: { valor: "2026-09-27T00:00Z", precision: "dia" } },
      lugar: { radio_km: 5, pais: "LT" },
    }),
    incidente(),
  ]);
  const ucrania = publicacion([ataque()]);
  const resumen = resumir(incidentes, ucrania);

  it("calcula las cifras del momento con lo publicado", () => {
    const cifras = cifrasAhora({
      resumen,
      ucrania: resumirUcrania(ucrania),
      directo: directo([aviso(), aviso({ id: "x", estado: "operacion_reanudada" })]),
      gnssHoy: ficheroGnss("2026-10-02"),
      ahora: Date.parse("2026-09-30T20:00Z"),
    });
    expect(cifras.cierres).toBe(1);
    expect(cifras.incidentes).toBe(1);
    // El último parte: la noche del 29 al 30 de septiembre, publicada hace 15 horas.
    expect(cifras.drones).toEqual({
      lanzados: 188,
      jornada: { tipo: "noche", desde: dia("2026-09-29"), hasta: dia("2026-09-30") },
      antiguo: false,
    });
    expect(cifras.focos).toBe(0);
    const fichero = ficheroGnss("2026-10-02");
    // Las zonas altas del fichero diario, con la misma cuenta que la leyenda de la capa.
    expect(cifras.gnss).toEqual({ zonas: fichero.resumen.celdas_alta, dia: dia("2026-10-02") });
    expect(cifras.gnss?.zonas).toBe(zonasAltas(agregar([fichero])));
    expect(cifras.gnss?.zonas).toBeGreaterThan(0);
  });

  it("todas las líneas: un número a la izquierda (nunca palabras) y su texto a la derecha", () => {
    const cifras: CifrasAhora = {
      cierres: 0,
      incidentes: 9999,
      drones: { lanzados: 1234, jornada: { tipo: "noche", desde: dia("2026-10-02"), hasta: dia("2026-10-03") }, antiguo: false },
      focos: 7,
      gnss: { zonas: 0, dia: dia("2026-10-02") },
    };
    for (const idioma of ["es", "en"] as const) {
      const t = idioma === "es" ? es : en;
      render(<EuropaAhora t={t} idioma={idioma} cifras={cifras} onIr={() => undefined} />);
      const filas = Array.from(document.querySelectorAll("[data-cifra]"));
      expect(filas).toHaveLength(5);
      for (const fila of filas) {
        // La misma rejilla en todas: columna fija para el número, el resto para el texto.
        expect(fila.className).toContain("grid-cols-[3.25rem_minmax(0,1fr)]");
        const numero = fila.querySelector("[data-numero]");
        const texto = fila.querySelector("[data-texto]");
        expect(numero?.textContent).toMatch(/^[\d.,]+$/);
        expect(numero?.className).toContain("text-right");
        expect(texto?.className).toContain("min-w-0");
        expect(fila.children).toHaveLength(2);
      }
      const gnss = document.querySelector('[data-cifra="gnss"]');
      expect(gnss?.querySelector("[data-numero]")?.textContent).toBe("0");
      expect(gnss?.querySelector("[data-texto]")?.textContent).toBe(t.ahora.gnss);
      expect(gnss?.textContent).not.toMatch(/sin interferencia|no interference/);
      cleanup();
    }
  });

  it("los drones dicen la noche sin ambigüedad y, con más de 36 horas, que es el último parte", () => {
    const fila = (drones: CifrasAhora["drones"], t = es) => {
      const cifras: CifrasAhora = { cierres: 0, incidentes: 0, drones, focos: 0, gnss: null };
      const { container } = render(<EuropaAhora t={t} idioma="es" cifras={cifras} onIr={() => undefined} />);
      const texto = container.querySelector('[data-cifra="drones"] [data-texto]')?.textContent;
      cleanup();
      return texto;
    };
    const noche: NonNullable<CifrasAhora["drones"]> = {
      lanzados: 157,
      jornada: { tipo: "noche", desde: dia("2026-10-02"), hasta: dia("2026-10-03") },
      antiguo: false,
    };
    expect(fila(noche)).toBe("drones lanzados la última noche · noche del 2 al 3 de octubre");
    expect(fila(noche, en)).toBe("drones launched last night · night of 2 to 3 October");
    expect(fila({ ...noche, antiguo: true })).toBe("drones lanzados · último parte: noche del 2 al 3 de octubre");
    expect(fila({ ...noche, antiguo: true }, en)).toBe("drones launched · latest report: night of 2 to 3 October");
    // Una noche que cambia de mes, y un parte de día.
    expect(fila({ ...noche, jornada: { tipo: "noche", desde: dia("2026-09-30"), hasta: dia("2026-10-01") } })).toBe(
      "drones lanzados la última noche · noche del 30 de septiembre al 1 de octubre",
    );
    expect(fila({ ...noche, jornada: { tipo: "dia", desde: dia("2026-10-01"), hasta: dia("2026-10-01") } })).toBe(
      "drones lanzados en el último parte de día · día 1 de octubre",
    );
  });

  it("el parte pasa a «último parte» a las 36 horas de su fin", () => {
    const ucrania = resumirUcrania(publicacion([ataque()]));
    const fin = Date.parse("2026-09-30T05:00Z");
    const hora = 3_600_000;
    const drones = (ahora: number) =>
      cifrasAhora({ resumen: null, ucrania, directo: null, gnssHoy: null, ahora }).drones?.antiguo;
    expect(drones(fin + 36 * hora)).toBe(false);
    expect(drones(fin + 36 * hora + 60_000)).toBe(true);
  });

  it("sin ficheros, cada cifra sale como «—» y no rompe", () => {
    const vacias: CifrasAhora = { cierres: null, incidentes: null, drones: null, focos: null, gnss: null };
    expect(cifrasAhora({ resumen: null, ucrania: null, directo: null, gnssHoy: null, ahora: null })).toEqual(
      vacias,
    );
    render(<EuropaAhora t={es} idioma="es" cifras={vacias} onIr={() => undefined} />);
    const botones = screen.getAllByRole("button");
    expect(botones).toHaveLength(5);
    for (const boton of botones) expect(boton.textContent?.startsWith("—")).toBe(true);
    expect(botones[0]?.getAttribute("aria-label")).toContain(es.ahora.sinDato);
  });

  it("cada cifra es un botón que lleva a su sitio del mapa", async () => {
    const usuario = userEvent.setup();
    const ir = vi.fn();
    const cifras: CifrasAhora = {
      cierres: 2,
      incidentes: 14,
      drones: { lanzados: 120, jornada: { tipo: "noche", desde: dia("2026-10-02"), hasta: dia("2026-10-03") }, antiguo: false },
      focos: 3,
      gnss: { zonas: 4, dia: dia("2026-10-02") },
    };
    render(<EuropaAhora t={es} idioma="es" cifras={cifras} onIr={ir} />);
    await usuario.click(screen.getByRole("button", { name: /cierres de aeropuerto en curso/ }));
    await usuario.click(screen.getByRole("button", { name: /zonas con interferencia GPS hoy/ }));
    expect(ir.mock.calls).toEqual([["cierres"], ["gnss"]]);
    expect(document.querySelector('[data-cifra="cierres"] [data-numero]')?.className).toContain("text-notificado");
    expect(document.querySelector('[data-cifra="gnss"] [data-numero]')?.className).toContain("text-atribuido");
  });
});

describe("aplicación con los ficheros del almacén", () => {
  const incidentes = coleccion([incidente()]);
  const ucrania = publicacion([ataque()]);
  const resumen = resumir(incidentes, ucrania);
  const base = {
    "/datos/resumen.json": resumen,
    "/datos/ucrania-resumen.json": resumirUcrania(ucrania),
  };

  function servir(ficheros: Record<string, unknown>) {
    vi.stubGlobal(
      "fetch",
      vi.fn((ruta: string) => {
        const cuerpo = ficheros[ruta];
        return Promise.resolve(
          cuerpo === undefined
            ? new Response("no", { status: 403 })
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

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("el panel cuenta el cierre en curso y abre su ficha; el mapa recibe el aviso", async () => {
    servir({
      ...base,
      [URL_DIRECTO]: directo(),
      [`${BASE_GNSS}/indice.json`]: indiceGnss(["2025-09-22"]),
      [`${BASE_GNSS}/dia/2025-09-22.json`]: ficheroGnss("2025-09-22"),
    });
    const usuario = userEvent.setup();
    render(
      <ProveedorDeRuta inicial="/">
        <App />
      </ProveedorDeRuta>,
    );
    const mapa = await screen.findByTestId("mapa");
    await waitFor(() => expect(within(mapa).getAllByRole("listitem")).toHaveLength(1));
    // El botón avisa sin abrirse: un número con los cierres en curso.
    const boton = screen.getByRole("button", { name: new RegExp(`^${es.ahora.etiqueta}`) });
    await waitFor(() => expect(boton.querySelector("[data-indicador=cierres]")?.textContent).toBe("1"));
    expect(boton.getAttribute("aria-label")).toBe(`${es.ahora.etiqueta} · ${es.ahora.avisoCierres(1)}`);
    await usuario.click(boton);
    const panel = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    const cierres = within(panel).getByRole("button", { name: /cierres de aeropuerto en curso/ });
    expect(cierres.textContent?.startsWith("1")).toBe(true);
    const lineaGnss = within(panel).getByRole("button", { name: /interferencia GPS/ });
    const fichero = ficheroGnss("2025-09-22");
    await waitFor(() =>
      expect(lineaGnss.querySelector("[data-numero]")?.textContent).toBe(String(fichero.resumen.celdas_alta)),
    );
    await usuario.click(cierres);
    const ficha = await screen.findByRole("complementary", { name: /EKCH/ });
    expect(within(ficha).getByText("Posible cierre en curso")).toBeTruthy();
    // Pulsar una cifra cierra el desplegable.
    expect(screen.queryByRole("dialog", { name: es.ahora.etiqueta })).toBeNull();
  });

  it("el número GPS del panel es el que da la leyenda de la capa para ese día", async () => {
    servir({
      ...base,
      [`${BASE_GNSS}/indice.json`]: indiceGnss(["2026-09-28", "2026-09-29"]),
      [`${BASE_GNSS}/dia/2026-09-28.json`]: ficheroGnss("2026-09-28", [celda("841f053ffffffff", 20.6, 55.4, 100, 50)]),
      [`${BASE_GNSS}/dia/2026-09-29.json`]: ficheroGnss("2026-09-29"),
    });
    const usuario = userEvent.setup();
    render(
      <ProveedorDeRuta inicial="/">
        <App />
      </ProveedorDeRuta>,
    );
    await screen.findByTestId("mapa");
    await usuario.click(screen.getByRole("button", { name: new RegExp(`^${es.ahora.etiqueta}`) }));
    const panel = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    const linea = within(panel).getByRole("button", { name: /interferencia GPS/ });
    await waitFor(() => expect(linea.querySelector("[data-numero]")?.textContent).not.toBe("—"));
    const enPanel = Number(linea.querySelector("[data-numero]")?.textContent);
    expect(enPanel).toBeGreaterThan(0);
    // Pulsarla abre la capa en ese día: su leyenda cuenta lo mismo.
    await usuario.click(linea);
    await waitFor(() => expect(window.location.search).toBe("?desde=2026-09-29&hasta=2026-09-29"));
    const leyenda = await waitFor(() => {
      const zonas = document.querySelector("[data-zonas-altas]");
      if (zonas === null) throw new Error(`sin leyenda: ${document.querySelector("[data-leyenda=gnss]")?.textContent}`);
      return zonas;
    });
    expect(Number(leyenda.getAttribute("data-zonas-altas"))).toBe(enPanel);
    expect(leyenda.textContent).toBe(es.gnss.zonasAltas(enPanel));
  });

  it("sin directo.json ni interferencia, el panel muestra «—» y la web sigue", async () => {
    servir(base);
    render(
      <ProveedorDeRuta inicial="/">
        <App />
      </ProveedorDeRuta>,
    );
    await screen.findByTestId("mapa");
    const boton = screen.getByRole("button", { name: es.ahora.etiqueta });
    expect(boton.querySelector("[data-indicador]")).toBeNull();
    fireEvent.click(boton);
    const panel = await screen.findByRole("dialog", { name: es.ahora.etiqueta });
    const cierres = within(panel).getByRole("button", { name: /cierres de aeropuerto en curso/ });
    expect(cierres.textContent?.startsWith("—")).toBe(true);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
