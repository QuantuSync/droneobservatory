// Comprobación en producción de la revisión del contenido (docs/informe_revision_contenido.md),
// en el teléfono (360, 390 y 412 px, con tacto) y en escritorio:
// 1. cinco incidentes con el titular cambiado: el titular, el estado y las citas de su ficha dicen
//    lo mismo que los datos publicados, y una cita nombra lo que afirma el titular;
// 2. la capa de Ucrania tiene impactos en Odesa y sus fichas se abren con su fuente;
// 3. Polonia (EODI-2025-00295): punto en el mapa, marcador de atribuido y ficha con el lugar
//    según la fiscalía y los demás lugares.
// Deja las capturas en docs/capturas (CAPTURAS para otra carpeta). Va contra producción por
// defecto; con BASE=http://localhost:4173, contra el servidor local.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const TELEFONOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "390x844", width: 390, height: 844 },
  { nombre: "412x915", width: 412, height: 915 },
];
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
/** Cinco de los titulares cambiados, con la palabra que tiene que nombrar alguna cita. */
const CAMBIADOS = [
  { id: "EODI-2025-00094", nombra: "Bronojsund" },
  { id: "EODI-2025-00140", nombra: "Arna" },
  { id: "EODI-2025-00059", nombra: "Sandefjord" },
  { id: "EODI-2026-00083", nombra: "Split" },
  { id: "EODI-2026-00166", nombra: "Budapest" },
];
const POLONIA = "EODI-2025-00295";
const ESTADOS: Record<string, string> = {
  notificado: "Notificado",
  confirmado: "Confirmado",
  atribuido: "Confirmado",
  desmentido: "Desmentido",
};

interface Publicado {
  id: string;
  titulo: { es: string; en: string };
  estado: { actual: string };
  fuentes: { frase_origen: string; enlace: string }[];
  lugar: { localidad?: string; fuente_punto?: string; otros_lugares?: { nombre: string }[] };
}
interface Impacto {
  id: string;
  region: string;
  sentido: string;
  parte_diario?: boolean;
  lugar: { nombre: string; punto: { lat: number; lon: number } };
  fuentes: { enlace: string }[];
}
type MapaDePruebas = {
  jumpTo: (o: { center: [number, number]; zoom: number }) => void;
  project: (p: [number, number]) => { x: number; y: number };
  once: (e: string, f: () => void) => void;
};

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com|tiles\.droneobservatory\.eu/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(2500);
  await pagina.screenshot({ path: join(CAPTURAS, `revision-${nombre}.png`) });
}

async function publicados(pagina: Page): Promise<Map<string, Publicado>> {
  const mapa = (await (await pagina.request.get("/datos/incidentes.geojson")).json()) as {
    features: { id: string; properties: Publicado }[];
  };
  const sin = (await (await pagina.request.get("/datos/incidentes_sin_ubicacion.json")).json()) as {
    incidentes: Publicado[];
  };
  const todos = [...mapa.features.map((f) => ({ ...f.properties, id: f.id })), ...sin.incidentes];
  return new Map(todos.map((i) => [i.id, i]));
}

