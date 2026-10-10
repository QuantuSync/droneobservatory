// La página de texto «Avisos» (/avisos, /en/alerts), con la misma lógica que el panel del mapa
// (componentes/Avisos.tsx): primero los tres pasos (qué recibirás, qué quieres recibir y
// suscríbete), después la explicación por dispositivo y al final la lista de canales, cada uno
// con su código QR para poder imprimirla. Funciona sin ejecutar código. Los textos y los enlaces
// son los de src/avisos.ts.

import { RUTAS_AVISOS, TEXTO_AVISOS, TIENDAS, canales, enlaceAndroid, enlaceWeb, rutaQr } from "../avisos.ts";
import type { Canal, Dispositivo } from "../avisos.ts";
import { NOMBRE } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { e, html } from "./html.ts";
import type { Html } from "./html.ts";

/** Fecha de la última revisión de la página, para el sitemap. */
const REVISION_AVISOS = "2026-10-10T00:00:00Z";
/** Lado del código QR en la página, en píxeles. */
export const LADO_QR = 144;

const DISPOSITIVOS: readonly Dispositivo[] = ["android", "iphone", "ordenador"];

function externo(url: string, texto: string): Html {
  return e("a", { href: url, rel: "noopener" }, texto);
}

/** Los tres pasos, para el canal de toda Europa; el de un país, en la lista del final. */
function pasos(idioma: Idioma, europa: Canal): Html {
  const t = TEXTO_AVISOS[idioma];
  const n = t.nombreDispositivo;
  return e(
    "ol",
    { class: "texto-pasos", id: "pasos" },
    e("li", null, e("h2", null, t.pasoRecibir), e("p", null, t.recibir)),
    e(
      "li",
      null,
      e("h2", null, t.pasoElegir),
      e(
        "p",
        null,
        `${europa.nombre} (`,
        e("span", { class: "mono" }, europa.tema),
        `) ${t.oPais} `,
        e("a", { href: "#canales" }, t.canales.toLowerCase()),
        ".",
      ),
    ),
    e(
      "li",
      null,
      e("h2", null, t.pasoSuscribir),
      e(
        "ul",
        { class: "texto-botones" },
        e("li", null, e("a", { class: "texto-boton", href: enlaceAndroid(europa) }, `${t.suscribirme} · ${n.android}`)),
        e("li", null, e("a", { class: "texto-boton", href: TIENDAS.appStore, rel: "noopener" }, `${t.suscribirme} · ${n.iphone}`)),
        e("li", null, e("a", { class: "texto-boton", href: enlaceWeb(europa), rel: "noopener" }, `${t.suscribirme} · ${n.ordenador}`)),
      ),
    ),
  );
}

function detalle(idioma: Idioma): Html {
  const t = TEXTO_AVISOS[idioma];
  return e(
    "section",
    { id: "dispositivos" },
    e("h2", null, t.detalle),
    DISPOSITIVOS.map((d) =>
      e(
        "section",
        { id: `en-${d}` },
        e("h3", null, t.nombreDispositivo[d]),
        e("ol", null, t.detalleDispositivo[d].map((paso) => e("li", null, paso))),
        d === "android"
          ? e("p", null, externo(TIENDAS.googlePlay, "Google Play"), " · ", externo(TIENDAS.fdroid, "F-Droid"))
          : d === "iphone"
            ? e("p", null, externo(TIENDAS.appStore, "App Store"))
            : null,
      ),
    ),
  );
}

function canal(c: Canal, idioma: Idioma): Html {
  const t = TEXTO_AVISOS[idioma];
  return e(
    "li",
    { class: "texto-canal", id: `canal-${c.tema}` },
    e("h3", null, c.nombre),
    e("p", { class: "mono" }, c.tema),
    e("img", { src: rutaQr(c), alt: t.qr(c.nombre), width: LADO_QR, height: LADO_QR, loading: "lazy" }),
    e(
      "p",
      { class: "texto-canal-enlaces" },
      e("a", { href: enlaceAndroid(c) }, t.nombreDispositivo.android),
      " · ",
      e("a", { href: enlaceWeb(c), rel: "noopener" }, t.abrirNavegador),
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
  const lista = canales(idioma);
  const europa = lista[0];
  if (europa === undefined) throw new Error("sin canales de avisos");
  return {
    idioma,
    rutas: RUTAS_AVISOS,
    titulo: `${t.titulo} · ${NOMBRE}`,
    descripcion: t.descripcion,
    cuerpo: html(
      e("h1", null, t.titulo),
      pasos(idioma, europa),
      detalle(idioma),
      e("section", { id: "que-se-avisa" }, e("h2", null, t.queSeAvisa), e("ul", null, t.avisa.map((a) => e("li", null, a))), e("p", null, t.queNo)),
      e(
        "section",
        { id: "canales" },
        e("h2", null, t.canales),
        e("p", null, t.canalesNota),
        e("ul", { class: "texto-canales" }, lista.map((c) => canal(c, idioma))),
      ),
    ),
    modificada: REVISION_AVISOS,
  };
}
