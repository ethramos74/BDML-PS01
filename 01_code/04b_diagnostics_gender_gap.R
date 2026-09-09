# ==============================================================================
# Archivo:   01_code/04b_diagnostics_gender_gap.R
# Proposito: Diagnostico de regresion y analisis de sensibilidad para la
#            especificacion preferida de la Seccion 2 (Modelo 3), siguiendo el
#            procedimiento de la complementaria C2 (outliers, leverage e
#            influencia): separar las dos nociones, caracterizar a quienes
#            cumplen ambas condiciones y reportar cuanto se mueve la brecha
#            al excluirlos.
# Input:     02_outputs/data_geih_cleaned.rds
# Output:    02_outputs/tables/table_gender_gap_robustness.tex
#            02_outputs/figures/fig_leverage_influence.png
# ==============================================================================

# 1. Dependencias
if (!require(pacman)) install.packages("pacman")
pacman::p_load(
  tidyverse,  # Manipulacion de datos y graficos
  rio,        # Importacion/exportacion
  here,       # Rutas relativas
  MASS,       # studres(): residuos estudentizados
  sandwich,   # Errores estandar robustos (HC1)
  stargazer,  # Exportacion de tablas en LaTeX
  conflicted  # Resolver conflictos entre funciones homonimas
)
conflict_prefer(name = "select", winner = "dplyr")
conflict_prefer(name = "filter", winner = "dplyr")
options(scipen = 999)

dir.create(here("02_outputs", "tables"), recursive = TRUE, showWarnings = FALSE)
dir.create(here("02_outputs", "figures"), recursive = TRUE, showWarnings = FALSE)

# 2. Cargar datos limpios y reestimar la especificacion preferida
data_path <- here("02_outputs", "data_geih_cleaned.rds")
if (!file.exists(data_path)) {
  stop("No se encuentra 'data_geih_cleaned.rds'. Corre primero 02_cleaning.R")
}
df <- rio::import(data_path)

# Modelo 3 de 04_gender_gap.R: capital humano + oferta laboral y hogar.
formula_m3 <- ln_y_total_m ~ female + age + age_sq + cat_educ +
  totalHoursWorked + num_minors

m3_oferta <- lm(formula = formula_m3, data = df)

# ==============================================================================
# 3. Leverage: valores inusuales de los regresores
# ==============================================================================
# El leverage h_ii es el i-esimo elemento de la diagonal de la matriz de
# proyeccion, h_ii = x_i'(X'X)^{-1}x_i. Depende solo de X, no de y: mide que
# tan lejos esta el vector de regresores del individuo i respecto al resto de
# la muestra.

df <- df |>
  mutate(num_leverage = hatvalues(m3_oferta))

num_meanLeverage <- mean(df$num_leverage)
corte_leverage   <- 3 * num_meanLeverage

message(sprintf("Leverage promedio: %.5f | corte (3 x promedio): %.5f",
                num_meanLeverage, corte_leverage))
message(sprintf("Leverage maximo observado: %.5f", max(df$num_leverage)))

# El leverage esta acotado por 1, y el caso extremo ocurre cuando una dummy
# identifica a una unica observacion: el modelo la ajusta de forma exacta. Eso
# pasaba antes de fundir las categorias residuales de relab en 02_cleaning.R, y
# era lo que degeneraba el estimador HC1, que pondera por 1 / (1 - h_ii).
stopifnot(max(df$num_leverage) < 0.99)

# ==============================================================================
# 4. Outliers: resultados inusuales condicionales en los regresores
# ==============================================================================
# Los residuos crudos no son comparables entre si porque su varianza depende
# del leverage. Se usan residuos estudentizados, que reescalan cada residuo con
# una estimacion leave-one-out de su desviacion estandar.

df <- df |>
  mutate(num_studresid = studres(m3_oferta))

corte_outlier <- 3   # regla de dedo de la complementaria

# ==============================================================================
# 5. Influencia: leverage alto Y residuo grande
# ==============================================================================
# Ninguna de las dos condiciones basta por si sola. Al omitir la observacion i,
#
#   beta_hat - beta_hat_(-i) = ( e_i / (1 - h_ii) ) * (X'X)^{-1} x_i
#
# de modo que el leverage amplifica el residuo. Un punto lejano en X con
# residuo cercano a cero no mueve la estimacion, y un residuo grande con
# leverage bajo tampoco.

df <- df |>
  mutate(
    bin_leverageAlto = num_leverage > corte_leverage,
    bin_outlier      = abs(num_studresid) > corte_outlier,
    bin_influyente   = bin_leverageAlto & bin_outlier
  )

message("Cruce entre leverage alto y outlier:")
print(table(leverage_alto = df$bin_leverageAlto, outlier = df$bin_outlier))

# ==============================================================================
# 6. Quienes son las observaciones influyentes?
# ==============================================================================
# El paso siguiente no es borrarlas, sino entender por que son distintas y si
# sus valores son plausibles. Si lo son, el problema puede estar en la
# especificacion (una no linealidad o una interaccion omitida) y no en el dato.

