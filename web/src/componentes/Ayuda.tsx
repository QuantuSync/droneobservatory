import { useEffect, useRef } from "react";

import { ESTADOS } from "../datos/vocabulario.ts";
import { ATAJOS } from "../estado/atajos.ts";
import type { Textos } from "../i18n/index.ts";
import { PALETA } from "../paleta.ts";
import { MarcaFoco } from "./FocoTermico.tsx";
import { MarcaAtribuido, Simbolo } from "./Simbolo.tsx";

interface Props {
  t: Textos;
  abierta: boolean;
  onCerrar: () => void;
}

/** Punto de un impacto con lugar, como en el mapa: relleno (fuente oficial) o solo el aro. */
function MarcaImpacto({ parte }: { parte: boolean }) {
  return (
    <svg aria-hidden="true" width="10" height="10" viewBox="0 0 10 10" data-marca-impacto="">
      <circle
        cx="5"
        cy="5"
        r="3.4"
        fill={parte ? PALETA.fondo : PALETA.guerra}
        stroke={PALETA.guerra}
        strokeWidth="1.2"
      />
    </svg>
  );
}

/** Aviso de la detección en directo, como en el mapa: etiqueta con el código OACI y punta. */
function MarcaAviso() {
  return (
    <svg aria-hidden="true" width="34" height="18" viewBox="0 0 34 18" data-marca-aviso="">
      <path
        d="M7 0.75H27A6.25 6.25 0 0 1 27 13.25H19.5L17 17L14.5 13.25H7A6.25 6.25 0 0 1 7 0.75Z"
        fill={PALETA.panelSolido}
        stroke={PALETA.notificado}
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <text x="17" y="9.6" textAnchor="middle" fontSize="7" fill={PALETA.texto}>
        OACI
      </text>
    </svg>
  );
}

/** Región rusa, como en el mapa: violeta apagado con contorno discontinuo. */
function MarcaRusia() {
  return (
    <svg aria-hidden="true" width="14" height="10" viewBox="0 0 14 10" data-marca-rusia="">
      <rect
        x="0.6"
        y="0.6"
        width="12.8"
        height="8.8"
        fill={PALETA.guerraTenue}
        fillOpacity="0.4"
        stroke={PALETA.guerraTenue}
        strokeDasharray="2 1.5"
      />
    </svg>
  );
}

/** Marcas de la guerra por satélite, como en el mapa. */
function MarcaCorredor() {
  return (
    <svg aria-hidden="true" width="18" height="10" viewBox="0 0 18 10" data-marca-corredor="">
      <path d="M1 9 Q9 0 17 7" fill="none" stroke={PALETA.guerra} strokeWidth="1.4" strokeOpacity="0.7" />
    </svg>
  );
}

function MarcaLuz() {
  return (
    <svg aria-hidden="true" width="10" height="10" viewBox="0 0 10 10" data-marca-luz="">
      <circle cx="5" cy="5" r="4.2" fill={PALETA.fondo} stroke={PALETA.guerraTenue} strokeWidth="0.8" />
    </svg>
  );
}

function MarcaSatelite() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" data-marca-satelite="">
      <circle cx="9" cy="9" r="7.6" fill="none" stroke={PALETA.guerraClaro} strokeWidth="1" />
      <circle cx="9" cy="9" r="4.6" fill={PALETA.guerra} stroke={PALETA.guerraClaro} strokeWidth="1.4" />
    </svg>
  );
}

function MarcaAlumbrado() {
  return (
    <svg aria-hidden="true" width="10" height="10" viewBox="0 0 10 10" data-marca-alumbrado="">
      <circle cx="5" cy="5" r="3.8" fill={PALETA.fondo} stroke={PALETA.guerraTenue} strokeWidth="1.2" />
      <circle cx="5" cy="5" r="1.3" fill={PALETA.guerraClaro} />
    </svg>
  );
}

/** Nombre legible de una tecla en el panel de ayuda. */
function tecla(nombre: string): string {
  return nombre === "Escape" ? "Esc" : nombre.toUpperCase();
}

/**
 * Ayuda (tecla ?): qué significa cada forma, color, área, línea y número del mapa, y los
 * atajos de teclado. Sustituye a la leyenda fija. Es un diálogo modal nativo.
 */
