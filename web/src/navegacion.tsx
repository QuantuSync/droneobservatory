// Navegación de una web de una sola pantalla: la dirección solo dice el idioma y la ficha
// abierta, así que basta con leerla, cambiarla con el historial del navegador y enterarse
// cuando el usuario vuelve atrás.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";

interface Navegacion {
  ruta: string;
  navegar: (ruta: string) => void;
}

const Contexto = createContext<Navegacion>({ ruta: "/", navegar: () => undefined });

interface PropsProveedor {
  /** Ruta con la que se pinta por primera vez: la del prerenderizado o la del navegador. */
  inicial: string;
  children: ReactNode;
}

export function ProveedorDeRuta({ inicial, children }: PropsProveedor) {
  const [ruta, setRuta] = useState(inicial);

  useEffect(() => {
    const alVolver = () => setRuta(window.location.pathname);
    window.addEventListener("popstate", alVolver);
    return () => window.removeEventListener("popstate", alVolver);
  }, []);

  const navegar = useCallback((nueva: string) => {
    if (nueva !== window.location.pathname) window.history.pushState(null, "", nueva);
    setRuta(nueva);
  }, []);

  const valor = useMemo(() => ({ ruta, navegar }), [ruta, navegar]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useNavegacion(): Navegacion {
  return useContext(Contexto);
}

interface PropsEnlace extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  /** Ruta de esta misma web. */
  a: string;
  children: ReactNode;
}

/** Enlace a otra ruta de la web: cambia la dirección sin recargar la página. */
export function Enlace({ a, children, onClick, ...resto }: PropsEnlace) {
  const { navegar } = useNavegacion();
  function alPulsar(evento: MouseEvent<HTMLAnchorElement>) {
    onClick?.(evento);
    // Con una tecla modificadora o el botón central, el navegador abre otra pestaña.
    const conModificador = evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey;
    if (evento.defaultPrevented || evento.button !== 0 || conModificador) return;
    evento.preventDefault();
    navegar(a);
  }
  return (
    <a href={a} onClick={alPulsar} {...resto}>
      {children}
    </a>
  );
}
