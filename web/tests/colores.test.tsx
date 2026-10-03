// @vitest-environment jsdom
// Colores de los estados: naranja notificado, rojo confirmado, rojo con bandera atribuido, gris
// discontinuo desmentido; el verde, solo para «datos al día». Y el pulso: solo las novedades.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Ayuda } from "../src/componentes/Ayuda.tsx";
import { BarraEstado } from "../src/componentes/BarraEstado.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { BANDERA_SIMBOLO, Simbolo } from "../src/componentes/Simbolo.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { novedadesQueLaten } from "../src/estado/novedades.ts";
import { textos } from "../src/i18n/index.ts";
import {
  CAPA_INCIDENTES_GRAVES,
  CAPA_RECIENTES,
  CAPA_SELECCION,
  CAPA_SELECCION_BANDERA,
  CAPA_DIRECTO,
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_NUMERO_GRUPOS,
  CENTRO_TEXTO_AVISO,
  TAMANO_NUMERO_GRUPO,
  TAMANO_TEXTO_AVISO,
  COLOR_DE_GRUPO,
  ES_ATRIBUIDO,
  estilo,
} from "../src/mapa/estilo.ts";
import { OBJETIVO_TACTIL_PX } from "../src/mapa/Mapa.tsx";
import { nombreIcono } from "../src/mapa/geometria.ts";
import {
  BANDERA,
  COLOR_DE_AVISO,
  ESTADOS_AVISO,
  ETIQUETA_AVISO,
  ICONO_BANDERA_ELEGIDA,
  LADO as LADO_ICONO,
  nombreIconoAviso,
  registrarIconos,
} from "../src/mapa/iconos.ts";
import { COLOR_BANDERA, COLOR_ESTADO, PALETA, contraste, trazadoBandera } from "../src/paleta.ts";
import { incidente } from "./ejemplos.ts";

afterEach(cleanup);

const es = textos("es");
const en = textos("en");

/** Matrices de Machado, Oliveira y Fernandes (2009), gravedad 1. */
const DALTONISMO: Record<string, number[][]> = {
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  tritanopia: [
    [1.255528, -0.076749, -0.178779],
    [-0.078411, 0.930809, 0.147602],
    [0.004733, 0.691367, 0.3039],
  ],
};

