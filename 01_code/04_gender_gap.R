# ==============================================================================
# Archivo:   01_code/04_gender_gap.R
# Proposito: Resolver la Seccion 2 (Gender Labor Income Gap) del PS1:
#            1. Estimar la brecha incondicional.
#            2. Estimar modelos condicionales (Good Controls vs Bad Controls),
#               con discusion explicita de CUALES controles son discutibles.
#            3. Verificar consistencia de N entre modelos.
#            4. Descomposicion Frisch-Waugh-Lovell (FWL) y validacion numerica.
#            5. Errores estandar analiticos (HC1) vs Bootstrap no parametrico,
#               con manejo de errores y paralelizacion.
#            6. Perfiles edad-ingreso por sexo, peak ages e IC por bootstrap,
#               con chequeo de concavidad y de rango observado.
#            7. Exportacion de tablas (.tex) y figuras (.png).
# ==============================================================================

# 1. Dependencias
if (!require(pacman)) install.packages("pacman")
pacman::p_load(
  tidyverse,  # Manipulacion de datos y graficos
  rio,        # Importacion/exportacion
  here,       # Rutas relativas
  sandwich,   # Errores estandar robustos (HC1)
  lmtest,     # Coeftest para inferencia robusta
  boot,       # Bootstrap no parametrico
  stargazer,  # Exportacion de tablas en LaTeX
  parallel    # Deteccion de nucleos para paralelizar el bootstrap
)

# Fijar semilla para reproducibilidad del bootstrap
set.seed(202602)

# Configuracion de paralelizacion (multicore en Linux/Mac, snow en Windows)
os_type    <- .Platform$OS.type
boot_par   <- if (os_type == "windows") "snow" else "multicore"
boot_ncpus <- max(1, parallel::detectCores() - 1)

# Crear carpetas de salida si no existen
dir.create(here("02_outputs", "tables"), recursive = TRUE, showWarnings = FALSE)
dir.create(here("02_outputs", "figures"), recursive = TRUE, showWarnings = FALSE)

# 2. Cargar datos limpios
data_path <- here("02_outputs", "data_geih_cleaned.rds")
if (!file.exists(data_path)) {
  stop("No se encuentra 'data_geih_cleaned.rds'. Corre primero 02_cleaning.R")
}
df <- rio::import(data_path)

# --- Verificacion de integridad de 'female' ----------------------------------
# Chequeo de sanidad estandar antes de modelar.
message("Distribucion de 'female' (1 = mujer, 0 = hombre):")
print(table(df$female, useNA = "ifany"))
stopifnot(
  "'female' debe tener variacion (no puede ser constante) para poder estimarse" =
    length(unique(df$female)) > 1
)

# ==============================================================================
# 3. Modelos de Brecha de Genero (Incondicional y Condicionales)
# ==============================================================================
#
# NOTA METODOLOGICA SOBRE "BAD CONTROLS" (para justificar en la sustentacion):
# - age, age_sq, cat_educ: "good controls". Son en gran medida pre-determinados
#   respecto a la decision de participacion/salario actual, y estan motivados
#   por la teoria de capital humano (Seccion 1).
# - totalHoursWorked y num_minors: controles AMBIGUOS, no automaticamente
#   "buenos". Las horas trabajadas y el numero de menores a cargo pueden ser
#   CONSECUENCIA de la penalizacion por maternidad/roles de genero, no
#   caracteristicas exogenas. Si el genero afecta la decision de cuantas horas
#   trabajar (via normas sociales o carga de cuidado), controlar por horas
#   absorbe parte del efecto causal de genero que queremos medir, y el
#   coeficiente de 'female' en M3 debe leerse como "brecha condicional en
#   horas trabajadas y composicion del hogar", NO como la brecha total.
#   Se incluyen aqui porque es una decision defendible (aislar discriminacion
#   "dentro" de un mismo nivel de oferta laboral), pero debe explicitarse.
# - formal y cat_relab (Modelo 4): controles mas claramente "malos" para el
#   objetivo de medir discriminacion salarial, porque la segregacion
#   ocupacional y la informalidad son en parte MECANISMOS a traves de los
#   cuales opera la discriminacion de genero, no caracteristicas exogenas del
#   trabajador. Por eso M4 se reporta solo con fines de discusion/robustez y
#   NO se usa como especificacion preferida para FWL ni para los perfiles
#   edad-ingreso.

