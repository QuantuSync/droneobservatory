// Las atribuciones aplicadas con la declaración oficial literal (recogida/declaraciones_oficiales.py),
// en un navegador real, en el teléfono (360, 390 y 412 px, con tacto) y en escritorio: son
// exactamente las aplicadas; cada una con su marcador con bandera en el mapa y su ficha completa
// (a quién, según quién, la cita literal con su enlace y la investigación en curso); la cifra de
// la cabecera y del menú; la leyenda y el filtro; y los que no se atribuyen, sin atribuir y con
// titulares que no señalan a nadie. Deja las capturas en docs/capturas (CAPTURAS para otra
// carpeta). Va contra producción por defecto; con BASE=http://localhost:4173, contra el servidor
// local, reenviando el almacén público, que solo admite el dominio propio.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import type { Resumen } from "../src/datos/tipos.ts";
import { textos } from "../src/i18n/index.ts";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas");
const MAPA_LISTO = "[data-mapa-listo=true]";
const MS_DE_ASENTAMIENTO = 2500;
const TELEFONOS = [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "390x844", width: 390, height: 844 },
  { nombre: "412x915", width: 412, height: 915 },
];
const ESCRITORIO = { nombre: "escritorio", width: 1440, height: 900 };
const ES = textos("es");

/** Las atribuciones aplicadas, con su autoridad escrita, su cita y su enlace. */
const APLICADAS = [
  {
    id: "EODI-2026-00134",
    autoridad: "el Gobierno federal alemán (Bundesregierung)",
    cita: "Die Bundesregierung weist die Verantwortung für den versuchten Anschlag auf den Flughafen Leipzig/Halle vom 4. August 2026 eindeutig Russland zu.",
    enlace: "https://www.bundesregierung.de/breg-de/service/fragen-und-anworten/reaktion-angriff-leipzig-2451522",
    investigacion: "strafrechtlichen Ermittlungen",
  },
  {
    id: "EODI-2026-00245",
    autoridad: "las Fuerzas Armadas de Suecia (Försvarsmakten)",
    cita: "Nu kan Försvarsmakten bekräfta att en rysk drönare har genomfört en olovlig flygning.",
    enlace: "https://www.forsvarsmakten.se/kontakt/press-och-media/forsvarsmakten-bekraftar-observation-av-rysk/",
  },
  {
    id: "EODI-2025-00295",
    autoridad: "la Cancillería del primer ministro de Polonia (Kancelaria Prezesa Rady Ministrów)",
    cita: "W środę nad ranem polska przestrzeń powietrzna została naruszona przez rosyjskie drony.",
    enlace: "https://www.gov.pl/web/premier/premier-doszlo-do-naruszenia-polskiej-przestrzeni-powietrznej---procedury-zadzialaly",
  },
  {
    id: "EODI-2026-00211",
    autoridad: "el presidente de Rumanía (Președintele României)",
    cita: "Declar, cu toată fermitatea, că responsabilitatea integrală pentru acest incident îi aparține Federației Ruse.",
    enlace:
      "https://www.presidency.ro/ro/media/comunicate-de-presa/declaratia-de-presa-a-presedintelui-romaniei-nicusor-dan-in-urma-incidentului-grav-cauzat-de-o-drona-ruseasca-in-galati",
    investigacion: "anchetă completă",
  },
];
/** Constanza, Buzău, Lituania y Wunstorf: sin atribuir. */
const SIN_ATRIBUIR = ["EODI-2026-00152", "EODI-2026-00125", "EODI-2026-00090", "EODI-2026-00276"];
const SENALA = /\b(rus[oa]s?|russian|ucranian[oa]s?|ukrainian|controlad[oa]|controlled|respaldad[oa]|backed)\b/i;

async function preparar(contexto: BrowserContext, baseURL: string | undefined) {
  if (baseURL?.includes("localhost") !== true) return;
  await contexto.route(/your-objectstorage\.com|tiles\.droneobservatory\.eu/, async (ruta) => {
    const respuesta = await ruta.fetch();
    await ruta.fulfill({ response: respuesta, headers: { ...respuesta.headers(), "access-control-allow-origin": "*" } });
  });
}

async function capturar(pagina: Page, nombre: string) {
  await pagina.waitForTimeout(MS_DE_ASENTAMIENTO);
  await pagina.screenshot({ path: join(CAPTURAS, `atribuciones-${nombre}.png`) });
}

async function entrar(pagina: Page, ruta: string) {
  await pagina.addInitScript(() => window.localStorage.removeItem("eodi.ultima-visita"));
  await pagina.goto(ruta);
  await pagina.waitForSelector(MAPA_LISTO);
}

