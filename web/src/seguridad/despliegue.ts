// Lectura de las cabeceras, redirecciones y reescrituras de vercel.json. La usan el servidor
// local, para imitar el despliegue, los tests que comprueban la política de seguridad y la
// comprobación de capacidad de la integración continua.

export interface Cabecera {
  key: string;
  value: string;
}

export interface ConfiguracionDespliegue {
  headers?: { source: string; headers: Cabecera[] }[];
  redirects?: { source: string; destination: string; permanent: boolean }[];
  rewrites?: { source: string; destination: string }[];
  bulkRedirectsPath?: string;
}

/**
 * Capacidad de Vercel para este proyecto (plan Pro): 2.048 reglas de enrutado en vercel.json
 * (cabeceras, redirecciones y reescrituras) y 1.000 redirecciones masivas incluidas
 * (bulkRedirectsPath). Pasar de ellas hace fallar el despliegue y la web deja de actualizarse.
 */
export const CAPACIDAD_RUTAS = 2048;
export const CAPACIDAD_REDIRECCIONES_MASIVAS = 1000;
/** La integración continua falla al pasar de esta parte de la capacidad, antes de que falle el despliegue. */
export const AVISO_CAPACIDAD = 0.8;

export interface UsoCapacidad {
  nombre: string;
  usadas: number;
  capacidad: number;
}

/** Lo usado de cada capacidad: las reglas de vercel.json y las redirecciones masivas. */
export function usoDeCapacidad(configuracion: ConfiguracionDespliegue, redireccionesMasivas: number): UsoCapacidad[] {
  const reglas =
    (configuracion.headers?.length ?? 0) + (configuracion.redirects?.length ?? 0) + (configuracion.rewrites?.length ?? 0);
  return [
    { nombre: "reglas de vercel.json", usadas: reglas, capacidad: CAPACIDAD_RUTAS },
    { nombre: "redirecciones masivas", usadas: redireccionesMasivas, capacidad: CAPACIDAD_REDIRECCIONES_MASIVAS },
  ];
}

/** Las capacidades que pasan del aviso, con un texto claro para la integración continua. */
export function capacidadesAlLimite(uso: UsoCapacidad[]): string[] {
  return uso
    .filter((u) => u.usadas > u.capacidad * AVISO_CAPACIDAD)
    .map(
      (u) =>
        `${u.nombre}: ${u.usadas} de ${u.capacidad} (más del ${AVISO_CAPACIDAD * 100} %); el despliegue fallará ` +
        `al pasar de ${u.capacidad}: reducirlas o ampliar la capacidad en Vercel antes de fusionar`,
    );
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
