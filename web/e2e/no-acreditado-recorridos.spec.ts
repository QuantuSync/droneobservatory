// La presencia de dron «no acreditada», como la ve una persona: en un Android (Chromium, Pixel 7),
// un iPhone (WebKit, iPhone 14), una tableta táctil y el escritorio (Chromium y WebKit), en español
// y en inglés.
//
// - Copenhague (EODI-2025-00154): la ficha dice «Dron no acreditado» y la secuencia entera, cada
//   paso con su fecha, quién lo declara y el enlace a su fuente; el estado sigue «Confirmado» y el
//   efecto (el cierre y los desvíos), a la vista; su marca es el círculo morado.
// - La leyenda de la ayuda tiene el círculo morado «No acreditado» con lo que quiere decir.
// - La nota de qué es «confirmado» se ve junto al mapa en el escritorio y la tableta (sin pisar el
//   zoom, las atribuciones ni los botones del mapa) y, en el teléfono, en el menú con las cifras
//   (nunca sobre el mapa); tocarla, abrir la ayuda y cerrarla no mueven el mapa.
// - Las cifras dicen «confirmados por una autoridad» y no cuentan a Copenhague.
//
// Los datos publicados no traen aún el valor nuevo: la prueba lo pone en Copenhague al vuelo, en
// /datos/resumen.json y en su ficha (/datos/incidentes/EODI-2025-00154.json), con el historial
// del contrato de datos; si un día Copenhague no está o le falta algo, lo completa. Proyectos
// android, iphone, tableta, escritorio-chromium y escritorio-webkit (playwright.config.ts). Va
// contra producción por defecto; con BASE, contra otra dirección. Capturas en CAPTURAS.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Locator, Page } from "@playwright/test";

import { cifras } from "../src/datos/derivar.ts";
import type { Fuente, IncidenteDetalle, IncidenteResumen, PasoPresencia, Resumen } from "../src/datos/tipos.ts";
import { textos } from "../src/i18n/index.ts";

const MAPA = "[data-mapa-listo=true]";
const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "no-acreditado");
const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];
const COPENHAGUE = "EODI-2025-00154";
const MORADO = "#e81cf0";
const POLITI = { es: "la policía de Copenhague", en: "Copenhagen Police" };

/** Las dos fuentes que cita el historial; si la ficha publicada no las trae, se añaden. */
const FUENTES: Fuente[] = [
  {
    id: "gdelt-36b6a2a29b6bc102-declaracion-1",
    enlace: "https://www.kristeligt-dagblad.dk/",
    medio: "Københavns Politi (declaración oficial citada en kristeligt-dagblad.dk)",
    fecha: { valor: "2025-09-23T10:00Z", precision: "aproximada" },
    idioma: "da",
    fiabilidad: "B",
    credibilidad: 2,
    frase_origen: "Københavns Politi bekræfter droner over lufthavnen.",
    replicas: 0,
  },
  {
    id: "detalle-d5bf7ff3b226254a",
    enlace: "https://politi.dk/koebenhavns-politi",
    medio: "Københavns Politi",
    fecha: { valor: "2026-06-25T00:00Z", precision: "dia" },
    idioma: "da",
    fiabilidad: "A",
    credibilidad: 2,
    frase_origen: "Københavns Politi kan hverken be- eller afkræfte, at der var droner.",
    replicas: 0,
  },
];

const HISTORIAL: PasoPresencia[] = [
  { valor: "confirmada", fecha: { valor: "2025-09-23T00:00Z", precision: "dia" }, fuente_id: FUENTES[0]?.id ?? "", quien: POLITI },
  {
    valor: "no_acreditada",
    fecha: { valor: "2026-06-25T00:00Z", precision: "dia" },
    fuente_id: FUENTES[1]?.id ?? "",
    quien: POLITI,
    motivo: {
      es: "tras la investigación: no puede confirmar ni descartar que hubiera drones",
      en: "after the investigation: it can neither confirm nor rule out that there were drones",
    },
  },
];

const PASOS = {
  es: ["Confirmado el 23/09/2025 por la policía de Copenhague", "No acreditado el 25/06/2026 por la policía de Copenhague, tras la investigación"],
  en: ["Confirmed on 23/09/2025 by Copenhagen Police", "Not substantiated on 25/06/2026 by Copenhagen Police, after the investigation"],
};

