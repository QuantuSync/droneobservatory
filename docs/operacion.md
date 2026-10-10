# Operación del observatorio

Qué mirar y qué hacer, en lenguaje llano y con las órdenes exactas. El detalle de cada pieza está
en [`servidor.md`](servidor.md); cómo se fusiona un cambio, en [`fusiones.md`](fusiones.md).

Todas las órdenes «en el servidor» se escriben después de entrar en él, desde Git Bash en el
equipo que guarda las credenciales (`%USERPROFILE%\.eodi\`):

```
ssh -i ~/.eodi/servidor_ssh -o UserKnownHostsFile=~/.eodi/servidor_known_hosts operador@2.28.197.102
```

## Cómo ver si todo va bien

**Sin entrar en ningún sitio.** El servidor publica cada 5 minutos su salud en
<https://droneobservatory-almacen.nbg1.your-objectstorage.com/salud.json>: la última recogida y
la última publicación, la captura del seguimiento, las copias (base, archivo y segunda copia en
Helsinki), el disco, los `problemas` y los `avisos`. Si `problemas` está vacío y `generado` es de
hace menos de 10 minutos, todo va bien.

**Los avisos llegan solos.** El workflow `vigia-recogida` lee ese fichero cada 10 minutos (y
`estado.json` y `directo.json`). Si hay un problema:

- abre una incidencia en el repositorio con el problema y dónde mirar (GitHub manda el aviso por
  correo a quien vigila el repositorio);
- el propio trabajo falla, y GitHub manda al dueño el correo «Run failed: vigia-recogida»: al
  aparecer el problema y después una vez por hora mientras siga;
- la incidencia se cierra sola cuando se arregla.

Problemas que avisan: datos publicados con más de 2 horas, recogida que termina con un código
distinto de 0 y 2, captura del seguimiento sin recibir nada en 10 minutos, archivo de alertas de alerts.in.ua sin
respuesta correcta de la API en 15 minutos o con la API respondiendo 401 o 403, copia de la base o del
archivo con más de 2 horas, segunda copia con más de 3 horas, copia pública de reserva de Helsinki
sin estar al día más de 30 minutos, disco por encima del 75 %, servidor
sin dar señales (salud.json con más de 20 minutos), exportación semanal fallida o con más de 8
días, detección en directo parada más de media hora, paso de la base a solo disco fallido,
versión citable de los datos del mes sin generar (pasadas las 06:00 UTC del día 1) o una
publicada que ha cambiado.

Avisos que se ven pero no son fallo: la recogida terminó con avisos (código 2: por ejemplo, el
tope de 240 s de las fuentes oficiales) y los incidentes que retiene la barrera de titulares. Se
ven en el resumen de cada ejecución del vigía y en `salud.json`; los identificadores, solo en el
diario del servidor: `journalctl -u eodi-vigilancia -n 20`.

**Probar que el aviso llega** (alarma de mentira): en GitHub, *Actions* → *vigia-recogida* →
*Run workflow* con «Alarma de prueba» marcada, o `gh workflow run vigia-recogida.yml -f
prueba=true`. Abre la incidencia «Alarma de prueba de la vigilancia» y el trabajo falla; la
incidencia se cierra a mano.

**En el servidor**, de un vistazo:

```
systemctl list-timers 'eodi-*'                  # cuándo toca cada trabajo
systemctl --failed                              # unidades en fallo (la recogida con avisos sale aquí)
journalctl -u eodi-recogida -n 40               # la última recogida
sudo systemctl start eodi-vigilancia.service && journalctl -u eodi-vigilancia -n 10
df -h /
```

## Si la recogida falla

1. Mirar por qué: `journalctl -u eodi-recogida -n 120`. Un código 2 es «con avisos» y publica
   igual; cualquier otro no publica.
2. Si es algo pasajero (una fuente caída, la red), la siguiente recogida (minuto 17) lo arregla
   sola. Para lanzar una ya, fuera de los minutos 12 a 40: `sudo systemctl start
   eodi-recogida.service`.
3. Si es un fallo del código tras una fusión: volver al commit anterior de `main` con un PR que
   lo revierta (nunca un push forzado) y comprobar las dos recogidas siguientes.
4. Si la base no abre: apartado «Si hay que restaurar la base».

## Si cae el almacén principal

El almacén público de Núremberg (`droneobservatory-almacen`) guarda el mapa de fondo, los datos
publicados y las capas que pide la web. Desde el 9 de octubre de 2026 tiene una copia pública de
reserva en Helsinki (`droneobservatory-reserva`), con los mismos objetos y cabeceras, que el
servidor pone al día cada 2 minutos y tras cada publicación (`eodi-reserva`, `almacen/reserva.py`).

**Qué pasa solo, sin hacer nada:**

- La web no pide al almacén directamente: lo pide a su dominio (`/almacen/…`) y lo sirve la función
  `api/almacen.ts` con la caché de Vercel delante. Si Núremberg no contesta en 3 segundos o da un
  error, la función lo pide a Helsinki y durante un minuto ya no prueba Núremberg. Lo que ya está en
  la caché se sigue sirviendo aunque fallen los dos (hasta 7 días).
- Si la propia función fallara, el navegador pide a Helsinki directamente (a los 15 segundos sin
  respuesta o con el primer error).
- El build de la web baja los datos de Helsinki si Núremberg no responde.
- La recogida sigue, pero no puede publicar (sube a Núremberg): la web se queda con los últimos
  datos publicados y la barra de arriba dice de cuándo son. Al volver Núremberg, la recogida
  siguiente publica y la reserva se pone al día sola.
- La vigilancia avisa: `salud.json` (que está en Núremberg) deja de responder y llega el correo
  «Run failed: vigia-recogida» con la incidencia.

**Cómo saber si es el almacén:**

```
curl -s -o /dev/null -w "%{http_code} %{time_total}s " https://droneobservatory-almacen.nbg1.your-objectstorage.com/estado.json
curl -s -o /dev/null -w "%{http_code} %{time_total}s " https://droneobservatory-reserva.hel1.your-objectstorage.com/estado.json
curl -sI https://droneobservatory.eu/almacen/estado.json | grep -i "x-almacen\|x-vercel-cache"
```

`x-almacen: reserva` dice que la web ya está sirviendo desde Helsinki. El estado del servicio de
Hetzner está en <https://status.hetzner.com/>.

**Si la caída dura horas** y hace falta que los datos nuevos lleguen a la web: cambiar los papeles,
con un PR (y su ensayo) que intercambie en `configuracion/almacen_publico.json` el bloque principal
(`ubicacion`, `punto_s3`, `bucket`, `publico`) con el de `reserva`, y en `api/almacen.ts` el orden
de `ORIGENES` (un test comprueba que coinciden). La recogida publica entonces en Helsinki, la web lo
pide primero allí y la copia de reserva va de Helsinki a Núremberg. Al volver Núremberg, se deshace
con otro PR igual. Nunca a mano en el servidor: la copia de reserva copiaría en sentido contrario.

## Si cae Vercel

Vercel sirve la web entera: las páginas, los datos de `/datos/…`, la función del almacén y la
tarea programada de la vigilancia. Si Vercel cae, `droneobservatory.eu` no carga y no hay nada que
hacer de nuestro lado; el estado del servicio está en <https://www.vercel-status.com/>.

- La recogida sigue cada hora y publica en el almacén; la vigilancia del servidor también. Cuando
  Vercel vuelve, el gancho de la recogida siguiente reconstruye la web con los datos al día (o,
  para no esperar, en el servidor:
  `sudo -u eodi sh -c 'curl -s -X POST "$(cat /home/eodi/.eodi/vercel_gancho)"'`).
- Mientras tanto, los datos siguen a mano en las direcciones públicas de los dos almacenes, para
  quien los integre en otro sistema: `…/publicacion/manifiesto.json`, `…/publicacion/incidentes.geojson`,
  `…/publicacion/ucrania.json`, `…/publicacion/prevision.json` y las versiones mensuales en
  `…/versiones/AAAA-MM/`, con `…` = `https://droneobservatory-almacen.nbg1.your-objectstorage.com` o
  `https://droneobservatory-reserva.hel1.your-objectstorage.com`.
- El aviso de la vigilancia depende en parte de Vercel (la tarea que lanza el workflow): con Vercel
  caído, el aviso llega cuando GitHub ejecute su programación, o al mirar `salud.json`.

## Cómo comprobar la copia de Helsinki

**Sin entrar en ningún sitio**: los dos manifiestos tienen que ser iguales (como mucho, 2 minutos
de diferencia tras una publicación):

```
for a in droneobservatory-almacen.nbg1 droneobservatory-reserva.hel1; do
  curl -s https://$a.your-objectstorage.com/publicacion/manifiesto.json | sha256sum
done
```

`salud.json` dice en `copias.reserva_web` la última vez que la reserva estaba entera y al día;
si pasa de 30 minutos, la vigilancia abre la incidencia «reserva».

**En el servidor**:

```
systemctl list-timers eodi-reserva.timer
journalctl -u eodi-reserva -n 20                       # «copiados N, borrados N, pendientes 0…»
sudo -u eodi cat /home/eodi/.eodi/reserva.json        # última pasada, última vez al día, pendientes
sudo -u eodi bash /home/eodi/droneobservatory/servidor/reserva.sh comprobar   # compara sin copiar
sudo systemctl start eodi-reserva.service             # una pasada ya
```

**El mapa de fondo** (24,6 GB) no lo copia la pasada de cada 2 minutos: se sube una vez con
`servidor/preparar_almacen.py --reserva --desde-principal` (como trabajo de sesión, unos 50
minutos), que comprueba la huella SHA-256 mientras sube. La pasada solo comprueba que está con el
mismo tamaño y, si falta, lo dice en `grandes_pendientes`. Si un día se cambia el mapa de fondo
(otro nombre en `objetos.teselas`), hay que subirlo a los dos almacenes antes de fusionar el cambio.

**Prueba de que la web aguanta sin el principal**: informe_robustez.md, «Prueba de caída».

## Si la web no se actualiza

La web se reconstruye en Vercel cada vez que la recogida publica datos nuevos (gancho de
despliegue) y con cada fusión en `main`.

1. ¿Publicó la recogida? En `salud.json`, `recogida.ultima_publicacion`; en el servidor,
   `journalctl -u eodi-recogida -n 40 | grep -i publica`.
2. ¿Están los datos en el almacén?
   `curl -s https://droneobservatory-almacen.nbg1.your-objectstorage.com/publicacion/manifiesto.json | head`.
3. ¿Construyó Vercel? En el panel de Vercel, proyecto `droneobservatory`, *Deployments*. Si la
   construcción falló porque el almacén no respondía, la web anterior sigue publicada y la
   siguiente recogida lo vuelve a pedir. Para pedirlo a mano, en el servidor:
   `sudo -u eodi sh -c 'curl -s -X POST "$(cat /home/eodi/.eodi/vercel_gancho)"'`.

## Si la versión citable del mes no se genera

```
journalctl -u eodi-versiones.service -n 40
sudo -u eodi cat /home/eodi/.eodi/versiones.json        # «fallo» y «problemas»
sudo systemctl start eodi-versiones.service              # otra vez: genera la que falte
```

Si falló porque la web no respondía o los datos cambiaban mientras se bajaban, basta con lanzarla
otra vez. Una versión publicada no se toca nunca: si la comprobación dice que una ha cambiado o
falta, se restaura desde la segunda copia de Helsinki (`servidor/replica.sh listar | grep
versiones/`), con los mismos ficheros y las huellas de su `metadatos.json`.

## Si la captura del seguimiento se para

```
systemctl status eodi-seguimiento.service
journalctl -u eodi-seguimiento.service -n 40
sudo systemctl restart eodi-seguimiento.service      # el hueco queda anotado
```

Lo que NEPTUN emite mientras el servicio está parado se pierde: relanzarlo cuanto antes. El
archivo ya guardado está a salvo: sube cada hora a la copia privada y a la segunda copia.

## Si el archivo de alertas se para

```
systemctl status eodi-alertas.service
journalctl -u eodi-alertas.service -n 40
sudo -u eodi cat /home/eodi/.eodi/alertas.json         # última respuesta, último error
sudo systemctl restart eodi-alertas.service
```

- **401 o 403** (`error_autorizacion` en `alertas.json`): el token ya no vale o la IP del servidor
  está bloqueada. Pedir un token nuevo en <https://devs.alerts.in.ua/>, dejarlo en
  `%USERPROFILE%\.eodi\alerts_in_ua_token.txt` y en el servidor:
  `tr -d '\r\n' < ~/.eodi/alerts_in_ua_token.txt | ssh … 'sudo -u eodi sh -c "umask 077; cat > /home/eodi/.eodi/alerts_in_ua_token"'`
  y reiniciar la unidad.
- **Otro fallo**: el servicio reintenta solo con esperas crecientes. Lo que no se vea de las
  activas mientras esté parado lo rellena el histórico del día siguiente (el último mes), salvo la
  lista de amenazas, que solo dan las activas.

## Si los avisos de ntfy fallan

La vigilancia avisa con el problema `ntfy` (https://ntfy.droneobservatory.eu/v1/health no
responde) o `avisos` (el envío ha fallado dos recogidas seguidas). Lo que no salió se reintenta
solo en la recogida siguiente, sin duplicar lo ya enviado.

1. `systemctl status ntfy caddy`; `journalctl -u ntfy -u caddy -n 50`; si hace falta,
   `sudo systemctl restart ntfy caddy`.
2. `cat /home/eodi/.eodi/avisos.json` y la línea «avisos:» de `journalctl -u eodi-recogida`.
   Un 401 o 403 es el token de `observatorio`: borrar `/home/eodi/.eodi/ntfy_observatorio` y
   ejecutar `sudo bash /home/eodi/droneobservatory/servidor/ntfy.sh`, que crea otro.
3. Certificado: Caddy lo renueva solo; necesita 80 y 443 abiertos y el registro A de `ntfy`.

Todo lo demás (qué se avisa, los dos usuarios, cómo añadir un canal y cómo enviar un aviso a
mano) está en [avisos.md](avisos.md).

## Si el disco se llena

El aviso llega al 75 %. Ver qué ocupa: `sudo du -sh /home/eodi/* /home/eodi/datos/* | sort -h`.
Lo que se puede borrar sin perder nada: carpetas de ensayo de sesiones (`/home/eodi/ensayo*`),
`/var/tmp/*` de sesiones y los clones de trabajos de una vez (`/home/eodi/calidad`,
`/home/eodi/dirigido`, `/home/eodi/revision`). Nunca `base/`, `datos/` ni `.eodi/`. Si hace falta
más disco, Hetzner amplía el servidor (`hcloud server change-type`) o se añade un volumen.

## Si hay que restaurar la base

La base está en el disco del servidor y en copias cifradas cada hora (48 h), cada día (30 días) y
cada semana (un año) en el almacén privado, y otra vez en Helsinki.

```
sudo systemctl stop eodi-recogida.timer
sudo -u eodi bash /home/eodi/droneobservatory/servidor/base.sh copias listar
sudo -u eodi bash /home/eodi/droneobservatory/servidor/base.sh copias restaurar \
  --destino /home/eodi/base/trabajo/restaurada.sqlite --huella
sudo -u eodi mv /home/eodi/base/eodi.sqlite /home/eodi/base/eodi.antes-de-restaurar.sqlite
sudo -u eodi mv /home/eodi/base/trabajo/restaurada.sqlite /home/eodi/base/eodi.sqlite
sudo systemctl start eodi-recogida.timer
```

Si el almacén de Núremberg no respondiera, la misma copia está en Helsinki. Probado el 8 de octubre
de 2026 (67 MB bajados, descifrados y comprobados en 18 s):

```
sudo -u eodi bash /home/eodi/droneobservatory/servidor/replica.sh listar | grep base/horaria | tail -3
sudo -u eodi bash /home/eodi/droneobservatory/servidor/replica.sh restaurar \
  --objeto base/horaria/<copia>.db.age --destino /home/eodi/base/trabajo/helsinki.db.age
sudo -u eodi sh -c 'cd /home/eodi/droneobservatory && EODI_CLAVE_AGE="$(cat /home/eodi/.eodi/clave_age.txt)" \
  .venv/bin/python -c "from pathlib import Path; from almacen import sitio; t=Path(\"/home/eodi/base/trabajo\"); \
  sitio.descifrar_a_fichero((t/\"helsinki.db.age\").read_bytes(), t/\"restaurada.sqlite\"); \
  print(sitio.integra(t/\"restaurada.sqlite\"))"'
```

Cada martes a las 10:55 UTC el servidor restaura la última copia que está en los dos sitios en una
carpeta aparte, comprueba que está entera y que Helsinki tiene la misma (`eodi-prueba-restauracion`);
si falla, avisa la vigilancia.

## Si hay que levantar un servidor nuevo

Si el servidor ha desaparecido, desde el equipo que guarda las credenciales, en la raíz de un clon
de `main`:

```
bash servidor/reconstruir.sh
```

Crea el servidor, lo endurece, lo instala, lleva las credenciales y activa los temporizadores. Después:

1. restaurar la base (apartado anterior, con el temporizador parado) y el archivo del seguimiento:
   `sudo -u eodi bash /home/eodi/droneobservatory/servidor/seguimiento_archivo.sh restaurar-todo`;
2. poner los interruptores como estaban: `echo disco | sudo -u eodi tee /home/eodi/.eodi/base_modo`,
   `echo almacen | sudo -u eodi tee /home/eodi/.eodi/publicacion_modo` y
   `echo no | sudo -u eodi tee /home/eodi/.eodi/base_secundaria` (desde el 13 de octubre de 2026);
   el archivo de alertas sigue solo: `restaurar-todo` ya trae sus ficheros y, con
   `alertas_tabla/estado.json` sin restaurar, el servicio lo rehace con la tabla;
3. dejar el gancho de despliegue de Vercel en `/home/eodi/.eodi/vercel_gancho` (lo da el panel de
   Vercel, *Settings* → *Git* → *Deploy Hooks*, o su API) con permisos 600;
4. activar las copias de Hetzner: `hcloud server enable-backup eodi-recogida`;
5. comprobar las dos recogidas siguientes.

Cuánto tarda y qué pasos hay, medido: [`informe_blindaje.md`](informe_blindaje.md), fase 6. El
simulacro completo, sin tocar el servidor de verdad: `bash servidor/simulacro.sh`.

## Si hay que volver a publicar los datos en GitHub («doble»)

Desde el 7 de octubre de 2026 a las 22:50 UTC los datos publicados van solo al almacén. Volver a la publicación
doble es un cambio, en el servidor, fuera de los minutos 12 a 40:

```
echo doble | sudo -u eodi tee /home/eodi/.eodi/publicacion_modo
```

Desde la recogida siguiente vuelve el commit «Actualiza los datos publicados» en `main` (además del
almacén) y la exportación semanal sale también por GitHub. Probado el 8 de octubre de 2026 a la
01:17 UTC: un cambio, y la recogida volvió a hacer el commit, idéntico byte a byte al almacén.

Desde que `main` está protegida (regla «main protegida»), ese commit solo entra con una clave de
despliegue (la regla deja pasar a las claves de despliegue y a nadie más), y el servidor ya no
tiene ninguna con escritura en el repositorio público. Antes de cambiar el interruptor:

```
# en el servidor, si no existe ya la clave
sudo -u eodi ssh-keygen -q -t ed25519 -N "" -C "servidor eodi-recogida" -f /home/eodi/.eodi/despliegue_web
# en el equipo del dueño, darla de alta con escritura
ssh -i ~/.eodi/servidor_ssh -o UserKnownHostsFile=~/.eodi/servidor_known_hosts operador@2.28.197.102 \
  sudo cat /home/eodi/.eodi/despliegue_web.pub \
  | gh repo deploy-key add - --repo QuantuSync/droneobservatory --title "servidor eodi-recogida" --allow-write
```

Para que la web lea otra vez del repositorio, además, un PR que ponga `"origen": "github"` en
`configuracion/publicacion_web.json`. Al volver a `almacen`, borrar otra vez esa clave
(`gh repo deploy-key delete <id> --repo QuantuSync/droneobservatory`).

## Cómo se encienden las rutas en la web

Las rutas se calculan cada hora aunque estén apagadas en la web. Para encenderlas, un PR que ponga
`"mostrar": true` en `configuracion/rutas_en_la_web.json`. La primera ejecución de `eodi-rutas`
tras la recogida siguiente sube todas las noches publicables al almacén público y la web las
enseña. Para apagarlas, lo mismo con `false`: se retiran del almacén.
