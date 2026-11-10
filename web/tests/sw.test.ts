// El service worker de la app (public/sw.js): reglas de caché, respaldo sin conexión, aviso de
// versión nueva, lista de lo que se guarda, límites y borrado. Se carga el fichero tal cual en un
// contexto aparte (node:vm), con una caché y una red de mentira.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

import { describe, expect, it } from "vitest";

const ORIGEN = "https://droneobservatory.eu";

interface PeticionSw {
  url: string;
  method?: string;
  mode?: string;
  headers?: Headers;
  cache?: string;
}

type Regla = "pagina" | "huella" | "datos" | "estatico" | null;

interface Manejador {
  responder(peticion: PeticionSw, esperar?: (p: Promise<unknown>) => void, cliente?: string | null): Promise<Response> | null;
  guardarLista(direcciones: string[]): Promise<number>;
  limpiarViejas(): Promise<void>;
  borrarTodo(): Promise<void>;
}

interface ApiSw {
  reglaDe(peticion: PeticionSw, origen: string): Regla;
  portadaDe(ruta: string): string;
  claveDe(url: string): string;
  codigoDe(html: string): string;
  crearManejador(entorno: {
    cajas: CajasFalsas;
    pedir: (peticion: PeticionSw | Request) => Promise<Response>;
    origen: string;
    avisar: (cliente: string | null, mensaje: unknown) => Promise<void>;
    esperaMs?: number;
  }): Manejador;
  CACHES_EN_USO: string[];
  PREFIJO: string;
}

function cargarSw(): ApiSw {
  const codigo = readFileSync(join(import.meta.dirname, "..", "public", "sw.js"), "utf8");
  const contexto: { self: { eodiSw?: ApiSw }; URL: typeof URL; Request: typeof Request; setTimeout: typeof setTimeout } = {
    self: {},
    URL,
    Request,
    setTimeout,
  };
  runInNewContext(codigo, contexto);
  if (contexto.self.eodiSw === undefined) throw new Error("sw.js no expone sus reglas");
  return contexto.self.eodiSw;
}

/** Una Cache Storage en memoria, con el orden de inserción de la de verdad. */
class CajaFalsa {
  entradas = new Map<string, Response>();
  async match(clave: string | Request, opciones?: { ignoreSearch?: boolean }): Promise<Response | undefined> {
    let url = typeof clave === "string" ? clave : clave.url;
    if (opciones?.ignoreSearch === true) url = url.split("?")[0] ?? url;
    const r = this.entradas.get(url);
    return r?.clone();
  }
  async put(clave: string, respuesta: Response): Promise<void> {
    this.entradas.set(clave, respuesta);
  }
  async delete(clave: string | { url: string }): Promise<boolean> {
    return this.entradas.delete(typeof clave === "string" ? clave : clave.url);
  }
  async keys(): Promise<{ url: string }[]> {
    return [...this.entradas.keys()].map((url) => ({ url }));
  }
}

class CajasFalsas {
  cajas = new Map<string, CajaFalsa>();
  async open(nombre: string): Promise<CajaFalsa> {
    let caja = this.cajas.get(nombre);
    if (caja === undefined) {
      caja = new CajaFalsa();
      this.cajas.set(nombre, caja);
    }
    return caja;
  }
  async keys(): Promise<string[]> {
    return [...this.cajas.keys()];
  }
  async delete(nombre: string): Promise<boolean> {
    return this.cajas.delete(nombre);
  }
}

/** Una respuesta de la propia web («basic», como las del mismo origen). */
function respuesta(cuerpo: string, status = 200): Response {
  const r = new Response(cuerpo, { status });
  Object.defineProperty(r, "type", { value: "basic" });
  return r;
}

const sw = cargarSw();

function preparar(red: (url: string) => Promise<Response>, esperaMs = 50) {
  const cajas = new CajasFalsas();
  const pedidas: string[] = [];
  const avisos: unknown[] = [];
  const manejador = sw.crearManejador({
    cajas,
    origen: ORIGEN,
    esperaMs,
    pedir: (peticion) => {
      pedidas.push(peticion.url);
      return red(peticion.url);
    },
    avisar: async (_cliente, mensaje) => {
      avisos.push(mensaje);
    },
  });
  const pendientes: Promise<unknown>[] = [];
  const responder = (url: string, mode = "cors") =>
    manejador.responder({ url: `${ORIGEN}${url}`, method: "GET", mode, headers: new Headers() }, (p) => pendientes.push(p), "c1");
  return { cajas, pedidas, avisos, manejador, responder, pendientes };
}

