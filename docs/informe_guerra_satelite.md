# Informe: guerra por satélite

Fecha: 3 de octubre de 2026. Rama `guerra-satelite`, PR #65. Esquema 1.9.0.

La capa de guerra del European Observatory of Drone Incidents suma cuatro piezas públicas que
salen de satélites y de los partes:

1. **Antes y después** de cada instalación alcanzada: la última imagen óptica de Sentinel-2 sin
   nubes anterior al ataque y la primera posterior, recortadas sobre el sitio, con una cortinilla
   en la ficha del impacto.
2. **Apagones vistos desde el espacio**: el brillo nocturno de las ciudades y regiones afectadas
   por cada ataque con objetivos de energía, antes y después, y la pérdida de luz cuando llega
   al umbral validado.
3. **Focos de calor en vivo**: los focos de NASA FIRMS de las últimas 24 horas sobre Ucrania y la
   Rusia europea, con los que coinciden con un impacto declarado resaltados.
4. **Corredores de ataque**: arcos desde las zonas de lanzamiento hasta las regiones alcanzadas,
   con el grosor según los drones del periodo.

## 1. Fuentes y acceso verificados

Comprobado el 3 de octubre de 2026, sin cuenta en ninguna de las tres.

| Pieza | Fuente | Acceso | Condiciones |
| --- | --- | --- | --- |
| Antes y después | Sentinel-2 L2A en el archivo abierto de AWS (bucket `sentinel-cogs`, GeoTIFF optimizados para la nube), con el catálogo STAC público de Earth Search (`earth-search.aws.element84.com/v1`, colección `sentinel-2-l2a`), de Element 84 | Sin cuenta ni clave (el registro de datos abiertos de AWS lo indica así) | «Access to Sentinel data is free, full and open» (aviso legal de los datos Sentinel); lo derivado lleva «Contains modified Copernicus Sentinel data <año>» |
| Luz nocturna | Banda día-noche de VIIRS de NOAA-20: gránulos SDR (`VIIRS-DNB-SDR`, radiancia calibrada y su calidad) y GEO (`VIIRS-DNB-GEO`, posición y ángulos de satélite, Sol y Luna) del archivo abierto de NOAA en AWS (`noaa-nesdis-n20-pds`) | Sin cuenta | «NOAA data disseminated through NODD are open to the public and can be used as desired» |
| Nubes de cada noche | Open-Meteo, Historical Forecast API (la misma de `recogida/meteo.py`) | Sin clave | CC BY 4.0, «Weather data by Open-Meteo.com» |
| Focos en vivo | NASA FIRMS, los CSV que la recogida ya descarga cada 3 horas | La clave de FIRMS que ya tiene el servidor | Atribución de FIRMS en la metodología |
| Corredores | Partes de la Fuerza Aérea de Ucrania (zonas declaradas) y `configuracion/zonas_lanzamiento.json` del motor de deducción | — | — |

**Black Marble.** El producto diario corregido por Luna y nubes (VNP46A2) se lista sin cuenta en
LAADS DAAC, pero la descarga de cada fichero devuelve la página de entrada de NASA Earthdata:
exige un token. Como la radiancia calibrada sí se publica sin cuenta en el archivo de NOAA, la
medida se hace con los gránulos SDR de VIIRS y con su propia corrección de Luna y de nubes
(apartado 3). No hace falta ninguna cuenta.

## 2. Antes y después de cada instalación alcanzada

[`recogida/satelite.py`](../recogida/satelite.py), [`recogida/cog.py`](../recogida/cog.py).

- **Qué impactos.** Los publicados con foco térmico detectado (de FIRMS) y, después, el resto de
  impactos en instalaciones; como los publica la web (sin retirados ni unidos a otro). Hoy son
  33: 17 con foco y 16 en instalaciones.
- **Recorte.** Con foco, centrado en los focos que contaron (lo que ardió); en una instalación con
  foco, en el punto medio entre la instalación y los focos, con lado de sobra para los dos; sin
  foco, en la instalación. Lado según el tipo (4 km refinerías, puertos y aeródromos; 2,5 km
  depósitos e industria; 1,5 km subestaciones; 3 km localidades), hasta 6 km.
