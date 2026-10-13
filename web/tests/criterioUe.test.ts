// Las fronteras y los nombres del mapa siguen la posición de la Unión Europea: ningún rótulo de
// las entidades que no reconoce (norte de Chipre, Transnistria, Abjasia, Osetia del Sur, las
// «repúblicas populares» de Donetsk y de Lugansk), ninguna frontera internacional que separe de
// su país Crimea, el Donbás ocupado, Transnistria, Abjasia, Osetia del Sur o el norte de Chipre,
// y Crimea con Ucrania en los polígonos de país. Los filtros del estilo se evalúan como lo hace
// MapLibre (featureFilter) sobre rasgos reales de las teselas (tests/fixtures) y sobre nombres
// en varias lenguas.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { featureFilter } from "@maplibre/maplibre-gl-style-spec";
import type { ICanonicalTileID } from "@maplibre/maplibre-gl-style-spec";
import type { FilterSpecification, LayerSpecification } from "maplibre-gl";
import { describe, expect, it } from "vitest";

import { textos } from "../src/i18n/index.ts";
import { CAPAS_CON_CRITERIO } from "../src/mapa/criterioUe.ts";
import { estilo } from "../src/mapa/estilo.ts";
import { seccionesDeMetodologia } from "../src/rutasEnLaWeb.ts";

const WEB = join(import.meta.dirname, "..");

type Propiedades = Record<string, string | number | boolean>;
interface Rasgo {
  capa: "boundaries" | "places";
  tipo: 1 | 2;
  propiedades: Propiedades;
  geometria: [number, number][][];
}
interface Tesela {
  zona: string;
  z: number;
  x: number;
  y: number;
  rasgos: Rasgo[];
}

const TESELAS = (
  JSON.parse(readFileSync(join(WEB, "tests", "fixtures", "teselas-criterio-ue.json"), "utf-8")) as {
    extension: number;
    teselas: Tesela[];
  }
).teselas;

/** MapLibre trabaja con teselas de extensión 8192; el MVT trae 4096. */
const ESCALA = 8192 / 4096;

function capasDe(idioma: "es" | "en"): Map<string, LayerSpecification> {
  return new Map(estilo(idioma, "https://ejemplo.org", "#ffffff").layers.map((capa) => [capa.id, capa]));
}

/** Si la capa dibuja el rasgo en esa tesela, con el mismo filtro que evalúa MapLibre. */
function dibuja(capa: LayerSpecification, rasgo: Rasgo, tesela: Pick<Tesela, "z" | "x" | "y">): boolean {
  const filtro = "filter" in capa ? (capa.filter as FilterSpecification | undefined) : undefined;
  const evaluado = featureFilter(filtro, `layers.${capa.id}.filter`);
  return evaluado.filter(
    { zoom: tesela.z },
    {
      type: rasgo.tipo,
      properties: rasgo.propiedades,
      geometry: rasgo.geometria.map((linea) => linea.map(([x, y]) => ({ x: x * ESCALA, y: y * ESCALA }))),
    },
    // «within» solo usa z, x e y de la tesela.
    { z: tesela.z, x: tesela.x, y: tesela.y } as unknown as ICanonicalTileID,
  );
}

