// Constantes del encuadre que usa la pantalla fuera del mapa. Van aparte de Mapa.tsx
// porque importar cualquier valor de él arrastraría MapLibre al paquete inicial.

/** Zoom al que se ve un país entero cuando el incidente no tiene punto. */
export const ZOOM_DE_PAIS = 4.5;

/** Tope de zoom al encuadrar lo que queda tras «Aplicar» los filtros (el de abrir una ficha). */
export const ZOOM_MAXIMO_AL_APLICAR = 8;