const sinRed = () => Promise.reject(new TypeError("Failed to fetch"));

describe("reglas de caché", () => {
  const regla = (url: string, extra: Partial<PeticionSw> = {}) =>
    sw.reglaDe({ url, method: "GET", mode: "cors", headers: new Headers(), ...extra }, ORIGEN);

  it("el código con huella, primero de la caché; HTML y datos, primero de la red", () => {
    expect(regla(`${ORIGEN}/assets/index-AbC123.js`)).toBe("huella");
    expect(regla(`${ORIGEN}/`, { mode: "navigate" })).toBe("pagina");
    expect(regla(`${ORIGEN}/en/EODI-2025-00001`, { mode: "navigate" })).toBe("pagina");
    expect(regla(`${ORIGEN}/datos/resumen.json`)).toBe("datos");
    expect(regla(`${ORIGEN}/datos/incidentes/EODI-2025-00001.json`)).toBe("datos");
    expect(regla(`${ORIGEN}/arranque.js`)).toBe("datos");
    expect(regla(`${ORIGEN}/mapa/tierra.geojson`)).toBe("estatico");
    expect(regla(`${ORIGEN}/mapa/fuentes/Noto/0-255.pbf`)).toBe("estatico");
    expect(regla(`${ORIGEN}/apple-touch-icon.png`)).toBe("estatico");
  });

  it("una navegación a un fichero (una descarga, el mapa del sitio, una imagen) no es una página", () => {
    for (const ruta of [
      "/datos/incidentes.csv",
      "/datos/incidentes.geojson",
      "/sitemap.xml",
      "/llms.txt",
      "/robots.txt",
      "/compartir.png",
      "/compartir/EODI-2026-00719.png",
      "/avisos/qr/eodi.svg",
    ]) {
      expect(regla(`${ORIGEN}${ruta}`, { mode: "navigate" }), ruta).toBeNull();
    }
    // Las páginas, con o sin .html, siguen siéndolo.
    for (const ruta of ["/", "/en", "/EODI-2026-00719", "/paises/de", "/en/methodology", "/404.html"]) {
      expect(regla(`${ORIGEN}${ruta}`, { mode: "navigate" }), ruta).toBe("pagina");
    }
    // Y lo mismo, pedido por la página, sigue guardándose como dato o como estático.
    expect(regla(`${ORIGEN}/datos/incidentes.geojson`)).toBe("datos");
    expect(regla(`${ORIGEN}/avisos/qr/eodi.svg`)).toBe("estatico");
  });

  it("nunca el mapa de fondo, /api/, las versiones, otros sitios, Range ni lo que no es GET", () => {
    expect(regla(`${ORIGEN}/almacen/europa-z14.pmtiles`)).toBeNull();
    expect(regla(`${ORIGEN}/almacen/estado.json`)).toBeNull();
    expect(regla(`${ORIGEN}/api/borde?id=EODI-1`)).toBeNull();
    expect(regla(`${ORIGEN}/datos/versiones/2026-10/incidentes.csv`)).toBeNull();
    expect(regla("https://stats.droneobservatory.eu/count?p=/")).toBeNull();
    expect(regla("https://droneobservatory-reserva.hel1.your-objectstorage.com/estado.json")).toBeNull();
    expect(regla(`${ORIGEN}/datos/resumen.json`, { headers: new Headers({ range: "bytes=0-10" }) })).toBeNull();
    expect(regla(`${ORIGEN}/datos/resumen.json`, { method: "POST" })).toBeNull();
    expect(regla(`${ORIGEN}/sw.js`)).toBeNull();
    expect(regla(`${ORIGEN}/rutas.json`)).toBeNull();
    // Los manifiestos los pide el navegador por su cuenta: Safari los corta al dejar la página.
    expect(regla(`${ORIGEN}/manifest.webmanifest`)).toBeNull();
    expect(regla(`${ORIGEN}/manifest-en.webmanifest`)).toBeNull();
  });

  it("la portada de cada idioma y la clave sin búsqueda", () => {
    expect(sw.portadaDe("/en/EODI-2025-00001")).toBe("/en");
    expect(sw.portadaDe("/en")).toBe("/en");
    expect(sw.portadaDe("/EODI-2025-00001")).toBe("/");
    expect(sw.portadaDe("/entorno")).toBe("/");
    expect(sw.claveDe(`${ORIGEN}/?pais=PL#x`)).toBe(`${ORIGEN}/`);
  });
});

