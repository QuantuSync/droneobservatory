// @vitest-environment jsdom
// «No acreditado» y «descartado», bien visibles en toda la web: el círculo de la presencia en la
// ficha (morado o gris relleno, el mismo del mapa), los cambios de la presencia dentro del
// «Historial de estados» por orden de fecha y con su fuente, la marca «descartado» en el mapa y los
// filtros, el aro exterior de un grupo que junta alguno con la presencia rectificada, el aro de
// selección de su color, la página de texto y el rótulo de la fecha de «Notas oficiales».
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { Ayuda } from "../src/componentes/Ayuda.tsx";
import { BarraEstado } from "../src/componentes/BarraEstado.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { Simbolo } from "../src/componentes/Simbolo.tsx";
import { detalleIncidente, resumir, resumirIncidente, resumirUcrania } from "../src/datos/derivar.ts";
import { MARCAS, conMayuscula, confirmadoPorAutoridad, estadoEscrito, historialCompleto, marcaDe, quienSinArticulo } from "../src/datos/presencia.ts";
import type { FeatureIncidente, PasoPresencia, PropiedadesIncidente } from "../src/datos/tipos.ts";
import { GRAVES, SIN_FILTROS, filtrar, leerFiltros, ultimas24Horas } from "../src/estado/filtros.ts";
import { textos } from "../src/i18n/index.ts";
import { CAPA_GRUPOS_PRESENCIA, CAPAS_DE_INCIDENTES, COLOR_PRESENCIA_DE_GRUPO, estilo } from "../src/mapa/estilo.ts";
import { pilas } from "../src/mapa/geometria.ts";
import { COLOR_MARCA, GRAVEDAD, PALETA } from "../src/paleta.ts";
import { paginas } from "../src/texto/paginas.ts";
import { coleccion, estadoSistema, fuente, incidente, publicacion } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");
const PUNTO_CPH: [number, number] = [12.63793, 55.60927];

/** Lo que se lee de un elemento, sin la flecha ni el aviso de los enlaces externos. */
function leido(elemento: Element | null | undefined): string {
  const copia = elemento?.cloneNode(true) as Element | undefined;
  for (const extra of copia?.querySelectorAll("[aria-hidden=true], .sr-only") ?? []) extra.remove();
  return (copia?.textContent ?? "").replace(/\s+/g, " ").trim();
}

const NOTICIA = fuente({ id: "gdelt-43a09a408be869cd", medio: "dr.dk", fecha: { valor: "2025-09-23T09:15Z", precision: "aproximada" } });
const CONFIRMA = fuente({ id: "detalle-c164c43ddf12cd41", medio: "Københavns Politi", fecha: { valor: "2025-09-25T00:00Z", precision: "dia" }, fiabilidad: "A" });
const RIGSPOLITIET = fuente({
  id: "gdelt-c3900a03bd9503d2",
  enlace: "https://politi.dk/rigspolitiet/nyhedsliste/droner-kastrup",
  medio: "Rigspolitiet",
  fecha: { valor: "2026-06-25T00:00Z", precision: "dia" },
  fiabilidad: "A",
});
const DINAMARCA = { es: "la Policía Nacional de Dinamarca", en: "the Danish National Police" };
const NO_ACREDITADA: PasoPresencia[] = [
  { valor: "confirmada", fecha: { valor: "2025-09-22T20:15Z", precision: "aproximada" }, fuente_id: CONFIRMA.id, quien: { es: "la policía de Copenhague", en: "the Copenhagen Police" } },
  {
    valor: "no_acreditada",
    fecha: { valor: "2026-06-25T00:00Z", precision: "dia" },
    fuente_id: RIGSPOLITIET.id,
    quien: DINAMARCA,
    motivo: { es: "no dispone de pruebas concluyentes de que fueran drones", en: "it has no conclusive evidence that they were drones" },
  },
];