function lonLat(tesela: Tesela, [px, py]: [number, number]): [number, number] {
  const n = 2 ** tesela.z;
  const lon = ((tesela.x + px / 4096) / n) * 360 - 180;
  const y = (tesela.y + py / 4096) / n;
  const lat = (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI;
  return [lon, lat];
}

/** Línea entera entre el istmo de Perekop, el de Chongar y la flecha de Arabat. */
function enElIstmoDeCrimea(tesela: Tesela, rasgo: Rasgo): boolean {
  return rasgo.geometria.flat().every((punto) => {
    const [lon, lat] = lonLat(tesela, punto);
    return lon > 33.5 && lon < 35.1 && lat > 45.7 && lat < 46.3;
  });
}

const lineas = TESELAS.flatMap((tesela) =>
  tesela.rasgos.filter((r) => r.capa === "boundaries").map((rasgo) => ({ tesela, rasgo })),
);
const rotulos = TESELAS.flatMap((tesela) =>
  tesela.rasgos.filter((r) => r.capa === "places").map((rasgo) => ({ tesela, rasgo })),
);
const codigo = (r: Rasgo) => r.propiedades.brk_a3;

/** Contornos de Natural Earth de entidades no reconocidas y zonas de la ONU, por su código. */
const NO_RECONOCIDAS: Record<string, string> = {
  B35: "Abjasia",
  B36: "Transnistria",
  B37: "Osetia del Sur",
  B90: "Donbás ocupado",
  C02: "«República Popular de Donetsk»",
  C03: "«República Popular de Lugansk»",
  B20: "norte de Chipre",
  B43: "zona de separación de Chipre",
};

describe.each(["es", "en"] as const)("mapa de fondo según la UE (%s)", (idioma) => {
  const capas = capasDe(idioma);
  const pais = capas.get("boundaries_country");
  const interior = capas.get("boundaries");
  const rotuloPais = capas.get("places_country");
  const rotuloRegion = capas.get("places_region");

  it("las capas con criterio siguen en el estilo de Protomaps", () => {
    for (const id of CAPAS_CON_CRITERIO) expect(capas.has(id), id).toBe(true);
  });

  it("las teselas traen los casos que se comprueban", () => {
    for (const c of Object.keys(NO_RECONOCIDAS)) {
      expect(lineas.some(({ rasgo }) => codigo(rasgo) === c), c).toBe(true);
    }
    const istmo = lineas.filter(
      ({ tesela, rasgo }) =>
        tesela.z >= 6 && rasgo.propiedades.kind === "country" && rasgo.propiedades.disputed === true && enElIstmoDeCrimea(tesela, rasgo),
    );
    expect(new Set(istmo.map(({ tesela }) => tesela.z))).toEqual(new Set([6, 7, 8, 11]));
    const nombres = rotulos.map(({ rasgo }) => rasgo.propiedades["name:en"]);
    for (const n of ["Northern Cyprus", "Abkhazia", "South Ossetia", "Kosovo", "Cyprus", "Georgia", "Moldova", "Ukraine"]) {
      expect(nombres, n).toContain(n);
    }
  });

  it("no dibuja ninguna línea de las entidades no reconocidas ni de las zonas de la ONU", () => {
    if (pais === undefined || interior === undefined) throw new Error("sin capas de fronteras");
    const ocultas = lineas.filter(
      ({ rasgo }) =>
        String(codigo(rasgo)) in NO_RECONOCIDAS ||
        ["unrecognized_country", "overlay_limit"].includes(String(rasgo.propiedades.kind)),
    );
    expect(ocultas.length).toBeGreaterThanOrEqual(10);
    for (const { tesela, rasgo } of ocultas) {
      const quien = `${NO_RECONOCIDAS[String(codigo(rasgo))] ?? rasgo.propiedades.kind} z${tesela.z}`;
      expect(dibuja(pais, rasgo, tesela), quien).toBe(false);
      expect(dibuja(interior, rasgo, tesela), quien).toBe(false);
    }
  });

  it("el límite de Crimea con el resto de Ucrania es interior, nunca frontera de país", () => {
    if (pais === undefined || interior === undefined) throw new Error("sin capas de fronteras");
    const crimea = lineas.filter(
      ({ tesela, rasgo }) =>
        rasgo.propiedades.kind === "country" &&
        (codigo(rasgo) === "B89" || (rasgo.propiedades.disputed === true && enElIstmoDeCrimea(tesela, rasgo))),
    );
    expect(crimea.length).toBeGreaterThanOrEqual(5);
    for (const { tesela, rasgo } of crimea) {
      expect(dibuja(pais, rasgo, tesela), `Crimea z${tesela.z}`).toBe(false);
      expect(dibuja(interior, rasgo, tesela), `Crimea z${tesela.z}`).toBe(true);
    }
  });

  it("las demás fronteras de país siguen: Kosovo, Georgia con Rusia, Moldavia con Ucrania…", () => {
    if (pais === undefined) throw new Error("sin capa de fronteras");
    const kosovo = lineas.filter(({ rasgo }) => codigo(rasgo) === "B57");
    expect(kosovo.length).toBeGreaterThan(0);
    for (const { tesela, rasgo } of kosovo) expect(dibuja(pais, rasgo, tesela), "Kosovo").toBe(true);
    // En disputa en OpenStreetMap pero fuera del istmo: Kosovo, la frontera de Georgia con Rusia…
    const enDisputaFuera = lineas.filter(
      ({ tesela, rasgo }) =>
        tesela.z >= 6 && rasgo.propiedades.kind === "country" && rasgo.propiedades.disputed === true && !enElIstmoDeCrimea(tesela, rasgo),
    );
    expect(enDisputaFuera.some(({ tesela }) => tesela.zona === "Kosovo")).toBe(true);
    expect(enDisputaFuera.some(({ tesela }) => tesela.zona === "Georgia")).toBe(true);
    for (const { tesela, rasgo } of enDisputaFuera) expect(dibuja(pais, rasgo, tesela), tesela.zona).toBe(true);
    const normales = lineas.filter(
      ({ rasgo }) =>
        rasgo.propiedades.kind === "country" && rasgo.propiedades.disputed === undefined && codigo(rasgo) === undefined,
    );
    expect(normales.length).toBeGreaterThan(10);
    for (const { tesela, rasgo } of normales) expect(dibuja(pais, rasgo, tesela), tesela.zona).toBe(true);
  });

  it("no rotula el norte de Chipre, Abjasia ni Osetia del Sur, y sí los países reconocidos", () => {
    if (rotuloPais === undefined || rotuloRegion === undefined) throw new Error("sin capas de rótulos");
    for (const { tesela, rasgo } of rotulos) {
      const nombre = String(rasgo.propiedades["name:en"]);
      const prohibido = ["Northern Cyprus", "Abkhazia", "South Ossetia"].includes(nombre);
      const capa = rasgo.propiedades.kind === "region" ? rotuloRegion : rotuloPais;
      expect(dibuja(capa, rasgo, tesela), `${nombre} z${tesela.z}`).toBe(!prohibido);
    }
  });

  // Nombres que no están hoy en las teselas, o en otra lengua, sin el elemento de Wikidata: el
  // filtro los para igual, en cualquiera de los campos de nombre.
  const PROHIBIDOS = [
    "Northern Cyprus",
    "Norte de Chipre",
    "República Turca del Norte de Chipre",
    "Turkish Republic of Northern Cyprus",
    "Kuzey Kıbrıs Türk Cumhuriyeti",
    "Турецкая Республика Северного Кипра",
    "Transnistria",
    "Pridnestrovie",
    "Pridnestrovian Moldavian Republic",
    "Приднестровье",
    "Приднестровская Молдавская Республика",
    "Abkhazia",
    "Abjasia",
    "Аҧсны",
    "Аԥсны - Абхазия",
    "Абхазия",
    "South Ossetia",
    "Osetia del Sur",
    "Хуссар Ирыстон - Южная Осетия",
    "Южная Осетия",
    "Donetsk People's Republic",
    "Luhansk People's Republic",
    "Lugansk People's Republic",
    "República Popular de Donetsk",
    "República Popular de Lugansk",
    "Донецкая Народная Республика",
    "Луганская Народная Республика",
    "Донецька Народна Республіка",
    "ДНР",
    "ЛНР",
  ];
  const CAMPOS = ["name", "pgf:name", "name:es", "name:en", "name:ru"];
  const TESELA = { z: 7, x: 77, y: 44 };

  it.each(PROHIBIDOS)("no rotula «%s» como país ni como región", (nombre) => {
    if (rotuloPais === undefined || rotuloRegion === undefined) throw new Error("sin capas de rótulos");
    for (const [kind, capa] of [
      ["country", rotuloPais],
      ["region", rotuloRegion],
    ] as const) {
      for (const campo of CAMPOS) {
        const rasgo: Rasgo = { capa: "places", tipo: 1, propiedades: { kind, [campo]: nombre }, geometria: [[[2048, 2048]]] };
        expect(dibuja(capa, rasgo, TESELA), `${kind} ${campo}`).toBe(false);
      }
    }
  });

  it("no rotula una entidad no reconocida por su elemento de Wikidata aunque el nombre sea otro", () => {
    if (rotuloPais === undefined) throw new Error("sin capa de rótulos");
    for (const wikidata of ["Q23681", "Q23334", "Q23427", "Q907112", "Q16150196", "Q16746854", "Q15966495"]) {
      const rasgo: Rasgo = { capa: "places", tipo: 1, propiedades: { kind: "country", wikidata, name: "X" }, geometria: [[[2048, 2048]]] };
      expect(dibuja(rotuloPais, rasgo, TESELA), wikidata).toBe(false);
    }
  });

  it("las ciudades y las regiones de Ucrania se rotulan como siempre", () => {
    const localidad = capas.get("places_locality");
    if (localidad === undefined || rotuloRegion === undefined || rotuloPais === undefined) throw new Error("sin capas de rótulos");
    for (const nombre of ["Donetsk", "Luhansk", "Lugansk", "Sukhumi", "Tskhinvali", "Tiraspol", "Nicosia", "Sevastopol", "Донецк"]) {
      const rasgo: Rasgo = { capa: "places", tipo: 1, propiedades: { kind: "locality", name: nombre, "name:en": nombre }, geometria: [[[2048, 2048]]] };
      expect(dibuja(localidad, rasgo, TESELA), nombre).toBe(true);
    }
    for (const nombre of ["Autonomous Republic of Crimea", "Donetsk Oblast", "Óblast de Lugansk", "Adjara", "Gagauzia"]) {
      const rasgo: Rasgo = { capa: "places", tipo: 1, propiedades: { kind: "region", name: nombre, "name:en": nombre }, geometria: [[[2048, 2048]]] };
      expect(dibuja(rotuloRegion, rasgo, TESELA), nombre).toBe(true);
    }
    for (const nombre of ["Ukraine", "Moldova", "Georgia", "Cyprus", "Kosovo"]) {
      const rasgo: Rasgo = { capa: "places", tipo: 1, propiedades: { kind: "country", name: nombre, "name:en": nombre }, geometria: [[[2048, 2048]]] };
      expect(dibuja(rotuloPais, rasgo, TESELA), nombre).toBe(true);
    }
  });
});

describe("polígonos de país (presión por país y resaltado)", () => {
  type Anillo = [number, number][];
  const paises = JSON.parse(readFileSync(join(WEB, "public", "mapa", "paises.geojson"), "utf-8")) as {
    features: { properties: { iso: string }; geometry: { type: "Polygon" | "MultiPolygon"; coordinates: Anillo[] | Anillo[][] } }[];
  };

  function dentro([x, y]: [number, number], anillo: Anillo): boolean {
    let dentro = false;
    for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
      const [xi, yi] = anillo[i] as [number, number];
      const [xj, yj] = anillo[j] as [number, number];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro;
    }
    return dentro;
  }

  function paisesEn(punto: [number, number]): string[] {
    return paises.features
      .filter(({ geometry }) => {
        const poligonos = (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as Anillo[][];
        return poligonos.some(([exterior, ...huecos]) => exterior !== undefined && dentro(punto, exterior) && !huecos.some((h) => dentro(punto, h)));
      })
      .map((f) => f.properties.iso);
  }

  it.each([
    ["Simferópol", [34.1, 44.95], "UA"],
    ["Sebastopol", [33.55, 44.6], "UA"],
    ["Kerch", [36.4, 45.35], "UA"],
    ["Dzhankói", [34.4, 45.7], "UA"],
    ["Donetsk", [37.8, 48.0], "UA"],
    ["Lugansk", [39.3, 48.57], "UA"],
    ["Tiraspol", [29.6, 46.84], "MD"],
    ["Sujumi", [41.0, 43.0], "GE"],
    ["Tsjinvali", [43.96, 42.23], "GE"],
    ["Nicosia norte", [33.36, 35.2], "CY"],
    ["Famagusta", [33.93, 35.12], "CY"],
    ["Kyrenia", [33.32, 35.33], "CY"],
    ["Taman", [36.7, 45.2], "RU"],
  ] as const)("%s está en %s y en ningún otro país", (_, punto, iso) => {
    expect(paisesEn([punto[0], punto[1]])).toEqual([iso]);
  });
});

describe("la metodología lo dice", () => {
  it.each([
    ["es", "Las fronteras y los nombres del mapa siguen la posición de la Unión Europea."],
    ["en", "Map borders and names follow the position of the European Union."],
  ] as const)("%s: en las secciones que pintan el panel y la página de metodología", (idioma, frase) => {
    const parrafos = seccionesDeMetodologia(textos(idioma)).flatMap((s) =>
      s.bloques.flatMap((b) => ("parrafo" in b ? [b.parrafo.map((t) => (typeof t === "string" ? t : t.texto)).join("")] : [])),
    );
    expect(parrafos).toContain(frase);
  });
});
