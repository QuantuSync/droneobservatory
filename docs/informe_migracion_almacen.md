# Informe: salida de Cloudflare del almacén público

2 de octubre de 2026. PR #57 (código, fusionado a las 21:44 UTC como 30ca7c3) y este informe.

## Qué pasó

El 2 de octubre de 2026 a las 20:07 UTC (22:07 en Madrid) Cloudflare suspendió la cuenta del
proyecto por una denuncia automática de «abuso de red» sin detalle, con dos medidas:
suspensión del usuario y bloqueo del tráfico de la cuenta. Desde entonces
`tiles.droneobservatory.eu` responde 403 con la página «Website Access Blocked» a todo:
teselas y `estado.json`.

Efecto en la web: carga y muestra los incidentes (vienen de Vercel), pero sin mapa de fondo, y
sin `estado.json` la barra de estado mide la antigüedad desde el último cambio de los datos
(«Actualizado hace 2 h» a las 20:17 UTC, cuando el último cambio de incidentes era de las
18:17), no desde la última recogida correcta.

El DNS del dominio sigue en Cloudflare y funciona; no se ha tocado, como tampoco el bucket,
los registros ni los tokens.

## La recogida

**No falló.** Diario del servidor desde las 20:00 UTC:

| Ejecución | Resultado | Publicó en `main` | `estado.json` |
| --- | --- | --- | --- |
| 20:17 (eodi-recogida) | correcta, 11 min 44 s | sí (2044230), Vercel desplegó a las 20:28 | subido a R2 por su API S3 |
| 21:17 (eodi-recogida) | correcta, 11 min 34 s | sí, desplegado | subido a R2 por su API S3 (última con el script anterior) |

Las demás unidades (`eodi-guerra`, `eodi-detalle`, `eodi-busqueda`, `eodi-deduccion`,
`eodi-trafico`) terminaron bien en todas sus ejecuciones desde las 20:00 UTC; ninguna unidad
quedó como fallida. La API S3 de R2 siguió aceptando `estado.json` tras la suspensión, pero
nadie podía leerlo: el bloqueo es del tráfico público.

**Por qué no podía bloquear la publicación**: la subida de `estado.json` ya iba en la salida
del script (`trap EXIT`), después de publicar, con su fallo como aviso. Se mantiene igual con
el almacén nuevo y ahora está probado también con avisos: `tests/test_servidor.py`
(`test_si_la_subida_falla_la_recogida_publica_igual`) comprueba que con la subida fallando la
recogida publica los datos en `main` y sale con su propio código. La subida en sí
(`recogida/almacen_publico.py`) reintenta con espera creciente (2 y 4 s), no pasa de 60 s,
no repite un 400/401/403/404 y nunca lanza.

No hizo falta ningún arreglo inmediato en el servidor.

## Ritmo de peticiones de los lectores (48 h)

Medido del 30 de septiembre a las 20:47 al 2 de octubre a las 20:47 UTC. El código no
registra cada petición: las cifras salen de los recuentos del diario multiplicados por lo que
pide el código en cada paso, o de los ficheros de caché escritos en esas horas (*derivadas*).
El diario de algunas unidades empieza más tarde por el reinicio del 2 de octubre a las 05:5x.

