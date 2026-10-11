import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import type {
  EstadoDirecto,
  EstadoFuente,
  EstadoSistema,
  ResultadoRecogida,
} from "../datos/tipos.ts";
import { fechaHora } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { frescura, referenciaDeFrescura } from "../tiempo/frescura.ts";
import type { EstadoFrescura } from "../tiempo/frescura.ts";
import { haceCuanto } from "./Feed.tsx";

const MS_POR_MINUTO = 60_000;

interface Props {
  t: Textos;
  /** Último cambio de los datos publicados, o null si no se han podido cargar. */
  actualizado: string | null;
  /** estado.json de la recogida; null mientras no esté publicado o no valide. */
  sistema: EstadoSistema | null;
  /** Hora actual; null hasta que la página está en el navegador. */
  ahora: Date | null;
  /** Solo «hace 26 min», sin «Actualizado»: para la barra del teléfono. */
  corta?: boolean;
  /** Hacia dónde se abre el detalle, bajo el botón. */
  alinear?: "izquierda" | "derecha";
}

const COLOR_PUNTO: Record<EstadoFrescura, string> = {
  al_dia: "bg-al-dia",
  con_retraso: "bg-notificado",
  desactualizado: "bg-atribuido",
};

const COLOR_TEXTO: Record<EstadoFrescura, string> = {
  al_dia: "text-al-dia",
  con_retraso: "text-notificado",
  desactualizado: "text-atribuido",
};

const COLOR_RESULTADO: Record<ResultadoRecogida, string> = {
  correcta: "bg-al-dia",
  con_avisos: "bg-notificado",
  fallida: "bg-atribuido",
};

const COLOR_DIRECTO: Record<EstadoDirecto, string> = {
  en_marcha: "bg-al-dia",
  con_respaldo: "bg-notificado",
  parado: "bg-atribuido",
};

const COLOR_FUENTE: Record<EstadoFuente, string> = {
  leida: "bg-al-dia",
  con_aviso: "bg-notificado",
  no_leida: "bg-atribuido",
};

