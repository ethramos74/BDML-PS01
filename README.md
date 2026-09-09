# Problem Set 1: Predicting Income

Big Data and Machine Learning para Economía Aplicada, MECA 4107, 2026-20. Equipo 02.

[Repositorio](https://github.com/SebastianVela/BigData_Taller_1) · [Enunciado](Problem_Set_1.pdf)

## Desarrollo actual

| Sección | Cuaderno ejecutado | Lectura en HTML |
|---|---|---|
| Datos: obtención, validación y limpieza | [Datos](datos/01_datos_obtencion_validacion_limpieza.ipynb) | [HTML de datos](datos/01_datos_obtencion_validacion_limpieza.html) |
| Perfil edad-ingreso | [Edad](punto1_perfil_edad_ingreso/punto1_perfil_edad_ingreso.ipynb) | [HTML de edad](punto1_perfil_edad_ingreso/punto1_perfil_edad_ingreso.html) |
| Brecha de género | [Género](punto2_brecha_genero/punto2_brecha_genero.ipynb) | [HTML de género](punto2_brecha_genero/punto2_brecha_genero.html) |
| Predicción: MCO y ridge | [Predicción](punto3_prediccion_ingreso/punto3_prediccion_ingreso_laboral.ipynb) | [HTML de predicción](punto3_prediccion_ingreso/punto3_prediccion_ingreso_laboral.html) |

Los HTML incluyen resultados, ecuaciones y figuras. Las tablas principales se guardan como CSV y LaTeX (.tex), con precisión completa en los CSV.

Esta revisión comprende cuadernos, código, tablas y gráficas. Los PDF y las notas de `slides/` pertenecen a la versión anterior y están pendientes de actualización; no representan las cifras de esta revisión. La ejecución principal no genera diapositivas.

## Ejecución reproducible

Python 3.11 a 3.13. Desde la raíz:

```bash
python -m venv .venv
# Windows PowerShell
.venv/Scripts/Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

La ejecución completa procesa datos, edad, género y predicción, y termina con las pruebas. También se puede ejecutar una sección:

```bash
python main.py --etapa datos
python main.py --etapa edad
python main.py --etapa brecha
python main.py --etapa prediccion
python main.py --etapa verificar
```

Los cuadernos son procesos independientes y no necesitan una sesión abierta de Jupyter. Las semillas de remuestreo y particiones son 2026. El ajuste predictivo con selección de grupos puede tardar varios minutos; el tiempo depende del equipo. Las versiones directas están fijadas en [requirements.txt](requirements.txt).

## Datos y ponderación

Se conservan los diez bloques del [sitio del curso](https://ignaciomsarmiento.github.io/GEIH2018_sample/), con 32,177 filas. La muestra principal contiene 14,764 ocupados de 18 años o más con ingreso laboral mensual positivo observado. Género y predicción excluyen un caso sin educación y comparan todas sus especificaciones en la misma muestra de 14,763 registros.

Se usa `fex_c` para que descriptivas y modelos de edad y género representen la población cubierta de Bogotá, en vez de la distribución de filas de la muestra. No recupera automáticamente la población que no reporta ingreso. Los coeficientes se estiman por mínimos cuadrados ponderados; se reportan covarianzas analíticas HC1 e intervalos bootstrap percentiles. Los pesos viajan con la fila remuestreada y se vuelven a aplicar al estimador. Esta aproximación por personas no reproduce todos los estratos y conglomerados del diseño DANE.

Cada estimación ponderada informa cuántos registros utiliza y cuántas personas representan, sumando `fex_c` sin normalizarlo. Las tablas de subgrupos y particiones conservan sus propios totales. No se reporta un IC del total de personas porque el archivo no contiene el diseño de muestreo completo ni pesos replicados que permitan estimar su varianza de diseño. Esto no equivale a incertidumbre cero. Los intervalos de medias, coeficientes y picos tienen un objeto distinto. La documentación de [totales de encuestas](https://search.r-project.org/CRAN/refmans/survey/html/surveysummary.html) describe esta distinción. Los totales de entrenamiento y validación son contribuciones a la expansión del archivo, no dos estimaciones independientes de toda Bogotá.

No se ponderan los conteos de validación, tipos ni porcentajes de no nulos: estos miden integridad y disponibilidad de registros. Las tablas finales de datos cubren todas las columnas de la base consolidada y de la muestra:

- [Resumen de base completa](datos/auditoria/summary_base_completa.csv).
- [Cobertura y tipos de la base completa](datos/auditoria/cobertura_base_completa.csv).
- [Resumen de muestra de análisis](datos/auditoria/summary_muestra_analisis.csv).
- [Diccionario de variables](datos/auditoria/diccionario_muestra.csv).

La descarga reutiliza caché y consulta `robots.txt` antes de nuevas peticiones; respeta una pausa mínima de un segundo o el mayor `crawl-delay` declarado. El registro de la consulta previa documenta HTTP 404, ausencia del archivo. Esa respuesta no constituye una licencia. No se imputan ingresos ni se recortan extremos en el análisis principal.

## Métodos por sección

Edad estima la parábola incondicional y la condicional únicamente en horas y vínculo. El pico es el cociente de los coeficientes lineal y cuadrático. Se reportan método delta y bootstrap percentil de 2,000 réplicas según la lógica de `boot(data, statistic, R)` de la clase, implementada en Python. La comparación muestra ambos perfiles sin descomponer su diferencia. Robustez y heterogeneidad presentan la ecuación estimada en cada variante y el estimador dibujado.

Género muestra medias ponderadas de log-ingreso por edad y sexo con IC puntuales. La escalera S0-S7 explica las proyecciones FWL, la segunda etapa y su inferencia ponderada. Se usa bootstrap de 500 réplicas por modelo, con 1,000 en S5, y percentiles. Los perfiles S1 y S5 interactúan Female con edad y edad², con 1,000 réplicas para los picos. El gráfico identifica las medias de las distribuciones bootstrap. Se conserva la heterogeneidad por subgrupos con formulación matemática.

La figura FWL superpone las pendientes obtenidas por residualización y por el modelo completo ponderado, y compara sus residuos finales con la recta de 45°. Los paneles (a) y (b) de los perfiles por sexo muestran la media bootstrap del pico en S1 y S5; el panel (d) la muestra sobre su distribución bootstrap. Las leyendas identifican sexo y edad en años.

Predicción compara solo MCO y ridge. Incluye las referencias reestimadas, sus variantes ponderadas, polinomios, bases cúbicas por tramos, interacciones, variables laborales y del hogar, y selección hacia adelante, atrás y mixta. Las bases por tramos son transformaciones de regresores; el modelo sigue siendo lineal en coeficientes. Cada especificación y cada columna se documentan en las tablas de resultados.

Se usan bloques 1-7 para ajuste (10,263 personas) y 8-10 para validación (4,500). El ganador minimiza RMSE de validación sin ponderar, conforme al enunciado. `fex_c` no entra como predictor; el RMSE ponderado se reporta como sensibilidad para representar la población cubierta de Bogotá. Los modelos de referencia con sufijo `w` reestiman los análisis poblacionales de las secciones anteriores.

La penalización se selecciona por LOOCV en una malla de 25 valores. Durante la búsqueda de grupos se fija la penalización inicial y luego se vuelve a seleccionar para el subconjunto retenido. Las búsquedas son locales; no se afirma haber enumerado todos los subconjuntos. PRESS es exacto con diseño, escala y penalización fijos. La CV complementaria reconstruye transformaciones y lambda, manteniendo los grupos del ganador; no se denomina CV anidada del procedimiento completo.

La importancia principal mide aumento del RMSE de validación al permutar cada variable y reconstruir sus transformaciones e interacciones (30 repeticiones). Se contrasta con eliminar la variable y reajustar. Dentro de esa sección se muestra cómo responde el modelo a la variable más importante para cubrir el requisito del enunciado. La validación participa en la selección; su mínimo no es un test independiente. Ninguna brecha, curva o discrepancia predictiva identifica por sí sola un efecto causal o evasión tributaria.

## Mapa de código y resultados

| Código principal | Productos |
|---|---|
| `datos/src/geih_datos.py` y cuaderno de datos | `datos/brutos/`, `datos/limpios/`, `datos/auditoria/` |
| `src/numerica.py` | Estimadores estables y covarianzas usados por edad y género |
| `src/reportes.py` | Tablas CSV/LaTeX y medias ponderadas |
| `punto1_perfil_edad_ingreso/src/analisis_edad.py`, `perfil_edad.py` | `punto1_perfil_edad_ingreso/salidas/` |
| `punto2_brecha_genero/src/analisis_brecha.py`, `brecha_genero.py` | `punto2_brecha_genero/salidas/` |
| `punto3_prediccion_ingreso/src/analisis_lineal.py`, `geih_modelos.py` | `punto3_prediccion_ingreso/salidas/` |
| `tests/` | Comparaciones independientes con statsmodels y scikit-learn, remuestreo, selección y cobertura de variables |

La tabla `auditoria_predictores.csv` revisa todo el conjunto disponible; `columnas_modelos.csv` documenta el diseño de cada candidato; `rmse_especificaciones.csv` aplica la regla de selección a toda la tabla. Las trayectorias se guardan en `seleccion_adelante.csv`, `seleccion_atras.csv` y `seleccion_mixto.csv`.

## Referencias

- [Clase de bootstrap del profesor](https://github.com/ignaciomsarmiento/BDML_2026_20/blob/main/Lecture03/Lecture_03_bootstrap.ipynb).
- [Repositorio del curso](https://github.com/ignaciomsarmiento/BDML_2026_20) y secciones complementarias de FWL, validación y ridge.
- [Prevención de fuga de información, scikit-learn](https://scikit-learn.org/1.7/common_pitfalls.html).

## Integrantes

1. __________________________________
2. __________________________________
3. __________________________________
4. __________________________________

El historial debe reflejar contribuciones reales. El enunciado exige cinco contribuciones sustanciales por integrante incorporadas a main; los espacios de nombres no acreditan esa participación.
