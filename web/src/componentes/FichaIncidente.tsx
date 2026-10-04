import { afirmacionesDe, rangoDeFuentes, valorLegible } from "../datos/afirmaciones.ts";
import { ACTOR_SIN_NOMBRE, atribucionResumida } from "../datos/derivar.ts";
import { cierre as leerCierre } from "../datos/efecto.ts";
import type {
  AfirmacionPublica,
  Atribucion,
  IncidenteDetalle,
  PresenciaDron,
  RangoODesconocido,
} from "../datos/tipos.ts";
import {
  esRangoAbierto,
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
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { EstadoConTexto, Historial, ListaFuentes, nombreDeAutoridad } from "./Fuentes.tsx";
import { LineaFoco, ZOOM_VISOR_PUNTO } from "./FocoTermico.tsx";
import { LineaTrafico } from "./TraficoAereo.tsx";
import { Fila } from "./Panel.tsx";
import { Simbolo } from "./Simbolo.tsx";

/** Marca que acompaña al texto de la presencia de dron, para no depender del color. */
const MARCA_PRESENCIA: Record<PresenciaDron, string> = {
  confirmada: "✓",
  no_confirmada: "?",
  descartada: "✕",
};

interface Props {
  t: Textos;
  idioma: Idioma;
  incidente: IncidenteDetalle;
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

function ValorDeFuente({ t, idioma, valor }: { t: Textos; idioma: Idioma; valor: unknown }) {
  const legible = valorLegible(valor);
  switch (legible.clase) {
    case "desconocido":
      return <span className="text-secundario">{t.ficha.desconocido}</span>;
    case "rango":
      return <span className="mono">{rango(legible.rango, idioma)}</span>;
    case "instante":
      return <span className="mono">{fechaHora(legible.valor)}</span>;
    case "texto":
      return <span>{legible.texto}</span>;
  }
}

/** Desplegable con lo que dice cada fuente sobre los campos de una fila. */
function QueDiceCadaFuente({
  t,
  idioma,
  afirmaciones,
}: {
  t: Textos;
  idioma: Idioma;
  afirmaciones: readonly AfirmacionPublica[];
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
              <ValorDeFuente t={t} idioma={idioma} valor={afirmacion.valor} />{" "}
              <span className="text-secundario">{t.ficha.valorSegun}</span> {afirmacion.medio}{" "}
              <span className="mono rounded-sm border border-linea px-1 text-acento">
                <span className="sr-only">{t.ficha.codigo(codigo)}</span>
                <span aria-hidden="true">{codigo}</span>
              </span>{" "}
              <span className="mono text-secundario">{instante(afirmacion.fecha)}</span>
              {afirmacion.cita && <q className="block text-secundario">{afirmacion.cita}</q>}
            </li>
          );
        })}
      </ul>
    </details>
  );
}