function Punto({ color }: { color: string }) {
  return <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${color}`} />;
}

/** Minutos que faltan para la siguiente recogida (redondeando hacia arriba). */
export function minutosHasta(siguiente: string, ahora: Date): number {
  return Math.ceil((new Date(siguiente).getTime() - ahora.getTime()) / MS_POR_MINUTO);
}

/** Una fila del detalle: el rótulo en texto y la hora, sola, en la cifra monoespaciada. */
function Fila({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-secundario">{rotulo}</dt>
      <dd className="text-right text-texto">{children}</dd>
    </div>
  );
}

function Hora({ instante }: { instante: string }) {
  return <span className="mono">{fechaHora(instante)}</span>;
}

interface PropsDetalle {
  t: Textos;
  id: string;
  estado: EstadoFrescura | null;
  actualizado: string | null;
  sistema: EstadoSistema | null;
  ahora: Date | null;
}

/** Detalle desplegable: horas exactas, la siguiente recogida y el estado de cada fuente. */
function Detalle({ t, id, estado, actualizado, sistema, ahora }: PropsDetalle) {
  const e = t.estadoDatos;
  return (
    <div id={id} className="flex flex-col gap-2 text-xs">
      <dl className="flex flex-col gap-1">
        {estado !== null && <Fila rotulo={e.detalle}>{e.etiqueta[estado]}</Fila>}
        {actualizado !== null && (
          <Fila rotulo={e.datosPublicados}>
            <Hora instante={actualizado} />
          </Fila>
        )}
        {sistema !== null && (
          <>
            <Fila rotulo={e.ultimaRecogida}>
              <Hora instante={sistema.inicio} />
            </Fila>
            <Fila rotulo={e.resultadoRotulo}>
              <span className="inline-flex items-center gap-1.5">
                <Punto color={COLOR_RESULTADO[sistema.resultado]} />
                {e.resultado[sistema.resultado]}
              </span>
            </Fila>
            <Fila rotulo={e.siguienteRecogida}>
              {ahora === null ? (
                <Hora instante={sistema.siguiente} />
              ) : (
                e.siguienteEn(minutosHasta(sistema.siguiente, ahora))
              )}
            </Fila>
          </>
        )}
      </dl>
      {sistema !== null && (
        <div>
          <p className="mb-1 text-secundario">{e.fuentes}</p>
          {/* Cada fuente en dos líneas: nombre y estado, y debajo su último dato. */}
          <ul className="flex flex-col gap-1.5">
            {sistema.fuentes.map((fuente) => (
              <li key={fuente.id} className="grid grid-cols-[auto_1fr_auto] items-center gap-x-2">
                <Punto color={COLOR_FUENTE[fuente.estado]} />
                <span className="text-texto">{e.fuente[fuente.id]}</span>
                <span className="text-secundario">{e.estadoFuente[fuente.estado]}</span>
                <span className="col-start-2 col-end-4 text-secundario">
                  {fuente.ultimo_dato === null ? (
                    e.sinUltimoDato
                  ) : (
                    <span className="mono">{fechaHora(fuente.ultimo_dato)}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
          {sistema.directo !== undefined && (
            <div
              className="mt-1.5 grid grid-cols-[auto_1fr_auto] items-center gap-x-2"
              data-servicio-directo={sistema.directo.estado}
            >
              <Punto color={COLOR_DIRECTO[sistema.directo.estado]} />
              <span className="text-texto">{e.directo}</span>
              <span className="text-secundario">{e.estadoDirecto[sistema.directo.estado]}</span>
              <span className="col-start-2 col-end-4 text-secundario">
                {e.ultimoCiclo}:{" "}
                {sistema.directo.ultimo_ciclo_correcto === null ? (
                  e.sinUltimoDato
                ) : (
                  <span className="mono">{fechaHora(sistema.directo.ultimo_ciclo_correcto)}</span>
                )}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Estado de los datos en una línea corta: «Actualizado hace 42 min», con el color de la
 * antigüedad. Con estado.json publicado, la antigüedad se mide desde la última recogida
 * correcta. Al pulsarlo se abre el detalle (horas exactas, siguiente recogida y cada fuente)
 * bajo el botón; se cierra con Escape o pulsando fuera. El punto nunca es verde sin haberlo
 * comprobado, y el estado va también escrito en el detalle y para los lectores de pantalla.
 */
export function BarraEstado({
  t,
  actualizado,
  sistema,
  ahora,
  corta = false,
  alinear = "izquierda",
}: Props) {
  const [abierta, setAbierta] = useState(false);
  const idDetalle = useId();
  const caja = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierta) return undefined;
    const fuera = (evento: PointerEvent) => {
      if (!caja.current?.contains(evento.target as Node)) setAbierta(false);
    };
    const tecla = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") {
        evento.stopPropagation();
        setAbierta(false);
      }
    };
    document.addEventListener("pointerdown", fuera);
    window.addEventListener("keydown", tecla, true);
    return () => {
      document.removeEventListener("pointerdown", fuera);
      window.removeEventListener("keydown", tecla, true);
    };
  }, [abierta]);
  const referencia = referenciaDeFrescura(sistema, actualizado);
  if (referencia === null) {
    return (
      <p className="flex items-center gap-2 text-xs text-secundario">
        <Punto color="bg-atribuido" />
        {sistema === null ? t.estadoDatos.sinDatos : t.estadoDatos.nuncaCorrecta}
      </p>
    );
  }
  const estado = ahora === null ? null : frescura(referencia, ahora);
  const hace = ahora === null ? null : haceCuanto(t, referencia, ahora);
  return (
    <div
      ref={caja}
      className="relative"
      data-frescura={estado ?? "sin_comprobar"}
      data-fuente-frescura={sistema === null ? "datos" : "recogida"}
    >
      <button
        type="button"
        className={`flex cursor-pointer items-center gap-2 whitespace-nowrap rounded-sm px-1.5 text-left text-xs hover:bg-elevado ${
          corta ? "min-h-11" : "min-h-7"
        }`}
        aria-expanded={abierta}
        aria-controls={idDetalle}
        onClick={() => setAbierta(!abierta)}
      >
        <Punto color={estado === null ? "bg-linea" : COLOR_PUNTO[estado]} />
        <span className={estado === null ? "text-secundario" : COLOR_TEXTO[estado]}>
          {hace === null ? (
            t.estadoDatos.actualizado
          ) : corta ? (
            hace
          ) : (
            // Por debajo de 1440 px de ancho basta con «hace 42 min».
            <>
              <span className="max-[1439px]:hidden">{t.estadoDatos.actualizado}</span> {hace}
            </>
          )}
        </span>
        {estado !== null && <span className="sr-only">· {t.estadoDatos.etiqueta[estado]}</span>}
      </button>
      {abierta && (
        <div
          className={`flotante absolute top-full z-40 mt-1 tactil:mt-2 w-80 max-w-[calc(100vw-1.5rem)] p-3 ${
            alinear === "derecha" ? "right-0" : "left-0"
          }`}
        >
          <Detalle
            t={t}
            id={idDetalle}
            estado={estado}
            actualizado={actualizado}
            sistema={sistema}
            ahora={ahora}
          />
        </div>
      )}
    </div>
  );
}