/** Copenhague (EODI-2025-00154): notificado, confirmado y la presencia no acreditada en 2026. */
function copenhague(cambios: Partial<PropiedadesIncidente> = {}): FeatureIncidente {
  return incidente(
    {
      id: "EODI-2025-00154",
      tipo: "interrupcion_aeroportuaria",
      estado: {
        actual: "confirmado",
        historial: [
          { estado: "notificado", fecha: { valor: "2025-09-23T09:15Z", precision: "aproximada" }, fuente_id: NOTICIA.id },
          { estado: "confirmado", fecha: { valor: "2025-09-25T00:00Z", precision: "dia" }, fuente_id: CONFIRMA.id },
        ],
      },
      presencia_dron: "no_acreditada",
      presencia_historial: NO_ACREDITADA,
      lugar: { radio_km: 5, pais: "DK" },
      fuentes: [NOTICIA, CONFIRMA, RIGSPOLITIET],
      ...cambios,
    },
    PUNTO_CPH,
  );
}

const UKAB = fuente({ id: "airprox-2024294", enlace: "https://www.airproxboard.org.uk/2024294", medio: "UK Airprox Board", fecha: { valor: "2025-11-20T00:00Z", precision: "dia" }, fiabilidad: "A" });

/** Lakenheath (EODI-2025-00164): notificado, con la presencia descartada (era un F-15). */
function lakenheath(): FeatureIncidente {
  return incidente(
    {
      id: "EODI-2025-00164",
      estado: { actual: "notificado", historial: [{ estado: "notificado", fecha: { valor: "2025-04-05T07:30Z", precision: "aproximada" }, fuente_id: NOTICIA.id }] },
      presencia_dron: "descartada",
      presencia_historial: [
        { valor: "descartada", fecha: { valor: "2025-11-20T00:00Z", precision: "dia" }, fuente_id: UKAB.id, quien: { es: "el UK Airprox Board", en: "the UK Airprox Board" }, motivo: { es: "era un F-15", en: "it was an F-15" } },
      ],
      lugar: { radio_km: 5, pais: "GB" },
      fuentes: [NOTICIA, UKAB],
    },
    [0.55783, 52.4047],
  );
}

function confirmado(id: string, punto: [number, number] = PUNTO_CPH): FeatureIncidente {
  return incidente(
    { id, estado: { actual: "confirmado", historial: [{ estado: "confirmado", fecha: { valor: "2025-09-22T22:00Z", precision: "dia" } }] }, presencia_dron: "confirmada" },
    punto,
  );
}

describe("la marca", () => {
  it("no acreditado es morado y descartado es gris relleno, del gris de «desmentido»; el desmentido manda", () => {
    expect(marcaDe(resumirIncidente(copenhague()))).toBe("no_acreditado");
    expect(marcaDe(resumirIncidente(lakenheath()))).toBe("descartado");
    expect(marcaDe({ estado: "desmentido", presencia: "descartada" })).toBe("desmentido");
    expect(COLOR_MARCA.descartado).toBe(PALETA.desmentido);
    expect(MARCAS).toContain("descartado");
    expect(GRAVEDAD.descartado).toBeGreaterThan(GRAVEDAD.desmentido);
    expect(GRAVEDAD.descartado).toBeLessThan(GRAVEDAD.notificado);
    const { container } = render(
      <>
        <Simbolo estado="descartado" />
        <Simbolo estado="desmentido" />
      </>,
    );
    const descartado = container.querySelector("svg[data-circulo=descartado] circle");
    const desmentido = container.querySelector("svg[data-circulo=desmentido] circle");
    expect(descartado?.getAttribute("fill")).toBe(PALETA.descartado);
    expect(descartado?.getAttribute("stroke-dasharray")).toBeNull();
    expect(desmentido?.getAttribute("fill")).toBe("none");
  });

  it("junto al círculo gris, el texto dice también la presencia; no cuenta como confirmado", () => {
    const resumen = resumirIncidente(lakenheath());
    expect(estadoEscrito(es, "es", resumen)).toBe("Notificado · Dron descartado");
    expect(estadoEscrito(en, "en", resumen)).toBe("Reported · Drone ruled out");
    expect(confirmadoPorAutoridad(resumirIncidente(copenhague()))).toBe(false);
  });
});

