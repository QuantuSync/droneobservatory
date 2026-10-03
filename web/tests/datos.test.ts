import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { CARGANDO, cargarIncidente, cargarResumen } from "../src/datos/carga.ts";
import { COLUMNAS_INCIDENTES, celda, csvAtaques, csvIncidentes } from "../src/datos/csv.ts";
import {
  DESCONOCIDO,
  detalleIncidente,
  detalleSinUbicacion,
  meta,
  resumir,
  resumirUcrania,
} from "../src/datos/derivar.ts";
import {
  ataquesPorRegion,
  cifrasDeRegion,
  dominioUcrania,
  lanzamientosPorNoche,
  nochesDeGuerra,
} from "../src/datos/ucrania.ts";
import {
  validarAtaque,
  validarColeccion,
  validarDetalleIncidente,
  validarPublicacionUcrania,
  validarResumen,
  validarResumenUcrania,
} from "../src/datos/validar.ts";
import * as vocabulario from "../src/datos/vocabulario.ts";
import { CAMPOS_INCIDENTE, validarEstadoSistema, validarSinUbicacion } from "../src/datos/validar.ts";
import { cierre } from "../src/datos/efecto.ts";
import { afirmacionesDe, rangoDeFuentes, valorLegible } from "../src/datos/afirmaciones.ts";
import { referenciaDeFrescura } from "../src/tiempo/frescura.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import {
  CARGAS_MALICIOSAS,
  afirmacion,
  ataque,
  coleccion,
  estadoSistema,
  focoTermico,
  fuente,
  incidente,
  publicacion,
  traficoAereo,
} from "./ejemplos.ts";

/** Campos que la web ya acepta aunque el esquema todavía no los marque como públicos. */
const CAMPOS_ANTICIPADOS = ["afirmaciones_publicas"];

const RAIZ = join(import.meta.dirname, "..", "..");

function leerJson(...ruta: string[]): unknown {
  return JSON.parse(readFileSync(join(RAIZ, ...ruta), "utf-8")) as unknown;
}

const episodio = "EODI-EP-2025-0001";
const incidentes = coleccion([
  incidente(),
  incidente(
    {
      id: "EODI-2025-00016",
      tipo: "sobrevuelo",
      episodio,
      estado: {
        actual: "confirmado",
        historial: [{ estado: "confirmado", fecha: { valor: "2025-11-05T11:45Z", precision: "hora" } }],
      },
      tiempo: { inicio: { valor: "2025-11-04T20:00Z", precision: "hora" } },
      lugar: { radio_km: 5, pais: "BE", localidad: "Diest" },
      control: { ultima_actualizacion: { valor: "2026-09-30T12:42Z", precision: "minuto" } },
    },
    [5.0, 51.0],
  ),
  incidente(
    {
      id: "EODI-2025-00026",
      episodio,
      estado: {
        actual: "atribuido",
        historial: [{ estado: "atribuido", fecha: { valor: "2025-11-04T20:00Z", precision: "hora" } }],
      },
      tiempo: { inicio: { valor: "2025-11-04T19:00Z", precision: "hora" } },
      lugar: { radio_km: 5, pais: "BE" },
    },
    [4.45, 50.46],
  ),
]);

const ataques = publicacion([
  ataque(),
  ataque({
    id: "EODI-UA-2026-1012",
    incluido_en: "EODI-UA-2026-1013",
    regiones: [{ region: "UA-32", derribados: { min: 5, max: 5 } }],
  }),
  ataque({
    id: "EODI-UA-2026-1014",
    sentido: "UA_RU",
    periodo: {
      inicio: { valor: "2026-09-28T17:00Z", precision: "minuto" },
      fin: { valor: "2026-09-29T05:00Z", precision: "minuto" },
    },
    lanzados: { total: "desconocido" },
    regiones: [{ region: "RU-BEL" }, { region: "UA-43" }],
  }),
]);

