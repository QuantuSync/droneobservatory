import { defineConfig, devices } from "@playwright/test";

// Comprobación en un navegador real, en escritorio y en móvil. Por defecto va contra
// producción; con BASE=http://localhost:4173 va contra el servidor local (npm run servir).
const BASE = process.env.BASE ?? "https://droneobservatory.eu";

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
    { name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "movil", use: { ...devices["Pixel 7"] } },
  ],
});
