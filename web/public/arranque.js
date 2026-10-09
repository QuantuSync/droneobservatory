// Arranque de la web: si el código o el estilo de la página (los ficheros de /assets/, con huella en
// el nombre) no llegan, se vuelven a pedir, con espera creciente. Pasa unos segundos tras cada
// publicación: el despliegue nuevo sirve ya la página que los nombra y la petición del fichero
// llega aún al anterior, que no lo tiene (404). Una hoja de estilo o un script clásico se piden de
// nuevo sin la caché del navegador. Un módulo no: el navegador recuerda su fallo mientras dure la
// página, así que se recarga la página. Tras cuatro esperas sin éxito, lo dice y ofrece
// «Reintentar». La web avisa con el evento «eodi:fallo-arranque» cuando lo que no llega es el
// código del mapa (src/datos/reintentos.ts, importarOAvisar).
// Este fichero no lleva huella: es el mismo en todos los despliegues. No envía nada a ningún sitio.
(() => {
  const ESPERAS_MS = [500, 1000, 2000, 4000];
  const CLAVE_RECARGAS = "eodi.recargas-arranque";
  // Las recargas cuentan juntas durante este rato; pasado, se empieza de cero.
  const VENTANA_MS = 120_000;
  const intentos = new Map();
  let recargando = false;
  let avisado = false;

  function avisar() {
    if (avisado) return;
    if (document.body === null) {
      document.addEventListener("DOMContentLoaded", avisar);
      return;
    }
    avisado = true;
    const ingles = document.documentElement.lang === "en";
    const caja = document.createElement("div");
    caja.className = "aviso-arranque";
    caja.setAttribute("role", "alert");
    caja.setAttribute("data-error-carga", "");
    const texto = document.createElement("p");
    texto.textContent = ingles
      ? "The website could not be loaded. Check the connection and try again."
      : "No se ha podido cargar la web. Comprueba la conexión y vuelve a intentarlo.";
    const boton = document.createElement("button");
    boton.type = "button";
    boton.textContent = ingles ? "Retry" : "Reintentar";
    boton.addEventListener("click", () => window.location.reload());
    caja.append(texto, boton);
    document.body.prepend(caja);
  }

  /** Recarga la página tras la espera que toca, o avisa si ya no quedan. */
  function recargar() {
    if (recargando) return;
    recargando = true;
    let hechas;
    try {
      const guardado = JSON.parse(window.sessionStorage.getItem(CLAVE_RECARGAS) ?? "null");
      const vigente = guardado !== null && Date.now() - guardado.desde < VENTANA_MS;
      hechas = vigente ? guardado : { n: 0, desde: Date.now() };
      if (hechas.n < ESPERAS_MS.length) {
        window.sessionStorage.setItem(CLAVE_RECARGAS, JSON.stringify({ n: hechas.n + 1, desde: hechas.desde }));
      }
    } catch {
      // Sin almacenamiento no se sabría cuántas van: mejor avisar que recargar sin fin.
      avisar();
      return;
    }
    if (hechas.n >= ESPERAS_MS.length) {
      avisar();
      return;
    }
    window.setTimeout(() => window.location.reload(), ESPERAS_MS[hechas.n]);
  }

  /** Pide otra vez una hoja de estilo o un script clásico, con otra dirección (sin caché). */
  function pedirOtraVez(elemento, atributo) {
    const base = elemento.getAttribute(atributo).split("?")[0];
    const hechos = intentos.get(base) ?? 0;
    if (hechos >= ESPERAS_MS.length) {
      recargar();
      return;
    }
    intentos.set(base, hechos + 1);
    window.setTimeout(() => {
      const otro = document.createElement(elemento.tagName);
      for (const { name, value } of Array.from(elemento.attributes)) otro.setAttribute(name, value);
      otro.setAttribute(atributo, `${base}?reintento=${hechos + 1}`);
      elemento.replaceWith(otro);
    }, ESPERAS_MS[hechos]);
  }

  window.addEventListener(
    "error",
    (evento) => {
      const elemento = evento.target;
      if (elemento instanceof HTMLScriptElement && elemento.src.includes("/assets/")) {
        if (elemento.type === "module") recargar();
        else pedirOtraVez(elemento, "src");
      } else if (
        elemento instanceof HTMLLinkElement &&
        elemento.rel === "stylesheet" &&
        elemento.href.includes("/assets/")
      ) {
        pedirOtraVez(elemento, "href");
      }
    },
    true,
  );
  window.addEventListener("eodi:fallo-arranque", recargar);
})();