| Fuente (sitio) | Unidad | Pasos | Peticiones/h, media / pico | Reintentos | Errores | ¿Insiste ante un rechazo? |
| --- | --- | --- | --- | --- | --- | --- |
| t.me/kpszsu, t.me/mod_russia | recogida | 50 | 37 / 47 | ninguno visible | 0 | no |
| t.me/s, 37 canales, lectura | guerra | 26 | 40–60 (derivada) | — | 0 | no |
| t.me/s, histórico | guerra | 26 | ~775, pico ~800 hasta el 2-10 19:06; ahora casi 0 | — | sin 429 | no |
| **favt.gov.ru** (Rosaviatsia) | guerra | 26 | **8** (2 comprobaciones por paso × 4 intentos), ~190 al día | 3 por comprobación (5, 10, 20 s) | **502 siempre**; nunca una correcta | **sí** |
| **admin-smolensk.ru** | guerra | 26 | **1** desde el 2-10 18:50 | 0 (el 403 no se repite) | **403** | **sí**, cada hora |
| otras 12 webs oficiales de la capa de guerra | guerra | 26 | 1 al día (×4 con error de red) | 3 | 403 (5 webs), error de red (7) | no |
| data.gdeltproject.org, horaria | recogida | 50 | 10 / 16 (derivada) | 0 | 23 franjas aún no publicadas (404), reintentadas hasta 6 h | no |
| data.gdeltproject.org, búsqueda dirigida | busqueda | 9 | 376 / ~3070 (derivada: 18 048 ficheros, 16 días por hora) | — | 1 paso cortado por tiempo | no |
| 20 webs oficiales (23 fuentes) | recogida | 50 | 45–150 en total, ≤8 por sitio (derivada) | — | 1 fallo de descarga | no |
| forsvaret.dk, lvnl.nl, skyguide.ch (navegador automático) | detalle | 10 | 3 páginas cada 3 h con sus recursos | ninguno (un intento) | 0; responden 200 | **no** |
| parlamentos, investigaciones, UK Airprox Board | detalle | 10 | 20–35 (derivada) | — | 0 | no |
| firms.modaps.eosdis.nasa.gov | recogida | 11 descargas | ~1 | 1 (5 s) | 0 | no |
| historical-forecast-api.open-meteo.com | recogida y deducción | 61 | 139 / 362 (6683 ficheros de caché) | 2 | 0 | no |
| mesonet.agron.iastate.edu (IEM) | trafico | 26 | ~3 / 25 | 3 | un 429 tras 3 reintentos | no |
| github.com/adsblol (archivo) | trafico | 26 | 80–100 en los pasos de relleno | reanudaciones inmediatas | 0 | no |
| copernicus-dem-90m (S3) | deducción | 11 | 8 / 300 | 0 | 403/404 se tratan como mar | no |
| API del extractor | recogida | 50 | 2,2 / 16 (112 llamadas) | 1 (5 s) | 0 | no |

El lector con navegador automático no insiste: las tres webs le responden bien en todos los
pasos. Los dos que sí insistían están en la comprobación de la web oficial de los canales de
la capa de guerra (`recogida/canales_guerra.py`): tras un fallo se repetía en la lectura
siguiente, cada hora, y otra vez en el histórico de esa misma hora.

### Lo corregido

- **Comprobación de las webs oficiales**: tras fallos seguidos espera 1, 2, 4, 8 y 16 horas y
  después una vez al día; un rechazo (401, 403, 451 o página de bloqueo), un día entero. La
  lectura y el histórico de la misma hora ya no la repiten. favt.gov.ru pasa de ~190
  peticiones al día a 4 por día tras el primero (una comprobación diaria con sus 3
  reintentos), y admin-smolensk.ru de 24 a 1. Probado en `tests/test_canales_guerra.py`.
- **Tope diario de reintentos por sitio** en el descargador común
  (`recogida/reintentos.py`, `recogida/descarga.py`): 40 al día entre todas las unidades,
  anotados en `/home/eodi/datos/reintentos/<sitio>.json`. Pasado el tope, ese día cada
  petición a ese sitio se hace una vez. Dentro de una ejecución la espera ya era creciente
  (5, 10, 20 y 40 s, y lo que pida `Retry-After` hasta 300 s).
- **Reanudaciones del archivo de adsb.lol**: esperan 2, 4, 8, 16 y 32 s; antes eran
  inmediatas.

El IEM (un 429 en 48 h, ya con espera creciente y `Retry-After`) y Open-Meteo (tope de 300
llamadas por paso y caché) no reintentan de forma agresiva; quedan cubiertos por el tope
diario por sitio.

