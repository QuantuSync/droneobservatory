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

   Desde el 22 de octubre de 2026, **instalaciones con el mismo nombre**: un alias completo de una
   instalación que otra del país lleva como ciudad («Васил Левски» es el estadio de Karlovo y la
   ciudad del aeropuerto de Sofía, LBSF) no casa solo. Decide el tipo que nombra el texto
   («Летище», aeropuerto); si no, la que está a menos de 30 km de la ciudad que nombra; si
   tampoco, ninguna (`noticias._entre_homonimos`). EODI-2026-00064 y EODI-2026-00077 tenían el
   punto y el objetivo en el estadio.

   Desde el 19 de octubre de 2026, además, **el lugar es la instalación afectada** aunque ninguna
   autoridad dé el punto exacto: si el objetivo de la ficha identifica una instalación del
   nomenclátor por su código OACI y el punto está a más de 1 km de ella, el marcador pasa a la
   instalación (EODI-2026-00146: el punto del candidato, en la ciudad de Melilla, a 2,2 km del
   aeropuerto). El objetivo no se toca y nunca cambia un punto que da una autoridad. Medido en la
   base el 19/10/2026: de 176 incidentes con objetivo OACI del nomenclátor y punto, solo cambia
   ese. Las cárceles no están en el nomenclátor (no tienen código ni tipo propio), así que la regla
   aún no las alcanza.

   Desde el 21 de octubre de 2026: con el punto del candidato (el de la ciudad) y un objetivo
   «otra» con el nombre de la ciudad, la instalación que nombra sin duda el titular pasa a ser el
   lugar y el objetivo, con su categoría y su OACI (EODI-2026-00131, «aeropuerto de Berlín»:
   Berlin Brandenburg, EDDB; EODI-2026-00322, Hamburgo: EDDH), si el punto está a 30 km o menos.
   Y un objetivo «otra» que se llama como la localidad del suceso no es una instalación: no se
   guarda (EODI-2026-00648, «Józefów · Otro lugar»; también al crear la ficha,
   `incidentes.objetivo_es_la_localidad`). La cabecera de la ficha en la web es el nombre de la
   instalación solo si tiene categoría propia; si no, el titular, una sola vez.
3. **Estado.** Confirmado o atribuido solo con un paso de una fuente oficial (una autoridad, leída
   o citada); si no, vuelve a notificado con el motivo en los dos idiomas. Una declaración cuya
   cita solo dice quién habla y el verbo de decir («Podinsp. Marta Sulowska z Komendy Stołecznej
   Policji przekazała», EODI-2026-00648; `declaraciones.sin_afirmacion`, en las lenguas que lee
   el observatorio) no es una fuente oficial: ni da el estado ni confirma la presencia hasta que
   tenga una cita con lo que dijo. El extractor guarda entonces la frase que sigue en el texto
   («… że pracownicy Wojskowego Instytutu …»), o descarta la declaración si no la hay. Si la
   ficha ya estaba bajada a notificado por esa cita vacía, la cita revisada de la autoridad que
   afirma el suceso (`incidentes_revisados.json`, citas) la vuelve a confirmar
   (`revisados.reconfirmar`).
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
   Una traducción al español con restos en inglés («according to», «said», «reported», «told»;
   `validaciones.restos_sin_traducir`) no se guarda, y si ya estaba guardada no cuenta: la cita
   vuelve a salir sin traducir y se pide otra vez, que se guarda en otra fila (`<huella>#<n>`,
   la tabla no cambia filas). Así salió la cita de EODI-2026-00689 el 27 de octubre de 2026
   («…y uno de ellos se hundió, according to»); era la única de toda la tabla.
7. **Retención.** Una ficha nueva que todavía no ha pasado el control (un posible duplicado sin
   decidir, la verificación pendiente por el tope de gasto o por una caída del servicio) no se
   publica. Hasta el 28 de octubre de 2026 salía a las 6 horas con lo que hubiera; desde
   entonces no sale hasta que el filtro de entrada (abajo) la deja pasar. Lo que ya
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
- **Un buque alcanzado por un dron en el mar** es «sobrevuelo» salvo que una autoridad diga que
  estaba en aguas del país (desde el 21 de octubre de 2026; antes era «incursión», como los
  buques del 13 de octubre, EODI-2026-00512): el tipo lo decide `incidentes.con_tipo`. Los restos
  a bordo y el origen del dron no lo demuestran; el rastreo o la autoridad que dice que el dron
  entró en el espacio aéreo, sí (EODI-2026-00541, al sureste de Sulina).
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

