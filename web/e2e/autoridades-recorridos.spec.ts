// Las autoridades, siempre en el idioma de la página (docs/nombres_lugar.md), como lo ve una
// persona en un Android, un iPhone, una tableta y el escritorio (Chromium y WebKit): la ficha que
// el 14 de octubre de 2026 decía en español «Declaración de Defense Ministry of Romania».
//
// Proyectos android, iphone, tableta, escritorio-chromium y escritorio-webkit. Va contra producción
// por defecto; con BASE, contra otra dirección (y con BYPASS, la clave de las vistas previas).
import { expect, test } from "./base.ts";
import { destino, publicados } from "./publicados.ts";

const MAPA = "[data-mapa-listo=true]";
const FICHA = process.env.FICHA ?? "EODI-2026-00532";
const PROYECTOS = ["android", "iphone", "tableta", "escritorio-chromium", "escritorio-webkit"];
const ESPERADO = {
  es: { si: "Declaración del Ministerio de Defensa Nacional de Rumanía", no: "Defense Ministry of Romania" },
  en: { si: "Statement by the Romanian Ministry of National Defence", no: "Ministerul Apărării Naționale (" },
};

if (process.env.BYPASS !== undefined) {
  test.use({ extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } });
}

for (const idioma of ["es", "en"] as const) {
  test(`autoridades de la ficha en el idioma de la página (${idioma})`, async ({ page: pagina }, info) => {
    test.skip(!PROYECTOS.includes(info.project.name), "en los dispositivos de los recorridos");
    test.setTimeout(180_000);
    const errores: string[] = [];
    pagina.on("pageerror", (e) => errores.push(e.message));
    // La ficha que queda si el repaso la unió a otra (e2e/publicados.ts).
    const id = destino(await publicados(pagina.request), FICHA) ?? FICHA;
    await pagina.goto(idioma === "en" ? `/en/${id}` : `/${id}`, { waitUntil: "domcontentloaded" });
    await expect(pagina.locator(MAPA)).toBeAttached({ timeout: 60_000 });
    const ficha = pagina.locator("[data-ficha] article").first();
    await expect(ficha).toBeVisible({ timeout: 30_000 });
    // Las fuentes, más abajo: se llega desplazando la ficha como lo haría una persona.
    const declaracion = ficha.getByRole("link", { name: ESPERADO[idioma].si }).first();
    await declaracion.scrollIntoViewIfNeeded();
    await expect(declaracion).toBeVisible();
    const texto = (await ficha.textContent()) ?? "";
    expect(texto).not.toContain(ESPERADO[idioma].no);
    expect(errores).toEqual([]);
  });
}
