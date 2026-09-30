import { LICENCIA_DATOS, LICENCIA_DATOS_URL, NOMBRE, ORIGEN, REPOSITORIO } from "../sitio.ts";
import type { Textos } from "./tipos.ts";

export const es: Textos = {
  descripcion:
    "Mapa y registro abierto de incidentes con drones en Europa: sobrevuelos, incursiones e " +
    "interrupciones de aeropuertos, con sus fuentes, su estado y su grado de confirmación.",
  saltarAlMapa: "Saltar al mapa",
  cabecera: {
    incidentes: "Incidentes",
    confirmados: "Confirmados",
    paises: "Países",
    contadores: "Cifras del periodo elegido",
    metodologia: "Metodología",
    cambiarIdioma: "Cambiar a inglés",
    otroIdioma: "EN",
  },
  estadoDatos: {
    actualizado: "ACTUALIZADO",
    etiqueta: {
      al_dia: "DATOS AL DÍA",
      con_retraso: "DATOS CON RETRASO",
      desactualizado: "DATOS DESACTUALIZADOS",
    },
    antiguedad: (horas) => (horas < 1 ? "hace menos de 1 h" : `hace ${horas} h`),
    sinDatos: "SIN DATOS",
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
  capas: {
    titulo: "Capas",
    incidentes: "Incidentes",
    ucrania: "Ucrania",
    densidad: "Densidad",
    lista: "Lista",
  },
  leyenda: {
    titulo: "Leyenda",
    forma: "Forma: tipo",
    color: "Color: estado",
    precision: "Área: precisión de la ubicación",
    episodio: "Línea: mismo episodio",
    agrupacion: "Número: incidentes agrupados",
    ucrania: "Ataques por región en el periodo",
    menos: "menos",
    mas: "más",
    densidad: "Densidad de incidentes",
  },
  mapa: {
    etiqueta: "Mapa de Europa con los incidentes del periodo elegido",
    instrucciones:
      "Con el foco en el mapa, las flechas lo desplazan y las teclas más y menos cambian el " +
      "zoom. La lista de incidentes da acceso a las mismas fichas sin usar el mapa.",
    acercar: "Acercar",
    alejar: "Alejar",
    atribucion: "Atribuciones del mapa",
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
    cierre: { si: "Cierre", no: "Sin cierre", desconocido: "Cierre sin confirmar" },
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
  },
  lista: {
    titulo: "Lista de incidentes",
    incidentes: (n) => (n === 1 ? "1 incidente en el periodo" : `${n} incidentes en el periodo`),
    vacia: "Ningún incidente en el periodo elegido.",
    regiones: "Regiones de Ucrania",
  },
  tiempo: {
    titulo: "Línea de tiempo",
    granularidad: "Agrupar por",
    porGranularidad: { dia: "Día", semana: "Semana", mes: "Mes" },
    reproducir: "Reproducir",
    pausar: "Pausar",
    todo: "Todo",
    desde: "Inicio del periodo",
    hasta: "Fin del periodo",
    periodo: (desde, hasta) => `${desde} – ${hasta}`,
    incidentesPorTramo: "Incidentes",
    lanzamientosPorNoche: "Drones lanzados contra Ucrania",
    instrucciones:
      "Arrastra sobre el histograma para elegir un periodo, o mueve sus dos extremos con las " +
      "flechas del teclado.",
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
              "En los contadores, «confirmados» suma los incidentes confirmados y los " +
                "atribuidos. El estado se indica siempre con color y con texto.",
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
    altImagen: "Mapa de Europa con los incidentes con drones registrados",
  },
  regiones: {
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