describe("la ficha", () => {
  it("la presencia lleva el círculo de su marca, del mismo tamaño que los de los estados", () => {
    for (const [feature, marca] of [
      [copenhague(), "no_acreditado"],
      [lakenheath(), "descartado"],
    ] as const) {
      const { container, unmount } = render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(feature)} />);
      const fila = container.querySelector("[data-presencia]")?.parentElement;
      const circulo = fila?.querySelector(`svg[data-circulo=${marca}]`);
      expect(circulo, marca).not.toBeNull();
      expect(circulo?.getAttribute("width")).toBe(container.querySelector("svg[data-circulo]")?.getAttribute("width"));
      expect(fila?.textContent).not.toContain("◇");
      unmount();
    }
  });

  it("arriba, el círculo morado lleva su nombre al lado: no se lee como el color del tipo", () => {
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(copenhague())} />);
    const arriba = container.querySelector("[data-marca-ficha]");
    expect(arriba?.getAttribute("data-marca-ficha")).toBe("no_acreditado");
    expect(arriba?.textContent).toBe(`No acreditado · ${es.tipo.interrupcion_aeroportuaria}`);
    // Un confirmado sin rectificar sigue con el tipo solo.
    cleanup();
    const otro = render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(confirmado("EODI-2025-00030"))} />);
    expect(otro.container.querySelector("[data-marca-ficha]")?.textContent).toBe(es.tipo[detalleIncidente(confirmado("EODI-2025-00030")).tipo]);
  });

  it("el historial de estados incluye el paso a no acreditado, por fecha, con su círculo y su fuente enlazada", () => {
    for (const [t, idioma, esperado] of [
      [es, "es", ["Notificado 23/09/2025", "Confirmado 25/09/2025", "No acreditado 25/06/2026 Policía Nacional de Dinamarca"]],
      [en, "en", ["Reported 23/09/2025", "Confirmed 25/09/2025", "Not substantiated 25/06/2026 Danish National Police"]],
    ] as const) {
      const { container, unmount } = render(<FichaIncidente t={t} idioma={idioma} incidente={detalleIncidente(copenhague())} />);
      const seccion = [...container.querySelectorAll("section")].find((s) => s.querySelector("h3")?.textContent === t.ficha.historial);
      const pasos = [...(seccion?.querySelectorAll("ol > li") ?? [])];
      expect(pasos).toHaveLength(3);
      for (const [i, texto] of esperado.entries()) {
        for (const trozo of texto.split(" ")) expect(leido(pasos[i]), `${idioma} ${i}`).toContain(trozo);
      }
      const ultimo = pasos[2];
      expect(ultimo?.getAttribute("data-historial-presencia")).toBe("no_acreditado");
      expect(ultimo?.querySelector("svg[data-circulo=no_acreditado]")).not.toBeNull();
      expect(ultimo?.querySelector("a")?.getAttribute("href")).toBe(RIGSPOLITIET.enlace);
      expect(leido(ultimo)).toContain(idioma === "es" ? "No dispone de pruebas concluyentes" : "It has no conclusive evidence");
      unmount();
    }
  });

  it("Lakenheath: el historial acaba en «Descartado», con el círculo gris relleno y el UK Airprox Board", () => {
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={detalleIncidente(lakenheath())} />);
    const paso = container.querySelector("[data-historial-presencia=descartado]");
    expect(paso?.querySelector("svg[data-circulo=descartado]")).not.toBeNull();
    expect(leido(paso)).toContain("Descartado");
    expect(leido(paso)).toContain("UK Airprox Board");
    expect(paso?.querySelector("a")?.getAttribute("href")).toBe(UKAB.enlace);
  });

  it("los pasos que solo repiten lo que dice el estado no se añaden; a igual fecha, el estado va antes", () => {
    const pasos = historialCompleto(es, "es", detalleIncidente(copenhague()));
    expect(pasos.map((p) => (p.clase === "estado" ? p.paso.estado : p.marca))).toEqual(["notificado", "confirmado", "no_acreditado"]);
    const mismaFecha = historialCompleto(es, "es", {
      estado: { historial: [{ estado: "notificado", fecha: { valor: "2026-06-25T00:00Z", precision: "dia" } }] },
      presencia_historial: [{ valor: "no_acreditada", fecha: { valor: "2026-06-25T00:00Z", precision: "dia" }, fuente_id: "x" }],
      fuentes: [],
    });
    expect(mismaFecha.map((p) => p.clase)).toEqual(["estado", "presencia"]);
    expect(quienSinArticulo("la policía de Dinamarca")).toBe("Policía de Dinamarca");
    expect(quienSinArticulo("the Danish Police")).toBe("Danish Police");
  });

  it("el motivo del historial empieza con mayúscula, en los dos idiomas, sin tocar el resto", () => {
    expect(conMayuscula("tras la investigación: no pudo confirmar que fueran drones")).toBe("Tras la investigación: no pudo confirmar que fueran drones");
    expect(conMayuscula("al cerrar la investigación, la Policía no halló pruebas")).toBe("Al cerrar la investigación, la Policía no halló pruebas");
    expect(conMayuscula("ámbito del informe Airprox")).toBe("Ámbito del informe Airprox");
    expect(conMayuscula("«informe Airprox» 2025123")).toBe("«Informe Airprox» 2025123");
    expect(conMayuscula("after the investigation: could not confirm")).toBe("After the investigation: could not confirm");
    expect(conMayuscula("Informe Airprox 2025123")).toBe("Informe Airprox 2025123");
    expect(conMayuscula("2 drones avistados")).toBe("2 drones avistados");
    expect(conMayuscula("")).toBe("");
  });
});

