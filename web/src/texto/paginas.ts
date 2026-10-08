// Páginas que se leen sin ejecutar código: el contenido real en el propio HTML, sacado de los
// mismos datos publicados que dibuja el mapa. La portada y cada incidente llevan además la
// aplicación del mapa encima (scripts/paginas.ts), con el texto debajo; las listas, los países,
// la guerra en Ucrania, la metodología y la ayuda son solo texto. Ninguna página dice nada que
// no esté en los datos o en los textos de la web.

import { afirmacionesDe, rangoDeFuentes } from "../datos/afirmaciones.ts";
import { ACTOR_SIN_NOMBRE, cifras, DESCONOCIDO } from "../datos/derivar.ts";
import type { Cifras } from "../datos/derivar.ts";
import { cierre as leerCierre } from "../datos/efecto.ts";
import { corredoresDelPeriodo } from "../datos/guerraSatelite.ts";
import type {
  AfirmacionPublica,
  Atribucion,
  Fuente,
  IncidenteDetalle,
  IncidenteResumen,
  RangoODesconocido,
  Resumen,
  ResumenUcrania,
} from "../datos/tipos.ts";
import { diaDeTexto, factoresQueCuentan, habitualDe, probabilidadLlana, mesEscrito, textoCambio, textoFactor } from "../datos/prevision.ts";
import type { Prevision } from "../datos/prevision.ts";
import { ataquesPorRegion, cifrasDeRegion, diaDeParte, sentidoDeFila } from "../datos/ucrania.ts";
import { autoridadEscrita, medioEscrito } from "../i18n/autoridades.ts";
import { fechaDia, fechaHora, instante, numero, pais, rango, region, textos } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Bloque, Trozo } from "../i18n/tipos.ts";
import {
  DESCARGAS,
  IDIOMAS,
  LICENCIA_DATOS,
  LICENCIA_DATOS_URL,
  NOMBRE,
  ORIGEN,
  REPOSITORIO,
  rutaDeFicha,
  rutaDeIdioma,
} from "../sitio.ts";
import { textoAproximado } from "../datos/lugarAproximado.ts";
import type { Idioma } from "../sitio.ts";
import { fechaDeDia } from "../tiempo/dias.ts";
import { e, html, jsonLd } from "./html.ts";
import type { Hijo, Html } from "./html.ts";
import { BORRAR_VISITA, PAGINAS_SERVICIO, RUTAS_SERVICIO, SCRIPT_BORRAR_VISITA, textoServicio } from "./servicio.ts";
import type { PaginaServicio } from "./servicio.ts";
import { textosPagina } from "./textos.ts";
import type { TextosPagina } from "./textos.ts";
import { RUTAS_EN_LA_WEB, seccionesDeMetodologia } from "../rutasEnLaWeb.ts";

/** Datos de los que salen todas las páginas: los mismos ficheros que lee el mapa. */
export interface DatosPaginas {
  resumen: Resumen;
  /** Ficha completa de cada incidente publicado (con punto o sin él). */
  detalles: ReadonlyMap<string, IncidenteDetalle>;
  ucrania: ResumenUcrania;
  /** La previsión publicada; null si aún no hay. */
  prevision?: Prevision | null;
}

/** Una página: su dirección en cada idioma, sus metadatos y su contenido. */
export interface PaginaTexto {
  idioma: Idioma;
  /** Dirección de esta página y de su versión en el otro idioma. */
  rutas: Record<Idioma, string>;
  titulo: string;
  descripcion: string;
  /** Contenido de <main>. */
  cuerpo: Html;
  /** Datos estructurados (schema.org). */
  estructurados: unknown[];
  /** La portada y los incidentes llevan el mapa encima; el resto es solo texto. */
  conMapa: boolean;
  /** Última modificación de lo que dice la página (instante ISO), para el sitemap. */
  modificada: string;
  /** Scripts de este sitio que necesita una página solo de texto (el botón de privacidad). */
  scripts?: readonly string[];
}

// ---------------------------------------------------------------------------------------------
// Direcciones

export const RUTAS = {
  incidentes: { es: "/incidentes", en: "/en/incidents" },
  paises: { es: "/paises", en: "/en/countries" },
  ucrania: { es: "/ucrania", en: "/en/ukraine" },
  metodologia: { es: "/metodologia", en: "/en/methodology" },
  prevision: { es: "/prevision", en: "/en/forecast" },
  ayuda: { es: "/ayuda", en: "/en/help" },
} as const satisfies Record<string, Record<Idioma, string>>;

export function rutasDeAnio(anio: string): Record<Idioma, string> {
  return { es: `${RUTAS.incidentes.es}/${anio}`, en: `${RUTAS.incidentes.en}/${anio}` };
}

export function rutasDePais(codigo: string): Record<Idioma, string> {
  const c = codigo.toLowerCase();
  return { es: `${RUTAS.paises.es}/${c}`, en: `${RUTAS.paises.en}/${c}` };
}

function rutasDeIncidente(id: string): Record<Idioma, string> {
  return { es: rutaDeFicha(id, "es"), en: rutaDeFicha(id, "en") };
}

const PORTADA: Record<Idioma, string> = { es: rutaDeIdioma("es"), en: rutaDeIdioma("en") };

export function direccionCompleta(ruta: string): string {
  return ORIGEN + (ruta === "/" ? "/" : ruta);
}

// ---------------------------------------------------------------------------------------------
// Piezas comunes

function anioDe(i: IncidenteResumen): string {
  return String(fechaDeDia(i.dia).getUTCFullYear());
}

/** Del más reciente al más antiguo; a igual día, por identificador. */
function porFecha(a: IncidenteResumen, b: IncidenteResumen): number {
  return b.dia - a.dia || (b.inicio ?? 0) - (a.inicio ?? 0) || b.id.localeCompare(a.id);
}

function enlace(ruta: string, ...hijos: Hijo[]): Html {
  return e("a", { href: ruta }, ...hijos);
}

function externo(url: string, ...hijos: Hijo[]): Html {
  return e("a", { href: url, rel: "noopener", hreflang: null }, ...hijos);
}

function trozos(lista: readonly Trozo[]): Html {
  return html(lista.map((t) => (typeof t === "string" ? t : externo(t.enlace, t.texto))));
}

function bloque(b: Bloque): Html {
  if ("parrafo" in b) return e("p", null, trozos(b.parrafo));
  return e(
    "dl",
    null,
    b.lista.map((elemento) =>
      html(
        elemento.termino !== undefined && e("dt", null, elemento.termino),
        e("dd", null, trozos(elemento.texto)),
      ),
    ),
  );
}

function filaDatos(nombre: string, ...valor: Hijo[]): Html {
  return html(e("dt", null, nombre), e("dd", null, ...valor));
}

/**
 * Fila «Tipo de dron», lo mismo que la ficha: lo que identificó la autoridad, con su cita, o lo
 * deducido: «compatible con un dron de largo alcance de la guerra» con sus razones, o, si un
 * grupo destaca, los grupos con su probabilidad. Sin base o sin razones, nada.
 */
