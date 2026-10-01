import { useEffect, useRef } from "react";

import { fechaHora } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Bloque, Marca, Trozo } from "../i18n/tipos.ts";
import { DESCARGAS, LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Simbolo } from "./Simbolo.tsx";

interface Props {
  t: Textos;
  abierta: boolean;
  /** Fecha de la versión de los datos; null si no se han cargado. */
  actualizado: string | null;
  /** Si se publica el fichero de incidentes con ubicación imprecisa. */
  sinUbicacion: boolean;
  onCerrar: () => void;
}

function Texto({ t, trozos }: { t: Textos; trozos: readonly Trozo[] }) {
  return (
    <>
      {trozos.map((trozo, i) =>
        typeof trozo === "string" ? (
          trozo
        ) : (
          <EnlaceExterno
            key={i}
            enlace={trozo.enlace}
            aviso={t.ficha.enlaceExterno}
            avisoNoValido={t.ficha.enlaceNoValido}
          >
            {trozo.texto}
          </EnlaceExterno>
        ),
      )}
    </>
  );
}

function SimboloDeMarca({ marca }: { marca: Marca }) {
  return "tipo" in marca ? (
    <Simbolo tipo={marca.tipo} estado="notificado" />
  ) : (
    <Simbolo tipo="interrupcion_aeroportuaria" estado={marca.estado} />
  );
}

function BloqueDeTexto({ t, bloque }: { t: Textos; bloque: Bloque }) {
  if ("parrafo" in bloque) {
    return (
      <p className="mt-2">
        <Texto t={t} trozos={bloque.parrafo} />
      </p>
    );
  }
  return (
    <dl className="mt-2">
      {bloque.lista.map((elemento, i) => (
        <div key={i} className="border-b border-linea py-2">
          {elemento.termino !== undefined && (
            <dt className="flex items-center gap-2 font-medium text-texto">
              {elemento.marca !== undefined && <SimboloDeMarca marca={elemento.marca} />}
              {elemento.termino}
            </dt>
          )}
          <dd className="text-secundario">
            <Texto t={t} trozos={elemento.texto} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Descarga({ ruta, formato }: { ruta: string; formato: string }) {
  return (
    <a href={ruta} download className="control mono min-h-7 text-xs">
      {formato}
    </a>
  );
}

function Descargas({
  t,
  actualizado,
  sinUbicacion,
}: {
  t: Textos;
  actualizado: string | null;
  sinUbicacion: boolean;
}) {
  const d = t.metodologia.descargas;
  const version = actualizado === null ? null : fechaHora(actualizado);
  return (
    <section className="mt-6" aria-labelledby="metodologia-descargas">
      <h3 id="metodologia-descargas" className="text-lg font-semibold tracking-tight">
        {d.titulo}
      </h3>
      <p className="mt-2">{d.intro}</p>
      <dl className="mt-2">
        <div className="flex flex-wrap items-center gap-2 border-b border-linea py-2">
          <dt className="mr-auto">{d.incidentes}</dt>
          <dd className="flex gap-2">
            <Descarga ruta={DESCARGAS.incidentesGeojson} formato="GeoJSON" />
            <Descarga ruta={DESCARGAS.incidentesCsv} formato="CSV" />
          </dd>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-b border-linea py-2">
          <dt className="mr-auto">{d.ucrania}</dt>
          <dd className="flex gap-2">
            <Descarga ruta={DESCARGAS.ucraniaJson} formato="JSON" />
            <Descarga ruta={DESCARGAS.ucraniaCsv} formato="CSV" />
          </dd>
        </div>
        {sinUbicacion && (
          <div className="flex flex-wrap items-center gap-2 border-b border-linea py-2">
            <dt className="mr-auto">{d.sinUbicacion}</dt>
            <dd className="flex gap-2">
              <Descarga ruta={DESCARGAS.sinUbicacionJson} formato="JSON" />
            </dd>
          </div>
        )}
      </dl>
      {version !== null && <p className="mono mt-2 text-xs text-secundario">{d.version(version)}</p>}
      <p className="mt-1 text-xs text-secundario">
        {d.licencia}:{" "}
        <EnlaceExterno
          enlace={LICENCIA_DATOS_URL}
          aviso={t.ficha.enlaceExterno}
          avisoNoValido={t.ficha.enlaceNoValido}
        >
          {LICENCIA_DATOS}
        </EnlaceExterno>
      </p>
      {version !== null && (
        <>
          <p className="rotulo mt-3">{d.citaTitulo}</p>
          <p className="mt-1 border-l border-acento pl-2 text-secundario">{d.cita(version)}</p>
        </>
      )}
    </section>
  );
}

/**
 * Metodología: panel que se abre desde la cabecera en todas las resoluciones, sin salir de
 * la pantalla. Es un diálogo modal nativo: retiene el foco y se cierra con Escape.
 */
export function Metodologia({ t, abierta, actualizado, sinUbicacion, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const elemento = dialogo.current;
    if (elemento === null || typeof elemento.showModal !== "function") return;
    if (abierta && !elemento.open) elemento.showModal();
    if (!abierta && elemento.open) elemento.close();
  }, [abierta]);

  return (
    // El diálogo nativo ya atiende al teclado (Escape); el clic fuera del panel lo cierra.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={dialogo}
      aria-labelledby="metodologia-titulo"
      onClose={onCerrar}
      onClick={(evento) => {
        if (evento.target === dialogo.current) onCerrar();
      }}
      className="m-0 ml-auto h-dvh max-h-none w-full max-w-2xl bg-panel-solido p-0 backdrop:bg-fondo/60"
    >
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 border-b border-linea px-5 py-3">
          {/* El logo completo: WebP y PNG de respaldo, a 48 px y al doble para pantallas densas. */}
          <picture className="shrink-0">
            <source type="image/webp" srcSet="/marca/logo-96.webp 1x, /marca/logo-192.webp 2x" />
            <img
              src="/marca/logo-96.png"
              srcSet="/marca/logo-96.png 1x, /marca/logo-192.png 2x"
              alt=""
              width={48}
              height={48}
            />
          </picture>
          <div className="mr-auto">
            <p className="text-xs text-secundario">{NOMBRE}</p>
            <h2 id="metodologia-titulo" className="text-lg font-semibold tracking-tight">
              {t.metodologia.titulo}
            </h2>
          </div>
          <button
            type="button"
            className="control min-h-7 px-2 text-xs"
            aria-label={t.metodologia.cerrar}
            onClick={onCerrar}
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 pb-8 pt-2">
          {t.metodologia.secciones.map((seccion) => (
            <section key={seccion.id} className="mt-6" aria-labelledby={`metodologia-${seccion.id}`}>
              <h3 id={`metodologia-${seccion.id}`} className="text-lg font-semibold tracking-tight">
                {seccion.titulo}
              </h3>
              {seccion.bloques.map((bloque, i) => (
                <BloqueDeTexto key={i} t={t} bloque={bloque} />
              ))}
            </section>
          ))}
          <Descargas t={t} actualizado={actualizado} sinUbicacion={sinUbicacion} />
        </div>
      </div>
    </dialog>
  );
}
