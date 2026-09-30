// Lectura de las cabeceras y reescrituras de vercel.json. La usan el servidor local, para
// imitar el despliegue, y los tests que comprueban la política de seguridad.

export interface Cabecera {
  key: string;
  value: string;
}

export interface ConfiguracionDespliegue {
  headers?: { source: string; headers: Cabecera[] }[];
  rewrites?: { source: string; destination: string }[];
}

/**
 * Convierte un patrón de ruta de vercel.json en una expresión regular. Admite lo que usa
 * este proyecto: grupos entre paréntesis y parámetros con nombre y patrón propio,
 * «:id(patrón)».
 */
export function patronDeRuta(fuente: string): RegExp {
  return new RegExp(`^${fuente.replace(/:\w+\(/g, "(")}$`);
}

/** Cabeceras que el despliegue añade a una ruta, en orden; una posterior sustituye a otra. */
export function cabecerasDe(configuracion: ConfiguracionDespliegue, ruta: string): Map<string, string> {
  const cabeceras = new Map<string, string>();
  for (const regla of configuracion.headers ?? []) {
    if (!patronDeRuta(regla.source).test(ruta)) continue;
    for (const { key, value } of regla.headers) cabeceras.set(key, value);
  }
  return cabeceras;
}

export function destinoDeReescritura(
  configuracion: ConfiguracionDespliegue,
  ruta: string,
): string | null {
  for (const regla of configuracion.rewrites ?? []) {
    if (patronDeRuta(regla.source).test(ruta)) return regla.destination;
  }
  return null;
}

/** Directivas de una política de seguridad de contenido: nombre y lista de orígenes. */
export function directivasCsp(politica: string): Map<string, string[]> {
  const directivas = new Map<string, string[]>();
  for (const parte of politica.split(";")) {
    const [nombre, ...valores] = parte.trim().split(/\s+/);
    if (nombre !== undefined && nombre.length > 0) directivas.set(nombre, valores);
  }
  return directivas;
}
