// @vitest-environment jsdom
// Puntos con información de satélite: cuáles son y en qué orden, su marca en el mapa (por
// encima, sin agrupar, con su señal en los grupos), el botón «Con satélite» con su número y su
// lista, y la ficha con lo de satélite arriba.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FichaImpacto } from "../src/componentes/FichaImpacto.tsx";
import {
  BotonSatelite,
  cargarIndiceSatelite,
  loQueTiene,
  olvidarIndiceSatelite,
} from "../src/componentes/GuerraSatelite.tsx";
import { puntosConSatelite, tiposDe } from "../src/datos/guerraSatelite.ts";
import type {
  CiudadAlumbrado,
  CiudadSinLuz,
  IndiceSatelite,
  TipoSatelite,
} from "../src/datos/guerraSatelite.ts";
import type { FilaImpacto } from "../src/datos/tipos.ts";
import { textos } from "../src/i18n/index.ts";
import {
  ATENUADAS_SIN_SATELITE,
  CAPAS_DE_PUNTOS_DE_GUERRA,
  CAPAS_DE_UCRANIA,
  CAPAS_PULSABLES,
  CAPA_IMPACTOS,
  CAPA_IMPACTOS_GRUPOS,
  CAPA_SATELITE,
  CAPA_SATELITE_ARO,
  CAPA_SATELITE_FOCO,
  estilo,
} from "../src/mapa/estilo.ts";
import { impactosConSateliteEnMapa } from "../src/mapa/geometria.ts";
import { PALETA } from "../src/paleta.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { focoTermico, impacto } from "./ejemplos.ts";

const es = textos("es");
const diaDe = (fecha: string) => diaDeInstante(`${fecha}T00:00Z`);

afterEach(() => {
  cleanup();
  olvidarIndiceSatelite();
});

const imagen = (fecha: string, lado: "antes" | "despues") => ({
  fecha: `${fecha}T08:57:28Z`,
  escena: "S2C_35TQM_20260920_0_L2A",
  objeto: `satelite/EODI-IG-2026-03486/${lado}-${fecha.replaceAll("-", "")}-S2C_35TQM_20260920_0_L2A.jpg`,
  nubes_recorte: 0,
});
const INDICE: IndiceSatelite = {
  generado: "2026-10-04T06:43Z",
  fuente: "Copernicus Sentinel-2 L2A",
  atribucion: "Contains modified Copernicus Sentinel data 2026",
  parejas: {
    "EODI-IG-2026-03486": {
      recorte: { lat: 46.51, lon: 30.7, lado_m: 4000 },
      antes: imagen("2026-09-20", "antes"),
      despues: imagen("2026-09-30", "despues"),
      lugar: "Euroterminal",
      cambio: { hectareas: 24.6, contorno: [[0.4, 0.4], [0.6, 0.4], [0.5, 0.6]] },
    },
  },
};

const fila = (id: string, dia: string, foco: 0 | 1, lon = 30, lat = 46): FilaImpacto => [
  id,
  diaDe(dia),
  0,
  lon,
  lat,
  foco,
  0,
  1,
  "UA-51",
];

const ODESA: CiudadSinLuz = {
  nombre: "Одеса",
  region: "UA-51",
  lon: 30.73,
  lat: 46.48,
  perdida: 69,
  lista: [
    {
      ataque: "EODI-UA-2025-0336",
      dia: diaDe("2025-12-13"),
      zona: "ciudad",
      region: "UA-51",
      ciudad: { nombre: "Одеса", lon: 30.73, lat: 46.48 },
      perdida: 69,
      noche: "2025-12-13",
      noches: ["2025-12-13", "2025-12-15"],
      referencia: { desde: "2025-11-22", hasta: "2025-12-12", noches: 3 },
    },
  ],
};
const SUMY: CiudadAlumbrado = {
  ciudad: { id: "c2", nombre: "Суми", punto: { lat: 50.91, lon: 34.8 } },
  region: "UA-59",
  desde: "2024-02-29",
  al_menos: true,
  actual: { brillo: 0.23, desde: "2026-08-24", hasta: "2026-10-02", noches: 10 },
  antiguo: { brillo: 0.24, desde: "2024-02-29", hasta: "2024-04-03", noches: 10 },
  noches: 172,
  origen: "medido",
};

