// Los avisos del observatorio: los datos (public/anuncios.json) con los textos aprobados tal cual,
// la sección de la página «Avisos» con su ancla, y la ventana de todas las páginas
// (public/anuncio.js), cargada tal cual en un documento aparte (jsdom) con una red de mentira.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ANUNCIOS, fallosDeAnuncios, fechaDeAnuncio } from "../src/anuncios.ts";
import type { Anuncio } from "../src/anuncios.ts";
import { RUTAS_AVISOS } from "../src/avisos.ts";
import { paginaAvisos, revisionAvisos } from "../src/texto/avisos.ts";
import { paginaSoloTexto } from "../scripts/paginas.ts";

const WEB = join(import.meta.dirname, "..");
const CODIGO = readFileSync(join(WEB, "public", "anuncio.js"), "utf-8");
const ESTILOS = readFileSync(join(WEB, "src", "estilos.css"), "utf-8");
const INDICE = readFileSync(join(WEB, "index.html"), "utf-8");
const SW = readFileSync(join(WEB, "public", "sw.js"), "utf-8");

const PARON = "paron-2026-11-27";

/** Lo que se usa de jsdom (sin tipos publicados en el proyecto): un documento con su ventana. */
interface JSDOM {
  window: Window & typeof globalThis & { eval(codigo: string): unknown };
}
const { JSDOM } = createRequire(import.meta.url)("jsdom") as {
  JSDOM: new (html: string, opciones: Record<string, unknown>) => JSDOM;
};

/** Los textos aprobados, copiados del encargo: ni una palabra ni un signo distintos. */
const APROBADOS = {
  tituloEs: "Parón en la publicación de sucesos del 27 al 28 de noviembre de 2026",
  tituloEn: "Pause in incident publication from 27 to 28 November 2026",
  parrafosEs: [
    "Entre las 23:17 UTC del 27 de noviembre y las 08:41 UTC del 28 de noviembre de 2026 el observatorio no publicó sucesos nuevos.",
    "Qué pasó. Un medio de noticias empezó a limitar nuestras consultas y nuestro sistema se quedaba esperando su respuesta. Esa espera bloqueaba el tratamiento de todas las noticias pendientes, no solo las de ese medio. No fue un ataque ni un fallo de la web.",
    "Qué se retrasó. Las noticias pendientes se procesaron a las 08:17 UTC del 28 de noviembre y se publicaron a las 08:41 UTC. Entre ellas estaba el cierre del aeropuerto de Colonia/Bonn por un posible dron la noche del 27, que se publicó con casi doce horas de retraso. No se perdió ningún dato.",
    "Qué hemos cambiado. Cada página que consultamos tiene ahora su propio límite de tiempo. Si un medio no responde, se aparta y se vuelve a intentar más tarde, y el resto de noticias sigue adelante. Además, cada fallo queda registrado para detectarlo antes.",
  ],
  parrafosEn: [
    "Between 23:17 UTC on 27 November and 08:41 UTC on 28 November 2026 the observatory did not publish new incidents.",
    "What happened. A news outlet began limiting our requests and our system kept waiting for its reply. That wait blocked the processing of all pending news, not only that outlet's. It was not an attack or a fault in the website.",
    "What was delayed. The pending news was processed at 08:17 UTC on 28 November and published at 08:41 UTC. It included the closure of Cologne Bonn Airport over a possible drone on the night of the 27th, which was published almost twelve hours late. No data was lost.",
    "What we have changed. Each page we check now has its own time limit. If an outlet does not respond, it is set aside and retried later, and the rest of the news moves on. Every failure is also logged so we can spot it sooner.",
  ],
  ventanaEs:
    "Entre la noche del 27 y la mañana del 28 de noviembre el observatorio estuvo casi diez horas sin publicar sucesos nuevos por un fallo técnico. Ya está resuelto y no se perdió ningún dato. Más información en Avisos.",
  ventanaEn:
    "Between the night of 27 November and the morning of 28 November the observatory went almost ten hours without publishing new incidents because of a technical fault. It has been fixed and no data was lost. More information in Notices.",
};

