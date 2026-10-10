// @vitest-environment jsdom
// Fichas de la guerra por satélite: imágenes de antes y después con su cortinilla y la
// atribución de Copernicus, ficha de un corredor, de una ciudad con pérdida de luz y de una
// ciudad con alumbrado reducido de forma permanente.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  FichaAlumbrado,
  FichaCorredor,
  ListaCorredores,
  letreroDeCorredor,
  nombreDeCorredor,
  FichaLuz,
  ImagenesSatelite,
  cargarIndiceSatelite,
  olvidarIndiceSatelite,
} from "../src/componentes/GuerraSatelite.tsx";
import type { CiudadAlumbrado, CiudadSinLuz, Corredor } from "../src/datos/guerraSatelite.ts";
import { textos } from "../src/i18n/index.ts";

const es = textos("es");
const en = textos("en");

afterEach(() => {
  cleanup();
  olvidarIndiceSatelite();
});

const INDICE = {
  generado: "2026-10-03T06:33Z",
  fuente: "Copernicus Sentinel-2 L2A",
  atribucion: "Contains modified Copernicus Sentinel data 2026",
  parejas: {
    "EODI-IG-2026-03486": {
      recorte: { lat: 46.51, lon: 30.7, lado_m: 4000 },
      antes: {
        fecha: "2026-09-20T08:57:28Z",
        escena: "S2C_35TQM_20260920_0_L2A",
        objeto: "satelite/EODI-IG-2026-03486/antes-20260920-S2C_35TQM_20260920_0_L2A.jpg",
        nubes_recorte: 0,
      },
      despues: {
        fecha: "2026-09-30T08:57:30Z",
        escena: "S2C_35TQM_20260930_1_L2A",
        objeto: "satelite/EODI-IG-2026-03486/despues-20260930-S2C_35TQM_20260930_1_L2A.jpg",
        nubes_recorte: 0.001,
      },
      cambio: { hectareas: 12.5, contorno: [[0.4, 0.4], [0.6, 0.4], [0.5, 0.6]] },
    },
  },
};

function descarga(cuerpo: unknown, estado = 200): typeof fetch {
  return (() =>
    Promise.resolve(new Response(JSON.stringify(cuerpo), { status: estado }))) as typeof fetch;
}

describe("imágenes de antes y después", () => {
  it("cortinilla con las dos fechas, el deslizador y la atribución", async () => {
    await cargarIndiceSatelite(descarga(INDICE));
    render(<ImagenesSatelite t={es} idioma="es" id="EODI-IG-2026-03486" />);
    await waitFor(() => expect(screen.getByText(INDICE.atribucion)).toBeTruthy());
    const imagenes = screen.getAllByRole("img");
    expect(imagenes).toHaveLength(2);
    expect(imagenes[0]?.getAttribute("src")).toMatch(/antes-20260920/);
    const deslizador = screen.getByRole("slider", { name: es.satelite.imagen.deslizador });
    fireEvent.change(deslizador, { target: { value: "20" } });
    expect(imagenes[1]?.getAttribute("style")).toContain("inset(0 0 0 20%)");
    expect(screen.getAllByText(/20\/09\/2026/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/30\/09\/2026/).length).toBeGreaterThan(0);
  });

  it("dice lo esencial al lector de pantalla: recorte, fechas, zona con cambios y cuánto se ve", async () => {
    await cargarIndiceSatelite(descarga(INDICE));
    render(<ImagenesSatelite t={es} idioma="es" id="EODI-IG-2026-03486" />);
    await waitFor(() => expect(screen.getByText(INDICE.atribucion)).toBeTruthy());
    const figura = screen.getByRole("figure");
    expect(figura.querySelector("figcaption")?.textContent).toBe(
      "Dos imágenes de satélite en color natural del mismo recorte de 4 km, una del 20/09/2026 y otra del " +
        "30/09/2026, superpuestas con un deslizador. La zona que cambió entre las dos, 12,5 hectáreas, va marcada con un contorno.",
    );
    const deslizador = screen.getByRole("slider", { name: es.satelite.imagen.deslizador });
    fireEvent.change(deslizador, { target: { value: "20" } });
    expect(deslizador.getAttribute("aria-valuetext")).toBe("20 % de la imagen de antes y 80 % de la de después a la vista");
  });

  it("sin pareja no pinta nada, y con el índice roto tampoco", async () => {
    await cargarIndiceSatelite(descarga(INDICE));
    const { container } = render(<ImagenesSatelite t={es} idioma="es" id="EODI-IG-2026-00001" />);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.innerHTML).toBe("");
    olvidarIndiceSatelite();
    expect(await cargarIndiceSatelite(descarga({ parejas: 1 }))).toBeNull();
    // Un fallo no se queda: la siguiente vez se vuelve a pedir.
    await new Promise((r) => setTimeout(r, 0));
    expect(await cargarIndiceSatelite(descarga(INDICE))).not.toBeNull();
  });
});

