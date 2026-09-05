# ==============================================================================
# Archivo:   01_code/02_cleaning.R
# Propósito: Limpieza de datos de la GEIH 2018 para Bogotá y construcción
#            de la muestra analítica común para todas las secciones del PS1.
# Input:     02_outputs/data_geih_consolidada.rds
# Output:    02_outputs/data_geih_cleaned.rds
# ==============================================================================

# 1. Cargar librerías requeridas
if (!require(pacman)) install.packages("pacman")
pacman::p_load(
  tidyverse, # Manipulación de datos
  rio,       # Importación y exportación eficiente
  here       # Rutas relativas basadas en la raíz del proyecto
)

# 2. Cargar base consolidada generada en 01_scraping.R
input_path  <- here("02_outputs", "data_geih_consolidada.rds")
output_path <- here("02_outputs", "data_geih_cleaned.rds")

if (!file.exists(input_path)) {
  stop("❌ No se encontró la base consolidada en '", input_path, 
       "'. Ejecuta primero 01_scraping.R.")
}

message("Cargando datos crudos consolidados...")
db_geih <- rio::import(input_path)

# 3. Construcción de variables a nivel de hogar
# El conteo de menores (<18 años) debe realizarse sobre toda la estructura
# del hogar antes de filtrar por adultos ocupados.
message("Calculando variables a nivel de hogar...")
db_geih <- db_geih |>
  mutate(bin_minor = ifelse(age < 18, 1, 0)) |>
  group_by(directorio, secuencia_p) |>
  mutate(num_minors = sum(bin_minor, na.rm = TRUE)) |>
  ungroup() |>
  select(-bin_minor)

# 4. Aplicación de filtros muestrales
# Restricciones del taller:
# - Adultos (age >= 18)
# - Ocupados (ocu == 1)
# - Ingreso laboral mensual positivo (y_total_m > 0)
# - Horas trabajadas positivas (totalHoursWorked > 0)
message("Filtrando la muestra analítica (adultos ocupados con ingresos positivos)...")
initial_obs <- nrow(db_geih)

db_sample <- db_geih |>
  filter(
    age >= 18,
    ocu == 1,
    !is.na(y_total_m),
    y_total_m > 0,
    !is.na(totalHoursWorked),
    totalHoursWorked > 0
  )

message(paste("Muestra filtrada:", nrow(db_sample), "de", initial_obs, "observaciones retenidas."))

# 5. Estandarización y creación de variables para el análisis
message("Generando variables de análisis (Mincer, sexo y controles)...")
db_clean <- db_sample |>
  mutate(
    # Variable de resultado principal
    ln_y_total_m = log(y_total_m),
    
    # Variable de tratamiento/interés para la Sección 2 (1 = Mujer, 0 = Hombre)
    # En GEIH: sex == 1 es Hombre, sex == 2 es Mujer
    female = ifelse(sex == 2, 1, 0),
    
    # Variables de ciclo de vida (Sección 1 y controles)
    age_sq = age^2,
    
    # Nivel educativo como factor con categoría de referencia
    # (maxEducLevel: 1=Ninguno, 2=Preescolar, 3=Primaria inc., etc.)
    cat_educ = factor(
      case_when(
        is.na(maxEducLevel) | maxEducLevel == 9 ~ 1,
        TRUE ~ maxEducLevel
      ),
      levels = 1:7,
      labels = c("None", "Preschool", "Primary_Incomplete", 
                 "Primary_Complete", "Secondary_Incomplete", 
                 "Secondary_Complete", "Tertiary")
    ),
    cat_educ = fct_relevel(cat_educ, "None"),
    
    # Tipo de empleo / relación laboral (relab) como factor
    cat_relab = as.factor(relab),
    
    # Posición como jefe(a) de hogar
    head_hh = ifelse(p6050 == 1, 1, 0),
    
    # Indicador de formalidad (si está reportado)
    formal = as.factor(formal)
  )

# 6. Exportar base limpia
message("Exportando base limpia a: ", output_path)
rio::export(db_clean, output_path)
message("✅ Proceso de limpieza finalizado con éxito.")
