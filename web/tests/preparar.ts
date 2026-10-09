// Antes de cada fichero de pruebas: los reintentos de las descargas (src/datos/reintentos.ts) se
// hacen igual, pero sin esperar entre intentos.
import { fijarEsperas } from "../src/datos/reintentos.ts";

fijarEsperas([0, 0, 0, 0]);
