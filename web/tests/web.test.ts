import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import * as vocabulario from "../src/datos/vocabulario.ts";
import { en } from "../src/i18n/en.ts";
import { es } from "../src/i18n/es.ts";
import { fecha, fechaHora, instante, numero, pais, rango, region } from "../src/i18n/index.ts";
import { areas, circulo, destino, lineasDeEpisodio, pilas } from "../src/mapa/geometria.ts";
import { ACENTO_POR_DEFECTO, COLOR_ESTADO, PALETA, contraste } from "../src/paleta.ts";
import { analizarRuta, fichaDeId } from "../src/rutas.ts";
import { NOMBRE, rutaDeFicha, rutaDeIdioma } from "../src/sitio.ts";
import { resumirIncidente } from "../src/datos/derivar.ts";
import { incidente } from "./ejemplos.ts";

const WEB = join(import.meta.dirname, "..");

/** Forma de un diccionario: las claves y, en las funciones, solo que son funciones. */
function forma(valor: unknown): unknown {
  if (typeof valor === "function") return "función";
  if (Array.isArray(valor)) return valor.map(forma);
  if (typeof valor === "object" && valor !== null) {
    return Object.fromEntries(Object.entries(valor).map(([clave, hijo]) => [clave, forma(hijo)]));
  }
  return typeof valor;
}

function textosDe(valor: unknown): string[] {
  if (typeof valor === "string") return [valor];
  if (typeof valor === "function") {
    return [String((valor as (...a: unknown[]) => unknown)("x", "y"))];
  }
  if (typeof valor === "object" && valor !== null) return Object.values(valor).flatMap(textosDe);
  return [];
}

describe("textos en español e inglés", () => {
  it("los dos idiomas tienen exactamente las mismas claves", () => {
    const sinSecciones = (t: typeof es) => ({ ...t, metodologia: { ...t.metodologia, secciones: 0 } });
    expect(forma(sinSecciones(en))).toEqual(forma(sinSecciones(es)));
  });

  it("la metodología tiene las mismas secciones y los mismos enlaces en los dos", () => {
    const esqueleto = (t: typeof es) =>
      t.metodologia.secciones.map((seccion) => ({
        id: seccion.id,
        bloques: seccion.bloques.map((bloque) =>
          "parrafo" in bloque ? "parrafo" : bloque.lista.map((e) => e.marca ?? null),
        ),
      }));
    const enlaces = (t: typeof es) =>
      JSON.stringify(t.metodologia.secciones).match(/"enlace":"[^"]+"/g);
    expect(esqueleto(en)).toEqual(esqueleto(es));
    expect(enlaces(en)).toEqual(enlaces(es));
  });

  it("la metodología cubre lo que tiene que explicar", () => {
    expect(es.metodologia.secciones.map((s) => s.id)).toEqual([
      "que",
      "tipos",
      "estados",
      "presencia",
      "almirantazgo",
      "agrupacion",
      "declaraciones",
      "historial",
      "fuentes",
      "focos",
      "sesgo",
      "licencias",
    ]);
    const texto = JSON.stringify(es.metodologia);
    for (const obligado of [
      "Solo drones",
      "Copenhague",
      "extracción automática validada por reglas",
      "Apache-2.0",
      "CC BY 4.0",
      "OpenStreetMap",
      "Protomaps",
      "ODbL",
      "Natural Earth",
      "https://www.gdeltproject.org/",
      "GeoNames",
      "NASA FIRMS",
      "no demuestra nada",
      "antorchas",
      "nubes",
    ]) {
      expect(texto).toContain(obligado);
    }
  });

  it("la atribución de NASA FIRMS va completa en los dos idiomas", () => {
    const AGRADECIMIENTO =
      "We acknowledge the use of data and/or imagery from NASA's Fire Information for " +
      "Resource Management System (FIRMS) (https://www.earthdata.nasa.gov/firms), part of " +
      "NASA's Earth Science Data and Information System (ESDIS).";
    for (const t of [es, en]) {
      const licencias = t.metodologia.secciones.find((s) => s.id === "licencias");
      const textos = (licencias?.bloques ?? []).flatMap((bloque) =>
        "lista" in bloque
          ? bloque.lista.map((item) =>
              item.texto.map((trozo) => (typeof trozo === "string" ? trozo : trozo.texto)).join(""),
            )
          : [],
      );
      expect(textos).toContain(AGRADECIMIENTO);
    }
    expect(JSON.stringify(en.metodologia)).toContain("absence of a hotspot proves nothing");
  });

  it("todo valor de las listas cerradas tiene su texto", () => {
    for (const t of [es, en]) {
      expect(Object.keys(t.tipo).sort()).toEqual([...vocabulario.TIPOS].sort());
      expect(Object.keys(t.estado).sort()).toEqual([...vocabulario.ESTADOS].sort());
      expect(Object.keys(t.presencia).sort()).toEqual([...vocabulario.PRESENCIAS].sort());
      expect(Object.keys(t.precision).sort()).toEqual([...vocabulario.PRECISIONES].sort());
      expect(Object.keys(t.categoria).sort()).toEqual([...vocabulario.CATEGORIAS_OBJETIVO].sort());
      expect(Object.keys(t.medida).sort()).toEqual([...vocabulario.MEDIDAS].sort());
      expect(Object.keys(t.sentido).sort()).toEqual([...vocabulario.SENTIDOS].sort());
      expect(Object.keys(t.imprecisa.nivel).sort()).toEqual([...vocabulario.NIVELES_UBICACION].sort());
      expect(Object.keys(t.ficha.danos).sort()).toEqual([...vocabulario.NIVELES_DANOS].sort());
      expect(Object.keys(t.categoriaUcrania).sort()).toEqual(
        [...vocabulario.CATEGORIAS_OBJETIVO_UCRANIA].sort(),
      );
    }
  });

  it("el nombre del proyecto no se traduce", () => {
    expect(NOMBRE).toBe("European Observatory of Drone Incidents");
    expect(textosDe(es).join(" ")).not.toMatch(/Observatorio Europeo/i);
    expect(es.compartir.titulo).toContain(NOMBRE);
    expect(en.compartir.titulo).toContain(NOMBRE);
  });

  it("las regiones de los dos idiomas son las del mapa (Ucrania y Rusia)", () => {
    const delMapa = ["ucrania-regiones.geojson", "rusia-regiones.geojson"]
      .flatMap((fichero) => {
        const geojson = JSON.parse(
          readFileSync(join(WEB, "public", "mapa", fichero), "utf-8"),
        ) as { features: { properties: { iso: string } }[] };
        return geojson.features.map((f) => f.properties.iso);
      })
      .sort();
    expect(Object.keys(es.regiones).sort()).toEqual(delMapa);
    expect(Object.keys(en.regiones).sort()).toEqual(delMapa);
  });
});

