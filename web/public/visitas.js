// Contador de visitas (docs/visitas.md). Envía cada página vista al contador propio del
// observatorio, GoatCounter en https://stats.droneobservatory.eu (servidor en la UE), con lo mismo
// que su script oficial count.js: la dirección de la página sin la búsqueda (los filtros nunca
// cuentan), su título, la web de procedencia, el tamaño de pantalla y si el navegador lo maneja un
// programa. Sin cookies (credentials: "omit") y sin nada guardado en el navegador. GoatCounter no
// guarda la dirección IP.
//
// - Solo en producción (droneobservatory.eu): ni en las vistas previas de Vercel ni en local.
// - En el mapa, que es una sola página, cada dirección nueva cuenta una vez por carga: abrir la
//   ficha de un incidente cuenta como vista de /EODI-…; volver al mapa o cambiar filtros, no.
// - Excluir un navegador: abrir https://droneobservatory.eu/#toggle-goatcounter (el mecanismo de
//   GoatCounter: guarda «skipgc» = «t» en el almacenamiento local y deja de contar; otra vez, vuelve).
// - Si el contador no responde, la web no se entera: el envío no se espera y los errores se callan.
(() => {
  const CONTADOR = "https://stats.droneobservatory.eu/count";
  const PRODUCCION = ["droneobservatory.eu", "www.droneobservatory.eu"];
  const EXCLUIR = "skipgc";
  // Solo para las pruebas automáticas: cuenta fuera de producción (el envío se intercepta).
  const PRUEBA = "eodi.visitas.prueba";
  const contadas = new Set();
  let primera = true;

  const leer = (clave) => {
    try {
      return window.localStorage.getItem(clave);
    } catch {
      return null;
    }
  };

  // El mismo enlace que GoatCounter: #toggle-goatcounter activa o desactiva este navegador.
  if (window.location.hash === "#toggle-goatcounter") {
    try {
      const fuera = leer(EXCLUIR) === "t";
      if (fuera) window.localStorage.removeItem(EXCLUIR);
      else window.localStorage.setItem(EXCLUIR, "t");
      window.alert(
        fuera
          ? "Este navegador vuelve a contar en las visitas. / This browser is counted again."
          : "Este navegador ya no cuenta en las visitas. / This browser is no longer counted.",
      );
    } catch {
      // Sin almacenamiento local no se puede excluir: no pasa nada más.
    }
  }

  // Los mismos indicios de navegador automático que count.js (GoatCounter los descarta).
  const automatico = () => {
    const w = window;
    if (w.callPhantom || w._phantom || w.phantom) return 150;
    if (w.__nightmare) return 151;
    if (document.__selenium_unwrapped || document.__webdriver_evaluate || document.__driver_evaluate)
      return 152;
    if (navigator.webdriver) return 153;
    return 0;
  };

  const sePuede = () => {
    if (leer(EXCLUIR) === "t") return false;
    if (document.visibilityState === "prerender") return false;
    if (window.top !== window.self) return false;
    return PRODUCCION.includes(window.location.hostname) || leer(PRUEBA) === "1";
  };

  // De la búsqueda solo las campañas (utm_*, ref): nunca los filtros del mapa.
  const campana = () => {
    const parametros = new URLSearchParams(window.location.search);
    const quedan = new URLSearchParams();
    for (const [clave, valor] of parametros) {
      if (clave.startsWith("utm_") || clave === "ref") quedan.append(clave, valor);
    }
    const texto = quedan.toString();
    return texto ? `?${texto}` : "";
  };

  const enviar = (ruta) => {
    const datos = new URLSearchParams({
      p: ruta,
      t: document.title,
      // La procedencia solo con la primera página de la carga: las siguientes son de la propia web.
      r: primera ? document.referrer : "",
      s: [window.screen.width, window.screen.height, window.devicePixelRatio || 1].join(","),
      b: String(automatico()),
      q: primera ? campana() : "",
      rnd: Math.random().toString(36).slice(2),
    });
    primera = false;
    try {
      fetch(`${CONTADOR}?${datos}`, {
        method: "POST",
        mode: "no-cors",
        credentials: "omit",
        keepalive: true,
      }).catch(() => {});
    } catch {
      // Un navegador sin fetch: la visita no cuenta y la página sigue igual.
    }
  };

  const contar = () => {
    try {
      if (!sePuede()) return;
      const ruta = window.location.pathname;
      if (contadas.has(ruta)) return;
      contadas.add(ruta);
      // Un momento para que el mapa ponga el título de la ficha.
      window.setTimeout(() => enviar(ruta), primera ? 0 : 400);
    } catch {
      // Nada de esto puede romper la página.
    }
  };

  // El mapa avisa de cada cambio de dirección (src/visitas.ts); el botón «atrás» también.
  window.eodiVisitas = { contar };
  window.addEventListener("popstate", contar);
  contar();
})();