# Modelo 1: Incondicional (Linea base)
m1_incond <- lm(ln_y_total_m ~ female, data = df)

# Modelo 2: Capital Humano (Good controls: exogenos / pre-mercado)
m2_humcap <- lm(ln_y_total_m ~ female + age + age_sq + cat_educ, data = df)

# Modelo 3: Capital Humano + Composicion del Hogar y Oferta Laboral
#           (especificacion PREFERIDA; ver nota de bad controls arriba)
m3_oferta <- lm(ln_y_total_m ~ female + age + age_sq + cat_educ +
                  totalHoursWorked + num_minors, data = df)

# Modelo 4: Modelo Saturado con Atributos del Empleo (Bad Controls, solo
#           discusion/robustez, no se usa para FWL ni perfiles)
m4_puesto <- lm(ln_y_total_m ~ female + age + age_sq + cat_educ +
                  totalHoursWorked + num_minors + formal + cat_relab, data = df)

# --- Chequeo de consistencia muestral entre modelos -------------------------
# Si N difiere entre modelos, las comparaciones de coeficientes/R2 mezclan el
# efecto de los controles con cambios de composicion muestral por missings.
n_check <- c(M1 = nobs(m1_incond), M2 = nobs(m2_humcap),
             M3 = nobs(m3_oferta), M4 = nobs(m4_puesto))
message("Observaciones por modelo: ",
        paste(names(n_check), n_check, sep = "=", collapse = ", "))
if (length(unique(n_check)) > 1) {
  warning(paste(
    "Los modelos NO usan el mismo numero de observaciones (posibles NA en",
    "'formal' o 'cat_relab'). Considera restringir todos los modelos a la",
    "submuestra comun antes de comparar coeficientes/R2, o documentar",
    "explicitamente por que difieren."
  ))
}

# Calcular errores estandar robustos a heterocedasticidad (HC1 - White/sandwich)
se_m1_hc1 <- sqrt(diag(vcovHC(m1_incond, type = "HC1")))
se_m2_hc1 <- sqrt(diag(vcovHC(m2_humcap, type = "HC1")))
se_m3_hc1 <- sqrt(diag(vcovHC(m3_oferta, type = "HC1")))
se_m4_hc1 <- sqrt(diag(vcovHC(m4_puesto, type = "HC1")))

# --- Interpretacion economica exacta del coeficiente de genero --------------
# En un modelo log-lin, el efecto porcentual EXACTO de un dummy es
# 100 * (exp(beta) - 1), no simplemente 100 * beta (que es solo una
# aproximacion valida para betas pequenos).
pct_effect <- function(beta) 100 * (exp(beta) - 1)

message("--------------------------------------------------")
message("Brecha de genero: efecto porcentual EXACTO sobre el ingreso laboral")
message(sprintf("  M1 Incondicional          : %.2f%%", pct_effect(coef(m1_incond)["female"])))
message(sprintf("  M2 + Capital humano       : %.2f%%", pct_effect(coef(m2_humcap)["female"])))
message(sprintf("  M3 + Oferta laboral/hogar : %.2f%%", pct_effect(coef(m3_oferta)["female"])))
message(sprintf("  M4 + Atributos del empleo : %.2f%%", pct_effect(coef(m4_puesto)["female"])))
message("--------------------------------------------------")

# Significancia estadistica (HC1) del coeficiente de genero en cada modelo
for (mod_name in c("m1_incond", "m2_humcap", "m3_oferta", "m4_puesto")) {
  mod <- get(mod_name)
  ct  <- coeftest(mod, vcov. = vcovHC(mod, type = "HC1"))
  
  if (!"female" %in% rownames(ct)) {
    message(sprintf("[%s] 'female' no es estimable (colinealidad perfecta).", mod_name))
    next
  }
  
  message(sprintf("%s | female: beta=%.4f, SE(HC1)=%.4f, p=%.4f",
                  mod_name, ct["female", 1], ct["female", 2], ct["female", 4]))
}

