# Visitas y resumen diario

La web cuenta sus visitas con un contador propio, **GoatCounter**, en el servidor del observatorio
en Hetzner (Núremberg, Alemania), y cada mañana llega al móvil de Lucas un resumen privado por ntfy.
Todo funciona solo: nadie tiene que hacer nada para que se cuente, se copie o se envíe.

| | |
| --- | --- |
| Panel | **https://stats.droneobservatory.eu** (privado: pide usuario) |
| Usuario del panel | `lucasalanizpintos@gmail.com`, administrador, el único |
| Contraseña | Solo en el equipo de Lucas: `%USERPROFILE%\.eodi\goatcounter_lucas.txt` |
| Resumen diario | Tema privado `lucas-resumen` de https://ntfy.droneobservatory.eu, cada día a las 08:00 de Madrid |
| Contador en la web | `web/public/visitas.js` (servido desde el propio dominio) y `web/src/visitas.ts` |
| Servidor | `servidor/visitas.sh` (instalación), `servidor/visitas_resumen.sh` y `recogida/visitas.py` (resumen, muestras y copia) |

## Qué se cuenta

Cada página vista de droneobservatory.eu, en español y en inglés: el mapa, cada página de texto (las
listas, los países, la metodología, la ayuda, los avisos, privacidad…) y la 404. En el mapa, que es
una sola página, **abrir la ficha de un incidente cuenta como vista de su página** (`/EODI-…` o
`/en/EODI-…`, con el título de la ficha). Cada dirección cuenta una vez por carga: volver al mapa o
reabrir la misma ficha no suma. **Cambiar filtros no cuenta**: los filtros van en la búsqueda de la
dirección (`?estado=…`) y el contador envía solo la ruta.

De cada página vista llega lo mismo que envía el script oficial de GoatCounter (`count.js`): la ruta,
el título, la web de procedencia (solo con la primera página de cada carga), las campañas `utm_*`,
el tamaño de pantalla y si el navegador lo maneja un programa. GoatCounter añade el sistema y el
navegador (sin guardar la cabecera User-Agent) y el país.

**Qué no se cuenta ni se guarda:**

- **Ninguna cookie.** El envío sale sin credenciales (`credentials: "omit"`) y el contador no pone
  ninguna en la web. La única cookie de GoatCounter es la de iniciar sesión en el panel.
- **Ninguna dirección IP.** Comprobado en el código de GoatCounter 2.7 (`memstore.go`): usa la IP
  del visitante, en memoria, para saber el país y para reconocer la sesión durante 8 horas como
  mucho (la clave de sesión es «navegador + IP»), y en la base solo guarda un número de sesión
  aleatorio. **Pero al pararse vuelca esas sesiones abiertas a la tabla `store` de la base**, para
  seguirlas al arrancar, y no las borra hasta entonces. Por eso la unidad, justo después de cada
  parada (`ExecStopPost`), las borra con borrado seguro y vacía el diario WAL
  (`servidor/goatcounter_ajustes.py sin-sesiones`): ninguna IP queda en el disco ni en las copias.
  El coste: una visita en curso cuenta como nueva tras un reinicio. Caddy no escribe registro de
  accesos.
- Ni la región ni el idioma (desactivados en `servidor/goatcounter_ajustes.py`).
- **Bots**: GoatCounter descarta los agentes conocidos y los navegadores manejados por programas (el
  script envía el mismo indicador que `count.js`, y las pruebas automáticas con Playwright quedan
  fuera).
- **Solo producción**: el script cuenta solo en `droneobservatory.eu` (y `www.`). En las vistas
  previas de Vercel, en local y dentro de un marco no envía nada.

**Visitas y visitantes únicos.** GoatCounter guarda cada página vista (opción «Individual
pageviews», activada para el resumen) con su sesión. *Visitas* = páginas vistas; *visitantes únicos*
= sesiones distintas del día. Una sesión dura 8 horas: quien vuelve por la tarde tras venir por la
mañana cuenta dos veces. El panel de GoatCounter enseña sobre todo *visitantes* por página (una
persona cuenta una vez por página y sesión), así que sus cifras son algo menores que las *visitas*
del resumen.

**Si el contador no responde**, la web funciona igual: el envío no se espera (no hay `await`), sus
errores se callan y la página no depende de él. Lo comprueba `web/e2e/visitas.spec.ts` con el
contador caído y con el script bloqueado.

**Política de seguridad (CSP).** El script se sirve desde el propio dominio (`/visitas.js`), así que
`script-src` sigue en `'self'`. Solo cambia `connect-src`, que añade `https://stats.droneobservatory.eu`
(`vercel.json`; lo comprueban `tests/test_almacen_publico.py` y `web/tests/seguridad.test.ts`).