export function filaTipoDron(t: Textos, d: IncidenteDetalle): Html | false {
  const tipo = d.tipo_dron;
  if (tipo === undefined) return false;
  const textos = t.tipoDron;
  if (tipo.identificado !== undefined) {
    const fuente = d.fuentes.find((f) => f.id === tipo.identificado?.fuente);
    return filaDatos(
      textos.fila,
      e("span", { "data-tipo-dron": "autoridad" }, textos.identificado(tipo.identificado.modelo)),
      e("span", { class: "texto-nota" }, textos.grupoDe(textos.grupos[tipo.identificado.grupo])),
      e("q", { class: "texto-nota" }, tipo.identificado.cita),
      fuente !== undefined && e("span", { class: "texto-nota" }, t.ficha.valorSegun, " ", fuente.medio),
    );
  }
  const publicado = tipo.publicado;
  const conRazon = (tipo.razones ?? []).map((r) => textos.razon(r));
  if (publicado === undefined || conRazon.length === 0) return false;
  if (publicado.presentacion === "compatible_guerra") {
    return filaDatos(
      textos.fila,
      e("span", { "data-tipo-dron": "guerra" }, textos.compatibleGuerra),
      e("ul", null, conRazon.map((r) => e("li", null, r))),
      e("span", { class: "texto-nota" }, textos.deducido),
    );
  }
  const otras = Math.round((publicado.otras ?? 0) * 100);
  const zona = d.zona?.grupo;
  const razones = [
    publicado.casos_referencia !== undefined && zona !== undefined
      ? textos.base(publicado.casos_referencia, textos.zonas[zona])
      : null,
    ...conRazon,
  ].filter((x): x is string => x !== null);
  return filaDatos(
    textos.fila,
    e("span", { "data-tipo-dron": "deducido" }, textos.compatibleCon, ":"),
    e(
      "ul",
      null,
      publicado.compatible.map((c) =>
        e("li", null, textos.grupos[c.grupo], " · ", textos.probabilidad(Math.round((c.probabilidad ?? 0) * 100))),
      ),
    ),
    otras > 0 && e("span", { class: "texto-nota" }, textos.otras(otras)),
    e("span", { class: "texto-nota" }, textos.deducido),
    razones.length > 0 && e("span", { class: "texto-nota" }, textos.porQue, ":"),
    razones.length > 0 && e("ul", null, razones.map((r) => e("li", null, r))),
  );
}

/** El lugar de un incidente en una línea: localidad, región si no hay punto, país. */
function lugarEscrito(d: IncidenteDetalle, idioma: Idioma): string {
  const partes: string[] = [];
  if (d.lugar.localidad !== undefined) partes.push(d.lugar.localidad);
  if (d.lon === null && d.lugar.region !== undefined) partes.push(d.lugar.region);
  partes.push(pais(d.lugar.pais, idioma));
  return partes.join(", ");
}

function lugarResumido(i: IncidenteResumen, idioma: Idioma): string {
  return [i.objetivo, pais(i.pais, idioma)].filter((p): p is string => p !== null).join(", ");
}

/** Una entrada de lista: fecha, titular enlazado, estado y lugar. */
function entrada(i: IncidenteResumen, idioma: Idioma, t: Textos): Html {
  return e(
    "li",
    null,
    e("span", { class: "mono" }, fechaDia(i.dia)),
    " · ",
    enlace(rutaDeFicha(i.id, idioma), i.titulo[idioma]),
    " · ",
    t.estado[i.estado],
    " · ",
    lugarResumido(i, idioma),
  );
}

function listaDeIncidentes(lista: readonly IncidenteResumen[], idioma: Idioma, t: Textos, tp: TextosPagina): Html {
  if (lista.length === 0) return e("p", null, tp.lista.sinIncidentes);
  return e("ul", { class: "texto-lista" }, [...lista].sort(porFecha).map((i) => entrada(i, idioma, t)));
}

function tablaCifras(c: Cifras, tp: TextosPagina, idioma: Idioma, extra: Hijo = null): Html {
  return e(
    "dl",
    { class: "texto-cifras", "data-cifras": "" },
    filaDatos(tp.portada.incidentes, e("span", { "data-cifra": "incidentes" }, numero(c.incidentes, idioma))),
    filaDatos(tp.portada.confirmados, e("span", { "data-cifra": "confirmados" }, numero(c.confirmados, idioma))),
    filaDatos(tp.portada.atribuidos, e("span", { "data-cifra": "atribuidos" }, numero(c.atribuidos, idioma))),
    extra,
  );
}

function sitioEstructurado(idioma: Idioma): unknown {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: NOMBRE,
    alternateName: "EODI",
    url: direccionCompleta(PORTADA[idioma]),
    inLanguage: idioma,
  };
}

// ---------------------------------------------------------------------------------------------
// Portada

function portada(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const c = cifras(datos.resumen.incidentes);
  const ultimos = [...datos.resumen.incidentes].sort(porFecha).slice(0, 20);
  const anios = aniosDe(datos.resumen.incidentes);
  const cuerpo = html(
    e("h1", null, NOMBRE),
    tp.portada.que.map((p) => e("p", null, p)),
    e("h2", null, tp.portada.cifras),
    tablaCifras(
      c,
      tp,
      idioma,
      html(
        filaDatos(tp.portada.paises, e("span", { "data-cifra": "paises" }, numero(c.paises, idioma))),
        filaDatos(tp.portada.actualizado, e("span", { class: "mono", "data-actualizado": "" }, fechaHora(datos.resumen.actualizado))),
      ),
    ),
    e("h2", null, tp.portada.ultimos),
    listaDeIncidentes(ultimos, idioma, t, tp),
    e("p", null, enlace(RUTAS.incidentes[idioma], tp.portada.todos)),
    e("h2", null, tp.portada.porAnio),
    e("ul", { class: "texto-enlaces" }, anios.map(([anio, n]) => e("li", null, enlace(rutasDeAnio(anio)[idioma], anio), ` (${numero(n, idioma)})`))),
    e("h2", null, tp.portada.porPais),
    e("ul", { class: "texto-enlaces" }, paisesDe(datos.resumen.incidentes, idioma).map(([codigo, nombre, n]) => e("li", null, enlace(rutasDePais(codigo)[idioma], nombre), ` (${numero(n, idioma)})`))),
    e("h2", null, tp.portada.mas),
    e(
      "ul",
      { class: "texto-enlaces" },
      e("li", null, enlace(RUTAS.ucrania[idioma], tp.ucrania.titulo)),
      e("li", null, enlace(RUTAS.metodologia[idioma], tp.metodologia.titulo)),
      e("li", null, enlace(RUTAS.ayuda[idioma], tp.ayuda.titulo)),
      e("li", null, enlace(`${RUTAS.metodologia[idioma]}#datos-abiertos`, tp.portada.descargas)),
    ),
  );
  return {
    idioma,
    rutas: PORTADA,
    titulo: tp.portada.titulo,
    descripcion: tp.portada.descripcion,
    cuerpo,
    estructurados: [sitioEstructurado(idioma)],
    conMapa: true,
    modificada: datos.resumen.actualizado,
  };
}

function aniosDe(incidentes: readonly IncidenteResumen[]): [string, number][] {
  const cuenta = new Map<string, number>();
  for (const i of incidentes) cuenta.set(anioDe(i), (cuenta.get(anioDe(i)) ?? 0) + 1);
  return [...cuenta].sort(([a], [b]) => b.localeCompare(a));
}

/** [código, nombre, número], por nombre en el idioma de la página. */
function paisesDe(incidentes: readonly IncidenteResumen[], idioma: Idioma): [string, string, number][] {
  const cuenta = new Map<string, number>();
  for (const i of incidentes) cuenta.set(i.pais, (cuenta.get(i.pais) ?? 0) + 1);
  return [...cuenta]
    .map(([codigo, n]): [string, string, number] => [codigo, pais(codigo, idioma), n])
    .sort(([, a], [, b]) => a.localeCompare(b, idioma));
}

