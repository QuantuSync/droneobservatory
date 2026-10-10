// Panel «Avisos» en tres pasos, en 360 × 800, 768 × 1024, 1366 × 768 y 1920 × 1080: un solo botón
// «Suscribirme» con las instrucciones del dispositivo (Android, iPhone u ordenador), el QR solo en
// el ordenador, «Toda Europa» por defecto y el buscador de países. Abrir y cerrar no mueve el
// mapa; Escape cierra y devuelve el foco al botón; una sola barra de desplazamiento; lo elegido,
// en claro. Deja capturas en docs/capturas/avisos-sencillos (CAPTURAS para otra carpeta). Va
// contra producción por defecto; con BASE=<vista previa> y BYPASS=<clave>, contra una vista previa.
import { join } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const CAPTURAS = process.env.CAPTURAS ?? join(import.meta.dirname, "..", "..", "docs", "capturas", "avisos-sencillos");
const MAPA = "[data-mapa-listo=true]";
const AGENTES = {
  android: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36",
  iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
  ordenador: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
} as const;
const CASOS = [
  { nombre: "360x800-android", width: 360, height: 800, tactil: true, equipo: "android" },
  { nombre: "360x800-iphone", width: 360, height: 800, tactil: true, equipo: "iphone" },
  { nombre: "768x1024-android", width: 768, height: 1024, tactil: true, equipo: "android" },
  { nombre: "1366x768-ordenador", width: 1366, height: 768, tactil: false, equipo: "ordenador" },
  { nombre: "1920x1080-ordenador", width: 1920, height: 1080, tactil: false, equipo: "ordenador" },
] as const;

async function vista(pagina: Page): Promise<string> {
  const mapa = pagina.locator(MAPA);
  await pagina.waitForTimeout(1600);
  let anterior = "";
  for (let i = 0; i < 30; i += 1) {
    await pagina.waitForTimeout(400);
    const ahora = `${await mapa.getAttribute("data-centro")}|${await mapa.getAttribute("data-zoom")}`;
    if (ahora === anterior) break;
    anterior = ahora;
  }
  return anterior;
}

