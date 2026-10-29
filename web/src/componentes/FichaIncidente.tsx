import { afirmacionesDe, valorLegible } from "../datos/afirmaciones.ts";
import { ACTOR_SIN_NOMBRE, atribucionResumida } from "../datos/derivar.ts";
import { cierre as leerCierre } from "../datos/efecto.ts";
import { relato } from "../datos/relato.ts";
import { historialCompleto, marcaDe, marcaDePresencia, pasosDePresencia, rotuloDeMarca } from "../datos/presencia.ts";
import type {
  AfirmacionPublica,
  Atribucion,
  IncidenteDetalle,
  PresenciaDron,
  RangoODesconocido,
} from "../datos/tipos.ts";
import {
  fechaHora,
  instante,
  jornadaEscrita,
  numero,
  pais,
  rango,
  textoAtribuido,
} from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { diaDeInstante } from "../tiempo/dias.ts";
import { Cita } from "./Cita.tsx";
import { EnlaceFuente } from "./EnlaceFuente.tsx";
import { EstadoConTexto, fuenteEnFrase, Historial, ListaFuentes, nombreDeAutoridad, nombreDeFuente } from "./Fuentes.tsx";
import { LineaFoco, ZOOM_VISOR_PUNTO } from "./FocoTermico.tsx";
import { LineaTrafico } from "./TraficoAereo.tsx";
import { Fila } from "./Panel.tsx";
import { Simbolo } from "./Simbolo.tsx";
import { textoAproximado } from "../datos/lugarAproximado.ts";
import { FilaRecorrido, FilaTipoDron } from "./TipoDron.tsx";
import {
  anteriorEscrito,
  enFlancoEste,
  lugarEscrito,
  modeloEscrito,
  objetivoEscrito,
  otroLugarEscrito,
  regionEscrita,
} from "../datos/nombres.ts";

/**
 * Marca que acompaña al texto de la presencia de dron, para no depender del color. La no
 * acreditada y la descartada llevan en su lugar su círculo, el mismo del mapa (Simbolo).
 */
const MARCA_PRESENCIA: Record<Exclude<PresenciaDron, "no_acreditada" | "descartada">, string> = {
  confirmada: "✓",
  no_confirmada: "?",
};

interface Props {
  t: Textos;
  idioma: Idioma;
  incidente: IncidenteDetalle;
  /** Fecha de los datos publicados, para la frase del estado actual («A 27 de octubre de 2026…»). */
  actualizado?: string | null;
}

/** Campos públicos que respalda cada fila de la ficha, para listar qué dice cada fuente. */
const CAMPOS_DE_FILA = {
  presencia: ["presencia_dron"],
  fecha: ["tiempo.inicio", "tiempo.fin"],
  lugar: ["lugar.pais", "lugar.localidad"],
  drones: ["drones.numero", "drones.clase", "drones.modelo"],
  duracion: ["tiempo.duracion_min"],
  efecto: [
    "consecuencias.cierre.valor",
    "consecuencias.cierre.minutos",
    "consecuencias.vuelos_desviados",
    "consecuencias.vuelos_cancelados",
    "consecuencias.vuelos_retrasados",
    "consecuencias.danos.nivel",
    "consecuencias.heridos",
    "consecuencias.fallecidos",
  ],
  respuesta: ["respuesta.medidas"],
  atribucion: ["atribucion.actor", "atribucion.autoridad"],
} as const;

/** Un código interno de lo que dice la fuente («no_confirmada», «si», «aeropuerto», «DE»)
 *  escrito con las palabras de la página; lo que no es un código, tal cual. */
function textoDeCodigo(t: Textos, idioma: Idioma, campo: string, texto: string): string {
  const en = <T extends string>(tabla: Partial<Record<T, string>>): string | undefined =>
    (tabla as Record<string, string | undefined>)[texto];
  switch (campo) {
    case "presencia_dron":
      return en(t.presencia) ?? texto;
    case "tipo":
      return en(t.tipo) ?? texto;
    case "objetivo.categoria":
      return en(t.categoria) ?? texto;
    case "lugar.pais":
      return /^[A-Z]{2}$/.test(texto) ? pais(texto, idioma) : texto;
    case "consecuencias.cierre.valor":
      return texto === "si" ? t.ficha.cierreSinDuracion : texto === "no" ? t.ficha.sinCierre : texto;
    case "consecuencias.danos.nivel":
      return en(t.ficha.danos) ?? texto;
    default:
      return texto;
  }
}

