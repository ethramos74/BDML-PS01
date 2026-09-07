##########################################################
# Master script
#
# Corre este archivo para reproducir todos los resultados
# del repositorio:
#
#   source("01_code/00_rundirectory.R")
#
# Este script solo llama a otros scripts. La lógica vive
# en cada uno de ellos.
#
# Las llamadas están comentadas hasta que el script
# correspondiente exista. Al terminar un script, se
# descomenta su línea acá.
##########################################################

# Paso 1: descargar los 10 chunks de la GEIH
# source("01_code/01_data_scraper.R")

# Paso 2: filtros muestrales y limpieza -> base única de análisis
# source("01_code/02_build_analysis_sample.R")

# Paso 3: Sección 1 - perfil edad-ingreso
# source("01_code/03_estimate_age_income_profile.R")

# Paso 4: Sección 2 - brecha de ingreso por género
# source("01_code/04_estimate_gender_gap.R")

# Paso 5: Sección 3 - desempeño predictivo fuera de muestra
# source("01_code/05_evaluate_prediction_models.R")