function paron(): Anuncio {
  const a = ANUNCIOS.find((x) => x.id === PARON);
  if (a === undefined) throw new Error("sin el aviso del parón");
  return a;
}

describe("datos de los avisos (public/anuncios.json)", () => {
  it("están bien formados", () => {
    expect(fallosDeAnuncios(ANUNCIOS)).toEqual([]);
  });

  it("el parón es el más reciente, con los textos aprobados literalmente", () => {
    const a = paron();
    expect(ANUNCIOS[0]?.id).toBe(PARON);
    expect(a.fecha).toBe("2026-11-28");
    expect(a.titulo).toEqual({ es: APROBADOS.tituloEs, en: APROBADOS.tituloEn });
    expect(a.parrafos).toEqual({ es: APROBADOS.parrafosEs, en: APROBADOS.parrafosEn });
    expect(a.ventana?.texto).toEqual({ es: APROBADOS.ventanaEs, en: APROBADOS.ventanaEn });
    expect(a.ventana?.enlace).toEqual({
      texto: { es: "Avisos", en: "Notices" },
      ruta: { es: `${RUTAS_AVISOS.es}#${PARON}`, en: `${RUTAS_AVISOS.en}#${PARON}` },
    });
  });

  it("la ventana del parón dura como mucho 24 horas desde la publicación", () => {
    const v = paron().ventana;
    expect(v).toBeDefined();
    const hasta = Date.parse(v?.hasta ?? "");
    // Publicado el 28 de noviembre por la tarde (UTC): la ventana se va al día siguiente.
    expect(hasta).toBeGreaterThan(Date.parse("2026-11-29T12:00:00Z"));
    expect(hasta).toBeLessThanOrEqual(Date.parse("2026-11-29T23:59:00Z"));
  });

  it("detecta los fallos de un aviso mal escrito", () => {
    const malo = {
      ...paron(),
      id: "Mal id",
      fecha: "28/11/2026",
      ventana: {
        desde: "2026-11-29T00:00:00Z",
        hasta: "2026-11-28T00:00:00Z",
        texto: { es: "Sin enlace.", en: "No link." },
        enlace: { texto: { es: "Avisos", en: "Notices" }, ruta: { es: "/avisos", en: "https://otro.example/x" } },
      },
    } satisfies Anuncio;
    const fallos = fallosDeAnuncios([malo, malo]).join(" | ");
    expect(fallos).toContain("id no válido");
    expect(fallos).toContain("id repetido");
    expect(fallos).toContain("fecha no válida");
    expect(fallos).toContain("acaba antes de empezar");
    expect(fallos).toContain("no contiene «Avisos»");
    expect(fallos).toContain("el enlace en no lleva");
  });
});

describe("página «Avisos»", () => {
  it("lleva el aviso arriba, con su ancla, su fecha y sus párrafos, en los dos idiomas", () => {
    for (const idioma of ["es", "en"] as const) {
      const cuerpo = paginaAvisos(idioma).cuerpo.valor;
      const inicio = cuerpo.indexOf(`<article class="texto-anuncio" id="${PARON}">`);
      expect(inicio).toBeGreaterThan(-1);
      expect(inicio).toBeLessThan(cuerpo.indexOf('id="pasos"'));
      const titulo = idioma === "es" ? APROBADOS.tituloEs : APROBADOS.tituloEn;
      expect(cuerpo).toContain(`<h3>${titulo}</h3>`);
      expect(cuerpo).toContain('<time datetime="2026-11-28">28/11/2026</time>');
      const parrafos = idioma === "es" ? APROBADOS.parrafosEs : APROBADOS.parrafosEn;
      for (const p of parrafos) expect(cuerpo).toContain(`<p>${p.replace(/'/g, "&#39;")}</p>`);
    }
  });

  it("la revisión de la página es la del aviso más reciente", () => {
    expect(paginaAvisos("es").modificada).toBe("2026-11-28T00:00:00Z");
    expect(revisionAvisos([])).toBe("2026-10-11T00:00:00Z");
  });

  it("sin avisos, no hay sección; con datos mal escritos, el build falla", () => {
    expect(paginaAvisos("es", []).cuerpo.valor).not.toContain("avisos-del-observatorio");
    expect(() => paginaAvisos("es", [{ ...paron(), id: "MAL" }])).toThrow(/anuncios\.json/);
  });

  it("fechaDeAnuncio escribe día/mes/año", () => {
    expect(fechaDeAnuncio("2026-11-28")).toBe("28/11/2026");
  });
});

