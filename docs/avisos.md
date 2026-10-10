# Avisos públicos con ntfy

Cualquiera recibe en el móvil o en el ordenador un aviso cuando hay un suceso importante con drones
en Europa, sin cuenta: con la aplicación ntfy (Android o iPhone) o en el navegador, desde el
servidor propio del observatorio, **https://ntfy.droneobservatory.eu**. Hay un canal de toda
Europa, `drones-europe`, y uno por país cubierto, `drones-<país en inglés>` (`drones-slovakia`,
`drones-poland`, `drones-united-kingdom`...): el nombre se entiende solo en la aplicación. La página
pública es `/avisos` (`/en/alerts`), y el botón «Avisos» de la cabecera del mapa abre un panel con
lo mismo.

## El panel «Avisos» y la página

El panel de la cabecera tiene tres pasos y nada más (`web/src/componentes/Avisos.tsx`):

1. **Qué recibirás**, en dos líneas.
2. **Qué quieres recibir**: un selector con «Toda Europa» por defecto y los países por orden
   alfabético, con un buscador que no distingue tildes ni mayúsculas.
3. **Suscríbete**: la web mira si es Android, iPhone (o iPad) u ordenador y enseña un solo botón,
   «Suscribirme», con las instrucciones de ese dispositivo, como mucho tres pasos:
   - Android: el botón abre la aplicación ntfy ya suscrita (`ntfy://ntfy.droneobservatory.eu/<canal>`),
     y debajo un enlace pequeño a Google Play.
   - iPhone: la documentación de ntfy solo describe los enlaces `ntfy://` en Android, así que el
     botón lleva a la App Store y los pasos traen el servidor y el canal con su botón «Copiar».
   - Ordenador: el botón abre el canal en el navegador, donde se permiten las notificaciones, y al
     lado sale un solo código QR del canal elegido, «Escanéalo con tu móvil». En el móvil nunca
     sale el QR.

Al pie, «Más ayuda» lleva a la página de texto, que sigue el mismo orden: los tres pasos, la
explicación detallada de cada dispositivo, qué se avisa y, al final, todos los canales con su
código QR (para poder imprimirla).

## Cómo funciona

1. Al final de cada recogida horaria (`servidor/recogida.sh`), y solo si la publicación en el
   almacén salió bien (así el enlace del aviso ya funciona), corre
   `python -m recogida.avisos enviar`. Su tope es de 120 s (`TOPE_AVISOS_SEGUNDOS`). Un fallo no
   cambia el código de la recogida.
2. `recogida/avisos.py` lee qué incidentes están publicados (`incidentes.geojson` e
   `incidentes_sin_ubicacion.json` en `/home/eodi/datos/publicacion`) y su documento interno en la
   base, solo leyendo (`/home/eodi/base/eodi.sqlite`).
3. Decide cuáles merecen aviso (apartado «Qué se avisa») y publica cada aviso en el tema `drones-europe`
   y en el de su país, en JSON, con el token del usuario `observatorio`.
4. Anota lo enviado, por incidente y tema, en una base propia:
   `/home/eodi/datos/avisos/avisos.sqlite`, con las tablas `avisos` y `activacion`. La base del
   observatorio no se toca. Un incidente se avisa **una sola vez**: las actualizaciones posteriores
   no avisan, y si ya salió a un país no sale a otro aunque cambie de país.
5. Si un envío falla, lo que sí salió queda anotado y lo demás se reintenta en la recogida
   siguiente, sin duplicar. El resultado de cada pasada queda en `/home/eodi/.eodi/avisos.json`
   (`fallos_seguidos`, `error`, `ultimo_envio`).
6. **Empieza desde la activación.** La primera pasada, sin la marca de `activacion`, anota todos
   los incidentes publicados como ya avisados y no envía nada. Se activó el 10 de octubre de 2026,
   antes de fusionar.

### Qué se avisa (y nada más)

- **Incidente nuevo en Europa** (país de `configuracion/avisos.json`) con estado `confirmado` o
  `atribuido`, o `notificado` con al menos una fuente de origen OFICIAL según el modelo:
  `es_autoridad` o fiabilidad A (autoridad, ministerio, gestor aeroportuario o de navegación
  aérea; `exportacion/procedencia.py`). Una noticia de prensa sin fuente oficial no se avisa.
- **Cierre o suspensión de un aeropuerto por drones**, con la misma regla de estado y fuente:
  tipo `interrupcion_aeroportuaria`, o cierre `si`. Solo cuando consta como incidente registrado.
  El detector de tráfico no crea incidentes, así que nunca avisa por sí solo.
