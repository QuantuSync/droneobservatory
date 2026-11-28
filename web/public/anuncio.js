// Ventana de los avisos del observatorio, en todas las páginas (el mapa y las páginas de texto).
// Todo lo de cada aviso está en los datos (public/anuncios.json), no aquí: su texto en los dos
// idiomas, la palabra que enlaza y adónde (el aviso completo en la página «Avisos», con su ancla) y
// desde cuándo y hasta cuándo sale la ventana (ventana.desde y ventana.hasta, en UTC). Pasada la
// hora de «hasta», no vuelve a salir sin que nadie toque nada. Un aviso sin «ventana» solo sale en la
// página «Avisos». Si hay varios vigentes, sale el primero de la lista (el más reciente) que este
// navegador no haya cerrado.
//
// - Se cierra con su botón, con Escape (con el foco en la ventana o en ningún sitio) y con un lector
//   de pantalla (es una región con nombre y el botón tiene el suyo). Cerrada, ese aviso no vuelve a
//   salir en ese navegador: su id queda en el almacenamiento local (eodi.anuncios.cerrados). Si el
//   navegador no deja guardar, se cierra solo en esa página.
// - No tapa el mapa: va en una esquina, sin fondo que bloquee, y por debajo de los paneles y las
//   hojas del mapa (estilos.css, .anuncio).
// - Nada en línea (la política de seguridad no lo admite): los elementos se crean uno a uno y los
//   estilos están en la hoja de la web.
// - Las pruebas automáticas la apagan con eodi.anuncios.ninguno = "1" en el almacenamiento local
//   (e2e/base.ts), salvo las que la prueban.
(() => {
  const DATOS = "/anuncios.json";
  const CERRADOS = "eodi.anuncios.cerrados";
  const NINGUNO = "eodi.anuncios.ninguno";
  const TEXTOS = {
    es: { region: "Aviso del observatorio", cerrar: "Cerrar el aviso" },
    en: { region: "Observatory notice", cerrar: "Close the notice" },
  };
  // setTimeout no admite esperas más largas (unos 24 días).
  const ESPERA_MAXIMA_MS = 2_147_483_647;

  const leer = (clave) => {
    try {
      return window.localStorage.getItem(clave);
    } catch {
      return null;
    }
  };

  const cerradosGuardados = () => {
    try {
      const lista = JSON.parse(leer(CERRADOS) ?? "[]");
      return Array.isArray(lista) ? lista.filter((id) => typeof id === "string") : [];
    } catch {
      return [];
    }
  };

  const guardarCerrado = (id) => {
    try {
      const lista = cerradosGuardados();
      if (!lista.includes(id)) lista.push(id);
      window.localStorage.setItem(CERRADOS, JSON.stringify(lista));
    } catch {
      // Modo privado o almacenamiento bloqueado: se cierra solo en esta página.
    }
  };

  const idiomaDe = (lang) => (typeof lang === "string" && lang.toLowerCase().startsWith("en") ? "en" : "es");

  const texto = (valor) => typeof valor === "string" && valor.length > 0;
  const enLosDos = (valor) => valor !== null && typeof valor === "object" && texto(valor.es) && texto(valor.en);

  /** Si un aviso tiene una ventana bien formada y vigente en ese instante (milisegundos). */
  const vigente = (anuncio, ahora) => {
    const v = anuncio !== null && typeof anuncio === "object" ? anuncio.ventana : undefined;
    if (v === null || typeof v !== "object") return false;
    if (!texto(anuncio.id) || !enLosDos(v.texto)) return false;
    if (v.enlace === null || typeof v.enlace !== "object" || !enLosDos(v.enlace.texto) || !enLosDos(v.enlace.ruta)) return false;
    const desde = Date.parse(v.desde);
    const hasta = Date.parse(v.hasta);
    if (Number.isNaN(desde) || Number.isNaN(hasta)) return false;
    return desde <= ahora && ahora < hasta;
  };

  /** El aviso que toca enseñar: el primero vigente y no cerrado, o null. */
  const elegir = (datos, ahora, cerrados) => {
    const lista = datos !== null && typeof datos === "object" && Array.isArray(datos.anuncios) ? datos.anuncios : [];
    return lista.find((a) => vigente(a, ahora) && !cerrados.includes(a.id)) ?? null;
  };

  /** El texto partido en lo de antes, la palabra del enlace (la última vez que sale) y lo de después. */
  const partir = (frase, palabra) => {
    const donde = frase.lastIndexOf(palabra);
    if (donde < 0) return [`${frase} `, palabra, ""];
    return [frase.slice(0, donde), palabra, frase.slice(donde + palabra.length)];
  };

  let caja = null;
  let actual = null;
  let reloj = null;

  const rellenar = () => {
    if (caja === null || actual === null) return;
    const idioma = idiomaDe(document.documentElement.lang);
    const v = actual.ventana;
    const [antes, palabra, despues] = partir(v.texto[idioma], v.enlace.texto[idioma]);
    caja.lang = idioma;
    caja.setAttribute("aria-label", TEXTOS[idioma].region);
    const parrafo = document.createElement("p");
    parrafo.className = "anuncio-texto";
    const enlace = document.createElement("a");
    enlace.href = v.enlace.ruta[idioma];
    enlace.textContent = palabra;
    parrafo.append(antes, enlace, despues);
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "anuncio-cerrar";
    boton.setAttribute("aria-label", TEXTOS[idioma].cerrar);
    boton.setAttribute("data-anuncio-cerrar", "");
    const aspa = document.createElement("span");
    aspa.setAttribute("aria-hidden", "true");
    aspa.textContent = "×";
    boton.append(aspa);
    boton.addEventListener("click", () => cerrar(true));
    caja.replaceChildren(parrafo, boton);
  };

  const quitar = () => {
    if (caja === null) return;
    const teniaFoco = caja.contains(document.activeElement);
    caja.remove();
    caja = null;
    actual = null;
    if (reloj !== null) window.clearTimeout(reloj);
    reloj = null;
    // El foco no se pierde: va al contenido principal (el mapa, si lo hay), sin mover nada.
    if (teniaFoco) {
      const destino = document.getElementById("mapa") ?? document.querySelector("main, h1");
      if (destino instanceof HTMLElement) {
        if (!destino.hasAttribute("tabindex")) destino.setAttribute("tabindex", "-1");
        destino.focus({ preventScroll: true });
      }
    }
  };

  function cerrar(guardar) {
    if (actual !== null && guardar) guardarCerrado(actual.id);
    quitar();
  }

  const alPulsar = (evento) => {
    if (evento.key !== "Escape" || caja === null) return;
    const foco = document.activeElement;
    const libre = foco === null || foco === document.body || foco === document.documentElement;
    if (libre || caja.contains(foco)) cerrar(true);
  };

  const ensenar = (anuncio, ahora) => {
    actual = anuncio;
    caja = document.createElement("aside");
    caja.className = "anuncio";
    caja.setAttribute("data-anuncio", anuncio.id);
    rellenar();
    // La primera de la página, para que el teclado y el lector la encuentren antes que el resto.
    document.body.prepend(caja);
    const queda = Date.parse(anuncio.ventana.hasta) - ahora;
    if (queda < ESPERA_MAXIMA_MS) reloj = window.setTimeout(() => cerrar(false), queda);
  };

  const empezar = async () => {
    if (leer(NINGUNO) === "1") return;
    let datos;
    try {
      const respuesta = await fetch(DATOS, { credentials: "same-origin" });
      if (!respuesta.ok) return;
      datos = await respuesta.json();
    } catch {
      return;
    }
    const ahora = Date.now();
    const anuncio = elegir(datos, ahora, cerradosGuardados());
    if (anuncio === null || caja !== null) return;
    ensenar(anuncio, ahora);
  };

  // Para las pruebas (tests/anuncio.test.ts): la lógica, sin red.
  window.eodiAnuncios = { elegir, vigente, partir, idiomaDe, CERRADOS, NINGUNO };

  document.addEventListener("keydown", alPulsar);
  // El mapa cambia el idioma sin recargar: la ventana cambia con él.
  try {
    new MutationObserver(rellenar).observe(document.documentElement, { attributes: true, attributeFilter: ["lang"] });
  } catch {
    // Sin MutationObserver, la ventana se queda en el idioma con que salió.
  }
  if (document.body === null) document.addEventListener("DOMContentLoaded", () => void empezar());
  else void empezar();
})();
