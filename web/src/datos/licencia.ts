// Licencia y créditos de los datos abiertos dentro de cada fichero JSON descargable (/datos): qué
// licencia tiene la compilación, qué queda fuera, quién es el autor (con su ORCID), cómo se cita y
// su dirección, para que viajen con los datos cuando alguien los integra en otro sistema. Los CSV no
// tienen dónde llevarlos: los dan las cabeceras HTTP «Link» de /datos (vercel.json) y la página
// de datos abiertos.

import { textos } from "../i18n/index.ts";
import { AUTOR_FIRMA, AUTOR_NOMBRE, CORREO_AUTOR, LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORCID_URL, ORIGEN, citaRecomendada, versionDeDatos } from "../sitio.ts";

/** El autor, como lo llevan los ficheros (recogida/licencia.py). */
export interface AutorDatos {
  nombre: string;
  firma: { es: string; en: string };
  orcid: string;
  correo: string;
}

export const AUTOR_DATOS: AutorDatos = {
  nombre: AUTOR_NOMBRE,
  firma: { es: AUTOR_FIRMA.es, en: AUTOR_FIRMA.en },
  orcid: ORCID_URL,
  correo: CORREO_AUTOR,
};

export interface MetadatosLicencia {
  nombre: string;
  url: string;
  titular: string;
  autor: AutorDatos;
  fuente: string;
  alcance: { es: string; en: string };
  cita: { es: string; en: string };
}

/** La licencia de los datos publicados a `actualizado` (instante ISO de la versión). */
export function metadatosLicencia(actualizado: string): MetadatosLicencia {
  const version = versionDeDatos(actualizado);
  const es = textos("es").metodologia.descargas;
  const en = textos("en").metodologia.descargas;
  return {
    nombre: LICENCIA_DATOS,
    url: LICENCIA_DATOS_URL,
    titular: NOMBRE,
    autor: AUTOR_DATOS,
    fuente: `${ORIGEN}/`,
    alcance: { es: es.licenciaTexto, en: en.licenciaTexto },
    cita: { es: citaRecomendada(version, "es"), en: citaRecomendada(version, "en") },
  };
}

/**
 * El texto de un fichero JSON publicado con la licencia como primer miembro del objeto raíz (en un
 * GeoJSON, un miembro ajeno permitido por el estándar). El resto del contenido no cambia.
 */
export function conLicencia(texto: string, actualizado: string): string {
  // Los ficheros del almacén ya traen la licencia (recogida/licencia.py): la de la descarga, con
  // la fecha de la versión en la cita, la sustituye.
  const datos = JSON.parse(texto) as Record<string, unknown>;
  delete datos.licencia;
  return JSON.stringify({ licencia: metadatosLicencia(actualizado), ...datos });
}
