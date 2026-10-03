# Informe: salida de Cloudflare del almacén público

2 de octubre de 2026. PR #57 (código, fusionado a las 21:44 UTC como 30ca7c3), PR #58 (este
informe), PR #60 (comprobación del estado) y puesta en marcha el 3 de octubre.

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

## Puesta en marcha (3 de octubre de 2026)

- **Bucket**: creado a las 02:27 UTC por `servidor/preparar_almacen.py` en `nbg1`, con
  política de solo lectura pública (`s3:GetObject`) y CORS para los dos orígenes de la web
  (GET, HEAD, cabecera `Range`).
- **Teselas**: subidas desde la copia verificada de este equipo en unos 10 minutos (40 MB/s).
  La vía desde R2 ya no responde: su API devuelve 401. En el bucket:
  24 570 229 564 bytes; la huella SHA-256 se comprobó mientras subía
  (`393c9a0d…11c98`); el ETag que calcula Hetzner, `b21fef7f0f34a39efd0a643f2930ce61-184`,
  es idéntico al de R2 y al de la copia local, confirmación independiente de que el contenido
  es el mismo byte a byte. HEAD 200 y petición Range 206 con la cabecera `PMTiles` y CORS
  para cada origen.
- **`servidor/preparar_almacen.sh`** desde `main`: llevó las credenciales al servidor
  (`/home/eodi/.eodi/almacen.env`, 600, `eodi`), vio las teselas ya copiadas, publicó el último
  `estado.json` y repitió las comprobaciones: «almacén público listo». La primera pasada se
  paró en la comprobación de `estado.json`: con lectura pública solo de objetos, Hetzner
  responde 403 (no 404) a un objeto que aún no existe. Corregido en el PR #60.
- **Recogida de las 03:17 UTC**: terminó bien y subió `estado.json` al almacén en el primer
  intento, sin ningún aviso («estado.json publicado en el almacén»).
- Las credenciales de R2 del servidor (`/home/eodi/.eodi/r2.env`) se borraron: ya no
  responden.

## Coste

Tarifa de Hetzner (la de su página de Object Storage, consultada el 3 de octubre de 2026; la
API de precios de Hetzner Cloud no incluye Object Storage): precio base de 6,49 € al mes sin
IVA, cobrado por horas con ese máximo al mes, con 1 TB de almacenamiento y 1 TB de salida
incluidos; por encima, 6,26 € por TB y mes de almacenamiento y 1 € por TB de salida. La
entrada, el tráfico interno de eu-central y las llamadas a la API no se cobran.

Con el tamaño real (24,57 GB de teselas más 2 kB de estado: el 2,5 % del almacenamiento
incluido) el coste es el precio base: **6,49 € al mes sin IVA, 7,85 € con el 21 % de IVA de la
cuenta**, mientras la salida no pase de 1 TB (unas 200 000 visitas al mes con unos 5 MB de
teselas cada una). La factura real se verá en la consola, en *Billing*, a final de mes.
Anotado en `docs/servidor.md`.

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
| Mapa de fondo | no (403 de Cloudflare) | no, hasta preparar el bucket |
| Barra de estado | «Actualizado hace 2 h», desde el último cambio de datos | igual, hasta que el almacén tenga `estado.json` |

Con el almacén en marcha (3 de octubre, 03:32 UTC), en escritorio y en 390×844:

| | Resultado |
| --- | --- |
| Mapa de fondo | sí, a tres zooms: países y fronteras (inicial), ciudades con sus nombres (medio), pueblos, ríos y nombres locales (cercano) |
| Barra de estado | «Actualizado ahora mismo · datos al día» en escritorio y «hace 1 min» en el teléfono, en verde: mide desde `estado.json` |
| Orígenes pedidos | el propio sitio y el almacén (64 peticiones Range en escritorio, 26 en el teléfono) |
| Peticiones a dominios de Cloudflare | ninguna |
| Violaciones de la política de contenido | ninguna |
| Errores | ninguno; una petición de tesela cancelada por el propio mapa al cambiar de zoom |

Capturas en [`capturas/`](capturas/): `almacen-cloudflare-bloqueado-*.png` (antes),
`almacen-sin-credenciales-*.png` (desplegado, sin bucket) y `almacen-inicial-*.png`,
`almacen-medio-*.png` y `almacen-cercano-*.png` (en marcha), cada una en `escritorio` y
`390x844`.

## Pendientes y su arreglo

Hechos el 3 de octubre: credenciales de Hetzner, bucket, teselas, `estado.json`, mapa y
hora en producción y borrado de `r2.env` en el servidor (apartado «Puesta en marcha»).

1. **Bucket R2 antiguo.** El bucket `eodi-teselas` y su objeto siguen en la cuenta de
   Cloudflare. Arreglo: cuando la cuenta vuelva a estar operativa, borrarlo (24,6 GB por
   encima de los 10 GB gratuitos) junto con `%USERPROFILE%\.eodi\r2_estado.env`.
2. **El registro `tiles` del DNS** sigue apuntando a R2. Arreglo: borrarlo cuando la cuenta
   lo permita; ya nada lo usa.
3. **Factura real del almacén.** Arreglo: a final de octubre, comparar en la consola de
   Hetzner (*Billing*) el cargo de Object Storage con los 6,49 € sin IVA previstos y anotarlo
   aquí y en `docs/servidor.md`.

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
