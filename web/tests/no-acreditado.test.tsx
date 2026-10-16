// @vitest-environment jsdom
// La presencia de dron «no acreditada» (esquema 1.20.0): una autoridad oficial cerró su
// investigación sin pruebas del dron o retiró su declaración sin decir que fuera otra cosa. El
// incidente y su efecto siguen; cambia lo que se sabe del dron. Aquí: la validación (con el
// historial roto, el incidente se sigue pintando), las cifras («confirmados por una autoridad» sin
// los no acreditados ni los descartados), los filtros, el mapa (círculo morado, que no pone rojo
// un grupo), la ficha con la secuencia y sus fuentes (también una corrección parcial), la página
// de texto, el CSV y la nota del mapa en los dos idiomas.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Marcador } from "../src/componentes/Marcador.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { Filtros } from "../src/componentes/Filtros.tsx";
import { COLUMNAS_INCIDENTES, csvIncidentes } from "../src/datos/csv.ts";
import { cifras, detalleIncidente, resumir, resumirIncidente, resumirUcrania } from "../src/datos/derivar.ts";
import { confirmadoPorAutoridad, estadoEscrito, marcaDe, pasosDePresencia } from "../src/datos/presencia.ts";
import type { FeatureIncidente, PasoPresencia, PropiedadesIncidente } from "../src/datos/tipos.ts";
import { tolerarCamposNuevos, validarColeccion, validarDetalleIncidente } from "../src/datos/validar.ts";
import { GRAVES, SIN_FILTROS, TODO, escribirFiltros, filtrar, leerFiltros, ultimas24Horas } from "../src/estado/filtros.ts";
import { textos } from "../src/i18n/index.ts";
import { pilas } from "../src/mapa/geometria.ts";
import { PALETA } from "../src/paleta.ts";
import { paginas } from "../src/texto/paginas.ts";
import { textosPagina } from "../src/texto/textos.ts";
import { coleccion, fuente, incidente, publicacion } from "./ejemplos.ts";

afterEach(() => {
  cleanup();
  tolerarCamposNuevos(false);
});

const es = textos("es");
const en = textos("en");

/** Lo que se lee de un elemento, sin la flecha ni el aviso de los enlaces externos. */
function leido(elemento: Element | null | undefined): string {
  const copia = elemento?.cloneNode(true) as Element | undefined;
  for (const extra of copia?.querySelectorAll("[aria-hidden=true], .sr-only") ?? []) extra.remove();
  return copia?.textContent ?? "";
}

const DECLARACION_2025 = fuente({
  id: "gdelt-36b6a2a29b6bc102-declaracion-1",
  enlace: "https://www.kristeligt-dagblad.dk/danmark/politiet-droner",
  medio: "Københavns Politi (declaración oficial citada en kristeligt-dagblad.dk)",
  fecha: { valor: "2025-09-23T10:00Z", precision: "aproximada" },
  idioma: "da",
  fiabilidad: "B",
  credibilidad: 2,
  frase_origen: "Politiet bekræfter, at der er observeret droner over lufthavnen.",
});
const POLITI_2026 = fuente({
  id: "detalle-d5bf7ff3b226254a",
  enlace: "https://politi.dk/koebenhavns-politi/nyhedsliste/efterforskning-af-droner",
  medio: "Københavns Politi",
  fecha: { valor: "2026-06-25T00:00Z", precision: "dia" },
  idioma: "da",
  fiabilidad: "A",
  credibilidad: 2,
  frase_origen: "Politiet kan hverken be- eller afkræfte, at der var droner.",
});
const POLITI = { es: "la policía de Copenhague", en: "Copenhagen Police" };

/** El historial de Copenhague del contrato de datos, con una corrección parcial al final. */
const HISTORIAL: PasoPresencia[] = [
  { valor: "confirmada", fecha: { valor: "2025-09-23T00:00Z", precision: "dia" }, fuente_id: DECLARACION_2025.id, quien: POLITI },
  {
    valor: "no_acreditada",
    fecha: { valor: "2026-06-25T00:00Z", precision: "dia" },
    fuente_id: POLITI_2026.id,
    quien: POLITI,
    motivo: {
      es: "tras la investigación: no puede confirmar ni descartar que hubiera drones",
      en: "after the investigation: it can neither confirm nor rule out that there were drones",
    },
  },
];
const PARCIAL: PasoPresencia = {
  valor: "no_acreditada",
  fecha: { valor: "2026-07-02T00:00Z", precision: "dia" },
  fuente_id: POLITI_2026.id,
  quien: POLITI,
  motivo: { es: "mantiene lo dicho sobre la noche del 22", en: "it stands by what it said about the night of the 22nd" },
  parcial: true,
};