## Auditoría de las fichas (desde el 21 de octubre de 2026)

`proceso/auditoria_fichas.py` cuenta, en cada pasada del control y sin llamar a nada, las fichas
vigentes con cada fallo conocido: A, cabecera de una palabra; B, instalación no reconocida; C,
cita de autoridad vacía; D, titular sin respaldo; E, presencia sin base; F, lugar (buque, mar
marcado como interior, fecha de publicación cuando una fuente da otra); G, nombres (punto anterior
sin nombre, titular publicado con otra forma de la ciudad); H, instalación homónima (desde el
22/10/2026: el objetivo no casa con el tipo del suceso, como una interrupción aeroportuaria con un
estadio, o su instalación está a más de 30 km de la localidad de la ficha); I, alias genérico
(desde el 22/10/2026: el objetivo se llama solo con palabras corrientes, como «Base navale», o las
fuentes nombran su instalación solo con un nombre o una ciudad genéricos, como «im Norden», «en el
norte», por el aeródromo de Norden-Norddeich); J, hora local como UTC (desde el 22/10/2026: la
hora UTC de la ficha es la hora local que escribe una de sus fuentes y ninguna escribe la que le
toca en la zona del suceso; desde el 27/10/2026 también con el desfase del otro horario del año y
con 10 minutos de margen); P, presencia rebajada sin cierre (desde el 27/10/2026: «no acreditada»
o «descartada» sin un paso del historial que diga qué autoridad la rebajó y cuándo; se completa con
su rectificación oficial, docs/rectificaciones.md). Los recuentos del día y los
identificadores quedan en `control.json` («auditoria»), el resumen diario los da con lo que
cambian respecto al día anterior y, si una comprobación sube, el aviso de silencio lo cuenta una
vez (`recogida/silencio.py`, caso «auditoria»). A mano, en solo lectura sobre una copia de la
base: `python -m recogida.auditoria_fichas [--base …] [--json]`.

### Alias genéricos (desde el 22 de octubre de 2026)

Los alias de las instalaciones salen tal cual de las etiquetas de nombre de OpenStreetMap
(`recogida/instalaciones_osm.py`) y las ciudades de `lugares_europa.json` se ponen a mano. Algunos
son solo palabras corrientes: «Base navale» (una base de La Reunión), «Port» (un puerto polaco),
«Stadion Miejski», «Kaserne 1»; y la ciudad «Norden» del aeródromo de Norden-Norddeich es también
«el norte» en alemán. Un alias o una ciudad hecho solo de palabras de
`configuracion/palabras_corrientes.json` (puntos cardinales, el nombre genérico de cada tipo de
instalación, adjetivos y enlaces), de palabras de tipo de lugar enteras o de números no casa nada
(`proceso/noticias.generico`): hace falta un nombre propio o la ciudad. Las palabras corrientes que
son también un lugar (Porto, Halle, Malå, Orlík, Au) quedan fuera de la lista. La comprobación I
de la auditoría avisa si una ficha toma su objetivo de un alias genérico.

### Hora local tomada como UTC (desde el 22 de octubre de 2026)

El extractor da el inicio y el fin en UTC y tiene que convertir la hora local que escribe la
fuente; a veces la copia sin convertir: «gegen 19.30 Uhr» en Bremen el 2 de noviembre de 2025
(hora de invierno, UTC+1) son las 18:30 UTC, y EODI-2025-00007 publicaba las 19:30 UTC. Al hacer la
ficha (`proceso/fechas.hora_en_utc`), si la frase del inicio escribe una sola hora
(`textos_dron.hora_local`), la hora UTC de la ficha es esa misma y en la zona del suceso (la del
país o la de su territorio, con su horario de verano) no lo es, la hora se toma como local y se pasa
a UTC; el fin de la misma ficha se corrige en lo mismo. Si la frase escribe la hora local ya bien
convertida, u otra hora, no se toca. Las fichas ya guardadas no conservan la frase del inicio: se
corrigen con una revisión del inicio con su cita (`titulares.inicio` en
`incidentes_revisados.json`), y la comprobación J de la auditoría avisa de las que queden.

