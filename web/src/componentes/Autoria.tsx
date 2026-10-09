import type { Textos } from "../i18n/index.ts";
import { AUTOR_LINEA, CORREO_AUTOR, ORCID, ORCID_URL } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";

/**
 * Créditos del autor en una línea sobria: quién lo hace, su ORCID enlazado y el correo de
 * contacto (los mismos que las páginas de texto y que llevan dentro los ficheros de datos).
 */
export function Autoria({ t, idioma }: { t: Textos; idioma: Idioma }) {
  return (
    <p className="mt-1 text-xs text-secundario" data-autoria="">
      <span data-autor="">{AUTOR_LINEA[idioma]}</span> · ORCID{" "}
      <EnlaceExterno enlace={ORCID_URL} aviso={t.ficha.enlaceExterno} avisoNoValido={t.ficha.enlaceNoValido}>
        {ORCID}
      </EnlaceExterno>{" "}
      · {t.metodologia.descargas.contacto}:{" "}
      <a className="enlace" href={`mailto:${CORREO_AUTOR}`}>
        {CORREO_AUTOR}
      </a>
    </p>
  );
}
