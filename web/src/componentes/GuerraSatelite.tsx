// Fichas y piezas de la guerra por satélite: imágenes de antes y después de un impacto, pérdida
// de luz nocturna de una región o una ciudad y corredores de ataque.

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";

import { urlDelAlmacen } from "../almacenPublico.ts";
import { OBJETO_PAREJAS } from "../datos/guerraSatelite.ts";
import { TIPOS_SATELITE, tiposDe } from "../datos/guerraSatelite.ts";
import type {
  CiudadAlumbrado,
  CiudadSinLuz,
  Corredor,
  PuntoSatelite,
  TipoSatelite,
  IndiceSatelite,
  ParejaSatelite,
} from "../datos/guerraSatelite.ts";
import type { LuzResumen } from "../datos/tipos.ts";
import { validarIndiceSatelite } from "../datos/validar.ts";
import { fechaDia, numero, region } from "../i18n/index.ts";
import type { Textos } from "../i18n/index.ts";
import { Enlace } from "../navegacion.tsx";
import { rutaDeFicha } from "../sitio.ts";
import type { Idioma } from "../sitio.ts";
import { diaDeInstante } from "../tiempo/dias.ts";
import { PALETA } from "../paleta.ts";
import { Fila } from "./Panel.tsx";

/** «2025-09-11…» como dd/mm/aaaa. */
function dia(valor: string): string {
  return fechaDia(diaDeInstante(`${valor.slice(0, 10)}T00:00Z`));
}

// ---- Índice de imágenes (almacén público) --------------------------------------------

let indice: Promise<IndiceSatelite | null> | null = null;

/** El índice de parejas, pedido una sola vez por visita; si falla, se vuelve a pedir la próxima. */
export function cargarIndiceSatelite(descargar: typeof fetch = fetch): Promise<IndiceSatelite | null> {
  const pedido =
    indice ??
    descargar(urlDelAlmacen(OBJETO_PAREJAS))
      .then(async (respuesta) => {
        if (!respuesta.ok) return null;
        const resultado = validarIndiceSatelite(await respuesta.json());
        return resultado.ok ? resultado.datos : null;
      })
      .catch(() => null);
  indice = pedido;
  void pedido.then((datos) => {
    if (datos === null && indice === pedido) indice = null;
  });
  return pedido;
}

/** Para las pruebas: olvida el índice cargado. */
export function olvidarIndiceSatelite(): void {
  indice = null;
}

/** Posición inicial de la cortinilla, en % del ancho desde la izquierda. */
const CORTINILLA_INICIAL = 50;
const PASO_TECLADO = 5;

/**
 * Las dos imágenes superpuestas: la de antes a la izquierda de la cortinilla y la de después a
 * la derecha. Se arrastra con el dedo o el ratón; con el teclado, el deslizador.
 */
