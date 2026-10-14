import type { IncidenteDetalle, RazonTipoDron } from "../datos/tipos.ts";
import type { Textos } from "../i18n/index.ts";
import type { Idioma } from "../sitio.ts";
import { Cita, traduccionParaMostrar } from "./Cita.tsx";
import { fuenteEnFrase } from "./Fuentes.tsx";
import { Fila } from "./Panel.tsx";

interface Props {
  t: Textos;
  idioma: Idioma;
  incidente: IncidenteDetalle;
}

/** El original de la cita de una razón cuando se enseña traducida. */
function OriginalDeRazon({ t, idioma, razon }: { t: Textos; idioma: Idioma; razon: RazonTipoDron }) {
  const datos = razon.datos;
  if (!datos?.cita || traduccionParaMostrar(idioma, datos.cita, undefined, datos.cita_traduccion) === null) {
    return null;
  }
  return (
    <details className="text-xs">
      <summary className="cursor-pointer text-acento tel:flex tel:min-h-11 tel:items-center">
        {t.ficha.verOriginal}
      </summary>
      <span className="block pl-2">«{datos.cita}»</span>
    </details>
  );
}

/**
 * Fila «Tipo de dron» de la ficha. Si la autoridad identificó el dron, eso y su fuente. Si no, lo
 * deducido, separado a la vista de lo que dice una autoridad: cuando ningún grupo destaca, una
 * sola frase («compatible con un dron de largo alcance de la guerra») con sus razones debajo;
 * cuando uno destaca y eso está comprobado, los grupos con su probabilidad y, al desplegar, por
 * qué. Sin base o sin ninguna razón, la fila no aparece.
 */
export function FilaTipoDron({ t, idioma, incidente }: Props) {
  const tipo = incidente.tipo_dron;
  if (tipo === undefined) return null;
  const textos = t.tipoDron;
  const identificado = tipo.identificado;
  if (identificado !== undefined) {
    const fuente = incidente.fuentes.find((f) => f.id === identificado.fuente);
    return (
      <Fila nombre={textos.fila}>
        <span data-tipo-dron="autoridad">{textos.identificado(identificado.modelo)}</span>
        <span className="block text-xs text-secundario">
          {textos.grupoDe(textos.grupos[identificado.grupo])}
        </span>
        <Cita
          t={t}
          idioma={idioma}
          texto={identificado.cita}
          idiomaOriginal={fuente?.idioma}
          traduccion={identificado.cita_traduccion}
          como="q"
          className="block text-xs text-secundario"
        />
        {fuente !== undefined && (
          <span className="block text-xs text-secundario">
            {t.ficha.valorSegun} {fuenteEnFrase(t, fuente.medio, idioma)}
          </span>
        )}
      </Fila>
    );
  }
  const publicado = tipo.publicado;
  const razones = tipo.razones ?? [];
  // Sin ninguna razón que enseñar no hay fila.
  if (publicado === undefined || razones.length === 0) return null;
  if (publicado.presentacion === "compatible_guerra") {
    return (
      <Fila nombre={textos.fila}>
        <span data-tipo-dron="guerra">{textos.compatibleGuerra}</span>
        <ul className="text-xs text-secundario">
          {razones.map((razon, i) => (
            <li key={i} className="py-0.5" data-razon={razon.clave}>
              {textos.razon(razon)}
              <OriginalDeRazon t={t} idioma={idioma} razon={razon} />
            </li>
          ))}
        </ul>
        <span className="block text-xs text-secundario">{textos.deducido}</span>
      </Fila>
    );
  }
  const otras = Math.round((publicado.otras ?? 0) * 100);
  const zona = incidente.zona?.grupo;
  return (
    <Fila nombre={textos.fila}>
      <span className="block text-xs text-secundario" data-tipo-dron="deducido">
        {textos.compatibleCon}
      </span>
      <ul>
        {publicado.compatible.map((c) => (
          <li key={c.grupo}>
            {textos.grupos[c.grupo]}{" "}
            <span className="mono text-secundario">
              {textos.probabilidad(Math.round((c.probabilidad ?? 0) * 100))}
            </span>
          </li>
        ))}
      </ul>
      {otras > 0 && <span className="mono block text-xs text-secundario">{textos.otras(otras)}</span>}
      <span className="block text-xs text-secundario">{textos.deducido}</span>
      <details className="mt-1 text-xs">
        <summary className="cursor-pointer text-acento tel:flex tel:min-h-11 tel:items-center">
          {textos.porQue}
        </summary>
        <ul className="mt-1">
          {publicado.casos_referencia !== undefined && zona !== undefined && (
            <li className="border-t border-linea py-1">
              {textos.base(publicado.casos_referencia, textos.zonas[zona])}
            </li>
          )}
          {razones.map((razon, i) => (
            <li key={i} className="border-t border-linea py-1" data-razon={razon.clave}>
              {textos.razon(razon)}
              <OriginalDeRazon t={t} idioma={idioma} razon={razon} />
            </li>
          ))}
        </ul>
      </details>
    </Fila>
  );
}

/** Fila «Recorrido según la autoridad»: los lugares en orden, con su hora si la da, y la frase. El
 * recorrido se dibuja en el mapa mientras la ficha está abierta. */
export function FilaRecorrido({ t, idioma, incidente }: Props) {
  const recorrido = incidente.recorrido;
  if (recorrido === undefined) return null;
  const fuente = incidente.fuentes.find((f) => f.id === recorrido.fuente);
  return (
    <Fila nombre={t.rutas.recorrido}>
      <span data-recorrido="">
        {recorrido.puntos.map((p) => (p.hora === undefined ? p.nombre : `${p.nombre} (${p.hora})`)).join(" → ")}
      </span>
      <Cita
        t={t}
        idioma={idioma}
        texto={recorrido.cita}
        idiomaOriginal={fuente?.idioma}
        traduccion={recorrido.cita_traduccion}
        como="q"
        className="block text-xs text-secundario"
      />
      {fuente !== undefined && (
        <span className="block text-xs text-secundario">
          {t.ficha.valorSegun} {fuenteEnFrase(t, fuente.medio, idioma)}
        </span>
      )}
      <span className="block text-xs text-secundario">{t.rutas.recorridoNota}</span>
    </Fila>
  );
}