- **Lectura.** De cada escena candidata se lee solo la ventana del recorte: primero la
  clasificación de escena (SCL, 20 m), y si vale, el color natural (TCI, 10 m). Una pareja son
  unos 9 MB leídos, frente a unos 200 MB por banda de una escena entera.
- **Nubes sobre el recorte.** Vale una escena con un 3 % o menos de nube media o alta, cirro o
  sombra de nube y un 2 % o menos sin dato dentro del recorte. La nubosidad de la escena entera
  no decide: sobre Kirishi, la escena S2A_36VVM del 3 de octubre de 2025, con un 49 % de nubes
  en la escena, tenía el recorte cubierto del todo, y la del 1 de octubre (0,03 %) limpio; esos
  recortes reales de la SCL son los de los tests.
- **Fechas.** Antes: la más reciente que vale en los 180 días anteriores al inicio del ataque
  (la misma ventana del impacto que usa el cruce con FIRMS). Después: la primera que vale desde
  el fin del ataque y su publicación. Si aún no hay ninguna, la pareja queda a medias y cada
  ejecución mira solo las escenas nuevas; de una misma toma va primero la tesela del huso UTM de
  la imagen de antes, para que no queden giradas.
- **Imagen.** El color natural de la ESA con la misma curva fija para todas (aclara los tonos
  medios); JPEG de calidad 85 sin metadatos, 10 m por píxel. Las imágenes, inmutables, y el
  índice `satelite/parejas.json` (escenas, fechas, nubes del recorte y la atribución) van al
  almacén público de Hetzner.
- **Web.** En la ficha del impacto, a todo el ancho: las dos imágenes con una cortinilla que se
  arrastra (y un deslizador para el teclado), las fechas, las escenas, el producto y «Contains
  modified Copernicus Sentinel data <años>». Con la pareja a medias, la imagen de antes y el
  aviso de que la posterior se añade sola.

<!-- RESULTADOS SATELITE -->

## 3. Apagones vistos desde el espacio

[`proceso/luces.py`](../proceso/luces.py) (regla), [`recogida/luces.py`](../recogida/luces.py)
(medida en el servidor).

- **Qué ataques.** Los que tienen un impacto con objetivo de energía y los que un mensaje oficial
  de una administración regional asocia a la energía (subestaciones, cortes de luz) entre el
  inicio del ataque y 18 horas después de su fin.
- **Qué ciudades.** 65 ciudades (41 de Ucrania y 24 de la Rusia europea) en
  `configuracion/ciudades_luces.json`, con su radio; la región suma las suyas.
- **Medida de una noche.** Los gránulos de NOAA-20 de 21:50 a 00:50 UTC (el paso de la 01:30
  hora local). De cada ciudad, el gránulo con el satélite más alto; la radiancia dentro del
  radio menos la mediana de un anillo de 10 a 25 km más allá (eso quita la Luna reflejada por el
  suelo y la nieve). Vale la noche con el satélite a 55° o menos del cenit, el Sol a 12° o más
  bajo el horizonte, el 60 % o más del círculo de la ciudad visto con calidad buena, el fondo a
  4 nW o menos y el 70 % de nubes o menos (Open-Meteo, a la hora del paso). Se leen solo las
  filas del gránulo que tocan las ciudades.
- **Regla.** Referencia: la mediana de las noches válidas de las 21 anteriores (3 como mínimo).
  Hay pérdida de luz cuando **dos noches o más** de la del inicio a 7 después del fin pierden el
  **50 %** o más frente a la referencia, en ciudades con **0,5 nW/(cm²·sr)** o más de referencia.
  Se publica la mayor, su noche, las noches con pérdida, la referencia y el brillo de esa noche,
  con origen «medido».

### Validación

Casos en `configuracion/validacion_luces.json`: 18 apagones documentados de 2024 a 2026 (20
ciudades, con la fuente de cada uno) y 9 controles (10 ciudades) de periodos sin ataques contra
la energía en la ciudad. Además, los controles automáticos: cada ciudad medida, cada 7 noches, la
misma regla en ventanas sin ataque (411 ventanas). Medidas 528 noches, en el servidor, entre el 3
y el 4 de octubre, con el trabajo limitado a 1 GB.

