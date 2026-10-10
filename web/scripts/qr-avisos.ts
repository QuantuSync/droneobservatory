// Códigos QR de los canales de avisos (src/avisos.ts), como imágenes estáticas del build en
// /avisos/qr/<canal>.svg: módulos negros sobre blanco con el margen de 4 módulos que pide la norma,
// para que cualquier cámara los lea también en el tema oscuro de la web. Cada código lleva a la
// dirección del canal en el servidor ntfy, que abre la aplicación o el navegador.

import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

import qrcode from "qrcode-generator";

import { canales, enlaceWeb } from "../src/avisos.ts";

const MARGEN = 4;

/** El SVG de un código QR (corrección de errores M), con un trazado por fila de módulos. */
export function svgQr(texto: string, titulo: string): string {
  const qr = qrcode(0, "M");
  qr.addData(texto);
  qr.make();
  const n = qr.getModuleCount();
  const lado = n + 2 * MARGEN;
  const trazos: string[] = [];
  for (let fila = 0; fila < n; fila += 1) {
    for (let columna = 0; columna < n; columna += 1) {
      if (qr.isDark(fila, columna)) trazos.push(`M${columna + MARGEN} ${fila + MARGEN}h1v1h-1z`);
    }
  }
  const escapado = titulo.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${lado} ${lado}" shape-rendering="crispEdges">` +
    `<title>${escapado}</title><rect width="${lado}" height="${lado}" fill="#fff"/>` +
    `<path fill="#000" d="${trazos.join("")}"/></svg>\n`
  );
}

/** Escribe el código QR de cada canal en <carpeta>/avisos/qr. Devuelve cuántos. */
export async function escribirQrAvisos(carpeta: string): Promise<number> {
  const destino = join(carpeta, "avisos", "qr");
  await mkdir(destino, { recursive: true });
  const lista = canales("es");
  for (const canal of lista) {
    await writeFile(join(destino, `${canal.tema}.svg`), svgQr(enlaceWeb(canal), enlaceWeb(canal)), "utf-8");
  }
  return lista.length;
}
