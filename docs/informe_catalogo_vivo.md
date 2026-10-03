# Catálogo vivo y datos para AEGIS

European Observatory of Drone Incidents, 3 de octubre de 2026. Las horas son UTC. Cambios:
PR #64 (catálogo 1.1.0, catálogo vivo, origen valor a valor, motor de deducción 1.1.0, fuentes
españolas y portuarias, barrido dirigido, esquema de la base 1.8.0, formato de exportación
1.4.0, vocabulario 1.4.0), PR #66, #69 y #70 (ajustes del catálogo vivo vistos en su primera
pasada), PR #67 (fusión de un mismo suceso partido en días seguidos), PR #68 (la exportación
admite la versión del catálogo vivo) y, en AEGIS, PR #50 (admisión del origen `registro` y
vocabulario 1.4.0). Todo es interno: la web no muestra nada nuevo.

## 0. Resumen

| | Antes | Después |
| --- | ---: | ---: |
| Modelos / clases / fuentes del catálogo | 48 / 12 / 147 | 59 / 13 / 251 en la configuración; 86 modelos y 279 fuentes con el catálogo vivo en la exportación 2026.10.03 |
| Modelos con aceleración (derivada, con fórmula y fuentes) | 0 | 18 |
| Fuentes que barre el catálogo vivo | — | 37 (2 diarias, 35 semanales) |
| Incidentes que sirve droneobservatory.eu | 473 | 508 |
| A–C con categoría admitida por AEGIS | 4 | 81 (registro de instalaciones) |
| A–C con hora / duración admitidas | 4 / 4 | 25 / 15 |
| A–C con número de drones admitido | 0 | 48 |
| A–C en España con categoría y fecha admitidas | 0 | 1 |
| A–C en puertos y presas | 0 | 4 |
| Direcciones de entrada (todos los activos) | 0 | 110 |
| Cruces de la OTAN con deriva resuelta | 2 de 48 | 22 de 52 |
| Incidentes de Europa con alguna clase descartada | 0 | 0 |
| Piezas de AEGIS que mueven la dinámica con datos reales | ninguna | la 4 (sectores) en aeropuerto |
| Gasto del extractor | — | 0,0032 USD (catálogo) + 0,83 USD (barrido dirigido) |
| Exportación para AEGIS | 2026.10.02 | 2026.10.03 (formato 1.4.0) |

## 1. Catálogo de prestaciones

### 1.1 Antes y después

| | Catálogo 1.0.0 | Catálogo 1.1.0 |
| --- | ---: | ---: |
| Modelos | 48 | 59 |
| Clases | 12 | 13 (nueva: `aeromodelo_ala_fija_pequeno`) |
| Fuentes numeradas | 147 | 251 |
| Campos por modelo | 29 | 39 |
| Modelos con velocidad máxima | 28 | 42 |
| Modelos con viento máximo | 18 | 25 |
| Modelos con autonomía | 32 | 43 |
| Modelos con techo | 27 | 31 |
| Modelos con aceleración horizontal / vertical | — | 18 / 18 |
| Modelos con ángulo de inclinación / velocidad de ascenso y descenso | — | 18 / 19 |

Campos nuevos: `angulo_inclinacion`, `velocidad_ascenso`, `velocidad_descenso`,
`relacion_empuje_peso`, `tiempo_0_100`, `factor_carga`, `angulo_alabeo`, `radio_viraje`,
`aceleracion_horizontal` y `aceleracion_vertical`. Cada cifra lleva su fuente (enlace, fecha de
consulta y tipo), la cita literal y, si dos fuentes no coinciden, las dos (la envolvente de la
clase toma el intervalo). Un campo sin fuente queda vacío y marcado `sin_fuente`.

### 1.2 Aceleraciones

Ningún fabricante de los modelos del catálogo publica la aceleración. Se deriva con física de
lo que sí publica, en [`proceso/deduccion/aceleraciones.py`](../proceso/deduccion/aceleraciones.py);
cada valor derivado lleva `derivada` con la fórmula, el supuesto y los datos de partida con su
fuente, y un test comprueba que el catálogo coincide con lo que da el código:

