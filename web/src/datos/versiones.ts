// Versiones citables de los datos abiertos (recogida/versiones.py): el día 1 de cada mes se
// congelan en el almacén público los ficheros descargables, con su huella y su metadatos.json.
// La web lista las versiones en «Metodología y datos abiertos», da una página a cada una y sirve
// sus ficheros en /datos/versiones/AAAA-MM/<fichero> (vercel.json los reescribe al almacén).

export interface VersionDatos {
  version: string;
  nombre: string;
  /** Cuándo se congeló (UTC). */
  fecha: string;
  /** La hora de los datos que congela. */
  datos_actualizados: string | null;
  incidentes: number;
  direccion: string;
  licencia: {
    nombre: string;
    url: string;
    titular: string;
    alcance: { es: string; en: string };
  };
  cita: { es: string; en: string };
  ficheros: Record<string, { bytes: number; sha256: string }>;
}

/** Lo que sirve la web en /datos/versiones.json: las versiones, de la más nueva a la más vieja. */
export interface IndiceVersiones {
  versiones: VersionDatos[];
}

export const RUTA_INDICE_VERSIONES = "/datos/versiones.json";

/** La página de una versión en cada idioma. */
export function rutasDeVersion(version: string): { es: string; en: string } {
  return { es: `/datos/versiones/${version}`, en: `/en/data/versions/${version}` };
}

/** La dirección permanente de un fichero de una versión. */
export function rutaDeFicheroDeVersion(version: string, fichero: string): string {
  return `/datos/versiones/${version}/${fichero}`;
}
