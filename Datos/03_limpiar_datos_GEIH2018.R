# =============================================================================
# PROBLEM SET 1 | GEIH 2018, BOGOTA
# 03. Limpieza: una sola muestra de analisis para las tres secciones
# =============================================================================
# OBJETIVO
# Construir, una unica vez, la base con la que trabajan las secciones 1, 2 y 3
# del problem set, a partir de la copia tipada que produce el script 02.
#
# DECISIONES (todas explicitas y parametrizadas en CONFIGURACION)
# 1. Poblacion: ocupados (ocu = 1) de 18 anos o mas, como exige el enunciado.
# 2. Ingreso: y_total_m (asalariados + independientes, mensual nominal 2018).
#    Los ocupados 18+ sin y_total_m NO entran a la muestra principal, pero se
#    conservan en la base ampliada con un motivo de exclusion. Son de dos tipos:
#    (a) trabajadores sin remuneracion (relab 6 y 7), que no tienen ingreso por
#    definicion; (b) asalariados con p6500 = 0 e independientes con p6750 NA,
#    que SI tienen empleo remunerado (jornada completa, antiguedad, primas,
#    formalidad) pero no reportaron el monto: es no respuesta, no ingreso cero.
#    El DANE los marca como faltantes (cclasnr2 = 1) y les imputa impaes, que se
#    conserva como referencia para robustez. Aqui no se imputa.
# 3. Extremos: no se recorta ni se winsoriza. Se crean banderas (alerta_*) para
#    analisis de robustez en cada seccion: ingreso por hora muy bajo, ingreso
#    mensual muy alto, jornadas implausibles y valores que el propio DANE
#    reemplazo por imputacion al considerarlos extremos (impaes).
# 4. Categoricas: relab, oficio, educacion, estrato y tamano de firma quedan
#    como factores con etiquetas. Los oficios con pocas observaciones se agrupan
#    en "Otros" para que todo nivel de validacion exista en entrenamiento;
#    relab 8 y 9 (9 personas) se funden en "Otro".
# 5. college se descarta: en la fuente marca secundaria completa, no terciaria
#    (ver validacion 7.12). Se reconstruye como `terciaria` desde maxEducLevel.
# 6. No se ponderan los modelos; fex_c se conserva por si alguna descriptiva
#    quiere hablar de Bogota y no de la muestra.
#
# SALIDAS
# datos/limpios/geih2018_muestra.rds      Muestra principal (una fila por persona).
# datos/limpios/geih2018_ocupados18.rds   Base ampliada: ocupados 18+, con
#                                          muestra_principal y motivo_exclusion.
# auditoria/limpieza/embudo_muestra.csv, exclusiones_por_motivo.csv,
#   alertas.csv, oficios_agrupados.csv, descriptivas_muestra.csv,
#   diccionario_variables.csv, sessionInfo.txt
#
# PIPELINE DE DATOS DEL PROBLEM SET (ejecutar en orden)
# 01_obtener_datos_GEIH2018.R   descarga y consolida
# 02_validar_datos_GEIH2018.R   valida la base y crea la copia tipada
# 03_limpiar_datos_GEIH2018.R   construye la muestra de analisis unica (este)
#
# RUTA DEL PROYECTO
# La raiz PS1_GEIH2018 se resuelve igual en los tres scripts: la variable de
# entorno PS1_GEIH2018_DIR si existe; si no, la subcarpeta PS1_GEIH2018 del
# directorio de trabajo (abra el proyecto de RStudio en "Taller 1").
#
# LO QUE DICE EL DANE SOBRE LAS VARIABLES QUE SE USAN AQUI (catalogo 547)
# - sex es P6020 recodificada (DANE 1 = hombre, 2 = mujer; aqui 1 = hombre, 0 = mujer).
# - p6210s1 registra 0 si cursa el primer ano o no aprobo grado; en educacion
#   superior son anos completos aprobados. Es la base de anios_educ.
# - oficio es la CNO-70 del SENA (subgrupos, 2 digitos); el DANE la guarda como
#   texto. Aqui es factor. RAMA2D (sector) y ESC (anos de escolaridad DANE) no
#   vienen en la muestra del curso: son limitaciones declaradas.
# - totalHoursWorked = p6800 (horas normales, principal) + p7045 (segundo empleo).
# - Los codigos 98/99 de "no sabe el monto" ya no estan en los montos (validado).
#
# USO EN RSTUDIO
# 1. Ejecute antes 02_validar_datos_GEIH2018.R (crea geih2018_tipado.rds). Si
#    no existe, este script convierte la base original por su cuenta.
# 2. Revise CONFIGURACION y ejecute con Source.
# 3. En cada seccion: muestra <- readRDS(".../datos/limpios/geih2018_muestra.rds")
#    Para robustez sin extremos: dplyr::filter(muestra, !alerta_extremo).
#    Para robustez con imputacion DANE de los que no reportaron monto: en la base
#    ampliada, usar impaes donde dane_faltante == 1.
#
# Para cargar SOLO las funciones: options(geih.limpiar = FALSE) antes de source().
# Dependencias: dplyr (>= 1.0). Estilo: tidyverse style guide, pipe nativo |>.
# =============================================================================

