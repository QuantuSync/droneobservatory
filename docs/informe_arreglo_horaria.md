# Arreglo de la recogida horaria

30 de septiembre de 2026. Diagnóstico de las ejecuciones de `recogida.yml` desde el
28 de septiembre, causas y arreglos. Las horas son UTC.

## 1. Diagnóstico

### 1.1 Ejecuciones desde el 28 de septiembre

El workflow está programado cada hora en el minuto 17. GitHub no dice a qué franja
corresponde cada ejecución programada: la columna «programada» es la franja anterior
más cercana y el retraso es, por tanto, un mínimo.

| N.º | Origen | Programada | Hora real | Duración | Resultado | Extractor (candidatos / llamadas) |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | programada | 28-sep 05:17 | 28-sep 05:30 (+13 min) | 2 min 47 s | correcta | sin extractor aún |
| 7 | a mano | — | 28-sep 09:48 | 5 min 46 s | correcta | 29 / 29 |
| 8 | a mano | — | 28-sep 10:12 | 2 min 31 s | correcta | 0 / 0 |
| 9 | a mano | — | 28-sep 12:38 | 4 min 45 s | correcta | 7 / 7 |
| 10 | a mano | — | 28-sep 13:31 | 4 min 37 s | correcta | 1 / 1 |
| 11 | a mano | — | 28-sep 13:54 | 4 min 10 s | correcta | 0 / 0 |
| 12 | programada | 28-sep 13:17 | 28-sep 14:03 (+46 min) | 4 min 29 s | correcta | 1 / 1 |
| 13 | programada | 28-sep 20:17 | 28-sep 20:35 (+18 min) | 5 min 18 s | correcta | 6 / 6 |
| 14 | programada | 29-sep 00:17 | 29-sep 01:01 (+44 min) | 5 min 28 s | correcta | 12 / 12 |
| 15 | programada | 29-sep 06:17 | 29-sep 06:59 (+42 min) | 6 min 07 s | correcta | 12 / 12 |
| **16** | programada | 29-sep 13:17 | 29-sep 14:06 (+49 min) | **30 min 26 s** | **código 2** | **11 / 2, 9 fallidas** |
| 17 | programada | 29-sep 19:17 | 29-sep 19:26 (+9 min) | 5 min 54 s | correcta | 15 / 15 |
| 18 | programada | 29-sep 23:17 | 29-sep 23:45 (+28 min) | 4 min 38 s | correcta | 1 / 1 |
| 19 | programada | 30-sep 05:17 | 30-sep 05:38 (+21 min) | 7 min 33 s | correcta | 16 / 16 |
| 20 | programada | 30-sep 12:17 | 30-sep 12:41 (+24 min) | 6 min 58 s | correcta | 20 / 20 |

Quince ejecuciones: diez programadas y cinco a mano. Una sola terminó con código 2.

### 1.2 Ejecuciones programadas: esperadas y reales

De las 00:17 del 28 de septiembre a las 13:17 del 30 hay **62 franjas programadas** y
hubo **10 ejecuciones programadas**: faltan 52, el 84 %. Las que hubo llegaron entre 9 y
49 minutos tarde, y los huecos entre dos seguidas fueron de 4 a 8 horas y media (el mayor,
de las 05:30 a las 14:03 del 28, solo cubierto por las ejecuciones a mano). Ninguna de
las que faltan aparece como cancelada ni fallida: GitHub, sencillamente, no las lanzó.
El grupo de concurrencia no las descarta, porque ninguna ejecución duró una hora.

### 1.3 El código 2 de la ejecución 16

El registro de la ejecución (29 de septiembre, de 14:06 a 14:37):

- `fuerza_aerea_ua`: 4 partes, 3 leídos, 1 fallido. `mindef_ru`: 4 partes leídos.
- `gdelt`: 29 franjas, 9 candidatos nuevos. `oficiales`: 323 notas, 21 relevantes.
- `extractor`: 11 candidatos, 2 llamadas bien y 9 con
  `código 503 (desconocido) tras 4 reintentos`.

**Causa del código 2:** el servicio del extractor estuvo caído desde hacia las 14:12
hasta, al menos, las 14:36. Cada llamada recibía un 503 cuyo cuerpo no era el JSON de error del
servicio (de ahí «desconocido»: responde una pasarela, no el servicio). El cliente
reintentaba cada llamada 4 veces con esperas de 10, 20, 40 y 80 s, y el extractor seguía
con el candidato siguiente: 9 candidatos por unos 2 min 40 s son los 25 minutos que
sobran en la duración. Al acabar, `fallidas=9` ponía el código de salida a 2.

