// Movimiento del mapa y de la interfaz: nada se anima si el sistema pide reducirlo.

export function movimientoReducido(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
