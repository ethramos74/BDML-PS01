# ==============================================================================
# Archivo:   01_code/02_cleaning.R
# Proposito: Limpieza de datos de la GEIH 2018 para Bogota y construccion
#            de la muestra analitica comun para todas las secciones del PS1.
# Input:     02_outputs/data_geih_consolidada.rds
# Output:    02_outputs/data_geih_cleaned.rds
# ==============================================================================

# 1. Cargar librerias requeridas
if (!require(pacman)) install.packages("pacman")
pacman::p_load(
  tidyverse, # Manipulacion de datos
  rio,       # Importacion y exportacion eficiente
  here       # Rutas relativas basadas en la raiz del proyecto
)

# 2. Cargar base consolidada generada en 01_scraping.R
input_path  <- here("02_outputs", "data_geih_consolidada.rds")
output_path <- here("02_outputs", "data_geih_cleaned.rds")

if (!file.exists(input_path)) {
  stop("No se encontro la base consolidada en '", input_path,
       "'. Ejecuta primero 01_scraping.R.")
}

message("Cargando datos crudos consolidados...")
db_geih <- rio::import(input_path)

# 3. Construccion de variables a nivel de hogar
# El conteo de menores (<18 anios) debe realizarse sobre toda la estructura
# del hogar antes de filtrar por adultos ocupados.
message("Calculando variables a nivel de hogar...")
db_geih <- db_geih |>
  mutate(bin_minor = ifelse(age < 18, 1, 0)) |>
  group_by(directorio, secuencia_p) |>
  mutate(num_minors = sum(bin_minor, na.rm = TRUE)) |>
  ungroup() |>
  select(-bin_minor)

# 4. Aplicacion de filtros muestrales
# Restricciones del taller:
# - Adultos (age >= 18)
# - Ocupados (ocu == 1)
# - Ingreso laboral mensual positivo (y_total_m > 0)
# - Horas trabajadas positivas (totalHoursWorked > 0)
message("Filtrando la muestra analitica (adultos ocupados con ingresos positivos)...")
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

# 5. Estandarizacion y creacion de variables para el analisis
# Los codigos y etiquetas de las variables categoricas se tomaron del
# diccionario oficial del curso:
# https://ignaciomsarmiento.github.io/GEIH2018_sample/dictionary.html
# https://ignaciomsarmiento.github.io/GEIH2018_sample/labels.html
message("Generando variables de analisis (Mincer, sexo y controles)...")
db_clean <- db_sample |>
  mutate(
    # Variable de resultado principal
    ln_y_total_m = log(y_total_m),
    
    # Variable de tratamiento/interes para la Seccion 2 (1 = Mujer, 0 = Hombre)
    # Diccionario: sex = 1 hombre, sex = 0 mujer
    female = ifelse(sex == 0, 1, 0),
    
    # Variables de ciclo de vida (Seccion 1 y controles)
    age_sq = age^2,
    
    # Nivel educativo como factor con categoria de referencia
    # maxEducLevel: 1=None, 2=Preschool, 3=Primary_Incomplete (1-4),
    # 4=Primary_Complete (5), 5=Secondary_Incomplete (6-10),
    # 6=Secondary_Complete (11), 7=Tertiary, 9=N/A
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
    
    # Tipo de empleo / relacion laboral (relab) como factor etiquetado
    # 1=Empleado particular (referencia), 2=Empleado gobierno,
    # 3=Empleado domestico, 4=Cuenta propia, 5=Patron/empleador,
    # 6=Trabajador familiar sin remuneracion, 7=Trabajador sin remuneracion
    # (otros hogares), 8=Jornalero/peon, 9=Otro
    cat_relab = factor(
      relab,
      levels = 1:9,
      labels = c("Empleado_Particular", "Empleado_Gobierno",
                 "Empleado_Domestico", "Cuenta_Propia",
                 "Patron_Empleador", "Trabajador_Familiar_SR",
                 "Trabajador_SR_Otros_Hogares", "Jornalero_Peon", "Otro")
    ),
    
    # Posicion como jefe(a) de hogar
    head_hh = ifelse(p6050 == 1, 1, 0),
    
    # Indicador de formalidad (seguridad social): 0 = Informal (referencia),
    # 1 = Formal
    formal = factor(formal, levels = c(0, 1), labels = c("Informal", "Formal"))
  )

# 6. Exportar base limpia
message("Exportando base limpia a: ", output_path)
rio::export(db_clean, output_path)
message("Proceso de limpieza finalizado con exito.")