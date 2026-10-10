// Recorridos como los hace una persona, en un Android (Chromium, Pixel 7), un iPhone (WebKit,
// iPhone 14), una tableta táctil (768 × 1024) y el escritorio (Chromium y WebKit, 1366 × 768 y
// 1920 × 1080, con ratón y solo con teclado). Nada se pulsa por código: en el teléfono se abre la
// hoja, se sube con el dedo, se desplaza el contenido y entonces se toca, que es lo que se comía el
// primer toque (el descarte del clic de un arrastre quedaba pendiente). En Chromium los toques y
// los arrastres son eventos táctiles de bajo nivel (CDP); WebKit no tiene arrastres táctiles en
// Playwright, así que allí la hoja se arrastra con el puntero del motor y se toca con su pantalla
// táctil, dejando la pausa de una persona entre una cosa y otra.
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts).
// Va contra producción por defecto; con BASE y BYPASS (o VERCEL_BYPASS), contra una vista previa.
import { expect, test } from "@playwright/test";
import type { BrowserContext, CDPSession, Locator, Page } from "@playwright/test";

const MAPA = "[data-mapa-listo=true]";
const CLAVE = process.env.BYPASS ?? process.env.VERCEL_BYPASS;
/** La pausa de una persona entre soltar un arrastre y tocar otra cosa. */
const PAUSA_MS = 450;
/** Lo que el dedo se queda quieto al final de un arrastre, antes de levantarse. */
const QUIETO_MS = 300;

interface Punto {
  x: number;
  y: number;
}

/** El dedo (o el ratón) de quien usa la web, con lo que permite cada motor. */
class Persona {
  readonly pagina: Page;
  private readonly cdp: CDPSession | null;
  readonly tactil: boolean;

  constructor(pagina: Page, cdp: CDPSession | null, tactil: boolean) {
    this.pagina = pagina;
    this.cdp = cdp;
    this.tactil = tactil;
  }

  static async en(pagina: Page, contexto: BrowserContext, tactil: boolean, chromium: boolean): Promise<Persona> {
    const cdp = tactil && chromium ? await contexto.newCDPSession(pagina) : null;
    return new Persona(pagina, cdp, tactil);
  }

  async centro(elemento: Locator): Promise<Punto> {
    await elemento.scrollIntoViewIfNeeded();
    const caja = await elemento.boundingBox();
    if (caja === null) throw new Error("sin caja");
    return { x: caja.x + caja.width / 2, y: caja.y + caja.height / 2 };
  }

  async tocarEn(punto: Punto) {
    if (this.cdp !== null) {
      await this.cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [punto] });
      await this.pagina.waitForTimeout(70);
      await this.cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    } else if (this.tactil) {
      await this.pagina.touchscreen.tap(punto.x, punto.y);
    } else {
      await this.pagina.mouse.move(punto.x, punto.y, { steps: 4 });
      await this.pagina.mouse.click(punto.x, punto.y);
    }
    await this.pagina.waitForTimeout(PAUSA_MS);
  }

  async tocar(elemento: Locator) {
    await this.tocarEn(await this.centro(elemento));
  }

  /** Arrastra en vertical desde un punto (hacia arriba con dy negativo). */
  async arrastrar(desde: Punto, dy: number) {
    const pasos = 14;
    if (this.cdp !== null) {
      await this.cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [desde] });
      for (let i = 1; i <= pasos; i += 1) {
        await this.cdp.send("Input.dispatchTouchEvent", {
          type: "touchMove",
          touchPoints: [{ x: desde.x, y: desde.y + (dy * i) / pasos }],
        });
        await this.pagina.waitForTimeout(16);
      }
      // El dedo se para antes de levantarse. Si se levanta en movimiento, Chromium sin pantalla
      // lanza un desplazamiento por inercia que no termina nunca, y el siguiente toque solo lo
      // detiene (sin clic), aunque la página esté vacía: no es de la web.
      await this.pagina.waitForTimeout(QUIETO_MS);
      await this.cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    } else {
      await this.pagina.mouse.move(desde.x, desde.y);
      await this.pagina.mouse.down();
      await this.pagina.mouse.move(desde.x, desde.y + dy, { steps: pasos });
      await this.pagina.mouse.up();
    }
    await this.pagina.waitForTimeout(700);
  }

  /**
   * Desplaza el contenido bajo el elemento: con el dedo en Chromium y con la rueda en el escritorio.
   * WebKit en modo teléfono no tiene ni lo uno ni lo otro en Playwright: allí se desplaza el
   * contenedor, como haría el dedo.
   */
  async desplazar(elemento: Locator, dy: number) {
    const punto = await this.centro(elemento);
    if (this.cdp !== null) {
      await this.arrastrar(punto, -dy);
      return;
    }
    if (this.tactil) {
      await elemento.evaluate((e, cuanto) => {
        for (let a: HTMLElement | null = e as HTMLElement; a !== null; a = a.parentElement) {
          if (/(auto|scroll)/.test(getComputedStyle(a).overflowY) && a.scrollHeight > a.clientHeight) {
            a.scrollBy(0, cuanto);
            return;
          }
        }
      }, dy);
    } else {
      await this.pagina.mouse.move(punto.x, punto.y);
      await this.pagina.mouse.wheel(0, dy);
    }
    await this.pagina.waitForTimeout(500);
  }
}

