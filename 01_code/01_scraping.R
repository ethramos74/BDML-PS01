# ==============================================================================
# Archivo: 01_code/01_scraping.R
# Propósito: Descargar los 10 chunks de la GEIH 2018 y consolidarlos
#            en una única base de datos localmente.
# Output:    02_outputs/data_geih_consolidada.rds
# ==============================================================================

# 1. Cargar dependencias con pacman para reproducibilidad
if (!require(pacman)) install.packages("pacman")
pacman::p_load(
  tidyverse, # Manipulación de datos y map_dfr()
  rvest,     # Web scraping (html_table, scrape)
  polite,    # Web scraping ético
  rio,       # Exportación e importación eficiente
  here       # Manejo de rutas relativas robustas
)

# 2. Definir y asegurar rutas de salida relativas al proyecto
output_dir  <- here("02_outputs")
output_path <- here("02_outputs", "data_geih_consolidada.rds")

# Crear la carpeta outputs si no existe aún
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
}

# 3. Control de ejecución: evitar scrapear si el archivo ya fue descargado localmente
if (file.exists(output_path)) {
  message("ℹ️ La base consolidada ya existe en '", output_path, "'. Se omite el scraping.")
  db_geih <- rio::import(output_path)
} else {
  
  # 4. Configuración de sesión polite con robots.txt
  main_url <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/"
  sesion   <- bow(main_url, force = TRUE)
  
  # 5. Función de descarga y parseo por chunk
  download_chunk <- function(i, sesion_base) {
    chunk_path <- paste0("pages/geih_page_", i, ".html")
    chunk_url  <- url_absolute(chunk_path, main_url)
    
    message(paste("-> Descargando chunk", i, "de 10:", chunk_url))
    
    # Navegación polite respetando crawl-delay
    sesion_chunk <- nod(sesion_base, chunk_url)
    html_chunk   <- scrape(sesion_chunk)
    
    # Extracción de la tabla HTML
    tabla <- html_chunk |>
      html_table() |>
      pluck(1)
    
    # Eliminar primera columna vacía (índice HTML)
    tabla <- tabla |> select(-1)
    
    return(tabla)
  }
  
  # 6. Descargar y apilar los 10 chunks
  message("Iniciando descarga de los 10 chunks de la GEIH...")
  db_raw <- map_dfr(1:10, download_chunk, sesion_base = sesion)
  
  # 7. Validar identificador único y estructura relacional
  db_geih <- db_raw |>
    mutate(id_unico = paste(directorio, secuencia_p, orden, sep = "_"))
  
  if (n_distinct(db_geih$id_unico) == nrow(db_geih)) {
    message("✅ ¡Éxito! Cada observación tiene un identificador único.")
  } else {
    warning("⚠️ Advertencia: Existen identificadores duplicados.")
  }
  
  # 8. Exportar la base consolidada
  rio::export(db_geih, output_path)
  message("✅ Base guardada exitosamente en: ", output_path)
}