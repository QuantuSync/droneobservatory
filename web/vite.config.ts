/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import type { ViteReactSSGOptions } from "vite-react-ssg";

import { aplicarCabecera, paginaDePortada } from "./src/cabecera.ts";
import { analizarRuta } from "./src/rutas.ts";
import { terminarPaginas } from "./scripts/paginas.ts";

const ssgOptions: ViteReactSSGOptions = {
  entry: "src/main.tsx",
  // /en se publica como en/index.html, junto a las páginas de cada incidente en inglés.
  dirStyle: "nested",
  // Sin CSS crítico en línea: la política de seguridad solo admite estilos de este sitio.
  beastiesOptions: false,
  // Las dos portadas se pintan de una en una: cada una fija su ruta antes de pintarse.
  concurrency: 1,
  onPageRendered: (ruta, html) =>
    aplicarCabecera(html, paginaDePortada(analizarRuta(ruta).idioma)),
  onFinished: terminarPaginas,
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  ssgOptions,
  worker: { format: "es" },
  build: { target: "es2022", sourcemap: false },
  test: {
    environment: "node",
    include: ["tests/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