Desde el 27 de octubre de 2026 la regla y la comprobación cubren tres caminos más, que dejaron
pasar 14 inicios desplazados una o dos horas (y a veces de día):

- **La frase del inicio no nombra el dron.** «Le trafic aérien a été brièvement interrompu jeudi
  vers 21h20» (EODI-2025-00335, Bruselas) no se leía porque `hora_local` exigía la palabra dron; la
  frase de la que el extractor tomó el inicio ya vale sin ella.
- **Horas aproximadas con su unidad.** «gegen 19 Uhr» (EODI-2025-00092, Lieja), «apie 21
  valandą» (EODI-2025-00099, Vilna), «vers 21 heures», «rond 19 uur».
- **El desfase del otro horario.** La hora local convertida con el desfase de verano en invierno o
  al revés: «12.05 val.» en Vilna el 29 de octubre de 2025, ya en hora de invierno (UTC+2),
  publicado como 09:05 UTC (EODI-2025-00178) (`fechas.desfases_errados`).

La comprobación J mira el inicio publicado frente a cualquier hora que escriba una frase de sus
fuentes, nombre o no el dron, con 10 minutos de margen, en la zona del suceso y con su horario
de ese día; una frase que da la hora en UTC o GMT no cuenta. Si la hora solo está en el artículo y
no en la frase guardada (EODI-2025-00222: «between 12.30 and 12.45 am local time (2230-2245GMT)»
en aa.com.tr), J no la ve: se corrige con una cita revisada y la revisión del inicio.

### Uniones, lugar revisado y noticias retrospectivas (desde el 25 de octubre de 2026)

- **La declaración del unido pasa a la que queda.** Al volver a leer una noticia que ya estaba en
  un registro unido, la declaración de autoridad que se saca de ella (`<noticia>-declaracion-N`) se
  quedaba en el unido: EODI-2026-00108 (Auvere) tenía la noticia de cbsnews.com pero no la
  declaración de la KAPO, y el 21 de octubre pasó a «posible dron». En cada recogida
  (`recogida/declaraciones_oficiales.uniones`), las declaraciones del unido cuya noticia está en la
  que queda pasan a esta con sus afirmaciones; el 25 de octubre eran 8 fichas, y solo 00108 cambió
  de estado y de presencia. La comprobación L avisa de una ficha sin ninguna autoridad que tenga
  alguna unida con ella.
- **Queda el identificador más antiguo.** Entre dos fichas publicadas, queda la de un año anterior
  antes que la de más fuentes (`incidentes.destino_de`): EODI-2025-00199 (Bruselas, 5 de diciembre
  de 2025) se había quedado dentro de EODI-2026-00094.
- **El lugar revisado fija el punto.** Una revisión del lugar con la localidad y sin el punto deja
  el nivel y el punto de esa localidad (la del nomenclátor, si es una sola) cuando el que tenía la
  ficha queda a más de 15 km más el radio de la localidad (`decidir.en_la_localidad_revisada`):
  EODI-2026-00238 tenía el punto de Tulcea y la revisión dice Rachelu, a 40 km. La comprobación M
  avisa de un lugar revisado con otro nivel u otro punto que los de la revisión.
- **Noticias retrospectivas.** La comprobación N avisa de una ficha cuyo inicio es la fecha de
  publicación y cuyas fuentes nombran otro mes: la noticia cuenta un suceso anterior y, con la
  fecha de publicación, no casa con la ficha del suceso. Se revisan a mano (unir con la ficha del
  suceso o corregir el inicio con su cita). Desde el cierre del 25 de octubre, la regla está en el
  control (abajo) y N es su comprobación fija.
- **Frontera.** El 25 de octubre, en los 90 días anteriores, había 2 parejas de fichas de frontera
  del mismo día y país sin unir a 15-30 km: una era el mismo suceso (Moldavia, EODI-2026-00676 y
  00682, unidas a mano) y la otra no (Lunga por la mañana y Brănești por la noche del 30 de
  septiembre). El radio no se amplía.

### Noticias retrospectivas (desde el 25 de octubre de 2026, por la tarde)