describe("resúmenes", () => {
  const resumen = resumir(incidentes, ataques);

  it("toma como actualización la más reciente de los dos ficheros", () => {
    expect(resumen.actualizado).toBe("2026-09-30T12:42Z");
  });

  it("reduce cada incidente a lo que necesita el mapa", () => {
    expect(resumen.incidentes.find((i) => i.id === "EODI-2025-00210")).toEqual({
      id: "EODI-2025-00210",
      punto: { lon: 11.7861, lat: 48.3536, radio_km: 5 },
      imprecisa: null,
      tipo: "interrupcion_aeroportuaria",
      estado: "notificado",
      presencia: "no_confirmada",
      titulo: { es: "Cierre del aeropuerto de Múnich", en: "Munich airport closure" },
      dia: diaDeInstante("2025-10-02"),
      pais: "DE",
      objetivo: "Flughafen München",
      episodio: null,
      foco: false,
    });
  });

  it("marca los incidentes con foco térmico detectado", () => {
    const conFoco = resumir(coleccion([incidente({ foco_termico: focoTermico() })]), ataques);
    expect(conFoco.incidentes[0]?.foco).toBe(true);
  });

  it("une los incidentes de un episodio en orden cronológico", () => {
    expect(resumen.episodios).toEqual([
      { id: episodio, incidentes: ["EODI-2025-00016", "EODI-2025-00026"] },
    ]);
  });

  it("cuenta los confirmados y los atribuidos por separado", () => {
    expect(meta(resumen, false)).toEqual({
      actualizado: "2026-09-30T12:42Z",
      incidentes: 3,
      confirmados: 1,
      atribuidos: 1,
      paises: 2,
      sinUbicacion: false,
    });
  });

  it("saca un evento por cada paso del historial, del más reciente al más antiguo", () => {
    expect(resumen.eventos.map((e) => [e.id, e.estado, e.nuevo])).toEqual([
      ["EODI-2025-00016", "confirmado", true],
      ["EODI-2025-00026", "atribuido", true],
      ["EODI-2025-00210", "notificado", true],
    ]);
    const conCambio = resumir(
      coleccion([
        incidente({
          estado: {
            actual: "confirmado",
            historial: [
              { estado: "notificado", fecha: { valor: "2026-09-01T10:00Z", precision: "hora" } },
              { estado: "confirmado", fecha: { valor: "2026-09-02T08:30Z", precision: "minuto" } },
            ],
          },
        }),
      ]),
      ataques,
    );
    expect(conCambio.eventos).toEqual([
      { id: "EODI-2025-00210", fecha: "2026-09-02T08:30Z", estado: "confirmado", nuevo: false },
      { id: "EODI-2025-00210", fecha: "2026-09-01T10:00Z", estado: "notificado", nuevo: true },
    ]);
  });

  it("la ficha lleva todas las propiedades y el punto", () => {
    const detalle = detalleIncidente(incidentes.features[0]!);
    expect(detalle).toMatchObject({ id: "EODI-2025-00210", lon: 11.7861, lat: 48.3536 });
    expect(validarDetalleIncidente(detalle).ok).toBe(true);
  });

  it("lo que genera el build valida contra el esquema", () => {
    expect(validarResumen(resumen).ok).toBe(true);
    expect(validarResumenUcrania(resumirUcrania(ataques)).ok).toBe(true);
  });
});

describe("capa de Ucrania", () => {
  const ucrania = resumirUcrania(ataques);
  const todo = { desde: 0, hasta: Number.MAX_SAFE_INTEGER };

  it("lleva a la tabla las regiones de Ucrania y las de Rusia, ordenadas", () => {
    // Las rusas también: antes se descartaban y el mapa no dibujaba nada sobre Rusia.
    expect(ucrania.regiones).toEqual(["RU-BEL", "UA-32", "UA-43", "UA-63"]);
  });

  it("ordena los ataques por día y marca las cifras desconocidas", () => {
    expect(ucrania.ataques.map((fila) => fila[0])).toEqual([
      "EODI-UA-2026-1014",
      "EODI-UA-2026-1012",
      "EODI-UA-2026-1013",
    ]);
    expect(ucrania.ataques[0]?.slice(3, 5)).toEqual([DESCONOCIDO, DESCONOCIDO]);
    expect(dominioUcrania(ucrania)).toEqual({
      desde: diaDeInstante("2026-09-28"),
      hasta: diaDeInstante("2026-09-29"),
    });
  });

  it("cuenta los ataques que citan cada región en el periodo", () => {
    expect(Object.fromEntries(ataquesPorRegion(ucrania, todo))).toEqual({
      "RU-BEL": 1,
      "UA-32": 2,
      "UA-43": 1,
      "UA-63": 1,
    });
    const soloElDia28 = { desde: diaDeInstante("2026-09-28"), hasta: diaDeInstante("2026-09-28") };
    expect(Object.fromEntries(ataquesPorRegion(ucrania, soloElDia28))).toEqual({
      "RU-BEL": 1,
      "UA-43": 1,
    });
  });

  it("no suma dos veces los derribos de un tramo incluido en otro parte", () => {
    const cifras = cifrasDeRegion(ucrania, "UA-32", todo);
    expect(cifras.ataques).toEqual({ RU_UA: 2, UA_RU: 0 });
    expect(cifras.derribados).toEqual({ min: 12, max: 12 });
    expect(cifras.lista.map((a) => a.id)).toEqual(["EODI-UA-2026-1013", "EODI-UA-2026-1012"]);
  });

  it("una región sin desglose de derribos no inventa un cero", () => {
    expect(cifrasDeRegion(ucrania, "UA-63", todo).derribados).toBeNull();
    expect(cifrasDeRegion(ucrania, "UA-99", todo).lista).toEqual([]);
  });

  it("los lanzamientos por noche solo cuentan los partes contra Ucrania que suman", () => {
    expect(Object.fromEntries(lanzamientosPorNoche(ucrania))).toEqual({
      [diaDeInstante("2026-09-29")]: 188,
    });
  });
});

