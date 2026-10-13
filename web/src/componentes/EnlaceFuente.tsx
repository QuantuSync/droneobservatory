import type { ReactNode } from "react";

import type { Fuente } from "../datos/tipos.ts";
import { fecha } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";

/**
 * El enlace de una fuente, igual en toda la web. Con copia en Internet Archive, al lado del
 * original sale «copia archivada». Si el original está caído, el enlace principal pasa a ser la
 * copia, se dice que el original ya no está y el original sigue a la vista, aparte. Caído y sin
 * copia, el original con el aviso. Los enlaces de las notas van en bloque en línea: en una pantalla
 * táctil su zona de 44 px ocupa sitio en la línea y nada la tapa.
 */
export function EnlaceFuente({
  t,
  fuente,
  className,
  children,
}: {
  t: Textos;
  fuente: Pick<Fuente, "enlace" | "copia_archivada" | "enlace_caido">;
  className?: string | undefined;
  children: ReactNode;
}) {
  const copia = fuente.copia_archivada;
  const aviso = t.ficha.enlaceExterno;
  const noValido = t.ficha.enlaceNoValido;
  const del = copia === undefined ? "" : fecha(new Date(copia.fecha));
  if (fuente.enlace_caido === true && copia !== undefined) {
    return (
      <>
        <EnlaceExterno enlace={copia.enlace} aviso={aviso} avisoNoValido={noValido} {...(className === undefined ? {} : { className })}>
          {children}
        </EnlaceExterno>{" "}
        <span className="text-xs text-secundario" data-copia-principal="">
          ({t.ficha.copiaArchivadaDel(del)}; {t.ficha.originalCaido}:{" "}
          <EnlaceExterno enlace={fuente.enlace} aviso={aviso} avisoNoValido={noValido} className="inline-block">
            {t.ficha.enlaceOriginal}
          </EnlaceExterno>
          )
        </span>
      </>
    );
  }
  return (
    <>
      <EnlaceExterno enlace={fuente.enlace} aviso={aviso} avisoNoValido={noValido} {...(className === undefined ? {} : { className })}>
        {children}
      </EnlaceExterno>
      {copia !== undefined && (
        <>
          {" "}
          <span className="text-xs" data-copia-archivada="">
            ·{" "}
            <EnlaceExterno
              enlace={copia.enlace}
              aviso={`${t.ficha.copiaArchivadaDel(del)}, ${aviso}`}
              avisoNoValido={noValido}
              className="inline-block"
            >
              {t.ficha.copiaArchivada}
            </EnlaceExterno>
          </span>
        </>
      )}
      {fuente.enlace_caido === true && copia === undefined && (
        <span className="text-xs text-secundario" data-enlace-caido="">
          {" "}
          ({t.ficha.caidoSinCopia})
        </span>
      )}
    </>
  );
}