La página de privacidad (`/privacidad`, `/en/privacy`) lo explica en una frase: se cuentan las
visitas de forma anónima, sin cookies ni direcciones IP, con un contador propio en un servidor de la
UE.

## El panel

https://stats.droneobservatory.eu → correo `lucasalanizpintos@gmail.com` y la contraseña de
`%USERPROFILE%\.eodi\goatcounter_lucas.txt`. Horas en hora de Madrid. Nada es público: sin usuario,
la dirección lleva a la entrada (303) y la API responde 401. La vigilancia lo comprueba cada 5
minutos (problema `visitas_privadas`). Los buscadores no lo indexan (`X-Robots-Tag: noindex,
nofollow`).

Para cambiar la contraseña: escribir la nueva en `goatcounter_lucas.txt` (sin salto de línea al
final) y, desde Git Bash en la raíz del clon:

```
tr -d '\r\n' < ~/.eodi/goatcounter_lucas.txt | ssh -i ~/.eodi/servidor_ssh \
  -o UserKnownHostsFile=~/.eodi/servidor_known_hosts operador@2.28.197.102 \
  sudo bash /home/eodi/droneobservatory/servidor/visitas.sh --clave-lucas
```

## Excluir las visitas propias

Con el mecanismo de GoatCounter: abrir **https://droneobservatory.eu/#toggle-goatcounter** en el
navegador que se quiere excluir. Sale el aviso «Este navegador ya no cuenta en las visitas» y queda
guardado en ese navegador (`skipgc` = `t` en su almacenamiento local). Abrir la misma dirección otra
vez lo vuelve a activar («Este navegador vuelve a contar»).

- **Móvil**: abrir la dirección en cada navegador que se use (Chrome y Safari por separado) y
  aceptar el aviso.
- **Ordenador**: lo mismo en cada navegador (Chrome, Edge, Firefox…).
- Se pierde si se borran los datos del sitio en ese navegador; en una ventana privada no vale.

## Suscriptores de ntfy

Lo que ntfy deja saber, mirado en su código y en sus métricas internas (`enable-metrics`, solo en
`127.0.0.1:9095`, sin pasar por Caddy):

- **En total**: `ntfy_subscribers_total`, los suscriptores **conectados en ese momento** (cada
  suscripción abierta a un tema). Cuenta las aplicaciones de Android con entrega al momento y las
  pestañas del navegador abiertas. **No cuenta los iPhone**, que no tienen conexión abierta: reciben
  la señal por ntfy.sh y piden el mensaje entonces. `recogida/visitas.py` toma una muestra cada 5
  minutos (`/home/eodi/datos/visitas/muestras_ntfy.jsonl`, 40 días).
- **Por canal**: ntfy no da suscriptores por tema. Lo único por canal que guarda son las
  notificaciones del navegador activadas (tabla `subscription_topic` de
  `/var/cache/ntfy/webpush.db`), que lee como root `servidor/ntfy_suscriptores.py` antes de cada
  pasada, solo los recuentos (`ntfy_navegador.json`). El 11 de octubre de 2026 había 1 (en
  `general`, el canal antiguo).
- No se cuentan direcciones IP ni se guardan registros de acceso de ntfy para esto.

El resumen da, por eso, los conectados al cierre del día, el máximo del día y el cambio respecto al
cierre del día anterior, y los canales con más notificaciones del navegador.

## El resumen diario

Cada día a las **08:00 de Madrid** (con el horario de verano: se calcula en `Europe/Madrid`), un
aviso privado con el título **«EODI · Resumen diario»**, en español, sin emoticonos, con los datos
del día anterior de 00:00 a 24:00 de Madrid. Al tocarlo se abre el panel de GoatCounter.

Lleva:

- visitas y visitantes únicos, con la cifra del día anterior y la media de los 7 días anteriores, y
  el cambio en porcentaje;
- las 5 páginas más vistas;
- las 5 procedencias principales (LinkedIn, Google, Directo…; la de la primera página de cada
  visitante);
- los 5 países principales;
- el reparto entre móvil y ordenador (por visitante: Android, iOS o pantalla de menos de 768 px es
  móvil);
- suscriptores de ntfy (apartado anterior) y avisos enviados ese día (`avisos.sqlite`);
- incidentes nuevos publicados ese día, con los titulares de hasta 5 (la primera vez que cada uno
  aparece en la web, anotada en `/home/eodi/datos/visitas/publicados.json`; para los que ya estaban
  al empezar, su alta en la base);
- recogidas correctas, con avisos y fallidas (diario de `eodi-recogida`) y los problemas abiertos de
  la vigilancia (`salud.json`).

Ejemplo (la forma exacta; las cifras son de muestra):