// ---------------------------------------------------------------------------------------------
// Incidente

function citaConFuente(t: Textos, idioma: Idioma, fuente: Fuente): Html {
  return html(
    e("blockquote", { lang: fuente.idioma }, `«${fuente.frase_origen}»`),
    e(
      "p",
      { class: "texto-fuente" },
      medioEscrito(fuente.medio, idioma, t.ficha.declaracionCitada),
      " · ",
      e("span", { class: "mono" }, instante(fuente.fecha)),
      " · ",
      externo(fuente.enlace, t.ficha.verFuente),
    ),
  );
}

function cifraDe(
  idioma: Idioma,
  t: Textos,
  valor: RangoODesconocido | undefined,
  afirmaciones: readonly AfirmacionPublica[],
): string {
  return rango(rangoDeFuentes(afirmaciones, valor), idioma) ?? t.ficha.desconocido;
}

function tieneCifra(valor: RangoODesconocido | undefined): boolean {
  return valor !== undefined && valor !== "desconocido";
}

function actorEscrito(t: Textos, idioma: Idioma, atribucion: Atribucion): string {
  if (atribucion.tipo === "estado" && atribucion.pais !== undefined) return pais(atribucion.pais, idioma);
  if (atribucion.tipo === "persona" && atribucion.actor === ACTOR_SIN_NOMBRE) return t.atribucion.unaPersona;
  return atribucion.actor;
}

/** Definición de un tipo, tal como la da la metodología. */
function definicionDeTipo(t: Textos, nombre: string): readonly Trozo[] | null {
  for (const seccion of t.metodologia.secciones) {
    if (seccion.id !== "tipos") continue;
    for (const b of seccion.bloques) {
      if (!("lista" in b)) continue;
      const elemento = b.lista.find((l) => l.termino === nombre);
      if (elemento !== undefined) return elemento.texto;
    }
  }
  return null;
}