Una noticia que cuenta un suceso anterior (una investigación que se cierra, el recuerdo de un
ataque de hace semanas) entraba como suceso nuevo con la fecha de su publicación: cuando la ficha
no da el inicio, se toma la publicación, y los pares del control solo se buscan a 30 o 48 horas,
así que nunca casaba con la ficha del suceso. Así entraron EODI-2026-00663 («u augustu», avaz.ba,
22 de octubre) y 00499 (freiepresse.de, 8 de octubre) sobre el intento de atentado de Leipzig del
4 de agosto, y 00666 sobre el hallazgo de Wunstorf del 15 de septiembre.

- **Cuándo pregunta** (`proceso/control_fichas.pide_fecha`): la ficha nueva tomó la fecha de
  publicación y una fuente nombra otro mes que el del inicio o un pasado lejano («last month»,
  «letzten Monat», «el mes pasado», en los idiomas de las fuentes: `configuracion/fechas.json`,
  `pasados.anterior`; `proceso/fechas.retrospectiva`), o su instalación tiene una ficha anterior
  del mismo sitio con la fecha comprobada en los 400 días anteriores
  (`proceso/control_fichas.previas_del_sitio`). «mai» en rumano es «más», no mayo.
- **Qué pregunta** (`modelo/control.cuerpo_retrospectiva`, siempre al experto): si cuenta un
  suceso anterior, si es el de una de las fichas anteriores del mismo sitio (sin ventana de días)
  y su fecha, con la frase literal que la respalda.
- **Qué hace** (`recogida/control_fichas.retrospectivas`): si es el mismo suceso, une las fichas
  (queda la de número menor); si da la fecha y su frase está en la fuente, la ficha la toma con
  precisión «dia» o, si solo da el mes, el día 1 con precisión «aproximada» (el esquema no tiene
  precisión de mes); si no es retrospectiva, el motivo del inicio queda marcado («noticia
  retrospectiva revisada») y no se vuelve a preguntar. Lo decidido se guarda en el control
  (`retrospectiva:<id>`) y se vuelve a poner si una extracción nueva devuelve la fecha de
  publicación.
- **Retención**: mientras no hay respuesta comprobada, la ficha no se publica. La que nombra otro
  mes o un pasado lejano se retiene sin límite; la que solo comparte instalación con una ficha
  anterior (casi siempre un suceso nuevo) esperaba como mucho 6 horas (hasta el 28 de octubre de
  2026; ahora la decide el filtro de entrada).
- **Comprobación fija**: la N de la auditoría es la misma regla sobre todo lo publicado.

### Fin sin frase que lo respalde (desde el 26 de octubre de 2026)

El extractor daba una hora de fin que ninguna frase escribía y se guardaba sin comprobarla (el
inicio sí se comprobaba con su frase). EODI-2025-00154 publicaba las 23:00 UTC en Copenhague por
«gut vier Stunden» desde las 18:30, y EODI-2026-00112 las 20:03 UTC por «până la ora 22:03», que
en Moldavia en marzo son las 19:03 UTC. De las 40 fichas con fin, 18 lo publicaban sin frase; en la
muestra de 10, seis estaban mal (cuatro con la hora local tomada como UTC) y cuatro bien, pero con
la frase guardada en otra parte de la nota: esas cuatro y Copenhague llevan ahora el fin revisado
con su cita.

- **La regla** (`proceso/fechas.fin_escrito`): una frase respalda un fin si escribe esa hora, en
  la hora local del suceso o en UTC («fra klokken 04.30 til 05.41», «tra le 19 e le 21», «um
  Mitternacht»), o una duración que, contada desde el inicio, da ese fin («Durante 40 minutos»,
  «een half uur», «to og en halv time»), con 10 minutos de margen.
- **En el origen** (`proceso/incidentes._fin_con_frase`): el fin de una ficha nueva solo se guarda
  si su frase lo respalda.
- **Al publicar** (`fechas.sin_fin_sin_frase`, en `exportacion/geojson.con_afirmaciones`): el fin
  y la duración sin frase no se publican, ni las afirmaciones de fin de una fuente cuya frase no
  lo escribe. El fin revisado a mano (`titulares`, `inicio.fin` con `fin_cita`) lleva su frase.
- **Comprobación fija**: la O de la auditoría, sobre lo que publica la web.

## Filtro de entrada (desde el 28 de octubre de 2026)

Ninguna ficha nueva se publica sin que el experto haya comprobado si repite un suceso que ya
tenemos o si cuenta otro día. Código: [`recogida/entrada.py`](../recogida/entrada.py) (el paso y
la medida a las 24 horas) y [`modelo/entrada.py`](../modelo/entrada.py) (las peticiones). Pruebas:
[`tests/test_entrada.py`](../tests/test_entrada.py).

