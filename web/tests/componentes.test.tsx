// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App.tsx";
import { BarraEstado } from "../src/componentes/BarraEstado.tsx";
import { EnlaceExterno } from "../src/componentes/EnlaceExterno.tsx";
import { FichaAtaque } from "../src/componentes/FichaAtaque.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { FUENTES_VISIBLES, ordenarFuentes } from "../src/componentes/Fuentes.tsx";
import { LineaTiempo } from "../src/componentes/LineaTiempo.tsx";
import { Metodologia } from "../src/componentes/Metodologia.tsx";
import { ProveedorDeRuta } from "../src/navegacion.tsx";
import { detalleIncidente, resumir, resumirUcrania } from "../src/datos/derivar.ts";
import { textos } from "../src/i18n/index.ts";
import { DESCARGAS } from "../src/sitio.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { CARGAS_MALICIOSAS, ataque, coleccion, fuente, incidente, publicacion } from "./ejemplos.ts";

// El mapa necesita WebGL; aquí se sustituye por una lista de lo que recibiría.
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
const en = textos("en");

declare global {
  interface Window {
    __ataque?: boolean;
  }
}

afterEach(() => {
  cleanup();
  delete window.__ataque;
});

function sinHtmlInyectado(contenedor: HTMLElement) {
  expect(contenedor.querySelector("script")).toBeNull();
  expect(contenedor.querySelector("img")).toBeNull();
  expect(contenedor.querySelector("svg[onload]")).toBeNull();
  for (const elemento of contenedor.querySelectorAll("*")) {
    for (const atributo of elemento.getAttributeNames()) {
      expect(atributo.startsWith("on"), `${elemento.tagName} ${atributo}`).toBe(false);
    }
  }
  expect(window.__ataque).toBeUndefined();
}

