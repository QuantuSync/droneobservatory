import { fechaHora } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { frescura, horasDesde } from "../tiempo/frescura.ts";
import type { EstadoFrescura } from "../tiempo/frescura.ts";

interface Props {
  t: Textos;
  /** Última actualización de los datos, o null si no se han podido cargar. */
  actualizado: string | null;
  /** Hora actual; null hasta que la página está en el navegador. */
  ahora: Date | null;
}

const COLOR_PUNTO: Record<EstadoFrescura, string> = {
  al_dia: "bg-confirmado",
  con_retraso: "bg-notificado",
  desactualizado: "bg-atribuido",
};

/**
 * Barra de estado: la fecha de la última actualización y, con la hora del navegador, si
 * los datos están al día, con retraso o desactualizados. El punto nunca es verde sin
 * haberlo comprobado, y el estado va también escrito.
 */
export function BarraEstado({ t, actualizado, ahora }: Props) {
  if (actualizado === null) {
    return (
      <p className="entre-lineas mono flex items-center gap-2 px-4 py-1 text-xs text-secundario">
        <span aria-hidden="true" className="size-2 rounded-full bg-atribuido" />
        {t.estadoDatos.sinDatos}
      </p>
    );
  }
  const estado = ahora === null ? null : frescura(actualizado, ahora);
  const horas = ahora === null ? null : Math.max(0, Math.floor(horasDesde(actualizado, ahora)));
  return (
    <p
      className="entre-lineas mono flex min-h-[2.625rem] flex-wrap items-center gap-x-2 px-4 py-1 text-xs text-secundario sm:min-h-0"
      data-frescura={estado ?? "sin_comprobar"}
    >
      <span
        aria-hidden="true"
        className={`size-2 rounded-full ${estado === null ? "bg-linea" : COLOR_PUNTO[estado]}`}
      />
      <span>
        {t.estadoDatos.actualizado} {fechaHora(actualizado)}
      </span>
      {estado !== null && horas !== null && (
        <span className="text-texto">
          · {t.estadoDatos.etiqueta[estado]} ({t.estadoDatos.antiguedad(horas)})
        </span>
      )}
    </p>
  );
}
