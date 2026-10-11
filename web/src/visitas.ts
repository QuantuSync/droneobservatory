// Aviso al contador de visitas (public/visitas.js, docs/visitas.md) de que el mapa ha cambiado de
// dirección: abrir la ficha de un incidente cuenta como vista de su página. Si el contador no está
// (bloqueado, sin cargar o fuera de producción), no hace nada.

interface ContadorDeVisitas {
  contar: () => void;
}

export function contarVista(): void {
  try {
    (window as { eodiVisitas?: ContadorDeVisitas }).eodiVisitas?.contar();
  } catch {
    // El contador nunca puede romper el mapa.
  }
}
