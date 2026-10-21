# Control de calidad permanente de las fichas

Desde el 14 de octubre de 2026. El 13 de octubre salieron dos veces el ataque con drones a dos
barcos en la zona económica búlgara del mar Negro (EODI-2026-00513 y 00514, con fuentes rumanas y
finlandesas) y la alerta del aeropuerto de Núremberg (00515 y 00516, con fuentes alemanas y una
griega); el 00515 tenía el lugar a nivel de país, el dron «confirmado» aunque su propia fuente
dice que no se encontró ninguno («allerdings konnte eine Drohne nicht gefunden werden») y «2–10
drones» que no daba ninguna fuente; y las citas salían en griego y en alemán en la web en
español. Este control lo comprueba todo en cada recogida, antes de publicar, y otra vez cada
madrugada.

Código: [`recogida/control_fichas.py`](../recogida/control_fichas.py) (el paso, el repaso y el
estado), [`proceso/control_fichas.py`](../proceso/control_fichas.py) (pares candidatos y reglas
de corrección, sin llamar a nada), [`proceso/lugar_preciso.py`](../proceso/lugar_preciso.py),
[`modelo/control.py`](../modelo/control.py) (las tres llamadas al servicio), 
[`exportacion/citas.py`](../exportacion/citas.py) (lo que se añade al publicar) y la regla de
presencia de [`proceso/presencia.py`](../proceso/presencia.py). Pruebas:
[`tests/test_control_fichas.py`](../tests/test_control_fichas.py).

## Por qué no se unían

- **Sin punto no hay unión.** `proceso/incidentes.mismo_sitio` exige que los dos tengan punto, o
  que ninguno lo tenga y den el mismo nombre de lugar. El 00515 solo sabía el país (Alemania) y el
  00516 tenía el punto de la ciudad: nunca podían unirse. En Bulgaria, el 00513 era de nivel país
  («Biala») y el 00514 de región («Mustanmeren-rannikko», la costa del mar Negro en finés): sin
  punto y con nombres distintos.
- **Idiomas distintos.** Las noticias se agrupan en candidatos por el lugar que nombra el titular y
  el tipo de señal, que dependen del idioma; un titular griego y uno alemán del mismo aeropuerto
  acaban en candidatos distintos, y los titulares solo se comparan dentro de un idioma.

## Qué hace en cada recogida

En `recogida/horaria.py`, paso «control de fichas», después de la presencia del dron y antes de
publicar. Nunca impide publicar lo demás ni cambia el código de salida.

1. **Uniones ya decididas.** Las uniones del control siguen hechas: si la ficha que queda se
   vuelve a extraer y pierde las fuentes de la unida, las recupera.
2. **Lugar del titular** (`proceso/lugar_preciso.py`, sin llamar a nada). Si el titular nombra sin
   duda una instalación del nomenclátor (un aeropuerto, una base, un puerto, una central) del país
   del incidente, el lugar es esa instalación, con su código OACI, y el marcador va en ella. Sin
   duda quiere decir: una sola instalación, con su tipo de lugar en el titular, nombrada por su
   nombre o por una ciudad que no tiene otra del mismo tipo («aeropuerto de Varsovia» puede ser
   Chopin o Modlin), y ninguna otra localidad en el titular («cerca de Heathrow, sobre Marlow» es
   Marlow). La gran ciudad que rodea la instalación (de 10 km de radio o más, a menos de dos
   radios) no cuenta como otra localidad: el titular la añade para situarla («Alhaurín de la Torre
   prison in Málaga», «Bucharest Otopeni airport»; desde el 20 de octubre de 2026). Solo cambia fichas sin punto o con el punto genérico de la misma ciudad (el GKG de
   Núremberg); nunca un punto oficial, el de otra instalación o el de otra localidad. El punto
   anterior queda en `lugar.historial` con el motivo.

   Desde el 20 de octubre de 2026 (fichas que se quedaban en el país a secas con una instalación
   en el titular): una pista o un helipuerto sin código OACI no hace dudar de un aeropuerto que
   lo tiene («aeropuerto de Cracovia» es Balice, no el «Lądowisko Kraków-Czyżyny»); y si el
   nomenclátor no tiene la instalación por la ciudad que nombra el titular, vale la única del
   tipo nombrado, del país, a menos de 30 km de esa ciudad y con su nombre en el suyo («Port of
   Constanța» es el «Portul Constanța»; «Alexandroupoli airport», el «Alexandroupoli Democritus
   Airport»). Una cuyo nombre lleva entero el de otra es una parte de ella («Portul Constanța
   Sud - Agigea») y no cuenta; si quedan dos (Chopin y Modlin), ninguna
   (`lugar_preciso._por_su_ciudad`).

   Desde el 19 de octubre de 2026, además, **el lugar es la instalación afectada** aunque ninguna
   autoridad dé el punto exacto: si el objetivo de la ficha identifica una instalación del
   nomenclátor por su código OACI y el punto está a más de 1 km de ella, el marcador pasa a la
   instalación (EODI-2026-00146: el punto del candidato, en la ciudad de Melilla, a 2,2 km del
   aeropuerto). El objetivo no se toca y nunca cambia un punto que da una autoridad. Medido en la
   base el 19/10/2026: de 176 incidentes con objetivo OACI del nomenclátor y punto, solo cambia
   ese. Las cárceles no están en el nomenclátor (no tienen código ni tipo propio), así que la regla
   aún no las alcanza.