Elección de los umbrales (barrido de medida, nubes, referencia mínima, umbral y noches
necesarias sobre los mismos casos):

| Regla | Apagones detectados | Controles con pérdida | Ventanas automáticas con pérdida |
| --- | --- | --- | --- |
| Una noche, nubes ≤ 30 %, referencia ≥ 1 nW (la de partida) | 0 de 7 evaluables | 0 de 9 | 5 de 236 (2,1 %) |
| Una noche, nubes ≤ 70 %, referencia ≥ 0,5 nW | 4 de 13 | 0 de 9 | 42 de 411 (10 %) |
| Una noche, sin filtro de nubes | 8 de 19 | 1 de 9 | 28–34 % |
| **Dos noches, nubes ≤ 70 %, referencia ≥ 0,5 nW (la elegida)** | **2 de 13** | **0 de 9** | **3 de 411 (0,7 %)** |

Una sola noche oscura es casi siempre una nube que el modelo de Open-Meteo no ve: con una noche
basta, la regla da pérdida en una de cada diez ventanas sin ataque. Con dos noches, las falsas
alarmas bajan al 0,7 % y la regla publica solo pérdidas que se repiten.

Casos (pérdida máxima frente a la referencia; «noches» son las válidas después del ataque):

| Caso | Ciudad | Referencia (nW) | Noches | Pérdida máxima | Noches ≥ 50 % | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| Járkov, 22-03-2024 | Járkov | 0,33 | 0 | — | — | sin noches válidas |
| Járkov, 11-04-2024 | Járkov | 0,31 | 4 | 33 % | 0 | ciudad ya a oscuras |
| Sumy, 22-05-2024 | Sumy | 0,24 | 4 | 23 % | 0 | ciudad ya a oscuras |
| Lutsk, 26-08-2024 | Lutsk | 2,35 | 5 | 34 % | 0 | no detectado |
| Odesa, 17-11-2024 | Odesa | 1,54 | 5 | 43 % | 0 | no detectado |
| Oeste, 28-11-2024 | Rivne | 3,13 | 2 | 60 % | 2 | **detectado** |
| Oeste, 28-11-2024 | Lutsk | 2,70 | 1 | 58 % | 1 | una noche |
| Oeste, 28-11-2024 | Leópolis | 5,03 | 2 | 30 % | 0 | no detectado |
| Ternópil, 03-12-2024 | Ternópil | 1,33 | 0 | — | — | sin noches válidas |
| Járkov, 25-12-2024 | Járkov | — | 0 | — | — | sin referencia |
| Kiev, 10-10-2025 | Kiev | 6,68 | 1 | 28 % | 0 | no detectado |
| Chernígov, 20-10-2025 | Chernígov | — | 0 | — | — | sin referencia |
| Kremenchuk, 08-11-2025 | Kremenchuk | 0,91 | 2 | 23 % | 0 | no detectado |
| Odesa, 13-12-2025 | Odesa | 1,33 | 4 | 69 % | 2 | **detectado** |
| Kiev, 09-01-2026 | Kiev | — | 0 | — | — | sin referencia |
| Kiev, 20-01-2026 | Kiev | 15,61 | 3 | 59 % | 1 | una noche |
| Chernígov, 24-01-2026 | Chernígov | 0,91 | 0 | — | — | sin noches válidas |
| Járkov, 26-01-2026 | Járkov | 1,13 | 0 | — | — | sin noches válidas |
| Chernígov, 21-03-2026 | Chernígov | 0,31 | 5 | 6 % | 0 | ciudad ya a oscuras |
| Mykoláiv, 08-09-2026 | Mykoláiv | 0,36 | 5 | 19 % | 0 | ciudad ya a oscuras |
| 9 controles (10 ciudades) | | 0,30–3,85 | 2–8 | de −40 % a 39 % | 0 | 0 con pérdida |

Lo que se ve en los datos:

