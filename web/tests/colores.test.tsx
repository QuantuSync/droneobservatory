// @vitest-environment jsdom
// Colores de los estados: naranja notificado, rojo confirmado, aro rojo con la bandera dentro el
// atribuido, gris discontinuo desmentido; el verde, solo para «datos al día». Y el pulso: solo
// las novedades.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Ayuda } from "../src/componentes/Ayuda.tsx";
import { BarraEstado } from "../src/componentes/BarraEstado.tsx";
import { FichaIncidente } from "../src/componentes/FichaIncidente.tsx";
import { createExpression } from "@maplibre/maplibre-gl-style-spec";

import { BANDERAS, indiceBandera, nombreIconoAtribuido, varianteConjunta } from "../src/banderas.ts";
import { MarcaAtribuido, Simbolo } from "../src/componentes/Simbolo.tsx";
import { detalleIncidente } from "../src/datos/derivar.ts";
import { novedadesQueLaten } from "../src/estado/novedades.ts";
import { textoAtribuido, textos } from "../src/i18n/index.ts";
import {
  CAPA_ATRIBUIDOS,
  CAPA_FOCOS_ATRIBUIDOS,
  CAPA_NUMERO_ATRIBUIDOS,
  CAPA_GRUPOS,
  CAPA_INCIDENTES_GRAVES,
  CAPA_RECIENTES,
  CAPA_SELECCION,
  CAPA_SELECCION_ATRIBUIDO,
  CAPA_DIRECTO,
  CAPA_INCIDENTES_DISCRETOS,
  CAPA_NUMERO_GRUPOS,
  CENTRO_TEXTO_AVISO,
  TAMANO_NUMERO_GRUPO,
  TAMANO_TEXTO_AVISO,
  COLOR_DE_GRUPO,
  ES_ATRIBUIDO,
  FUENTE_ATRIBUIDOS,
  ICONO_ATRIBUIDO,
  RADIO_GRUPO_MINIMO,
  estilo,
} from "../src/mapa/estilo.ts";
import { OBJETIVO_TACTIL_PX } from "../src/mapa/Mapa.tsx";
import { nombreIcono } from "../src/mapa/geometria.ts";
import {
  COLOR_DE_AVISO,
  ESTADOS_AVISO,
  ETIQUETA_AVISO,
  ICONO_OBSTACULO,
  LADO as LADO_ICONO,
  RADIO_INCIDENTE,
  nombreIconoAviso,
  registrarIconos,
} from "../src/mapa/iconos.ts";
import {
  COLOR_ARO_ATRIBUIDO,
  COLOR_ESTADO,
  COLOR_FILO_ATRIBUIDO,
  MARCA_ATRIBUIDO,
  PALETA,
  RADIO_BANDERA,
  contraste,
} from "../src/paleta.ts";
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

  it("la capa de guerra es violeta y se separa del rojo, del naranja y del verde con daltonismo", () => {
    // Distancia de color CIELAB (ΔE 1976) entre dos colores sRGB.
    const lab = (hex: string): [number, number, number] => {
      const [r, g, b] = [1, 3, 5].map((i) => lineal(parseInt(hex.slice(i, i + 2), 16))) as [
        number,
        number,
        number,
      ];
      const x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047;
      const y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
      const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
      return [116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))];
    };
    const distancia = (a: string, b: string) => {
      const [p, q] = [lab(a), lab(b)];
      return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
    };
    // Violeta azulado: ni rojo, ni naranja, ni cian, ni dorado.
    expect(tono(PALETA.guerra)).toBeGreaterThan(245);
    expect(tono(PALETA.guerra)).toBeLessThan(275);
    const sinFiltro = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    const visiones: [string, number[][]][] = [["normal", sinFiltro], ...Object.entries(DALTONISMO)];
    const familia = [PALETA.guerra, PALETA.guerraClaro, PALETA.guerraTenue];
    const estados = [COLOR_ESTADO.confirmado, COLOR_ESTADO.notificado, PALETA.alDia];
    for (const [vision, matriz] of visiones) {
      for (const propio of familia) {
        for (const ajeno of estados) {
          // Medido: el principal queda a ΔE 80 o más del rojo con visión normal y con daltonismo
          // rojo-verde (el coral anterior, a 5 en deuteranopía).
          expect(distancia(simular(propio, matriz), simular(ajeno, matriz)), `${vision} ${propio} ${ajeno}`)
            .toBeGreaterThanOrEqual(30);
        }
      }
      const rojo = distancia(simular(PALETA.guerra, matriz), simular(COLOR_ESTADO.confirmado, matriz));
      if (vision !== "tritanopia") expect(rojo, vision).toBeGreaterThanOrEqual(75);
    }
    // Se lee sobre el fondo del mapa.
    expect(contraste(PALETA.guerra, PALETA.fondo)).toBeGreaterThanOrEqual(4.5);
    // Dentro de la capa las diferencias siguen: lo resaltado, lo principal y lo apagado.
    expect(contraste(PALETA.guerraClaro, PALETA.guerra)).toBeGreaterThanOrEqual(1.5);
    expect(contraste(PALETA.guerra, PALETA.guerraTenue)).toBeGreaterThanOrEqual(1.4);
  });

  it("los elementos de la capa de guerra usan su familia y no los colores de los estados", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const propias = layers.filter((c) => /^(ucrania-|rusia-|guerra-)/.test(c.id));
    expect(propias.length).toBeGreaterThan(8);
    const texto = JSON.stringify(propias);
    for (const color of [COLOR_ESTADO.confirmado, COLOR_ESTADO.notificado, PALETA.alDia, "#f25c4f"]) {
      expect(texto).not.toContain(color);
    }
    for (const id of ["guerra-impactos", "guerra-corredores", "ucrania-relleno", "rusia-relleno"]) {
      const capa = JSON.stringify(propias.find((c) => c.id === id));
      expect(
        [PALETA.guerra, PALETA.guerraClaro, PALETA.guerraTenue].some((c) => capa.includes(c)),
        id,
      ).toBe(true);
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

  it("un grupo es rojo si contiene algún confirmado y naranja si todos son notificados", () => {
    // Los atribuidos no entran en los grupos: van siempre con su propio marcador.
    expect(COLOR_DE_GRUPO).toEqual([
      "case",
      [">", ["get", "n_confirmados"], 0],
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

/** Los círculos del marcador de un atribuido, de fuera adentro: [radio, relleno]. */
function circulos(svg: Element | null): [number, string][] {
  return [...(svg?.querySelectorAll("circle") ?? [])]
    .filter((c) => c.parentElement?.tagName.toLowerCase() !== "clippath")
    .map((c) => [Number(c.getAttribute("r")), c.getAttribute("fill") ?? ""]);
}

describe("marcador de los atribuidos", () => {
  const m = MARCA_ATRIBUIDO;
  const fuera: [number, string][] = [
    [m.radio + m.halo, COLOR_FILO_ATRIBUIDO],
    [m.radio, COLOR_ARO_ATRIBUIDO],
    [m.radio - m.aro, COLOR_FILO_ATRIBUIDO],
  ];
  const punto: [number, string][] = [
    [m.punto + m.aroPunto, COLOR_ARO_ATRIBUIDO],
    [m.punto, COLOR_FILO_ATRIBUIDO],
  ];

  it("Estado: aro rojo grueso, filo oscuro y la bandera recortada en círculo, sin punto", () => {
    const { container } = render(<Simbolo estado="atribuido" atribucion={{ tipo: "estado", pais: "RU" }} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("data-atribuido")).toBe("RU");
    expect(svg?.hasAttribute("data-persona")).toBe(false);
    // Sin mástil ni paño: solo círculos y la bandera.
    expect(svg?.querySelectorAll("path, rect, polygon, line")).toHaveLength(0);
    expect(circulos(svg)).toEqual(fuera);
    const imagen = svg?.querySelector("image");
    expect(imagen?.getAttribute("href")).toBe("/banderas/ru.svg");
    expect(Number(imagen?.getAttribute("width"))).toBe(2 * RADIO_BANDERA);
    // Recortada en un círculo del radio de la bandera, centrada.
    const recorte = svg?.querySelector("clipPath circle");
    expect(Number(recorte?.getAttribute("r"))).toBe(RADIO_BANDERA);
    expect(imagen?.getAttribute("clip-path")).toBe(`url(#${svg?.querySelector("clipPath")?.id ?? ""})`);
    expect(imagen?.getAttribute("preserveAspectRatio")).toBe("xMidYMid slice");
    expect(svg?.querySelector("[data-punto]")).toBeNull();
  });

  it("persona con nacionalidad: la bandera de su país y el punto fijo en el centro", () => {
    const { container } = render(<Simbolo estado="atribuido" atribucion={{ tipo: "persona", pais: "RO" }} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("data-atribuido")).toBe("RO");
    expect(svg?.hasAttribute("data-persona")).toBe(true);
    expect(svg?.querySelector("image")?.getAttribute("href")).toBe("/banderas/ro.svg");
    expect(circulos(svg)).toEqual([...fuera, ...punto]);
    // Fijo: ninguna animación.
    expect(svg?.innerHTML).not.toMatch(/animate|latido|pulso/);
  });

  it("persona sin nacionalidad publicada: aro rojo, relleno rojo liso y el punto", () => {
    const { container } = render(<Simbolo estado="atribuido" atribucion={{ tipo: "persona", pais: null }} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("data-atribuido")).toBe("liso");
    expect(svg?.querySelector("image")).toBeNull();
    expect(circulos(svg)).toEqual([...fuera, [RADIO_BANDERA, COLOR_ARO_ATRIBUIDO], ...punto]);
  });

  it("sin bandera en el juego, o sin tipo, el marcador cae al aro rojo con relleno liso", () => {
    for (const atribucion of [{ tipo: "estado" as const, pais: "US" }, { tipo: null, pais: null }, null]) {
      const { container } = render(<Simbolo estado="atribuido" atribucion={atribucion} />);
      const svg = container.querySelector("svg");
      expect(svg?.getAttribute("data-atribuido")).toBe("liso");
      expect(circulos(svg)).toEqual([...fuera, [RADIO_BANDERA, COLOR_ARO_ATRIBUIDO]]);
      cleanup();
    }
  });

  it("el aro se lee rojo: grueso, del rojo de «confirmado», y el filo es oscuro y fino", () => {
    expect(COLOR_ARO_ATRIBUIDO).toBe(COLOR_ESTADO.confirmado);
    expect(m.aro).toBeGreaterThanOrEqual(3);
    // El aro rojo es al menos la cuarta parte del radio: se ve entero aunque la bandera sea
    // blanca o azul.
    expect(m.aro / m.radio).toBeGreaterThanOrEqual(0.25);
    expect(m.filo).toBe(1);
    expect(COLOR_FILO_ATRIBUIDO).toBe(PALETA.fondo);
    expect(contraste(COLOR_ARO_ATRIBUIDO, COLOR_FILO_ATRIBUIDO)).toBeGreaterThan(4.5);
    // Ningún color claro propio: lo claro, si lo hay, es de la bandera.
    const { container } = render(<MarcaAtribuido variante={{ bandera: null, persona: true }} />);
    expect(container.innerHTML).not.toMatch(/#e8eef6|#f4f7fb|#fff/i);
  });

  it("tamaño intermedio: mayor que un círculo suelto, menor que el grupo más pequeño", () => {
    const diametro = 2 * m.radio;
    expect(diametro).toBeGreaterThan(2 * RADIO_INCIDENTE);
    // El grupo más pequeño mide su radio más su trazo de 1,5 px.
    expect(diametro + 2 * m.halo).toBeLessThan(2 * (RADIO_GRUPO_MINIMO + 1.5));
    expect(diametro).toBeGreaterThanOrEqual(22);
    expect(diametro).toBeLessThanOrEqual(24);
  });

  it("varios en un marcador: con la bandera común, o liso si son de países distintos", () => {
    const ru = { bandera: "RU", persona: false };
    expect(varianteConjunta([ru, ru])).toEqual(ru);
    expect(varianteConjunta([ru, { bandera: "RU", persona: true }])).toEqual(ru);
    expect(varianteConjunta([{ bandera: "RO", persona: true }, { bandera: "RO", persona: true }])).toEqual({
      bandera: "RO",
      persona: true,
    });
    expect(varianteConjunta([ru, { bandera: "BY", persona: false }])).toEqual({ bandera: null, persona: false });
    expect(varianteConjunta([ru, { bandera: null, persona: false }])).toEqual({ bandera: null, persona: false });
  });

  it("en el mapa, la expresión del icono da la misma variante, también en los grupos", () => {
    const expresion = createExpression(ICONO_ATRIBUIDO, { type: "resolvedImage" } as never);
    if (expresion.result !== "success") throw new Error(JSON.stringify(expresion.value));
    const ru = indiceBandera("RU");
    const ro = indiceBandera("RO");
    const cargadas = [
      nombreIconoAtribuido({ bandera: null, persona: false }),
      nombreIconoAtribuido({ bandera: null, persona: true }),
      nombreIconoAtribuido({ bandera: "RU", persona: false }),
      nombreIconoAtribuido({ bandera: "RO", persona: true }),
    ];
    const icono = (propiedades: Record<string, number>, disponibles = cargadas) => {
      const resultado = expresion.value.evaluate(
        { zoom: 5 } as never,
        { type: 1, properties: propiedades } as never,
        {},
        undefined,
        disponibles,
      ) as { name: string };
      return resultado.name;
    };
    expect(icono({ bandera: ru, persona: 0 })).toBe(`atribuido-${String(ru)}`);
    expect(icono({ bandera: ro, persona: 1 })).toBe(`atribuido-${String(ro)}-p`);
    expect(icono({ bandera: -1, persona: 1 })).toBe("atribuido--1-p");
    expect(icono({ bandera: -1, persona: 0 })).toBe("atribuido--1");
    // Un grupo de países distintos: liso, sin punto.
    expect(icono({ bandera_min: ru - 1, bandera_max: ru, persona_min: 1 })).toBe("atribuido--1");
    // Un grupo del mismo país: su bandera.
    expect(icono({ bandera_min: ru, bandera_max: ru, persona_min: 0 })).toBe(`atribuido-${String(ru)}`);
    // Mientras la bandera no ha cargado, liso (con el punto si es una persona).
    expect(icono({ bandera: ro, persona: 1 }, cargadas.slice(0, 2))).toBe("atribuido--1-p");
  });

  it("textos para el lector de pantalla, en los dos idiomas", () => {
    expect(textoAtribuido(es, "es", { tipo: "estado", pais: "RU" })).toBe("Atribuido a Rusia");
    expect(textoAtribuido(es, "es", { tipo: "persona", pais: "RO" })).toBe("Atribuido a una persona de nacionalidad rumana");
    expect(textoAtribuido(es, "es", { tipo: "persona", pais: null })).toBe("Atribuido a una persona");
    expect(textoAtribuido(en, "en", { tipo: "estado", pais: "RU" })).toBe("Attributed to Russia");
    expect(textoAtribuido(en, "en", { tipo: "persona", pais: "RO" })).toBe("Attributed to a person of Romanian nationality");
    expect(textoAtribuido(en, "en", { tipo: "persona", pais: null })).toBe("Attributed to a person");
    const { container } = render(
      <Simbolo estado="atribuido" atribucion={{ tipo: "estado", pais: "RU" }} etiqueta="Atribuido a Rusia" />,
    );
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("role")).toBe("img");
    expect(svg?.getAttribute("aria-label")).toBe("Atribuido a Rusia");
  });

  it("hay una bandera por cada país del juego y su gentilicio en los dos idiomas", () => {
    expect(BANDERAS).toHaveLength(48);
    for (const pais of BANDERAS) {
      expect(textoAtribuido(es, "es", { tipo: "persona", pais }), pais).toMatch(/^Atribuido a una persona de nacionalidad \S/);
      expect(textoAtribuido(en, "en", { tipo: "persona", pais }), pais).toMatch(/^Attributed to a person of \S.* nationality$/);
    }
  });

  it("todo lo demás es un círculo: relleno el notificado y el confirmado, discontinuo el desmentido", () => {
    for (const estado of ["notificado", "confirmado", "desmentido"] as const) {
      const { container } = render(<Simbolo estado={estado} />);
      const svg = container.querySelector("svg");
      expect(svg?.hasAttribute("data-atribuido"), estado).toBe(false);
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

  it("en el mapa, un icono por estado: círculos y el marcador del atribuido, ninguna otra forma", () => {
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
      registrarIconos(mapa as never);
      expect([...imagenes].sort()).toEqual(
        [
          "atribuido--1",
          "atribuido--1-p",
          ICONO_OBSTACULO,
          ...["confirmado", "desmentido", "notificado"].map((estado) => nombreIcono(estado)),
          ...["confirmado", "desmentido", "notificado"].map((estado) => nombreIcono(estado, true)),
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
      // Los atribuidos sin bandera: solo círculos rellenos (filo, aro, filo, relleno rojo y, la
      // persona, el punto con su aro), en el rojo de «confirmado» y el color del fondo.
      for (const [nombre, rellenos] of [
        ["atribuido--1", 4],
        ["atribuido--1-p", 6],
      ] as const) {
        const hecho = dibujos.get(nombre) ?? [];
        for (const prohibido of ["rect", "lineTo", "moveTo", "stroke", "drawImage"]) {
          expect(hecho, `${nombre} ${prohibido}`).not.toContain(prohibido);
        }
        expect(hecho.filter((paso) => paso === "arc"), nombre).toHaveLength(rellenos);
        expect(hecho.filter((paso) => paso === "fill"), nombre).toHaveLength(rellenos);
        const colores = hecho.filter((paso) => paso.startsWith("fillStyle=")).map((paso) => paso.split("=")[1]);
        expect(new Set(colores), nombre).toEqual(new Set([COLOR_FILO_ATRIBUIDO, COLOR_ARO_ATRIBUIDO]));
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
    // Encima de todo: ni un grupo vecino ni un atribuido la pisan, y los nombres del mapa ceden
    // ante ella (ocupa su sitio al colocarlos).
    expect(layers.at(-1)?.id).toBe(CAPA_DIRECTO);
    expect(disposicion["icon-ignore-placement"]).toBe(false);
    expect(disposicion["text-ignore-placement"]).toBe(false);
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

  it("la leyenda: notificado, confirmado, atribuido a un Estado, a una persona y desmentido", () => {
    for (const [t, textosLeyenda] of [
      [es, ["Notificado", "Confirmado", "Atribuido por una autoridad a un Estado", "Atribuido por una autoridad a una persona", "Desmentido"]],
      [en, ["Reported", "Confirmed", "Attributed by an authority to a State", "Attributed by an authority to a person", "Denied"]],
    ] as const) {
      render(<Ayuda t={t} idioma={t === es ? "es" : "en"} abierta={false} onCerrar={() => undefined} />);
      const leyenda = document.querySelector("[data-leyenda-estados]");
      const entradas = Array.from(leyenda?.querySelectorAll("li") ?? []);
      expect(entradas.map((li) => li.textContent)).toEqual(textosLeyenda);
      // El de la persona lleva el punto; el del Estado, no. Ninguno lleva una bandera concreta.
      expect(leyenda?.querySelector("[data-leyenda-atribuido=estado] [data-punto]")).toBeNull();
      expect(leyenda?.querySelector("[data-leyenda-atribuido=persona] [data-punto]")).not.toBeNull();
      expect(leyenda?.querySelectorAll("image")).toHaveLength(0);
      // La bandera es la del país al que la autoridad lo atribuye, no una afirmación propia.
      expect(document.querySelector("[data-leyenda-bandera]")?.textContent).toBe(t.atribucion.bandera);
      // Ningún otro símbolo de incidente en la ayuda: nada de formas por tipo. Los dos de más
      // son los del lugar aproximado (notificado y confirmado), con su texto.
      expect(document.querySelectorAll("svg[data-circulo], svg[data-atribuido]")).toHaveLength(7);
      expect(document.querySelectorAll("[data-leyenda-aproximado] svg[data-aproximado]")).toHaveLength(2);
      cleanup();
    }
  });

  it("en el mapa, el marcador va centrado en el punto, y el del incidente abierto algo mayor", () => {
    const { layers } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    for (const id of [CAPA_ATRIBUIDOS, CAPA_SELECCION_ATRIBUIDO]) {
      const disposicion = (layers.find((c) => c.id === id) as { layout: Record<string, unknown> }).layout;
      expect(disposicion["icon-image"], id).toEqual(ICONO_ATRIBUIDO);
      expect(disposicion["icon-anchor"], id).toBeUndefined();
      expect(disposicion["icon-offset"], id).toBeUndefined();
    }
    const elegida = (layers.find((c) => c.id === CAPA_SELECCION_ATRIBUIDO) as { layout: Record<string, unknown> }).layout;
    expect(elegida["icon-size"]).toBeGreaterThan(1);
    // Ninguna capa del mapa dibuja ya una bandera con mástil.
    expect(JSON.stringify(layers)).not.toMatch(/"icon-image":"bandera"|bottom-left/);
  });

  it("en el mapa, el atribuido no lleva área ni aro de selección y su bandera va encima de todo", () => {
    const { layers, sources } = estilo("es", "https://droneobservatory.eu", "#f4f7fb");
    const capa = (id: string) => layers.find((c) => c.id === id) as { filter?: unknown; source?: string };
    for (const id of ["areas-relleno", "areas-contorno", CAPA_SELECCION]) {
      expect(JSON.stringify(capa(id).filter), id).toContain(JSON.stringify(["!", ES_ATRIBUIDO]));
    }
    expect(capa(CAPA_SELECCION_ATRIBUIDO).filter).toEqual(ES_ATRIBUIDO);
    // Los atribuidos tienen su propia fuente: un atribuido nunca queda dentro de un grupo de
    // círculos. En ella solo está su marcador (y la marca del foco térmico, al lado).
    expect(capa(CAPA_ATRIBUIDOS).source).toBe(FUENTE_ATRIBUIDOS);
    // Se juntan solo entre ellos (nunca con los círculos) y solo al alejar: desde el zoom de las
    // fichas, cada uno en su punto. El grupo sabe si todos llevan la misma bandera.
    const deBanderas = sources[FUENTE_ATRIBUIDOS] as { cluster?: boolean; clusterMaxZoom?: number };
    expect(deBanderas.cluster).toBe(true);
    expect(deBanderas.clusterMaxZoom).toBeLessThan(8);
    expect(Object.keys((deBanderas as { clusterProperties?: object }).clusterProperties ?? {})).toEqual(
      expect.arrayContaining(["bandera_min", "bandera_max", "persona_min"]),
    );
    const deLaFuente = layers.filter((c) => "source" in c && c.source === FUENTE_ATRIBUIDOS).map((c) => c.id);
    expect(deLaFuente).toEqual([CAPA_ATRIBUIDOS, CAPA_NUMERO_ATRIBUIDOS, CAPA_FOCOS_ATRIBUIDOS]);
    // El número, con el estilo del de los grupos.
    const numero = layers.find((c) => c.id === CAPA_NUMERO_ATRIBUIDOS) as { paint: Record<string, unknown>; layout: Record<string, unknown> };
    const deGrupo = layers.find((c) => c.id === CAPA_NUMERO_GRUPOS) as { paint: Record<string, unknown>; layout: Record<string, unknown> };
    expect(numero.paint).toEqual(deGrupo.paint);
    expect(numero.layout["text-size"]).toBe(deGrupo.layout["text-size"]);
    expect(numero.layout["text-font"]).toEqual(deGrupo.layout["text-font"]);
    expect(JSON.stringify(capa(CAPA_FOCOS_ATRIBUIDOS).filter)).toContain("foco");
    expect(capa(CAPA_RECIENTES).source).not.toBe(FUENTE_ATRIBUIDOS);
    // Por encima de los círculos y de los grupos; y los nombres del mapa ceden ante él.
    const orden = layers.map((c) => c.id);
    for (const debajo of [CAPA_GRUPOS, CAPA_INCIDENTES_GRAVES, CAPA_INCIDENTES_DISCRETOS]) {
      expect(orden.indexOf(CAPA_ATRIBUIDOS), debajo).toBeGreaterThan(orden.indexOf(debajo));
    }
    // Pero el número de un grupo vecino va por encima de todos sus marcadores: se lee siempre.
    for (const debajo of [CAPA_ATRIBUIDOS, CAPA_NUMERO_ATRIBUIDOS, CAPA_FOCOS_ATRIBUIDOS, CAPA_SELECCION_ATRIBUIDO]) {
      expect(orden.indexOf(CAPA_NUMERO_GRUPOS), debajo).toBeGreaterThan(orden.indexOf(debajo));
    }
    const disposicion = (layers.find((c) => c.id === CAPA_ATRIBUIDOS) as { layout: Record<string, unknown> }).layout;
    expect(disposicion["icon-image"]).toEqual(ICONO_ATRIBUIDO);
    expect(disposicion["icon-allow-overlap"]).toBe(true);
    expect(disposicion["icon-ignore-placement"]).toBe(false);
    // También abierto: el nombre del lugar no queda partido debajo del marcador.
    const abierto = (layers.find((c) => c.id === CAPA_SELECCION_ATRIBUIDO) as { layout: Record<string, unknown> })
      .layout;
    expect(abierto["icon-ignore-placement"]).toBe(false);
  });

  it("el área pulsable es la de los demás y, con el dedo, de 44 px", () => {
    // La caja del icono (lo que se pulsa con el ratón) es al menos la del marcador.
    expect(LADO_ICONO).toBeGreaterThanOrEqual(2 * (MARCA_ATRIBUIDO.radio + MARCA_ATRIBUIDO.halo));
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
          actor: "Russland",
          autoridad: "Bundesregierung",
          fecha: { valor: "2025-10-04T10:00Z", precision: "minuto" },
          tipo: "estado",
          pais: "RU",
        },
      }),
    );
    const { container } = render(<FichaIncidente t={es} idioma="es" incidente={atribuido} />);
    const estado = container.querySelector("[data-estado-atribuido]");
    // El país, a partir de su código y no con el texto de la fuente; la autoridad, traducida.
    expect(estado?.textContent).toBe(
      "Confirmado · atribuido a Rusia, según el Gobierno federal alemán (Bundesregierung)",
    );
    // Junto al texto, el marcador con su bandera y su texto alternativo.
    const marca = estado?.querySelector("svg[data-atribuido]");
    expect(marca?.getAttribute("data-atribuido")).toBe("RU");
    expect(marca?.getAttribute("aria-label")).toBe("Atribuido a Rusia");
    // El mismo marcador en la cabecera de la ficha y en el paso a atribuido del historial.
    expect(container.querySelectorAll("svg[data-atribuido=RU]")).toHaveLength(3);
    expect(container.innerHTML).not.toContain("data-bandera");
    cleanup();
    const ingles = render(<FichaIncidente t={en} idioma="en" incidente={atribuido} />);
    expect(ingles.container.querySelector("[data-estado-atribuido]")?.textContent).toBe(
      "Confirmed · attributed to Russia, according to the German Federal Government (Bundesregierung)",
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
