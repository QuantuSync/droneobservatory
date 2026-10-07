import { rutasEs } from "./rutas.ts";
import { tipoDronEs } from "./tipoDron.ts";
import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN, REPOSITORIO } from "../sitio.ts";
import { REGIONES_RUSIA_ES } from "./regionesRusia.ts";
import type { FechaEscrita, Textos } from "./tipos.ts";
import { UMBRALES_DIRECTO } from "./umbrales.ts";

const MESES = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
] as const;

function diaMesAnio(f: FechaEscrita): string {
  return `${f.dia} de ${MESES[f.mes]} de ${f.anio}`;
}

export const es: Textos = {
  tipoDron: tipoDronEs,
  rutas: rutasEs,
  descripcion:
    "Mapa y registro abierto de incidentes con drones en Europa: sobrevuelos, incursiones e " +
    "interrupciones de aeropuertos, con sus fuentes, su estado y su grado de confirmación.",
  saltarAlMapa: "Saltar al mapa",
  marcador: {
    etiqueta: "Cifras del periodo elegido",
    incidentes: "incidentes",
    confirmados: "confirmados",
    atribuidos: "atribuidos",
    paises: "países",
  },
  firma: { metodologia: "Metodología y datos abiertos", atribuciones: "Atribuciones del mapa" },
  cabecera: { etiqueta: "Cabecera", menu: "Menú", cerrarMenu: "Cerrar el menú" },
  hoja: {
    altura: (altura) => `Hoja ${altura}: pulsa o arrastra para cambiar su altura`,
    alturas: { asomada: "asomada", media: "a media altura", completa: "a pantalla completa" },
  },
  controles: {
    capas: "Capas",
    incidentes: "Incidentes",
    ucrania: "Ucrania",
    densidad: "Densidad",
    presion: "Presión",
    gnss: "GPS",
    feed: "En directo",
    ayuda: "Ayuda",
    cambiarIdioma: "English version",
    idioma: "Idioma",
    zoom: "Zoom",
    paneles: "Más",
    acercar: "Acercar",
    alejar: "Alejar",
  },
  estadoDatos: {
    actualizado: "Actualizado",
    etiqueta: {
      al_dia: "datos al día",
      con_retraso: "datos con retraso",
      desactualizado: "datos desactualizados",
    },
    sinDatos: "Sin datos",
    detalle: "Estado de la recogida",
    datosPublicados: "Datos publicados",
    ultimaRecogida: "Última recogida",
    resultadoRotulo: "Resultado",
    siguienteRecogida: "Siguiente recogida",
    fuentes: "Fuentes",
    resultado: { correcta: "correcta", con_avisos: "con avisos", fallida: "fallida" },
    fuente: {
      fuerza_aerea_ua: "Fuerza Aérea de Ucrania",
      mindef_ru: "Ministerio de Defensa ruso",
      gdelt: "Noticias (GDELT)",
      oficiales: "Notas oficiales",
      extractor: "Extracción automática",
      firms: "Focos térmicos (NASA FIRMS)",
      airprox: "Encuentros con aeronaves (UK Airprox Board)",
      parlamentos: "Respuestas parlamentarias",
      investigaciones: "Informes de investigación y sentencias",
      estadisticas_oficiales: "Estadísticas oficiales",
      paginas_js: "Notas oficiales (webs con JavaScript)",
      ova_ua: "Administraciones regionales de Ucrania",
      estado_mayor_ua: "Estado Mayor ucraniano",
      gobernadores_ru: "Gobernadores rusos",
      rosaviatsia: "Rosaviatsia",
      trafico_aereo: "Tráfico aéreo (adsb.lol)",
      condiciones: "Meteorología (Open-Meteo, METAR)",
    },
    estadoFuente: { leida: "leída", con_aviso: "con aviso", no_leida: "no leída" },
    directo: "Detección en directo",
    estadoDirecto: { en_marcha: "en marcha", con_respaldo: "con la fuente de respaldo", parado: "parada" },
    ultimoCiclo: "último ciclo correcto",
    ultimoDato: "último dato",
    sinUltimoDato: "sin datos todavía",
    nuncaCorrecta: "Ninguna recogida correcta",
    siguienteEn: (minutos) => (minutos <= 0 ? "en curso" : `dentro de ${minutos} min`),
  },
  avisos: {
    cargando: "Cargando los datos…",
    datosNoValidos:
      "Los datos publicados no cumplen el esquema y no se muestran. Se volverán a mostrar " +
      "cuando la próxima actualización los corrija.",
    datosNoDisponibles: "No se han podido cargar los datos. Vuelve a intentarlo más tarde.",
    fichaNoEncontrada: "No hay ningún registro con este identificador.",
    fichaNoValida: "Esta ficha no cumple el esquema y no se muestra.",
    mapaNoDisponible:
      "El mapa no se puede dibujar en este navegador. La lista de incidentes sigue disponible.",
  },
  filtros: {
    titulo: "Filtros",
    graves: "Solo confirmados y atribuidos",
    ultimas24h: "Últimas 24 horas",
    ultimos7d: "Últimos 7 días",
    periodos: {
      todo: "Todo",
      "24h": "Últimas 24 horas",
      "7d": "Últimos 7 días",
      "30d": "Últimos 30 días",
      "1a": "Último año",
      entre: "Entre fechas",
    },
    desde: "Desde",
    hasta: "Hasta",
    entreFechas: (desde, hasta) => `${desde} – ${hasta}`,
    abrir: "Abrir los filtros",
    cerrar: "Cerrar los filtros",
    volverATodo: (periodo) => `Quitar el periodo «${periodo}» y ver todo`,
    tipo: "Tipo",
    pais: "País",
    todosLosPaises: "Todos los países",
    estado: "Estado",
    quitar: "Quitar filtros",
    recientes: "Periodo",
    activos: (n) => (n === 1 ? "1 activo" : `${n} activos`),
    zona: "Dónde",
    zonas: { todas: "Todos", frontera: "Frontera", interior: "Interior" },
  },
  feed: {
    titulo: "En directo",
    enDirecto: "Novedades",
    lista: "Lista",
    abrir: "Abrir el panel en directo",
    cerrar: "Cerrar el panel",
    nuevo: "Nuevo incidente",
    nuevoYa: (estado) => `Nuevo, ya ${estado.toLowerCase()}`,
    paso: (estado) => `Pasa a ${estado.toLowerCase()}`,
    vacio: "Nada que mostrar con estos filtros.",
  },
  relativo: (minutos, fecha) => {
    if (minutos < 1) return "ahora mismo";
    if (minutos < 60) return `hace ${minutos} min`;
    const horas = Math.floor(minutos / 60);
    if (horas < 24) return `hace ${horas} h`;
    const dias = Math.floor(horas / 24);
    return dias < 30 ? `hace ${dias} ${dias === 1 ? "día" : "días"}` : `el ${fecha}`;
  },
  ahora: {
    etiqueta: "Europa ahora",
    cierres: "cierres de aeropuerto en curso",
    incidentes: "incidentes en 7 días",
    drones: "drones lanzados la última noche",
    dronesDia: "drones lanzados en el último parte de día",
    dronesParte: "drones lanzados",
    ultimoParte: (cuando) => `último parte: ${cuando}`,
    focos: "focos térmicos confirmados en 7 días",
    gnss: "zonas con interferencia GPS hoy",
    sinDato: "sin dato",
    ir: (que) => `Ver en el mapa: ${que}`,
    abrir: "Abrir «Europa ahora»",
    cerrar: "Cerrar «Europa ahora»",
    avisoCierres: (n) => (n === 1 ? "1 cierre en curso" : `${n} cierres en curso`),
    avisoNovedades: (n) => (n === 1 ? "1 novedad desde tu última visita" : `${n} novedades desde tu última visita`),
  },
  desplegable: {
    escape: "Se cierra con Escape.",
  },
  directo: {
    etiqueta: "Aeropuerto · detección en directo",
    estado: {
      posible_cierre: "Posible cierre en curso",
      cierre_confirmado: "Cierre confirmado",
      operacion_reanudada: "Operación reanudada",
    },
    detectado: "Detectado",
    inicio: "Inicio del hueco",
    reanudado: "Reanudado",
    evidencia: "Evidencia",
    movimientos: (vistos, esperados) => `${vistos} movimientos vistos de ${esperados} esperados`,
    llegadasPerdidas: (n) => `${n} llegadas perdidas`,
    salidasPerdidas: (n) => `${n} salidas perdidas`,
    esperas: (n) => `${n} aviones en espera`,
    desvios: (n) => `${n} vuelos desviados`,
    confirmacion: "Confirmación",
    confirmacionTipo: { incidente: "incidente de la base", oficial: "fuente oficial" },
    primeraNoticia: "Primera noticia",
    ventaja: (minutos) =>
      minutos >= 0
        ? `detectado ${minutos} min antes de la primera noticia`
        : `detectado ${-minutos} min después de la primera noticia`,
    actualizado: "Actualizado",
    fuente: "Tráfico en tiempo real",
    fuentes: { adsb_lol: "adsb.lol", adsb_fi: "adsb.fi" },
    vigilados: (n) => `${n} aeropuertos vigilados`,
  },
  gnss: {
    etiqueta: "Interferencia GPS",
    leyenda: "Aeronaves con la posición degradada",
    niveles: { sin: "menos del 2 %", media: "del 2 al 10 %", alta: "más del 10 %" },
    proporcion: "Aeronaves afectadas",
    aeronaves: "Aeronaves",
    degradadas: "con la posición degradada",
    periodo: "Periodo",
    dias: (n) => (n === 1 ? "1 día con datos" : `${n} días con datos`),
    zonasAltas: (n) => (n === 1 ? "1 zona con interferencia alta" : `${n} zonas con interferencia alta`),
    sinDatos: "Sin datos de interferencia para este periodo",
    cargando: "Cargando la interferencia…",
    letrero: (proporcion) => `Interferencia GPS · ${proporcion} de las aeronaves`,
  },
  prevision: {
    etiqueta: "Previsión",
    cerrar: "Cerrar la previsión",
    cargando: "Cargando la previsión…",
    noDisponible: "La previsión no está disponible ahora.",
    deCada10: (n, porcentaje) => `${n} de cada 10 noches como esta (${porcentaje} %)`,
    calculada: (cuando) => `Calculada el ${cuando}.`,
    frontera: {
      titulo: "Esta noche en la frontera",
      noche: (desde, hasta) => `Noche del ${desde} al ${hasta}: que un dron de la guerra cruce o caiga en el país`,
      ninguno: "Hoy ningún país tiene una previsión comprobada.",
      habitual: (porcentaje) => `Lo habitual en este país: ${porcentaje} de cada 100 noches.`,
      dependeDe: "De qué depende hoy:",
      lanzados: (media, anoche) =>
        `drones lanzados contra Ucrania: ${media} de media en las tres últimas noches (anoche, ${anoche})`,
      crimea: (noches) => `noches con drones salidos de Crimea, el camino del sur: ${noches} de las últimas 7`,
      incidentes: (n, pais) => `incidentes de frontera en ${pais} en los últimos 7 días: ${n}`,
      efectos: { sube: "sube el riesgo", baja: "lo baja", nada: "no lo cambia" },
      historial: (noches, desde, conDron, enAlto, mejora) =>
        `Comprobado con ${noches} noches desde el ${desde}, cada una solo con lo anterior: de las ${conDron} noches con dron, ${enAlto} estaban entre la cuarta parte de noches con más riesgo. Acierta un ${mejora} % más que la frecuencia de siempre.`,
      verHistorial: "Historial de aciertos",
      columnaDijo: "Cuando dijo",
      columnaNoches: "Noches",
      columnaConDron: "Con dron",
      tramo: (desde, hasta) => `del ${desde} al ${hasta} %`,
      ultimas: "Últimas noches (previsión reconstruida y si hubo dron):",
      conDron: "dron",
      enVivo: (puntuadas, conDron) =>
        `Previsiones hechas en vivo ya puntuadas: ${puntuadas} noches, con dron en ${conDron}.`,
    },
    segundaNoche: {
      titulo: "Segunda noche",
      aviso: (lanzados, probabilidad) =>
        `Anoche fue una oleada grande (${lanzados} drones). Que esta noche también lo sea: ${probabilidad}.`,
    },
    rachas: {
      titulo: "Rachas por país",
      ninguna: "Ningún país está ahora por encima de lo normal.",
      linea: (desde, n, habitual, veces, tendencia) =>
        `desde el ${desde}: ${n} incidentes frente a ${habitual} lo habitual (${veces} veces) · ${tendencia}`,
      tendencia: { crece: "crece", estable: "se mantiene", se_apaga: "se apaga" },
      ir: (pais) => `Ver ${pais} en el mapa con el periodo de la racha`,
      terminada: (pais, hasta) => `${pais} (hasta el ${hasta})`,
      terminadas: (lista) => `Han vuelto a lo normal: ${lista}.`,
      historial: (semanas, siguientes, normal) =>
        `Comprobado con ${semanas} semanas en racha desde julio de 2025: la semana siguiente tuvo ${siguientes} incidentes donde lo normal eran ${normal}. Cuenta sucesos, no noticias: cada incidente una vez, en la fecha del suceso.`,
      enFicha: "Racha",
    },
    grafica: {
      titulo: "Incidentes por semana y la banda de lo normal",
      resumen: (semanas, incidentes, normal) =>
        `${incidentes} incidentes en las últimas ${semanas} semanas; lo normal, ${normal} por semana.`,
      barra: (semana, n) => `Semana del ${semana}: ${n}`,
      banda: (minimo, maximo) => `Banda gris: lo normal, de ${minimo} a ${maximo} por semana (8 de cada 10 semanas).`,
    },
    cambios: {
      titulo: "Qué ha cambiado",
      periodo: (desde, hasta) => `De ${desde} a ${hasta}, frente a los doce meses anteriores. Lo que no ha cambiado no se lista.`,
      ambito: {
        ucrania_objetivo: "Ucrania, a qué se ataca (impactos con objetivo conocido, canales oficiales con datos todo el periodo)",
        europa_tipo: "Europa, tipo de incidente",
      },
      linea: (clase, reciente, habitual, casos, de, sentido) =>
        `${clase}: ${reciente} % (${casos} de ${de}), frente al ${habitual} % habitual · ${sentido}`,
      sentido: { sube: "sube", baja: "baja" },
      historial: (casos, sostenidos) =>
        `Comprobado desde septiembre de 2025: de ${casos} cambios marcados, el mes siguiente siguió igual en ${sostenidos}.`,
    },
    semana: {
      titulo: "La semana que viene",
      cual: (desde, hasta) => `Del ${desde} al ${hasta}, incidentes esperados`,
      provisional: "provisional: se fija el sábado",
      ninguno: "Ningún país tiene una previsión semanal comprobada.",
      fila: (esperado, minimo, maximo) => `${esperado} (entre ${minimo} y ${maximo}, 8 de cada 10 semanas)`,
      marcador: (dentro, total) => `Marcador: ${dentro} de ${total} semanas dentro del margen`,
      columnaSemana: "Semana",
      columnaPais: "País",
      columnaPrevisto: "Previsto",
      columnaReal: "Hubo",
      leyendaMarcador:
        "* reconstruida: calculada ahora solo con los datos de entonces. Las demás se hicieron en vivo y no se pueden retocar.",
    },
  },
  zona: {
    titulo: "Frontera o interior",
    grupo: { frontera: "Frontera", interior: "Interior" },
    motivo: (motivo, distancia) => {
      const km = distancia === null ? "" : `, a ${distancia} km de la frontera con Ucrania, Rusia o Bielorrusia`;
      switch (motivo) {
        case "ataque":
          return "enlazado con el ataque ruso contra Ucrania de esa noche";
        case "cerca_de_la_frontera":
          return `a 150 km o menos de la frontera con Ucrania, Rusia o Bielorrusia${km}`;
        case "costa_mar_negro":
          return `en la costa del mar Negro${km}`;
        case "lejos_de_la_frontera":
          return `a más de 150 km de la frontera con Ucrania, Rusia o Bielorrusia y lejos del mar Negro${km}`;
        case "incursion_en_pais_fronterizo":
          return "sin lugar conocido; el dron entró desde fuera en un país fronterizo";
        case "pais_dentro_de_la_banda":
          return "sin lugar conocido; todo el país está a 150 km o menos de la frontera";
        case "sin_lugar":
          return "sin lugar conocido ni relación con un ataque";
      }
    },
  },
  presion: {
    etiqueta: "País · presión",
    leyenda: {
      todo: "Incidentes desde el primer dato",
      reciente: {
        "24h": "Incidentes en las últimas 24 horas",
        "7d": "Incidentes en los últimos 7 días",
        "30d": "Incidentes en los últimos 30 días",
        "1a": "Incidentes en el último año",
      },
      entre: (intervalo) => `Incidentes ${intervalo}`,
    },
    menos: "menos",
    mas: "más",
    tendencia: { sube: "sube", baja: "baja", estable: "estable" },
    frente: (anterior) => `frente a ${anterior} en el periodo anterior de igual duración`,
    sinComparacion: "sin periodo anterior con datos",
    eligePeriodo: "Elige un periodo para ver la tendencia",
    incidentes: (n) => (n === 1 ? "1 incidente" : `${n} incidentes`),
    porTipo: "Por tipo",
    porEstado: "Por estado",
    lista: "Incidentes del periodo",
    vacia: "Ningún incidente en el periodo elegido.",
    letrero: (pais, n) => `${pais} · ${n === 1 ? "1 incidente" : `${n} incidentes`}`,
  },
  novedades: {
    aviso: (n) =>
      n === 1 ? "1 novedad desde tu última visita" : `${n} novedades desde tu última visita`,
    recorrer: "Verlas",
    siguiente: "Siguiente",
    anterior: "Anterior",
    descartar: "Descartar",
    posicion: (i, n) => `Novedad ${i} de ${n}`,
    recorrido: "Recorrer las novedades",
  },
  ayuda: {
    titulo: "Cómo leer el mapa",
    cerrar: "Cerrar la ayuda",
    colores:
      "Cada incidente es un círculo relleno del color de su estado: naranja, notificado; " +
      "rojo, confirmado. El desmentido es un círculo gris de borde discontinuo, sin relleno. " +
      "Un atribuido (un confirmado que una autoridad atribuye a un Estado o a una persona) es " +
      "un círculo algo mayor, con un aro rojo grueso y, dentro, la bandera del país al que se " +
      "atribuye; atribuido a una persona, lleva además un punto oscuro fijo en el centro. Va " +
      "siempre por encima de todo y no se agrupa con los círculos. El tipo de incidente va " +
      "escrito en la ficha, la lista y los filtros.",
    periodo:
      "El botón «Filtros» abre el periodo (todo, las últimas 24 horas, los últimos 7 o 30 " +
      "días, el último año o entre dos fechas) y los filtros de estado, tipo y país. Con un " +
      "periodo elegido, el botón lo lleva escrito y su equis vuelve a todo. El mapa, la lista, " +
      "las cifras, «En directo» y todas las capas muestran ese periodo. «Últimas 24 horas» " +
      "cuenta desde este momento: entra lo que empezó en las 24 horas anteriores y, si solo se " +
      "sabe el día, lo de hoy y ayer.",
    ahora:
      "«Europa ahora» abre las cifras del momento; cada una lleva al sitio del mapa que la " +
      "explica. En el botón, un número naranja cuenta los cierres de aeropuerto en curso y uno " +
      "blanco, las novedades desde tu visita anterior: dentro, «Verlas» las recorre una a una " +
      "y «Descartar» las quita.",
    areas:
      "Cada incidente ocupa un área: el círculo es el radio en que se sabe que ocurrió.",
    lineas: "Una línea fina une los incidentes de un mismo episodio: varios objetivos en una noche.",
    numeros:
      "Un círculo con un número dentro junta varios incidentes (el de un solo incidente va " +
      "relleno y sin número): crece con el número, y su anillo " +
      "es rojo si contiene algún confirmado y naranja si todos son notificados. Al acercar el " +
      "mapa se separan. Los nombres del mapa ceden ante los círculos: se ven enteros o no se " +
      "ven.",
    pila:
      "Si los incidentes están en el mismo punto exacto, al pulsar el círculo eliges cuál abrir.",
    pulsos:
      "Solo late lo nuevo desde tu última visita (y el círculo que lo contiene): deja de latir " +
      "al pulsar «Verlas» o «Descartar» o al abrir el incidente. Con el movimiento reducido " +
      "del sistema, en lugar de latir lleva un anillo fijo. Los notificados van más apagados.",
    reciente: "Un destello suave marca lo que empezó en las últimas 24 horas.",
    novedad: "En la primera visita no late nada: aún no hay una visita anterior con la que comparar.",
    ucrania:
      "En la capa de Ucrania, cada región se colorea de violeta según los ataques que la citan " +
      "en el periodo: es el color de toda la capa de guerra, distinto del rojo y el naranja de " +
      "los incidentes.",
    rusia:
      "Las regiones rusas van en violeta apagado y con contorno discontinuo: sus cifras son las del " +
      "Ministerio de Defensa ruso, una reivindicación de parte.",
    impactos:
      "Un punto violeta pequeño es un lugar concreto alcanzado (una localidad o una instalación; " +
      "si la fuente solo nombra la comunidad o el distrito, ese, con su radio) " +
      "según las administraciones regionales, el Estado Mayor ucraniano o los gobernadores " +
      "rusos. Relleno: fuente oficial; solo el aro: reivindicación de parte. Al alejar se " +
      "agrupan con su número. Los partes diarios de la línea del frente van en los datos " +
      "descargables.",
    foco:
      "Un punto claro junto a un incidente, un impacto o un grupo de impactos, o en el centro de una región de Ucrania, marca un " +
      "foco térmico detectado por satélite (NASA FIRMS) en su lugar y su hora: blanco en los " +
      "incidentes y violeta claro en la capa de guerra.",
    directo:
      "Una etiqueta con el código OACI dentro y una punta que señala el aeropuerto es un aviso " +
      "de la detección en directo, sin pulso. Su borde dice el estado: naranja, posible cierre " +
      "en curso; rojo, cierre confirmado; gris, operación reanudada. Va levantada sobre el " +
      "punto para no tapar el número de un grupo.",
    atajos: "Atajos de teclado",
    acciones: {
      ayuda: "Abrir o cerrar esta ayuda",
      cerrar: "Cerrar lo abierto: el desplegable, la ficha o el panel",
      capaIncidentes: "Capa de incidentes",
      capaUcrania: "Capa de Ucrania",
      capaDensidad: "Capa de densidad",
      capaSatelite: "Encender o apagar «Con satélite»",
      filtroGraves: "Solo confirmados y atribuidos",
      filtro24h: "Últimas 24 horas",
      filtro7d: "Últimos 7 días",
      sinFiltros: "Quitar los filtros",
      filtros: "Abrir o cerrar los filtros y el periodo",
      ahora: "Abrir o cerrar «Europa ahora»",
      feed: "Abrir o cerrar el panel en directo",
      lista: "Lista de incidentes",
      metodologia: "Metodología y datos abiertos",
    },
  },
  pila: { titulo: (n) => `${n} incidentes en este punto` },
  imprecisa: {
    etiqueta: "ubicación imprecisa",
    nivel: {
      instalacion: "instalación sin situar",
      localidad: "localidad sin situar",
      region: "solo la región",
      pais: "solo el país",
    },
  },
  guerra: {
    reproducir: "Noche a noche",
    pausar: "Pausar",
    reanudar: "Reanudar",
    detener: "Detener",
    drones: "drones lanzados contra Ucrania",
    sinCifra: "sin cifra de lanzamientos",
    mezcla: (shahed, reactivos) =>
      [shahed === null ? null : `Shahed y Geran: desde ${shahed}`, reactivos === null ? null : `a reacción: desde ${reactivos}`]
        .filter((parte) => parte !== null)
        .join(" · ") + " (según los partes)",
  },
  mapa: {
    etiqueta: "Mapa de Europa con los incidentes del periodo elegido",
    instrucciones:
      "Con el foco en el mapa, las flechas lo desplazan y las teclas más y menos cambian el " +
      "zoom. La lista de incidentes da acceso a las mismas fichas sin usar el mapa.",
    grupo: (n) => (n === 1 ? "1 incidente: acerca para verlo" : `${n} incidentes: acerca para verlos`),
    pila: (n) => `${n} incidentes en este mismo punto: pulsa para elegir uno`,
    atribuidos: (n) => `${n} incidentes atribuidos: acerca para separarlos`,
    grupoImpactos: (n) => `${n} impactos con lugar: acerca para verlos`,
    impacto: (parte, foco) =>
      `Impacto con lugar${parte ? " · reivindicación de parte" : ""}${foco ? " · foco térmico" : ""}`,
  },
  tipo: {
    interrupcion_aeroportuaria: "Interrupción aeroportuaria",
    incursion: "Incursión",
    sobrevuelo: "Sobrevuelo",
  },
  estado: {
    notificado: "Notificado",
    confirmado: "Confirmado",
    atribuido: "Atribuido",
    desmentido: "Desmentido",
  },
  atribucion: {
    aEstado: (pais) => `Atribuido a ${pais}`,
    aEstadoSinPais: "Atribuido a un Estado",
    aPersonaDe: (gentilicio) => `Atribuido a una persona de nacionalidad ${gentilicio}`,
    aPersonaDePais: (pais) => `Atribuido a una persona con nacionalidad de ${pais}`,
    aPersona: "Atribuido a una persona",
    unaPersona: "una persona",
    leyendaEstado: "Atribuido por una autoridad a un Estado",
    leyendaPersona: "Atribuido por una autoridad a una persona",
    bandera:
      "Dentro del aro rojo, la bandera del país al que la autoridad atribuye el incidente (el " +
      "Estado o la nacionalidad de la persona, si la autoridad la dice); no es una afirmación " +
      "del observatorio. Sin país, el aro va relleno de rojo. Una persona lleva además un punto " +
      "oscuro en el centro.",
  },
  presencia: {
    confirmada: "Dron confirmado",
    no_confirmada: "Dron no confirmado",
    descartada: "Dron descartado",
  },
  precision: {
    minuto: "hora exacta",
    hora: "hora aproximada",
    dia: "solo el día",
    aproximada: "fecha aproximada",
  },
  categoria: {
    aeropuerto: "Aeropuerto",
    base_militar: "Base militar",
    puerto: "Puerto",
    energia: "Energía",
    presa: "Presa",
    estadio: "Estadio",
    industrial: "Instalación industrial",
    gubernamental: "Sede gubernamental",
    otra: "Otro lugar",
  },
  categoriaUcrania: {
    energia: "energía",
    residencial: "zona residencial",
    ferrocarril: "ferrocarril",
    puerto: "puerto",
    industrial: "industria",
    otra: "otros",
  },
  categoriaGuerra: {
    energia: "energía",
    combustible: "combustible",
    residencial: "residencial",
    ferrocarril: "ferrocarril",
    puerto: "puerto",
    industrial: "industria",
    aerodromo: "aeródromo",
  },
  categoriaInstalacion: {
    refineria: "refinería",
    deposito_combustible: "depósito de combustible",
    central: "central eléctrica",
    subestacion: "subestación",
    aerodromo: "aeródromo",
    puerto: "puerto",
    militar: "instalación militar",
    ferrocarril: "estación ferroviaria",
    industrial: "planta industrial",
  },
  medida: {
    cierre_espacio_aereo: "cierre del espacio aéreo",
    patrulla: "patrulla",
    cazas: "despegue de cazas",
    derribo: "derribo",
    inhibicion: "inhibición",
    ninguna_conocida: "ninguna conocida",
  },
  sentido: {
    RU_UA: "De Rusia contra Ucrania",
    UA_RU: "De Ucrania contra Rusia",
  },
  ficha: {
    titulo: "Ficha",
    cerrar: "Cerrar la ficha",
    copiarEnlace: "Copiar enlace",
    enlaceCopiado: "Enlace copiado",
    enlaceNoCopiado: "No se ha podido copiar",
    estado: "Estado del suceso",
    presenciaDron: "Presencia de dron",
    fecha: "Fecha",
    lugar: "Lugar",
    lugarSegun: "Lugar según",
    otrosLugares: "Otros lugares",
    puntoAnterior: "Punto anterior",
    radio: (km) => `área de ${km} km de radio`,
    drones: "Drones",
    duracion: "Duración",
    efecto: "Efecto",
    respuesta: "Respuesta",
    atribucion: "Atribución",
    parteDelAtaque: "Parte del ataque",
    ataqueDeLa: (jornada) => `Parte del ataque ruso contra Ucrania de la ${jornada}`,
    porFuente: "la fuente lo relaciona con el ataque",
    porFecha: "coincide en fecha y viene de Ucrania",
    confirmadoAtribuido: (actor, autoridad) => `Confirmado · atribuido a ${actor}, según ${autoridad}`,
    atribuidoA: (actor, autoridad) => `${actor}, según ${autoridad}`,
    investigacion: "Investigación en curso",
    investiga: (autoridad) => `Lo que investiga ${autoridad} (no cambia el estado del incidente):`,
    verFuente: "ver la fuente",
    // «de el prefecto» se contrae: «del prefecto».
    declaracionCitada: (autoridad, medio) =>
      `Declaración ${autoridad.startsWith("el ") ? `del ${autoridad.slice(3)}` : `de ${autoridad}`}, citada en ${medio}`,
    motivoDesmentido: "Motivo del desmentido",
    desconocido: "Sin dato",
    minutos: (n) => `${n} min`,
    rangoDeFuentes: "rango de las fuentes A–C",
    queDiceCadaFuente: (n) => (n === 1 ? "Qué dice la fuente" : `Qué dice cada fuente (${n})`),
    valorSegun: "según",
    cierreDe: (minutos) => `Cierre de ${minutos} min`,
    cierreSinDuracion: "Cierre, sin duración conocida",
    sinCierre: "Sin cierre",
    cierreDesconocido: "Cierre: desconocido",
    vuelosDesviados: "vuelos desviados",
    vuelosCancelados: "vuelos cancelados",
    vuelosRetrasados: "vuelos retrasados",
    heridos: "heridos",
    fallecidos: "fallecidos",
    danos: {
      ninguno: "Sin daños",
      menores: "Daños menores",
      graves: "Daños graves",
      desconocido: "Daños sin confirmar",
    },
    modelo: "Modelo",
    episodio: "Episodio",
    fuentes: (n) => (n === 1 ? "1 fuente" : `${n} fuentes`),
    masFuentes: (n) => `Ver ${n} más`,
    menosFuentes: "Ver menos",
    replicas: (n) => (n === 1 ? "1 réplica" : `${n} réplicas`),
    codigo: (codigo) => `Código del Almirantazgo ${codigo}`,
    declaracionOficial: "Declaración oficial citada",
    enlaceExterno: "enlace externo, se abre en otra pestaña",
    enlaceNoValido: "enlace no válido",
    historial: "Historial de estados",
    fuenteNoPublica: "fuente no pública",
    actualizada: "Ficha actualizada",
  },
  ataque: {
    etiqueta: "Ataque · capa de Ucrania",
    reivindicacion:
      "Cifras de una de las partes en guerra, sin otra fuente que las confirme.",
    periodo: "Periodo",
    lanzados: "Drones lanzados",
    reactivos: "De ellos, a reacción",
    shahed: "Shahed / Geran",
    senuelos: "Gerbera y señuelos",
    otros: "Otros",
    derribados: "Derribados",
    derribadosONeutralizados: "Derribados o neutralizados",
    guerraElectronica: "Perdidos por guerra electrónica",
    localizacionesImpacto: "Localizaciones con impacto",
    localizacionesRestos: "Localizaciones con caída de restos",
    zonasLanzamiento: "Zonas de lanzamiento",
    regiones: "Regiones afectadas",
    regionesMisiles: "Regiones citadas solo por misiles",
    cruces: "Cruces a otros países",
    cruceDeclarado: "Declarado por Ucrania; sin incidente del país",
    incluidoEn: "Cifras incluidas en el parte",
    solapadoCon: "Se solapa con el parte",
  },
  trafico: {
    rotulo: "Tráfico aéreo",
    cierreMedido: "Cierre medido con tráfico aéreo real",
    duracion: (minutos) => `${minutos} min`,
    desviados: (n) => `${n} vuelos desviados`,
    enEspera: (n) => `${n} en espera`,
    declarado: "Según las fuentes",
    datos: "Datos de adsb.lol",
  },
  foco: {
    rotulo: "Satélite",
    detectado: "Foco térmico detectado por satélite",
    distancia: (km) => `a ${km} km`,
    visor: "Ver en el visor de NASA FIRMS",
  },
  region: {
    etiqueta: "Región · capa de Ucrania",
    ataques: "Ataques en el periodo",
    ataquesPorSentido: {
      RU_UA: "Ataques rusos según la Fuerza Aérea de Ucrania",
      UA_RU: "Ataques ucranianos según el Ministerio de Defensa ruso",
    },
    derribados: "Drones derribados sobre la región",
    ultimoAtaque: "Último ataque",
    sinAtaques: "Ningún parte cita esta región en el periodo elegido.",
    listaAtaques: "Partes que la citan",
    masAtaques: (n) => `Ver ${n} más`,
    nota:
      "Las cifras son las que da cada parte en sus comunicados. Los derribos por región son " +
      "los que cada parte desglosa por región.",
    fuenteCifras: (medio) => `Cifras de ${medio}`,
    reivindicacion: "reivindicación de parte",
    impactos: "Impactos con lugar en el periodo",
    listaImpactos: "Lugares alcanzados",
  },
  impacto: {
    etiqueta: "Impacto con lugar · capa de guerra",
    lugar: "Lugar",
    instalacionEn: (localidad) => `en ${localidad}`,
    radio: (km) => `área de ${km} km de radio`,
    nivel: {
      comunidad: "la fuente solo nombra la comunidad, no la localidad",
      distrito: "la fuente solo nombra el distrito, no la localidad",
    },
    tipo: { impacto: "Alcanzado", restos: "Caída de restos de un dron derribado" },
    objetivo: "Tipo de objetivo",
    sinObjetivo: "la fuente no lo dice",
    fecha: "Fecha",
    publicado: "publicado; el impacto fue antes",
    diaAtaque: "día del ataque según el mensaje",
    parteDiario: "parte diario de la administración: las 24 horas anteriores a su publicación",
    victimas: "Víctimas",
    heridos: (n) => `${n} heridos`,
    fallecidos: (n) => `${n} fallecidos`,
    ataque: "Ataque de esa noche",
    region: "Región",
    credibilidad: "Credibilidad",
    credibilidadTexto: {
      1: "confirmado",
      2: "probable",
      3: "posible",
      4: "dudoso",
      5: "improbable",
      6: "sin base",
    },
    reivindicacion: "Reivindicación de parte",
    reivindicacionTexto:
      "Solo lo dice una de las partes en guerra, sin otra fuente independiente ni dato " +
      "medido que lo confirme.",
    ocupacion: "autoridad instalada por Rusia",
    fuentes: (n) => (n === 1 ? "1 fuente" : `${n} fuentes`),
    cargando: "Cargando el impacto…",
    noDisponible: "No se ha podido cargar este impacto.",
  },
  lista: {
    titulo: "Lista de incidentes",
    incidentes: (n) => (n === 1 ? "1 incidente en el periodo" : `${n} incidentes en el periodo`),
    vacia: "Ningún incidente en el periodo elegido.",
    regiones: "Regiones de la capa de guerra",
  },
  tiempo: {
    periodo: (desde, hasta) => `${desde} – ${hasta}`,
    intervalo: (a, b) => {
      if (a.anio !== b.anio) return `del ${diaMesAnio(a)} al ${diaMesAnio(b)}`;
      if (a.mes !== b.mes) return `del ${a.dia} de ${MESES[a.mes]} al ${diaMesAnio(b)}`;
      if (a.dia !== b.dia) return `del ${a.dia} al ${diaMesAnio(b)}`;
      return `del ${diaMesAnio(a)}`;
    },
    noche: (a, b) =>
      a.mes === b.mes ? `noche del ${a.dia} al ${b.dia} de ${MESES[b.mes]}` : `noche del ${a.dia} de ${MESES[a.mes]} al ${b.dia} de ${MESES[b.mes]}`,
    dia: (f) => `día ${f.dia} de ${MESES[f.mes]}`,
  },

  metodologia: {
    titulo: "Metodología",
    cerrar: "Cerrar la metodología",
    secciones: [
      {
        id: "que",
        titulo: "Qué se registra",
        bloques: [
          {
            parrafo: [
              `El ${NOMBRE} registra incidentes con drones en Europa: aparatos no tripulados ` +
                "que sobrevuelan una instalación, entran en un espacio aéreo desde fuera o " +
                "interrumpen el funcionamiento de un aeropuerto.",
            ],
          },
          {
            parrafo: [
              "Solo drones. No se registran globos, misiles, aviones tripulados, punteros " +
                "láser ni interferencias de señal sin dron, y tampoco los vuelos autorizados " +
                "o los accidentes de drones propios en maniobras.",
            ],
          },
          {
            parrafo: [
              "Cada incidente se sitúa como un área, un punto con su radio, porque casi " +
                "nunca se conoce la posición exacta. Cada dato conserva quién lo dice: de " +
                "cada fuente se guarda el hecho, una frase breve de origen en su idioma y el " +
                "enlace, nunca el texto completo.",
            ],
          },
        ],
      },
      {
        id: "tipos",
        titulo: "Tipos",
        bloques: [
          {
            lista: [
              {
                termino: "Interrupción aeroportuaria",
                texto: [
                  "Un aeropuerto cierra o tiene vuelos desviados, cancelados o retrasados. " +
                    "Si se da, este tipo manda sobre los demás.",
                ],
              },
              {
                termino: "Incursión",
                texto: [
                  "El dron entra desde fuera del país y su origen está demostrado por " +
                    "rastreo o por restos. Un avistamiento sin origen demostrado nunca es " +
                    "una incursión.",
                ],
              },
              {
                termino: "Sobrevuelo",
                texto: ["Cualquier otro vuelo de drones sobre una instalación o una localidad."],
              },
            ],
          },
        ],
      },
      {
        id: "estados",
        titulo: "Estados",
        bloques: [
          {
            lista: [
              {
                termino: "Notificado",
                marca: { estado: "notificado" },
                texto: [
                  "Lo cuentan las noticias. Es el estado inicial de todo incidente. En naranja.",
                ],
              },
              {
                termino: "Confirmado",
                marca: { estado: "confirmado" },
                texto: ["Una autoridad afirma que el incidente ocurrió. En rojo."],
              },
              {
                termino: "Atribuido",
                marca: { estado: "atribuido" },
                texto: [
                  "Un confirmado del que una autoridad competente (gobierno, ministerio, fuerzas " +
                    "armadas, fiscalía o policía) afirma expresamente, con sus propias palabras, quién " +
                    "es el responsable: un Estado o una persona. No basta una noticia que lo cuente sin " +
                    "sus palabras, ni que la autoridad investigue, examine una posible relación, no lo " +
                    "descarte, lo vea posible o lo sospeche: eso va en la ficha como investigación en " +
                    "curso y el incidente sigue confirmado. El autor nunca es la autoridad que declara. " +
                    "A una persona, solo si la autoridad la ha detenido, acusado o condenado, y su nombre " +
                    "solo si la autoridad lo da. Si una atribución deja de sostenerse, se retira con un " +
                    "paso en el historial que dice por qué. En el mapa, un " +
                    "círculo con un aro rojo grueso, mayor que el de un incidente y por encima de " +
                    "todo, centrado en el lugar: dentro, la bandera del país al que la autoridad lo " +
                    "atribuye, el Estado o la nacionalidad de la persona (esta, solo si la autoridad " +
                    "la dice expresamente; nunca se deduce del nombre, del lugar ni del idioma). Sin " +
                    "país, o con un país sin bandera en la web, el aro va relleno de rojo. Atribuido " +
                    "a una persona, lleva además un punto oscuro fijo en el centro. La bandera es la " +
                    "que da la autoridad, no una afirmación del observatorio. Varios atribuidos " +
                    "juntos al alejar el mapa son un marcador con su número; si son de países " +
                    "distintos, va relleno de rojo, sin bandera. La ficha lo muestra como " +
                    "«Confirmado · atribuido a…», con quién atribuye y a quién.",
                ],
              },
              {
                termino: "Desmentido",
                marca: { estado: "desmentido" },
                texto: [
                  "Una autoridad niega el incidente. Sigue publicado, con el motivo. Solo " +
                    "otra autoridad de fiabilidad igual o mayor puede devolverlo a confirmado.",
                ],
              },
            ],
          },
          {
            parrafo: [
              "En el marcador, los confirmados y los atribuidos se cuentan por separado: un " +
                "incidente atribuido ya no suma entre los confirmados. El estado se indica " +
                "siempre con color y con texto. Un círculo que junta varios incidentes es rojo " +
                "si contiene algún confirmado o atribuido y naranja si todos son notificados.",
            ],
          },
        ],
      },
      {
        id: "presencia",
        titulo: "Presencia de dron",
        bloques: [
          {
            parrafo: [
              "El estado del suceso dice si el incidente ocurrió; la presencia de dron dice si " +
                "la autoridad lo atribuye a un dron. Si la autoridad competente lo da por " +
                "hecho, está confirmado: basta con que el gestor aeroportuario, el de " +
                "navegación aérea, la policía, el ejército, un ministerio, la fiscalía o la " +
                "autoridad de aviación civil actúe o declare atribuyendo el suceso a un dron " +
                "(un cierre por dron, un aviso de dron que comunica, una intervención por " +
                "dron). No se piden restos, grabación ni detección por sensor. Queda sin " +
                "confirmar si la propia autoridad lo deja abierto («posible dron», «objeto no " +
                "identificado», «se investiga si era un dron») o si solo lo cuentan la prensa " +
                "o los testigos. Es descartada cuando una autoridad lo niega.",
            ],
          },
          {
            parrafo: [
              "El caso de Lieja lo muestra. En noviembre de 2025 el gestor de navegación " +
                "aérea cerró el tráfico del aeropuerto tras el aviso de un dron: la autoridad " +
                "lo atribuye a un dron y la presencia es confirmada. El titular de cada ficha " +
                "dice lo mismo que este campo: afirma el dron cuando está confirmado y lo da " +
                "como posible cuando no lo está.",
            ],
          },
        ],
      },
      {
        id: "almirantazgo",
        titulo: "Código del Almirantazgo",
        bloques: [
          {
            parrafo: [
              "Cada fuente lleva un código de dos caracteres, por ejemplo B2. La letra mide " +
                "la fiabilidad de la fuente, de A (autoridad con competencia directa) a F " +
                "(no se puede juzgar). El número mide la credibilidad del dato, de 1 " +
                "(confirmado por fuentes independientes) a 6 (no se puede juzgar).",
            ],
          },
          {
            lista: [
              { termino: "A", texto: ["Notas oficiales de la autoridad competente."] },
              {
                termino: "B",
                texto: [
                  "Declaraciones oficiales citadas por una noticia y partes de la Fuerza " +
                    "Aérea de Ucrania.",
                ],
              },
              { termino: "C", texto: ["Noticias de medios."] },
              { termino: "D", texto: ["Comunicados del Ministerio de Defensa ruso."] },
            ],
          },
          {
            parrafo: [
              "Las fuentes E y F no se publican. Cuando las fuentes dan cifras distintas, la " +
                "ficha muestra el rango que cubren las fuentes de fiabilidad A a C.",
            ],
          },
        ],
      },
      {
        id: "agrupacion",
        titulo: "Cómo se agrupan las noticias",
        bloques: [
          {
            parrafo: [
              "Las noticias se leen por extracción automática validada por reglas: una " +
                "ficha que no cumple el esquema, o cuya frase de origen no está en la " +
                "noticia, se descarta. Las copias de una misma nota cuentan una sola vez y " +
                "aparecen como réplicas.",
            ],
          },
          {
            parrafo: [
              "Dos noticias son el mismo incidente si hablan del mismo objetivo o de puntos " +
                "a menos de la suma de sus radios más 10 km, y sus inicios distan menos de 6 " +
                "horas o, cuando solo se conoce el día, caen en el mismo día o en el " +
                "siguiente. Más de 12 horas sin actividad abren un incidente nuevo. Dos " +
                "cierres del mismo sitio en noches distintas son siempre dos incidentes.",
            ],
          },
          {
            parrafo: [
              "Un episodio une los incidentes de dos o más objetivos del mismo país en la " +
                "misma noche, de 16:00 a 06:00 UTC. En el mapa van unidos por una línea fina.",
            ],
          },
        ],
      },
      {
        id: "declaraciones",
        titulo: "Declaraciones oficiales citadas",
        bloques: [
          {
            parrafo: [
              "Cuando una noticia cita a una autoridad, la declaración se registra como " +
                "fuente propia, de fiabilidad B, con el enlace a la noticia que la recoge. " +
                "Confirma el incidente si la autoridad afirma que ocurrió, y con él la " +
                "presencia de dron, salvo que la propia autoridad lo deje abierto; y lo " +
                "desmiente o atribuye si eso es lo que dice.",
            ],
          },
        ],
      },
      {
        id: "historial",
        titulo: "Nada se borra",
        bloques: [
          {
            parrafo: [
              "Ningún registro se elimina. Cada cambio de estado se añade al historial con " +
                "su fecha y la fuente que lo provoca, y un desmentido no borra lo anterior. " +
                "Si el cambio lo provocó una fuente que no se publica, el historial conserva " +
                "el cambio y omite la fuente.",
            ],
          },
        ],
      },
      {
        id: "fuentes",
        titulo: "Fuentes",
        bloques: [
          {
            lista: [
              {
                termino: "Noticias europeas",
                texto: [
                  "Se localizan con los ficheros GKG de ",
                  { texto: "GDELT", enlace: "https://www.gdeltproject.org/" },
                  " y se enlazan al medio original.",
                ],
              },
              {
                termino: "Notas oficiales",
                texto: [
                  "Policías, gestores de navegación aérea, aeropuertos y ministerios de " +
                    "defensa que publican sus comunicados en abierto.",
                ],
              },
              {
                termino: "Capa de Ucrania",
                texto: [
                  "Partes de la Fuerza Aérea de Ucrania y comunicados del Ministerio de " +
                    "Defensa ruso. Son reivindicaciones de parte: cada ataque agrega lo que " +
                    "declara uno de los dos bandos, normalmente por noche, sin otra fuente " +
                    "que lo confirme.",
                ],
              },
              {
                termino: "Lugares alcanzados, de Rusia contra Ucrania",
                texto: [
                  "Canales oficiales de las administraciones militares regionales de Ucrania " +
                    "y de la de Kiev, identificados desde la web oficial de cada una: " +
                    "fiabilidad B, fuente oficial.",
                ],
              },
              {
                termino: "Lugares alcanzados, de Ucrania contra Rusia",
                texto: [
                  "Canal del Estado Mayor ucraniano (sus reivindicaciones de ataques a " +
                    "refinerías, depósitos y aeródromos) y canales de los gobernadores y " +
                    "gobiernos regionales rusos que enlaza su web oficial (los daños que " +
                    "reconocen en su territorio). Son partes en guerra: fiabilidad C, " +
                    "reivindicación de parte. Lo ocupado por Rusia lleva siempre su código " +
                    "de Ucrania; las autoridades instaladas por Rusia se marcan como tales.",
                ],
              },
              {
                termino: "Puntuación de un lugar alcanzado",
                texto: [
                  "Los mensajes de un mismo canal no son fuentes independientes. Una sola " +
                    "fuente oficial da «probable»; una reivindicación de parte, «posible». " +
                    "Sube si lo confirma otra fuente independiente, si lo dicen los dos " +
                    "lados (como mínimo «probable») o si el satélite detecta un foco " +
                    "térmico nuevo en el lugar, que cuenta como un dato medido. El mismo " +
                    "trato para las dos partes. Los misiles y las bombas de los mismos " +
                    "mensajes no se registran.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "focos",
        titulo: "Focos térmicos por satélite",
        bloques: [
          {
            parrafo: [
              "Cada impacto declarado (un dron que explotó o cayó, con su lugar a 10 km o " +
                "menos) se cruza con las anomalías térmicas que detectan los satélites de ",
              { texto: "NASA FIRMS", enlace: "https://www.earthdata.nasa.gov/firms" },
              " (VIIRS en Suomi NPP, NOAA-20 y NOAA-21, y MODIS en Terra y Aqua). La marca " +
                "dice que hubo al menos dos focos dentro de su radio de precisión (entre 2 y " +
                "10 km) desde el inicio del ataque hasta 36 horas después de su fin.",
            ],
          },
          {
            parrafo: [
              "Las refinerías y las plantas tienen antorchas que el satélite ve siempre: solo " +
                "cuenta un foco nuevo respecto a los 30 días anteriores o con una potencia más " +
                "de cuatro veces la habitual de ese sitio. Como hay antorchas que pasan meses " +
                "sin verse, un foco nuevo en un sitio que ya ardía el año anterior solo cuenta " +
                "si su potencia pasa de cuatro veces la de ese sitio en el año, salvo que un " +
                "mismo paso del satélite vea tres o más. Se descartan los focos de baja " +
                "confianza. Los impactos que solo se conocen por región no se evalúan; los " +
                "lugares alcanzados de los canales regionales y del Estado Mayor, sí, salvo los " +
                "de los partes diarios de la línea del frente y los ataques con FPV, donde la " +
                "artillería da focos cada día. Tampoco se evalúa un lugar cuyo radio ardió la " +
                "mitad de los 30 días anteriores o más, repartido por muchos sitios: un foco " +
                "nuevo allí no dice nada.",
            ],
          },
          {
            parrafo: [
              "Los satélites pasan varias veces al día sobre cada lugar y cada paso deja sus " +
                "detecciones. La marca aparece cuando hay foco: es un dato físico medido, un " +
                "fuego dentro del radio en la ventana del ataque, que acompaña a lo que dicen " +
                "las fuentes.",
            ],
          },
        ],
      },
      {
        id: "satelite",
        titulo: "Guerra por satélite",
        bloques: [
          {
            parrafo: [
              "En la capa de guerra, cuatro piezas salen de satélites y de los partes. " +
                "Imágenes de antes y después: para cada impacto con foco térmico detectado y " +
                "para cada impacto en una instalación, la última imagen de ",
              { texto: "Sentinel-2", enlace: "https://registry.opendata.aws/sentinel-2-l2a-cogs/" },
              " sin nubes anterior al ataque y la primera posterior, recortadas sobre el sitio " +
                "en color natural y con el mismo ajuste de brillo. Las nubes se miden en el " +
                "propio recorte con la clasificación de escena de la ESA: vale una imagen con un " +
                "3 % de nube o menos sobre la instalación, aunque la escena entera esté nublada. " +
                "Solo se publica la pareja en la que se ve el cambio: las dos imágenes se llevan a " +
                "una misma rejilla de 10 m y se mide la diferencia del índice de quemado (bandas " +
                "B8A y B12) y el oscurecimiento en el color natural, sin nubes, sombras, nieve ni " +
                "agua, y por encima de lo que cambia el resto del recorte (la estación, los " +
                "cultivos, la luz). Cuenta la mancha que toca un círculo de 800 m alrededor del " +
                "impacto, y se publica si llega a 10 hectáreas; si la primera imagen posterior " +
                "despejada no la muestra (el humo o una nube fina la tapan), se prueban las " +
                "siguientes durante 15 días. La zona cambiada va marcada con un contorno y la " +
                "imagen se encuadra en ella. Todo lo que sale del satélite se enciende con " +
                "«Con satélite»; los corredores, con su botón.",
            ],
          },
          {
            parrafo: [
              "Luz nocturna: tras cada ataque con objetivos de energía (un impacto en la red " +
                "eléctrica o un mensaje oficial de la región que la nombra), el brillo de las " +
                "ciudades y regiones afectadas en la banda día-noche de VIIRS (NOAA-20), del ",
              {
                texto: "archivo abierto de NOAA",
                enlace: "https://registry.opendata.aws/noaa-jpss/",
              },
              ". El brillo es la luz de la ciudad por encima del fondo que la rodea, medido en " +
                "el mismo paso del satélite (así se quita la luz de la Luna reflejada por el " +
                "suelo); solo cuentan las noches con el 70 % de nubes o menos (nubosidad de " +
                "Open-Meteo a la hora del paso) y con el satélite casi en la vertical. La " +
                "referencia es la mediana de las noches válidas de las tres semanas anteriores; " +
                "hay pérdida de luz cuando dos noches o más de la semana siguiente pierden la " +
                "mitad o más, en ciudades con 0,5 nW/(cm²·sr) o más de referencia. Los umbrales " +
                "se fijaron con 20 apagones documentados de 2024 a 2026, 9 controles y 411 " +
                "ventanas sin ataques (3 dieron pérdida).",
            ],
          },
          {
            parrafo: [
              "Alumbrado reducido de forma permanente: una ciudad cuyo brillo se queda por debajo " +
                "de 0,5 nW/(cm²·sr) sobre el fondo no puede dar un apagón con esta regla, así que se " +
                "marca en el mapa con un signo propio. Se marca cuando la mediana de sus últimas 10 " +
                "noches válidas está por debajo de ese mínimo y, mes a mes hacia atrás (meses con 3 " +
                "noches válidas o más), la mediana mensual también lo está; un mes suelto por encima " +
                "(la nieve refleja la luz de la ciudad, como en enero de 2026) no rompe la racha, dos " +
                "meses medidos seguidos sí. Su ficha da la fecha desde la que está así (o «al menos " +
                "desde» la primera noche medida), el brillo actual y el más antiguo medido, cada uno " +
                "la mediana de 10 noches válidas, y el número de noches en que se basa. Se calcula con " +
                "todas las noches medidas por NOAA-20.",
            ],
          },
          {
            parrafo: [
              "Focos de calor confirmados: de los de NASA FIRMS de las últimas 24 horas sobre " +
                "Ucrania y la Rusia europea, con los mismos filtros que el cruce con los impactos " +
                "(fuera las antorchas de las refinerías y las plantas con calor habitual, la baja " +
                "confianza y las zonas que arden a diario, como las ciudades del frente), solo se " +
                "publican los que caen en el radio de un impacto declarado en las 36 horas de " +
                "alrededor. En «Con satélite» cuentan como impactos con foco en cuanto se " +
                "confirman, junto a los del cruce histórico. Los demás (quemas agrícolas, " +
                "industria, incendios forestales) se siguen descargando y cruzando, pero no se " +
                "dibujan.",
            ],
          },
          {
            parrafo: [
              "Corredores de ataque: arcos desde las zonas de lanzamiento que nombran los " +
                "partes de la Fuerza Aérea de Ucrania (con el punto del catálogo de zonas del " +
                "motor de deducción) hasta las regiones alcanzadas, con el grosor según los " +
                "drones de esos ataques en el periodo elegido. En los ataques contra Rusia, cuyo " +
                "parte da los derribos por región, el arco sale del punto de la frontera de " +
                "Ucrania más cercano a cada región y su cifra son esos derribos.",
            ],
          },
        ],
      },
      {
        id: "rutas",
        titulo: "Rutas de los drones sobre Ucrania",
        bloques: [
          {
            parrafo: [
              "La subcapa «Rutas» de la capa de Ucrania dibuja por dónde pasaron los drones de " +
                "cada noche, como franjas semitransparentes con su anchura de incertidumbre, nunca " +
                "como líneas exactas. Se publican cuando el ataque ha terminado: pasadas las 12:00 " +
                "UTC del día siguiente y dos horas después del último aviso de la noche. Nunca en " +
                "directo.",
            ],
          },
          {
            lista: [
              {
                termino: "Con NEPTUN",
                texto: [
                  "Desde el 4 de octubre de 2026 el observatorio guarda el flujo de ",
                  { texto: "NEPTUN", enlace: "https://neptun.in.ua/" },
                  ", que estima la posición, el rumbo, la velocidad y el número de cada amenaza a " +
                    "partir de informes (no es un radar). Las noches con ese archivo casi completo " +
                    "usan sus pistas, con el radio de incertidumbre que da NEPTUN y su enlace visible.",
                ],
              },
              {
                termino: "Con la Fuerza Aérea de Ucrania",
                texto: [
                  "Para el resto de noches, desde 2023, se reconstruye la ruta con los mensajes de " +
                    "seguimiento de la Fuerza Aérea («БпЛА на півночі Сумщини, курс…»): cada " +
                    "mensaje da una zona (una localidad, una parte de una región, una región o el " +
                    "mar) y a veces un rumbo o un destino; dos mensajes se enlazan si el dron pudo " +
                    "volar de una zona a la otra en ese tiempo y en esa dirección. Un grupo no se " +
                    "identifica por el texto: puede dividirse, unirse o no saberse. Cada tramo " +
                    "guarda de qué mensajes sale.",
                ],
              },
              {
                termino: "Comprobación",
                texto: [
                  "En las noches con NEPTUN, la ruta reconstruida solo con la Fuerza Aérea se " +
                    "compara con las pistas de NEPTUN y con la línea recta de la zona de lanzamiento " +
                    "a cada impacto de la noche. Las rutas reconstruidas se publican solo si quedan " +
                    "claramente más cerca de NEPTUN que la línea recta (la mediana un 20 % menor o " +
                    "más, y mejor en cada noche). La leyenda y la ficha de cada tramo dicen de qué " +
                    "fuente sale y su precisión.",
                ],
              },
              {
                termino: "Incursiones",
                texto: [
                  "En los incidentes de Rumanía, Moldavia y Polonia en que la autoridad nombra los " +
                    "lugares por los que pasó el dron, la ficha dibuja ese recorrido al abrirla, con " +
                    "la frase de la que sale. Cuando una ruta de una noche acaba en un incidente " +
                    "europeo de esa noche, la ficha del tramo lo enlaza.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "tipo-dron",
        titulo: "Tipo de dron",
        bloques: [
          {
            parrafo: [
              "Cada incidente dice qué clase de dron pudo ser solo cuando hay base para ello. Si " +
                "una autoridad nombra el modelo (por ejemplo, los restos de un Gerbera que " +
                "identifica el ejército), la ficha dice eso y de dónde sale. Si no, el " +
                "observatorio lo deduce y lo enseña aparte, como «compatible con», con la " +
                "probabilidad de cada clase y el porqué.",
            ],
          },
          {
            lista: [
              {
                termino: "Rasgos descritos",
                texto: [
                  "De las frases de las fuentes se leen la forma (multirrotor, ala fija, ala en " +
                    "delta), el ruido (hélice, motor de combustión, reacción), el tamaño, las " +
                    "luces, el número de aparatos, la duración, la altura, la velocidad, la hora " +
                    "y el comportamiento (quieto, dando vueltas, de paso, en formación). Cada " +
                    "rasgo guarda la frase literal y su fuente. Lo que el texto no dice no se " +
                    "supone.",
                ],
              },
              {
                termino: "Cálculo",
                texto: [
                  "Se parte de la frecuencia de cada clase en los casos de la misma zona " +
                    "(frontera o interior) en que una autoridad identificó el dron. Cada rasgo " +
                    "sube o baja las clases según lo que dice de ellas el catálogo de " +
                    "prestaciones, y pesan las restricciones físicas: la distancia a Ucrania, " +
                    "Rusia y Bielorrusia (y a la costa) frente al alcance de cada clase; el viento " +
                    "y la temperatura de esa hora y ese lugar; la duración y la altura frente a " +
                    "su autonomía y su techo; y la velocidad: por debajo de 230 km/h, hélice; por " +
                    "encima de 300 km/h, reacción; entre medias no decide.",
                ],
              },
              {
                termino: "Comprobación",
                texto: [
                  "El cálculo se repite con cada caso de respuesta conocida apartado (restos y " +
                    "declaraciones oficiales en Rumanía, Moldavia, Polonia, Lituania, Letonia, " +
                    "Bulgaria y Turquía, y encuentros con drones clasificados por la UK Airprox " +
                    "Board) y se compara con decir siempre la clase más frecuente. Solo se " +
                    "publican las clases que tienen al menos 5 casos comprobados, mejoran a esa " +
                    "referencia y dan probabilidades que se cumplen. El 6 de octubre de 2026 " +
                    "pasan el dron de ataque de largo alcance de hélice y el señuelo de largo " +
                    "alcance, en la frontera. Las cifras de cada clase están en el informe " +
                    "docs/informe_tipo_y_rutas.md del repositorio.",
                ],
              },
              {
                termino: "Sin base",
                texto: [
                  "Sin rasgos que pesen ni entrada desde fuera en la frontera, con el dron sin " +
                    "confirmar o con una clase más probable que no ha pasado la comprobación, la " +
                    "fila no aparece.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "trafico",
        titulo: "Tráfico aéreo medido",
        bloques: [
          {
            parrafo: [
              "En los incidentes en aeropuertos con vuelos regulares, el cierre se mide con el " +
                "tráfico real: el archivo diario de ",
              { texto: "adsb.lol", enlace: "https://adsb.lol/" },
              ", una red abierta de receptores ADS-B. Se cuentan los aterrizajes y despegues " +
                "de aviones de línea y de negocios en franjas de 15 minutos y se comparan con " +
                "la misma franja del mismo día de la semana de las cuatro semanas anteriores. " +
                "Un cierre medido es un tramo con el 30 % o menos del tráfico habitual que " +
                "coincide con el incidente; su inicio y su fin son el último movimiento antes " +
                "del hueco y el primero después.",
            ],
          },
          {
            parrafo: [
              "Un vuelo desviado es el que bajaba hacia el aeropuerto y aterrizó en otro, o el " +
                "que aterrizó en otro aeropuerto con un número de vuelo que las semanas " +
                "anteriores llegaba allí a esa hora. Un vuelo en espera es el que hizo " +
                "circuitos de espera, con el detector de la biblioteca abierta traffic. Si lo " +
                "medido difiere de lo que dicen las fuentes, se muestran los dos.",
            ],
          },
          {
            parrafo: [
              "Cobertura: cada día se compara lo que ve adsb.lol en cada aeropuerto con los " +
                "vuelos IFR de referencia de EUROCONTROL, y los huecos se interpretan en los " +
                "aeropuertos y días en que se ve la mitad o más. Cada hueco se cruza con los " +
                "METAR del aeropuerto: los que explica el tiempo (niebla, tormenta, nieve, " +
                "viento fuerte o pista contaminada) se apartan. El cierre medido se muestra " +
                "junto al incidente con el que coincide.",
            ],
          },
          {
            parrafo: [
              "La ficha lleva el cierre medido cuando el incidente es en un aeropuerto con " +
                "vuelos regulares, adsb.lol publicó el día completo, la cobertura de ese " +
                "aeropuerto ese día es suficiente, hay cuatro semanas de línea base y un hueco " +
                "coincide con el incidente. Cada valor sale de la medida; ninguno se estima.",
            ],
          },
        ],
      },
      {
        id: "directo",
        titulo: "Detección en directo de cierres",
        bloques: [
          {
            parrafo: [
              `Cada ${UMBRALES_DIRECTO.cicloS} segundos se piden las posiciones de las aeronaves ` +
                "alrededor de los aeropuertos vigilados (los de cobertura alta los cuatro días " +
                "de su línea base en el archivo diario) a ",
              { texto: "adsb.lol", enlace: "https://adsb.lol/" },
              "; si no responde, el servicio pasa solo a ",
              { texto: "adsb.fi", enlace: "https://adsb.fi/" },
              ". Con esas posiciones se reconstruyen las llegadas y las salidas, con las mismas " +
                `reglas que el tráfico medido y un retraso de ${UMBRALES_DIRECTO.retrasoMin} minutos para que ` +
                "cada movimiento quede completo, y se comparan con la mediana del mismo día de " +
                "la semana y la misma hora local de las cuatro semanas anteriores.",
            ],
          },
          {
            lista: [
              {
                termino: "Posible cierre en curso",
                texto: [
                  `Desde el último movimiento faltan al menos ${UMBRALES_DIRECTO.esperadosMin} movimientos ` +
                    `esperados, se ve como mucho el ${UMBRALES_DIRECTO.fraccionVistos} de ellos, lo que ` +
                    `falta crece al menos ${UMBRALES_DIRECTO.ritmo} movimientos por minuto de hueco, ` +
                    "ninguna aeronave está despegando o aterrizando, todo ello durante " +
                    `${UMBRALES_DIRECTO.persistenciaMin} minutos, y ningún METAR ` +
                    "desde una hora antes lo explica (niebla, visibilidad, techo, tormenta, nieve, " +
                    "viento fuerte o pista contaminada).",
                ],
              },
              {
                termino: "Cierre confirmado",
                texto: ["Una fuente oficial o un incidente de la base recoge el cierre."],
              },
              {
                termino: "Operación reanudada",
                texto: [
                  `Vuelven al menos ${UMBRALES_DIRECTO.reanudacion} movimientos y en la última media ` +
                    "hora se ve la mitad o más de lo esperado. El aviso sigue " +
                    `${UMBRALES_DIRECTO.permanenciaH} horas en el mapa.`,
                ],
              },
            ],
          },
          {
            parrafo: [
              "Cada aviso guarda su hora de detección, su evidencia (movimientos esperados y " +
                "vistos, llegadas y salidas perdidas, aviones en espera y vuelos desviados) y, " +
                "cuando llega, la hora de la primera noticia, que da la ventaja de la " +
                "detección. Un aviso pone en marcha la búsqueda dirigida de noticias; cuando se " +
                "confirma, el incidente entra en la base por el flujo normal con el cierre " +
                "medido.",
            ],
          },
        ],
      },
      {
        id: "gnss",
        titulo: "Interferencia GPS",
        bloques: [
          {
            parrafo: [
              "Cada posición ADS-B lleva su integridad (NIC) y su precisión (NACp). Una " +
                "aeronave tiene la posición degradada en una zona un día si alguna de sus " +
                "posiciones allí trae NIC menor que 7 o NACp menor que 8, los mínimos de la " +
                "norma de ADS-B Out. Las zonas son hexágonos H3 de resolución 4 (unos 1770 " +
                "km²), la rejilla de gpsjam.org. La proporción de aeronaves afectadas resta " +
                "una degradada, para que un solo equipo averiado no tiña la zona: (degradadas " +
                "− 1) / aeronaves.",
            ],
          },
          {
            parrafo: [
              "Cada zona del mapa reúne 20 aeronaves o más en el día. Niveles: menos del 2 % " +
                "sin interferencia, del 2 al 10 % media y más del 10 % alta, en gris cuanto más " +
                "claro más proporción y el nivel alto en rojo. En un periodo se " +
                "suman por zona las aeronaves y las degradadas de cada día (de cada mes en los " +
                "periodos de más de 7 días). Se calcula en el servidor con el archivo diario " +
                "de adsb.lol. «Europa ahora» cuenta las zonas con " +
                "interferencia alta del último día publicado; la leyenda de la capa cuenta, con " +
                "el mismo cálculo, las del periodo elegido.",
            ],
          },
        ],
      },
      {
        id: "presion",
        titulo: "Presión por país",
        bloques: [
          {
            parrafo: [
              "Cada país se rellena en gris según sus incidentes en el periodo elegido, con " +
                "los filtros activos: cinco escalones respecto al país con más. La tendencia " +
                "compara con el periodo anterior de la misma duración: estable si la " +
                "diferencia es cero, o de uno y no pasa del 10 % de lo anterior; si no, sube " +
                "o baja, con la cifra. Al pulsar un país salen sus cifras por tipo y por " +
                "estado y sus incidentes.",
            ],
          },
          {
            parrafo: [
              "Las cifras por país cuentan los incidentes registrados con lo que publican en " +
                "abierto los medios y las autoridades de cada país, en las lenguas que lee la " +
                "recogida.",
            ],
          },
        ],
      },
      {
        id: "frontera",
        titulo: "Frontera o interior",
        bloques: [
          {
            parrafo: [
              "En el mapa hay dos cosas distintas: drones de la guerra que cruzan o caen cerca de la frontera con Ucrania, Rusia (también Kaliningrado) o Bielorrusia o en la costa del mar Negro, y drones sobre aeropuertos, bases e instalaciones del interior de Europa. El filtro «Dónde» enseña todos, solo los de frontera o solo los de interior; las cifras de la cabecera lo siguen. Cada incidente lleva en su ficha su grupo y la regla que lo decide.",
            ],
          },
          {
            lista: [
              { termino: "1. Ataque", texto: ["Si el incidente está enlazado con el ataque ruso contra Ucrania de esa noche, es de frontera."] },
              {
                termino: "2. Distancia",
                texto: [
                  "Con punto: es de frontera si está a 150 km o menos de la frontera terrestre con Ucrania, Rusia o Bielorrusia, o a 50 km o menos de la costa del mar Negro; si no, de interior. El corte sale de los datos: de los incidentes con punto, los de la banda llegan hasta 144 km (incursiones en Polonia, Rumanía y Lituania) y el siguiente está a 191 km (el aeropuerto de Bucarest).",
                ],
              },
              { termino: "3. Lugar nombrado", texto: ["Sin punto, la misma distancia desde el lugar del país que nombran su localidad, su región o su titular; un titular que lo sitúa en el mar Negro es de frontera."] },
              {
                termino: "4. Sin lugar",
                texto: [
                  "Es de frontera si el dron entró desde fuera (incursión, entrada desde el exterior o dron de un Estado) en un país con frontera con Ucrania, Rusia o Bielorrusia o con costa en el mar Negro, o si todo el país está a 150 km o menos de esa frontera (Moldavia). Si no, de interior.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "prevision",
        titulo: "Previsión y tendencias",
        bloques: [
          {
            parrafo: [
              "El botón «Previsión» dice qué está pasando más de lo normal y qué es probable que pase. Solo se publica lo que ha pasado una comprobación con el pasado: cada número se calcula con los datos anteriores a una fecha y se compara con lo que ocurrió después, avanzando en el tiempo, sin usar nunca datos futuros. Se compara con dos referencias simples, la frecuencia de siempre del país y «mañana igual que hoy», y se publica solo si acierta más que las dos y la mejora se sostiene al repetir la comprobación con semanas tomadas al azar. Lo que no pasa no sale. Con pocos datos no se afirma nada.",
            ],
          },
          {
            lista: [
              {
                termino: "Esta noche en la frontera",
                texto: [
                  "Probabilidad de que un dron de la guerra cruce o caiga en el país la noche siguiente (al menos un incidente de frontera esa noche). Se calcula antes de la noche, solo con lo que ya se sabe: los drones lanzados contra Ucrania de media en las tres últimas noches (partes de la Fuerza Aérea de Ucrania), cuántas de las siete últimas noches salieron drones desde Crimea y los incidentes de frontera del país en los siete días anteriores. Es una regresión logística que se reajusta cada mes. Se dice como «2 de cada 10 noches como esta (20 %)», con lo habitual del país y si cada factor sube o baja hoy el riesgo frente a su valor habitual. Sale para cada país en que pasa la comprobación.",
                ],
              },
              {
                termino: "Segunda noche",
                texto: [
                  "Tras una oleada grande sobre Ucrania (los drones lanzados llegan al percentil 90 de las 60 noches anteriores), la probabilidad de que la siguiente también lo sea. Sale solo esas noches y solo mientras su comprobación lo respalde.",
                ],
              },
              {
                termino: "Rachas por país",
                texto: [
                  "Lo normal de un país es la media de sus semanas del último año sin las cuatro últimas. Hay racha cuando las cuatro últimas semanas suman más de lo que lo normal da 1 de cada 20 veces (binomial negativa con la dispersión del propio país), con 3 incidentes como mínimo en 2 días distintos o más. Cuenta sucesos, no noticias: cada incidente una vez, en la fecha del suceso. Un país con menos de 5 incidentes en su año normal no tiene racha. Se dice desde cuándo, cuántos incidentes frente a lo habitual y si crece (las dos últimas semanas superan a las dos anteriores) o se apaga. La comprobación: tras marcar una racha, la semana siguiente se parece más a la racha que a lo normal.",
                ],
              },
              {
                termino: "La semana que viene",
                texto: [
                  "Lo esperado es la media de las semanas anteriores con un peso que se reduce a la mitad cada cuatro semanas; el margen va del 10 al 90 % de una binomial negativa con la dispersión del país, así que 8 de cada 10 semanas deberían caer dentro. Se publica en los países en que mejora a la frecuencia de siempre y a «la semana que viene igual que esta».",
                ],
              },
              {
                termino: "Qué ha cambiado",
                texto: [
                  "La proporción de cada tipo de objetivo entre los impactos sobre Ucrania con objetivo conocido (solo de los canales oficiales que dan impactos en todos los trimestres desde enero de 2025, para que un canal que empieza o deja de nombrar lugares no cambie la mezcla) y la de cada tipo de incidente en Europa, en los tres últimos meses cerrados frente a los doce anteriores. Se lista solo lo que ha cambiado de verdad: fuera de lo que lo habitual da 1 de cada 20 veces y con 3 puntos de diferencia o más. Se mira la proporción y no el número porque el número de un mes depende de cuántas fuentes se leen. Comprobación: tras marcar un cambio, el mes siguiente se parece más a lo reciente que a lo habitual. Por región de Ucrania no: cada región la cuenta un solo canal, y un cambio regional no se distingue de un cambio de cobertura.",
                ],
              },
              {
                termino: "Mezcla de cada oleada",
                texto: [
                  "En la capa de Ucrania, la ficha de cada ataque y «Noche a noche» dicen cuántos de los drones lanzados eran Shahed o Geran y cuántos a reacción cuando el parte de la Fuerza Aérea de Ucrania lo dice («близько 60 з них – шахеди», «понад 50 із них – реактивні»); el resto son señuelos Gerbera y otros tipos. Son mínimos y solo de los partes oficiales. La página de texto de Ucrania tiene la mezcla mes a mes.",
                ],
              },
              {
                termino: "Cómo se puntúa",
                texto: [
                  "Las probabilidades, con la puntuación de Brier (el error al cuadrado entre la probabilidad y lo que pasó); los números semanales, con el logaritmo de la probabilidad que dio el método a lo que pasó. El historial de aciertos de cada parte dice con cuántas noches o semanas se comprobó, cuánto mejora a la referencia y, en la frontera, qué pasó en cada tramo de probabilidad. Las previsiones de las semanas anteriores a su publicación se reconstruyen tal como se habrían hecho entonces y se marcan como reconstruidas.",
                ],
              },
              {
                termino: "Registro en vivo",
                texto: [
                  "Desde el 6 de octubre de 2026 cada previsión queda guardada con su hora antes de conocerse el resultado (la de la frontera, en la primera actualización desde las 17:00 UTC; la semanal, el sábado) en un registro que no admite cambios ni borrados, y se puntúa cuando el resultado ya se conoce (3 días después de la noche, una semana después de acabar la semana). Va en el fichero publicado prevision.json y en la exportación de datos, con su método y su fecha.",
                ],
              },
            ],
          },
        ],
      },
      {
        id: "licencias",
        titulo: "Licencias y atribuciones",
        bloques: [
          {
            lista: [
              {
                termino: "Código",
                texto: [{ texto: "Apache-2.0", enlace: `${REPOSITORIO}/blob/main/LICENSE` }, "."],
              },
              {
                termino: "Datos",
                texto: [
                  { texto: LICENCIA_DATOS, enlace: LICENCIA_DATOS_URL },
                  ". Las frases de origen pertenecen a sus autores y se reproducen como " +
                    "cita breve junto al enlace.",
                ],
              },
              {
                termino: "Mapa base",
                texto: [
                  "© colaboradores de ",
                  { texto: "OpenStreetMap", enlace: "https://www.openstreetmap.org/copyright" },
                  " (ODbL), con teselas y estilo de ",
                  { texto: "Protomaps", enlace: "https://protomaps.com/" },
                  ".",
                ],
              },
              {
                termino: "Fronteras y regiones",
                texto: [
                  { texto: "Natural Earth", enlace: "https://www.naturalearthdata.com/" },
                  ", dominio público.",
                ],
              },
              {
                termino: "Noticias",
                texto: [{ texto: "GDELT", enlace: "https://www.gdeltproject.org/" }, "."],
              },
              {
                termino: "Localidades",
                texto: [
                  { texto: "GeoNames", enlace: "https://www.geonames.org/" },
                  " (CC BY 4.0).",
                ],
              },
              {
                termino: "Tráfico aéreo",
                texto: [
                  "© adsb.lol contributors (",
                  { texto: "adsb.lol", enlace: "https://adsb.lol/" },
                  "), ",
                  { texto: "ODbL 1.0", enlace: "https://opendatacommons.org/licenses/odbl/1-0/" },
                  ". El bloque de tráfico aéreo de los ficheros publicados deriva de esos datos " +
                    "y se ofrece con la misma licencia. Aeropuertos y pistas de ",
                  { texto: "OurAirports", enlace: "https://ourairports.com/data/" },
                  " (dominio público); referencia de cobertura de EUROCONTROL (Aviation " +
                    "Intelligence Portal), que no se publica; esperas con el método de la " +
                    "biblioteca ",
                  { texto: "traffic", enlace: "https://github.com/xoolive/traffic" },
                  " (MIT, © Xavier Olive).",
                ],
              },
              {
                termino: "Tráfico en tiempo real",
                texto: [
                  "© adsb.lol contributors (",
                  { texto: "adsb.lol", enlace: "https://adsb.lol/" },
                  "), ",
                  { texto: "ODbL 1.0", enlace: "https://opendatacommons.org/licenses/odbl/1-0/" },
                  "; y, como respaldo, ",
                  { texto: "adsb.fi", enlace: "https://adsb.fi/" },
                  ".",
                ],
              },
              {
                termino: "Meteorología",
                texto: [
                  { texto: "Weather data by Open-Meteo.com", enlace: "https://open-meteo.com/" },
                  " (CC BY 4.0) y METAR del ",
                  {
                    texto: "Iowa Environmental Mesonet",
                    enlace: "https://mesonet.agron.iastate.edu/",
                  },
                  " de Iowa State University.",
                ],
              },
              {
                termino: "Imágenes de satélite",
                texto: [
                  "Contains modified Copernicus Sentinel data (",
                  {
                    texto: "Sentinel-2 L2A en AWS",
                    enlace: "https://registry.opendata.aws/sentinel-2-l2a-cogs/",
                  },
                  "). Luz nocturna: VIIRS de NOAA-20, ",
                  { texto: "NOAA Open Data Dissemination", enlace: "https://registry.opendata.aws/noaa-jpss/" },
                  ".",
                ],
              },
              {
                termino: "Focos térmicos",
                texto: [
                  "We acknowledge the use of data and/or imagery from NASA's Fire " +
                    "Information for Resource Management System (FIRMS) (",
                  {
                    texto: "https://www.earthdata.nasa.gov/firms",
                    enlace: "https://www.earthdata.nasa.gov/firms",
                  },
                  "), part of NASA's Earth Science Data and Information System (ESDIS).",
                ],
              },
            ],
          },
        ],
      },
    ],
    descargas: {
      titulo: "Datos abiertos",
      intro:
        "Los datos se pueden descargar y reutilizar citando la fuente. Se regeneran con cada " +
        "actualización.",
      incidentes: "Incidentes",
      ucrania: "Ataques de la capa de Ucrania",
      sinUbicacion: "Incidentes con ubicación imprecisa",
      version: (fecha) => `Versión del ${fecha}`,
      licencia: "Licencia",
      citaTitulo: "Cita recomendada",
      cita: (fecha) =>
        `${NOMBRE} (EODI). Incidentes con drones en Europa, versión del ${fecha}. ` +
        `${ORIGEN}. Licencia ${LICENCIA_DATOS}.`,
    },
  },
  compartir: {
    titulo: `${NOMBRE} · Incidentes con drones en Europa`,
    tituloIncidente: (titulo) => `${titulo} · ${NOMBRE}`,
    tituloAtaque: (id) => `Ataque ${id} · ${NOMBRE}`,
    altImagen: `Logo y nombre del ${NOMBRE} sobre el mapa de Europa con los incidentes registrados`,
    lema: "Incidentes con drones en Europa, con sus fuentes y su grado de confirmación",
  },
  regiones: {
    ...REGIONES_RUSIA_ES,
    "UA-05": "Vínnytsia",
    "UA-07": "Volinia",
    "UA-09": "Lugansk",
    "UA-12": "Dnipropetrovsk",
    "UA-14": "Donetsk",
    "UA-18": "Zhytómyr",
    "UA-21": "Transcarpatia",
    "UA-23": "Zaporiyia",
    "UA-26": "Ivano-Frankivsk",
    "UA-30": "Kiev (ciudad)",
    "UA-32": "Kiev (región)",
    "UA-35": "Kirovogrado",
    "UA-40": "Sebastopol",
    "UA-43": "Crimea",
    "UA-46": "Leópolis",
    "UA-48": "Mykoláiv",
    "UA-51": "Odesa",
    "UA-53": "Poltava",
    "UA-56": "Rivne",
    "UA-59": "Sumy",
    "UA-61": "Ternópil",
    "UA-63": "Járkov",
    "UA-65": "Jersón",
    "UA-68": "Jmelnitski",
    "UA-71": "Cherkasy",
    "UA-74": "Chernígov",
    "UA-77": "Chernivtsi",
  },
  satelite: {
    capas: "Capa de guerra",
    corredores: "Corredores",
    principales: {
      principales: (n, total) => `${n} de ${total} corredores, los de más drones; el grosor y la intensidad, según los drones.`,
      todos: (total) => `Los ${total} corredores del periodo; el grosor y la intensidad, según los drones.`,
      verTodos: (total) => `Ver los ${total}`,
      verPrincipales: "Ver solo los principales",
    },
    letreroCorredor: (origen, region, drones) => `${origen} → ${region} · ${drones} drones`,
    letreroCiudad: (ciudad, perdida) => `${ciudad} · ${perdida} % menos de luz nocturna`,
    letreroAlumbrado: (ciudad) => `${ciudad} · alumbrado reducido de forma permanente`,
    corredor: {
      etiqueta: "Corredor de ataque · capa de guerra",
      origen: "Origen",
      destino: "Destino",
      desdeUcrania: "Ucrania",
      desdeUcraniaTexto:
        "El arco sale del punto de la frontera de Ucrania más cercano a la región; la cifra " +
        "es la de derribos por región del parte ruso.",
      drones: "Drones en el periodo",
      dronesTexto: {
        RU_UA:
          "Drones lanzados en los ataques del periodo que salieron de esta zona (entre otras, " +
          "si el parte nombra varias) y alcanzaron esta región, según la Fuerza Aérea de Ucrania.",
        UA_RU: "Drones que el Ministerio de Defensa ruso dice haber derribado sobre la región.",
      },
      ataques: (n) => (n === 1 ? "1 ataque" : `${n} ataques`),
      periodo: "Periodo",
      varios: "Hay varios corredores en ese punto. Elige uno:",
      etiquetaVarios: "Corredores · capa de guerra",
      lista: "Corredores de ataque del periodo",
    },
    luzFicha: {
      etiqueta: "Luz nocturna · capa de guerra",
      rotulo: "Luz nocturna",
      perdida: (pct) => `${pct} % menos de luz`,
      peorNoche: (fecha) => `la noche del ${fecha}`,
      noches: (n) => (n === 1 ? "1 noche con pérdida" : `${n} noches con pérdida`),
      referencia: (desde, hasta, n) =>
        `frente a la mediana de ${n} noches sin nubes del ${desde} al ${hasta}`,
      origen: "Medido por satélite",
      ataque: "Ataque",
      region: "Región",
      regionEntera: "suma de sus ciudades medidas",
      sinPerdida: "Ninguna pérdida de luz medida en el periodo.",
      metodo:
        "Brillo de la banda día-noche de VIIRS (NOAA-20) sobre el fondo, en noches con el 70 % " +
        "de nubes o menos. Noches con la fecha de su tarde; el paso del satélite es hacia la " +
        "01:30 hora local.",
    },
    alumbradoFicha: {
      etiqueta: "Alumbrado reducido · capa de guerra",
      titulo: "Ciudad con alumbrado reducido de forma permanente",
      desde: "Desde",
      desdeTexto: (fecha, alMenos) => (alMenos ? `al menos desde el ${fecha}` : `el ${fecha}`),
      porEncima: (mes) => `En ${mes} aún pasaba de la referencia mínima.`,
      actual: "Brillo actual",
      referencia: "Brillo de referencia",
      brillo: (valor) => `${valor} nW/(cm²·sr)`,
      tramo: (desde, hasta, noches) =>
        `mediana de ${noches} noches válidas del ${desde} al ${hasta}`,
      noches: "Noches medidas",
      metodo:
        "Por debajo de 0,5 nW/(cm²·sr) sobre el fondo, de forma sostenida, la ciudad está casi " +
        "a oscuras y un apagón no se ve desde el satélite. Brillo de referencia: el más antiguo " +
        "medido. VIIRS de NOAA-20; un mes suelto por encima (nieve) no cuenta.",
    },
    imagen: {
      rotulo: "Imagen de satélite",
      antes: "Antes",
      despues: "Después",
      deslizador: "Comparar la imagen de antes y la de después",
      escena: (id) => `escena ${id}`,
      nubes: (pct) => `${pct} % de nubes en el recorte`,
      producto: (lado) => `Sentinel-2 L2A, color natural, 10 m por píxel, recorte de ${lado} km`,
      alt: (momento, fecha) => `Imagen de satélite ${momento} del ataque, ${fecha}`,
      zonaCambio: (hectareas, antes, despues) =>
        `Zona con cambios: ${hectareas} hectáreas · antes ${antes} · después ${despues}`,
      ocultarContorno: "Ocultar contorno",
      verContorno: "Ver contorno",
    },
    zona: (_id, nombre) => nombre,
    ayudaCorredores:
      "Un arco fino y violeta va de una zona de lanzamiento a una región alcanzada: más grueso, más " +
      "drones en el periodo. Contra Rusia sale del punto de la frontera de Ucrania más cercano. " +
      "Basta con acercar el ratón o el dedo: el arco se ilumina y gana a la región de debajo; " +
      "con el tabulador se recorren uno a uno.",
    ayudaSubcapas:
      "Con la capa de Ucrania se ven sus regiones y sus impactos. «Corredores» y «Con " +
      "satélite» se encienden con su botón (y se apagan con él); al apagar la capa de Ucrania se " +
      "apagan también.",
    tipos: {
      cortinilla: "antes y después",
      foco: "foco de calor",
      apagon: "apagón",
      oscura: "ciudad a oscuras",
    },
    leyendaTipos: {
      cortinilla: "Antes y después con cambio visible",
      foco: "Foco de calor que coincide con un impacto",
      apagon: "Ciudad que perdió luz tras un ataque",
      oscura: "Ciudad con alumbrado reducido permanente",
    },
    leyenda: "Leyenda",
    filtrar: "Filtrar la lista por tipo",
    ayudaLuz:
      "Con «Con satélite»: una región o una ciudad oscurecida perdió luz nocturna tras un ataque " +
      "contra la red eléctrica, medido por satélite (apagón): más oscura, más pérdida.",
    ayudaAlumbrado:
      "Con «Con satélite»: un aro con un punto claro es una ciudad a oscuras, con el alumbrado " +
      "reducido de forma permanente: " +
      "su brillo nocturno lleva tiempo por debajo del mínimo con que se mide un apagón.",
    ayudaSatelite:
      "Un impacto más grande con el borde claro tiene información de satélite: con un segundo " +
      "aro, imagen de antes y después en la que se ve el cambio; con la marca de foco, un foco " +
      "de calor que coincide con él. Siempre encima de los demás; un grupo con alguno lleva el " +
      "borde claro. «Con satélite» enciende los cuatro tipos (antes y después, foco, apagón y " +
      "ciudad a oscuras), atenúa lo demás y abre su leyenda y su lista, que se filtra por tipo.",
    conSatelite: (n) => `Con satélite · ${n}`,
    verLista: (n) => `Lista · ${n}`,
    rotuloCapas: "Capa de Ucrania",
    listaSatelite: "Puntos con información de satélite",
    abrirLista: "Abrir la lista de puntos con satélite",
    cerrarLista: "Cerrar la lista de puntos con satélite",
    letreroSatelite: (imagen, foco) =>
      `Impacto con satélite · ${[imagen ? "antes y después" : null, foco ? "foco de calor" : null]
        .filter((x) => x !== null)
        .join(" · ")}`,
  },
};