function ValorDeFuente({ t, idioma, valor, campo = "" }: { t: Textos; idioma: Idioma; valor: unknown; campo?: string }) {
  const legible = valorLegible(valor);
  switch (legible.clase) {
    case "desconocido":
      return <span className="text-secundario">{t.ficha.desconocido}</span>;
    case "rango":
      return <span className="mono">{rango(legible.rango, idioma)}</span>;
    case "instante":
      return <span className="mono">{legible.precision === "dia" || legible.precision === "aproximada" ? instante({ valor: legible.valor, precision: "dia" }) : fechaHora(legible.valor)}</span>;
    case "texto":
      return <span>{textoDeCodigo(t, idioma, campo, legible.texto)}</span>;
  }
}

/** Desplegable con lo que dice cada fuente sobre los campos de una fila. */
function QueDiceCadaFuente({
  t,
  idioma,
  afirmaciones,
  idiomas = new Map(),
}: {
  t: Textos;
  idioma: Idioma;
  afirmaciones: readonly AfirmacionPublica[];
  /** Idioma de cada fuente, para la cita original. */
  idiomas?: ReadonlyMap<string, string>;
}) {
  if (afirmaciones.length === 0) return null;
  const variosCampos = new Set(afirmaciones.map((a) => a.campo)).size > 1;
  return (
    <details className="mt-1 text-xs">
      <summary className="cursor-pointer text-acento tel:flex tel:min-h-11 tel:items-center">
        {t.ficha.queDiceCadaFuente(afirmaciones.length)}
      </summary>
      <ul className="mt-1">
        {afirmaciones.map((afirmacion, i) => {
          const codigo = `${afirmacion.fiabilidad}${afirmacion.credibilidad}`;
          return (
            <li key={i} className="border-t border-linea py-1">
              {variosCampos && (
                <span className="mono block text-secundario">{afirmacion.campo}</span>
              )}
              <ValorDeFuente t={t} idioma={idioma} valor={afirmacion.valor} campo={afirmacion.campo} />{" "}
              <span className="text-secundario">{t.ficha.valorSegun}</span> {fuenteEnFrase(t, afirmacion.medio, idioma)}{" "}
              <span className="mono rounded-sm border border-linea px-1 text-acento">
                <span className="sr-only">{t.ficha.codigo(codigo)}</span>
                <span aria-hidden="true">{codigo}</span>
              </span>{" "}
              <span className="mono text-secundario">{instante(afirmacion.fecha)}</span>
              {afirmacion.cita && (
                <Cita
                  t={t}
                  idioma={idioma}
                  texto={afirmacion.cita}
                  idiomaOriginal={idiomas.get(afirmacion.fuente_id)}
                  traduccion={afirmacion.cita_traduccion}
                  como="q"
                  className="block text-secundario"
                />
              )}
            </li>
          );
        })}
      </ul>
    </details>
  );
}

/** La cifra publicada, tal cual: lo que dice cada fuente va aparte («qué dice cada fuente»). */
function Cifra({
  t,
  idioma,
  valor,
  unidad,
}: {
  t: Textos;
  idioma: Idioma;
  valor: RangoODesconocido | undefined;
  unidad?: string;
}) {
  const texto = rango(valor, idioma);
  if (texto === null) return <span className="text-secundario">{t.ficha.desconocido}</span>;
  return (
    <>
      <span className="mono">{texto}</span>
      {unidad !== undefined && ` ${unidad}`}
    </>
  );
}

/** A quién se atribuye, en el idioma de la web: un Estado por su código, nunca con el texto de
 *  la fuente («Russland»); una persona que la autoridad no nombra, «una persona». */
