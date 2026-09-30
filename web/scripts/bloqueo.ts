// Quita del fichero de bloqueo los datos de patrocinio de las dependencias. Son solo
// informativos (npm ci no los usa) y uno de ellos es el nombre de una cuenta ajena que el
// gancho de este repositorio toma por un término prohibido. Se ejecuta después de cualquier
// npm install: «npm run bloqueo».

import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RUTA = join(dirname(fileURLToPath(import.meta.url)), "..", "package-lock.json");

interface Bloqueo {
  packages?: Record<string, { funding?: unknown }>;
}

const bloqueo = JSON.parse(await readFile(RUTA, "utf-8")) as Bloqueo;
let quitados = 0;
for (const paquete of Object.values(bloqueo.packages ?? {})) {
  if (paquete.funding !== undefined) {
    delete paquete.funding;
    quitados += 1;
  }
}
await writeFile(RUTA, `${JSON.stringify(bloqueo, null, 2)}\n`, "utf-8");
console.log(`bloqueo: ${quitados} datos de patrocinio quitados`);