| Dato publicado | Fórmula | Resultado |
| --- | --- | --- |
| Ángulo máximo de inclinación θ de un multirrotor | a = g·tan θ (vuelo nivelado, empuje que sostiene el peso) | aceleración horizontal |
| Ángulo publicado de un modo que no es el manual (el modelo tiene modo manual sin ángulo publicado) | a ≥ g·tan θ | cota inferior |
| Ángulo θ | a ≥ g·(1/cos θ − 1) | cota inferior de la vertical |
| Relación empuje/peso r | a = g·(r − 1) | vertical |
| 0-100 km/h en t s | a ≥ (100/3,6)/t | cota inferior horizontal |
| Ala fija: factor de carga n, alabeo φ o radio de viraje con su velocidad | g·√(n² − 1), g·tan φ, V²/r | aceleración lateral |

Envolventes resultantes con el catálogo de la configuración (horizontal, m/s²): menos de 250 g
5,66-6,87; consumo hasta 7,12; profesional hasta 8,23. 78 valores derivados, ninguno de fuente
directa. Los modelos que añade el catálogo vivo llevan también sus aceleraciones derivadas
(PR #70); una clase con un modelo sin ángulo publicado queda sin cota de aceleración (§9).

### 1.3 FPV, militares y aeromodelos

- **FPV**: velocidades con fuente de DJI FPV, DJI Avata, iFlight Nazgul Eco y Evoque y de las
  fichas FPV de War&Sanctions (como datos de `fpv_militar_rf` y `fpv_fibra`, con el modelo de la
  fuente en la nota). La clase tiene ahora velocidad máxima en sus 7 modelos (antes 1) y viento
  en 3 (antes 1); envolvente de velocidad 8-55,6 m/s.
- **Militares**: viento máximo de Supercam S350 y ZALA 421-16E (la clase de ala fija táctica
  eléctrica pasa de 0 a 2 modelos con viento), velocidades de municiones merodeadoras (de 0 a 3
  modelos) y de ataque de largo alcance (de 2 a 4); modelos nuevos Geran-4 y Geran-5 (ataque a
  reacción) y Maya (señuelo), con sus casos de validación.
- **Aeromodelo de ala fija pequeño**: clase nueva (eléctrica, mediana, corto alcance) con cuatro
  modelos de referencia; la regla de descripción reconoce sus palabras en los testimonios.

## 2. Catálogo vivo

### 2.1 Qué hace

[`recogida/catalogo_vivo.py`](../recogida/catalogo_vivo.py) y
[`proceso/catalogo_vivo.py`](../proceso/catalogo_vivo.py), configurado en
[`configuracion/barrido_catalogo.json`](../configuracion/barrido_catalogo.json). Temporizador
`eodi-catalogo` a las 05:23 cada día ([`servidor/catalogo.sh`](../servidor/catalogo.sh), su propio
cerrojo, prioridad baja, tope 60 minutos). Lee la base de la rama `estado` y deja lo que encuentra
en `/home/eodi/datos/catalogo`; la recogida horaria lo guarda en la tabla `catalogo_vivo` de la
base, el motor de deducción lo usa y la exportación semanal lo lleva.

| Tipo de fuente | Ritmo | Fuentes | Cómo entra |
| --- | --- | --- | --- |
| Inteligencia | diario | War&Sanctions (GUR) | directo |
| Datos propios | diario | incidentes, UK Airprox, partes de la capa de guerra | directo |
| Fabricante | semanal | DJI (productos, anuncios, Enterprise), Skydio, Parrot, Quantum Systems, Delair, Tekever, ATLAS, Flyability | directo |
| Lista oficial de marcado de clase de la UE | semanal | EASA, EU Drone Port | directo |
| Autoridad (restos, partes) | semanal | 12: defensa e interior de Polonia, Rumanía, Moldavia, Lituania, Letonia, Estonia y Finlandia | directo |
| Análisis técnico | semanal | CAR, CSIS, RUSI, ISW, ISIS | directo |
| Prensa técnica | semanal | Militarnyi, Defence Express, The War Zone, Army Recognition, DroneDJ, DroneXL | candidata hasta una segunda fuente de otro sitio |

Cada sitio se lee respetando su robots.txt, con una pausa mínima entre peticiones, espera
creciente ante errores y el tope diario de reintentos de la recogida. Lo estructurado (fichas,
tablas, listas) lo lee el código; el extractor solo lee las frases con un nombre de modelo y una
cifra que el código no resuelve, con un esquema cerrado y validación por código (unidad de la
magnitud del campo, valor dentro de lo físico); presupuesto 0,10 USD al día y 3 USD la primera
pasada. Lo que encuentra se clasifica en modelos nuevos, cifras nuevas de modelos conocidos,
tácticas y apariciones de modelos en los datos propios. Una cifra nueva solo ensancha la
envolvente de su clase (nunca descarta más que antes) y sube la versión del catálogo
(`1.1.0+vivo.N`); cada cambio queda en un historial.

### 2.2 Primera pasada

3 de octubre de 2026, 10:35-11:09 (34 minutos, casi todo en las pausas entre peticiones):

| | |
| --- | ---: |
| Fuentes leídas | 37 de 37 |
| Fichas de War&Sanctions leídas | 203 |
| Hallazgos | 447 |
| Cifras nuevas admitidas | 52 |
| Modelos nuevos admitidos (sin clase decidida por código: entran en el registro, no en la deducción) | 326 |
| Modelos nuevos candidatos (solo prensa) | 1 |
| Tácticas | 31 |
| Candidatas confirmadas por una segunda fuente | 8 |
| Cifras rechazadas por unidad ajena al campo | 1 |
| Llamadas al extractor / cifras rechazadas por la validación | 2 / 3 |
| Gasto del extractor | 0,0032 USD |
| Versión resultante | `1.1.0+vivo.1` |

La primera pasada se hizo dos veces: en la primera, War&Sanctions marcaba como FPV algunos
nodrizas («Carrier of FPV drones»: Burya-20, Pchelka) y sus cifras (10 h de autonomía, 300 km)
ensanchaban la clase FPV, y la ficha del Avata 2 daba «autonomía 10 km». PR #66 lo corrige (el
nodriza no es un FPV; una cifra con una unidad que no es de la magnitud del campo no entra) y la
pasada buena es la segunda.