3. **Estado.** Confirmado o atribuido solo con un paso de una fuente oficial (una autoridad, leída
   o citada); si no, vuelve a notificado con el motivo en los dos idiomas.
4. **Duplicados** (también entre idiomas). Pares candidatos: del mismo país; del mismo día o la
   misma noche si las dos fechas las escribe una fuente (a 30 horas como mucho), o a 48 horas si
   alguna es solo la de publicación (entonces cuenta también la primera noticia); en el mismo
   sitio si los dos tienen punto (a 15 km más los radios; si alguno no lo tiene, basta el país:
   el lugar aproximado cuenta); y del mismo tipo de sitio (un aeropuerto y una base no, salvo que
   estén a 10 km). Nunca los que una revisión separó (`relacionados`) ni dos cierres del mismo
   sitio en noches distintas. Cada par se compara con lo que dicen sus fuentes, en su idioma
   (llamada «comparar»), que dice si es el mismo día, el mismo sitio y si alguna ficha resume
   varios sucesos. **Mismo**, solo con el mismo día, el mismo sitio y ninguna ficha que resuma
   varios sucesos: se unen con la fusión anotada como revisada y **se conserva el identificador
   más antiguo**, el de número de registro menor (hasta el 14 de octubre de 2026 era el de
   fecha de alta, que cambia al reconstruir la base: Moldavia, 28 de noviembre de 2025, quedó en
   00247 en vez de 00243, y 2026-00084 en 2026-00114; las dos se rehicieron solas sobre la más
   antigua en la recogida siguiente, con las fichas que se habían unido a ellas) (el enlace del otro lleva al que queda; el que queda hereda la confirmación
   oficial del otro). **Distinto**: no se vuelve a comparar salvo que lleguen fuentes nuevas (de
   madrugada). **Dudoso**: se vuelve a comparar con cada fuente nueva y a las 6 horas se resuelve
   como distintos. Ante la duda, el control no une: un duplicado que se le escapa se corrige a
   mano en `incidentes_revisados.json`; una unión mal hecha mezcla dos sucesos.
