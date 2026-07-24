# Productividad Total de los Factores por actividad económica

Informe del Centro Javeriano de Competitividad sobre la evolución de la
Productividad Total de los Factores en Colombia entre 2005 y 2024. El análisis
encadena las variaciones anuales del enfoque de producción y descompone la PTF
del total de la economía entre nueve actividades económicas.

## Reproducibilidad

La fuente primaria se conserva en
`data/raw/anex-PTF-Productividad-2025.xlsx`. Para reconstruir las bases
procesadas, los cuadros y las figuras:

```powershell
node scripts/extract_ptf_workbook.mjs
python scripts/build_ptf_data.py
```

El primer script extrae las series de las nueve actividades y del total de la
economía. También recupera las ponderaciones anuales de Törnqvist, verifica que
reproduzcan las trece columnas publicadas por el DANE y calcula la contribución
de cada actividad a la PTF total. El segundo script construye los indicadores
de largo plazo y genera los cuadros y figuras.

Los cálculos usan los cuadros anuales del enfoque de producción. El cambio
entre los niveles de 2005 y 2024 se construye con las 19 variaciones
logarítmicas correspondientes a 2006--2024; por tanto, no se incluye la
variación 2004--2005 que aparece bajo el rótulo 2005.

Los documentos principales son:

- `main.tex`: informe técnico.
- `comunicado_prensa_ptf.tex`: comunicado de prensa.
