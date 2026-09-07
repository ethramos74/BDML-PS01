# =============================================================================
# PROBLEM SET 1 | GEIH 2018, BOGOTA
# 02. Validacion de la base original consolidada (geih2018_original.rds)
# =============================================================================
# OBJETIVO
# Comprobar que la base producida por 01_obtener_datos_GEIH2018.R quedo bien:
# dimensiones, nombres y orden de las 177 variables, columnas de procedencia,
# contenido textual (NA, notacion cientifica, decimales), llaves, codigos
# frente al diccionario y las etiquetas, identidades entre variables
# construidas, y comparabilidad entre bloques de entrenamiento y validacion.
#
# ALCANCE
# - No filtra personas, no imputa, no recodifica y no estima modelos.
# - Cada prueba queda registrada con resultado OK, ADVERTENCIA o ERROR.
#   ERROR: la base no quedo como se esperaba; revisar antes de continuar.
#   ADVERTENCIA: la base esta bien, pero hay un hecho que condiciona la
#   limpieza o el analisis (por ejemplo, la particion por bloques es temporal).
# - Opcionalmente guarda una copia con tipos numericos (geih2018_tipado.rds).
#   Esa copia conserva las 32.177 filas y las 177 variables; solo convierte
#   el texto a numero. La muestra analitica se define en otra etapa.
#
# PIPELINE DE DATOS DEL PROBLEM SET (ejecutar en orden)
# 01_obtener_datos_GEIH2018.R   descarga y consolida
# 02_validar_datos_GEIH2018.R   valida la base y crea la copia tipada (este)
# 03_limpiar_datos_GEIH2018.R   construye la muestra de analisis unica
#
# RUTA DEL PROYECTO
# La raiz PS1_GEIH2018 se resuelve igual en los tres scripts: la variable de
# entorno PS1_GEIH2018_DIR si existe; si no, la subcarpeta PS1_GEIH2018 del
# directorio de trabajo (abra el proyecto de RStudio en "Taller 1").
#
# USO EN RSTUDIO
# 1. Ejecute antes 01_obtener_datos_GEIH2018.R.
# 2. Ejecute este archivo completo con Source.
# 3. Lea el resumen en consola y los archivos en auditoria/validacion/.
#    El objeto validacion_geih$resultados contiene todas las pruebas.
#
# DICCIONARIO DEL DANE
# Las pruebas 5.5, 6.5 y 7.23 usan lo que documenta el catalogo de microdatos
# del DANE (GEIH 2018, catalogo 547): codigos especiales 98/99 en montos,
# 998/999 en antiguedad, categorias admisibles por variable y la construccion
# de las horas. Si el archivo documentacion/diccionario_dane_geih2018_variables.csv
# esta presente, la prueba 6.5 cruza los codigos observados con sus categorias.
#
# Para cargar SOLO las funciones, sin ejecutar:
# options(geih.validar = FALSE)
# source("02_validar_datos_GEIH2018.R", encoding = "UTF-8")
# Despues puede ejecutar: validacion_geih <- validar_geih(config_val)
#
# SALIDAS, dentro de auditoria/validacion/:
# resultados_validacion.csv   Una fila por prueba (id, categoria, resultado).
# perfil_columnas.csv         Perfil textual y numerico de cada columna.
# codigos_observados.csv      Valores observados de las variables codificadas.
# mes_por_bloque.csv          Tabla mes x bloque (muestra el orden temporal).
# muestra_por_bloque.csv      Conteos de ocupados e ingresos por bloque.
# comparabilidad_particion.csv Medias por particion entrenamiento/validacion.
# ingresos_faltantes_relab.csv Ocupados 18+ sin y_total_m, por relab.
# faltantes_predictores.csv   NA de los predictores candidatos en la muestra base.
# formal_vs_cotPension.csv    Cruce informativo de formalidad.
# esquema_tipado.csv          Tipo de cada columna en la copia tipada.
# Y, si exportar_tipado = TRUE: datos/intermedios/geih2018_tipado.rds
#
# Dependencias: solo R base (probado el diseno con R >= 4.1).
# =============================================================================

# 1. CONFIGURACION --------------------------------------------------------------

# Raiz del proyecto compartida por los scripts 01, 02 y 03 (ver encabezado).
carpeta_proyecto_geih <- function() {
  ruta <- Sys.getenv("PS1_GEIH2018_DIR", unset = "")
  if (nzchar(ruta)) ruta else file.path(getwd(), "PS1_GEIH2018")
}

config_val <- list(
  carpeta_proyecto = carpeta_proyecto_geih(),
  archivo_datos = NULL,          # NULL: <carpeta_proyecto>/datos/brutos/geih2018_original.rds
  carpeta_documentacion = NULL,  # NULL: <carpeta_proyecto>/documentacion
  carpeta_salida = NULL,         # NULL: <carpeta_proyecto>/auditoria/validacion
  carpeta_intermedios = NULL,    # NULL: <carpeta_proyecto>/datos/intermedios
  n_observaciones_esperadas = 32177L,
  n_variables_esperadas = 177L,
  bloques_esperados = 1:10,
  bloques_entrenamiento = 1:7,
  bloques_validacion = 8:10,
  edad_minima_muestra = 18,      # Solo para el panorama informativo de la muestra.
  exportar_tipado = TRUE,
  detener_si_error = FALSE       # TRUE: stop() al final si alguna prueba da ERROR.
)

# 2. REFERENCIAS ESPERADAS ------------------------------------------------------

# Las 177 variables originales, en el orden exacto en que las publica el sitio.
variables_esperadas <- c(
  "directorio", "secuencia_p", "orden", "clase", "dominio", "mes", "estrato1",
  "sex", "age", "p6050", "p6090", "p6100", "p6210", "p6210s1", "p6240",
  "oficio", "p6426", "relab", "p6500", "p6510", "p6510s1", "p6510s2", "p6545",
  "p6545s1", "p6545s2", "p6580", "p6580s1", "p6580s2", "p6585s1", "p6585s1a1",
  "p6585s1a2", "p6585s2", "p6585s2a1", "p6585s2a2", "p6585s3", "p6585s3a1",
  "p6585s3a2", "p6585s4", "p6585s4a1", "p6585s4a2", "p6590", "p6590s1",
  "p6600", "p6600s1", "p6610", "p6610s1", "p6620", "p6620s1", "p6630s1",
  "p6630s1a1", "p6630s2", "p6630s2a1", "p6630s3", "p6630s3a1", "p6630s4",
  "p6630s4a1", "p6630s6", "p6630s6a1", "p6750", "p6760", "p550",
  "hoursWorkUsual", "p6870", "p6920", "p7040", "hoursWorkActualSecondJob",
  "p7050", "p7070", "p7090", "p7110", "p7120", "p7140s1", "p7140s2", "p7150",
  "p7160", "p7310", "p7350", "p7422", "p7422s1", "p7472", "p7472s1", "p7495",
  "p7500s1", "p7500s1a1", "p7500s2", "p7500s2a1", "p7500s3", "p7500s3a1",
  "p7505", "p7510s1", "p7510s1a1", "p7510s2", "p7510s2a1", "p7510s3",
  "p7510s3a1", "p7510s5", "p7510s5a1", "p7510s6", "p7510s6a1", "p7510s7",
  "p7510s7a1", "pet", "ina", "impa", "isa", "ie", "imdi", "iof1", "iof2",
  "iof3h", "iof3i", "iof6", "cclasnr2", "cclasnr3", "cclasnr4", "cclasnr5",
  "cclasnr6", "cclasnr7", "cclasnr8", "cclasnr11", "impaes", "isaes", "iees",
  "imdies", "iof1es", "iof2es", "iof3hes", "iof3ies", "iof6es", "ingtotob",
  "ingtotes", "ingtot", "fex_c", "depto", "fex_dpto", "fweight",
  "maxEducLevel", "college", "regSalud", "cotPension", "wap", "ocu", "dsi",
  "pea", "inac", "totalHoursWorked", "formal", "informal", "cuentaPropia",
  "microEmpresa", "sizeFirm", "y_salary_m", "y_salary_m_hu", "y_ingLab_m",
  "y_horasExtras_m", "y_especie_m", "y_vivienda_m", "y_otros_m",
  "y_auxilioAliment_m", "y_auxilioTransp_m", "y_subFamiliar_m",
  "y_subEducativo_m", "y_primas_m", "y_bonificaciones_m",
  "y_primaServicios_m", "y_primaNavidad_m", "y_primaVacaciones_m",
  "y_viaticos_m", "y_accidentes_m", "y_salarySec_m", "y_ingLab_m_ha",
  "y_gananciaNeta_m", "y_gananciaNetaAgro_m", "y_gananciaIndep_m",
  "y_gananciaIndep_m_hu", "y_total_m", "y_total_m_ha"
)