describe("la ventana en todas las páginas, sin nada en línea", () => {
  it("el mapa y las páginas de texto cargan /anuncio.js como fichero", () => {
    expect(INDICE).toContain('<script src="/anuncio.js" defer></script>');
    const plantilla = '<!doctype html><html lang="es"><head><script src="/visitas.js" defer></script><!--cabecera--><title>x</title><!--/cabecera--></head><body><div id="root"></div></body></html>';
    const pagina = { ...paginaAvisos("es"), estructurados: [], conMapa: false };
    const salida = paginaSoloTexto(plantilla, pagina, "2026-11-28T12:00:00Z");
    expect(salida).toContain('<script src="/anuncio.js" defer></script>');
  });

  it("el código no escribe HTML ni estilos en línea", () => {
    expect(CODIGO).not.toMatch(/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\.style\b|setAttribute\("style"|eval\(|new Function/);
    expect(ESTILOS).toContain(".anuncio {");
  });

  it("el service worker pide la ventana y sus datos primero a la red", () => {
    expect(SW).toContain('"/anuncio.js", "/anuncios.json"');
  });
});

// ---------------------------------------------------------------------------------------------
// La ventana, ejecutada en un documento aparte.

interface Api {
  elegir(datos: unknown, ahora: number, cerrados: string[]): { id: string } | null;
  vigente(anuncio: unknown, ahora: number): boolean;
  partir(frase: string, palabra: string): [string, string, string];
  idiomaDe(lang: string): "es" | "en";
}

const AHORA = Date.parse("2026-11-28T20:00:00Z");

function datosCon(...anuncios: Anuncio[]): { anuncios: Anuncio[] } {
  return { anuncios };
}

function conVentana(id: string, desde: string, hasta: string): Anuncio {
  const base = paron();
  const v = base.ventana;
  if (v === undefined) throw new Error("sin ventana");
  return {
    ...base,
    id,
    ventana: {
      ...v,
      desde,
      hasta,
      enlace: { ...v.enlace, ruta: { es: `/avisos#${id}`, en: `/en/alerts#${id}` } },
    },
  };
}

interface Documento {
  dom: JSDOM;
  api: Api;
  peticiones: string[];
  listo: () => Promise<void>;
}

function abrir(opciones: { lang?: string; datos?: unknown; guardado?: Record<string, string>; ahora?: number; cuerpo?: string } = {}): Documento {
  const dom = new JSDOM(
    `<!doctype html><html lang="${opciones.lang ?? "es"}"><head></head><body>${opciones.cuerpo ?? '<main id="mapa" tabindex="-1"><button id="otro">otro</button></main>'}</body></html>`,
    { url: "https://droneobservatory.eu/", runScripts: "outside-only", pretendToBeVisual: true },
  );
  const w = dom.window;
  for (const [clave, valor] of Object.entries(opciones.guardado ?? {})) w.localStorage.setItem(clave, valor);
  const peticiones: string[] = [];
  const datos = opciones.datos ?? datosCon(paron());
  let fin: () => void = () => undefined;
  const hecho = new Promise<void>((r) => {
    fin = r;
  });
  Object.assign(w, {
    fetch: (url: string) => {
      peticiones.push(url);
      fin();
      return Promise.resolve({ ok: true, json: () => Promise.resolve(datos) });
    },
  });
  const ahora = opciones.ahora ?? AHORA;
  w.Date.now = () => ahora;
  w.eval(CODIGO);
  const api = (w as unknown as { eodiAnuncios: Api }).eodiAnuncios;
  const listo = async () => {
    if (peticiones.length > 0) await hecho;
    for (let i = 0; i < 5; i += 1) await new Promise((r) => setTimeout(r, 0));
  };
  return { dom, api, peticiones, listo };
}

function ventana(d: Documento): Element | null {
  return d.dom.window.document.querySelector("[data-anuncio]");
}

describe("public/anuncio.js", () => {
  it("elige el primer aviso vigente y no cerrado", () => {
    const { api } = abrir({ datos: { anuncios: [] } });
    const viejo = conVentana("viejo", "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z");
    const futuro = conVentana("futuro", "2026-12-01T00:00:00Z", "2026-12-02T00:00:00Z");
    const uno = conVentana("uno", "2026-11-28T00:00:00Z", "2026-11-29T20:00:00Z");
    const dos = conVentana("dos", "2026-11-28T00:00:00Z", "2026-11-30T00:00:00Z");
    const datos = datosCon(viejo, futuro, uno, dos);
    expect(api.elegir(datos, AHORA, [])?.id).toBe("uno");
    expect(api.elegir(datos, AHORA, ["uno"])?.id).toBe("dos");
    expect(api.elegir(datos, AHORA, ["uno", "dos"])).toBeNull();
    // Justo a la hora de caducar ya no sale.
    expect(api.vigente(uno, Date.parse("2026-11-29T20:00:00Z"))).toBe(false);
    expect(api.vigente(uno, Date.parse("2026-11-29T19:59:59Z"))).toBe(true);
    // Un aviso sin ventana (solo para la página) o mal formado no sale.
    const { ventana: _sin, ...soloPagina } = uno;
    void _sin;
    expect(api.elegir(datosCon(soloPagina as Anuncio), AHORA, [])).toBeNull();
    expect(api.elegir({ nada: 1 }, AHORA, [])).toBeNull();
    expect(api.elegir(null, AHORA, [])).toBeNull();
  });

  it("parte el texto en la última aparición de la palabra del enlace", () => {
    const { api } = abrir({ datos: { anuncios: [] } });
    expect(api.partir(APROBADOS.ventanaEs, "Avisos")).toEqual([APROBADOS.ventanaEs.slice(0, -7), "Avisos", "."]);
    expect(api.idiomaDe("en-GB")).toBe("en");
    expect(api.idiomaDe("es")).toBe("es");
  });

  it("sale en español con el texto aprobado y el enlace al aviso", async () => {
    const d = abrir();
    await d.listo();
    expect(d.peticiones).toEqual(["/anuncios.json"]);
    const caja = ventana(d);
    expect(caja).not.toBeNull();
    expect(caja?.tagName).toBe("ASIDE");
    expect(caja?.getAttribute("aria-label")).toBe("Aviso del observatorio");
    expect(caja?.querySelector("p")?.textContent).toBe(APROBADOS.ventanaEs);
    const enlace = caja?.querySelector("a");
    expect(enlace?.textContent).toBe("Avisos");
    expect(enlace?.getAttribute("href")).toBe(`/avisos#${PARON}`);
    expect(caja?.querySelector("button")?.getAttribute("aria-label")).toBe("Cerrar el aviso");
    // La primera de la página, para el teclado y el lector de pantalla.
    expect(d.dom.window.document.body.firstElementChild).toBe(caja);
  });

  it("sale en inglés en las páginas en inglés y cambia con el idioma", async () => {
    const d = abrir({ lang: "en" });
    await d.listo();
    const caja = ventana(d);
    expect(caja?.querySelector("p")?.textContent).toBe(APROBADOS.ventanaEn);
    expect(caja?.querySelector("a")?.textContent).toBe("Notices");
    expect(caja?.querySelector("a")?.getAttribute("href")).toBe(`/en/alerts#${PARON}`);
    expect(caja?.getAttribute("aria-label")).toBe("Observatory notice");
    d.dom.window.document.documentElement.lang = "es";
    await d.listo();
    expect(ventana(d)?.querySelector("p")?.textContent).toBe(APROBADOS.ventanaEs);
  });

  it("el botón la cierra para siempre en ese navegador y el foco va al mapa", async () => {
    const d = abrir();
    await d.listo();
    const boton = ventana(d)?.querySelector("button") as HTMLButtonElement;
    boton.focus();
    boton.click();
    expect(ventana(d)).toBeNull();
    expect(d.dom.window.document.activeElement?.id).toBe("mapa");
    expect(JSON.parse(d.dom.window.localStorage.getItem("eodi.anuncios.cerrados") ?? "[]")).toEqual([PARON]);
    const otra = abrir({ guardado: { "eodi.anuncios.cerrados": JSON.stringify([PARON]) } });
    await otra.listo();
    expect(ventana(otra)).toBeNull();
  });

  it("Escape la cierra con el foco en ella o en ningún sitio, no con el foco en otro control", async () => {
    const d = abrir();
    await d.listo();
    const w = d.dom.window;
    const escape = () => w.document.activeElement?.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    (w.document.getElementById("otro") as HTMLButtonElement).focus();
    escape();
    expect(ventana(d)).not.toBeNull();
    (ventana(d)?.querySelector("a") as HTMLAnchorElement).focus();
    escape();
    expect(ventana(d)).toBeNull();
    expect(w.localStorage.getItem("eodi.anuncios.cerrados")).toContain(PARON);

    const libre = abrir();
    await libre.listo();
    (libre.dom.window.document.activeElement as HTMLElement | null)?.blur();
    libre.dom.window.document.body.dispatchEvent(new libre.dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(ventana(libre)).toBeNull();
  });

  it("caducada, antes de tiempo o apagada para las pruebas, no sale (ni pide los datos si está apagada)", async () => {
    const caducada = abrir({ ahora: Date.parse("2026-12-01T00:00:00Z") });
    await caducada.listo();
    expect(ventana(caducada)).toBeNull();
    const apagada = abrir({ guardado: { "eodi.anuncios.ninguno": "1" } });
    await apagada.listo();
    expect(apagada.peticiones).toEqual([]);
    expect(ventana(apagada)).toBeNull();
  });

  it("se va sola a la hora de caducar con la página abierta", async () => {
    const hasta = Date.parse(paron().ventana?.hasta ?? "");
    const d = abrir({ ahora: hasta - 300 });
    await d.listo();
    expect(ventana(d)).not.toBeNull();
    await new Promise((r) => setTimeout(r, 450));
    expect(ventana(d)).toBeNull();
    // Caducar no es cerrar: no se guarda nada.
    expect(d.dom.window.localStorage.getItem("eodi.anuncios.cerrados")).toBeNull();
  });

  it("si los datos no llegan, la página sigue igual", async () => {
    const dom = new JSDOM('<!doctype html><html lang="es"><body><p>x</p></body></html>', {
      url: "https://droneobservatory.eu/",
      runScripts: "outside-only",
    });
    Object.assign(dom.window, { fetch: () => Promise.reject(new Error("sin red")) });
    expect(() => dom.window.eval(CODIGO)).not.toThrow();
    await new Promise((r) => setTimeout(r, 10));
    expect(dom.window.document.querySelector("[data-anuncio]")).toBeNull();
  });
});