# ==============================================================================
# 4. Descomposicion Frisch-Waugh-Lovell (FWL)
#    Aplicada a la especificacion preferida (Modelo 3: Capital Humano + Hogar)
# ==============================================================================

controles_fwl <- ~ age + age_sq + cat_educ + totalHoursWorked + num_minors

# Paso 1: Regresar Y (ln_y_total_m) sobre W y extraer residuos (Y_tilde)
res_y <- residuals(lm(update(controles_fwl, ln_y_total_m ~ .), data = df))

# Paso 2: Regresar D (female) sobre W y extraer residuos (D_tilde)
res_d <- residuals(lm(update(controles_fwl, female ~ .), data = df))

# Paso 3: Regresion simple de Y_tilde sobre D_tilde (sin intercepto, ya que
#         ambos residuos tienen media cero por construccion)
fwl_fit <- lm(res_y ~ res_d - 1)

# Verificacion de identidad numerica del teorema FWL
beta_m3  <- coef(m3_oferta)["female"]
beta_fwl <- coef(fwl_fit)["res_d"]

message("--------------------------------------------------")
message(paste("Coeficiente female en regresion multiple   :", round(beta_m3, 6)))
message(paste("Coeficiente female via descomposicion FWL  :", round(beta_fwl, 6)))
message(paste("Diferencia absoluta (tolerancia max 1e-7)  :", abs(beta_m3 - beta_fwl)))
message("--------------------------------------------------")

# ==============================================================================
# 5. Inferencia: Bootstrap no parametrico para coeficientes de genero
# ==============================================================================

message("Ejecutando Bootstrap no parametrico (B = 1000 repeticiones)...")

# Funcion estadistica para el paquete boot, CON manejo de errores: en un
# remuestreo con reemplazo es posible (aunque poco probable) que alguna
# categoria de un factor (cat_educ, cat_relab, formal) quede sin
# observaciones, lo que rompe lm(). Sin este tryCatch, una sola replica mala
# tumba las 1000 iteraciones despues de varios minutos de computo.
boot_gender_fn <- function(data, indices) {
  d_boot <- data[indices, ]
  tryCatch({
    fit1 <- lm(ln_y_total_m ~ female, data = d_boot)
    fit2 <- lm(ln_y_total_m ~ female + age + age_sq + cat_educ, data = d_boot)
    fit3 <- lm(ln_y_total_m ~ female + age + age_sq + cat_educ +
                 totalHoursWorked + num_minors, data = d_boot)
    fit4 <- lm(ln_y_total_m ~ female + age + age_sq + cat_educ +
                 totalHoursWorked + num_minors + formal + cat_relab, data = d_boot)
    c(coef(fit1)["female"], coef(fit2)["female"],
      coef(fit3)["female"], coef(fit4)["female"])
  }, error = function(e) {
    c(NA_real_, NA_real_, NA_real_, NA_real_)
  })
}

# 1,000 replicaciones bootstrap (paralelizadas)
boot_results <- boot(
  data = df, statistic = boot_gender_fn, R = 1000,
  parallel = boot_par, ncpus = boot_ncpus
)

# Reportar si alguna replica fallo (quedo en NA) antes de calcular el SE
n_failed <- colSums(is.na(boot_results$t))
if (any(n_failed > 0)) {
  message("Replicas bootstrap descartadas por modelo (NA): ",
          paste(n_failed, collapse = ", "))
}

# Errores estandar por bootstrap (desviacion estandar muestral de las replicas)
se_boot <- apply(boot_results$t, 2, sd, na.rm = TRUE)

# ==============================================================================
# 6. Exportar Tabla Comparativa de Brecha de Genero (LaTeX)
# ==============================================================================

se_analytical_list <- list(se_m1_hc1, se_m2_hc1, se_m3_hc1, se_m4_hc1)