for (const caso of CASOS) {
  test(`avisos en tres pasos en ${caso.nombre}`, async ({ browser, baseURL, browserName }, info) => {
    test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
    const contexto = await browser.newContext({
      viewport: { width: caso.width, height: caso.height },
      hasTouch: caso.tactil,
      isMobile: caso.equipo !== "ordenador",
      userAgent: AGENTES[caso.equipo],
      ...(baseURL === undefined ? {} : { baseURL }),
      ...(process.env.BYPASS === undefined ? {} : { extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } }),
    });
    const pagina = await contexto.newPage();
    await pagina.goto("/", { waitUntil: "domcontentloaded" });
    await pagina.locator(MAPA).waitFor({ timeout: 60_000 });
    const inicial = await vista(pagina);

    const boton = pagina.locator("[data-boton-avisos]:visible");
    await boton.click();
    const panel = pagina.locator("[data-panel-avisos]:visible");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-dispositivo", caso.equipo);
    await expect(panel.locator(":scope > ol > li")).toHaveCount(3);
    await expect(panel.locator("[data-suscribirme]")).toHaveCount(1);
    await expect(panel.locator("[data-suscribirme]")).toHaveText("Suscribirme");
    // Toda Europa por defecto, en claro con el texto oscuro.
    const selector = panel.locator("[data-canal-elegido]");
    await expect(selector).toHaveValue("drones-europe");
    await expect.poll(() => selector.evaluate((e) => getComputedStyle(e).color)).toBe("rgb(6, 10, 18)");
    // El QR, solo en el ordenador.
    await expect(panel.locator("[data-qr-avisos]")).toHaveCount(caso.equipo === "ordenador" ? 1 : 0);
    const destino = await panel.locator("[data-suscribirme]").getAttribute("href");
    if (caso.equipo === "android") expect(destino).toMatch(/^ntfy:\/\/ntfy\.droneobservatory\.eu\/drones-europe/);
    if (caso.equipo === "iphone") expect(destino).toContain("apps.apple.com");
    if (caso.equipo === "ordenador") expect(destino).toBe("https://ntfy.droneobservatory.eu/drones-europe");
    // Una sola barra de desplazamiento.
    const desplazables = await panel.evaluate((p) => {
      const lista: string[] = [];
      for (let e: HTMLElement | null = p as HTMLElement; e !== null && e !== document.body; e = e.parentElement) {
        const estilo = getComputedStyle(e);
        if (/(auto|scroll)/.test(estilo.overflowY) && e.scrollHeight > e.clientHeight + 1) lista.push(e.className);
      }
      return lista;
    });
    expect(desplazables.length).toBeLessThanOrEqual(1);
    expect(await vista(pagina)).toBe(inicial);
    await pagina.screenshot({ path: join(CAPTURAS, `panel-${caso.nombre}.png`) });

    // El buscador: «polo» deja Polonia, y el botón (y el QR) siguen al canal.
    await panel.locator("[data-buscar-canal]").fill("polo");
    await expect(selector).toHaveValue("drones-poland");
    if (caso.equipo === "iphone") await expect(panel.locator("code").last()).toHaveText("drones-poland");
    else await expect(panel.locator("[data-suscribirme]")).toHaveAttribute("href", /drones-poland/);
    if (caso.equipo === "ordenador") await expect(panel.locator("[data-qr-avisos] img")).toHaveAttribute("src", "/avisos/qr/drones-poland.svg");
    await panel.locator("[data-suscribirme]").scrollIntoViewIfNeeded();
    await pagina.screenshot({ path: join(CAPTURAS, `panel-polonia-${caso.nombre}.png`) });

    // Con el teclado hasta el selector; Escape cierra, devuelve el foco y no mueve el mapa.
    await selector.focus();
    await pagina.keyboard.press("Escape");
    await expect(pagina.locator("[data-panel-avisos]:visible")).toHaveCount(0);
    expect(await boton.evaluate((e) => e === document.activeElement)).toBe(true);
    expect(await vista(pagina)).toBe(inicial);
    await contexto.close();
  });
}

for (const tamano of [
  { nombre: "360x800", width: 360, height: 800 },
  { nombre: "1366x768", width: 1366, height: 768 },
] as const) {
  test(`página de avisos en ${tamano.nombre}`, async ({ browser, baseURL, browserName }, info) => {
    test.skip(browserName !== "chromium" || info.project.name !== "escritorio");
    const contexto = await browser.newContext({
      viewport: { width: tamano.width, height: tamano.height },
      ...(baseURL === undefined ? {} : { baseURL }),
      ...(process.env.BYPASS === undefined ? {} : { extraHTTPHeaders: { "x-vercel-protection-bypass": process.env.BYPASS } }),
    });
    const pagina = await contexto.newPage();
    for (const ruta of ["/avisos", "/en/alerts"]) {
      await pagina.goto(ruta, { waitUntil: "load" });
      const orden = await pagina.evaluate(() => ["pasos", "dispositivos", "canales"].map((id) => document.getElementById(id)?.getBoundingClientRect().top ?? -1));
      expect(orden[0]).toBeGreaterThan(0);
      expect(orden[1]).toBeGreaterThan(orden[0] ?? 0);
      expect(orden[2]).toBeGreaterThan(orden[1] ?? 0);
      await expect(pagina.locator(".texto-canal img")).toHaveCount(43);
      expect(await pagina.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
    await pagina.goto("/avisos", { waitUntil: "load" });
    await pagina.screenshot({ path: join(CAPTURAS, `pagina-${tamano.nombre}.png`) });
    await pagina.locator("#canales").scrollIntoViewIfNeeded();
    await pagina.screenshot({ path: join(CAPTURAS, `pagina-canales-${tamano.nombre}.png`) });
    await contexto.close();
  });
}
