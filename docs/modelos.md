# Dos modelos: base y experto

Documentación técnica interna (no se enseña en la web). Desde el 14 de octubre de 2026 las
llamadas al servicio de modelos usan dos modelos: el **base** para todo y el **experto** solo
para los casos difíciles, que decide el código con reglas fijas. Antes había uno solo (Haiku 4.5,
el de `EODI_EXTRACTOR_MODELO`).

| Papel | Modelo | Tarifa (USD por millón de tokens) |
|---|---|---|
| base | Haiku 5.5 | 0,10 entrada / 0,50 salida con peticiones de hasta 100.000 tokens; 0,50 / 2,50 por encima |
| experto | Sonnet 5.5 | 2 / 10 |
| anterior (vuelta atrás) | Haiku 4.5 | 1 / 5 |

En todos, escribir en la caché cuesta 1,25 veces la entrada y leerla 0,1 veces; los lotes cuestan
la mitad. El tramo de más de 100.000 tokens se aplica a toda la petición cuando su entrada (con la
caché) pasa de 100.000. Las tarifas están en `modelo/modelos.py` (`MODELOS`) y cada llamada se
cobra con la del modelo que la hizo (el campo `model` de la respuesta).

## Configuración

Variables del fichero de secretos `extractor.env` (en el servidor, `/home/eodi/.eodi/
extractor.env`; en local, `%USERPROFILE%\.eodi\extractor.env`), que cargan todas las unidades:

- `EODI_MODELO_BASE`: el identificador completo del modelo base (el del proveedor, que acaba en
  `haiku-5-5`). Si no está, se usa `EODI_EXTRACTOR_MODELO`, el de antes.
- `EODI_MODELO_EXPERTO`: el identificador completo del experto (acaba en `sonnet-5-5`). Si no
  está, no se escala nada.

Los identificadores completos solo están en ese fichero: el código reconoce cada modelo por su
familia y su versión (`haiku-5-5`, `sonnet-5-5`, `haiku-4-5`) para saber su tarifa y lo que
admite. Un identificador que no reconoce se trata como el modelo de antes (tarifa de 1 / 5 y
petición con temperatura).

**Volver atrás**: quitar `EODI_MODELO_BASE` y `EODI_MODELO_EXPERTO` del fichero (en el servidor
y en local). Todo vuelve a hacerse con `EODI_EXTRACTOR_MODELO`, con temperatura 0 y sin esfuerzo,
como antes. Para quitar solo el escalado, quitar `EODI_MODELO_EXPERTO`.

## Peticiones adaptadas a cada modelo

Cada petición se escribe una vez (`modelo/ficha.py`, `ficha_oficial.py`, `guerra.py`,
`catalogo.py`, `control.py`) con temperatura 0 y un esfuerzo, y `modelos.adaptar` deja lo que
admite el modelo que la va a hacer (lo hace el cliente, `modelo/cliente.py`, en cada llamada y en
cada petición de un lote):

- **Temperatura**: los modelos nuevos dan un error 400 con `temperature`, `top_p` o `top_k`; se
  quitan. El de antes la conserva.
- **Esfuerzo** (`output_config.effort`): los modelos nuevos razonan antes de contestar y el
  esfuerzo gradúa cuánto. El de antes no lo admite y se quita.

| Petición | Esfuerzo | Por qué |
|---|---|---|
| ficha de una noticia (`ficha.py`) | medio | decide los datos que se publican |
| documento oficial (`ficha_oficial.py`) | medio | ídem |
| verificación de una ficha (`control.py`) | medio | comprobar cada dato contra su frase |
| comparación de dos fichas (`control.py`) | alto | lo más difícil: si son el mismo suceso |
| lugares de un parte de Ucrania (`guerra.py`) | bajo | formato fijo, mecánico |
| frases del catálogo (`catalogo.py`) | bajo | clasificar una frase |
| traducción de citas (`control.py`) | bajo | mecánico |