```
EODI · Resumen diario

Datos del lunes 12 de octubre de 2026 (hora de Madrid).

VISITAS
  Visitas: 1.284 (día anterior 1.102, +17 %; media de 7 días 968,4, +33 %)
  Visitantes únicos: 412 (día anterior 377, +9 %; media de 7 días 301,6, +37 %)

Páginas más vistas
  1. /: 498
  2. /EODI-2026-00509: 121
  3. /en: 96
  4. /avisos: 44
  5. /metodologia: 31

Procedencias
  1. Directo: 171
  2. LinkedIn: 118
  3. Google: 76
  4. X: 21
  5. elpais.com: 9

Países
  1. España: 188
  2. Polonia: 54
  3. Alemania: 39
  4. Estados Unidos: 22
  5. Francia: 18

Dispositivos: móvil 64 % (264), ordenador 36 % (148)

AVISOS (ntfy)
  Suscriptores conectados al cierre: 37 (+5 respecto al día anterior; máximo del día 41)
  Con notificaciones en el navegador: 6 (drones-europe 4, drones-poland 2)
  Avisos enviados: 4 mensajes de 2 incidentes

INCIDENTES NUEVOS PUBLICADOS: 2
  EODI-2026-00510: Drones sobre la base aérea de ...
  EODI-2026-00511: Cierre del aeropuerto de ...

SISTEMA
  Recogidas: 24 correctas (1 con avisos), 0 fallidas
  Vigilancia: ningún problema abierto
```

**Suscribirse en la aplicación ntfy** (una vez, en el móvil de Lucas):

- **Android**: Ajustes → Gestionar usuarios → Añadir usuario: servidor
  `https://ntfy.droneobservatory.eu`, usuario `lucas`, la contraseña de
  `%USERPROFILE%\.eodi\ntfy_lucas.txt`. Después, en la pantalla principal, «+» → tema
  `lucas-resumen`, marcar «Usar otro servidor» y poner `https://ntfy.droneobservatory.eu` →
  Suscribirse.
- **iPhone**: Settings → Users (o «Manage users») → añadir el mismo servidor, usuario y contraseña.
  Después «+» → tema `lucas-resumen`, «Use another server» con `https://ntfy.droneobservatory.eu` →
  Subscribe.

Solo lo lee `lucas` y solo publica `observatorio` (`servidor/ntfy.sh`); `auth-default-access:
deny-all` cierra el resto: sin usuario, leer o publicar en `lucas-resumen` da 403, y `lucas` tampoco
puede publicar en él (comprobado el 11 de octubre de 2026). Con iPhone, a ntfy.sh solo pasa la señal
de «hay un mensaje nuevo», sin el contenido (`upstream-base-url`).

**Cómo se envía.** `eodi-visitas.timer` lanza `eodi-visitas.service` cada 5 minutos (`servidor/visitas_resumen.sh`
→ `python -m recogida.visitas pasada`, como `eodi`, con los grupos `goatcounter` y
`systemd-journal`, 300 MB como mucho). A partir de las 08:00 de Madrid, si el resumen del día
anterior no ha salido, lo compone y lo publica con el token de `observatorio`, con tres intentos (2
y 4 s de espera). Si falla, queda anotado en `/home/eodi/.eodi/visitas.json` (`resumen.error`,
`fallos_seguidos`) y la pasada siguiente, 5 minutos después, lo repite. Sale una sola vez por día.

## Copias

- **Copia de la base de visitas**, cada hora, en la misma unidad: copia coherente con la API de
  copia de SQLite (solo lectura), comprimida, al bucket privado `droneobservatory-archivo`:
  `visitas/ultima.sqlite.gz` (sustituida cuando cambia) y la primera de cada día en
  `visitas/diaria/AAAA-MM-DD.sqlite.gz`, que no se sobrescribe.
- **Segunda copia en Helsinki**: `eodi-replica` lleva todo el bucket del archivo, cifrado con la
  clave pública age, a `droneobservatory-replica` (`archivo/visitas/….age`; `almacen/replica.py`
  sustituye `visitas/ultima.sqlite.gz` cuando cambia).
- **Copias de Hetzner** del servidor entero: también tienen `/var/lib/goatcounter`.

**Restaurar** (por ejemplo, en un servidor nuevo):

```
sudo -u eodi bash /home/eodi/droneobservatory/servidor/visitas_resumen.sh restaurar \
  --destino /home/eodi/base/trabajo/visitas.sqlite3          # o --objeto visitas/diaria/AAAA-MM-DD.sqlite.gz
sudo systemctl stop goatcounter
sudo install -m 640 -o goatcounter -g goatcounter /home/eodi/base/trabajo/visitas.sqlite3 \
  /var/lib/goatcounter/goatcounter.sqlite3
sudo rm -f /var/lib/goatcounter/goatcounter.sqlite3-wal /var/lib/goatcounter/goatcounter.sqlite3-shm
sudo systemctl start goatcounter
```