export function Cortinilla({
  t,
  pareja,
}: {
  t: Textos;
  pareja: ParejaSatelite;
}) {
  const [posicion, setPosicion] = useState(CORTINILLA_INICIAL);
  const [contorno, setContorno] = useState(true);
  const caja = useRef<HTMLDivElement>(null);
  const arrastrando = useRef(false);

  function mover(evento: PointerEvent<HTMLDivElement>) {
    const elemento = caja.current;
    if (elemento === null) return;
    const rect = elemento.getBoundingClientRect();
    if (rect.width === 0) return;
    const x = ((evento.clientX - rect.left) / rect.width) * 100;
    setPosicion(Math.round(Math.min(100, Math.max(0, x))));
  }

  function teclado(evento: KeyboardEvent<HTMLInputElement>) {
    if (evento.key === "Home") setPosicion(0);
    if (evento.key === "End") setPosicion(100);
  }

  const { antes, despues } = pareja;
  return (
    <figure className="mt-1" data-cortinilla="">
      <div
        ref={caja}
        className="relative aspect-square w-full touch-none select-none overflow-hidden rounded-sm border border-linea bg-elevado"
        onPointerDown={(evento) => {
          arrastrando.current = true;
          evento.currentTarget.setPointerCapture(evento.pointerId);
          mover(evento);
        }}
        onPointerMove={(evento) => {
          if (arrastrando.current) mover(evento);
        }}
        onPointerUp={() => {
          arrastrando.current = false;
        }}
        onPointerCancel={() => {
          arrastrando.current = false;
        }}
      >
        <img
          src={urlDelAlmacen(antes.objeto)}
          alt={t.satelite.imagen.alt(t.satelite.imagen.antes.toLowerCase(), dia(antes.fecha))}
          className="absolute inset-0 size-full object-cover"
          draggable={false}
          loading="lazy"
          decoding="async"
        />
        <img
          src={urlDelAlmacen(despues.objeto)}
          alt={t.satelite.imagen.alt(t.satelite.imagen.despues.toLowerCase(), dia(despues.fecha))}
          className="absolute inset-0 size-full object-cover"
          style={{ clipPath: `inset(0 0 0 ${posicion}%)` }}
          draggable={false}
          loading="lazy"
          decoding="async"
        />
        {contorno && (
          <svg
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 size-full"
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            data-contorno-cambio=""
          >
            <polygon
              points={pareja.cambio.contorno.map(([x, y]) => `${x},${y}`).join(" ")}
              fill="none"
              stroke={PALETA.guerraClaro}
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        )}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 w-0.5 bg-guerra-claro"
          style={{ left: `${posicion}%` }}
        />
        <button
          type="button"
          className="flotante absolute bottom-1.5 right-1.5 px-1.5 py-0.5 text-[0.6875rem]"
          aria-pressed={contorno}
          onPointerDown={(evento) => evento.stopPropagation()}
          onClick={() => setContorno(!contorno)}
        >
          {contorno ? t.satelite.imagen.ocultarContorno : t.satelite.imagen.verContorno}
        </button>
        <span className="flotante pointer-events-none absolute left-1.5 top-1.5 px-1.5 py-0.5 text-[0.6875rem]">
          {t.satelite.imagen.antes} · <span className="mono">{dia(antes.fecha)}</span>
        </span>
        <span className="flotante pointer-events-none absolute right-1.5 top-1.5 px-1.5 py-0.5 text-[0.6875rem]">
          {t.satelite.imagen.despues} · <span className="mono">{dia(despues.fecha)}</span>
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={PASO_TECLADO}
        value={posicion}
        aria-label={t.satelite.imagen.deslizador}
        className="mt-2 w-full accent-[var(--acento)]"
        onChange={(evento) => setPosicion(Number(evento.target.value))}
        onKeyDown={teclado}
      />
    </figure>
  );
}

/** Apartado «Imagen de satélite» de la ficha de un impacto, a todo el ancho, si tiene alguna. */
export function ImagenesSatelite({ t, idioma, id }: { t: Textos; idioma: Idioma; id: string }) {
  const [datos, setDatos] = useState<IndiceSatelite | null | undefined>(undefined);
  useEffect(() => {
    let vigente = true;
    void cargarIndiceSatelite().then((resultado) => {
      if (vigente) setDatos(resultado);
    });
    return () => {
      vigente = false;
    };
  }, []);
  const pareja = datos?.parejas[id];
  if (datos === undefined || datos === null || pareja === undefined) return null;
  const lado = new Intl.NumberFormat(idioma, { maximumFractionDigits: 1 }).format(
    pareja.recorte.lado_m / 1000,
  );
  const hectareas = new Intl.NumberFormat(idioma, { maximumFractionDigits: 1 }).format(
    pareja.cambio.hectareas,
  );
  const { antes, despues } = pareja;
  return (
    <section className="mt-3" data-imagenes-satelite="">
      <h3 className="rotulo">{t.satelite.imagen.rotulo}</h3>
      <div>
        <Cortinilla t={t} pareja={pareja} />
        <span className="block text-sm" data-zona-cambio="">
          {t.satelite.imagen.zonaCambio(hectareas, dia(antes.fecha), dia(despues.fecha))}
        </span>
        <span className="block text-xs text-secundario">{t.satelite.imagen.producto(lado)}</span>
        <span className="mono block text-[0.6875rem] text-secundario">
          {t.satelite.imagen.antes}: {dia(antes.fecha)} · {t.satelite.imagen.escena(antes.escena)}
          <br />
          {t.satelite.imagen.despues}: {dia(despues.fecha)} · {t.satelite.imagen.escena(despues.escena)}
        </span>
        <span className="block text-xs text-secundario" data-atribucion-copernicus="">
          {datos.atribucion}
        </span>
      </div>
    </section>
  );
}