function incidente(d: IncidenteDetalle, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const de = (campos: readonly string[]) => afirmacionesDe(d, campos);
  const porFuente = new Map(d.fuentes.map((f) => [f.id, f]));
  const titulo = d.titulo[idioma];
  const lugar = lugarEscrito(d, idioma);
  const estadoTexto = t.estado[d.estado.actual];
  const pasoAtribuido = d.estado.historial.findLast((p) => p.estado === "atribuido");
  const fuenteAtribucion =
    d.atribucion === undefined || pasoAtribuido?.fuente_id === undefined
      ? undefined
      : porFuente.get(pasoAtribuido.fuente_id);
  const fuentePunto = d.lugar.fuente_punto === undefined ? undefined : porFuente.get(d.lugar.fuente_punto);
  const otros = d.lugar.otros_lugares ?? [];
  const cierre = leerCierre(d.tipo, d.consecuencias);
  const c = d.consecuencias;
  const efectos: Hijo[] = [];
  if (cierre !== null) {
    efectos.push(
      cierre.clase === "con_duracion"
        ? t.ficha.cierreDe(cifraDe(idioma, t, cierre.minutos, de(["consecuencias.cierre.minutos"])))
        : cierre.clase === "sin_duracion"
          ? t.ficha.cierreSinDuracion
          : cierre.clase === "sin_cierre"
            ? t.ficha.sinCierre
            : t.ficha.cierreDesconocido,
    );
  }
  const vuelos: [RangoODesconocido | undefined, string, string][] = [
    [c?.vuelos_desviados, t.ficha.vuelosDesviados, "consecuencias.vuelos_desviados"],
    [c?.vuelos_cancelados, t.ficha.vuelosCancelados, "consecuencias.vuelos_cancelados"],
    [c?.vuelos_retrasados, t.ficha.vuelosRetrasados, "consecuencias.vuelos_retrasados"],
    [c?.heridos, t.ficha.heridos, "consecuencias.heridos"],
    [c?.fallecidos, t.ficha.fallecidos, "consecuencias.fallecidos"],
  ];
  for (const [valor, unidad, campo] of vuelos) {
    if (tieneCifra(valor)) efectos.push(`${cifraDe(idioma, t, valor, de([campo]))} ${unidad}`);
  }
  if (c?.danos !== undefined) {
    efectos.push(html(t.ficha.danos[c.danos.nivel], c.danos.frase !== undefined && html(": ", e("q", null, c.danos.frase))));
  }
  const definicion = definicionDeTipo(t, t.tipo[d.tipo]);
  const medidas = d.respuesta?.medidas ?? [];
  const fuentes = [...d.fuentes].sort(
    (a, b) => a.fiabilidad.localeCompare(b.fiabilidad) || a.fecha.valor.localeCompare(b.fecha.valor) || a.id.localeCompare(b.id),
  );
  const medios = new Map(d.fuentes.map((f) => [f.id, medioEscrito(f.medio, idioma, t.ficha.declaracionCitada)]));

  const cuerpo = html(
    e("p", { class: "texto-rotulo" }, t.tipo[d.tipo]),
    e("h1", { "data-titular": "" }, titulo),
    e("p", { class: "mono" }, d.id),
    e("p", null, enlace(rutaDeFicha(d.id, idioma), tp.incidente.verEnMapa)),
    e(
      "dl",
      { class: "texto-ficha" },
      filaDatos(
        t.ficha.estado,
        e("strong", { "data-estado": d.estado.actual }, estadoTexto),
        d.atribucion !== undefined && d.estado.actual === "atribuido" &&
          html(" · ", t.ficha.atribuidoA(actorEscrito(t, idioma, d.atribucion), autoridadEscrita(d.atribucion.autoridad, idioma))),
        e("span", { class: "texto-nota" }, tp.incidente.significa, ": ", tp.estado[d.estado.actual]),
      ),
      d.presencia_dron !== undefined &&
        filaDatos(
          t.ficha.presenciaDron,
          t.presencia[d.presencia_dron],
          e("span", { class: "texto-nota" }, tp.incidente.significa, ": ", tp.presencia[d.presencia_dron]),
        ),
      filaDatos(
        tp.incidente.tipo,
        t.tipo[d.tipo],
        definicion !== null && e("span", { class: "texto-nota" }, trozos(definicion)),
      ),
      filaDatos(
        t.ficha.fecha,
        e("span", { class: "mono" }, instante(d.tiempo.inicio)),
        d.tiempo.fin !== undefined && html(" – ", e("span", { class: "mono" }, instante(d.tiempo.fin))),
        e("span", { class: "texto-nota" }, t.precision[d.tiempo.inicio.precision]),
      ),
      filaDatos(
        t.ficha.lugar,
        lugar,
        d.lon !== null
          ? e("span", { class: "texto-nota" }, t.ficha.radio(numero(d.lugar.radio_km, idioma)))
          : d.aproximado !== undefined && d.aproximado !== null
            ? html(
                e("span", { class: "texto-nota", "data-lugar-aproximado": d.aproximado.nivel }, textoAproximado(t, idioma, d.aproximado, d.lugar.pais).nivel),
                e("span", { class: "texto-nota" }, textoAproximado(t, idioma, d.aproximado, d.lugar.pais).deDonde),
              )
            : e("span", { class: "texto-nota" }, t.imprecisa.etiqueta, " · ", t.imprecisa.nivel[d.lugar.nivel]),
      ),
      d.zona !== undefined &&
        filaDatos(
          t.zona.titulo,
          e("span", { "data-zona": d.zona.grupo }, t.zona.grupo[d.zona.grupo]),
          e("span", { class: "texto-nota" }, t.zona.motivo(d.zona.motivo, d.zona.distancia_km ?? null)),
        ),
      d.objetivo !== undefined &&
        filaDatos(tp.incidente.objetivo, d.objetivo.nombre ?? "", d.objetivo.nombre !== undefined && " · ", t.categoria[d.objetivo.categoria], d.objetivo.oaci !== undefined && html(" · ", e("span", { class: "mono" }, d.objetivo.oaci))),
      fuentePunto !== undefined &&
        filaDatos(t.ficha.lugarSegun, e("span", { "data-lugar-segun": "" }, autoridadEscrita(fuentePunto.medio, idioma)), citaConFuente(t, idioma, fuentePunto)),
      otros.length > 0 &&
        filaDatos(
          t.ficha.otrosLugares,
          e(
            "ul",
            { "data-otros-lugares": "" },
            otros.map((otro) => {
              const fuente = otro.fuente === undefined ? undefined : porFuente.get(otro.fuente);
              return e("li", null, otro.nombre, fuente !== undefined && citaConFuente(t, idioma, fuente));
            }),
          ),
        ),
      (d.lugar.historial ?? []).map((cambio) =>
        filaDatos(
          t.ficha.puntoAnterior,
          e("span", { "data-punto-anterior": "" }, cambio.anterior.localidad ?? ""),
          " · ",
          e("span", { class: "mono" }, instante(cambio.fecha)),
          e("span", { class: "texto-nota" }, cambio.motivo[idioma]),
        ),
      ),
      filaDatos(
        t.ficha.drones,
        cifraDe(idioma, t, d.drones?.numero, de(["drones.numero"])),
        d.drones?.modelo !== undefined && e("span", { class: "texto-nota" }, t.ficha.modelo, ": ", d.drones.modelo),
      ),
      filaTipoDron(t, d),
      d.recorrido !== undefined &&
        filaDatos(
          t.rutas.recorrido,
          e("span", { "data-recorrido": "" }, d.recorrido.puntos.map((p) => (p.hora === undefined ? p.nombre : `${p.nombre} (${p.hora})`)).join(" → ")),
          e("q", { class: "texto-nota" }, d.recorrido.cita),
          e("span", { class: "texto-nota" }, t.rutas.recorridoNota),
        ),
      d.tiempo.duracion_min !== undefined && filaDatos(t.ficha.duracion, t.ficha.minutos(numero(d.tiempo.duracion_min, idioma))),
      efectos.length > 0 && filaDatos(t.ficha.efecto, e("ul", null, efectos.map((x) => e("li", null, x)))),
      medidas.length > 0 && filaDatos(t.ficha.respuesta, medidas.map((m) => t.medida[m]).join(" · ")),
      d.atribucion !== undefined &&
        filaDatos(
          t.ficha.atribucion,
          e("span", { "data-atribucion": "" }, t.ficha.atribuidoA(actorEscrito(t, idioma, d.atribucion), autoridadEscrita(d.atribucion.autoridad, idioma))),
          fuenteAtribucion !== undefined
            ? citaConFuente(t, idioma, fuenteAtribucion)
            : e("span", { class: "texto-nota mono" }, instante(d.atribucion.fecha)),
        ),
      d.investigacion !== undefined &&
        d.investigacion.length > 0 &&
        filaDatos(
          t.ficha.investigacion,
          e(
            "ul",
            null,
            d.investigacion.map((x) => {
              const fuente = porFuente.get(x.fuente_id);
              return e(
                "li",
                null,
                t.ficha.investiga(autoridadEscrita(x.autoridad, idioma)),
                e("blockquote", { lang: fuente?.idioma }, `«${x.cita}»`),
                e("p", { class: "texto-fuente" }, e("span", { class: "mono" }, instante(x.fecha)), fuente !== undefined && html(" · ", externo(fuente.enlace, t.ficha.verFuente))),
              );
            }),
          ),
        ),
      d.foco_termico !== undefined && filaDatos(t.foco.rotulo, t.foco.detectado),
      d.control.motivo_desmentido !== undefined && filaDatos(t.ficha.motivoDesmentido, d.control.motivo_desmentido),
      d.episodio !== undefined && filaDatos(t.ficha.episodio, e("span", { class: "mono" }, d.episodio)),
    ),
    e("h2", null, tp.incidente.todasLasFuentes, ` (${numero(fuentes.length, idioma)})`),
    fuentes.length === 0
      ? e("p", null, tp.incidente.sinFuentes)
      : e(
          "ol",
          { class: "texto-fuentes", "data-fuentes": "" },
          fuentes.map((f) =>
            e(
              "li",
              null,
              e("p", null, e("strong", null, medios.get(f.id) ?? f.medio), " · ", e("span", { class: "mono" }, instante(f.fecha)), " · ", e("abbr", { title: tp.incidente.codigoFuente }, `${f.fiabilidad}${f.credibilidad}`)),
              e("blockquote", { lang: f.idioma }, `«${f.frase_origen}»`),
              e("p", null, externo(f.enlace, f.enlace)),
            ),
          ),
        ),
    e("h2", null, t.ficha.historial),
    e(
      "ol",
      { class: "texto-historial" },
      d.estado.historial.map((paso) =>
        e(
          "li",
          null,
          e("strong", null, t.estado[paso.estado]),
          " · ",
          e("span", { class: "mono" }, instante(paso.fecha)),
          " · ",
          paso.motivo !== undefined
            ? e("span", { "data-motivo-historial": "" }, paso.motivo[idioma])
            : paso.fuente_id === undefined
              ? t.ficha.fuenteNoPublica
              : (medios.get(paso.fuente_id) ?? paso.fuente_id),
        ),
      ),
    ),
    e("p", { class: "texto-nota mono" }, t.ficha.actualizada, ": ", fechaHora(d.control.ultima_actualizacion.valor)),
    e(
      "p",
      null,
      enlace(RUTAS.incidentes[idioma], tp.incidente.volver),
      " · ",
      enlace(rutasDePais(d.lugar.pais)[idioma], tp.pais.tituloDe(pais(d.lugar.pais, idioma))),
    ),
  );
  return {
    idioma,
    rutas: rutasDeIncidente(d.id),
    titulo: t.compartir.tituloIncidente(titulo),
    descripcion: tp.incidente.descripcion(estadoTexto, instante(d.tiempo.inicio), lugar),
    cuerpo,
    estructurados: [suceso(d, idioma, titulo, lugar)],
    conMapa: true,
    modificada: d.control.ultima_actualizacion.valor,
  };
}

/** El incidente como suceso de schema.org, solo con campos que están en los datos. */
function suceso(d: IncidenteDetalle, idioma: Idioma, titulo: string, lugar: string): unknown {
  const fechaIso = (v: string, precision: string) => (precision === "dia" || precision === "aproximada" ? v.slice(0, 10) : v);
  const sitio: Record<string, unknown> = {
    "@type": "Place",
    name: lugar,
    address: {
      "@type": "PostalAddress",
      addressCountry: d.lugar.pais,
      ...(d.lon === null && d.lugar.region !== undefined ? { addressRegion: d.lugar.region } : {}),
      ...(d.lugar.localidad !== undefined ? { addressLocality: d.lugar.localidad } : {}),
    },
  };
  if (d.lon !== null) sitio["geo"] = { "@type": "GeoCoordinates", latitude: d.lat, longitude: d.lon };
  return {
    "@context": "https://schema.org",
    "@type": "Event",
    "@id": direccionCompleta(rutaDeFicha(d.id, idioma)),
    identifier: d.id,
    name: titulo,
    inLanguage: idioma,
    url: direccionCompleta(rutaDeFicha(d.id, idioma)),
    startDate: fechaIso(d.tiempo.inicio.valor, d.tiempo.inicio.precision),
    ...(d.tiempo.fin !== undefined ? { endDate: fechaIso(d.tiempo.fin.valor, d.tiempo.fin.precision) } : {}),
    location: sitio,
    description: `${textos(idioma).estado[d.estado.actual]}. ${textos(idioma).tipo[d.tipo]}.`,
  };
}

