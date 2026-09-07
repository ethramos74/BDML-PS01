# =============================================================================
# PROBLEM SET 1 | GEIH 2018, BOGOTA
# 01. Descarga, extraccion y verificacion de los datos originales
# =============================================================================
# OBJETIVO
# Recuperar los diez bloques publicados para el taller. Las paginas page1.html,
# ..., page10.html contienen una referencia a otro HTML con la tabla real.
# Este script descubre esas referencias; no necesita ejecutar JavaScript.
#
# ALCANCE
# - Conserva los HTML y las 177 variables originales como TEXTO.
# - Conserva literalmente "NA", ceros, blancos y notacion cientifica.
# - Agrega procedencia y asignacion de bloques para la seccion 3.
# - No filtra personas, no imputa, no recodifica y no estima modelos.
# - La asignacion entrenamiento/validacion NO define aun la muestra analitica.
#
# PIPELINE DE DATOS DEL PROBLEM SET (ejecutar en orden)
# 01_obtener_datos_GEIH2018.R   descarga y consolida (este archivo)
# 02_validar_datos_GEIH2018.R   valida la base y crea la copia tipada
# 03_limpiar_datos_GEIH2018.R   construye la muestra de analisis unica
#
# RUTA DEL PROYECTO
# Los tres scripts usan la misma carpeta raiz PS1_GEIH2018, resuelta asi:
#   1. la variable de entorno PS1_GEIH2018_DIR, si esta definida
#      (p. ej. en .Renviron: PS1_GEIH2018_DIR=C:/.../Taller 1/PS1_GEIH2018);
#   2. si no, la subcarpeta PS1_GEIH2018 del directorio de trabajo actual
#      (abra el proyecto de RStudio en la carpeta "Taller 1" y funciona).
# Nadie necesita editar rutas personales dentro de los scripts.
#
# USO EN RSTUDIO
# 1. Abra su proyecto de RStudio y guarde este script dentro del proyecto.
# 2. Revise CONFIGURACION (normalmente no hay que cambiar nada).
# 3. Ejecute el archivo completo con Source. La primera ejecucion descarga;
#    las siguientes reutilizan los HTML existentes.
# 4. El objeto resultado_geih$datos contiene la base original consolidada.
#    Tambien puede recuperarla despues con readRDS() desde la ruta indicada.
#
# Para cargar SOLO las funciones, sin descargar:
# options(geih.ejecutar = FALSE)
# source("01_obtener_datos_GEIH2018.R", encoding = "UTF-8")
# Despues puede ejecutar: resultado_geih <- obtener_geih(config)
#
# SALIDAS, dentro de carpeta_salida (= raiz del proyecto):
# datos/html/                 Copias originales del sitio y sus tablas.
# datos/brutos/bloque_XX.rds  Cada bloque extraido, sin limpieza analitica.
# datos/brutos/geih2018_original.rds  Diez bloques consolidados.
# documentacion/             Diccionario y etiquetas en RDS y CSV.
# auditoria/                 Manifiesto, dimensiones, esquema y sesion de R.
#
# Dependencias: curl, xml2, rvest >= 1.0.0. No requiere tidyverse completo.
# Verificacion: ejecutado completo en R 4.3.3 (Windows). Resultado: 32.177
# observaciones en 10 bloques (3.217-3.218 cada uno), 177 variables originales
# en el orden del sitio mas 4 columnas de procedencia (fila_en_bloque, chunk,
# url_origen, muestra_ps3). La base resultante paso las 74 pruebas del script
# 02 sin errores. Hechos de la fuente que conviene saber desde aqui:
# - Los bloques siguen el calendario de la encuesta (bloque 1 = enero-febrero,
#   bloque 10 = noviembre-diciembre): la particion de la seccion 3 es temporal.
# - Los valores llegan como texto; "7e+05" son cifras redondas (se recuperan
#   exactas con as.numeric) y los faltantes son la cadena "NA".
# - Las columnas p550 y y_gananciaNetaAgro_m son 100% NA (no hay agro en Bogota).
# Referencias:
# https://ignaciomsarmiento.github.io/GEIH2018_sample/index.html
# https://rvest.tidyverse.org/reference/read_html.html
# https://rvest.tidyverse.org/reference/html_table.html
# https://cran.r-project.org/web/packages/curl/refman/curl.html
# =============================================================================

