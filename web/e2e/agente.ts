/**
 * Lo que los navegadores de las pruebas añaden a su agente de usuario: en el cortafuegos de Vercel
 * (Security → Traffic → Top User Agents) se distinguen así de los visitantes. Desde el 27 de octubre
 * de 2026, cuando el 97 % de las peticiones del día eran de los recorridos con el agente de un
 * teléfono o un ordenador cualquiera. dispositivoDe (src/avisos.ts) sigue reconociendo el
 * dispositivo con el sufijo (tests/teselas.test.ts). Lo usan playwright.config.ts y las pruebas que
 * ponen su propio agente (e2e/avisos-sencillos.spec.ts).
 */
export const SUFIJO_AGENTE = " EODI-recorrido/1.0 (+https://droneobservatory.eu)";
