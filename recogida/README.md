# recogida

Recogida automática de fuentes.

| Módulo | Contenido |
| --- | --- |
| `descarga.py` | Descarga educada: pausa por sitio, navegador real, reintentos y detección de bloqueos |
| `cache.py` | Páginas en bruto comprimidas en `data/cache/`, fuera de git |
| `telegram.py` | Lectura de la vista pública web de un canal (`t.me/s/<canal>`) |
| `recorrido.py` | Recorrido hacia atrás con `?before=` y avance reanudable |
| `fuerza_aerea.py` | Fuente: verificación del canal oficial y lectura desde el cursor |
| `parte.py` | Parser por código de los partes de ataque (solo drones) |
| `ejecucion.py` | Procesado de publicaciones y recuentos |
| `horaria.py` | Ejecución horaria del workflow |
| `historico.py` | Recuperación única del histórico desde octubre de 2022 |