function actorEscrito(t: Textos, idioma: Idioma, atribucion: Atribucion): string {
  if (atribucion.tipo === "estado" && atribucion.pais !== undefined) return pais(atribucion.pais, idioma);
  if (atribucion.tipo === "persona" && atribucion.actor === ACTOR_SIN_NOMBRE) return t.atribucion.unaPersona;
  return atribucion.actor;
}

function tieneCifra(valor: RangoODesconocido | undefined): boolean {
  return valor !== undefined && valor !== "desconocido";
}

export function FichaIncidente({ t, idioma, incidente, actualizado = null }: Props) {
  const { tiempo, lugar, objetivo, drones, consecuencias, respuesta, atribucion } = incidente;
  // El marcador de un atribuido: su bandera y, si es una persona, el punto.
  const marcador = atribucionResumida(incidente);
  // A quién y según quién, escrito en el idioma de la web: el país a partir de su código, la
  // persona sin nombre como «una persona» y la autoridad traducida.
  const actor = atribucion === undefined ? "" : actorEscrito(t, idioma, atribucion);
  const autoridad = atribucion === undefined ? "" : nombreDeAutoridad(atribucion.autoridad, idioma);
  const porFuente = new Map(incidente.fuentes.map((f) => [f.id, f]));
  const idiomasFuentes = new Map(incidente.fuentes.map((f) => [f.id, f.idioma]));
  // La declaración que lo atribuye: la fuente del último paso a «atribuido», con su frase literal.
  const pasoAtribuido = incidente.estado.historial.findLast((paso) => paso.estado === "atribuido");
  const fuenteAtribucion =
    atribucion === undefined || pasoAtribuido?.fuente_id === undefined
      ? undefined
      : porFuente.get(pasoAtribuido.fuente_id);
  const titulo = incidente.titulo[idioma];
  // Los nombres de lugar, como se escriben en el idioma de la página (datos/nombres.ts). La
  // cabecera es la instalación solo si es una de verdad (con categoría propia, no «otra»): si
  // no, el titular, sin repetirlo debajo (EODI-2026-00648, «Józefów · Otro lugar»).
  const instalacion = objetivo !== undefined && objetivo.categoria !== "otra";
  const nombre = (instalacion ? objetivoEscrito(incidente, idioma) : null) ?? titulo;
  const modelo = modeloEscrito(drones?.modelo);
  const vuelos: [RangoODesconocido | undefined, string][] = [
    [consecuencias?.vuelos_desviados, t.ficha.vuelosDesviados],
    [consecuencias?.vuelos_cancelados, t.ficha.vuelosCancelados],
    [consecuencias?.vuelos_retrasados, t.ficha.vuelosRetrasados],
    [consecuencias?.heridos, t.ficha.heridos],
    [consecuencias?.fallecidos, t.ficha.fallecidos],
  ];
  const medidas = respuesta?.medidas ?? [];
  const de = (campos: readonly string[]) => afirmacionesDe(incidente, campos);
  // «desconocido» en el cierre quiere decir que ninguna fuente habla de cierre: solo se dice
  // en las interrupciones aeroportuarias, donde el cierre es lo que se espera saber.
  const cierre = leerCierre(incidente.tipo, consecuencias);
  const rangoCierre =
    cierre?.clase === "con_duracion"
      ? rango(cierre.minutos, idioma)
      : null;
  const textoCierre =
    cierre === null
      ? null
      : cierre.clase === "con_duracion"
        ? t.ficha.cierreDe(rangoCierre ?? "")
        : cierre.clase === "sin_duracion"
          ? t.ficha.cierreSinDuracion
          : cierre.clase === "sin_cierre"
            ? t.ficha.sinCierre
            : t.ficha.cierreDesconocido;
  const imprecisa = incidente.lon === null ? incidente.lugar : null;
  const aproximado = incidente.lon === null ? (incidente.aproximado ?? null) : null;
  // La fuente oficial cuya frase nombra el lugar del punto, si está entre las del incidente.
  const fuentePunto = lugar.fuente_punto === undefined ? undefined : porFuente.get(lugar.fuente_punto);
  // Los demás lugares; el que lleva fuente se explica con su frase (un daño de la defensa).
  const otrosLugares = (lugar.otros_lugares ?? []).map((otro, i) => ({
    ...otro,
    escrito: otroLugarEscrito(incidente, i, idioma),
  }));
  const sinFuente = otrosLugares.filter(
    (otro) => otro.escrito !== null && (otro.fuente === undefined || !porFuente.has(otro.fuente)),
  );
  const conFuente = otrosLugares.filter((otro) => otro.fuente !== undefined && porFuente.has(otro.fuente));
  const cambios = lugar.historial ?? [];
  // La presencia de dron rectificada: su secuencia, con la fecha y la fuente de cada paso.
  const pasosPresencia = pasosDePresencia(t, idioma, incidente);
  const marca = marcaDe({ estado: incidente.estado.actual, presencia: incidente.presencia_dron ?? null });
  const marcaPresencia = marcaDePresencia(incidente.presencia_dron);
  return (
    <article>
      {/* El círculo es la marca del incidente en el mapa, no el color del tipo: con la presencia
          rectificada lleva su nombre al lado («No acreditado · Interrupción aeroportuaria»). */}
      <p className="rotulo flex items-center gap-2" data-marca-ficha={marca}>
        <Simbolo estado={marca} atribucion={marcador} aproximado={incidente.lon === null} />
        {marca === "no_acreditado" || marca === "descartado" ? `${rotuloDeMarca(t, marca)} · ${t.tipo[incidente.tipo]}` : t.tipo[incidente.tipo]}
      </p>
      <h2 className="text-xl font-semibold tracking-tight mt-1 text-2xl">{nombre}</h2>
      {nombre !== titulo && <p className="mt-2 text-texto">{titulo}</p>}
      <p className="mono mt-1 text-xs text-secundario">{incidente.id}</p>
      {/* La ficha contada en un párrafo, antes de los campos (datos/relato.ts). */}
      <p className="mt-3 text-sm leading-relaxed text-texto" data-relato="">
        {relato(incidente, idioma, actualizado ?? incidente.control.ultima_actualizacion.valor).join(" ")}
      </p>

      <dl className="mt-3">
        <Fila nombre={t.ficha.estado}>
          {incidente.estado.actual === "atribuido" && atribucion !== undefined ? (
            <span className="inline-flex items-center gap-1.5" data-estado-atribuido="">
              <Simbolo estado="atribuido" atribucion={marcador} etiqueta={textoAtribuido(t, idioma, marcador)} />
              {t.ficha.confirmadoAtribuido(actor, autoridad)}
            </span>
          ) : (
            <EstadoConTexto t={t} estado={incidente.estado.actual} />
          )}
        </Fila>
        {incidente.presencia_dron !== undefined && (
          <Fila nombre={t.ficha.presenciaDron}>
            {marcaPresencia === null ? (
              <span aria-hidden="true" className="mono mr-1.5 text-acento">
                {MARCA_PRESENCIA[incidente.presencia_dron as keyof typeof MARCA_PRESENCIA]}
              </span>
            ) : (
              <Simbolo estado={marcaPresencia} className="mr-1.5 inline-block align-[-0.2em]" />
            )}
            <span data-presencia={incidente.presencia_dron}>{t.presencia[incidente.presencia_dron]}</span>
            {pasosPresencia.length > 0 && (
              // Cada paso enlaza a su fuente; una corrección parcial es una nota que no cambia el valor.
              <ol aria-label={t.presenciaHistorial.rotulo} className="mt-1 text-xs" data-presencia-historial="">
                {pasosPresencia.map((paso, i) => (
                  <li
                    key={i}
                    className={paso.parcial ? "mt-0.5 text-secundario" : "mt-0.5 text-texto"}
                    data-paso-presencia={paso.valor}
                    data-parcial={paso.parcial ? "" : undefined}
                  >
                    {paso.fuente === undefined ? (
                      paso.texto
                    ) : (
                      <EnlaceFuente t={t} fuente={paso.fuente}>
                        {paso.texto}
                      </EnlaceFuente>
                    )}
                    {paso.resto}
                  </li>
                ))}
              </ol>
            )}
            <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.presencia)} />
          </Fila>
        )}
        <Fila nombre={t.ficha.fecha}>
          <span className="mono">{instante(tiempo.inicio)}</span>
          {tiempo.fin !== undefined && <span className="mono"> – {instante(tiempo.fin)}</span>}
          <span className="block text-xs text-secundario">
            {t.precision[tiempo.inicio.precision]}
          </span>
          <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.fecha)} />
        </Fila>
        <Fila nombre={t.ficha.lugar}>
          <span data-lugar="">{lugarEscrito(incidente, idioma, imprecisa !== null)}</span>
          {objetivo !== undefined && (
            <span className="block text-xs text-secundario">
              {t.categoria[objetivo.categoria]}
              {objetivo.oaci !== undefined && <span className="mono"> · {objetivo.oaci}</span>}
            </span>
          )}
          {imprecisa === null && "radio_km" in lugar ? (
            <span className="block text-xs text-secundario">
              {t.ficha.radio(numero(lugar.radio_km, idioma))}
            </span>
          ) : (
            imprecisa !== null && (
              <span className="block text-xs" data-lugar-aproximado={aproximado?.nivel ?? ""}>
                {aproximado !== null ? (
                  <>
                    <span className="text-notificado">
                      {textoAproximado(t, idioma, aproximado, lugar.pais, regionEscrita(incidente, idioma)).nivel}
                    </span>
                    <span className="block text-secundario">
                      {textoAproximado(t, idioma, aproximado, lugar.pais, regionEscrita(incidente, idioma)).deDonde}
                    </span>
                  </>
                ) : (
                  <span className="text-notificado">
                    {t.imprecisa.etiqueta} · {t.imprecisa.nivel[imprecisa.nivel]}
                  </span>
                )}
              </span>
            )
          )}
          <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.lugar)} />
        </Fila>
        {/* Frontera o interior solo tiene sentido en el flanco este (datos/nombres.ts). */}
        {incidente.zona !== undefined && enFlancoEste(incidente) && (
          <Fila nombre={t.zona.titulo}>
            <span data-zona={incidente.zona.grupo}>{t.zona.grupo[incidente.zona.grupo]}</span>
            <span className="block text-xs text-secundario">
              {t.zona.motivo(incidente.zona.motivo, incidente.zona.distancia_km ?? null)}
            </span>
          </Fila>
        )}
        {fuentePunto !== undefined && (
          <Fila nombre={t.ficha.lugarSegun}>
            <span data-lugar-segun="">{nombreDeFuente(t, fuentePunto.medio, idioma)}</span>
            <Cita
              t={t}
              idioma={idioma}
              texto={fuentePunto.frase_origen}
              idiomaOriginal={fuentePunto.idioma}
              traduccion={fuentePunto.traduccion}
              className="mt-0.5 border-l border-acento pl-2 text-secundario"
            />
            <span className="mono block text-xs text-secundario">
              {instante(fuentePunto.fecha)}
              {" · "}
              <EnlaceFuente t={t} fuente={fuentePunto}>
                {t.ficha.verFuente}
              </EnlaceFuente>
            </span>
          </Fila>
        )}
        {otrosLugares.length > 0 && (
          <Fila nombre={t.ficha.otrosLugares}>
            {conFuente.map((otro) => {
              const fuente = porFuente.get(otro.fuente ?? "");
              return (
                fuente !== undefined && (
                  <span key={otro.nombre} className="mb-1.5 block" data-otro-lugar-explicado="">
                    {otro.escrito}
                    <Cita
                      t={t}
                      idioma={idioma}
                      texto={fuente.frase_origen}
                      idiomaOriginal={fuente.idioma}
                      traduccion={fuente.traduccion}
                      className="mt-0.5 border-l border-acento pl-2 text-secundario"
                    />
                    <span className="mono block text-xs text-secundario">
                      {nombreDeFuente(t, fuente.medio, idioma)} · {instante(fuente.fecha)}
                      {" · "}
                      <EnlaceFuente t={t} fuente={fuente}>
                        {t.ficha.verFuente}
                      </EnlaceFuente>
                    </span>
                  </span>
                )
              );
            })}
            {sinFuente.length > 0 && (
              <span data-otros-lugares="">{sinFuente.map((otro) => otro.escrito).join(", ")}</span>
            )}
          </Fila>
        )}
        {cambios.map((cambio, i) => (
          <Fila key={cambio.fecha.valor} nombre={t.ficha.puntoAnterior}>
            <span data-punto-anterior="">{anteriorEscrito(incidente, i, idioma) ?? ""}</span>
            <span className="mono block text-xs text-secundario">{instante(cambio.fecha)}</span>
            <span className="block text-xs text-texto">{cambio.motivo[idioma]}</span>
          </Fila>
        ))}
        <Fila nombre={t.ficha.drones}>
          <Cifra t={t} idioma={idioma} valor={drones?.numero} />
          {modelo !== null && (
            <span className="block text-xs text-secundario">
              {t.ficha.modelo}: {modelo}
            </span>
          )}
          <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.drones)} />
        </Fila>
        <FilaTipoDron t={t} idioma={idioma} incidente={incidente} />
        <FilaRecorrido t={t} idioma={idioma} incidente={incidente} />
        {tiempo.duracion_min !== undefined && (
          <Fila nombre={t.ficha.duracion}>
            <span className="mono">{t.ficha.minutos(numero(tiempo.duracion_min, idioma))}</span>
            <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.duracion)} />
          </Fila>
        )}
        {(textoCierre !== null ||
          vuelos.some(([v]) => tieneCifra(v)) ||
          consecuencias?.danos !== undefined) && (
          <Fila nombre={t.ficha.efecto}>
            <ul>
              {textoCierre !== null && <li>{textoCierre}</li>}
              {vuelos.map(
                ([valor, unidad]) =>
                  tieneCifra(valor) && (
                    <li key={unidad}>
                      <Cifra t={t} idioma={idioma} valor={valor} unidad={unidad} />
                    </li>
                  ),
              )}
              {consecuencias?.danos !== undefined && (
                <li>
                  {t.ficha.danos[consecuencias.danos.nivel]}
                  {consecuencias.danos.frase !== undefined && (
                    <Cita
                      t={t}
                      idioma={idioma}
                      texto={consecuencias.danos.frase}
                      traduccion={consecuencias.danos.frase_traduccion}
                      como="q"
                      className="block text-xs text-secundario"
                    />
                  )}
                </li>
              )}
            </ul>
            <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.efecto)} />
          </Fila>
        )}
        {medidas.length > 0 && (
          <Fila nombre={t.ficha.respuesta}>
            {medidas.map((medida) => t.medida[medida]).join(" · ")}
            <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.respuesta)} />
          </Fila>
        )}
        {atribucion !== undefined && (
          <Fila nombre={t.ficha.atribucion}>
            {t.ficha.atribuidoA(actor, autoridad)}
            {fuenteAtribucion !== undefined && (
              <Cita
                t={t}
                idioma={idioma}
                texto={fuenteAtribucion.frase_origen}
                idiomaOriginal={fuenteAtribucion.idioma}
                traduccion={fuenteAtribucion.traduccion}
                className="mt-0.5 border-l border-acento pl-2 text-secundario"
                datos={{ "data-cita-atribucion": "" }}
              />
            )}
            <span className="mono block text-xs text-secundario">
              {instante(atribucion.fecha)}
              {fuenteAtribucion !== undefined && (
                <>
                  {" · "}
                  <EnlaceFuente t={t} fuente={fuenteAtribucion}>
                    {t.ficha.verFuente}
                  </EnlaceFuente>
                </>
              )}
            </span>
            <QueDiceCadaFuente t={t} idioma={idioma} idiomas={idiomasFuentes} afirmaciones={de(CAMPOS_DE_FILA.atribucion)} />
          </Fila>
        )}
        {incidente.investigacion !== undefined && incidente.investigacion.length > 0 && (
          <Fila nombre={t.ficha.investigacion}>
            <ul data-investigacion="">
              {incidente.investigacion.map((entrada) => {
                const fuente = porFuente.get(entrada.fuente_id);
                return (
                  <li key={`${entrada.fuente_id}-${entrada.cita}`} className="mb-1.5">
                    {t.ficha.investiga(nombreDeAutoridad(entrada.autoridad, idioma))}
                    <Cita
                      t={t}
                      idioma={idioma}
                      texto={entrada.cita}
                      idiomaOriginal={fuente?.idioma}
                      traduccion={entrada.cita_traduccion}
                      className="mt-0.5 border-l border-acento pl-2 text-secundario"
                    />
                    <span className="mono block text-xs text-secundario">
                      {instante(entrada.fecha)}
                      {fuente !== undefined && (
                        <>
                          {" · "}
                          <EnlaceFuente t={t} fuente={fuente}>
                            {t.ficha.verFuente}
                          </EnlaceFuente>
                        </>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Fila>
        )}
        {incidente.ataque !== undefined && (
          <Fila nombre={t.ficha.parteDelAtaque}>
            {t.ficha.ataqueDeLa(
              jornadaEscrita(t, {
                tipo: incidente.ataque.jornada.tipo,
                desde: diaDeInstante(`${incidente.ataque.jornada.desde}T00:00Z`),
                hasta: diaDeInstante(`${incidente.ataque.jornada.hasta}T00:00Z`),
              }),
            )}
            <span className="block text-xs">
              <Enlace a={rutaDeFicha(incidente.ataque.id, idioma)} className="enlace mono">
                {incidente.ataque.id}
              </Enlace>
              <span className="text-secundario">
                {" · "}
                {incidente.ataque.por === "fuente" ? t.ficha.porFuente : t.ficha.porFecha}
              </span>
            </span>
          </Fila>
        )}
        {(incidente.relacionados ?? []).map((relacionado) => (
          <Fila key={relacionado.id} nombre={t.ficha.sucesoRelacionado}>
            <span data-suceso-relacionado={relacionado.id}>
              <Enlace a={rutaDeFicha(relacionado.id, idioma)} className="enlace mono">
                {relacionado.id}
              </Enlace>
              <span className="block text-xs text-secundario">{relacionado.nota[idioma]}</span>
            </span>
          </Fila>
        ))}
        {incidente.trafico_aereo !== undefined && (
          <LineaTrafico
            t={t}
            idioma={idioma}
            trafico={incidente.trafico_aereo}
            consecuencias={consecuencias}
          />
        )}
        {incidente.foco_termico !== undefined && incidente.lon !== null && (
          <LineaFoco
            t={t}
            idioma={idioma}
            foco={incidente.foco_termico}
            lon={incidente.lon}
            lat={incidente.lat}
            zoom={ZOOM_VISOR_PUNTO}
          />
        )}
        {incidente.control.motivo_desmentido !== undefined && (
          <Fila nombre={t.ficha.motivoDesmentido}>
            {/* Lo que dijo quien lo desmiente, con sus palabras: una cita, como las de las fuentes. */}
            <Cita
              t={t}
              idioma={idioma}
              texto={incidente.control.motivo_desmentido}
              traduccion={incidente.control.motivo_desmentido_traduccion}
              comillas={false}
              className="border-l border-acento pl-2 text-secundario"
              datos={{ "data-motivo-desmentido": "" }}
            />
          </Fila>
        )}
        {incidente.episodio !== undefined && (
          <Fila nombre={t.ficha.episodio}>
            <span className="mono">{incidente.episodio}</span>
          </Fila>
        )}
      </dl>

      <ListaFuentes t={t} fuentes={incidente.fuentes} idioma={idioma} />
      <Historial
        t={t}
        historial={incidente.estado.historial}
        fuentes={incidente.fuentes}
        atribucion={marcador}
        idioma={idioma}
        pasos={historialCompleto(t, idioma, incidente)}
      />
      <p className="mono mt-4 text-xs text-secundario">
        {t.ficha.actualizada}: {fechaHora(incidente.control.ultima_actualizacion.valor)}
      </p>
    </article>
  );
}
