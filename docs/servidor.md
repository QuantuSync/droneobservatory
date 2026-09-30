# Servidor de recogida

La recogida de cada hora la lanza un servidor propio en Hetzner Cloud, no GitHub Actions.
Todo lo que hay en él sale de los scripts de [`servidor/`](../servidor), que no llevan
ningún secreto: con ellos y con los secretos que se guardan en local se reconstruye desde
cero con una sola orden.

## Qué hay en el servidor

| | |
| --- | --- |
| Servidor | `eodi-recogida`, tipo CX23, Núremberg (`nbg1`), Ubuntu 26.04 LTS |
| Cortafuegos de Hetzner | `eodi-recogida`: solo entra SSH (TCP 22); lo demás, cerrado |
| Usuario `eodi` | Ejecuta el observatorio. Sin privilegios, sin contraseña y sin entrada por SSH |
| Usuario `operador` | Administra: entra por SSH con clave y usa `sudo` |
| SSH | Solo con clave, sin contraseña y sin root |
| Además | fail2ban, actualizaciones de seguridad automáticas con reinicio a las 04:45 si hace falta, zona horaria UTC, hora sincronizada, diario de systemd con tope de tamaño y de antigüedad |

Dos particularidades:

- **Python 3.13.** Ubuntu 26.04 trae Python 3.14; el 3.13 del proyecto se instala del
  archivo de paquetes `ppa:deadsnakes/ppa`, incluido en las actualizaciones automáticas.
- **IPv4 por delante de IPv6** (`/etc/gai.conf`). Desde este centro de datos la conexión
  por IPv6 con Telegram falla casi siempre, y Python agota el tiempo límite de cada
  petición antes de probar con IPv4: sin esta preferencia, la lectura de un canal no cabe
  en su tope de tiempo.

En `/home/eodi`:

- `droneobservatory/`: clon del repositorio en `main` y su entorno virtual (`.venv`) con
  Python 3.13 y `requirements.txt`.
- `.eodi/`, con permisos 600 y propiedad de `eodi`:
  - `clave_age.txt`: la identidad age de la base;
  - `extractor.env`: las variables del extractor, una por línea;
  - `despliegue_datos`: clave de despliegue con escritura solo en `droneobservatory-datos`;
  - `despliegue_web`: clave de despliegue con escritura solo en `droneobservatory`, para
    publicar los ficheros de la web;
  - `known_hosts`: la clave de host publicada por GitHub.

Las dos claves de despliegue se generan en el servidor y la privada no sale de él. En
GitHub figuran en cada repositorio con el título «servidor eodi-recogida».

## La recogida horaria

`eodi-recogida.timer` lanza `eodi-recogida.service` en el minuto 17 de cada hora (UTC). Si
el servidor estaba apagado a su hora, la ejecución pendiente se lanza al arrancar. La
unidad ejecuta [`servidor/recogida.sh`](../servidor/recogida.sh) como `eodi`, con un tope
de 45 minutos, y el script:

1. toma un cerrojo (`flock`): si hay otra recogida en marcha, no se lanza;
2. deja el clon en la última versión de `main` y reinstala las dependencias solo si ha
   cambiado `requirements.txt`;
3. ejecuta `python -m recogida.horaria`, que descarga la base de la rama `estado`, recoge
   lo nuevo y vuelve a subirla;
4. publica en `main` `publicacion/ucrania.json`, `publicacion/incidentes.geojson` y
   `publicacion/incidentes_sin_ubicacion.json` si han cambiado, con autor QuantuSync y la
   dirección anónima. También cuando la recogida
   termina con avisos (código 2); nunca cuando falla con otro código.

Sale con el código de la recogida: con avisos, la unidad queda como fallida en systemd,
igual que el workflow quedaba en rojo, y la hora siguiente se lanza igual.

El script se ejecuta desde el clon, así que un cambio suyo en `main` vale desde la
recogida siguiente. Las unidades de systemd y el endurecimiento, en cambio, se instalan:
si cambian `instalar.sh`, `endurecer.sh` o `configuracion.sh`, hay que volver a ejecutar
`reconstruir.sh`.

## Secretos en local

