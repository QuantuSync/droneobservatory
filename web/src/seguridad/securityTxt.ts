// Contenido de /.well-known/security.txt (RFC 9116). Se genera en cada build para que la
// caducidad quede siempre a un año.

import { CONTACTO_SEGURIDAD, ORIGEN } from "../sitio.ts";

export const RUTA_SECURITY_TXT = "/.well-known/security.txt";
const ANIOS_DE_VALIDEZ = 1;

export function securityTxt(ahora: Date): string {
  const caducidad = new Date(ahora);
  caducidad.setUTCFullYear(caducidad.getUTCFullYear() + ANIOS_DE_VALIDEZ);
  caducidad.setUTCMilliseconds(0);
  return [
    `Contact: mailto:${CONTACTO_SEGURIDAD}`,
    `Expires: ${caducidad.toISOString().replace(".000Z", "Z")}`,
    "Preferred-Languages: es, en",
    `Canonical: ${ORIGEN}${RUTA_SECURITY_TXT}`,
    "",
  ].join("\n");
}