5. **Cada dato con su fuente** (llamada «verificar»). Las fichas nuevas o con fuentes nuevas se
   comprueban con sus fuentes (titular y primeras frases, como las lee el extractor, solo en
   memoria): para la presencia del dron, el número de drones, el cierre y su duración, el día, la
   hora y el lugar, qué dice cada fuente con la frase literal. **Una frase que no está, literal,
   en el texto de su fuente no cuenta.** Con lo que queda:
   - si una fuente dice que no se encontró el dron, que no se vio ninguno o que era otra cosa, la
     presencia no queda confirmada (salvo que la autoridad que confirmó el suceso lo atribuya a un
     dron en esa declaración, o haya pruebas físicas que confirma una autoridad, o la revisión a
     mano diga otra cosa). La regla del código (`presencia.NO_HALLADO` y `NADA_HALLADO`) reconoce
     también «se buscó y no se encontró nada» sin nombrar el dron («niets meer gevonden»,
     «nichts gefunden», «nothing was found», «nic nie znaleziono»…) en las 23 lenguas que lee el
     observatorio, salvo que lo buscado fuera una persona o un vehículo;
   - si una autoridad atribuye el suceso a drones (una declaración suya que habla de drones sin
     dejarlo abierto, o su propio documento), no encontrarlos no lo cambia: no encontrar pruebas no
     demuestra que no hubiera dron (EODI-2025-00066, Volkel: Defensa dispara a los drones y «no
     fueron encontrados»). Ni «no se encontró» ni «posible» bajan esa presencia ni la llevan al
     experto; lo que desmiente una autoridad no lo cambia la verificación: va a la cola de las
     rectificaciones oficiales (docs/rectificaciones.md), donde decide el experto;
   - si ninguna de sus fuentes cuenta un suceso (contenido patrocinado o de socio, opinión,
     análisis, explicativo, entrevista o resumen, según su página: docs/modelos.md, «Lo que no es
     un suceso no es ficha»), la ficha se repite con el experto, que decide si se retira;
   - el número de drones solo si una fuente lo da («dos drones», «varios»: 2-10, «un enjambre»:
     5-50); un plural sin cantidad o el número de pilotos no es un número de drones: sin dato;
   - el cierre solo con frase (o con la regla del cierre de pista); su duración, solo con frase;
   - la hora solo con frase (si no, queda el día); el día, con frase, si la ficha solo tenía la
     fecha de publicación;
   - el lugar de una ficha sin punto, el sitio que nombra la frase (una sola instalación o una
     sola localidad del país);
   - nunca sube un estado ni confirma una presencia: eso lo hacen las reglas de siempre con las
     fuentes oficiales.
   Si llegan fuentes nuevas antes de volver a verificar, solo se quita un valor si sigue siendo el
   mismo que se comprobó.
6. **Citas** (llamada «traducir»). Cada cita que enseña la web se traduce una vez al español y al
   inglés y se guarda (tabla `traducciones`, por la huella del texto). La publicación anota las
   que salen sin traducir y el control las traduce en su pasada siguiente: las de las fichas de
   Europa en cada recogida y las de la capa de Ucrania, las más recientes primero, de madrugada.
7. **Retención.** Una ficha nueva que todavía no ha pasado el control (un posible duplicado sin
   decidir, la verificación pendiente por el tope de gasto o por una caída del servicio) no se
   publica, como mucho 6 horas; después se publica con lo que haya y queda anotada. Lo que ya
   estaba publicado nunca se retiene: se corrige. Así un duplicado nuevo se une antes de salir y
   no genera un segundo aviso.

Todo es idempotente: una pasada sin nada nuevo no llama al servicio ni cambia nada. Cada decisión
es una fila nueva de la tabla `control_fichas` (nada se borra); cada corrección, una versión nueva
del incidente con el motivo en el historial («control de fichas: …»).

La segunda lectura ([`docs/segunda_lectura.md`](segunda_lectura.md)) puede mandar, como mucho dos
por recogida, fichas publicadas a la verificación y pares a la comparación de este control,
hechas directamente por el experto; lo que decide se aplica con estas mismas reglas.

## Lo que se ve en la web

- **«Qué dice la fuente»** lleva, junto a cada dato verificado, la frase literal de la fuente que
  lo respalda (si casa con lo publicado), además de lo que ya daba cada fuente.
- **Citas en el idioma de la página.** Cada cita (la frase de cada fuente, «Qué dice la fuente»,
  el lugar según la autoridad, la atribución, la investigación, el tipo de dron y su razón, el
  recorrido, los daños, el desmentido; en la capa de Ucrania, las fuentes de ataques e impactos y
  los cruces) sale traducida al idioma de la página, con el original debajo, plegado: «Ver
  original» / «Show original» (`web/src/componentes/Cita.tsx`; en las páginas de texto,
  `citaTraducida` de `web/src/texto/paginas.ts`). Si no hay traducción o la cita ya está en ese
  idioma, el original tal cual.
