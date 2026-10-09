import "@fontsource-variable/jetbrains-mono/wght.css";
import "@fontsource-variable/onest/wght.css";
import { ViteReactSSG } from "vite-react-ssg/single-page";

import { App } from "./App.tsx";
import "./estilos.css";
import { tolerarCamposNuevos } from "./datos/validar.ts";
import { ProveedorDeRuta } from "./navegacion.tsx";
import { IDIOMAS, rutaDeIdioma } from "./sitio.ts";

// Una sola pantalla: la aplicación lee de la dirección el idioma (/ o /en) y, si la hay,
// la ficha abierta (/EODI-…). Se prerenderizan las dos portadas; las páginas de cada
// incidente salen de ellas al final del build.
let rutaDelPrerenderizado = "/";

// En el navegador, un campo nuevo en los datos no invalida un fichero (datos/validar.ts).
tolerarCamposNuevos();

function Raiz() {
  const enNavegador = typeof window !== "undefined";
  const inicial = enNavegador ? window.location.pathname : rutaDelPrerenderizado;
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