# 1. CONFIGURACION --------------------------------------------------------------

# Raiz del proyecto compartida por los scripts 01, 02 y 03 (ver encabezado).
carpeta_proyecto_geih <- function() {
  ruta <- Sys.getenv("PS1_GEIH2018_DIR", unset = "")
  if (nzchar(ruta)) ruta else file.path(getwd(), "PS1_GEIH2018")
}

config_limpieza <- list(
  carpeta_proyecto = carpeta_proyecto_geih(),
  archivo_tipado = NULL,      # NULL: <proyecto>/datos/intermedios/geih2018_tipado.rds
  archivo_original = NULL,    # NULL: <proyecto>/datos/brutos/geih2018_original.rds
  carpeta_limpios = NULL,     # NULL: <proyecto>/datos/limpios
  carpeta_auditoria = NULL,   # NULL: <proyecto>/auditoria/limpieza
  edad_minima = 18,
  smmlv_2018 = 781242,            # Salario minimo mensual legal vigente 2018 (pesos).
  horas_semana_referencia = 48,   # Jornada legal 2018, para el minimo por hora.
  fraccion_minimo_hora = 0.25,    # alerta_ingreso_bajo: ingreso/hora < 25% del minimo/hora.
  multiplo_smmlv_alto = 20,       # alerta_ingreso_alto: ingreso mensual > 20 SMMLV.
  horas_maximas_plausibles = 84,  # alerta_horas_altas: mas de 12 horas x 7 dias.
  min_obs_oficio = 20,            # Oficios con menos obs. en la muestra principal -> "Otros".
  exportar_csv = FALSE,           # TRUE: tambien guarda la muestra principal como CSV.
  instalar_faltantes = TRUE
)

# 2. UTILIDADES -----------------------------------------------------------------

resolver_rutas_limpieza <- function(cfg) {
  raiz <- cfg$carpeta_proyecto
  if (is.null(cfg$archivo_tipado)) {
    cfg$archivo_tipado <- file.path(raiz, "datos", "intermedios", "geih2018_tipado.rds")
  }
  if (is.null(cfg$archivo_original)) {
    cfg$archivo_original <- file.path(raiz, "datos", "brutos", "geih2018_original.rds")
  }
  if (is.null(cfg$carpeta_limpios)) cfg$carpeta_limpios <- file.path(raiz, "datos", "limpios")
  if (is.null(cfg$carpeta_auditoria)) cfg$carpeta_auditoria <- file.path(raiz, "auditoria", "limpieza")
  cfg
}

comprobar_paquetes_limpieza <- function(instalar = FALSE) {
  if (!requireNamespace("dplyr", quietly = TRUE) && instalar) {
    utils::install.packages("dplyr", repos = "https://cloud.r-project.org")
  }
  if (!requireNamespace("dplyr", quietly = TRUE)) {
    stop("Instale el paquete dplyr y ejecute de nuevo.", call. = FALSE)
  }
  if (utils::packageVersion("dplyr") < package_version("1.0.0")) {
    stop("Actualice dplyr a una version >= 1.0.0.", call. = FALSE)
  }
}

escribir_csv <- function(datos, archivo) {
  utils::write.csv(datos, archivo, row.names = FALSE, fileEncoding = "UTF-8", na = "NA")
}

