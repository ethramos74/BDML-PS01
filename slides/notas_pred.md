# Predicción del ingreso

Tiempo orientativo: 15 minutos para el cuerpo principal. Las páginas señaladas como anexo sirven para preguntas.

## 1. Result Overview

El ganador es el mínimo efectivo de toda la tabla. El universo es explícito y no se afirma que sea el mejor algoritmo posible. 1 minuto.

## 2. Una evaluación fuera de muestra con orden temporal

La validación está formada por bloques 8-10. Explicar que seleccionamos con esos datos y no los llamamos test independiente. 1 minuto.

## 3. Modelos de referencia de las secciones 1 y 2

M4 reproduce la brecha aditiva y M4i su extensión con perfiles por sexo. M0 usa la media de entrenamiento, no la media de validación. 1 minuto.

## 4. Flexibilidad dentro de modelos lineales

Motivar el aumento de flexibilidad: recursos, no linealidades, interacciones, ocupación y contracción. No asignar parsimonia después de conocer el ganador. 1.5 minutos.

## 5. Regularización, árboles y promedio de modelos

Boosting combina árboles pequeños de forma secuencial. La parada temprana se determina dentro del entrenamiento; después se reajusta con todas sus filas. El promedio jackknife combina modelos lineales. 1 minuto.

## 6. Flexibilidad, contracción y error predictivo

Comparar error de ajuste y errores fuera de muestra. No afirmar una descomposición causal sesgo-varianza a partir de una sola curva. 1 minuto.

## 7. LOOCV y validación estiman riesgos diferentes

LOOCV del ganador reajusta un modelo por persona excluida. Fija los hiperparámetros, incluyendo el número de árboles. La CV externa vuelve a determinar la parada temprana. Ninguna corrige haber usado validación para elegir familia. 2 minutos.

## 8. Importancia por permutación conjunta

Permutar conjuntamente las variables redundantes preserva su relación dentro del grupo. Medir cuánto empeoran las predicciones del modelo fijo. La medida depende de correlaciones y no identifica efectos causales. 1.5 minutos.

## 9. Las predicciones dependen de las horas de forma no lineal

PDP modifica las horas y ALE acumula diferencias locales. Ambas son descriptivas y pueden implicar perfiles con escaso soporte conjunto. 1.5 minutos.

## 10. La precisión cambia según el vínculo laboral

Comparar la precisión de asalariados e independientes y señalar el soporte pequeño de algunos vínculos. El error esperado puede variar mucho entre contribuyentes. 1 minuto.

## 11. Un residuo grande requiere corroboración externa

Cerrar respondiendo la pregunta central: el modelo localiza discrepancias, pero no observa evasión. Proponer evaluación externa de falsos positivos y desempeño por grupos. 1 minuto.

## 12. Anexo · Intervalos con calibración separada

Es split conformal con orden finito. La cobertura nominal requiere intercambiabilidad. La muestra temporal y la dependencia de encuesta impiden asumir esa garantía automáticamente.

## 13. Anexo · Incertidumbre en la comparación

Los intervalos condicionan en los ajustes y no corrigen selección ni multiplicidad. Un intervalo que contiene cero no prueba equivalencia.