describe("validación contra el esquema", () => {
  it("los ficheros publicados validan", () => {
    expect(validarColeccion(leerJson("publicacion", "incidentes.geojson"))).toMatchObject({
      ok: true,
    });
    expect(validarPublicacionUcrania(leerJson("publicacion", "ucrania.json"))).toMatchObject({
      ok: true,
    });
  });

  it("acepta los ejemplos", () => {
    expect(validarColeccion(incidentes).ok).toBe(true);
    expect(validarAtaque(ataque()).ok).toBe(true);
  });

  it.each([
    ["un estado fuera de la lista", { estado: { actual: "rumor", historial: [] } }],
    ["un campo que no está en el esquema", { interno: true }],
    ["un identificador mal formado", { id: "EODI-25-1" }],
    ["un radio fuera de rango", { lugar: { radio_km: 500, pais: "DE" } }],
    ["ninguna fuente", { fuentes: [] }],
    ["un enlace que no es http", { fuentes: [fuente({ enlace: "javascript:alert(1)" })] }],
    ["una credibilidad fuera de 1 a 6", { fuentes: [fuente({ credibilidad: 9 })] }],
  ])("rechaza %s", (_nombre, cambios) => {
    const roto = incidente(cambios as never);
    const resultado = validarColeccion(coleccion([roto]));
    expect(resultado.ok).toBe(false);
  });

  it("rechaza lo que no es una colección", () => {
    for (const valor of [null, 3, "texto", [], {}, { type: "FeatureCollection" }]) {
      expect(validarColeccion(valor).ok).toBe(false);
    }
  });

  it("rechaza coordenadas imposibles", () => {
    expect(validarColeccion(coleccion([incidente({}, [200, 95])])).ok).toBe(false);
  });

  it("rechaza un resumen de Ucrania que apunta a una región que no existe", () => {
    const resumen = resumirUcrania(ataques);
    resumen.regiones = [];
    expect(validarResumenUcrania(resumen).ok).toBe(false);
  });

  it("dice dónde está el error y no pasa de unos pocos", () => {
    const rotos = coleccion(Array.from({ length: 50 }, () => incidente({ tipo: "otro" as never })));
    const resultado = validarColeccion(rotos);
    expect(resultado.ok).toBe(false);
    if (!resultado.ok) {
      expect(resultado.errores[0]).toContain(".features[0].properties.tipo");
      expect(resultado.errores.length).toBeLessThanOrEqual(20);
    }
  });

  it("un texto hostil es un texto válido: se valida la forma, no se interpreta", () => {
    const hostil = incidente({
      titulo: { es: CARGAS_MALICIOSAS.script, en: CARGAS_MALICIOSAS.svg },
      fuentes: [fuente({ frase_origen: CARGAS_MALICIOSAS.manejador })],
    });
    expect(validarColeccion(coleccion([hostil])).ok).toBe(true);
  });
});

