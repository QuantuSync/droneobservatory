import { useEffect, useState } from "react";

import { EVENTO_VERSION_NUEVA } from "../app/registro.ts";
import type { Textos } from "../i18n/index.ts";

/**
 * «Hay una versión nueva · Actualizar»: un aviso discreto abajo, solo cuando el service worker dice
 * que la página que se ve es de un código anterior (app/registro.ts). «Actualizar» recarga la
 * página; sin pulsarlo, la siguiente carga ya es la nueva. No tapa el mapa ni lo mueve.
 */
export function AvisoVersion({ t }: { t: Textos }) {
  const [hay, setHay] = useState(false);
  useEffect(() => {
    const alAvisar = () => setHay(true);
    window.addEventListener(EVENTO_VERSION_NUEVA, alAvisar);
    return () => window.removeEventListener(EVENTO_VERSION_NUEVA, alAvisar);
  }, []);
  if (!hay) return null;
  return (
    <div
      role="status"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-[calc(env(safe-area-inset-bottom)+4.5rem)]"
      data-version-nueva=""
    >
      <p className="flotante pointer-events-auto flex items-center gap-2 px-3 py-1.5 text-xs text-texto">
        {t.app.versionNueva} ·
        <button
          type="button"
          className="control min-h-8 rounded-sm px-2 text-xs tactil:min-h-11"
          onClick={() => window.location.reload()}
        >
          {t.app.actualizar}
        </button>
      </p>
    </div>
  );
}
