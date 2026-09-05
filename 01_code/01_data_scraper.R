# ============================================================
# 0. PAQUETES
# ============================================================

if (!require(pacman)) install.packages("pacman")
library(pacman)

p_load(
  rio,        # Import data.
  tidyverse,  # Manipulate data and create figures.
  conflicted, # Resolve function conflicts.
  rvest,      # Read HTML tables.
  here        # Directorio raíz del proyecto
)

getwd()

# ============================================================
# 1. URLS DE LOS 10 CHUNKS
# ============================================================

c1_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page1.html"
c2_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page2.html"
c3_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page3.html"
c4_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page4.html"
c5_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page5.html"
c6_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page6.html"
c7_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page7.html"
c8_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page8.html"
c9_url  <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page9.html"
c10_url <- "https://ignaciomsarmiento.github.io/GEIH2018_sample/page10.html"

chunk_urls <- c(
  c1_url,
  c2_url,
  c3_url,
  c4_url,
  c5_url,
  c6_url,
  c7_url,
  c8_url,
  c9_url,
  c10_url
)


# ============================================================
# 2. FUNCIÓN PARA DESCARGAR CADA CHUNK
# ============================================================

TIEMPO_ESPERA <- 5

leer_chunk <- function(page_url, i) {
  
  message("Procesando chunk ", i, " de ", length(chunk_urls), "...")
  
  # Convertir page1.html -> pages/geih_page_1.html
  table_url <- str_replace(
    page_url,
    "page(\\d+)\\.html$",
    "pages/geih_page_\\1.html"
  )
  
  # Leer tabla
  df_chunk <- table_url %>%
    read_html() %>%
    html_element("table") %>%
    html_table() %>%
    select(-1)
  
  message(
    "Chunk ", i, ": ",
    nrow(df_chunk), " filas x ",
    ncol(df_chunk), " columnas."
  )
  
  if (i < length(chunk_urls)) {
    Sys.sleep(TIEMPO_ESPERA)
  }
  
  df_chunk
}


# ============================================================
# 3. DESCARGAR Y UNIR LOS 10 CHUNKS
# ============================================================

df_full <- map2(
  chunk_urls,
  seq_along(chunk_urls),
  leer_chunk
) %>%
  bind_rows()


# ============================================================
# 4. RESULTADO
# ============================================================

cat(
  "\nRESULTADO FINAL\n",
  "df_full: ",
  nrow(df_full), " filas x ",
  ncol(df_full), " columnas\n",
  sep = ""
)


# ============================================================
# 5. GUARDADO
# ============================================================

write.csv(
  df_full,
  here("PS1_GEIH.csv"),
  row.names = FALSE,
  fileEncoding = "UTF-8"
)