describe("listas cerradas iguales a las del esquema", () => {
  type Esquema = Record<string, unknown>;
  const leer = (nombre: string) => leerJson("esquema", "1.9.0", `${nombre}.schema.json`) as Esquema;
  const en = (objeto: unknown, ...claves: string[]): unknown =>
    claves.reduce<unknown>((actual, clave) => (actual as Esquema)[clave], objeto);

  const incidenteEsquema = leer("incidente");
  const comun = leer("comun");
  const ataqueEsquema = leer("ataque_ucrania");
  const regionEsquema = leer("region_ucrania");
  const p = "properties";

  it.each([
    ["tipos", vocabulario.TIPOS, en(incidenteEsquema, p, "tipo", "enum")],
    ["presencias", vocabulario.PRESENCIAS, en(incidenteEsquema, p, "presencia_dron", "enum")],
    [
      "categorías",
      vocabulario.CATEGORIAS_OBJETIVO,
      en(incidenteEsquema, p, "objetivo", p, "categoria", "enum"),
    ],
    ["usos", vocabulario.USOS, en(incidenteEsquema, p, "objetivo", p, "uso", "enum")],
    ["clases", vocabulario.CLASES_DRON, en(incidenteEsquema, p, "drones", p, "clase", "enum")],
    [
      "cierres",
      vocabulario.CIERRES,
      en(incidenteEsquema, p, "consecuencias", p, "cierre", p, "valor", "enum"),
    ],
    [
      "daños",
      vocabulario.NIVELES_DANOS,
      en(incidenteEsquema, p, "consecuencias", p, "danos", p, "nivel", "enum"),
    ],
    [
      "medidas",
      vocabulario.MEDIDAS,
      en(incidenteEsquema, p, "respuesta", p, "medidas", "items", "enum"),
    ],
    ["estados", vocabulario.ESTADOS, en(comun, "$defs", "estado_historial", p, "actual", "enum")],
    ["precisiones", vocabulario.PRECISIONES, en(comun, "$defs", "instante", p, "precision", "enum")],
    ["fiabilidades", vocabulario.FIABILIDADES, en(comun, "$defs", "fiabilidad", "enum")],
    ["sentidos", vocabulario.SENTIDOS, en(ataqueEsquema, p, "sentido", "enum")],
    [
      "tipos de dron",
      vocabulario.TIPOS_DRON_ATAQUE,
      en(ataqueEsquema, p, "tipos_dron", "items", "enum"),
    ],
    [
      "categorías de derribo",
      vocabulario.CATEGORIAS_DERRIBADOS,
      en(ataqueEsquema, p, "derribados_categoria", "enum"),
    ],
    [
      "objetivos de Ucrania",
      vocabulario.CATEGORIAS_OBJETIVO_UCRANIA,
      en(regionEsquema, p, "categorias_objetivo", "items", "enum"),
    ],
  ])("%s", (_nombre, propias, delEsquema) => {
    expect([...propias].sort()).toEqual([...(delEsquema as string[])].sort());
  });

  it.each([
    ["incidente", vocabulario.PATRON_ID_INCIDENTE, en(incidenteEsquema, p, "id", "pattern")],
    ["ataque", vocabulario.PATRON_ID_ATAQUE, en(ataqueEsquema, p, "id", "pattern")],
    ["episodio", vocabulario.PATRON_ID_EPISODIO, en(incidenteEsquema, p, "episodio", "pattern")],
    ["instante", vocabulario.PATRON_INSTANTE, en(comun, "$defs", "instante", p, "valor", "pattern")],
    ["país", vocabulario.PATRON_PAIS, en(comun, "$defs", "pais", "pattern")],
    ["región", vocabulario.PATRON_REGION, en(comun, "$defs", "region_iso", "pattern")],
    ["idioma", vocabulario.PATRON_IDIOMA, en(comun, "$defs", "idioma", "pattern")],
  ])("patrón de %s", (_nombre, propio, delEsquema) => {
    expect(propio.source).toBe(new RegExp(delEsquema as string).source);
  });

  it("los campos públicos del esquema son los que la web valida", () => {
    // Un campo público nuevo en el esquema tiene que llegar también al validador de la web.
    const publicos = Object.entries(incidenteEsquema[p] as Record<string, Esquema>)
      .filter(([, campo]) => campo["x-visibilidad"] === "publico")
      .map(([nombre]) => nombre);
    for (const campo of publicos) expect(CAMPOS_INCIDENTE).toContain(campo);
    // Y al revés: la web solo acepta campos públicos del esquema, salvo los que ya lee
    // antes de que la exportación los publique.
    for (const campo of CAMPOS_INCIDENTE) {
      expect([...publicos, ...CAMPOS_ANTICIPADOS]).toContain(campo);
    }
    const completo = incidente({
      episodio,
      atribucion: {
        actor: "x",
        autoridad: "y",
        fecha: { valor: "2026-01-01T00:00Z", precision: "dia" },
      },
      afirmaciones_publicas: [afirmacion()],
      foco_termico: focoTermico(),
      trafico_aereo: traficoAereo(),
    });
    expect(Object.keys(completo.properties).sort()).toEqual(
      [...new Set([...publicos, ...CAMPOS_ANTICIPADOS])].sort(),
    );
    expect(validarColeccion(coleccion([completo])).ok).toBe(true);
  });

  it("las afirmaciones públicas nunca traen fuentes E ni F", () => {
    const conE = incidente({ afirmaciones_publicas: [afirmacion({ fiabilidad: "E" as never })] });
    expect(validarColeccion(coleccion([conE])).ok).toBe(false);
  });
});