`restaurar` comprueba la huella y la integridad de la base. Desde Helsinki (si Núremberg no
responde): `replica.sh restaurar --objeto archivo/visitas/ultima.sqlite.gz.age --destino …` y después
`gunzip`.

## Vigilancia

En `salud.json` (`recogida/vigilancia.py`), con correo como el resto (workflow `vigia-recogida`):

| Problema | Cuándo |
| --- | --- |
| `goatcounter` | https://stats.droneobservatory.eu/status no responde en dos intentos |
| `resumen` | A las 09:00 de Madrid no ha salido el resumen del día anterior (con el último error) |
| `copia_visitas` | La última copia de la base de visitas tiene más de 3 horas |
| `visitas_privadas` | El panel, su API o `lucas-resumen` responden sin usuario |

## Qué hacer si falla

- **El contador no responde** (`goatcounter`): `systemctl status goatcounter caddy`,
  `journalctl -u goatcounter -n 50`; `sudo systemctl restart goatcounter`. Certificado: `journalctl
  -u caddy | grep -i stats`. La web sigue funcionando; las visitas de ese rato se pierden.
- **El resumen no sale** (`resumen`): `sudo cat /home/eodi/.eodi/visitas.json` y `journalctl -u
  eodi-visitas -n 40`. Un 401 o 403 es el token de `observatorio` o sus permisos en `lucas-resumen`:
  `sudo bash /home/eodi/droneobservatory/servidor/ntfy.sh` los rehace. Se reintenta solo cada 5
  minutos. Para ver el texto sin enviar nada:
  `sudo -u eodi bash /home/eodi/droneobservatory/servidor/visitas_resumen.sh resumen --dia AAAA-MM-DD --ensayo`.
- **Probar el envío sin tocar `lucas-resumen`**: dar permiso temporal en un tema de pruebas
  (`sudo -u ntfy ntfy access observatorio prueba-xxxx write-only` y `sudo -u ntfy ntfy access lucas
  prueba-xxxx read-only`), `visitas_resumen.sh resumen --dia AAAA-MM-DD --tema prueba-xxxx` (se niega
  a enviar a `lucas-resumen` o a un canal público) y quitar los permisos (`ntfy access --reset
  observatorio prueba-xxxx` y lo mismo con `lucas`). Hecho así el 11 de octubre de 2026.
- **La copia no se hace** (`copia_visitas`): `visitas.json` → `copia.error`. Suele ser el almacén o
  las credenciales (`almacen.env`).
- **Algo privado ha quedado abierto** (`visitas_privadas`): `python -m recogida.visitas comprobar`
  dice qué. Panel: en la base, `sites.settings` → `"public":"private"` (`visitas.sh` lo vuelve a
  poner). Tema: `servidor/ntfy.sh` rehace los permisos.
- **Servidor nuevo**: `reconstruir.sh` ejecuta `visitas.sh` con la contraseña de
  `goatcounter_lucas.txt` (después de `ntfy.sh`); luego se restaura la base de visitas (apartado
  «Copias»). Si cambia la IP, poner la nueva en los registros A y AAAA de `stats`, como los de `ntfy`
  (`hcloud zone rrset set-records --record <ip> droneobservatory.eu stats A`).
- **Actualizar GoatCounter**: cambiar `GOATCOUNTER_VERSION` y `GOATCOUNTER_SHA256` en
  `servidor/configuracion.sh` (la huella la publica la propia versión en GitHub), fusionar y
  ejecutar `sudo bash /home/eodi/droneobservatory/servidor/visitas.sh`.

## Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| GoatCounter | `/usr/local/bin/goatcounter` (v2.7.0), unidad `goatcounter.service` (usuario `goatcounter`, `127.0.0.1:8081`, 300 MB) |
| Base de visitas | `/var/lib/goatcounter/goatcounter.sqlite3` (750/640, `goatcounter`; `eodi` la lee por el grupo) |
| Ajustes del sitio y borrado de sesiones | `servidor/goatcounter_ajustes.py` → `/usr/local/libexec/eodi/` |
| HTTPS | `configuracion/ntfy/Caddyfile` (bloque `stats.droneobservatory.eu`) |
| DNS | `stats A 2.28.197.102` y `stats AAAA 2a01:4f8:1c1e:bafa::1`, creados uno a uno con `hcloud zone rrset create` |
| Métricas de ntfy | `configuracion/ntfy/server.yml` (`127.0.0.1:9095`) |
| Muestras, publicados, recuento por canal | `/home/eodi/datos/visitas/` |
| Estado del resumen y de la copia | `/home/eodi/.eodi/visitas.json` |
| Contraseña del panel | Solo `%USERPROFILE%\.eodi\goatcounter_lucas.txt` |