function copenhague(cambios: Partial<PropiedadesIncidente> = {}): FeatureIncidente {
  return incidente(
    {
      id: "EODI-2025-00154",
      estado: {
        actual: "confirmado",
        historial: [{ estado: "confirmado", fecha: { valor: "2025-09-25T00:00Z", precision: "dia" }, fuente_id: POLITI_2026.id }],
      },
      titulo: { es: "Drones cierran el aeropuerto de Copenhague", en: "Drones close Copenhagen Airport" },
      presencia_dron: "no_acreditada",
      presencia_historial: [...HISTORIAL],
      lugar: { radio_km: 5, pais: "DK" },
      objetivo: { categoria: "aeropuerto", nombre: "Københavns Lufthavn", oaci: "EKCH" },
      consecuencias: { cierre: { valor: "si", minutos: { min: 240, max: 240 } }, vuelos_desviados: { min: 35, max: 35 } },
      fuentes: [DECLARACION_2025, POLITI_2026],
      ...cambios,
    },
    [12.63793, 55.60927],
  );
}

function confirmado(id: string, cambios: Partial<PropiedadesIncidente> = {}, punto: [number, number] = [11.7861, 48.3536]) {
  return incidente(
    {
      id,
      estado: { actual: "confirmado", historial: [{ estado: "confirmado", fecha: { valor: "2025-10-03T02:00Z", precision: "dia" } }] },
      presencia_dron: "confirmada",
      ...cambios,
    },
    punto,
  );
}

describe("validación", () => {
  it("acepta el valor nuevo y el historial del contrato", () => {
    expect(validarColeccion(coleccion([copenhague()])).ok).toBe(true);
    expect(validarColeccion(coleccion([copenhague({ presencia_historial: [...HISTORIAL, PARCIAL] })])).ok).toBe(true);
    expect(validarDetalleIncidente(detalleIncidente(copenhague())).ok).toBe(true);
  });

  it("cerrado (las pruebas), un historial roto no valida", () => {
    for (const roto of [[], [{ valor: "quizas", fecha: { valor: "2025-09-23T00:00Z", precision: "dia" }, fuente_id: "x" }], "no"]) {
      expect(validarColeccion(coleccion([copenhague({ presencia_historial: roto as never })])).ok).toBe(false);
    }
  });

  it("en el navegador y en el build, un historial roto se quita y el incidente se sigue pintando", () => {
    tolerarCamposNuevos(true, true);
    const roto = copenhague({ presencia_historial: [{ valor: "quizas" }] as never });
    const resultado = validarColeccion(coleccion([roto]));
    expect(resultado.ok).toBe(true);
    if (resultado.ok) {
      const p = resultado.datos.features[0]?.properties;
      expect(p?.presencia_dron).toBe("no_acreditada");
      expect(p !== undefined && "presencia_historial" in p).toBe(false);
    }
    const detalle = detalleIncidente(copenhague({ presencia_historial: "no" as never }));
    expect(validarDetalleIncidente(detalle).ok).toBe(true);
    // Uno bueno no se toca.
    const bueno = validarDetalleIncidente(detalleIncidente(copenhague()));
    expect(bueno.ok && bueno.datos.presencia_historial).toHaveLength(2);
  });
});