describe("formato", () => {
  it("escribe las fechas como dd/mm/aaaa y las horas en UTC", () => {
    expect(fecha(new Date("2026-09-30T12:42:00Z"))).toBe("30/09/2026");
    expect(fechaHora("2026-09-30T12:42Z")).toBe("30/09/2026 · 12:42 UTC");
    expect(fechaHora("2026-01-05T03:07Z")).toBe("05/01/2026 · 03:07 UTC");
  });

  it("no da la hora de un instante que solo conoce el día", () => {
    expect(instante({ valor: "2026-09-13T00:00Z", precision: "dia" })).toBe("13/09/2026");
    expect(instante({ valor: "2026-09-13T11:30Z", precision: "aproximada" })).toBe("13/09/2026");
    expect(instante({ valor: "2026-09-08T14:30Z", precision: "minuto" })).toBe(
      "08/09/2026 · 14:30 UTC",
    );
  });

  it("escribe los rangos y calla lo desconocido", () => {
    expect(rango({ min: 4, max: 4 }, "es")).toBe("4");
    expect(rango({ min: 2, max: 10 }, "es")).toBe("2–10");
    expect(rango("desconocido", "es")).toBeNull();
    expect(rango(undefined, "en")).toBeNull();
    expect(numero(2401, "en")).toBe("2,401");
    expect(numero(2401, "es")).toBe("2.401");
  });

  it("nombra países y regiones en cada idioma, y deja el código si no los conoce", () => {
    expect(pais("DE", "es")).toBe("Alemania");
    expect(pais("DE", "en")).toBe("Germany");
    expect(region("UA-63", "es")).toBe("Járkov");
    expect(region("UA-63", "en")).toBe("Kharkiv");
    expect(region("RU-BEL", "es")).toBe("Bélgorod");
    expect(region("RU-BEL", "en")).toBe("Belgorod");
    expect(region("XX-YY", "es")).toBe("XX-YY");
  });
});

