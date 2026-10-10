import type { RefObject } from "react";

import { RUTAS_AVISOS, TEXTO_AVISOS, TIENDAS, canales, enlaceAndroid, enlaceWeb, rutaQr } from "../avisos.ts";
import type { Canal } from "../avisos.ts";
import type { Idioma } from "../sitio.ts";

/** Campana sencilla, del color del texto: acompaña al rótulo «Avisos» en la cabecera. */
export function IconoCampana({ lado = 14 }: { lado?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={lado}
      height={lado}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
    >
      <path d="M4 11V7a4 4 0 0 1 8 0v4l1.25 1.5H2.75L4 11Z" />
      <path d="M6.5 14a1.5 1.5 0 0 0 3 0" />
    </svg>
  );
}

/**
 * El botón «Avisos» de la cabecera, en el escritorio y en el teléfono: la herramienta que más
 * importa, a la vista sin abrir ningún menú. Mismo estilo que la cabecera, con más peso: campana,
 * texto claro, seminegrita y un borde. Abierto, en claro como todo lo seleccionado.
 */
export function BotonAvisos({
  idioma,
  abierto,
  onAbrir,
  referencia,
  grande = false,
}: {
  idioma: Idioma;
  abierto: boolean;
  onAbrir: () => void;
  referencia?: RefObject<HTMLButtonElement | null> | undefined;
  grande?: boolean;
}) {
  const t = TEXTO_AVISOS[idioma];
  return (
    <button
      ref={referencia}
      type="button"
      className={`control gap-1.5 whitespace-nowrap rounded-sm border border-linea font-semibold text-texto ${
        grande ? "min-h-11 px-2.5 text-sm" : "min-h-7 px-2 text-xs"
      }`}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      aria-label={t.abrir}
      data-boton-avisos=""
      onClick={onAbrir}
    >
      <IconoCampana lado={grande ? 16 : 14} />
      {t.enlace}
    </button>
  );
}

const ENLACE = "text-texto underline decoration-secundario underline-offset-2 hover:decoration-acento";
const BOTON =
  "control min-h-11 w-full justify-center rounded-sm border border-linea px-3 text-center text-sm text-texto esc:min-h-9";

function CanalAvisos({ canal, idioma }: { canal: Canal; idioma: Idioma }) {
  const t = TEXTO_AVISOS[idioma];
  return (
    <details className="group border-b border-linea last:border-b-0" open={canal.general} data-canal={canal.tema}>
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 py-2 text-sm text-texto esc:min-h-9 [&::-webkit-details-marker]:hidden">
        <span aria-hidden="true" className="w-3 text-xs text-secundario transition-transform group-open:rotate-90">
          ▸
        </span>
        <span className="mr-auto">{canal.general ? t.general : canal.nombre}</span>
        <span className="mono text-xs text-secundario">{canal.tema}</span>
      </summary>
      <div className="flex flex-col gap-3 pb-3 text-xs text-secundario">
        <section aria-label={`${t.android} · ${canal.nombre}`} className="flex flex-col gap-1.5">
          <h4 className="rotulo">{t.android}</h4>
          <a className={BOTON} href={enlaceAndroid(canal)}>
            {t.suscribirAndroid}
          </a>
          <p>
            {t.sinAplicacion}{" "}
            <a className={ENLACE} href={TIENDAS.googlePlay} rel="noopener" target="_blank">
              Google Play
            </a>{" "}
            ·{" "}
            <a className={ENLACE} href={TIENDAS.fdroid} rel="noopener" target="_blank">
              F-Droid
            </a>
            .
          </p>
        </section>
        <section aria-label={`${t.iphone} · ${canal.nombre}`} className="flex flex-col gap-1.5">
          <h4 className="rotulo">{t.iphone}</h4>
          <a className={ENLACE} href={TIENDAS.appStore} rel="noopener" target="_blank">
            {t.instalarIphone}
          </a>
          <ol className="list-decimal pl-5">
            {t.pasosIphone(canal.tema).map((paso) => (
              <li key={paso} className="break-words">
                {paso}
              </li>
            ))}
          </ol>
        </section>
        <section aria-label={`${t.ordenador} · ${canal.nombre}`} className="flex flex-col gap-1.5">
          <h4 className="rotulo">{t.ordenador}</h4>
          <a className={BOTON} href={enlaceWeb(canal)} rel="noopener" target="_blank">
            {t.abrirNavegador}
          </a>
          <p>{t.notaNavegador}</p>
        </section>
        <figure className="flex flex-col items-center gap-1">
          <img src={rutaQr(canal)} alt={t.qr(canal.nombre)} width={144} height={144} loading="lazy" className="rounded-sm" />
          <figcaption className="mono text-[0.6875rem]">{enlaceWeb(canal).replace("https://", "")}</figcaption>
        </figure>
      </div>
    </details>
  );
}

/**
 * Lo que dice la página «Avisos», en el panel del mapa: qué se avisa, sin cuenta, y cada canal
 * (el general abierto; los países plegados) con sus botones para Android, iPhone y el ordenador y
 * su código QR. Abrir o cerrar un canal no mueve el mapa. Al pie, la página completa.
 */
export function Avisos({ idioma }: { idioma: Idioma }) {
  const t = TEXTO_AVISOS[idioma];
  return (
    <div className="flex flex-col gap-3 text-sm" data-panel-avisos="">
      <p className="text-xs text-secundario">{t.sinCuenta}</p>
      <section className="flex flex-col gap-1">
        <h3 className="rotulo">{t.queSeAvisa}</h3>
        <ul className="list-disc pl-4 text-xs text-texto">
          {t.avisa.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
        <p className="text-xs text-secundario">{t.queNo}</p>
      </section>
      <section className="flex flex-col">
        <h3 className="rotulo mb-1">{t.canales}</h3>
        {canales(idioma).map((canal) => (
          <CanalAvisos key={canal.tema} canal={canal} idioma={idioma} />
        ))}
      </section>
      <p className="text-xs">
        <a className={ENLACE} href={RUTAS_AVISOS[idioma]}>
          {t.paginaCompleta}
        </a>
      </p>
    </div>
  );
}
