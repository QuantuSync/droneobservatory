import type { NocheRutas, TramoRuta } from "../datos/rutas.ts";
import type { Textos } from "../i18n/index.ts";
import { jornadaEscrita, numero } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { diaDeInstante } from "../tiempo/dias.ts";
import { EnlaceExterno } from "./EnlaceExterno.tsx";
import { Fila } from "./Panel.tsx";

const CANAL_FUERZA_AEREA = "https://t.me/kpszsu/";
const MENSAJES_VISIBLES = 6;

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

/** Ficha de un tramo de ruta: noche, grupo, aparatos, tipo, velocidad, fuente y precisión. */
export function FichaRuta({
  t,
  idioma,
  noche,
  tramo,
}: {
  t: Textos;
  idioma: Idioma;
  noche: NocheRutas;
  tramo: TramoRuta;
}) {
  const r = t.rutas;
  const grupo = noche.grupos.find((g) => g.grupo === tramo.grupo);
  const maximo = grupo?.aparatos_max ?? null;
  const aparatos = tramo.numero ?? (maximo === null ? null : { min: maximo, max: maximo });
  const velocidad = tramo.kmh ?? grupo?.kmh_mediana ?? null;
  const mensajes = tramo.mensajes ?? [];
  return (
    <article data-ficha-ruta="">
      <p className="text-secundario">{r.fuente[noche.fuente]}</p>
      <h2 className="text-2xl font-semibold tracking-tight">
        {jornadaEscrita(
          t,
          { tipo: "noche", desde: diaDeInstante(noche.noche), hasta: diaDeInstante(noche.noche) + 1 },
          true,
        )}
      </h2>
      <dl className="mt-3">
        <Fila nombre={r.grupo}>
          <span>{r.grupoNumero(tramo.grupo)}</span>
          {tramo.division === true && <span className="block text-xs text-secundario">{r.division}</span>}
          {tramo.union === true && <span className="block text-xs text-secundario">{r.union}</span>}
          {noche.fuente === "fuerza_aerea" && (
            <span className="block text-xs text-secundario">{r.sinIdentidad}</span>
          )}
        </Fila>
        {aparatos !== null && (
          <Fila nombre={r.aparatos}>
            <span className="mono">
              {aparatos.min === aparatos.max
                ? numero(aparatos.max, idioma)
                : `${numero(aparatos.min, idioma)}–${numero(aparatos.max, idioma)}`}
            </span>
          </Fila>
        )}
        <Fila nombre={r.tipo}>
          <span>{r.tipos[tramo.tipo]}</span>
        </Fila>
        {velocidad !== null && (
          <Fila nombre={r.velocidad}>
            <span className="mono">{r.kmh(Math.round(velocidad))}</span>
          </Fila>
        )}
        <Fila nombre={r.tramo}>
          <span>{r.clases[tramo.clase]}</span>
          <span className="mono block text-xs text-secundario">
            {[hora(tramo.desde.t), hora(tramo.hasta.t)].filter((x) => x !== "").join(" → ")}
          </span>
          {tramo.desde.zona !== undefined && (
            <span className="block text-xs text-secundario">{tramo.desde.zona}</span>
          )}
        </Fila>
        <Fila nombre={r.precision}>
          <span className="mono">{r.precisionKm(numero(Math.round(tramo.precision_km), idioma))}</span>
          <span className="block text-xs text-secundario">{r.nota}</span>
        </Fila>
        <Fila nombre={r.origen}>
          <span>{r.fuente[noche.fuente]}</span>
          {noche.atribucion !== undefined && (
            <span className="block text-xs">
              <EnlaceNeptun t={t} texto={noche.atribucion.texto} enlace={noche.atribucion.enlace} />
            </span>
          )}
          {tramo.pista !== undefined && (
            <span className="mono block text-xs text-secundario">
              {r.pista}: {tramo.pista}
            </span>
          )}
          {mensajes.length > 0 && (
            <span className="block text-xs text-secundario">
              {r.mensajes}:{" "}
              {mensajes.slice(0, MENSAJES_VISIBLES).map((id, i) => (
                <span key={id}>
                  {i > 0 && ", "}
                  <EnlaceExterno
                    enlace={`${CANAL_FUERZA_AEREA}${id}`}
                    aviso={t.ficha.enlaceExterno}
                    avisoNoValido={t.ficha.enlaceNoValido}
                    className="mono text-acento underline underline-offset-2"
                  >
                    {id}
                  </EnlaceExterno>
                </span>
              ))}
              {mensajes.length > MENSAJES_VISIBLES && ` (+${mensajes.length - MENSAJES_VISIBLES})`}
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

/** Leyenda de la subcapa: cuántas noches se dibujan de cuántas, qué es y de dónde sale. */
export function LeyendaRutas({
  t,
  mostradas,
  total,
  conNeptun,
  atribucion,
  noche,
  cargando,
}: {
  t: Textos;
  mostradas: number;
  total: number;
  conNeptun: boolean;
  atribucion: { texto: string; enlace: string } | null;
  noche: boolean;
  cargando: boolean;
}) {
  const r = t.rutas;
  return (
    <details open className="flotante w-max max-w-[min(20rem,calc(100vw-2rem))] px-2.5 py-1.5 text-xs" data-leyenda="rutas">
      <summary className="cursor-pointer font-medium text-texto">{r.subcapa}</summary>
      <p className="text-secundario" data-rutas-visibles={mostradas} data-rutas-total={total}>
        {cargando ? r.cargando : noche ? r.leyendaNoche : total === 0 ? r.sinRutas : r.leyenda(mostradas, total)}
      </p>
      <p className="text-secundario">{r.nota}</p>
      {conNeptun && atribucion !== null && (
        <p>
          <EnlaceNeptun t={t} texto={atribucion.texto} enlace={atribucion.enlace} />
        </p>
      )}
    </details>
  );
}
