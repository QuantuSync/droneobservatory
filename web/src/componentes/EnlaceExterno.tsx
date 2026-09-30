import type { ReactNode } from "react";

import { enlaceSeguro } from "../seguridad/enlaces.ts";

interface Props {
  /** Dirección tal como viene de los datos; solo se enlaza si es http o https. */
  enlace: string;
  /** Texto para lectores de pantalla: «enlace externo, se abre en otra pestaña». */
  aviso: string;
  /** Texto que sustituye al aviso cuando la dirección se descarta. */
  avisoNoValido: string;
  className?: string;
  children: ReactNode;
}

/**
 * Enlace a un sitio ajeno. Se abre en otra pestaña sin dar acceso a esta ni enviar la
 * página de origen, y lleva una marca visible de enlace externo. Una dirección que no es
 * http ni https se muestra como texto, sin enlace.
 */
export function EnlaceExterno({ enlace, aviso, avisoNoValido, className, children }: Props) {
  const destino = enlaceSeguro(enlace);
  if (destino === null) {
    return (
      <span className={className}>
        {children} <span className="text-secundario">({avisoNoValido})</span>
      </span>
    );
  }
  return (
    <a
      href={destino}
      target="_blank"
      rel="noopener noreferrer"
      className={`enlace ${className ?? ""}`}
    >
      {children}
      <span aria-hidden="true" className="ml-1 text-dorado">
        ↗
      </span>
      <span className="sr-only"> ({aviso})</span>
    </a>
  );
}