function lineal(canal: number): number {
  const v = canal / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

function simular(hex: string, matriz: number[][]): string {
  const rgb = [1, 3, 5].map((i) => lineal(parseInt(hex.slice(i, i + 2), 16)));
  const salida = matriz.map((fila) => fila.reduce((s, m, k) => s + m * (rgb[k] ?? 0), 0));
  return `#${salida
    .map((v) => {
      const c = Math.min(1, Math.max(0, v));
      const s = c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
      return Math.round(s * 255)
        .toString(16)
        .padStart(2, "0");
    })
    .join("")}`;
}

function tono(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [
    number,
    number,
    number,
  ];
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return h * 60;
}

function diferenciaDeTono(a: string, b: string): number {
  const d = Math.abs(tono(a) - tono(b));
  return Math.min(d, 360 - d);
}

describe("colores de los estados", () => {
  it("naranja notificado, rojo confirmado y atribuido, gris el desmentido", () => {
    expect(COLOR_ESTADO).toEqual({
      notificado: "#ff9a2e",
      confirmado: "#f53a50",
      atribuido: "#f53a50",
      desmentido: PALETA.secundario,
    });
    // Naranja de verdad (entre 20° y 40°) y rojo (a menos de 15° del rojo puro): ni dorado ni
    // cian.
    expect(tono(COLOR_ESTADO.notificado)).toBeGreaterThan(20);
    expect(tono(COLOR_ESTADO.notificado)).toBeLessThan(40);
    expect(diferenciaDeTono(COLOR_ESTADO.confirmado, "#ff0000")).toBeLessThan(15);
  });

  it("el naranja y el rojo se distinguen por luminancia, también con daltonismo", () => {
    const { notificado, confirmado } = COLOR_ESTADO;
    // Medido: 1,77:1 con visión normal; 1,62 deuteranopía, 2,15 protanopía, 1,66 tritanopía.
    expect(contraste(notificado, confirmado)).toBeGreaterThanOrEqual(1.7);
    for (const [nombre, matriz] of Object.entries(DALTONISMO)) {
      const separacion = contraste(simular(notificado, matriz), simular(confirmado, matriz));
      expect(separacion, nombre).toBeGreaterThanOrEqual(1.6);
    }
  });

  it("los dos se leen sobre el fondo oscuro: AA de texto en todas las superficies", () => {
    for (const superficie of [PALETA.fondo, PALETA.panelSolido, PALETA.elevado]) {
      expect(contraste(COLOR_ESTADO.notificado, superficie)).toBeGreaterThanOrEqual(4.5);
      expect(contraste(COLOR_ESTADO.confirmado, superficie)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("el rojo de los estados no es el de la capa de guerra", () => {
    expect(PALETA.guerra).not.toBe(COLOR_ESTADO.confirmado);
    expect(diferenciaDeTono(PALETA.guerra, COLOR_ESTADO.confirmado)).toBeGreaterThanOrEqual(10);
    // Las capas de la guerra usan su propio color, no el de los estados.
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const guerra = layers.filter((c) => c.id.startsWith("ucrania-"));
    expect(guerra.length).toBeGreaterThan(0);
    expect(JSON.stringify(guerra)).not.toContain(COLOR_ESTADO.confirmado);
  });

  it("ningún estado de incidente es verde: el verde es solo el de «datos al día»", () => {
    const verde = PALETA.alDia;
    for (const color of Object.values(COLOR_ESTADO)) expect(color).not.toBe(verde);
    for (const color of Object.values(COLOR_DE_AVISO)) expect(color).not.toBe(verde);
    expect(JSON.stringify(COLOR_DE_GRUPO)).not.toContain(verde);
  });

  it("un grupo es rojo si contiene algún confirmado o atribuido y naranja si todos son notificados", () => {
    expect(COLOR_DE_GRUPO).toEqual([
      "case",
      [">", ["+", ["get", "n_atribuidos"], ["get", "n_confirmados"]], 0],
      COLOR_ESTADO.confirmado,
      [">", ["get", "n_notificados"], 0],
      COLOR_ESTADO.notificado,
      COLOR_ESTADO.desmentido,
    ]);
  });

  it("los avisos en directo van en la misma escala, sin verde: naranja posible, rojo confirmado", () => {
    expect(COLOR_DE_AVISO).toEqual({
      posible_cierre: COLOR_ESTADO.notificado,
      cierre_confirmado: COLOR_ESTADO.confirmado,
      operacion_reanudada: PALETA.secundario,
    });
  });
});

describe("bandera de los atribuidos", () => {
  it("el atribuido es solo una bandera roja: sin forma, círculo ni punto", () => {
    const { container } = render(<Simbolo estado="atribuido" />);
    const svg = container.querySelector("svg");
    expect(svg?.hasAttribute("data-bandera")).toBe(true);
    expect(svg?.querySelectorAll("circle, rect, ellipse, polygon")).toHaveLength(0);
    for (const trazo of Array.from(svg?.querySelectorAll("path") ?? [])) {
      expect(trazo.getAttribute("d")).toBe(trazadoBandera(BANDERA_SIMBOLO));
    }
    expect(svg?.innerHTML).toContain(COLOR_BANDERA);
    expect(COLOR_BANDERA).toBe(COLOR_ESTADO.confirmado);
  });

  it("todo lo demás es un círculo: relleno el notificado y el confirmado, discontinuo el desmentido", () => {
    for (const estado of ["notificado", "confirmado", "desmentido"] as const) {
      const { container } = render(<Simbolo estado={estado} />);
      const svg = container.querySelector("svg");
      expect(svg?.querySelector("[data-bandera]"), estado).toBeNull();
      expect(svg?.children, estado).toHaveLength(1);
      const circulo = svg?.querySelector("circle");
      expect(circulo, estado).not.toBeNull();
      if (estado === "desmentido") {
        expect(circulo?.getAttribute("fill")).toBe("none");
        expect(circulo?.getAttribute("stroke")).toBe(COLOR_ESTADO.desmentido);
        expect(circulo?.getAttribute("stroke-dasharray")).toBeTruthy();
      } else {
        expect(circulo?.getAttribute("fill")).toBe(COLOR_ESTADO[estado]);
        expect(circulo?.getAttribute("fill-opacity")).toBeNull();
      }
      cleanup();
    }
  });

  it("en el mapa, un icono por estado: círculos y la bandera, ninguna otra forma", () => {
    // Un lienzo que apunta lo que se dibuja.
    const dibujos = new Map<string, string[]>();
    let actual: string[] = [];
    const contexto = new Proxy(
      {},
      {
        get: (_objeto, nombre: string) =>
          nombre === "getImageData"
            ? () => {
                const hecho = actual;
                actual = [];
                return { hecho };
              }
            : (...argumentos: unknown[]) => {
                actual.push(nombre);
                return argumentos;
              },
        set: (_objeto, nombre: string, valor: unknown) => {
          actual.push(`${nombre}=${String(valor)}`);
          return true;
        },
      },
    );
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = (() => contexto) as never;
    try {
      const imagenes = new Set<string>();
      const mapa = {
        hasImage: (nombre: string) => imagenes.has(nombre),
        addImage: (nombre: string, imagen: { hecho: string[] }) => {
          imagenes.add(nombre);
          dibujos.set(nombre, imagen.hecho);
        },
      };
      registrarIconos(mapa as never, "#ffffff");
      expect([...imagenes].sort()).toEqual(
        [
          ICONO_BANDERA_ELEGIDA,
          ...["atribuido", "confirmado", "desmentido", "notificado"].map(nombreIcono),
          ...ESTADOS_AVISO.map(nombreIconoAviso),
        ].sort(),
      );
      // La etiqueta de un aviso no es un círculo relleno: una píldora con punta (líneas rectas),
      // fondo de panel opaco y solo el borde del color de su estado.
      for (const estado of ESTADOS_AVISO) {
        const hecho = dibujos.get(nombreIconoAviso(estado)) ?? [];
        expect(hecho, estado).toContain("lineTo");
        expect(hecho, estado).toContain(`fillStyle=${PALETA.panelSolido}`);
        expect(hecho, estado).toContain(`strokeStyle=${COLOR_DE_AVISO[estado]}`);
        expect(hecho.filter((paso) => paso.startsWith("fillStyle=")), estado).toEqual([
          `fillStyle=${PALETA.panelSolido}`,
        ]);
      }
      for (const estado of ["notificado", "confirmado", "desmentido"]) {
        const hecho = dibujos.get(nombreIcono(estado)) ?? [];
        expect(hecho, estado).toContain("arc");
        for (const prohibido of ["rect", "lineTo", "moveTo", "ellipse", "quadraticCurveTo", "bezierCurveTo"]) {
          expect(hecho, `${estado} ${prohibido}`).not.toContain(prohibido);
        }
        expect(hecho.includes("fill"), estado).toBe(estado !== "desmentido");
        expect(hecho.includes(`fillStyle=${COLOR_ESTADO[estado as "notificado"]}`), estado).toBe(estado !== "desmentido");
      }
      for (const nombre of [nombreIcono("atribuido"), ICONO_BANDERA_ELEGIDA]) {
        const hecho = dibujos.get(nombre) ?? [];
        expect(hecho, nombre).not.toContain("arc");
        expect(hecho, nombre).not.toContain("rect");
        expect(hecho, nombre).toContain("lineTo");
      }
    } finally {
      HTMLCanvasElement.prototype.getContext = original;
    }
  });

  it("el aviso en directo es una etiqueta levantada que no pisa el número de un grupo", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const capa = layers.find((c) => c.id === CAPA_DIRECTO);
    expect(capa?.type).toBe("symbol");
    const disposicion = (capa as { layout: Record<string, unknown> }).layout;
    // Ni círculo ni relleno del color del estado: su icono y el OACI escrito dentro.
    expect(layers.filter((c) => c.id.startsWith("directo") && c.type === "circle")).toHaveLength(0);
    expect(disposicion["icon-image"]).toEqual(["concat", "aviso-", ["get", "estado"]]);
    expect(disposicion["text-field"]).toEqual(["get", "oaci"]);
    expect(disposicion["icon-anchor"]).toBe("bottom");
    // Encima de todo, solo el número de los grupos: el de un grupo vecino tampoco queda tapado.
    expect(layers.at(-1)?.id).toBe(CAPA_NUMERO_GRUPOS);
    expect(layers.at(-2)?.id).toBe(CAPA_DIRECTO);
    // Geometría, en píxeles sobre el punto del aeropuerto (y hacia arriba es negativo):
    // la punta queda `hueco` píxeles por encima, y el número de un grupo centrado en el
    // mismo punto ocupa como mucho media altura de su letra por encima.
    const [, desplazamiento] = disposicion["icon-offset"] as [number, number];
    const puntaDeLaEtiqueta = desplazamiento;
    const arribaDelNumero = -TAMANO_NUMERO_GRUPO / 2;
    expect(puntaDeLaEtiqueta).toBeLessThan(arribaDelNumero);
    expect(Math.abs(puntaDeLaEtiqueta)).toBe(ETIQUETA_AVISO.hueco);
    // El OACI va centrado en la píldora, no en el punto.
    const [, textoY] = disposicion["text-offset"] as [number, number];
    expect(textoY * TAMANO_TEXTO_AVISO).toBeCloseTo(-CENTRO_TEXTO_AVISO);
    const abajoDelTexto = textoY * TAMANO_TEXTO_AVISO + TAMANO_TEXTO_AVISO / 2;
    expect(abajoDelTexto).toBeLessThan(arribaDelNumero);
    // Tampoco pisa el círculo relleno de un incidente suelto en el mismo punto.
    expect(puntaDeLaEtiqueta).toBeLessThan(-LADO_ICONO / 4);
    // Y el número de un grupo va encima de los incidentes sueltos, con halo del fondo.
    const numero = layers.find((c) => c.id === CAPA_NUMERO_GRUPOS) as { paint: Record<string, unknown> };
    expect(numero.paint["text-halo-width"]).toBeGreaterThan(0);
    const orden = layers.map((c) => c.id);
    expect(orden.indexOf(CAPA_NUMERO_GRUPOS)).toBeGreaterThan(orden.indexOf(CAPA_INCIDENTES_GRAVES));
    expect(orden.indexOf(CAPA_NUMERO_GRUPOS)).toBeGreaterThan(orden.indexOf(CAPA_INCIDENTES_DISCRETOS));
    // Sin pulso: ningún pulso se dibuja para los avisos.
    expect(JSON.stringify(disposicion)).not.toContain("pulso");
  });

  it("la leyenda tiene cuatro entradas: notificado, confirmado, atribuido y desmentido", () => {
    render(<Ayuda t={es} abierta={false} onCerrar={() => undefined} />);
    const leyenda = document.querySelector("[data-leyenda-estados]");
    const entradas = Array.from(leyenda?.querySelectorAll("li") ?? []);
    expect(entradas.map((li) => li.textContent)).toEqual([
      es.estado.notificado,
      es.estado.confirmado,
      es.estado.atribuido,
      es.estado.desmentido,
    ]);
    // Ningún otro símbolo de incidente en la ayuda: nada de formas por tipo.
    const simbolos = document.querySelectorAll("svg[data-circulo], svg[data-bandera]");
    expect(simbolos).toHaveLength(4);
  });

  it("en el mapa, el pie del mástil es el punto del incidente: el centro del icono", () => {
    expect(BANDERA.lado).toBe(LADO_ICONO);
    expect(BANDERA.pie).toEqual([LADO_ICONO / 2, LADO_ICONO / 2]);
    // El mástil sube en vertical desde el pie y todo el banderín queda arriba a la derecha.
    expect(BANDERA.tope[0]).toBe(BANDERA.pie[0]);
    expect(BANDERA.tope[1]).toBeLessThan(BANDERA.pie[1]);
    for (const [x, y] of BANDERA.banderin) {
      expect(x).toBeGreaterThanOrEqual(BANDERA.pie[0]);
      expect(y).toBeLessThan(BANDERA.pie[1]);
      expect(x).toBeLessThanOrEqual(LADO_ICONO);
      expect(y).toBeGreaterThanOrEqual(0);
    }
    // 13 px de mástil y 11 de banderín: tan grande como las formas de los demás (14 px).
    expect(BANDERA.pie[1] - BANDERA.tope[1]).toBe(13);
    const ancho = Math.max(...BANDERA.banderin.map((p) => p[0])) - BANDERA.pie[0];
    expect(ancho).toBeGreaterThanOrEqual(10);
    // Y en la leyenda y las fichas, el pie abajo a la izquierda.
    expect(BANDERA_SIMBOLO.pie[0]).toBeLessThan(BANDERA_SIMBOLO.lado / 3);
    expect(BANDERA_SIMBOLO.pie[1]).toBeGreaterThan((BANDERA_SIMBOLO.lado * 2) / 3);
  });

  it("en el mapa, el atribuido no lleva área, destello ni aro de selección; sí su bandera", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const capa = (id: string) => layers.find((c) => c.id === id) as { filter?: unknown };
    for (const id of ["areas-relleno", "areas-contorno", CAPA_RECIENTES, CAPA_SELECCION]) {
      expect(JSON.stringify(capa(id).filter), id).toContain(JSON.stringify(["!", ES_ATRIBUIDO]));
    }
    expect(capa(CAPA_SELECCION_BANDERA).filter).toEqual(ES_ATRIBUIDO);
    // Las capas de incidentes sueltos usan el icono sin cambiar el ancla (el centro = el pie).
    const graves = layers.find((c) => c.id === CAPA_INCIDENTES_GRAVES) as {
      layout: Record<string, unknown>;
    };
    expect(graves.layout["icon-anchor"]).toBeUndefined();
    // El grupo sigue siendo rojo si contiene atribuidos.
    expect(JSON.stringify(COLOR_DE_GRUPO)).toContain("n_atribuidos");
  });

  it("el área pulsable es la de los demás y, con el dedo, de 44 px", () => {
    // La caja del icono (lo que se pulsa con el ratón) es la misma para la bandera y las formas.
    expect(LADO_ICONO).toBeGreaterThanOrEqual(28);
    expect(OBJETIVO_TACTIL_PX).toBe(44);
  });

  it("la ficha dice «Confirmado · atribuido a…» con el actor y la autoridad", () => {
    const atribuido = detalleIncidente(
      incidente({
        estado: {
          actual: "atribuido",
          historial: [
            {
              estado: "atribuido",
              fecha: { valor: "2025-10-04T10:00Z", precision: "minuto" },
              fuente_id: "gdelt-0000000000000001",
            },
          ],
        },
        atribucion: {
          actor: "Rusia",
          autoridad: "Gobierno de Dinamarca",
          fecha: { valor: "2025-10-04T10:00Z", precision: "minuto" },
        },
      }),
    );
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={atribuido} />);
    const estado = container.querySelector("[data-estado-atribuido]");
    expect(estado?.textContent).toBe("Confirmado · atribuido a Rusia, según Gobierno de Dinamarca");
    expect(estado?.querySelector("[data-bandera]")).not.toBeNull();
    cleanup();
    const ingles = render(<FichaIncidente t={en} idioma="en" incidente={atribuido} />);
    expect(ingles.container.querySelector("[data-estado-atribuido]")?.textContent).toBe(
      "Confirmed · attributed to Rusia, according to Gobierno de Dinamarca",
    );
  });

  it("el verde de la barra de estado es el de «datos al día», no el de un estado", () => {
    const { container } = render(
      <BarraEstado
        t={es}
        actualizado="2026-10-03T10:17Z"
        sistema={null}
        ahora={new Date("2026-10-03T10:30:00Z")}
      />,
    );
    expect(container.innerHTML).toContain("bg-al-dia");
    expect(container.innerHTML).not.toContain("bg-confirmado");
  });
});

describe("pulso: solo las novedades desde la última visita", () => {
  const nuevos = ["EODI-2026-00001", "EODI-2026-00002"];
  const sinVer = { descartadas: false, recorridas: false, abiertos: new Set<string>() };

  it("laten los nuevos; en la primera visita no hay nuevos y no late nada", () => {
    expect([...novedadesQueLaten(nuevos, sinVer)]).toEqual(nuevos);
    expect(novedadesQueLaten([], sinVer).size).toBe(0);
  });

  it("se apagan al pulsar «Verlas» o «Descartar»", () => {
    expect(novedadesQueLaten(nuevos, { ...sinVer, recorridas: true }).size).toBe(0);
    expect(novedadesQueLaten(nuevos, { ...sinVer, descartadas: true }).size).toBe(0);
  });

  it("un incidente deja de latir al abrirlo; los demás siguen", () => {
    const abiertos = new Set([nuevos[0] ?? ""]);
    expect([...novedadesQueLaten(nuevos, { ...sinVer, abiertos })]).toEqual([nuevos[1]]);
  });
});