# Lee la copia tipada del script 02; si no existe, convierte la base original.
cargar_base_tipada <- function(cfg) {
  if (file.exists(cfg$archivo_tipado)) {
    message("Leyendo base tipada: ", cfg$archivo_tipado)
    return(readRDS(cfg$archivo_tipado))
  }
  if (!file.exists(cfg$archivo_original)) {
    stop("No se encontro ni la base tipada ni la original. Ejecute los scripts 01 y 02.",
         call. = FALSE)
  }
  message("No existe la base tipada; convirtiendo la original: ", cfg$archivo_original)
  no_convertir <- c("dominio", "url_origen", "muestra_ps3", "chunk")
  readRDS(cfg$archivo_original) |>
    dplyr::mutate(dplyr::across(
      -dplyr::any_of(no_convertir),
      ~ as.numeric(dplyr::na_if(.x, "NA"))
    ))
}

# 3. ETIQUETAS ------------------------------------------------------------------

etiquetas_relab <- c(
  "1" = "Obrero/empleado particular", "2" = "Empleado del gobierno",
  "3" = "Empleado domestico", "4" = "Cuenta propia", "5" = "Patron/empleador",
  "6" = "Sin remuneracion", "7" = "Sin remuneracion", "8" = "Otro", "9" = "Otro"
)
niveles_relab <- c("Obrero/empleado particular", "Empleado del gobierno",
                   "Empleado domestico", "Cuenta propia", "Patron/empleador",
                   "Sin remuneracion", "Otro")

niveles_educ <- c("Ninguno", "Preescolar", "Primaria incompleta", "Primaria completa",
                  "Secundaria incompleta", "Secundaria completa", "Terciaria")

niveles_size_firm <- c("Independiente", "2-5 trabajadores", "6-10 trabajadores",
                       "11-50 trabajadores", "Mas de 50 trabajadores")

# Grupos mayores de la clasificacion de oficios a dos digitos (CNO-70).
cortes_oficio <- c(0, 19, 29, 39, 49, 59, 69, 99)
niveles_oficio_grupo <- c("Profesionales y tecnicos", "Directivos", "Administrativos",
                          "Comerciantes y vendedores", "Servicios", "Agropecuarios",
                          "Operarios y transporte")

# 4. CONSTRUCCION DE LA BASE ----------------------------------------------------

