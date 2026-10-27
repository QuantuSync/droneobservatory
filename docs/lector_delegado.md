# Lector delegado

Algunas fuentes oficiales no dejan entrar a la dirección del servidor de la recogida (los rangos
de los centros de datos de Hetzner): responden 403 o no aceptan la conexión, mientras desde otras
redes cargan con normalidad. Para esas fuentes, la web tiene una función de servidor en Vercel,
`api/lector.ts`, que descarga la página y se la devuelve a la recogida tal cual.

## Qué hace

La recogida pide `https://droneobservatory.eu/api/lector?fuente=<id>&url=<dirección>` y recibe:

- el cuerpo de la página, sin tocar;
- el código de estado de la fuente (un 403 o un 404 de la fuente llegan como 403 o 404);
- `X-Lector-Url-Final` (la dirección final, tras las redirecciones), `X-Lector-Fecha` (la fecha
  que dio la fuente) y `X-Lector-Fuente`;
- `X-Lector: origen` si la respuesta es la de la fuente, o `X-Lector: propio` si es del lector:
  400 (dirección no admitida), 403 (el robots.txt del sitio no lo deja), 429 (tope por minuto,
  con `Retry-After`), 502 (redirección fuera de la lista) o 504 (la fuente no respondió en 25 s).

La función corre en Estocolmo (`arn1`, `vercel.json`), con 60 s como mucho por petición.

En la recogida (`recogida/lector_delegado.py`) es solo otro transporte del descargador de siempre
(`recogida/descarga.py`): la pausa de 3 s entre peticiones al mismo sitio, los reintentos con espera
creciente, el tope diario de reintentos, el tope de 45 s de cada fuente y la comprobación de que lo
descargado es lo esperado (un canal RSS, una página HTML) son los mismos. Un 504 del lector, o una
respuesta sin `X-Lector`, cuenta como un error de red y se reintenta; un 400 o un 403 es un fallo de
la fuente. Si el lector falla, la fuente cuenta como fallida igual que una fuente directa (con su
pausa de 6 horas tras tres fallos seguidos) y la recogida sigue con las demás.

## Para qué fuentes

| Fuente | Desde | Por qué |
|---|---|---|
| `csn_sucesos` (Consejo de Seguridad Nuclear) | 27 de octubre de 2026 | csn.es respondió 403 a la dirección del servidor del 23 al 26 de octubre de 2026 ([fuentes_retiradas.md](fuentes_retiradas.md)). |

`mod_lv` (Ministerio de Defensa de Letonia) no se puede delegar: mod.gov.lv tampoco acepta la
conexión desde Vercel ni desde GitHub, y desde el 27 de octubre de 2026 tampoco mil.lv ni sargs.lv
sirven de sustitutas ([fuentes_retiradas.md](fuentes_retiradas.md)).

## Por qué no es un proxy abierto

- Solo descarga direcciones de su lista cerrada (`FUENTES` en `api/lector.ts`): para cada fuente,
  su dirección base (esquema y sitio exactos, sin puerto ni usuario) y los caminos admitidos,
  enteros y sin parámetros. Cualquier otra dirección se rechaza con 400 sin pedir nada.
- Las redirecciones se siguen a mano, como mucho 3, y cada salto tiene que estar también en la
  lista.
- Respeta el robots.txt de cada sitio para la identificación del observatorio
  (`EODI-bot/1.0 (+https://droneobservatory.eu)`, la misma que la recogida), con las mismas reglas
  que `urllib.robotparser`; el robots.txt se guarda una hora.
- Tiene un tope de 30 peticiones por minuto en cada instancia (la recogida pide unas pocas por
  hora).
- No lleva credenciales ni cookies: lo que descarga es público. Las respuestas no se guardan en la
  caché de Vercel (`no-store`).

## Cómo añadir una fuente

1. Comprobar que el bloqueo es a la dirección del servidor: desde el servidor la fuente no
   responde (o da 403) y desde la función desplegada, en una vista previa, responde 200 con lo
   esperado.
2. En `api/lector.ts`, añadir a `FUENTES` su `id`, su `base` y sus `caminos` (expresiones enteras
   con `^…$`; el `/robots.txt` también).
3. En `configuracion/fuentes_oficiales.json`, añadir `"delegada": true` a su entrada.
4. `web/tests/lector.test.ts` comprueba que las fuentes delegadas de la configuración y las de la
   lista son las mismas, y que la dirección de cada una se admite.

## Ensayos

`EODI_LECTOR_URL` cambia la dirección del lector (por ejemplo, la de una vista previa) y
`EODI_LECTOR_BYPASS` la clave de acceso de las vistas previas protegidas. En producción no se usa
ninguna de las dos, y la clave nunca va en un fichero.