- **Máximo de salida**: el razonamiento cuenta en el máximo. A cada petición se le suma un margen
  por modelo y esfuerzo (bajo, medio, alto): base 3.000 / 8.000 / 12.000; experto 2.000 / 4.000 /
  6.000. Medido el 14 de octubre de 2026 con fichas reales: el base razona de 1.100 a 4.800 tokens
  por ficha con esfuerzo medio (con 4.000 de margen, dos de cada diez se cortaban); el experto
  apenas razona. El peor caso del gasto (`coste.peor_caso`) cuenta ese margen.
- **Salida estructurada**: igual que antes (`output_config.format` con su esquema). Las
  respuestas se leen por tipo de bloque, así que el bloque de razonamiento que va delante no
  estorba.
- **Caché**: las instrucciones van marcadas para la caché en el base, que hace varias llamadas
  seguidas con las mismas instrucciones. En el experto se quita la marca: hace una o dos llamadas
  por recogida y escribir la caché le costaría un 25 % más sin leerla nunca.
- **Espera de cada respuesta**: 90 s (base: 120 s) y 150 s (experto), en vez de 60 s.

## Cuándo se escala al experto

Lo decide el código (`proceso/escalado.py`) mirando la respuesta del base; si se escala, se repite
la misma petición con el experto y **vale la respuesta del experto**.

1. **poca_seguridad**: el base da menos de 0,7 de confianza a un dato clave de la ficha (es
   incidente, tipo, país, lugar, inicio, presencia, número de drones, cierre, minutos de cierre,
   dron estatal).
2. **duplicado_dudoso** (comparación de dos fichas): el base dice «dudoso», su decisión no casa
   con lo que él mismo dice del día y del sitio, o dice «mismo día y mismo sitio» y aun así las
   separa (en la prueba, separó así dos duplicados reales porque una fuente citaba otro suceso).
3. **contradiccion** y **sin_cita**: en la ficha, una autoridad dice que hubo drones y otra que no,
   o un dato clave no tiene una frase que esté, literal, en su fuente; en la verificación de una
   ficha publicada, lo que lee el base contradice la presencia, el número de drones o el cierre
   de la ficha.
4. **critico**: dron confirmado, atribuido (dron estatal o una declaración de autoría), incursión
   en un país de la OTAN o en Moldavia (lista de `configuracion/avisos.json`) o cierre de
   aeropuerto.
5. **publicada** (desde el 15 de octubre de 2026, obligatoria): ver «Nada publicado se retira ni se
   rebaja sin el experto».
6. **senal** (ídem): el base da un candidato por «no es un incidente», aunque esté seguro, y alguna
   fuente es oficial o habla de hundimiento, víctimas, desaparecidos, heridos, daños, cierre de
   aeropuerto o incursión. Fuente oficial: un medio de `configuracion/fuentes_oficiales.json`, un
   dominio de gobierno, defensa, policía o aviación civil (`dominios_oficiales`) o una declaración
   de una autoridad en la ficha. Las palabras, en las lenguas de las fuentes (español, inglés,
   alemán, francés, rumano, polaco, búlgaro, ruso, ucraniano, neerlandés, italiano, danés…), están
   en `configuracion/senales_escalado.json`; se buscan en el titular y el texto que se mandaron,
   sin mayúsculas ni acentos.

Fuera de esas señales, una ficha que el base da por «no es un incidente» con seguridad no se
escala. Una verificación que
confirma la ficha no se escala aunque el caso sea crítico: su ficha ya la decidió el experto. Las
tareas mecánicas (traducir, partes de Ucrania, catálogo, documentos oficiales) no se escalan.

## Nada publicado se retira ni se rebaja sin el experto

Desde el 15 de octubre de 2026. En la prueba comparativa, Haiku 5.5 dio con seguridad (0,8) por
«no es incidente» una noticia del ataque con drones del 6 de octubre de 2026 a dos buques en aguas
búlgaras del mar Negro (uno se hundió, hubo desaparecidos; EODI-2026-00489), y ninguna regla lo
escalaba. Desde entonces:

- **Fichas**: una respuesta del base que daría por «no es incidente» la ficha ya publicada de su
  candidato, o que rebajaría su presencia (confirmada → no confirmada → descartada), su dron estatal
  o su cierre, se escala siempre (`escalado.motivos_publicada`, motivo «publicada: …»). Si el
  experto no puede (tope del día agotado o error), el candidato espera (cursor `esperan_experto`) y
  **la ficha publicada se queda como estaba**.
- **Red de seguridad** (`extraccion.procesar_respuesta`): si una respuesta del base que retiraría o
  rebajaría una ficha publicada llega sin el experto (un lote, una ficha que no valida, una
  respuesta ilegible), no se aplica: la ficha publicada sigue igual, la extracción se guarda con
  `ficha_base` y `conservada` (una reconstrucción no la lee) y el candidato queda en
  `esperan_experto` con `revision`, para repetirse con el experto en la recogida siguiente (se
  vuelve a extraer aunque sus noticias no hayan cambiado y se escala siempre).
- **Uniones del control**: una comparación que uniría dos fichas y retiraría así una ya publicada
  (la que se une a la otra; las retenidas no cuentan) se escala siempre (`escalado.motivos_union`).
  Sin el experto, el par queda «dudoso» esperándolo y las dos fichas siguen publicadas.
- **Verificaciones**: ya se escalaban siempre que contradicen la presencia, el número de drones o el
  cierre (la única forma de rebajar la presencia), y sin el experto no se aplica nada.
- Las reglas del código que no son decisiones del modelo (bajar un estado sin fuente oficial, un
  suceso sin día) siguen como antes.
- **Sin experto configurado** (vuelta atrás: sin `EODI_MODELO_EXPERTO`) todo sigue como antes del
  14 de octubre: el modelo único decide.

Pruebas: `tests/test_nada_se_retira.py` (la 00489, cada señal con un caso inventado, fuentes
oficiales, retirada y rebaja de una ficha publicada con y sin experto, lotes, reconstrucción y
uniones del control).

## Lo que no es un suceso no es ficha

Desde el 15 de octubre de 2026. La EODI-2026-00539 se publicó a partir de un reportaje de
contenido de socio de delfi.lt (sección `projektai/pulsas`) sobre cómo actúa la defensa aérea de
la OTAN, sin ningún suceso concreto; se retiró a mano en el PR #242. Ahora el control lo impide
desde el origen ([`proceso/no_es_suceso.py`](../proceso/no_es_suceso.py)):

- Al descargar cada fuente se leen, además de sus primeras frases, **las marcas de su página**
  (`modelo/paginas.marcas`): tipo, sección y etiquetas del artículo (`og:type`,
  `article:section`, `article:tag`, `keywords`…) y el tipo y la sección de sus datos estructurados
  (`OpinionNewsArticle`, `AdvertiserContentArticle`…). Nunca los menús ni las clases de estilo:
  «Reklama» y «Užsakomasis turinys» están en el menú de todas las páginas de delfi.lt.
- Las señales, en las lenguas que lee el observatorio, están en
  [`configuracion/no_es_suceso.json`](../configuracion/no_es_suceso.json), por categorías: contenido
  patrocinado o de socio y publicidad («partner content», «sponsored», «advertorial», «Anzeige»,
  «Partnerinhalt», «turinio partneris», «publicidad»…), opinión («opinión», «Kommentar», «op-ed»…),
  análisis, explicativos («cómo funciona…»), entrevistas y resúmenes generales. Se buscan en las
  marcas, en la dirección (secciones como `/opinion/`, `/sponsored/` o `delfi.lt/projektai/`) y en
  la cabeza del titular («Opinión:», «Kommentar |»); los explicativos, en todo el titular.
- El modelo ve lo que dice la página de cada fuente («La página lo marca como…») y sus
  instrucciones dicen que esos artículos no son incidentes si no cuentan un suceso concreto con su
  fecha y su lugar.
- **Una ficha nueva** cuyas fuentes son todas contenido patrocinado o de socio no se crea, aunque
  el base la dé por suceso, y sin gastar en el experto. Si todas son de las otras categorías y el
  base la da por suceso, hay duda real: **decide el experto** (motivo de escalado
  `no_es_suceso: <categoría> (<medio>: «<señal>»)`). Basta una fuente que cuente el suceso para que
  no se aplique.