- Las ciudades del este y del norte llevan desde 2024 con el alumbrado casi apagado: Járkov,
  Sumy, Chernígov y Mykoláiv dan de 0,2 a 0,4 nW de referencia, del orden del ruido de la
  banda. Un apagón ahí no cambia lo que ve el satélite.
- En invierno la mayoría de las noches están cubiertas: de los 20 casos, 7 no tienen ninguna
  noche válida después o no tienen referencia, y los demás tienen de 1 a 5.
- Donde hay ciudad iluminada y noches despejadas, la caída se ve: Rivne y Odesa la dan dos
  noches; Lutsk (oeste, 28-11-2024) y Kiev (20-01-2026) la dan en la única noche válida o en
  una de tres.

**Pendiente y su arreglo.** Más noches válidas por ataque: medir también los pasos de Suomi NPP
y de NOAA-21, que llevan el mismo VIIRS y están en el mismo archivo abierto de NOAA sin cuenta
(`noaa-nesdis-snpp-pds`, `noaa-nesdis-n21-pds`). Son tres pasos por noche en lugar de uno, a
unos 50 minutos entre sí, y con nubes que se mueven, más noches con al menos un paso despejado. El arreglo es añadir los dos
buckets a `recogida/luces.py` (el formato es el mismo), quedarse con el paso de cada noche con
menos nubes y repetir la validación con la misma regla.

## 4. Focos de calor en vivo

[`recogida/focos_vivo.py`](../recogida/focos_vivo.py). Cada hora, de los CSV de FIRMS que la
recogida descarga cada 3 horas, los focos de las últimas 24 horas que caen en Ucrania (con lo
ocupado) o en una región de la Rusia europea (los polígonos de las regiones que dibuja la web;
la caja de FIRMS incluye también Rumanía, Moldavia o Bielorrusia), con los mismos filtros que el
cruce con los impactos:

- fuera VIIRS de confianza baja y MODIS por debajo de 30;
- fuera las fuentes de calor habituales: a menos de 1 km (VIIRS) o 2 km (MODIS) de un foco de
  los 30 días anteriores sin pasar de 4 veces su potencia, o en un emplazamiento con 3 focos o
  más en el año anterior sin pasar de 4 veces su percentil 90 (las antorchas de las refinerías,
  como Kirishi);
- fuera el fuego frecuente: un entorno de 5 km que ardió 15 días o más de los 30 anteriores
  repartido en 15 celdas de 0,01° o más (las ciudades del frente).

Se resaltan los que caen en el radio de búsqueda de un impacto publicado (sin partes diarios ni
FPV) entre 36 horas antes y 36 horas después de su publicación. El fichero
(`focos/ultimas24h.json`) va al almacén público con caché de 5 minutos y la web lo lee
directamente cada 10 minutos; la capa muestra «Focos de calor de 24 h · último dato hh:mm UTC».

Primera ejecución con los datos reales del servidor (3 de octubre, 09:51 UTC): 881 focos leídos
en Ucrania y la Rusia europea; 467 fuera por fuentes habituales de los 30 días, 178 por
emplazamientos del año y 11 de confianza baja; 225 publicados, 3 de ellos coincidentes con un
impacto declarado. 10,8 kB, 2,3 s y 251 MB (la primera del día, con el resumen anual de
emplazamientos, 9 s y 377 MB).

## 5. Corredores de ataque

[`web/src/datos/guerraSatelite.ts`](../web/src/datos/guerraSatelite.ts). Se calculan en la web
para el periodo de la línea de tiempo:

- **Contra Ucrania**: de cada zona de lanzamiento que nombra el parte de la Fuerza Aérea (casada
  con `zonas_lanzamiento.json` por sus raíces, como el motor de deducción; de varias zonas con el
  mismo nombre, la primera con punto) a cada región del ataque. Su cifra son los drones lanzados
  en los ataques del periodo que salieron de esa zona (entre otras, si el parte nombra varias) y
  alcanzaron esa región; los tramos cuyas cifras ya están en otro parte no se suman dos veces.
  Hoy casan 862 ataques con 18 zonas con punto; «ТОТ Донецької обл.» es una zona del catálogo
  sin punto y no tiene arco.