# 1. CONFIGURACION --------------------------------------------------------------

# Raiz del proyecto compartida por los scripts 01, 02 y 03 (ver encabezado).
carpeta_proyecto_geih <- function() {
  ruta <- Sys.getenv("PS1_GEIH2018_DIR", unset = "")
  if (nzchar(ruta)) ruta else file.path(getwd(), "PS1_GEIH2018")
}

config <- list(
  carpeta_salida = carpeta_proyecto_geih(),
  url_base = "https://ignaciomsarmiento.github.io/GEIH2018_sample/",
  bloques_esperados = 1:10,
  bloques_entrenamiento = 1:7,
  bloques_validacion = 8:10,
  n_observaciones_esperadas = 32177L,
  n_variables_esperadas = 177L,
  pausa_segundos = 1,          # Descarga secuencial y respetuosa con el sitio.
  timeout_segundos = 300,      # Cada tabla HTML puede superar los 22 MB.
  intentos = 3L,
  instalar_faltantes = TRUE,   # Instala desde CRAN solo paquetes ausentes.
  exportar_csv_datos = FALSE  # RDS es la salida principal: conserva tipos.
)

# 2. DEPENDENCIAS Y UTILIDADES --------------------------------------------------

comprobar_paquetes <- function(instalar = FALSE) {
  paquetes <- c("curl", "xml2", "rvest")
  disponibles <- vapply(paquetes, requireNamespace, logical(1), quietly = TRUE)
  faltantes <- paquetes[!disponibles]

  if (length(faltantes) > 0L && instalar) {
    utils::install.packages(faltantes, repos = "https://cloud.r-project.org")
  }
  disponibles <- vapply(paquetes, requireNamespace, logical(1), quietly = TRUE)
  if (any(!disponibles)) {
    stop("Instale los paquetes: ", paste(paquetes[!disponibles], collapse = ", "),
         ". Luego ejecute nuevamente el script.", call. = FALSE)
  }
  if (utils::packageVersion("rvest") < package_version("1.0.0")) {
    stop("Actualice rvest a una version >= 1.0.0.", call. = FALSE)
  }
}

escribir_csv <- function(datos, archivo) {
  utils::write.csv(datos, archivo, row.names = FALSE, fileEncoding = "UTF-8",
                   na = "NA")
}

crear_carpetas <- function(raiz) {
  dir.create(raiz, recursive = TRUE, showWarnings = FALSE)
  raiz <- normalizePath(raiz, winslash = "/", mustWork = TRUE)
  carpetas <- list(
    html = file.path(raiz, "datos", "html"),
    brutos = file.path(raiz, "datos", "brutos"),
    documentacion = file.path(raiz, "documentacion"),
    auditoria = file.path(raiz, "auditoria")
  )
  for (ruta in carpetas) {
    dir.create(ruta, recursive = TRUE, showWarnings = FALSE)
    if (!dir.exists(ruta)) stop("No se pudo crear: ", ruta, call. = FALSE)
  }
  carpetas
}

# 3. DESCARGA CON CACHE LOCAL Y REINTENTOS --------------------------------------