export function Ayuda({ t, abierta, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const elemento = dialogo.current;
    if (elemento === null || typeof elemento.showModal !== "function") return;
    if (abierta && !elemento.open) elemento.showModal();
    if (!abierta && elemento.open) elemento.close();
  }, [abierta]);

  const a = t.ayuda;
  return (
    // El diálogo nativo ya atiende al teclado (Escape); el clic fuera del panel lo cierra.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={dialogo}
      aria-labelledby="ayuda-titulo"
      onClose={onCerrar}
      onClick={(evento) => {
        if (evento.target === dialogo.current) onCerrar();
      }}
      className="flotante m-auto max-h-[86vh] w-[min(92vw,40rem)] overflow-y-auto p-0 backdrop:bg-fondo/60"
    >
      <div className="flex items-center border-b border-linea px-5 py-3">
        <h2 id="ayuda-titulo" className="mr-auto text-lg font-semibold tracking-tight">
          {a.titulo}
        </h2>
        <button type="button" className="control px-2 text-xs" aria-label={a.cerrar} onClick={onCerrar}>
          <span aria-hidden="true">✕</span>
        </button>
      </div>
      <div className="grid gap-5 px-5 py-4 sm:grid-cols-2">
        <section className="sm:col-span-2">
          <p className="text-secundario">{a.colores}</p>
          <ul className="mt-2 flex flex-col gap-1" data-leyenda-estados="">
            {ESTADOS.flatMap((estado) =>
              estado === "atribuido"
                ? [
                    <li key="atribuido-estado" className="flex items-center gap-2" data-leyenda-atribuido="estado">
                      <MarcaAtribuido />
                      {t.atribucion.leyendaEstado}
                    </li>,
                    <li key="atribuido-persona" className="flex items-center gap-2" data-leyenda-atribuido="persona">
                      <MarcaAtribuido variante={{ bandera: null, persona: true }} />
                      {t.atribucion.leyendaPersona}
                    </li>,
                  ]
                : [
                    <li key={estado} className="flex items-center gap-2">
                      <Simbolo estado={estado} />
                      {t.estado[estado]}
                    </li>,
                  ],
            )}
          </ul>
          <p className="mt-2 text-secundario" data-leyenda-bandera="">
            {t.atribucion.bandera}
          </p>
          <p className="mt-2 flex items-start gap-2 text-secundario" data-leyenda-aproximado="">
            <span className="flex shrink-0 gap-0.5 pt-0.5">
              <Simbolo estado="notificado" aproximado />
              <Simbolo estado="confirmado" aproximado />
            </span>
            {a.aproximado}
          </p>
        </section>
        <ul className="flex flex-col gap-2 text-secundario sm:col-span-2">
          {[a.periodo, a.ahora, a.areas, a.lineas, a.numeros, a.pila, a.pulsos, a.reciente, a.novedad, a.ucrania].map(
            (texto) => (
              <li key={texto}>{texto}</li>
            ),
          )}
          <li className="flex items-start gap-2">
            <span className="pt-1">
              <MarcaRusia />
            </span>
            {a.rusia}
          </li>
          <li className="flex items-start gap-2">
            <span className="flex gap-1 pt-1">
              <MarcaImpacto parte={false} />
              <MarcaImpacto parte />
            </span>
            {a.impactos}
          </li>
          <li className="flex items-start gap-2">
            <span className="flex gap-1 pt-1">
              <MarcaFoco />
              <MarcaFoco color={PALETA.guerraClaro} />
            </span>
            {a.foco}
          </li>
          <li className="flex items-start gap-2">
            <span className="pt-1">
              <MarcaAviso />
            </span>
            {a.directo}
          </li>
          {(
            [
              [null, t.satelite.ayudaSubcapas],
              [<MarcaCorredor key="c" />, t.satelite.ayudaCorredores],
              [<MarcaLuz key="l" />, t.satelite.ayudaLuz],
              [<MarcaAlumbrado key="a" />, t.satelite.ayudaAlumbrado],
              [<MarcaSatelite key="s" />, t.satelite.ayudaSatelite],
            ] as const
          ).map(([marca, texto]) => (
            <li key={texto} className="flex items-start gap-2">
              <span className="pt-1">{marca}</span>
              {texto}
            </li>
          ))}
        </ul>
        <section className="sm:col-span-2">
          <h3 className="font-medium">{a.atajos}</h3>
          <dl className="mt-2 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5">
            {ATAJOS.map(([nombre, accion]) => (
              <div key={nombre} className="contents">
                <dt>
                  <kbd className="tecla">{tecla(nombre)}</kbd>
                </dt>
                <dd className="text-secundario">{a.acciones[accion]}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </dialog>
  );
}