describe("respuestas", () => {
  it("lo que no se toca va a la red sin el service worker", () => {
    const { responder } = preparar(sinRed);
    expect(responder("/almacen/europa-z14.pmtiles")).toBeNull();
    expect(responder("/api/lector")).toBeNull();
  });

  it("el código con huella se pide una vez y después sale de la caché, también sin red", async () => {
    let red: (url: string) => Promise<Response> = () => Promise.resolve(respuesta("codigo"));
    const { responder, pedidas } = preparar((url) => red(url));
    expect(await (await responder("/assets/a-1.js"))?.text()).toBe("codigo");
    red = sinRed;
    expect(await (await responder("/assets/a-1.js"))?.text()).toBe("codigo");
    expect(pedidas).toHaveLength(1);
  });

  it("los datos, de la red; sin red o con un 5xx, la última copia; un 404 pasa tal cual", async () => {
    let red: (url: string) => Promise<Response> = () => Promise.resolve(respuesta('{"v":1}'));
    const { responder } = preparar((url) => red(url));
    expect(await (await responder("/datos/resumen.json"))?.text()).toBe('{"v":1}');
    red = () => Promise.resolve(respuesta('{"v":2}'));
    expect(await (await responder("/datos/resumen.json"))?.text()).toBe('{"v":2}');
    red = sinRed;
    expect(await (await responder("/datos/resumen.json"))?.text()).toBe('{"v":2}');
    red = () => Promise.resolve(respuesta("caido", 503));
    expect(await (await responder("/datos/resumen.json"))?.text()).toBe('{"v":2}');
    red = () => Promise.resolve(respuesta("no", 404));
    expect((await responder("/datos/resumen.json"))?.status).toBe(404);
    red = sinRed;
    await expect(responder("/datos/incidentes/EODI-nunca-vista.json")).rejects.toThrow();
  });

  it("una ficha visitada se abre sin conexión; una no visitada, con la portada de su idioma", async () => {
    let red: (url: string) => Promise<Response> = (url) => Promise.resolve(respuesta(`html ${new URL(url).pathname}`));
    const { responder } = preparar((url) => red(url));
    await responder("/en", "navigate");
    await responder("/en/EODI-2025-00001", "navigate");
    red = sinRed;
    expect(await (await responder("/en/EODI-2025-00001", "navigate"))?.text()).toBe("html /en/EODI-2025-00001");
    expect(await (await responder("/en/EODI-2025-00002", "navigate"))?.text()).toBe("html /en");
    await expect(responder("/EODI-2025-00002", "navigate")).rejects.toThrow();
  });

  it("una página lenta sale de la copia y avisa si la nueva trae otro código", async () => {
    let red: (url: string) => Promise<Response> = () =>
      Promise.resolve(respuesta('<script src="/assets/index-viejo.js"></script>'));
    const { responder, avisos, pendientes, cajas } = preparar((url) => red(url), 20);
    await responder("/", "navigate");
    red = () =>
      new Promise((hecho) => setTimeout(() => hecho(respuesta('<script src="/assets/index-nuevo.js"></script>')), 80));
    const servida = await responder("/", "navigate");
    expect(await servida?.text()).toContain("index-viejo");
    await Promise.all(pendientes);
    expect(avisos).toEqual([{ tipo: "version-nueva" }]);
    const guardada = await (await cajas.open("eodi-paginas-v1")).match(`${ORIGEN}/`);
    expect(await guardada?.text()).toContain("index-nuevo");
  });

  it("sin aviso si la página nueva trae el mismo código (solo datos nuevos)", async () => {
    let red: (url: string) => Promise<Response> = () => Promise.resolve(respuesta('<script src="/assets/a.js"></script> 12:17'));
    const { responder, avisos, pendientes } = preparar((url) => red(url), 20);
    await responder("/", "navigate");
    red = () => new Promise((hecho) => setTimeout(() => hecho(respuesta('<script src="/assets/a.js"></script> 13:17')), 60));
    await responder("/", "navigate");
    await Promise.all(pendientes);
    expect(avisos).toEqual([]);
  });

  it("el código de un HTML: los ficheros con huella que nombra", () => {
    expect(sw.codigoDe('<link href="/assets/b.css"><script src="/assets/a.js"></script><script src="/assets/a.js">')).toBe(
      "/assets/a.js /assets/b.css",
    );
  });
});