# Los HTML existentes no se reemplazan. Para una nueva descarga completa,
# elija otra carpeta_salida. Los archivos .part nunca se usan como datos.
descargar_html <- function(url, archivo, cfg) {
  nuevo <- !file.exists(archivo)
  estado_http <- NA_integer_ # No hay nueva consulta HTTP al reutilizar cache.

  if (!nuevo) {
    if (is.na(file.size(archivo)) || file.size(archivo) == 0) {
      stop("El archivo guardado esta vacio: ", archivo,
           ". Eliminelo y vuelva a ejecutar.", call. = FALSE)
    }
    message("  Reutilizando: ", basename(archivo))
  } else {
    temporal <- paste0(archivo, ".part")
    on.exit(unlink(temporal), add = TRUE)
    ultimo_error <- ""
    descargado <- FALSE

    for (intento in seq_len(cfg$intentos)) {
      Sys.sleep(cfg$pausa_segundos)
      message("  Descargando: ", basename(archivo),
              " [intento ", intento, "/", cfg$intentos, "]")

      descargado <- tryCatch({
        conexion <- curl::new_handle(
          followlocation = TRUE,
          connecttimeout = 30,
          timeout = cfg$timeout_segundos,
          useragent = "GEIH2018-academic-data-download"
        )
        curl::curl_download(url, temporal, quiet = TRUE, mode = "wb",
                            handle = conexion)
        estado_http <- as.integer(curl::handle_data(conexion)$status_code)
        if (!identical(estado_http, 200L)) {
          stop("Se esperaba una respuesta HTTP 200 completa; se recibio ",
               estado_http, ".")
        }
        if (!file.exists(temporal) || file.size(temporal) == 0) {
          stop("El servidor devolvio un archivo vacio.")
        }
        TRUE
      }, error = function(e) {
        ultimo_error <<- conditionMessage(e)
        FALSE
      })

      if (descargado) break
      unlink(temporal)
      if (intento < cfg$intentos) Sys.sleep(min(2^intento, 15))
    }

    if (!descargado) {
      stop("No se pudo descargar ", url, "\n", ultimo_error,
           "\nLos archivos completos previos se conservan para reanudar.",
           call. = FALSE)
    }
    if (!file.rename(temporal, archivo)) {
      stop("No se pudo guardar la descarga en: ", archivo, call. = FALSE)
    }
  }

  # El MD5 permite comparar copias; no autentica el contenido frente al servidor.
  data.frame(
    url = url,
    archivo = normalizePath(archivo, winslash = "/", mustWork = TRUE),
    descargado_en_esta_ejecucion = nuevo,
    estado_http = estado_http,
    bytes = unname(file.size(archivo)),
    md5 = unname(tools::md5sum(archivo)),
    modificacion_archivo_utc = format(file.info(archivo)$mtime,
                                    tz = "UTC", usetz = TRUE),
    verificado_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
    stringsAsFactors = FALSE
  )
}

leer_html_local <- function(archivo) {
  # HUGE admite tablas extensas. La integridad tabular se comprueba por separado.
  xml2::read_html(archivo, encoding = "UTF-8",
                 options = c("RECOVER", "NOERROR", "NOBLANKS", "HUGE"))
}

# 4. DESCUBRIMIENTO DE LOS DIEZ BLOQUES -----------------------------------------

descubrir_bloques <- function(archivo_indice, cfg) {
  documento <- leer_html_local(archivo_indice)
  enlaces <- xml2::xml_attr(xml2::xml_find_all(documento, "//a[@href]"), "href")
  enlaces <- unique(enlaces[!is.na(enlaces) &
    grepl("(^|/)page[0-9]+\\.html$", enlaces)])
  numeros <- as.integer(sub("^page([0-9]+)\\.html$", "\\1", basename(enlaces)))
  orden <- order(numeros) # Orden numerico: 1, 2, ..., 10; no 1, 10, 2, ...

  if (!identical(numeros[orden], as.integer(cfg$bloques_esperados))) {
    stop("La pagina principal no contiene exactamente los diez bloques esperados.",
         call. = FALSE)
  }
  data.frame(
    chunk = numeros[orden],
    url_pagina = xml2::url_absolute(enlaces[orden], cfg$url_base),
    stringsAsFactors = FALSE
  )
}