describe("ficha de un incidente", () => {
  const detalle = detalleIncidente(incidente());

  it("muestra el tipo, el objetivo, el estado con texto y las filas de datos", () => {
    render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    expect(screen.getByRole("heading", { level: 2 })).toHaveProperty(
      "textContent",
      "Flughafen München",
    );
    expect(screen.getByText("Interrupción aeroportuaria")).toBeTruthy();
    expect(screen.getAllByText("Notificado").length).toBeGreaterThan(0);
    expect(screen.getByText("Dron no confirmado")).toBeTruthy();
    expect(screen.getByText("02/10/2025 · 22:18 UTC")).toBeTruthy();
    expect(screen.getByText("2–10")).toBeTruthy();
    expect(screen.getByText(`(${es.ficha.rangoDeFuentes})`)).toBeTruthy();
    expect(screen.getByText("cierre del espacio aéreo")).toBeTruthy();
    expect(screen.getByText("EDDM", { exact: false })).toBeTruthy();
  });

  it("da cada fuente con su enlace, su código del Almirantazgo y su frase en su idioma", () => {
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    const enlace = screen.getByRole("link", { name: /example\.org/ });
    expect(enlace.getAttribute("href")).toBe("https://example.org/noticia");
    expect(screen.getByText("C3")).toBeTruthy();
    expect(screen.getByText(es.ficha.codigo("C3"))).toBeTruthy();
    const frase = container.querySelector("blockquote");
    expect(frase?.getAttribute("lang")).toBe("de");
    expect(frase?.textContent).toBe("Flughafen wegen Drohnen gesperrt");
  });

  it("señala las declaraciones oficiales citadas y las pone delante", () => {
    const declaracion = fuente({
      id: "gdelt-0000000000000002-declaracion-1",
      medio: "Polizei (declaración oficial citada en example.org)",
      fiabilidad: "B",
      credibilidad: 1,
    });
    const conDeclaracion = detalleIncidente(incidente({ fuentes: [fuente(), declaracion] }));
    render(<FichaIncidente t={es} idioma="es" incidente={conDeclaracion} />);
    expect(screen.getByText(es.ficha.declaracionOficial)).toBeTruthy();
    expect(ordenarFuentes(conDeclaracion.fuentes)[0]?.id).toBe(declaracion.id);
    expect(screen.getByText("B1")).toBeTruthy();
  });

  it("no despliega cientos de fuentes de golpe", async () => {
    const muchas = Array.from({ length: FUENTES_VISIBLES + 3 }, (_, i) =>
      fuente({ id: `gdelt-${String(i).padStart(16, "0")}`, medio: `medio-${i}.example` }),
    );
    const { container } = render(
      <FichaIncidente t={es} idioma="es" incidente={detalleIncidente(incidente({ fuentes: muchas }))} />,
    );
    expect(container.querySelectorAll("blockquote")).toHaveLength(FUENTES_VISIBLES);
    await userEvent.click(screen.getByRole("button", { name: es.ficha.masFuentes(3) }));
    expect(container.querySelectorAll("blockquote")).toHaveLength(muchas.length);
  });

  it("muestra el historial y calla la fuente que no es pública", () => {
    const conHistorial = detalleIncidente(
      incidente({
        estado: {
          actual: "desmentido",
          historial: [
            {
              estado: "notificado",
              fecha: { valor: "2026-09-13T11:30Z", precision: "aproximada" },
              fuente_id: "gdelt-0000000000000001",
            },
            { estado: "desmentido", fecha: { valor: "2026-09-14T08:00Z", precision: "hora" } },
          ],
        },
        control: {
          ultima_actualizacion: { valor: "2026-09-30T05:38Z", precision: "minuto" },
          motivo_desmentido: "El centro de crisis retiró el aviso",
        },
      }),
    );
    render(<FichaIncidente t={es} idioma="es" incidente={conHistorial} />);
    const historial = screen.getByRole("heading", { name: es.ficha.historial }).parentElement!;
    const pasos = within(historial).getAllByRole("listitem");
    expect(pasos).toHaveLength(2);
    expect(pasos[0]?.textContent).toContain("Notificado");
    expect(pasos[0]?.textContent).toContain("example.org");
    expect(pasos[1]?.textContent).toContain("Desmentido");
    expect(pasos[1]?.textContent).toContain(es.ficha.fuenteNoPublica);
    expect(screen.getByText("El centro de crisis retiró el aviso")).toBeTruthy();
  });

  it("sale en inglés con el nombre del país traducido", () => {
    render(<FichaIncidente t={en} idioma="en" incidente={detalle} />);
    expect(screen.getByText("Airport disruption")).toBeTruthy();
    expect(screen.getByText("Munich airport closure")).toBeTruthy();
    expect(screen.getByText("Germany", { exact: false })).toBeTruthy();
  });

  it.each(Object.entries(CARGAS_MALICIOSAS))(
    "un texto externo con %s se ve como texto y no se ejecuta",
    (_nombre, carga) => {
      const hostil = detalleIncidente(
        incidente({
          titulo: { es: carga, en: carga },
          objetivo: { categoria: "otra", nombre: carga },
          lugar: { radio_km: 5, pais: "DE", localidad: carga },
          drones: { numero: "desconocido", modelo: carga },
          consecuencias: { danos: { nivel: "menores", frase: carga } },
          atribucion: {
            actor: carga,
            autoridad: carga,
            fecha: { valor: "2026-01-01T00:00Z", precision: "dia" },
          },
          fuentes: [fuente({ medio: carga, frase_origen: carga })],
          control: {
            ultima_actualizacion: { valor: "2026-09-30T05:38Z", precision: "minuto" },
            motivo_desmentido: carga,
          },
        }),
      );
      const { container } = render(<FichaIncidente t={es} idioma="es" incidente={hostil} />);
      sinHtmlInyectado(container);
      // El texto llega entero a la pantalla, con sus símbolos tal cual.
      expect(container.querySelector("blockquote")?.textContent).toBe(carga);
      expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(carga);
    },
  );

  it("una fuente con un enlace que no es http ni https se queda sin enlace", () => {
    const hostil = detalleIncidente(
      incidente({ fuentes: [fuente({ enlace: "javascript:window.__ataque=true", medio: "medio" })] }),
    );
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={hostil} />);
    expect(container.querySelector("a")).toBeNull();
    expect(screen.getByText(`(${es.ficha.enlaceNoValido})`)).toBeTruthy();
  });
});

describe("enlace externo", () => {
  it("se abre en otra pestaña sin dar acceso a esta y lo dice", () => {
    render(
      <EnlaceExterno enlace="https://example.org/a" aviso="enlace externo" avisoNoValido="no válido">
        Medio
      </EnlaceExterno>,
    );
    const enlace = screen.getByRole("link");
    expect(enlace.getAttribute("href")).toBe("https://example.org/a");
    expect(enlace.getAttribute("target")).toBe("_blank");
    expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
    expect(enlace.textContent).toContain("↗");
    expect(enlace.textContent).toContain("(enlace externo)");
  });

  it.each(["javascript:alert(1)", "data:text/html,x", "/relativa", "ftp://example.org"])(
    "no enlaza %s",
    (enlace) => {
      const { container } = render(
        <EnlaceExterno enlace={enlace} aviso="enlace externo" avisoNoValido="no válido">
          Medio
        </EnlaceExterno>,
      );
      expect(container.querySelector("a")).toBeNull();
      expect(container.textContent).toContain("Medio");
      expect(container.textContent).toContain("(no válido)");
    },
  );
});