describe("peticiones aparte (Safari corta las de la página que se va)", () => {
  it("el código, los datos y lo estático se piden con una petición nueva, sin la señal de la página", async () => {
    const vistas: (PeticionSw | Request)[] = [];
    const manejador = sw.crearManejador({
      cajas: new CajasFalsas(),
      origen: ORIGEN,
      pedir: (p) => {
        vistas.push(p);
        return Promise.resolve(respuesta("x"));
      },
      avisar: async () => undefined,
    });
    const corte = new AbortController();
    corte.abort();
    for (const ruta of ["/assets/a-1.js", "/datos/resumen.json", "/mapa/tierra.geojson"]) {
      const peticion = new Request(`${ORIGEN}${ruta}`, { signal: corte.signal });
      expect(await (await manejador.responder(peticion))?.text()).toBe("x");
    }
    expect(vistas).toHaveLength(3);
    for (const vista of vistas) {
      expect(vista).toBeInstanceOf(Request);
      expect((vista as Request).signal.aborted).toBe(false);
      expect((vista as Request).credentials).toBe("same-origin");
    }
  });
});

describe("los reintentos sin caché llegan a la red sin caché", () => {
  it("la petición aparte conserva «no-cache» y «reload»; lo demás va con la caché del navegador", async () => {
    const vistas: Request[] = [];
    const manejador = sw.crearManejador({
      cajas: new CajasFalsas(),
      origen: ORIGEN,
      pedir: (p) => {
        vistas.push(p as Request);
        return Promise.resolve(respuesta("x"));
      },
      avisar: async () => undefined,
    });
    await manejador.responder(new Request(`${ORIGEN}/datos/resumen.json`, { cache: "no-cache" }));
    await manejador.responder(new Request(`${ORIGEN}/assets/a-2.js`, { cache: "reload" }));
    await manejador.responder(new Request(`${ORIGEN}/datos/estado.json`));
    await manejador.responder(new Request(`${ORIGEN}/mapa/tierra.geojson`, { cache: "force-cache" }));
    expect(vistas.map((v) => v.cache)).toEqual(["no-cache", "reload", "default", "default"]);
  });
});

describe("guardar lo descargado, límites y borrado", () => {
  it("guarda desde la caché HTTP lo que la página ya ha descargado, sin /almacen/ ni otros sitios", async () => {
    const vistas: { url: string; cache?: string }[] = [];
    const cajas = new CajasFalsas();
    const manejador = sw.crearManejador({
      cajas,
      origen: ORIGEN,
      pedir: (p) => {
        vistas.push({ url: p.url, cache: (p as Request).cache });
        return Promise.resolve(respuesta("x"));
      },
      avisar: async () => undefined,
    });
    const n = await manejador.guardarLista([
      "/#pagina",
      "/assets/index-1.js",
      "/datos/resumen.json",
      "/mapa/paises.geojson",
      "/almacen/europa-z14.pmtiles",
      "https://stats.droneobservatory.eu/count",
      "/api/lector",
    ]);
    expect(n).toBe(4);
    expect(vistas.every((v) => v.cache === "force-cache")).toBe(true);
    expect(vistas.map((v) => new URL(v.url).pathname)).toEqual(["/", "/assets/index-1.js", "/datos/resumen.json", "/mapa/paises.geojson"]);
    // Lo ya guardado no se vuelve a pedir.
    expect(await manejador.guardarLista(["/assets/index-1.js"])).toBe(0);
  });

  it("cada caché tiene un tope: se van las entradas más antiguas", async () => {
    const { responder, cajas } = preparar(() => Promise.resolve(respuesta("p")));
    for (let i = 0; i < 45; i += 1) await responder(`/EODI-2025-${String(i).padStart(5, "0")}`, "navigate");
    const claves = await (await cajas.open("eodi-paginas-v1")).keys();
    expect(claves).toHaveLength(40);
    expect(claves[0]?.url).toBe(`${ORIGEN}/EODI-2025-00005`);
  });

  it("al activarse borra las cachés de versiones anteriores; «borrar» las borra todas", async () => {
    const { manejador, cajas } = preparar(sinRed);
    await cajas.open("eodi-paginas-v0");
    await cajas.open("otra-cosa");
    for (const nombre of sw.CACHES_EN_USO) await cajas.open(nombre);
    await manejador.limpiarViejas();
    expect((await cajas.keys()).sort()).toEqual([...sw.CACHES_EN_USO, "otra-cosa"].sort());
    await manejador.borrarTodo();
    expect(await cajas.keys()).toEqual(["otra-cosa"]);
  });
});

describe("borrar mi última visita", () => {
  it("public/borrar-visita.js borra también las cachés de la app", () => {
    const codigo = readFileSync(join(import.meta.dirname, "..", "public", "borrar-visita.js"), "utf8");
    expect(codigo).toContain("caches.keys()");
    expect(codigo).toContain('startsWith("eodi-")');
    expect(sw.PREFIJO).toBe("eodi-");
  });
});
