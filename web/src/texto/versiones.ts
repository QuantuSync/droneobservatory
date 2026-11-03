// Versiones citables de los datos abiertos en las páginas de texto: la lista de «Metodología y
// datos abiertos» y la página de cada versión, con sus ficheros, su huella, su licencia y su cita.

import { rutaDeFicheroDeVersion, rutasDeVersion } from "../datos/versiones.ts";
import type { VersionDatos } from "../datos/versiones.ts";
import { urlDeDoi } from "../datos/versionesArchivadas.ts";
import type { VersionArchivada } from "../datos/versionesArchivadas.ts";
import { fecha, numero, textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import type { Hijo, Html } from "./html.ts";

function dia(instante: string | null): string {
  return instante === null ? "—" : fecha(new Date(instante));
}

/** La sección de las versiones dentro de los datos abiertos de la metodología. */
export function seccionVersiones(versiones: readonly VersionDatos[], idioma: Idioma): Html {
  const v = textos(idioma).metodologia.versiones;
  const ultima = versiones[0];
  return e(
    "section",
    { id: "versiones" },
    e("h3", null, v.titulo),
    e("p", null, v.intro),
    versiones.length === 0
      ? e("p", null, v.ninguna)
      : html(
          e(
            "ul",
            null,
            versiones.map((x) =>
              e("li", null, e("a", { href: rutasDeVersion(x.version)[idioma] }, v.linea(x.version, dia(x.fecha), numero(x.incidentes, idioma)))),
            ),
          ),
          ultima !== undefined && html(e("h4", null, v.citaTitulo), e("blockquote", { "data-cita-version": ultima.version }, ultima.cita[idioma])),
        ),
  );
}

/** El cuerpo de la página de una versión. */
export function cuerpoVersion(version: VersionDatos, idioma: Idioma, rutaMetodologia: string): Html {
  const t = textos(idioma).metodologia;
  const v = t.versiones;
  return html(
    e("h1", null, v.tituloVersion(version.version)),
    e("p", null, v.congelada(dia(version.fecha), dia(version.datos_actualizados), numero(version.incidentes, idioma))),
    e("p", null, v.fija),
    // Una lista y no una tabla: en el teléfono, la huella (64 letras) no deja sitio a tres columnas.
    e(
      "dl",
      { class: "texto-ficheros" },
      Object.entries(version.ficheros).map(([nombre, f]) =>
        html(
          e("dt", null, e("a", { href: rutaDeFicheroDeVersion(version.version, nombre), download: true }, nombre), " · ", numero(f.bytes, idioma), " ", v.bytes.toLowerCase()),
          e("dd", { class: "mono texto-huella" }, v.huella, ": ", f.sha256),
        ),
      ),
    ),
    e("p", { class: "texto-nota" }, v.comoComprobar),
    e("h2", null, t.descargas.licencia),
    e("p", null, e("a", { href: version.licencia.url, rel: "license noopener" }, version.licencia.nombre), ". ", version.licencia.alcance[idioma]),
    e("h2", null, v.citaTitulo),
    e("blockquote", { "data-cita-version": version.version }, version.cita[idioma]),
    version.autor !== undefined &&
      e(
        "p",
        { "data-autoria": "" },
        `${idioma === "es" ? "Autor" : "Author"}: ${version.autor.firma[idioma]}`,
        " · ORCID ",
        e("a", { href: version.autor.orcid, rel: "author noopener", hreflang: null }, version.autor.orcid.replace("https://orcid.org/", "")),
      ),
    e("p", null, e("a", { href: `${rutaMetodologia}#versiones` }, v.todas)),
  );
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
 * de los datos vivos (cada hora) y de las versiones mensuales de la propia web.
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