function Cifra({
  t,
  idioma,
  valor: publicado,
  unidad,
  afirmaciones = [],
}: {
  t: Textos;
  idioma: Idioma;
  valor: RangoODesconocido | undefined;
  unidad?: string;
  /** Lo que dice cada fuente sobre este campo: si lo hay, el rango sale de las A–C. */
  afirmaciones?: readonly AfirmacionPublica[];
}) {
  const valor = rangoDeFuentes(afirmaciones, publicado);
  const texto = rango(valor, idioma);
  if (texto === null) return <span className="text-secundario">{t.ficha.desconocido}</span>;
  return (
    <>
      <span className="mono">{texto}</span>
      {unidad !== undefined && ` ${unidad}`}
      {esRangoAbierto(valor) && (
        <span className="text-xs text-secundario"> ({t.ficha.rangoDeFuentes})</span>
      )}
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

export function FichaIncidente({ t, idioma, incidente }: Props) {
  const { tiempo, lugar, objetivo, drones, consecuencias, respuesta, atribucion } = incidente;
  // El marcador de un atribuido: su bandera y, si es una persona, el punto.
  const marcador = atribucionResumida(incidente);
  // A quién y según quién, escrito en el idioma de la web: el país a partir de su código, la
  // persona sin nombre como «una persona» y la autoridad traducida.
  const actor = atribucion === undefined ? "" : actorEscrito(t, idioma, atribucion);
  const autoridad = atribucion === undefined ? "" : nombreDeAutoridad(atribucion.autoridad, idioma);
  const porFuente = new Map(incidente.fuentes.map((f) => [f.id, f]));
  const titulo = incidente.titulo[idioma];
  const nombre = objetivo?.nombre ?? titulo;
  const vuelos: [RangoODesconocido | undefined, string, string][] = [
    [consecuencias?.vuelos_desviados, t.ficha.vuelosDesviados, "consecuencias.vuelos_desviados"],
    [consecuencias?.vuelos_cancelados, t.ficha.vuelosCancelados, "consecuencias.vuelos_cancelados"],
    [consecuencias?.vuelos_retrasados, t.ficha.vuelosRetrasados, "consecuencias.vuelos_retrasados"],
    [consecuencias?.heridos, t.ficha.heridos, "consecuencias.heridos"],
    [consecuencias?.fallecidos, t.ficha.fallecidos, "consecuencias.fallecidos"],
  ];
  const medidas = respuesta?.medidas ?? [];
  const de = (campos: readonly string[]) => afirmacionesDe(incidente, campos);
  // «desconocido» en el cierre quiere decir que ninguna fuente habla de cierre: solo se dice
  // en las interrupciones aeroportuarias, donde el cierre es lo que se espera saber.
  const cierre = leerCierre(incidente.tipo, consecuencias);
  const rangoCierre =
    cierre?.clase === "con_duracion"
      ? rango(rangoDeFuentes(de(["consecuencias.cierre.minutos"]), cierre.minutos), idioma)
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
  return (
    <article>
      <p className="rotulo flex items-center gap-2">
        <Simbolo estado={incidente.estado.actual} atribucion={marcador} />
        {t.tipo[incidente.tipo]}
      </p>
      <h2 className="text-xl font-semibold tracking-tight mt-1 text-2xl">{nombre}</h2>
      {nombre !== titulo && <p className="mt-2 text-texto">{titulo}</p>}
      <p className="mono mt-1 text-xs text-secundario">{incidente.id}</p>

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
            <span aria-hidden="true" className="mono mr-1.5 text-acento">
              {MARCA_PRESENCIA[incidente.presencia_dron]}
            </span>
            {t.presencia[incidente.presencia_dron]}
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.presencia)} />
          </Fila>
        )}
        <Fila nombre={t.ficha.fecha}>
          <span className="mono">{instante(tiempo.inicio)}</span>
          {tiempo.fin !== undefined && <span className="mono"> – {instante(tiempo.fin)}</span>}
          <span className="block text-xs text-secundario">
            {t.precision[tiempo.inicio.precision]}
          </span>
          <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.fecha)} />
        </Fila>
        <Fila nombre={t.ficha.lugar}>
          {lugar.localidad !== undefined && `${lugar.localidad}, `}
          {imprecisa?.region !== undefined && imprecisa.region !== undefined && `${imprecisa.region}, `}
          {pais(lugar.pais, idioma)}
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
              <span className="block text-xs text-notificado">
                {t.imprecisa.etiqueta} · {t.imprecisa.nivel[imprecisa.nivel]}
              </span>
            )
          )}
          <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.lugar)} />
        </Fila>
        <Fila nombre={t.ficha.drones}>
          <Cifra
            t={t}
            idioma={idioma}
            valor={drones?.numero}
            afirmaciones={de(["drones.numero"])}
          />
          {drones?.modelo !== undefined && (
            <span className="block text-xs text-secundario">
              {t.ficha.modelo}: {drones.modelo}
            </span>
          )}
          <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.drones)} />
        </Fila>
        {tiempo.duracion_min !== undefined && (
          <Fila nombre={t.ficha.duracion}>
            <span className="mono">{t.ficha.minutos(numero(tiempo.duracion_min, idioma))}</span>
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.duracion)} />
          </Fila>
        )}
        {(textoCierre !== null ||
          vuelos.some(([v]) => tieneCifra(v)) ||
          consecuencias?.danos !== undefined) && (
          <Fila nombre={t.ficha.efecto}>
            <ul>
              {textoCierre !== null && <li>{textoCierre}</li>}
              {vuelos.map(
                ([valor, unidad, campo]) =>
                  tieneCifra(valor) && (
                    <li key={unidad}>
                      <Cifra
                        t={t}
                        idioma={idioma}
                        valor={valor}
                        unidad={unidad}
                        afirmaciones={de([campo])}
                      />
                    </li>
                  ),
              )}
              {consecuencias?.danos !== undefined && (
                <li>
                  {t.ficha.danos[consecuencias.danos.nivel]}
                  {consecuencias.danos.frase !== undefined && (
                    <span className="block text-xs text-secundario">
                      {consecuencias.danos.frase}
                    </span>
                  )}
                </li>
              )}
            </ul>
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.efecto)} />
          </Fila>
        )}
        {medidas.length > 0 && (
          <Fila nombre={t.ficha.respuesta}>
            {medidas.map((medida) => t.medida[medida]).join(" · ")}
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.respuesta)} />
          </Fila>
        )}
        {atribucion !== undefined && (
          <Fila nombre={t.ficha.atribucion}>
            {t.ficha.atribuidoA(actor, autoridad)}
            <span className="mono block text-xs text-secundario">
              {instante(atribucion.fecha)}
            </span>
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.atribucion)} />
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
                    <blockquote lang={fuente?.idioma} className="mt-0.5 border-l border-acento pl-2 text-secundario">
                      «{entrada.cita}»
                    </blockquote>
                    <span className="mono block text-xs text-secundario">
                      {instante(entrada.fecha)}
                      {fuente !== undefined && (
                        <>
                          {" · "}
                          <EnlaceExterno
                            enlace={fuente.enlace}
                            aviso={t.ficha.enlaceExterno}
                            avisoNoValido={t.ficha.enlaceNoValido}
                          >
                            {t.ficha.verFuente}
                          </EnlaceExterno>
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
          <Fila nombre={t.ficha.motivoDesmentido}>{incidente.control.motivo_desmentido}</Fila>
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
      />
      <p className="mono mt-4 text-xs text-secundario">
        {t.ficha.actualizada}: {fechaHora(incidente.control.ultima_actualizacion.valor)}
      </p>
    </article>
  );
}
