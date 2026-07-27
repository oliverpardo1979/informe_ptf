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
node scripts/validate_ptf_weights.mjs
node scripts/build_calculation_workbooks.mjs
python scripts/build_ptf_data.py
python scripts/build_ptf_paper_figures.py
```

El primer script extrae las series de las nueve actividades y del total de la
economía bajo el enfoque de producción, así como la serie agregada del enfoque
de valor agregado. También recupera las ponderaciones anuales de Törnqvist,
verifica que reproduzcan las trece columnas publicadas por el DANE y calcula la
contribución de cada actividad a la PTF total. El segundo construye los
ponderadores directos como el promedio de las participaciones del valor bruto
de producción nominal en dos años consecutivos y los compara con los pesos
implícitos. El tercero agrega a los dos anexos originales seis hojas con los
cálculos, la validación y la trazabilidad de las figuras, sin modificar los
cuadros del DANE. Los dos scripts de Python construyen los indicadores,
contrafactuales, cuadros y figuras del informe y del paper.

La validación directa usa los cuadros oferta-utilización a precios corrientes
de 2005--2013 y 2014--2024, conservados en `data/raw`. Entre 2006 y 2024, la
diferencia máxima entre el ponderador directo y el implícito es de 0,00031
puntos porcentuales. Para 2005 se conserva el peso implícito porque el promedio
de Törnqvist exige la producción nominal de 2004 y la serie pública con base
2015 comienza en 2005.

Los cálculos sectoriales usan los cuadros anuales del enfoque de producción y
el bloque macroeconómico usa el Cuadro 1 del enfoque de valor agregado. El
análisis sectorial encadena las 20 tasas logarítmicas de 2005--2024 y compara
los niveles de 2004 y 2024. El bloque de valor agregado incluye además la tasa
preliminar de 2025: encadena 21 tasas y compara los niveles de 2004 y 2025. En
ambos casos, la observación rotulada 2005 mide el crecimiento entre 2004 y
2005 y se incluye como el primer año.

Los documentos principales son:

- `main.tex`: informe técnico.
- `paper.tex`: paper académico en inglés, preparado para Overleaf.
- `comunicado_prensa_ptf.tex`: comunicado de prensa.

El PDF compilado del paper se conserva en
`Paper/Pardo_Orozco_SectoralTFP_Colombia.pdf`.
