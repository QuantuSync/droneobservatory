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

**Se arregla solo y avisa solo si no puede.** Cada servicio se reintenta solo y la recogida
fallida se repite a los 10 y a los 25 minutos ([servidor.md](servidor.md), «Reintentos»). El
workflow `vigia-recogida` lee ese fichero cada 10 minutos (y `estado.json` y `directo.json`). Si
hay un problema que no se ha arreglado solo:

- abre una incidencia en el repositorio con el problema y dónde mirar (GitHub manda el aviso por
  correo a quien vigila el repositorio); desde el 12 de octubre de 2026 ya no llega además el
  correo «Run failed: vigia-recogida»;
- la incidencia se cierra sola cuando se arregla.

Lo que se arregló solo (reintentos, fallos sueltos que desaparecen en menos de 30 minutos) no
manda correo: sale en la sección SISTEMA del resumen diario privado ([visitas.md](visitas.md)).

**El servidor se repara solo** (desde el 14 de octubre de 2026, [servidor.md](servidor.md),
«Guardián del sistema»): cada 5 minutos el guardián recrea `/dev/null` y los demás dispositivos si
faltan, deja `/tmp` en 1777, reinicia sshd si no responde y limpia cachés si el disco pasa del 90 %;
si dos recogidas seguidas fallan por el sistema, reinicia el servidor (una vez cada 6 horas) y lanza
la recogida pendiente; y si el servidor no da señales en 30 minutos, el vigía lo reinicia por la API
de Hetzner (una vez cada 6 horas). La incidencia del servidor solo se abre si nada de eso lo arregla.

Problemas que avisan: datos publicados con más de 3 horas, 3 recogidas seguidas que terminan, tras
sus reintentos, con un código distinto de 0 y 2, captura del seguimiento sin recibir nada en 10 minutos, archivo de alertas de alerts.in.ua sin
respuesta correcta de la API en 15 minutos o con la API respondiendo 401 o 403, copia de la base o del
archivo con más de 2 horas, segunda copia con más de 3 horas, copia pública de reserva de Helsinki
sin estar al día más de 30 minutos, disco por encima del 75 %, servidor
sin dar señales tras el reinicio desde fuera (salud.json con más de 30 minutos y el reinicio de las
6 horas ya hecho), lo que el guardián del sistema no consigue arreglar, exportación semanal fallida o con más de 8
días, detección en directo parada más de media hora, compilación de producción de la web fallida
también tras su reintento, paso de la base a solo disco fallido,
versión citable de los datos del mes sin generar (pasadas las 06:00 UTC del día 1) o una
publicada que ha cambiado, la barrera de titulares que resuelve sola más de 3 incidentes en un día
o que deja uno retenido más de 8 horas, e `incidentes.geojson` sin cambiar en 24 horas con
incidentes nuevos con punto en la base (apartado «Si la barrera de titulares retiene incidentes»),
el contador de visitas sin responder, el resumen diario sin enviar a las 09:00 de Madrid, la copia
de la base de visitas con más de 3 horas y el panel de visitas o el tema privado del resumen
abiertos sin usuario (apartado «Si el contador de visitas o el resumen diario fallan»).

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

## Si la barrera de titulares retiene incidentes

La barrera (`proceso/cita_titular.py`) no publica un incidente si ningún texto de sus fuentes
respalda el titular. Cuentan las citas guardadas y el titular del propio artículo fuente tal como
está en la base; nunca un texto del extractor ni el titular de otro artículo. La primera frase del
artículo no cuenta porque la base no guarda el texto de los artículos. Nada espera a una revisión
a mano (`recogida/barrera.py`, en cada recogida antes de publicar):

- si el titular del artículo fuente nombra el lugar o el país, se guarda como cita del incidente
  (una fuente `titular-…` del mismo artículo) y se publica;
- lo que siga retenido 6 horas se resuelve solo. Si algún texto de sus fuentes nombra el país o una
  de sus regiones, se publica a nivel de país con ubicación aproximada: sin punto ni nombre de la
  instalación, con el marcador de lugar aproximado de la web y un titular sin el lugar concreto.
  Si ninguno nombra ni el país, se retira como no verificable, con el motivo;
- las resoluciones quedan en el cursor `barrera_titulares` de la base (registro interno de
  descartes, con su motivo y desde cuándo estaba retenido) y en el historial del incidente.

La vigilancia lee `/home/eodi/.eodi/barrera.json`, que escribe la recogida, y avisa por correo solo
si algo va mal: más de 3 resoluciones en 24 horas (`barrera_resoluciones`: el extractor elige mal
las citas), un retenido de más de 8 horas (`barrera_atascada`: la resolución no se aplica) o el mapa
parado (`mapa_parado`: `incidentes.geojson` sin cambiar en 24 horas con incidentes nuevos con punto
en la base). Los identificadores, en el diario: `journalctl -u eodi-vigilancia -n 20`.