describe("ficha de un ataque de la capa de Ucrania", () => {
  it("avisa de que son cifras de parte y da el desglose", () => {
    render(
      <ProveedorDeRuta inicial="/">
        <FichaAtaque t={es} idioma="es" ataque={ataque({ incluido_en: "EODI-UA-2026-1010" })} />
      </ProveedorDeRuta>,
    );
    expect(screen.getByText(es.ataque.reivindicacion)).toBeTruthy();
    expect(screen.getByText(es.sentido.RU_UA)).toBeTruthy();
    expect(screen.getByText("188")).toBeTruthy();
    expect(screen.getByText("86–188")).toBeTruthy();
    expect(screen.getByText(es.ataque.derribadosONeutralizados)).toBeTruthy();
    expect(screen.getByText("Kiev (región)", { exact: false })).toBeTruthy();
    expect(screen.getByRole("link", { name: "EODI-UA-2026-1010" }).getAttribute("href")).toBe(
      "/EODI-UA-2026-1010",
    );
  });
});

describe("barra de estado", () => {
  const actualizado = "2026-09-30T12:42Z";
  const pasadas = (horas: number) => new Date(Date.UTC(2026, 8, 30, 12, 42) + horas * 3_600_000);
  const punto = (contenedor: HTMLElement) => contenedor.querySelector("[aria-hidden=true]")!;

  it("sin la hora del navegador no afirma nada: ni verde ni etiqueta", () => {
    const { container } = render(<BarraEstado t={es} actualizado={actualizado} ahora={null} />);
    expect(container.textContent).toBe("ACTUALIZADO 30/09/2026 · 12:42 UTC");
    expect(punto(container).className).not.toContain("bg-confirmado");
  });

  it.each([
    [0.5, "al_dia", "bg-confirmado", "DATOS AL DÍA (hace menos de 1 h)"],
    [3.6, "con_retraso", "bg-notificado", "DATOS CON RETRASO (hace 3 h)"],
    [30, "desactualizado", "bg-atribuido", "DATOS DESACTUALIZADOS (hace 30 h)"],
  ])("a las %s horas dice %s con color y con texto", (horas, estado, color, texto) => {
    const { container } = render(
      <BarraEstado t={es} actualizado={actualizado} ahora={pasadas(horas)} />,
    );
    expect(container.querySelector("p")?.dataset.frescura).toBe(estado);
    expect(punto(container).className).toContain(color);
    expect(container.textContent).toContain(texto);
  });

  it("en inglés dice UPDATED y el estado en inglés", () => {
    const { container } = render(<BarraEstado t={en} actualizado={actualizado} ahora={pasadas(7)} />);
    expect(container.textContent).toContain("UPDATED 30/09/2026 · 12:42 UTC");
    expect(container.textContent).toContain("DATA OUT OF DATE (7 h ago)");
  });

  it("sin datos lo dice y no pinta verde", () => {
    const { container } = render(<BarraEstado t={es} actualizado={null} ahora={pasadas(0)} />);
    expect(container.textContent).toBe("SIN DATOS");
    expect(punto(container).className).toContain("bg-atribuido");
  });
});

describe("metodología", () => {
  it("ofrece las cuatro descargas con licencia, versión y cita", () => {
    const { container } = render(
      <Metodologia t={es} abierta actualizado="2026-09-30T12:42Z" onCerrar={() => undefined} />,
    );
    const descargas = [...container.querySelectorAll("a[download]")].map((a) => a.getAttribute("href"));
    expect(descargas).toEqual([
      DESCARGAS.incidentesGeojson,
      DESCARGAS.incidentesCsv,
      DESCARGAS.ucraniaJson,
      DESCARGAS.ucraniaCsv,
    ]);
    expect(container.textContent).toContain("Versión del 30/09/2026 · 12:42 UTC");
    expect(container.textContent).toContain(
      "European Observatory of Drone Incidents (EODI). Incidentes con drones en Europa, " +
        "versión del 30/09/2026 · 12:42 UTC. https://droneobservatory.eu. Licencia CC BY 4.0.",
    );
    const licencia = [...container.querySelectorAll("a")].find((a) => a.textContent?.includes("CC BY 4.0"));
    expect(licencia?.getAttribute("href")).toBe("https://creativecommons.org/licenses/by/4.0/");
  });

  it("todos sus enlaces externos se abren aparte y sin referencia", () => {
    const { container } = render(
      <Metodologia t={en} abierta actualizado={null} onCerrar={() => undefined} />,
    );
    const externos = [...container.querySelectorAll('a[href^="http"]')];
    expect(externos.length).toBeGreaterThan(5);
    for (const enlace of externos) {
      expect(enlace.getAttribute("target")).toBe("_blank");
      expect(enlace.getAttribute("rel")).toBe("noopener noreferrer");
    }
    expect(container.textContent).toContain("automatic extraction validated by rules");
  });
});