// ---------------------------------------------------------------------------------------------
// Listas y países

function listaCompleta(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const lista = datos.resumen.incidentes;
  return {
    idioma,
    rutas: RUTAS.incidentes,
    titulo: `${tp.lista.titulo} · ${NOMBRE}`,
    descripcion: tp.lista.descripcion(lista.length),
    cuerpo: html(
      e("h1", null, tp.lista.titulo),
      e("p", null, tp.lista.descripcion(lista.length)),
      e("h2", null, tp.lista.anios),
      e("ul", { class: "texto-enlaces" }, aniosDe(lista).map(([anio, n]) => e("li", null, enlace(rutasDeAnio(anio)[idioma], anio), ` (${numero(n, idioma)})`))),
      e("h2", null, tp.lista.titulo),
      listaDeIncidentes(lista, idioma, t, tp),
    ),
    estructurados: [],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

function listaDeAnio(datos: DatosPaginas, anio: string, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const lista = datos.resumen.incidentes.filter((i) => anioDe(i) === anio);
  return {
    idioma,
    rutas: rutasDeAnio(anio),
    titulo: `${tp.lista.anio(anio)} · ${NOMBRE}`,
    descripcion: tp.lista.descripcionAnio(anio, lista.length),
    cuerpo: html(
      e("h1", null, tp.lista.anio(anio)),
      e("p", null, tp.lista.descripcionAnio(anio, lista.length)),
      tablaCifras(cifras(lista), tp, idioma),
      listaDeIncidentes(lista, idioma, t, tp),
      e("p", null, enlace(RUTAS.incidentes[idioma], tp.lista.titulo)),
    ),
    estructurados: [],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

function listaDePaises(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const tp = textosPagina(idioma);
  const paises = paisesDe(datos.resumen.incidentes, idioma);
  return {
    idioma,
    rutas: RUTAS.paises,
    titulo: `${tp.pais.titulo} · ${NOMBRE}`,
    descripcion: tp.pais.descripcion(paises.length),
    cuerpo: html(
      e("h1", null, tp.pais.titulo),
      e("p", null, tp.pais.descripcion(paises.length)),
      e("ul", { class: "texto-enlaces" }, paises.map(([codigo, nombre, n]) => e("li", null, enlace(rutasDePais(codigo)[idioma], nombre), ` (${numero(n, idioma)})`))),
    ),
    estructurados: [],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

function paginaDePais(datos: DatosPaginas, codigo: string, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const lista = datos.resumen.incidentes.filter((i) => i.pais === codigo);
  const nombre = pais(codigo, idioma);
  const c = cifras(lista);
  return {
    idioma,
    rutas: rutasDePais(codigo),
    titulo: `${tp.pais.tituloDe(nombre)} · ${NOMBRE}`,
    descripcion: tp.pais.descripcionDe(nombre, lista.length),
    cuerpo: html(
      e("h1", null, tp.pais.tituloDe(nombre)),
      e("p", null, tp.pais.descripcionDe(nombre, lista.length)),
      e("h2", null, tp.pais.cifras),
      tablaCifras(c, tp, idioma),
      e("h2", null, tp.pais.lista),
      listaDeIncidentes(lista, idioma, t, tp),
      e("p", null, enlace(RUTAS.paises[idioma], tp.pais.otros)),
    ),
    estructurados: [],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

// ---------------------------------------------------------------------------------------------
// Guerra en Ucrania

const TODO = { desde: Number.NEGATIVE_INFINITY, hasta: Number.POSITIVE_INFINITY };

interface Suma {
  min: number;
  max: number;
  con: boolean;
}

function sumar(s: Suma, min: number, max: number): void {
  if (min === DESCONOCIDO) return;
  s.min += min;
  s.max += max;
  s.con = true;
}

function suma(s: Suma, idioma: Idioma, t: Textos): string {
  return s.con ? (rango({ min: s.min, max: s.max }, idioma) ?? t.ficha.desconocido) : t.ficha.desconocido;
}

function nueva(): Suma {
  return { min: 0, max: 0, con: false };
}

function guerra(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const u = datos.ucrania;
  const totales = { lanzados: nueva(), derribados: nueva(), derribadosUaRu: nueva() };
  const meses = new Map<string, { partes: number; lanzados: Suma; derribados: Suma; derribadosUaRu: Suma }>();
  let primero = Number.POSITIVE_INFINITY;
  let ultimo = Number.NEGATIVE_INFINITY;
  for (const fila of u.ataques) {
    const dia = diaDeParte(fila);
    primero = Math.min(primero, dia);
    ultimo = Math.max(ultimo, dia);
    const mes = fechaDeDia(dia).toISOString().slice(0, 7);
    const m = meses.get(mes) ?? { partes: 0, lanzados: nueva(), derribados: nueva(), derribadosUaRu: nueva() };
    meses.set(mes, m);
    m.partes += 1;
    // Un tramo cuyas cifras ya están en otro parte no se vuelve a sumar.
    if (fila[7] !== 1) continue;
    if (sentidoDeFila(fila) === "RU_UA") {
      sumar(m.lanzados, fila[3], fila[4]);
      sumar(totales.lanzados, fila[3], fila[4]);
      sumar(m.derribados, fila[5], fila[6]);
      sumar(totales.derribados, fila[5], fila[6]);
    } else {
      sumar(m.derribadosUaRu, fila[5], fila[6]);
      sumar(totales.derribadosUaRu, fila[5], fila[6]);
    }
  }
  // La mezcla de lo lanzado, solo con lo que dicen los partes: los meses en que alguno cuenta
  // aparte los Shahed («близько 60 з них – шахеди») o los drones a reacción.
  const mezcla = new Map<string, { partes: number; lanzados: number; shahed: number; conReactivos: number; reactivos: number }>();
  for (const fila of u.ataques) {
    if (fila[7] !== 1 || sentidoDeFila(fila) !== "RU_UA") continue;
    // Una cifra de Shahed propia (no la de los reactivos, que van dentro) y menor que el total:
    // si el parte dice que todos eran Shahed (hasta 2024), no hay mezcla que contar.
    const conShahed = fila[10] > 0 && fila[10] > fila[11] && fila[10] < fila[4];
    if (!conShahed && fila[11] <= 0) continue;
    const mes = fechaDeDia(diaDeParte(fila)).toISOString().slice(0, 7);
    const m = mezcla.get(mes) ?? { partes: 0, lanzados: 0, shahed: 0, conReactivos: 0, reactivos: 0 };
    mezcla.set(mes, m);
    if (conShahed) {
      m.partes += 1;
      m.lanzados += fila[4];
      m.shahed += fila[10];
    }
    if (fila[11] > 0) {
      m.conReactivos += 1;
      m.reactivos += fila[11];
    }
  }
  const porRegion = [...ataquesPorRegion(u, TODO)]
    .map(([codigo, n]) => ({ codigo, n, derribados: cifrasDeRegion(u, codigo, TODO).derribados }))
    .sort((a, b) => b.n - a.n || a.codigo.localeCompare(b.codigo));
  const corredores = corredoresDelPeriodo(u, TODO).sort((a, b) => b.drones - a.drones || a.clave.localeCompare(b.clave));
  const ayuda = t.ayuda;
  const satelite = t.metodologia.secciones.find((s) => s.id === "satelite");
  const seccionRutas = RUTAS_EN_LA_WEB ? t.metodologia.secciones.find((s) => s.id === "rutas") : undefined;
  const fuentesPartes = (["RU_UA", "UA_RU"] as const).map((s) => [s, u.fuentes[s]] as const);
  const cuerpo = html(
    e("h1", null, tp.ucrania.titulo),
    e("p", null, tp.ucrania.descripcion),
    Number.isFinite(primero) && e("p", { class: "texto-nota" }, tp.ucrania.periodo(fechaDia(primero), fechaDia(ultimo))),
    e("h2", null, tp.ucrania.capa),
    e("p", null, ayuda.ucrania),
    e("p", null, ayuda.rusia),
    e("p", null, ayuda.impactos),
    e("h2", null, tp.ucrania.totales),
    e(
      "dl",
      { class: "texto-cifras" },
      filaDatos(tp.ucrania.partes, numero(u.ataques.length, idioma)),
      filaDatos(tp.ucrania.lanzados, suma(totales.lanzados, idioma, t)),
      filaDatos(tp.ucrania.derribados, suma(totales.derribados, idioma, t)),
      filaDatos(tp.ucrania.derribadosUaRu, suma(totales.derribadosUaRu, idioma, t)),
      filaDatos(tp.ucrania.impactos, numero(u.impactos.length, idioma)),
    ),
    e("h2", null, tp.ucrania.porRegion),
    e(
      "table",
      null,
      e("thead", null, e("tr", null, e("th", { scope: "col" }, tp.ucrania.region), e("th", { scope: "col" }, tp.ucrania.ataquesQueLaCitan), e("th", { scope: "col" }, tp.ucrania.derribadosEnLaRegion))),
      e(
        "tbody",
        null,
        porRegion.map((r) =>
          e("tr", null, e("th", { scope: "row" }, region(r.codigo, idioma)), e("td", null, numero(r.n, idioma)), e("td", null, rango(r.derribados ?? undefined, idioma) ?? t.ficha.desconocido)),
        ),
      ),
    ),
    e("h2", null, tp.ucrania.porMes),
    e(
      "table",
      null,
      e(
        "thead",
        null,
        e("tr", null, e("th", { scope: "col" }, tp.ucrania.mes), e("th", { scope: "col" }, tp.ucrania.partes), e("th", { scope: "col" }, tp.ucrania.lanzados), e("th", { scope: "col" }, tp.ucrania.derribados), e("th", { scope: "col" }, tp.ucrania.derribadosUaRu)),
      ),
      e(
        "tbody",
        null,
        [...meses]
          .sort(([a], [b]) => b.localeCompare(a))
          .map(([mes, m]) =>
            e("tr", null, e("th", { scope: "row", class: "mono" }, mes), e("td", null, numero(m.partes, idioma)), e("td", null, suma(m.lanzados, idioma, t)), e("td", null, suma(m.derribados, idioma, t)), e("td", null, suma(m.derribadosUaRu, idioma, t))),
          ),
      ),
    ),
    mezcla.size > 0 && e("h2", null, tp.ucrania.mezcla),
    mezcla.size > 0 && e("p", null, tp.ucrania.mezclaIntro),
    mezcla.size > 0 &&
      e(
        "table",
        null,
        e("thead", null, e("tr", null, e("th", { scope: "col" }, tp.ucrania.mes), e("th", { scope: "col" }, tp.ucrania.partesConShahed), e("th", { scope: "col" }, tp.ucrania.shahedDeclarados), e("th", { scope: "col" }, tp.ucrania.partesConReactivos), e("th", { scope: "col" }, tp.ucrania.reactivosDeclarados))),
        e(
          "tbody",
          null,
          [...mezcla]
            .sort(([a], [b]) => b.localeCompare(a))
            .map(([mes, m]) =>
              e(
                "tr",
                null,
                e("th", { scope: "row", class: "mono" }, mes),
                e("td", null, numero(m.partes, idioma)),
                e("td", null, m.partes === 0 ? "—" : tp.ucrania.deLanzados(numero(m.shahed, idioma), numero(m.lanzados, idioma), Math.round((100 * m.shahed) / m.lanzados))),
                e("td", null, numero(m.conReactivos, idioma)),
                e("td", null, m.conReactivos === 0 ? "—" : numero(m.reactivos, idioma)),
              ),
            ),
        ),
      ),
    e("h2", null, tp.ucrania.corredores),
    e("p", null, tp.ucrania.corredoresIntro),
    e(
      "table",
      null,
      e("thead", null, e("tr", null, e("th", { scope: "col" }, tp.ucrania.origen), e("th", { scope: "col" }, tp.ucrania.destino), e("th", { scope: "col" }, tp.ucrania.drones), e("th", { scope: "col" }, tp.ucrania.ataques))),
      e(
        "tbody",
        null,
        corredores.map((k) =>
          e("tr", null, e("td", null, k.origen ?? tp.ucrania.sinOrigen), e("td", null, region(k.region, idioma)), e("td", null, numero(k.drones, idioma)), e("td", null, numero(k.ataques, idioma))),
        ),
      ),
    ),
    e("h2", null, tp.ucrania.comoSeObtiene),
    e("p", null, tp.ucrania.fuentesDeLosPartes),
    e(
      "ul",
      null,
      fuentesPartes.map(([s, f]) =>
        e("li", null, tp.ucrania.sentido[s], ": ", f === null ? t.ficha.desconocido : html(f.medio, " (", e("abbr", { title: tp.incidente.codigoFuente }, `${f.fiabilidad}${f.credibilidad}`), ")", f.reivindicacion && html(" · ", tp.ucrania.reivindicacion))),
      ),
    ),
    satelite !== undefined && html(e("h3", null, satelite.titulo), satelite.bloques.map(bloque)),
    seccionRutas !== undefined && html(e("h3", null, seccionRutas.titulo), seccionRutas.bloques.map(bloque)),
    e("p", null, enlace(RUTAS.metodologia[idioma], tp.metodologia.titulo)),
  );
  return {
    idioma,
    rutas: RUTAS.ucrania,
    titulo: `${tp.ucrania.titulo} · ${NOMBRE}`,
    descripcion: tp.ucrania.descripcion,
    cuerpo,
    estructurados: [],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

// ---------------------------------------------------------------------------------------------
// Metodología y ayuda

function metodologia(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const d = t.metodologia.descargas;
  const version = fechaHora(datos.resumen.actualizado);
  const descargas: [string, string, string][] = [
    [d.incidentes, DESCARGAS.incidentesGeojson, "GeoJSON"],
    [d.incidentes, DESCARGAS.incidentesCsv, "CSV"],
    [d.sinUbicacion, DESCARGAS.sinUbicacionJson, "JSON"],
    [d.ucrania, DESCARGAS.ucraniaJson, "JSON"],
    [d.ucrania, DESCARGAS.ucraniaCsv, "CSV"],
  ];
  const cuerpo = html(
    e("h1", null, tp.metodologia.titulo),
    e("nav", { "aria-label": tp.metodologia.indice }, e("ul", { class: "texto-enlaces" }, seccionesDeMetodologia(t).map((s) => e("li", null, enlace(`#${s.id}`, s.titulo))), e("li", null, enlace("#datos-abiertos", d.titulo)), e("li", null, enlace("#sobre", t.metodologia.sobre)))),
    seccionesDeMetodologia(t).map((s) => e("section", { id: s.id }, e("h2", null, s.titulo), s.bloques.map(bloque))),
    e(
      "section",
      { id: "datos-abiertos" },
      e("h2", null, d.titulo),
      e("p", null, d.intro),
      e("ul", null, descargas.map(([nombre, ruta, formato]) => e("li", null, nombre, ": ", e("a", { href: ruta, download: true }, formato)))),
      e("p", { class: "mono" }, d.version(version)),
      e("p", null, d.licencia, ": ", externo(LICENCIA_DATOS_URL, LICENCIA_DATOS)),
      e("p", { "data-licencia-texto": "" }, d.licenciaTexto),
      e("h3", null, d.citaTitulo),
      e("blockquote", null, d.cita(version)),
    ),
    e(
      "section",
      { id: "sobre" },
      e("h2", null, t.metodologia.sobre),
      e("ul", { class: "texto-enlaces" }, PAGINAS_SERVICIO.map((p) => e("li", null, enlace(RUTAS_SERVICIO[p][idioma], textoServicio(p, idioma).enlace)))),
    ),
  );
  const descripcion = tp.metodologia.descripcion;
  return {
    idioma,
    rutas: RUTAS.metodologia,
    titulo: `${tp.metodologia.titulo} · ${NOMBRE}`,
    descripcion,
    cuerpo,
    estructurados: [conjuntoDeDatos(datos, idioma)],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

/** El conjunto de datos abierto, con su licencia y sus descargas. */
function conjuntoDeDatos(datos: DatosPaginas, idioma: Idioma): unknown {
  const tp = textosPagina(idioma);
  const formatos: [string, string][] = [
    [DESCARGAS.incidentesGeojson, "application/geo+json"],
    [DESCARGAS.incidentesCsv, "text/csv"],
    [DESCARGAS.sinUbicacionJson, "application/json"],
    [DESCARGAS.ucraniaJson, "application/json"],
    [DESCARGAS.ucraniaCsv, "text/csv"],
  ];
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: tp.portada.titulo,
    description: tp.portada.descripcion,
    url: direccionCompleta(RUTAS.metodologia[idioma]),
    inLanguage: idioma,
    license: LICENCIA_DATOS_URL,
    isAccessibleForFree: true,
    creator: { "@type": "Organization", name: NOMBRE, url: `${ORIGEN}/` },
    dateModified: datos.resumen.actualizado,
    spatialCoverage: { "@type": "Place", name: "Europe" },
    distribution: formatos.map(([ruta, tipo]) => ({ "@type": "DataDownload", contentUrl: ORIGEN + ruta, encodingFormat: tipo })),
  };
}

function ayuda(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const a = t.ayuda;
  const parrafos = [a.colores, a.aproximado, a.periodo, a.ahora, a.areas, a.lineas, a.numeros, a.pila, a.pulsos, a.reciente, a.novedad, a.ucrania, a.rusia, a.impactos, a.foco, a.directo];
  return {
    idioma,
    rutas: RUTAS.ayuda,
    titulo: `${tp.ayuda.titulo} · ${NOMBRE}`,
    descripcion: tp.ayuda.descripcion,
    cuerpo: html(
      e("h1", null, tp.ayuda.titulo),
      parrafos.map((p) => e("p", null, p)),
      e("h2", null, a.atajos),
      e("ul", null, Object.values(a.acciones).map((accion) => e("li", null, accion))),
    ),
    estructurados: [],
    conMapa: false,
    modificada: datos.resumen.actualizado,
  };
}

// ---------------------------------------------------------------------------------------------
// Todas

/** Todas las páginas, en los dos idiomas. */
export function paginas(datos: DatosPaginas): PaginaTexto[] {
  const resultado: PaginaTexto[] = [];
  const anios = aniosDe(datos.resumen.incidentes).map(([anio]) => anio);
  const codigos = [...new Set(datos.resumen.incidentes.map((i) => i.pais))].sort();
  for (const idioma of IDIOMAS) {
    resultado.push(portada(datos, idioma));
    for (const i of datos.resumen.incidentes) {
      const detalle = datos.detalles.get(i.id);
      if (detalle === undefined) throw new Error(`sin ficha completa: ${i.id}`);
      resultado.push(incidente(detalle, idioma));
    }
    resultado.push(listaCompleta(datos, idioma));
    for (const anio of anios) resultado.push(listaDeAnio(datos, anio, idioma));
    resultado.push(listaDePaises(datos, idioma));
    for (const codigo of codigos) resultado.push(paginaDePais(datos, codigo, idioma));
    resultado.push(guerra(datos, idioma));
    resultado.push(paginaPrevision(datos, idioma));
    resultado.push(metodologia(datos, idioma));
    resultado.push(ayuda(datos, idioma));
    for (const pagina of PAGINAS_SERVICIO) resultado.push(paginaServicio(pagina, idioma));
  }
  return resultado;
}

// ---------------------------------------------------------------------------------------------
// Servicio público: aviso legal, privacidad, independencia, correcciones y accesibilidad

/** Fecha de la última revisión de las páginas de servicio, para el sitemap. */
const REVISION_SERVICIO = "2026-10-08T00:00:00Z";

/**
 * El botón que borra la fecha de la última visita, en la página de privacidad: oculto hasta que
 * su script (SCRIPT_BORRAR_VISITA) lo enseña; sin código, la explicación de cómo hacerlo.
 */
function borrarVisita(idioma: Idioma): Html {
  const b = BORRAR_VISITA[idioma];
  return html(
    e(
      "p",
      null,
      e("button", { type: "button", class: "texto-boton", hidden: true, "data-borrar-visita": "", "data-hecho": b.hecho, "data-fallo": b.fallo }, b.boton),
    ),
    e("p", { role: "status", "aria-live": "polite", "data-borrar-visita-estado": "" }),
    e("noscript", null, e("p", null, b.sinCodigo)),
  );
}

export function paginaServicio(pagina: PaginaServicio, idioma: Idioma): PaginaTexto {
  const texto = textoServicio(pagina, idioma);
  const conBoton = pagina === "privacidad";
  return {
    idioma,
    rutas: RUTAS_SERVICIO[pagina],
    titulo: `${texto.titulo} · ${NOMBRE}`,
    descripcion: texto.descripcion,
    cuerpo: html(
      e("h1", null, texto.titulo),
      texto.secciones.map((s) =>
        e("section", { id: s.id }, e("h2", null, s.titulo), s.bloques.map(bloque), conBoton && s.id === "navegador" && borrarVisita(idioma)),
      ),
    ),
    estructurados: [],
    conMapa: false,
    modificada: REVISION_SERVICIO,
    ...(conBoton ? { scripts: [SCRIPT_BORRAR_VISITA] } : {}),
  };
}

// ---------------------------------------------------------------------------------------------
// Previsión y tendencias

function paginaPrevision(datos: DatosPaginas, idioma: Idioma): PaginaTexto {
  const t = textos(idioma);
  const tp = textosPagina(idioma);
  const p = t.prevision;
  const d = datos.prevision;
  const partes: Hijo[] = [e("h1", null, tp.prevision.titulo), e("p", null, tp.prevision.intro)];
  if (d === null || d === undefined) {
    partes.push(e("p", null, p.noDisponible));
  } else {
    const dia = (texto: string) => fechaDia(diaDeTexto(texto));
    const comoSeComprueba = (...hijos: Hijo[]) => e("details", null, e("summary", null, p.comoSeComprueba), ...hijos);
    const frontera = d.frontera.paises.map((f) =>
      e(
        "section",
        { "data-frontera": f.pais },
        e("h3", null, pais(f.pais, idioma)),
        e("p", null, probabilidadLlana(t, f.probabilidad, f.de_cada_10)),
        e("p", null, p.frontera.habitual(habitualDe(f.comprobacion))),
        factoresQueCuentan(f).length === 0
          ? e("p", null, p.frontera.sinCambios)
          : html(
              e("p", null, p.frontera.dependeDe),
              e("ul", null, factoresQueCuentan(f).map(({ factor, efecto }) => e("li", null, textoFactor(t, idioma, f, factor, efecto)))),
            ),
        comoSeComprueba(
          e("p", null, p.frontera.historial(numero(f.comprobacion.noches, idioma), dia(f.comprobacion.desde), f.comprobacion.noches_con_dron, habitualDe(f.comprobacion), f.comprobacion.con_dron_en_riesgo_alto)),
          e(
            "table",
            null,
            e("caption", null, p.frontera.verHistorial),
            e("thead", null, e("tr", null, e("th", null, p.frontera.columnaDijo), e("th", null, p.frontera.columnaNoches), e("th", null, p.frontera.columnaConDron))),
            e("tbody", null, f.comprobacion.tramos.map((tramo) => e("tr", null, e("td", null, p.frontera.tramo(Math.round(tramo.desde * 100), Math.round(tramo.hasta * 100))), e("td", null, numero(tramo.noches, idioma)), e("td", null, numero(tramo.con_dron, idioma))))),
          ),
        ),
      ),
    );
    partes.push(
      e(
        "section",
        { id: "frontera" },
        e("h2", null, p.frontera.titulo),
        e("p", null, p.frontera.noche(dia(d.frontera.noche.desde), dia(d.frontera.noche.hasta))),
        frontera.length === 0 ? e("p", null, p.frontera.ninguno) : frontera,
      ),
    );
    const aviso = d.segunda_noche?.aviso;
    if (aviso !== undefined) {
      partes.push(e("section", { id: "segunda-noche" }, e("h2", null, p.segundaNoche.titulo), e("p", null, p.segundaNoche.aviso(numero(aviso.lanzados, idioma), probabilidadLlana(t, aviso.probabilidad, aviso.de_cada_10)))));
    }
    if (d.rachas !== undefined) {
      const r = d.rachas;
      partes.push(
        e(
          "section",
          { id: "rachas" },
          e("h2", null, p.rachas.titulo),
          r.activas.length === 0
            ? e("p", null, p.rachas.ninguna)
            : e("ul", null, r.activas.map((racha) => e("li", { "data-racha": racha.pais }, enlace(rutasDePais(racha.pais)[idioma], pais(racha.pais, idioma)), ": ", p.rachas.linea(dia(racha.desde), racha.incidentes, numero(racha.habitual, idioma), numero(racha.veces, idioma), p.rachas.tendencia[racha.tendencia])))),
          comoSeComprueba(e("p", null, p.rachas.historial(r.comprobacion.semanas_en_racha, r.comprobacion.incidentes_semana_siguiente, numero(r.comprobacion.normal_semana_siguiente, idioma)))),
        ),
      );
    }
    if (d.cambios !== undefined && d.cambios.ambitos.some((a) => a.cambios.length > 0)) {
      partes.push(
        e(
          "section",
          { id: "cambios" },
          e("h2", null, p.cambios.titulo),
          e("p", null, p.cambios.periodo(mesEscrito(d.cambios.recientes.desde, idioma), mesEscrito(d.cambios.recientes.hasta, idioma))),
          d.cambios.ambitos
            .filter((a) => a.cambios.length > 0)
            .map((a) =>
              html(
                e("h3", null, p.cambios.ambito[a.ambito]),
                e("ul", null, a.cambios.map((c) => e("li", null, textoCambio(t, a, c)))),
                comoSeComprueba(e("p", null, p.cambios.historial(a.comprobacion.casos, a.comprobacion.sostenidos))),
              ),
            ),
        ),
      );
    }
    partes.push(
      e("p", null, d.metodo[idioma], " ", p.calculada(fechaHora(d.calculado)), " ", enlace(`${RUTAS.metodologia[idioma]}#prevision`, tp.prevision.comoSeCalcula)),
    );
  }
  return {
    idioma,
    rutas: RUTAS.prevision,
    titulo: `${tp.prevision.titulo} · ${NOMBRE}`,
    descripcion: tp.prevision.descripcion,
    cuerpo: html(partes),
    estructurados: [],
    conMapa: false,
    modificada: d?.calculado.replace("Z", ":00Z") ?? datos.resumen.actualizado,
  };
}

// ---------------------------------------------------------------------------------------------
// Marco de la página: cabecera de navegación y pie, iguales en todas

export function marco(pagina: PaginaTexto, actualizado: string): Html {
  const tp = textosPagina(pagina.idioma);
  const idioma = pagina.idioma;
  const otro: Idioma = idioma === "es" ? "en" : "es";
  const nav: [string, string][] = [
    [PORTADA[idioma], tp.nav.mapa],
    [RUTAS.incidentes[idioma], tp.nav.incidentes],
    [RUTAS.paises[idioma], tp.nav.paises],
    [RUTAS.ucrania[idioma], tp.nav.ucrania],
    [RUTAS.prevision[idioma], tp.nav.prevision],
    [RUTAS.metodologia[idioma], tp.nav.metodologia],
    [RUTAS.ayuda[idioma], tp.nav.ayuda],
  ];
  return html(
    e("a", { class: "texto-saltar", href: "#contenido" }, tp.saltar),
    e(
      "header",
      { class: "texto-cabecera" },
      e("a", { class: "texto-marca", href: PORTADA[idioma] }, e("img", { src: "/marca/eodi-simplificado.svg", alt: "", width: 24, height: 24 }), NOMBRE),
      e("nav", { "aria-label": tp.navegacion }, e("ul", null, nav.map(([ruta, nombre]) => e("li", null, e("a", { href: ruta, "aria-current": ruta === pagina.rutas[idioma] ? "page" : null }, nombre))))),
      e("a", { class: "texto-idioma", href: pagina.rutas[otro], hreflang: otro, lang: otro }, tp.otroIdioma),
    ),
    e("main", { id: "contenido" }, pagina.cuerpo),
    e(
      "footer",
      { class: "texto-pie" },
      e("p", { class: "mono", "data-datos-de": "" }, tp.datosDe(fechaHora(actualizado))),
      e("p", null, tp.licencia, " ", externo(LICENCIA_DATOS_URL, LICENCIA_DATOS), " · ", externo(REPOSITORIO, tp.codigo)),
      e(
        "nav",
        { "aria-label": textosPagina(idioma).sobre },
        e("ul", { class: "texto-enlaces" }, PAGINAS_SERVICIO.map((p) => e("li", null, e("a", { href: RUTAS_SERVICIO[p][idioma], "aria-current": RUTAS_SERVICIO[p][idioma] === pagina.rutas[idioma] ? "page" : null }, textoServicio(p, idioma).enlace)))),
      ),
    ),
  );
}

export { jsonLd };