describe("rutas", () => {
  it("lee el idioma y la ficha de la dirección", () => {
    expect(analizarRuta("/")).toEqual({ idioma: "es", ficha: null });
    expect(analizarRuta("/en")).toEqual({ idioma: "en", ficha: null });
    expect(analizarRuta("/en/")).toEqual({ idioma: "en", ficha: null });
    expect(analizarRuta("/EODI-2025-00210")).toEqual({
      idioma: "es",
      ficha: { clase: "incidente", id: "EODI-2025-00210" },
    });
    expect(analizarRuta("/en/EODI-UA-2026-1014")).toEqual({
      idioma: "en",
      ficha: { clase: "ataque", id: "EODI-UA-2026-1014" },
    });
  });

  it("no toma por ficha lo que no es un identificador", () => {
    for (const ruta of ["/EODI-1-2", "/enlace", "/en/otra/cosa", "/EODI-2025-00210/extra"]) {
      expect(analizarRuta(ruta).ficha).toBeNull();
    }
    expect(fichaDeId("<script>")).toBeNull();
  });

  it("la ruta de una ficha se vuelve a leer igual", () => {
    for (const idioma of ["es", "en"] as const) {
      for (const id of ["EODI-2025-00210", "EODI-UA-2026-1014"]) {
        expect(analizarRuta(rutaDeFicha(id, idioma))).toMatchObject({ idioma, ficha: { id } });
      }
      expect(analizarRuta(rutaDeIdioma(idioma))).toEqual({ idioma, ficha: null });
    }
  });
});

