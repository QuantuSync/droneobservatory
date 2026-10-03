// Umbrales de la detección en directo de cierres de aeropuerto, tal como los explica la
// metodología en los dos idiomas. Son los del servicio del servidor (recogida/directo.py),
// ajustados reproduciendo días reales con las trazas guardadas.

export const UMBRALES_DIRECTO = {
  /** Segundos de cada ciclo de consulta. */
  cicloS: "80",
  /** Minutos de retraso con que se cuenta cada movimiento, para que quede completo. */
  retrasoMin: "4",
  /** Movimientos esperados que tienen que faltar como mínimo. */
  esperadosMin: "12",
  /** Proporción máxima de lo esperado que se ve durante el hueco. */
  fraccionVistos: "10 %",
  /** Movimientos esperados por minuto de hueco como mínimo. */
  ritmo: "0,5",
  /** Minutos que tiene que mantenerse la señal. */
  persistenciaMin: "4",
  /** Movimientos que marcan la vuelta del tráfico. */
  reanudacion: "2",
  /** Horas que un aviso reanudado sigue en el mapa. */
  permanenciaH: "12",
} as const;