describe("CSV de datos abiertos", () => {
  it("escapa comas, comillas y saltos de línea", () => {
    expect(celda('a,"b"\nc')).toBe('"a,""b""\nc"');
    expect(celda(undefined)).toBe("");
    expect(celda(12.5)).toBe("12.5");
  });

  it.each(["=1+1", "+34", "-2", "@SUM(A1)", "\tx"])("neutraliza la fórmula %j", (texto) => {
    expect(celda(texto).replace(/^"/, "").startsWith("'")).toBe(true);
  });

  it("escribe una fila por incidente con su enlace propio", () => {
    const lineas = csvIncidentes(incidentes).trimEnd().split("\r\n");
    expect(lineas[0]).toBe(COLUMNAS_INCIDENTES.join(","));
    expect(lineas).toHaveLength(4);
    expect(lineas[1]).toContain("EODI-2025-00210,interrupcion_aeroportuaria,notificado");
    expect(lineas[1]?.endsWith("https://droneobservatory.eu/EODI-2025-00210")).toBe(true);
  });

  it("escribe una fila por ataque con sus regiones", () => {
    const lineas = csvAtaques(ataques).trimEnd().split("\r\n");
    expect(lineas).toHaveLength(4);
    expect(lineas[1]).toContain("EODI-UA-2026-1013,RU_UA");
    expect(lineas[1]).toContain("UA-32|UA-63");
  });

  it("un título hostil no sale como fórmula ni rompe las columnas", () => {
    const hostil = coleccion([incidente({ titulo: { es: '=HYPERLINK("http://x","y")', en: "a,b" } })]);
    const fila = csvIncidentes(hostil).trimEnd().split("\r\n")[1];
    expect(fila).toContain(`"'=HYPERLINK(""http://x"",""y"")"`);
    expect(fila).toContain('"a,b"');
  });
});

describe("carga de ficheros", () => {
  const responder = (cuerpo: unknown, estado = 200): typeof fetch =>
    (() => Promise.resolve(new Response(JSON.stringify(cuerpo), { status: estado }))) as typeof fetch;

  it("entrega los datos que validan", async () => {
    const resumen = resumir(incidentes, ataques);
    await expect(cargarResumen(responder(resumen))).resolves.toEqual({
      estado: "listo",
      datos: resumen,
    });
  });

  it("no entrega un fichero que no valida", async () => {
    const carga = await cargarResumen(responder({ actualizado: "ayer", incidentes: [{}] }));
    expect(carga.estado).toBe("no_valido");
  });

  it("distingue lo que no existe de lo que no responde", async () => {
    await expect(cargarIncidente("EODI-2025-99999", responder({}, 404))).resolves.toEqual({
      estado: "no_encontrado",
    });
    await expect(cargarIncidente("EODI-2025-99999", responder({}, 500))).resolves.toEqual({
      estado: "no_disponible",
    });
    const sinRed = (() => Promise.reject(new TypeError("sin red"))) as typeof fetch;
    await expect(cargarResumen(sinRed)).resolves.toEqual({ estado: "no_disponible" });
    const html = (() => Promise.resolve(new Response("<!doctype html>"))) as typeof fetch;
    await expect(cargarResumen(html)).resolves.toEqual({ estado: "no_disponible" });
    expect(CARGANDO.estado).toBe("cargando");
  });
});

describe("estado del sistema", () => {
  it("acepta el formato acordado", () => {
    expect(validarEstadoSistema(estadoSistema()).ok).toBe(true);
    expect(validarEstadoSistema(estadoSistema({ ultima_correcta: null })).ok).toBe(true);
  });

  it("acepta la última exportación semanal, con hora o null", () => {
    const conExportacion = { ...estadoSistema(), ultima_exportacion: "2026-10-01T10:12Z" };
    expect(validarEstadoSistema(conExportacion).ok).toBe(true);
    expect(validarEstadoSistema({ ...conExportacion, ultima_exportacion: null }).ok).toBe(true);
    expect(validarEstadoSistema({ ...conExportacion, ultima_exportacion: "ayer" }).ok).toBe(false);
  });

  it("acepta la última ejecución del motor de deducción, con hora o null", () => {
    const conMotor = { ...estadoSistema(), ultima_deduccion: "2026-10-02T09:05Z" };
    expect(validarEstadoSistema(conMotor).ok).toBe(true);
    expect(validarEstadoSistema({ ...conMotor, ultima_deduccion: null }).ok).toBe(true);
    expect(validarEstadoSistema({ ...conMotor, ultima_deduccion: "ayer" }).ok).toBe(false);
  });

  it.each([
    ["otra versión", { version: 2 }],
    ["un resultado desconocido", { resultado: "regular" }],
    ["una hora mal escrita", { fin: "30/09/2026" }],
    ["una fuente desconocida", { fuentes: [{ id: "otra", estado: "leida", ultimo_dato: null }] }],
    ["un campo de más", { contenido: "x" }],
  ])("rechaza %s", (_nombre, cambios) => {
    expect(validarEstadoSistema({ ...estadoSistema(), ...cambios }).ok).toBe(false);
  });

  it("la antigüedad se mide desde la última recogida correcta si hay estado.json", () => {
    expect(referenciaDeFrescura(estadoSistema(), "2026-09-30T12:42Z")).toBe("2026-09-30T18:24Z");
    expect(referenciaDeFrescura(null, "2026-09-30T12:42Z")).toBe("2026-09-30T12:42Z");
    expect(
      referenciaDeFrescura(estadoSistema({ ultima_correcta: null }), "2026-09-30T12:42Z"),
    ).toBeNull();
  });
});

describe("quién dice qué", () => {
  const conAfirmaciones = detalleIncidente(
    incidente({
      drones: { numero: { min: 2, max: 10 } },
      afirmaciones_publicas: [
        afirmacion({ valor: { min: 3, max: 3 }, fiabilidad: "C", fuente_id: "b" }),
        afirmacion({ valor: { min: 10, max: 10 }, fiabilidad: "A", fuente_id: "a" }),
        afirmacion({ valor: { min: 40, max: 40 }, fiabilidad: "D", fuente_id: "d" }),
        afirmacion({ campo: "presencia_dron", valor: "confirmada", fiabilidad: "B" }),
      ],
    }),
  );

  it("filtra por campo y ordena por fiabilidad", () => {
    expect(afirmacionesDe(conAfirmaciones, ["drones.numero"]).map((a) => a.fiabilidad)).toEqual([
      "A",
      "C",
      "D",
    ]);
  });

  it("el rango sale solo de las fuentes A a C", () => {
    const deDrones = afirmacionesDe(conAfirmaciones, ["drones.numero"]);
    expect(rangoDeFuentes(deDrones, { min: 2, max: 10 })).toEqual({ min: 3, max: 10 });
    expect(rangoDeFuentes([], { min: 2, max: 10 })).toEqual({ min: 2, max: 10 });
  });

  it("muestra cada valor como texto, sea del tipo que sea", () => {
    expect(valorLegible({ min: 1, max: 2 })).toEqual({ clase: "rango", rango: { min: 1, max: 2 } });
    expect(valorLegible("desconocido")).toEqual({ clase: "desconocido" });
    expect(valorLegible(["patrulla", "cazas"])).toEqual({
      clase: "texto",
      texto: "patrulla · cazas",
    });
    expect(valorLegible(CARGAS_MALICIOSAS.script)).toEqual({
      clase: "texto",
      texto: CARGAS_MALICIOSAS.script,
    });
  });
});

describe("incidentes con ubicación imprecisa", () => {
  const sinPunto = (cambios: Record<string, unknown> = {}) => {
    const { lugar: _lugar, ...resto } = incidente({ id: "EODI-2026-00300" }).properties;
    return { ...resto, lugar: { pais: "PL", nivel: "region", region: "Lublin" }, ...cambios };
  };

  it("valida el fichero y rechaza un radio o un nivel que no tocan", () => {
    expect(validarSinUbicacion({ incidentes: [sinPunto()] }).ok).toBe(true);
    expect(
      validarSinUbicacion({ incidentes: [sinPunto({ lugar: { pais: "PL", nivel: "pueblo" } })] }).ok,
    ).toBe(false);
    expect(
      validarSinUbicacion({
        incidentes: [sinPunto({ lugar: { pais: "PL", nivel: "pais", radio_km: 5 } })],
      }).ok,
    ).toBe(false);
  });

  it("entran en el resumen sin punto, con su nivel, y en los eventos", () => {
    const publicacion = validarSinUbicacion({ incidentes: [sinPunto()] });
    if (!publicacion.ok) throw new Error("no valida");
    const conImprecisos = resumir(incidentes, ataques, publicacion.datos);
    const impreciso = conImprecisos.incidentes.find((i) => i.id === "EODI-2026-00300");
    expect(impreciso?.punto).toBeNull();
    expect(impreciso?.imprecisa).toEqual({ nivel: "region", region: "Lublin" });
    expect(conImprecisos.eventos.some((e) => e.id === "EODI-2026-00300")).toBe(true);
    expect(validarResumen(conImprecisos).ok).toBe(true);
    expect(meta(conImprecisos, true)).toMatchObject({ incidentes: 4, paises: 3, sinUbicacion: true });
  });

  it("su ficha valida sin punto", () => {
    const publicacion = validarSinUbicacion({ incidentes: [sinPunto()] });
    if (!publicacion.ok) throw new Error("no valida");
    const detalle = detalleSinUbicacion(publicacion.datos.incidentes[0]!);
    expect(detalle.lon).toBeNull();
    expect(validarDetalleIncidente(detalle).ok).toBe(true);
    expect(validarDetalleIncidente({ ...detalle, lon: 3 }).ok).toBe(false);
  });
});

describe("cierre en la ficha", () => {
  it("dice la duración, que no la hay, que no hubo cierre o nada", () => {
    expect(cierre("sobrevuelo", { cierre: { valor: "si", minutos: { min: 30, max: 45 } } })).toEqual({
      clase: "con_duracion",
      minutos: { min: 30, max: 45 },
    });
    expect(cierre("sobrevuelo", { cierre: { valor: "si" } })).toEqual({ clase: "sin_duracion" });
    expect(cierre("sobrevuelo", { cierre: { valor: "si", minutos: "desconocido" } })).toEqual({
      clase: "sin_duracion",
    });
    expect(cierre("sobrevuelo", { cierre: { valor: "no" } })).toEqual({ clase: "sin_cierre" });
    expect(cierre("sobrevuelo", { cierre: { valor: "desconocido" } })).toBeNull();
    expect(cierre("sobrevuelo", undefined)).toBeNull();
  });

  it("en una interrupción aeroportuaria, un cierre sin datos se dice desconocido", () => {
    expect(cierre("interrupcion_aeroportuaria", { cierre: { valor: "desconocido" } })).toEqual({
      clase: "desconocido",
    });
    expect(cierre("interrupcion_aeroportuaria", undefined)).toEqual({ clase: "desconocido" });
  });
});

describe("la guerra noche a noche", () => {
  it("agrupa por noche los ataques contra Ucrania y pesa las regiones", () => {
    const noches = nochesDeGuerra(resumirUcrania(ataques));
    expect(noches).toHaveLength(1);
    expect(noches[0]?.lanzados).toBe(188);
    // UA-32 trae derribos desglosados (12, y 5 de un tramo que no suma: cuenta 1).
    expect(Object.fromEntries(noches[0]?.regiones ?? [])).toEqual({ "UA-32": 13, "UA-63": 1 });
  });
});