## Dónde está ahora cada cosa

| Qué | Antes | Ahora |
| --- | --- | --- |
| Teselas `europa-z14.pmtiles` | R2 `eodi-teselas`, `tiles.droneobservatory.eu` | Hetzner Object Storage `droneobservatory-almacen` (`nbg1`), <https://droneobservatory-almacen.nbg1.your-objectstorage.com/europa-z14.pmtiles> |
| `estado.json` | R2, `tiles.droneobservatory.eu/estado.json` | el mismo bucket, `/estado.json`, subido cada hora por la recogida |
| Dirección del almacén | escrita en la web, la vigilancia y el script del servidor | `configuracion/almacen_publico.json`, leída por todos |
| Credenciales de subida | derivadas del token de Cloudflare (`r2.env`) | `almacen.env` (Hetzner), en local y en el servidor |
| Glifos y sprites | la propia web (Vercel) | sin cambios |
| Política de contenido | `connect-src 'self' https://tiles.droneobservatory.eu` | `connect-src 'self' https://droneobservatory-almacen.nbg1.your-objectstorage.com`; el resto, igual |
| Vigilancia (`vigia-recogida`, `tests`) | `tiles.droneobservatory.eu/estado.json` | la dirección de la configuración |
| Copia de las teselas | solo en R2 | además, `C:\dev\eodi-teselas-copia\europa-z14.pmtiles` en este equipo |

La copia local se descargó de R2 por su API S3 (sigue respondiendo con la cuenta suspendida)
en 373 s y se verificó: 24 570 229 564 bytes, el mismo ETag multiparte que R2
(`b21fef7f0f34a39efd0a643f2930ce61-184`, partes de 128 MiB) y SHA-256
`393c9a0da1ef1c55c2338b61eeabaa840b3e96011a1ad5cc9c38ff6cc8a11c98`, que queda en la
configuración y que `preparar_almacen.py` comprueba mientras sube.

El disco del servidor (38 GB, 29 libres, con el histórico de adsb.lol creciendo unos 16 MB por
día procesado) no da para una copia intermedia de 24,6 GB: la copia va de R2 al almacén por
partes de 128 MiB en memoria. Desde el servidor, R2 se lee a 90 MB/s (256 MiB en 3 s): unos
5 minutos para todo el fichero.

La calificación de seguridad de la web no cambia: la política solo cambia el origen
permitido en `connect-src`; sigue sin `unsafe-inline`, `unsafe-eval`, comodines ni `blob:`.

## Coste

Hetzner Object Storage cobra un precio base por hora mientras haya al menos un bucket, con
1 TB de almacenamiento y 1 TB de salida incluidos al mes; la entrada, el tráfico interno de
eu-central y las llamadas a la API son gratis. Tarifa publicada desde el 1 de abril de 2026:
6,49 € al mes sin IVA, y 1 € por TB de salida por encima de la cuota.

Con el tamaño real (24,57 GB de teselas más 2 kB de estado: el 2,5 % del almacenamiento
incluido) el coste es el precio base, **6,49 € al mes sin IVA**, mientras la salida no pase
de 1 TB (unas 200 000 visitas al mes con unos 5 MB de teselas cada una). Anotado en
`docs/servidor.md`.

## Comprobación en producción

Con Playwright contra <https://droneobservatory.eu>, en escritorio (1440×900) y en 390×844,
antes y después del despliegue de 30ca7c3 (21:46 UTC):

