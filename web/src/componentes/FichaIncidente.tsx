import type { IncidenteDetalle, PresenciaDron, RangoODesconocido } from "../datos/tipos.ts";
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
  const vuelos: [RangoODesconocido | undefined, string][] = [
    [consecuencias?.vuelos_desviados, t.ficha.vuelosDesviados],
    [consecuencias?.vuelos_cancelados, t.ficha.vuelosCancelados],
    [consecuencias?.vuelos_retrasados, t.ficha.vuelosRetrasados],
    [consecuencias?.heridos, t.ficha.heridos],
    [consecuencias?.fallecidos, t.ficha.fallecidos],
  ];
  const medidas = respuesta?.medidas ?? [];
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
          </Fila>
        )}
        <Fila nombre={t.ficha.fecha}>
          <span className="mono">{instante(tiempo.inicio)}</span>
          {tiempo.fin !== undefined && <span className="mono"> – {instante(tiempo.fin)}</span>}
          <span className="block text-xs text-secundario">
            {t.precision[tiempo.inicio.precision]}
          </span>
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
        </Fila>
        <Fila nombre={t.ficha.drones}>
          <Cifra t={t} idioma={idioma} valor={drones?.numero} />
          {drones?.modelo !== undefined && (
            <span className="block text-xs text-secundario">
              {t.ficha.modelo}: {drones.modelo}
            </span>
          )}
        </Fila>
        {(tiempo.duracion_min !== undefined || tieneCifra(minutosCierre)) && (
          <Fila nombre={t.ficha.duracion}>
            {tiempo.duracion_min !== undefined ? (
              <span className="mono">{t.ficha.minutos(numero(tiempo.duracion_min, idioma))}</span>
            ) : (
              <Cifra t={t} idioma={idioma} valor={minutosCierre} unidad="min" />
            )}
          </Fila>
        )}
        {consecuencias !== undefined && (
          <Fila nombre={t.ficha.efecto}>
            <ul>
              {consecuencias.cierre !== undefined && (
                <li>{t.ficha.cierre[consecuencias.cierre.valor]}</li>
              )}
              {vuelos.map(
                ([valor, unidad]) =>
                  tieneCifra(valor) && (
                    <li key={unidad}>
                      <Cifra t={t} idioma={idioma} valor={valor} unidad={unidad} />
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
          </Fila>
        )}
        {medidas.length > 0 && (
          <Fila nombre={t.ficha.respuesta}>
            {medidas.map((medida) => t.medida[medida]).join(" · ")}
          </Fila>
        )}
        {atribucion !== undefined && (
          <Fila nombre={t.ficha.atribucion}>
            {t.ficha.atribuidoA(atribucion.actor, atribucion.autoridad)}
            <span className="mono block text-xs text-secundario">
              {instante(atribucion.fecha)}
            </span>
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