- Los campos nuevos de lo publicado son opcionales: `traduccion` (junto a `frase_origen`),
  `cita_traduccion` (junto a `cita`), `frase_traduccion` (daños y cruces) y
  `motivo_desmentido_traduccion`, cada uno con `es` y `en`. El esquema de la base (1.18.0) y la
  exportación semanal para AEGIS (formato 1.11.0) no cambian: las traducciones viven en su tabla
  y solo se añaden a los ficheros de la web.

## Avisos

`recogida/avisos.py` cuenta lo avisado con el número de un registro que después se unió a otro
como avisado para el que queda: el mismo suceso no se avisa dos veces. Y como un duplicado nuevo
se retiene hasta que el control decide, normalmente ni llega a publicarse.

## Madrugada

Una pasada al día, de madrugada en Europa:

1. con el cerrojo de la recogida, lo que no llama al servicio (uniones, reglas, verificaciones ya
   decididas, retención) y la recogida de los lotes de citas de las horas anteriores;
2. sin el cerrojo, manda por lote (a mitad de precio, desde el 14 de octubre de 2026,
   [`docs/modelos.md`](modelos.md)) la comprobación de todo lo publicado en las últimas 48 horas:
   los pares ya decididos que tienen fuentes nuevas y la verificación de las fichas con fuentes
   nuevas (las horarias solo comparan pares nuevos o dudosos y verifican de nuevo una ficha como
   mucho cada 6 horas); lo que el modelo base pide escalar se repite con el experto, y todo se
   guarda con el cerrojo;
3. sin el cerrojo, manda por lote las citas que siguen sin traducir, las de las fichas primero y
   después las de la capa de Ucrania, las más recientes primero, con lo que sobra del día y sin
   pasar de su propio tope (`TOPE_NOCHE_CITAS_USD`, 0,05 dólares: lo nuevo de cada día cabe de
   sobra; la revisión del paso 2 tiene el suyo, `TOPE_NOCHE_USD`); espera a que cada lote
   termine (3 horas como mucho);
4. con el cerrojo otra vez, guarda las traducciones.

En cada recogida horaria, las citas nuevas no se traducen con llamadas directas: van en un lote
que recoge la recogida siguiente (cursor `control_fichas:lotes`).

Lo que corrige sale en la recogida siguiente. El estado del control:
`python -m recogida.control_fichas estado`.

## La primera ronda del repaso, deshecha

La primera versión de los pares (14 de octubre de 2026, 02:33 UTC) comparaba con 48 horas y
60 km para todo y unió 80 registros, con aciertos (Núremberg, el 6 de octubre en Bulgaria, notas
tardías de un mismo cierre) y errores graves: derribos de días seguidos en Rumanía en una ficha,
Brønnøysund del 28 y del 30 de septiembre de 2025, la base de Kleine-Brogel con el aeropuerto de
Bruselas o toda la incursión en Polonia de septiembre de 2025 en una sola ficha. Se deshizo a las
02:47 (antes de publicarse): cada ficha volvió a su versión anterior del historial, cada fusión
quedó revertida y cada decisión se anotó como «revocada». Con las reglas de ahora (mismo día o
noche, mismo sitio, sin resúmenes) esos pares no son candidatos y, comparados igualmente, salen
distintos.

## Las separaciones del 13 de octubre, revisadas

El repaso comparó también las 22 parejas de fichas que dejó la separación de sucesos mezclados
(docs/sucesos_mezclados.md), sin unirlas solo. 20 son sucesos distintos, como se separaron. Dos
eran el mismo suceso partido y se unen en `incidentes_revisados.json`:

- EODI-2025-00456 con EODI-2025-00287: la parte que tenía que ser el cierre de Múnich salió como
  otra ficha de los drones sobre Elsenborn (dos de sus tres fuentes son de Elsenborn).