### Por qué

Del 7 al 28 de octubre de 2026 salieron publicadas 27 fichas nuevas que eran un suceso que ya
teníamos (después se unieron a mano o por el control), además de un nombre de autoridad con el
país equivocado. Tres casos del 27 y 28 de octubre:

- **EODI-2026-00689** repetía el ataque a buques frente a Bulgaria de la noche del 12 al 13 de
  octubre (EODI-2026-00512), contado dos semanas después.
- **EODI-2026-00692** era el derribo de dos drones por cazas rumanos sobre Sulina del 17 de octubre
  (EODI-2026-00582), contado en un resumen del mes; y **EODI-2026-00620**, el mismo derribo con la
  fecha del domingo 18.
- **EODI-2026-00512** daba el Consejo de Seguridad del Consejo de Ministros de Bulgaria como
  «de Moldavia»: la traducción del nombre dedujo el país de la lengua (rumano) de la noticia.

Las fichas se comparaban solo con las del mismo sitio y del mismo día o de los dos días vecinos
(`proceso/control_fichas.candidatos`), así que un suceso contado otro día o con el lugar a nivel de
país nunca encontraba su pareja; y lo que esperaba una decisión salía a las 6 horas con lo que
hubiera.

### Qué hace

En cada recogida horaria, después de las noticias retrospectivas y antes de publicar, cada ficha
nueva (activa y aún no publicada) que no tiene una decisión vigente para sus fuentes y su inicio
(`huella`) pasa por el filtro:

1. **Conjunto de comparación, sin mirar la distancia** (`entrada.conjunto`): las fichas activas de
   su país con el inicio de 30 días antes a 3 días después de su inicio o de su primera noticia.
   Si la ficha es de mar, de frontera o con el lugar a nivel de país o de región, también las de
   los países del mismo mar o vecinos (`MARES`, `VECINOS`). Si son más de 40, las del mismo tipo y
   las más cercanas en el tiempo, nunca menos de 40. Las que una revisión separó no entran.
2. **Una llamada al experto** con la ficha, sus fuentes, las autoridades que cita y el conjunto
   (una línea por ficha: id, fecha, lugar, tipo, titular y una frase). Responde en JSON: si es el
   mismo suceso que una del conjunto (su id o «ninguna»), si cuenta otro día (fecha y frase), y la
   frase de la fuente que da la fecha, el lugar y cada autoridad con su país (o «no»).
3. **Lo que se hace con la respuesta** (`entrada.decidir`, que comprueba cada frase en su fuente):
   - mismo suceso: se une antes de publicar (queda la más antigua, `mas_antiguo`);
   - otro día con frase: la ficha toma ese día y vuelve a pasar por el filtro (como mucho una vez);
   - fecha sin frase y la ficha con fecha aproximada: no se publica;
   - lugar sin frase: el lugar baja a nivel de país;
   - una autoridad sin frase, o de otro país sin una frase que lo diga: no cuenta como declaración
     oficial (la fuente se queda, con fiabilidad C) y se anota en `autoridades_fuera`. Una
     extracción nueva de la ficha no la vuelve a hacer oficial: `_alta` lee la decisión guardada
     del filtro (`extraccion.sin_oficiales_del_filtro`). Sin eso, el 28 de octubre de 2026 la
     presencia de EODI-2026-00694 cambió cuatro veces en un día (auditoría K);
   - si duda, o falta una frase, se le vuelve a preguntar una vez con las fuentes de las
     candidatas más cercanas (`MAX_CANDIDATAS_CONTEXTO`);
   - **fechas firmes** (`fecha_firme`: el día sale de una frase, no de la publicación): dos fichas
     con fechas firmes a más de 2 días (`DIAS_FIRMES`) no se unen; se le vuelve a preguntar con
     las fuentes de la otra y, si insiste, la ficha se retiene para una revisión. Tampoco se cambia
     un día firme por otro a más de 2 días. En la prueba del 28 de octubre de 2026 el experto unía
     el ataque a buques del 12 de octubre (EODI-2026-00512) al del 6 (00489), tras moverlo al 6 por
     «o săptămână după ce atacurile au dus la scufundarea», que no da ningún día.
