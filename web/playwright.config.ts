import { defineConfig, devices } from "@playwright/test";

// Comprobación en un navegador real, en escritorio y en móvil. Por defecto va contra
// producción; con BASE=http://localhost:4173 va contra el servidor local (npm run servir).
const BASE = process.env.BASE ?? "https://droneobservatory.eu";

const RECORRIDOS = /recorridos\.spec\.ts$/;
const TABLETA_ANDROID =
  "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  reporter: "list",
  use: {
    baseURL: BASE,
    screenshot: "off",
    trace: "off",
  },
  projects: [
    { name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testIgnore: RECORRIDOS },
    { name: "movil", use: { ...devices["Pixel 7"] }, testIgnore: RECORRIDOS },
    // Los recorridos de una persona (e2e/recorridos.spec.ts), cada uno en su dispositivo. WebKit se
    // instala aparte: npx playwright install webkit.
    { name: "android", use: { ...devices["Pixel 7"] }, testMatch: RECORRIDOS },
    { name: "iphone", use: { ...devices["iPhone 14"] }, testMatch: RECORRIDOS },
    {
      name: "tableta",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 }, hasTouch: true, isMobile: true, userAgent: TABLETA_ANDROID },
      testMatch: RECORRIDOS,
    },
    { name: "escritorio-chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 768 } }, testMatch: RECORRIDOS },
    { name: "escritorio-webkit", use: { ...devices["Desktop Safari"], viewport: { width: 1366, height: 768 } }, testMatch: RECORRIDOS },
  ],
});
