// Datos de ejemplo para los tests, con la forma de los ficheros públicos.

import type {
  AfirmacionPublica,
  EstadoSistema,
  Ataque,
  ColeccionIncidentes,
  FeatureIncidente,
  Fuente,
  PropiedadesIncidente,
  PublicacionUcrania,
} from "../src/datos/tipos.ts";

export function fuente(cambios: Partial<Fuente> = {}): Fuente {
  return {
    id: "gdelt-0000000000000001",
    enlace: "https://example.org/noticia",
    medio: "example.org",
    fecha: { valor: "2025-10-03T01:00Z", precision: "aproximada" },
    idioma: "de",
    fiabilidad: "C",
    credibilidad: 3,
    frase_origen: "Flughafen wegen Drohnen gesperrt",
    replicas: 0,
    ...cambios,
  };
}

export function incidente(
  cambios: Partial<PropiedadesIncidente> = {},
  coordenadas: [number, number] = [11.7861, 48.3536],
): FeatureIncidente {
  const propiedades: PropiedadesIncidente = {
    id: "EODI-2025-00210",
    tipo: "interrupcion_aeroportuaria",
    estado: {
      actual: "notificado",
      historial: [
        {
          estado: "notificado",
          fecha: { valor: "2025-10-03T02:00Z", precision: "aproximada" },
          fuente_id: "gdelt-0000000000000001",
        },
      ],
    },
    titulo: { es: "Cierre del aeropuerto de Múnich", en: "Munich airport closure" },
    presencia_dron: "no_confirmada",
    tiempo: { inicio: { valor: "2025-10-02T22:18Z", precision: "minuto" } },
    lugar: { radio_km: 5, pais: "DE" },
    objetivo: { categoria: "aeropuerto", nombre: "Flughafen München", oaci: "EDDM" },
    drones: { numero: { min: 2, max: 10 } },
    consecuencias: { cierre: { valor: "si" }, vuelos_cancelados: { min: 17, max: 17 } },
    respuesta: { medidas: ["cierre_espacio_aereo"] },
    fuentes: [fuente()],
    control: { ultima_actualizacion: { valor: "2026-09-28T09:43Z", precision: "minuto" } },
    ...cambios,
  };
  return {
    type: "Feature",
    id: propiedades.id,
    geometry: { type: "Point", coordinates: coordenadas },
    properties: propiedades,
  };
}

export function coleccion(features: FeatureIncidente[]): ColeccionIncidentes {
  return { type: "FeatureCollection", features };
}

export function ataque(cambios: Partial<Ataque> = {}): Ataque {
  return {
    id: "EODI-UA-2026-1013",
    tipo: "ataque_guerra",
    periodo: {
      inicio: { valor: "2026-09-29T15:00Z", precision: "minuto" },
      fin: { valor: "2026-09-30T05:00Z", precision: "minuto" },
    },
    sentido: "RU_UA",
    reivindicacion_de_parte: true,
    estado: {
      actual: "confirmado",
      historial: [
        {
          estado: "notificado",
          fecha: { valor: "2026-09-30T05:01Z", precision: "minuto" },
          fuente_id: "kpszsu-81648",
        },
      ],
    },
    lanzados: { total: { min: 188, max: 188 }, shahed_geran: { min: 86, max: 188 } },
    derribados: { min: 155, max: 155 },
    derribados_categoria: "derribados_o_neutralizados",
    regiones: [{ region: "UA-32", derribados: { min: 12, max: 12 } }, { region: "UA-63" }],
    fuentes: [
      fuente({
        id: "kpszsu-81648",
        enlace: "https://t.me/kpszsu/81648",
        medio: "Повітряні Сили ЗС України",
        idioma: "uk",
        fiabilidad: "B",
        credibilidad: 2,
        frase_origen: "У ніч на 30 вересня противник атакував",
      }),
    ],
    control: { ultima_actualizacion: { valor: "2026-09-30T05:38Z", precision: "minuto" } },
    ...cambios,
  };
}

export function publicacion(ataques: Ataque[]): PublicacionUcrania {
  return { ataques };
}

/** Textos hostiles: si alguno se interpretara como HTML, el test lo vería en el DOM. */
export const CARGAS_MALICIOSAS = {
  script: '<script>window.__ataque = true</script>',
  manejador: '<img src=x onerror="window.__ataque = true">',
  svg: '<svg onload="window.__ataque = true"><a xlink:href="javascript:alert(1)">x</a></svg>',
  entidades: "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &#x3C;b&#x3E;",
  atributo: '" onmouseover="window.__ataque = true" x="',
} as const;

export function afirmacion(cambios: Partial<AfirmacionPublica> = {}): AfirmacionPublica {
  return {
    campo: "drones.numero",
    fuente_id: "gdelt-0000000000000001",
    medio: "example.org",
    fiabilidad: "C",
    credibilidad: 3,
    fecha: { valor: "2025-10-03T01:00Z", precision: "aproximada" },
    valor: { min: 2, max: 2 },
    ...cambios,
  };
}

export function estadoSistema(cambios: Partial<EstadoSistema> = {}): EstadoSistema {
  return {
    version: 1,
    inicio: "2026-09-30T18:17Z",
    fin: "2026-09-30T18:24Z",
    resultado: "con_avisos",
    ultima_correcta: "2026-09-30T18:24Z",
    siguiente: "2026-09-30T19:17Z",
    fuentes: [
      { id: "fuerza_aerea_ua", estado: "leida", ultimo_dato: "2026-09-30T05:01Z" },
      { id: "mindef_ru", estado: "leida", ultimo_dato: "2026-09-30T05:26Z" },
      { id: "gdelt", estado: "leida", ultimo_dato: "2026-09-30T18:00Z" },
      { id: "oficiales", estado: "con_aviso", ultimo_dato: null },
      { id: "extractor", estado: "leida", ultimo_dato: "2026-09-30T17:00Z" },
    ],
    ...cambios,
  };
}
