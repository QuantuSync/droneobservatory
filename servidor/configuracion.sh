# Valores comunes de los scripts del servidor de recogida. Se carga con «.», no se ejecuta.
# Aquí no hay ningún secreto: solo nombres, rutas y plazos.
# shellcheck shell=bash

# --- Servidor en Hetzner Cloud -------------------------------------------------------
SERVIDOR_NOMBRE="eodi-recogida"
# El tipo compartido más pequeño de la gama: la recogida usa un núcleo unos minutos por hora.
SERVIDOR_TIPO="cx23"
SERVIDOR_LOCALIZACION="nbg1"
# La última Ubuntu con soporte largo.
SERVIDOR_IMAGEN="ubuntu-26.04"
CORTAFUEGOS_NOMBRE="eodi-recogida"
CLAVE_SSH_NOMBRE="eodi-recogida"
PUERTO_SSH=22
# Cuánto se espera a que el servidor recién creado acepte conexiones.
ESPERA_SSH_INTENTOS=60
ESPERA_SSH_PAUSA_S=5

# --- Secretos en la máquina desde la que se reconstruye ------------------------------
LOCAL_SECRETOS="${EODI_LOCAL_SECRETOS:-$HOME/.eodi}"
LOCAL_TOKEN="$LOCAL_SECRETOS/hcloud_token.txt"
LOCAL_CLAVE_SSH="$LOCAL_SECRETOS/servidor_ssh"
LOCAL_HOSTS_CONOCIDOS="$LOCAL_SECRETOS/servidor_known_hosts"
LOCAL_CLAVE_AGE="$LOCAL_SECRETOS/clave_age.txt"
LOCAL_EXTRACTOR="$LOCAL_SECRETOS/extractor.env"

# --- Usuarios ------------------------------------------------------------------------
# Quien ejecuta el observatorio: sin privilegios y sin entrada por SSH.
USUARIO="eodi"
# Quien administra el servidor: entra por SSH con clave y usa sudo.
OPERADOR="operador"

# --- Observatorio --------------------------------------------------------------------
CASA="${EODI_CASA:-/home/$USUARIO}"
CLON="${EODI_CLON:-$CASA/droneobservatory}"
SECRETOS="${EODI_SECRETOS:-$CASA/.eodi}"
ENTORNO="$CLON/.venv"
PYTHON_VERSION="3.13"
RAMA="main"
REPOSITORIO="QuantuSync/droneobservatory"
REPOSITORIO_DATOS="QuantuSync/droneobservatory-datos"
URL_LECTURA="https://github.com/$REPOSITORIO.git"
URL_ESCRITURA="git@github.com:$REPOSITORIO.git"
URL_DATOS="git@github.com:$REPOSITORIO_DATOS.git"
AUTOR="QuantuSync"
# Dirección anónima de la cuenta: el correo personal no aparece en ningún commit.
CORREO="192205734+QuantuSync@users.noreply.github.com"
MENSAJE_PUBLICACION="Actualiza los datos publicados"
PUBLICADOS=(publicacion/ucrania.json publicacion/incidentes.geojson
  publicacion/incidentes_sin_ubicacion.json)
# Código con el que sale la recogida cuando termina con avisos
# (recogida.horaria.SALIDA_AVISO): la base está subida y se publica igual.
SALIDA_AVISO=2

# --- Ficheros de secretos en el servidor ---------------------------------------------
CLAVE_AGE="$SECRETOS/clave_age.txt"
EXTRACTOR="$SECRETOS/extractor.env"
DESPLIEGUE_DATOS="$SECRETOS/despliegue_datos"
DESPLIEGUE_WEB="$SECRETOS/despliegue_web"
HOSTS_CONOCIDOS="$SECRETOS/known_hosts"
# Credenciales S3 de R2 (R2_ID, R2_SECRETO, R2_CUENTA), una por línea, para subir estado.json.
R2_CREDENCIALES="$SECRETOS/r2.env"
# El último estado publicado: de él sale la hora de la última recogida correcta.
ESTADO_ANTERIOR="$SECRETOS/estado.json"
CERROJO="$SECRETOS/recogida.lock"
# Título de las claves de despliegue en GitHub: por él se encuentran para sustituirlas.
TITULO_DESPLIEGUE="servidor eodi-recogida"
# Clave de host publicada por GitHub: sin confiar en la primera conexión.
HOST_GITHUB="github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"

# --- Temporizador --------------------------------------------------------------------
UNIDAD="eodi-recogida"
# Minuto 17 de cada hora, para no coincidir con el pico de las horas en punto.
MINUTO_RECOGIDA=17
# Una ejecución normal tarda de 5 a 7 minutos y los topes de cada paso suman 24 en el
# peor caso (recogida/horaria.py). Los 45 son la última red, por si algo se cuelga.
TOPE_MINUTOS=45

# --- Estado del sistema (estado.json en el bucket de teselas) ------------------------
R2_BUCKET="eodi-teselas"
ESTADO_OBJETO="estado.json"
# La web lo pide cada 5 minutos; un minuto de caché basta para no servir uno viejo.
ESTADO_CACHE="public, max-age=60"
# Subir un fichero de 1 kB tarda menos de un segundo; 30 s cubren una red lenta.
ESTADO_TOPE_S=30
LOCAL_R2="$LOCAL_SECRETOS/r2_estado.env"

# --- Revisión de lo publicado (servidor/revision.sh) -----------------------------------
# Espera por el cerrojo: una recogida dura como mucho los 45 minutos de su tope.
ESPERA_CERROJO_S=3600
# Lo que se retiene el cerrojo, como mucho, mientras se fusiona la rama revisada: el
# workflow de tests tarda unos 5 minutos y la fusión, otros pocos; tres horas cubren un
# fallo que haya que arreglar antes.
ESPERA_FUSION_S=10800
PAUSA_AVISO_S=30

# --- Endurecimiento ------------------------------------------------------------------
# Reinicio tras una actualización de seguridad que lo pida: de madrugada y a los 28
# minutos del lanzamiento de las 04:17, cuando hasta la recogida más lenta ha terminado.
HORA_REINICIO="04:45"
# Intentos fallidos de entrada por SSH antes de vetar una dirección, en qué ventana y
# cuánto dura el veto.
VETO_INTENTOS=5
VETO_VENTANA="10m"
VETO_DURACION="1h"
# Diario de systemd: tope de disco y de antigüedad. Una recogida deja unas decenas de
# líneas, así que el tope de antigüedad llega mucho antes que el de disco.
DIARIO_MAXIMO="200M"
DIARIO_ANTIGUEDAD="90day"

# --- Red -----------------------------------------------------------------------------
# Línea de /etc/gai.conf que da preferencia a las direcciones IPv4 (las IPv6 con IPv4
# incrustada, ::ffff:0:0/96) al elegir a cuál conectarse. 100 es la precedencia más alta
# de la tabla por defecto.
PREFERENCIA_IPV4="precedence ::ffff:0:0/96  100"