descubrir_tabla_interna <- function(archivo_pagina, url_pagina, chunk) {
  documento <- leer_html_local(archivo_pagina)
  nodos <- xml2::xml_find_all(documento, "//*[@w3-include-html]")
  referencia <- xml2::xml_attr(nodos, "w3-include-html")
  if (length(referencia) != 1L || is.na(referencia) || !nzchar(referencia)) {
    stop("No se encontro una referencia unica a la tabla del bloque ", chunk,
         ". Revise si cambio el sitio.", call. = FALSE)
  }
  url <- xml2::url_absolute(referencia, url_pagina)
  esperado <- sprintf("geih_page_%d.html", chunk)
  if (!identical(basename(url), esperado)) {
    stop("La tabla enlazada no corresponde al bloque ", chunk, ": ", url,
         call. = FALSE)
  }
  url
}

# 5. EXTRACCION FIEL Y VERIFICACION DE CADA TABLA -------------------------------

comprobar_cierre_tabla <- function(archivo) {
  # Detecta HTML guardado incompleto, aun cuando el lector pueda repararlo.
  conexion <- file(archivo, open = "rb")
  on.exit(close(conexion), add = TRUE)
  seek(conexion, where = max(0, file.size(archivo) - 8192), origin = "start")
  final <- rawToChar(readBin(conexion, what = "raw", n = 8192L))
  if (!grepl("</table\\s*>", final, ignore.case = TRUE)) {
    stop("Falta el cierre de la tabla en ", archivo,
         ". La descarga puede estar incompleta. Revise o descargue de nuevo",
         " ese archivo antes de continuar.", call. = FALSE)
  }
}

extraer_bloque <- function(archivo, chunk, url_origen, cfg) {
  comprobar_cierre_tabla(archivo)
  documento <- leer_html_local(archivo)
  tablas <- xml2::xml_find_all(documento, "//table")
  if (length(tablas) != 1L) {
    stop("Se esperaba exactamente una tabla en el bloque ", chunk,
         call. = FALSE)
  }
  tabla <- tablas[[1L]]
  encabezados <- trimws(xml2::xml_text(
    xml2::xml_find_all(tabla, "./thead/tr/th")
  ))
  if (length(encabezados) != cfg$n_variables_esperadas + 1L ||
      !identical(encabezados[1L], "")) {
    stop("Encabezado inesperado en el bloque ", chunk,
         ": deben existir 177 variables y una columna inicial sin nombre.",
         call. = FALSE)
  }
  encabezados[1L] <- "fila_en_bloque"
  if (anyDuplicated(encabezados) || any(!nzchar(encabezados))) {
    stop("Hay nombres de columnas vacios o repetidos en el bloque ", chunk,
         call. = FALSE)
  }
  if (any(c("chunk", "url_origen", "muestra_ps3") %in% encabezados)) {
    stop("Los nombres de procedencia coinciden con variables de la fuente.",
         call. = FALSE)
  }

  # No permitir que html_table rellene silenciosamente filas mal formadas.
  filas <- xml2::xml_find_all(tabla, "./tbody/tr")
  anchos <- vapply(filas, function(fila) {
    length(xml2::xml_find_all(fila, "./td"))
  }, integer(1))
  if (length(filas) == 0L || any(anchos != length(encabezados))) {
    stop("La tabla del bloque ", chunk, " esta vacia o no es rectangular.",
         call. = FALSE)
  }

  # convert = FALSE es fundamental: NO convertir "NA", "2e+05" o codigos.
  # trim = FALSE conserva tambien los espacios de las celdas originales.
  datos <- as.data.frame(
    rvest::html_table(tabla, header = TRUE, trim = FALSE, convert = FALSE),
    stringsAsFactors = FALSE, optional = TRUE
  )
  if (ncol(datos) != length(encabezados) || nrow(datos) != length(filas)) {
    stop("Las dimensiones extraidas no coinciden con el HTML del bloque ",
         chunk, call. = FALSE)
  }
  names(datos) <- encabezados
  if (!all(vapply(datos, is.character, logical(1)))) {
    stop("La extraccion altero el tipo textual de alguna columna.", call. = FALSE)
  }
  requeridas <- c("directorio", "secuencia_p", "orden", "age", "sex", "ocu",
                  "totalHoursWorked", "relab", "y_total_m")
  if (!all(requeridas %in% names(datos))) {
    stop("Faltan variables obligatorias en el bloque ", chunk, call. = FALSE)
  }

  datos$chunk <- as.integer(chunk)
  datos$url_origen <- url_origen
  datos$muestra_ps3 <- if (chunk %in% cfg$bloques_entrenamiento) {
    "entrenamiento"
  } else if (chunk %in% cfg$bloques_validacion) {
    "validacion"
  } else {
    stop("Bloque sin asignacion en la seccion 3.", call. = FALSE)
  }
  datos
}

