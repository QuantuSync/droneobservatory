// La política de seguridad de contenido solo admite scripts servidos por este sitio. El
// prerenderizado deja algún script en línea con el estado inicial: aquí se separan del HTML
// para publicarlos como ficheros.

export interface ScriptSeparado {
  ruta: string;
  codigo: string;
}

/** Scripts sin atributo src. Los bloques de datos (JSON) no se ejecutan y se dejan. */
const SCRIPT_EN_LINEA = /<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g;
const TIPO_DE_DATOS = /type="application\/(ld\+)?json"/;

export function separarScriptsEnLinea(
  html: string,
  rutaDe: (codigo: string) => string,
): { html: string; scripts: ScriptSeparado[] } {
  const scripts: ScriptSeparado[] = [];
  const limpio = html.replace(SCRIPT_EN_LINEA, (todo, atributos: string, codigo: string) => {
    if (TIPO_DE_DATOS.test(atributos) || codigo.trim().length === 0) return todo;
    const ruta = rutaDe(codigo);
    scripts.push({ ruta, codigo });
    // Diferido, como los módulos: el estado inicial no tiene por qué frenar la primera pintura.
    return `<script${atributos} src="${ruta}" defer></script>`;
  });
  return { html: limpio, scripts };
}

/** Número de scripts ejecutables que siguen en línea en una página. */
export function contarScriptsEnLinea(html: string): number {
  return separarScriptsEnLinea(html, () => "").scripts.length;
}
