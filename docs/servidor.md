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
4. publica en `main` `publicacion/ucrania.json` y `publicacion/incidentes.geojson` si han
   cambiado, con autor QuantuSync y la dirección anónima. También cuando la recogida
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

## Emergencia: recogida desde GitHub

El workflow `recogida` sigue en el repositorio, solo con lanzamiento a mano, y conserva sus
secretos. Si el servidor no está disponible:

```
gh workflow run recogida.yml --ref main
```

Si el servidor sigue encendido, antes hay que parar su temporizador: dos recogidas a la
vez se pisarían la rama `estado`.

## Cómo se ve si la recogida se para

El trabajo `salud-recogida` del workflow de tests mira la fecha del último commit de la
rama `estado` del repositorio de datos y señala en su resumen si tiene más de 2 horas.
Solo se ejecuta cuando hay un push o un pull request.