describe("cifras: «confirmados por una autoridad»", () => {
  const todos = [
    copenhague(),
    confirmado("EODI-2025-00001"),
    confirmado("EODI-2025-00002", { presencia_dron: "descartada" }),
    confirmado("EODI-2025-00003", {
      estado: { actual: "atribuido", historial: [{ estado: "atribuido", fecha: { valor: "2025-10-03T02:00Z", precision: "dia" } }] },
      atribucion: { actor: "Rusia", autoridad: "Gobierno", fecha: { valor: "2025-10-03T02:00Z", precision: "dia" }, tipo: "estado", pais: "RU" },
    }),
    incidente({ id: "EODI-2025-00004" }),
  ].map(resumirIncidente);

  it("no cuentan los de presencia no acreditada ni descartada, que siguen siendo incidentes", () => {
    expect(cifras(todos)).toEqual({ incidentes: 5, confirmados: 2, atribuidos: 1, paises: 2 });
    expect(todos.filter(confirmadoPorAutoridad).map((i) => i.id)).toEqual(["EODI-2025-00001", "EODI-2025-00003"]);
  });

  it("el rótulo lo dice en los dos idiomas, también en el teléfono (rejilla)", () => {
    expect(es.marcador.confirmados).toBe("confirmados por una autoridad");
    expect(en.marcador.confirmados).toBe("confirmed by an authority");
    for (const forma of ["linea", "rejilla"] as const) {
      const { container, unmount } = render(<Marcador t={es} idioma="es" cifras={cifras(todos)} animar={false} forma={forma} />);
      const cifra = container.querySelector("[data-contador=confirmados]");
      expect(cifra?.getAttribute("data-valor")).toBe("2");
      expect(cifra?.querySelector("dt")?.textContent).toBe("confirmados por una autoridad");
      // En la rejilla, el número arriba del todo aunque el rótulo ocupe dos líneas.
      if (forma === "rejilla") expect(cifra?.className).toContain("justify-end");
      unmount();
    }
  });

  it("«Solo confirmados y atribuidos» deja fuera los no acreditados y los descartados; «No acreditado» los enseña", () => {
    const graves = filtrar(todos, { ...SIN_FILTROS, estados: [...GRAVES] }).map((i) => i.id);
    expect(graves).toEqual(["EODI-2025-00001", "EODI-2025-00003"]);
    expect(filtrar(todos, { ...SIN_FILTROS, estados: ["no_acreditado"] }).map((i) => i.id)).toEqual(["EODI-2025-00154"]);
    // Sin filtro de estado, todos: nada desaparece del mapa.
    expect(filtrar(todos, SIN_FILTROS)).toHaveLength(5);
    // Y va en la dirección.
    expect(escribirFiltros({ ...SIN_FILTROS, estados: ["no_acreditado", "notificado"] })).toBe("?estado=notificado,no_acreditado");
    expect(leerFiltros("?estado=no_acreditado").estados).toEqual(["no_acreditado"]);
  });

  it("el filtro de estado tiene «No acreditado» con su círculo morado", () => {
    const { container, getByRole } = render(
      <Filtros
        t={es}
        idioma="es"
        filtros={SIN_FILTROS}
        onFiltros={() => undefined}
        seleccion={TODO}
        onSeleccion={() => undefined}
        dominio={null}
        paises={[]}
        onQuitar={() => undefined}
      />,
    );
    const boton = getByRole("button", { name: "No acreditado" });
    expect(boton.querySelector("svg[data-circulo=no_acreditado] circle")?.getAttribute("fill")).toBe(PALETA.noAcreditado);
    expect(container.querySelectorAll("[aria-pressed]").length).toBeGreaterThanOrEqual(5);
  });
});

describe("el mapa", () => {
  const recientes = ultimas24Horas(0);

  it("un no acreditado es un círculo morado; uno descartado, un círculo gris relleno", () => {
    expect(marcaDe(resumirIncidente(copenhague()))).toBe("no_acreditado");
    expect(marcaDe(resumirIncidente(confirmado("EODI-2025-00002", { presencia_dron: "descartada" })))).toBe("descartado");
    // Un desmentido sigue gris aunque su presencia no se acredite.
    const desmentido = copenhague({
      estado: { actual: "desmentido", historial: [{ estado: "desmentido", fecha: { valor: "2026-06-25T00:00Z", precision: "dia" } }] },
    });
    expect(marcaDe(resumirIncidente(desmentido))).toBe("desmentido");
    const [pila] = pilas([resumirIncidente(copenhague())], { recientes, novedades: new Set() }).features;
    expect(pila?.properties).toMatchObject({ estado: "no_acreditado", icono: "incidente-no_acreditado", grave: 0, n_confirmados: 0, n_no_acreditados: 1 });
  });

  it("en un mismo punto manda el confirmado: un no acreditado no pone rojo un grupo, pero va por encima de lo notificado", () => {
    const punto: [number, number] = [12.63793, 55.60927];
    const conConfirmado = pilas(
      [copenhague(), confirmado("EODI-2025-00001", {}, punto)].map(resumirIncidente),
      { recientes, novedades: new Set() },
    ).features[0]?.properties;
    expect(conConfirmado).toMatchObject({ estado: "confirmado", n_confirmados: 1, n_no_acreditados: 1 });
    const conNotificado = pilas(
      [copenhague(), incidente({ id: "EODI-2025-00004" }, punto)].map(resumirIncidente),
      { recientes, novedades: new Set() },
    ).features[0]?.properties;
    expect(conNotificado).toMatchObject({ estado: "no_acreditado", n_confirmados: 0, n_notificados: 1 });
  });

  it("junto al círculo morado, el texto dice también la presencia", () => {
    const i = resumirIncidente(copenhague());
    expect(estadoEscrito(es, "es", i)).toBe("Confirmado · Dron no acreditado");
    expect(estadoEscrito(en, "en", i)).toBe("Confirmed · Drone not substantiated");
  });
});