- **Una ficha publicada** nunca se retira sin el experto: si el control de las fichas
  (`recogida/control_fichas.no_es_suceso_de`, al leer sus fuentes para verificarla) o una nueva
  extracción ven que ninguna de sus fuentes cuenta un suceso, su candidato se repite con el experto
  (`esperan_experto` con `revision`). Con una fuente oficial, nunca. Si el experto la da por «no es
  incidente», se retira con el motivo en español y en inglés (`retirado.motivo` y `motivo_en`).

Pruebas: `tests/test_no_es_suceso.py` (la 00539 con las marcas reales de su página, señales en
varios idiomas, menús, una noticia que basta, la ficha nueva sin experto, la duda que decide el
experto, la publicada que retira el experto con su motivo en dos idiomas y la que se queda sin él,
y el control de las fichas).

## Topes

Principio (desde el 15 de octubre de 2026): **lo crítico nunca espera a que se renueve un tope**.

- Cada modo (`modelo/coste.py`) mantiene su tope en dólares con la tarifa real de cada modelo, solo
  para las llamadas del modelo base. **Lo que gasta el experto cuenta solo contra su propio tope**,
  nunca contra el de la recogida horaria ni el de otro modo (`Almacen.gastado` no suma las llamadas
  escaladas). El 14 de octubre de 2026, cuatro candidatos esperaron porque la llamada al experto no
  cabía en el tope de la horaria (0,26 de 0,30 USD) aunque el experto tenía margen.
- **Tope normal del experto: 1,00 USD al día** (UTC), sumando todos los modos
  (`LIMITE_EXPERTO_DIARIO_USD`, `Almacen.gastado_modelo`). Antes de cada llamada se suma lo que
  lleva gastado hoy y el peor caso. Con el tope de 0,30 USD, el 15 de octubre de 2026 tras 8
  escalados (0,23 USD) los pares duplicados del mar Negro y la ficha de Mihail Kogălniceanu
  quedaron esperando hasta el día siguiente.
- **Reserva crítica: 0,50 USD al día** aparte (`RESERVA_CRITICA_DIARIA_USD`), solo para los casos
  críticos (`escalado.es_critico`, y `control_fichas.critico` para las fichas ya publicadas):
  - incursiones o sucesos en bases e instalaciones militares de países de la OTAN o en Moldavia (la
    categoría del objetivo o las expresiones de `criticos.base_militar` en
    `configuracion/senales_escalado.json`, como «air base», «baza aeriană» o «Kogălniceanu», con el
    país del caso de la OTAN o Moldavia);
  - fichas confirmadas o atribuidas (motivos «critico: …»);
  - cierres de aeropuerto;
  - sucesos con víctimas, heridos, desaparecidos, hundimientos o daños (en la ficha o en sus
    fuentes, con las señales de `senales_escalado.json`);
  - todo lo que retire o rebaje una ficha publicada (motivos «publicada: …», una unión que retira
    una publicada, una verificación que contradice su presencia o su cierre).

  Si el tope normal no da, estos casos usan la reserva y no esperan (`coste.comprobar_experto`
  devuelve el tramo). Lo que el experto gasta por encima de 1 USD en el día es de la reserva.
- **Si se agota también la reserva**, el caso crítico no espera al día siguiente: se reintenta en
  cada recogida (`espera_experto` a 50 minutos), sale en el resumen diario y, si lleva más de 6
  horas sin poder resolverse, la vigilancia abre la incidencia (`experto_critico`).
- **Un caso que no es crítico** y no cabe en el tope normal espera al día siguiente en vez de
  publicarse con la respuesta del base, y nunca frena lo demás:
  - una ficha nueva: el candidato no se publica y queda en el cursor `esperan_experto` hasta las
    00:00 UTC; al día siguiente va de los primeros. Si el experto falla (caído, error), espera solo
    hasta la recogida siguiente;
  - un par dudoso: queda «dudoso» con `espera_experto` (no se da por distinto a las 6 horas) y la
    ficha nueva sigue retenida, sin el límite de 6 horas, hasta que decida el experto;
  - una verificación que contradice la ficha: no se aplica nada hasta que la repita el experto; la
    ficha nueva sigue retenida.