- **Incursión desde la guerra en un país de la OTAN o en Moldavia**: tipo `incursion` unido a un
  ataque de la capa de guerra (`ataque`) o con `pruebas.entrada_exterior`. Va con prioridad alta.
- Solo los sucesos de las **últimas 72 horas** (`ventana_horas`). Un incidente antiguo que llega
  tarde al registro (un histórico, una nota atrasada) no es un aviso.
- La capa de guerra de Ucrania y Rusia **no avisa**: sus ataques no son incidentes de Europa.

Volumen esperado, medido sobre los datos reales del 10 de octubre de 2026: 32 avisos en 30 días
(20 incursiones con prioridad alta y 12 sobrevuelos), unos 1 al día.

### Aspecto de cada aviso

Sin emoticonos ni etiquetas. En Markdown (`"markdown": true`), que en texto plano también se lee.

- **Título**: `ESLOVAQUIA · Incursión confirmada`, con el país en mayúsculas y en español.
- **Cuerpo**: una línea en español (qué pasó, **lugar**, fecha con la hora local del país y la
  UTC, **estado** y fuente), una línea en blanco y la misma información en inglés, empezando por
  `SLOVAKIA · Confirmed incursion`.
- **Fuente**: la de más rango según el modelo (la autoridad antes que la prensa). De una
  declaración citada, el nombre de quien declara.
- **Icono**: `https://droneobservatory.eu/marca/aviso-256.png`, el logo de 256 px de
  `web/marca/generar_marca.py`.
- **Al tocarlo** se abre `https://droneobservatory.eu/EODI-…`. Esa dirección ya es el mapa con la
  ficha del incidente abierta: el botón «Ver en el mapa / View on map» lleva al mismo sitio.
- **Prioridad**: 4 (alta) para las incursiones desde la guerra en un país de la OTAN o en Moldavia;
  3 (normal) para lo demás. Nunca 5.

## Dónde está cada cosa

