import { useId, useState } from "react";

import type { EstadoFuente, EstadoSistema, ResultadoRecogida } from "../datos/tipos.ts";
import { fechaHora, hora } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { frescura, horasDesde, referenciaDeFrescura } from "../tiempo/frescura.ts";
import type { EstadoFrescura } from "../tiempo/frescura.ts";

interface Props {
  t: Textos;
  /** Último cambio de los datos publicados, o null si no se han podido cargar. */
  actualizado: string | null;
  /** estado.json de la recogida; null mientras no esté publicado o no valide. */
  sistema: EstadoSistema | null;
  /** Hora actual; null hasta que la página está en el navegador. */
  ahora: Date | null;
}

const COLOR_PUNTO: Record<EstadoFrescura, string> = {
  al_dia: "bg-confirmado",
  con_retraso: "bg-notificado",
  desactualizado: "bg-atribuido",
};

const COLOR_RESULTADO: Record<ResultadoRecogida, string> = {
  correcta: "bg-confirmado",
  con_avisos: "bg-notificado",
  fallida: "bg-atribuido",
};

const COLOR_FUENTE: Record<EstadoFuente, string> = {
  leida: "bg-confirmado",
  con_aviso: "bg-notificado",
  no_leida: "bg-atribuido",
};

function Punto({ color }: { color: string }) {
  return <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${color}`} />;
}

/** Franja con la última recogida, su resultado, la siguiente y el estado de cada fuente. */
function FranjaSistema({ t, sistema, id }: { t: Textos; sistema: EstadoSistema; id: string }) {
  const e = t.estadoDatos;
  return (
    <div id={id} className="mono border-b border-borde px-4 py-2 text-xs text-secundario">
      <p className="flex flex-wrap items-center gap-x-2">
        <Punto color={COLOR_RESULTADO[sistema.resultado]} />
        <span>
          {e.ultimaRecogida}: {fechaHora(sistema.inicio)} – {hora(new Date(sistema.fin))} UTC
        </span>
        <span className="text-texto">· {e.resultado[sistema.resultado]}</span>
        <span>
          · {e.siguiente}: {fechaHora(sistema.siguiente)}
        </span>
      </p>
      <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1">
        {sistema.fuentes.map((fuente) => (
          <li key={fuente.id} className="flex items-center gap-1.5">
            <Punto color={COLOR_FUENTE[fuente.estado]} />
            <span className="text-texto">{e.fuente[fuente.id]}</span>
            <span>
              {e.estadoFuente[fuente.estado]} · {e.ultimoDato}{" "}
              {fuente.ultimo_dato === null ? e.sinUltimoDato : fechaHora(fuente.ultimo_dato)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Barra de estado: cuándo se actualizaron los datos y, con la hora del navegador, si están
 * al día, con retraso o desactualizados. Con estado.json publicado, la antigüedad se mide
 * desde la última recogida correcta y se puede desplegar el estado de cada fuente. El
 * punto nunca es verde sin haberlo comprobado, y el estado va también escrito.
 */
export function BarraEstado({ t, actualizado, sistema, ahora }: Props) {
  const [abierta, setAbierta] = useState(false);
  const idFranja = useId();
  const referencia = referenciaDeFrescura(sistema, actualizado);
  if (referencia === null) {
    return (
      <p className="entre-lineas mono flex items-center gap-2 px-4 py-1 text-xs text-secundario">
        <Punto color="bg-atribuido" />
        {sistema === null ? t.estadoDatos.sinDatos : t.estadoDatos.nuncaCorrecta.toUpperCase()}
      </p>
    );
  }
  const estado = ahora === null ? null : frescura(referencia, ahora);
  const horas = ahora === null ? null : Math.max(0, Math.floor(horasDesde(referencia, ahora)));
  return (
    <div className="entre-lineas">
      <div
        className="mono flex min-h-[2.625rem] flex-wrap items-center gap-x-2 px-4 py-1 text-xs text-secundario sm:min-h-0"
        data-frescura={estado ?? "sin_comprobar"}
        data-fuente-frescura={sistema === null ? "datos" : "recogida"}
      >
        <Punto color={estado === null ? "bg-linea" : COLOR_PUNTO[estado]} />
        <span>
          {t.estadoDatos.actualizado} {fechaHora(referencia)}
        </span>
        {estado !== null && horas !== null && (
          <span className="text-texto">
            · {t.estadoDatos.etiqueta[estado]} ({t.estadoDatos.antiguedad(horas)})
          </span>
        )}
        {sistema !== null && (
          <button
            type="button"
            className="ml-auto cursor-pointer uppercase tracking-wider text-dorado underline-offset-2 hover:underline"
            aria-expanded={abierta}
            aria-controls={idFranja}
            onClick={() => setAbierta(!abierta)}
          >
            {t.estadoDatos.sistema} {abierta ? "▴" : "▾"}
          </button>
        )}
      </div>
      {sistema !== null && abierta && <FranjaSistema t={t} sistema={sistema} id={idFranja} />}
    </div>
  );
}