stargazer(
  m1_incond, m2_humcap, m3_oferta, m4_puesto,
  type = "latex",
  out = here("02_outputs", "tables", "table_gender_gap.tex"),
  title = "Gender Wage Gap Specifications in Bogota (GEIH 2018)",
  label = "tab:gender_gap",
  dep.var.labels = "Log Monthly Labor Income",
  column.labels = c("Unconditional", "Human Capital", "Labor Supply/HH", "Job Attributes"),
  keep = c("female"),
  keep.stat = c("n", "rsq", "adj.rsq"),   # asegura medida de ajuste explicita
  se = se_analytical_list,
  add.lines = list(
    c("Bootstrap SE (female)", round(se_boot[1], 4), round(se_boot[2], 4),
      round(se_boot[3], 4), round(se_boot[4], 4)),
    c("Age and Education controls", "No", "Yes", "Yes", "Yes"),
    c("Hours and Household controls", "No", "No", "Yes", "Yes"),
    c("Job/Firm Controls (Bad Controls)", "No", "No", "No", "Yes")
  ),
  notes = "Analytical SEs (HC1 robust) in parentheses. Bootstrap SE: 1,000 reps. See text for discussion of hours/household and job-attribute controls as potential 'bad controls'.",
  notes.append = FALSE
)

# ==============================================================================
# 7. Perfiles Edad-Ingreso por Sexo y Estimacion de Peak Age
# ==============================================================================

message("Estimando modelo interactivo para perfiles edad-ingreso por sexo...")

m_perfil <- lm(ln_y_total_m ~ female * (age + age_sq) + cat_educ +
                 totalHoursWorked + num_minors, data = df)

# Funcion para calcular peak age: argmax log(w) respecto a la edad
calc_peaks <- function(model) {
  b <- coef(model)
  peak_men   <- -b["age"] / (2 * b["age_sq"])
  peak_women <- -(b["age"] + b["female:age"]) / (2 * (b["age_sq"] + b["female:age_sq"]))
  return(c(peak_men = unname(peak_men), peak_women = unname(peak_women)))
}

peaks_point <- calc_peaks(m_perfil)

# --- Chequeo de concavidad y de rango observado ------------------------------
# La formula del vertice solo identifica un MAXIMO si el coeficiente
# cuadratico es negativo. Ademas, un peak fuera del rango observado de edad
# es una extrapolacion que debe reportarse con cautela.
b_perfil <- coef(m_perfil)
age_sq_men   <- b_perfil["age_sq"]
age_sq_women <- b_perfil["age_sq"] + b_perfil["female:age_sq"]

check_peak <- function(age_sq_coef, peak, label) {
  if (is.na(age_sq_coef) || age_sq_coef >= 0) {
    warning(sprintf(
      "El coeficiente de age_sq para %s es >= 0: la relacion es convexa, el punto calculado es un MINIMO, no un peak.",
      label))
  }
  if (!is.na(peak) && (peak < min(df$age, na.rm = TRUE) || peak > max(df$age, na.rm = TRUE))) {
    warning(sprintf(
      "La edad pico implicita para %s (%.1f) esta fuera del rango observado [%d, %d]: es una extrapolacion.",
      label, peak, min(df$age, na.rm = TRUE), max(df$age, na.rm = TRUE)))
  }
}
check_peak(age_sq_men, peaks_point["peak_men"], "hombres")
check_peak(age_sq_women, peaks_point["peak_women"], "mujeres")

# Funcion estadistica para el bootstrap con manejo seguro de errores
boot_peak_fn <- function(data, indices) {
  d_b <- data[indices, ]
  tryCatch({
    mod <- lm(ln_y_total_m ~ female * (age + age_sq) + cat_educ +
                totalHoursWorked + num_minors, data = d_b)
    b <- coef(mod)
    peak_men   <- -b["age"] / (2 * b["age_sq"])
    peak_women <- -(b["age"] + b["female:age"]) / (2 * (b["age_sq"] + b["female:age_sq"]))
    c(peak_men = unname(peak_men), peak_women = unname(peak_women))
  }, error = function(e) {
    c(peak_men = NA_real_, peak_women = NA_real_)
  })
}

boot_peaks <- boot(
  data = df, statistic = boot_peak_fn, R = 1000,
  parallel = boot_par, ncpus = boot_ncpus
)

repl_men   <- boot_peaks$t[, 1]
repl_men   <- repl_men[is.finite(repl_men)]

