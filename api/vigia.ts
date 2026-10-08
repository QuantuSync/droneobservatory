// Disparador de la vigilancia, independiente del servidor y del programador de GitHub.
//
// GitHub lanza las ejecuciones programadas de este repositorio con horas de retraso o se las salta
// (el 7 de octubre de 2026, con la programación cada 10 minutos, no hubo ninguna en tres horas y
// media; antes salían 5 o 6 al día de las 24 de la programación horaria). Esta función la lanza
// la tarea programada de Vercel cada 10 minutos (vercel.json, «crons»): lee lo que publica el
// servidor en el almacén público (salud.json y directo.json) y, si hay un problema o el servidor no
// da señales, lanza el workflow vigia-recogida, que abre la incidencia y falla, con lo que GitHub
// manda el correo al dueño. Si todo va bien no hace nada más.
//
// Necesita dos variables del proyecto de Vercel: CRON_SECRET (Vercel la manda en la cabecera
// Authorization de cada llamada de la tarea programada; sin ella, nadie más puede lanzarla) y
// EODI_VIGIA_TOKEN (un token de GitHub que solo puede lanzar workflows de este repositorio). Sin el
// token, solo deja el diagnóstico en el registro de la función.
//
// Sin import: el empaquetado de Vercel no sigue los ficheros .ts de web/. La dirección del almacén
// es la de configuracion/almacen_publico.json (web/tests/vigia.test.ts comprueba que coinciden).

export const ALMACEN = "https://droneobservatory-almacen.nbg1.your-objectstorage.com";
export const REPOSITORIO = "QuantuSync/droneobservatory";
export const WORKFLOW = "vigia-recogida.yml";
/** salud.json se sube cada 5 minutos: con 20 sin él, el servidor no da señales. */
export const MAX_SIN_SALUD_MS = 20 * 60_000;
/** directo.json se sube cada minuto: media hora sin él es que la detección se ha parado. */
export const MAX_SIN_DIRECTO_MS = 30 * 60_000;
/**
 * La web se reconstruye tras cada publicación. Sus datos llevan la hora de inicio de la recogida
 * (unos 16 minutos antes de publicar): más de 100 minutos por detrás de la última publicación son
 * al menos dos reconstrucciones perdidas.
 */
export const MAX_WEB_ATRASADA_MS = 100 * 60_000;
export const WEB = "https://droneobservatory.eu";

export interface Diagnostico {
  problema: boolean;
  motivos: string[];
}

function instante(valor: unknown): number | null {
  if (typeof valor !== "string") return null;
  const ms = Date.parse(valor.replace(/Z$/, "") + "Z");
  return Number.isNaN(ms) ? null : ms;
}

/** Si hay que avisar, con lo que publica el servidor (null: el fichero no se pudo leer). */
export function diagnosticar(
  salud: unknown,
  directo: unknown,
  ahora: number,
  web: unknown = undefined,
): Diagnostico {
  const motivos: string[] = [];
  const s = (salud ?? null) as { generado?: unknown; problemas?: { id?: unknown }[] } | null;
  const generado = instante(s?.generado);
  if (s === null || generado === null || ahora - generado > MAX_SIN_SALUD_MS) {
    motivos.push("el servidor no da señales (salud.json ausente o con más de 20 minutos)");
  } else {
    for (const p of s.problemas ?? []) motivos.push(`problema: ${String(p.id)}`);
  }
  const publicada = instante(
    (s as { recogida?: { ultima_publicacion?: unknown } } | null)?.recogida?.ultima_publicacion,
  );
  const enLaWeb = instante((web as { actualizado?: unknown } | null | undefined)?.actualizado);
  if (web !== undefined && publicada !== null && (enLaWeb === null || publicada - enLaWeb > MAX_WEB_ATRASADA_MS)) {
    motivos.push("la web no se actualiza (sus datos van más de 100 minutos por detrás de la última publicación)");
  }
  const d = (directo ?? null) as { generado?: unknown } | null;
  const ultimo = instante(d?.generado);
  if (ultimo === null || ahora - ultimo > MAX_SIN_DIRECTO_MS) {
    motivos.push("la detección en directo no publica");
  }
  return { problema: motivos.length > 0, motivos };
}

/** La llamada de los minutos 0 a 9 de cada hora (la tarea programada pasa cada 10 minutos). */
export function horaria(ahora: Date): boolean {
  return ahora.getUTCMinutes() < 10;
}

async function leer(objeto: string, base: string = ALMACEN): Promise<unknown> {
  try {
    const respuesta = await fetch(`${base}/${objeto}`, {
      headers: { "Cache-Control": "no-cache" },
      signal: AbortSignal.timeout(15_000),
    });
    return respuesta.ok ? ((await respuesta.json()) as unknown) : null;
  } catch {
    return null;
  }
}

export async function GET(peticion: Request): Promise<Response> {
  const secreto = process.env.CRON_SECRET;
  if (secreto === undefined || peticion.headers.get("authorization") !== `Bearer ${secreto}`) {
    return new Response("no", { status: 401 });
  }
  const [salud, directo, web] = await Promise.all([
    leer("salud.json"),
    leer("directo.json"),
    leer("datos/resumen.json", WEB),
  ]);
  const diagnostico = diagnosticar(salud, directo, Date.now(), web);
  // Una sola línea en el registro con el diagnóstico y lo que pasó al lanzar (nunca el token).
  const token = (process.env.EODI_VIGIA_TOKEN ?? "").trim();
  // Con un problema, siempre; sin él, una vez por hora (la llamada de los minutos 0 a 9), para que
  // el vigía cierre las incidencias ya arregladas: GitHub se salta casi todas sus ejecuciones
  // programadas.
  const lanzar = diagnostico.problema || horaria(new Date());
  let lanzado: string = lanzar ? "sin token" : "no hace falta";
  if (lanzar && token.length > 0) {
    try {
      const respuesta = await fetch(
        `https://api.github.com/repos/${REPOSITORIO}/actions/workflows/${WORKFLOW}/dispatches`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "EODI-vigia",
          },
          body: JSON.stringify({ ref: "main" }),
          signal: AbortSignal.timeout(15_000),
        },
      );
      lanzado = `HTTP ${respuesta.status}`;
      if (!respuesta.ok) lanzado += ` ${(await respuesta.text()).slice(0, 200)}`;
    } catch (error) {
      lanzado = `error ${String(error).slice(0, 200)}`;
    }
  }
  console.log(JSON.stringify({ ...diagnostico, lanzado }));
  return new Response(JSON.stringify({ ...diagnostico, lanzado }), {
    status: 200,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
