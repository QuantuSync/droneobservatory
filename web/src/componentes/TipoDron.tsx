import type { IncidenteDetalle } from "../datos/tipos.ts";
import type { Textos } from "../i18n/index.ts";
import { Fila } from "./Panel.tsx";

interface Props {
  t: Textos;
  incidente: IncidenteDetalle;
}

/**
 * Fila «Tipo de dron» de la ficha. Si la autoridad identificó el dron, eso y su fuente; si no,
 * «Compatible con» y los grupos comprobados con su probabilidad, separados a la vista de lo que
 * dice una autoridad, y al desplegar por qué (rasgos descritos con su cita y restricciones). Sin
 * base, la fila no aparece.
 */
export function FilaTipoDron({ t, incidente }: Props) {
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
        <q className="block text-xs text-secundario">{identificado.cita}</q>
        {fuente !== undefined && (
          <span className="block text-xs text-secundario">
            {t.ficha.valorSegun} {fuente.medio}
          </span>
        )}
      </Fila>
    );
  }
  const publicado = tipo.publicado;
  if (publicado === undefined) return null;
  const otras = Math.round(publicado.otras * 100);
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
              {textos.probabilidad(Math.round(c.probabilidad * 100))}
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
          {(tipo.razones ?? []).map((razon, i) => (
            <li key={i} className="border-t border-linea py-1" data-razon={razon.clave}>
              {textos.razon(razon)}
            </li>
          ))}
        </ul>
      </details>
    </Fila>
  );
}