// ---- Luz nocturna -------------------------------------------------------------------

/** Las pérdidas de luz de una lista, de la más reciente a la más antigua. */
export function ListaLuz({
  t,
  idioma,
  luces,
}: {
  t: Textos;
  idioma: Idioma;
  luces: readonly LuzResumen[];
}) {
  return (
    <ul data-luz-lista="">
      {luces.map((l) => (
        <li key={`${l.ataque}|${l.zona}|${l.ciudad?.nombre ?? ""}`} className="border-b border-linea py-1.5">
          <span className="font-medium">
            {t.satelite.luzFicha.perdida(numero(l.perdida, idioma))}
          </span>{" "}
          <span className="text-secundario">{t.satelite.luzFicha.peorNoche(dia(l.noche))}</span>
          <span className="block text-xs text-secundario">
            {l.ciudad === null ? t.satelite.luzFicha.regionEntera : l.ciudad.nombre} ·{" "}
            {t.satelite.luzFicha.noches(l.noches.length)} ·{" "}
            {t.satelite.luzFicha.referencia(dia(l.referencia.desde), dia(l.referencia.hasta), l.referencia.noches)}
          </span>
          <span className="block text-xs text-secundario">
            {t.satelite.luzFicha.ataque}:{" "}
            <Enlace a={rutaDeFicha(l.ataque, idioma)} className="enlace mono">
              {l.ataque}
            </Enlace>{" "}
            · {t.satelite.luzFicha.origen}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Ficha de una ciudad que perdió luz nocturna en el periodo. */
export function FichaLuz({
  t,
  idioma,
  ciudad,
  periodo,
}: {
  t: Textos;
  idioma: Idioma;
  ciudad: CiudadSinLuz;
  periodo: string;
}) {
  return (
    <article data-ficha-luz="">
      <h2 className="text-2xl font-semibold tracking-tight">
        <span lang={ciudad.region.startsWith("UA-") ? "uk" : "ru"}>{ciudad.nombre}</span>
      </h2>
      <p className="mono mt-1 text-xs text-secundario">
        {region(ciudad.region, idioma)} · {periodo}
      </p>
      <dl className="mt-3">
        <Fila nombre={t.satelite.luzFicha.rotulo}>
          <ListaLuz t={t} idioma={idioma} luces={ciudad.lista} />
        </Fila>
      </dl>
      <p className="mt-2 text-xs text-secundario">{t.satelite.luzFicha.metodo}</p>
    </article>
  );
}

/** «AAAA-MM» como mm/aaaa. */
function mes(valor: string): string {
  return `${valor.slice(5, 7)}/${valor.slice(0, 4)}`;
}

/** Ficha de una ciudad con alumbrado reducido de forma permanente. */
export function FichaAlumbrado({
  t,
  idioma,
  ciudad,
}: {
  t: Textos;
  idioma: Idioma;
  ciudad: CiudadAlumbrado;
}) {
  const textos = t.satelite.alumbradoFicha;
  const brillo = (valor: number) => numero(valor, idioma);
  return (
    <article data-ficha-alumbrado="">
      <p className="text-secundario">{textos.titulo}</p>
      <h2 className="text-2xl font-semibold tracking-tight">
        <span lang={ciudad.region.startsWith("UA-") ? "uk" : "ru"}>{ciudad.ciudad.nombre}</span>
      </h2>
      <p className="mono mt-1 text-xs text-secundario">{region(ciudad.region, idioma)}</p>
      <dl className="mt-3">
        <Fila nombre={textos.desde}>
          <span>{textos.desdeTexto(dia(ciudad.desde), ciudad.al_menos)}</span>
          {ciudad.ultimo_mes_por_encima !== undefined && (
            <span className="block text-xs text-secundario">
              {textos.porEncima(mes(ciudad.ultimo_mes_por_encima))}
            </span>
          )}
        </Fila>
        <Fila nombre={textos.actual}>
          <span className="font-medium">{textos.brillo(brillo(ciudad.actual.brillo))}</span>
          <span className="block text-xs text-secundario">
            {textos.tramo(dia(ciudad.actual.desde), dia(ciudad.actual.hasta), ciudad.actual.noches)}
          </span>
        </Fila>
        <Fila nombre={textos.referencia}>
          <span className="font-medium">{textos.brillo(brillo(ciudad.antiguo.brillo))}</span>
          <span className="block text-xs text-secundario">
            {textos.tramo(dia(ciudad.antiguo.desde), dia(ciudad.antiguo.hasta), ciudad.antiguo.noches)}
          </span>
        </Fila>
        <Fila nombre={textos.noches}>
          <span>{numero(ciudad.noches, idioma)}</span>
        </Fila>
      </dl>
      <p className="mt-2 text-xs text-secundario">{textos.metodo}</p>
    </article>
  );
}

// ---- Corredores -----------------------------------------------------------------------

/** Origen de un corredor: la zona de lanzamiento o, contra Rusia, Ucrania. */
export function origenDeCorredor(t: Textos, corredor: Corredor): string {
  return corredor.origen === null
    ? t.satelite.corredor.desdeUcrania
    : t.satelite.zona(corredor.clave.split("|")[0] ?? "", corredor.origen);
}

/** «Kursk → Járkov». */
export function nombreDeCorredor(t: Textos, corredor: Corredor): string {
  return `${origenDeCorredor(t, corredor)} → ${t.regiones[corredor.region] ?? corredor.region}`;
}

/** «Kursk → Járkov · 120 drones»: el letrero del arco y su nombre accesible. */
export function letreroDeCorredor(t: Textos, idioma: Idioma, corredor: Corredor): string {
  return t.satelite.letreroCorredor(
    origenDeCorredor(t, corredor),
    t.regiones[corredor.region] ?? corredor.region,
    new Intl.NumberFormat(idioma).format(corredor.drones),
  );
}

/** Varios arcos casi a la misma distancia del punto pulsado: se elige uno. */
export function ListaCorredores({
  t,
  corredores,
  onElegir,
}: {
  t: Textos;
  corredores: readonly Corredor[];
  onElegir: (clave: string) => void;
}) {
  return (
    <div data-lista-corredores="">
      <p className="text-secundario">{t.satelite.corredor.varios}</p>
      <ul className="mt-2">
        {corredores.map((c) => (
          <li key={c.clave} className="border-b border-linea">
            <button
              type="button"
              className="w-full py-2 text-left hover:text-texto"
              onClick={() => onElegir(c.clave)}
            >
              {nombreDeCorredor(t, c)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Ficha de un corredor de ataque del periodo. */
export function FichaCorredor({
  t,
  idioma,
  corredor,
  periodo,
}: {
  t: Textos;
  idioma: Idioma;
  corredor: Corredor;
  periodo: string;
}) {
  const origen = origenDeCorredor(t, corredor);
  return (
    <article data-ficha-corredor="">
      <p className="text-secundario">{t.sentido[corredor.sentido]}</p>
      <h2 className="text-2xl font-semibold tracking-tight">
        {origen} → {region(corredor.region, idioma)}
      </h2>
      <dl className="mt-3">
        <Fila nombre={t.satelite.corredor.origen}>
          <span>{origen}</span>
          {corredor.origen === null && (
            <span className="block text-xs text-secundario">{t.satelite.corredor.desdeUcraniaTexto}</span>
          )}
        </Fila>
        <Fila nombre={t.satelite.corredor.destino}>
          <span>{region(corredor.region, idioma)}</span>
          <span className="mono ml-2 text-xs text-secundario">{corredor.region}</span>
        </Fila>
        <Fila nombre={t.satelite.corredor.drones}>
          <span className="mono">{numero(corredor.drones, idioma)}</span>
          <span className="block text-xs text-secundario">
            {t.satelite.corredor.dronesTexto[corredor.sentido]}
          </span>
          <span className="block text-xs text-secundario">{t.satelite.corredor.ataques(corredor.ataques)}</span>
        </Fila>
        <Fila nombre={t.satelite.corredor.periodo}>
          <span className="mono">{periodo}</span>
        </Fila>
      </dl>
    </article>
  );
}

// ---- Con satélite ---------------------------------------------------------------------

/** «antes y después · foco de calor»: lo que tiene un punto con información de satélite. */
export function loQueTiene(t: Textos, punto: PuntoSatelite): string {
  return tiposDe(punto)
    .map((tipo) => t.satelite.tipos[tipo])
    .join(" · ");
}

/** El signo de cada tipo en el mapa, para la leyenda y el filtro. */
export function SignoSatelite({ tipo }: { tipo: TipoSatelite }) {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" data-signo={tipo}>
      {tipo === "cortinilla" && (
        <>
          <circle cx="8" cy="8" r="7" fill="none" stroke={PALETA.guerraClaro} strokeWidth="1" />
          <circle cx="8" cy="8" r="4.2" fill={PALETA.guerra} stroke={PALETA.guerraClaro} strokeWidth="1.4" />
        </>
      )}
      {tipo === "foco" && (
        <>
          <circle cx="7" cy="9" r="4.2" fill={PALETA.guerra} stroke={PALETA.guerraClaro} strokeWidth="1.4" />
          <circle cx="12" cy="4" r="2.4" fill={PALETA.guerraClaro} stroke={PALETA.fondo} strokeWidth="1" />
        </>
      )}
      {tipo === "apagon" && (
        <circle cx="8" cy="8" r="6" fill={PALETA.fondo} stroke={PALETA.guerraTenue} strokeWidth="1" />
      )}
      {tipo === "oscura" && (
        <>
          <circle cx="8" cy="8" r="5.6" fill={PALETA.fondo} stroke={PALETA.guerraTenue} strokeWidth="1.4" />
          <circle cx="8" cy="8" r="1.8" fill={PALETA.guerraClaro} />
        </>
      )}
    </svg>
  );
}

interface PropsSatelite {
  t: Textos;
  idioma: Idioma;
  puntos: readonly PuntoSatelite[];
  /** Lista desplegada (en escritorio, el desplegable entero). */
  abierta: boolean;
  onAbierta: (abierta: boolean) => void;
  /** Tipos a los que se limita la lista; vacío, todos. */
  filtro: readonly TipoSatelite[];
  onFiltro: (filtro: TipoSatelite[]) => void;
  onElegir: (punto: PuntoSatelite) => void;
}

/**
 * Lo que acompaña a «Con satélite» encendido: la leyenda de los cuatro tipos (plegada al empezar),
 * el filtro por tipo y la lista, del más reciente al más antiguo; pulsar una fila lleva al punto y
 * abre su ficha. Todo a lo ancho de donde va: el menú del teléfono o el desplegable del escritorio.
 * Con `acceso`, la lista se abre y se cierra con su propio botón (el teléfono); sin él, se ve
 * siempre (el desplegable ya se abre con la flecha).
 */
export function PanelSatelite({
  t,
  idioma,
  puntos,
  abierta,
  onAbierta,
  filtro,
  onFiltro,
  onElegir,
  acceso,
}: PropsSatelite & { acceso: boolean }) {
  const [leyenda, setLeyenda] = useState(false);
  const textos = t.satelite;
  const visibles =
    filtro.length === 0 ? puntos : puntos.filter((p) => tiposDe(p).some((x) => filtro.includes(x)));
  const cuenta = (tipo: TipoSatelite) => puntos.filter((p) => tiposDe(p).includes(tipo)).length;
  const conLista = !acceso || abierta;
  // En el teléfono, 44 px de alto para el dedo; en el desplegable del escritorio, compactos.
  const alto = acceso ? "min-h-11" : "min-h-7";
  return (
    <div className="w-full" data-panel-satelite="">
      <div className="border-b border-linea px-3 py-2">
        <button
          type="button"
          className={`rotulo flex w-full items-center justify-between text-left ${alto}`}
          aria-expanded={leyenda}
          onClick={() => setLeyenda(!leyenda)}
        >
          {textos.leyenda} <span aria-hidden="true">{leyenda ? "▴" : "▾"}</span>
        </button>
        {leyenda && (
          <ul className="mt-1 flex w-full flex-col gap-1.5 text-xs text-secundario" data-leyenda-satelite="">
            {TIPOS_SATELITE.map((tipo) => (
              <li key={tipo} className="flex items-center gap-2">
                <span className="flex shrink-0">
                  <SignoSatelite tipo={tipo} />
                </span>
                <span>{textos.leyendaTipos[tipo]}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div role="group" aria-label={textos.filtrar} className="flex flex-wrap gap-1 border-b border-linea px-3 py-2">
        {TIPOS_SATELITE.map((tipo) => (
          <button
            key={tipo}
            type="button"
            className={`control gap-1.5 whitespace-nowrap px-2 text-xs ${alto}`}
            aria-pressed={filtro.includes(tipo)}
            onClick={() =>
              onFiltro(
                filtro.includes(tipo)
                  ? filtro.filter((x) => x !== tipo)
                  : TIPOS_SATELITE.filter((x) => x === tipo || filtro.includes(x)),
              )
            }
          >
            <span className="flex shrink-0">
              <SignoSatelite tipo={tipo} />
            </span>
            {textos.tipos[tipo]} · {numero(cuenta(tipo), idioma)}
          </button>
        ))}
      </div>
      {acceso && (
        <button
          type="button"
          className="control min-h-11 w-full justify-between whitespace-nowrap px-3 text-sm"
          aria-expanded={abierta}
          aria-label={abierta ? textos.cerrarLista : textos.abrirLista}
          onClick={() => onAbierta(!abierta)}
        >
          <span>{textos.verLista(numero(visibles.length, idioma))}</span>
          <span aria-hidden="true">{abierta ? "▴" : "▾"}</span>
        </button>
      )}
      {conLista && (
        <div data-lista-satelite="">
          <ul aria-label={textos.listaSatelite}>
            {visibles.map((p) => (
              <li key={`${p.clase}|${p.clave}`} className="border-b border-linea last:border-b-0">
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-elevado"
                  onClick={() => {
                    onAbierta(false);
                    onElegir(p);
                  }}
                >
                  <span className="block text-texto">
                    {p.lugar === null ? region(p.region, idioma) : p.lugar}
                  </span>
                  <span className="mono block text-xs text-secundario">
                    {fechaDia(p.dia)} · {loQueTiene(t, p)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Botón «Con satélite · N» de la capa de guerra: enciende los cuatro tipos de lo que se ve desde
 * el satélite (cortinilla con cambio, foco confirmado, apagón, ciudad a oscuras), cada uno con su
 * signo, y atenúa lo demás de la capa. En escritorio lleva al lado la flecha de su desplegable
 * (`PanelSatelite`); en el teléfono (`grande`) es solo el botón, del mismo tamaño que los de las
 * capas, y el panel va debajo, a todo el ancho del menú.
 */
export function BotonSatelite({
  activo,
  onActivo,
  grande = false,
  ...panel
}: PropsSatelite & {
  activo: boolean;
  onActivo: (activo: boolean) => void;
  grande?: boolean;
}) {
  const { t, idioma, puntos, abierta, onAbierta } = panel;
  const textos = t.satelite;
  if (grande) {
    return (
      <button
        type="button"
        className="control min-h-11 whitespace-nowrap px-2 text-sm"
        aria-pressed={activo}
        data-con-satelite=""
        onClick={() => onActivo(!activo)}
      >
        {textos.conSatelite(numero(puntos.length, idioma))}
      </button>
    );
  }
  const boton = "control min-h-7 whitespace-nowrap px-2 text-xs";
  return (
    <div className="relative flex" data-con-satelite="">
      <button
        type="button"
        className={boton}
        aria-pressed={activo}
        onClick={() => {
          onActivo(!activo);
          onAbierta(!activo);
        }}
      >
        {textos.conSatelite(numero(puntos.length, idioma))}
      </button>
      {activo && (
        <button
          type="button"
          className={boton}
          aria-expanded={abierta}
          aria-label={abierta ? textos.cerrarLista : textos.abrirLista}
          onClick={() => onAbierta(!abierta)}
        >
          <span aria-hidden="true">{abierta ? "▴" : "▾"}</span>
        </button>
      )}
      {activo && abierta && (
        <div className="flotante absolute right-0 top-full z-40 mt-1 max-h-[70vh] w-80 overflow-y-auto">
          <PanelSatelite {...panel} acceso={false} />
        </div>
      )}
    </div>
  );
}
