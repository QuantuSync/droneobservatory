// El lector delegado: descarga, para la recogida, una página de una fuente oficial que no deja
// entrar a la dirección del servidor (docs/lector_delegado.md). La recogida pide
// /api/lector?fuente=<id>&url=<dirección> y recibe la página tal cual, con el código de estado de
// la fuente, su fecha y la dirección final.
//
// No es un proxy abierto: solo descarga direcciones de FUENTES (la fuente, su dirección base y los
// caminos admitidos, sin parámetros), también al seguir una redirección; respeta el robots.txt de
// cada sitio para la identificación del observatorio; y tiene un tope de peticiones por minuto. No
// lleva credenciales: lo que descarga es público.
//
// Sus respuestas llevan X-Lector: «origen» si son las de la fuente, «propio» si son del lector
// (dirección no admitida, robots.txt, tope, la fuente no respondió).
//
// Sin import: el empaquetado de Vercel no sigue los ficheros .ts de web/. Las fuentes delegadas
// de configuracion/fuentes_oficiales.json (las de "delegada": true) tienen que estar aquí
// (web/tests/lector.test.ts lo comprueba).

export interface FuenteDelegada {
  id: string;
  /** Esquema y sitio, sin barra final. */
  base: string;
  /** Los caminos que se pueden descargar, enteros (sin parámetros). */
  caminos: readonly RegExp[];
}

export const FUENTES: readonly FuenteDelegada[] = [
  {
    // Ministerio de Defensa de Letonia: la lista de noticias y cada noticia.
    id: "mod_lv",
    base: "https://www.mod.gov.lv",
    caminos: [/^\/robots\.txt$/, /^\/lv\/zinas$/, /^\/lv\/zinas\/[a-z0-9-]{10,}$/],
  },
  {
    // Consejo de Seguridad Nuclear: el canal de sucesos notificados.
    id: "csn_sucesos",
    base: "https://www.csn.es",
    caminos: [/^\/robots\.txt$/, /^\/sucesos-notificados\/-\/asset_publisher\/AhgtIexAjt0q\/rss$/],
  },
];

/** La identificación del observatorio, la misma que usa la recogida (recogida/descarga.py). */
export const AGENTE = "EODI-bot/1.0 (+https://droneobservatory.eu)";
const CABECERAS = {
  "User-Agent": AGENTE,
  Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "uk,en;q=0.8",
};
/** Peticiones por minuto de cada instancia, sumadas todas las fuentes (la recogida pide unas 10). */
export const TOPE_POR_MINUTO = 30;
/** Lo que se espera a la fuente en cada petición; la recogida corta a los 30 s. */
export const TOPE_MS = 25_000;
const REDIRECCIONES = 3;
/** Lo que se guarda el robots.txt de cada sitio. */
const ROBOTS_MS = 3_600_000;

/** La fuente de la lista y la dirección admitida, o el motivo del rechazo. */
export function admitir(fuente: string | null, direccion: string | null): { fuente: FuenteDelegada; url: URL } | string {
  const delegada = FUENTES.find((f) => f.id === fuente);
  if (delegada === undefined) return "fuente no admitida";
  if (direccion === null) return "falta la dirección";
  let url: URL;
  try {
    url = new URL(direccion);
  } catch {
    return "dirección no válida";
  }
  return admitida(delegada, url) ? { fuente: delegada, url } : "dirección no admitida";
}

function admitida(fuente: FuenteDelegada, url: URL): boolean {
  return (
    url.origin === fuente.base &&
    url.username === "" &&
    url.password === "" &&
    url.search === "" &&
    url.hash === "" &&
    fuente.caminos.some((c) => c.test(url.pathname))
  );
}

/** El tope de peticiones por minuto, con una ventana deslizante. */
export class Tope {
  private readonly momentos: number[] = [];
  private readonly porMinuto: number;
  private readonly reloj: () => number;

  constructor(porMinuto = TOPE_POR_MINUTO, reloj: () => number = Date.now) {
    this.porMinuto = porMinuto;
    this.reloj = reloj;
  }

  /** Si cabe una petición más ahora (y la anota); si no, los segundos que faltan. */
  pedir(): true | number {
    const ahora = this.reloj();
    while (this.momentos.length > 0 && ahora - (this.momentos[0] ?? 0) >= 60_000) this.momentos.shift();
    if (this.momentos.length >= this.porMinuto) {
      return Math.max(1, Math.ceil((60_000 - (ahora - (this.momentos[0] ?? 0))) / 1000));
    }
    this.momentos.push(ahora);
    return true;
  }

  vaciar(): void {
    this.momentos.length = 0;
  }
}

interface Regla {
  permitir: boolean;
  camino: string;
}

/**
 * Las reglas del robots.txt que valen para la identificación del observatorio: las del grupo
 * «EODI-bot» si lo hay, y si no las de «*». Como urllib.robotparser de la recogida, sin comodines.
 */