describe("puntos con información de satélite", () => {
  const impactos = [
    fila("EODI-IG-2026-03486", "2026-09-25", 0, 30.7, 46.51), // con imagen
    fila("EODI-IG-2026-03500", "2026-09-28", 1), // con foco
    fila("EODI-IG-2026-03501", "2026-09-29", 0), // sin nada
  ];

  it("solo los que tienen algo, del más reciente al más antiguo, con lo que tiene cada uno", () => {
    const puntos = puntosConSatelite(impactos, INDICE, [ODESA], [SUMY], diaDe);
    expect(puntos.map((p) => [p.clave, p.imagen, p.foco, p.luz])).toEqual([
      ["c2", false, false, true],
      ["EODI-IG-2026-03500", false, true, false],
      ["EODI-IG-2026-03486", true, false, false],
      ["UA-51|Одеса", false, false, true],
    ]);
    expect(puntos.find((p) => p.clave === "EODI-IG-2026-03486")?.lugar).toBe("Euroterminal");
    const conLasDos = puntos.find((p) => p.clave === "EODI-IG-2026-03486");
    expect(conLasDos === undefined ? "" : loQueTiene(es, { ...conLasDos, foco: true })).toBe(
      "antes y después · foco de calor",
    );
    expect(puntos.map((p) => tiposDe(p))).toEqual([["oscura"], ["foco"], ["cortinilla"], ["apagon"]]);
    // Un foco de las últimas 24 horas que coincide con un impacto cuenta en cuanto se confirma.
    const recientes = puntosConSatelite(impactos, null, null, null, diaDe, new Set(["EODI-IG-2026-03501"]));
    expect(recientes.map((p) => p.clave)).toEqual(["EODI-IG-2026-03501", "EODI-IG-2026-03500"]);
    // Sin índice de imágenes, los de foco siguen.
    expect(puntosConSatelite(impactos, null, null, null, diaDe).map((p) => p.clave)).toEqual([
      "EODI-IG-2026-03500",
    ]);
  });

  it("en el mapa: sin agrupar, los de imagen encima, con su aro y su marca de foco", () => {
    const puntos = puntosConSatelite(
      [...impactos, fila("EODI-IG-2026-03502", "2026-09-30", 1)],
      INDICE,
      [ODESA],
      null,
      diaDe,
    );
    const mapa = impactosConSateliteEnMapa(puntos);
    expect(mapa.features.map((f) => f.properties)).toEqual([
      { id: "EODI-IG-2026-03502", imagen: 0, foco: 1 },
      { id: "EODI-IG-2026-03500", imagen: 0, foco: 1 },
      { id: "EODI-IG-2026-03486", imagen: 1, foco: 0 },
    ]);
    const { layers, sources } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const orden = layers.map((c) => c.id);
    for (const id of [CAPA_SATELITE_ARO, CAPA_SATELITE, CAPA_SATELITE_FOCO]) {
      expect(orden.indexOf(id)).toBeGreaterThan(orden.indexOf(CAPA_IMPACTOS));
      expect(CAPAS_DE_UCRANIA).toContain(id);
      const capa = layers.find((c) => c.id === id);
      const fuente = capa && "source" in capa ? sources[String(capa.source)] : undefined;
      expect(fuente).toBeDefined();
      expect(fuente).not.toHaveProperty("cluster");
    }
    expect(CAPAS_PULSABLES.indexOf(CAPA_SATELITE)).toBeLessThan(
      CAPAS_PULSABLES.indexOf(CAPA_IMPACTOS),
    );
    expect(CAPAS_DE_PUNTOS_DE_GUERRA).toContain(CAPA_SATELITE);
    // Más grande que un impacto, con el borde violeta claro.
    const satelite = layers.find((c) => c.id === CAPA_SATELITE)?.paint as Record<string, unknown>;
    const normal = layers.find((c) => c.id === CAPA_IMPACTOS)?.paint as Record<string, unknown>;
    expect(Number(satelite["circle-radius"])).toBeGreaterThan(Number(normal["circle-radius"]));
    expect(satelite["circle-stroke-color"]).toBe(PALETA.guerraClaro);
    // Un grupo con alguno lleva el borde claro.
    const grupos = layers.find((c) => c.id === CAPA_IMPACTOS_GRUPOS)?.paint as Record<
      string,
      unknown
    >;
    expect(JSON.stringify(grupos["circle-stroke-color"])).toContain("satelite");
    expect(JSON.stringify(sources)).toContain('"satelite":["max",["get","satelite"]]');
    // «Con satélite» atenúa los demás impactos, no los suyos.
    expect(ATENUADAS_SIN_SATELITE.map(([capa]) => capa)).toContain(CAPA_IMPACTOS);
    expect(ATENUADAS_SIN_SATELITE.map(([capa]) => capa)).not.toContain(CAPA_SATELITE);
  });
});