seleccionar_y_construir <- function(base, cfg) {
  umbral_hora_bajo <- cfg$smmlv_2018 / (cfg$horas_semana_referencia * 30 / 7) *
    cfg$fraccion_minimo_hora
  umbral_mensual_alto <- cfg$multiplo_smmlv_alto * cfg$smmlv_2018

  base |>
    dplyr::filter(ocu == 1, age >= cfg$edad_minima) |>
    dplyr::mutate(
      # Identificacion y diseno
      id_persona = paste(directorio, secuencia_p, orden, sep = "-"),
      entrenamiento = muestra_ps3 == "entrenamiento",
      mes_f = factor(mes, levels = 1:12),

      # Resultado
      log_y = log(y_total_m),

      # Demografia
      female = 1L - as.integer(sex),
      jefe_hogar = as.integer(p6050 == 1),
      estrato_f = factor(estrato1, levels = 1:6),

      # Educacion
      educ_f = factor(maxEducLevel, levels = 1:7, labels = niveles_educ),
      terciaria = as.integer(maxEducLevel == 7),
      p6210s1 = as.numeric(p6210s1),
      anios_educ = dplyr::case_when(
        is.na(p6210) | p6210 == 9 | is.na(p6210s1) | p6210s1 == 99 ~ NA_real_,
        p6210 %in% c(1, 2) ~ 0,
        p6210 == 3 ~ p6210s1,
        p6210 == 4 ~ dplyr::if_else(p6210s1 == 0, 5, p6210s1),
        p6210 == 5 ~ dplyr::if_else(p6210s1 == 0, 9, p6210s1),
        p6210 == 6 ~ 11 + p6210s1
      ),

      # Empleo
      relab_f = factor(unname(etiquetas_relab[as.character(relab)]), levels = niveles_relab),
      oficio_grupo = cut(oficio, breaks = cortes_oficio, labels = niveles_oficio_grupo),
      sizeFirm_f = factor(sizeFirm, levels = 1:5, labels = niveles_size_firm),
      cotiza_pension = as.integer(cotPension == 1),
      antiguedad_anios = as.numeric(p6426) / 12,
      segundo_empleo = as.integer(p7040 == 1),

      # Exclusion de la muestra principal (solo por ingreso; no se imputa)
      motivo_exclusion = dplyr::case_when(
        !is.na(y_total_m) & y_total_m > 0 ~ NA_character_,
        !is.na(y_total_m) & y_total_m <= 0 ~ "Ingreso reportado igual a 0",
        relab %in% c(6, 7) ~ "Sin remuneracion por definicion (relab 6 o 7)",
        relab %in% c(1, 2, 3, 8) ~ "Asalariado que no reporto el monto (p6500 = 0; DANE lo imputa)",
        relab %in% c(4, 5, 9) ~ "Independiente o patron que no reporto el monto (p6750 NA; DANE lo imputa)",
        TRUE ~ "Sin ingreso reportado"
      ),
      dane_faltante = as.integer(cclasnr2 == 1),
      muestra_principal = is.na(motivo_exclusion),

      # Alertas de valores extremos (no excluyen; sirven para robustez)
      alerta_ingreso_bajo = !is.na(y_total_m_ha) & y_total_m_ha < umbral_hora_bajo,
      alerta_ingreso_alto = !is.na(y_total_m) & y_total_m > umbral_mensual_alto,
      alerta_horas_altas = totalHoursWorked > cfg$horas_maximas_plausibles,
      # El DANE reemplaza en impaes los ingresos que juzga extremos: si hay
      # impaes y tambien y_total_m observado, el DANE no creyo el valor.
      alerta_dane_extremo = !is.na(y_total_m) & !is.na(impaes),
      alerta_extremo = alerta_ingreso_bajo | alerta_ingreso_alto | alerta_horas_altas |
        alerta_dane_extremo
    ) |>
    dplyr::select(
      # Identificacion y diseno muestral
      id_persona, directorio, secuencia_p, orden, chunk, muestra_ps3, entrenamiento,
      mes, mes_f, fex_c,
      # Muestra
      muestra_principal, motivo_exclusion,
      # Resultado y componentes
      y_total_m, log_y, y_total_m_ha, y_ingLab_m, y_gananciaIndep_m, y_salary_m,
      impa, impaes, dane_faltante,
      # Demografia
      age, sex, female, jefe_hogar, estrato1, estrato_f,
      # Educacion
      maxEducLevel, educ_f, terciaria, anios_educ, p6210, p6210s1,
      # Empleo
      relab, relab_f, oficio, oficio_grupo, sizeFirm, sizeFirm_f, microEmpresa,
      cuentaPropia, formal, cotPension, cotiza_pension, regSalud, p6426,
      antiguedad_anios, totalHoursWorked, hoursWorkUsual, segundo_empleo,
      # Alertas
      alerta_ingreso_bajo, alerta_ingreso_alto, alerta_horas_altas, alerta_dane_extremo,
      alerta_extremo
    )
}

# Agrupa en "Otros" los oficios con pocas observaciones en la muestra principal.
# Devuelve la base con oficio_f y la tabla de oficios agrupados.
agrupar_oficios <- function(ocupados, cfg) {
  conteo <- ocupados |>
    dplyr::filter(muestra_principal) |>
    dplyr::count(oficio, name = "n_muestra_principal") |>
    dplyr::mutate(agrupado_en_otros = n_muestra_principal < cfg$min_obs_oficio) |>
    dplyr::arrange(oficio)
  raros <- conteo$oficio[conteo$agrupado_en_otros]
  niveles <- c(sprintf("%02d", conteo$oficio[!conteo$agrupado_en_otros]), "Otros")

  ocupados <- ocupados |>
    dplyr::mutate(
      oficio_f = dplyr::if_else(oficio %in% raros, "Otros", sprintf("%02d", oficio)),
      # Oficios que solo aparecen fuera de la muestra principal tambien van a Otros.
      oficio_f = dplyr::if_else(oficio_f %in% niveles, oficio_f, "Otros"),
      oficio_f = factor(oficio_f, levels = niveles)
    ) |>
    dplyr::relocate(oficio_f, .after = oficio)
  list(datos = ocupados, oficios = conteo)
}

# 5. DOCUMENTACION DE LA BASE ---------------------------------------------------