describe("paleta", () => {
  const css = readFileSync(join(WEB, "src", "estilos.css"), "utf-8");
  const token = (nombre: string) => new RegExp(`--color-${nombre}: (#[0-9a-f]{6});`).exec(css)?.[1];

  it("los colores del mapa son los de la hoja de estilos", () => {
    expect(token("fondo")).toBe(PALETA.fondo);
    expect(token("panel-solido")).toBe(PALETA.panelSolido);
    expect(token("elevado")).toBe(PALETA.elevado);
    expect(token("linea")).toBe(PALETA.linea);
    // El acento es una sola variable, --acento, de la que tira toda la interfaz.
    expect(/--acento: (#[0-9a-f]{6});/.exec(css)?.[1]).toBe(ACENTO_POR_DEFECTO);
    expect(css).toContain("--color-acento: var(--acento);");
    expect(css).not.toMatch(/dorado|#c9a54a/i);
    expect(token("texto")).toBe(PALETA.texto);
    expect(token("secundario")).toBe(PALETA.secundario);
    expect(token("confirmado")).toBe(COLOR_ESTADO.confirmado);
    expect(token("notificado")).toBe(COLOR_ESTADO.notificado);
    expect(token("atribuido")).toBe(COLOR_ESTADO.atribuido);
    expect(token("desmentido")).toBe(COLOR_ESTADO.desmentido);
  });

  it("los colores de texto cumplen el contraste AA sobre todas las superficies", () => {
    const AA_TEXTO = 4.5;
    for (const superficie of [PALETA.fondo, PALETA.panelSolido, PALETA.elevado]) {
      for (const texto of [
        PALETA.texto,
        PALETA.secundario,
        ACENTO_POR_DEFECTO,
        ...Object.values(COLOR_ESTADO),
      ]) {
        expect(contraste(texto, superficie), `${texto} sobre ${superficie}`).toBeGreaterThanOrEqual(
          AA_TEXTO,
        );
      }
    }
    // Texto oscuro sobre el acento (el botón principal).
    expect(contraste(PALETA.fondo, ACENTO_POR_DEFECTO)).toBeGreaterThanOrEqual(AA_TEXTO);
  });

  it("los colores de estado cumplen el contraste AA de los elementos gráficos", () => {
    const AA_GRAFICO = 3;
    for (const superficie of [PALETA.fondo, PALETA.panelSolido, PALETA.elevado]) {
      for (const color of Object.values(COLOR_ESTADO)) {
        expect(contraste(color, superficie), `${color} sobre ${superficie}`).toBeGreaterThanOrEqual(
          AA_GRAFICO,
        );
      }
    }
  });

  it("no hay radios grandes", () => {
    const radios = [...css.matchAll(/--radius-(\w+): (\d+)px;/g)]
      .filter(([, nombre]) => nombre !== "full")
      .map(([, , px]) => Number(px));
    expect(Math.max(...radios)).toBeLessThanOrEqual(3);
  });

  it("el acento no se confunde con ningún color de estado", () => {
    const tono = (hex: string) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [
        number,
        number,
        number,
      ];
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      if (max === min) return null;
      const d = max - min;
      const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
      return h * 60;
    };
    const acento = tono(ACENTO_POR_DEFECTO) ?? 0;
    const SEPARACION_MINIMA_GRADOS = 45;
    for (const color of [COLOR_ESTADO.confirmado, COLOR_ESTADO.notificado, COLOR_ESTADO.atribuido]) {
      const diferencia = Math.abs(acento - (tono(color) ?? 0));
      expect(Math.min(diferencia, 360 - diferencia), color).toBeGreaterThanOrEqual(
        SEPARACION_MINIMA_GRADOS,
      );
    }
  });
});

describe("geometría del mapa", () => {
  const munich = resumirIncidente(incidente());
  const diest = resumirIncidente(incidente({ id: "EODI-2025-00016", tipo: "sobrevuelo" }, [5, 51]));

  it("un punto a 111 km al norte sube un grado de latitud", () => {
    const [lon, lat] = destino(10, 50, 111.195, 0);
    expect(lon).toBeCloseTo(10, 6);
    expect(lat).toBeCloseTo(51, 3);
  });

  it("el área de precisión es un polígono cerrado con el radio del incidente", () => {
    const anillo = circulo(11.7861, 48.3536, 5).coordinates[0]!;
    expect(anillo[0]).toEqual(anillo[anillo.length - 1]);
    const norte = anillo[0]!;
    expect((norte[1] ?? 0) - 48.3536).toBeCloseTo(5 / 111.195, 3);
    expect(areas([munich]).features[0]?.properties.estado).toBe("notificado");
  });

  it("cada punto lleva el icono de su tipo y su estado", () => {
    const opciones = { hoy: 0, novedades: new Set<string>() };
    expect(pilas([munich, diest], opciones).features.map((f) => f.properties.icono)).toEqual([
      "interrupcion_aeroportuaria-notificado",
      "sobrevuelo-notificado",
    ]);
  });

  it("varios incidentes en el mismo punto son un solo símbolo: nada de estrellas", () => {
    // Un cuadrado (sobrevuelo) y un rombo (incursión) en el mismo sitio hacían una estrella de
    // ocho puntas. Ahora se dibuja el más grave con el número de incidentes.
    const mismoSitio = [
      resumirIncidente(incidente({ id: "EODI-2026-00001", tipo: "sobrevuelo" }, [25.4, 47.53333])),
      resumirIncidente(
        incidente(
          {
            id: "EODI-2026-00002",
            tipo: "incursion",
            estado: {
              actual: "confirmado",
              historial: [{ estado: "confirmado", fecha: { valor: "2026-01-01T00:00Z", precision: "dia" } }],
            },
          },
          [25.4, 47.53333],
        ),
      ),
    ];
    const coleccion = pilas(mismoSitio, { hoy: 0, novedades: new Set(["EODI-2026-00001"]) });
    expect(coleccion.features).toHaveLength(1);
    expect(coleccion.features[0]?.properties).toMatchObject({
      id: "EODI-2026-00002",
      ids: "EODI-2026-00002,EODI-2026-00001",
      n: 2,
      tipo: "incursion",
      estado: "confirmado",
      grave: 1,
      n_confirmados: 1,
      n_notificados: 1,
      novedad: 1,
    });
  });

  it("marca lo que empezó en las últimas 24 horas", () => {
    expect(pilas([munich], { hoy: munich.dia, novedades: new Set() }).features[0]?.properties.reciente).toBe(1);
    expect(pilas([munich], { hoy: munich.dia + 5, novedades: new Set() }).features[0]?.properties.reciente).toBe(0);
  });

  it("la línea de un episodio solo une incidentes visibles y necesita dos", () => {
    const episodios = [{ id: "EODI-EP-2025-0001", incidentes: [munich.id, diest.id] }];
    expect(lineasDeEpisodio(episodios, [munich, diest]).features[0]?.geometry.coordinates).toEqual([
      [munich.punto?.lon, munich.punto?.lat],
      [diest.punto?.lon, diest.punto?.lat],
    ]);
    expect(lineasDeEpisodio(episodios, [munich]).features).toEqual([]);
  });
});