- EODI-2026-00384 (la parte lituana) con EODI-2026-00376: el mismo cierre de Vilna del 3 de octubre
  de 2026; la parte se anota con `coincide_con` y la unión la hace la regla de siempre.

## Gasto

- Modo `control`: 0,15 dólares al día (recogidas horarias y madrugada), con el mismo registro de
  llamadas y el mismo freno que el extractor (`modelo/coste.py`): antes de cada llamada se suma lo
  gastado y el peor caso; si pasa, no se llama y lo pendiente espera (las fichas nuevas, como
  mucho 6 horas).
- Modo `control_repaso`: 4 dólares y después 6 más (14 de octubre de 2026, para las unas 600
  fichas que quedaron sin verificar), para el repaso de todo lo publicado
  (`python -m recogida.control_fichas repaso --cerrojo …`), por lotes (a mitad de precio) y en
  dos rondas: los pares primero (las uniones) y después la verificación de cada ficha y las citas
  (las de Europa y, con lo que quede, las de Ucrania).

- Modo `traducciones`: 2 dólares una sola vez (14 de octubre de 2026) para las citas que quedaban
  sin traducir (unas 8.600 de la capa de Ucrania y 440 de Europa), por lote y con el modelo base:
  `python -m recogida.control_fichas traducir-pendientes`.
- Dos modelos ([`docs/modelos.md`](modelos.md)): cada llamada se cobra con la tarifa del modelo
  que la hizo; un par dudoso y una verificación que contradice la ficha se repiten con el
  experto, que tiene su propio tope diario (1 dólar) y una reserva crítica (0,50 dólares) para los
  casos críticos. Lo que no es crítico y no cabe espera al día siguiente; lo crítico, si también se
  agotó la reserva, se reintenta en cada recogida. La ficha nueva sigue retenida mientras tanto
  (sin el límite de 6 horas).

## Repaso con el experto (desde el 20 de octubre de 2026)

Un repaso de todo lo publicado con el experto y las reglas nuevas
(`python -m recogida.control_fichas repaso-experto --cerrojo …`, `repaso_experto`), por lotes (a
mitad de precio) y de madrugada:

- **Presupuesto aparte**: modo `repaso_experto`, 15 dólares en total
  (`coste.LIMITE_REPASO_EXPERTO_USD`). No cuenta contra el tope diario del experto ni su reserva
  crítica (`CUPOS_PROPIOS`), ni contra su parte del mes ni el tope mensual (`FUERA_DEL_MES`): no
  quita nada a la recogida ni al control de cada día. Antes de cada lote se suma lo gastado y el
  peor caso con la tarifa del experto; lo que no cabe no se manda.
- **Dos rondas**, como el repaso: los pares (todos los candidatos de las reglas, también los ya
  decididos, y las series de `configuracion/repaso_experto.json`: fichas que pueden contar el
  mismo suceso sin ser candidatas, como la serie de Constanza o dos fichas de países vecinos,
  comparadas de dos en dos si están a menos de 3 días, o todas con `sin_ventana`: la serie de
  Constanza, cuyas fichas de la explosión del 5 de junio llevaban la fecha de noticias
  posteriores) y la verificación de cada ficha publicada
  (primero las que tienen un fallo conocido o el lugar en el país a secas).
- **Por el camino normal**: cada respuesta es del experto y se aplica como las del control (las
  uniones, las correcciones con su frase literal y el motivo en el historial; nada publicado se
  retira sin él). Las reglas deterministas (lugar del titular, buques, fechas, tipo, frontera o
  interior, nombres y titulares) se aplican antes y después de cada lote.
- **Sin repetir**: cada decisión lleva `repaso_experto` con su fecha; lo que el repaso ya decidió
  con las mismas fuentes no se vuelve a preguntar. Si se para (el presupuesto o 6 horas), sigue
  donde lo dejó la vez siguiente.

## Fallos conocidos de las fichas (desde el 20 de octubre de 2026)

