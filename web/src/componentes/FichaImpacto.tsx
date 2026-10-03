import type { ImpactoGuerra } from "../datos/tipos.ts";
import { fechaDia, instante, numero, rango, region } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { diaDeInstante } from "../tiempo/dias.ts";
import { LineaFoco, ZOOM_VISOR_PUNTO } from "./FocoTermico.tsx";
import { ImagenesSatelite } from "./GuerraSatelite.tsx";
import { ListaFuentes } from "./Fuentes.tsx";
import { Fila } from "./Panel.tsx";
import { Enlace } from "../navegacion.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  impacto: ImpactoGuerra;
}

/**
 * Ficha de un impacto con lugar de la capa de guerra: el lugar alcanzado, el tipo de objetivo,
 * la fecha, la región y el ataque de esa noche, la puntuación y las fuentes con su enlace, y la
 * marca «reivindicación de parte» cuando solo lo dice una de las partes.
 */
export function FichaImpacto({ t, idioma, impacto }: Props) {
  const { lugar } = impacto;
  const radio = new Intl.NumberFormat(idioma, { maximumFractionDigits: 1 }).format(lugar.radio_km);
  const latino = lugar.nombre_latino !== undefined && lugar.nombre_latino !== lugar.nombre;
  const heridos = rango(impacto.heridos, idioma);
  const fallecidos = rango(impacto.fallecidos, idioma);
  const categorias = impacto.categorias_objetivo ?? [];
  return (
    <article>
      <p className="text-secundario">{t.sentido[impacto.sentido]}</p>
      <h2 className="text-2xl font-semibold tracking-tight">
        <span lang={impacto.region.startsWith("UA-") ? "uk" : "ru"}>{lugar.nombre}</span>
      </h2>
      {latino && <p className="text-secundario">{lugar.nombre_latino}</p>}
      <p className="mono mt-1 text-xs text-secundario">{impacto.id}</p>
      {impacto.reivindicacion_de_parte === true && (
        <p className="mt-3 border-l border-acento pl-2" data-reivindicacion="">
          <span className="font-medium">{t.impacto.reivindicacion}</span>
          <span className="block text-xs text-secundario">{t.impacto.reivindicacionTexto}</span>
        </p>
      )}
      <dl className="mt-3">
        <Fila nombre={t.impacto.lugar}>
          <span>
            {lugar.nivel === "instalacion" && lugar.categoria !== undefined
              ? t.categoriaInstalacion[lugar.categoria]
              : null}
            {lugar.nivel === "instalacion" && lugar.localidad !== undefined
              ? ` ${t.impacto.instalacionEn(lugar.localidad)}`
              : null}
          </span>
          <span className="block text-xs text-secundario">{t.impacto.radio(radio)}</span>
          <span className="block text-xs text-secundario">{t.impacto.tipo[impacto.impacto]}</span>
        </Fila>
        <Fila nombre={t.impacto.objetivo}>
          {categorias.length > 0 ? (
            <span>{categorias.map((c) => t.categoriaGuerra[c]).join(", ")}</span>
          ) : (
            <span className="text-secundario">{t.impacto.sinObjetivo}</span>
          )}
        </Fila>
        <Fila nombre={t.impacto.fecha}>
          {impacto.dia !== undefined && (
            <span className="mono block">
              {fechaDia(diaDeInstante(`${impacto.dia}T00:00Z`))}
              <span className="block text-xs text-secundario">
                {impacto.parte_diario === true ? t.impacto.parteDiario : t.impacto.diaAtaque}
              </span>
            </span>
          )}
          <span className="mono block">{instante(impacto.fecha)}</span>
          <span className="block text-xs text-secundario">{t.impacto.publicado}</span>
        </Fila>
        <Fila nombre={t.impacto.region}>
          <span>{region(impacto.region, idioma)}</span>
          <span className="mono ml-2 text-xs text-secundario">{impacto.region}</span>
        </Fila>
        {impacto.ataque !== undefined && (
          <Fila nombre={t.impacto.ataque}>
            <Enlace a={rutaDeFicha(impacto.ataque, idioma)} className="enlace mono">
              {impacto.ataque}
            </Enlace>
          </Fila>
        )}
        {(heridos !== null || fallecidos !== null) && (
          <Fila nombre={t.impacto.victimas}>
            {heridos !== null && <span className="block">{t.impacto.heridos(heridos)}</span>}
            {fallecidos !== null && (
              <span className="block">{t.impacto.fallecidos(fallecidos)}</span>
            )}
          </Fila>
        )}
        <Fila nombre={t.impacto.credibilidad}>
          <span className="mono">{numero(impacto.credibilidad, idioma)}</span>
          <span className="ml-2">{t.impacto.credibilidadTexto[impacto.credibilidad]}</span>
        </Fila>
        {impacto.foco_termico !== undefined && (
          <LineaFoco
            t={t}
            idioma={idioma}
            foco={impacto.foco_termico}
            lon={lugar.punto.lon}
            lat={lugar.punto.lat}
            zoom={ZOOM_VISOR_PUNTO}
          />
        )}
      </dl>
      <ImagenesSatelite t={t} idioma={idioma} id={impacto.id} />
      <ListaFuentes t={t} fuentes={impacto.fuentes} />
    </article>
  );
}
