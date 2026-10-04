# Corrección de errores de datos

European Observatory of Drone Incidents, 4 de octubre de 2026. Las horas son UTC. Un pull request
por bloque, en este orden. La base es de solo añadir: cada corrección entra como versión nueva con
su motivo en el historial, y lo retirado queda marcado como retirado con su causa. Todo se
reprocesa desde los mensajes y las citas ya guardados, sin volver a descargar ni llamar al
extractor salvo donde se dice.

Cifras «antes» medidas sobre la base de la rama `estado` de las 08:15 del 4 de octubre (la que
servía droneobservatory.eu), antes de cambiar nada.

## Bloque 1. Víctimas imposibles y homenajes guardados como impactos

### Causa

Dos fallos en la lectura por código de los mensajes de las administraciones
(`proceso/mensajes_guerra.py`):

1. **El año se leía como número de víctimas.** La cifra de víctimas se buscaba en todo el mensaje
   con un número de hasta cuatro cifras junto al verbo, y solo se quitaban las fechas sin año
   («30 грудня»). En «загинув 30 грудня 2024 року» quedaba «загинув 2024». Además, la cifra del
   mensaje entero (todas las armas, todos los lugares, acumulados desde el inicio de la invasión,
   ganado muerto) se asignaba al impacto si el mensaje daba un solo lugar: «Загинули 500 голів
   свійської тварини» (Pavlohrad, 500 fallecidos), «з початку повномасштабного вторгнення …
   поранені понад 2100 людей» (Zaporiyia, 2.100 heridos), las víctimas de un misil en Kryvyi Rih
   repetidas por el canal de Zaporiyia (130 heridos), edades sin guion («жінки 59 та 67 років»).
   Y al volver a leer un mensaje, el impacto se quedaba con la mayor cifra vista, así que una cifra
   mal leída no se corregía nunca.
2. **Los homenajes no se distinguían de un ataque.** La administración de Donetsk publica cada día,
   con la plataforma Меморіал, la memoria de un caído («…загинув 30 грудня 2024 року поблизу
   селища Роздольне… внаслідок атаки ворожого FPV-дрона»); la de Lviv, las despedidas de sus
   militares. Esos mensajes nombran un dron, un daño y un pueblo, y salían como impacto de la
   noche de su publicación.

### Cambios

- **Víctimas leídas frase a frase** (`_victimas_frase`): un número igual a un año que la frase
  escribe como fecha («30 грудня 2024 року», «у 2025 році») no es una cifra de víctimas; las
  edades sin guion y los animales tampoco; una cifra de más de 100 solo vale con la cifra pegada
  al verbo («загинули 120 людей», «поранено 130 осіб»); si no, el campo queda vacío.
- **Víctimas solo de frases de drones**: cuentan las frases cuya arma (la suya o la de la frase
  anterior) son drones y nada más, y que no dan un acumulado («з початку», «с начала», «за
  тиждень»). Mismo criterio para heridos y fallecidos. Siguen asignándose al impacto solo si el
  mensaje da un único lugar.
- **Homenajes, obituarios y memoria** (regla `HOMENAJE`, motivo `homenaje`): un mensaje de la
  plataforma Меморіал, con «на псевдо» o «позивний», «Пам'яті …», un premio póstumo o la muerte
  de alguien con fecha y año no es un impacto. Las frases de condolencia o de luto dentro de un
  parte («Світла пам'ять», «Схиляємо голови», «соболезнования») se saltan, sin anular el resto del
  parte.
- **Cada fuente guarda sus víctimas** (`lecturas[].victimas`, interno, esquema 1.9.0 ampliado) y
  el impacto lleva la mayor de sus fuentes: volver a leer un mensaje corrige la cifra.
- **Corrección de lo guardado** (`recogida/guerra.corregir`, cursor `guerra:correccion`, versión
  `victimas-homenajes/1`): una vez, dentro de la recogida horaria, vuelve a leer con las reglas
  nuevas el mensaje de cada fuente de los impactos vigentes desde los textos que guarda el lector
  en el servidor. Una fuente cuyo mensaje no describe un ataque con dron sobre un lugar se quita;
  un impacto sin fuentes queda retirado con su motivo; las víctimas se rehacen. Cada cambio deja
  su motivo en el historial. A mano: `python -m recogida.guerra corregir --base <db.age>`.
- Versión del analizador `mensajes-guerra/3`.

### Cifras

Medidas aplicando la corrección a una copia de la base de las 08:15 con los mensajes del servidor
(6.292 impactos vigentes revisados; ninguna fuente sin texto).

| | Antes | Después |
| --- | ---: | ---: |
| Impactos retirados (homenaje, obituario o memoria) | — | 30 |
| Impactos con la cifra de víctimas cambiada | — | 75 |
| Impactos con fallecidos igual a un año (2023, 2024 o 2025) | 8 | 0 |
| Impactos con más de 100 heridos o fallecidos | 12 | 0 |
| Impactos vigentes | 6.292 | 6.262 |

Entre los retirados, los seis del encargo: EODI-IG-2025-00179 (Rozdolne), EODI-IG-2025-00165,
EODI-IG-2026-03500 (premio póstumo a dos periodistas), EODI-IG-2026-00059, EODI-IG-2026-03471
(despedida de militares en Lviv) y EODI-IG-2026-00068. Los demás son memorias de Меморіал en
Donetsk, obituarios de civiles (Mariúpol 2022, Malotaranivka 2023) y un aviso de baños en Odesa
(«на водоймах Одеської області загинули 15 людей»).

Fallecidos y heridos de los impactos vigentes por trimestre (por el día del ataque, o el de la
publicación si el mensaje no lo da):

| Trimestre | Fallecidos antes | Fallecidos después | Heridos antes | Heridos después |
| --- | ---: | ---: | ---: | ---: |
| 2024 T4 | 4.048 | 0 | 0 | 0 |
| 2025 T1 | 2.100 | 12 | 2.313 | 93 |
| 2025 T2 | 526 | 23 | 660 | 264 |
| 2025 T3 | 50 | 16 | 138 | 87 |
| 2025 T4 | 4.152 | 14 | 490 | 156 |
| 2026 T1 | 34 | 24 | 368 | 200 |
| 2026 T2 | 6.100 | 28 | 298 | 168 |
| 2026 T3 | 195 | 43 | 487 | 321 |
| 2026 T4 | 71 | 4 | 63 | 4 |

La fila 2024 T4 eran homenajes fechados por el año de la muerte. Las víctimas que quedan son las
que una frase de drones atribuye a un único lugar: es una cota inferior de las víctimas de los
ataques con drones, no el total de cada región.

### Pruebas añadidas

`tests/test_victimas_guerra.py`: los seis mensajes reales (no son impactos y no dan un año como
víctimas), año en la frase, más de 100 solo con la cifra pegada al verbo, edades y ganado,
acumulados y misiles en el mismo mensaje, condolencia dentro de un parte, corrección de lo
guardado (retira el homenaje con su motivo, corrige la cifra, deja historial, una sola vez) y
relectura que corrige la cifra.
