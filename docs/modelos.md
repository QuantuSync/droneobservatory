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

Una ficha que el base da por «no es un incidente» con seguridad no se escala. Una verificación que
confirma la ficha no se escala aunque el caso sea crítico: su ficha ya la decidió el experto. Las
tareas mecánicas (traducir, partes de Ucrania, catálogo, documentos oficiales) no se escalan.

## Topes

- Cada modo (`modelo/coste.py`) mantiene su tope en dólares, ahora con la tarifa real de cada
  modelo: lo que gasta el experto cuenta en el modo de la llamada.
- El experto tiene además su tope diario propio: **0,30 USD** al día (UTC), sumando todos los modos
  (`LIMITE_EXPERTO_DIARIO_USD`, `Almacen.gastado_modelo`). Antes de cada llamada se suma lo que
  lleva gastado hoy y el peor caso.
- **Si el tope del experto se agota**, el caso que lo necesitaba **espera al día siguiente** en vez
  de publicarse con la respuesta del base, y nunca frena lo demás:
  - una ficha nueva: el candidato no se publica y queda en el cursor `esperan_experto` hasta las
    00:00 UTC; al día siguiente va de los primeros. Si el experto falla (caído, error), espera solo
    hasta la recogida siguiente;
  - un par dudoso: queda «dudoso» con `espera_experto` (no se da por distinto a las 6 horas) y la
    ficha nueva sigue retenida, sin el límite de 6 horas, hasta que decida el experto;
  - una verificación que contradice la ficha: no se aplica nada hasta que la repita el experto; la
    ficha nueva sigue retenida.

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
  `traducciones`, 2 USD): `python -m recogida.control_fichas traducir-pendientes`.

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

## Prueba comparativa del 14 de octubre de 2026

(Ver el apartado siguiente: resultados y decisión.)