describe("el mapa", () => {
  const opciones = { recientes: ultimas24Horas(0), novedades: new Set<string>() };

  it("un punto con confirmados y un no acreditado lleva el aro exterior morado; con un descartado, gris", () => {
    const [cph] = pilas([copenhague(), confirmado("EODI-2025-00030"), confirmado("EODI-2025-00097")].map(resumirIncidente), opciones).features;
    expect(cph?.properties).toMatchObject({ estado: "confirmado", n: 3, n_confirmados: 2, n_no_acreditados: 1, n_descartados: 0 });
    const [lk] = pilas([lakenheath(), confirmado("EODI-2026-00006", [0.55783, 52.4047])].map(resumirIncidente), opciones).features;
    expect(lk?.properties).toMatchObject({ n_descartados: 1, n_no_acreditados: 0 });
    // Un descartado suelto es su propio círculo gris relleno, no un grave.
    const [solo] = pilas([resumirIncidente(lakenheath())], opciones).features;
    expect(solo?.properties).toMatchObject({ estado: "descartado", icono: "incidente-descartado", grave: 0 });

    const capas = estilo("es", "https://droneobservatory.eu", "#f4f7fb").layers;
    const aro = capas.find((c) => c.id === CAPA_GRUPOS_PRESENCIA);
    expect(aro).toBeDefined();
    expect(CAPAS_DE_INCIDENTES).toContain(CAPA_GRUPOS_PRESENCIA);
    expect(JSON.stringify(COLOR_PRESENCIA_DE_GRUPO)).toContain(PALETA.noAcreditado);
    expect(JSON.stringify(COLOR_PRESENCIA_DE_GRUPO)).toContain(PALETA.descartado);
    // Va justo encima del anillo del grupo, debajo de su número.
    const ids = capas.map((c) => c.id);
    expect(ids.indexOf(CAPA_GRUPOS_PRESENCIA)).toBe(ids.indexOf("grupos") + 1);
    // El aro de selección toma el color de la marca rectificada.
    const seleccion = capas.find((c) => c.id === "seleccion");
    const color = JSON.stringify(seleccion && "paint" in seleccion ? seleccion.paint : null);
    expect(color).toContain(PALETA.noAcreditado);
    expect(color).toContain(PALETA.descartado);
    // Los grupos de la agrupación suman también los descartados.
    const fuente = estilo("es", "https://droneobservatory.eu", "#f4f7fb").sources.incidentes;
    expect(JSON.stringify(fuente)).toContain("n_descartados");
  });

  it("el filtro «Descartado» y «No acreditado» se leen de la dirección; las cifras los cuentan aparte", () => {
    const col = coleccion([copenhague(), lakenheath(), confirmado("EODI-2025-00030")]);
    const resumen = resumir(col, publicacion([]));
    expect(leerFiltros("?estado=descartado").estados).toEqual(["descartado"]);
    expect(leerFiltros("?estado=no_acreditado,descartado").estados).toEqual(["no_acreditado", "descartado"]);
    const ids = (estados: string) =>
      filtrar(resumen.incidentes, { ...SIN_FILTROS, estados: leerFiltros(`?estado=${estados}`).estados }).map((i) => i.id);
    expect(ids("descartado")).toEqual(["EODI-2025-00164"]);
    expect(ids("no_acreditado")).toEqual(["EODI-2025-00154"]);
    expect(filtrar(resumen.incidentes, { ...SIN_FILTROS, estados: [...GRAVES] }).map((i) => i.id)).toEqual(["EODI-2025-00030"]);
  });

  it("la leyenda explica las dos en los dos idiomas: el incidente ocurrió", () => {
    for (const [t, idioma, claves] of [
      [es, "es", ["El incidente ocurrió", "no se acreditó", "se descartó"]],
      [en, "en", ["The incident happened", "not substantiated", "ruled out"]],
    ] as const) {
      const { container, unmount } = render(<Ayuda t={t} idioma={idioma} abierta={false} onCerrar={() => undefined} />);
      const texto = container.querySelector("[data-leyenda-estados]")?.textContent ?? "";
      for (const clave of claves) expect(texto, clave).toContain(clave);
      expect(container.querySelector("[data-leyenda-descartado] svg[data-circulo=descartado]")).not.toBeNull();
      expect(t.ayuda.numeros).toContain(idioma === "es" ? "aro exterior morado" : "outer purple ring");
      unmount();
    }
  });
});

