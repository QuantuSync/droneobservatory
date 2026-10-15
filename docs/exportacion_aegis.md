# Exportación semanal para AEGIS: dónde está y cómo se lee (formato 1.10.0)

Guía para la sesión que actualice AEGIS. Fecha: 12 de octubre de 2026 (PR #212).

## 1. Ubicación

Desde el blindaje (7–8 de octubre de 2026), la exportación ya **no** está en GitHub:

- **Bucket:** `droneobservatory-exportaciones`, en Hetzner Object Storage, ubicación `nbg1`.
- **Punto S3:** `https://nbg1.your-objectstorage.com`, con direcciones de ruta
  (`<punto>/<bucket>/<objeto>`) y firma SigV4 con la región `nbg1`.
- **Cada versión:** `exportaciones/<versión>/`, con `manifiesto.json` en claro y un
  `<fichero>.gz.age` por fichero. El manifiesto se sube el último: una versión sin manifiesto
  está a medias y no se lee.
- **Configuración:** [`configuracion/exportaciones.json`](../configuracion/exportaciones.json).

El repositorio `QuantuSync/droneobservatory-datos` (carpeta `exportaciones/`, etiquetas
`eodi-AAAA.MM.DD`) solo tiene las versiones 2026.10.01 a 2026.10.05. Desde el 13 de octubre de 2026
está archivado (solo lectura) y sin claves de despliegue.

**Nombre de la versión.** Es `AAAA.MM.DD`, la fecha UTC del día en que se genera. Desde el
formato 1.9.0, una segunda versión del mismo día (generada a mano) lleva `.N` detrás
(`2026.10.12.1`). El orden de las cadenas es el de las versiones. AEGIS tiene que aceptar el
patrón `^\d{4}\.\d{2}\.\d{2}(\.[1-9]\d*)?$`, porque el de hoy no admite el sufijo.

## 2. Credencial

Credencial de solo lectura: `%USERPROFILE%\.eodi\aegis_lectura.env`. Tiene el mismo formato que
`almacen.env`, con dos líneas, `ALMACEN_ID=…` y `ALMACEN_SECRETO=…`. El secreto nunca va a un
repositorio, a un registro ni a la salida de un programa.

Estado el 12 de octubre de 2026: **la credencial aún no existe**. Hetzner solo crea credenciales
S3 desde su consola web; no tiene API para ello. Esta sesión no tenía sesión abierta en la consola. Pasos para el dueño
(apartado 8). Hasta entonces se puede leer con `%USERPROFILE%\.eodi\almacen.env`, la credencial
del proyecto. Lee y escribe todo, así que solo se usa en el equipo del dueño.

AEGIS lee el almacén con esta credencial desde el 12 de octubre de 2026. La clave SSH
`aegis_lectura_ssh` se retiró el 13 de octubre: su clave de despliegue «aegis-lectura» se quitó del
repositorio de datos y el fichero está en `%USERPROFILE%\.eodi\retiradas\`. Comprobado ese día: la
importación de AEGIS desde el almacén termina con código 0 sin ella.

## 3. Cómo leer, verificar huellas y descifrar

Con un clon de este repositorio (Python 3.13, `pip install -r requirements.txt`):

```
set EODI_ALMACEN_CREDENCIALES=%USERPROFILE%\.eodi\aegis_lectura.env
python -m almacen.exportaciones listar
python -m almacen.exportaciones bajar --version 2026.10.12.1 --destino <carpeta nueva>
python -m almacen.exportaciones espejo --repositorio "C:\dev\Observatorio AEGIS\eodi-exportaciones"
```

- **`listar`:** devuelve las versiones completas, es decir, las que tienen manifiesto.
- **`bajar`:** deja los ficheros cifrados y el manifiesto, y comprueba la huella de cada cifrado.
- **`espejo`:** deja un repositorio git local con las mismas carpetas y etiquetas que tenía
  `droneobservatory-datos`. El importador de hoy puede leerlo pasando esa ruta como
  `--repositorio`.

Hay dos caminos para AEGIS:

- **Recomendado: leer el bucket directamente.** Por S3, sin git. Listar con
  `GET /droneobservatory-exportaciones?list-type=2&prefix=exportaciones/`, bajar el manifiesto y
  luego cada fichero.
- **El más corto: el espejo.** Lanzar `espejo` antes del importador de siempre.

Verificación de cada fichero, en este orden:

1. `sha256(<fichero>.gz.age)` tiene que ser `manifiesto.ficheros[i].cifrado.sha256` y su
   tamaño `cifrado.bytes`. Si no coincide, no se descifra.
2. Descifrar con age con la identidad de `%USERPROFILE%\.eodi\clave_age.txt` (la variable de
   usuario `EODI_CLAVE_AGE_FICHERO` ya apunta ahí): `pyrage.decrypt(datos, [identidad])` o
   `age --decrypt -i clave_age.txt`.
3. Descomprimir con gzip.
4. `sha256(en claro)` tiene que ser `ficheros[i].sha256` y su tamaño `ficheros[i].bytes`.
5. Validar cada registro contra `ficheros[i].esquema`, la ruta del JSON Schema dentro de la
   versión (los esquemas también van cifrados, en `esquema/…`).

Si algo no cuadra, no se importa nada; es lo que ya hace `tools/import_eodi.py`. La huella del
manifiesto (`sha256(manifiesto.json)`) identifica la versión. El cifrado no es determinista
(age usa una clave efímera), pero el contenido en claro sí lo es.

## 4. Frecuencia

- **Cada lunes a las 03:47 UTC** (`eodi-exportacion.timer`). Tarda unos 2 minutos y suele
  estar en el bucket antes de las 03:50.
- **Si falla**, `estado.json` lo publica y la vigilancia abre la incidencia «La exportación
  semanal no se genera».
- **A mano**, se generan versiones extra con sufijo `.N`.

La tarea de AEGIS de los lunes a las 07:00 hora local va bien después de la exportación.

## 5. Ficheros y esquemas

Cada fichero lleva su esquema en `esquema/` dentro de la versión:

- **`esquema/eodi/`:** los de la base, versión 1.19.0, con la marca de visibilidad de cada
  campo.
- **`esquema/exportacion/`:** los propios, formato 1.12.0.
- **`esquema/catalogo/`:** los del catálogo.

El manifiesto da también:

- `version_formato`, `version_esquema` y `version_vocabulario`;
- `creditos`: autor, ORCID, licencia CC BY 4.0, cita y dirección;
- desde 1.9.0, `terceros` y `excluidos`.

Formato de los ficheros: `.jsonl` lleva un registro por línea; `.json` es un documento.

| Fichero | Esquema | Qué es | Origen |
| --- | --- | --- | --- |
| `incidentes.jsonl` | `eodi/incidente` | Cada incidente entero, campos públicos e internos, también fundidos y retirados. `procedencia` por campo, `nivel_detalle` (A–D), `presencia_dron`, `trafico_aereo` (cierre medido, respuesta militar, interferencia GNSS), `condiciones` (meteorología, astronomía), `deduccion` (clases compatibles, descartadas e indeterminadas con sus reglas), `tipo_dron` (rasgos con su cita, probabilidades y `publicado.compatible`) | Por campo en `procedencia`: medido, oficial, registro, oficial_citado, parte, prensa o deducido, con su método y su regla. El valor de prensa sustituido queda en `sustituye` |
| `afirmaciones.jsonl` | `exportacion/afirmacion` | Cada dato por fuente, sin filtrar ninguna, con su código del Almirantazgo, su confianza de extracción y si sigue vigente | El de su fuente |
| `episodios.jsonl` | `eodi/episodio` | Episodios (series de incidentes) | Regla |
| `ucrania_ataques.jsonl` | `eodi/ataque_ucrania` | Ataques de cada noche: partes de la Fuerza Aérea de Ucrania y del Ministerio de Defensa ruso, foco térmico, luces, condiciones, deducción, restricciones de aeropuertos | parte, oficial, medido o deducido, por campo |
| `ucrania_regiones.jsonl` | `exportacion/region_ucrania` | Cada región de cada ataque | Por campo |
| `guerra_impactos.jsonl` | `eodi/impacto_guerra` | Impactos con lugar (localidad, instalación, comunidad o **distrito**, con su radio real), foco térmico y deducción | parser, extractor (con confianza) o regla; foco medido |
| `guerra_mensajes.jsonl` | `exportacion/mensaje_guerra` | Cada mensaje de los canales de guerra leído, sin texto | Registro de lectura |
| `restricciones_aeropuertos.jsonl` | `eodi/restriccion_aeropuerto` | Restricciones de Rosaviatsia | oficial |
| `frecuencias.json` | `exportacion/frecuencias` | Incidentes por categoría, país y mes, con el sesgo de cobertura declarado (sin corregir) | Recuento |
| `descartes.jsonl` | `exportacion/descarte` | Noticias rechazadas, partes fallidos, duplicados, fusiones dudosas, desmentidos y retirados, con su motivo | Registro |
| `contexto_pais.jsonl` | `exportacion/contexto_pais` | Cifras oficiales agregadas por país (contexto, no incidentes) | oficial, transcripción |
| `previsiones.jsonl` | `exportacion/prevision` | Previsiones registradas antes de conocer el resultado | Calculado, con método y fecha |
| `rutas_noches.jsonl`, `rutas_grupos.jsonl` | `exportacion/ruta_noche`, `ruta_grupo` | Rutas publicadas en la web y estadísticas de sus grupos | Extremos de la Fuerza Aérea, oficial; lo demás, calculado |
| `encuentros.jsonl`, `estadisticas_oficiales.jsonl`, `documentos_oficiales.jsonl` | `eodi/encuentro`, `estadistica_oficial`, `documento_oficial` | UK Airprox, cifras oficiales y documentos oficiales leídos, con su cruce con los incidentes | oficial |
| `catalogo_drones.json`, `catalogo_fuentes.json`, `zonas_lanzamiento.json` | `catalogo/…` | Catálogo de prestaciones de drones con la fuente numerada de cada cifra, y zonas de lanzamiento | La fuente de cada cifra |
| `clases_dron.json` | `exportacion/clases_dron` | Clases del motor con su envolvente por campo (límites de movimiento) | deducido de la fuente de cada cifra |
| `catalogo_novedades.json`, `catalogo_tacticas.json`, `catalogo_apariciones.json`, `deduccion_validacion.json` | `exportacion/…` | Catálogo vivo y validación del motor de deducción | Regla |
| `vocabulario.json` | `exportacion/vocabulario` | Correspondencia con las categorías y clases de AEGIS (1.4.0) | Configuración |
| **`fuerza_aerea_seguimiento.jsonl`** (nuevo) | `exportacion/fuerza_aerea_mensaje` | Mensajes de seguimiento de la Fuerza Aérea de Ucrania (t.me/kpszsu) de todas las noches del archivo, desde 2022. Cada aviso: tipo (`ataque`, `reaccion`, `reconocimiento`), grupo, número, `zona` y `destino` con `lat`, `lon` y `radio_km`, `rumbo` en grados desde el norte y regiones ISO. Son zonas y direcciones, **no posiciones** | Lo que dice el mensaje, oficial (parser). El punto y el radio de cada zona, deducido (nomenclátor) |
| **`neptun_pistas.jsonl`** (nuevo) | `exportacion/neptun_pista` | Pistas archivadas de NEPTUN (desde el 4 de octubre de 2026), una por amenaza de tipo `uav`, `fpv` o `recon`, punto a punto. Cada punto: `t`, `lat`, `lon`, `rumbo`, `kmh`, `numero`, `incertidumbre_km`, `confianza`, `calidad_posicion`, `confirmaciones`, `region` y `localidad`. Misiles, bombas guiadas y aviones no entran | **deducido por NEPTUN**, `estimacion: true`, `radar: false`. `atribucion` obligatoria y `aviso` |
| **`rutas_reconstruidas.jsonl`** (nuevo) | `exportacion/ruta_reconstruida` | Reconstrucción de las rutas de cada noche cerrada con los mensajes de la Fuerza Aérea, **se publique o no**: tramos con `precision_km`, recorridos y grupos (tamaño, velocidad, divisiones y uniones). `publicada` dice si está en la web | deducido (regla `rutas-1.0.0+recorridos-1.0.0`). Incertidumbre: `precision_km` y `validacion` (error medido contra NEPTUN: mediana de 62,1 km frente a 62,2 km de la línea recta, `pasa: false`; por eso no se publica) |
| **`cierres_medidos.jsonl`** (nuevo) | `exportacion/cierre_medido` | **Todas** las interrupciones medidas de los aeropuertos, casadas o no con un incidente. `anomalia` sigue el esquema `eodi/comun#/$defs/anomalia_trafico`: inicio, fin, duración, llegadas y salidas perdidas frente a la línea base, desvíos, esperas, cobertura y estado | medido (adsb.lol, ODbL 1.0) |
| **`prevision_validacion.json`** (nuevo) | `exportacion/prevision_validacion` | La previsión publicada (`documento`, esquema `urn:eodi:prevision:1.0.0`): riesgo de frontera de cada noche por país (**Rumanía, Moldavia** y los demás que pasan su comprobación), previsión semanal, comprobación sobre los datos pasados (área bajo la curva, mejora sobre la frecuencia) y `registro` de lo previsto **puntuado con lo que pasó** | deducido (regla `prevision-1.0.0`, con la fecha de cálculo) |
| **`tipo_dron_validacion.json`** (nuevo) | `exportacion/tipo_dron_validacion` | Calibración del tipo de dron (acierto por tramo de probabilidad) | deducido |
| **`barrera_titulares.json`** (nuevo) | `exportacion/barrera_titulares` | Estado de la barrera de titulares (retenidos, resueltos a nivel de país o retirados), veredicto de cada incidente activo (su cita respalda el titular o está justificado a mano) y titular del artículo que lo respalda | Respaldos, prensa. Estado y veredictos, deducido |

**Tamaño.** Medido en el ensayo del 12 de octubre de 2026 con la base real: 72 ficheros, 39 de
datos y 33 esquemas. En claro ocupan 253 MB, frente a 181 MB de la 2026.10.12. Comprimidos con
gzip y cifrados, que es lo que se descarga, ocupan **15,2 MB**, frente a 11,0 MB. Cada fichero ya
se comprimía por separado.

| Fichero nuevo | Registros | En claro | Cifrado |
| --- | --- | --- | --- |
| `fuerza_aerea_seguimiento.jsonl` | 38 643 | 35,5 MB | 2,36 MB |
| `neptun_pistas.jsonl` | 12 197 | 15,3 MB | 0,67 MB |
| `cierres_medidos.jsonl` | 14 476 | 13,1 MB | 0,60 MB |
| `rutas_reconstruidas.jsonl` | 877 noches | 7,2 MB | 0,56 MB |
| `barrera_titulares.json` | 445 | 43 KB | 2 KB |
| `prevision_validacion.json` | 1 | 24 KB | 4 KB |
| `tipo_dron_validacion.json` | 1 | 27 KB | 2 KB |

Crecen cada semana `neptun_pistas.jsonl` (unos 2 MB en claro por día de archivo, 0,1 MB
cifrado) y `fuerza_aerea_seguimiento.jsonl`. Los demás crecen poco.

Lo que ya iba y conviene saber: el tipo «compatible» de cada incidente va en
`incidentes.jsonl`, en `tipo_dron.publicado.compatible` y `deduccion.compatibles`, como deducido
con su regla. La cita que respalda cada incidente va en `fuentes[].frase_origen`. Los impactos a
nivel de distrito van en `guerra_impactos.jsonl`, en `lugar.nivel` igual a `distrito`.

## 6. Qué es nuevo respecto a la versión 2026.10.01

La 2026.10.01 (formato 1.0.0, esquema 1.2.0) traía 8 ficheros: `incidentes`, `afirmaciones`,
`episodios`, `ucrania_ataques`, `ucrania_regiones`, `frecuencias`, `descartes` y
`vocabulario`. AEGIS tiene importadas de la 2026.10.01 a la 2026.10.05 (formato 1.4.0). Desde
entonces:

- **Formatos 1.2.0 a 1.4.0 (ya en la 2026.10.05):**
  - ficheros nuevos: `catalogo_*`, `clases_dron`, `zonas_lanzamiento`, `deduccion_validacion`,
    `contexto_pais`, `encuentros`, `estadisticas_oficiales`, `documentos_oficiales`,
    `guerra_impactos`, `guerra_mensajes` y `restricciones_aeropuertos`;
  - en los incidentes, el mejor origen en cada campo y `sustituye`.
- **Formatos 1.5.0 a 1.8.0 (desde la 2026.10.12):**
  - ficheros nuevos: `previsiones.jsonl`, `rutas_noches.jsonl` y `rutas_grupos.jsonl` (1.7.0,
    con los recorridos unidos);
  - `creditos` en el manifiesto (1.8.0);
  - esquema de la base 1.16.0, con `tipo_dron`, `trafico_aereo.interferencia_gnss` y lugares de
    distrito.
- **Formato 1.9.0:**
  - los siete ficheros marcados como nuevos en el apartado 5;
  - `terceros` y `excluidos` en el manifiesto;
  - el sufijo `.N` en el nombre de la versión.
- **Formato 1.10.0 (esta guía, desde el 13 de octubre de 2026), esquema de la base 1.17.0:**
  - cada fuente de `incidentes.jsonl` puede llevar `copia_archivada` (`enlace` a la copia en
    Internet Archive, la más cercana a la fecha de la fuente, y `fecha` de esa copia en UTC) y
    `enlace_caido: true` cuando el original ya no lleva al artículo (falló dos veces seguidas con
    al menos una hora entre medias: 404 o 410, error del servidor, dominio que ya no existe, sin
    respuesta o redirección a la portada). Los dos son campos opcionales: una fuente sin copia
    no los lleva. Los da `recogida/archivo_web.py` (servicio `eodi-archivo`) y son los mismos
    que se ven en la web;
  - ningún fichero nuevo ni quitado; las demás formas, iguales.
- **Formato 1.11.0 (desde el 13 de octubre de 2026), esquema de la base 1.18.0:**
  - un incidente que juntaba sucesos distintos se ha separado (`docs/sucesos_mezclados.md`). El
    primero de EODI-2026-00072 es el cierre del aeropuerto de Vilna del 13 de septiembre de 2026
    y el otro, el derribo de la noche del 14 al 15. Cada parte es una ficha con su identificador;
    la que ya existía para el mismo suceso se queda y la otra lleva `fusionado_en`, como
    cualquier fusión. EODI-2026-00072 sigue en `incidentes.jsonl` con `fusionado_en`:
    EODI-2026-00007, el cierre;
  - campo opcional `relacionados` en el incidente: una lista de `{id, separado_de, nota: {es,
    en}}` con las otras fichas en que se separó el incidente `separado_de`. Es un enlace entre
    fichas, no un dato del suceso, y por eso no lleva procedencia (como `fusionado_en`);
  - las fronteras de los polígonos siguen la posición de la Unión Europea: un punto de Crimea o
    de Sebastopol es Ucrania (antes, Rusia, como en Natural Earth). No cambia ningún incidente
    de la recogida, que no cubre Ucrania ni Rusia; cambian las distancias a Rusia del motor de
    deducción para los puntos cercanos a Crimea;
  - ningún fichero nuevo ni quitado; las demás formas, iguales.

  El importador de AEGIS (`tools/import_eodi.py`) importa solo los incidentes activos (sin
  `fusionado_en` ni `retirado`) e ignora los campos que no usa: la separación entra sola, sin
  cambiar nada, y el campo nuevo no le estorba.

- **Formato 1.12.0 (desde el 14 de octubre de 2026), esquema de la base 1.19.0:**
  - campo interno opcional `control.modelos` en el incidente: qué modelo decidió cada dato de la
    ficha (nombre del campo de la ficha → identificador del modelo), el de la extracción y, en
    los datos que corrigió el control, el de la verificación (`docs/modelos.md`). Los incidentes
    de antes del 14 de octubre de 2026 no lo tienen. Como `control` no es un dato del suceso, no
    lleva procedencia;
  - ningún fichero nuevo ni quitado; las demás formas, iguales.

  El importador de AEGIS (`tools/import_eodi.py`) no valida el bloque `control` ni usa ese campo:
  importa igual (comprobado con una versión generada en el ensayo del 14 de octubre de 2026).

Todos los cambios son compatibles. Ningún fichero de antes cambia de forma (en 1.10.0 solo se
añaden dos campos opcionales a las fuentes, en 1.11.0 uno al incidente y en 1.12.0 uno interno a su
control), y los seis que lee AEGIS hoy son iguales: `incidentes`, `encuentros`, `clases_dron`, `catalogo_drones`,
`catalogo_fuentes` y `vocabulario`. Por eso el número principal no sube.

## 7. Lo que no se exporta y por qué

- **Alertas oficiales de Ucrania de alerts.in.ua** (por región, distrito y comunidad, con inicio,
  fin, nivel y amenazas). Sus condiciones (<https://devs.alerts.in.ua/>, «Відмова від
  відповідальності») dicen «Не використовуйте API для критичної інфраструктури»: no usar la
  API para infraestructura crítica. AEGIS protege puertos del Estado, así que no entran. Siguen
  archivadas solo en el servidor. El manifiesto lo dice en `excluidos`.
- **Interferencia GNSS diaria por celda** (`gnss_diaria`, más de un millón de filas) y
  **cobertura por aeropuerto y día** (`cobertura_trafico`). Lo de cada incidente va en
  `incidentes.jsonl` (`trafico_aereo`). La tabla entera no aporta a AEGIS más que tamaño.
- **Trazas en bruto** de adsb.lol, de METAR y del flujo de NEPTUN (sus alertas y sus mensajes
  de texto). Están en el disco del servidor y van resumidas en los ficheros de arriba.
- **Texto de los mensajes de los canales de guerra** (como hasta ahora).

## 8. Credencial de solo lectura: pasos para el dueño

Hetzner no tiene credenciales de solo lectura ni de un solo bucket: cada credencial vale para
**todos los buckets de su proyecto, con lectura y escritura**. Lo más seguro que permite, y es
lo que recomienda Hetzner, es esto: la credencial vive en un **proyecto aparte, sin buckets**, y
la política de `droneobservatory-exportaciones` le da `s3:GetObject` y `s3:ListBucket` y nada
más. Así no puede escribir en ningún bucket del observatorio ni leer los demás. La credencial
del servidor no cambia.

1. Hetzner Console → *+ New project* → nombre `AEGIS-lectura`. Apuntar su número, la cifra de
   `console.hetzner.com/projects/<número>/…`.
2. En ese proyecto: *Security* → *S3 credentials* → *Generate credentials*, descripción
   «lectura-exportacion». Guardar el par en `%USERPROFILE%\.eodi\aegis_lectura.env`, en el
   formato de `almacen.env`. El secreto solo se ve una vez.
3. En un clon del observatorio, con la credencial del proyecto EODI:
   `python -m almacen.lectura_exportacion politica --proyecto <número> --clave-id <Access Key>`.
4. Comprobar: `python -m almacen.lectura_exportacion comprobar --credenciales
   %USERPROFILE%\.eodi\aegis_lectura.env`. Tiene que salir todo «bien», con salida 0:
   - lista las versiones y descarga un fichero con su huella;
   - no puede escribir ni borrar en el bucket;
   - no puede listar ni escribir en `droneobservatory-almacen`, `-reserva`, `-archivo`, `-base`
     ni `-replica`.

   La comprobación no escribe secretos en ninguna parte.

El pendiente del blindaje (separar «servidor» y «lectura-exportacion») queda así: «servidor»
sigue siendo la credencial del proyecto EODI, y «lectura-exportacion» es la de `AEGIS-lectura`.

## 9. Qué tiene que cambiar AEGIS

1. **Origen:** el bucket en vez de `git@github.com:QuantuSync/droneobservatory-datos.git`. O el
   espejo local, apuntando el importador a su ruta.
2. **Credencial:** `%USERPROFILE%\.eodi\aegis_lectura.env` en vez de `aegis_lectura_ssh`. La
   identidad age es la misma.
3. **Patrón de versión:** aceptar el sufijo `.N`. La 2026.10.12 y la 2026.10.12.1 son las
   primeras que AEGIS no tiene.
4. **Ficheros nuevos** que pueden servirle, siempre como evidencia neutra:
   - `cierres_medidos.jsonl` (medido);
   - `fuerza_aerea_seguimiento.jsonl` (oficial con zonas deducidas);
   - `neptun_pistas.jsonl`: estimación, nunca como medida de sensor, y con la atribución
     visible si se muestra;
   - `rutas_reconstruidas.jsonl`: deducido, con su error medido;
   - `prevision_validacion.json`: deducido.

   La regla de admisión de AEGIS sobre lo que entra en un parámetro tiene que decidir qué
   orígenes admite de estos ficheros. Hoy no admite ni prensa ni parte.
5. **Tarea programada:** sigue los lunes a las 07:00 hora local. Avisar si `listar` no responde,
   en vez de quedarse en «sin version nueva».