/** Errores de consola, excepciones y peticiones fallidas durante el recorrido. */
function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("console", (mensaje) => {
    // Chromium sin la aplicación ntfy instalada avisa de que no puede abrir su enlace.
    if (mensaje.type() === "error" && !/ntfy:/.test(mensaje.text())) errores.push(`consola: ${mensaje.text()}`);
  });
  pagina.on("pageerror", (error) => errores.push(`excepción: ${error.message}`));
  pagina.on("requestfailed", (peticion) => {
    const motivo = peticion.failure()?.errorText ?? "";
    if (peticion.url().startsWith("ntfy:") || /ABORTED|cancelled/i.test(motivo)) return;
    errores.push(`petición: ${peticion.url()} ${motivo}`);
  });
  return errores;
}

async function abrir(contexto: BrowserContext, pagina: Page, ruta = "/"): Promise<string[]> {
  // Las tiendas no se abren de verdad.
  await contexto.route(/apps\.apple\.com|play\.google\.com|f-droid\.org/, (r) => r.fulfill({ status: 200, body: "" }));
  const errores = vigilar(pagina);
  await pagina.goto(ruta, { waitUntil: "domcontentloaded" });
  await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
  await pagina.waitForTimeout(1500);
  return errores;
}

/** Anota cada clic que llega a la ventana: a qué enlace iba y si alguien lo anuló. */
async function anotarClics(pagina: Page) {
  await pagina.evaluate(() => {
    const ventana = window as unknown as { __clics: { href: string | null; anulado: boolean }[] };
    ventana.__clics = [];
    window.addEventListener("click", (evento) => {
      const enlace = evento.target instanceof Element ? evento.target.closest("a") : null;
      ventana.__clics.push({ href: enlace?.href ?? null, anulado: evento.defaultPrevented });
      // El enlace de la aplicación no lleva a ninguna parte en el navegador de pruebas.
      if (enlace?.href.startsWith("ntfy:") === true) evento.preventDefault();
    });
  });
}

async function ultimoClic(pagina: Page) {
  return pagina.evaluate(() => (window as unknown as { __clics: { href: string | null; anulado: boolean }[] }).__clics.at(-1));
}

/** La vista del mapa cuando deja de moverse. */
async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  let anterior = "";
  for (let i = 0; i < 30; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior && !ahora.includes("null")) break;
    anterior = ahora;
  }
  return anterior;
}

/** Sube la hoja del teléfono con el dedo desde el asa y la deja a pantalla completa. */
async function subirHoja(persona: Persona) {
  const hoja = persona.pagina.locator("aside[data-altura]");
  await persona.arrastrar(await persona.centro(hoja.locator("button[data-arrastre]").first()), -350);
  await expect(hoja).toHaveAttribute("data-altura", "completa");
  await persona.pagina.waitForTimeout(PAUSA_MS);
}

/** Cambia un conmutador con un solo toque y lo deja como estaba con otro. */
async function conmutarDosVeces(persona: Persona, control: Locator) {
  const antes = await control.getAttribute("aria-pressed");
  const despues = antes === "true" ? "false" : "true";
  await persona.tocar(control);
  await expect(control, "el primer toque cambia el control").toHaveAttribute("aria-pressed", despues);
  await persona.tocar(control);
  await expect(control).toHaveAttribute("aria-pressed", antes ?? "false");
}

if (CLAVE !== undefined) test.use({ extraHTTPHeaders: { "x-vercel-protection-bypass": CLAVE } });

const TELEFONOS = ["android", "iphone"];