describe("la página de texto", () => {
  it("el historial de la página de la ficha lleva el paso de la presencia con su enlace", () => {
    const feature = copenhague();
    const todas = paginas({
      resumen: resumir(coleccion([feature]), publicacion([])),
      detalles: new Map([[feature.id, detalleIncidente(feature)]]),
      ucrania: resumirUcrania(publicacion([])),
    });
    for (const idioma of ["es", "en"] as const) {
      const pagina = todas.find((p) => p.idioma === idioma && p.rutas[idioma].endsWith(feature.id));
      const cuerpo = String(pagina?.cuerpo ?? "");
      const historial = cuerpo.slice(cuerpo.indexOf("texto-historial"));
      expect(historial).toContain('data-historial-presencia="no_acreditado"');
      expect(historial).toContain(`href="${RIGSPOLITIET.enlace}"`);
      expect(historial).toContain(idioma === "es" ? "No acreditado" : "Not substantiated");
    }
  });
});

describe("Notas oficiales en el estado de la recogida", () => {
  it("su fecha dice que es la de la última nota publicada y que se consulta cada hora", async () => {
    const sistema = estadoSistema({
      fuentes: [
        { id: "gdelt", estado: "leida", ultimo_dato: "2026-10-16T05:00Z" },
        { id: "oficiales", estado: "leida", ultimo_dato: "2026-10-15T16:29Z" },
      ],
    });
    const usuario = userEvent.setup();
    render(<BarraEstado t={es} actualizado="2026-10-16T05:35Z" sistema={sistema} ahora={new Date("2026-10-16T05:40Z")} />);
    await usuario.click(screen.getByRole("button"));
    expect(document.querySelector("[data-dato-fuente=oficiales]")?.textContent).toBe(
      "se consulta cada hora · última nota publicada: 15/10/2026 · 16:29 UTC",
    );
    expect(document.querySelector("[data-dato-fuente=gdelt]")?.textContent).toContain("último dato: ");
    expect(en.estadoDatos.datoDeFuente.oficiales).toBe("checked every hour · latest notice published");
  });
});
