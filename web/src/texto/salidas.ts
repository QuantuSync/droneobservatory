// Lo que el build escribe además de las páginas: el sitemap, llms.txt, la página 404 y las
// redirecciones permanentes de los incidentes unidos a otro.

import { escaparHtml } from "../cabecera.ts";
import { cifras } from "../datos/derivar.ts";
import type { Resumen } from "../datos/tipos.ts";
import { fechaHora, textos } from "../i18n/index.ts";
import { DESCARGAS, IDIOMAS, LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN, rutaDeFicha, rutaDeIdioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import { direccionCompleta, RUTAS } from "./paginas.ts";
import type { PaginaTexto } from "./paginas.ts";
import { PAGINAS_SERVICIO, RUTAS_SERVICIO, textoServicio } from "./servicio.ts";
import { textosPagina } from "./textos.ts";

/** sitemap.xml con todas las páginas, su versión en el otro idioma y su última modificación. */
export function sitemap(paginas: readonly PaginaTexto[]): string {
  const entradas = paginas.map((p) => {
    const alternativas = IDIOMAS.map(
      (idioma) =>
        `<xhtml:link rel="alternate" hreflang="${idioma}" href="${escaparHtml(direccionCompleta(p.rutas[idioma]))}"/>`,
    ).join("");
    return (
      `<url><loc>${escaparHtml(direccionCompleta(p.rutas[p.idioma]))}</loc>` +
      `<lastmod>${escaparHtml(p.modificada)}</lastmod>${alternativas}</url>`
    );
  });
  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n` +
    `${entradas.join("\n")}\n</urlset>\n`
  );
}

/** Redirecciones permanentes de un identificador unido al incidente que queda, en los dos
 *  idiomas; solo si el que queda está publicado y el unido no lo está. */
export function redirecciones(
  unidos: Readonly<Record<string, string>>,
  publicados: ReadonlySet<string>,
): { source: string; destination: string; statusCode: number }[] {
  return Object.entries(unidos)
    .filter(([origen, destino]) => publicados.has(destino) && !publicados.has(origen))
    .sort(([a], [b]) => a.localeCompare(b))
    .flatMap(([origen, destino]) =>
      IDIOMAS.map((idioma) => ({
        source: rutaDeFicha(origen, idioma),
        destination: rutaDeFicha(destino, idioma),
        statusCode: 308,
      })),
    );
}

/** La página 404, en los dos idiomas. */
export function noEncontrada(): PaginaTexto {
  const es = textosPagina("es");
  const en = textosPagina("en");
  return {
    idioma: "es",
    rutas: { es: rutaDeIdioma("es"), en: rutaDeIdioma("en") },
    titulo: `${es.noEncontrada.titulo} · ${en.noEncontrada.titulo} · ${NOMBRE}`,
    descripcion: es.noEncontrada.texto,
    cuerpo: html(
      e("h1", null, es.noEncontrada.titulo),
      e("p", null, es.noEncontrada.texto, " ", e("a", { href: rutaDeIdioma("es") }, es.noEncontrada.volver)),
      e(
        "div",
        { lang: "en" },
        e("h2", null, en.noEncontrada.titulo),
        e("p", null, en.noEncontrada.texto, " ", e("a", { href: rutaDeIdioma("en") }, en.noEncontrada.volver)),
      ),
    ),
    estructurados: [],
    conMapa: false,
    modificada: "",
  };
}

/** llms.txt: qué es el observatorio, qué contiene, cómo leer los estados y dónde está todo. */
export function llmsTxt(resumen: Resumen): string {
  const c = cifras(resumen.incidentes);
  const es = textosPagina("es");
  const en = textosPagina("en");
  const enlaces = (idioma: "es" | "en") => {
    const tp = textosPagina(idioma);
    return [
      `- [${tp.portada.titulo}](${direccionCompleta(rutaDeIdioma(idioma))})`,
      `- [${tp.lista.titulo}](${direccionCompleta(RUTAS.incidentes[idioma])})`,
      `- [${tp.pais.titulo}](${direccionCompleta(RUTAS.paises[idioma])})`,
      `- [${tp.ucrania.titulo}](${direccionCompleta(RUTAS.ucrania[idioma])})`,
      `- [${tp.prevision.titulo}](${direccionCompleta(RUTAS.prevision[idioma])})`,
      `- [${tp.metodologia.titulo}](${direccionCompleta(RUTAS.metodologia[idioma])})`,
      `- [${tp.ayuda.titulo}](${direccionCompleta(RUTAS.ayuda[idioma])})`,
      ...PAGINAS_SERVICIO.map(
        (pagina) => `- [${textoServicio(pagina, idioma).titulo}](${direccionCompleta(RUTAS_SERVICIO[pagina][idioma])})`,
      ),
    ].join("\n");
  };
  const estados = (idioma: "es" | "en") => {
    const tp = textosPagina(idioma);
    const nombres =
      idioma === "es"
        ? { notificado: "Notificado", confirmado: "Confirmado", atribuido: "Atribuido", desmentido: "Desmentido" }
        : { notificado: "Reported", confirmado: "Confirmed", atribuido: "Attributed", desmentido: "Denied" };
    return (["notificado", "confirmado", "atribuido", "desmentido"] as const)
      .map((estado) => `- ${nombres[estado]}: ${tp.estado[estado]}`)
      .join("\n");
  };
  const fecha = fechaHora(resumen.actualizado);
  return [
    `# ${NOMBRE}`,
    "",
    `> ${en.portada.descripcion}`,
    "",
    en.portada.que.join(" "),
    "",
    `Figures at ${fecha}: ${c.incidentes} incidents, ${c.confirmados} confirmed (${c.atribuidos} of them attributed), ${c.paises} countries.`,
    "",
    "Every incident has its own page at /EODI-YYYY-NNNNN (Spanish) and /en/EODI-YYYY-NNNNN (English), with its status, drone presence, place, date, consequences, attribution with the authority's literal statement, every saved quote with its source link and date, and the history of status changes with its reasons.",
    "",
    "## How to read the status",
    "",
    estados("en"),
    "",
    "## Pages",
    "",
    enlaces("en"),
    "",
    "## Open data",
    "",
    `Licence: ${LICENCIA_DATOS} (${LICENCIA_DATOS_URL}) for the observatory's compilation (incidents, statuses, classifications and figures). Rebuilt on every data update. Quoted sentences remain their authors' and are used as quotations, with their source; the measured air traffic block (trafico_aereo) derives from adsb.lol and is offered under ODbL 1.0.`,
    "",
    `How to cite: ${textos("en").metodologia.descargas.cita(fecha)}`,
    "",
    `- [Incidents, GeoJSON](${ORIGEN}${DESCARGAS.incidentesGeojson})`,
    `- [Incidents, CSV](${ORIGEN}${DESCARGAS.incidentesCsv})`,
    `- [Incidents with an approximate location (no exact point), JSON](${ORIGEN}${DESCARGAS.sinUbicacionJson})`,
    `- [Ukraine layer attacks, JSON](${ORIGEN}${DESCARGAS.ucraniaJson})`,
    `- [Ukraine layer attacks, CSV](${ORIGEN}${DESCARGAS.ucraniaCsv})`,
    `- [Sitemap](${ORIGEN}/sitemap.xml)`,
    "",
    "## En español",
    "",
    `> ${es.portada.descripcion}`,
    "",
    es.portada.que.join(" "),
    "",
    `Cifras a ${fecha}: ${c.incidentes} incidentes, ${c.confirmados} confirmados (${c.atribuidos} de ellos atribuidos), ${c.paises} países.`,
    "",
    "Cada incidente tiene su página en /EODI-AAAA-NNNNN (español) y /en/EODI-AAAA-NNNNN (inglés).",
    "",
    "### Cómo se leen los estados",
    "",
    estados("es"),
    "",
    "### Páginas",
    "",
    enlaces("es"),
    "",
    `Datos abiertos con licencia ${LICENCIA_DATOS} (${LICENCIA_DATOS_URL}) para la compilación del observatorio (incidentes, estados, clasificaciones y cifras): ${ORIGEN}${RUTAS.metodologia.es}#datos-abiertos. Las frases citadas siguen siendo de sus autores; el tráfico aéreo medido (trafico_aereo) se ofrece con ODbL 1.0.`,
    "",
    `Cómo citar: ${textos("es").metodologia.descargas.cita(fecha)}`,
    "",
  ].join("\n");
}