perfil_influyentes <- df |>
  group_by(bin_influyente) |>
  summarise(
    n                = n(),
    ingreso_mediano  = median(y_total_m),
    ingreso_medio    = mean(y_total_m),
    edad_media       = mean(age),
    horas_medias     = mean(totalHoursWorked),
    prop_mujeres     = mean(female),
    prop_tertiary    = mean(cat_educ == "Tertiary"),
    .groups = "drop"
  )

message("Perfil de las observaciones influyentes frente al resto:")
print(perfil_influyentes)

# ==============================================================================
# 7. Analisis de sensibilidad
# ==============================================================================
# Se reestima la misma especificacion sobre dos submuestras: la que excluye las
# observaciones que cumplen ambas condiciones, y una mas agresiva que excluye
# todas las que superan el umbral convencional de la distancia de Cook (4/n).
# La segunda sirve como cota superior del movimiento posible.

df <- df |>
  mutate(num_cook = cooks.distance(m3_oferta))

corte_cook <- 4 / nobs(m3_oferta)

m3_sinInfluyentes <- lm(formula = formula_m3,
                        data = filter(df, !bin_influyente))
m3_sinCook        <- lm(formula = formula_m3,
                        data = filter(df, num_cook <= corte_cook))

se_full     <- sqrt(diag(vcovHC(m3_oferta,         type = "HC1")))
se_sinInfl  <- sqrt(diag(vcovHC(m3_sinInfluyentes, type = "HC1")))
se_sinCook  <- sqrt(diag(vcovHC(m3_sinCook,        type = "HC1")))

# En un modelo log-lin el efecto porcentual exacto de un dummy es
# 100 * (exp(beta) - 1), no 100 * beta.
pct_effect <- function(beta) 100 * (exp(beta) - 1)

reportar_brecha <- function(etiqueta, modelo, errores) {
  beta <- coef(modelo)["female"]
  message(sprintf("  %-22s n = %5d | beta = %.4f (%.2f%%) | SE(HC1) = %.4f",
                  etiqueta, nobs(modelo), beta, pct_effect(beta),
                  errores["female"]))
}

message("Sensibilidad de la brecha de genero:")
reportar_brecha("Muestra completa",   m3_oferta,         se_full)
reportar_brecha("Sin influyentes",    m3_sinInfluyentes, se_sinInfl)
reportar_brecha("Sin Cook > 4/n",     m3_sinCook,        se_sinCook)

# Un cambio importante es evidencia de sensibilidad, no evidencia de que la
# estimacion restringida sea la correcta. Las observaciones excluidas son parte
# legitima de la poblacion de interes, asi que la especificacion reportada en
# la Seccion 2 sigue siendo la de muestra completa.

# ==============================================================================
# 8. Tabla comparativa (LaTeX)
# ==============================================================================

stargazer(
  m3_oferta, m3_sinInfluyentes, m3_sinCook,
  type = "latex",
  out = here("02_outputs", "tables", "table_gender_gap_robustness.tex"),
  title = "Sensitivity of the Gender Gap to Influential Observations",
  label = "tab:gender_gap_robustness",
  dep.var.labels = "Log Monthly Labor Income",
  column.labels = c("Full sample", "Excl. influential", "Excl. Cook"),
  keep = c("female"),
  keep.stat = c("n", "rsq", "adj.rsq"),
  se = list(se_full, se_sinInfl, se_sinCook),
  add.lines = list(
    c("Dropped observations", "--",
      sum(df$bin_influyente), sum(df$num_cook > corte_cook)),
    c("Exclusion rule", "--",
      "High leverage and $|t| > 3$", "Cook's D $>$ 4/n")
  ),
  notes = "All columns estimate the preferred specification (M3). HC1 robust SEs in parentheses. Columns (2) and (3) are sensitivity checks, not the reported specification.",
  notes.append = FALSE
)

# ==============================================================================
# 9. Grafico: leverage frente a residuo estudentizado
# ==============================================================================
# Las lineas punteadas parten el plano en los casos que interesa distinguir:
# leverage alto sin residuo grande, residuo grande sin leverage, y la esquina
# donde coinciden ambos, que es la unica con capacidad de mover el modelo.

fig_diag <- ggplot(data = df,
                   mapping = aes(x = num_leverage, y = num_studresid)) +
  geom_point(aes(color = bin_influyente), alpha = 0.4, size = 1.2) +
  geom_hline(yintercept = c(-corte_outlier, corte_outlier),
             linetype = "dashed", color = "#D55E00") +
  geom_vline(xintercept = corte_leverage,
             linetype = "dashed", color = "#D55E00") +
  scale_color_manual(
    values = c("FALSE" = "grey55", "TRUE" = "#0072B2"),
    labels = c("FALSE" = "Resto de la muestra",
               "TRUE"  = "Leverage alto y |t| > 3"),
    name = NULL
  ) +
  labs(
    x = expression(paste("Leverage (", h[ii], ")")),
    y = "Residuo estudentizado",
    caption = sprintf(
      "Nota. Lineas punteadas: |t| = 3 y leverage = 3 veces el promedio (%.4f).",
      corte_leverage)
  ) +
  theme_classic() +
  theme(legend.position = "bottom")

ggsave(
  filename = here("02_outputs", "figures", "fig_leverage_influence.png"),
  plot = fig_diag,
  width = 8,
  height = 5.2,
  dpi = 300
)

message("Diagnostico completado. Tabla y figura exportadas en 02_outputs/")
