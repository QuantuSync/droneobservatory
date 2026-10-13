// Fronteras y nombres del mapa de fondo según la posición de la Unión Europea. Las teselas de
// Protomaps mezclan dos orígenes: hasta el zoom 5, las líneas de Natural Earth, con su código
// `brk_a3` y la clase `unrecognized_country` para las entidades que nadie o casi nadie reconoce;
// desde el 6, las de OpenStreetMap, sin código y con `disputed` en las líneas en disputa. Los
// nombres de país llevan `wikidata`. Lo de abajo sale de leer las teselas del build 20260930 en
// Chipre, Moldavia, Georgia, Crimea y el Donbás; tests/criterioUe.test.ts lo comprueba con
// rasgos sacados de esas teselas (tests/fixtures/teselas-criterio-ue.json).

import type { ExpressionSpecification } from "maplibre-gl";

/**
 * Entidades que la UE no reconoce como Estado y anexiones que no reconoce, por su elemento de
 * Wikidata: el norte de Chipre, Abjasia, Osetia del Sur, Transnistria, las «repúblicas
 * populares» de Donetsk y de Lugansk (antes y después de 2022) y la «República de Crimea» rusa.
 */
export const WIKIDATA_NO_RECONOCIDOS: readonly string[] = [
  "Q23681",
  "Q23334",
  "Q23427",
  "Q907112",
  "Q16150196",
  "Q114334914",
  "Q16746854",
  "Q114327408",
  "Q15966495",
];

/**
 * Trozos de nombre de esas entidades en las lenguas que pueden llegar a un rótulo (el español, el
 * inglés y el nombre local) y en ruso, ucraniano y turco. Solo se buscan en los rótulos de país
 * y de región: las ciudades (Donetsk, Lugansk, Sujumi, Tsjinvali, Tiraspol, Nicosia) se rotulan
 * como cualquier otra.
 */
export const NOMBRES_NO_RECONOCIDOS: readonly string[] = [
  "Northern Cyprus",
  "North Cyprus",
  "Norte de Chipre",
  "Chipre del Norte",
  "Kuzey Kıbrıs",
  "Kıbrıs Türk",
  "Северного Кипра",
  "Северный Кипр",
  "Transnistr",
  "Pridnestrov",
  "Приднестров",
  "Abkhaz",
  "Abjasia",
  "Абхаз",
  "Аԥсны",
  "Аҧсны",
  "Apsny",
  "South Ossetia",
  "Osetia del Sur",
  "Южная Осетия",
  "Південна Осетія",
  "Хуссар Ирыстон",
  "Donetsk People",
  "Luhansk People",
  "Lugansk People",
  "Popular de Donetsk",
  "Popular de Lugansk",
  "Донецкая Народная",
  "Луганская Народная",
  "Донецька Народна",
  "Луганська Народна",
  "ДНР",
  "ЛНР",
];

/** Los campos de nombre que se miran: los que puede pintar el rótulo y los de las lenguas de arriba. */
const CAMPOS_DE_NOMBRE: readonly string[] = [
  "name",
  "pgf:name",
  "name:es",
  "name:en",
  "name2",
  "name3",
  "name:ru",
  "name:uk",
  "name:tr",
];

const TODOS_LOS_NOMBRES: ExpressionSpecification = [
  "concat",
  ...CAMPOS_DE_NOMBRE.flatMap((campo) => [["coalesce", ["get", campo], ""], "|"]),
] as unknown as ExpressionSpecification;

/** Rótulo de una entidad no reconocida: no se pinta. */
export const ROTULO_NO_RECONOCIDO: ExpressionSpecification = [
  "any",
  ["in", ["coalesce", ["get", "wikidata"], ""], ["literal", WIKIDATA_NO_RECONOCIDOS]],
  ...NOMBRES_NO_RECONOCIDOS.map((trozo) => ["in", trozo, TODOS_LOS_NOMBRES]),
] as unknown as ExpressionSpecification;

