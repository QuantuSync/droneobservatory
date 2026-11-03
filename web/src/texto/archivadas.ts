// Las versiones de los datos abiertos depositadas con DOI (configuracion/versiones_archivadas.json)
// en las páginas de texto: el apartado de «Metodología y datos abiertos».

import { partesDeCita, ULTIMA_ARCHIVADA, urlDeDoi } from "../datos/versionesArchivadas.ts";
import type { VersionArchivada } from "../datos/versionesArchivadas.ts";
import { fecha, numero, textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import type { Hijo, Html } from "./html.ts";

/** La cita recomendada de los datos: la de la versión archivada más reciente, con el DOI
 *  enlazado. Sin versión archivada, nada. */
export function citaRecomendadaConDoi(idioma: Idioma, nivel: "h2" | "h3"): Html | false {
  const v = ULTIMA_ARCHIVADA;
  if (v === undefined) return false;
  const p = partesDeCita(v);
  return html(
    e(nivel, { id: nivel === "h3" ? "citar" : null }, textos(idioma).metodologia.descargas.citaTitulo),
    e("blockquote", { "data-cita-recomendada": v.version }, p.antes, externo(p.doi, p.doi), p.despues),
  );
}

function dia(instante: string | null): string {
  return instante === null ? "—" : fecha(new Date(instante));
}

/** «Zenodo y DARIAH», «Zenodo, DARIAH y X». */
function enumeracion(lista: readonly string[], idioma: Idioma): string {
  const y = idioma === "es" ? " y " : " and ";
  return lista.length <= 1 ? (lista[0] ?? "") : `${lista.slice(0, -1).join(", ")}${y}${lista.at(-1) ?? ""}`;
}

function externo(url: string, ...hijos: Hijo[]): Html {
  return e("a", { href: url, rel: "noopener", hreflang: null }, ...hijos);
}

/**
 * Las versiones depositadas con DOI (configuracion/versiones_archivadas.json), de la más nueva a
 * la más vieja, cada una con su DOI, su repositorio, sus cifras, su licencia y su cita. Distintas
 * de los datos vivos, que cambian cada hora.
 */
export function seccionArchivadas(versiones: readonly VersionArchivada[], idioma: Idioma): Html | false {
  if (versiones.length === 0) return false;
  const a = textos(idioma).metodologia.archivadas;
  return e(
    "section",
    { id: "archivadas" },
    e("h3", null, a.titulo),
    e("p", null, a.intro),
    e(
      "ul",
      { class: "texto-archivadas" },
      versiones.map((v) =>
        e(
          "li",
          { "data-doi": v.doi },
          e("p", null, e("strong", null, a.linea(v.version, dia(`${v.fecha}T12:00:00Z`), numero(v.incidentes, idioma), numero(v.paises, idioma)))),
          e("p", null, "DOI: ", externo(urlDeDoi(v.doi), e("span", { class: "mono" }, urlDeDoi(v.doi)))),
          e("p", null, `${a.repositorio}: `, externo(v.pagina, v.repositorio), ` (${v.institucion[idioma]}). `, v.copias.length > 0 ? a.copias(enumeracion(v.copias, idioma)) : ""),
          e("p", null, a.corte(`${dia(v.corte_datos)} ${v.corte_datos.slice(11, 16)}`)),
          e(
            "p",
            null,
            `${a.licencia}: `,
            e("a", { href: v.licencia.url, rel: "license noopener", hreflang: null }, v.licencia.nombre),
            "; ",
            a.trafico,
            ", ",
            e("a", { href: v.licencia_trafico.url, rel: "license noopener", hreflang: null }, v.licencia_trafico.nombre),
            ".",
          ),
          e("p", null, externo(v.pagina, a.pagina)),
          e("h4", null, a.citaTitulo),
          e("blockquote", { "data-cita-archivada": v.version }, v.cita),
        ),
      ),
    ),
  );
}
