# Pipeline de datos — Problem Set 1 (GEIH 2018, Bogotá)

Tres scripts de R, ejecutados en orden, llevan los datos desde el sitio del curso hasta una única muestra de análisis que usan las tres secciones del problem set. Cada script es autocontenido, deja un rastro de auditoría en CSV y puede cargarse solo con sus funciones (`options(geih.<accion> = FALSE)` antes de `source()`).

| Script | Qué hace | Entrada | Salida principal | Dependencias |
|---|---|---|---|---|
| `01_obtener_datos_GEIH2018.R` | Descarga los 10 bloques del sitio (con caché local y reintentos), verifica cada tabla y consolida la base **como texto**, sin tocar valores | Web del curso | `datos/brutos/geih2018_original.rds` (32,177 × 181) | curl, xml2, rvest |
| `02_validar_datos_GEIH2018.R` | Corre cerca de 80 pruebas sobre estructura, procedencia, contenido, llaves, códigos, diccionarios (curso y DANE), identidades entre variables y comparabilidad entrenamiento/validación; crea la copia con tipos numéricos | `geih2018_original.rds` | `datos/intermedios/geih2018_tipado.rds` y `auditoria/validacion/*.csv` | solo R base |
| `03_limpiar_datos_GEIH2018.R` | Fija la muestra de análisis (ocupados 18+ con ingreso positivo observado), construye variables y factores, marca extremos y documenta cada columna | `geih2018_tipado.rds` | `datos/limpios/geih2018_muestra.rds` (14,764 × 54) y `datos/limpios/geih2018_ocupados18.rds` (16,542 × 56) | dplyr ≥ 1.0 |

## Ruta del proyecto

Los tres scripts resuelven la carpeta raíz `PS1_GEIH2018` de la misma forma: primero la variable de entorno `PS1_GEIH2018_DIR` (si está definida) y, si no, la subcarpeta `PS1_GEIH2018` del directorio de trabajo. Con el proyecto de RStudio abierto en la carpeta `Taller 1` no hay que editar ninguna ruta. Quien quiera trabajar desde otro sitio agrega una línea a su `.Renviron`, por ejemplo `PS1_GEIH2018_DIR=C:/Users/nombre/OneDrive - Universidad de los Andes/202602 - BigData/Taller 1/PS1_GEIH2018`, y reinicia R.

## Estructura de carpetas que producen

```
PS1_GEIH2018/
├── datos/
│   ├── html/          copias de las páginas descargadas (caché del script 01)
│   ├── brutos/        bloque_01..10.rds y geih2018_original.rds (texto)
│   ├── intermedios/   geih2018_tipado.rds (numérico, sin filtros)
│   └── limpios/       geih2018_muestra.rds y geih2018_ocupados18.rds
├── documentacion/     diccionario y etiquetas del curso (rds/csv) y
│                      diccionario_dane_geih2018_variables.csv (catálogo DANE 547)
└── auditoria/
    ├── manifiesto.csv, resumen_bloques.csv, esquema_columnas.csv   (script 01)
    ├── validacion/    resultados_validacion.csv, perfil_columnas.csv, ...  (script 02)
    └── limpieza/      embudo_muestra.csv, exclusiones_por_motivo.csv, alertas.csv,
                       oficios_agrupados.csv, descriptivas_muestra.csv,
                       diccionario_variables.csv                        (script 03)
```

Para que el script 02 cruce los códigos observados con las categorías oficiales del DANE (prueba 6.5), copie `diccionario_dane_geih2018_variables.csv` en `documentacion/`. Si el archivo no está, la prueba queda como advertencia y todo lo demás corre igual.

## Cómo usar la muestra en las secciones

```r
muestra <- readRDS(file.path(carpeta_proyecto_geih(), "datos", "limpios", "geih2018_muestra.rds"))
```

La variable dependiente es `log_y` (= `log(y_total_m)`), `female` es la dummy de mujer, `age` la edad y `totalHoursWorked` las horas semanales. Los controles categóricos ya son factores con etiquetas y sin niveles vacíos: `relab_f`, `oficio_f`, `oficio_grupo`, `educ_f`, `estrato_f`, `sizeFirm_f`, `mes_f`. La partición de la sección 3 es `muestra_ps3` (`entrenamiento` = bloques 1–7, `validacion` = 8–10) o la lógica `entrenamiento`. Para robustez sin valores extremos, `dplyr::filter(muestra, !alerta_extremo)`. Para robustez con la imputación del DANE de quienes no reportaron monto, la base ampliada `geih2018_ocupados18.rds` trae `impaes` y `dane_faltante`.

## Decisiones de limpieza (resumen; el detalle está en el encabezado del script 03)

La población es la que exige el enunciado: ocupados (`ocu == 1`) de 18 años o más. De ellos, 1,778 no tienen `y_total_m` y quedan fuera de la muestra principal pero dentro de la base ampliada con un `motivo_exclusion`: 248 son trabajadores sin remuneración (no tienen ingreso por definición) y 1,530 son asalariados con `p6500 = 0` o independientes con `p6750` vacío que sí tienen empleo remunerado pero no reportaron el monto; el DANE los marca como faltantes y les imputa. No se imputa nada. No se recorta ni se winsoriza: se crean banderas (`alerta_ingreso_bajo`, `alerta_ingreso_alto`, `alerta_horas_altas`, `alerta_dane_extremo`, y su unión `alerta_extremo`) con umbrales configurables. `college` de la fuente se descarta porque marca secundaria completa, no terciaria; se reemplaza por `terciaria`. Los oficios con menos de 20 personas se agrupan en "Otros" para que todo nivel de validación exista en entrenamiento, y `relab` 8 y 9 (9 personas) se funden en "Otro". No se ponderan los modelos; `fex_c` se conserva para descriptivas de Bogotá.

## Hechos de los datos que condicionan el análisis

Los bloques siguen el calendario de la encuesta (bloque 1 = enero–febrero, bloque 10 = noviembre–diciembre), así que la partición de la sección 3 es temporal y no aleatoria, aunque las descriptivas por partición son muy parecidas. `y_total_m` es exactamente `y_ingLab_m + y_gananciaIndep_m` y nadie tiene ambos componentes; nunca vale cero. El ingreso por hora del sitio es `y_total_m / (totalHoursWorked × 30/7)`. `totalHoursWorked` es la suma de las horas normales del empleo principal (`p6800`) y las horas efectivas del segundo empleo (`p7045`). Ningún código especial del cuestionario (98/99 en montos, 998/999 en antigüedad) sobrevive en los datos. En `p6050`, `p6870` y `relab` el 9 es una categoría válida; en las demás variables con 9 es "no sabe" y se trata como NA. `sex` viene recodificada (1 hombre, 0 mujer). `ESC` (años de escolaridad del DANE) y `RAMA2D` (sector) no están en la muestra del curso.