diccionario_variables <- function() {
  dplyr::tribble(
    ~variable, ~descripcion, ~origen,
    "id_persona", "Llave unica de persona: directorio-secuencia_p-orden", "construida",
    "directorio", "Llave de vivienda (GEIH)", "original",
    "secuencia_p", "Llave de hogar dentro de la vivienda", "original",
    "orden", "Llave de persona dentro del hogar", "original",
    "chunk", "Bloque del sitio (1-10); sigue el calendario de la encuesta", "script 01",
    "muestra_ps3", "entrenamiento (bloques 1-7) o validacion (bloques 8-10), seccion 3", "script 01",
    "entrenamiento", "TRUE si muestra_ps3 == entrenamiento", "construida",
    "mes", "Mes de la entrevista (1-12)", "original",
    "mes_f", "mes como factor", "construida",
    "fex_c", "Factor de expansion anualizado (no se usa en los modelos)", "original",
    "muestra_principal", "TRUE si la persona entra a la muestra de analisis (ingreso positivo observado)", "construida",
    "motivo_exclusion", "Por que no entra a la muestra principal; NA si entra", "construida",
    "y_total_m", "Ingreso laboral mensual nominal 2018: asalariado + independiente (pesos)", "original",
    "log_y", "log(y_total_m); variable dependiente de las tres secciones", "construida",
    "y_total_m_ha", "Ingreso laboral por hora = y_total_m / (totalHoursWorked x 30/7)", "original",
    "y_ingLab_m", "Componente asalariado de y_total_m (todas las ocupaciones)", "original",
    "y_gananciaIndep_m", "Componente independiente de y_total_m (= p6750 / p6760)", "original",
    "y_salary_m", "Salario mensual ocupacion principal (= p6500; 0 convertido a NA en la fuente)", "original",
    "impa", "Ingreso monetario primera actividad segun DANE, antes de imputacion (referencia)", "original",
    "impaes", "Ingreso primera actividad imputado por DANE, solo faltantes/extremos (referencia)", "original",
    "dane_faltante", "1 si el DANE clasifico el ingreso de la primera actividad como faltante (cclasnr2 == 1): no respuesta del monto", "construida",
    "age", "Edad en anos", "original",
    "sex", "1 = hombre, 0 = mujer (codificacion de la fuente)", "original",
    "female", "1 = mujer, 0 = hombre (= 1 - sex)", "construida",
    "jefe_hogar", "1 si es jefe o jefa del hogar (p6050 == 1)", "construida",
    "estrato1", "Estrato socioeconomico de la vivienda (1-6)", "original",
    "estrato_f", "estrato1 como factor", "construida",
    "maxEducLevel", "Maximo nivel educativo (1 ninguno ... 7 terciaria)", "original",
    "educ_f", "maxEducLevel como factor con etiquetas", "construida",
    "terciaria", "1 si educacion terciaria (maxEducLevel == 7); reemplaza a college", "construida",
    "anios_educ", "Anos de educacion aproximados desde p6210 y p6210s1 (superior = 11 + anos aprobados)", "construida",
    "p6210", "Nivel educativo mas alto (pregunta original)", "original",
    "p6210s1", "Ultimo grado o ano aprobado en ese nivel", "original",
    "relab", "Tipo de ocupacion (1-9, codigo original)", "original",
    "relab_f", "relab como factor; 6 y 7 = Sin remuneracion, 8 y 9 = Otro", "construida",
    "oficio", "Ocupacion a dos digitos (codigo original)", "original",
    "oficio_f", "oficio como factor; codigos con pocas observaciones agrupados en Otros", "construida",
    "oficio_grupo", "Grupo mayor de ocupacion (7 categorias)", "construida",
    "sizeFirm", "Tamano de la empresa (1-5, codigo original)", "original",
    "sizeFirm_f", "sizeFirm como factor con etiquetas", "construida",
    "microEmpresa", "1 si la empresa tiene 5 trabajadores o menos (incluye cuenta propia)", "original",
    "cuentaPropia", "1 si trabajador por cuenta propia (relab == 4)", "original",
    "formal", "1 si formal segun seguridad social (definicion de la fuente)", "original",
    "cotPension", "1 cotiza, 2 no cotiza, 3 pensionado", "original",
    "cotiza_pension", "1 si cotiza actualmente a pension (cotPension == 1)", "construida",
    "regSalud", "Regimen de salud: 1 contributivo, 2 especial, 3 subsidiado; NA frecuente", "original",
    "p6426", "Meses en la empresa o negocio actual", "original",
    "antiguedad_anios", "p6426 / 12", "construida",
    "totalHoursWorked", "Horas trabajadas la semana pasada, todas las ocupaciones", "original",
    "hoursWorkUsual", "Horas semanales usuales en la ocupacion principal", "original",
    "segundo_empleo", "1 si tenia un segundo trabajo la semana pasada (p7040 == 1)", "construida",
    "alerta_ingreso_bajo", "TRUE si el ingreso por hora es menor que la fraccion configurada del minimo por hora", "construida",
    "alerta_ingreso_alto", "TRUE si el ingreso mensual supera el multiplo configurado del SMMLV", "construida",
    "alerta_horas_altas", "TRUE si totalHoursWorked supera el maximo plausible configurado", "construida",
    "alerta_dane_extremo", "TRUE si el DANE reemplazo el ingreso observado por un valor imputado (impaes no NA con y_total_m observado): lo juzgo extremo", "construida",
    "alerta_extremo", "TRUE si se activa cualquiera de las alertas anteriores", "construida"
  )
}