4. **Sin respuesta del experto** (tope, caída, tiempo de la pasada) la ficha **espera** y cuenta
   como caso crítico (`esperan_experto` del estado). Nada sale por tiempo: se quitó la salida a las
   6 horas de las fichas nuevas.

La decisión es una fila de `control_fichas` con la clave `entrada:<id>`; con la misma huella no se
vuelve a preguntar. La traducción de los nombres de autoridad ya no deduce el país de la lengua
del nombre (`modelo/control.INSTRUCCIONES_TRADUCIR`).

### Medida a las 24 horas

Entre 24 horas y 7 días después de publicarse, cada ficha que pasó el filtro se vuelve a comprobar
con el experto (`medida:<id>`, como mucho 6 por pasada): fecha, lugar, autoridad y duplicado, cada
uno con su frase. Si encuentra un error con frase, se corrige como en el filtro y se apunta. El
resumen diario (`recogida/visitas.py`) lleva la línea «Fichas nuevas de ayer: N; con error a las
24 h: M (ids)».

### Gasto

Modo `entrada` (`modelo/coste.py`): 3,00 USD al día, solo del experto, aparte del tope del experto,
de su reserva y del cupo del control (`CUPOS_PROPIOS`). El tope mensual pasa de 60 a 150 USD.

## Conjunto de referencia (desde el 21 de octubre de 2026)

La red de seguridad antes de cambiar la estructura: unas 50 fichas cuyo valor correcto de cada dato
(estado, presencia del dron, tipo, objetivo con su categoría y OACI, país, localidad, día de
inicio, frontera o interior, número de drones y cabecera en español) está comprobado leyendo el
texto completo de sus fuentes (o su copia archivada), no la ficha. Cubren cada valor de presencia
y de estado, los tres tipos, aeropuertos, bases, puertos, centrales y lugares sin instalación,
buques y mar, frontera e interior, uniones, separaciones, rectificaciones y varios idiomas y países.

- `tests/referencia/fichas.json`: por ficha, por qué se eligió y, por dato, el valor correcto con
  la cita literal y el enlace de la fuente que lo justifica («sin fuente» y enlace nulo si el valor
  es «no consta» o sale del lugar, como la zona).
- `tests/referencia/fichas/<id>.json`: la copia pública de cada ficha (solo campos que ya se
  publican, más sus pruebas y el punto), de la que la prueba saca los datos.
- `tests/referencia/discrepancias.json`: las fichas cuyo valor de hoy no es el correcto (id, campo,
  valor de la ficha, valor correcto, cita y motivo). Es el trabajo pendiente.

Dos comprobaciones fijas, con las mismas funciones (`proceso/referencia.py`: reglas del tipo y la
presencia, coherencia del historial, zona, objetivo y cabecera):

1. **En la CI**, `tests/test_referencia.py` pasa las copias guardadas por esas funciones y compara
   con la referencia. Falla si aparece una discrepancia que no está en la lista, si una de la lista
   ya está corregida (se quita; si vuelve, falla como nueva) o si la lista crece por encima de
   `TOPE_DISCREPANCIAS`: la lista solo puede encoger.
2. **En el servidor**, en cada control de fichas la auditoría compara las fichas de la base, como
   las publica la exportación, con la referencia: comprobación **R**, con «id campo» por cada
   diferencia nueva e «id ausente» si una ficha deja de estar vigente (fundida o retirada). Entra en
   `control.json`, en el resumen diario y, si sube, en el aviso, como las demás.

**La referencia solo se cambia con una cita nueva de una fuente**, nunca para que pase una prueba:
si un valor correcto cambia (una autoridad rectifica), se pone el valor nuevo con la cita literal y
el enlace de la fuente nueva. Si el código o los datos se apartan de la referencia, se arregla el
código o la ficha, no la referencia.

Para añadir una ficha:

1. Elegirla por lo que cubre que no cubran las demás y anotarlo en `por_que`.
2. Leer el texto completo de sus fuentes (el original o su copia archivada) y decidir cada dato
   con su cita literal y su enlace; nunca copiarlo de la ficha.
3. Guardar su copia pública con `proceso.referencia.copia_publica(proceso.referencia.publicada(d))`
   sobre el documento de la base, en `tests/referencia/fichas/<id>.json`. Los tres ficheros se
   guardan en ASCII (`json.dumps(..., ensure_ascii=True)`, con escapes para las letras con tilde):
   la comprobación de palabras del repositorio lee bytes y parte en dos las palabras con
   letras como «ț» o «ș», y lo que queda suelto puede parecer una palabra prohibida.
