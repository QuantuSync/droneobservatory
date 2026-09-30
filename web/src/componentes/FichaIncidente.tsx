import { afirmacionesDe, rangoDeFuentes, valorLegible } from "../datos/afirmaciones.ts";
import type {
  AfirmacionPublica,
  IncidenteDetalle,
  PresenciaDron,
  RangoODesconocido,
} from "../datos/tipos.ts";
import { esRangoAbierto, fechaHora, instante, numero, pais, rango } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { EstadoConTexto, Historial, ListaFuentes } from "./Fuentes.tsx";
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
  duracion: ["tiempo.duracion_min", "consecuencias.cierre.minutos"],
  efecto: [
    "consecuencias.cierre.valor",
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
      <summary className="cursor-pointer text-dorado">
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
              <span className="mono rounded-sm border border-borde px-1 text-dorado">
                <span className="sr-only">{t.ficha.codigo(codigo)}</span>
                <span aria-hidden="true">{codigo}</span>
              </span>{" "}
              <span className="mono text-secundario">{instante(afirmacion.fecha)}</span>
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

function tieneCifra(valor: RangoODesconocido | undefined): boolean {
  return valor !== undefined && valor !== "desconocido";
}

export function FichaIncidente({ t, idioma, incidente }: Props) {
  const { tiempo, lugar, objetivo, drones, consecuencias, respuesta, atribucion } = incidente;
  const titulo = incidente.titulo[idioma];
  const nombre = objetivo?.nombre ?? titulo;
  const minutosCierre = consecuencias?.cierre?.minutos;
  const vuelos: [RangoODesconocido | undefined, string, string][] = [
    [consecuencias?.vuelos_desviados, t.ficha.vuelosDesviados, "consecuencias.vuelos_desviados"],
    [consecuencias?.vuelos_cancelados, t.ficha.vuelosCancelados, "consecuencias.vuelos_cancelados"],
    [consecuencias?.vuelos_retrasados, t.ficha.vuelosRetrasados, "consecuencias.vuelos_retrasados"],
    [consecuencias?.heridos, t.ficha.heridos, "consecuencias.heridos"],
    [consecuencias?.fallecidos, t.ficha.fallecidos, "consecuencias.fallecidos"],
  ];
  const medidas = respuesta?.medidas ?? [];
  const de = (campos: readonly string[]) => afirmacionesDe(incidente, campos);
  const cierre = consecuencias?.cierre;
  // «desconocido» en el cierre quiere decir que ninguna fuente habla de cierre: no se rotula.
  const cierreConocido = cierre !== undefined && cierre.valor !== "desconocido";
  return (
    <article>
      <p className="etiqueta flex items-center gap-2">
        <Simbolo tipo={incidente.tipo} estado={incidente.estado.actual} />
        {t.tipo[incidente.tipo]}
      </p>
      <h2 className="titular mt-1 text-2xl">{nombre}</h2>
      {nombre !== titulo && <p className="mt-2 text-texto">{titulo}</p>}
      <p className="mono mt-1 text-xs text-secundario">{incidente.id}</p>

      <dl className="mt-3">
        <Fila nombre={t.ficha.estado}>
          <EstadoConTexto t={t} tipo={incidente.tipo} estado={incidente.estado.actual} />
        </Fila>
        {incidente.presencia_dron !== undefined && (
          <Fila nombre={t.ficha.presenciaDron}>
            <span aria-hidden="true" className="mono mr-1.5 text-dorado">
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
          {pais(lugar.pais, idioma)}
          {objetivo !== undefined && (
            <span className="block text-xs text-secundario">
              {t.categoria[objetivo.categoria]}
              {objetivo.oaci !== undefined && <span className="mono"> · {objetivo.oaci}</span>}
            </span>
          )}
          <span className="block text-xs text-secundario">
            {t.ficha.radio(numero(lugar.radio_km, idioma))}
          </span>
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
        {(tiempo.duracion_min !== undefined || tieneCifra(minutosCierre)) && (
          <Fila nombre={t.ficha.duracion}>
            {tiempo.duracion_min !== undefined ? (
              <span className="mono">{t.ficha.minutos(numero(tiempo.duracion_min, idioma))}</span>
            ) : (
              <Cifra
                t={t}
                idioma={idioma}
                valor={minutosCierre}
                unidad="min"
                afirmaciones={de(["consecuencias.cierre.minutos"])}
              />
            )}
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.duracion)} />
          </Fila>
        )}
        {consecuencias !== undefined && (cierreConocido || vuelos.some(([v]) => tieneCifra(v)) || consecuencias.danos !== undefined) && (
          <Fila nombre={t.ficha.efecto}>
            <ul>
              {cierreConocido && <li>{t.ficha.cierre[cierre.valor]}</li>}
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
              {consecuencias.danos !== undefined && (
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
            {t.ficha.atribuidoA(atribucion.actor, atribucion.autoridad)}
            <span className="mono block text-xs text-secundario">
              {instante(atribucion.fecha)}
            </span>
            <QueDiceCadaFuente t={t} idioma={idioma} afirmaciones={de(CAMPOS_DE_FILA.atribucion)} />
          </Fila>
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

      <ListaFuentes t={t} fuentes={incidente.fuentes} />
      <Historial
        t={t}
        historial={incidente.estado.historial}
        fuentes={incidente.fuentes}
        tipo={incidente.tipo}
      />
      <p className="mono mt-4 text-xs text-secundario">
        {t.ficha.actualizada}: {fechaHora(incidente.control.ultima_actualizacion.valor)}
      </p>
    </article>
  );
}