describe("línea de tiempo", () => {
  const dominio = { desde: diaDeInstante("2025-01-01"), hasta: diaDeInstante("2025-12-31") };
  const ANCHO = 730;

  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(ANCHO);
  });

  function montar(periodo = dominio) {
    const onPeriodo = vi.fn();
    const onGranularidad = vi.fn();
    const onReproducir = vi.fn();
    render(
      <LineaTiempo
        t={es}
        idioma="es"
        dominio={dominio}
        periodo={periodo}
        onPeriodo={onPeriodo}
        granularidad="mes"
        onGranularidad={onGranularidad}
        incidentesPorDia={new Map([[diaDeInstante("2025-03-10"), 4]])}
        lanzamientosPorDia={null}
        reproduciendo={false}
        onReproducir={onReproducir}
      />,
    );
    return { onPeriodo, onGranularidad, onReproducir };
  }

  it("sus dos extremos se mueven con el teclado, de tramo en tramo", () => {
    const { onPeriodo } = montar();
    const inicio = screen.getByRole("slider", { name: es.tiempo.desde });
    const fin = screen.getByRole("slider", { name: es.tiempo.hasta });
    expect(inicio.getAttribute("aria-valuetext")).toBe("01/01/2025");
    fireEvent.keyDown(inicio, { key: "ArrowRight" });
    expect(onPeriodo).toHaveBeenLastCalledWith({
      desde: diaDeInstante("2025-02-01"),
      hasta: dominio.hasta,
    });
    fireEvent.keyDown(fin, { key: "ArrowLeft" });
    expect(onPeriodo).toHaveBeenLastCalledWith({
      desde: dominio.desde,
      hasta: diaDeInstante("2025-11-30"),
    });
    fireEvent.keyDown(fin, { key: "Home" });
    expect(onPeriodo).toHaveBeenLastCalledWith({ desde: dominio.desde, hasta: dominio.desde });
  });

  it("un extremo no cruza al otro ni sale del dominio", () => {
    const unMes = { desde: diaDeInstante("2025-03-01"), hasta: diaDeInstante("2025-03-31") };
    const { onPeriodo } = montar(unMes);
    fireEvent.keyDown(screen.getByRole("slider", { name: es.tiempo.desde }), { key: "End" });
    expect(onPeriodo).toHaveBeenLastCalledWith({ desde: unMes.hasta, hasta: unMes.hasta });
    fireEvent.keyDown(screen.getByRole("slider", { name: es.tiempo.hasta }), { key: "PageUp" });
    expect(onPeriodo).toHaveBeenLastCalledWith({
      desde: unMes.desde,
      hasta: diaDeInstante("2025-08-31"),
    });
  });

  it("cambia de granularidad, reproduce y vuelve a todo el dominio", async () => {
    const unMes = { desde: diaDeInstante("2025-03-01"), hasta: diaDeInstante("2025-03-31") };
    const { onPeriodo, onGranularidad, onReproducir } = montar(unMes);
    expect(screen.getByRole("radio", { name: "Mes" }).getAttribute("aria-checked")).toBe("true");
    await userEvent.click(screen.getByRole("radio", { name: "Día" }));
    expect(onGranularidad).toHaveBeenCalledWith("dia");
    await userEvent.click(screen.getByRole("button", { name: es.tiempo.reproducir }));
    expect(onReproducir).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: es.tiempo.todo }));
    expect(onPeriodo).toHaveBeenLastCalledWith(dominio);
    expect(screen.getByText("01/03/2025 – 31/03/2025")).toBeTruthy();
  });
});