repl_women <- boot_peaks$t[, 2]
repl_women <- repl_women[is.finite(repl_women)]

message(sprintf("Replicas validas para peak age -> hombres: %d/1000, mujeres: %d/1000",
                length(repl_men), length(repl_women)))
stopifnot(
  "No hay suficientes replicas bootstrap validas para calcular el IC del peak age" =
    length(repl_men) > 50 && length(repl_women) > 50
)

ci_peak_men   <- quantile(repl_men, probs = c(0.025, 0.975))
ci_peak_women <- quantile(repl_women, probs = c(0.025, 0.975))

peak_summary_df <- data.frame(
  Group = c("Men", "Women"),
  Peak_Age = round(c(peaks_point["peak_men"], peaks_point["peak_women"]), 2),
  CI_Lower = round(c(ci_peak_men[1], ci_peak_women[1]), 2),
  CI_Upper = round(c(ci_peak_men[2], ci_peak_women[2]), 2)
)

stargazer(
  peak_summary_df,
  summary = FALSE,
  rownames = FALSE,
  type = "latex",
  out = here("02_outputs", "tables", "table_peak_ages_gender.tex"),
  title = "Implied Peak Ages by Gender (Conditional Model)",
  label = "tab:peak_ages_gender"
)

# ==============================================================================
# 8. Grafico de Perfiles Edad-Ingreso Predichos por Sexo (con IC del peak age)
# ==============================================================================

grid_age <- tibble(
  age = rep(seq(18, 65, by = 1), 2),
  female = rep(c(0, 1), each = length(seq(18, 65, by = 1)))
) |>
  mutate(
    age_sq = age^2,
    cat_educ = factor("Secondary_Complete", levels = levels(df$cat_educ)),
    totalHoursWorked = mean(df$totalHoursWorked, na.rm = TRUE),
    num_minors = median(df$num_minors, na.rm = TRUE)
  )

pred_obj <- predict(m_perfil, newdata = grid_age, se.fit = TRUE)
grid_age <- grid_age |>
  mutate(
    pred_ln_y = pred_obj$fit,
    ci_lo = pred_ln_y - 1.96 * pred_obj$se.fit,
    ci_hi = pred_ln_y + 1.96 * pred_obj$se.fit,
    Gender = ifelse(female == 1, "Women", "Men")
  )

fig_profiles <- ggplot(grid_age, aes(x = age, y = pred_ln_y, color = Gender, fill = Gender)) +
  # Bandas de IC del peak age (fondo, para no tapar las curvas)
  annotate("rect", xmin = ci_peak_men[1], xmax = ci_peak_men[2],
           ymin = -Inf, ymax = Inf, fill = "#1f77b4", alpha = 0.08) +
  annotate("rect", xmin = ci_peak_women[1], xmax = ci_peak_women[2],
           ymin = -Inf, ymax = Inf, fill = "#e377c2", alpha = 0.08) +
  geom_ribbon(aes(ymin = ci_lo, ymax = ci_hi), alpha = 0.18, color = NA) +
  geom_line(linewidth = 1.1) +
  geom_vline(xintercept = peaks_point["peak_men"], linetype = "dashed", color = "#1f77b4", linewidth = 0.7) +
  geom_vline(xintercept = peaks_point["peak_women"], linetype = "dashed", color = "#e377c2", linewidth = 0.7) +
  scale_color_manual(values = c("Men" = "#1f77b4", "Women" = "#e377c2")) +
  scale_fill_manual(values = c("Men" = "#1f77b4", "Women" = "#e377c2")) +
  labs(
    title = "Predicted Age-Labor Income Profiles by Gender",
    subtitle = "Shaded bands = 95% bootstrap CI of the implied peak age",
    x = "Age",
    y = "Predicted Log Labor Income",
    color = "Gender",
    fill = "Gender"
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

ggsave(
  filename = here("02_outputs", "figures", "fig_gender_age_profiles.png"),
  plot = fig_profiles,
  width = 8,
  height = 5.2,
  dpi = 300
)

message("Seccion 2 completada. Tablas y graficos exportados en 02_outputs/")