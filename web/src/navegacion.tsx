// Navegación de una web de una sola pantalla: la ruta dice el idioma y la ficha abierta, y
// la búsqueda (?…) los filtros. Se llevan con el historial del navegador, sin biblioteca.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";

interface Navegacion {
  ruta: string;
  busqueda: string;
  /** Va a otra ruta y conserva los filtros de la búsqueda. */
  navegar: (ruta: string) => void;
  /**
   * Cambia la búsqueda (filtros y periodo). Con `anadir`, deja una entrada en el historial
   * para que el botón atrás lo deshaga; si no, reemplaza la actual.
   */
  cambiarBusqueda: (busqueda: string, anadir?: boolean) => void;
}

const Contexto = createContext<Navegacion>({
  ruta: "/",
  busqueda: "",
  navegar: () => undefined,
  cambiarBusqueda: () => undefined,
});

interface PropsProveedor {
  /** Ruta con la que se pinta por primera vez: la del prerenderizado o la del navegador. */
  inicial: string;
  /** Búsqueda inicial; en el prerenderizado no hay. */
  busquedaInicial?: string;
  children: ReactNode;
}

export function ProveedorDeRuta({ inicial, busquedaInicial = "", children }: PropsProveedor) {
  const [ruta, setRuta] = useState(inicial);
  const [busqueda, setBusqueda] = useState(busquedaInicial);

  // Los filtros de la dirección solo existen en el navegador: el HTML prerenderizado va sin
  // ellos y la primera pintura también, para que coincidan; se leen justo después.
  useEffect(() => {
    if (window.location.search !== "") setBusqueda(window.location.search);
  }, []);

  useEffect(() => {
    const alVolver = () => {
      setRuta(window.location.pathname);
      setBusqueda(window.location.search);
    };
    window.addEventListener("popstate", alVolver);
    return () => window.removeEventListener("popstate", alVolver);
  }, []);

  const navegar = useCallback(
    (nueva: string) => {
      const destino = `${nueva}${busqueda}`;
      if (destino !== `${window.location.pathname}${window.location.search}`) {
        window.history.pushState(null, "", destino);
      }
      setRuta(nueva);
    },
    [busqueda],
  );

  const cambiarBusqueda = useCallback((nueva: string, anadir = false) => {
    const destino = `${window.location.pathname}${nueva}`;
    if (anadir && nueva !== window.location.search) window.history.pushState(null, "", destino);
    else window.history.replaceState(null, "", destino);
    setBusqueda(nueva);
  }, []);

  const valor = useMemo(
    () => ({ ruta, busqueda, navegar, cambiarBusqueda }),
    [ruta, busqueda, navegar, cambiarBusqueda],
  );
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

/** Enlace a otra ruta de la web: cambia la dirección sin recargar y conserva los filtros. */
export function Enlace({ a, children, onClick, ...resto }: PropsEnlace) {
  const { navegar, busqueda } = useNavegacion();
  function alPulsar(evento: MouseEvent<HTMLAnchorElement>) {
    onClick?.(evento);
    // Con una tecla modificadora o el botón central, el navegador abre otra pestaña.
    const conModificador = evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey;
    if (evento.defaultPrevented || evento.button !== 0 || conModificador) return;
    evento.preventDefault();
    navegar(a);
  }
  return (
    <a href={`${a}${busqueda}`} onClick={alPulsar} {...resto}>
      {children}
    </a>
  );
}