// ---------------------------------------------------------------------------------------------
test.describe("teléfono: abrir la hoja, subirla con el dedo, desplazar y entonces tocar", () => {
  test.beforeEach(({ browserName }, info) => {
    void browserName;
    test.skip(!TELEFONOS.includes(info.project.name), "solo en el Android y el iPhone");
  });

  test("Filtros: el primer toque tras subir la hoja selecciona; se cierra de las tres formas", async ({ page: pagina, context: contexto, browserName }) => {
    const errores = await abrir(contexto, pagina);
    const persona = await Persona.en(pagina, contexto, true, browserName === "chromium");
    const boton = pagina.locator("[data-boton-filtros] button:visible").first();
    const hoja = pagina.locator("aside[data-altura]");
    const filtros = pagina.locator("[data-filtros]:visible");

    await persona.tocar(boton);
    await expect(filtros).toBeVisible();
    await subirHoja(persona);
    await persona.desplazar(filtros, 250);
    await persona.desplazar(filtros, -250);
    const controles = filtros.locator("button[aria-pressed]");
    await conmutarDosVeces(persona, controles.first());
    await conmutarDosVeces(persona, controles.nth(1));
    await conmutarDosVeces(persona, controles.last());

    // Con la X.
    await persona.tocar(hoja.getByRole("button", { name: "Cerrar los filtros" }));
    await expect(filtros).toHaveCount(0);
    // Con Escape.
    await persona.tocar(boton);
    await expect(filtros).toBeVisible();
    await pagina.keyboard.press("Escape");
    await expect(filtros).toHaveCount(0);
    // Arrastrando hacia abajo; después, el siguiente toque responde a la primera.
    await persona.tocar(boton);
    await expect(filtros).toBeVisible();
    await persona.arrastrar(await persona.centro(hoja.locator("button[data-arrastre]").first()), 600);
    await expect(filtros).toHaveCount(0);
    await persona.tocar(boton);
    await expect(filtros).toBeVisible();
    await conmutarDosVeces(persona, controles.first());
    expect(errores).toEqual([]);
  });

  test("Avisos: subir la hoja, buscar un país y «Suscribirme» al primer toque", async ({ page: pagina, context: contexto, browserName }, info) => {
    const errores = await abrir(contexto, pagina);
    const persona = await Persona.en(pagina, contexto, true, browserName === "chromium");
    await persona.tocar(pagina.locator("[data-boton-avisos]:visible").first());
    const panel = pagina.locator("[data-panel-avisos]:visible");
    await expect(panel).toBeVisible();
    await persona.tocar(panel.locator("[data-buscar-canal]"));
    await pagina.keyboard.type("pol", { delay: 80 });
    await expect(panel.locator("[data-canal-elegido]")).toHaveValue("drones-poland");
    // Como lo hizo quien encontró el fallo: subir la hoja, desplazar y el primer toque es
    // «Suscribirme».
    await subirHoja(persona);
    await persona.desplazar(panel, 300);
    await anotarClics(pagina);

    const suscribirme = panel.locator("[data-suscribirme]");
    const android = info.project.name === "android";
    const nueva = android ? null : contexto.waitForEvent("page", { timeout: 5000 });
    await persona.tocar(suscribirme);
    const clic = await ultimoClic(pagina);
    expect(clic, "el toque llega a «Suscribirme»").toBeDefined();
    expect(clic?.anulado, "nadie anula el toque").toBe(false);
    if (android) {
      expect(clic?.href).toBe("ntfy://ntfy.droneobservatory.eu/drones-poland?display=EODI+%C2%B7+Polonia");
    } else {
      expect(clic?.href).toContain("apps.apple.com");
      await (await nueva)?.close();
      // En el iPhone, el servidor y el canal se copian con sus botones.
      const estado = panel.locator("[role=status]").last();
      await persona.tocar(panel.getByRole("button", { name: /servidor/ }));
      await expect(estado).toContainText("ntfy.droneobservatory.eu");
      await persona.tocar(panel.getByRole("button", { name: /canal/ }));
      await expect(estado).toContainText("drones-poland");
    }
    await pagina.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    expect(errores).toEqual([]);
  });

  test("Europa ahora y Previsión: pestaña y plegables al primer toque tras subir la hoja", async ({
    page: pagina,
    context: contexto,
    browserName,
  }) => {
    const errores = await abrir(contexto, pagina);
    const persona = await Persona.en(pagina, contexto, true, browserName === "chromium");
    await persona.tocar(pagina.locator("[data-boton-ahora]:visible").first());
    const pestanas = pagina.locator("[data-pestanas-ahora]");
    await expect(pestanas).toBeVisible();
    await subirHoja(persona);
    const prevision = pestanas.getByRole("tab", { name: "Previsión" });
    await persona.tocar(prevision);
    await expect(prevision, "la pestaña cambia al primer toque").toHaveAttribute("aria-selected", "true");
    const panel = pagina.locator("[data-prevision]:visible");
    await expect(panel).toBeVisible({ timeout: 15_000 });
    await persona.desplazar(panel, 300);
    const plegable = panel.locator("summary:visible").first();
    await persona.tocar(plegable);
    await expect.poll(() => plegable.evaluate((e) => (e.parentElement as HTMLDetailsElement).open)).toBe(true);
    await persona.tocar(pestanas.getByRole("tab", { name: "Europa ahora" }));
    await expect(pestanas.getByRole("tab", { name: "Europa ahora" })).toHaveAttribute("aria-selected", "true");
    await pagina.keyboard.press("Escape");
    await expect(pestanas).toHaveCount(0);
    expect(errores).toEqual([]);
  });

  test("Menú: cada capa cambia al primer toque tras desplazar, y «Aplicar» cierra", async ({ page: pagina, context: contexto, browserName }) => {
    const errores = await abrir(contexto, pagina);
    const persona = await Persona.en(pagina, contexto, true, browserName === "chromium");
    await persona.tocar(pagina.locator("[data-boton-menu]:visible").first());
    const menu = pagina.locator("dialog[open]");
    await expect(menu).toBeVisible();
    await persona.desplazar(menu, 300);
    await persona.desplazar(menu, -300);
    const capas = menu.locator("button[aria-pressed]:visible");
    const cuantas = await capas.count();
    expect(cuantas).toBeGreaterThan(3);
    for (let i = 0; i < Math.min(cuantas, 4); i += 1) await conmutarDosVeces(persona, capas.nth(i));
    await persona.tocar(menu.locator("[data-pie-menu] button").filter({ hasText: /^Aplicar$/ }));
    await expect(menu).toHaveCount(0);
    expect(errores).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------------
test.describe("tableta y escritorio", () => {
  test.beforeEach(({ browserName }, info) => {
    void browserName;
    test.skip(TELEFONOS.includes(info.project.name), "el teléfono va arriba");
  });

  for (const tamano of [
    { width: 1366, height: 768 },
    { width: 1920, height: 1080 },
  ]) {
    test.describe(`${tamano.width}×${tamano.height}`, () => {
      test.use({ viewport: tamano });
      test(`Filtros y Avisos a la primera, a ${tamano.width}×${tamano.height} en escritorio y en la tableta`, async ({
        page: pagina,
        context: contexto,
        browserName,
      }, info) => {
        const tableta = info.project.name === "tableta";
        test.skip(tableta && tamano.width !== 1366, "la tableta tiene su tamaño");
        if (tableta) await pagina.setViewportSize({ width: 768, height: 1024 });
        const errores = await abrir(contexto, pagina);
        const persona = await Persona.en(pagina, contexto, tableta, browserName === "chromium");
        const inicial = await vista(pagina);

        await persona.tocar(pagina.locator("[data-boton-filtros] button:visible").first());
        const filtros = pagina.locator("[data-filtros]:visible");
        await expect(filtros).toBeVisible();
        const controles = filtros.locator("button[aria-pressed]");
        await conmutarDosVeces(persona, controles.first());
        await conmutarDosVeces(persona, controles.nth(1));
        await pagina.keyboard.press("Escape");
        await expect(filtros).toHaveCount(0);

        await persona.tocar(pagina.locator("[data-boton-avisos]:visible").first());
        const panel = pagina.locator("[data-panel-avisos]:visible");
        await expect(panel).toBeVisible();
        await panel.locator("[data-canal-elegido]").selectOption("drones-france");
        const suscribirme = panel.locator("[data-suscribirme]");
        if (tableta) {
          // Una tableta Android abre la aplicación, igual que el teléfono.
          await expect(suscribirme).toHaveAttribute("href", /^ntfy:\/\/ntfy\.droneobservatory\.eu\/drones-france\?display=/);
          await anotarClics(pagina);
          await persona.tocar(suscribirme);
          expect((await ultimoClic(pagina))?.anulado).toBe(false);
        } else {
          await expect(suscribirme).toHaveAttribute("href", "https://ntfy.droneobservatory.eu/drones-france");
          const qr = panel.locator("[data-qr-avisos] img");
          await expect(qr).toHaveAttribute("src", "/avisos/qr/drones-france.svg");
          await expect.poll(() => qr.evaluate((imagen: HTMLImageElement) => imagen.complete && imagen.naturalWidth > 0)).toBe(true);
        }
        await pagina.keyboard.press("Escape");
        await expect(panel).toHaveCount(0);
        expect(await vista(pagina), "abrir y cerrar paneles no mueve el mapa").toBe(inicial);
        expect(errores).toEqual([]);
      });
    });
  }

  test("solo con teclado: Avisos y Filtros", async ({ page: pagina, context: contexto }, info) => {
    test.skip(info.project.name === "tableta", "la tableta va con el dedo");
    const errores = await abrir(contexto, pagina);
    const avisos = pagina.locator("[data-boton-avisos]:visible").first();
    await avisos.focus();
    await pagina.keyboard.press("Enter");
    const panel = pagina.locator("[data-panel-avisos]:visible");
    await expect(panel).toBeVisible();
    await panel.locator("[data-buscar-canal]").focus();
    await pagina.keyboard.type("ital", { delay: 40 });
    await expect(panel.locator("[data-canal-elegido]")).toHaveValue("drones-italy");
    await pagina.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    await expect(avisos).toBeFocused();

    const botonFiltros = pagina.locator("[data-boton-filtros] button:visible").first();
    await botonFiltros.focus();
    await pagina.keyboard.press("Enter");
    const filtros = pagina.locator("[data-filtros]:visible");
    await expect(filtros).toBeVisible();
    const primero = filtros.locator("button[aria-pressed]").first();
    const antes = await primero.getAttribute("aria-pressed");
    await primero.focus();
    await pagina.keyboard.press("Space");
    await expect(primero).not.toHaveAttribute("aria-pressed", antes ?? "false");
    await pagina.keyboard.press("Space");
    await expect(primero).toHaveAttribute("aria-pressed", antes ?? "false");
    await pagina.keyboard.press("Escape");
    await expect(filtros).toHaveCount(0);
    expect(errores).toEqual([]);
  });
});

// ---------------------------------------------------------------------------------------------
test("mapa: tocar un incidente abre su ficha y cerrarla no mueve el mapa", async ({ page: pagina, context: contexto, browserName }, info) => {
  const tactil = info.project.name !== "escritorio-chromium" && info.project.name !== "escritorio-webkit";
  const errores = await abrir(contexto, pagina);
  const persona = await Persona.en(pagina, contexto, tactil, browserName === "chromium");
  await pagina.waitForTimeout(1000);
  const antes = await vista(pagina);
  const punto = await pagina.evaluate(() => {
    interface Rasgo {
      source: string;
      layer: { id: string; type: string };
      geometry: { type: string; coordinates: [number, number] };
    }
    interface MapaDePruebas {
      queryRenderedFeatures: (caja?: [[number, number], [number, number]]) => Rasgo[];
      project: (coordenadas: [number, number]) => { x: number; y: number };
    }
    const elemento = document.querySelector<HTMLElement & { mapaDePruebas?: MapaDePruebas }>(".maplibregl-map");
    const mapa = elemento?.mapaDePruebas;
    if (elemento === null || mapa === undefined) return null;
    const caja = elemento.getBoundingClientRect();
    const marca = (r: Rasgo) => r.source !== "protomaps" && r.layer.type !== "fill";
    for (const rasgo of mapa.queryRenderedFeatures().filter((r) => r.layer.id.startsWith("incidentes-") && r.geometry.type === "Point")) {
      const q = mapa.project(rasgo.geometry.coordinates);
      if (q.x < 60 || q.y < 140 || q.x > caja.width - 60 || q.y > caja.height - 160) continue;
      const cerca = mapa.queryRenderedFeatures([[q.x - 30, q.y - 30], [q.x + 30, q.y + 30]]).filter(marca);
      if (new Set(cerca.map((r) => JSON.stringify(r.geometry.coordinates))).size === 1) return { x: caja.x + q.x, y: caja.y + q.y };
    }
    return null;
  });
  expect(punto, "un incidente aislado a la vista").not.toBeNull();
  if (punto === null) return;
  await persona.tocarEn(punto);
  const ficha = pagina.locator("[data-ficha]:visible");
  await expect(ficha.first()).toBeVisible();
  // Abrirla solo aparta el mapa si el panel lateral taparía el punto (en la tableta puede pasar).
  const abierta = await vista(pagina);
  if (info.project.name !== "tableta") expect(abierta, "abrir la ficha no mueve el mapa").toBe(antes);
  await pagina.keyboard.press("Escape");
  await expect(pagina.locator("aside[data-ficha]:visible")).toHaveCount(0);
  expect(await vista(pagina), "cerrar la ficha no mueve el mapa").toBe(abierta);
  expect(errores).toEqual([]);
});
