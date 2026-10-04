import type { Ataque, RangoODesconocido } from "../datos/tipos.ts";
import { fechaHora, instante, pais, rango, region } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { Historial, ListaFuentes } from "./Fuentes.tsx";
import { LineaFoco, ZOOM_VISOR_REGION } from "./FocoTermico.tsx";
import { lucesDeAtaque } from "../datos/guerraSatelite.ts";
import { ListaLuz } from "./GuerraSatelite.tsx";
import { Fila } from "./Panel.tsx";
import { Enlace } from "../navegacion.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  ataque: Ataque;
  /** Centro [lon, lat] de las regiones con foco térmico, para abrir el visor de FIRMS. */
  centros?: ReadonlyMap<string, [number, number]> | undefined;
}

/** Centro de Ucrania: si no se sabe el de la región, el visor se abre en el país entero. */
const CENTRO_UCRANIA: [number, number] = [31.2, 48.4];
const ZOOM_VISOR_PAIS = 5;

function cifra(valor: RangoODesconocido | undefined, idioma: Idioma): string | null {
  return rango(valor, idioma);
}

function FilaCifra({
  nombre,
  valor,
  idioma,
}: {
  nombre: string;
  valor: RangoODesconocido | undefined;
  idioma: Idioma;
}) {
  const texto = cifra(valor, idioma);
  if (texto === null) return null;
  return (
    <Fila nombre={nombre}>
      <span className="mono">{texto}</span>
    </Fila>
  );
}

function EnlaceAtaque({ id, idioma }: { id: string; idioma: Idioma }) {
  return (
    <Enlace a={rutaDeFicha(id, idioma)} className="enlace mono">
      {id}
    </Enlace>
  );
}

/** Ficha de un ataque de la capa de Ucrania: lo que declara una de las partes en guerra. */
export function FichaAtaque({ t, idioma, ataque, centros }: Props) {
  const regiones = ataque.regiones ?? [];
  const desglose: [string, RangoODesconocido | undefined][] = [
    [t.ataque.shahed, ataque.lanzados?.shahed_geran],
    [t.ataque.senuelos, ataque.lanzados?.gerbera_senuelos],
    [t.ataque.otros, ataque.lanzados?.otros],
  ];
  const zonas = ataque.zonas_lanzamiento ?? [];
  const cruces = ataque.cruces ?? [];
  const soloMisiles = ataque.regiones_misiles ?? [];
  return (
    <article>
      <p className="rotulo">{t.sentido[ataque.sentido]}</p>
      <h2 className="text-xl font-semibold tracking-tight mono mt-1 text-xl">{ataque.id}</h2>
      {ataque.reivindicacion_de_parte === true && (
        <p className="mt-2 border-l border-notificado pl-2 text-secundario">
          {t.ataque.reivindicacion}
        </p>
      )}
      {/* Lo que se ve desde el satélite va lo primero: la luz nocturna que perdió. */}
      {(ataque.perdida_luz ?? []).length > 0 && (
        <dl className="mt-3" data-satelite-arriba="">
          <Fila nombre={t.satelite.luzFicha.rotulo}>
            <ListaLuz t={t} idioma={idioma} luces={lucesDeAtaque(ataque)} />
          </Fila>
        </dl>
      )}

      <dl className="mt-3">
        <Fila nombre={t.ataque.periodo}>
          <span className="mono">
            {instante(ataque.periodo.inicio)} – {instante(ataque.periodo.fin)}
          </span>
        </Fila>
        <FilaCifra nombre={t.ataque.lanzados} valor={ataque.lanzados?.total} idioma={idioma} />
        {desglose.map(([nombre, valor]) => (
          <FilaCifra key={nombre} nombre={nombre} valor={valor} idioma={idioma} />
        ))}
        <FilaCifra
          nombre={
            ataque.derribados_categoria === "derribados_o_neutralizados"
              ? t.ataque.derribadosONeutralizados
              : t.ataque.derribados
          }
          valor={ataque.derribados}
          idioma={idioma}
        />
        <FilaCifra
          nombre={t.ataque.guerraElectronica}
          valor={ataque.perdidos_guerra_electronica}
          idioma={idioma}
        />
        <FilaCifra
          nombre={t.ataque.localizacionesImpacto}
          valor={ataque.localizaciones_impacto}
          idioma={idioma}
        />
        <FilaCifra
          nombre={t.ataque.localizacionesRestos}
          valor={ataque.localizaciones_restos}
          idioma={idioma}
        />
        {zonas.length > 0 && <Fila nombre={t.ataque.zonasLanzamiento}>{zonas.join(" · ")}</Fila>}
        {regiones.length > 0 && (
          <Fila nombre={t.ataque.regiones}>
            <ul>
              {regiones.map((r) => {
                const derribados = cifra(r.derribados, idioma);
                return (
                  <li key={r.region}>
                    {region(r.region, idioma)}
                    {derribados !== null && (
                      <span className="mono text-xs text-secundario"> · {derribados}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </Fila>
        )}
        {regiones.map((r) => {
          if (r.foco_termico === undefined) return null;
          const centro = centros?.get(r.region);
          return (
            <LineaFoco
              key={r.region}
              t={t}
              idioma={idioma}
              foco={r.foco_termico}
              lon={(centro ?? CENTRO_UCRANIA)[0]}
              lat={(centro ?? CENTRO_UCRANIA)[1]}
              zoom={centro === undefined ? ZOOM_VISOR_PAIS : ZOOM_VISOR_REGION}
              ataque={region(r.region, idioma)}
            />
          );
        })}
        {soloMisiles.length > 0 && (
          <Fila nombre={t.ataque.regionesMisiles}>
            {soloMisiles.map((codigo) => region(codigo, idioma)).join(" · ")}
          </Fila>
        )}
        {cruces.length > 0 && (
          <Fila nombre={t.ataque.cruces}>
            <ul>
              {cruces.map((cruce) => (
                <li key={cruce.pais}>
                  {pais(cruce.pais, idioma)}
                  <span className="mono text-xs text-secundario">
                    {" "}
                    · {cifra(cruce.numero, idioma) ?? t.ficha.desconocido}
                  </span>
                </li>
              ))}
            </ul>
          </Fila>
        )}
        {ataque.incluido_en !== undefined && (
          <Fila nombre={t.ataque.incluidoEn}>
            <EnlaceAtaque id={ataque.incluido_en} idioma={idioma} />
          </Fila>
        )}
        {ataque.solapado_con !== undefined && (
          <Fila nombre={t.ataque.solapadoCon}>
            <EnlaceAtaque id={ataque.solapado_con} idioma={idioma} />
          </Fila>
        )}
        {ataque.control.motivo_desmentido !== undefined && (
          <Fila nombre={t.ficha.motivoDesmentido}>{ataque.control.motivo_desmentido}</Fila>
        )}
      </dl>

      <ListaFuentes t={t} fuentes={ataque.fuentes} />
      <Historial
        t={t}
        historial={ataque.estado.historial}
        fuentes={ataque.fuentes}
      />
      <p className="mono mt-4 text-xs text-secundario">
        {t.ficha.actualizada}: {fechaHora(ataque.control.ultima_actualizacion.valor)}
      </p>
    </article>
  );
}