/** La ficha de Copenhague por si un día no se publica: lo mínimo que valida. */
const FICHA_DE_RESERVA: IncidenteDetalle = {
  id: COPENHAGUE,
  tipo: "interrupcion_aeroportuaria",
  estado: {
    actual: "confirmado",
    historial: [{ estado: "confirmado", fecha: { valor: "2025-09-25T00:00Z", precision: "dia" }, fuente_id: FUENTES[1]?.id ?? "" }],
  },
  titulo: { es: "Drones cierran el aeropuerto de Copenhague", en: "Drones close Copenhagen Airport" },
  presencia_dron: "confirmada",
  tiempo: { inicio: { valor: "2025-09-22T20:00Z", precision: "hora" } },
  lugar: { radio_km: 5, pais: "DK" },
  objetivo: { categoria: "aeropuerto", nombre: "Københavns Lufthavn", oaci: "EKCH" },
  consecuencias: { cierre: { valor: "si", minutos: { min: 240, max: 240 } }, vuelos_desviados: { min: 35, max: 35 } },
  fuentes: [...FUENTES],
  control: { ultima_actualizacion: { valor: "2026-10-14T06:17Z", precision: "minuto" } },
  lon: 12.63793,
  lat: 55.60927,
};

const RESUMEN_DE_RESERVA: IncidenteResumen = {
  id: COPENHAGUE,
  punto: { lon: 12.63793, lat: 55.60927, radio_km: 5 },
  imprecisa: null,
  aproximado: null,
  tipo: "interrupcion_aeroportuaria",
  estado: "confirmado",
  presencia: "confirmada",
  titulo: FICHA_DE_RESERVA.titulo,
  dia: 20353,
  inicio: Date.parse("2025-09-22T20:00Z"),
  pais: "DK",
  objetivo: "Københavns Lufthavn",
  episodio: null,
  foco: false,
  atribucion: null,
  zona: "interior",
  dron: [],
};

function ruta(idioma: "es" | "en", id = ""): string {
  return idioma === "en" ? `/en/${id}` : `/${id}`;
}

/** Copenhague con la presencia no acreditada y su historial, en el resumen y en su ficha. */
async function conNoAcreditado(contexto: BrowserContext): Promise<{ resumen: () => Resumen | null; ficha: () => IncidenteDetalle | null }> {
  let resumen: Resumen | null = null;
  let ficha: IncidenteDetalle | null = null;
  await contexto.route(/\/datos\/resumen\.json(\?.*)?$/, async (pedido) => {
    const respuesta = await pedido.fetch();
    const datos = (await respuesta.json()) as Resumen;
    const incidentes = datos.incidentes.some((i) => i.id === COPENHAGUE) ? datos.incidentes : [...datos.incidentes, RESUMEN_DE_RESERVA];
    resumen = {
      ...datos,
      incidentes: incidentes.map((i): IncidenteResumen => (i.id === COPENHAGUE ? { ...i, estado: "confirmado", presencia: "no_acreditada" } : i)),
    };
    await pedido.fulfill({ status: 200, contentType: "application/json", json: resumen });
  });
  await contexto.route(new RegExp(`/datos/incidentes/${COPENHAGUE}\\.json(\\?.*)?$`), async (pedido) => {
    const respuesta = await pedido.fetch();
    const publicada = respuesta.ok() ? ((await respuesta.json()) as IncidenteDetalle) : FICHA_DE_RESERVA;
    const fuentes = [...publicada.fuentes, ...FUENTES.filter((f) => !publicada.fuentes.some((p) => p.id === f.id))];
    ficha = {
      ...publicada,
      estado: publicada.estado.actual === "confirmado" ? publicada.estado : FICHA_DE_RESERVA.estado,
      presencia_dron: "no_acreditada",
      presencia_historial: HISTORIAL,
      fuentes,
      consecuencias: publicada.consecuencias ?? FICHA_DE_RESERVA.consecuencias,
    } as IncidenteDetalle;
    await pedido.fulfill({ status: 200, contentType: "application/json", json: ficha });
  });
  return { resumen: () => resumen, ficha: () => ficha };
}

function vigilar(pagina: Page): string[] {
  const errores: string[] = [];
  pagina.on("pageerror", (e) => {
    if (/access control checks/.test(e.message)) return;
    errores.push(`excepción: ${e.message}`);
  });
  return errores;
}

/** La vista cuando el mapa deja de moverse. */
async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  let anterior = "";
  for (let i = 0; i < 40; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior && !ahora.includes("null")) return ahora;
    anterior = ahora;
  }
  return anterior;
}