4. Si el valor de hoy no es el correcto, añadirlo a `discrepancias.json` con su motivo: solo al
   añadir una ficha nueva, o al corregir la referencia con citas nuevas, puede subir
   `TOPE_DISCREPANCIAS`, y en el mismo cambio.

### Un solo sitio decide el estado y la presencia (desde el 21 de octubre de 2026)

`proceso/decidir.py` decide los dos valores a partir de las pruebas de la ficha cada vez que se
guarda (`Almacen.guardar_incidente`): `decidir_estado` (el último paso del historial, salvo un
desmentido que no vale) y `decidir_presencia` (por prioridad: rectificación, revisión a mano,
documento oficial, «era otra cosa», autoridad que lo atribuye a un dron o pruebas físicas con el
suceso confirmado; si no, no confirmada). Las dos devuelven el valor, la fuente y la regla que lo
deciden; si el valor cambia al guardar, el motivo queda en el historial. Los demás pasos aportan
pruebas (fuentes, frases, pasos del historial, afirmaciones, rectificaciones) y lo que escriban
antes del guardado no es lo que queda. Las revisiones a mano entran como una fuente más
(`revisada-…`) con prioridad. La referencia pasa sus copias por la misma decisión, por eso las
copias guardan lo que cada fuente afirma de la presencia.

### Un solo sitio decide también los demás datos (desde el 21 de octubre de 2026)

`decidir.aplicar` decide además, en cada guardado, el objetivo, el lugar, el inicio, el número de
drones, el cierre y el titular (`decidir_datos`) y, con el estado ya decidido, el tipo
(`incidentes.con_tipo`); la cabecera sale de ellos (`auditoria_fichas.cabecera`). Los demás pasos
siguen escribiendo en memoria, pero lo que queda al guardar es lo que deciden estas reglas:

- **objetivo** (`decidir_objetivo`): la revisión a mano; si la ficha no tiene instalación (o es
  «otra»), la que nombran el titular y las fuentes, una sola del nomenclátor, del país y cerca del
  punto (`proceso/objetivo_del_titular.py`); si no, la de la ficha con el OACI de la instalación
  del nomenclátor que su nombre nombra (con OACI, categoría «aeropuerto», también una base aérea).
  Una cárcel es «otra». Sin OACI no va la clave (el esquema no admite un OACI nulo).
- **lugar**: la revisión a mano; con homónimos, la localidad que dice la fuente por su municipio
  («Józefów w gminie Nieporęt», `ubicacion.lugar_del_homonimo`).
- **drones** (`decidir_drones`): la revisión a mano; «desconocido» si la autoridad concluye que no
  era un dron (presencia descartada). «Al menos N» espera al esquema que admita un rango sin
  máximo (el 1.20.0 exige el máximo).
- **titular** (`decidir_titulo`, desde el 23 de octubre de 2026), en español y en inglés, al
  final, con todo lo demás ya decidido: el texto revisado a mano («datos» y, si no, «titulares»)
  o el de la ficha; el dron como confirmado o posible según la presencia
  (`proceso/titulares.py`); y, sin atribución de una autoridad, sin el país del dron ni su autor
  (`atribucion.titulo_sin_atribucion`). Solo se quita la nacionalidad pegada al dron («drones
  rusos», «drones y aviones turcos», «Russian Shahed drones»), en los dos idiomas; se quedan la
  del espacio aéreo («espacio aéreo ucraniano»), el lugar, una persona o un buque. Un titular no
  afirma drones que ninguna cita nombra: si la cita guardada no los nombra, una revisión de
  «datos» rehace el titular con la cita que sí lo hace (EODI-2026-00668) o la ficha se retira.
  Ningún otro paso escribe el titular; antes lo hacían el control, la revisión a mano, la barrera
  y las declaraciones oficiales, y se pisaban cada hora (EODI-2025-00378).
- **tipo** (`incidentes.con_tipo`): interrupción si se interrumpió un aeropuerto; incursión solo
  si la autoridad lo atribuye, o cuenta el espacio aéreo violado, la frontera cruzada, el rastreo,
  el derribo, la caída o los restos con el suceso confirmado, o hay pruebas físicas con el suceso
  confirmado; en el mar, solo si lo atribuye. Si no, sobrevuelo.