describir_muestra <- function(muestra) {
  resumir <- function(d) {
    d |>
      dplyr::summarise(
        n = dplyr::n(),
        ingreso_mediana = stats::median(y_total_m),
        ingreso_media = mean(y_total_m),
        log_y_media = mean(log_y),
        log_y_sd = stats::sd(log_y),
        edad_media = mean(age),
        prop_mujeres = mean(female),
        horas_media = mean(totalHoursWorked),
        prop_formal = mean(formal),
        prop_cuenta_propia = mean(cuentaPropia),
        prop_terciaria = mean(terciaria, na.rm = TRUE),
        prop_alerta_extremo = mean(alerta_extremo),
        .groups = "drop"
      )
  }
  dplyr::bind_rows(
    muestra |> dplyr::mutate(particion = "total") |> dplyr::group_by(particion) |> resumir(),
    muestra |> dplyr::group_by(particion = muestra_ps3) |> resumir()
  )
}

# 6. EJECUCION COMPLETA ---------------------------------------------------------

limpiar_geih <- function(cfg = config_limpieza) {
  comprobar_paquetes_limpieza(cfg$instalar_faltantes)
  cfg <- resolver_rutas_limpieza(cfg)
  dir.create(cfg$carpeta_limpios, recursive = TRUE, showWarnings = FALSE)
  dir.create(cfg$carpeta_auditoria, recursive = TRUE, showWarnings = FALSE)

  base <- cargar_base_tipada(cfg)
  n_base <- nrow(base)
  n_ocupados <- sum(base$ocu == 1, na.rm = TRUE)

  message("Construyendo la base de ocupados de ", cfg$edad_minima, "+ ...")
  ocupados <- seleccionar_y_construir(base, cfg)
  resultado_oficios <- agrupar_oficios(ocupados, cfg)
  ocupados <- resultado_oficios$datos

  muestra <- ocupados |>
    dplyr::filter(muestra_principal) |>
    dplyr::select(-muestra_principal, -motivo_exclusion) |>
    droplevels()

  # Controles de integridad de la muestra principal ----------------------------
  stopifnot(
    !anyDuplicated(muestra$id_persona),
    all(muestra$y_total_m > 0), all(is.finite(muestra$log_y)),
    all(!is.na(muestra$age)), all(muestra$age >= cfg$edad_minima),
    all(muestra$female %in% 0:1), all(!is.na(muestra$relab_f)),
    all(!is.na(muestra$totalHoursWorked)), all(!is.na(muestra$oficio_f)),
    all(muestra$muestra_ps3 %in% c("entrenamiento", "validacion"))
  )
  niveles_val <- levels(droplevels(muestra$oficio_f[!muestra$entrenamiento]))
  niveles_ent <- levels(droplevels(muestra$oficio_f[muestra$entrenamiento]))
  if (length(setdiff(niveles_val, niveles_ent)) > 0L) {
    warning("oficio_f tiene niveles solo en validacion: ",
            paste(setdiff(niveles_val, niveles_ent), collapse = ", "),
            ". Suba min_obs_oficio.", call. = FALSE)
  }

  # Auditoria --------------------------------------------------------------------
  embudo <- dplyr::tibble(
    paso = 1:4,
    descripcion = c(
      "Base tipada (todas las personas)",
      "Ocupados (ocu == 1)",
      paste0("Ocupados de ", cfg$edad_minima, " anos o mas (base ampliada)"),
      "Con ingreso laboral positivo observado (muestra principal)"
    ),
    n_personas = c(n_base, n_ocupados, nrow(ocupados), nrow(muestra))
  ) |>
    dplyr::mutate(n_excluidas = dplyr::lag(n_personas) - n_personas)

  exclusiones <- ocupados |>
    dplyr::filter(!muestra_principal) |>
    dplyr::count(motivo_exclusion, relab_f, name = "n") |>
    dplyr::arrange(motivo_exclusion, relab_f)

  alertas <- muestra |>
    dplyr::group_by(particion = muestra_ps3) |>
    dplyr::summarise(
      n = dplyr::n(),
      alerta_ingreso_bajo = sum(alerta_ingreso_bajo),
      alerta_ingreso_alto = sum(alerta_ingreso_alto),
      alerta_horas_altas = sum(alerta_horas_altas),
      alerta_dane_extremo = sum(alerta_dane_extremo),
      alerta_extremo = sum(alerta_extremo),
      .groups = "drop"
    )

  descriptivas <- describir_muestra(muestra)
  diccionario <- diccionario_variables()

  sin_documentar <- setdiff(names(ocupados), diccionario$variable)
  if (length(sin_documentar) > 0L) {
    stop("Variables sin documentar en diccionario_variables(): ",
         paste(sin_documentar, collapse = ", "), call. = FALSE)
  }
  diccionario <- diccionario |>
    dplyr::mutate(
      en_muestra_principal = variable %in% names(muestra),
      tipo_R = vapply(variable, function(v) class(ocupados[[v]])[1L], character(1))
    )

  # Guardar ----------------------------------------------------------------------
  archivo_muestra <- file.path(cfg$carpeta_limpios, "geih2018_muestra.rds")
  archivo_ocupados <- file.path(cfg$carpeta_limpios, "geih2018_ocupados18.rds")
  saveRDS(muestra, archivo_muestra)
  saveRDS(ocupados, archivo_ocupados)
  if (isTRUE(cfg$exportar_csv)) {
    escribir_csv(muestra, file.path(cfg$carpeta_limpios, "geih2018_muestra.csv"))
  }
  escribir_csv(embudo, file.path(cfg$carpeta_auditoria, "embudo_muestra.csv"))
  escribir_csv(exclusiones, file.path(cfg$carpeta_auditoria, "exclusiones_por_motivo.csv"))
  escribir_csv(alertas, file.path(cfg$carpeta_auditoria, "alertas.csv"))
  escribir_csv(resultado_oficios$oficios, file.path(cfg$carpeta_auditoria, "oficios_agrupados.csv"))
  escribir_csv(descriptivas, file.path(cfg$carpeta_auditoria, "descriptivas_muestra.csv"))
  escribir_csv(diccionario, file.path(cfg$carpeta_auditoria, "diccionario_variables.csv"))
  saveRDS(cfg, file.path(cfg$carpeta_auditoria, "configuracion_limpieza.rds"))
  writeLines(utils::capture.output(utils::sessionInfo()),
             file.path(cfg$carpeta_auditoria, "sessionInfo.txt"), useBytes = TRUE)

  # Resumen en consola -----------------------------------------------------------
  message("\n=== Embudo de la muestra ===")
  print(as.data.frame(embudo), row.names = FALSE)
  message("\n=== Exclusiones de la muestra principal ===")
  print(as.data.frame(exclusiones), row.names = FALSE)
  message("\n=== Alertas dentro de la muestra principal (no excluyen) ===")
  print(as.data.frame(alertas), row.names = FALSE)
  message("\n=== Oficios agrupados en Otros: ",
          sum(resultado_oficios$oficios$agrupado_en_otros), " codigos, ",
          sum(resultado_oficios$oficios$n_muestra_principal[resultado_oficios$oficios$agrupado_en_otros]),
          " personas ===")
  message("\n=== Descriptivas de la muestra principal ===")
  print(as.data.frame(descriptivas), row.names = FALSE, digits = 4)
  message("\nMuestra principal: ", nrow(muestra), " personas, ", ncol(muestra), " variables -> ",
          normalizePath(archivo_muestra, winslash = "/"))
  message("Base ampliada:     ", nrow(ocupados), " ocupados 18+ -> ",
          normalizePath(archivo_ocupados, winslash = "/"))

  invisible(list(muestra = muestra, ocupados = ocupados, embudo = embudo,
                 exclusiones = exclusiones, alertas = alertas, oficios = resultado_oficios$oficios,
                 descriptivas = descriptivas, diccionario = diccionario, configuracion = cfg))
}

# 7. PUNTO DE ENTRADA -----------------------------------------------------------

if (isTRUE(getOption("geih.limpiar", TRUE))) {
  limpieza_geih <- limpiar_geih(config_limpieza)
}