describe("botón «Con satélite», su leyenda, su filtro y su lista", () => {
  const puntos = puntosConSatelite(
    [fila("EODI-IG-2026-03486", "2026-09-25", 1, 30.7, 46.51), fila("EODI-IG-2026-03500", "2026-09-28", 1)],
    INDICE,
    [ODESA],
    [SUMY],
    diaDe,
  );

  function Prueba({ elegir }: { elegir: (clave: string) => void }) {
    const [activo, setActivo] = useState(false);
    const [abierta, setAbierta] = useState(false);
    const [filtro, setFiltro] = useState<TipoSatelite[]>([]);
    return (
      <BotonSatelite
        t={es}
        idioma="es"
        puntos={puntos}
        activo={activo}
        onActivo={setActivo}
        abierta={abierta}
        onAbierta={setAbierta}
        filtro={filtro}
        onFiltro={setFiltro}
        onElegir={(p) => elegir(p.clave)}
      />
    );
  }

  it("da la suma real, despliega la leyenda de los cuatro tipos y la lista; una fila lleva a su ficha", () => {
    const elegir = vi.fn();
    render(<Prueba elegir={elegir} />);
    fireEvent.click(screen.getByRole("button", { name: "Con satélite · 4" }));
    // La leyenda empieza plegada y se despliega.
    expect(screen.queryByText(es.satelite.leyendaTipos.apagon)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Leyenda/ }));
    for (const tipo of ["cortinilla", "foco", "apagon", "oscura"] as const) {
      expect(screen.getByText(es.satelite.leyendaTipos[tipo])).toBeTruthy();
    }
    const fila = screen.getByRole("button", { name: /Euroterminal/ });
    expect(fila.textContent).toContain("25/09/2026 · antes y después · foco de calor");
    fireEvent.click(fila);
    expect(elegir).toHaveBeenCalledWith("EODI-IG-2026-03486");
  });

  it("el filtro deja solo apagones y ciudades a oscuras", () => {
    render(<Prueba elegir={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Con satélite · 4" }));
    fireEvent.click(screen.getByRole("button", { name: /^apagón · 1/ }));
    fireEvent.click(screen.getByRole("button", { name: /^ciudad a oscuras · 1/ }));
    const filas = screen.getAllByRole("listitem").filter((li) => li.closest("[aria-label]")?.getAttribute("aria-label") === es.satelite.listaSatelite);
    expect(filas.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Суми"),
      expect.stringContaining("Одеса"),
    ]);
  });
});

describe("ficha de un impacto con información de satélite", () => {
  const descarga = (() =>
    Promise.resolve(new Response(JSON.stringify(INDICE)))) as typeof fetch;

  it("la cortinilla y el foco van lo primero, bajo el título", async () => {
    await cargarIndiceSatelite(descarga);
    const { container } = render(
      <FichaImpacto
        t={es}
        idioma="es"
        impacto={impacto({ id: "EODI-IG-2026-03486", foco_termico: focoTermico() })}
      />,
    );
    await waitFor(() => expect(container.querySelector("[data-cortinilla]")).not.toBeNull());
    const html = container.innerHTML;
    const cortinilla = html.indexOf("data-cortinilla");
    expect(cortinilla).toBeGreaterThan(html.indexOf("</h2>"));
    expect(cortinilla).toBeLessThan(html.indexOf(`>${es.impacto.lugar}<`));
    expect(html.indexOf("data-foco-arriba")).toBeLessThan(html.indexOf(`>${es.impacto.lugar}<`));
    // El contorno de la zona cambiada, que se oculta con un toque, y sus hectáreas.
    expect(container.querySelector("[data-contorno-cambio] polygon")?.getAttribute("points")).toBe(
      "0.4,0.4 0.6,0.4 0.5,0.6",
    );
    expect(container.querySelector("[data-zona-cambio]")?.textContent).toBe(
      "Zona con cambios: 24,6 hectáreas · antes 20/09/2026 · después 30/09/2026",
    );
    fireEvent.click(screen.getByRole("button", { name: es.satelite.imagen.ocultarContorno }));
    expect(container.querySelector("[data-contorno-cambio]")).toBeNull();
  });

  it("sin información de satélite, ni hueco ni aviso", async () => {
    await cargarIndiceSatelite(descarga);
    const { container } = render(
      <FichaImpacto t={es} idioma="es" impacto={impacto({ id: "EODI-IG-2026-09999" })} />,
    );
    await new Promise((r) => setTimeout(r, 0));
    expect(container.querySelector("[data-cortinilla]")).toBeNull();
    expect(container.querySelector("[data-foco-arriba]")).toBeNull();
    expect(container.textContent).not.toContain(es.satelite.imagen.rotulo);
    expect(container.querySelector("[data-zona-cambio]")).toBeNull();
  });
});