| | Antes | Después |
| --- | --- | --- |
| Orígenes pedidos | el propio sitio y `tiles.droneobservatory.eu` | el propio sitio y `droneobservatory-almacen.nbg1.your-objectstorage.com` |
| Peticiones a dominios de Cloudflare | 2 (bloqueadas, 403) | ninguna |
| Violaciones de la política de contenido | ninguna | ninguna |
| `connect-src` servida | `'self' https://tiles.droneobservatory.eu` | `'self' https://droneobservatory-almacen.nbg1.your-objectstorage.com` |
| Incidentes servidos (`/datos/resumen.json`) | 467 | 467 |
| Mapa de fondo | no (403 de Cloudflare) | no, hasta preparar el bucket (pendiente 1) |
| Barra de estado | «Actualizado hace 2 h», desde el último cambio de datos | igual, hasta que el almacén tenga `estado.json` |

Capturas en [`capturas/`](capturas/): `almacen-cloudflare-bloqueado-*.png` (antes) y
`almacen-sin-credenciales-*.png` (después), cada una en `escritorio` y `390x844`.

## Pendientes y su arreglo

1. **Credenciales S3 de Hetzner.** La API de Hetzner Cloud no gestiona Object Storage (ni
   buckets ni credenciales; comprobado contra `api.hetzner.cloud` y `api.hetzner.com`):
   se generan en la consola. Arreglo: generarlas (proyecto EODI → *Security* →
   *S3 credentials* → *Generate credentials*), guardarlas en
   `%USERPROFILE%\.eodi\almacen.env` (`ALMACEN_ID=…`, `ALMACEN_SECRETO=…`) y ejecutar
   `bash servidor/preparar_almacen.sh`. Hasta entonces la web sigue sin mapa de fondo y la
   recogida deja cada hora «aviso: sin credenciales del almacén público» sin cambiar su
   resultado. No hace falta otro despliegue.
2. **Mapa de fondo y hora de actualización en producción.** Arreglo: tras el paso anterior,
   repetir la comprobación y las capturas de escritorio y 390×844 a varios zooms (inicial,
   fronteras y ciudades, nombres de calle) y comprobar que la barra mide desde
   `estado.json` («Actualizado hace N min», en verde).
3. **Bucket R2 y credenciales antiguas.** El bucket `eodi-teselas`, su objeto y
   `/home/eodi/.eodi/r2.env` siguen ahí. Arreglo: una vez comprobado el almacén nuevo, borrar
   `r2.env` del servidor y, cuando la cuenta de Cloudflare vuelva a estar operativa, decidir
   si se borra el bucket (24,6 GB por encima de los 10 GB gratuitos).
4. **El registro `tiles` del DNS** sigue apuntando a R2. Arreglo: borrarlo cuando la cuenta
   lo permita; ya nada lo usa.

### Sacar también el DNS de Cloudflare (sin hacer)

Hoy Cloudflare es el DNS autoritativo de `droneobservatory.eu`. Para salir:

1. Crear la zona en otro DNS (Hetzner DNS, que el CLI `hcloud zone` ya gestiona con el mismo
   token, o el del registrador) con los registros actuales: apex A `216.150.1.1` y
   `216.150.16.1` (Vercel), `www` CNAME `60d65e86c6f6416c.vercel-dns-016.com`, CAA del apex
   (`letsencrypt.org` y `pki.goog`; sin los socios que añade Cloudflare), y los TXT de
   verificación que haya. `tiles` no hace falta.
2. Bajar el TTL de los registros en Cloudflare unos días antes, si la cuenta lo permite.
3. Cambiar los servidores de nombres en el registrador del dominio a los del DNS nuevo; si
   hay DNSSEC, quitar antes el registro DS en el registrador y volver a firmarlo con el DNS
   nuevo.
4. Comprobar con `dig +trace` que responde el DNS nuevo, que Vercel sigue validando el
   dominio y que el certificado se renueva (la CAA tiene que admitir a la autoridad que use
   Vercel).
5. Revisar lo que dependía de Cloudflare: `Always Use HTTPS`, HSTS y TLS mínimo eran de la
   zona de `tiles`; la web ya los pone en sus propias cabeceras (`vercel.json`). En
   `docs/servidor.md` y en `reconstruir.sh` no queda nada que use el token de Cloudflare
   salvo la tabla de secretos.
