import "@fontsource/saira-condensed/latin-600.css";
import "@fontsource/saira-condensed/latin-700.css";
import "@fontsource/saira-condensed/latin-ext-600.css";
import "@fontsource/saira-condensed/latin-ext-700.css";
import "@fontsource-variable/inter/wght.css";
import { ViteReactSSG } from "vite-react-ssg/single-page";

import { App } from "./App.tsx";
import "./estilos.css";
import { ProveedorDeRuta } from "./navegacion.tsx";
import { IDIOMAS, rutaDeIdioma } from "./sitio.ts";

// Una sola pantalla: la aplicación lee de la dirección el idioma (/ o /en) y, si la hay,
// la ficha abierta (/EODI-…). Se prerenderizan las dos portadas; las páginas de cada
// incidente salen de ellas al final del build.
let rutaDelPrerenderizado = "/";

function Raiz() {
  const inicial = typeof window === "undefined" ? rutaDelPrerenderizado : window.location.pathname;
  return (
    <ProveedorDeRuta inicial={inicial}>
      <App />
    </ProveedorDeRuta>
  );
}

export const createRoot = ViteReactSSG(<Raiz />, ({ routePath }) => {
  if (routePath !== undefined) rutaDelPrerenderizado = routePath;
});

/** Rutas que se prerenderizan: la portada de cada idioma. */
export function includedRoutes(): string[] {
  return IDIOMAS.map(rutaDeIdioma);
}
