import { useId, useMemo, useState } from "react";
import type { ReactNode, RefObject } from "react";

import {
  RUTAS_AVISOS,
  SERVIDOR_AVISOS,
  TEXTO_AVISOS,
  TIENDAS,
  canales,
  dispositivoActual,
  enlaceAndroidPara,
  enlaceWeb,
  filtrarCanales,
  rutaQr,
} from "../avisos.ts";
import type { Dispositivo, TextoAvisos } from "../avisos.ts";
import type { Idioma } from "../sitio.ts";

/** Campana sencilla, del color del texto: acompaña al rótulo «Avisos» en la cabecera. */
export function IconoCampana({ lado = 14 }: { lado?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={lado}
      height={lado}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
    >
      <path d="M4 11V7a4 4 0 0 1 8 0v4l1.25 1.5H2.75L4 11Z" />
      <path d="M6.5 14a1.5 1.5 0 0 0 3 0" />
    </svg>
  );
}

/**
 * El botón «Avisos» de la cabecera, en el escritorio y en el teléfono: la herramienta que más
 * importa, a la vista sin abrir ningún menú. Mismo estilo que la cabecera, con más peso: campana,
 * texto claro, seminegrita y un borde. Abierto, en claro como todo lo seleccionado.
 */
export function BotonAvisos({
  idioma,
  abierto,
  onAbrir,
  referencia,
  grande = false,
}: {
  idioma: Idioma;
  abierto: boolean;
  onAbrir: () => void;
  referencia?: RefObject<HTMLButtonElement | null> | undefined;
  grande?: boolean;
}) {
  const t = TEXTO_AVISOS[idioma];
  return (
    <button
      ref={referencia}
      type="button"
      className={`control gap-1.5 whitespace-nowrap rounded-sm border border-linea font-semibold text-texto ${
        grande ? "min-h-11 px-2.5 text-sm" : "min-h-7 px-2 text-xs"
      }`}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      aria-label={t.abrir}
      data-boton-avisos=""
      onClick={onAbrir}
    >
      <IconoCampana lado={grande ? 16 : 14} />
      {t.enlace}
    </button>
  );
}

const ENLACE = "enlace-texto text-texto underline decoration-secundario underline-offset-2 hover:decoration-acento";
const CAMPO = "control min-h-11 w-full rounded-sm border border-linea px-2 text-sm text-texto esc:min-h-9";
/** El botón «Suscribirme»: grande y con el estilo de la acción principal («Aplicar»). */
const BOTON_GRANDE = "control control-principal min-h-12 min-w-0 flex-1 rounded-sm px-4 text-center text-base esc:text-base";
const BOTON_COPIAR = "control min-h-11 shrink-0 rounded-sm border border-linea px-2 text-xs text-texto esc:min-h-8";

/** Un paso, con su número a la vista; la lista ordenada ya lo anuncia al lector de pantalla. */
function Paso({ numero, titulo, children }: { numero: number; titulo: string; children: ReactNode }) {
  return (
    <li className="flex flex-col gap-2">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-texto">
        <span
          aria-hidden="true"
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-linea text-xs"
        >
          {numero}
        </span>
        {titulo}
      </h3>
      {children}
    </li>
  );
}

