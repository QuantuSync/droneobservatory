// Licencia de los datos abiertos dentro de cada fichero JSON descargable (/datos): qué licencia
// tiene la compilación, qué queda fuera y cómo se cita. Los CSV no tienen dónde llevarla: la dan
// la cabecera HTTP «Link: rel="license"» de /datos (vercel.json) y la página de datos abiertos.

import { fechaHora, textos } from "../i18n/index.ts";
import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN } from "../sitio.ts";

export interface MetadatosLicencia {
  nombre: string;
  url: string;
  titular: string;
  fuente: string;
  alcance: { es: string; en: string };
  cita: { es: string; en: string };
}

/** La licencia de los datos publicados a `actualizado` (instante ISO de la versión). */
export function metadatosLicencia(actualizado: string): MetadatosLicencia {
  const version = fechaHora(actualizado);
  const es = textos("es").metodologia.descargas;
  const en = textos("en").metodologia.descargas;
  return {
    nombre: LICENCIA_DATOS,
    url: LICENCIA_DATOS_URL,
    titular: NOMBRE,
    fuente: `${ORIGEN}/`,
    alcance: { es: es.licenciaTexto, en: en.licenciaTexto },
    cita: { es: es.cita(version), en: en.cita(version) },
  };
}

/**
 * El texto de un fichero JSON publicado con la licencia como primer miembro del objeto raíz (en un
 * GeoJSON, un miembro ajeno permitido por el estándar). El resto del contenido no cambia.
 */
export function conLicencia(texto: string, actualizado: string): string {
  const datos = JSON.parse(texto) as Record<string, unknown>;
  return JSON.stringify({ licencia: metadatosLicencia(actualizado), ...datos });
}
