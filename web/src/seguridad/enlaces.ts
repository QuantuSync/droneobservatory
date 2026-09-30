// Los enlaces de los datos vienen de fuentes externas: solo se aceptan http y https.

const ESQUEMAS_PERMITIDOS: ReadonlySet<string> = new Set(["http:", "https:"]);

/**
 * Devuelve la dirección normalizada si es http o https, y null en cualquier otro caso
 * (javascript:, data:, direcciones relativas o texto que no es una dirección).
 */
export function enlaceSeguro(enlace: unknown): string | null {
  if (typeof enlace !== "string") return null;
  let url: URL;
  try {
    url = new URL(enlace.trim());
  } catch {
    return null;
  }
  return ESQUEMAS_PERMITIDOS.has(url.protocol) ? url.href : null;
}