# Columnas de procedencia que agrega el script 01 y su posicion esperada.
variables_procedencia <- c("fila_en_bloque", "chunk", "url_origen", "muestra_ps3")

# Conjuntos de valores admisibles segun el diccionario y labels.html.
# Los codigos 9 ("N/A", "no sabe") se admiten porque las etiquetas los listan;
# la prueba informa si aparecen o si la fuente ya los dejo como NA.
conjuntos_esperados <- list(
  clase = 1, depto = 11, sex = 0:1, mes = 1:12, estrato1 = 1:6, p6050 = 1:9,
  p6090 = c(1, 2, 9), p6100 = c(1:3, 9), p6210 = c(1:6, 9), p6240 = 1:6,
  oficio = 1:99, relab = 1:9, p6870 = 1:9, p6920 = 1:3, p7040 = 1:2,
  maxEducLevel = c(1:7, 9), college = 0:1, regSalud = c(1:3, 9),
  cotPension = c(1:3, 9), wap = 0:1, ocu = 0:1, dsi = 0:1, pea = 0:1,
  inac = 0:1, pet = 1, ina = 1, formal = 0:1, informal = 0:1,
  cuentaPropia = 0:1, microEmpresa = 0:1, sizeFirm = 1:5
)

# Variables que el sitio publica vacias para Bogota (no hay actividad agricola).
vacias_esperadas <- c("p550", "y_gananciaNetaAgro_m")

# 3. UTILIDADES -----------------------------------------------------------------

resolver_rutas <- function(cfg) {
  raiz <- cfg$carpeta_proyecto
  if (is.null(cfg$archivo_datos)) {
    cfg$archivo_datos <- file.path(raiz, "datos", "brutos", "geih2018_original.rds")
  }
  if (is.null(cfg$carpeta_documentacion)) {
    cfg$carpeta_documentacion <- file.path(raiz, "documentacion")
  }
  if (is.null(cfg$carpeta_salida)) {
    cfg$carpeta_salida <- file.path(raiz, "auditoria", "validacion")
  }
  if (is.null(cfg$carpeta_intermedios)) {
    cfg$carpeta_intermedios <- file.path(raiz, "datos", "intermedios")
  }
  cfg
}

escribir_csv <- function(datos, archivo) {
  utils::write.csv(datos, archivo, row.names = FALSE, fileEncoding = "UTF-8",
                   na = "NA")
}

fmt <- function(x) formatC(round(x), format = "d", big.mark = ",")

# "NA" literal -> NA; el resto se convierte con as.numeric (admite 7e+05).
a_numero <- function(x) {
  x[x == "NA"] <- NA_character_
  suppressWarnings(as.numeric(x))
}

# Igualdad elemento a elemento tolerante a NA: NA == NA cuenta como igual.
igual_na <- function(a, b, tol = 0, relativa = FALSE) {
  ambos_na <- is.na(a) & is.na(b)
  ninguno_na <- !is.na(a) & !is.na(b)
  dif <- abs(a - b)
  if (relativa) dif <- dif / pmax(abs(a), abs(b), 1)
  iguales <- ninguno_na & !is.na(dif) & dif <= tol
  ambos_na | iguales
}

# Registro de pruebas -----------------------------------------------------------

crear_bitacora <- function() {
  b <- new.env()
  b$filas <- list()
  b
}

registrar <- function(bitacora, id, categoria, prueba, resultado, detalle = "") {
  stopifnot(resultado %in% c("OK", "ADVERTENCIA", "ERROR"))
  bitacora$filas[[length(bitacora$filas) + 1L]] <- data.frame(
    id = id, categoria = categoria, prueba = prueba, resultado = resultado,
    detalle = detalle, stringsAsFactors = FALSE
  )
  marca <- switch(resultado, OK = "[OK]  ", ADVERTENCIA = "[ADV] ", ERROR = "[ERR] ")
  message(marca, id, " ", prueba, if (nzchar(detalle)) paste0(" | ", detalle) else "")
  invisible(NULL)
}

# Registra OK o el resultado alternativo segun una condicion logica.
comprobar <- function(bitacora, id, categoria, prueba, condicion, detalle = "",
                      si_falla = "ERROR") {
  ok <- isTRUE(condicion)
  registrar(bitacora, id, categoria, prueba, if (ok) "OK" else si_falla, detalle)
  invisible(ok)
}

resumir_valores <- function(x, maximo = 12L) {
  x <- sort(unique(x))
  if (length(x) > maximo) {
    paste0(paste(x[seq_len(maximo)], collapse = ", "), ", ... (", length(x), " valores)")
  } else {
    paste(x, collapse = ", ")
  }
}

tabla_a_df <- function(tab, nombre_fila) {
  # Convierte una tabla de dos entradas en data.frame; los NA de los nombres
  # (useNA = "ifany") pasan a la cadena "NA" para no romper row.names.
  filas <- dimnames(tab)[[1L]]
  columnas <- dimnames(tab)[[2L]]
  filas[is.na(filas)] <- "NA"
  columnas[is.na(columnas)] <- "NA"
  df <- as.data.frame(matrix(as.vector(tab), nrow = nrow(tab)), stringsAsFactors = FALSE)
  names(df) <- columnas
  df <- cbind(setNames(data.frame(filas, stringsAsFactors = FALSE), nombre_fila), df)
  rownames(df) <- NULL
  df
}

# 4. BLOQUES DE PRUEBAS ---------------------------------------------------------