describe("la ficha", () => {
  it("dice la presencia en vigor y la secuencia entera, con la fecha, quién y el enlace de cada paso", () => {
    const detalle = detalleIncidente(copenhague());
    for (const [t, idioma, pasos, valor] of [
      [
        es,
        "es",
        [
          "Confirmado el 23/09/2025 por la policía de Copenhague",
          "No acreditado el 25/06/2026 por la policía de Copenhague, tras la investigación: no puede confirmar ni descartar que hubiera drones",
        ],
        "Dron no acreditado",
      ],
      [
        en,
        "en",
        [
          "Confirmed on 23/09/2025 by Copenhagen Police",
          "Not substantiated on 25/06/2026 by Copenhagen Police, after the investigation: it can neither confirm nor rule out that there were drones",
        ],
        "Drone not substantiated",
      ],
    ] as const) {
      const { container, unmount } = render(<FichaIncidente t={t} idioma={idioma} incidente={detalle} />);
      expect(container.querySelector("[data-presencia]")?.textContent).toBe(valor);
      const lista = container.querySelector("[data-presencia-historial]");
      expect(lista?.getAttribute("aria-label")).toBe(t.presenciaHistorial.rotulo);
      const elementos = [...(lista?.querySelectorAll("li") ?? [])];
      expect(elementos.map(leido)).toEqual(pasos);
      // Cada paso enlaza a su fuente.
      expect(elementos.map((li) => li.querySelector("a")?.getAttribute("href"))).toEqual([DECLARACION_2025.enlace, POLITI_2026.enlace]);
      // La marca de la ficha es el círculo morado, y el estado del suceso no cambia.
      expect(container.querySelector("article > p svg[data-circulo=no_acreditado]")).not.toBeNull();
      expect(container.textContent).toContain(t.estado.confirmado);
      // El efecto sigue a la vista: el cierre y los desvíos.
      expect(container.textContent).toContain(t.ficha.efecto);
      expect(container.textContent).toContain(t.ficha.vuelosDesviados);
      unmount();
    }
  });

  it("una corrección parcial es una nota de la secuencia que no cambia el valor", () => {
    const detalle = detalleIncidente(copenhague({ presencia_historial: [...HISTORIAL, PARCIAL] }));
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    const parcial = container.querySelector("[data-presencia-historial] li[data-parcial]");
    expect(leido(parcial)).toBe("Corrección parcial el 02/07/2026 por la policía de Copenhague: mantiene lo dicho sobre la noche del 22");
    expect(parcial?.className).toContain("text-secundario");
    expect(container.querySelector("[data-presencia]")?.textContent).toBe("Dron no acreditado");
    expect(pasosDePresencia(en, "en", detalle).at(-1)?.texto).toBe("Partial correction on 02/07/2026 by Copenhagen Police");
  });

  it("sin historial, solo la presencia, como antes", () => {
    const detalle = detalleIncidente(confirmado("EODI-2025-00001"));
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalle} />);
    expect(container.querySelector("[data-presencia]")?.textContent).toBe("Dron confirmado");
    expect(container.querySelector("[data-presencia-historial]")).toBeNull();
  });

  it("un paso cuya fuente no está entre las del incidente sale sin enlace, y sin quien, sin «por»", () => {
    const sinFuente: PasoPresencia[] = [{ valor: "no_acreditada", fecha: { valor: "2026-06-25T00:00Z", precision: "dia" }, fuente_id: "otra" }];
    const [paso] = pasosDePresencia(es, "es", { presencia_historial: sinFuente, fuentes: [] });
    expect(paso).toMatchObject({ texto: "No acreditado el 25/06/2026", resto: "", fuente: undefined });
  });
});