- Cada espera anota el tope con que se decidió (`tope` en `esperan_experto`, `tope_experto` en las
  decisiones del control): si el tope sube, las esperas anteriores vencen en la recogida siguiente
  (`coste.espera_vencida`; las de antes del 15 de octubre de 2026, sin ese dato, son de 0,30 USD).
  Cada espera de un caso crítico lleva `critico`. Un par o una verificación cuya espera vence
  vuelve en la recogida horaria siguiente aunque sus fichas ya no sean nuevas
  (`control_fichas.esperas_vencidas`), sin esperar a la pasada de madrugada.

## Lotes (mitad de precio) para lo que no es urgente

- **Madrugada** (`eodi-control`, 01:41 UTC): los pares y las verificaciones de las últimas 48 horas
  van por lote (`repaso` con alcance «noche»), sin el cerrojo mientras el lote se procesa (3 horas
  como mucho); lo que el base pide escalar se repite con el experto en llamadas directas, dentro
  de su tope. Tope de la revisión: `TOPE_NOCHE_USD` (0,08 USD). Después, las citas sin traducir,
  también por lote, con su propio tope (`TOPE_NOCHE_CITAS_USD`, 0,05 USD, unas 500 citas en el
  peor caso): lo nuevo de cada día son unas 15 a 30 citas de la capa de Ucrania (medido el 14 de
  octubre de 2026), así que queda traducido esa misma noche y el resto del tope se come lo
  atrasado. Lo que gaste la revisión no le quita sitio.
- **Citas de cada hora**: las citas nuevas que deja cada recogida van en un lote que recoge la
  recogida siguiente (cursor `control_fichas:lotes`); el peor caso de los lotes sin recoger se
  reserva en el tope del día. Un lote que no termina en 25 horas se olvida y sus citas vuelven a
  quedar pendientes.
- **Traducción de una vez** de las citas que quedaban sin traducir el 14 de octubre de 2026 (modo
  `traducciones`, 2 USD): `python -m recogida.control_fichas traducir-pendientes`. La primera
  pasada (303 peticiones, 0,39 USD) tradujo 5.924 citas: con la regla «si ya está en ese idioma,
  deja vacío», el modelo base dejó vacía una de las dos traducciones en un tercio de las citas en
  ruso y en ucraniano, y esas no se guardan. Desde entonces se piden siempre las dos (en la sonda,
  0 vacías de 90) y el registro avisa de cada tanda con citas incompletas.

## Qué modelo decidió cada dato

- Cada llamada se anota con su modelo y si fue un escalado (tabla `llamadas_modelo`, junto a
  `llamadas_extractor`).
- Cada extracción guarda `modelo` y, si se escaló, `escalado` (los motivos).
- Cada incidente guarda en `control.modelos` (interno, esquema 1.19.0) el modelo que decidió cada
  dato de la ficha (campo de la ficha → identificador): el de la extracción y, en los que corrige
  el control, el de la verificación. Viaja en la exportación para AEGIS (formato 1.12.0,
  `docs/exportacion_aegis.md`).
- Cada decisión del control (par, verificación) guarda `modelo` y, si se escaló, `escalado`.

## Resumen diario

`control.json` guarda, por día de Madrid, las llamadas, las escaladas y el gasto de cada papel
(base, experto, anterior) de todas las llamadas del observatorio. El resumen de las 08:00
(sección SISTEMA) lo dice en una línea: «Modelos: modelo base N llamadas, X USD; modelo experto M
llamadas (E escaladas), Y USD; total Z USD». Los nombres de los modelos no salen en el resumen.

Además guarda, por día UTC, el gasto del experto repartido entre su tope normal y la reserva
crítica (`experto`) y los casos críticos que esperan ahora al experto (`criticos_esperando`, con
desde cuándo). El resumen lo dice así: «Experto: tope normal X de 1,00 USD; reserva crítica Y de
0,50 USD» y, si hay casos críticos esperando, «Casos críticos esperando al experto: N (se
reintentan en cada recogida)», uno por línea.

