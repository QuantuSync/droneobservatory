// La página de texto «Avisos» (/avisos, /en/alerts): qué se avisa y cómo suscribirse a cada canal
// sin cuenta, en Android, en iPhone o en el ordenador, con su código QR. Funciona sin ejecutar
// código: cada canal es un <details> (el general, abierto). El panel «Avisos» del mapa dice lo
// mismo (componentes/Avisos.tsx); los textos y los enlaces son los de src/avisos.ts.

import { RUTAS_AVISOS, TEXTO_AVISOS, TIENDAS, canales, enlaceAndroid, enlaceWeb, rutaQr } from "../avisos.ts";
import type { Canal } from "../avisos.ts";
import { NOMBRE } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import type { Html } from "./html.ts";

/** Fecha de la última revisión de la página, para el sitemap. */
const REVISION_AVISOS = "2026-10-10T00:00:00Z";
/** Lado del código QR en la página, en píxeles. */
export const LADO_QR = 168;

function externo(url: string, texto: string): Html {
  return e("a", { href: url, rel: "noopener" }, texto);
}

function canal(c: Canal, idioma: Idioma): Html {
  const t = TEXTO_AVISOS[idioma];
  return e(
    "details",
    { class: "texto-canal", id: `canal-${c.tema}`, open: c.general },
    e("summary", null, c.general ? t.general : c.nombre, " ", e("span", { class: "mono" }, c.tema)),
    e(
      "div",
      { class: "texto-canal-cuerpo" },
      e(
        "div",
        null,
        e("h3", null, t.android),
        e("p", null, e("a", { class: "texto-boton", href: enlaceAndroid(c) }, t.suscribirAndroid)),
        e("p", null, t.sinAplicacion, " ", externo(TIENDAS.googlePlay, "Google Play"), " · ", externo(TIENDAS.fdroid, "F-Droid"), "."),
        e("h3", null, t.iphone),
        e("p", null, externo(TIENDAS.appStore, t.instalarIphone)),
        e("ol", null, t.pasosIphone(c.tema).map((paso) => e("li", null, paso))),
        e("h3", null, t.ordenador),
        e("p", null, e("a", { class: "texto-boton", href: enlaceWeb(c), rel: "noopener" }, t.abrirNavegador)),
        e("p", null, t.notaNavegador),
      ),
      e(
        "figure",
        { class: "texto-qr" },
        e("img", { src: rutaQr(c), alt: t.qr(c.nombre), width: LADO_QR, height: LADO_QR, loading: "lazy" }),
        e("figcaption", { class: "mono" }, enlaceWeb(c).replace("https://", "")),
      ),
    ),
  );
}

export interface PaginaAvisos {
  idioma: Idioma;
  rutas: Record<Idioma, string>;
  titulo: string;
  descripcion: string;
  cuerpo: Html;
  modificada: string;
}

export function paginaAvisos(idioma: Idioma): PaginaAvisos {
  const t = TEXTO_AVISOS[idioma];
  return {
    idioma,
    rutas: RUTAS_AVISOS,
    titulo: `${t.titulo} · ${NOMBRE}`,
    descripcion: t.descripcion,
    cuerpo: html(
      e("h1", null, t.titulo),
      e("p", null, t.sinCuenta),
      e("section", { id: "que-se-avisa" }, e("h2", null, t.queSeAvisa), e("ul", null, t.avisa.map((a) => e("li", null, a))), e("p", null, t.queNo)),
      e("section", { id: "canales" }, e("h2", null, t.canales), canales(idioma).map((c) => canal(c, idioma))),
    ),
    modificada: REVISION_AVISOS,
  };
}