extraer_documentacion <- function(archivo, encabezados_esperados) {
  documento <- leer_html_local(archivo)
  tablas <- xml2::xml_find_all(documento, "//table")
  if (length(tablas) != 1L) {
    stop("Se esperaba una tabla de documentacion en ", archivo, call. = FALSE)
  }
  datos <- as.data.frame(
    rvest::html_table(tablas[[1L]], header = TRUE, trim = FALSE, convert = FALSE),
    stringsAsFactors = FALSE, optional = TRUE
  )
  names(datos) <- trimws(names(datos)) # Solo normalizar espacios del encabezado.
  if (!identical(names(datos), encabezados_esperados) || nrow(datos) == 0L) {
    stop("Estructura inesperada de documentacion en ", archivo, call. = FALSE)
  }
  datos
}

# 6. EJECUCION COMPLETA ---------------------------------------------------------

obtener_geih <- function(cfg = config) {
  comprobar_paquetes(cfg$instalar_faltantes)
  stopifnot(
    identical(as.integer(cfg$bloques_esperados), 1:10),
    identical(as.integer(cfg$bloques_entrenamiento), 1:7),
    identical(as.integer(cfg$bloques_validacion), 8:10),
    cfg$intentos >= 1L, cfg$pausa_segundos >= 0, cfg$timeout_segundos > 0
  )
  carpetas <- crear_carpetas(cfg$carpeta_salida)
  manifiesto <- NULL

  # Esta funcion registra cada recurso inmediatamente. Asi queda trazabilidad
  # incluso si una descarga posterior falla. No se borra el HTML anterior.
  obtener_archivo <- function(url, nombre) {
    archivo <- file.path(carpetas$html, nombre)
    registro <- descargar_html(url, archivo, cfg)
    manifiesto <<- rbind(manifiesto, registro)
    escribir_csv(manifiesto, file.path(carpetas$auditoria, "manifiesto.csv"))
    archivo
  }

  message("1/4. Identificando los diez bloques del sitio...")
  indice <- obtener_archivo(paste0(cfg$url_base, "index.html"), "index.html")
  fuentes <- descubrir_bloques(indice, cfg)
  bloques <- vector("list", nrow(fuentes))
  resumen <- vector("list", nrow(fuentes))
  esquema_referencia <- NULL

  message("2/4. Descargando y extrayendo los bloques, sin limpieza analitica...")
  for (i in seq_len(nrow(fuentes))) {
    chunk <- fuentes$chunk[i]
    message("Bloque ", chunk, " de 10")
    pagina <- obtener_archivo(fuentes$url_pagina[i], sprintf("page_%02d.html", chunk))
    url_tabla <- descubrir_tabla_interna(pagina, fuentes$url_pagina[i], chunk)
    archivo <- obtener_archivo(url_tabla, sprintf("geih_page_%02d.html", chunk))
    datos <- extraer_bloque(archivo, chunk, url_tabla, cfg)

    if (is.null(esquema_referencia)) esquema_referencia <- names(datos)
    if (!identical(names(datos), esquema_referencia)) {
      stop("El bloque ", chunk, " tiene columnas distintas o en otro orden.",
           " No se consolidara una base con esquemas incompatibles.", call. = FALSE)
    }
    saveRDS(datos, file.path(carpetas$brutos, sprintf("bloque_%02d.rds", chunk)))
    bloques[[i]] <- datos
    resumen[[i]] <- data.frame(
      chunk = chunk, observaciones = nrow(datos),
      variables_originales = cfg$n_variables_esperadas,
      muestra_ps3 = datos$muestra_ps3[1L],
      url_pagina = fuentes$url_pagina[i], url_tabla = url_tabla,
      stringsAsFactors = FALSE
    )
    escribir_csv(do.call(rbind, resumen[seq_len(i)]),
                  file.path(carpetas$auditoria, "resumen_bloques.csv"))
    message("  Extraccion verificada: ", nrow(datos), " observaciones.")
  }

  datos <- do.call(rbind, bloques)
  rownames(datos) <- NULL
  if (nrow(datos) != cfg$n_observaciones_esperadas) {
    stop("Total inesperado: ", nrow(datos), "; esperado: ",
         cfg$n_observaciones_esperadas,
         ". Los bloques se conservaron, pero no se publica una consolidacion",
         " nueva. Revise resumen_bloques.csv y la fuente antes de continuar.",
         call. = FALSE)
  }

  message("3/4. Recuperando el diccionario y las etiquetas...")
  archivo_diccionario <- obtener_archivo(
    paste0(cfg$url_base, "dictionary.html"), "dictionary.html"
  )
  archivo_etiquetas <- obtener_archivo(
    paste0(cfg$url_base, "labels.html"), "labels.html"
  )
  diccionario <- extraer_documentacion(archivo_diccionario, c("Variable", "Description"))
  etiquetas <- extraer_documentacion(archivo_etiquetas, c("Variable", "values", "level"))

  message("4/4. Guardando la base original y los controles de integridad...")
  archivo_datos <- file.path(carpetas$brutos, "geih2018_original.rds")
  saveRDS(datos, archivo_datos)
  if (cfg$exportar_csv_datos) {
    escribir_csv(datos, file.path(carpetas$brutos, "geih2018_original.csv"))
  }
  saveRDS(diccionario, file.path(carpetas$documentacion, "diccionario.rds"))
  saveRDS(etiquetas, file.path(carpetas$documentacion, "etiquetas.rds"))
  escribir_csv(diccionario, file.path(carpetas$documentacion, "diccionario.csv"))
  escribir_csv(etiquetas, file.path(carpetas$documentacion, "etiquetas.csv"))
  escribir_csv(data.frame(
    posicion = seq_along(datos), variable = names(datos),
    tipo_R = vapply(datos, function(x) class(x)[1L], character(1)),
    es_procedencia = names(datos) %in%
      c("fila_en_bloque", "chunk", "url_origen", "muestra_ps3"),
    row.names = NULL
  ), file.path(carpetas$auditoria, "esquema_columnas.csv"))
  saveRDS(cfg, file.path(carpetas$auditoria, "configuracion.rds"))
  writeLines(capture.output(utils::sessionInfo()),
             file.path(carpetas$auditoria, "sessionInfo.txt"), useBytes = TRUE)

  resumen <- do.call(rbind, resumen)
  message("Finalizado: ", nrow(datos), " observaciones originales; ",
          cfg$n_variables_esperadas, " variables originales y 4 de procedencia.")
  message("Base guardada en: ", normalizePath(archivo_datos, winslash = "/"))
  message("Los valores originales siguen como texto. La limpieza es otra etapa.")
  print(resumen[c("chunk", "observaciones", "muestra_ps3")], row.names = FALSE)

  invisible(list(datos = datos, diccionario = diccionario, etiquetas = etiquetas,
                 resumen_bloques = resumen, manifiesto = manifiesto,
                 archivo_datos = archivo_datos))
}

# 7. PUNTO DE ENTRADA -----------------------------------------------------------

if (isTRUE(getOption("geih.ejecutar", TRUE))) {
  resultado_geih <- obtener_geih(config)
}
