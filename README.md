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

El script maestro descarga los datos, construye la muestra de análisis y corre las secciones en orden, escribiendo todas las figuras y tablas a `02_outputs/`. No requiere intervención manual ni correr scripts sueltos.

El scraping se omite automáticamente si `02_outputs/data_geih_consolidada.rds` ya existe, así que reejecutar el pipeline no vuelve a golpear el servidor de la fuente.

## Estructura del código

La estructura del repositorio sigue la plantilla provista para el curso ([ignaciomsarmiento/PS_Repo](https://github.com/ignaciomsarmiento/PS_Repo)).

| Script | Responsabilidad |
|---|---|
| `00_rundirectory.R` | Script maestro. Corre todo el pipeline en orden. |
| `01_scraping.R` | Descarga los 10 chunks de la GEIH desde https://ignaciomsarmiento.github.io/GEIH2018_sample/ y los consolida en una sola base. |
| `02_cleaning.R` | Aplica los filtros muestrales y las decisiones de limpieza. Produce la base única que usan las tres secciones. |
| `03_estimate_age_income_profile.R` | Sección 1. Perfil edad–ingreso incondicional y condicional; edad pico e intervalo bootstrap. *(pendiente)* |
| `04_gender_gap.R` | Sección 2. Brecha de género incondicional y condicional (con discusión de good/bad controls), descomposición FWL, errores analíticos (HC1) y bootstrap, perfiles edad-ingreso por sexo. |
| `04b_diagnostics_gender_gap.R` | Sección 2. Diagnóstico de regresión (leverage, residuos estudentizados) y análisis de sensibilidad de la brecha a las observaciones influyentes. |
| `05_evaluate_prediction_models.R` | Sección 3. Split train/validation, RMSE de todas las especificaciones, LOOCV e importancia de variables. *(pendiente)* |

Las llamadas a los scripts pendientes están comentadas en `00_rundirectory.R` y se descomentan cuando el script correspondiente exista.

## Muestra y decisiones de limpieza

**Fuente:** GEIH 2018, muestra de Bogotá del reporte de *Medición de Pobreza Monetaria y Desigualdad* (DANE). Distribuida en 10 chunks.

**Variable de resultado:** `y_total_m` — ingreso laboral mensual total, salarial más cuenta propia. Todas las especificaciones usan su logaritmo.

**Restricciones muestrales:** individuos que reportan estar empleados (`ocu == 1`) y tienen 18 años o más, con ingreso laboral y horas trabajadas estrictamente positivos. La muestra final es de **14,764 observaciones** de las 32,177 originales.

Las decisiones de limpieza se aplican una sola vez en `02_cleaning.R` y quedan justificadas en comentarios ahí mismo, para que todas las secciones trabajen sobre exactamente la misma muestra.

Los ingresos en cero y los faltantes se excluyen con `y_total_m > 0`: el modelo es log-lineal y el logaritmo de cero no está definido. Quienes reportan cero son en su mayoría trabajadores sin remuneración, que no pertenecen a la población de interés.

`num_minors` se calcula sobre la estructura completa del hogar antes de filtrar por adultos ocupados. Contarlo después subestimaría la carga de cuidado, porque los menores mismos quedan fuera de la muestra.

Las categorías 8 (jornalero/peón) y 9 (otro) de `relab` suman 9 personas y se funden en una sola categoría `Otro`. Una dummy que identifica a un único individuo lo ajusta de forma exacta: su leverage tiende a 1 y su residuo a cero, de modo que el estimador HC1, que pondera por `1/(1 - h_ii)`, se vuelve singular. Por la misma razón se aplica `droplevels()`: los factores se declaran con los niveles del diccionario oficial, pero tras los filtros varios quedan sin observaciones.

Los outliers de ingreso no se recortan ni se winsorizan. `04b_diagnostics_gender_gap.R` los caracteriza y mide cuánto se mueve la brecha al excluirlos; la especificación reportada sigue siendo la de muestra completa.

## Diagnóstico de la Sección 2

Siguiendo la complementaria C2, el diagnóstico separa leverage alto (`h_ii` mayor a tres veces el promedio) de outliers (residuo estudentizado con `|t| > 3`), y trata como influyentes solo a las observaciones que cumplen ambas condiciones. De las 14,764 observaciones, 263 tienen leverage alto sin ser outliers, 202 son outliers sin leverage alto, y **6 cumplen ambas**.

Esas 6 son personas de 74 a 84 años con ingresos entre 5 y 21 millones mensuales, cinco de seis hombres y cinco de seis con educación terciaria. Son valores plausibles —empleadores y profesionales en edad de jubilación que siguen trabajando—, no errores de digitación, así que no hay razón para eliminarlos. Excluirlos mueve la brecha de −0.222 a −0.221. El corte más agresivo por distancia de Cook (`> 4/n`, 836 observaciones) la lleva a −0.181, y sirve como cota del movimiento posible.

## Salidas

Todo en `02_outputs/`, generado automáticamente:

- `figures/` — visualizaciones en `.png`
- `tables/` — tablas de estimación en `.tex`

## Software

- R 4.6.0
- Dependencias cargadas con `pacman::p_load()` al inicio de cada script, así que se instalan solas si faltan.

| Paquete | Uso |
|---|---|
| `tidyverse` | Manipulación de datos y gráficos |
| `rvest`, `polite` | Scraping de los chunks de la GEIH |
| `rio`, `here` | Importación/exportación y rutas relativas a la raíz |
| `sandwich`, `lmtest` | Errores estándar robustos HC1 e inferencia |
| `MASS` | Residuos estudentizados para el diagnóstico de regresión |
| `conflicted` | Resolución explícita de funciones homónimas |
| `boot` | Bootstrap no paramétrico (1,000 repeticiones, paralelizado) |
| `stargazer` | Exportación de tablas a LaTeX |

El bootstrap usa `set.seed(202602)` y se paraleliza con `multicore` en macOS/Linux y `snow` en Windows, así que los resultados son reproducibles en cualquier máquina.