```
sudo cat /home/eodi/.eodi/barrera.json                 # retenidos, resoluciones y mapa
journalctl -u eodi-recogida -n 400 | grep -E 'barrera|no se publica'
```

Para corregir uno a mano (otra cita, unir, retirar), `configuracion/incidentes_revisados.json`
sigue valiendo y se aplica antes de la barrera.

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
- Desde el 12 de octubre de 2026, si Núremberg no acepta la publicación, la recogida la sube
  directamente a la reserva de Helsinki: la web sigue con datos al día.
- La vigilancia avisa: `salud.json` (que está en Núremberg) deja de responder y se abre la
  incidencia, que llega por correo.

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

**Los datos nunca paran la compilación** (desde el 14 de octubre de 2026, cuando falló a las 05:07
y a las 05:12 UTC porque los datos publicados traían un campo, `traduccion`, que el código de main
aún no conocía: [`web/scripts/tolerancia.ts`](../web/scripts/tolerancia.ts)). Un campo que la web no
conoce se ignora; un incidente, ataque o impacto que no cumple el esquema se quita de la web y los
demás se publican; un fichero que no se puede leer se toma de la web anterior
(`https://droneobservatory.eu/datos/...`), y la previsión, si no vale, se omite. Todo queda en el
registro de la compilación con líneas `AVISO DE DATOS` (en Vercel, *Deployments* → el despliegue →
*Build Logs*). Solo falla si no hay forma de tener los datos, y entonces sigue la web anterior.

**La vigilancia lo comprueba** ([`recogida/despliegue_web.py`](../recogida/despliegue_web.py), en
cada pasada del vigía, secreto `EODI_VERCEL_TOKEN`): el despliegue de producción tiene que ser del
último commit de main y estar en verde. Si falla, el vigía pide uno nuevo de main (una vez); si
vuelve a fallar, abre la incidencia «La web no se publica en Vercel», que se cierra sola cuando sale
bien. A mano:

```
VERCEL_TOKEN=$(cat ~/.eodi/vercel_token.txt) python -m recogida.despliegue_web --sha $(git rev-parse origin/main) --sin-reintento
```

## Pruebas en la nube

Desde el 15 de octubre de 2026 las pruebas pesadas no se pasan en el ordenador de quien
desarrolla: las hace GitHub Actions en cada PR y tras cada despliegue de producción.

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `tests` ([tests.yml](../.github/workflows/tests.yml)) | cada push y cada PR | ruff, mypy, todas las pruebas de Python, la exportación de ensayo, y de la web: lint, tipos, vitest, compilación y las páginas de texto en un navegador real; además, la barrera de titulares y la validación sobre los datos publicados de verdad |
| `recorridos` ([recorridos.yml](../.github/workflows/recorridos.yml)) | cada PR, cada despliegue de Vercel y a mano | todos los recorridos de Playwright de `web/e2e`: Chromium y WebKit; Android, iPhone, tableta y escritorio; español e inglés, en 11 trabajos en paralelo |

**Contra qué va `recorridos`.** Si el PR cambia la web (`web/`, `api/`, `publicacion/`,
`vercel.json` o la configuración que lee la web), Vercel publica una vista previa y, cuando está
lista, avisa a GitHub; los recorridos van contra esa vista previa, con la clave de acceso de las
vistas previas en el secreto `EODI_VERCEL_BYPASS`. Si el PR no cambia la web, Vercel no construye
y los recorridos van contra producción. Tras cada despliegue de producción (cada fusión en main),
se repiten contra https://droneobservatory.eu.

**Cómo se ven los resultados.**

- En el PR, en la lista de comprobaciones: `tests / …` y `recorridos / <dispositivo> <trozo>`.
  Los de la vista previa aparecen unos minutos después de que Vercel termine (cuelgan del commit,
  no del evento del PR). Un PR se fusiona con todo en verde.
- En la pestaña *Actions* del repositorio, el workflow `recorridos`: cada ejecución dice en el
  trabajo `destino` contra qué dirección fue. Si un trabajo falla, al final de la ejecución hay
  un artefacto `informe-<dispositivo>-<n>` con el informe HTML de Playwright (qué prueba falló,
  en qué paso y con qué mensaje); se abre descomprimido con `npx playwright show-report <carpeta>`.
- Tras un despliegue de producción que no pasa los recorridos se abre la incidencia «Los
  recorridos fallan en producción» con el enlace a la ejecución (o se comenta la que ya esté
  abierta). Se cierra sola cuando un despliegue de producción vuelve a pasarlos.
- A mano: *Actions* → `recorridos` → *Run workflow*, con la dirección que se quiera (también una
  vista previa). Con `gh`: `gh workflow run recorridos -f base=https://droneobservatory.eu` y
  `gh run watch`.