async function resumen(pagina: Page): Promise<Resumen> {
  return (await (await pagina.request.get("/datos/resumen.json")).json()) as Resumen;
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
    test.afterEach(async ({ context }) => {
      await context.unrouteAll({ behavior: "ignoreErrors" });
    });

    test(`${nombre}: los atribuidos son exactamente los aplicados, con la ficha completa`, async ({
      page,
      context,
      baseURL,
    }) => {
      await preparar(context, baseURL);
      const datos = await resumen(page);
      const atribuidos = datos.incidentes.filter((i) => i.estado === "atribuido").map((i) => i.id);
      expect(atribuidos.toSorted()).toEqual(APLICADAS.map((a) => a.id).toSorted());
      for (const aplicada of APLICADAS) {
        await entrar(page, `/${aplicada.id}`);
        const ficha = page.getByRole("complementary", { name: new RegExp(aplicada.id) });
        await expect(ficha).toBeVisible();
        // Junto al estado, el marcador con la bandera rusa y a quién se atribuye.
        const marca = ficha.locator("[data-estado-atribuido] svg[data-atribuido]");
        await expect(marca).toHaveAttribute("data-atribuido", "RU");
        await expect(ficha.locator("[data-estado-atribuido]")).toContainText("Rusia");
        // A quién, según quién (traducida, con el original), la cita literal y su enlace.
        await expect(ficha).toContainText(ES.ficha.atribuidoA("Rusia", aplicada.autoridad));
        const cita = ficha.locator("[data-cita-atribucion]");
        await expect(cita).toHaveText(`«${aplicada.cita}»`);
        await expect(cita.locator("xpath=..").locator(`a[href="${aplicada.enlace}"]`)).toHaveCount(1);
        if (aplicada.investigacion !== undefined) {
          await expect(ficha.locator("[data-investigacion]")).toContainText(aplicada.investigacion);
        }
        await cita.scrollIntoViewIfNeeded();
        await capturar(page, `ficha-${aplicada.id}-${nombre}`);
      }
    });

    test(`${nombre}: marcadores en el mapa, cifra, leyenda y filtro`, async ({ page, context, baseURL }) => {
      await preparar(context, baseURL);
      await entrar(page, "/");
      // El marcador de los atribuidos está registrado en el mapa (la bandera se le pone al llegar).
      await expect(page.locator(MAPA_LISTO)).toHaveAttribute("data-iconos", /atribuido-/);
      await capturar(page, `mapa-${nombre}`);
      // Lejos, los que se pisan son un solo marcador con su número.
      await page.locator(".maplibregl-canvas").focus();
      for (let i = 0; i < 2; i += 1) {
        await page.keyboard.press("Minus");
        await page.waitForTimeout(700);
      }
      await capturar(page, `mapa-lejos-${nombre}`);
      // La cifra de atribuidos, en la cabecera o en el menú.
      if (telefono) await page.getByRole("banner").getByRole("button", { name: "Menú" }).click();
      const cifra = page.locator("[data-marca-cifra]").filter({ visible: true }).first().locator("xpath=..");
      await expect(cifra).toHaveText(new RegExp(`^${APLICADAS.length}`));
      await capturar(page, `cifras-${nombre}`);
      // Leyenda (en el teléfono, desde el menú).
      await page.getByRole("button", { name: "Ayuda", exact: true }).click();
      const ayuda = page.getByRole("dialog", { name: "Cómo leer el mapa" });
      await expect(ayuda.locator("[data-leyenda-atribuido=estado]")).toHaveText(ES.atribucion.leyendaEstado);
      await ayuda.locator("[data-leyenda-estados]").scrollIntoViewIfNeeded();
      await capturar(page, `leyenda-${nombre}`);
      await ayuda.getByRole("button", { name: "Cerrar la ayuda" }).click();
      if (telefono && (await page.getByRole("dialog", { name: "Menú" }).isVisible())) {
        await page.getByRole("dialog", { name: "Menú" }).getByRole("button", { name: "Cerrar el menú" }).click();
      }
      // Filtro por estado.
      await page.getByRole("button", { name: /^Abrir los filtros/ }).filter({ visible: true }).click();
      const filtros = page.getByRole("group", { name: "Filtros" }).filter({ visible: true });
      await expect(filtros.getByRole("button", { name: "Atribuido" }).locator("svg[data-atribuido]")).toBeVisible();
      await capturar(page, `filtros-${nombre}`);
    });

    test(`${nombre}: Constanza, Buzău, Lituania y Wunstorf, sin atribuir y sin señalar a nadie`, async ({
      page,
      context,
      baseURL,
    }) => {
      await preparar(context, baseURL);
      const datos = await resumen(page);
      for (const id of SIN_ATRIBUIR) {
        const incidente = datos.incidentes.find((i) => i.id === id);
        if (incidente === undefined) continue;
        expect(incidente.estado).not.toBe("atribuido");
        expect(incidente.titulo.es).not.toMatch(SENALA);
        expect(incidente.titulo.en).not.toMatch(SENALA);
      }
      // Wunstorf, con la investigación de la fiscalía federal.
      await entrar(page, "/EODI-2026-00276");
      const ficha = page.getByRole("complementary", { name: /EODI-2026-00276/ });
      await expect(ficha.locator("[data-estado-atribuido]")).toHaveCount(0);
      await expect(ficha.locator("[data-investigacion]")).toContainText("Bundesanwaltschaft");
      await capturar(page, `wunstorf-${nombre}`);
    });
  });
}
