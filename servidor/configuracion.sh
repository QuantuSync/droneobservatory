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
# Credenciales S3 del almacén público (ALMACEN_ID, ALMACEN_SECRETO), una por línea, para
# subir estado.json. La dirección del almacén está en configuracion/almacen_publico.json.
ALMACEN_CREDENCIALES="$SECRETOS/almacen.env"
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

# --- Estado del sistema (estado.json en el almacén público) ---------------------------
ESTADO_OBJETO="estado.json"
# La web lo pide cada 5 minutos; un minuto de caché basta para no servir uno viejo.
ESTADO_CACHE="public, max-age=60"
# La subida (recogida/almacen_publico.py) reintenta con espera creciente y no pasa de 60 s.
LOCAL_ALMACEN="$LOCAL_SECRETOS/almacen.env"

# --- Exportación semanal para AEGIS (servidor/exportacion.sh) ----------------------------
UNIDAD_EXPORTACION="eodi-exportacion"
# Los lunes a las 03:47 UTC: a mitad de camino entre la recogida de las 03:17 y la de las
# 04:17, de madrugada en Europa y antes del reinicio de seguridad de las 04:45.
CALENDARIO_EXPORTACION="Mon *-*-* 03:47:00 UTC"
# Espera por el cerrojo (como mucho los 45 minutos de una recogida) más la exportación, que
# tarda un par de minutos.
TOPE_EXPORTACION_MINUTOS=90
# La última exportación correcta (versión y hora): la lee estado.json.
EXPORTACION_REGISTRO="$SECRETOS/exportacion.json"

# --- Revisión de lo publicado (servidor/revision.sh) -----------------------------------
# Espera por el cerrojo: una recogida dura como mucho los 45 minutos de su tope.
ESPERA_CERROJO_S=3600
# Lo que se retiene el cerrojo, como mucho, mientras se fusiona la rama revisada: el
# workflow de tests tarda unos 5 minutos y la fusión, otros pocos; tres horas cubren un
# fallo que haya que arreglar antes.
ESPERA_FUSION_S=10800
PAUSA_AVISO_S=30

# --- Reintentos por sitio (recogida/reintentos.py) ------------------------------------
# Un fichero por sitio con los reintentos del día: el descargador común deja de reintentar a
# un sitio que pasa del tope diario. Lo comparten todas las unidades.
REINTENTOS_DATOS="${EODI_REINTENTOS_DATOS:-$CASA/datos/reintentos}"
export EODI_REINTENTOS_DATOS="$REINTENTOS_DATOS"

# --- Anomalías térmicas de NASA FIRMS (recogida/firms.py) ------------------------------
# CSV diarios comprimidos, fuera del repositorio y de la base: la base se sube cifrada cada
# hora y no debe crecer con los focos agrícolas.
FIRMS_DATOS="${EODI_FIRMS_DATOS:-$CASA/datos/firms}"
# La clave va como una línea más del fichero de variables del extractor.
VARIABLE_FIRMS="EODI_FIRMS_MAP_KEY"
LOCAL_FIRMS="$LOCAL_SECRETOS/firms_map_key.txt"
# Histórico (servidor/firms_historico.sh): cada tanda acaba en el minuto 12 de la hora, cinco
# antes de la recogida horaria, y no empieza otra hasta que esta ha terminado. Una tanda de
# menos de dos minutos no merece la pena. Tras un fallo (FIRMS caído, sin red) se espera
# diez minutos; seis fallos seguidos lo paran.
FIRMS_FIN_TANDA=12
FIRMS_TANDA_MINIMA_S=120
FIRMS_ESPERA_FALLO_S=600
FIRMS_FALLOS_MAXIMOS=6