**Consecuencia:** la base se subió a la rama `estado`, pero el paso «Publicar los
ficheros si han cambiado» no se ejecutó, porque el paso anterior había salido con error.
Los ficheros públicos se quedaron sin el cambio de esa ejecución hasta la 17, cinco horas
después.

**Los 9 candidatos pendientes** se procesaron en la ejecución 17 (19:26): sus 15
llamadas son esos 9 y los 6 candidatos nuevos de GDELT. En la base de las 12:48 del 30 de
septiembre no queda ningún candidato pendiente en la ventana horaria.

No hubo más códigos 2. El parte fallido de la Fuerza Aérea no lo causa: un parte ilegible
se cuenta y se guarda, pero no cambia el código de salida.

### 1.4 El parte ucraniano fallido

Es la publicación [`kpszsu/81106`](https://t.me/kpszsu/81106), del 28 de septiembre a
las 14:06 (17:06 en Kiev), con el motivo `cifra de lanzados sin máximo`. Aparece como
fallida en todas las ejecuciones desde la 13 porque cada una relee 48 horas del canal.

No es un formato nuevo de parte. Es un avance de media tarde, con el ataque sin terminar:
«ворог продовжує атакувати Україну … Станом на 16.30 зафіксовано понад 100 ударних
безпілотників … десятки дронів ще в повітрі». El detector lo tomaba por parte (periodo,
verbo de ataque y cifra de drones) y el lector lo rechazaba, como está previsto, porque
«más de 100» no cabe en un rango. El parte de cierre del mismo ataque llegó hora y media
después ([`81127`](https://t.me/kpszsu/81127): 124 drones de 6.30 a 18.30) y se leyó
bien: es el ataque `EODI-UA-2026-1007`. No se perdió ningún dato.

### 1.5 Otros defectos encontrados al revisar

- **El límite de gasto diario contaba como fallo.** Al llegar al límite, el extractor
  dejaba de llamar y los candidatos sin llamada se sumaban a «fallidas»: código 2. No
  llegó a pasar, pero el 29 y el 30 de septiembre el gasto horario fue de 0,27 de los
  0,30 dólares diarios.
- **Un canal de partes que no responde tumbaba la ejecución.** Un fallo de descarga de
  la página del canal no se atrapaba: la ejecución entera salía con código 1, sin leer
  las demás fuentes, sin subir la base y sin publicar.
- **Nada limitaba el tiempo de un paso.** Solo existía el tope de 45 minutos del trabajo.

## 2. Arreglos

### 2.1 Un aviso no frena la publicación

`recogida.yml` guarda el código de salida de la recogida. Con 0 o con el código de aviso
(2) sigue y publica; un último paso, «Dejar en rojo una recogida con avisos», hace fallar
el trabajo si el código fue 2. Con cualquier otro código el trabajo se para en el paso de
recogida y no se publica, como antes.

### 2.2 Caídas del servicio del extractor

- El cliente distingue dos errores. **Temporales**: 408, 429, cualquier 5xx (500, 502,
  503, 504, 529…) y los cortes de conexión. **Definitivos**: todo lo demás (400, 401,
  403: petición inválida, clave inválida, saldo agotado).
- En la ejecución horaria un error temporal se reintenta **una vez**, a los 5 s (o lo que
  pida el servicio, con tope de 20 s). Si vuelve a fallar, el extractor da el servicio por
  caído en esa ejecución: no hace más llamadas y todos los candidatos quedan pendientes
  para la siguiente. Una caída como la del día 29 cuesta ahora unos segundos, no 25
  minutos. Las órdenes del histórico, que se lanzan a mano, conservan los 4 reintentos.
- La caída queda en el registro como aviso, con el código y el mensaje del servicio, y
  **no pone la ejecución en rojo**. La base guarda desde cuándo dura (fila `extractor` de
  la tabla de cursores); si pasa de **6 horas seguidas**, la ejecución queda en rojo. Una
  respuesta correcta del servicio cierra la caída.
- Un error definitivo para el extractor en esa ejecución y **sí la pone en rojo**, con el
  mensaje exacto del servicio.
- El error lleva el código, el tipo y el mensaje tal como los da el servicio, en una
  línea y con un tope de 300 letras. La clave nunca sale: se sustituye si el servicio la
  repite.
- Alcanzar el límite de gasto diario **no es un fallo**: se anota y los candidatos
  esperan al día siguiente.
- Tests con cada tipo de error: 429, 500, 502, 503, 504 y 529, cortes de conexión
  (tiempo agotado, conexión reiniciada, conexión cerrada sin respuesta, lectura
  incompleta), 400, 401, 403, saldo agotado, clave inválida, caída a mitad de tanda,
  caída de más de 6 horas y su cierre, y límite diario.

### 2.3 El avance de un ataque en curso no es un parte

Un texto que dice que el ataque sigue («продовжує атакувати») **y** da el recuento como
un corte abierto («станом на … зафіксовано понад N») deja de contar como parte y, por
tanto, como fallido; la auditoría de cobertura lo explica como «avance de un ataque en
curso». Hacen falta las dos señales: los partes de 2022 que empiezan por «продовжує
атакувати» con cifras cerradas y los de una noche terminada con cifra sin máximo siguen
como estaban. Comprobado contra las 78 278 publicaciones del canal en la caché local:
ninguna cambia de clasificación.

### 2.4 Tope de tiempo por paso

Cada paso recibe un plazo (`recogida/plazo.py`). El descargador no empieza una petición
ni una espera que no quepa en él. Los topes, con lo medido del 28 al 30 de septiembre:

| Paso | Medido | Tope | Si se agota |
| --- | --- | --- | --- |
| Fuerza Aérea (`fuerza_aerea_ua`) | 95 a 130 s (31 a 43 páginas) | 300 s | la fuente no se lee: aviso |
| Ministerio ruso (`mindef_ru`) | unos 12 s (3 o 4 páginas) | 120 s | la fuente no se lee: aviso |
| GDELT | 37 s (29 franjas; 1,3 s por franja) | 360 s | sigue la siguiente ejecución desde el cursor |
| Fuentes oficiales | 90 a 97 s | 240 s | fuentes sin leer: aviso |
| Extractor | hasta 165 s (29 candidatos) | 420 s | candidatos pendientes, sin aviso |

Suman **24 minutos** en el peor caso, frente a los 5 a 7 de una ejecución normal y a los
45 del trabajo. Cada paso puede pasarse de su tope, como mucho, lo que tarda la operación
que tenga en curso: 30 s una descarga y unos 2 minutos una llamada al extractor con su
reintento.

Además, un canal de partes que no responde es ahora un aviso (código 2): lo demás se
recoge, se sube y se publica.

### 2.5 Ejecuciones perdidas

El workflow de tests tiene un trabajo nuevo, `salud-recogida`, que consulta la última
ejecución correcta de `recogida.yml` y escribe en su resumen cuánto hace de ella, con una
anotación de aviso si pasa de 6 horas o no se puede saber. Solo informa: no lanza la
recogida ni hace fallar los tests.

## 3. Lo que queda sin decidir

1. **Ejecuciones programadas que no se lanzan.** Es el problema de fondo y no se arregla
   desde el repositorio: con 10 de 62, la recogida «horaria» es en la práctica una cada
   seis horas, y el aviso de salud (umbral de 6 horas) saltará a menudo. Opciones:
   programar más franjas por hora (el grupo de concurrencia evita que se pisen y una
   ejecución sin novedades cuesta unos 3 minutos), o lanzar `workflow_dispatch` desde un
   planificador externo. No se ha hecho ninguna de las dos.
2. **El aviso de salud solo se ve cuando hay un push o un pull request**, que es cuando
   corre el workflow de tests. En una semana sin cambios nadie lo mira.
3. **Un error definitivo ligado a un candidato concreto** (un 400 por su contenido)
   pararía el extractor en ese candidato en cada ejecución, en rojo, hasta que alguien
   intervenga. Es lo pedido (un 400 para el extractor), y hasta ahora no ha ocurrido. Si
   ocurre, la salida es apartar el candidato tras varios errores seguidos.
4. **Fuentes oficiales sin leer por tiempo** se han dejado como aviso (en rojo), igual
   que una fuente de partes sin leer. Si resulta ruidoso, puede pasar a simple anotación.
5. **Tras un corte de más de unos cinco días**, los 300 s de la Fuerza Aérea no dan para
   leer el canal hasta el cursor (la lectura es todo o nada) y la fuente quedaría en
   aviso en cada ejecución: habría que ponerla al día con `recogida.historico`. Antes el
   límite eran 500 páginas, unos 25 minutos.
6. **El mensaje de error del servicio va tal cual al registro**, que es público. No
   lleva la clave, pero sí el texto que el servicio quiera poner.
7. **Se tratan como temporales también el 408 y todos los 5xx**, no solo los códigos
   citados (429, 500, 502, 503, 504, 529).
8. **La fila de `81106` sigue en la tabla de partes fallidos** de la base como no
   resuelta, junto a otras diez del histórico. Ya no se cuenta en las ejecuciones (la
   publicación ha salido de la ventana de 48 horas), pero nadie la marca como resuelta.
9. **El paso de publicación no vuelve a traer `main`.** Si alguien hace un merge mientras
   corre una ejecución, su push se rechaza y los ficheros se publican en la siguiente.