**En el ordenador de las sesiones** solo se pasan las pruebas de lo que se toca
(`pytest tests/test_<lo_tocado>.py`, `npx vitest run tests/<lo_tocado>.test.ts`): ni la batería
completa, ni la compilación de la web, ni Playwright. Lo demás se espera a la CI (son las
reglas fijas de las sesiones de desarrollo, fuera del repositorio).

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

## Si el contador de visitas o el resumen diario fallan

El contador (GoatCounter, https://stats.droneobservatory.eu) y el resumen diario privado de las
08:00 de Madrid están explicados en [visitas.md](visitas.md). Si el contador cae, la web sigue igual
y solo se pierden las visitas de ese rato.

```
systemctl status goatcounter caddy eodi-visitas.timer
journalctl -u goatcounter -n 40
journalctl -u eodi-visitas -n 40                     # muestras, copia y «resumen del … enviado»
sudo cat /home/eodi/.eodi/visitas.json               # resumen.error, copia.error
sudo systemctl restart goatcounter                   # las sesiones abiertas se borran al parar
sudo -u eodi bash /home/eodi/droneobservatory/servidor/visitas_resumen.sh comprobar
```

El resumen se reintenta solo cada 5 minutos. Un 401 o 403 al enviarlo son los permisos de
`observatorio` en `lucas-resumen`: `sudo bash /home/eodi/droneobservatory/servidor/ntfy.sh` los
rehace. Restaurar la base de visitas desde su copia: [visitas.md](visitas.md), «Copias».

## Cómo se borra en el servidor

En el servidor nadie usa `rm`: el 13 de octubre de 2026 una sesión borró `/dev/null` limpiando sus
ficheros de prueba y dejó el servidor sin SSH ni servicios. Las sesiones borran con el ayudante
[`servidor/borrar.py`](../servidor/borrar.py), que solo borra dentro de `/home/eodi` (salvo `base/`,
`datos/`, `.eodi/`, el clon `droneobservatory/` y los navegadores de `.cache/ms-playwright/`),
`/home/operador`, `/tmp` y `/var/tmp`, y se niega con cualquier otra ruta (`/dev`, `/etc`, `/usr`,
`/bin`, `/boot`, `/proc`, `/sys`...):

```
sudo python3 /home/eodi/droneobservatory/servidor/borrar.py --ensayo /home/operador/prueba   # qué borraría
sudo python3 /home/eodi/droneobservatory/servidor/borrar.py /home/operador/prueba
sudo -u eodi python3 /home/eodi/droneobservatory/servidor/borrar.py /home/eodi/ensayo-x  # lo del usuario eodi
```

Nada del sistema se toca a mano (ni `/dev`, ni `/etc`, ni ficheros del sistema) salvo la
configuración propia del observatorio, que la escriben `instalar.sh` y sus scripts. Si algo del
sistema se rompe, el guardián lo repara ([servidor.md](servidor.md), «Guardián del sistema»).

## Si el servidor no da señales

Normalmente no hay que hacer nada: el guardián lo arregla en 5 minutos y, si no, el vigía lo
reinicia por la API de Hetzner a los 30 minutos sin señales. Si llega la incidencia «El servidor del
observatorio necesita atención» con «no da señales», es que el reinicio de las 6 horas ya se gastó.
Desde Git Bash en el equipo con las credenciales:

```
export HCLOUD_TOKEN=$(cat ~/.eodi/hcloud_token.txt)
hcloud server metrics eodi-recogida --type cpu,network     # ¿hace algo?
hcloud server reboot eodi-recogida                           # reinicio suave
hcloud server reset eodi-recogida                            # si el suave no basta
```

Tras arrancar, el guardián lanza la recogida pendiente solo.

## Si el disco se llena

El aviso llega al 75 %; al 90 % el guardián limpia solo las cachés y los temporales. Ver qué ocupa:
`sudo du -sh /home/eodi/* /home/eodi/datos/* | sort -h`.
Lo que se puede borrar sin perder nada, con `servidor/borrar.py` (apartado «Cómo se borra en el
servidor»): carpetas de ensayo de sesiones (`/home/eodi/ensayo*`), `/var/tmp/*` de sesiones y los
clones de trabajos de una vez (`/home/eodi/calidad`, `/home/eodi/dirigido`, `/home/eodi/revision`).
Nunca `base/`, `datos/` ni `.eodi/`. Si hace falta
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
   `sudo -u eodi bash /home/eodi/droneobservatory/servidor/seguimiento_archivo.sh restaurar-todo`,
   y la base de visitas ([visitas.md](visitas.md), «Copias»);
2. poner los interruptores como estaban: `echo disco | sudo -u eodi tee /home/eodi/.eodi/base_modo`,
   `echo almacen | sudo -u eodi tee /home/eodi/.eodi/publicacion_modo` y
   `echo no | sudo -u eodi tee /home/eodi/.eodi/base_secundaria` (desde el 13 de octubre de 2026;
   sin el fichero también vale `no`: el repositorio de datos está archivado y `reconstruir.sh` ya no
   le da de alta ninguna clave);
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