describe("la página de texto, el CSV y la nota", () => {
  it("la página del incidente dice la presencia y su secuencia con los enlaces; la portada, la nota", () => {
    const feature = copenhague();
    const datos = {
      resumen: resumir(coleccion([feature]), publicacion([])),
      detalles: new Map([[feature.id, detalleIncidente(feature)]]),
      ucrania: resumirUcrania(publicacion([])),
    };
    const todas = paginas(datos);
    for (const [idioma, t, primero] of [
      ["es", es, "Confirmado el 23/09/2025 por la policía de Copenhague"],
      ["en", en, "Confirmed on 23/09/2025 by Copenhagen Police"],
    ] as const) {
      const pagina = todas.find((p) => p.idioma === idioma && p.rutas[idioma].endsWith(feature.id));
      const cuerpo = String(pagina?.cuerpo ?? "");
      expect(cuerpo).toContain(t.presencia.no_acreditada);
      expect(cuerpo).toContain("data-presencia-historial");
      expect(cuerpo).toContain(primero);
      expect(cuerpo).toContain(`href="${POLITI_2026.enlace}"`);
      // Los datos estructurados también dicen la presencia rectificada.
      expect(JSON.stringify(pagina?.estructurados)).toContain(t.presencia.no_acreditada);
      const portada = todas.find((p) => p.idioma === idioma && p.titulo === textosPagina(idioma).portada.titulo);
      expect(String(portada?.cuerpo ?? "")).toContain("data-nota-mapa");
    }
  });

  it("el CSV lleva el valor y el historial resumido en la última columna", () => {
    const texto = csvIncidentes(coleccion([copenhague({ presencia_historial: [...HISTORIAL, PARCIAL] }), confirmado("EODI-2025-00001")]));
    const [cabecera, primera, segunda] = texto.split("\r\n");
    expect(cabecera?.split(",").at(-1)).toBe("presencia_historial");
    expect(COLUMNAS_INCIDENTES.at(-1)).toBe("presencia_historial");
    expect(primera).toContain(",no_acreditada,");
    expect(primera?.endsWith(",2025-09-23:confirmada|2026-06-25:no_acreditada|2026-07-02:no_acreditada:parcial")).toBe(true);
    expect(segunda?.endsWith(",")).toBe(true);
  });

  it("la nota del mapa, en los dos idiomas", () => {
    expect(es.mapa.nota).toBe(
      "El observatorio registra lo que se notifica y lo que declaran las autoridades. «Confirmado» significa que una autoridad oficial lo ha declarado, no que exista una prueba física pública.",
    );
    expect(en.mapa.nota).toBe(
      "The observatory records what is reported and what authorities state. “Confirmed” means an official authority has stated it, not that public physical evidence exists.",
    );
  });

  it("la metodología define «no acreditado», lo distingue de «descartado» y dice que nada se borra", () => {
    for (const [t, termino, claves] of [
      [es, "No acreditado", ["no es lo mismo que probar que no hubo un dron", "si un aeropuerto cerró, cerró", "fuente oficial", "revisión", "parcial"]],
      [en, "Not substantiated", ["is not the same as proving there was no drone", "if an airport closed, it closed", "official source", "review", "partial"]],
    ] as const) {
      const seccion = t.metodologia.secciones.find((s) => s.id === "presencia");
      const texto = JSON.stringify(seccion);
      expect(texto).toContain(termino);
      for (const clave of claves) expect(texto, clave).toContain(clave);
      const lista = seccion?.bloques.find((b) => "lista" in b);
      const definicion = lista !== undefined && "lista" in lista ? lista.lista.find((d) => d.termino === termino) : undefined;
      expect(definicion?.marca).toEqual({ estado: "no_acreditado" });
    }
  });
});