- **revisiones a mano** (`configuracion/incidentes_revisados.json`, «datos»): una por ficha y dato
  (`objetivo`, `lugar`, `inicio`, `drones`, `cierre`, `titulo`), con el valor, la cita (25
  palabras como mucho) y el enlace de la fuente que lo dice, y el motivo. Valen para la ficha que
  tiene esa fuente o, si la fuente leída no está en la ficha, la de su país (`pais`). La
  revisión `cierre` dice si hubo cierre; su duración citada se queda. Ninguna otra regla cambia
  un dato revisado a mano: la fecha de una nota oficial no pisa el inicio revisado, el control
  no corrige el número de drones ni el inicio revisados ni quita la instalación revisada, y la
  ubicación oficial toma la localidad de la revisión. Si dos reglas se pisan, la comprobación K
  de la auditoría lo cuenta (un dato que vuelve 3 veces o más en 48 horas).

### Criterios de cada dato (desde el 21 de octubre de 2026)

Con ellos se decide el valor correcto de la referencia (y el que debe dar la ficha):

- **Nombre de la instalación:** el nombre único del nomenclátor (`configuracion/lugares_europa.json`
  para aeropuertos y bases, `configuracion/instalaciones_europa.json` para lo demás), el mismo en
  todas las fichas y en su lengua oficial; si el nomenclátor no lo tiene en esa lengua, el nombre
  oficial en ella (Luchtmachtbasis Schaffen, Kerncentrale Doel). Nunca en la lengua de la fuente
  (una embajada en Copenhague va en danés, no en italiano). La clave `oaci` va siempre, a nulo si
  no la tiene.
- **lugar:** la localidad del suceso, no la instalación, la provincia ni el destino del avión; en
  el mar, el mar o la costa (Öresund, costa de Wicklow). Con homónimos manda la fuente (Józefów de
  la gmina Nieporęt, no el de junto a Otwock).
- **drones:** el número que da una fuente para ESTE suceso. «Al menos N» → `{min: N, max: null}`;
  «más de N» → `{min: N+1, max: null}`; un número indefinido como «kilkanaście» → su rango. Las
  violaciones del espacio aéreo no son drones. Si la autoridad dice que no hubo dron →
  «desconocido».
- **presencia:** `no_acreditada` si una autoridad cierra la investigación sin probarlo ni
  descartarlo; `descartada` si la autoridad concluye que era otra cosa, aunque lo diga con «muy
  probablemente» en su conclusión. Una «posible» otra causa de la prensa, o un aviso inicial, no
  descarta nada; una búsqueda sin resultado el mismo día tampoco es un cierre.
- **estado:** `confirmado` si una autoridad u operador oficial declara que el suceso ocurrió (un
  portavoz que confirma los avisos, la OTAN que reconoce que saltó el detector); negar el dron
  rectifica la presencia, no el estado. `atribuido` solo con una autoridad del país afectado.
- **tipo:** `incursion` solo si una autoridad, o una prueba física que confirma una autoridad,
  demuestra que un dron estatal entró desde fuera; las fuentes anónimas o la narración del
  periodista no bastan. Un buque alcanzado en el mar es `sobrevuelo` salvo que una autoridad diga
  que estaba en aguas del país.
- **cita:** del mismo suceso y que diga ese dato (no la fecha de publicación).
- **zona:** la regla de los 150 km del flanco este, medida desde la localidad de la ficha (la
  que enseña en «Lugar»; si no está en el nomenclátor, desde el punto). Desde el 27 de octubre de
  2026: el punto puede ser la instalación, y el aeropuerto Chopin, cerrado por los drones rusos
  del 10 de septiembre de 2025 (EODI-2025-00233), está a 151 km de Bielorrusia mientras Varsovia
  está a 147. Solo cuando la regla no puede, una revisión de `datos` con el campo `zona` y la cita
  de una fuente de la ficha.

## Correcciones a mano

Siguen en `configuracion/incidentes_revisados.json` y mandan sobre el control: una presencia
revisada a mano no la cambia el control, una unión revisada no la deshace nadie. La sección
`titulares` admite ahora `drones` (`{"valor": "desconocido"}`) para quitar un número de drones que
no da ninguna fuente, como en el 00515.