# --- Fuentes oficiales de detalle (recogida/detalle.py) ---------------------------------
# Lo descargado de cada fuente (informes, documentos con sus pasajes, encuentros leídos,
# listas renderizadas y resultados de lotes), fuera del repositorio y de la base.
DETALLE_DATOS="${EODI_DETALLE_DATOS:-$CASA/datos/detalle}"
UNIDAD_DETALLE="eodi-detalle"
# Cada 3 horas en el minuto 52: lejos de la recogida horaria (17), del tráfico aéreo (40), de
# la exportación (03:47) y del reinicio de seguridad (04:45).
CALENDARIO_DETALLE="*-*-* 02/3:52:00 UTC"
# Una recogida normal pide unas decenas de páginas (unos minutos con las pausas) y renderiza
# tres listas; el tope cubre una fuente lenta sin que llegue la siguiente.
TOPE_DETALLE_MINUTOS=120
CERROJO_DETALLE="$SECRETOS/detalle.lock"
# --- Canales de la capa de guerra con lugar (servidor/guerra.sh) -------------------------
# Lo que el lector guarda de cada canal, fuera del repositorio y de la base: la recogida
# horaria solo lee estos ficheros.
GUERRA_DATOS="${EODI_GUERRA_DATOS:-$CASA/datos/guerra}"
UNIDAD_GUERRA="eodi-guerra"
# Minuto 50: lejos de la recogida (17), de las tandas de FIRMS (12) y del tráfico (40).
MINUTO_GUERRA=50
CERROJO_GUERRA="$SECRETOS/guerra.lock"
# La lectura de unos 40 canales tarda de 3 a 6 minutos; el resto de la hora sigue el
# histórico (unos 50 000 páginas desde enero de 2025, a una cada 3 s: unos dos días).
GUERRA_DESDE="2025-01-01"
GUERRA_HISTORICO_MINUTOS=40
TOPE_GUERRA_MINUTOS=55
# --- Tráfico aéreo de adsb.lol y condiciones medidas (recogida/trafico.py) -----------
# Lo que sale del procesado de cada día (movimientos, militares, GNSS, trazas filtradas, METAR
# y la referencia de EUROCONTROL) y la caché de Open-Meteo y del IEM: fuera del repositorio y
# de la base, del usuario del observatorio y solo para él.
TRAFICO_DATOS="${EODI_TRAFICO_DATOS:-$CASA/datos/trafico}"
METEO_DATOS="${EODI_METEO_DATOS:-$CASA/datos/meteo}"
# Cerrojo propio del procesado: nunca el de la recogida horaria.
CERROJO_TRAFICO="$SECRETOS/trafico.lock"
UNIDAD_TRAFICO="eodi-trafico"
# Cada hora en el minuto 40. Un día tarda unos 10 minutos de un núcleo; cada ejecución sigue
# con los días pendientes hasta 50 minutos y no empieza otro si no cabe, así que el histórico
# avanza sin pausa y el día nuevo entra en la primera ejecución tras su publicación (hacia las
# 03:25 UTC del día siguiente). El tope de la unidad, 70 minutos, es la última red.
MINUTO_TRAFICO=40
TRAFICO_TOPE_MINUTOS=50
TRAFICO_TOPE_UNIDAD=70
# Prioridad baja de CPU y de disco: la recogida horaria va siempre por delante.
TRAFICO_NICE=15

# --- Búsqueda dirigida de noticias (recogida/busqueda_dirigida.py) ---------------------
# Los titulares con dron de cada día leído de GDELT y lo hallado para cada cierre medido sin
# incidente, fuera del repositorio y de la base.
BUSQUEDA_DATOS="${EODI_BUSQUEDA_DATOS:-$CASA/datos/busqueda}"
UNIDAD_BUSQUEDA="eodi-busqueda"
CERROJO_BUSQUEDA="$SECRETOS/busqueda.lock"
# Minuto 2: termina antes de la recogida (17) si no hay nada que leer y, con días que leer
# (unos 2 minutos cada uno, 192 ficheros), sigue hasta su tope con prioridad baja.
MINUTO_BUSQUEDA=2
BUSQUEDA_TOPE_MINUTOS=40
BUSQUEDA_TOPE_UNIDAD=50

# --- Revisión de la calidad de los datos (servidor/calidad.sh) -------------------------
CALIDAD_INFORME="$CASA/calidad-informe.json"

# --- Motor de deducción (servidor/deduccion.sh, recogida/deduccion.py) -----------------
# Resultados, relieve de Copernicus DEM y validación, fuera del repositorio y de la base: la
# recogida horaria los guarda en la base.
DEDUCCION_DATOS="${EODI_DEDUCCION_DATOS:-$CASA/datos/deduccion}"
UNIDAD_DEDUCCION="eodi-deduccion"
# Minuto 5: tras arrancar la búsqueda dirigida (2), con la base que subió la recogida horaria
# anterior (17); el lector de la capa de guerra (50) ha terminado y el cálculo de FIRMS (12) y la
# recogida siguiente quedan lejos para una pasada incremental, que tarda un minuto.
MINUTO_DEDUCCION=5
# Una pasada incremental tarda segundos; una completa, unos minutos (más la primera descarga del
# relieve). El tope es la última red.
TOPE_DEDUCCION_MINUTOS=50
DEDUCCION_NICE=15
CERROJO_DEDUCCION="$SECRETOS/deduccion.lock"
# Última ejecución correcta del motor: la lee estado.json (ultima_deduccion).
DEDUCCION_REGISTRO="$SECRETOS/deduccion.json"

# --- Catálogo vivo (servidor/catalogo.sh, recogida/catalogo_vivo.py) ------------------------
# Lo que encuentra el barrido periódico del catálogo de prestaciones (novedades, catálogo vivo,
# historial, tácticas, apariciones, control y gasto), fuera del repositorio y de la base: la
# recogida horaria lo guarda en la base.
CATALOGO_DATOS="${EODI_CATALOGO_DATOS:-$CASA/datos/catalogo}"
UNIDAD_CATALOGO="eodi-catalogo"
# Una vez al día a las 05:23 UTC: tras el reinicio de seguridad (04:45) y lejos de la recogida
# (17), del tráfico aéreo (40), del lector de canales (50) y del motor de deducción (05). Lee
# War&Sanctions y los datos propios cada día y el resto de fuentes una vez a la semana.
CALENDARIO_CATALOGO="*-*-* 05:23:00 UTC"
# Unos minutos al día con las pausas por sitio; la primera pasada lee más. El tope es la red.
TOPE_CATALOGO_MINUTOS=60
CATALOGO_NICE=15
CERROJO_CATALOGO="$SECRETOS/catalogo.lock"

# --- Barrido dirigido (servidor/dirigido.sh, recogida/barrido_dirigido.py) --------------------
DIRIGIDO_INFORME="$CASA/dirigido-informe.json"

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
