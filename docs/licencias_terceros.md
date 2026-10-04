# Código y datos de terceros

Lo que el observatorio reutiliza de otros proyectos, con su licencia. El código del
repositorio es Apache-2.0 (`LICENSE`) y los datos publicados, CC BY 4.0 (`LICENSE-DATOS`),
salvo lo que se dice aquí.

## Código y modelos

### traffic (MIT)

`proceso/espera.py` reproduce el detector de circuitos de espera de
[traffic](https://github.com/xoolive/traffic) (commit `aee9ba0`,
`src/traffic/algorithms/navigation/holding_pattern`), y
`configuracion/espera_traffic.json` lleva sus pesos (`scaler.onnx` y `classifier.onnx`)
exportados sin cambios. Los criterios de aproximación frustrada de `proceso/vuelos.py` siguen
los de la misma biblioteca.

```
MIT License

Copyright (c) 2018 Xavier Olive

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### skylight y gods-eye-view (MIT)

Los conjuntos de designadores de tipo OACI de `proceso/aeronaves.py` (helicópteros, drones y
cazas) parten de los de [skylight](https://github.com/cpaczek/skylight)
(`web/src/display/aircraftGlyph.ts`) y de su adaptación en
[gods-eye-view](https://github.com/bilawalsidhu/gods-eye-view) (`src/data/aircraftClass.js`),
ampliados con aviones radar, cisternas, patrulla marítima y transportes militares.

```
MIT License

Copyright (c) 2026 cpaczek

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

```
MIT License

Copyright (c) 2026 Bilawal Sidhu

(El mismo texto de permiso y de ausencia de garantía que el anterior.)
```

### h3 (Apache-2.0)

La interferencia GNSS usa la biblioteca [h3](https://github.com/uber/h3-py) (Uber
Technologies, Apache-2.0) como dependencia de `requirements.txt`; no se copia su código.

### flag-icons (MIT)

Las banderas del marcador de los incidentes atribuidos (`web/public/banderas/*.svg`) son las
versiones cuadradas (`flags/1x1`) de [flag-icons](https://github.com/lipis/flag-icons) 7.5.0,
copiadas en el repositorio (la web no las carga de ningún servidor externo). El único cambio:
`width="512" height="512"` en la etiqueta `<svg>`, para que todos los navegadores las dibujen
en el lienzo del mapa. Son 48: los países europeos de `configuracion/paises_europa.json`,
Rusia, Bielorrusia, Ucrania, Turquía, el Vaticano e Irán, los mismos de
`configuracion/paises_atribucion.json`. La licencia va también junto a ellas
(`web/public/banderas/LICENSE.txt`).

```
The MIT License (MIT)

Copyright (c) 2013 Panayiotis Lipiridis

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Datos

| Datos | Licencia y condiciones | Uso |
| --- | --- | --- |
| Archivo diario de [adsb.lol](https://adsb.lol/) (`adsblol/globe_history_AAAA`) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), © adsb.lol contributors; los receptores ceden sus datos con CC0 | Se procesa en el servidor. El bloque `trafico_aereo` de los ficheros publicados es una base de datos derivada y se ofrece con ODbL 1.0 (`LICENSE-DATOS`); la web lo atribuye en la metodología. Las trazas filtradas quedan en el disco del servidor y no se publican |
| [Open-Meteo](https://open-meteo.com/) (Historical Forecast API) | CC BY 4.0, «Weather data by Open-Meteo.com»; uso no comercial sin clave | Condiciones internas de cada incidente; atribución en la web |
| METAR del [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/) | Dominio público; se agradece la atribución | Exclusión meteorológica y condiciones internas; atribución en la web |
| [OurAirports](https://ourairports.com/data/) | Dominio público | `configuracion/aeropuertos_trafico.json` |
| [EUROCONTROL](https://www.eurocontrol.int/performance/data/download/csv/) «Airport traffic» | Copia con mención de EUROCONTROL, sin fines comerciales y sin modificarlo | Solo como referencia interna de la cobertura, en el disco del servidor; no se publica ninguna cifra suya |
| [Copernicus DEM GLO-90](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) (archivo público `copernicus-dem-90m` de AWS) | Licencia gratuita de Copernicus para el público general; lo derivado lleva «produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved» | Horizonte de radar del motor de deducción, en el servidor; las teselas no se redistribuyen y el resultado es interno (exportación para AEGIS) |
| Catálogo de prestaciones de drones (`configuracion/catalogo_drones.json`) | Cifras de fabricantes, inteligencia, análisis técnico y prensa técnica, cada una con su enlace y una frase breve de la fuente como cita | Motor de deducción; las fuentes numeradas en `configuracion/catalogo_fuentes.json` |
