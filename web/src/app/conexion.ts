// Si el navegador tiene conexión (navigator.onLine y los eventos online/offline). Sin conexión, la
// barra de estado dice «Sin conexión · datos de las …» en lugar del indicador de datos al día; al
// volver, la web vuelve a pedir los datos (App.tsx).

import { useSyncExternalStore } from "react";

function suscribir(oyente: () => void): () => void {
  window.addEventListener("online", oyente);
  window.addEventListener("offline", oyente);
  return () => {
    window.removeEventListener("online", oyente);
    window.removeEventListener("offline", oyente);
  };
}

/** true con conexión; en el servidor (prerenderizado), siempre true. */
export function useEnLinea(): boolean {
  return useSyncExternalStore(
    suscribir,
    () => navigator.onLine,
    () => true,
  );
}