Al comparar esa pasada con las fichas se vieron tres modelos mal leídos: el DJI Flip sin velocidad
máxima (su ficha pone las condiciones de la medida antes del valor), el Mavic 2 con la velocidad de
ascenso como velocidad máxima y el Inspire 3 (4,3 kg) en la clase de consumo, y un nombre tomado
del título de la página («DJI Mini 4K | DJI Mini 2 SE- Especificaciones»). PR #69 corrige el lector;
esos modelos se retiraron del estado del catálogo vivo y una tercera pasada los volvió a leer: 12
cifras y 3 modelos más, versión `1.1.0+vivo.2`, en producción desde la pasada del motor de las 17:05
(466 s). La clase de menos de 250 g tiene velocidad 6-19 m/s y la profesional, aceleración
horizontal hasta 8,23 m/s².

## 3. Origen de cada valor

[`exportacion/mejor_origen.py`](../exportacion/mejor_origen.py) pone en cada campo exportado el
valor de mejor origen que tiene el observatorio y guarda el anterior en `procedencia.sustituye`:

| Campo | De dónde sale ahora | Origen |
| --- | --- | --- |
| `tiempo.inicio`, `tiempo.duracion` | cierre medido con el tráfico aéreo del aeropuerto | `medido` |
| `tiempo.inicio` | registro oficial (detalle oficial), o la hora que escribe una autoridad, convertida a UTC con la zona del país | `oficial`, `oficial_citado` |
| fecha del suceso de un incidente con fecha de publicación | la única interrupción medida del aeropuerto antes de la publicación, o un documento oficial del mismo sitio | `medido`, `oficial` |
| `objetivo.categoria`, `objetivo.nombre`, `objetivo.oaci`, `lugar.pais` | la instalación del nomenclátor (OpenStreetMap), por nombre, categoría y distancia | `registro` (nuevo) |
| `drones.numero`, `drones.patron` | frase de una autoridad o documento oficial; si solo lo dice la prensa, sigue siendo `prensa` | origen de la frase |

