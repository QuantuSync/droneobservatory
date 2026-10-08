// Versiones citables de los datos abiertos en las páginas de texto: la lista de «Metodología y
// datos abiertos» y la página de cada versión, con sus ficheros, su huella, su licencia y su cita.

import { rutaDeFicheroDeVersion, rutasDeVersion } from "../datos/versiones.ts";
import type { VersionDatos } from "../datos/versiones.ts";
import { fecha, numero, textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import type { Html } from "./html.ts";

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
    e(
      "table",
      null,
      e("thead", null, e("tr", null, e("th", null, v.fichero), e("th", null, v.bytes), e("th", null, v.huella))),
      e(
        "tbody",
        null,
        Object.entries(version.ficheros).map(([nombre, f]) =>
          e(
            "tr",
            null,
            e("td", null, e("a", { href: rutaDeFicheroDeVersion(version.version, nombre), download: true }, nombre)),
            e("td", { class: "mono" }, numero(f.bytes, idioma)),
            e("td", { class: "mono texto-huella" }, f.sha256),
          ),
        ),
      ),
    ),
    e("p", { class: "texto-nota" }, v.comoComprobar),
    e("h2", null, t.descargas.licencia),
    e("p", null, e("a", { href: version.licencia.url, rel: "license noopener" }, version.licencia.nombre), ". ", version.licencia.alcance[idioma]),
    e("h2", null, v.citaTitulo),
    e("blockquote", { "data-cita-version": version.version }, version.cita[idioma]),
    e("p", null, e("a", { href: `${rutaMetodologia}#versiones` }, v.todas)),
  );
}