validar_estructura <- function(datos, cfg, b) {
  cat_ <- "1. Estructura"
  comprobar(b, "1.1", cat_, "El objeto es un data.frame",
            is.data.frame(datos), paste("clase:", paste(class(datos), collapse = "/")))
  comprobar(b, "1.2", cat_, "Numero de observaciones",
            nrow(datos) == cfg$n_observaciones_esperadas,
            paste0("observadas: ", fmt(nrow(datos)), "; esperadas: ",
                   fmt(cfg$n_observaciones_esperadas)))
  n_esp <- cfg$n_variables_esperadas + length(variables_procedencia)
  comprobar(b, "1.3", cat_, "Numero de columnas (177 originales + 4 de procedencia)",
            ncol(datos) == n_esp, paste0("observadas: ", ncol(datos), "; esperadas: ", n_esp))

  nombres <- names(datos)
  comprobar(b, "1.4", cat_, "Sin nombres de columna vacios o repetidos",
            !anyDuplicated(nombres) && all(nzchar(nombres)))

  faltan <- setdiff(variables_esperadas, nombres)
  sobran <- setdiff(nombres, c(variables_esperadas, variables_procedencia))
  comprobar(b, "1.5", cat_, "Las 177 variables originales estan presentes",
            length(faltan) == 0L,
            if (length(faltan)) paste("faltan:", paste(faltan, collapse = ", ")) else "")
  comprobar(b, "1.6", cat_, "No hay columnas inesperadas",
            length(sobran) == 0L,
            if (length(sobran)) paste("sobran:", paste(sobran, collapse = ", ")) else "",
            si_falla = "ADVERTENCIA")

  originales <- nombres[nombres %in% variables_esperadas]
  comprobar(b, "1.7", cat_, "Las variables originales conservan el orden del sitio",
            identical(originales, variables_esperadas),
            if (!identical(originales, variables_esperadas)) {
              paste("primera diferencia en posicion",
                    which(originales != variables_esperadas)[1L])
            } else "")

  posiciones_ok <- identical(nombres[1L], "fila_en_bloque") &&
    identical(utils::tail(nombres, 3L), c("chunk", "url_origen", "muestra_ps3"))
  comprobar(b, "1.8", cat_, "Columnas de procedencia en su posicion (primera y tres ultimas)",
            posiciones_ok, paste("procedencia presente:",
                                 paste(intersect(variables_procedencia, nombres), collapse = ", ")))
  invisible(NULL)
}

validar_procedencia <- function(datos, cfg, b) {
  cat_ <- "2. Procedencia y bloques"
  chunk <- datos$chunk
  comprobar(b, "2.1", cat_, "chunk es entero y toma los valores 1 a 10",
            is.integer(chunk) && identical(sort(unique(chunk)), as.integer(cfg$bloques_esperados)),
            paste("valores:", resumir_valores(chunk)))

  conteo <- table(chunk)
  comprobar(b, "2.2", cat_, "Cada bloque tiene entre 3.217 y 3.218 observaciones",
            all(conteo >= 3217L & conteo <= 3218L) && sum(conteo) == cfg$n_observaciones_esperadas,
            paste(names(conteo), as.integer(conteo), sep = "=", collapse = "; "))

  esperada <- ifelse(chunk %in% cfg$bloques_entrenamiento, "entrenamiento",
                     ifelse(chunk %in% cfg$bloques_validacion, "validacion", NA_character_))
  comprobar(b, "2.3", cat_, "muestra_ps3: entrenamiento = bloques 1-7, validacion = bloques 8-10",
            identical(as.character(datos$muestra_ps3), esperada),
            paste("conteo:", paste(names(table(datos$muestra_ps3)),
                                   as.integer(table(datos$muestra_ps3)), sep = "=", collapse = "; ")))

  url <- as.character(datos$url_origen)
  url_esperada <- sprintf("geih_page_%d.html", chunk)
  comprobar(b, "2.4", cat_, "url_origen apunta a geih_page_<chunk>.html en cada fila",
            all(basename(url) == url_esperada) && length(unique(url)) == length(cfg$bloques_esperados),
            paste("urls distintas:", length(unique(url))))

  fila <- a_numero(datos$fila_en_bloque)
  secuencia_ok <- all(vapply(split(fila, chunk), function(f) {
    identical(as.numeric(f), as.numeric(seq_along(f)))
  }, logical(1)))
  comprobar(b, "2.5", cat_, "fila_en_bloque es 1..n consecutivo dentro de cada bloque",
            secuencia_ok)
  invisible(NULL)
}

