import { defineConfig, devices } from "@playwright/test";

import { SUFIJO_AGENTE } from "./e2e/agente.ts";

// Comprobación en un navegador real, en escritorio y en móvil. Por defecto va contra
// producción; con BASE=http://localhost:4173 va contra el servidor local (npm run servir).
const BASE = process.env.BASE ?? "https://droneobservatory.eu";
// La clave de acceso de las vistas previas protegidas de Vercel (en la CI, el secreto
// EODI_VERCEL_BYPASS; nunca en el repositorio). Sin ella, nada.
const CLAVE = process.env.BYPASS ?? process.env.VERCEL_BYPASS;

const RECORRIDOS = /(recorridos|copias-archivadas)\.spec\.ts$/;
// Cada navegador se identifica como de las pruebas (e2e/agente.ts).
const agente = (base: string) => `${base}${SUFIJO_AGENTE}`;
const TABLETA_ANDROID =
  "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  // En la CI, un reintento: una página que tarda en llegar a un ejecutor compartido no es un fallo
  // de la web (Playwright marca la prueba como «flaky» y se ve en el informe).
  retries: process.env.CI === "true" ? 1 : 0,
  timeout: 90_000,
  reporter: "list",
  use: {
    baseURL: BASE,
    screenshot: "off",
    trace: "off",
    // Sin el service worker de la app (public/sw.js), salvo en los recorridos de la app
    // (e2e/app-recorridos.spec.ts, que lo pide con serviceWorkers: "allow"). Con él, cada prueba
    // pedía a la web dos veces casi todo: Playwright desactiva la caché HTTP del navegador al
    // interceptar peticiones (e2e/base.ts), así que lo que la página manda guardar al service worker
    // («guardar», con «force-cache») volvía a la red, y lo que responde el service worker no pasa por
    // las rutas de base.ts. Medido el 4 de noviembre de 2026: de 700 a 800 de las unas 2.400
    // peticiones de cada trabajo eran del service worker. Los contextos que abren las pruebas con
    // browser.newContext() lo bloquean también (base.ts).
    serviceWorkers: "block",
    // Con la clave, Vercel deja además una cookie de acceso: las peticiones que hace el service worker
    // de la app (public/sw.js), que no llevan las cabeceras de Playwright, también pasan.
    ...(CLAVE === undefined || CLAVE === ""
      ? {}
      : { extraHTTPHeaders: { "x-vercel-protection-bypass": CLAVE, "x-vercel-set-bypass-cookie": "true" } }),
  },
  projects: [
    {
      name: "escritorio",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, userAgent: agente(devices["Desktop Chrome"].userAgent) },
      testIgnore: RECORRIDOS,
    },
    { name: "movil", use: { ...devices["Pixel 7"], userAgent: agente(devices["Pixel 7"].userAgent) }, testIgnore: RECORRIDOS },
    // Los recorridos de una persona (e2e/recorridos.spec.ts), cada uno en su dispositivo. WebKit se
    // instala aparte: npx playwright install webkit.
    { name: "android", use: { ...devices["Pixel 7"], userAgent: agente(devices["Pixel 7"].userAgent) }, testMatch: RECORRIDOS },
    { name: "iphone", use: { ...devices["iPhone 14"], userAgent: agente(devices["iPhone 14"].userAgent) }, testMatch: RECORRIDOS },
    {
      name: "tableta",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 }, hasTouch: true, isMobile: true, userAgent: agente(TABLETA_ANDROID) },
      testMatch: RECORRIDOS,
    },
    {
      name: "escritorio-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 768 }, userAgent: agente(devices["Desktop Chrome"].userAgent) },
      testMatch: RECORRIDOS,
    },
    {
      name: "escritorio-webkit",
      use: { ...devices["Desktop Safari"], viewport: { width: 1366, height: 768 }, userAgent: agente(devices["Desktop Safari"].userAgent) },
      testMatch: RECORRIDOS,
    },
  ],
});
