import type { NocheRutas, RecorridoRuta } from "../datos/rutas.ts";
import type { Textos } from "../i18n/index.ts";
import { jornadaEscrita, numero } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { diaDeInstante } from "../tiempo/dias.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Fila } from "./Panel.tsx";


function hora(t: string | undefined): string {
  return t === undefined ? "" : `${t.slice(11, 16)} UTC`;
}

/** El enlace visible a NEPTUN, junto a todo lo que sale de sus datos. */
export function EnlaceNeptun({ t, texto, enlace }: { t: Textos; texto: string; enlace: string }) {
  return (
    <EnlaceExterno
      enlace={enlace}
      aviso={t.ficha.enlaceExterno}
      avisoNoValido={t.ficha.enlaceNoValido}
      className="text-acento underline underline-offset-2"
    >
      <span data-enlace-neptun="">{texto}</span>
    </EnlaceExterno>
  );
}

function nocheEscrita(t: Textos, noche: string, mayuscula: boolean): string {
  const dia = diaDeInstante(noche);
  return jornadaEscrita(t, { tipo: "noche", desde: dia, hasta: dia + 1 }, mayuscula);
}

/** Ficha del recorrido de un grupo: noche, aparatos, tipo y velocidad si constan, horas, fuente y
 * precisión. */
export function FichaRuta({
  t,
  idioma,
  noche,
  recorrido,
}: {
  t: Textos;
  idioma: Idioma;
  noche: NocheRutas;
  recorrido: RecorridoRuta;
}) {
  const r = t.rutas;
  const km = (x: number) => numero(Math.round(x), idioma);
  const precision =
    Math.round(recorrido.precision_km.min) === Math.round(recorrido.precision_km.max)
      ? r.precisionKm(km(recorrido.precision_km.max))
      : r.precisionEntre(km(recorrido.precision_km.min), km(recorrido.precision_km.max));
  return (
    <article data-ficha-ruta="">
      <p className="text-secundario">{r.fuente[noche.fuente]}</p>
      <h2 className="text-2xl font-semibold tracking-tight">{nocheEscrita(t, noche.noche, true)}</h2>
      <dl className="mt-3">
        <Fila nombre={r.grupo}>
          <span>{r.grupoNumero(recorrido.grupo)}</span>
          {recorrido.division && <span className="block text-xs text-secundario">{r.division}</span>}
          {recorrido.union && <span className="block text-xs text-secundario">{r.union}</span>}
          <span className="block text-xs text-secundario">{r.sinIdentidad}</span>
        </Fila>
        {recorrido.aparatos !== null && (
          <Fila nombre={r.aparatos}>
            <span className="mono">{numero(recorrido.aparatos, idioma)}</span>
          </Fila>
        )}
        <Fila nombre={r.tipo}>
          <span>{r.tipos[recorrido.tipo]}</span>
        </Fila>
        {recorrido.kmh !== null && (
          <Fila nombre={r.velocidad}>
            <span className="mono">{r.kmh(Math.round(recorrido.kmh))}</span>
          </Fila>
        )}
        <Fila nombre={r.recorridoGrupo}>
          <span className="mono">{r.longitud(km(recorrido.longitud_km))}</span>
          {recorrido.inicio !== null && recorrido.fin !== null && (
            <span className="mono block text-xs text-secundario">
              {hora(recorrido.inicio)} → {hora(recorrido.fin)}
            </span>
          )}
        </Fila>
        <Fila nombre={r.precision}>
          <span className="mono">{precision}</span>
          <span className="block text-xs text-secundario">{r.nota}</span>
        </Fila>
        <Fila nombre={r.origen}>
          <span>{r.fuente[noche.fuente]}</span>
          {noche.atribucion !== undefined && (
            <span className="block text-xs">
              <EnlaceNeptun t={t} texto={noche.atribucion.texto} enlace={noche.atribucion.enlace} />
            </span>
          )}
          {(recorrido.pistas ?? []).length > 0 && (
            <span className="mono block text-xs text-secundario">
              {r.pista}: {(recorrido.pistas ?? []).join(", ")}
            </span>
          )}
        </Fila>
        {noche.ataques.length > 0 && (
          <Fila nombre={r.ataque}>
            {noche.ataques.map((id) => (
              <Enlace key={id} a={rutaDeFicha(id, idioma)} className="mono block text-acento underline underline-offset-2">
                {id}
              </Enlace>
            ))}
          </Fila>
        )}
        {(noche.incidentes ?? []).length > 0 && (
          <Fila nombre={r.incidentes}>
            {(noche.incidentes ?? []).map((id) => (
              <Enlace key={id} a={rutaDeFicha(id, idioma)} className="mono block text-acento underline underline-offset-2">
                {id}
              </Enlace>
            ))}
          </Fila>
        )}
      </dl>
    </article>
  );
}

/** Leyenda de la subcapa: qué noche se ve, cuántos grupos de cuántos, cómo se lee y de dónde
 * sale. Cabe entera en la pantalla del teléfono: el texto se parte en líneas, nunca se sale. */
export function LeyendaRutas({
  t,
  noche,
  mostrados,
  total,
  conNeptun,
  atribucion,
  cargando,
}: {
  t: Textos;
  noche: string | null;
  mostrados: number;
  total: number;
  conNeptun: boolean;
  atribucion: { texto: string; enlace: string } | null;
  cargando: boolean;
}) {
  const r = t.rutas;
  return (
    <details
      open
      className="flotante w-80 max-w-full px-2.5 py-1.5 text-xs"
      data-leyenda="rutas"
    >
      <summary className="cursor-pointer font-medium text-texto">
        {noche === null ? r.subcapa : `${r.subcapa} · ${nocheEscrita(t, noche, false)}`}
      </summary>
      <p className="text-secundario" data-rutas-visibles={mostrados} data-rutas-total={total}>
        {cargando ? r.cargando : noche === null || total === 0 ? r.sinRutas : r.leyenda(mostrados, total)}
      </p>
      <p className="flex items-center gap-1.5 text-secundario">
        <span aria-hidden="true" className="leyenda-ruta" />
        {r.comoSeLee}
      </p>
      <p className="text-secundario">{r.otraNoche}</p>
      {conNeptun && atribucion !== null && (
        <p className="break-words">
          <EnlaceNeptun t={t} texto={atribucion.texto} enlace={atribucion.enlace} />
        </p>
      )}
    </details>
  );
}