/**
 * Istmos de Perekop y Chongar y la flecha de Arabat, donde OpenStreetMap dibuja como frontera de
 * Rusia, en disputa, el límite entre Crimea y el resto de Ucrania (entre 33,61 y 34,98 de
 * longitud y 45,76 y 46,23 de latitud en todas las teselas). No hay otra línea en disputa dentro.
 */
export const ISTMO_DE_CRIMEA = {
  type: "Polygon" as const,
  coordinates: [
    [
      [33.4, 45.6],
      [35.2, 45.6],
      [35.2, 46.4],
      [33.4, 46.4],
      [33.4, 45.6],
    ],
  ],
};

/**
 * Líneas que no se dibujan: las de las entidades no reconocidas de Natural Earth (contornos de
 * Transnistria, Abjasia, Osetia del Sur, las «repúblicas populares», el norte de Chipre, el
 * Alto Karabaj, el Sáhara Occidental…), las zonas de separación de la ONU (`overlay_limit`, la de
 * Chipre) y la Línea Verde de Chipre, que Natural Earth da como frontera en disputa (B20).
 */
export const LINEA_OCULTA: ExpressionSpecification = [
  "any",
  ["in", ["coalesce", ["get", "kind"], ""], ["literal", ["unrecognized_country", "overlay_limit"]]],
  ["==", ["coalesce", ["get", "brk_a3"], ""], "B20"],
];

/**
 * Líneas de frontera de país que pasan a dibujarse como límite interior: el de Crimea con el
 * resto de Ucrania, que Natural Earth marca B89 y OpenStreetMap como frontera rusa en disputa.
 * Es el límite de la República Autónoma de Crimea, una región de Ucrania.
 */
export const LINEA_INTERIOR_DE_UCRANIA: ExpressionSpecification = [
  "any",
  ["all", ["==", ["get", "kind"], "country"], ["==", ["coalesce", ["get", "brk_a3"], ""], "B89"]],
  ["all", ["==", ["get", "disputed"], true], ["within", ISTMO_DE_CRIMEA]],
] as unknown as ExpressionSpecification;

const NIVEL_DE_PAIS: ExpressionSpecification = ["<=", ["get", "kind_detail"], 2];

/** Filtro de la capa de fronteras entre países (boundaries_country). */
export const FILTRO_FRONTERA_DE_PAIS: ExpressionSpecification = [
  "all",
  NIVEL_DE_PAIS,
  ["!", LINEA_OCULTA],
  ["!", LINEA_INTERIOR_DE_UCRANIA],
];

/** Filtro de la capa de límites interiores (boundaries). */
export const FILTRO_LIMITE_INTERIOR: ExpressionSpecification = [
  "all",
  ["!", LINEA_OCULTA],
  ["any", ["!", NIVEL_DE_PAIS], LINEA_INTERIOR_DE_UCRANIA],
];

interface CapaConFiltro {
  id: string;
  filter?: unknown;
}

/**
 * Pone el criterio en las capas de Protomaps: fronteras y rótulos de país y de región. Las demás
 * capas pasan sin cambios.
 */
export function conCriterioUe<C extends CapaConFiltro>(capa: C): C {
  switch (capa.id) {
    case "boundaries_country":
      return { ...capa, filter: FILTRO_FRONTERA_DE_PAIS };
    case "boundaries":
      return { ...capa, filter: FILTRO_LIMITE_INTERIOR };
    case "places_country":
      return { ...capa, filter: ["all", ["==", ["get", "kind"], "country"], ["!", ROTULO_NO_RECONOCIDO]] };
    case "places_region":
      return { ...capa, filter: ["all", ["==", ["get", "kind"], "region"], ["!", ROTULO_NO_RECONOCIDO]] };
    default:
      return capa;
  }
}

/** Capas cuyo filtro cambia el criterio: si Protomaps les cambia el nombre, la prueba lo dice. */
export const CAPAS_CON_CRITERIO: readonly string[] = [
  "boundaries_country",
  "boundaries",
  "places_country",
  "places_region",
];