| Qué | Dónde |
| --- | --- |
| Canales (temas), nombres en español e inglés, zona horaria, OTAN | `configuracion/avisos.json` |
| Configuración de ntfy | `configuracion/ntfy/server.yml` → `/etc/ntfy/server.yml` |
| HTTPS (Caddy, Let's Encrypt automático) | `configuracion/ntfy/Caddyfile` → `/etc/caddy/Caddyfile` |
| Instalación, usuarios y permisos | `servidor/ntfy.sh` (como root; se puede repetir) |
| Topes de memoria | `/etc/systemd/system/{ntfy,caddy}.service.d/eodi.conf` (`NTFY_MEMORIA`, `CADDY_MEMORIA`: 300M) |
| Claves de las notificaciones del navegador | `/etc/ntfy/webpush.env` (640, root:ntfy; solo en el servidor) |
| Usuarios y permisos de ntfy | `/var/lib/ntfy/user.db` |
| Últimos mensajes (24 h) | `/var/cache/ntfy/cache.db` |
| Token de `observatorio` | `/home/eodi/.eodi/ntfy_observatorio` (600) |
| Lo ya avisado | `/home/eodi/datos/avisos/avisos.sqlite` |
| Estado para la vigilancia | `/home/eodi/.eodi/avisos.json` |
| Contraseña de `lucas` | Solo en el equipo de Lucas: `%USERPROFILE%\.eodi\ntfy_lucas.txt` |
| Avisos manuales | `C:\dev\avisos\enviar-aviso.ps1` y el acceso directo «Enviar aviso» del escritorio; copia sin credenciales en `herramientas/enviar-aviso.ps1` |
| Envío | `recogida/avisos.py` |
| Página y panel | `web/src/avisos.ts`, `web/src/texto/avisos.ts`, `web/src/componentes/Avisos.tsx`; los QR, `web/scripts/qr-avisos.ts` en el build |

Configuración de ntfy (2.29): `base-url https://ntfy.droneobservatory.eu`, escucha solo en
`127.0.0.1:2586` detrás de Caddy, `auth-default-access: deny-all`, sin registro de usuarios, sin
adjuntos (no hay carpeta de adjuntos), caché de 24 h y `upstream-base-url https://ntfy.sh`. Con
esto último, en iPhone el aviso llega al momento: a ntfy.sh solo pasa una señal de «hay un mensaje
nuevo» (el identificador y la huella del tema), sin el contenido. Límites por visitante: 60
suscripciones, ráfaga de 60 peticiones y 1 cada 5 s después, y 200 mensajes al día.

DNS (zona de Hetzner): `ntfy A 2.28.197.102` y `ntfy AAAA 2a01:4f8:1c1e:bafa::1`, creados con
`hcloud zone rrset create` y no con `import-zonefile` (la zona real tiene registros que no están en
el fichero, como el TXT `google-site-verification`). Cortafuegos de Hetzner (11710690) y del
servidor (nftables): 80 y 443 abiertos, además del 22.

## Los dos usuarios que publican

Nadie más puede escribir. Ningún tema admite publicación anónima.

| Usuario | Para qué | Permisos | Credencial |
| --- | --- | --- | --- |
| `observatorio` | Avisos automáticos de la recogida | Solo escritura en los temas públicos | Token en `/home/eodi/.eodi/ntfy_observatorio` (600); su contraseña es aleatoria y no se guarda |
| `lucas` | Avisos manuales, correcciones y comunicados | Lectura y escritura en los temas públicos; rol `user`, sin administración | Contraseña larga en `%USERPROFILE%\.eodi\ntfy_lucas.txt`, solo ahí |

Todo el mundo (`everyone`) tiene solo lectura en los temas públicos. Cualquier otro tema queda
cerrado.

## Cómo añadir un canal

1. Añadir el país a `configuracion/avisos.json` (`tema` `drones-` y el país en inglés, minúsculas y guiones, nombres
   `es` y `en`, `zona_horaria`, `otan`). Debe estar también en `configuracion/paises_europa.json`:
   lo comprueba `tests/test_avisos.py`.
2. Fusionar. La web vuelve a construirse con el canal, su QR y su sitio en la página.
3. En el servidor, rehacer los permisos con la lista nueva:
   `sudo bash /home/eodi/droneobservatory/servidor/ntfy.sh`. Sin `--clave-lucas` no cambia la
   contraseña de `lucas` y mantiene sus permisos.

## Cómo envía Lucas un aviso manual

**Con el acceso directo «Enviar aviso» del escritorio** (lo más sencillo). Ejecuta
`C:\dev\avisos\enviar-aviso.ps1`, que está fuera del repositorio; la copia versionada, sin ninguna
credencial, es `herramientas/enviar-aviso.ps1`. Junto al script va `avisos.json`, la lista de
canales (copia de `configuracion/avisos.json`; si se añade un país, copiarla de nuevo), y el icono
`aviso.ico`.

1. Doble clic en «Enviar aviso».
2. Contestar lo que pregunta: el país (Intro para «Toda Europa», o el número o el nombre del país),
   el título corto, el texto en español, el texto en inglés y si es una incursión en un país de la
   OTAN o en Moldavia (`s`: prioridad 4; `n`: prioridad 3).
3. Revisar la vista previa y escribir `s` para enviar (cualquier otra cosa no envía nada).

Sale a `drones-europe` y, si se eligió país, también a su canal. El título lleva el formato de los
automáticos (`ESLOVAQUIA · Qué pasa`, o `EUROPA · Qué pasa` si es para toda Europa); el mensaje,
en Markdown, el texto en español, el inglés y el enlace a droneobservatory.eu; al tocarlo se abre
la web; el icono es el logo del observatorio. La contraseña de `lucas` se lee de
`%USERPROFILE%\.eodi\ntfy_lucas.txt` y no se muestra nunca.

Para probarlo sin tocar los canales públicos: dar permiso temporal a `lucas` en un tema de pruebas
(`sudo -u ntfy ntfy access lucas prueba-xxxx read-write`), ejecutar
`powershell -ExecutionPolicy Bypass -File C:\dev\avisos\enviar-aviso.ps1 -Prueba prueba-xxxx` y
quitar el permiso (`sudo -u ntfy ntfy access --reset lucas prueba-xxxx`). Con `-Prueba` se niega a
enviar a un canal público. Probado así el 10 de octubre de 2026.

**Desde la aplicación o el navegador**:

1. Abrir https://ntfy.droneobservatory.eu (o la app ntfy) e iniciar sesión con el usuario `lucas`
   y la contraseña de `ntfy_lucas.txt`. En el navegador: «Iniciar sesión», arriba a la derecha. En
   Android: Ajustes → Gestionar usuarios → Añadir usuario, con el servidor
   `https://ntfy.droneobservatory.eu`. En iPhone: en Settings, el apartado de usuarios, con el
   mismo servidor.
2. Abrir el tema (`drones-europe`, y después el del país) y escribir el mensaje. En el navegador,
   la flecha junto a «Escriba un mensaje aquí» abre el formulario completo: título, prioridad,
   Markdown y enlace al pulsar.
3. Enviar el mismo aviso a `drones-europe` y al canal del país.

**Plantilla** (mismo formato que los automáticos):

- Título: `PAÍS · Qué pasa`, por ejemplo `POLONIA · Comunicado del observatorio` o
  `RUMANÍA · Corrección`.
- Prioridad: 3 (normal); 4 solo para una incursión confirmada en un país de la OTAN o en Moldavia.
  Nunca 5.
- Markdown activado. Mensaje:

```
Qué pasa, en una frase. **Lugar (País)**, 10/10/2026, 20:04 hora local (18:04 UTC). Estado: **confirmado**. Fuente: Ministerio de Defensa.

COUNTRY · What happens. Same sentence in English. **Place (Country)**, 10 Oct 2026, 20:04 local time (18:04 UTC). Status: **confirmed**. Source: Ministry of Defence.
```

- Al pulsar: `https://droneobservatory.eu/EODI-AAAA-NNNNN` si hay incidente.

**Desde una terminal** (con la contraseña en el fichero; el cuerpo, en un fichero UTF-8: el curl de
Windows manda otra codificación y ntfy lo tomaría por un adjunto, que están desactivados):

```
printf 'user = "lucas:%s"\n' "$(cat ~/.eodi/ntfy_lucas.txt)" | curl -K - \
  -H "Title: =?UTF-8?B?$(printf 'POLONIA · Comunicado' | base64 -w0)?=" \
  -H "Markdown: yes" -H "Priority: 3" -H "Click: https://droneobservatory.eu" \
  -H "Icon: https://droneobservatory.eu/marca/aviso-256.png" \
  --data-binary @aviso.txt https://ntfy.droneobservatory.eu/drones-europe
```

## Cambio de nombre de los canales (10 de octubre de 2026)

Los canales `general` y `<país>` pasaron a `drones-europe` y `drones-<país>`. Lo anotado en
`avisos.sqlite` con el nombre anterior cuenta como enviado al nuevo (`temas_anteriores` de
`configuracion/avisos.json`), así que ningún aviso se repite. Se publicó una vez en `general` un
aviso en español e inglés con el canal nuevo y el enlace a la página de avisos, y después
`servidor/ntfy.sh` rehízo los permisos solo con los temas nuevos: los antiguos ya no se pueden leer.
Quien siguiera suscrito a `general` debe suscribirse a `drones-europe`.

## Qué hacer si falla

La vigilancia (`recogida/vigilancia.py`, cada 5 minutos) añade a `salud.json` dos problemas, que
llegan por correo como los demás (workflow `vigia-recogida`):

- **`ntfy`**: `https://ntfy.droneobservatory.eu/v1/health` no responde `{"healthy":true}` en dos
  intentos.
- **`avisos`**: el envío ha fallado dos recogidas seguidas (`fallos_seguidos` ≥ 2 en
  `/home/eodi/.eodi/avisos.json`).

Pasos:

1. `systemctl status ntfy caddy` y `journalctl -u ntfy -u caddy -n 50`. Reiniciar con
   `sudo systemctl restart ntfy caddy`.
2. Certificado: `journalctl -u caddy | grep -i certificate`. Caddy lo renueva solo, unos 30 días
   antes de que caduque. Necesita los puertos 80 y 443 abiertos y el registro A de `ntfy`
   apuntando al servidor.
3. Envío: `cat /home/eodi/.eodi/avisos.json` y la línea «avisos:» del diario de la recogida
   (`journalctl -u eodi-recogida -n 80`). Un 401 o 403 es el token: comprobar
   `/home/eodi/.eodi/ntfy_observatorio`. Si se perdió, borrarlo y volver a ejecutar
   `servidor/ntfy.sh`, que crea otro.
4. Lo que no salió se reintenta solo en la recogida siguiente. Para ver qué saldría sin enviar
   nada: `sudo -u eodi /home/eodi/droneobservatory/.venv/bin/python -m recogida.avisos ensayo
   --publicacion /home/eodi/datos/publicacion --base /home/eodi/base/eodi.sqlite
   --datos /home/eodi/datos/avisos`.
5. Para probar un formato, `python -m recogida.avisos ejemplo --id EODI-… --tema <tema de pruebas>`.
   Se niega a publicar en un tema público. El tema de pruebas necesita permisos temporales: dar
   `sudo -u ntfy ntfy access observatorio <tema> write-only` y quitarlos después con
   `ntfy access --reset observatorio <tema>`.
6. Servidor nuevo (`reconstruir.sh`): ejecuta `ntfy.sh` con la contraseña de `lucas` y abre 80 y
   443 en el cortafuegos nuevo. Si cambia la IP, hay que poner la nueva en los registros A y AAAA de
   `ntfy`: `hcloud zone rrset set-records --record <ip> droneobservatory.eu ntfy A` (y lo mismo con
   `AAAA` y la IPv6). Sin la base de
   avisos anterior, la primera pasada vuelve a anotar todo como ya avisado: no se reenvía nada.