describe("aplicación", () => {
  const incidentes = coleccion([
    incidente(),
    incidente({
      id: "EODI-2026-00007",
      tiempo: { inicio: { valor: "2026-09-13T00:00Z", precision: "dia" } },
      lugar: { radio_km: 5, pais: "LT" },
      titulo: { es: "Cierre del aeropuerto de Vilna", en: "Vilnius airport closed" },
    }),
  ]);
  const ucrania = publicacion([ataque()]);
  const resumen = resumir(incidentes, ucrania);

  function servir(ficheros: Record<string, unknown>) {
    vi.stubGlobal(
      "fetch",
      vi.fn((ruta: string) => {
        const cuerpo = ficheros[ruta];
        return Promise.resolve(
          cuerpo === undefined
            ? new Response("no", { status: 404 })
            : new Response(JSON.stringify(cuerpo), { status: 200 }),
        );
      }),
    );
  }

  function abrir(ruta: string) {
    return render(
      <ProveedorDeRuta inicial={ruta}>
        <App />
      </ProveedorDeRuta>,
    );
  }

  beforeEach(() => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const buenos = {
    "/datos/resumen.json": resumen,
    "/datos/ucrania-resumen.json": resumirUcrania(ucrania),
    "/datos/incidentes/EODI-2026-00007.json": detalleIncidente(incidentes.features[1]!),
  };

  it("pinta los incidentes y cuenta los del periodo", async () => {
    servir(buenos);
    abrir("/");
    const mapa = await screen.findByTestId("mapa");
    await waitFor(() => expect(within(mapa).getAllByRole("listitem")).toHaveLength(2));
    const contadores = screen.getByLabelText(es.cabecera.contadores);
    expect(contadores.textContent).toBe("Incidentes2Confirmados0Países2");
    expect(document.documentElement.lang).toBe("es");
  });

  it("la dirección de un incidente abre su ficha, también al recargar", async () => {
    servir(buenos);
    abrir("/en/EODI-2026-00007");
    const ficha = await screen.findByRole("complementary", { name: /EODI-2026-00007/ });
    await within(ficha).findByText("Vilnius airport closed");
    expect(within(ficha).getByRole("button", { name: en.ficha.copiarEnlace })).toBeTruthy();
    await waitFor(() =>
      expect(document.title).toBe("Vilnius airport closed · European Observatory of Drone Incidents"),
    );
    expect(document.documentElement.lang).toBe("en");
  });

  it("copia la dirección propia de la ficha", async () => {
    servir(buenos);
    const usuario = userEvent.setup();
    const escribir = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    abrir("/EODI-2026-00007");
    await usuario.click(await screen.findByRole("button", { name: es.ficha.copiarEnlace }));
    expect(escribir).toHaveBeenCalledWith("https://droneobservatory.eu/EODI-2026-00007");
    expect(await screen.findByRole("button", { name: es.ficha.enlaceCopiado })).toBeTruthy();
  });

  it("si el resumen no cumple el esquema avisa y no pinta nada a medias", async () => {
    const roto = { ...resumen, incidentes: [{ ...resumen.incidentes[0], estado: "rumor" }] };
    servir({ ...buenos, "/datos/resumen.json": roto });
    abrir("/");
    const aviso = await screen.findByRole("alert");
    expect(aviso.textContent).toContain(es.avisos.datosNoValidos);
    expect(screen.queryByTestId("mapa")).toBeNull();
    expect(screen.queryByRole("slider")).toBeNull();
  });

  it("si la ficha no cumple el esquema lo dice en lugar de mostrarla", async () => {
    const detalle = { ...detalleIncidente(incidentes.features[1]!), tipo: "otro" };
    servir({ ...buenos, "/datos/incidentes/EODI-2026-00007.json": detalle });
    abrir("/EODI-2026-00007");
    expect((await screen.findByText(es.avisos.fichaNoValida)).getAttribute("role")).toBe("alert");
    expect(screen.queryByText("Cierre del aeropuerto de Vilna")).toBeNull();
  });

  it("un identificador que no existe lo dice", async () => {
    servir(buenos);
    abrir("/EODI-2031-00001");
    expect(await screen.findByText(es.avisos.fichaNoEncontrada)).toBeTruthy();
  });

  it("la lista da acceso a las fichas sin usar el mapa", async () => {
    servir(buenos);
    const usuario = userEvent.setup();
    abrir("/");
    await screen.findByTestId("mapa");
    await usuario.click(screen.getByRole("button", { name: es.capas.lista }));
    const lista = await screen.findByRole("complementary", { name: es.lista.titulo });
    const enlaces = within(lista).getAllByRole("link");
    expect(enlaces.map((a) => a.getAttribute("href"))).toEqual([
      "/EODI-2026-00007",
      "/EODI-2025-00210",
    ]);
    await usuario.click(enlaces[0]!);
    expect(await screen.findByRole("complementary", { name: /EODI-2026-00007/ })).toBeTruthy();
  });
});