/** Un dato para copiar (el servidor o el canal), con su botón. */
function Copiable({
  texto,
  rotulo,
  t,
  onCopiado,
}: {
  texto: string;
  rotulo: string;
  t: TextoAvisos;
  onCopiado: (texto: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <code className="mono min-w-0 flex-1 break-all rounded-sm border border-linea px-2 py-1 text-xs text-texto">{texto}</code>
      <button
        type="button"
        className={BOTON_COPIAR}
        aria-label={rotulo}
        onClick={() => {
          void navigator.clipboard?.writeText(texto).then(
            () => onCopiado(texto),
            () => undefined,
          );
        }}
      >
        {t.copiar}
      </button>
    </div>
  );
}

/**
 * El panel «Avisos» del mapa, en tres pasos y nada más: qué recibirás; qué quieres recibir (un
 * selector con «Toda Europa» por defecto y los países por orden alfabético, con buscador); y
 * suscríbete, con un solo botón y las instrucciones del dispositivo que se está usando. El código
 * QR del canal sale solo en el ordenador, para llevarlo al móvil. Al pie, «Más ayuda» lleva a la
 * página de texto. Nada de esto mueve el mapa.
 */
export function Avisos({ idioma, dispositivo }: { idioma: Idioma; dispositivo?: Dispositivo }) {
  const t = TEXTO_AVISOS[idioma];
  const [equipo] = useState<Dispositivo>(() => dispositivo ?? dispositivoActual());
  // En Android, intent:// donde el navegador lo admite (lleva a Google Play sin la aplicación).
  const [agente] = useState(() => (typeof navigator === "undefined" ? "" : navigator.userAgent));
  const lista = useMemo(() => canales(idioma), [idioma]);
  const [busqueda, setBusqueda] = useState("");
  const [tema, setTema] = useState(lista[0]?.tema ?? "");
  const [copiado, setCopiado] = useState<string | null>(null);
  const idBuscar = useId();
  const idCanal = useId();
  const idResultado = useId();

  const elegido = lista.find((c) => c.tema === tema) ?? lista[0];
  if (elegido === undefined) return null;
  const visibles = filtrarCanales(lista, busqueda);
  // Lo elegido sigue en el selector aunque la búsqueda no lo encuentre, para que no mienta.
  const opciones = visibles.some((c) => c.tema === elegido.tema) ? visibles : [elegido, ...visibles];
  const pasos = t.pasos[equipo](elegido.tema);
  const destino = equipo === "android" ? enlaceAndroidPara(elegido, agente) : equipo === "iphone" ? TIENDAS.appStore : enlaceWeb(elegido);

  return (
    <div className="flex flex-col gap-4 text-sm" data-panel-avisos="" data-dispositivo={equipo}>
      <ol className="flex flex-col gap-5">
        <Paso numero={1} titulo={t.pasoRecibir}>
          <p className="text-sm text-texto">{t.recibir}</p>
        </Paso>

        <Paso numero={2} titulo={t.pasoElegir}>
          <label htmlFor={idBuscar} className="text-xs text-secundario">
            {t.buscar}
          </label>
          <input
            id={idBuscar}
            type="search"
            className={CAMPO}
            value={busqueda}
            autoComplete="off"
            spellCheck={false}
            aria-controls={idCanal}
            aria-describedby={idResultado}
            data-buscar-canal=""
            onChange={(evento) => {
              const texto = evento.target.value;
              setBusqueda(texto);
              const hallados = filtrarCanales(lista, texto);
              const primero = hallados[0];
              if (primero !== undefined && !hallados.some((c) => c.tema === tema)) setTema(primero.tema);
            }}
          />
          <label htmlFor={idCanal} className="text-xs text-secundario">
            {t.canal}
          </label>
          <select
            id={idCanal}
            className={CAMPO}
            value={elegido.tema}
            data-activo=""
            data-canal-elegido=""
            onChange={(evento) => setTema(evento.target.value)}
          >
            {opciones.map((c) => (
              <option key={c.tema} value={c.tema} className="bg-panel-solido text-texto">
                {c.nombre}
              </option>
            ))}
          </select>
          <p id={idResultado} role="status" className="text-xs text-secundario">
            {visibles.length === 0 ? t.sinResultados : ""}
          </p>
        </Paso>

        <Paso numero={3} titulo={t.pasoSuscribir}>
          <div className="flex items-center gap-3">
            <a
              className={BOTON_GRANDE}
              href={destino}
              data-suscribirme=""
              {...(equipo === "android" ? {} : { rel: "noopener", target: "_blank" })}
            >
              {t.suscribirme}
            </a>
            {equipo === "ordenador" && (
              <figure className="flex shrink-0 flex-col items-center gap-1" data-qr-avisos="">
                <img src={rutaQr(elegido)} alt={t.qr(elegido.nombre)} width={112} height={112} className="rounded-sm" />
                <figcaption className="max-w-28 text-center text-xs text-secundario">{t.escanear}</figcaption>
              </figure>
            )}
          </div>
          <ol className="flex list-decimal flex-col gap-1 pl-5 text-xs text-texto">
            {pasos.map((paso) => (
              <li key={paso} className="break-words">
                {paso}
              </li>
            ))}
          </ol>
          {equipo === "iphone" && (
            <div className="flex flex-col gap-2">
              <Copiable texto={SERVIDOR_AVISOS} rotulo={t.copiarServidor} t={t} onCopiado={setCopiado} />
              <Copiable texto={elegido.tema} rotulo={t.copiarCanal} t={t} onCopiado={setCopiado} />
            </div>
          )}
          {equipo === "android" && (
            <p className="text-xs">
              <a className={ENLACE} href={TIENDAS.googlePlay} rel="noopener" target="_blank">
                {t.sinAplicacion}
              </a>
            </p>
          )}
          <p role="status" className="text-xs text-secundario">
            {copiado !== null ? `${t.copiado}: ${copiado}` : ""}
          </p>
        </Paso>
      </ol>
      <p className="text-xs">
        <a className={ENLACE} href={RUTAS_AVISOS[idioma]}>
          {t.masAyuda}
        </a>
      </p>
    </div>
  );
}