El 20 de octubre de 2026, con el experto casi sin tope, salieron tres fichas mal publicadas:
EODI-2026-00639 («Chelsea 3, Bulgaria»: el nombre del buque como lugar, «sobrevuelo» y
«interior»), EODI-2026-00632 (una nota de nordbayern.de que dice «Erst letzte Woche…» sobre el
aeropuerto de Núremberg, publicada como suceso nuevo del 19) y EODI-2026-00637 («Puerto de Ems»,
una traducción inventada de Eemshaven que venía de Wikidata). Reglas generales:

- **Un buque, un vehículo o una aeronave nunca es un lugar** (`proceso/buques.py`). Si el lugar
  del suceso es el nombre de un barco que nombran las fuentes («vessel Chelsea 3», «MV …»), el
  lugar pasa a ser la zona marítima que dan las fuentes («mar Negro, zona económica exclusiva de
  Bulgaria», «mar Negro») o «mar», a nivel de región y sin punto (`incidentes.lugar_sin_buque`, al
  construir la ficha y en las reglas deterministas del control). El extractor y la verificación lo
  saben (`modelo/ficha.py`, `modelo/control.py`).
- **Un buque alcanzado por un dron en el mar no es un sobrevuelo**: impacto, explosión, ataque o
  restos a bordo en el mar son el dron de un ataque que llegó desde el mar; el tipo es
  «incursión», como los buques del 13 de octubre (EODI-2026-00512), con las pruebas físicas que
  den las fuentes (`incidentes.aplicar_reglas`, `alcanzado_en_el_mar`).
- **Frontera o interior en el mar**: un suceso en el mar de un país con costa en el mar Negro es
  de la costa del mar Negro (`zona.clasificar`, motivo `costa_mar_negro`), nunca «interior»;
  con un punto en tierra (el puerto de Constanza, Sulina) manda el punto.
- **Pasado sin día** (`proceso/fechas.py`, `configuracion/fechas.json`, `pasados`): «la semana
  pasada», «letzte Woche», «hace unos días»… en cualquier idioma no son la fecha de publicación.
  El inicio queda aproximado (la víspera de la nota como muy tarde) y su motivo lleva la ventana
  (la semana natural anterior, o los 10 días antes); la fusión lo compara con los incidentes del
  mismo sitio en esa ventana (`incidentes.misma_ventana`, `ventana_pasada`) y la nota se une al
  suceso registrado como fuente nueva.
- **Los nombres propios de las instalaciones no se traducen** (Eemshaven, Schiphol, Rotterdam);
  solo los exónimos de las tablas («Núremberg», «Copenhague»). Un nombre de Wikidata del tipo
  «Puerto de X» cuyo X no está en el nombre original no se usa
  (`nombres_lugar.traduccion_inventada`).
- **Titular en inglés**: «possible» va delante de todo el grupo del dron («Possible mystery
  drones», «Possible narco-drones»), no en medio (`titulares._como_posible`).
- **El control los busca en cada ficha** (`control_fichas.fallos_de_ficha`: `buque_como_lugar`,
  `alcanzado_como_sobrevuelo`, `interior_en_el_mar`, `fecha_de_publicacion_con_pasado`) y la
  verifica con el experto (motivo `fallo_ficha`) aunque sus fuentes no hayan cambiado; la decisión
  guarda los fallos vistos y no se repite mientras sean los mismos.

## Resumen diario y vigilancia

- `control.json` (`~/.eodi/`) guarda cada pasada de los dos últimos días: fichas
  corregidas y por qué, duplicados unidos, retenidas y liberadas, gasto y paradas.
- El resumen diario privado (sección SISTEMA) dice cuántas fichas corrigió el
  control y de qué clase (lugar, drones, presencia, cierre, hora, día, estado), los duplicados que
  unió, las que retuvo y lo que gastó, con hasta 5 ejemplos.
- La vigilancia solo abre incidencia («control_fichas») si el propio control falla 3 pasadas
  seguidas; lo que corrige o retiene no es un problema.

## Correcciones a mano

Siguen en `configuracion/incidentes_revisados.json` y mandan sobre el control: una presencia
revisada a mano no la cambia el control, una unión revisada no la deshace nadie. La sección
`titulares` admite ahora `drones` (`{"valor": "desconocido"}`) para quitar un número de drones que
no da ninguna fuente, como en el 00515.