En `%USERPROFILE%\.eodi\`, fuera de cualquier repositorio:

| Fichero | Qué es |
| --- | --- |
| `hcloud_token.txt` | Token de la API de Hetzner Cloud del proyecto EODI |
| `servidor_ssh`, `servidor_ssh.pub` | Par de claves SSH del operador, solo para este servidor |
| `servidor_known_hosts` | Clave de host del servidor, anotada en la primera conexión |
| `clave_age.txt` | Identidad age de la base |
| `extractor.env` | Variables del extractor (`EODI_EXTRACTOR_*`) |
| `cloudflare_token.txt` | Token de la API de Cloudflare (R2 y DNS de las teselas) |
| `r2_estado.env` | Credenciales S3 de R2 para subir `estado.json` (`R2_ID`, `R2_SECRETO`, `R2_CUENTA`), derivadas del token por `reconstruir.sh` si no existen |

En GitHub, el repositorio guarda además el secreto `EODI_DATOS_CLAVE_LECTURA`: una clave
de despliegue de solo lectura del repositorio de datos, con la que el workflow de tests
mira la fecha de la rama `estado`. No tiene copia en local: si se pierde, se crea otra.

## Reconstruir desde cero

Hace falta `hcloud`, `gh` con sesión de la cuenta QuantuSync, `ssh` y los ficheros
`hcloud_token.txt`, `clave_age.txt` y `extractor.env` de la tabla anterior. En Windows,
desde Git Bash y en la raíz del clon:

```
bash servidor/reconstruir.sh
```

El script:

1. crea, si no existen, el par de claves SSH local, la clave en Hetzner, el cortafuegos y
   el servidor;
2. copia `servidor/` al servidor y ejecuta `endurecer.sh` y `instalar.sh`;
3. copia la clave age y las variables del extractor;
4. sustituye en GitHub las claves de despliegue «servidor eodi-recogida» de los dos
   repositorios por las del servidor;
5. activa el temporizador.

Puede repetirse sobre un servidor que ya existe: deja igual lo que ya está y vuelve a
aplicar la configuración. Para empezar de verdad desde cero se borra antes el servidor:

```
export HCLOUD_TOKEN="$(tr -d '\r\n' < ~/.eodi/hcloud_token.txt)"
hcloud server delete eodi-recogida
bash servidor/reconstruir.sh
```

Nada de lo que hay en el servidor es irrecuperable: la base vive en la rama `estado` y la
caché de páginas (`data/cache/`) se vuelve a llenar sola.

## Estado del sistema para la web

Al salir, con el código que sea, [`servidor/recogida.sh`](../servidor/recogida.sh) compone
`estado.json` ([`recogida/estado.py`](../recogida/estado.py)) y lo sube al bucket R2
`eodi-teselas`, que se sirve en <https://tiles.droneobservatory.eu/estado.json>. No hay
commit en git, así que la web no se reconstruye cada hora.

El fichero lleva la hora de inicio y de fin de la recogida, su resultado (`correcta`,
`con_avisos` o `fallida`), la hora de la última correcta, la de la siguiente prevista
(minuto 17) y, por cada fuente (`fuerza_aerea_ua`, `mindef_ru`, `gdelt`, `oficiales` y
`extractor`), su estado (`leida`, `con_aviso` o `no_leida`) y la hora de su último dato.
No lleva ningún contenido. La recogida deja el estado de cada fuente en un fichero
temporal (`recogida.horaria --estado`). El último estado publicado se guarda en
`/home/eodi/.eodi/estado.json`, de donde sale la hora de la última recogida correcta.

- **Subida**: `curl --aws-sigv4` contra el punto S3 de R2, con `Cache-Control: public,
  max-age=60` (la web lo pide cada 5 minutos). El CORS es el del bucket, el mismo que para
  las teselas. Las credenciales llegan a curl por su entrada, no por la línea de órdenes.
- **Si falla** (sin credenciales, sin red, R2 caído), la recogida no cambia de resultado:
  queda un aviso en el diario («aviso: no se pudo subir estado.json al bucket»).
- **Credenciales**: `/home/eodi/.eodi/r2.env`, con permisos 600. El token de Cloudflare no
  puede crear otros tokens (la API responde 9109) y las credenciales temporales de R2
  caducan, así que se derivan del propio token: identificador del token como clave de
  acceso y SHA-256 del token como secreto. Tienen los permisos de R2 del token, que son de
  toda la cuenta, no solo de este bucket. Para limitarlas al bucket hay que crear en el
  panel de Cloudflare un token de R2 con escritura solo en `eodi-teselas`, guardarlo en
  `r2_estado.env` con el mismo formato y volver a ejecutar `reconstruir.sh`.

## Órdenes útiles

Entrar en el servidor (la IP la da `hcloud server ip eodi-recogida`):

```
ssh -i ~/.eodi/servidor_ssh -o UserKnownHostsFile=~/.eodi/servidor_known_hosts operador@<IP>
```

Y dentro:

```
systemctl list-timers eodi-recogida.timer     # cuándo fue la última y cuándo es la siguiente
journalctl -u eodi-recogida.service -n 80     # registro de las últimas recogidas
systemctl status eodi-recogida.service        # resultado de la última
sudo systemctl start eodi-recogida.service    # lanzar una ahora
sudo systemctl stop eodi-recogida.timer       # parar la recogida horaria
sudo systemctl start eodi-recogida.timer      # reanudarla
```

## Revisión de todo lo publicado

Cuando cambian las reglas con que se construyen los incidentes, lo ya publicado se revisa
en el servidor con [`servidor/revision.sh`](../servidor/revision.sh), como `eodi` y desde
la rama que trae las reglas:

```
sudo -u eodi bash /home/eodi/droneobservatory/servidor/revision.sh <rama> /home/eodi/revision.liberar
```

Toma el mismo cerrojo que la recogida horaria (espera a que termine la que esté en marcha),
deja un clon aparte en `/home/eodi/revision` con la rama y con los ficheros publicados de
`main`, y ejecuta `python -m recogida.revision`: muestra de coste, lote del extractor
dentro de su propio límite de gasto (5 dólares), reconstrucción de todos los incidentes,
fusiones y episodios, publicación en el clon aparte y subida de la base. El informe queda
en `/home/eodi/revision-informe.json`. Con un fichero de aviso, retiene el cerrojo hasta
que ese fichero existe (como mucho tres horas): se crea con `touch` cuando la rama ya está
fusionada, y así la recogida horaria no vuelve a publicar con el código anterior mientras
tanto.

## Emergencia: recogida desde GitHub

El workflow `recogida` sigue en el repositorio, solo con lanzamiento a mano, y conserva sus
secretos. Si el servidor no está disponible:

```
gh workflow run recogida.yml --ref main
```

Si el servidor sigue encendido, antes hay que parar su temporizador: dos recogidas a la
vez se pisarían la rama `estado`.

## Cómo se ve si la recogida se para

El workflow `vigia-recogida` se lanza cada hora en el minuto 41 y mira la fecha del último
commit de la rama `estado` del repositorio de datos. Si tiene más de 2 horas, abre una
incidencia en este repositorio («La recogida horaria no actualiza la base»), una sola
mientras dure el problema, y la cierra cuando la rama vuelve a actualizarse. Solo tiene
permiso para las incidencias; el repositorio de datos, que es privado, lo lee con la clave
de despliegue de solo lectura «droneobservatory: salud (solo lectura)» (secreto
`EODI_DATOS_CLAVE_LECTURA`), que pide solo el commit y no descarga la base. Si no puede
leer la rama, el trabajo queda en rojo sin tocar las incidencias. GitHub lanza las
ejecuciones programadas con retraso y a veces se salta alguna: el aviso puede llegar tarde.
Además, desactiva las programaciones de un repositorio público sin actividad durante 60
días; la recogida publica en `main` casi cada hora, así que no debería pasar.

El trabajo `salud-recogida` del workflow de tests hace la misma comprobación en cada push o
pull request y la deja en su resumen.

## Fuentes que no se leen desde el servidor

- **Ministerio de Defensa de Finlandia** (`mod_fi`, `defmin.fi/ajankohtaista`). Retirada
  de `configuracion/fuentes_oficiales.json` el 30 de septiembre de 2026. Al servidor, que
  tiene una dirección de centro de datos, le responde 403 con una página de comprobación
  anti-robots, con la identificación del observatorio y con la de un navegador, y también a
  `robots.txt`; desde una conexión doméstica responde 200. Leerla exigiría saltarse esa
  comprobación, y el observatorio lee las fuentes con su identificación y respetando lo que
  piden. Sigue en `fuentes_oficiales_candidatas.json` por si el ministerio publica un canal
  RSS o deja de vetar esas direcciones. Las confirmaciones oficiales de Finlandia quedan en
  las declaraciones que cita la prensa.
