// Botón «Borrar mi última visita» de la página de privacidad (src/texto/servicio.ts). Borra del
// almacenamiento local del navegador la fecha de la última visita (src/estado/novedades.ts,
// CLAVE_VISITA) y dice que se ha borrado. Sin este script, el botón no se ve y la página explica
// cómo borrarla desde el navegador. No envía nada a ningún sitio.
(() => {
  const CLAVE_VISITA = "eodi.ultima-visita";
  const boton = document.querySelector("[data-borrar-visita]");
  const estado = document.querySelector("[data-borrar-visita-estado]");
  if (!(boton instanceof HTMLButtonElement) || estado === null) return;
  boton.hidden = false;
  boton.addEventListener("click", () => {
    try {
      window.localStorage.removeItem(CLAVE_VISITA);
      estado.textContent = boton.dataset.hecho ?? "";
    } catch {
      estado.textContent = boton.dataset.fallo ?? "";
    }
  });
})();
