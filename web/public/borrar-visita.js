// Botón «Borrar mi última visita» de la página de privacidad (src/texto/servicio.ts). Borra del
// almacenamiento local del navegador la fecha de la última visita (src/estado/novedades.ts,
// CLAVE_VISITA) y el canal elegido en «Avisos» (src/avisos.ts, CLAVE_CANAL), y las copias que guarda
// la app (las cachés «eodi-…» del service worker, public/sw.js: páginas, código y datos ya vistos),
// y dice que se ha borrado. Sin este script, el botón no se ve y la página explica cómo borrarla desde el
// navegador. No envía nada a ningún sitio.
(() => {
  const CLAVE_VISITA = "eodi.ultima-visita";
  const CLAVE_CANAL = "eodi.avisos.canal";
  const boton = document.querySelector("[data-borrar-visita]");
  const estado = document.querySelector("[data-borrar-visita-estado]");
  if (!(boton instanceof HTMLButtonElement) || estado === null) return;
  boton.hidden = false;
  // Las cachés de la app: solo las de la web («eodi-…»). Sin Cache Storage (o sin service worker),
  // no hay nada que borrar.
  const borrarCaches = async () => {
    if (typeof caches === "undefined") return;
    const nombres = await caches.keys();
    await Promise.all(nombres.filter((n) => n.startsWith("eodi-")).map((n) => caches.delete(n)));
  };
  boton.addEventListener("click", () => {
    try {
      window.localStorage.removeItem(CLAVE_VISITA);
      window.localStorage.removeItem(CLAVE_CANAL);
      estado.textContent = boton.dataset.hecho ?? "";
    } catch {
      estado.textContent = boton.dataset.fallo ?? "";
    }
    borrarCaches().catch(() => {
      estado.textContent = boton.dataset.fallo ?? "";
    });
  });
})();
