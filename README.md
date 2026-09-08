# Predicting Individual Labor Income in Bogotá

Modelos de ingreso laboral individual sobre la GEIH 2018 (Bogotá), evaluados en dos dimensiones: qué dicen sobre la estructura del mercado laboral y qué tan bien predicen fuera de muestra.

**Autores:** Ethan Ramos
<!-- Compañeros: agreguen su nombre en esta línea con su propio commit. -->

Big Data & Machine Learning para Economía Aplicada (MECA-4107) — Universidad de los Andes — 2026-20

---

## Pregunta

¿Qué le puede decir un modelo de ingreso laboral a la autoridad tributaria sobre quién podría estar sub-reportando, y dónde se rompen sus predicciones?

El análisis va en tres secciones: el perfil edad–ingreso derivado de teoría de capital humano, la brecha de ingreso por género y la elección de controles, y la comparación de especificaciones por desempeño fuera de muestra.

## Replicación

Desde una sesión de R en la raíz del repositorio:

```r
source("01_code/00_rundirectory.R")
```

El script maestro descarga los datos, construye la muestra de análisis y corre las tres secciones en orden, escribiendo todas las figuras y tablas a `02_outputs/`. No requiere intervención manual ni correr scripts sueltos.

Los datos crudos no se versionan: `01_data_scraper.R` los descarga de la fuente en cada corrida y los deja en `03_temp/`.

## Estructura del código

La estructura del repositorio sigue la plantilla provista para el curso ([ignaciomsarmiento/PS_Repo](https://github.com/ignaciomsarmiento/PS_Repo)).

Los scripts se van agregando a medida que avanza el análisis. En `00_rundirectory.R` cada llamada está comentada hasta que su script existe.

| Script | Responsabilidad |
|---|---|
| `00_rundirectory.R` | Script maestro. Corre todo el pipeline en orden. |
| `01_data_scraper.R` / `01_scraping.R` | Descarga los 10 chunks de la GEIH desde https://ignaciomsarmiento.github.io/GEIH2018_sample/. **Pendiente:** hay dos versiones, falta que el equipo decida cuál queda. |
| `02_cleaning.R` | Aplica los filtros muestrales y las decisiones de limpieza. Produce la base única que usan las tres secciones. |
| `03_estimate_age_income_profile.R` | Sección 1. Perfil edad–ingreso incondicional y condicional; edad pico e intervalo bootstrap. |
| `04_gender_gap.R` | Sección 2. Brecha de género incondicional y condicional (con discusión de good/bad controls), descomposición FWL, errores analíticos (HC1) y bootstrap, perfiles edad-ingreso por sexo. |
| `05_evaluate_prediction_models.R` | Sección 3. Split train/validation, RMSE de todas las especificaciones, LOOCV e importancia de variables. |
| `functions/` | Funciones compartidas entre scripts (bootstrap, formateo de tablas, cálculo de RMSE). |

## Muestra y decisiones de limpieza

**Fuente:** GEIH 2018, muestra de Bogotá del reporte de *Medición de Pobreza Monetaria y Desigualdad* (DANE). Distribuida en 10 chunks.

**Variable de resultado:** `y_total_m` — ingreso laboral mensual total, salarial más cuenta propia. Todas las especificaciones usan su logaritmo.

**Restricciones muestrales:** individuos que reportan estar empleados y tienen 18 años o más.

Las decisiones sobre faltantes, ingresos en cero y observaciones implausibles se aplican una sola vez en `02_build_analysis_sample.R` y quedan justificadas en comentarios ahí mismo, para que las tres secciones trabajen sobre exactamente la misma muestra.

*(Documentar aquí las decisiones una vez tomadas: qué se hizo con los ceros, dónde se cortaron los outliers y por qué.)*

## Salidas

Todo en `02_outputs/`, generado automáticamente:

- `figures/` — visualizaciones en `.png`
- `tables/` — tablas de estimación en `.tex`

Los nombres son autoexplicativos y siguen `snake_case`.

## Software

- R 4.6.0
- Dependencias cargadas con `pacman::p_load()` al inicio de cada script, así que se instalan solas si faltan.

Paquetes principales: `tidyverse`, `rvest`, `boot`, `caret`, `stargazer`.