## Prueba comparativa del 14 de octubre de 2026

Antes de cambiar nada, en el servidor sobre una copia de la base y sin publicar nada (gasto 1,85
USD, tope 3). 73 fichas: los casos fallidos conocidos (Núremberg 00515/00516, los buques de
Bulgaria 00512-00514), 14 que el repaso del control corrigió en la presencia o el número de
drones y 54 de muestra variada (países, idiomas, tipos y estados), cada una con la petición tal
como la hace la recogida (titular y primeras frases de hasta tres fuentes, descargadas de nuevo).
Y 18 pares de fichas para los duplicados (los conocidos y 14 que el control ya había decidido).
Tres opciones: **a**) el modelo de antes (Haiku 4.5); **b**) Haiku 5.5 solo; **c**) Haiku 5.5 y,
cuando las reglas lo piden, Sonnet 5.5, cuya respuesta vale.

Cada desacuerdo entre las tres se juzgó con lo que dicen las fuentes (los datos en que coinciden
las tres cuentan como acierto de las tres). «Inventado»: un valor que la fuente no da (el «2-10»
de «drei Piloten», los 45 minutos de cierre de otro aeropuerto); «falta»: la fuente lo dice y la
ficha no. Presencia y tipo se puntúan como quedan tras las reglas del código (un cierre por dron
confirma la presencia y hace la interrupción). Los casos que las fuentes no permiten decidir no se
puntúan.

| Campo | a | b | c |
|---|---|---|---|
| es incidente (73) | 70 | 71 | 72 |
| presencia de dron (71) | 64 | 69 | 68 |
| número de drones (71) | 45 | 67 | 64 |
| fecha (64) | 56 | 59 | 62 |
| lugar (69) | 52 | 66 | 68 |
| duración del cierre (73) | 68 | 73 | 73 |
| tipo (66) | 61 | 62 | 65 |
| estado (66) | 55 | 58 | 62 |
| **total (553)** | **471** | **525** | **534** |
| datos inventados | 28 | 2 | 6 |
| datos que faltan | 33 | 11 | 5 |
| frases que no están literales en su fuente | 178 | 9 | 0 |
| duplicados detectados (13 reales) | 11 | 7 (3 dudosos) | 12 (1 dudoso) |
| duplicados falsos | 0 | 0 | 0 |
| coste medio por ficha (USD) | 0,0051 | 0,0022 | 0,0282 |
| coste medio por par (USD) | 0,0039 | 0,0011 | 0,0053 |

El coste de c cuenta el experto sin caché, como en producción. Se escalaron 68 de 73 fichas
(93 %): la muestra es de incidentes publicados, casi todos críticos (confirmados, cierres,
incursiones); en la recogida, la mayoría de los candidatos no son incidentes y no se escalan.

**Decisión: se adopta c.** Acierta al menos tanto como a en todos los campos, inventa menos (6
frente a 28) y detecta más duplicados sin ninguno falso. El base nuevo (b) ya es mejor que el
de antes en todo, así que la base es Haiku 5.5.

Lo que se vio:

- El modelo de antes inventaba el número de drones (19 veces: «2-10» con un plural, con «drei
  Piloten», con «câteva aeronave», con «two observations») y se quedaba sin salida en fichas largas
  (una respuesta cortada en el máximo de 1.500 tokens: Erfurt).
- El experto también pone «2-10» a veces con un plural sin número (6 veces); el base, casi nunca.
  La verificación del control lo corrige después (un plural sin cantidad no es un número).
- El base separaba dos duplicados reales porque una fuente de una de las fichas citaba otro
  suceso, aunque él mismo decía «mismo día y mismo sitio». Por eso se añadió la regla de escalado
  «mismo día y mismo sitio, pero separados»; con ella el experto los une (y uno más: los buques
  del 6 de octubre, que a y b separaban).
- Un fallo que ninguna regla recoge: el base dijo con seguridad (0,8) que una noticia sobre el
  ataque a dos buques frente a Biala no era un incidente; no se escaló. Otra ficha del mismo
  suceso sí se publicó.