El origen `registro` está en el esquema de la base 1.8.0, en la exportación 1.4.0 y en el
vocabulario 1.4.0; AEGIS lo admite solo en los cuatro campos de la instalación (PR #50).

Medido sobre la exportación de la base de producción del 3 de octubre a las 14:30 (508 activos,
216 de nivel A–C) frente a la de la mañana con el código anterior (469 activos, 194 A–C). «Admitido»
es lo que AEGIS admite: medido, oficial, oficial citado, deducido y, en los cuatro campos de la
instalación, registro.

| Campo (incidentes A–C) | Antes: admitido / prensa | Después: admitido / prensa | Después, por origen |
| --- | ---: | ---: | --- |
| `tiempo.inicio` | 6 / 188 | 26 / 190 | medido 13, oficial 7, oficial citado 6 |
| `tiempo.duracion_min` | 2 / 15 | 14 / 13 | medido 13, oficial 1 |
| `drones.numero` | 32 / 162 | 70 / 146 | oficial citado 67, oficial 3 |
| `drones.patron` | 0 / 0 | 5 / 14 | oficial citado 5 |
| `objetivo.categoria` | 2 / 119 | 84 / 51 | registro 82, oficial 2 |
| `objetivo.nombre` | 2 / 118 | 84 / 50 | registro 82, oficial 2 |
| `objetivo.oaci` | 0 / 63 | 71 / 0 | registro 71 |
| `lugar.pais` | 2 / 192 | 81 / 135 | registro 79, oficial 2 |

Sobre todos los activos: hora de inicio admitida 7 → 33, duración 2 → 18, número de drones 38 → 79,
categoría 2 → 210 (registro 208). Las reglas de la fecha del suceso se aplican
a 27 incidentes que tenían la fecha de publicación: 12 por un cierre medido, 7 por la hora que
escribe una autoridad, 5 por la única interrupción medida antes de la publicación y 3 por un
documento oficial del mismo sitio. Los incidentes con fecha de publicación son ahora 207 de 508
(antes 193 de 469): los 31 que trae el barrido dirigido de §6 llegan casi todos con la fecha del
artículo, y la recogida horaria les aplica las mismas reglas cuando aparece el dato medido u
oficial.

## 4. Motor de deducción en Europa

Motor 1.1.0: usa la hora y la duración de mejor origen, el viento de esa hora (Open-Meteo), la
deriva hora a hora cuando solo se conoce el día (deriva 1.1.0: compatible si alguna hora lo es,
descartada solo si ninguna), las frases de testigos y autoridades para la regla de descripción,
la dirección de entrada declarada o deducida y el catálogo vivo.

Medido en producción: el motor que guardó la base de la mañana (motor 1.0.0, catálogo 1.0.0)
frente a la pasada completa de las 13:05 (motor 1.1.0, catálogo `1.1.0+vivo.1`, 305 s, 1,5 GB):

| | Antes | Después |
| --- | ---: | ---: |
| Incidentes en Europa evaluados | 467 | 508 |
| Con alguna clase descartada | 0 | 0 |
| Clases compatibles por incidente (media) | 7,88 de 12 | 8,09 de 13 |
| Cruces de la OTAN con deriva resuelta (compatible o no con la deriva) | 2 de 48 | 22 de 52 |
| Con dirección de entrada | — | 110 (108 deducida, 2 declarada) |
| Validación (casos con la clase real conocida) | 26 aciertos de 26, 0 fallos graves | 28 aciertos de 28, 0 fallos graves |

La validación incluye dos casos nuevos (Geran-4 y Maya). La clase real no se descarta en ninguno.
Ningún incidente de Europa tiene aún una clase descartada: lo que descarta es la altura, la velocidad
o la trayectoria observadas con su origen, y los incidentes de Europa no las traen (ver §9).

## 5. Direcciones de entrada y zonas de despegue

[`proceso/deduccion/direccion.py`](../proceso/deduccion/direccion.py): la dirección de entrada es
`declarada` cuando una autoridad escribe de dónde vino el dron («entró desde Bielorrusia») y
`deducida` cuando la tierra desde la que se puede despegar se concentra en un sector: 12 sectores
de 30°, fracción de tierra de las zonas de despegue de las clases compatibles; con una
concentración de 0,2 o más, el sector más cargado da `desde_grados`. Cada una va marcada.

Direcciones de entrada en producción (todos los activos con deducción): 110, de ellas 2
declaradas (aeropuertos) y 108 deducidas: aeropuerto 80, otra categoría 23, base militar 3, energía 1,
estadio 1.

Zonas de despegue y direcciones en los incidentes A–C cuya categoría admite AEGIS (la pieza 4 pide
al menos 5 por categoría):

| Categoría de AEGIS | Antes (2026.10.02) | Después (2026.10.03) | Pieza 4 |
| --- | ---: | ---: | --- |
| aeropuerto | 4 | 74 | activa (clase profesional, 74 zonas) |
| energía | 0 | 3 | inactiva (mínimo 5) |
| espacio público | 0 | 1 | inactiva |
| puerto | 0 | 3 | inactiva |
| agua (presas) | 0 | 0 | inactiva |

Direcciones de entrada en los incidentes A–C: aeropuerto 41, otra 13, base militar 1, energía 1,
estadio 1.

## 6. España, puertos y presas

### 6.1 Fuentes oficiales nuevas en la recogida

Comprobadas en vivo y añadidas a [`configuracion/fuentes_oficiales.json`](../configuracion/fuentes_oficiales.json)
(la recogida horaria las lee como las demás; el lector de RSS admite ahora también Atom):

| Fuente | País | Canal |
| --- | --- | --- |
| AESA (Agencia Estatal de Seguridad Aérea) | ES | RSS |
| Ministerio de Defensa, notas de prensa | ES | RSS |
| Puertos del Estado | ES | RSS |
| Consejo de Seguridad Nuclear, sucesos notificados | ES | RSS |
| La Moncloa, notas | ES | RSS |
| Autoridad Portuaria de Valencia | ES | RSS |
| Puerto de Gdańsk | PL | RSS |
| Puerto de Tallin | EE | RSS |
| Puerto de Køge | DK | RSS |

Las palabras de dron de GDELT incluyen ahora el gallego y el euskera, además del castellano y el
catalán.

### 6.2 Barrido dirigido de GDELT desde enero de 2025

[`recogida/barrido_dirigido.py`](../recogida/barrido_dirigido.py) y
[`servidor/dirigido.sh`](../servidor/dirigido.sh): los titulares con una palabra de dron de los 640
días del 1 de enero de 2025 al 2 de octubre de 2026 que nombran una instalación de España o un
puerto o una presa de Europa del nomenclátor (un nombre de una sola palabra solo cuenta escrito con
mayúscula; una localidad española solo tras «aeropuerto, central, cárcel, puerto… de»), más los
artículos que ya tenía la base con esos nombres. Una vez, el 3 de octubre:

| | |
| --- | ---: |
| Artículos hallados en GDELT | 1 077 |
| Artículos nuevos en la base | 973 |
| Candidatos tocados / enviados al extractor | 257 / 284 |
| Gasto del extractor (modo `dirigida`, tope 3 USD) | 0,83 USD |
| Incidentes publicados antes / después | 478 / 509 |

Incidentes nuevos: 7 en España (aeropuertos de Gran Canaria —dos—, Lanzarote, Fuerteventura y
Málaga; prisiones de Sevilla I en Alcalá de Guadaíra y de Tarragona), 22 en el puerto de Constanza
(Rumanía, explosiones de drones de junio a septiembre de 2026), 6 en el aeropuerto de Leipzig/Halle y
1 en el de Bremen. Fusión: al rehacer, los incidentes que encajan con varios anteriores que a su
vez encajan entre sí (noticias del mismo suceso fechadas en días seguidos) se funden ahora en uno
(PR #67, 4 fusiones en Leipzig y Constanza); la recogida de las 14:17 publicó 508.

### 6.3 Regla de lugar: Skrydstrup

Un titular que enumera instalaciones del mismo tipo («Esbjerg, Sonderborg, Skrydstrup») ya no da el
suceso a la que nombra la ficha si el candidato es de otra de la lista y ningún titular las nombra a
la vez: va a la del candidato. La base aérea de Skrydstrup (24 de septiembre de 2025) sigue sin
incidente propio en la lista de Wikipedia «2025 European drone sightings» (24 de 25): sus artículos
están fundidos con el de Aalborg desde antes y la regla nueva actúa al extraer de nuevo; ver §9.

## 7. Consumo en el servidor

| Trabajo | Dónde | Duración | Memoria | Ritmo |
| --- | --- | --- | --- | --- |
| Barrido del catálogo vivo, primera pasada | este equipo (la base cifrada en local) | 34 min, casi todo en pausas | 650 MB | una vez |
| Barrido del catálogo vivo, diario | servidor, 05:23, prioridad 15, tope 60 min | lo que toca cada día (War&Sanctions y datos propios; el resto, semanal) | — | diario |
| Motor de deducción, pasada completa (catálogo nuevo) | servidor, minuto 5 | 305 s | 1,5 GB | al cambiar el catálogo |
| Motor de deducción, incremental | servidor, minuto 5 | 84 s | — | cada hora |
| Lectura de GDELT para el barrido dirigido (640 días) | 162 días en el servidor, 478 en este equipo (12 hilos) | 2 min por día en el servidor; ~4 h en local | 450 MB | una vez |
| Barrido dirigido (búsqueda, lote del extractor, rehacer y publicar) | servidor, con el cerrojo de la recogida | 22 min | 2,6 GB | una vez |
| Exportación 2026.10.03 | servidor | 105 s | 1,7 GB | semanal (lunes) |

La recogida horaria sigue en unos 3,1-3,4 GB de pico. La primera pasada del catálogo se lanzó en el
servidor con un tope de 900 MB y no cabía (descifra la base); se hizo en local y se subió la carpeta
de datos. El barrido dirigido tuvo el cerrojo de la recogida de 13:04 a 13:25, y la recogida de las
13:17 no se lanzó; la siguiente terminó bien y publicó.

## 8. AEGIS

### 8.1 Lo que AEGIS admite

Versión 2026.10.03 (huella del manifiesto `478fd944f632ea9cca29c1b91412d6e541f538745ea06f92d4c559a93378a9d0`,
corte 2026-10-03T15:29:38Z), importada con `tools/import_eodi.py` y activada en AEGIS con la regla de
admisión de PR #50; la anterior es la 2026.10.02 de `docs/informe_amenaza_eodi.md` de AEGIS.

| Dato que pedía AEGIS | 2026.10.02 | 2026.10.03 |
| --- | ---: | ---: |
| Incidentes activos / A–C | 388 / 150 | 508 / 217 |
| A–C con categoría admitida | 4 (aeropuerto) | 81: aeropuerto 74, energía 3, puerto 3, espacio público 1 |
| A–C con hora admitida / duración admitida | 4 / 4 | 25 / 15 |
| A–C con número de drones admitido | 0 | 48 |
| A–C con patrón de vuelo admitido | campo inexistente | 5 (más 14 de prensa) |
| A–C con dirección de entrada | campo inexistente | 57 |
| A–C en España con categoría y fecha admitidas | 0 | 1 (aeropuerto) |
| A–C en puertos y presas | 0 | 4 (puertos) |
| Aceleración | campo inexistente | por modelo (derivada, con fórmula y fuentes); envolvente de clase en la profesional (hasta 8,23 m/s²) |
| Velocidad de los modelos FPV | sin dato | 8-55,6 m/s |

### 8.2 Qué pieza actúa

| Pieza | Con 2026.10.02 | Con 2026.10.03 |
| --- | --- | --- |
| 1. Cota de velocidad por clase (con identidad declarada) | estrechan menos de 250 g (24,7 m/s) y profesional (33,1 m/s) | estrecha la profesional (33,1 m/s); la de consumo no (37,9 > 35 m/s); la de menos de 250 g queda sin cota de velocidad en esta versión (ver §9) |
| 2. Clases compatibles | informa por pista | informa por pista, con 13 clases |
| 3. Comportamiento | aeropuerto: 4 incidentes, 279 encuentros | aeropuerto: 74 incidentes, 279 encuentros; energía 3, puerto 3, espacio público 1; 5 patrones de origen oficial citado |
| 4. Sectores de entrada | inactiva en todas | **activa en aeropuerto** (74 incidentes, clase profesional); el resto por debajo de 5 |
| 5. Vigilancia en España | normal (0 con fecha) | normal (1 con fecha; hacen falta 2 en 4 semanas) |
| 6. Ficha de instalación | aeropuerto 33, energía 2, espacio público 1 | con los 81 incidentes admitidos y su origen por dato |

### 8.3 Medición

`tools/medir_amenaza.py` con las mismas semillas, configuraciones `base` (piezas apagadas) y `todas`
(lo que corre por defecto), en el clon de AEGIS con la versión 2026.10.03 activa. La fila `base`
reproduce la del informe de AEGIS en todos los conjuntos (mismo entorno de medida).

| conjunto | versión | configuración | ejecuciones | contención % | escapes | semiancho med. / p95 (m) | semiancho vel. (m/s) | t detección / confirmación / 1.ª cámara (s) | falsas ALTA / pistas falsas confirmadas | GOSPA (m) | cambios de identidad |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- | ---: | ---: |
| Escenarios (25) | 2026.10.02 | todas | 25 | 99,967 | 9 | 9,67 / 295,37 | 17,52 | 0,5 / 2,5 / 22,2 | 0 / 0 | 50,32 | 378 |
| Escenarios (25) | 2026.10.03 | base | 25 | 99,967 | 9 | 9,67 / 295,37 | 17,52 | 0,5 / 2,5 / 22,25 | 0 / 0 | 50,32 | 378 |
| Escenarios (25) | 2026.10.03 | todas | 25 | 99,967 | 9 | 9,67 / 295,37 | 17,52 | 0,5 / 2,5 / 22,25 | 0 / 0 | 50,32 | 378 |
| Barrido de 640 | 2026.10.02 | todas | 640 | 99,920 | 227 | 5,17 / 26,99 | 15,65 | 3,5 / 5,5 / 17,5 | 1 / 1 | 35,98 | 166 |
| Barrido de 640 | 2026.10.03 | base | 640 | 99,920 | 227 | 5,17 / 26,99 | 15,65 | 3,5 / 5,5 / 17,5 | 1 / 1 | 35,98 | 166 |
| Barrido de 640 | 2026.10.03 | todas | 640 | **99,919** | **230** | 5,17 / 26,99 | 15,65 | 3,5 / 5,5 / 17,5 | 1 / 1 | 35,98 | 166 |
| Enjambre 64 × 5 | 2026.10.02 | todas | 320 | 99,967 | 415 | 181,13 / 385,56 | 82,07 | 0,5 / 2,5 / 177,5 | 0 / 1 | 73,25 | 20485 |
| Enjambre 64 × 5 | 2026.10.03 | base | 320 | 99,967 | 415 | 181,13 / 385,56 | 82,07 | 0,5 / 2,5 / 177,5 | 0 / 1 | 73,25 | 20485 |
| Enjambre 64 × 5 | 2026.10.03 | todas | 320 | 99,967 | 415 | 181,13 / 385,56 | 82,07 | 0,5 / 2,5 / 177,5 | 0 / 1 | 73,25 | 20485 |
| Cheste (119 × 5) | 2026.10.02 | todas | 595 | 99,907 | 252 | 1,34 / 5,38 | 10,60 | 18,0 / 20,0 / 18,5 | 0 / 0 | 38,01 | 257 |
| Cheste (119 × 5) | 2026.10.03 | base | 595 | 99,907 | 252 | 1,34 / 5,38 | 10,60 | 18,0 / 20,0 / 18,5 | 0 / 0 | 38,01 | 257 |
| Cheste (119 × 5) | 2026.10.03 | todas | 595 | 99,907 | 252 | 1,34 / 5,38 | 10,60 | 18,0 / 20,0 / 18,5 | 0 / 0 | 38,01 | 257 |
| Zenodo (2 × 5) | 2026.10.02 | todas | 10 | 100,000 | 0 | 1,77 / 3,81 | 10,97 | 0,0 / 2,0 / 0,5 | 0 / 0 | 32,78 | 2 |
| Zenodo (2 × 5) | 2026.10.03 | base | 10 | 100,000 | 0 | 1,77 / 3,81 | 10,97 | 0,0 / 2,0 / 0,5 | 0 / 0 | 32,78 | 2 |
| Zenodo (2 × 5) | 2026.10.03 | todas | 10 | 100,000 | 0 | 1,77 / 3,81 | 10,97 | 0,0 / 2,0 / 0,5 | 0 / 0 | 32,78 | 2 |

Lo único que cambia es el barrido de 640 en Barajas, el único emplazamiento de categoría
aeropuerto, donde la pieza 4 está ahora activa: con solo la pieza 4 encendida (`--config p4`), las
128 ejecuciones de Barajas dan exactamente lo mismo que con todas. En Barajas, contención 99,982 →
99,977 % (10 → 13 ticks de escape, en 3 de 128 ejecuciones), GOSPA medio igual (27,41 m; cada
ejecución se mueve como mucho 0,08 m en un sentido u otro, en 28 de 128), y sin cambio en el tiempo
de primera evidencia de cámara (17,0 s), la confirmación, los cambios de identidad ni las falsas
alarmas. En los demás conjuntos, las piezas activas con esta versión no cambian ninguna métrica: la
1 en la clase profesional solo actúa con identidad declarada; la 2, la 3 y la 6 informan; la 5 está
en nivel normal.

Lo que falta para que las piezas 1, 3 y 5 muevan la dinámica: la 1, la cota de la clase de menos de
250 g (llega con la próxima exportación) y una de consumo por debajo de 35 m/s (hoy 37,9); la 3,
etiquetas de comportamiento por incidente para calibrar contra datos reales (hay 5 patrones de
origen oficial citado); la 5, un segundo incidente admitido en España en cuatro semanas.

## 9. Pendientes con su arreglo

| Pendiente | Arreglo |
| --- | --- |
| La exportación 2026.10.03 lleva el catálogo `1.1.0+vivo.1`: la clase de menos de 250 g sin cota de velocidad (el DJI Flip entró sin ella) y el Inspire 3 en la clase de consumo. | Corregido en producción desde las 17:05 (`1.1.0+vivo.2`, PR #69 y #70, motor recalculado). Llega a AEGIS con la exportación semanal del lunes 5 de octubre: menos de 250 g vuelve a 6-19 m/s y la pieza 1 la estrecha (19·1,2 + 5,5 = 28,3 m/s). |
| Viento máximo de la clase de consumo sin cota: DJI no publica el del Mavic Pro. | Añadir a `configuracion/catalogo_drones.json` el viento del manual de usuario del Mavic Pro como fuente del fabricante. |
| Envolvente de aceleración de las clases de menos de 250 g y de consumo sin cota: Neo, Neo 2, Flip, Mavic Pro y Mavic 2 no publican el ángulo máximo en su ficha. | Leer el ángulo de inclinación de sus manuales de usuario (fuente del fabricante) y dejar que `aceleraciones.py` derive la aceleración. |
| Clases militares (merodeadoras, pistón, señuelo, reacción) sin velocidad ni viento de clase: los modelos nuevos de War&Sanctions no publican todas las cifras y un modelo sin dato deja sin cota a su clase. | Buscar esas cifras en una segunda fuente de inteligencia o análisis (CAR, ISIS) con el barrido semanal; hasta entonces la clase descarta solo por lo que publican todos sus modelos. |
| Ningún incidente de Europa con una clase descartada. | Lo que descarta es la altura, la velocidad o la trayectoria observadas con su origen: extraer la altura de los encuentros de UK Airprox (708 la traen) y de los informes de investigación, y las trazas de radar que publiquen las autoridades, como datos del incidente con origen oficial. |
| Pieza 4 de AEGIS inactiva en energía (3), espacio público (1), puerto (3) y presas (0). | Repetir el barrido dirigido de GDELT cada mes para esas categorías (el script ya lo admite con `--desde`) y seguir leyendo las autoridades portuarias añadidas. |
| Pieza 5 de AEGIS: en España hay un solo incidente admitido con fecha. | Lectores propios de las fuentes españolas que no tienen canal: Policía Nacional (lista de notas en JSON, `ajax_cargar_noticias.php`, 3 notas por llamada), Guardia Civil (las 10 últimas noticias de su lista estática), ENAIRE (sala de prensa con enlaces fechados) y delegaciones del Gobierno (página de enlaces). |
| La base aérea de Skrydstrup sigue fundida en el incidente de Aalborg (lista de Wikipedia: 24 de 25). | Volver a extraer el candidato de Aalborg con la regla nueva del titular que enumera instalaciones; la recogida lo hace cuando cambian sus artículos. |
| Puerto de Constanza: 22 incidentes, varios del mismo día y algunos de drones marinos de superficie. | Regla que separe los drones de superficie (dron marino, naval) de los aéreos y fusión de los del mismo día y sitio; la fusión por noches distintas es parte del trabajo siguiente. |
| La pieza 1 de AEGIS no usa todavía la aceleración (lee solo velocidad y viento de `clases_dron.json`). | En AEGIS, leer `aceleracion_horizontal` y `aceleracion_vertical` de la envolvente y usarlas en la propagación del conjunto recortado. |
| Autel no se lee (su web responde 403 a la recogida). | Tomar sus modelos de las listas de marcado de clase y de una ficha de distribuidor que se pueda leer. |
| La recogida horaria llega a 3,1-3,4 GB de pico; dos recogidas se cortaron por memoria cuando coincidieron con trabajos de prueba. | Los trabajos de prueba van con 1 GB como máximo, prioridad baja, fuera de los minutos 15 a 40 y de uno en uno. |