perfilar_columnas <- function(datos, originales) {
  patron_numero <- "^-?([0-9]+\\.?[0-9]*|\\.[0-9]+)([eE][-+]?[0-9]+)?$"
  filas <- lapply(originales, function(v) {
    x <- datos[[v]]
    es_na_real <- is.na(x)
    es_na_texto <- !es_na_real & x == "NA"
    es_blanco <- !es_na_real & !nzchar(trimws(x))
    tiene_espacios <- !es_na_real & x != trimws(x)
    presente <- x[!es_na_real & !es_na_texto & !es_blanco]
    numerico <- grepl(patron_numero, presente)
    cientifica <- grepl("[eE]", presente)
    decimal <- grepl("\\.", presente) & !cientifica
    valores <- a_numero(presente)
    data.frame(
      variable = v,
      tipo_R = class(x)[1L],
      n_na_real = sum(es_na_real),
      n_na_texto = sum(es_na_texto),
      n_blancos = sum(es_blanco),
      n_con_espacios = sum(tiene_espacios),
      n_presentes = length(presente),
      n_no_numericos = sum(!numerico),
      n_notacion_cientifica = sum(cientifica),
      n_con_decimales = sum(decimal),
      n_valores_unicos = length(unique(presente)),
      minimo = if (any(numerico)) min(valores[numerico], na.rm = TRUE) else NA_real_,
      maximo = if (any(numerico)) max(valores[numerico], na.rm = TRUE) else NA_real_,
      ejemplo_no_numerico = if (any(!numerico)) presente[!numerico][1L] else "",
      ejemplo_cientifica = if (any(cientifica)) presente[cientifica][1L] else "",
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, filas)
}

validar_contenido <- function(datos, originales, cfg, b) {
  cat_ <- "3. Contenido textual y conversion"
  perfil <- perfilar_columnas(datos, originales)

  comprobar(b, "3.1", cat_, "Las 177 variables originales son de tipo character (como las guardo el script 01)",
            all(perfil$tipo_R == "character"),
            paste("tipos:", paste(names(table(perfil$tipo_R)), as.integer(table(perfil$tipo_R)),
                                  sep = "=", collapse = "; ")))
  comprobar(b, "3.2", cat_, "Los faltantes vienen como texto 'NA' (no hay NA reales, blancos ni espacios)",
            sum(perfil$n_na_real) == 0L && sum(perfil$n_blancos) == 0L && sum(perfil$n_con_espacios) == 0L,
            paste0("NA reales: ", sum(perfil$n_na_real), "; blancos: ", sum(perfil$n_blancos),
                   "; con espacios: ", sum(perfil$n_con_espacios)))

  no_num <- perfil$variable[perfil$n_no_numericos > 0L]
  comprobar(b, "3.3", cat_, "Todo valor presente es numerico, salvo dominio (= 'BOGOTA')",
            identical(no_num, "dominio"),
            paste("columnas con texto no numerico:", paste(no_num, collapse = ", ")))

  # Conversion: as.numeric no debe producir NA adicionales ni perder precision
  # en la notacion cientifica (el sitio la usa para cifras redondas: 7e+05).
  perdidas <- vapply(originales[originales != "dominio"], function(v) {
    x <- datos[[v]]
    as.numeric(sum(is.na(a_numero(x))) - sum(x == "NA"))
  }, numeric(1))
  comprobar(b, "3.4", cat_, "as.numeric convierte sin crear NA adicionales",
            all(perdidas == 0),
            if (any(perdidas != 0)) paste("problemas en:", paste(names(perdidas)[perdidas != 0], collapse = ", ")) else "")

  con_cientifica <- perfil$variable[perfil$n_notacion_cientifica > 0L]
  enteras <- vapply(con_cientifica, function(v) {
    x <- datos[[v]]
    x <- x[grepl("[eE]", x)]
    cifras <- nchar(gsub("[^0-9]", "", sub("[eE].*$", "", x)))
    valores <- a_numero(x)
    all(cifras <= 7L) && all(is.finite(valores)) && all(valores == round(valores))
  }, logical(1))
  comprobar(b, "3.5", cat_, "La notacion cientifica corresponde a enteros con <= 7 cifras (se recupera exacta)",
            all(enteras),
            paste0(length(con_cientifica), " columnas la usan; total de celdas: ",
                   fmt(sum(perfil$n_notacion_cientifica))))

  vacias <- perfil$variable[perfil$n_presentes == 0L]
  comprobar(b, "3.6", cat_, "Columnas totalmente vacias: solo p550 y y_gananciaNetaAgro_m (sin agro en Bogota)",
            setequal(vacias, vacias_esperadas),
            paste("vacias:", paste(vacias, collapse = ", ")), si_falla = "ADVERTENCIA")

  con_decimales <- perfil$variable[perfil$n_con_decimales > 0L]
  registrar(b, "3.7", cat_, "Columnas con decimales (informativo)", "OK",
            paste0(length(con_decimales), " columnas; entre ellas fex_c, fex_dpto, los ingresos por hora ",
                   "y los agregados de ingreso (y_total_m con precision de punto flotante simple)"))
  perfil
}

validar_llaves <- function(num, datos, b) {
  cat_ <- "4. Llaves y constantes"
  llave <- paste(datos$directorio, datos$secuencia_p, datos$orden, sep = "-")
  comprobar(b, "4.1", cat_, "directorio + secuencia_p + orden identifica una unica persona",
            !anyDuplicated(llave),
            paste0("viviendas: ", fmt(length(unique(datos$directorio))), "; hogares: ",
                   fmt(length(unique(paste(datos$directorio, datos$secuencia_p)))),
                   "; duplicados: ", sum(duplicated(llave))))
  comprobar(b, "4.2", cat_, "clase = 1 (urbano), dominio = BOGOTA y depto = 11 son constantes",
            all(num$clase == 1) && all(datos$dominio == "BOGOTA") && all(num$depto == 11),
            "no sirven como controles: no varian en la muestra")
  comprobar(b, "4.3", cat_, "directorio esta ordenado de forma creciente a lo largo de los bloques",
            !is.unsorted(num$directorio),
            "los bloques siguen el orden de la encuesta (vivienda y mes)", si_falla = "ADVERTENCIA")
  comprobar(b, "4.4", cat_, "Los factores de expansion son positivos y sin faltantes",
            all(!is.na(num$fex_c)) && all(num$fex_c > 0) && all(!is.na(num$fex_dpto)) && all(num$fex_dpto > 0),
            paste0("fex_c: min ", round(min(num$fex_c), 2), ", max ", round(max(num$fex_c), 2),
                   "; suma (poblacion expandida): ", fmt(sum(num$fex_c))))
  invisible(NULL)
}

validar_codigos <- function(num, cfg, b) {
  cat_ <- "5. Codificaciones"
  filas <- list()
  for (v in names(conjuntos_esperados)) {
    x <- num[[v]]
    presentes <- x[!is.na(x)]
    esperado <- conjuntos_esperados[[v]]
    fuera <- sort(unique(presentes[!presentes %in% esperado]))
    filas[[v]] <- data.frame(
      variable = v, n_presentes = length(presentes), n_na = sum(is.na(x)),
      valores_observados = resumir_valores(presentes, 20L),
      valores_esperados = resumir_valores(esperado, 20L),
      fuera_de_rango = paste(fuera, collapse = ", "),
      stringsAsFactors = FALSE
    )
    if (length(fuera)) {
      registrar(b, paste0("5.", v), cat_, paste0(v, ": valores fuera del conjunto esperado"), "ERROR",
                paste("valores:", paste(fuera, collapse = ", ")))
    }
  }
  codigos <- do.call(rbind, filas)
  rownames(codigos) <- NULL
  comprobar(b, "5.1", cat_, "Todas las variables codificadas toman solo valores admisibles",
            all(!nzchar(codigos$fuera_de_rango)),
            paste(nrow(codigos), "variables revisadas"))

  con_nueve <- c("maxEducLevel", "regSalud", "cotPension", "p6210")
  usa_nueve <- vapply(con_nueve, function(v) any(num[[v]] == 9, na.rm = TRUE), logical(1))
  registrar(b, "5.2", cat_, "Codigo 9 ('N/A' / 'no sabe') en variables ordinales (informativo)", "OK",
            paste0("aparece en: ", if (any(usa_nueve)) paste(con_nueve[usa_nueve], collapse = ", ") else "ninguna",
                   "; en las demas la fuente ya lo dejo como NA. Tratarlo como NA, no como categoria"))

  comprobar(b, "5.3", cat_, "age es entera y esta entre 0 y 110",
            all(num$age == round(num$age)) && all(num$age >= 0 & num$age <= 110),
            paste0("min ", min(num$age), ", max ", max(num$age)))

  horas <- num$totalHoursWorked
  comprobar(b, "5.4", cat_, "totalHoursWorked (cuando existe) esta entre 1 y 168",
            all(horas[!is.na(horas)] >= 1 & horas[!is.na(horas)] <= 168),
            paste0("min ", min(horas, na.rm = TRUE), ", max ", max(horas, na.rm = TRUE),
                   "; > 126 horas (18 al dia): ", sum(horas > 126, na.rm = TRUE)))

  # Codigos especiales del cuestionario DANE que NO deben sobrevivir como valores:
  # montos: 98 = recibio pero no sabe el monto, 99 = no sabe si recibio;
  # p6426: 998 = mas de 999 meses, 999 = no sabe; horas segundo empleo: 98/99.
  montos <- c("p6500", "p6510s1", "p6545s1", "p6580s1", "p6585s1a1", "p6585s2a1",
              "p6585s3a1", "p6585s4a1", "p6590s1", "p6600s1", "p6610s1", "p6620s1",
              "p6630s1a1", "p6630s2a1", "p6630s3a1", "p6630s4a1", "p6630s6a1",
              "p6750", "p7070", "p7422s1", "p7472s1", "p7500s1a1", "p7500s2a1",
              "p7500s3a1", "p7510s1a1", "p7510s2a1", "p7510s3a1", "p7510s5a1",
              "p7510s6a1", "p7510s7a1")
  centinelas <- c(
    vapply(montos, function(v) as.numeric(sum(num[[v]] %in% c(98, 99))), numeric(1)),
    p6426 = sum(num$p6426 %in% c(998, 999)),
    hoursWorkActualSecondJob = sum(num$hoursWorkActualSecondJob %in% c(98, 99))
  )
  comprobar(b, "5.5", cat_, "Sin codigos especiales del DANE (98/99 en montos, 998/999 en antiguedad)",
            all(centinelas == 0),
            if (any(centinelas > 0)) {
              paste("presentes en:", paste(names(centinelas)[centinelas > 0],
                                           centinelas[centinelas > 0], sep = "=", collapse = "; "))
            } else paste(length(centinelas), "variables revisadas"), si_falla = "ADVERTENCIA")
  codigos
}

validar_documentacion <- function(datos, num, cfg, b) {
  cat_ <- "6. Diccionario y etiquetas"
  archivo_dic <- file.path(cfg$carpeta_documentacion, "diccionario.rds")
  archivo_eti <- file.path(cfg$carpeta_documentacion, "etiquetas.rds")

  if (file.exists(archivo_dic)) {
    dic <- readRDS(archivo_dic)
    nombres_dic <- trimws(as.character(dic$Variable))
    truncados <- grepl("~", nombres_dic, fixed = TRUE)
    exactos <- nombres_dic[!truncados]
    faltan <- setdiff(exactos, names(datos))
    comprobar(b, "6.1", cat_, "Toda variable del diccionario (nombre completo) existe en la base",
              length(faltan) == 0L,
              if (length(faltan)) paste("faltan:", paste(faltan, collapse = ", ")) else
                paste(length(exactos), "nombres exactos verificados"))
    # Los nombres con "~" vienen truncados por Stata: prefijo ~ ultimo caracter.
    resueltos <- vapply(nombres_dic[truncados], function(n) {
      partes <- strsplit(n, "~", fixed = TRUE)[[1L]]
      candidatos <- names(datos)[startsWith(names(datos), partes[1L]) &
                                   endsWith(names(datos), partes[2L])]
      if (length(candidatos) == 1L) candidatos else NA_character_
    }, character(1))
    comprobar(b, "6.2", cat_, "Cada nombre truncado del diccionario (con '~') corresponde a una unica variable",
              all(!is.na(resueltos)),
              paste0(sum(truncados), " truncados; sin resolver: ",
                     paste(names(resueltos)[is.na(resueltos)], collapse = ", ")))
    sin_doc <- setdiff(variables_esperadas, c(exactos, resueltos))
    comprobar(b, "6.3", cat_, "Toda variable de la base esta documentada en el diccionario",
              length(sin_doc) == 0L,
              if (length(sin_doc)) paste("sin documentar:", paste(sin_doc, collapse = ", ")) else "",
              si_falla = "ADVERTENCIA")
  } else {
    registrar(b, "6.1", cat_, "diccionario.rds no encontrado en documentacion/", "ADVERTENCIA",
              "se omite el cruce de nombres con el diccionario")
  }

  if (file.exists(archivo_eti)) {
    eti <- readRDS(archivo_eti)
    eti$Variable <- trimws(as.character(eti$Variable))
    eti$values <- suppressWarnings(as.numeric(trimws(as.character(eti$values))))
    for (v in unique(eti$Variable)) {
      if (!v %in% names(num)) next
      admisibles <- eti$values[eti$Variable == v]
      presentes <- unique(num[[v]][!is.na(num[[v]])])
      fuera <- sort(presentes[!presentes %in% admisibles])
      comprobar(b, paste0("6.4.", v), cat_,
                paste0(v, ": todos los valores observados tienen etiqueta en labels.html"),
                length(fuera) == 0L,
                if (length(fuera)) paste("sin etiqueta:", paste(fuera, collapse = ", ")) else
                  paste0(length(presentes), " valores observados de ", length(admisibles), " etiquetados"),
                si_falla = "ADVERTENCIA")
    }
  } else {
    registrar(b, "6.4", cat_, "etiquetas.rds no encontrado en documentacion/", "ADVERTENCIA",
              "se omite el cruce de codigos con las etiquetas")
  }

  # Cruce con el catalogo del DANE (archivo generado a partir de
  # microdatos.dane.gov.co/index.php/catalog/547/data-dictionary).
  archivo_dane <- file.path(cfg$carpeta_documentacion, "diccionario_dane_geih2018_variables.csv")
  if (file.exists(archivo_dane)) {
    dane <- utils::read.csv(archivo_dane, stringsAsFactors = FALSE, encoding = "UTF-8",
                            fileEncoding = "UTF-8-BOM")
    # Nombres del DANE que el sitio del curso publica con otro nombre.
    alias_dane <- c(P6020 = "sex", P6040 = "age", P4030S1A1 = "estrato1", P6430 = "relab",
                    OFICIO = "oficio", P6800 = "hoursWorkUsual",
                    P7045 = "hoursWorkActualSecondJob", DPTO = "depto", MES = "mes")
    n_cruzadas <- 0L
    for (i in seq_len(nrow(dane))) {
      nombre_dane <- toupper(trimws(dane$variable[i]))
      nombre <- if (nombre_dane %in% names(alias_dane)) alias_dane[[nombre_dane]] else tolower(nombre_dane)
      categorias <- trimws(dane$categorias[i])
      # sex, ocu y dsi se excluyen: el curso las recodifica (1/2 -> 1/0; 1/NA -> 1/0).
      if (!nombre %in% names(num) || !nzchar(categorias) || nombre %in% c("sex", "ocu", "dsi")) next
      admisibles <- suppressWarnings(as.numeric(sub("=.*$", "", trimws(strsplit(categorias, ";")[[1L]]))))
      admisibles <- admisibles[!is.na(admisibles)]
      if (length(admisibles) == 0L) next
      presentes <- unique(num[[nombre]][!is.na(num[[nombre]])])
      fuera <- sort(presentes[!presentes %in% admisibles])
      n_cruzadas <- n_cruzadas + 1L
      if (length(fuera) > 0L) {
        registrar(b, paste0("6.5.", nombre), cat_,
                  paste0(nombre, ": valores fuera de las categorias del DANE (", nombre_dane, ")"),
                  "ADVERTENCIA", paste("sin categoria DANE:", paste(fuera, collapse = ", ")))
      }
    }
    registrar(b, "6.5", cat_, "Codigos observados dentro de las categorias documentadas por el DANE", "OK",
              paste(n_cruzadas, "variables discretas cruzadas con el catalogo 547 (sex, ocu y dsi se excluyen: el curso las recodifica)"))
  } else {
    registrar(b, "6.5", cat_, "diccionario_dane_geih2018_variables.csv no encontrado en documentacion/",
              "ADVERTENCIA", "se omite el cruce con las categorias del DANE")
  }
  invisible(NULL)
}

validar_consistencia <- function(num, b) {
  cat_ <- "7. Consistencia de variables construidas"
  ocupado <- num$ocu == 1
  n_dif <- function(cond) sum(!cond)

  # Condicion de actividad
  comprobar(b, "7.1", cat_, "pea = 1 exactamente cuando ocu = 1 o dsi = 1",
            all(num$pea == as.numeric(num$ocu == 1 | num$dsi == 1)))
  comprobar(b, "7.2", cat_, "ocu + dsi + inac = wap (ocupado, desocupado e inactivo particionan la PET)",
            all(num$ocu + num$dsi + num$inac == num$wap))
  comprobar(b, "7.3", cat_, "pet (1/NA) coincide con wap (1/0) e ina (1/NA) con inac (1/0)",
            all(igual_na(num$pet, ifelse(num$wap == 1, 1, NA))) &&
              all(igual_na(num$ina, ifelse(num$inac == 1, 1, NA))))

  # Variables de empleo solo para ocupados
  laborales <- c("relab", "oficio", "totalHoursWorked", "hoursWorkUsual", "sizeFirm",
                 "microEmpresa", "formal", "informal", "p6426", "p6870")
  solo_ocupados <- vapply(laborales, function(v) all(is.na(num[[v]]) == !ocupado), logical(1))
  comprobar(b, "7.4", cat_, "relab, oficio, horas, sizeFirm, formal... existen exactamente para ocu = 1",
            all(solo_ocupados),
            if (!all(solo_ocupados)) paste("fallan:", paste(laborales[!solo_ocupados], collapse = ", ")) else
              paste0("ocupados: ", fmt(sum(ocupado))))

  comprobar(b, "7.5", cat_, "cuentaPropia = 1 exactamente cuando relab = 4",
            all(num$cuentaPropia == as.numeric(!is.na(num$relab) & num$relab == 4)))
  recod <- c(1, 2, 2, 3, 4, 4, 4, 5, 5)[num$p6870]
  comprobar(b, "7.6", cat_, "sizeFirm recodifica p6870 (1; 2-3; 4; 5-7; 8-9)",
            all(igual_na(num$sizeFirm, recod)), paste("diferencias:", n_dif(igual_na(num$sizeFirm, recod))))
  comprobar(b, "7.7", cat_, "microEmpresa = 1 exactamente cuando sizeFirm es 1 o 2",
            all(igual_na(num$microEmpresa, ifelse(is.na(num$sizeFirm), NA, as.numeric(num$sizeFirm <= 2)))))
  comprobar(b, "7.8", cat_, "cotPension es identica a p6920",
            all(igual_na(num$cotPension, num$p6920)))
  comprobar(b, "7.9", cat_, "regSalud es p6100 con el codigo 9 convertido a NA",
            all(igual_na(num$regSalud, ifelse(!is.na(num$p6100) & num$p6100 == 9, NA, num$p6100))))
  comprobar(b, "7.10", cat_, "formal + informal = 1 para todo ocupado",
            all((num$formal + num$informal)[ocupado] == 1))

  # Educacion
  mapa <- c(1, 2, NA, 5, 6, 7)          # p6210 1,2,4,5,6 -> maxEducLevel; 3 -> 3 o 4
  esperado_educ <- mapa[num$p6210]
  educ_ok <- is.na(num$maxEducLevel) |
    (!is.na(num$p6210) & num$p6210 == 3 & num$maxEducLevel %in% c(3, 4)) |
    igual_na(num$maxEducLevel, esperado_educ)
  comprobar(b, "7.11", cat_, "maxEducLevel es coherente con p6210 (3 -> primaria incompleta/completa)",
            all(educ_ok), paste("incoherencias:", n_dif(educ_ok)))
  coincide_terciaria <- mean(num$college == as.numeric(!is.na(num$maxEducLevel) & num$maxEducLevel == 7))
  coincide_media <- mean(num$college == as.numeric(!is.na(num$maxEducLevel) & num$maxEducLevel == 6))
  comprobar(b, "7.12", cat_, "college = 1 corresponde a educacion terciaria (maxEducLevel = 7), como dice el diccionario",
            coincide_terciaria == 1,
            paste0("coincide con terciaria en ", round(100 * coincide_terciaria, 1), "% de las filas; ",
                   "coincide con maxEducLevel = 6 (media / secundaria completa) en ",
                   round(100 * coincide_media, 1), "%. Si no es 100% terciaria, NO usar college: ",
                   "construir la dummy desde maxEducLevel == 7 o p6210 == 6"),
            si_falla = "ADVERTENCIA")

  # Ingresos
  y <- num$y_total_m
  yl <- num$y_ingLab_m
  yg <- num$y_gananciaIndep_m
  suma <- ifelse(is.na(yl) & is.na(yg), NA, ifelse(is.na(yl), 0, yl) + ifelse(is.na(yg), 0, yg))
  comprobar(b, "7.13", cat_, "y_total_m = y_ingLab_m + y_gananciaIndep_m (NA solo si ambos faltan)",
            all(igual_na(y, suma, tol = 1)), paste("diferencias:", n_dif(igual_na(y, suma, tol = 1))))
  comprobar(b, "7.14", cat_, "Nadie tiene a la vez ingreso asalariado e ingreso independiente",
            !any(!is.na(yl) & !is.na(yg)),
            paste0("con y_ingLab_m: ", fmt(sum(!is.na(yl))), "; con y_gananciaIndep_m: ", fmt(sum(!is.na(yg)))))
  comprobar(b, "7.15", cat_, "y_total_m existe solo para ocupados y nunca vale cero",
            all(is.na(y[!ocupado])) && !any(y == 0, na.rm = TRUE),
            paste0("ocupados sin y_total_m: ", fmt(sum(ocupado & is.na(y))),
                   "; ceros: ", sum(y == 0, na.rm = TRUE)))
  comprobar(b, "7.16", cat_, "y_ingLab_m >= y_salary_m y ambos faltan a la vez",
            all(igual_na(is.na(yl), is.na(num$y_salary_m))) && all(yl >= num$y_salary_m - 0.5, na.rm = TRUE))
  salario_esperado <- ifelse(!is.na(num$p6500) & num$p6500 == 0, NA, num$p6500)
  comprobar(b, "7.17", cat_, "y_salary_m = p6500, con los ceros de p6500 convertidos a NA",
            all(igual_na(num$y_salary_m, salario_esperado, tol = 0.5)),
            paste0("p6500 = 0: ", fmt(sum(num$p6500 == 0, na.rm = TRUE)),
                   " (los 'ingresos cero' del enunciado estan aqui, no en y_total_m)"))
  ganancia_esperada <- num$p6750 / num$p6760
  comprobar(b, "7.18", cat_, "y_gananciaNeta_m = p6750 / p6760 (ganancia mensualizada) y = y_gananciaIndep_m",
            all(igual_na(num$y_gananciaNeta_m, ganancia_esperada, tol = 1e-5, relativa = TRUE)) &&
              all(igual_na(num$y_gananciaNeta_m, yg)))

  factor_mes <- 30 / 7   # horas semanales x 30/7 = horas al mes
  hora_total <- y / (num$totalHoursWorked * factor_mes)
  comprobar(b, "7.19", cat_, "y_total_m_ha = y_total_m / (totalHoursWorked x 30/7)",
            all(igual_na(num$y_total_m_ha, hora_total, tol = 1e-5, relativa = TRUE)),
            "el ingreso por hora usa horas de la semana pasada y un mes de 30 dias")
  hora_salario <- num$y_salary_m / (num$hoursWorkUsual * factor_mes)
  comprobar(b, "7.20", cat_, "y_salary_m_hu = y_salary_m / (hoursWorkUsual x 30/7)",
            all(igual_na(num$y_salary_m_hu, hora_salario, tol = 1e-5, relativa = TRUE)))
  hora_lab <- yl / (num$totalHoursWorked * factor_mes)
  comprobar(b, "7.21", cat_, "y_ingLab_m_ha = y_ingLab_m / (totalHoursWorked x 30/7)",
            all(igual_na(num$y_ingLab_m_ha, hora_lab, tol = 1e-5, relativa = TRUE)))

  coincide_impa <- mean(igual_na(num$impa, y, tol = 1)[!is.na(y)])
  registrar(b, "7.22", cat_, "impa (DANE, primera actividad) frente a y_total_m (informativo)", "OK",
            paste0("coinciden en ", round(100 * coincide_impa, 1), "% de las filas con y_total_m; ",
                   "impa = 0 en ", fmt(sum(num$impa == 0, na.rm = TRUE)), " filas"))

  # Horas: la variable del curso suma las horas NORMALES del empleo principal
  # (p6800 = hoursWorkUsual) y las horas efectivas del segundo empleo (p7045).
  segundo <- ifelse(is.na(num$hoursWorkActualSecondJob), 0, num$hoursWorkActualSecondJob)
  comprobar(b, "7.23", cat_, "totalHoursWorked = hoursWorkUsual + hoursWorkActualSecondJob (0 si no hay segundo empleo)",
            all(igual_na(num$totalHoursWorked, ifelse(is.na(num$hoursWorkUsual), NA, num$hoursWorkUsual + segundo))),
            "no usa p6850 (horas efectivas la semana pasada), que el sitio no publica")
  invisible(NULL)
}

panorama_muestra <- function(num, datos, cfg, b) {
  cat_ <- "8. Panorama de la muestra (informativo)"
  ocupado <- num$ocu == 1
  adulto <- num$age >= cfg$edad_minima_muestra
  y <- num$y_total_m
  base <- ocupado & adulto & !is.na(y)

  registrar(b, "8.1", cat_, "Tamanos de muestra candidatos", "OK",
            paste0("ocupados: ", fmt(sum(ocupado)), "; ocupados 18+: ", fmt(sum(ocupado & adulto)),
                   "; ocupados 18+ con y_total_m: ", fmt(sum(base)),
                   "; ocupados 18+ sin y_total_m: ", fmt(sum(ocupado & adulto & is.na(y)))))

  faltantes <- datos[ocupado & adulto & is.na(y), c("relab", "p6500", "p6750", "impaes", "cclasnr2")]
  tabla_falt <- as.data.frame(table(relab = faltantes$relab), stringsAsFactors = FALSE)
  names(tabla_falt) <- c("relab", "n_sin_y_total_m")
  tabla_falt$n_p6500_igual_0 <- as.integer(tapply(a_numero(faltantes$p6500) == 0, faltantes$relab, sum, na.rm = TRUE))
  tabla_falt$n_con_impaes <- as.integer(tapply(faltantes$impaes != "NA", faltantes$relab, sum))
  registrar(b, "8.2", cat_, "Ocupados 18+ sin y_total_m, por relab", "OK",
            paste(tabla_falt$relab, tabla_falt$n_sin_y_total_m, sep = "=", collapse = "; "))

  cuantiles <- stats::quantile(y[base], c(0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1))
  registrar(b, "8.3", cat_, "Distribucion de y_total_m en ocupados 18+ (pesos de 2018)", "OK",
            paste(names(cuantiles), fmt(cuantiles), sep = ": ", collapse = "; "))
  smmlv <- 781242
  registrar(b, "8.4", cat_, "Ingresos bajos frente al salario minimo 2018 (781.242)", "OK",
            paste0("< 1/2 SMMLV: ", fmt(sum(y[base] < smmlv / 2)), "; < 100.000: ", fmt(sum(y[base] < 1e5)),
                   "; >= 50 millones: ", fmt(sum(y[base] >= 5e7))))

  relab_base <- table(num$relab[base])
  raros <- names(relab_base)[relab_base < 30]
  registrar(b, "8.5", cat_, "Categorias de relab con menos de 30 ocupados 18+ con ingreso", if (length(raros)) "ADVERTENCIA" else "OK",
            paste0(paste(names(relab_base), as.integer(relab_base), sep = "=", collapse = "; "),
                   if (length(raros)) paste0(" | raras: ", paste(raros, collapse = ", "),
                                             " (cuidado con factores y LOOCV por leverage)") else ""))

  # Ingresos observados que el DANE reemplazo por imputacion (impaes presente
  # junto con y_total_m): el DANE los considero extremos.
  reemplazados <- base & !is.na(num$impaes)
  registrar(b, "8.7", cat_, "Ingresos observados que el DANE sustituyo por imputacion (los juzgo extremos)",
            if (any(reemplazados)) "ADVERTENCIA" else "OK",
            paste0(fmt(sum(reemplazados)), " casos en la muestra base; y_total_m < 100.000 en ",
                   fmt(sum(reemplazados & y < 1e5)), " y > 20 millones en ",
                   fmt(sum(reemplazados & y > 2e7)), ". El script 03 los marca con alerta_dane_extremo"))

  # Faltantes en los predictores candidatos dentro de la muestra base, por
  # particion: un NA en un control reduce la muestra de esa especificacion.
  candidatos <- c("age", "sex", "maxEducLevel", "p6210", "p6210s1", "estrato1", "p6050",
                  "relab", "oficio", "sizeFirm", "p6426", "totalHoursWorked",
                  "hoursWorkUsual", "formal", "cotPension", "regSalud", "p7040", "mes")
  particion <- as.character(datos$muestra_ps3)
  faltantes_pred <- data.frame(
    variable = candidatos,
    n_na_entrenamiento = vapply(candidatos, function(v) {
      sum(is.na(num[[v]]) & base & particion == "entrenamiento")
    }, integer(1)),
    n_na_validacion = vapply(candidatos, function(v) {
      sum(is.na(num[[v]]) & base & particion == "validacion")
    }, integer(1)),
    row.names = NULL, stringsAsFactors = FALSE
  )
  con_na <- faltantes_pred[faltantes_pred$n_na_entrenamiento + faltantes_pred$n_na_validacion > 0, ]
  registrar(b, "8.6", cat_, "Faltantes en predictores candidatos dentro de la muestra base (informativo)",
            if (nrow(con_na)) "ADVERTENCIA" else "OK",
            if (nrow(con_na)) {
              paste0(con_na$variable, ": ", con_na$n_na_entrenamiento, " / ", con_na$n_na_validacion,
                     collapse = "; ")
            } else "ningun predictor candidato tiene NA en la muestra base")

  por_bloque <- data.frame(
    chunk = sort(unique(datos$chunk)),
    n_total = as.integer(table(datos$chunk)),
    n_ocupados = as.integer(tapply(ocupado, datos$chunk, sum)),
    n_ocupados_18 = as.integer(tapply(ocupado & adulto, datos$chunk, sum)),
    n_ocupados_18_con_y = as.integer(tapply(base, datos$chunk, sum)),
    meses = as.character(tapply(num$mes, datos$chunk, function(m) paste(sort(unique(m)), collapse = "/"))),
    muestra_ps3 = as.character(tapply(as.character(datos$muestra_ps3), datos$chunk, function(m) m[1L])),
    stringsAsFactors = FALSE
  )
  list(base = base, por_bloque = por_bloque, faltantes_relab = tabla_falt,
       faltantes_predictores = faltantes_pred)
}

validar_comparabilidad <- function(num, datos, base, cfg, b) {
  cat_ <- "9. Comparabilidad entrenamiento / validacion"
  mes_bloque <- table(bloque = datos$chunk, mes = num$mes)
  meses_por_bloque <- apply(mes_bloque > 0, 1, sum)
  registrar(b, "9.1", cat_, "Los bloques siguen el calendario: cada bloque cubre 2-3 meses consecutivos", "ADVERTENCIA",
            paste0("meses por bloque: ", paste(names(meses_por_bloque), meses_por_bloque, sep = "=", collapse = "; "),
                   ". Entrenamiento ~ enero-septiembre; validacion ~ septiembre-diciembre. ",
                   "La particion NO es aleatoria: parte del error de validacion puede ser estacional"))

  viv_ent <- unique(datos$directorio[datos$chunk %in% cfg$bloques_entrenamiento])
  viv_val <- unique(datos$directorio[datos$chunk %in% cfg$bloques_validacion])
  hogares <- paste(datos$directorio, datos$secuencia_p)
  repartidos <- tapply(datos$chunk, hogares, function(ch) length(unique(ch)) > 1)
  comprobar(b, "9.2", cat_, "Casi ninguna vivienda aparece en ambas particiones (solo cortes en la frontera)",
            length(intersect(viv_ent, viv_val)) <= 2L,
            paste0("viviendas en ambas: ", length(intersect(viv_ent, viv_val)),
                   "; hogares repartidos entre bloques: ", sum(repartidos)), si_falla = "ADVERTENCIA")

  particion <- as.character(datos$muestra_ps3)
  resumen <- do.call(rbind, lapply(c("entrenamiento", "validacion"), function(p) {
    sel <- base & particion == p
    data.frame(
      particion = p, n = sum(sel),
      media_log_y = mean(log(num$y_total_m[sel])), sd_log_y = stats::sd(log(num$y_total_m[sel])),
      media_edad = mean(num$age[sel]), prop_hombres = mean(num$sex[sel]),
      media_horas = mean(num$totalHoursWorked[sel]),
      prop_cuenta_propia = mean(num$cuentaPropia[sel]), prop_formal = mean(num$formal[sel]),
      stringsAsFactors = FALSE
    )
  }))
  dif_log <- abs(diff(resumen$media_log_y))
  comprobar(b, "9.3", cat_, "Medias de log(y), edad, sexo y horas son similares entre particiones",
            dif_log < 0.05,
            paste0("dif. media log(y): ", round(dif_log, 3), "; n entrenamiento: ", fmt(resumen$n[1]),
                   "; n validacion: ", fmt(resumen$n[2])), si_falla = "ADVERTENCIA")

  # Solo niveles observados: los NA se revisan aparte (prueba 8.6).
  for (v in c("relab", "oficio", "sizeFirm", "maxEducLevel", "estrato1")) {
    x_ent <- num[[v]][base & particion == "entrenamiento"]
    x_val <- num[[v]][base & particion == "validacion"]
    en_ent <- unique(x_ent[!is.na(x_ent)])
    en_val <- unique(x_val[!is.na(x_val)])
    solo_val <- setdiff(en_val, en_ent)
    comprobar(b, paste0("9.4.", v), cat_,
              paste0(v, ": todo nivel de validacion existe en entrenamiento (predict() con factores)"),
              length(solo_val) == 0L,
              if (length(solo_val)) paste("solo en validacion:", paste(solo_val, collapse = ", ")) else
                paste0(length(en_ent), " niveles en entrenamiento"), si_falla = "ADVERTENCIA")
  }
  list(mes_bloque = tabla_a_df(mes_bloque, "bloque"), resumen = resumen)
}

convertir_tipos <- function(datos, originales) {
  for (v in originales) {
    if (v == "dominio") next
    x <- a_numero(datos[[v]])
    es_entera <- all(is.na(x) | (x == round(x) & abs(x) < 2147483647))
    datos[[v]] <- if (isTRUE(es_entera)) as.integer(x) else x
  }
  datos$fila_en_bloque <- as.integer(datos$fila_en_bloque)
  datos$chunk <- as.integer(datos$chunk)
  datos$muestra_ps3 <- as.character(datos$muestra_ps3)
  datos
}

# 5. EJECUCION COMPLETA ---------------------------------------------------------

validar_geih <- function(cfg = config_val) {
  cfg <- resolver_rutas(cfg)
  if (!file.exists(cfg$archivo_datos)) {
    stop("No se encontro la base: ", cfg$archivo_datos,
         "\nRevise carpeta_proyecto en CONFIGURACION.", call. = FALSE)
  }
  dir.create(cfg$carpeta_salida, recursive = TRUE, showWarnings = FALSE)
  b <- crear_bitacora()

  message("Leyendo: ", cfg$archivo_datos)
  datos <- readRDS(cfg$archivo_datos)

  message("\n--- 1. Estructura ---")
  validar_estructura(datos, cfg, b)
  originales <- intersect(variables_esperadas, names(datos))

  message("\n--- 2. Procedencia y bloques ---")
  validar_procedencia(datos, cfg, b)

  message("\n--- 3. Contenido textual y conversion ---")
  perfil <- validar_contenido(datos, originales, cfg, b)
  escribir_csv(perfil, file.path(cfg$carpeta_salida, "perfil_columnas.csv"))

  # Version numerica de trabajo para el resto de las pruebas.
  num <- as.data.frame(lapply(datos[originales[originales != "dominio"]], a_numero))

  message("\n--- 4. Llaves y constantes ---")
  validar_llaves(num, datos, b)

  message("\n--- 5. Codificaciones ---")
  codigos <- validar_codigos(num, cfg, b)
  escribir_csv(codigos, file.path(cfg$carpeta_salida, "codigos_observados.csv"))

  message("\n--- 6. Diccionario y etiquetas ---")
  validar_documentacion(datos, num, cfg, b)

  message("\n--- 7. Consistencia de variables construidas ---")
  validar_consistencia(num, b)
  escribir_csv(tabla_a_df(table(formal = num$formal, cotPension = num$cotPension, useNA = "ifany"), "formal"),
               file.path(cfg$carpeta_salida, "formal_vs_cotPension.csv"))

  message("\n--- 8. Panorama de la muestra ---")
  panorama <- panorama_muestra(num, datos, cfg, b)
  escribir_csv(panorama$por_bloque, file.path(cfg$carpeta_salida, "muestra_por_bloque.csv"))
  escribir_csv(panorama$faltantes_relab, file.path(cfg$carpeta_salida, "ingresos_faltantes_relab.csv"))
  escribir_csv(panorama$faltantes_predictores, file.path(cfg$carpeta_salida, "faltantes_predictores.csv"))

  message("\n--- 9. Comparabilidad entrenamiento / validacion ---")
  comparabilidad <- validar_comparabilidad(num, datos, panorama$base, cfg, b)
  escribir_csv(comparabilidad$mes_bloque, file.path(cfg$carpeta_salida, "mes_por_bloque.csv"))
  escribir_csv(comparabilidad$resumen, file.path(cfg$carpeta_salida, "comparabilidad_particion.csv"))

  archivo_tipado <- NULL
  if (isTRUE(cfg$exportar_tipado)) {
    message("\n--- 10. Copia con tipos numericos ---")
    dir.create(cfg$carpeta_intermedios, recursive = TRUE, showWarnings = FALSE)
    tipado <- convertir_tipos(datos, originales)
    archivo_tipado <- file.path(cfg$carpeta_intermedios, "geih2018_tipado.rds")
    saveRDS(tipado, archivo_tipado)
    escribir_csv(data.frame(
      posicion = seq_along(tipado), variable = names(tipado),
      tipo_R = vapply(tipado, function(x) class(x)[1L], character(1)),
      n_na = vapply(tipado, function(x) sum(is.na(x)), integer(1)),
      row.names = NULL, stringsAsFactors = FALSE
    ), file.path(cfg$carpeta_salida, "esquema_tipado.csv"))
    comprobar(b, "10.1", "10. Copia tipada", "La copia tipada conserva filas y columnas y no crea NA adicionales",
              nrow(tipado) == nrow(datos) && ncol(tipado) == ncol(datos) &&
                all(vapply(originales, function(v) sum(is.na(tipado[[v]])) == sum(datos[[v]] == "NA"), logical(1))),
              paste("guardada en:", archivo_tipado))
  }

  resultados <- do.call(rbind, b$filas)
  rownames(resultados) <- NULL
  escribir_csv(resultados, file.path(cfg$carpeta_salida, "resultados_validacion.csv"))

  conteo <- table(factor(resultados$resultado, levels = c("OK", "ADVERTENCIA", "ERROR")))
  message("\n=============================================================")
  message("RESUMEN: ", conteo[["OK"]], " OK | ", conteo[["ADVERTENCIA"]], " ADVERTENCIA | ",
          conteo[["ERROR"]], " ERROR (", nrow(resultados), " pruebas)")
  message("Detalle en: ", normalizePath(cfg$carpeta_salida, winslash = "/"))
  if (conteo[["ERROR"]] > 0) {
    message("\nPruebas con ERROR:")
    print(resultados[resultados$resultado == "ERROR", c("id", "prueba", "detalle")], row.names = FALSE)
  }
  if (conteo[["ADVERTENCIA"]] > 0) {
    message("\nAdvertencias (hechos que condicionan la limpieza y el analisis):")
    print(resultados[resultados$resultado == "ADVERTENCIA", c("id", "prueba")], row.names = FALSE)
  }
  if (isTRUE(cfg$detener_si_error) && conteo[["ERROR"]] > 0) {
    stop("La validacion encontro errores. Revise resultados_validacion.csv.", call. = FALSE)
  }

  invisible(list(resultados = resultados, perfil_columnas = perfil, codigos = codigos,
                 muestra_por_bloque = panorama$por_bloque, mes_por_bloque = comparabilidad$mes_bloque,
                 comparabilidad = comparabilidad$resumen, archivo_tipado = archivo_tipado,
                 configuracion = cfg))
}

# 6. PUNTO DE ENTRADA -----------------------------------------------------------

if (isTRUE(getOption("geih.validar", TRUE))) {
  validacion_geih <- validar_geih(config_val)
}
