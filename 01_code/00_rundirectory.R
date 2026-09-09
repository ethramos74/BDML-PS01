# ==============================================================================
# Archivo:   01_code/00_rundirectory.R
# Proposito: Script maestro. Reproduce de principio a fin los resultados del
#            repositorio a partir de los datos crudos.
#
# Uso:       Desde una sesion de R en la raiz del proyecto,
#              source("01_code/00_rundirectory.R")
#
# Cadena de dependencias:
#   01_scraping.R -> 02_outputs/data_geih_consolidada.rds
#   02_cleaning.R -> 02_outputs/data_geih_cleaned.rds
#   03 / 04 / 04b / 05 -> 02_outputs/tables y 02_outputs/figures
#
# Las tres secciones parten de la MISMA base limpia, de modo que los
# resultados sean comparables entre secciones.
# ==============================================================================

rm(list = ls()); cat("\014"); gc()

if (!require(pacman)) install.packages("pacman")
pacman::p_load(here)   # Rutas relativas a la raiz del repositorio

message("Raiz del proyecto: ", here())

# 1. Descarga y consolidacion de los 10 chunks de la GEIH 2018.
#    El script se omite solo si la base consolidada ya existe localmente.
source(here("01_code", "01_scraping.R"))

# 2. Filtros muestrales y construccion de variables.
source(here("01_code", "02_cleaning.R"))

# 3. Seccion 1: perfil edad-ingreso.
# source(here("01_code", "03_estimate_age_income_profile.R"))

# 4. Seccion 2: brecha de ingreso por genero.
source(here("01_code", "04_gender_gap.R"))

# 4b. Seccion 2: diagnostico de regresion y analisis de sensibilidad.
source(here("01_code", "04b_diagnostics_gender_gap.R"))

# 5. Seccion 3: desempeno predictivo fuera de muestra.
# source(here("01_code", "05_evaluate_prediction_models.R"))

message("Listo. Revisar 02_outputs/tables y 02_outputs/figures.")