/** Toca el elemento con el dedo o lo pulsa con el ratón, en su centro. */
async function tocar(pagina: Page, elemento: Locator, tactil: boolean) {
  await elemento.scrollIntoViewIfNeeded();
  const caja = await elemento.boundingBox();
  if (caja === null) throw new Error("elemento sin caja");
  if (tactil) await pagina.touchscreen.tap(caja.x + caja.width / 2, caja.y + caja.height / 2);
  else await pagina.mouse.click(caja.x + caja.width / 2, caja.y + caja.height / 2);
}

function seSolapan(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

/** Disposición de teléfono: la barra con el botón del menú (por debajo de 768 px). */
async function esTelefono(pagina: Page): Promise<boolean> {
  return pagina.locator("[data-boton-menu]").isVisible();
}

if (process.env.ANCHO !== undefined && process.env.ALTO !== undefined) {
  test.use({ viewport: { width: Number(process.env.ANCHO), height: Number(process.env.ALTO) } });
}

test.describe("Presencia de dron no acreditada, como una persona", () => {
  test.afterEach(async ({ context }) => {
    await context.unrouteAll({ behavior: "ignoreErrors" });
  });

  for (const idioma of ["es", "en"] as const) {
    const t = textos(idioma);

    test(`Copenhague: la secuencia de la presencia con sus fuentes (${idioma})`, async ({ page: pagina, context: contexto }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(180_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const datos = await conNoAcreditado(contexto);
      await pagina.goto(ruta(idioma, COPENHAGUE), { waitUntil: "domcontentloaded" });
      await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
      const ficha = pagina.locator("[data-ficha] article").first();
      await expect(ficha).toBeVisible({ timeout: 30_000 });
      // En el teléfono, la hoja se sube con un toque en su asa.
      const asa = pagina.locator("aside[data-altura] button[data-arrastre]").first();
      if (tactil && (await asa.count()) > 0 && (await asa.isVisible())) await tocar(pagina, asa, tactil);
      // La marca de la ficha es el círculo morado; el estado sigue «Confirmado».
      await expect(ficha.locator("p svg[data-circulo=no_acreditado] circle").first()).toHaveAttribute("fill", MORADO);
      await expect(ficha).toContainText(t.estado.confirmado);
      const presencia = ficha.locator("[data-presencia]");
      await presencia.scrollIntoViewIfNeeded();
      await expect(presencia).toHaveText(t.presencia.no_acreditada);
      const pasos = ficha.locator("[data-presencia-historial] li");
      await expect(pasos).toHaveCount(2);
      const publicada = datos.ficha();
      expect(publicada).not.toBeNull();
      const enlaces = HISTORIAL.map((paso) => publicada?.fuentes.find((f) => f.id === paso.fuente_id)?.enlace);
      for (const [i, texto] of PASOS[idioma].entries()) {
        const paso = pasos.nth(i);
        await expect(paso).toContainText(texto);
        // Cada paso enlaza a su fuente (o a su copia archivada si el original cayó).
        const enlace = paso.locator("a[href]").first();
        await expect(enlace).toBeVisible();
        const href = await enlace.getAttribute("href");
        expect(href === enlaces[i] || (href ?? "").startsWith("https://web.archive.org/"), `${href} → ${enlaces[i]}`).toBe(true);
      }
      // El efecto sigue a la vista.
      await expect(ficha).toContainText(t.ficha.efecto);
      await pagina.screenshot({ path: join(CAPTURAS, `ficha-${idioma}-${info.project.name}.png`) });
      // Cerrar la ficha no mueve el mapa.
      const antes = await vista(pagina);
      await tocar(pagina, pagina.getByRole("button", { name: t.ficha.cerrar }).first(), tactil);
      await expect(pagina.locator("[data-ficha] article")).toHaveCount(0);
      expect(await vista(pagina)).toBe(antes);
      expect(errores).toEqual([]);
    });

    test(`leyenda morada, nota del mapa y cifras «confirmados por una autoridad» (${idioma})`, async ({ page: pagina, context: contexto }, info) => {
      test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
      test.setTimeout(180_000);
      const errores = vigilar(pagina);
      const tactil = info.project.use.hasTouch === true;
      const datos = await conNoAcreditado(contexto);
      await pagina.addInitScript(() => window.localStorage.removeItem("eodi.ultima-visita"));
      await pagina.goto(ruta(idioma), { waitUntil: "domcontentloaded" });
      await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
      await expect.poll(() => datos.resumen() !== null, { timeout: 30_000 }).toBe(true);
      const esperado = cifras(datos.resumen()?.incidentes ?? []);
      const telefono = await esTelefono(pagina);
      const inicial = await vista(pagina);

      if (telefono) {
        // Sobre el mapa no hay nota: no tapa nada.
        await expect(pagina.locator("[data-nota-mapa]:visible")).toHaveCount(0);
        await tocar(pagina, pagina.locator("[data-boton-menu]"), tactil);
        const menu = pagina.locator("dialog[open]");
        await expect(menu).toBeVisible();
        const cifra = menu.locator("[data-contador=confirmados]");
        await expect(cifra.locator("dt")).toHaveText(t.marcador.confirmados);
        await expect(cifra).toHaveAttribute("data-valor", String(esperado.confirmados));
        const nota = menu.locator("[data-nota-mapa]");
        await expect(nota).toHaveText(t.mapa.nota);
        await expect(nota).toBeVisible();
        // El rótulo largo cabe: ni la cifra ni la nota se salen del menú.
        const caja = await menu.boundingBox();
        for (const elemento of [cifra, nota]) {
          const propia = await elemento.boundingBox();
          expect(propia !== null && caja !== null && propia.x >= caja.x - 1 && propia.x + propia.width <= caja.x + caja.width + 1).toBe(true);
        }
        await pagina.screenshot({ path: join(CAPTURAS, `menu-${idioma}-${info.project.name}.png`) });
        // La ayuda, desde el menú.
        await tocar(pagina, menu.getByRole("button", { name: t.controles.ayuda, exact: true }), tactil);
      } else {
        const cifra = pagina.locator("header [data-contador=confirmados]");
        await expect(cifra.locator("dt")).toHaveText(t.marcador.confirmados);
        await expect(cifra).toHaveAttribute("data-valor", String(esperado.confirmados));
        // La nota, junto al mapa, sin pisar el zoom, las atribuciones ni los botones del mapa.
        const nota = pagina.locator("[data-nota-mapa]:visible").first();
        await expect(nota).toHaveText(t.mapa.nota);
        const propia = await nota.boundingBox();
        expect(propia).not.toBeNull();
        const controles = [
          pagina.getByRole("group", { name: t.controles.zoom }),
          pagina.getByLabel(t.firma.atribuciones),
          pagina.locator(".boton-mapa:visible"),
        ];
        for (const control of controles) {
          for (const elemento of await control.all()) {
            const otra = await elemento.boundingBox();
            if (otra !== null && propia !== null) expect(seSolapan(propia, otra), (await elemento.textContent()) ?? "").toBe(false);
          }
        }
        // Tocarla no mueve el mapa.
        await tocar(pagina, nota, tactil);
        expect(await vista(pagina)).toBe(inicial);
        await pagina.screenshot({ path: join(CAPTURAS, `nota-${idioma}-${info.project.name}.png`) });
        await tocar(pagina, pagina.locator("header").getByRole("button", { name: t.controles.ayuda, exact: true }), tactil);
      }

      // La leyenda: el círculo morado «No acreditado» con lo que quiere decir, y la nota.
      const ayuda = pagina.getByRole("dialog", { name: t.ayuda.titulo });
      await expect(ayuda).toBeVisible();
      const entrada = ayuda.locator("[data-leyenda-no-acreditado]");
      await entrada.scrollIntoViewIfNeeded();
      await expect(entrada).toBeVisible();
      await expect(entrada).toContainText(t.noAcreditado.etiqueta);
      await expect(entrada).toContainText(t.noAcreditado.leyenda);
      await expect(entrada.locator("svg[data-circulo=no_acreditado] circle")).toHaveAttribute("fill", MORADO);
      await expect(ayuda.locator("[data-nota-mapa]")).toHaveText(t.mapa.nota);
      await pagina.screenshot({ path: join(CAPTURAS, `leyenda-${idioma}-${info.project.name}.png`) });
      // Cerrar la ayuda no mueve el mapa.
      await tocar(pagina, ayuda.getByRole("button", { name: t.ayuda.cerrar }), tactil);
      await expect(ayuda).toBeHidden();
      expect(await vista(pagina)).toBe(inicial);
      expect(errores).toEqual([]);
    });
  }
});