describe("corredores y luz nocturna", () => {
  const corredor: Corredor = {
    clave: "bryansk|UA-74",
    sentido: "RU_UA",
    origen: "Briansk",
    desde: [34.18, 53.21],
    region: "UA-74",
    hasta: [31.9, 51.5],
    drones: 412,
    ataques: 9,
  };

  it("la ficha del corredor da origen, destino y drones del periodo", () => {
    render(<FichaCorredor t={es} idioma="es" corredor={corredor} periodo="01/09/2026 – 30/09/2026" />);
    expect(screen.getByRole("heading").textContent).toContain("Briansk");
    expect(screen.getByText("412")).toBeTruthy();
    expect(screen.getByText(es.satelite.corredor.ataques(9))).toBeTruthy();
  });

  it("contra Rusia el origen es Ucrania, también en inglés", () => {
    const ruso: Corredor = { ...corredor, clave: "UA|RU-BRY", sentido: "UA_RU", origen: null, region: "RU-BRY" };
    render(<FichaCorredor t={en} idioma="en" corredor={ruso} periodo="x" />);
    expect(screen.getByRole("heading").textContent).toMatch(/^Ukraine →/);
    expect(screen.getByText(en.satelite.corredor.desdeUcraniaTexto)).toBeTruthy();
  });

  it("la ficha de una ciudad da la pérdida, la noche, la referencia y el origen medido", () => {
    const ciudad: CiudadSinLuz = {
      nombre: "Харків",
      region: "UA-63",
      lon: 36.23,
      lat: 49.99,
      perdida: 87,
      lista: [
        {
          ataque: "EODI-UA-2024-0100",
          dia: 19803,
          zona: "ciudad",
          region: "UA-63",
          ciudad: { nombre: "Харків", lon: 36.23, lat: 49.99 },
          perdida: 87,
          noche: "2024-03-22",
          noches: ["2024-03-22", "2024-03-23"],
          referencia: { desde: "2024-02-29", hasta: "2024-03-20", noches: 6 },
        },
      ],
    };
    render(<FichaLuz t={es} idioma="es" ciudad={ciudad} periodo="x" />);
    expect(screen.getByText(es.satelite.luzFicha.perdida("87"))).toBeTruthy();
    expect(screen.getByText(/22\/03\/2024/)).toBeTruthy();
    expect(screen.getByText(/Medido por satélite/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "EODI-UA-2024-0100" })).toBeTruthy();
  });
});

describe("ficha de una ciudad con alumbrado reducido", () => {
  const ciudad: CiudadAlumbrado = {
    ciudad: { id: "c2", nombre: "Суми", punto: { lat: 50.91, lon: 34.8 } },
    region: "UA-59",
    desde: "2024-03-02",
    al_menos: true,
    actual: { brillo: 0.23, desde: "2026-08-24", hasta: "2026-10-02", noches: 10 },
    antiguo: { brillo: 0.24, desde: "2024-02-29", hasta: "2024-04-03", noches: 10 },
    noches: 172,
    origen: "medido",
  };

  it("dice desde cuándo, el brillo actual y el de referencia y en cuántas noches se basa", () => {
    const { container } = render(<FichaAlumbrado t={es} idioma="es" ciudad={ciudad} />);
    expect(screen.getByText("Ciudad con alumbrado reducido de forma permanente")).toBeTruthy();
    expect(screen.getByText("al menos desde el 02/03/2024")).toBeTruthy();
    expect(screen.getByText("0,23 nW/(cm²·sr)")).toBeTruthy();
    expect(screen.getByText("0,24 nW/(cm²·sr)")).toBeTruthy();
    expect(screen.getByText("mediana de 10 noches válidas del 24/08/2026 al 02/10/2026")).toBeTruthy();
    expect(screen.getByText("172")).toBeTruthy();
    expect(container.textContent).not.toMatch(/aún pasaba/);
  });

  it("con la fecha en que dejó de pasar de la referencia, y en inglés", () => {
    render(
      <FichaAlumbrado
        t={en}
        idioma="en"
        ciudad={{ ...ciudad, al_menos: false, desde: "2024-05-02", ultimo_mes_por_encima: "2024-04" }}
      />,
    );
    expect(screen.getByText("City with permanently reduced street lighting")).toBeTruthy();
    expect(screen.getByText("02/05/2024")).toBeTruthy();
    expect(screen.getByText("In 04/2024 it was still above the minimum reference.")).toBeTruthy();
  });
});

describe("varios corredores en el punto pulsado", () => {
  const kursk: Corredor = {
    clave: "kursk|UA-63",
    sentido: "RU_UA",
    origen: "Kursk",
    desde: [36.19, 51.73],
    region: "UA-63",
    hasta: [36.23, 49.99],
    drones: 120,
    ataques: 4,
  };
  const oriol: Corredor = { ...kursk, clave: "oriol|UA-63", origen: "Oriol", desde: [36.08, 52.97] };

  it("el letrero y el nombre accesible: origen → región · drones", () => {
    expect(nombreDeCorredor(es, kursk)).toBe(`Kursk → ${es.regiones["UA-63"]}`);
    expect(letreroDeCorredor(es, "es", kursk)).toBe(`Kursk → ${es.regiones["UA-63"]} · 120 drones`);
  });

  it("se elige uno de la lista corta", () => {
    const elegir = vi.fn();
    render(<ListaCorredores t={es} corredores={[kursk, oriol]} onElegir={elegir} />);
    expect(screen.getByText(es.satelite.corredor.varios)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: `Oriol → ${es.regiones["UA-63"]}` }));
    expect(elegir).toHaveBeenCalledWith("oriol|UA-63");
  });
});