export function reglasRobots(texto: string): Regla[] {
  const grupos: { agentes: string[]; reglas: Regla[] }[] = [];
  let actual: { agentes: string[]; reglas: Regla[] } | null = null;
  for (const linea of texto.split(/\r?\n/)) {
    const limpia = linea.replace(/#.*/, "").trim();
    const dos = limpia.indexOf(":");
    if (dos < 0) continue;
    const campo = limpia.slice(0, dos).trim().toLowerCase();
    const valor = limpia.slice(dos + 1).trim();
    if (campo === "user-agent") {
      if (actual === null || actual.reglas.length > 0) {
        actual = { agentes: [], reglas: [] };
        grupos.push(actual);
      }
      actual.agentes.push(valor.toLowerCase());
    } else if ((campo === "allow" || campo === "disallow") && actual !== null) {
      actual.reglas.push({ permitir: campo === "allow" || valor === "", camino: valor });
    }
  }
  const nombre = AGENTE.split("/")[0]?.toLowerCase() ?? "";
  const propio = grupos.find((g) => g.agentes.some((a) => a !== "*" && nombre.includes(a)));
  return (propio ?? grupos.find((g) => g.agentes.includes("*")))?.reglas ?? [];
}

/** Si el robots.txt deja leer el camino: manda la primera regla que lo cubre, como en la recogida. */
export function robotsPermite(reglas: readonly Regla[], camino: string): boolean {
  for (const regla of reglas) {
    if (regla.camino === "") continue;
    if (camino.startsWith(regla.camino)) return regla.permitir;
  }
  return true;
}

const tope = new Tope();
const robots = new Map<string, { reglas: Regla[]; hasta: number }>();

/** Los códigos que no llevan cuerpo (el constructor de Response no lo admite). */
const SIN_CUERPO = new Set([101, 204, 205, 304]);

function conCuerpo(cuerpo: ArrayBuffer, codigo: number, cabeceras: Headers): Response {
  return new Response(SIN_CUERPO.has(codigo) ? null : cuerpo, { status: codigo, headers: cabeceras });
}

async function pedir(url: string): Promise<Response | null> {
  const control = new AbortController();
  const corte = setTimeout(() => {
    control.abort();
  }, TOPE_MS);
  try {
    const r = await fetch(url, { headers: CABECERAS, redirect: "manual", signal: control.signal });
    // El cuerpo entero dentro del tope: así la respuesta del lector no se queda a medias.
    const cuerpo = await r.arrayBuffer();
    return conCuerpo(cuerpo, r.status, r.headers);
  } catch {
    return null;
  } finally {
    clearTimeout(corte);
  }
}

async function reglasDe(fuente: FuenteDelegada): Promise<Regla[] | null> {
  const guardadas = robots.get(fuente.base);
  if (guardadas !== undefined && Date.now() < guardadas.hasta) return guardadas.reglas;
  const r = await pedir(`${fuente.base}/robots.txt`);
  if (r === null) return null;
  // Sin robots.txt (404 u otro código), todo está permitido, como en la recogida.
  const reglas = r.status === 200 ? reglasRobots(await r.text()) : [];
  robots.set(fuente.base, { reglas, hasta: Date.now() + ROBOTS_MS });
  return reglas;
}

function propia(codigo: number, mensaje: string, extra: Record<string, string> = {}): Response {
  return new Response(mensaje, {
    status: codigo,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "X-Lector": "propio", ...extra },
  });
}

export async function GET(peticion: Request): Promise<Response> {
  const parametros = new URL(peticion.url).searchParams;
  const pedido = admitir(parametros.get("fuente"), parametros.get("url"));
  if (typeof pedido === "string") return propia(400, pedido);
  const turno = tope.pedir();
  if (turno !== true) return propia(429, "demasiadas peticiones", { "Retry-After": String(turno) });
  const { fuente } = pedido;
  let url = pedido.url;
  if (url.pathname !== "/robots.txt") {
    const reglas = await reglasDe(fuente);
    if (reglas === null) return propia(504, "la fuente no respondió (robots.txt)");
    if (!robotsPermite(reglas, url.pathname)) return propia(403, "su robots.txt no deja leerla");
  }
  for (let salto = 0; ; salto++) {
    const r = await pedir(url.href);
    if (r === null) return propia(504, "la fuente no respondió");
    const destino = r.status >= 300 && r.status < 400 ? r.headers.get("location") : null;
    if (destino === null || salto === REDIRECCIONES) {
      const cabeceras = new Headers({
        "Cache-Control": "no-store",
        "X-Lector": "origen",
        "X-Lector-Fuente": fuente.id,
        "X-Lector-Url-Final": url.href,
        "X-Lector-Fecha": r.headers.get("date") ?? new Date().toUTCString(),
      });
      const tipo = r.headers.get("content-type");
      if (tipo !== null) cabeceras.set("Content-Type", tipo);
      return conCuerpo(await r.arrayBuffer(), r.status, cabeceras);
    }
    const siguiente = new URL(destino, url);
    if (!admitida(fuente, siguiente)) return propia(502, `redirección a una dirección no admitida: ${siguiente.href}`);
    url = siguiente;
  }
}

/** Para las pruebas: vacía el tope y los robots.txt guardados. */
export function olvidar(): void {
  robots.clear();
  tope.vaciar();
}