for (const tamano of [...TELEFONOS, ESCRITORIO]) {
  const telefono = tamano !== ESCRITORIO;
  const nombre = tamano.nombre;

  test.describe(nombre, () => {
    test.use({
      viewport: { width: tamano.width, height: tamano.height },
      isMobile: telefono,
      hasTouch: telefono,
      deviceScaleFactor: telefono ? 2 : 1,
    });
    test.beforeEach(({ browserName }, info) => {
      test.skip(browserName !== "chromium" || info.project.name !== (telefono ? "movil" : "escritorio"));
    });

    test(`${nombre}: titulares cambiados, con su estado y su cita`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      const datos = await publicados(page);
      for (const { id, nombra } of CAMBIADOS) {
        const incidente = datos.get(id);
        expect(incidente, `${id} publicado`).toBeDefined();
        if (incidente === undefined) continue;
        expect(incidente.fuentes.some((f) => f.frase_origen.includes(nombra))).toBe(true);
        await page.goto(`/${id}`);
        await page.waitForSelector(MAPA_LISTO);
        const ficha = page.getByRole("complementary", { name: new RegExp(id) });
        await expect(ficha).toBeVisible();
        await expect(ficha).toContainText(incidente.titulo.es);
        await expect(ficha).toContainText(ESTADOS[incidente.estado.actual] ?? "");
        const cita = incidente.fuentes.find((f) => f.frase_origen.includes(nombra));
        if (cita !== undefined) {
          await ficha.getByText(/Qué dice cada fuente|Fuentes/).first().click({ trial: false }).catch(() => undefined);
          await expect(ficha).toContainText(cita.frase_origen.slice(0, 40));
          await ficha.getByText(cita.frase_origen.slice(0, 40)).first().scrollIntoViewIfNeeded();
        }
        await capturar(page, `titular-${id}-${nombre}`);
      }
    });

    test(`${nombre}: Odesa tiene impactos y su ficha se abre con su fuente`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      const ucrania = (await (await page.request.get("/datos/ucrania.json")).json()) as { impactos: Impacto[] };
      const odesa = ucrania.impactos.filter(
        (i) => i.region === "UA-51" && i.sentido === "RU_UA" && i.parte_diario !== true,
      );
      expect(odesa.length).toBeGreaterThan(0);
      const impacto = odesa.toSorted((a, b) => a.id.localeCompare(b.id)).at(-1);
      if (impacto === undefined) return;
      await page.goto("/");
      await page.waitForSelector(MAPA_LISTO);
      await page.locator(".maplibregl-canvas").focus();
      await page.keyboard.press("2");
      const { lat, lon } = impacto.lugar.punto;
      await page.evaluate(
        ([la, lo]) =>
          new Promise<void>((listo) => {
            const elemento = document.querySelector(".maplibregl-map") as HTMLElement & { mapaDePruebas?: MapaDePruebas };
            const mapa = elemento.mapaDePruebas;
            if (mapa === undefined) throw new Error("sin mapa de pruebas");
            mapa.once("idle", () => listo());
            mapa.jumpTo({ center: [lo, la], zoom: 12 });
          }),
        [lat, lon] as const,
      );
      await page.waitForTimeout(1500);
      await capturar(page, `odesa-mapa-${nombre}`);
      const punto = await page.evaluate(
        ([la, lo]) => {
          const elemento = document.querySelector(".maplibregl-map") as HTMLElement & { mapaDePruebas?: MapaDePruebas };
          const caja = elemento.getBoundingClientRect();
          const p = elemento.mapaDePruebas?.project([lo, la]) ?? { x: 0, y: 0 };
          return { x: caja.left + p.x, y: caja.top + p.y };
        },
        [lat, lon] as const,
      );
      if (telefono) await page.touchscreen.tap(punto.x, punto.y);
      else await page.mouse.click(punto.x, punto.y);
      await page.waitForTimeout(1500);
      // Un punto puede tener varios impactos: se abre la lista o la ficha; se busca la de Odesa.
      const lista = page.getByRole("button", { name: new RegExp(impacto.lugar.nombre) }).first();
      if (await lista.isVisible().catch(() => false)) await lista.click();
      await expect(page.getByText(/EODI-IG-\d{4}-\d{5}/).first()).toBeVisible();
      await expect(page.locator(`a[href="${impacto.fuentes[0]?.enlace ?? ""}"]`).first()).toBeAttached();
      await capturar(page, `odesa-ficha-${nombre}`);
    });

    test(`${nombre}: Polonia en el mapa con su marcador y su ficha`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      const datos = await publicados(page);
      const polonia = datos.get(POLONIA);
      expect(polonia?.lugar.fuente_punto).toBeTruthy();
      expect((polonia?.lugar.otros_lugares ?? []).length).toBeGreaterThan(5);
      await page.goto(`/${POLONIA}`);
      await page.waitForSelector(MAPA_LISTO);
      const ficha = page.getByRole("complementary", { name: new RegExp(POLONIA) });
      await expect(ficha).toBeVisible();
      await expect(ficha.locator("[data-estado-atribuido] svg[data-atribuido]")).toHaveAttribute("data-atribuido", "RU");
      await expect(ficha).toContainText("Wyryki");
      await expect(ficha).toContainText("Cześniki");
      await capturar(page, `polonia-ficha-${nombre}`);
      if (telefono) {
        await page.getByRole("button", { name: "Cerrar la ficha" }).first().click();
      }
      await capturar(page, `polonia-mapa-${nombre}`);
    });
  });
}
