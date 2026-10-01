import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN, REPOSITORIO } from "../sitio.ts";
import { REGIONES_RUSIA_ES } from "./regionesRusia.ts";
import type { Textos } from "./tipos.ts";

export const es: Textos = {
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
    tipo: "Tipo",
    pais: "País",
    todosLosPaises: "Todos los países",
    estado: "Estado",
    quitar: "Quitar filtros",
    recientes: "Periodo",
    activos: (n) => (n === 1 ? "1 activo" : `${n} activos`),
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
  novedades: {
    aviso: (n) =>
      n === 1 ? "1 novedad desde tu última visita" : `${n} novedades desde tu última visita`,
    recorrer: "Verlas",
    siguiente: "Siguiente",
    anterior: "Anterior",
    descartar: "Descartar",
    posicion: (i, n) => `${i} de ${n}`,
  },
  ayuda: {
    titulo: "Cómo leer el mapa",
    cerrar: "Cerrar la ayuda",
    formas: "La forma dice el tipo de incidente.",
    colores:
      "El color dice el estado. El desmentido va sin relleno y con contorno discontinuo.",
    areas:
      "Cada incidente ocupa un área: el círculo es el radio en que se sabe que ocurrió.",
    lineas: "Una línea fina une los incidentes de un mismo episodio: varios objetivos en una noche.",
    numeros:
      "Un círculo con un número junta varios incidentes: crece con el número, y su anillo " +
      "lleva el color del estado más grave que contiene. Al acercar el mapa se separan.",
    pila:
      "Si los incidentes están en el mismo punto exacto, al pulsar el círculo eliges cuál abrir.",
    pulsos:
      "Los confirmados y los atribuidos laten despacio; los atribuidos, algo más. Los " +
      "notificados van más apagados.",
    reciente: "Un destello suave marca lo que empezó en las últimas 24 horas.",
    novedad: "Un anillo del color de la interfaz marca lo que ha cambiado desde tu última visita.",
    ucrania:
      "En la capa de Ucrania, cada región se colorea según los ataques que la citan en el periodo.",
    rusia:
      "Las regiones rusas van en gris y con contorno discontinuo: sus cifras son las del " +
      "Ministerio de Defensa ruso, una reivindicación de parte.",
    impactos:
      "Un punto pequeño es un lugar concreto alcanzado (una localidad o una instalación) " +
      "según las administraciones regionales, el Estado Mayor ucraniano o los gobernadores " +
      "rusos. Relleno: fuente oficial; solo el aro: reivindicación de parte. Al alejar se " +
      "agrupan con su número. Los partes diarios de ataques en la línea del frente no se " +
      "dibujan.",
    foco:
      "Un punto claro junto a un incidente, un impacto o un grupo de impactos, o en el centro de una región de Ucrania, marca un " +
      "foco térmico detectado por satélite (NASA FIRMS) en su lugar y su hora. Su ausencia no " +
      "demuestra nada.",
    atajos: "Atajos de teclado",
    acciones: {
      ayuda: "Abrir o cerrar esta ayuda",
      cerrar: "Cerrar la ficha o el panel abierto, o quitar el periodo elegido",
      capaIncidentes: "Capa de incidentes",
      capaUcrania: "Capa de Ucrania",
      capaDensidad: "Capa de densidad",
      filtroGraves: "Solo confirmados y atribuidos",
      filtro24h: "Últimas 24 horas",
      filtro7d: "Últimos 7 días",
      sinFiltros: "Quitar los filtros",
      lineaTiempo: "Abrir o cerrar la línea de tiempo",
      reproducir: "Reproducir la línea de tiempo",
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
    noche: (fecha) => `Noche del ${fecha}`,
    drones: "drones lanzados contra Ucrania",
    sinCifra: "sin cifra de lanzamientos",
  },
  mapa: {
    etiqueta: "Mapa de Europa con los incidentes del periodo elegido",
    instrucciones:
      "Con el foco en el mapa, las flechas lo desplazan y las teclas más y menos cambian el " +
      "zoom. La lista de incidentes da acceso a las mismas fichas sin usar el mapa.",
    grupo: (n) => (n === 1 ? "1 incidente: acerca para verlo" : `${n} incidentes: acerca para verlos`),
    pila: (n) => `${n} incidentes en este mismo punto: pulsa para elegir uno`,
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
    estado: "Estado",
    presenciaDron: "Presencia de dron",
    fecha: "Fecha",
    lugar: "Lugar",
    radio: (km) => `área de ${km} km de radio`,
    drones: "Drones",
    duracion: "Duración",
    efecto: "Efecto",
    respuesta: "Respuesta",
    atribucion: "Atribución",
    atribuidoA: (actor, autoridad) => `${actor}, según ${autoridad}`,
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
      "Las cifras son las que da cada parte en sus comunicados. Los derribos por región " +
      "solo se cuentan cuando el parte los desglosa.",
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
    titulo: "Línea de tiempo",
    granularidad: "Agrupar por",
    porGranularidad: { dia: "Día", semana: "Semana", mes: "Mes" },
    reproducir: "Reproducir",
    pausar: "Pausar",
    reanudar: "Reanudar",
    detener: "Detener",
    verTodo: "Ver todo",
    periodoBoton: "Periodo",
    desde: "Inicio del periodo",
    hasta: "Fin del periodo",
    periodo: (desde, hasta) => `${desde} – ${hasta}`,
    incidentesPorTramo: "Incidentes",
    lanzamientosPorNoche: "Drones lanzados contra Ucrania",
    instrucciones:
      "Arrastra sobre el histograma para elegir un periodo, o mueve sus dos extremos con las " +
      "flechas del teclado.",
    plegar: "Plegar",
    desplegar: "Desplegar",
    acotado: "periodo acotado",
    maximo: (n) => `máx. ${n}`,
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
                marca: { tipo: "interrupcion_aeroportuaria" },
                texto: [
                  "Un aeropuerto cierra o tiene vuelos desviados, cancelados o retrasados. " +
                    "Si se da, este tipo manda sobre los demás.",
                ],
              },
              {
                termino: "Incursión",
                marca: { tipo: "incursion" },
                texto: [
                  "El dron entra desde fuera del país y su origen está demostrado por " +
                    "rastreo o por restos. Un avistamiento sin origen demostrado nunca es " +
                    "una incursión.",
                ],
              },
              {
                termino: "Sobrevuelo",
                marca: { tipo: "sobrevuelo" },
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
                texto: ["Lo cuentan las noticias. Es el estado inicial de todo incidente."],
              },
              {
                termino: "Confirmado",
                marca: { estado: "confirmado" },
                texto: ["Una autoridad afirma que el incidente ocurrió."],
              },
              {
                termino: "Atribuido",
                marca: { estado: "atribuido" },
                texto: [
                  "Una autoridad señala a un gobierno como responsable. La ficha dice quién " +
                    "atribuye y a quién.",
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
                "siempre con color y con texto.",
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
              "El estado dice si el incidente ocurrió; la presencia de dron dice si se sabe " +
                "que había un dron. Son dos preguntas distintas. La presencia es confirmada " +
                "cuando hay restos, rastreo por radar o una autoridad que lo afirma " +
                "expresamente; no confirmada cuando solo hay avistamientos; y descartada " +
                "cuando una autoridad lo niega.",
            ],
          },
          {
            parrafo: [
              "El caso de Copenhague lo muestra. En septiembre de 2025 el aeropuerto cerró " +
                "varias horas tras el aviso de drones. El cierre es un hecho que la " +
                "autoridad confirma, pero que lo visto fueran drones es otra afirmación: sin " +
                "restos ni rastreo, un incidente puede estar confirmado y tener la presencia " +
                "de dron sin confirmar.",
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
                "siguiente. Más de 12 horas sin actividad abren un incidente nuevo.",
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
                "Confirma el incidente si la autoridad afirma que ocurrió; confirma la " +
                "presencia de dron solo si afirma que había drones, no si habla de avisos " +
                "recibidos; y lo desmiente o atribuye si eso es lo que dice.",
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
                "de los partes diarios de la línea del frente, donde la artillería da focos " +
                "cada día.",
            ],
          },
          {
            parrafo: [
              "Límites: las nubes y el humo tapan el fuego, los satélites pasan pocas veces " +
                "al día y un incendio corto puede no coincidir con ningún paso; la ausencia de " +
                "foco no demuestra nada y no se muestra. Un foco dentro del radio puede ser " +
                "otro fuego cercano, como una quema agrícola. Es un indicio físico, no una " +
                "confirmación.",
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
              "Límites: adsb.lol no ve todos los aviones ni todos los aeropuertos igual. Cada " +
                "día se compara lo visto con los vuelos IFR de referencia de EUROCONTROL; con " +
                "menos de la mitad no se interpreta ningún hueco. Si el tiempo (niebla, " +
                "tormenta, nieve, viento fuerte o pista contaminada en los METAR) explica un " +
                "hueco, se tiene en cuenta. Muchas aeronaves militares vuelan sin emitir, así " +
                "que su ausencia en estos datos no demuestra nada. Un hueco en el tráfico no " +
                "indica su causa: también cierran aeropuertos los globos, los fallos técnicos " +
                "o las huelgas; por eso solo se muestra junto a un incidente conocido.",
            ],
          },
          {
            parrafo: [
              "El dato falta cuando el incidente no es en un aeropuerto con vuelos regulares, " +
                "cuando adsb.lol no publicó ese día o lo publicó incompleto, cuando la cobertura " +
                "de ese aeropuerto ese día es insuficiente, cuando aún no hay cuatro semanas de " +
                "línea base o cuando no se ve ningún hueco que coincida con el incidente. Un " +
                "dato que no se puede medir queda vacío; nunca se rellena.",
            ],
          },
        ],
      },
      {
        id: "sesgo",
        titulo: "Sesgo de cobertura",
        bloques: [
          {
            parrafo: [
              "El número de incidentes de un país depende de cuánto publican sus medios, de " +
                "los idiomas que se leen mejor y de si sus autoridades informan en abierto. " +
                "Un país con más registros no tiene por fuerza más incidentes: tiene más " +
                "noticias. Las cifras no sirven para comparar países sin tener esto en cuenta.",
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
};
