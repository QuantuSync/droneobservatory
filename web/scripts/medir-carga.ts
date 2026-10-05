// Medida de la primera carga del mapa en producción, con la caché vacía: tiempo hasta la primera
// pintura con contenido, hasta el mayor elemento pintado y hasta que el mapa está listo
// ([data-mapa-listo=true]), en escritorio y en móvil emulado (CPU cuatro veces más lenta). Se usa
// para comparar antes y después de un cambio: `node scripts/medir-carga.ts [pasadas] [dirección]`.

import { chromium, devices } from "@playwright/test";

const PASADAS = Number(process.argv[2] ?? "5");
const BASE = process.argv[3] ?? "https://droneobservatory.eu/";
const PERFILES = [
  { nombre: "escritorio", contexto: { viewport: { width: 1440, height: 900 } }, cpu: 1 },
  { nombre: "movil", contexto: { ...devices["Pixel 7"] }, cpu: 4 },
] as const;

function mediana(valores: number[]): number {
  const orden = [...valores].sort((a, b) => a - b);
  return orden[Math.floor(orden.length / 2)] ?? Number.NaN;
}

const navegador = await chromium.launch({
  args: [
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=CalculateNativeWinOcclusion",
  ],
});
for (const perfil of PERFILES) {
  const medidas = { fcp: [] as number[], lcp: [] as number[], mapa: [] as number[], html: [] as number[] };
  for (let i = 0; i < PASADAS; i += 1) {
    const contexto = await navegador.newContext({ ...perfil.contexto });
    const pagina = await contexto.newPage();
    const cdp = await contexto.newCDPSession(pagina);
    await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
    if (perfil.cpu > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: perfil.cpu });
    await pagina.addInitScript(() => {
      const w = window as unknown as { __lcp: number };
      w.__lcp = 0;
      new PerformanceObserver((lista) => {
        for (const entrada of lista.getEntries()) w.__lcp = entrada.startTime;
      }).observe({ type: "largest-contentful-paint", buffered: true });
    });
    const inicio = Date.now();
    const respuesta = await pagina.goto(`${BASE}?medida=${Date.now()}`, { waitUntil: "commit" });
    const cuerpo = (await respuesta?.body())?.length ?? 0;
    await pagina.locator("[data-mapa-listo=true]").waitFor({ state: "attached", timeout: 90_000 });
    const mapa = Date.now() - inicio;
    const { fcp, lcp } = await pagina.evaluate(() => ({
      fcp: performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? Number.NaN,
      lcp: (window as unknown as { __lcp: number }).__lcp,
    }));
    medidas.fcp.push(fcp);
    medidas.lcp.push(lcp);
    medidas.mapa.push(mapa);
    medidas.html.push(cuerpo);
    await contexto.close();
  }
  console.log(
    `${perfil.nombre}: FCP ${Math.round(mediana(medidas.fcp))} ms · LCP ${Math.round(mediana(medidas.lcp))} ms · ` +
      `mapa listo ${Math.round(mediana(medidas.mapa))} ms · HTML ${mediana(medidas.html)} bytes ` +
      `(mediana de ${PASADAS}; mapa listo de cada pasada: ${medidas.mapa.join(", ")})`,
  );
}
await navegador.close();
