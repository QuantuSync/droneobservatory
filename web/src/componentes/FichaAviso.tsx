import type { Aviso, Directo, EstadoAviso } from "../datos/directo.ts";
import { fechaHora, numero, pais } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Fila } from "./Panel.tsx";

/** Clase de color de cada estado de un aviso: los mismos tonos que los estados de los incidentes. */
export const CLASE_ESTADO_AVISO: Record<EstadoAviso, string> = {
  posible_cierre: "text-notificado",
  cierre_confirmado: "text-confirmado",
  operacion_reanudada: "text-secundario",
};

const ENLACE_FUENTE: Record<Directo["fuente"], string> = {
  adsb_lol: "https://adsb.lol/",
  adsb_fi: "https://adsb.fi/",
};

/** Atribución de la fuente en tiempo real: adsb.lol (ODbL) o adsb.fi, con su enlace. */
export function FuenteDirecto({ t, directo }: { t: Textos; directo: Directo }) {
  const enlace = (texto: string, direccion: string) => (
    <EnlaceExterno enlace={direccion} aviso={t.ficha.enlaceExterno} avisoNoValido={t.ficha.enlaceNoValido}>
      {texto}
    </EnlaceExterno>
  );
  return (
    <p className="mt-3 text-xs text-secundario" data-fuente-directo={directo.fuente}>
      {t.directo.fuente}:{" "}
      {directo.fuente === "adsb_lol" ? (
        <>
          © adsb.lol contributors ({enlace("adsb.lol", ENLACE_FUENTE.adsb_lol)}), ODbL 1.0
        </>
      ) : (
        enlace("adsb.fi", ENLACE_FUENTE.adsb_fi)
      )}
      {" · "}
      {t.directo.actualizado} <span className="mono">{fechaHora(directo.generado)}</span>
    </p>
  );
}

interface Props {
  t: Textos;
  idioma: Idioma;
  aviso: Aviso;
  directo: Directo;
}

/** Ficha de un aviso de la detección en directo: estado, horas, evidencia y confirmación. */
export function FichaAviso({ t, idioma, aviso, directo }: Props) {
  const e = aviso.evidencia;
  const d = t.directo;
  const n = (valor: number) => numero(valor, idioma);
  return (
    <article data-aviso={aviso.id}>
      <h2 className="text-2xl font-semibold tracking-tight">{aviso.nombre}</h2>
      <p className="mono mt-1 text-xs text-secundario">
        {aviso.oaci} · {pais(aviso.pais, idioma)}
      </p>
      <p className={`mt-2 font-medium ${CLASE_ESTADO_AVISO[aviso.estado]}`} data-estado-aviso={aviso.estado}>
        {d.estado[aviso.estado]}
      </p>
      <dl className="mt-3">
        <Fila nombre={d.detectado}>
          <span className="mono">{fechaHora(aviso.detectado)}</span>
        </Fila>
        <Fila nombre={d.inicio}>
          <span className="mono">{fechaHora(aviso.inicio)}</span>
        </Fila>
        {aviso.reanudado !== null && (
          <Fila nombre={d.reanudado}>
            <span className="mono">{fechaHora(aviso.reanudado)}</span>
          </Fila>
        )}
        <Fila nombre={d.evidencia}>
          <ul className="text-sm" data-evidencia="">
            <li>{d.movimientos(n(e.vistos), n(e.esperados))}</li>
            <li>{d.llegadasPerdidas(n(e.llegadas_perdidas))}</li>
            <li>{d.salidasPerdidas(n(e.salidas_perdidas))}</li>
            <li>{d.esperas(n(e.esperas))}</li>
            <li>{d.desvios(n(e.desvios))}</li>
          </ul>
        </Fila>
        {aviso.confirmacion !== null && (
          <Fila nombre={d.confirmacion}>
            <span className="block">{d.confirmacionTipo[aviso.confirmacion.tipo]}</span>
            {aviso.confirmacion.incidente !== null && (
              <Enlace a={rutaDeFicha(aviso.confirmacion.incidente, idioma)} className="enlace mono">
                {aviso.confirmacion.incidente}
              </Enlace>
            )}
            <span className="mono block text-xs text-secundario">
              {fechaHora(aviso.confirmacion.hora)}
            </span>
          </Fila>
        )}
        {aviso.primera_noticia !== null && (
          <Fila nombre={d.primeraNoticia}>
            <span className="mono">{fechaHora(aviso.primera_noticia)}</span>
            {aviso.ventaja_min !== null && (
              <span className="block text-xs text-secundario" data-ventaja="">
                {d.ventaja(aviso.ventaja_min)}
              </span>
            )}
          </Fila>
        )}
      </dl>
      <FuenteDirecto t={t} directo={directo} />
    </article>
  );
}
