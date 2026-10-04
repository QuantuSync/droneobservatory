// Impactos con lugar de la capa de guerra: validación, resumen, periodo y puntos del mapa.

import { describe, expect, it } from "vitest";

import { filaImpacto, fuentesPorSentido, resumirUcrania } from "../src/datos/derivar.ts";
import { impactosDelPeriodo } from "../src/datos/ucrania.ts";
import { validarImpacto, validarPublicacionUcrania, validarResumenUcrania } from "../src/datos/validar.ts";
import { impactosEnMapa } from "../src/mapa/geometria.ts";
import { diaDeInstante } from "../src/tiempo/dias.ts";
import { ataque, focoTermico, fuente, impacto, publicacion } from "./ejemplos.ts";

describe("impactos con lugar", () => {
  it("validan con su fuente y la marca de autoridad de ocupación", () => {
    const conOcupacion = impacto({
      fuentes: [{ ...fuente({ fiabilidad: "C", credibilidad: 3 }), autoridad_ocupacion: true }],
    });
    expect(validarImpacto(conOcupacion).ok).toBe(true);
    expect(validarPublicacionUcrania({ ...publicacion([ataque()]), impactos: [conOcupacion] }).ok).toBe(
      true,
    );
  });

  it("no aceptan campos internos ni un identificador ajeno", () => {
    expect(validarImpacto({ ...impacto(), lecturas: [] }).ok).toBe(false);
    expect(validarImpacto(impacto({ id: "EODI-2026-00001" })).ok).toBe(false);
  });

  it("se resumen en una fila con día, sentido, punto, foco, parte, instalación y región", () => {
    const conFoco = impacto({ foco_termico: focoTermico() });
    expect(filaImpacto(conFoco)).toEqual([
      "EODI-IG-2026-00001", diaDeInstante("2026-09-29"), 1, 39.8, 54.59, 1, 1, 1, "RU-RYA",
    ]);
    // El día del ataque que nombra el mensaje manda sobre el de la publicación.
    expect(filaImpacto(impacto({ dia: "2026-09-26" }))[1]).toBe(diaDeInstante("2026-09-26"));
  });

  it("el periodo de la línea de tiempo los deja fuera o dentro", () => {
    const resumen = resumirUcrania({
      ...publicacion([ataque()]),
      impactos: [impacto(), impacto({ id: "EODI-IG-2026-00002", dia: "2026-09-01" })],
    });
    expect(validarResumenUcrania(resumen).ok).toBe(true);
    const dia = diaDeInstante("2026-09-29");
    expect(impactosDelPeriodo(resumen, { desde: dia, hasta: dia }).map((f) => f[0])).toEqual([
      "EODI-IG-2026-00001",
    ]);
    const todo = { desde: diaDeInstante("2025-01-01"), hasta: dia };
    expect(impactosDelPeriodo(resumen, todo)).toHaveLength(2);
    expect(impactosDelPeriodo(resumen, todo, "RU-RYA")).toHaveLength(2);
    expect(impactosDelPeriodo(resumen, todo, "UA-63")).toHaveLength(0);
  });

  it("los partes diarios del frente no se dibujan", () => {
    const resumen = resumirUcrania({
      ...publicacion([ataque()]),
      impactos: [impacto(), impacto({ id: "EODI-IG-2026-00002", dia: "2026-09-28", parte_diario: true })],
    });
    expect(resumen.impactos.map((f) => f[0])).toEqual(["EODI-IG-2026-00001"]);
  });

  it("la fuente de cada sentido lleva su puntuación y la marca de reivindicación", () => {
    const ruso = ataque({
      id: "EODI-UA-2026-1020",
      sentido: "UA_RU",
      reivindicacion_de_parte: true,
      fuentes: [fuente({ medio: "Минобороны России", fiabilidad: "D", credibilidad: 3 })],
    });
    const fuentes = fuentesPorSentido(publicacion([ataque(), ruso]));
    expect(fuentes.UA_RU).toEqual({
      medio: "Минобороны России",
      fiabilidad: "D",
      credibilidad: 3,
      reivindicacion: true,
    });
  });

  it("son puntos del mapa con las banderas que suma la agrupación", () => {
    const coleccion = impactosEnMapa([filaImpacto(impacto({ foco_termico: focoTermico() }))]);
    expect(coleccion.features[0]?.geometry.coordinates).toEqual([39.8, 54.59]);
    expect(coleccion.features[0]?.properties).toEqual({
      id: "EODI-IG-2026-00001",
      sentido: 1,
      foco: 1,
      parte: 1,
      satelite: 0,
    });
    // Con información de satélite, el grupo que lo contiene lo señala.
    const conSatelite = impactosEnMapa([filaImpacto(impacto())], new Set(["EODI-IG-2026-00001"]));
    expect(conSatelite.features[0]?.properties.satelite).toBe(1);
  });
});

describe("día y parte diario del impacto", () => {
  it("el día tiene que ser una fecha y el parte diario una marca", () => {
    expect(validarImpacto(impacto({ dia: "2026-09-26", parte_diario: true })).ok).toBe(true);
    expect(validarImpacto(impacto({ dia: "26/09/2026" })).ok).toBe(false);
  });
});