- **Contra Rusia**: el parte ruso da los derribos por región; el arco sale del punto de la
  frontera de Ucrania más cercano al centro de la región y su cifra son esos derribos.
- **Dibujo**: arcos suaves sin animación, en el violeta de la capa de guerra con opacidad 0,18 y
  grosor de 0,4 a 3 px según la raíz de los drones (sobre el máximo del periodo), por debajo de impactos, focos y ciudades; los
  arcos sin cifra no se dibujan. Se ocultan con «Corredores» en el selector de capas y, al
  pulsarlos, la ficha da origen, destino, drones del periodo y número de ataques.

## 6. Servidor

<!-- SERVIDOR -->

## 7. Web

- Selector de capas: con la capa de Ucrania encendida aparecen «Corredores», «Focos 24 h» y
  «Luz nocturna», encendidas por defecto (en el teléfono, en el menú).
- Política de contenido: `img-src` admite el almacén público (las imágenes de Sentinel-2); un
  test lo comprueba.
- Metodología (ES y EN): apartado «Guerra por satélite» y las atribuciones de Copernicus
  Sentinel y de NOAA. Ayuda del mapa: las tres marcas nuevas.
- Comprobado en escritorio y en 360×800, 390×844 y 412×915, en local, en la vista previa del
  PR y en producción (apartado 9).

## 8. Color de la capa de guerra

Toda la capa de guerra (regiones de Ucrania y de Rusia, impactos, corredores, focos de 24 horas,
ciudades sin luz, marcas de los focos de un impacto, línea de la cortinilla y sus leyendas) usa
una sola familia **violeta azulada**:

| Uso | Color |
| --- | --- |
| Principal: regiones de Ucrania, impactos, corredores | `#9d7bff` |
| Resaltado: focos de un impacto, focos de 24 h que coinciden con uno, cortinilla | `#cbbcff` |
| Apagado: regiones de Rusia (con contorno discontinuo), focos de 24 h, aro de las ciudades sin luz | `#7a6cc0` |

**Por qué.** Los estados de los incidentes europeos ocupan el rojo (confirmado, `#f53a50`), el
naranja (notificado, `#ff9a2e`) y el verde (datos al día, `#56c271`). El coral anterior de la
capa de guerra (`#f25c4f`) se quedaba a ΔE 15 del rojo de «confirmado» con visión normal y a
ΔE 5 con deuteranopía: eran el mismo color para una de cada doce personas. El violeta azulado es
el tono que queda lejos de los tres a la vez y con los tres tipos de daltonismo, porque su
diferencia con el rojo está en el canal azul, que la deuteranopía y la protanopía conservan.
Medido con la simulación de Machado (2009) sobre CIELAB, `#9d7bff` frente a:

| Visión | Confirmado | Notificado | Datos al día |
| --- | --- | --- | --- |
| Normal | ΔE 98 | ΔE 130 | ΔE 131 |
| Deuteranopía | ΔE 102 | ΔE 131 | ΔE 91 |
| Protanopía | ΔE 80 | ΔE 128 | ΔE 101 |
| Tritanopía | ΔE 99 | ΔE 61 | ΔE 42 |

El coral anterior, con las mismas cuentas: ΔE 15, 5, 12 y 12 frente a «confirmado».

Contraste con el fondo del mapa (`#060a12`): 6,3:1. No es cian ni dorado. Dentro de la capa se
mantienen las diferencias que ya había: impacto de fuente oficial (relleno) frente a
reivindicación de parte (aro sin relleno), Ucrania (violeta pleno) frente a Rusia (violeta
apagado y contorno discontinuo), focos normales frente a coincidentes (apagado frente a claro).
El test `web/tests/colores.test.tsx` lo comprueba con las cuatro visiones: cada color de la
familia a ΔE 30 o más de los tres estados, el principal a ΔE 75 o más del rojo con visión normal,
deuteranopía y protanopía, contraste 4,5:1 sobre el fondo, y que ninguna capa de la guerra use un
color de estado.

<!-- PRODUCCION -->
